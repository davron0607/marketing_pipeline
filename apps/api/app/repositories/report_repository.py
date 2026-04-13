from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.report import Report


class ReportRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_project(self, project_id: int) -> list[Report]:
        result = await self.db.execute(
            select(Report).where(Report.project_id == project_id).order_by(Report.created_at.desc())
        )
        return list(result.scalars().all())

    async def get_by_id(self, report_id: int) -> Report | None:
        result = await self.db.execute(select(Report).where(Report.id == report_id))
        return result.scalar_one_or_none()

    async def create(self, project_id: int, job_id: int | None, report_type: str) -> Report:
        report = Report(project_id=project_id, job_id=job_id, report_type=report_type)
        self.db.add(report)
        await self.db.commit()
        await self.db.refresh(report)
        return report

    async def update(self, report: Report, **kwargs) -> Report:
        for k, v in kwargs.items():
            setattr(report, k, v)
        await self.db.commit()
        await self.db.refresh(report)
        return report
