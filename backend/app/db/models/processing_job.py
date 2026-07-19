from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, TYPE_CHECKING
from uuid import uuid4

from sqlalchemy import CheckConstraint, DateTime, Enum as SqlEnum, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.db.models.audio_asset import AudioAsset
    from app.db.models.generated_tab import GeneratedTab


class ProcessingJobStatus(str, Enum):
    QUEUED = "queued"
    PROCESSING = "processing"
    AUDIO_PREPARED = "audio_prepared"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ProcessingJob(TimestampMixin, Base):
    __tablename__ = "processing_jobs"
    __table_args__ = (CheckConstraint("progress >= 0 AND progress <= 100", name="ck_processing_jobs_progress"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    audio_asset_id: Mapped[str] = mapped_column(
        ForeignKey("audio_assets.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    status: Mapped[ProcessingJobStatus] = mapped_column(
        SqlEnum(
            ProcessingJobStatus,
            name="processing_job_status",
            native_enum=False,
            length=20,
            values_callable=lambda statuses: [status.value for status in statuses],
        ),
        default=ProcessingJobStatus.QUEUED,
        index=True,
        nullable=False,
    )
    progress: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    options: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    audio_asset: Mapped[AudioAsset] = relationship(back_populates="processing_jobs")
    generated_tab: Mapped[GeneratedTab | None] = relationship(
        back_populates="processing_job",
        uselist=False,
        cascade="all, delete-orphan",
    )
