from pydantic import BaseModel, Field
from typing import Optional


class QueryRequest(BaseModel):
    question: str = Field(..., description="Natural language question", example="Who are the top 5 customers by revenue last month?")
    top_k_tables: int = Field(default=5, ge=1, le=20, description="Max number of schema tables to inject into the prompt")


class QueryResponse(BaseModel):
    question: str
    sql: str
    explanation: str
    tables_used: list[str]
    latency_ms: float = 0.0
    warning: Optional[str] = None


class ColumnInfo(BaseModel):
    name: str
    type: str
    description: Optional[str] = None
    nullable: bool = True
    is_primary_key: bool = False
    is_foreign_key: bool = False
    references: Optional[str] = None  # e.g. "orders.customer_id"


class SchemaInfo(BaseModel):
    table_name: str
    description: str
    columns: list[ColumnInfo]
    sample_questions: list[str] = []
