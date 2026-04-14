from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # App
    APP_NAME: str = "Survey Analytics API"
    DEBUG: bool = False
    SECRET_KEY: str = "change-me-in-production-use-32-chars-min"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24  # 24h

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/survey_analytics"

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"

    # MinIO / S3
    MINIO_ENDPOINT: str = "localhost:9000"
    MINIO_PUBLIC_ENDPOINT: str = "localhost:9000"   # browser-reachable host:port
    MINIO_ACCESS_KEY: str = "minioadmin"
    MINIO_SECRET_KEY: str = "minioadmin"
    MINIO_BUCKET: str = "survey-datasets"
    MINIO_SECURE: bool = False

    # Celery
    CELERY_BROKER_URL: str = "redis://localhost:6379/0"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/0"

    class Config:
        env_file = ".env"
        case_sensitive = True


@lru_cache
def get_settings() -> Settings:
    return Settings()
