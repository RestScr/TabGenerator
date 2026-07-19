import config
from pathlib import Path
import os


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
