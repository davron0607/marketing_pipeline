from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException
from fastapi.responses import StreamingResponse
import io
from app.repositories.report_repository import ReportRepository
from app.services.upload_service import get_s3_client
from app.config import get_settings

settings = get_settings()


async def get_reports(db: AsyncSession, project_id: int):
    repo = ReportRepository(db)
    return await repo.get_by_project(project_id)


async def download_report(db: AsyncSession, report_id: int) -> StreamingResponse:
    repo = ReportRepository(db)
    report = await repo.get_by_id(report_id)
    if not report or not report.file_path:
        raise HTTPException(status_code=404, detail="Report not found or not ready")

    s3 = get_s3_client()
    obj = s3.get_object(Bucket=settings.MINIO_BUCKET, Key=report.file_path)
    data = obj["Body"].read()

    return StreamingResponse(
        io.BytesIO(data),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="report-{report_id}.pdf"'},
    )
