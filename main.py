import json
import os
import shutil
from pathlib import Path
import argparse
import config
import subprocess
import soundfile
import librosa
from basic_pitch.inference import predict_and_save
from basic_pitch import ICASSP_2022_MODEL_PATH
from notesgenerator import NotesGenerator, MidiFile, TabDrawer
import torch
from notesgenerator.web import post_json, check_url
from http import HTTPStatus


def load_tools():
    """
    Функция, которая инициализирует
    инструменты для работы скрипта.
    :return:
    """
    FFMPEG_PATH = config.BASE_DIR / "tools" / "ffmpeg-8.1.1-full_build-shared" / "bin"
    os.environ["PATH"] += os.pathsep + str(FFMPEG_PATH)


def get_args():
    """
    Получить аргументы для запуска скрипта в консоли.
    :return: Полученные аргументы.
    """
    parser = argparse.ArgumentParser()

    parser.add_argument("filename", help="Path to audio file")
    parser.add_argument("--output", "--o", help="Path to output folder")
    parser.add_argument("--url", "--u", help="Url to post data")
    parser.add_argument("--apikey", "--ak",  help="Api key for access") # ВРЕМЕННО НЕ ИСПОЛЬЗУЕТСЯ

    return parser.parse_args()


def separate_guitars(path_to_dir_with_separation : Path):
    """
    Разделение гитарных партий
    (lead и rhythm)
    :param path_to_dir_with_separation: Путь к папке, где лежат
    разделенные партии.
    :return: Пути к файлам лид и ритм гитар.
    """
    path_to_other_file = str(path_to_dir_with_separation / "other.wav")
    waveform, sample_rate = librosa.load(path_to_other_file)

    lead, rhythm = librosa.effects.hpss(waveform)

    lead_guitar_filename = (config.AVAILABLE_INSTRUMENTS_FOR_TABS.lead_guitar
                            + config.EXTENSIONS.wav)
    rhythm_guitar_filename = (config.AVAILABLE_INSTRUMENTS_FOR_TABS.rhythm_guitar
                              + config.EXTENSIONS.wav)

    path_to_lead = str(path_to_dir_with_separation / lead_guitar_filename)
    path_to_rhythm = str(path_to_dir_with_separation / rhythm_guitar_filename)

    soundfile.write(path_to_lead, lead, sample_rate)
    soundfile.write(path_to_rhythm, rhythm, sample_rate)

    return path_to_lead, path_to_rhythm


def separate_audio(filename : Path):
    """
    Разделить аудио файл на аудио дорожки инструментов.
    :param filename: Путь к аудио файлу для разделения.
    :return: Путь к папке с разделенными партиями.
    """
    if not filename.is_absolute():
        filename = config.BASE_DIR / filename

    assert filename.is_file()
    assert os.path.exists(filename)
    print("Separating audio...")

    input_path = str(filename)
    output_path = str(config.BASE_DIR / config.DEMUCS_OUTPUT_DIR)

    if torch.cuda.is_available():
        print("CUDA ENABLED")
        result = subprocess.run(
            [str(config.VENV_PATH), "-m",
             "demucs", input_path,
             "--device", "cuda",
             "-o", output_path],
            capture_output=True
        )
    else:
        print("CUDA DISABLED")
        result = subprocess.run(
            [str(config.VENV_PATH), "-m",
             "demucs", input_path,
             "-o", output_path],
            capture_output=True
        )

    separated_dir_path = config.BASE_DIR / config.DEMUCS_OUTPUT_DIR / "htdemucs" / Path(filename).stem
    print("Separating lead and rhythm guitars...")
    separate_guitars(separated_dir_path)

    return separated_dir_path


def convert_audio_to_midi(filename_path : Path):
    """
    Функция конвертации аудио файла в MIDI-файл.
    :param filename_path: Путь к файлу.
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

    return result_path


def main():
    """
    Точка входа в скрипт.
    :return:
    """
    args = get_args()

    if args.output is not None:
        config.DEFAULT_NOTES_OUTPUT_DIR_PATH = Path(args.output)

    if args.url is not None:
        if not check_url(args.url):
            print(f"Url \"{args.url}\" is not found")
        else:
            config.NOTES_POST_URL = args.url

    print("Starting script")
    filename = Path(args.filename)
    dir_with_separation = separate_audio(filename)

    # Генерация и получение имен сгенерированных MIDI-файлов
    print("Creating MIDI-files...")
    midi_files = []
    for item in config.AVAILABLE_INSTRUMENTS_FOR_TABS.get_available_instruments_for_tabs_fields():
        available_instrument_attribute = getattr(config.AVAILABLE_INSTRUMENTS_FOR_TABS, item)
        midi_file = available_instrument_attribute + config.EXTENSIONS.wav
        path_to_file = dir_with_separation / midi_file

        # Сама конвертация
        path_to_midi = convert_audio_to_midi(path_to_file)
        midi_files.append(
            MidiFile(available_instrument_attribute,
                     path_to_midi)
        )

    generated_notes = {}

    print("Creating tab notes...")
    for midi_file in midi_files:
        generated_notes.setdefault(
            midi_file.instrument_type,
            NotesGenerator.create_notes(midi_file)
        )

    print("Dumping notes into json...")
    dump_notes_into_json(generated_notes, filename.stem)

    if config.NOTES_POST_URL is not None:
        print(f"Sending output to \"{config.NOTES_POST_URL}\"...")
        result = post_json(config.NOTES_POST_URL, generated_notes)
        if result == HTTPStatus.OK:
            print("Success!")
        else:
            print("Failed. Status code:", result)

    # Для отладки.
    if config.DEBUG:
        print("Rendering and saving tabs...")
        save_tabs_into_files(generated_notes, filename.stem)

    # Удаление временной директории
    print("Removing separated directory")
    delete_directory(dir_with_separation)


def save_tabs_into_files(generated_notes : dict, song_name : str):
    """
    DEBUG-функция сохранения текстовых табулатур в файл.
    :param generated_notes: Набор сгенерированных нот для всех инструментов.
    :param song_name: Название песни, по которой создается папка с табулатурами.
    :return: None
    """
    save_dir_path = config.DEBUG_TABS_SAVE_DIR_PATH / song_name
    save_dir_path.mkdir(exist_ok=True, parents=True)

    for instrument_type, instrument_notes in generated_notes.items():
        save_path = save_dir_path / (instrument_type + config.EXTENSIONS.txt)
        tabs = TabDrawer.create_tab(instrument_type, instrument_notes)
        with open(save_path, "w") as file:
            file.write(tabs)


def dump_notes_into_json(notes : dict, song_name : str):
    """
    Сохранить ноты в JSON-файл.
    :param notes: Словарь с нотами.
    :param song_name: Название песни, под которым будет сохраняться JSON-файл.
    :return: None
    """
    save_path = (config.DEFAULT_NOTES_OUTPUT_DIR_PATH
                 / config.DEFAULT_NOTES_OUTPUT_FILENAME.format(song_name))
    save_path.parent.mkdir(exist_ok=True, parents=True)
    print(f"Dumping into {save_path}")
    with open(save_path, "w") as file:
        json.dump(notes, file)


def delete_directory(directory_path : Path):
    """
    Удаление директории и ее поддиректорий
    :param directory_path: Путь к директории
    :return: None
    """
    assert directory_path.is_dir()
    shutil.rmtree(directory_path)


# Точка входа
if __name__ == "__main__":
    load_tools()
    main()
