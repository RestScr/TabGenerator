#!/usr/bin/env python3
import argparse
import csv
from collections import defaultdict
from pathlib import Path


NOTE_NAMES = ("C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B")
GUITAR_TUNING = [
    ("e", 64),
    ("B", 59),
    ("G", 55),
    ("D", 50),
    ("A", 45),
    ("E", 40),
]


def note_name(midi_note):
    octave = midi_note // 12 - 1
    return f"{NOTE_NAMES[midi_note % 12]}{octave}"


def choose_string(midi_note, max_fret):
    candidates = []
    for index, (name, open_note) in enumerate(GUITAR_TUNING):
        fret = midi_note - open_note
        if 0 <= fret <= max_fret:
            candidates.append((fret, index, name))
    if not candidates:
        return None
    # Prefer lower frets. Ties choose the physically higher string.
    fret, index, _ = min(candidates, key=lambda c: (c[0], c[1]))
    return index, fret


def read_notes(path, min_velocity):
    notes = []
    with open(path, newline="") as f:
        reader = csv.reader(f)
        header = next(reader, None)
        for row in reader:
            if len(row) < 4:
                continue
            try:
                start = float(row[0])
                end = float(row[1])
                pitch = int(row[2])
                velocity = int(row[3])
            except ValueError:
                continue
            if velocity < min_velocity:
                continue
            notes.append((start, end, pitch, velocity))
    return sorted(notes, key=lambda n: (n[0], n[2]))


def render_tab(notes, max_fret, quantize, columns_per_line):
    grouped = defaultdict(list)
    for start, end, pitch, velocity in notes:
        grouped[round(start / quantize) * quantize].append((pitch, velocity, start, end))

    events = []
    for start in sorted(grouped):
        placements = {}
        labels = []
        for pitch, velocity, raw_start, raw_end in sorted(grouped[start], reverse=True):
            placement = choose_string(pitch, max_fret)
            if placement is None:
                continue
            string_index, fret = placement
            if string_index in placements:
                continue
            placements[string_index] = str(fret)
            labels.append(note_name(pitch))
        if placements:
            width = max(len(fret) for fret in placements.values())
            events.append((start, placements, width, "/".join(reversed(labels))))

    blocks = []
    for block_start in range(0, len(events), columns_per_line):
        block = events[block_start : block_start + columns_per_line]
        lines = {i: [name + "|"] for i, (name, _) in enumerate(GUITAR_TUNING)}
        time_line = ["   "]
        note_line = ["   "]

        for start, placements, width, label in block:
            event_width = max(width + 1, 6)
            spacer = "-" * event_width
            time_line.append(f"{start:>{event_width}.1f}")
            label = label if len(label) <= event_width else label[: event_width - 1] + "."
            note_line.append(f"{label:>{event_width}}")
            for index in lines:
                if index in placements:
                    lines[index].append(placements[index].rjust(event_width - 1, "-") + "-")
                else:
                    lines[index].append(spacer)

        rendered = []
        rendered.append("time " + "".join(time_line))
        rendered.append("note " + "".join(note_line))
        for index in range(len(GUITAR_TUNING)):
            rendered.append("".join(lines[index]))
        blocks.append("\n".join(rendered))

    return "\n\n".join(blocks) + "\n"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("input_csv", type=Path)
    parser.add_argument("output_tab", type=Path)
    parser.add_argument("--max-fret", type=int, default=15)
    parser.add_argument("--quantize", type=float, default=0.125)
    parser.add_argument("--min-velocity", type=int, default=0)
    parser.add_argument("--columns-per-line", type=int, default=16)
    args = parser.parse_args()

    notes = read_notes(args.input_csv, args.min_velocity)
    tab = render_tab(notes, args.max_fret, args.quantize, args.columns_per_line)
    args.output_tab.parent.mkdir(parents=True, exist_ok=True)
    args.output_tab.write_text(tab)


if __name__ == "__main__":
    main()
