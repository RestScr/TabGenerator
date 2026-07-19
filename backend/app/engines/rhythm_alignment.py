"""Tempo overrides and measure alignment for generated tabs."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RhythmSettings:
    tempo_bpm: int | None = None
    downbeat_offset_s: float = 0.0
    beats_per_measure: int = 4


def apply_rhythm_settings(bpm_module: object, audio_path: object, settings: RhythmSettings) -> object:
    bpm_map = bpm_module.BPMMap(audio_path)
    if settings.tempo_bpm is None:
        return bpm_map

    if not bpm_map.bpm_map:
        raise RuntimeError("Could not build a tempo map for the audio file")
    duration = bpm_map.bpm_map[-1].end
    bpm_map.bpm_map = [bpm_module.BPMPart(0, duration, settings.tempo_bpm)]
    return bpm_map


def grid_units_per_measure(bpm_map: object, beats_per_measure: int) -> int:
    return max(1, round(beats_per_measure / bpm_map.beat_size))
