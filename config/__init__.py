from pathlib import Path

DEBUG = True

class EXTENSIONS:
    """
    Статический класс с расширениями файлов
    """
    mid = ".mid"
    wav = ".wav"
    txt = ".txt"
    json = ".json"

    @staticmethod
    def get_extensions_fields():
        return [
            name for name, value in EXTENSIONS.__dict__.items()
            if not name.startswith("__") and not callable(value)
        ]


class AVAILABLE_INSTRUMENTS_FOR_TABS:
    """
    Статический конфиг-класс
    """
    lead_guitar = "lead_guitar"
    rhythm_guitar = "rhythm_guitar"

    @staticmethod
    def get_available_instruments_for_tabs_fields():
        return [name for name, value in AVAILABLE_INSTRUMENTS_FOR_TABS.__dict__.items()
                if not callable(value) and not name.startswith("__")]


BASE_DIR = Path(__file__).parent.parent

DEBUG_TABS_SAVE_DIR_PATH = BASE_DIR / "debug_tabs"

DEFAULT_MIDI_DIR = "midi/"

DEMUCS_OUTPUT_DIR = "demucs/"
VENV_PATH = BASE_DIR / ".venv" / "Scripts" / "python.exe"
DEFAULT_NOTES_OUTPUT_DIR_PATH = BASE_DIR / "tabs"
DEFAULT_NOTES_OUTPUT_FILENAME = "{0}_notes.json"

NOTES_POST_URL = None
