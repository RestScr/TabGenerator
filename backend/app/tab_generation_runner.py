"""CLI bridge for rendering a tab from a prepared GAPS MIDI file."""

from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path

from app.engines.tab_generation import TabGenerationOptions, generate_tab_from_midi


def main() -> None:
    parser = argparse.ArgumentParser(description="Render guitar tablature from a GAPS MIDI file")
    parser.add_argument("--audio", type=Path, required=True)
    parser.add_argument("--midi", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--artifact-root", type=Path, required=True)
    parser.add_argument("--instrument", default="lead_guitar")
    parser.add_argument("--voice-mode", default="guitar")
    parser.add_argument("--tuning", default="standard_e")
    parser.add_argument("--capo", type=int, default=0)
    parser.add_argument("--tempo", type=int, default=None)
    parser.add_argument("--downbeat-offset", type=float, default=0.0)
    parser.add_argument("--beats-per-measure", type=int, default=4)
    parser.add_argument("--max-fret", type=int, default=20)
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    result = generate_tab_from_midi(
        args.audio,
        args.midi,
        args.output,
        TabGenerationOptions(
            instrument_type=args.instrument,
            voice_mode=args.voice_mode,
            capo=args.capo,
            tuning=args.tuning,
            separate_sources=False,
            tempo_bpm=args.tempo,
            downbeat_offset_s=args.downbeat_offset,
            beats_per_measure=args.beats_per_measure,
            max_fret=args.max_fret,
        ),
    )
    note_events_path = args.output / "gaps_note_events.json"
    note_events_path.write_text(
        json.dumps(result.tab_data.get("note_events", []), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    result_path = args.output / "result.json"
    result_path.write_text(
        json.dumps(
            {
                "ascii_tab_storage_path": str(result.ascii_tab_path),
                "tab_data_storage_path": str(result.tab_data_path),
                "note_events_storage_path": str(note_events_path),
                "midi_path": str(result.midi_path),
                "tempo_bpm": result.tempo_bpm,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
