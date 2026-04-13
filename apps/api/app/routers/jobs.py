from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.routers.deps import get_current_active_user
from app.repositories.job_repository import JobRepository
from app.services.job_service import create_job
from app.schemas.job import JobCreate, JobResponse
from app.models.user import User

router = APIRouter()


@router.post("", response_model=JobResponse, status_code=201)
async def submit_job(
    payload: JobCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    return await create_job(db, payload.project_id, payload.upload_id, payload.job_type)


@router.get("", response_model=list[JobResponse])
async def list_jobs(
    project_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    repo = JobRepository(db)
    return await repo.get_by_project(project_id)


@router.get("/{job_id}", response_model=JobResponse)
async def get_job(
    job_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    repo = JobRepository(db)
    job = await repo.get_by_id(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job
