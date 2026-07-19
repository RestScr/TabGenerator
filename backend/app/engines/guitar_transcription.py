"""GAPS guitar audio-to-MIDI adapter for an isolated guitar stem."""

from __future__ import annotations

import logging
import time
from functools import lru_cache
from pathlib import Path

from app.engines.tuning import get_tuning


logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def _get_gaps_model():
    """Load GAPS once per audio-processing process and reuse it for candidates."""

    from hf_midi_transcription import MidiTranscriptionModel

    logger.info("GAPS: loading guitar model for candidate transcription")
    return MidiTranscriptionModel(device="cpu", instrument="guitar", batch_size=8)

def transcribe_guitar_to_midi(
    audio_path: Path,
    output_dir: Path,
    tuning: str = "standard_e",
    max_fret: int = 20,
) -> tuple[Path, Path | None]:
    """Run the guitar-specific GAPS model on ``guitar.wav``.

    GAPS is the one instrument-specific model selected for this pipeline.
    Fretboard mapping and deterministic cleanup remain downstream of this
    function.
    """
    if not audio_path.is_file():
        raise FileNotFoundError(f"Audio file was not found: {audio_path}")
    output_dir.mkdir(parents=True, exist_ok=True)

    started_at = time.monotonic()
    # Keep the tuning/max-fret arguments in the adapter contract. They are
    # consumed by the mapper after transcription; GAPS itself predicts pitches.
    get_tuning(tuning)
    midi_path = output_dir / f"{audio_path.stem}_gaps.mid"
    logger.info(
        "GAPS: transcribing isolated guitar stem %s (tuning=%s, max_fret=%s)",
        audio_path.name,
        tuning,
        max_fret,
    )
    model = _get_gaps_model()
    model.transcribe(audio_path, midi_path)
    if not midi_path.is_file():
        raise FileNotFoundError(f"GAPS did not create the expected MIDI output: {midi_path}")
    logger.info(
        "GAPS: MIDI saved in %.1fs (%s)",
        time.monotonic() - started_at,
        midi_path,
    )
    return midi_path, None


def transcribe_guitar_candidates_to_midi(
    audio_paths: list[Path],
    output_dir: Path,
    tuning: str = "standard_e",
    max_fret: int = 20,
) -> list[tuple[Path, Path, Path | None]]:
    """Transcribe every audio candidate with one shared GAPS instance.

    The returned tuple contains ``(audio_path, midi_path, events_path)`` so
    the selection stage can retain the provenance of the chosen MIDI file.
    """

    results = []
    candidate_output_dir = output_dir / "transcription_candidates"
    candidate_output_dir.mkdir(parents=True, exist_ok=True)
    for audio_path in audio_paths:
        midi_path, events_path = transcribe_guitar_to_midi(
            audio_path,
            candidate_output_dir,
            tuning=tuning,
            max_fret=max_fret,
        )
        results.append((audio_path, midi_path, events_path))
    return results
