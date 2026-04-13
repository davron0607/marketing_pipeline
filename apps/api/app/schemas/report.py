from pydantic import BaseModel
from datetime import datetime


class ReportResponse(BaseModel):
    id: int
    project_id: int
    job_id: int | None
    report_type: str
    status: str
    file_path: str | None
    created_at: datetime

    model_config = {"from_attributes": True}
