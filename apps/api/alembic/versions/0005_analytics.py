"""analytics results table

Revision ID: 0005
Revises: 0004
Create Date: 2026-04-13
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "analytics_results",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("project_id", sa.Integer, sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("job_run_id", sa.Integer, sa.ForeignKey("job_runs.id", ondelete="SET NULL"), nullable=True, index=True),
        sa.Column("analysis_type", sa.String(100), nullable=False),
        sa.Column("question_key", sa.String(500), nullable=True),
        sa.Column("result_data", postgresql.JSONB, nullable=True),
        sa.Column("insight_text", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade():
    op.drop_table("analytics_results")
