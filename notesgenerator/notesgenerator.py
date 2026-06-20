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
    GUITAR_STRINGS_PITCH = [40, 45, 50, 55, 59, 64]
    MAX_FRET_DISTANCE = 4 # Максимальная дистанция, от которой может
                          # задаваться следующая позиция на грифе
    MIN_VELOCITY = 50 # Минимальная громкость, ниже которой
                      # ноты пропускаются

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

                # Выбор наилучшей позиции ноты (чем ближе
                # к предыдущей позиции по ладу, тем лучше)
                if len(notes) > 0:
                    best_position = min(
                        possible_positions,
                        key=lambda x: abs(notes[-1].fret - x[0])
                    )
                else:
                    best_position = min(
                        possible_positions,
                        key=lambda x: abs(x[0])
                    )

                best_fret = best_position[0]
                best_string = best_position[1]

                if best_string is not None:
                    # Складываем в массив нот полученную ноту
                    notes.append(GuitarNote(note.start, best_string, best_fret))

        notes.sort(key=lambda x: x.start)

        return NotesGenerator.__split_notes(notes, bpm_map)

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
            if note.start > beat.end:
                result.beatmap.append(beat)
                beat = next(total_map)
            beat.notes.append(note)

        result.beatmap.append(beat)

        return result
