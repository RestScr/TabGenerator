from pathlib import Path


class MidiFile:
    """
    Структура для хранения информации о сгенерированном MIDI-файле
    """
    def __init__(self, instrument_type: str, midi_filename: Path, tuning: str = "standard_e", max_fret: int = 20, voice_mode: str = "all", capo: int = 0):
        self.instrument_type = instrument_type
        self.midi_filename = midi_filename
        self.tuning = tuning
        self.max_fret = max_fret
        self.voice_mode = voice_mode
        self.capo = capo
