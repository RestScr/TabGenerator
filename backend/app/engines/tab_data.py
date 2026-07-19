"""Structured tablature data derived from the rendered tab events."""

from __future__ import annotations

from typing import Any


def build_tab_data(ascii_tab: str, tempo_bpm: int, tuning: str) -> dict[str, Any]:
    rows = []
    for line in ascii_tab.splitlines():
        separator = line.find("|")
        if separator < 1:
            continue
        measures = line[separator + 1 :].split("|")
        if measures and measures[-1] == "":
            measures.pop()
        rows.append((line[:separator].strip(), measures))

    if not rows:
        raise ValueError("Rendered tab does not contain string rows")

    measure_count = min(len(measures) for _, measures in rows)
    measures_data = []
    for measure_index in range(measure_count):
        notes = []
        for string_index, (_, row_measures) in enumerate(rows):
            segment = row_measures[measure_index]
            denominator = max(len(segment) - 1, 1)
            column = 0
            while column < len(segment):
                if not segment[column].isdigit():
                    column += 1
                    continue
                start_column = column
                fret = ""
                while column < len(segment) and segment[column].isdigit():
                    fret += segment[column]
                    column += 1
                notes.append(
                    {
                        "id": f"m{measure_index + 1}-s{string_index + 1}-c{start_column}",
                        "string": string_index,
                        "fret": int(fret),
                        "position": start_column / denominator,
                    }
                )
        measures_data.append({"number": measure_index + 1, "notes": notes})

    return {
        "version": 1,
        "tempo_bpm": tempo_bpm,
        "time_signature": [4, 4],
        "tuning": tuning,
        "strings": [name for name, _ in rows],
        "measures": measures_data,
    }


def add_timed_events(
    tab_data: dict[str, Any],
    note_events: list[dict[str, Any]],
    tempo_bpm: int,
    beats_per_measure: int,
    downbeat_offset_s: float,
) -> dict[str, Any]:
    """Attach lossless timing data to the legacy measure representation."""
    seconds_per_beat = 60.0 / tempo_bpm
    measure_duration = seconds_per_beat * beats_per_measure
    measures = tab_data.get("measures", [])

    timed_events = []
    for event_index, event in enumerate(note_events):
        start = float(event["start"])
        duration = max(0.0, float(event.get("duration", 0.0)))
        relative_start = max(0.0, start - downbeat_offset_s)
        measure_index = min(
            len(measures) - 1,
            max(0, int(relative_start // measure_duration)),
        ) if measures else 0
        measure_start = downbeat_offset_s + measure_index * measure_duration
        raw_beat = max(0.0, (start - measure_start) / seconds_per_beat)
        beat = min(float(beats_per_measure), round(raw_beat * 4) / 4)
        position = min(1.0, max(0.0, beat / beats_per_measure))
        duration_beats = max(0.25, round((duration / seconds_per_beat) * 4) / 4)
        end_beat = beat + duration_beats
        subdivision = _subdivision_name(duration_beats)
        timed_event = {
            **event,
            "id": f"note-{event_index + 1}",
            "measure": measure_index + 1,
            "beat": beat,
            "position": position,
            "duration": duration,
            "duration_beats": duration_beats,
            "subdivision": subdivision,
            "tie_start": False,
            "tie_end": end_beat > beats_per_measure,
        }
        timed_events.append(timed_event)
        if measures:
            measures[measure_index].setdefault("events", []).append(timed_event)

    tab_data["note_events"] = timed_events
    tab_data["timing"] = {
        "tempo_bpm": tempo_bpm,
        "beats_per_measure": beats_per_measure,
        "beat_duration_s": seconds_per_beat,
        "measure_duration_s": measure_duration,
        "downbeat_offset_s": downbeat_offset_s,
    }
    return tab_data


def _subdivision_name(duration_beats: float) -> str:
    if duration_beats >= 4:
        return "whole"
    if duration_beats >= 2:
        return "half"
    if duration_beats >= 1:
        return "quarter"
    if duration_beats >= 0.5:
        return "eighth"
    return "sixteenth"
