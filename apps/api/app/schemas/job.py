from pydantic import BaseModel
from datetime import datetime
from typing import Literal


class JobCreate(BaseModel):
    project_id: int
    upload_id: int
    job_type: Literal["full_analysis", "fraud_check", "report_gen"] = "full_analysis"


class JobResponse(BaseModel):
    id: int
    project_id: int
    upload_id: int | None
    job_type: str
    status: str
    celery_task_id: str | None
    error_message: str | None
    started_at: datetime | None
    completed_at: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}
