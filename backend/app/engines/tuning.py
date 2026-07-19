"""Data-driven guitar tuning definitions shared by all transcription stages."""

from __future__ import annotations

from typing import TypedDict


class TuningDefinition(TypedDict):
    names: tuple[str, ...]
    midi: tuple[int, ...]


TUNINGS: dict[str, TuningDefinition] = {
    "standard_e": {
        "names": ("E", "B", "G", "D", "A", "E"),
        "midi": (40, 45, 50, 55, 59, 64),
    },
    "c_sharp": {
        "names": ("E", "B", "G", "D", "A", "C#"),
        "midi": (37, 45, 50, 55, 59, 64),
    },
    "drop_d": {
        "names": ("E", "B", "G", "D", "A", "D"),
        "midi": (38, 45, 50, 55, 59, 64),
    },
}


def get_tuning(tuning: str) -> TuningDefinition:
    return TUNINGS.get(tuning, TUNINGS["standard_e"])
