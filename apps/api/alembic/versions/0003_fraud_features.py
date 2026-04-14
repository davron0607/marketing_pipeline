"""fraud feature engineering table

Revision ID: 0003
Revises: 0002
Create Date: 2026-04-13
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "response_features",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("project_id", sa.Integer, sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("survey_response_id", sa.Integer, sa.ForeignKey("survey_responses.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("job_run_id", sa.Integer, sa.ForeignKey("job_runs.id", ondelete="SET NULL"), nullable=True, index=True),
        sa.Column("duration_sec", sa.Float, nullable=True),
        sa.Column("completion_speed_zscore", sa.Float, nullable=True),
        sa.Column("straightline_ratio", sa.Float, nullable=True),
        sa.Column("answer_entropy", sa.Float, nullable=True),
        sa.Column("longstring_max", sa.Integer, nullable=True),
        sa.Column("duplicate_answer_vector_hash", sa.Text, nullable=True),
        sa.Column("open_text_length_mean", sa.Float, nullable=True),
        sa.Column("open_text_uniqueness_score", sa.Float, nullable=True),
        sa.Column("attention_fail_count", sa.Integer, nullable=True),
        sa.Column("contradiction_count", sa.Integer, nullable=True),
        sa.Column("device_submission_count_24h", sa.Integer, nullable=True),
        sa.Column("ip_submission_count_24h", sa.Integer, nullable=True),
        sa.Column("missingness_ratio", sa.Float, nullable=True),
        sa.Column("features_json", postgresql.JSONB, nullable=True),
        sa.Column("computed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade():
    op.drop_table("response_features")
