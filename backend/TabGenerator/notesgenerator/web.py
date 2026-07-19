"""
Подмодуль, отвечающий за операции с http запросами
"""
import requests
from urllib.parse import urlparse


def check_url(url : str) -> bool:
    """
    Проверка, существует ли ссылка.
    :param url: Ссылка для проверки.
    :return: bool
    """
    try:
        response = requests.get(url, timeout=5)
        return True
    except requests.RequestException:
        return False


def post_json(url : str, data : dict) -> int:
    """
    Функция отправки JSON файлов на сервер.
    :param url: Ссылка.
    :param data: JSON-Объект для отправки.
    :return: Статус кода состояния HTTP.
    """
    result = requests.post(url, json=data)
    return result.status_code
