"""Choose the most usable transcription from several guitar candidates.

This module deliberately scores the MIDI result, not the source waveform.
The score is based on properties that are independent of a particular song:
playable pitch range, note fragmentation, duplicate detections, and usable
velocity/onset information.  It is a safety gate, not a claim that the
remaining MIDI is a perfect transcription.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

from app.engines.tuning import get_tuning


logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class MidiCandidateEvaluation:
    audio_path: Path
    midi_path: Path
    score: float
    metrics: dict[str, float | int]


def select_best_midi_candidate(
    candidates: list[tuple[Path, Path, Path | None]],
    tuning: str = "standard_e",
    max_fret: int = 20,
    capo: int = 0,
) -> tuple[MidiCandidateEvaluation, list[MidiCandidateEvaluation]]:
    """Evaluate all transcriptions and return the strongest one.

    Candidate order is preserved in the returned evaluations for manifest and
    debugging output.  A candidate with no valid notes is never selected when
    another candidate contains usable notes.
    """

    evaluations = [
        _evaluate_candidate(audio_path, midi_path, tuning, max_fret, capo)
        for audio_path, midi_path, _ in candidates
    ]
    if not evaluations:
        raise ValueError("No MIDI candidates were produced")

    selected = max(evaluations, key=lambda item: item.score)
    logger.info(
        "Transcription selection: %s selected (score=%.4f; candidates=%s)",
        selected.midi_path.name,
        selected.score,
        ", ".join(f"{item.midi_path.name}:{item.score:.4f}" for item in evaluations),
    )
    return selected, evaluations


def _evaluate_candidate(
    audio_path: Path,
    midi_path: Path,
    tuning: str,
    max_fret: int,
    capo: int,
) -> MidiCandidateEvaluation:
    import pretty_midi

    midi = pretty_midi.PrettyMIDI(str(midi_path))
    notes = [
        note
        for instrument in midi.instruments
        for note in instrument.notes
        if note.end > note.start and note.velocity > 0
    ]
    if not notes:
        return MidiCandidateEvaluation(
            audio_path,
            midi_path,
            float("-inf"),
            {"note_count": 0, "usable": 0},
        )

    open_pitches = list(get_tuning(tuning)["midi"])
    lowest_pitch = min(open_pitches) + capo
    highest_pitch = max(open_pitches) + max_fret + capo

    starts = sorted(float(note.start) for note in notes)
    unique_onsets = 1 + sum(
        1 for previous, current in zip(starts, starts[1:]) if current - previous > 0.09
    )
    short_count = sum(1 for note in notes if note.end - note.start < 0.06)
    out_of_range_count = sum(
        1 for note in notes if note.pitch < lowest_pitch or note.pitch > highest_pitch
    )

    duplicate_count = 0
    last_start_by_pitch: dict[int, float] = {}
    for note in sorted(notes, key=lambda item: item.start):
        previous_start = last_start_by_pitch.get(int(note.pitch))
        if previous_start is not None and note.start - previous_start < 0.08:
            duplicate_count += 1
        last_start_by_pitch[int(note.pitch)] = float(note.start)

    notes_per_onset = len(notes) / max(unique_onsets, 1)
    overfull_onsets = max(0.0, notes_per_onset - 6.0) / 6.0
    metrics: dict[str, float | int] = {
        "note_count": len(notes),
        "unique_onsets": unique_onsets,
        "notes_per_onset": round(notes_per_onset, 4),
        "duration_s": round(float(max(note.end for note in notes)), 4),
        "pitch_min": min(int(note.pitch) for note in notes),
        "pitch_max": max(int(note.pitch) for note in notes),
        "short_note_ratio": round(short_count / len(notes), 4),
        "duplicate_onset_ratio": round(duplicate_count / len(notes), 4),
        "out_of_guitar_range_ratio": round(out_of_range_count / len(notes), 4),
        "mean_velocity": round(sum(note.velocity for note in notes) / len(notes), 4),
    }

    playable_ratio = 1.0 - (out_of_range_count / len(notes))
    sustained_ratio = 1.0 - (short_count / len(notes))
    duplicate_ratio = 1.0 - (duplicate_count / len(notes))
    velocity_score = min(1.0, sum(note.velocity for note in notes) / (len(notes) * 127.0))
    chord_capacity_score = max(0.0, 1.0 - overfull_onsets)

    # These are relative transcription-health signals.  No note density or
    # fret pattern from a particular song is encoded here.
    score = (
        playable_ratio * 0.32
        + sustained_ratio * 0.22
        + duplicate_ratio * 0.22
        + velocity_score * 0.14
        + chord_capacity_score * 0.10
    )
    metrics["score"] = round(score, 6)
    metrics["usable"] = 1
    return MidiCandidateEvaluation(audio_path, midi_path, score, metrics)
