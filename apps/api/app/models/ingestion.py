from sqlalchemy import String, Text, BigInteger, Integer, ForeignKey, DateTime, Boolean
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime, timezone
from app.database import Base


class UploadedFile(Base):
    __tablename__ = "uploaded_files"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    original_filename: Mapped[str] = mapped_column(String(500), nullable=False)
    storage_key: Mapped[str] = mapped_column(String(1000), nullable=False)
    bucket: Mapped[str] = mapped_column(String(255), nullable=False, default="raw-uploads")
    file_size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    row_count: Mapped[int] = mapped_column(Integer, nullable=True)
    col_count: Mapped[int] = mapped_column(Integer, nullable=True)
    mime_type: Mapped[str] = mapped_column(String(100), nullable=True)
    upload_status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    error_msg: Mapped[str] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    job_runs: Mapped[list["JobRun"]] = relationship("JobRun", back_populates="uploaded_file")
    survey_responses: Mapped[list["SurveyResponse"]] = relationship("SurveyResponse", back_populates="uploaded_file")


class JobRun(Base):
    __tablename__ = "job_runs"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    upload_file_id: Mapped[int] = mapped_column(ForeignKey("uploaded_files.id", ondelete="SET NULL"), nullable=True)
    task_name: Mapped[str] = mapped_column(String(255), nullable=False)
    celery_task_id: Mapped[str] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
    error_msg: Mapped[str] = mapped_column(Text, nullable=True)
    meta: Mapped[dict] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    uploaded_file: Mapped["UploadedFile"] = relationship("UploadedFile", back_populates="job_runs")
    survey_responses: Mapped[list["SurveyResponse"]] = relationship("SurveyResponse", back_populates="job_run")


class SurveyResponse(Base):
    __tablename__ = "survey_responses"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    upload_file_id: Mapped[int] = mapped_column(ForeignKey("uploaded_files.id", ondelete="CASCADE"), nullable=False)
    job_run_id: Mapped[int] = mapped_column(ForeignKey("job_runs.id", ondelete="SET NULL"), nullable=True)
    respondent_id: Mapped[str] = mapped_column(String(500), nullable=True)
    raw_data: Mapped[dict] = mapped_column(JSONB, nullable=True)
    normalized_data: Mapped[dict] = mapped_column(JSONB, nullable=True)
    row_index: Mapped[int] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    uploaded_file: Mapped["UploadedFile"] = relationship("UploadedFile", back_populates="survey_responses")
    job_run: Mapped["JobRun"] = relationship("JobRun", back_populates="survey_responses")
    response_features: Mapped[list["ResponseFeatures"]] = relationship("ResponseFeatures", back_populates="survey_response")
    fraud_scores: Mapped[list["FraudScore"]] = relationship("FraudScore", back_populates="survey_response")


class ResponseFeatures(Base):
    __tablename__ = "response_features"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    survey_response_id: Mapped[int] = mapped_column(ForeignKey("survey_responses.id", ondelete="CASCADE"), nullable=False, index=True)
    job_run_id: Mapped[int] = mapped_column(ForeignKey("job_runs.id", ondelete="SET NULL"), nullable=True, index=True)
    duration_sec: Mapped[float] = mapped_column(nullable=True)
    completion_speed_zscore: Mapped[float] = mapped_column(nullable=True)
    straightline_ratio: Mapped[float] = mapped_column(nullable=True)
    answer_entropy: Mapped[float] = mapped_column(nullable=True)
    longstring_max: Mapped[int] = mapped_column(Integer, nullable=True)
    duplicate_answer_vector_hash: Mapped[str] = mapped_column(Text, nullable=True)
    open_text_length_mean: Mapped[float] = mapped_column(nullable=True)
    open_text_uniqueness_score: Mapped[float] = mapped_column(nullable=True)
    attention_fail_count: Mapped[int] = mapped_column(Integer, nullable=True)
    contradiction_count: Mapped[int] = mapped_column(Integer, nullable=True)
    device_submission_count_24h: Mapped[int] = mapped_column(Integer, nullable=True)
    ip_submission_count_24h: Mapped[int] = mapped_column(Integer, nullable=True)
    missingness_ratio: Mapped[float] = mapped_column(nullable=True)
    features_json: Mapped[dict] = mapped_column(JSONB, nullable=True)
    computed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    survey_response: Mapped["SurveyResponse"] = relationship("SurveyResponse", back_populates="response_features")
    fraud_scores: Mapped[list["FraudScore"]] = relationship("FraudScore", back_populates="response_features")


class FraudScoreConfig(Base):
    __tablename__ = "fraud_score_configs"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    config_name: Mapped[str] = mapped_column(String(255), nullable=False)
    weights: Mapped[dict] = mapped_column(JSONB, nullable=False)
    thresholds: Mapped[dict] = mapped_column(JSONB, nullable=False)
    attention_rules: Mapped[dict] = mapped_column(JSONB, nullable=True)
    contradiction_rules: Mapped[list] = mapped_column(JSONB, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    fraud_scores: Mapped[list["FraudScore"]] = relationship("FraudScore", back_populates="config")


class FraudScore(Base):
    __tablename__ = "fraud_scores"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    survey_response_id: Mapped[int] = mapped_column(ForeignKey("survey_responses.id", ondelete="CASCADE"), nullable=False, index=True)
    response_features_id: Mapped[int] = mapped_column(ForeignKey("response_features.id", ondelete="SET NULL"), nullable=True)
    fraud_score: Mapped[float] = mapped_column(nullable=False)
    fraud_label: Mapped[str] = mapped_column(String(10), nullable=False)
    fraud_reasons: Mapped[list] = mapped_column(JSONB, nullable=True)
    component_scores: Mapped[dict] = mapped_column(JSONB, nullable=True)
    config_id: Mapped[int] = mapped_column(ForeignKey("fraud_score_configs.id", ondelete="SET NULL"), nullable=True)
    scored_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)

    survey_response: Mapped["SurveyResponse"] = relationship("SurveyResponse", back_populates="fraud_scores")
    response_features: Mapped["ResponseFeatures"] = relationship("ResponseFeatures", back_populates="fraud_scores")
    config: Mapped["FraudScoreConfig"] = relationship("FraudScoreConfig", back_populates="fraud_scores")


class AnalyticsResult(Base):
    __tablename__ = "analytics_results"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    job_run_id: Mapped[int] = mapped_column(ForeignKey("job_runs.id", ondelete="SET NULL"), nullable=True, index=True)
    analysis_type: Mapped[str] = mapped_column(String(100), nullable=False)
    question_key: Mapped[str] = mapped_column(String(500), nullable=True)
    result_data: Mapped[dict] = mapped_column(JSONB, nullable=True)
    insight_text: Mapped[str] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )


class GeneratedReport(Base):
    __tablename__ = "generated_reports"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    job_run_id: Mapped[int] = mapped_column(ForeignKey("job_runs.id", ondelete="SET NULL"), nullable=True, index=True)
    report_type: Mapped[str] = mapped_column(String(100), nullable=False)
    storage_key: Mapped[str] = mapped_column(Text, nullable=True)
    bucket: Mapped[str] = mapped_column(String(255), nullable=True)
    file_size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    error_msg: Mapped[str] = mapped_column(Text, nullable=True)
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
