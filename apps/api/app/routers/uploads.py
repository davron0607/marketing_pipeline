from fastapi import APIRouter, Depends, UploadFile, File, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.routers.deps import get_current_active_user
from app.repositories.project_repository import ProjectRepository
from app.repositories.upload_repository import UploadRepository
from app.services.upload_service import upload_dataset
from app.schemas.upload import UploadResponse
from app.models.user import User

router = APIRouter()


@router.post("/project/{project_id}", response_model=UploadResponse, status_code=201)
async def upload_file(
    project_id: int,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    proj_repo = ProjectRepository(db)
    project = await proj_repo.get_by_id(project_id, current_user.id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return await upload_dataset(db, project_id, file)


@router.get("/project/{project_id}", response_model=list[UploadResponse])
async def list_uploads(
    project_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    proj_repo = ProjectRepository(db)
    project = await proj_repo.get_by_id(project_id, current_user.id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    repo = UploadRepository(db)
    return await repo.get_by_project(project_id)
