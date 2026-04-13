from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.job import Job
from datetime import datetime, timezone


class JobRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_project(self, project_id: int) -> list[Job]:
        result = await self.db.execute(
            select(Job).where(Job.project_id == project_id).order_by(Job.created_at.desc())
        )
        return list(result.scalars().all())

    async def get_by_id(self, job_id: int) -> Job | None:
        result = await self.db.execute(select(Job).where(Job.id == job_id))
        return result.scalar_one_or_none()

    async def create(self, project_id: int, upload_id: int, job_type: str) -> Job:
        job = Job(project_id=project_id, upload_id=upload_id, job_type=job_type)
        self.db.add(job)
        await self.db.commit()
        await self.db.refresh(job)
        return job

    async def update_status(
        self, job: Job, status: str,
        celery_task_id: str | None = None,
        error_message: str | None = None
    ) -> Job:
        job.status = status
        if celery_task_id:
            job.celery_task_id = celery_task_id
        if error_message:
            job.error_message = error_message
        if status == "running":
            job.started_at = datetime.now(timezone.utc)
        if status in ("completed", "failed"):
            job.completed_at = datetime.now(timezone.utc)
        await self.db.commit()
        await self.db.refresh(job)
        return job
