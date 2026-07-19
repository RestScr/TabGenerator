"""File-backed tab generation from the selected GAPS MIDI candidate."""

from __future__ import annotations

import json
import logging
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from app.core.settings import Settings, get_settings
from app.db.models import ProcessingJob
from app.db.session import SessionLocal
from app.services.audio_preparation import _find_audio_python


logger = logging.getLogger(__name__)


def create_tab_from_prepared_audio(
    job_id: str,
    candidate_id: str | None = None,
) -> dict:
    """Render and return a tab without writing anything to MySQL."""

    settings = get_settings()
    session = SessionLocal()
    try:
        job = session.get(ProcessingJob, job_id)
        if job is None:
            raise FileNotFoundError(f"Processing job was not found: {job_id}")
        options = dict(job.options or {})
        source_audio_path = _safe_join(settings.uploads_dir, job.audio_asset.storage_key)
        title = Path(job.audio_asset.original_filename).stem
    finally:
        session.close()

    artifact_root = settings.artifacts_dir.resolve()
    job_dir = _safe_join(artifact_root / "jobs", job_id)
    preparation_dir = job_dir / "audio_preparation"
    manifest_path = preparation_dir / "manifest.json"
    if not manifest_path.is_file():
        raise RuntimeError("GAPS manifest is not ready yet")

    manifest = _read_json(manifest_path)
    candidates = manifest.get("candidates", [])
    candidate = next(
        (item for item in candidates if item.get("id") == candidate_id),
        None,
    ) if candidate_id else next(
        (item for item in candidates if item.get("selected")),
        None,
    )
    if candidate is None:
        candidate = next((item for item in candidates if item.get("midi_storage_key")), None)
    if candidate is None or not candidate.get("midi_storage_key"):
        raise RuntimeError("No GAPS MIDI candidate is available for tablature generation")

    selected_id = str(candidate["id"])
    tab_root = job_dir / "tab_generation"
    tab_manifest_path = tab_root / "manifest.json"
    if tab_manifest_path.is_file():
        cached = _read_json(tab_manifest_path)
        if cached.get("candidate_id") == selected_id and _tab_artifacts_exist(cached, artifact_root):
            return _load_tab_response(cached, artifact_root)

    midi_path = _safe_storage_path(artifact_root, candidate["midi_storage_key"])
    output_dir = tab_root / selected_id
    output_dir.mkdir(parents=True, exist_ok=True)
    python_path = _find_audio_python(settings)
    command = [
        str(python_path),
        "-u",
        "-m",
        "app.tab_generation_runner",
        "--audio",
        str(source_audio_path),
        "--midi",
        str(midi_path),
        "--output",
        str(output_dir),
        "--artifact-root",
        str(artifact_root),
        "--instrument",
        str(options.get("instrument_type", "lead_guitar")),
        "--voice-mode",
        str(options.get("voice_mode", "guitar")),
        "--tuning",
        str(options.get("tuning", manifest.get("tuning", "standard_e"))),
        "--capo",
        str(int(options.get("capo", manifest.get("capo", 0)))),
        "--downbeat-offset",
        str(float(options.get("downbeat_offset_s", 0.0))),
        "--beats-per-measure",
        str(int(options.get("beats_per_measure", 4))),
        "--max-fret",
        str(int(options.get("max_fret", manifest.get("max_fret", 20)))),
    ]
    tempo = options.get("tempo_bpm")
    if tempo is not None:
        command.extend(["--tempo", str(int(tempo))])

    environment = os.environ.copy()
    environment["PYTHONUNBUFFERED"] = "1"
    backend_dir = str(settings.backend_dir.resolve())
    environment["PYTHONPATH"] = os.pathsep.join(
        value for value in (backend_dir, environment.get("PYTHONPATH")) if value
    )
    logger.info("GAPS-to-tab: rendering candidate %s for job %s", selected_id, job_id)
    process = subprocess.run(
        command,
        cwd=backend_dir,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )
    if process.returncode != 0:
        output = (process.stdout + "\n" + process.stderr)[-6000:]
        raise RuntimeError(f"Tab generation subprocess failed with code {process.returncode}: {output}")

    result = _read_json(output_dir / "result.json")
    now = datetime.now(timezone.utc).isoformat()
    tab_manifest = {
        "version": 1,
        "id": job_id,
        "processing_job_id": job_id,
        "candidate_id": selected_id,
        "title": title,
        "tempo_bpm": int(result["tempo_bpm"]),
        "created_at": now,
        "updated_at": now,
        "ascii_tab_storage_key": _storage_key(result["ascii_tab_storage_path"], artifact_root),
        "midi_storage_key": _storage_key(candidate["midi_storage_key"], artifact_root),
        "note_events_storage_key": _storage_key(result["note_events_storage_path"], artifact_root),
        "tab_data_storage_key": _storage_key(result["tab_data_storage_path"], artifact_root),
    }
    _write_json(tab_manifest_path, tab_manifest)
    return _load_tab_response(tab_manifest, artifact_root)


def get_prepared_tab(job_id: str, settings: Settings | None = None) -> dict | None:
    settings = settings or get_settings()
    artifact_root = settings.artifacts_dir.resolve()
    try:
        manifest_path = _safe_join(artifact_root / "jobs", job_id) / "tab_generation" / "manifest.json"
    except ValueError:
        return None
    if not manifest_path.is_file():
        return None
    try:
        return _load_tab_response(_read_json(manifest_path), artifact_root)
    except (OSError, KeyError, ValueError, json.JSONDecodeError):
        logger.exception("GAPS-to-tab: invalid tab manifest for job %s", job_id)
        return None


def _load_tab_response(manifest: dict, artifact_root: Path) -> dict:
    ascii_tab = _safe_storage_path(artifact_root, manifest["ascii_tab_storage_key"]).read_text(encoding="utf-8")
    tab_data = _read_json(_safe_storage_path(artifact_root, manifest["tab_data_storage_key"]))
    return {
        "id": manifest["id"],
        "processing_job_id": manifest["processing_job_id"],
        "title": manifest["title"],
        "tempo_bpm": manifest["tempo_bpm"],
        "created_at": manifest["created_at"],
        "updated_at": manifest["updated_at"],
        "ascii_tab": ascii_tab,
        "ascii_tab_storage_key": manifest["ascii_tab_storage_key"],
        "midi_storage_key": manifest.get("midi_storage_key"),
        "note_events_storage_key": manifest.get("note_events_storage_key"),
        "tab_data": tab_data,
    }


def _tab_artifacts_exist(manifest: dict, artifact_root: Path) -> bool:
    try:
        return all(
            _safe_storage_path(artifact_root, manifest[key]).is_file()
            for key in ("ascii_tab_storage_key", "tab_data_storage_key")
        )
    except (KeyError, ValueError):
        return False


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = path.with_suffix(".tmp")
    temporary_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary_path.replace(path)


def _storage_key(path: str, artifact_root: Path) -> str:
    return _safe_storage_path(artifact_root, path).relative_to(artifact_root).as_posix()


def _safe_storage_path(root: Path, storage_key: str) -> Path:
    return _safe_join(root, storage_key)


def _safe_join(root: Path, relative_path: str | Path) -> Path:
    root = root.resolve()
    candidate = (root / Path(relative_path)).resolve()
    try:
        candidate.relative_to(root)
    except ValueError as error:
        raise ValueError("Storage path escapes configured storage root") from error
    return candidate
