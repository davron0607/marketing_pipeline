from pydantic import BaseModel
from datetime import datetime


class UploadResponse(BaseModel):
    id: int
    project_id: int
    filename: str
    file_size: int
    row_count: int | None
    column_count: int | None
    created_at: datetime

    model_config = {"from_attributes": True}
