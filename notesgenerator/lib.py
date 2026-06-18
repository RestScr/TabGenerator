from torchgen.api.cpp import return_names

import config
import pretty_midi
from pathlib import Path
import os
import librosa
import math
from basic_pitch.inference import predict_and_save
from basic_pitch import ICASSP_2022_MODEL_PATH


class MidiFile:
    """
    Структура для хранения информации о сгенерированном MIDI-файле
    """
    def __init__(self, instrument_type : str, midi_filename : Path):
        self.instrument_type = instrument_type
        self.midi_filename = midi_filename


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


class BPMPart:
    """
    Структура, хранящая информацию об участке песни:
    начало участка (сек), конец участка (сек), темп.
    """
    def __init__(self, start : float, end : float, tempo : int):
        self.start = start
        self.end = end
        self.tempo = tempo

    def __iter__(self):
        return iter([self.start, self.end, self.tempo])


class BPMMap:
    """
    Класс, хранящий информацию
    об участках песни с различным темпом.
    """
    WINDOW_SIZE = 5 # Размер тактового окна при получении карты
                     # темпов в секундах
    def __init__(self, filename : Path):
        self.bpm_map = None
        self.rate_local(filename)

    def rate_local(self, filename : Path) -> None:
        """
        Функция получения темпа на каждом временном кадре песни в аудиофайле.
        :param filename: Путь к файлу.
        :return: None.
        """
        filename = assert_filename(filename)
        y, sample_rate = librosa.load(filename)

        window_size = BPMMap.WINDOW_SIZE

        bpm_map = []
        for start in range(0, int(len(y) / sample_rate), window_size):
            end = start + window_size
            y_segment = y[start*sample_rate:(start + window_size)*sample_rate]

            tempo, _ = librosa.beat.beat_track(y=y_segment, sr=sample_rate)
            if type(tempo) != float:
                tempo = tempo[0]
            tempo = math.ceil(tempo)
            if tempo > 0:
                bpm_map.append(BPMPart(start, end, tempo))

        # Досчитываем последний кусок песни
        # (он мог не попасть в окно)
        start, end = int(len(y) / sample_rate) // window_size * window_size, len(y) / sample_rate
        y_segment = y[start * sample_rate:(start + window_size) * sample_rate]
        tempo = math.ceil(librosa.beat.beat_track(y=y_segment, sr=sample_rate)[0])
        if tempo == 0:
            tempo = 1
        bpm_map.append(BPMPart(start, end, tempo))

        self.bpm_map = bpm_map


    def rate(self, filename : Path):
        """
        Функция получения общего темпа песни.
        :param filename: Путь к песне.
        :return: None
        """
        filename = assert_filename(filename)
        y, sample_rate = librosa.load(filename)

        onset_environment = librosa.onset.onset_strength(y=y, sr=sample_rate)

        global_tempo = librosa.feature.tempo(
            onset_envelope=onset_environment,
            sr=sample_rate
        )

        self.bpm_map = [BPMPart(0, len(y) / sample_rate, math.ceil(global_tempo[0]))]

    def __iter__(self):
        return iter([tuple(part) for part in self.bpm_map])


class MidiConverter:
    """
    Отдельно вынесенный класс конвертера аудио в MIDI_формат
    """
    _instance = None

    NOTE_DURATION_EPS = 0.2
    EPS = 0.1 # Погрешность для нот при очистке MIDI-файлов
    PITCH_EPS = 1 # Погрешность разности MIDI-нот

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

    @classmethod
    def __quantize(cls, path_to_midi : Path, bpm_map : BPMMap) -> None:
        """
        Функция, осуществляющая квантизацию MIDI-файла.
        :param path_to_midi: Путь к MIDI-файлу
        :return: None
        """
        midi = pretty_midi.PrettyMIDI(path_to_midi)

        bpm_map_iterator = iter(bpm_map.bpm_map)
        current_window = next(bpm_map_iterator)

        for instrument in midi.instruments:
            for note in instrument.notes:
                if note.start >= current_window.end:
                    # Если нота выходит за рамки текущего окна, переходим
                    # к следующему окну
                    current_window = next(bpm_map_iterator)

                step = 60 / current_window.tempo / 4
                note.start = round(note.start / step) * step
                note.end = round(note.end / step) * step

        # Очистка MIDI от артефактов
        midi = cls.__clean_midi(midi)

        # Сохранение нового MIDI
        midi.write(path_to_midi)

    @classmethod
    def __clean_midi(cls, midi : pretty_midi.PrettyMIDI) -> pretty_midi.PrettyMIDI:
        """
        Функция, которая занимается очисткой
        сгенерированных MIDI-файлов.
        :param midi: Объект открытого MIDI-файла.
        :return: Ссылка на очищенный MIDI-объект
        """
        for i in range(len(midi.instruments)):
            prettified_notes = midi.instruments[i].notes.copy()
            for j in range(1, len(midi.instruments[i].notes)):
                previous_note = midi.instruments[i].notes[j - 1]
                current_note = midi.instruments[i].notes[j]
                if abs(previous_note.end - current_note.start) <= cls.EPS\
                        and abs(previous_note.pitch - current_note.pitch) <= cls.PITCH_EPS:
                    if prettified_notes[j - 1] is not None:
                        prettified_notes[j - 1].end = current_note.end
                    prettified_notes[j] = None
                if abs(current_note.start - current_note.end) <= cls.NOTE_DURATION_EPS:
                    prettified_notes[j] = None

            prettified_notes = [note for note in prettified_notes if note is not None]
            midi.instruments[i].notes = prettified_notes

        return midi


    @classmethod
    def convert_audio_to_midi(cls, filename_path : Path, bpm_map : BPMMap) -> Path:
        """
        Функция конвертации аудио файла в MIDI-файл.
        :param filename_path: Путь к файлу.
        :param bpm_map: Карта темпов песни.
        :return: Результирующий путь к MIDI-файлу.
        """
        path_to_midi = Path(filename_path).parent / config.DEFAULT_MIDI_DIR
        path_to_midi.mkdir(exist_ok=True)

        predict_and_save(
            audio_path_list=[str(filename_path)],
            output_directory=path_to_midi,
            save_midi=True,
            sonify_midi=True,

            save_model_outputs=False,
            save_notes=False,
            model_or_model_path=ICASSP_2022_MODEL_PATH
        )

        midi_filename = Path(filename_path).stem + "_basic_pitch" + config.EXTENSIONS.mid
        result_path = path_to_midi / midi_filename

        # Квантизация (распределение равномерного темпа по всей песне)
        cls.__quantize(result_path, bpm_map)

        return result_path


def assert_filename(filename : Path) -> Path:
    """
    Функция проверки пути к файлу на:
    1. Путь ведет точно к файлу.
    2. Файл существует.
    :return: Возвращает полный путь к файлу
    """
    if not filename.is_absolute():
        filename = config.BASE_DIR / filename

    assert filename.is_file()
    assert os.path.exists(filename)

    return filename

