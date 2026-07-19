from midi import MidiFile
from bpm import BPMMap, BeatMap
import config
from pathlib import Path
import pretty_midi
from note import GuitarNote


class NotesGenerator:
    """
    Синглтон-фабрика генерации нот для табулатур.
    """
    _instance = None
    # Bottom-to-top visual tuning. The lowest line is labelled C# to match
    # the target tab format used by the consumer of this module.
    GUITAR_STRINGS_PITCH = [45, 45, 50, 55, 59, 64]
    MAX_FRET_DISTANCE = 4 # Максимальная дистанция, от которой может
                          # задаваться следующая позиция на грифе
    MIN_VELOCITY = 60 # Минимальная громкость, ниже которой
                      # ноты пропускаются
    REPEATED_NOTE_EPS = 0.22
    SUSTAIN_GAP_EPS = 0.08
    REATTACK_VELOCITY_MARGIN = 3

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
            return cls.__create_guitar_notes(midi_file.midi_filename, bpm_map)
        elif midi_file.instrument_type == config.AVAILABLE_INSTRUMENTS_FOR_TABS.lead_guitar:
            return cls.__create_guitar_notes(midi_file.midi_filename, bpm_map)
        else:
            return None

    @classmethod
    def __create_guitar_notes(cls, midi_filename : Path, bpm_map : BPMMap) -> BeatMap:
        """
        Фабричный метод для генерации гитарных нот для отображения на табулатуре
        :param midi_filename: Путь к MIDI-файлу
        :param bpm_map: Карта BPM аудиофайла.
        :return: Упорядоченный список нот.
        """
        midi = pretty_midi.PrettyMIDI(str(midi_filename))

        notes = []

        for instrument in midi.instruments:
            # Отсеиваем глухие ноты
            instrument.notes = [
                note
                for note in instrument.notes
                if note.velocity >= cls.MIN_VELOCITY
            ]
            for note in instrument.notes:
                pitch = note.pitch # тональность ноты

                possible_positions = [] # Массив возможных позиций на грифе
                for i, open_note in enumerate(cls.GUITAR_STRINGS_PITCH):
                    # i - номер струны
                    # fret - лад
                    # open_note - тональность открытой струны
                    fret = pitch - open_note
                    if 0 <= fret <= 20:
                        # Добавляем кортеж в массив с номером лада и струны
                        possible_positions.append((fret, i))

                # ВРЕМЕННО
                # Если нет позиций, то переходим к следующей ноте
                if len(possible_positions) == 0:
                    continue

                def position_score(position):
                    fret, string = position
                    low_string_bonus = -8 if string == 0 and pitch == cls.GUITAR_STRINGS_PITCH[0] else 0
                    previous_fret_distance = abs(notes[-1].fret - fret) if len(notes) > 0 else abs(fret)
                    duplicate_low_string_penalty = 4 if string == 0 and pitch > cls.GUITAR_STRINGS_PITCH[0] else 0
                    return previous_fret_distance + duplicate_low_string_penalty + low_string_bonus, fret, -string

                best_position = min(possible_positions, key=position_score)

                best_fret = best_position[0]
                best_string = best_position[1]

                if best_string is not None:
                    # Складываем в массив нот полученную ноту
                    notes.append(GuitarNote(note.start, best_string, best_fret, note.end, note.velocity))

        notes.sort(key=lambda x: x.start)
        notes = NotesGenerator.__merge_sustain_fragments(notes)
        notes = NotesGenerator.__remove_repeated_sustain_notes(notes)

        return NotesGenerator.__split_notes(notes, bpm_map)

    @staticmethod
    def __remove_repeated_sustain_notes(notes : list) -> list:
        """
        Basic Pitch often splits one sustained guitar note into several MIDI
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
        Basic Pitch often cuts a sustained note into adjacent MIDI notes with
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
