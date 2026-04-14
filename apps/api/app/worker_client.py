from celery import Celery
from app.config import get_settings

settings = get_settings()

celery_app = Celery(
    "worker",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
)


def dispatch_analysis(job_id: int, storage_key: str, project_id: int) -> str:
    result = celery_app.send_task(
        "worker.tasks.analysis_tasks.run_full_analysis",
        args=[job_id, storage_key, project_id],
    )
    return result.id


def dispatch_ingestion_task(
    job_run_id: int,
    upload_file_id: int,
    storage_key: str,
    project_id: int,
) -> str:
    result = celery_app.send_task(
        "app.tasks.ingestion_tasks.process_uploaded_survey_file",
        args=[job_run_id, upload_file_id, storage_key, project_id],
    )
    return result.id


def dispatch_feature_task(job_run_id: int, project_id: int) -> str:
    result = celery_app.send_task(
        "app.tasks.feature_tasks.compute_response_features",
        args=[job_run_id, project_id],
    )
    return result.id


def dispatch_scoring_task(job_run_id: int, project_id: int, config_id: int | None = None) -> str:
    result = celery_app.send_task(
        "app.tasks.scoring_tasks.run_fraud_scoring",
        args=[job_run_id, project_id, config_id],
    )
    return result.id


def dispatch_analytics_task(job_run_id: int, project_id: int) -> str:
    result = celery_app.send_task(
        "app.tasks.analytics_tasks.run_analytics",
        args=[job_run_id, project_id],
    )
    return result.id


def dispatch_report_task(job_run_id: int, project_id: int) -> str:
    result = celery_app.send_task(
        "app.tasks.report_tasks.generate_pdf_report",
        args=[job_run_id, project_id],
    )
    return result.id
