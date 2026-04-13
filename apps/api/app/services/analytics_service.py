import io
import pandas as pd
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException
from app.repositories.upload_repository import UploadRepository
from app.services.upload_service import get_upload_bytes
from app.schemas.analytics import AnalyticsSummaryResponse, ColumnStat


async def get_analytics_summary(db: AsyncSession, project_id: int) -> AnalyticsSummaryResponse:
    upload_repo = UploadRepository(db)
    uploads = await upload_repo.get_by_project(project_id)

    if not uploads:
        raise HTTPException(status_code=404, detail="No uploads found for this project")

    latest = uploads[0]
    content = get_upload_bytes(latest.storage_key)
    buf = io.BytesIO(content)

    if latest.filename.lower().endswith(".csv"):
        df = pd.read_csv(buf)
    else:
        df = pd.read_excel(buf)

    column_stats = []
    for col in df.columns:
        missing_pct = df[col].isna().mean()
        unique_count = df[col].nunique()
        try:
            top_value = str(df[col].value_counts().index[0]) if not df[col].empty else None
        except Exception:
            top_value = None
        column_stats.append(
            ColumnStat(
                column=col,
                dtype=str(df[col].dtype),
                missing_pct=round(float(missing_pct), 4),
                unique_count=int(unique_count),
                top_value=top_value,
            )
        )

    return AnalyticsSummaryResponse(
        project_id=project_id,
        total_rows=len(df),
        total_columns=len(df.columns),
        column_stats=column_stats,
    )
