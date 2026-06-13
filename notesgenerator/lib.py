import config
import pretty_midi
from pathlib import Path


class MidiFile:
    """
    Структура для хранения информации о сгенерированном MIDI-файле
    """
    def __init__(self, instrument_type : str, midi_filename : Path):
        self.instrument_type = instrument_type
        self.midi_filename = midi_filename


class NotesGenerator:
    """
    Синглтон-фабрика табулатур.
    """
    _instance = None
    GUITAR_STRINGS = [40, 45, 50, 55, 59, 64]
    STRING_NAMES = ["e", "B", "G", "D", "A", "E"]


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
    def create_notes(cls, midi_file : MidiFile):
        if midi_file.instrument_type == config.AVAILABLE_INSTRUMENTS_FOR_TABS.lead_guitar:
            return cls.create_guitar_notes(midi_file.midi_filename)
        elif midi_file.instrument_type == config.AVAILABLE_INSTRUMENTS_FOR_TABS.lead_guitar:
            return cls.create_guitar_notes(midi_file.midi_filename)
        else:
            return None


    @classmethod
    def create_guitar_notes(cls, midi_filename : Path):
        """
        Фабричный метод для генерации гитарных нот для отображения на табулатуре
        :param midi_filename: Путь к MIDI-файлу
        :return: Упорядоченный список нот.
        """
        midi = pretty_midi.PrettyMIDI(str(midi_filename))

        notes = []

        for instrument in midi.instruments:
            for note in instrument.notes:
                pitch = note.pitch

                best_string = None
                best_fret = None

                for i, open_note in enumerate(cls.GUITAR_STRINGS):
                    fret = pitch - open_note
                    if 0 <= fret <= 20:
                        best_fret = fret
                        best_string = i
                        break

                if best_string is not None:
                    notes.append((note.start, best_string, best_fret))

        notes.sort(key=lambda x: x[0])

        return notes
