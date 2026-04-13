from sqlalchemy import String, Text, ForeignKey, DateTime
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime, timezone
from app.database import Base


class Job(Base):
    __tablename__ = "jobs"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), nullable=False, index=True)
    upload_id: Mapped[int] = mapped_column(ForeignKey("uploads.id"), nullable=True)
    job_type: Mapped[str] = mapped_column(String(50), nullable=False)  # full_analysis, fraud_check, report_gen
    status: Mapped[str] = mapped_column(String(20), default="pending")  # pending, running, completed, failed
    celery_task_id: Mapped[str] = mapped_column(String(255), nullable=True)
    error_message: Mapped[str] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    project: Mapped["Project"] = relationship("Project", back_populates="jobs")  # type: ignore
    upload: Mapped["Upload"] = relationship("Upload")  # type: ignore
