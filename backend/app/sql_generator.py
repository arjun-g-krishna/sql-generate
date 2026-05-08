"""
SQLGenerator: builds the prompt, calls the LLM, parses and validates the output.

Supports:
  - Anthropic Claude (via ANTHROPIC_API_KEY)
  - OpenAI GPT-4o (via OPENAI_API_KEY)
  - Local models via Ollama (http://localhost:11434)

Set LLM_PROVIDER in your .env to one of: anthropic (default), openai, ollama
"""

from __future__ import annotations
import os
import re
import json
import logging
import unicodedata
from typing import Optional

import httpx
from app.models import QueryResponse
from app.schema_store import SchemaStore

logger = logging.getLogger(__name__)


class UnsafeSQLValidationError(Exception):
    """Raised when generated SQL violates read-only safety policy."""


# SQL statements that must never appear in generated queries
BLOCKED_KEYWORDS = {
    "DROP",
    "DELETE",
    "UPDATE",
    "INSERT",
    "TRUNCATE",
    "ALTER",
    "CREATE",
    "GRANT",
    "REVOKE",
    "MERGE",
    "CALL",
    "EXECUTE",
    "VACUUM",
    "ANALYZE",
    "COPY",
    "SET",
    "RESET",
}

SYSTEM_PROMPT = """You are an expert SQL assistant. You convert natural language questions into correct, efficient SQL queries.
Rules:
1. Output ONLY a JSON object — no prose, no markdown fences.
2. The JSON must have exactly these keys:
   - "sql": the complete SQL query (SELECT only — never DROP/DELETE/UPDATE/INSERT)
   - "explanation": one sentence describing what the query does
   - "tables_used": list of table names referenced in the query
3. Use standard SQL
4. For date arithmetic, use CURRENT_DATE and interval syntax.
5. If the question is ambiguous, make a reasonable assumption and note it in explanation.
6. Never fabricate column or table names, only use what's in the schema.

Example output:
{"sql": "SELECT c.full_name, SUM(o.total_amount) AS revenue FROM customers c JOIN orders o ON c.customer_id = o.customer_id GROUP BY c.customer_id, c.full_name ORDER BY revenue DESC LIMIT 10;", "explanation": "Returns the top 10 customers by total order revenue.", "tables_used": ["customers", "orders"]}"""


