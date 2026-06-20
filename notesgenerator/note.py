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
