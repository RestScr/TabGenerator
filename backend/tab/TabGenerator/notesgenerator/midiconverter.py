from basic_pitch.inference import predict_and_save
from basic_pitch import ICASSP_2022_MODEL_PATH
import pretty_midi
from pathlib import Path
from bpm import BPMMap
import config


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
