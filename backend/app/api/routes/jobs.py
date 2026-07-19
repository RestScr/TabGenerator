from typing import Annotated

import json
from pathlib import Path
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.settings import Settings, get_settings
from app.db.models import AudioAsset, GeneratedTab, ProcessingJob, ProcessingJobStatus
from app.db.session import get_db
from app.schemas.jobs import AudioPreparationResponse, ProcessingJobResponse
from app.schemas.tabs import GeneratedTabResponse
from app.services.audio_preparation import run_audio_preparation_for_job
from app.services.prepared_tab import create_tab_from_prepared_audio, get_prepared_tab
from app.services.storage import UploadTooLargeError, UploadValidationError, store_audio_upload

router = APIRouter()


@router.post("", response_model=ProcessingJobResponse, status_code=status.HTTP_202_ACCEPTED)
async def create_processing_job(
    file: Annotated[UploadFile, File(description="Audio file to transcribe")],
    background_tasks: BackgroundTasks,
    instrument_type: Annotated[str, Form()] = "lead_guitar",
    voice_mode: Annotated[str, Form()] = "guitar",
    tuning: Annotated[str, Form()] = "standard_e",
    capo: Annotated[int, Form()] = 0,
    separate_sources: Annotated[bool, Form()] = True,
    tempo_bpm: Annotated[int | None, Form()] = None,
    downbeat_offset_s: Annotated[float, Form()] = 0.0,
    beats_per_measure: Annotated[int, Form()] = 4,
    max_fret: Annotated[int, Form()] = 20,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> ProcessingJob:
    if tuning not in settings.allowed_tunings:
        allowed = ", ".join(settings.allowed_tunings)
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=f"Unsupported tuning. Allowed: {allowed}")
    if voice_mode not in {"lead", "rhythm", "guitar", "all"}:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Voice mode must be lead, rhythm, guitar, or all")
    if not 0 <= capo <= 12:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Capo must be between 0 and 12")
    if tempo_bpm is not None and not 30 <= tempo_bpm <= 300:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Tempo must be between 30 and 300 BPM")
    if not 0 <= downbeat_offset_s <= 60:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Downbeat offset must be between 0 and 60 seconds")
    if not 2 <= beats_per_measure <= 12:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Beats per measure must be between 2 and 12")
    if not 5 <= max_fret <= 24:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Maximum fret must be between 5 and 24")

    try:
        stored_upload = await store_audio_upload(file, settings)
    except UploadValidationError as error:
        raise HTTPException(status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, detail=str(error)) from error
    except UploadTooLargeError as error:
        raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail=str(error)) from error

    audio_asset = AudioAsset(
        original_filename=stored_upload.original_filename,
        storage_key=stored_upload.storage_key,
        content_type=stored_upload.content_type,
        size_bytes=stored_upload.size_bytes,
        sha256=stored_upload.sha256,
    )
    job = ProcessingJob(
        audio_asset=audio_asset,
        status=ProcessingJobStatus.QUEUED,
        progress=0,
        options={
            "instrument_type": instrument_type,
            "voice_mode": voice_mode,
            "tuning": tuning,
            "capo": capo,
            "separate_sources": separate_sources,
            "tempo_bpm": tempo_bpm,
            "downbeat_offset_s": downbeat_offset_s,
            "beats_per_measure": beats_per_measure,
            "max_fret": max_fret,
        },
    )

    try:
        db.add(job)
        db.commit()
        db.refresh(job)
    except SQLAlchemyError as error:
        db.rollback()
        stored_upload.path.unlink(missing_ok=True)
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Database is unavailable") from error

    if background_tasks is not None:
        background_tasks.add_task(run_audio_preparation_for_job, job.id)
    return job


@router.get("/{job_id}", response_model=ProcessingJobResponse)
def get_processing_job(job_id: str, db: Session = Depends(get_db)) -> ProcessingJob:
    try:
        job = db.get(ProcessingJob, job_id)
    except SQLAlchemyError as error:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Database is unavailable") from error

    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Processing job was not found")

    return job


