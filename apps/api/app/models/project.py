from sqlalchemy import String, Text, ForeignKey, DateTime
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime, timezone
from app.database import Base


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    owner: Mapped["User"] = relationship("User", back_populates="projects")  # type: ignore
    uploads: Mapped[list["Upload"]] = relationship("Upload", back_populates="project")  # type: ignore
    jobs: Mapped[list["Job"]] = relationship("Job", back_populates="project")  # type: ignore
    fraud_results: Mapped[list["FraudResult"]] = relationship("FraudResult", back_populates="project")  # type: ignore
    reports: Mapped[list["Report"]] = relationship("Report", back_populates="project")  # type: ignore
