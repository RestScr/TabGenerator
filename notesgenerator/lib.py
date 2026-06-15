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
            # Отсеиваем глухие ноты
            instrument.notes = [
                note
                for note in instrument.notes
                if note.velocity >= cls.MIN_VELOCITY
            ]
            for note in instrument.notes:
                pitch = note.pitch # тональность ноты

                best_string = None
                best_fret = None

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
                        key=lambda x: abs(notes[-1][2] - x[0])
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
                    notes.append((note.start, best_string, best_fret))

        notes.sort(key=lambda x: x[0])

        return notes


class TabDrawer:
    """
    Тестовый класс-синглтон для
    генерации текстовых табулатур
    """
    _instance = None
    STRING_NAMES = ["e", "B", "G", "D", "A", "E"]

    def __new__(cls):
        if cls._instance is not None:
            raise RuntimeError("This class is a singleton")
        return super().__new__(cls)

    @classmethod
    def get_instance(cls):
        """
        Получение экземпляра синглтона
        :return: Ссылка на экземпляр.
        """
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls.__init__(cls._instance)
        return cls._instance


    @classmethod
    def create_tab(cls, instrument_type : str, notes : list) -> str:
        """
        Фабричный метод генерации табов по заданному типу инструмента
        :param instrument_type:
        :param notes:
        :return:
        """
        if instrument_type == config.AVAILABLE_INSTRUMENTS_FOR_TABS.lead_guitar:
            return cls.create_guitar_notes(notes)
        if instrument_type == config.AVAILABLE_INSTRUMENTS_FOR_TABS.rhythm_guitar:
            return cls.create_guitar_notes(notes)
        else:
            return ""


    @classmethod
    def create_guitar_notes(cls, notes : list):
        """
        Генерация текстовых табулатур для гитары.
        :param notes: Гитарные ноты
        :return: Текстовые табулатуры.
        """
        if notes is None:
            return ""

        length = min(len(notes), 80)

        tab = [["-" for _ in range(length)] for _ in range(6)]

        for i, (_, string, fret) in enumerate(notes[:length]):
            tab[5 - string][i] = str(fret)

        # render
        out = []
        for i in range(6):
            out.append(cls.STRING_NAMES[i] + "| " + "-".join(tab[i]))

        return "\n".join(out)


class MidiConverter:
    """
    Отдельно вынесенный класс конвертера аудио в MIDI_формат
    """
    _instance = None

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