class SQLGenerator:
    def __init__(self, schema_store: SchemaStore):
        self.schema_store = schema_store
        self.provider = os.getenv("LLM_PROVIDER", "anthropic").lower()

        self.anthropic_key = os.getenv("ANTHROPIC_API_KEY", "")
        self.openai_key = os.getenv("OPENAI_API_KEY", "")

    async def generate(self, question: str, top_k_tables: int = 5) -> QueryResponse:
        relevant_tables = self.schema_store.get_relevant_tables(question, top_k=top_k_tables)
        schema_block = self.schema_store.format_schema_prompt(relevant_tables)

        user_message = f"""Database schema (only these tables are available):

{schema_block}

Question: {question}

Respond with a JSON object only."""

        raw = await self._call_llm(user_message)
        return self._parse_response(question, raw, relevant_tables)

    # ------------------------------------------------------------------
    # LLM backends
    # ------------------------------------------------------------------

    async def _call_llm(self, user_message: str) -> str:
        if self.provider == "openai":
            return await self._call_openai(user_message)
        elif self.provider == "ollama":
            return await self._call_ollama(user_message)
        return await self._call_anthropic(user_message)

    async def _call_anthropic(self, user_message: str) -> str:
        if not self.anthropic_key:
            raise ValueError("ANTHROPIC_API_KEY not set. Add it to your .env file.")

        payload = {
            "model": "claude-sonnet-4-20250514",
            "max_tokens": 1024,
            "system": SYSTEM_PROMPT,
            "messages": [{"role": "user", "content": user_message}],
        }
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": self.anthropic_key,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                },
                json=payload,
            )
            resp.raise_for_status()
            data = resp.json()
            return data["content"][0]["text"]

    async def _call_openai(self, user_message: str) -> str:
        if not self.openai_key:
            raise ValueError("OPENAI_API_KEY not set. Add it to your .env file.")

        payload = {
            "model": "gpt-4o",
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_message},
            ],
        }
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                "https://api.openai.com/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.openai_key}",
                    "content-type": "application/json",
                },
                json=payload,
            )
            resp.raise_for_status()
            data = resp.json()
            return data["choices"][0]["message"]["content"]

    async def _call_ollama(self, user_message: str) -> str:
        """Call a local Ollama model running at http://localhost:11434"""
        model = os.getenv("OLLAMA_MODEL", "deepseek-coder")
        
        # Combine system prompt with user message
        full_prompt = f"{SYSTEM_PROMPT}\n\n{user_message}"
        
        payload = {
            "model": model,
            "format": "json",
            "prompt": full_prompt,
            "stream": False,
        }
        
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(
                "http://localhost:11434/api/generate",
                headers={"Content-Type": "application/json"},
                json=payload,
            )
            resp.raise_for_status()
            data = resp.json()
            return data.get("response", "")

    # ------------------------------------------------------------------
    # Response parsing + safety
    # ------------------------------------------------------------------

    def _parse_response(self, question: str, raw: str, relevant_tables) -> QueryResponse:
        # Strip markdown fences if model ignored our instructions
        cleaned = re.sub(r"```(?:json)?|```", "", raw).strip()

        try:
            parsed = json.loads(cleaned, strict=False)
        except json.JSONDecodeError:
            # Last resort: extract anything that looks like a JSON object
            match = re.search(r"\{.*\}", cleaned, re.DOTALL)
            if match:
                try:
                    parsed = json.loads(match.group(), strict=False)
                except json.JSONDecodeError as e:
                    logger.error(f"Unparseable JSON match. Error: {e} | Content: {match.group()}")
                    raise ValueError(f"LLM returned invalid JSON: {e}")
            else:
                logger.error(f"Unparseable LLM response: {raw[:300]}")
                raise ValueError(f"LLM returned non-JSON output: {raw[:200]}")

        sql = parsed.get("sql", "").strip()
        explanation = parsed.get("explanation", "")
        tables_used = parsed.get("tables_used", [t.table_name for t in relevant_tables])
        if isinstance(tables_used, str):
            # The LLM sometimes returns a comma-separated string instead of a list
            tables_used = [t.strip() for t in tables_used.split(",")]
            
        # Enforce hard safety validation; never return unsafe SQL.
        warning = self._safety_check(sql)

        return QueryResponse(
            question=question,
            sql=sql,
            explanation=explanation,
            tables_used=tables_used,
            warning=warning,
        )

    @staticmethod
    def _safety_check(sql: str) -> Optional[str]:
        """
        Enforce strict read-only SQL validation.
        Returns None when SQL is safe; otherwise raises UnsafeSQLValidationError.
        """
        normalized = SQLGenerator._normalize_sql(sql)
        if not normalized:
            raise UnsafeSQLValidationError("Generated SQL is empty.")

        statement = SQLGenerator._remove_string_literals_and_comments(normalized)
        statement = re.sub(r"\s+", " ", statement).strip()

        if not statement:
            raise UnsafeSQLValidationError("Generated SQL contains no executable statement.")

        # Allow only one statement with optional trailing semicolon.
        semicolons = statement.count(";")
        if semicolons > 1 or (semicolons == 1 and not statement.endswith(";")):
            raise UnsafeSQLValidationError("Only a single SQL statement is allowed.")

        bare = statement.rstrip(";").strip()
        if not bare:
            raise UnsafeSQLValidationError("Generated SQL contains no executable statement.")

        starts_with_read = bare.startswith("SELECT ") or bare.startswith("WITH ")
        if not starts_with_read:
            raise UnsafeSQLValidationError("Only read-only SELECT queries are allowed.")

        if "SELECT" not in bare:
            raise UnsafeSQLValidationError("Query must contain a SELECT clause.")

        for keyword in BLOCKED_KEYWORDS:
            # Match as a whole word after removing literals/comments.
            if re.search(rf"\b{keyword}\b", bare):
                raise UnsafeSQLValidationError(
                    f"Blocked SQL operation detected ('{keyword}'). Only read-only queries are allowed."
                )

        # Block common write-intent punctuation outside literal/comment context.
        if "\\" in bare:
            raise UnsafeSQLValidationError("Backslash meta-commands are not allowed.")

        return None

    @staticmethod
    def _normalize_sql(sql: str) -> str:
        """Normalize unicode and uppercase for robust policy matching."""
        normalized = unicodedata.normalize("NFKC", sql)
        return normalized.upper().strip()

    @staticmethod
    def _remove_string_literals_and_comments(sql: str) -> str:
        """
        Remove SQL string literals and comments to prevent keyword bypasses such as:
        DROP /*x*/ TABLE, hidden content in '--', and quoted string tricks.
        """
        # Remove /* ... */ comments
        without_block_comments = re.sub(r"/\*.*?\*/", " ", sql, flags=re.DOTALL)
        # Remove -- ... end-of-line comments
        without_line_comments = re.sub(r"--[^\n]*", " ", without_block_comments)
        # Remove single-quoted string literals (including escaped '')
        without_single_quotes = re.sub(r"'(?:''|[^'])*'", "''", without_line_comments)
        # Remove double-quoted string literals/identifiers
        without_double_quotes = re.sub(r'"(?:\\"|[^"])*"', '""', without_single_quotes)
        return without_double_quotes
