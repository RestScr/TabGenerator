from midi import MidiFile
from bpm import BPMMap, BeatMap
import config
from pathlib import Path
import pretty_midi
from note import GuitarNote
from app.engines.fretboard_mapper import TranscriptionNote
from app.engines.string_fret_assignment import ProbabilisticStringFretMapper
from app.engines.tuning import get_tuning


class NotesGenerator:
    """
    Синглтон-фабрика генерации нот для табулатур.
    """
    _instance = None
    MAX_FRET_DISTANCE = 4 # Максимальная дистанция, от которой может
                          # задаваться следующая позиция на грифе
    MIN_VELOCITY = 60 # Отсекаем слабые артефакты транскриптора из полного микса.
    REPEATED_NOTE_EPS = 0.12
    SUSTAIN_GAP_EPS = 0.08
    REATTACK_VELOCITY_MARGIN = 3
    MIN_NOTE_DURATION = 0.06
    DUPLICATE_ONSET_EPS = 0.08

    def __new__(cls):
        if cls._instance is not None:
            raise RuntimeError("This class is a singleton")
        return super().__new__(cls)

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls.__init__(cls._instance)
        return cls._instance

    # Фабричный метод
    @classmethod
    def create_notes(cls, midi_file : MidiFile, bpm_map : BPMMap) -> BeatMap | None:
        if midi_file.instrument_type == config.AVAILABLE_INSTRUMENTS_FOR_TABS.lead_guitar:
            return cls.__create_guitar_notes(midi_file.midi_filename, bpm_map, midi_file.tuning, midi_file.max_fret, midi_file.voice_mode, midi_file.capo)
        elif midi_file.instrument_type == config.AVAILABLE_INSTRUMENTS_FOR_TABS.rhythm_guitar:
            return cls.__create_guitar_notes(midi_file.midi_filename, bpm_map, midi_file.tuning, midi_file.max_fret, midi_file.voice_mode, midi_file.capo)
        else:
            return None

    @classmethod
    def __create_guitar_notes(cls, midi_filename: Path, bpm_map: BPMMap, tuning: str = "standard_e", max_fret: int = 20, voice_mode: str = "all", capo: int = 0) -> BeatMap:
        """
        Фабричный метод для генерации гитарных нот для отображения на табулатуре
        :param midi_filename: Путь к MIDI-файлу
        :param bpm_map: Карта BPM аудиофайла.
        :return: Упорядоченный список нот.
        """
        midi = pretty_midi.PrettyMIDI(str(midi_filename))
        string_pitches = list(get_tuning(tuning)["midi"])

        raw_notes = cls.__select_and_clean_midi_notes(midi)
        raw_notes = cls.__select_voice(raw_notes, voice_mode)

        mapped_notes = ProbabilisticStringFretMapper.map_notes(
            [TranscriptionNote(note.start, note.end, note.pitch, note.velocity) for note in raw_notes],
            string_pitches,
            max_fret,
            capo,
        )
        notes = [
            GuitarNote(
                note.start,
                note.string,
                note.fret,
                note.end,
                note.velocity,
                note.assignment_confidence,
            )
            for note in mapped_notes
        ]

        notes.sort(key=lambda x: x.start)
        notes = NotesGenerator.__merge_sustain_fragments(notes)
        notes = NotesGenerator.__remove_repeated_sustain_notes(notes)
        techniques = NotesGenerator.__infer_techniques(notes)

        beat_map = NotesGenerator.__split_notes(notes, bpm_map)
        beat_map.note_events = [
            {
                "pitch": cls.__note_pitch(note, string_pitches),
                "start": float(note.start),
                "end": float(note.end) if note.end is not None else None,
                "duration": max(0.0, float((note.end or note.start) - note.start)),
                "velocity": int(note.velocity or 0),
                "string": int(note.string),
                "fret": int(note.fret),
                "assignment_confidence": round(float(note.assignment_confidence), 4),
                "technique": techniques.get(id(note)),
            }
            for note in notes
        ]
        return beat_map

    @staticmethod
    def __select_voice(notes: list, voice_mode: str) -> list:
        """Select one musically coherent voice from a polyphonic guitar MIDI.

        The selector is deliberately data-driven: it uses detected note onsets
        and pitch, not song-specific fret or timing rules. ``all`` and
        ``guitar`` keep the complete cleaned guitar transcription, while
        lead/rhythm choose the upper/lower voice when several notes start
        together.
        """
        if voice_mode in {"all", "guitar"} or len(notes) < 2:
            return notes
        if voice_mode not in {"lead", "rhythm"}:
            raise ValueError(f"Unsupported voice mode: {voice_mode}")

        onset_window = 0.09
        ordered = sorted(notes, key=lambda note: (note.start, note.pitch, -note.velocity))
        clusters: list[list] = []
        for note in ordered:
            if not clusters or note.start - clusters[-1][0].start > onset_window:
                clusters.append([note])
            else:
                clusters[-1].append(note)

        selected = []
        for cluster in clusters:
            # Keep the strongest note when equal-pitch duplicates survived
            # cleanup; then select the register requested by the user.
            by_pitch = {}
            for note in cluster:
                previous = by_pitch.get(note.pitch)
                if previous is None or note.velocity > previous.velocity:
                    by_pitch[note.pitch] = note
            candidates = list(by_pitch.values())
            if voice_mode == "lead":
                selected.append(min(candidates, key=lambda note: (-note.pitch, -note.velocity)))
            elif voice_mode == "rhythm":
                selected.append(min(candidates, key=lambda note: (note.pitch, -note.velocity)))
        return selected

    @classmethod
    def __select_and_clean_midi_notes(cls, midi: pretty_midi.PrettyMIDI) -> list:
        """Select guitar-like tracks and remove obvious transcription noise.

        GAPS normally writes one instrument, but this keeps a future
        multi-track MIDI from blindly merging every track into one guitar
        part.  It also removes ultra-short duplicate detections before the
        fretboard mapper sees them.
        """
        instruments = [instrument for instrument in midi.instruments if instrument.notes]
        if not instruments:
            return []

        guitar_tracks = [
            instrument for instrument in instruments
            if 24 <= int(instrument.program) <= 31
            or "guitar" in instrument.name.lower()
        ]
        selected = guitar_tracks or (instruments if len(instruments) == 1 else [max(instruments, key=lambda item: len(item.notes))])

        candidates = []
        for instrument in selected:
            candidates.extend(
                note for note in instrument.notes
                if note.velocity >= cls.MIN_VELOCITY
                and note.end > note.start
                and note.end - note.start >= cls.MIN_NOTE_DURATION
            )

        candidates.sort(key=lambda note: (note.start, note.pitch, -note.velocity))
        result = []
        last_by_pitch = {}
        for note in candidates:
            previous = last_by_pitch.get(note.pitch)
            if previous is not None and note.start - previous.start < cls.DUPLICATE_ONSET_EPS:
                previous.end = max(previous.end, note.end)
                previous.velocity = max(previous.velocity, note.velocity)
                continue
            result.append(note)
            last_by_pitch[note.pitch] = note
        return result

    @staticmethod
    def __infer_techniques(notes: list[GuitarNote]) -> dict[int, str]:
        """Infer conservative legato/slide hints from adjacent same-string notes."""

        techniques: dict[int, str] = {}
        by_string: dict[int, list[GuitarNote]] = {}
        for note in notes:
            by_string.setdefault(int(note.string), []).append(note)

        for string_notes in by_string.values():
            ordered = sorted(string_notes, key=lambda item: item.start)
            for previous, current in zip(ordered, ordered[1:]):
                previous_end = previous.end if previous.end is not None else previous.start
                gap = current.start - previous_end
                fret_delta = current.fret - previous.fret
                if gap < -0.01 or gap > 0.08 or fret_delta == 0:
                    continue

                absolute_delta = abs(fret_delta)
                if absolute_delta >= 4:
                    techniques[id(current)] = "slide"
                elif absolute_delta <= 4 and current.velocity <= previous.velocity + 4:
                    techniques[id(current)] = "hammer_on" if fret_delta > 0 else "pull_off"
        return techniques

    @staticmethod
    def __note_pitch(note: GuitarNote, string_pitches: list[int]) -> int:
        return int(string_pitches[note.string] + note.fret)

    @staticmethod
    def __remove_repeated_sustain_notes(notes : list) -> list:
        """
        Guitar transcribers often split one sustained guitar note into several MIDI
        notes. For tablature this creates extra repeated fret numbers. Keep a
        repeat only when there is a clear gap that likely means a new attack.
        """
        result = []
        last_by_position = {}

        for note in notes:
            key = (note.string, note.fret)
            previous = last_by_position.get(key)

            if previous is not None:
                too_fast_repeat = note.start - previous.start < NotesGenerator.REPEATED_NOTE_EPS
                if too_fast_repeat:
                    if previous.end is None or (note.end is not None and note.end > previous.end):
                        previous.end = note.end
                    continue

            result.append(note)
            last_by_position[key] = note

        return result

    @staticmethod
    def __merge_sustain_fragments(notes : list) -> list:
        """
        Guitar transcribers often cut a sustained note into adjacent MIDI notes with
        the same pitch. Treat touching fragments as one tab event.
        """
        result = []
        last_by_position = {}

        for note in notes:
            key = (note.string, note.fret)
            previous = last_by_position.get(key)

            if previous is not None and previous.end is not None:
                gap = note.start - previous.end
                previous_velocity = previous.velocity if previous.velocity is not None else 0
                current_velocity = note.velocity if note.velocity is not None else previous_velocity
                is_reattack = current_velocity > previous_velocity + NotesGenerator.REATTACK_VELOCITY_MARGIN
                if gap <= NotesGenerator.SUSTAIN_GAP_EPS and not is_reattack:
                    if note.end is not None and note.end > previous.end:
                        previous.end = note.end
                    previous.velocity = current_velocity
                    continue

            result.append(note)
            last_by_position[key] = note

        return result

    @staticmethod
    def __split_notes(notes : list, bpm_map : BPMMap) -> BeatMap:
        """
        Функция, которая разделяет полученные ноты на позиции
        ао заданной карте темпов.
        :param notes: Чистые нераспределенные ноты.
        :param bpm_map: BPM карта.
        :return: Список с долями с нотами в каждой доле.
        """
        total_map = iter(bpm_map.get_beats().beatmap)
        beat = next(total_map)
        result = BeatMap([])
        for note in notes:
            while note.start > beat.end:
                result.beatmap.append(beat)
                try:
                    beat = next(total_map)
                except StopIteration:
                    break
            beat.notes.append(note)

        result.beatmap.append(beat)

        return result
