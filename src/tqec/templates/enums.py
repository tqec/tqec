from enum import Enum, auto
from typing import Literal


class ZObservableOrientation(Enum):
    HORIZONTAL = auto()
    VERTICAL = auto()

    def horizontal_basis(self) -> Literal["x", "z"]:
        return "z" if self == ZObservableOrientation.HORIZONTAL else "x"

    def vertical_basis(self) -> Literal["x", "z"]:
        return "z" if self == ZObservableOrientation.VERTICAL else "x"
