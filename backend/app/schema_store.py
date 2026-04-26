"""
SchemaStore: holds all table definitions and retrieves relevant ones
via cosine similarity on sentence embeddings.

In prod you'd swap this for pgvector + a hosted embedding API.
"""

from __future__ import annotations
import numpy as np
from typing import Optional
from app.models import SchemaInfo, ColumnInfo


def _cosine(a: np.ndarray, b: np.ndarray) -> float:
    return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b) + 1e-9))


class SchemaStore:
    def __init__(self):
        self._tables: dict[str, SchemaInfo] = {}
        self._embeddings: dict[str, np.ndarray] = {}
        self._embed_model = None  # lazy-loaded

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def register_table(self, schema: SchemaInfo):
        self._tables[schema.table_name] = schema
        # Reset cached embedding so it's recomputed on next retrieval
        self._embeddings.pop(schema.table_name, None)

    def get_all_tables(self) -> list[SchemaInfo]:
        return list(self._tables.values())

    def get_relevant_tables(self, question: str, top_k: int = 5) -> list[SchemaInfo]:
        """Return the top-k tables most semantically relevant to the question."""
        if not self._tables:
            return []

        q_emb = self._embed(question)
        scores: list[tuple[float, str]] = []

        for name, table in self._tables.items():
            t_emb = self._get_or_compute_embedding(name, table)
            scores.append((_cosine(q_emb, t_emb), name))

        scores.sort(reverse=True)
        return [self._tables[name] for _, name in scores[:top_k]]

    def format_schema_prompt(self, tables: list[SchemaInfo]) -> str:
        """Format selected tables into a prompt-friendly DDL-style block."""
        parts = []
        for t in tables:
            cols = []
            for c in t.columns:
                flags = []
                if c.is_primary_key:
                    flags.append("PRIMARY KEY")
                if c.is_foreign_key and c.references:
                    flags.append(f"REFERENCES {c.references}")
                if not c.nullable:
                    flags.append("NOT NULL")
                flag_str = " " + " ".join(flags) if flags else ""
                desc_str = f"  -- {c.description}" if c.description else ""
                cols.append(f"  {c.name} {c.type}{flag_str}{desc_str}")

            col_block = ",\n".join(cols)
            parts.append(
                f"-- {t.description}\n"
                f"CREATE TABLE {t.table_name} (\n{col_block}\n);"
            )
        return "\n\n".join(parts)


    # ------------------------------------------------------------------
    # Live Database Introspection
    # ------------------------------------------------------------------

    def load_from_live_db(self, connection_string: str, metadata_config: dict = None):
        """Introspect a live database using SQLAlchemy to populate the SchemaStore."""
        try:
            from sqlalchemy import create_engine, inspect
        except ImportError:
            raise ImportError("SQLAlchemy is required for live database introspection. Run `pip install SQLAlchemy`.")
            
        engine = create_engine(connection_string)
        inspector = inspect(engine)
        metadata_config = metadata_config or {}

        for table_name in inspector.get_table_names():
            columns = []
            pk_constraint = inspector.get_pk_constraint(table_name)
            pks = pk_constraint.get('constrained_columns', [])
            fks = inspector.get_foreign_keys(table_name)
            
            fk_map = {fk['constrained_columns'][0]: f"{fk['referred_table']}.{fk['referred_columns'][0]}" for fk in fks if fk.get('constrained_columns') and fk.get('referred_columns')}

            for col in inspector.get_columns(table_name):
                col_meta = metadata_config.get(table_name, {}).get("columns", {}).get(col['name'], {})
                columns.append(ColumnInfo(
                    name=col['name'],
                    type=str(col['type']),
                    is_primary_key=(col['name'] in pks),
                    is_foreign_key=(col['name'] in fk_map),
                    references=fk_map.get(col['name']),
                    nullable=col['nullable'],
                    description=col_meta.get("description", col.get("comment", ""))
                ))
            
            table_meta = metadata_config.get(table_name, {})
            schema = SchemaInfo(
                table_name=table_name,
                description=table_meta.get("description", ""),
                sample_questions=table_meta.get("sample_questions", []),
                columns=columns
            )
            self.register_table(schema)

    # ------------------------------------------------------------------
    # Internal embedding helpers
    # ------------------------------------------------------------------

    def _get_embed_model(self):
        if self._embed_model is None:
            try:
                from sentence_transformers import SentenceTransformer
                self._embed_model = SentenceTransformer("all-MiniLM-L6-v2")
            except ImportError:
                # Fallback: simple bag-of-words TF vector (no deps needed)
                self._embed_model = "bow"
        return self._embed_model

    def _embed(self, text: str) -> np.ndarray:
        model = self._get_embed_model()
        if model == "bow":
            return self._bow_embed(text)
        return model.encode(text, normalize_embeddings=True)

    def _get_or_compute_embedding(self, name: str, table: SchemaInfo) -> np.ndarray:
        if name not in self._embeddings:
            text = f"{table.table_name} {table.description} " + " ".join(
                f"{c.name} {c.description or ''}" for c in table.columns
            ) + " " + " ".join(table.sample_questions)
            self._embeddings[name] = self._embed(text)
        return self._embeddings[name]

    @staticmethod
    def _bow_embed(text: str) -> np.ndarray:
        """Minimal bag-of-words fallback when sentence-transformers not installed."""
        import hashlib
        words = text.lower().split()
        vec = np.zeros(512)
        for w in words:
            idx = int(hashlib.md5(w.encode()).hexdigest(), 16) % 512
            vec[idx] += 1
        norm = np.linalg.norm(vec)
        return vec / (norm + 1e-9)
