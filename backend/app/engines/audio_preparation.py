"""Reusable audio-only preparation stage for future workers and the API bridge."""

from __future__ import annotations

import json
import logging
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from app.engines.source_separation import isolate_repeated_guitar_candidates


logger = logging.getLogger(__name__)
PreparationProgress = Callable[[int, str], None]


@dataclass(frozen=True)
class AudioPreparationResult:
    manifest_path: Path
    manifest: dict


def prepare_audio_with_demucs(
    audio_path: Path,
    job_output_dir: Path,
    artifact_root: Path,
    model_name: str = "htdemucs_6s",
    passes: int = 2,
    tuning: str = "standard_e",
    max_fret: int = 20,
    capo: int = 0,
    progress_callback: PreparationProgress | None = None,
) -> AudioPreparationResult:
    """Create Demucs candidates and transcribe each one with GAPS.

    This function has no database or HTTP dependency.  A future worker can
    call it directly; the current API bridge runs it in a dedicated audio
    Python subprocess because the API environment intentionally does not
    import torch or Demucs.
    """

    audio_path = audio_path.resolve()
    job_output_dir = job_output_dir.resolve()
    artifact_root = artifact_root.resolve()
    manifest_path = job_output_dir / "audio_preparation" / "manifest.json"

    if manifest_path.is_file():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if all(
            (artifact_root / candidate["storage_key"]).is_file()
            for candidate in manifest.get("candidates", [])
        ) and all("notes" in candidate for candidate in manifest.get("candidates", [])) and (
            manifest.get("transcription_model") == "GAPS"
            and manifest.get("tuning") == tuning
            and manifest.get("max_fret") == max_fret
            and manifest.get("capo") == capo
        ):
            logger.info("Audio preparation: reusing manifest %s", manifest_path)
            _report(progress_callback, 100, "Demucs candidates are ready")
            return AudioPreparationResult(manifest_path, manifest)

    started_at = time.monotonic()
    _report(progress_callback, 10, "Starting Demucs pass 1")
    candidates = isolate_repeated_guitar_candidates(
        audio_path,
        job_output_dir,
        model_name=model_name,
        passes=passes,
    )
    _report(progress_callback, 55, "Transcribing each candidate with GAPS")
    candidate_payload = _transcribe_candidates(
        candidates,
        job_output_dir,
        tuning=tuning,
        max_fret=max_fret,
        capo=capo,
        progress_callback=progress_callback,
    )
    _report(progress_callback, 90, "Writing candidate metadata")

    for candidate in candidate_payload:
        try:
            candidate_path = Path(candidate.pop("_audio_path"))
            relative_path = candidate_path.resolve().relative_to(artifact_root)
        except ValueError as error:
            raise RuntimeError(f"Candidate path escaped artifact storage: {candidate_path}") from error

        import soundfile

        info = soundfile.info(candidate_path)
        candidate["filename"] = candidate_path.name
        candidate["storage_key"] = relative_path.as_posix()
        candidate["content_type"] = "audio/wav"
        candidate["size_bytes"] = candidate_path.stat().st_size
        candidate["sample_rate"] = int(info.samplerate)
        candidate["channels"] = int(info.channels)
        candidate["duration_seconds"] = round(float(info.duration), 3)
        midi_path_value = candidate.pop("_midi_path", None)
        if midi_path_value:
            midi_path = Path(midi_path_value)
            try:
                midi_relative_path = midi_path.resolve().relative_to(artifact_root)
            except ValueError as error:
                raise RuntimeError(f"MIDI path escaped artifact storage: {midi_path}") from error
            candidate["midi_storage_key"] = midi_relative_path.as_posix()
            candidate["midi_filename"] = midi_path.name

    manifest = {
        "version": 1,
        "status": "ready",
        "source_filename": audio_path.name,
        "model_name": model_name,
        "passes": passes,
        "transcription_model": "GAPS",
        "tuning": tuning,
        "max_fret": max_fret,
        "capo": capo,
        "candidates": candidate_payload,
        "created_at_epoch": time.time(),
    }
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    _report(progress_callback, 100, "Demucs candidates are ready")
    logger.info(
        "Audio preparation: ready in %.1fs (candidates=%s, manifest=%s)",
        time.monotonic() - started_at,
        len(candidate_payload),
        manifest_path,
    )
    return AudioPreparationResult(manifest_path, manifest)


