from sqlalchemy.ext.asyncio import AsyncSession
from app.repositories.fraud_repository import FraudRepository
from app.repositories.upload_repository import UploadRepository
from app.schemas.fraud import FraudSummaryResponse, FraudFlagResponse


async def get_fraud_summary(db: AsyncSession, project_id: int) -> FraudSummaryResponse:
    repo = FraudRepository(db)
    flags = await repo.get_by_project(project_id)

    upload_repo = UploadRepository(db)
    uploads = await upload_repo.get_by_project(project_id)
    total = sum(u.row_count or 0 for u in uploads)

    flag_responses = [
        FraudFlagResponse(
            id=f.id,
            respondent_id=f.respondent_id,
            flag_type=f.flag_type,
            confidence=f.confidence,
            details=f.details,
        )
        for f in flags
    ]

    return FraudSummaryResponse(
        total_respondents=total,
        flagged_count=len(flags),
        fraud_rate=len(flags) / total if total > 0 else 0.0,
        flags=flag_responses,
    )
