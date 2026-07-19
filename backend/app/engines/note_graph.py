"""Build a conservative, confidence-aware graph from MIDI candidates.

GAPS may produce slightly different note boundaries for the Demucs stems.
This stage clusters observations by pitch and onset, merges corroborated
observations, and keeps unmatched observations only from the selected source.
It therefore gains agreement between candidates without blindly taking the
union of two noisy MIDI files.
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass
from pathlib import Path


logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class NoteGraphResult:
    midi_path: Path
    note_count: int
    corroborated_count: int
    selected_source_count: int
    dropped_unselected_count: int
    metrics: dict[str, int | float]


@dataclass(frozen=True)
class _Observation:
    source_index: int
    pitch: int
    start: float
    end: float
    velocity: int
    onset_confidence: float


def build_unified_note_graph(
    candidates: list[tuple[Path, Path, Path | None]],
    selected_midi_path: Path,
    output_path: Path,
    onset_tolerance_s: float = 0.09,
) -> NoteGraphResult:
    """Merge candidate MIDI files into a single conservative MIDI graph."""

    import pretty_midi

    observations: list[_Observation] = []
    selected_source_indexes: set[int] = set()
    for source_index, (_, midi_path, _) in enumerate(candidates):
        if midi_path.resolve() == selected_midi_path.resolve():
            selected_source_indexes.add(source_index)
        onset_times = _detect_onsets(candidates[source_index][0])
        midi = pretty_midi.PrettyMIDI(str(midi_path))
        for instrument in midi.instruments:
            for note in instrument.notes:
                if note.end <= note.start or note.velocity <= 0:
                    continue
                observations.append(
                    _Observation(
                        source_index,
                        int(note.pitch),
                        float(note.start),
                        float(note.end),
                        int(note.velocity),
                        _onset_confidence(float(note.start), onset_times),
                    )
                )

    clusters = _cluster_observations(observations, onset_tolerance_s)
    graph_notes = []
    corroborated_count = 0
    selected_source_count = 0
    dropped_unselected_count = 0

    for cluster in clusters:
        source_indexes = {observation.source_index for observation in cluster}
        corroborated = len(source_indexes) > 1
        selected_source = bool(source_indexes & selected_source_indexes)
        if not corroborated and not selected_source:
            dropped_unselected_count += 1
            continue

        if corroborated:
            corroborated_count += 1
        else:
            selected_source_count += 1

        start = sum(observation.start for observation in cluster) / len(cluster)
        end = max(observation.end for observation in cluster)
        velocity = _graph_velocity(cluster, len(candidates), corroborated)
        graph_notes.append((start, end, cluster[0].pitch, velocity))

    graph_notes.sort(key=lambda item: (item[0], item[2]))
    if not graph_notes:
        raise RuntimeError("Note graph contains no usable notes")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    midi = pretty_midi.PrettyMIDI()
    instrument = pretty_midi.Instrument(program=27, name="Unified guitar")
    instrument.notes.extend(
        pretty_midi.Note(
            velocity=int(velocity),
            pitch=int(pitch),
            start=float(start),
            end=float(end),
        )
        for start, end, pitch, velocity in graph_notes
    )
    midi.instruments.append(instrument)
    midi.write(str(output_path))

    result = NoteGraphResult(
        midi_path=output_path,
        note_count=len(graph_notes),
        corroborated_count=corroborated_count,
        selected_source_count=selected_source_count,
        dropped_unselected_count=dropped_unselected_count,
        metrics={
            "candidate_count": len(candidates),
            "observations": len(observations),
            "graph_notes": len(graph_notes),
            "corroborated_notes": corroborated_count,
            "selected_source_notes": selected_source_count,
            "dropped_unselected_notes": dropped_unselected_count,
            "corroboration_ratio": round(corroborated_count / len(graph_notes), 4),
            "onset_aligned_notes": sum(
                1 for cluster in clusters if _cluster_onset_confidence(cluster) >= 0.5
            ),
        },
    )
    logger.info(
        "Note graph: %s notes (%s corroborated, %s selected-source, %s dropped)",
        result.note_count,
        result.corroborated_count,
        result.selected_source_count,
        result.dropped_unselected_count,
    )
    return result


def _cluster_observations(
    observations: list[_Observation],
    onset_tolerance_s: float,
) -> list[list[_Observation]]:
    clusters: list[list[_Observation]] = []
    for observation in sorted(observations, key=lambda item: (item.pitch, item.start, item.source_index)):
        matching = next(
            (
                cluster
                for cluster in reversed(clusters)
                if cluster[0].pitch == observation.pitch
                and abs(cluster[0].start - observation.start) <= onset_tolerance_s
            ),
            None,
        )
        if matching is None:
            clusters.append([observation])
        else:
            matching.append(observation)
    return clusters


def _graph_velocity(
    cluster: list[_Observation],
    candidate_count: int,
    corroborated: bool,
) -> int:
    mean_velocity = sum(observation.velocity for observation in cluster) / len(cluster)
    support_ratio = len({observation.source_index for observation in cluster}) / max(candidate_count, 1)
    onset_confidence = _cluster_onset_confidence(cluster)
    source_confidence = 0.72 + 0.28 * support_ratio if corroborated else 0.72
    confidence = source_confidence * (0.88 + 0.12 * onset_confidence)
    return max(1, min(127, round(mean_velocity * confidence)))


def _detect_onsets(audio_path: Path) -> list[float]:
    """Detect broad audio attacks without making them a hard filter."""

    try:
        import librosa

        audio, sample_rate = librosa.load(audio_path, sr=22050, mono=True)
        return [
            float(value)
            for value in librosa.onset.onset_detect(
                y=audio,
                sr=sample_rate,
                units="time",
                backtrack=False,
            )
        ]
    except Exception as error:  # pragma: no cover - depends on optional audio codecs
        logger.warning("Note graph: onset detection skipped for %s: %s", audio_path.name, error)
        return []


def _onset_confidence(start: float, onset_times: list[float]) -> float:
    if not onset_times:
        return 0.5
    distance = min(abs(start - onset) for onset in onset_times)
    return math.exp(-distance / 0.08)


def _cluster_onset_confidence(cluster: list[_Observation]) -> float:
    return sum(observation.onset_confidence for observation in cluster) / len(cluster)
