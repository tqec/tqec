from abc import ABC, abstractmethod
from dataclasses import dataclass, field
import math
from typing import ClassVar

import svg


@dataclass
class SVGLayers:
    fill: list[svg.Element] = field(default_factory=list)
    draw: list[svg.Element] = field(default_factory=list)
    text: list[svg.Element] = field(default_factory=list)

    def flatten(self) -> list[svg.Element]:
        return self.fill + self.draw + self.text


class SVGPlaquetteDrawer(ABC):
    _CENTER_COORDINATE: ClassVar[complex] = 0.5 + 0.5j
    _CORNERS: ClassVar[list[complex]] = [0, 1, 1.0j, 1 + 1.0j]

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

    @staticmethod
    def scale_point(point: complex, width: float, height: float) -> complex:
        return complex(width * point.real, height * point.imag)


def _sort_by_angle(center: complex, points: list[complex]) -> list[complex]:
    translated_points = [p - center for p in points]
    sorted_translated_points = sorted(
        translated_points, key=lambda c: math.atan2(c.imag, c.real)
    )
    return [tp + center for tp in sorted_translated_points]


def svg_path_enclosing_points(points: list[complex]) -> svg.Path:
    center_point: complex = sum(points) / len(points)
    first, *others = _sort_by_angle(center_point, points)
    pathdata: list[svg.PathData] = [svg.M(first.real, first.imag)]
    for p in others:
        pathdata.append(svg.L(p.real, p.imag))
    pathdata.append(svg.Z())
    return svg.Path(d=pathdata, fill="none", stroke="black", stroke_width=0.01)
