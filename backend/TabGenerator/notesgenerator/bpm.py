import librosa
import math
from pathlib import Path
from constants import Beats
from asserters import assert_filename


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
    def __init__(self, beatmap : list[Beat], note_events : list[dict] | None = None):
        self.beatmap = beatmap
        # Keep the mapped events beside the beat buckets.  The ASCII renderer
        # is a presentation format and must not be the source of truth for
        # timing or duration.
        self.note_events = note_events or []

    def __iter__(self):
        return iter([beat.to_dict() for beat in self.beatmap])


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
        self.rate(filename)

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
        duration = len(y) / sample_rate
        for start in range(0, int(duration), window_size):
            end = min(start + window_size, duration)
            y_segment = y[start*sample_rate:(start + window_size)*sample_rate]

            tempo, _ = librosa.beat.beat_track(y=y_segment, sr=sample_rate)
            if type(tempo) != float:
                tempo = tempo[0]
            tempo = math.ceil(tempo)
            if tempo > 0:
                bpm_map.append(BPMPart(start, end, tempo))

        last_end = bpm_map[-1].end if bpm_map else 0
        if last_end < duration:
            start, end = last_end, duration
            y_segment = y[int(start * sample_rate):int(end * sample_rate)]
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
