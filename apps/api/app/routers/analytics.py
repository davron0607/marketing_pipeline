import logging
import json
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from app.database import get_db
from app.routers.deps import get_current_active_user
from app.repositories.project_repository import ProjectRepository
from app.services.analytics_service import get_analytics_summary
from app.schemas.analytics import AnalyticsSummaryResponse
from app.models.user import User

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/project/{project_id}", response_model=AnalyticsSummaryResponse)
async def analytics_summary(
    project_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    proj_repo = ProjectRepository(db)
    project = await proj_repo.get_by_id(project_id, current_user.id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return await get_analytics_summary(db, project_id)


@router.get("/projects/{project_id}/analytics-summary")
async def new_analytics_summary(
    project_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    GET /projects/{project_id}/analytics-summary
    Returns comprehensive analytics summary for a project.
    """
    proj_repo = ProjectRepository(db)
    project = await proj_repo.get_by_id(project_id, current_user.id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    logger.info("analytics-summary request project_id=%s user_id=%s", project_id, current_user.id)

    # Fraud / sample quality
    result = await db.execute(
        text(
            "SELECT fraud_label, COUNT(*) FROM fraud_scores WHERE project_id=:p GROUP BY fraud_label"
        ),
        {"p": project_id},
    )
    label_counts = {row[0]: int(row[1]) for row in result.fetchall()}
    total = sum(label_counts.values())
    valid = label_counts.get("valid", 0)
    review = label_counts.get("review", 0)
    reject = label_counts.get("reject", 0)
    usable = valid + review

    sample_quality = {
        "total": total,
        "valid": valid,
        "review": review,
        "reject": reject,
        "usable": usable,
    }

    # Analytics results
    result = await db.execute(
        text(
            "SELECT analysis_type, question_key, result_data, insight_text "
            "FROM analytics_results WHERE project_id=:p ORDER BY id"
        ),
        {"p": project_id},
    )
    rows = result.fetchall()

    insight_texts = []
    distributions = {}
    crosstabs = []
    top_drivers = []

    for analysis_type, question_key, result_data_raw, insight_text in rows:
        if isinstance(result_data_raw, str):
            try:
                rd = json.loads(result_data_raw)
            except Exception:
                rd = {}
        elif result_data_raw is None:
            rd = {}
        else:
            rd = dict(result_data_raw)

        if analysis_type in ("distribution_numeric", "distribution_single_choice", "distribution_text"):
            dist_type_map = {
                "distribution_numeric": "numeric",
                "distribution_single_choice": "single_choice",
                "distribution_text": "text",
            }
            if question_key:
                distributions[question_key] = {
                    "type": dist_type_map.get(analysis_type, "single_choice"),
                    "data": rd,
                }
        elif analysis_type == "crosstab":
            crosstabs.append(rd)
        elif analysis_type == "top_driver":
            top_drivers.append(rd)

        if insight_text:
            insight_texts.append(insight_text)

    return {
        "sample_quality": sample_quality,
        "insight_texts": insight_texts,
        "distributions": distributions,
        "crosstabs": crosstabs,
        "top_drivers": top_drivers,
    }
