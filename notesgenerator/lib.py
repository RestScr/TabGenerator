import config
import pretty_midi
from pathlib import Path
import os
import librosa
import math
from basic_pitch.inference import predict_and_save
from basic_pitch import ICASSP_2022_MODEL_PATH


class Beats:
    """
    Статическая структура, хранящая константы тактов
    """
    ONE_SECOND = 1 # Одна вторая доля
    ONE_FOURTH = 1/2 # четвертная доля
    ONE_EIGHTH = 1/4 # Восьмая доля
    ONE_SIXTEENTH = 1/8 # Шестнадцатая доля
    ONE_THIRTY_SECOND = 1/16 # тридцать вторая доля


class Note:
    """
    Базовый класс всех нот музыкальных
    инструментов.
    """
    def __init__(self, start):
        self.start = start


class GuitarNote(Note):
    """
    Класс гитарной ноты, хранящий
    информацию о проигрываемой струне и ладе.
    """
    def __init__(self, start, string, fret):
        super().__init__(start)
        self.string = string
        self.fret = fret

    def __iter__(self):
        return iter([self.start, self.string, self.fret])

    def to_dict(self):
        return {"start" : self.start, "string" : self.string, "fret" : self.fret}


class BPMPart:
    """
    Структура, хранящая информацию об участке песни:
    начало участка (сек), конец участка (сек), темп.
    """
    def __init__(self, start : float, end : float, tempo : int):
        assert tempo > 0
        self.start = start
        self.end = end
        self.tempo = tempo

    def __iter__(self):
        return iter([self.start, self.end, self.tempo])

    def to_dict(self):
        return {
            "start" : self.start,
            "end" : self.end,
            "tempo" : self.tempo}

    def get_beats(self, beat_size : float) -> list:
        """
        Функция разделения участка песни
        на фрагменты по заданному темпу.
        :param beat_size: Доля такта.
        :return:
        """
        output = []
        step = 60 / self.tempo * beat_size
        for i in range(math.ceil((self.end - self.start) / step)):
            new_beat = Beat(self.start + i * step, self.start + (i + 1) * step)
            output.append(new_beat)

        return output


class Beat:
    """
    Класс удара в такте.
    """
    def __init__(self, start : float, end : float, notes : list=None):
        if notes is None:
            notes = list()

        self.start = start
        self.end = end
        self.notes = notes

    def __iter__(self):
        return iter([self.start, self.end, self.notes])

    def to_dict(self):
        return {
            "start" : self.start,
            "end" : self.end,
            "notes" : [note.to_dict() for note in self.notes]}


class BeatMap:
    """
    Класс, хранящий разделение песни по тактам.
    """
    def __init__(self, beatmap : list[Beat]):
        self.beatmap = beatmap

    def __iter__(self):
        return iter([beat.to_dict() for beat in self.beatmap])


