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
