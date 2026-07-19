class Note:
    """
    Базовый класс всех нот музыкальных
    инструментов.
    """
    def __init__(self, start, end=None, velocity=None):
        self.start = start
        self.end = end
        self.velocity = velocity


class GuitarNote(Note):
    """
    Класс гитарной ноты, хранящий
    информацию о проигрываемой струне и ладе.
    """
    def __init__(self, start, string, fret, end=None, velocity=None):
        super().__init__(start, end, velocity)
        self.string = string
        self.fret = fret

    def __iter__(self):
        return iter([self.start, self.end, self.velocity, self.string, self.fret])

    def to_dict(self):
        return {
            "start" : self.start,
            "end" : self.end,
            "velocity" : self.velocity,
            "string" : self.string,
            "fret" : self.fret
        }
