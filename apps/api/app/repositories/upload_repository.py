from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.upload import Upload


class UploadRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_project(self, project_id: int) -> list[Upload]:
        result = await self.db.execute(
            select(Upload).where(Upload.project_id == project_id).order_by(Upload.created_at.desc())
        )
        return list(result.scalars().all())

    async def get_by_id(self, upload_id: int) -> Upload | None:
        result = await self.db.execute(select(Upload).where(Upload.id == upload_id))
        return result.scalar_one_or_none()

    async def create(
        self, project_id: int, filename: str, storage_key: str,
        file_size: int, row_count: int | None = None, column_count: int | None = None
    ) -> Upload:
        upload = Upload(
            project_id=project_id, filename=filename, storage_key=storage_key,
            file_size=file_size, row_count=row_count, column_count=column_count,
        )
        self.db.add(upload)
        await self.db.commit()
        await self.db.refresh(upload)
        return upload
