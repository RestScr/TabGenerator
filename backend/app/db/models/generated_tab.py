from __future__ import annotations

import json
from typing import TYPE_CHECKING
from uuid import uuid4

from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.dialects.mysql import LONGTEXT
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.db.models.processing_job import ProcessingJob


class GeneratedTab(TimestampMixin, Base):
    """Persisted output of one completed audio-to-tab processing job."""

    __tablename__ = "generated_tabs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    processing_job_id: Mapped[str] = mapped_column(
        ForeignKey("processing_jobs.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    tempo_bpm: Mapped[int] = mapped_column(Integer, nullable=False)
    ascii_tab: Mapped[str] = mapped_column(Text, nullable=False)
    ascii_tab_storage_key: Mapped[str] = mapped_column(String(512), nullable=False)
    midi_storage_key: Mapped[str | None] = mapped_column(String(512), nullable=True)
    note_events_storage_key: Mapped[str | None] = mapped_column(String(512), nullable=True)
    # A long song produces more than MySQL TEXT's 64 KiB limit.
    tab_data_json: Mapped[str] = mapped_column(LONGTEXT, nullable=False, default="{}")

    processing_job: Mapped[ProcessingJob] = relationship(back_populates="generated_tab")

    @property
    def tab_data(self) -> dict:
        return json.loads(self.tab_data_json)
