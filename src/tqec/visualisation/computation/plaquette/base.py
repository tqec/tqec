from abc import ABC, abstractmethod
from dataclasses import dataclass, field

import svg


@dataclass
class SVGLayers:
    fill: list[svg.Element] = field(default_factory=list)
    draw: list[svg.Element] = field(default_factory=list)
    text: list[svg.Element] = field(default_factory=list)

    def flatten(self) -> list[svg.Element]:
        return self.fill + self.draw + self.text


class SVGPlaquetteDrawer(ABC):
    _CENTER_COORDINATE: complex = 0.5 + 0.5j
    _CORNERS: list[complex] = [0, 1, 1.0j, 1 + 1.0j]

    @abstractmethod
    def draw(
        self,
        width: float,
        height: float,
        uuid: str,
        show_interaction_order: bool = True,
        show_hook_errors: bool = False,
    ) -> SVGLayers:
        pass
