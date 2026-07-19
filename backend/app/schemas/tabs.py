from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


class GeneratedTabSummaryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    processing_job_id: str
    title: str
    tempo_bpm: int
    created_at: datetime
    updated_at: datetime


class GeneratedTabResponse(GeneratedTabSummaryResponse):
    ascii_tab: str
    ascii_tab_storage_key: str
    midi_storage_key: str | None
    note_events_storage_key: str | None
    tab_data: dict[str, Any]
