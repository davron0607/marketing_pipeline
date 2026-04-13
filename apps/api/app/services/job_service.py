from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException
from app.repositories.job_repository import JobRepository
from app.repositories.upload_repository import UploadRepository
from app.models.job import Job


async def create_job(db: AsyncSession, project_id: int, upload_id: int, job_type: str) -> Job:
    upload_repo = UploadRepository(db)
    upload = await upload_repo.get_by_id(upload_id)
    if not upload or upload.project_id != project_id:
        raise HTTPException(status_code=404, detail="Upload not found")

    job_repo = JobRepository(db)
    job = await job_repo.create(project_id=project_id, upload_id=upload_id, job_type=job_type)

    # Dispatch to Celery
    try:
        from app.worker_client import dispatch_analysis
        task_id = dispatch_analysis(job.id, upload.storage_key, project_id)
        await job_repo.update_status(job, "pending", celery_task_id=task_id)
    except Exception as e:
        await job_repo.update_status(job, "failed", error_message=str(e))

    return job
