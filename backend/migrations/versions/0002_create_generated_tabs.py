"""create generated tabs

Revision ID: 0002_create_generated_tabs
Revises: 0001_create_processing_tables
Create Date: 2026-07-11
"""

from alembic import op
import sqlalchemy as sa


revision = "0002_create_generated_tabs"
down_revision = "0001_create_processing_tables"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "generated_tabs",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("processing_job_id", sa.String(length=36), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("tempo_bpm", sa.Integer(), nullable=False),
        sa.Column("ascii_tab", sa.Text(), nullable=False),
        sa.Column("ascii_tab_storage_key", sa.String(length=512), nullable=False),
        sa.Column("midi_storage_key", sa.String(length=512), nullable=True),
        sa.Column("note_events_storage_key", sa.String(length=512), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["processing_job_id"], ["processing_jobs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("processing_job_id"),
    )
def downgrade() -> None:
    op.drop_table("generated_tabs")
