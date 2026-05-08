from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import time
import logging
import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env from root directory
load_dotenv(Path(__file__).parent.parent / ".env")

from app.models import QueryRequest, QueryResponse, SchemaInfo
from app.sql_generator import SQLGenerator, UnsafeSQLValidationError
from app.schema_store import SchemaStore

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def _get_allowed_origins() -> list[str]:
    """
    Read CORS origins from CORS_ALLOW_ORIGINS (comma-separated).
    Falls back to local dev origins if not configured.
    """
    raw_origins = os.getenv("CORS_ALLOW_ORIGINS", "")
    parsed_origins = [origin.strip() for origin in raw_origins.split(",") if origin.strip()]
    if parsed_origins:
        return parsed_origins

    logger.warning(
        "CORS_ALLOW_ORIGINS not set. Falling back to localhost-only CORS policy."
    )
    return ["http://localhost:3000", "http://127.0.0.1:3000"]


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: load schema store
    logger.info("Loading schema store...")
    app.state.schema_store = SchemaStore()
    db_url = os.getenv("DATABASE_URL")
    if db_url:
        app.state.schema_store.load_from_live_db(db_url)
    else:
        logger.warning("No DATABASE_URL set in environment. Schema store will be empty.")
    app.state.generator = SQLGenerator(schema_store=app.state.schema_store)
    logger.info("Ready.")
    yield
    # Shutdown
    logger.info("Shutting down.")


app = FastAPI(
    title="NL-to-SQL API",
    description="Convert natural language questions to SQL queries",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_get_allowed_origins(),
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization", "Accept"],
)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/schema", response_model=list[SchemaInfo])
def get_schema():
    """Return all tables and columns in the loaded schema."""
    return app.state.schema_store.get_all_tables()


@app.post("/query", response_model=QueryResponse)
async def generate_sql(request: QueryRequest):
    """
    Convert a natural language question to a SQL query.
    Automatically injects only the relevant schema tables into the prompt.
    """
    start = time.perf_counter()

    if not request.question.strip():
        raise HTTPException(status_code=400, detail="Question cannot be empty")

    try:
        result = await app.state.generator.generate(
            question=request.question,
            top_k_tables=request.top_k_tables,
        )
    except UnsafeSQLValidationError as exc:
        # Invalid/unsafe generated SQL should be a client-visible validation error.
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    result.latency_ms = round((time.perf_counter() - start) * 1000, 1)
    logger.info(
        f"query={request.question!r} | tables_used={result.tables_used} | latency={result.latency_ms}ms"
    )
    return result
