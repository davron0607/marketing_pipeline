from pydantic import BaseModel
from datetime import datetime
from typing import Any


class UploadResponse(BaseModel):
    upload_id: int
    job_run_id: int
    filename: str
    status: str

    model_config = {"from_attributes": True}


class UploadedFileResponse(BaseModel):
    id: int
    project_id: int
    original_filename: str
    storage_key: str
    bucket: str
    file_size_bytes: int
    row_count: int | None
    col_count: int | None
    mime_type: str | None
    upload_status: str
    error_msg: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class JobRunResponse(BaseModel):
    id: int
    project_id: int
    upload_file_id: int | None
    task_name: str
    celery_task_id: str | None
    status: str
    started_at: datetime | None
    completed_at: datetime | None
    error_msg: str | None
    meta: dict[str, Any] | None
    created_at: datetime

    model_config = {"from_attributes": True}


class SurveyResponseSchema(BaseModel):
    id: int
    project_id: int
    upload_file_id: int
    job_run_id: int | None
    respondent_id: str | None
    raw_data: dict[str, Any] | None
    normalized_data: dict[str, Any] | None
    row_index: int | None
    created_at: datetime

    model_config = {"from_attributes": True}
