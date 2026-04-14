import logging
import json
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from app.database import get_db
from app.routers.deps import get_current_active_user
from app.repositories.project_repository import ProjectRepository
from app.services.fraud_service import get_fraud_summary
from app.schemas.fraud import FraudSummaryResponse
from app.models.user import User

logger = logging.getLogger(__name__)
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


@router.get("/projects/{project_id}/fraud-summary")
async def new_fraud_summary(
    project_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    GET /projects/{project_id}/fraud-summary
    Returns aggregated fraud scoring results for a project.
    """
    proj_repo = ProjectRepository(db)
    project = await proj_repo.get_by_id(project_id, current_user.id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    logger.info("fraud-summary request project_id=%s user_id=%s", project_id, current_user.id)

    # Total scored
    result = await db.execute(
        text("SELECT COUNT(*) FROM fraud_scores WHERE project_id=:p"),
        {"p": project_id},
    )
    total_scored = int((result.fetchone() or [0])[0])

    # Label counts
    result = await db.execute(
        text("SELECT fraud_label, COUNT(*) FROM fraud_scores WHERE project_id=:p GROUP BY fraud_label"),
        {"p": project_id},
    )
    label_counts = {row[0]: int(row[1]) for row in result.fetchall()}

    label_percentages = {
        lbl: round(cnt / total_scored * 100, 2) if total_scored else 0.0
        for lbl, cnt in label_counts.items()
    }

    # Top reasons from rejected responses
    try:
        result = await db.execute(
            text(
                "SELECT reason, COUNT(*) as cnt FROM ("
                "  SELECT jsonb_array_elements_text(fraud_reasons) as reason "
                "  FROM fraud_scores WHERE project_id=:p AND fraud_label='reject'"
                ") sub GROUP BY reason ORDER BY cnt DESC LIMIT 10"
            ),
            {"p": project_id},
        )
        top_reasons = [{"reason": row[0], "count": int(row[1])} for row in result.fetchall()]
    except Exception as e:
        logger.warning("Error fetching top reasons: %s", e)
        top_reasons = []

    # Top suspicious responses
    try:
        result = await db.execute(
            text(
                "SELECT sr.respondent_id, fs.fraud_score, fs.fraud_label, fs.fraud_reasons "
                "FROM fraud_scores fs "
                "JOIN survey_responses sr ON sr.id = fs.survey_response_id "
                "WHERE fs.project_id=:p AND fs.fraud_label='reject' "
                "ORDER BY fs.fraud_score DESC LIMIT 10"
            ),
            {"p": project_id},
        )
        top_suspicious = []
        for row in result.fetchall():
            reasons_raw = row[3]
            if isinstance(reasons_raw, str):
                try:
                    reasons = json.loads(reasons_raw)
                except Exception:
                    reasons = []
            elif reasons_raw is None:
                reasons = []
            else:
                reasons = list(reasons_raw)
            top_suspicious.append({
                "respondent_id": row[0],
                "fraud_score": round(float(row[1]), 2),
                "label": row[2],
                "reasons": reasons,
            })
    except Exception as e:
        logger.warning("Error fetching top suspicious: %s", e)
        top_suspicious = []

    return {
        "total_scored": total_scored,
        "label_counts": label_counts,
        "label_percentages": label_percentages,
        "top_reasons": top_reasons,
        "top_suspicious": top_suspicious,
    }
