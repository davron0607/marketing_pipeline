"""fraud scoring tables

Revision ID: 0004
Revises: 0003
Create Date: 2026-04-13
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None

DEFAULT_WEIGHTS = {
    "speed_component": 0.20,
    "straightline_component": 0.20,
    "entropy_component": 0.15,
    "contradiction_component": 0.10,
    "duplicate_component": 0.15,
    "open_text_component": 0.10,
    "missingness_component": 0.05,
    "geo_device_component": 0.05,
}

DEFAULT_THRESHOLDS = {"valid_max": 29, "review_max": 59}


def upgrade():
    op.create_table(
        "fraud_score_configs",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("project_id", sa.Integer, sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("config_name", sa.String(255), nullable=False),
        sa.Column("weights", postgresql.JSONB, nullable=False),
        sa.Column("thresholds", postgresql.JSONB, nullable=False),
        sa.Column("attention_rules", postgresql.JSONB, nullable=True),
        sa.Column("contradiction_rules", postgresql.JSONB, nullable=True),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "fraud_scores",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("project_id", sa.Integer, sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("survey_response_id", sa.Integer, sa.ForeignKey("survey_responses.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("response_features_id", sa.Integer, sa.ForeignKey("response_features.id", ondelete="SET NULL"), nullable=True),
        sa.Column("fraud_score", sa.Float, nullable=False),
        sa.Column("fraud_label", sa.String(10), nullable=False),
        sa.Column("fraud_reasons", postgresql.JSONB, nullable=True),
        sa.Column("component_scores", postgresql.JSONB, nullable=True),
        sa.Column("config_id", sa.Integer, sa.ForeignKey("fraud_score_configs.id", ondelete="SET NULL"), nullable=True),
        sa.Column("scored_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_fraud_scores_job_run", "fraud_scores", ["survey_response_id"])


def downgrade():
    op.drop_index("ix_fraud_scores_job_run", table_name="fraud_scores")
    op.drop_table("fraud_scores")
    op.drop_table("fraud_score_configs")
