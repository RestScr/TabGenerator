#!/usr/bin/env python3
import argparse
import sys
from pathlib import Path

from basic_pitch import FilenameSuffix, build_icassp_2022_model_path
from basic_pitch.inference import Model, predict_and_save


def add_tabgenerator_to_path(tabgenerator_dir: Path) -> None:
    notesgenerator_dir = tabgenerator_dir / "notesgenerator"
    if not notesgenerator_dir.is_dir():
        raise FileNotFoundError(f"TabGenerator notesgenerator dir not found: {notesgenerator_dir}")

    # TabGenerator currently uses top-level imports such as `from bpm import BPMMap`.
    sys.path.insert(0, str(notesgenerator_dir))
    sys.path.insert(0, str(tabgenerator_dir))


def midi_output_path(audio_path: Path, output_dir: Path) -> Path:
    return output_dir / f"{audio_path.stem}_basic_pitch.mid"


def generate_midi(audio_path: Path, output_dir: Path) -> Path:
    from basic_pitch.inference import verify_input_path, verify_output_dir

    verify_input_path(audio_path)
    output_dir.mkdir(parents=True, exist_ok=True)
    verify_output_dir(output_dir)

    model = Model(build_icassp_2022_model_path(FilenameSuffix.onnx))
    predict_and_save(
        audio_path_list=[audio_path],
        output_directory=output_dir,
        save_midi=True,
        sonify_midi=False,
        save_model_outputs=False,
        save_notes=True,
        model_or_model_path=model,
    )
    path = midi_output_path(audio_path, output_dir)
    if not path.is_file():
        raise FileNotFoundError(f"Expected MIDI output was not created: {path}")
    return path


def generate_tab(audio_path: Path, midi_path: Path, output_tab_path: Path) -> None:
    import config
    from bpm import BPMMap
    from midi import MidiFile
    from notesgenerator import NotesGenerator
    from tabdrawer import TabDrawer

    bpm_map = BPMMap(audio_path)
    notes = NotesGenerator.create_notes(
        MidiFile(config.AVAILABLE_INSTRUMENTS_FOR_TABS.lead_guitar, midi_path),
        bpm_map,
    )
    tab = TabDrawer.create_tab(config.AVAILABLE_INSTRUMENTS_FOR_TABS.lead_guitar, notes)

    output_tab_path.parent.mkdir(parents=True, exist_ok=True)
    output_tab_path.write_text(tab)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run Basic Pitch audio->MIDI, then TabGenerator MIDI->guitar tab."
    )
    parser.add_argument("audio_path", type=Path)
    parser.add_argument("-o", "--output-dir", type=Path, default=Path("output"))
    parser.add_argument(
        "--tabgenerator-dir",
        type=Path,
        default=Path(__file__).resolve().parents[2] / "TabGenerator",
    )
    parser.add_argument("--skip-midi", action="store_true", help="Reuse existing *_basic_pitch.mid")
    args = parser.parse_args()

    audio_path = args.audio_path.resolve()
    output_dir = args.output_dir.resolve()
    tabgenerator_dir = args.tabgenerator_dir.resolve()

    add_tabgenerator_to_path(tabgenerator_dir)

    if args.skip_midi:
        midi_path = midi_output_path(audio_path, output_dir)
        if not midi_path.is_file():
            raise FileNotFoundError(f"Cannot reuse missing MIDI file: {midi_path}")
    else:
        midi_path = generate_midi(audio_path, output_dir)

    output_tab_path = output_dir / f"{audio_path.stem}_tabgenerator_tab.txt"
    generate_tab(audio_path, midi_path, output_tab_path)
    print(f"Saved TabGenerator tab to {output_tab_path}")


if __name__ == "__main__":
    main()
