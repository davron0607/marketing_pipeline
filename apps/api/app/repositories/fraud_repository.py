from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from app.models.fraud import FraudResult


class FraudRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_project(self, project_id: int) -> list[FraudResult]:
        result = await self.db.execute(
            select(FraudResult).where(FraudResult.project_id == project_id)
        )
        return list(result.scalars().all())

    async def create_bulk(self, records: list[dict]) -> list[FraudResult]:
        items = [FraudResult(**r) for r in records]
        self.db.add_all(items)
        await self.db.commit()
        return items

    async def delete_by_project_job(self, project_id: int, job_id: int) -> None:
        from sqlalchemy import delete
        await self.db.execute(
            delete(FraudResult).where(
                FraudResult.project_id == project_id,
                FraudResult.job_id == job_id,
            )
        )
        await self.db.commit()
