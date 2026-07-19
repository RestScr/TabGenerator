"""Adapter around guitar transcription and TabGenerator codebases.

This module deliberately contains no HTTP, database, or queue code. A worker
will call ``generate_tab_from_audio`` and persist the returned artifacts.
"""

from __future__ import annotations

import importlib
import logging
import sys
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from app.engines.source_separation import isolate_guitar_track
from app.engines.tab_data import add_timed_events, build_tab_data
from app.engines.guitar_transcription import transcribe_guitar_to_midi
from app.engines.rhythm_alignment import RhythmSettings, apply_rhythm_settings, grid_units_per_measure


logger = logging.getLogger(__name__)
ProgressCallback = Callable[[int, str], None]


BACKEND_DIR = Path(__file__).resolve().parents[2]
TAB_GENERATOR_DIR = BACKEND_DIR / "TabGenerator"


@dataclass(frozen=True)
class TabGenerationOptions:
    instrument_type: str = "lead_guitar"
    voice_mode: str = "guitar"
    capo: int = 0
    tuning: str = "standard_e"
    separate_sources: bool = True
    reuse_existing_midi: bool = False
    tempo_bpm: int | None = None
    downbeat_offset_s: float = 0.0
    beats_per_measure: int = 4
    max_fret: int = 20


@dataclass(frozen=True)
class GeneratedTabResult:
    audio_path: Path
    midi_path: Path
    note_events_path: Path | None
    ascii_tab_path: Path
    ascii_tab: str
    tab_data_path: Path
    tab_data: dict
    tempo_bpm: int


def _prepend_import_path(path: Path) -> None:
    path_value = str(path)
    if path_value not in sys.path:
        sys.path.insert(0, path_value)


def _prepare_engine_imports() -> None:
    if not TAB_GENERATOR_DIR.is_dir():
        raise FileNotFoundError(f"TabGenerator directory was not found: {TAB_GENERATOR_DIR}")

    _prepend_import_path(TAB_GENERATOR_DIR / "notesgenerator")
    _prepend_import_path(TAB_GENERATOR_DIR)


def _generate_midi(
    audio_path: Path,
    output_dir: Path,
    tuning: str,
    max_fret: int,
) -> tuple[Path, Path | None]:
    return transcribe_guitar_to_midi(audio_path, output_dir, tuning=tuning, max_fret=max_fret)


def _render_ascii_tab(
    audio_path: Path,
    midi_path: Path,
    instrument_type: str,
    tuning: str = "standard_e",
    rhythm: RhythmSettings = RhythmSettings(),
    max_fret: int = 20,
    voice_mode: str = "guitar",
    capo: int = 0,
) -> tuple[str, int, dict]:
    config = importlib.import_module("config")
    bpm_module = importlib.import_module("bpm")
    midi_module = importlib.import_module("midi")
    notes_module = importlib.import_module("notesgenerator")
    tab_drawer_module = importlib.import_module("tabdrawer")

    if instrument_type not in config.AVAILABLE_INSTRUMENTS_FOR_TABS.get_available_instruments_for_tabs_fields():
        raise ValueError(f"Unsupported instrument type: {instrument_type}")

    started_at = time.monotonic()
    logger.info("TabGenerator: rendering ASCII tab (instrument=%s, tuning=%s)", instrument_type, tuning)
    bpm_map = apply_rhythm_settings(bpm_module, audio_path, rhythm)
    midi_file = midi_module.MidiFile(instrument_type, midi_path, tuning=tuning, max_fret=max_fret, voice_mode=voice_mode, capo=capo)
    notes = notes_module.NotesGenerator.create_notes(midi_file, bpm_map)
    ascii_tab = tab_drawer_module.TabDrawer.create_tab(
        instrument_type,
        notes,
        tuning=tuning,
        grid_units_per_measure=grid_units_per_measure(bpm_map, rhythm.beats_per_measure),
        downbeat_offset_s=rhythm.downbeat_offset_s,
    )

    if not ascii_tab:
        raise RuntimeError("TabGenerator returned an empty tablature")

    tempo_bpm = int(bpm_map.bpm_map[0].tempo) if bpm_map.bpm_map else 120
    tab_data = build_tab_data(ascii_tab, tempo_bpm, tuning)
    tab_data["time_signature"] = [rhythm.beats_per_measure, 4]
    tab_data["downbeat_offset_s"] = rhythm.downbeat_offset_s
    tab_data["max_fret"] = max_fret
    tab_data["voice_mode"] = voice_mode
    tab_data["capo"] = capo
    add_timed_events(
        tab_data,
        getattr(notes, "note_events", []),
        tempo_bpm,
        rhythm.beats_per_measure,
        rhythm.downbeat_offset_s,
    )
    logger.info(
        "TabGenerator: rendered tab in %.1fs (tempo=%s BPM, characters=%s)",
        time.monotonic() - started_at,
        tempo_bpm,
        len(ascii_tab),
    )
    return ascii_tab, tempo_bpm, tab_data


