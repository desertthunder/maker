from enum import Enum


class Color(str, Enum):
    SUCCESS = "\033[92m"
    ERROR = "\033[91m"
    INFO = "\033[94m"
    WARNING = "\033[93m"
    RESET = "\033[0m"


def colored(text: str, color: Color) -> str:
    return f"{color.value}{text}{Color.RESET.value}"

def echo(text: str, color: Color = Color.INFO) -> None:
    print(colored(text, color))

class InvalidPaperSizeError(ValueError):
    def __init__(self, size_str: str):
        super().__init__(
            f"Invalid paper size: {size_str}. Valid sizes: {[s.name for s in PaperSize]}"
        )


class NotADirectoryError(ValueError):
    def __init__(self, path: str):
        super().__init__(f"Not a directory: {path}")

class ProcessingError(Exception):
    def __init__(self, message: str):
        super().__init__(message)

class InvalidInputError(Exception):
    def __init__(self, input: str):
        super().__init__(f"Invalid input: {input}")

class PaperSize(Enum):
    A0 = (2384, 3370)
    A1 = (1684, 2384)
    A2 = (1191, 1684)
    A3 = (842, 1191)
    A4 = (595, 842)
    A5 = (420, 595)
    A6 = (298, 420)
    A7 = (210, 298)
    A8 = (147, 210)
    A9 = (105, 147)
    A10 = (74, 105)
    B0 = (2835, 4008)
    B1 = (2004, 2835)
    B2 = (1417, 2004)
    B3 = (1001, 1417)
    B4 = (709, 1001)
    B5 = (499, 709)
    B6 = (354, 499)
    B7 = (249, 354)
    B8 = (176, 249)
    B9 = (125, 176)
    B10 = (88, 125)

    @property
    def width(self) -> int:
        return self.value[0]

    @property
    def height(self) -> int:
        return self.value[1]

    @staticmethod
    def from_string(size_str: str) -> "PaperSize":
        try:
            return PaperSize[size_str.upper()]
        except KeyError as exc:
            raise InvalidPaperSizeError(size_str) from exc

