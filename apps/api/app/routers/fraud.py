from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.routers.deps import get_current_active_user
from app.repositories.project_repository import ProjectRepository
from app.services.fraud_service import get_fraud_summary
from app.schemas.fraud import FraudSummaryResponse
from app.models.user import User

router = APIRouter()


@router.get("/project/{project_id}", response_model=FraudSummaryResponse)
async def fraud_summary(
    project_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    proj_repo = ProjectRepository(db)
    project = await proj_repo.get_by_id(project_id, current_user.id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return await get_fraud_summary(db, project_id)