def generate_tab_from_audio(
    audio_path: Path,
    output_dir: Path,
    options: TabGenerationOptions | None = None,
    progress_callback: ProgressCallback | None = None,
) -> GeneratedTabResult:
    """Run the audio-to-tab pipeline and return generated artifacts.

    The caller owns job status, database transactions, and file lifecycle.
    """

    started_at = time.monotonic()
    _prepare_engine_imports()
    options = options or TabGenerationOptions()
    audio_path = audio_path.resolve()
    output_dir = output_dir.resolve()

    if not audio_path.is_file():
        raise FileNotFoundError(f"Audio file was not found: {audio_path}")

    logger.info(
        "Audio-to-tab: starting %s (separate_sources=%s, tuning=%s)",
        audio_path.name,
        options.separate_sources,
        options.tuning,
    )
    if options.separate_sources:
        _report_progress(progress_callback, 20, "Separating guitar from the mix")
        processing_audio_path = isolate_guitar_track(audio_path, output_dir)
        _report_progress(progress_callback, 55, "Guitar track isolated")
    else:
        processing_audio_path = audio_path
        _report_progress(progress_callback, 55, "Source separation skipped")

    midi_path = output_dir / f"{processing_audio_path.stem}_gaps.mid"
    note_events_path: Path | None = None
    if options.reuse_existing_midi and midi_path.is_file():
        note_events_path = None
        _report_progress(progress_callback, 80, "Reusing existing MIDI")
    else:
        _report_progress(progress_callback, 60, "Transcribing notes with the guitar model")
        midi_path, note_events_path = _generate_midi(
            processing_audio_path,
            output_dir,
            options.tuning,
            options.max_fret,
        )
        _report_progress(progress_callback, 80, "Guitar MIDI transcription completed")

    _report_progress(progress_callback, 85, "Building guitar tablature")
    ascii_tab, tempo_bpm, tab_data = _render_ascii_tab(
        audio_path,
        midi_path,
        options.instrument_type,
        options.tuning,
        RhythmSettings(options.tempo_bpm, options.downbeat_offset_s, options.beats_per_measure),
        options.max_fret,
        options.voice_mode,
        options.capo,
    )
    ascii_tab_path = output_dir / f"{audio_path.stem}_tabgenerator_tab.txt"
    ascii_tab_path.write_text(ascii_tab, encoding="utf-8")
    tab_data_path = output_dir / f"{audio_path.stem}_tab.json"
    import json
    tab_data_path.write_text(json.dumps(tab_data, ensure_ascii=False, indent=2), encoding="utf-8")
    _report_progress(progress_callback, 95, "Tablature artifact saved")
    logger.info(
        "Audio-to-tab: completed in %.1fs (tab=%s)",
        time.monotonic() - started_at,
        ascii_tab_path,
    )

    return GeneratedTabResult(
        audio_path=audio_path,
        midi_path=midi_path,
        note_events_path=note_events_path,
        ascii_tab_path=ascii_tab_path,
        ascii_tab=ascii_tab,
        tab_data_path=tab_data_path,
        tab_data=tab_data,
        tempo_bpm=tempo_bpm,
    )


def generate_tab_from_midi(
    audio_path: Path,
    midi_path: Path,
    output_dir: Path,
    options: TabGenerationOptions | None = None,
    progress_callback: ProgressCallback | None = None,
) -> GeneratedTabResult:
    """Render a tab from an already generated GAPS MIDI file.

    This is the second stage of the file-backed preparation pipeline: GAPS
    owns pitch detection, while the existing TabGenerator owns cleanup,
    string/fret assignment, rhythm layout, and tab rendering.
    """

    started_at = time.monotonic()
    _prepare_engine_imports()
    options = options or TabGenerationOptions()
    audio_path = audio_path.resolve()
    midi_path = midi_path.resolve()
    output_dir = output_dir.resolve()

    if not audio_path.is_file():
        raise FileNotFoundError(f"Audio file was not found: {audio_path}")
    if not midi_path.is_file():
        raise FileNotFoundError(f"GAPS MIDI file was not found: {midi_path}")

    _report_progress(progress_callback, 85, "Building guitar tablature from GAPS MIDI")
    ascii_tab, tempo_bpm, tab_data = _render_ascii_tab(
        audio_path,
        midi_path,
        options.instrument_type,
        options.tuning,
        RhythmSettings(options.tempo_bpm, options.downbeat_offset_s, options.beats_per_measure),
        options.max_fret,
        options.voice_mode,
        options.capo,
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    ascii_tab_path = output_dir / "gaps_tabgenerator_tab.txt"
    ascii_tab_path.write_text(ascii_tab, encoding="utf-8")
    tab_data_path = output_dir / "gaps_tab.json"
    import json

    tab_data_path.write_text(json.dumps(tab_data, ensure_ascii=False, indent=2), encoding="utf-8")
    _report_progress(progress_callback, 100, "GAPS tablature is ready")
    logger.info(
        "GAPS-to-tab: completed in %.1fs (midi=%s, tab=%s)",
        time.monotonic() - started_at,
        midi_path,
        ascii_tab_path,
    )

    return GeneratedTabResult(
        audio_path=audio_path,
        midi_path=midi_path,
        note_events_path=None,
        ascii_tab_path=ascii_tab_path,
        ascii_tab=ascii_tab,
        tab_data_path=tab_data_path,
        tab_data=tab_data,
        tempo_bpm=tempo_bpm,
    )


def _report_progress(
    progress_callback: ProgressCallback | None,
    progress: int,
    stage: str,
) -> None:
    logger.info("Audio-to-tab: %s%% - %s", progress, stage)
    if progress_callback is not None:
        progress_callback(progress, stage)
