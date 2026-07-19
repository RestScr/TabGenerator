"""create audio assets and processing jobs

Revision ID: 0001_create_processing_tables
Revises:
Create Date: 2026-07-11
"""

from alembic import op
import sqlalchemy as sa


revision = "0001_create_processing_tables"
down_revision = None
branch_labels = None
depends_on = None


job_status = sa.Enum(
    "queued",
    "processing",
    "completed",
    "failed",
    "cancelled",
    name="processing_job_status",
    native_enum=False,
    length=20,
)


def upgrade() -> None:
    op.create_table(
        "audio_assets",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("original_filename", sa.String(length=255), nullable=False),
        sa.Column("storage_key", sa.String(length=512), nullable=False),
        sa.Column("content_type", sa.String(length=127), nullable=True),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("storage_key"),
    )
    op.create_index("ix_audio_assets_sha256", "audio_assets", ["sha256"], unique=False)

    op.create_table(
        "processing_jobs",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("audio_asset_id", sa.String(length=36), nullable=False),
        sa.Column("status", job_status, nullable=False),
        sa.Column("progress", sa.Integer(), nullable=False),
        sa.Column("options", sa.JSON(), nullable=False),
        sa.Column("error_code", sa.String(length=64), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.CheckConstraint("progress >= 0 AND progress <= 100", name="ck_processing_jobs_progress"),
        sa.ForeignKeyConstraint(["audio_asset_id"], ["audio_assets.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_processing_jobs_audio_asset_id", "processing_jobs", ["audio_asset_id"], unique=False)
    op.create_index("ix_processing_jobs_status", "processing_jobs", ["status"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_processing_jobs_status", table_name="processing_jobs")
    op.drop_index("ix_processing_jobs_audio_asset_id", table_name="processing_jobs")
    op.drop_table("processing_jobs")
    op.drop_index("ix_audio_assets_sha256", table_name="audio_assets")
    op.drop_table("audio_assets")
