from datetime import datetime

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.db.models.processing_job import ProcessingJobStatus


class ProcessingJobResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    audio_asset_id: str
    status: ProcessingJobStatus
    progress: int
    options: dict[str, Any]
    error_code: str | None
    error_message: str | None
    created_at: datetime
    updated_at: datetime
    started_at: datetime | None
    finished_at: datetime | None


class AudioCandidateResponse(BaseModel):
    id: str
    label: str
    pass_index: int
    filename: str
    storage_key: str
    content_type: str
    size_bytes: int
    sample_rate: int
    channels: int
    duration_seconds: float
    midi_storage_key: str | None = None
    midi_filename: str | None = None
    note_count: int = 0
    notes: list[dict[str, int | float | str]] = Field(default_factory=list)
    gaps_quality: dict[str, int | float] | None = None
    gaps_error: str | None = None
    selected: bool = False


class AudioPreparationResponse(BaseModel):
    status: str
    progress: int
    message: str
    model_name: str | None = None
    transcription_model: str | None = None
    passes: int | None = None
    tuning: str | None = None
    max_fret: int | None = None
    capo: int | None = None
    manifest_storage_key: str | None = None
    candidates: list[AudioCandidateResponse] = Field(default_factory=list)