def _transcribe_candidates(
    candidates: list[tuple[str, str, int, Path]],
    job_output_dir: Path,
    *,
    tuning: str,
    max_fret: int,
    capo: int,
    progress_callback: PreparationProgress | None = None,
) -> list[dict]:
    from app.engines.guitar_transcription import transcribe_guitar_to_midi

    from app.engines.transcription_selection import select_best_midi_candidate

    transcription_dir = job_output_dir / "transcription_candidates"
    transcription_dir.mkdir(parents=True, exist_ok=True)
    successful: list[tuple[Path, Path, Path | None]] = []
    payload: list[dict] = []

    total_candidates = len(candidates)
    for candidate_index, (candidate_id, label, pass_index, audio_path) in enumerate(candidates):
        progress = 55 + round(30 * candidate_index / max(total_candidates, 1))
        _report(
            progress_callback,
            progress,
            f"GAPS: {label} ({candidate_index + 1}/{total_candidates})",
        )
        item = {
            "id": candidate_id,
            "label": label,
            "pass_index": pass_index,
            "_audio_path": str(audio_path),
        }
        try:
            midi_path, events_path = transcribe_guitar_to_midi(
                audio_path,
                transcription_dir,
                tuning=tuning,
                max_fret=max_fret,
            )
            item["_midi_path"] = str(midi_path)
            item["notes"] = _read_midi_notes(midi_path)
            item["note_count"] = len(item["notes"])
            successful.append((audio_path, midi_path, events_path))
        except Exception as error:  # one noisy candidate must not hide the others
            logger.exception("GAPS: candidate %s failed", candidate_id)
            item["notes"] = []
            item["note_count"] = 0
            item["gaps_error"] = str(error)
        payload.append(item)
        _report(
            progress_callback,
            55 + round(30 * (candidate_index + 1) / max(total_candidates, 1)),
            f"GAPS: обработан кандидат {candidate_index + 1}/{total_candidates}",
        )

    if not successful:
        raise RuntimeError("GAPS did not produce MIDI for any Demucs candidate")

    selected, evaluations = select_best_midi_candidate(
        successful,
        tuning=tuning,
        max_fret=max_fret,
        capo=capo,
    )
    evaluations_by_midi = {evaluation.midi_path.resolve(): evaluation for evaluation in evaluations}
    for item in payload:
        midi_path_value = item.get("_midi_path")
        if not midi_path_value:
            item["selected"] = False
            continue
        evaluation = evaluations_by_midi[Path(midi_path_value).resolve()]
        item["gaps_quality"] = evaluation.metrics
        # ``select_best_midi_candidate`` returns the first candidate only when
        # every MIDI is empty (all scores are -inf).  That is not a real
        # selection, so do not show a misleading "best" badge in that case.
        item["selected"] = (
            evaluation.score != float("-inf")
            and evaluation.midi_path.resolve() == selected.midi_path.resolve()
        )
    return payload


def _read_midi_notes(midi_path: Path) -> list[dict]:
    import pretty_midi

    midi = pretty_midi.PrettyMIDI(str(midi_path))
    notes = []
    for instrument in midi.instruments:
        for note in instrument.notes:
            if note.end <= note.start or note.velocity <= 0:
                continue
            notes.append(
                {
                    "id": f"n-{len(notes) + 1}",
                    "pitch": int(note.pitch),
                    "name": pretty_midi.note_number_to_name(int(note.pitch)),
                    "start_seconds": round(float(note.start), 3),
                    "duration_seconds": round(float(note.end - note.start), 3),
                    "velocity": int(note.velocity),
                }
            )
    notes.sort(key=lambda item: (item["start_seconds"], item["pitch"]))
    return notes


def _report(callback: PreparationProgress | None, progress: int, message: str) -> None:
    logger.info("Audio preparation: %s%% - %s", progress, message)
    if callback is not None:
        callback(progress, message)
