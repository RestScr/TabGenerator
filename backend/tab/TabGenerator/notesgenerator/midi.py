from pathlib import Path


class MidiFile:
    """
    Структура для хранения информации о сгенерированном MIDI-файле
    """
    def __init__(self, instrument_type : str, midi_filename : Path):
        self.instrument_type = instrument_type
        self.midi_filename = midi_filename