@router.get("/{job_id}/audio-preparation", response_model=AudioPreparationResponse)
def get_audio_preparation(
    job_id: str,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    try:
        job = db.get(ProcessingJob, job_id)
    except SQLAlchemyError as error:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Database is unavailable") from error

    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Processing job was not found")

    return _read_audio_preparation(
        job_id,
        settings,
        job.options.get(
            "audio_preparation",
            {
                "status": "pending",
                "progress": job.progress,
                "message": "Подготовка аудио ещё не началась.",
                "candidates": [],
            },
        ),
    )


@router.get("/{job_id}/audio-preparation/{candidate_id}")
def get_audio_candidate(
    job_id: str,
    candidate_id: str,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> FileResponse:
    try:
        job = db.get(ProcessingJob, job_id)
    except SQLAlchemyError as error:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Database is unavailable") from error

    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Processing job was not found")

    preparation = _read_audio_preparation(
        job_id,
        settings,
        job.options.get("audio_preparation", {}),
    )
    candidate = next(
        (item for item in preparation.get("candidates", []) if item.get("id") == candidate_id),
        None,
    )
    if candidate is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Audio candidate was not found")

    artifact_root = settings.artifacts_dir.resolve()
    candidate_path = (artifact_root / Path(candidate["storage_key"])).resolve()
    try:
        candidate_path.relative_to(artifact_root)
    except ValueError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Audio candidate was not found") from error
    if not candidate_path.is_file():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Audio candidate file was not found")

    return FileResponse(
        candidate_path,
        media_type=candidate.get("content_type", "audio/wav"),
        filename=candidate.get("filename", f"{candidate_id}.wav"),
        content_disposition_type="inline",
    )


@router.post("/{job_id}/audio-preparation/tab", response_model=GeneratedTabResponse)
def create_prepared_tab(
    job_id: str,
    candidate_id: str | None = None,
) -> dict[str, Any]:
    """Build a file-backed tab from the selected GAPS MIDI candidate."""

    try:
        return create_tab_from_prepared_audio(job_id, candidate_id)
    except FileNotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(error)) from error
    except RuntimeError as error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from error


def _read_audio_preparation(
    job_id: str,
    settings: Settings,
    fallback: dict[str, Any],
) -> dict[str, Any]:
    """Read live preparation state from artifacts, with DB fallback for old jobs."""

    artifact_root = settings.artifacts_dir.resolve()
    job_dir = (artifact_root / "jobs" / job_id).resolve()
    try:
        job_dir.relative_to(artifact_root)
    except ValueError:
        return fallback

    state_path = job_dir / "audio_preparation" / "state.json"
    manifest_path = job_dir / "audio_preparation" / "manifest.json"
    state: dict[str, Any] = {}
    if state_path.is_file():
        try:
            state = json.loads(state_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            state = {}

    if manifest_path.is_file():
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            manifest = None
        if isinstance(manifest, dict):
            state = {
                **state,
                "status": "ready",
                "progress": 100,
                "message": state.get(
                    "message",
                    "Гитарные кандидаты и ноты GAPS готовы к просмотру.",
                ),
                "model_name": manifest.get("model_name"),
                "transcription_model": manifest.get("transcription_model"),
                "passes": manifest.get("passes"),
                "tuning": manifest.get("tuning"),
                "max_fret": manifest.get("max_fret"),
                "capo": manifest.get("capo"),
                "manifest_storage_key": manifest_path.relative_to(artifact_root).as_posix(),
                "candidates": manifest.get("candidates", []),
            }

    return state or fallback


@router.get("/{job_id}/tab", response_model=GeneratedTabResponse)
def get_processing_job_result(
    job_id: str,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> GeneratedTab | dict[str, Any]:
    try:
        job = db.get(ProcessingJob, job_id)
        if job is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Processing job was not found")

        tab = db.scalar(select(GeneratedTab).where(GeneratedTab.processing_job_id == job_id))
    except SQLAlchemyError as error:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Database is unavailable") from error

    if tab is None:
        prepared_tab = get_prepared_tab(job_id, settings)
        if prepared_tab is not None:
            return prepared_tab
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Processing job is {job.status.value}; generated tab is not available yet",
        )

    return tab
