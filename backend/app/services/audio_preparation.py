"""API bridge for the reusable Demucs-only preparation stage."""

from __future__ import annotations

import json
import logging
import os
import re
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path

from app.core.settings import Settings, get_settings
from app.db.models import ProcessingJob, ProcessingJobStatus
from app.db.session import SessionLocal


logger = logging.getLogger(__name__)
PreparationProgress = Callable[[int, str], None]


def run_audio_preparation_for_job(job_id: str) -> None:
    """Run Demucs/GAPS and persist preparation state in the artifact folder.

    This function is intentionally shaped like a worker task: it claims no
    queue itself and owns one job lifecycle.  The current API schedules it as
    a background task; a future worker can call it from its queue consumer.

    The processing result is deliberately file-backed for now.  The database
    row created by ``POST /jobs`` is read only; progress, notes, MIDI paths,
    and the final preparation state are not written to MySQL.
    """

    settings = get_settings()
    session = SessionLocal()
    state_path: Path | None = None
    try:
        job = session.get(ProcessingJob, job_id)
        if job is None or job.status not in {
            ProcessingJobStatus.QUEUED,
            ProcessingJobStatus.PROCESSING,
        }:
            return

        options = dict(job.options or {})
        audio_path = _safe_join(settings.uploads_dir, job.audio_asset.storage_key)
        job_output_dir = _safe_join(settings.artifacts_dir / "jobs", job.id)
        job_output_dir.mkdir(parents=True, exist_ok=True)
        state_path = job_output_dir / "audio_preparation" / "state.json"

        _write_preparation_state(
            state_path,
            _preparation_state(
                status="processing",
                progress=5,
                message="Подготавливаем аудио через Demucs...",
                settings=settings,
            ),
        )
        # Do not keep a database session open while CPU/GPU processing runs.
        # The preparation stage does not need to write to processing_jobs.
        session.close()
        session = None

        if not options.get("separate_sources", True):
            _write_preparation_state(
                state_path,
                _preparation_state(
                    status="ready",
                    progress=100,
                    message="Выделение отключено: используется исходное аудио.",
                    settings=settings,
                    candidates=[],
                ),
            )
            return

        def report_progress(progress: int, message: str) -> None:
            _write_preparation_state(
                state_path,
                _preparation_state(
                    status="processing",
                    progress=progress,
                    message=message,
                    settings=settings,
                ),
            )

        _run_demucs_subprocess(
            audio_path,
            job_output_dir,
            settings,
            progress_callback=report_progress,
            tuning=str(options.get("tuning", "standard_e")),
            max_fret=int(options.get("max_fret", 20)),
            capo=int(options.get("capo", 0)),
        )
        manifest_path = job_output_dir / "audio_preparation" / "manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

        _write_preparation_state(
            state_path,
            _preparation_state(
                status="ready",
                progress=100,
                message="Гитарные кандидаты и ноты GAPS готовы к просмотру.",
                settings=settings,
                candidates=[],
                manifest_storage_key=manifest_path.resolve().relative_to(
                    settings.artifacts_dir.resolve()
                ).as_posix(),
            ),
        )
        logger.info(
            "Audio preparation: job %s is ready (candidates=%s; database untouched)",
            job_id,
            len(manifest.get("candidates", [])),
        )
    except Exception as error:
        if state_path is not None:
            try:
                _write_preparation_state(
                    state_path,
                    _preparation_state(
                        status="failed",
                        progress=0,
                        message=str(error),
                        settings=settings,
                    ),
                )
            except Exception:
                logger.exception("Audio preparation: could not write failed state for %s", job_id)
        logger.exception("Audio preparation failed for job %s; database was not changed", job_id)
    finally:
        if session is not None:
            session.close()


def _run_demucs_subprocess(
    audio_path: Path,
    job_output_dir: Path,
    settings: Settings,
    *,
    progress_callback: PreparationProgress | None = None,
    tuning: str = "standard_e",
    max_fret: int = 20,
    capo: int = 0,
) -> None:
    python_path = _find_audio_python(settings)
    command = [
        str(python_path),
        "-u",
        "-m",
        "app.audio_preparation_runner",
        "--audio",
        str(audio_path),
        "--job-output",
        str(job_output_dir),
        "--artifact-root",
        str(settings.artifacts_dir.resolve()),
        "--model",
        settings.demucs_model_name,
        "--passes",
        str(settings.demucs_passes),
        "--tuning",
        tuning,
        "--max-fret",
        str(max_fret),
        "--capo",
        str(capo),
    ]
    environment = os.environ.copy()
    environment["PYTHONUNBUFFERED"] = "1"
    backend_dir = str(settings.backend_dir.resolve())
    environment["PYTHONPATH"] = os.pathsep.join(
        value for value in (backend_dir, environment.get("PYTHONPATH")) if value
    )
    logger.info(
        "Audio preparation: running Demucs subprocess (python=%s, model=%s, passes=%s)",
        python_path,
        settings.demucs_model_name,
        settings.demucs_passes,
    )
    process = subprocess.Popen(
        command,
        cwd=backend_dir,
        env=environment,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )
    output_lines: list[str] = []
    assert process.stdout is not None
    for line in process.stdout:
        line = line.rstrip()
        if not line:
            continue
        output_lines.append(line)
        logger.info("Demucs subprocess: %s", line)
        match = re.search(r"Audio preparation: (\d+)% - (.+)$", line)
        if match and progress_callback is not None:
            progress_callback(int(match.group(1)), match.group(2))

    returncode = process.wait()
    if returncode != 0:
        error_output = "\n".join(output_lines)[-4000:] or "Demucs subprocess failed"
        raise RuntimeError(f"Demucs subprocess failed with code {returncode}: {error_output}")

def _find_audio_python(settings: Settings) -> Path:
    configured = str(settings.audio_processing_python or "").strip()
    configured_path = Path(configured).expanduser() if configured else None
    if configured_path is not None and not configured_path.is_absolute():
        configured_path = settings.backend_dir / configured_path
    candidates = [
        configured_path,
        settings.backend_dir / ".venv-audio/bin/python",
        settings.backend_dir / ".venv-worker/bin/python",
        Path(sys.executable),
    ]
    for candidate in candidates:
        if candidate is not None and candidate.is_file():
            # Do not resolve the venv's ``bin/python`` symlink: resolving it
            # turns the virtualenv interpreter into the system interpreter
            # and drops installed packages such as numpy and Demucs.
            return candidate.absolute()
    raise RuntimeError("No Python environment with Demucs was found")


def _preparation_state(
    *,
    status: str,
    progress: int,
    message: str,
    settings: Settings,
    candidates: list[dict] | None = None,
    manifest_storage_key: str | None = None,
) -> dict:
    state = {
        "status": status,
        "progress": progress,
        "message": message,
        "model_name": settings.demucs_model_name,
        "passes": settings.demucs_passes,
        "transcription_model": "GAPS",
        "candidates": candidates if candidates is not None else [],
    }
    if manifest_storage_key is not None:
        state["manifest_storage_key"] = manifest_storage_key
    return state


def _write_preparation_state(path: Path, preparation: dict) -> None:
    """Atomically publish progress without touching ``processing_jobs``."""

    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = path.with_suffix(".tmp")
    temporary_path.write_text(
        json.dumps(preparation, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    temporary_path.replace(path)


def _safe_join(root: Path, relative_path: str | Path) -> Path:
    root = root.resolve()
    candidate = (root / Path(relative_path)).resolve()
    try:
        candidate.relative_to(root)
    except ValueError as error:
        raise ValueError("Storage path escapes configured storage root") from error
    return candidate
