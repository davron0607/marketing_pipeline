from pydantic import BaseModel


class ColumnStat(BaseModel):
    column: str
    dtype: str
    missing_pct: float
    unique_count: int
    top_value: str | None = None


class AnalyticsSummaryResponse(BaseModel):
    project_id: int
    total_rows: int
    total_columns: int
    column_stats: list[ColumnStat]
