"""ingestion tables

Revision ID: 0002
Revises: 0001
Create Date: 2026-04-13
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "uploaded_files",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("project_id", sa.Integer, sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("original_filename", sa.String(500), nullable=False),
        sa.Column("storage_key", sa.String(1000), nullable=False),
        sa.Column("bucket", sa.String(255), nullable=False, server_default="raw-uploads"),
        sa.Column("file_size_bytes", sa.BigInteger, nullable=False, server_default="0"),
        sa.Column("row_count", sa.Integer, nullable=True),
        sa.Column("col_count", sa.Integer, nullable=True),
        sa.Column("mime_type", sa.String(100), nullable=True),
        sa.Column(
            "upload_status",
            sa.String(20),
            nullable=False,
            server_default="pending",
        ),
        sa.Column("error_msg", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "job_runs",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("project_id", sa.Integer, sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("upload_file_id", sa.Integer, sa.ForeignKey("uploaded_files.id", ondelete="SET NULL"), nullable=True),
        sa.Column("task_name", sa.String(255), nullable=False),
        sa.Column("celery_task_id", sa.String(255), nullable=True),
        sa.Column(
            "status",
            sa.String(20),
            nullable=False,
            server_default="pending",
        ),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_msg", sa.Text, nullable=True),
        sa.Column("meta", postgresql.JSONB, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "survey_responses",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("project_id", sa.Integer, sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("upload_file_id", sa.Integer, sa.ForeignKey("uploaded_files.id", ondelete="CASCADE"), nullable=False),
        sa.Column("job_run_id", sa.Integer, sa.ForeignKey("job_runs.id", ondelete="SET NULL"), nullable=True),
        sa.Column("respondent_id", sa.String(500), nullable=True),
        sa.Column("raw_data", postgresql.JSONB, nullable=True),
        sa.Column("normalized_data", postgresql.JSONB, nullable=True),
        sa.Column("row_index", sa.Integer, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_survey_responses_upload_file_id", "survey_responses", ["upload_file_id"])
    op.create_index("ix_survey_responses_job_run_id", "survey_responses", ["job_run_id"])


def downgrade():
    op.drop_index("ix_survey_responses_job_run_id", table_name="survey_responses")
    op.drop_index("ix_survey_responses_upload_file_id", table_name="survey_responses")
    op.drop_table("survey_responses")
    op.drop_table("job_runs")
    op.drop_table("uploaded_files")
