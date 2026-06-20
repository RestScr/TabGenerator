from bpm import BeatMap
import config


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
