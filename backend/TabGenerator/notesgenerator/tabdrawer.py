from bpm import BeatMap
import config
from app.engines.tuning import get_tuning


class TabDrawer:
    """
    Тестовый класс-синглтон для
    генерации текстовых табулатур
    """
    _instance = None
    COLUMNS_PER_BAR = 27
    # BPMMap currently uses 1/2 of a quarter-note step, so a 4/4 measure
    # occupies eight generated beat cells.
    BEATS_PER_BAR = 8

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
    def create_tab(
        cls,
        instrument_type: str,
        notes: BeatMap,
        tuning: str = "standard_e",
        grid_units_per_measure: int | None = None,
        downbeat_offset_s: float = 0.0,
    ) -> str:
        """
        Фабричный метод генерации табов по заданному типу инструмента
        :param instrument_type:
        :param notes:
        :return:
        """
        if instrument_type == config.AVAILABLE_INSTRUMENTS_FOR_TABS.lead_guitar:
            return cls.__create_guitar_notes(notes, tuning, grid_units_per_measure, downbeat_offset_s)
        if instrument_type == config.AVAILABLE_INSTRUMENTS_FOR_TABS.rhythm_guitar:
            return cls.__create_guitar_notes(notes, tuning, grid_units_per_measure, downbeat_offset_s)
        else:
            return ""

    @classmethod
    def __create_guitar_notes(
        cls,
        beatmap: BeatMap,
        tuning: str = "standard_e",
        grid_units_per_measure: int | None = None,
        downbeat_offset_s: float = 0.0,
    ) -> str:
        """
        Генерация текстовых табулатур для гитары.
        :param beatmap: Гитарные ноты
        :return: Текстовые табулатуры.
        """
        if beatmap is None:
            return ""

        string_names = get_tuning(tuning)["names"]

        notes = []
        for beat in beatmap.beatmap:
            notes.extend(beat.notes)
        notes.sort(key=lambda note: (note.start, note.string))

        if len(notes) == 0:
            return "\n".join(f"{name:<2}||" for name in string_names)

        beats = beatmap.beatmap
        beat_duration = beats[0].end - beats[0].start if len(beats) > 0 else 0.5
        bar_duration = beat_duration * (grid_units_per_measure or cls.BEATS_PER_BAR)
        first_bar_start = downbeat_offset_s
        last_note_start = max(note.start for note in notes)
        bar_count = max(1, int((last_note_start - first_bar_start) // bar_duration) + 1)

        tab = [
            [["-" for _ in range(cls.COLUMNS_PER_BAR)] for _ in range(bar_count)]
            for _ in range(6)
        ]

        for note in notes:
            relative_start = max(0, note.start - first_bar_start)
            bar_index = min(int(relative_start // bar_duration), bar_count - 1)
            bar_start = first_bar_start + bar_index * bar_duration
            offset = (note.start - bar_start) / bar_duration
            column = round(offset * (cls.COLUMNS_PER_BAR - 1))
            column = max(0, min(column, cls.COLUMNS_PER_BAR - 1))
            row = 5 - note.string
            fret = str(note.fret)

            is_bass_string = note.string <= 1
            is_late_in_bar = column >= cls.COLUMNS_PER_BAR - 4
            crosses_next_bar = note.end is not None and note.end > bar_start + bar_duration
            if is_bass_string and is_late_in_bar and crosses_next_bar and bar_index + 1 < bar_count:
                bar_index += 1
                column = 0

            fret_width = len(fret)
            if column > cls.COLUMNS_PER_BAR - fret_width:
                continue

            target_cells = tab[row][bar_index][column:column + fret_width]
            has_left_neighbor = column > 0 and tab[row][bar_index][column - 1] != "-"
            has_right_neighbor = (
                column + fret_width < cls.COLUMNS_PER_BAR
                and tab[row][bar_index][column + fret_width] != "-"
            )
            if not all(cell == "-" for cell in target_cells) or has_left_neighbor or has_right_neighbor:
                # A guitar string cannot play two frets at the same instant.
                # Keep the original timing instead of moving the later note
                # into a different beat. Keep one empty cell between events
                # so multi-digit frets cannot become strings such as "1410".
                continue

            for index, char in enumerate(fret):
                tab[row][bar_index][column + index] = char

        # render
        out = []
        for i in range(6):
            out.append(cls.__render_string(string_names[i], tab[i]))

        return "\n".join(out)

    @classmethod
    def __render_string(cls, string_name : str, bars : list[list[str]]) -> str:
        """
        Отрисовка одной струны в более читаемом формате:
        E |------------------------|------------------------|
        """
        rendered_bars = ["".join(bar) for bar in bars]
        return f"{string_name:<2}|" + "|".join(rendered_bars) + "|"