class BPMMap:
    """
    Класс, хранящий информацию
    об участках песни с различным темпом.
    """
    WINDOW_SIZE = 5 # Размер тактового окна при получении карты
                     # темпов в секундах
    def __init__(self, filename : Path, beat_size=None):
        if beat_size is None:
            beat_size = Beats.ONE_FOURTH
        self.beat_size = beat_size
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

    def get_beats(self) -> BeatMap:
        """
        Функция разделения всей карты BPM
        на такты.
        :return: Массив тактов.
        """
        output = BeatMap([])
        for part in self.bpm_map:
            output.beatmap.extend(part.get_beats(self.beat_size))

        return output

    def __iter__(self):
        return iter([part.to_dict() for part in self.bpm_map])


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
    def create_tab(cls, instrument_type : str, notes : BeatMap) -> str:
        """
        Фабричный метод генерации табов по заданному типу инструмента
        :param instrument_type:
        :param notes:
        :return:
        """
        if instrument_type == config.AVAILABLE_INSTRUMENTS_FOR_TABS.lead_guitar:
            return cls.__create_guitar_notes(notes)
        if instrument_type == config.AVAILABLE_INSTRUMENTS_FOR_TABS.rhythm_guitar:
            return cls.__create_guitar_notes(notes)
        else:
            return ""

    @classmethod
    def __create_guitar_notes(cls, beatmap : BeatMap) -> str:
        """
        Генерация текстовых табулатур для гитары.
        :param beatmap: Гитарные ноты
        :return: Текстовые табулатуры.
        """
        if beatmap is None:
            return ""

        length = len(beatmap.beatmap)

        tab = [["-" for _ in range(length)] for _ in range(6)]

        for i, beat in enumerate(beatmap.beatmap):
            for note in beat.notes:
                tab[5 - note.string][i] = str(note.fret)

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

    NOTE_DURATION_EPS = 0.05 # Минимальная допустимая длительность нот
    DISTANCE_EPS = 0.1 # Погрешность расстояния между нотами при очистке MIDI-файлов
    PITCH_EPS = 0 # Погрешность разности MIDI-нот
    MINIMAL_VELOCITY = 5 # Минимальная допустимая громкость нот

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
        midi.write(path_to_midi)

        # Разделение MIDI на партии
        cls.__split_midi(midi, path_to_midi.parent, path_to_midi.stem)

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

                current_note_duration = abs(current_note.end - current_note.start)
                notes_distance = abs(previous_note.end - current_note.start)
                pitch_delta = abs(previous_note.pitch - current_note.pitch)

                if notes_distance <= cls.DISTANCE_EPS and pitch_delta <= cls.PITCH_EPS:
                    if prettified_notes[j - 1] is not None:
                        prettified_notes[j - 1].end = current_note.end
                        prettified_notes[j] = None

                if current_note_duration <= cls.NOTE_DURATION_EPS:
                    prettified_notes[j] = None
                if current_note.velocity < cls.MINIMAL_VELOCITY:
                    prettified_notes[j] = None


            prettified_notes = [note for note in prettified_notes if note is not None]
            midi.instruments[i].notes = prettified_notes

        return midi

    @classmethod
    def __split_midi(cls, midi : pretty_midi.PrettyMIDI, save_dir : Path, midi_name : str) -> None:
        """
        Разделить MIDI-файл на несколько партий
        :param midi: Объект открытого MIDI-файла.
        :param save_dir: Папка для сохранения файлов.
        :param midi_name: Наименование разделяемого MIDI-файла.
        :return: None.
        """
        # Считываем ноты
        notes = []

        for instruments in midi.instruments:
            for note in instruments.notes:
                notes.append(note)

        # Выбор центральной опорной ноты для разделения трека на две партии
        max_pitch_note = max(notes, key=lambda note: note.pitch)
        min_pitch_note = min(notes, key=lambda note: note.pitch)
        pivot_note_pitch = (max_pitch_note.pitch + min_pitch_note.pitch) / 2

        low_octave_notes = []
        high_octave_notes = []

        for note in notes:
            if note.pitch >= pivot_note_pitch:
                high_octave_notes.append(note)
            else:
                low_octave_notes.append(note)

        # Сохранение первой партии
        file1 = pretty_midi.PrettyMIDI()
        instrument = pretty_midi.Instrument(
            program=0,
            name="Low_octave_part",
        )
        instrument.notes.extend(low_octave_notes)
        file1.instruments.append(instrument)
        file1.write(save_dir / (f"{midi_name}_1" + config.EXTENSIONS.mid))

        # Сохранение второй партии
        file2 = pretty_midi.PrettyMIDI()
        instrument = pretty_midi.Instrument(
            program=0,
            name="High_octave_part",
        )
        instrument.notes.extend(high_octave_notes)
        file2.instruments.append(instrument)
        file2.write(save_dir / (f"{midi_name}_2" + config.EXTENSIONS.mid))


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

