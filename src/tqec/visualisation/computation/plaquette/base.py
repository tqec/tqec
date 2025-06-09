from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
import math
from typing import ClassVar, Final
from typing_extensions import override
import svg

from tqec.interop.color import TQECColor
from tqec.plaquette.enums import PlaquetteOrientation
from tqec.plaquette.rpng.rpng import ExtendedBasis, PauliBasis
from tqec.visualisation.exception import TQECDrawingException


def lerp(a: complex, b: complex, t: float) -> complex:
    return (1 - t) * a + t * b


def _is_close(a: complex, b: complex, atol: float = 1e-8) -> bool:
    return abs(b - a) < atol


@dataclass(frozen=True)
class PlaquetteDrawerConfiguration:
    stroke_width: float = 0.01
    stroke_color: str = "black"
    font_size: float = 0.1
    hook_error_line_lerp_coefficient: float = 0.9
    plaquette_overfill_lerp_coefficient: float = 0.2
    text_lerp_coefficient: float = 0.8
    mixed_basis_color: str = "gray"
    reset_square_radius: float = 0.05
    measurement_circle_radius: float = 0.1


class PlaquetteCorner(Enum):
    TOP_LEFT = "TL"
    TOP_RIGHT = "TR"
    BOTTOM_LEFT = "BL"
    BOTTOM_RIGHT = "BR"


class SVGPlaquetteDrawer(ABC):
    _CENTER_COORDINATE: ClassVar[complex] = 0.5 + 0.5j
    _CORNERS: ClassVar[list[complex]] = [0, 1, 1.0j, 1 + 1.0j]
    _CORNERS_ENUM: ClassVar[list[PlaquetteCorner]] = [
        PlaquetteCorner.TOP_LEFT,
        PlaquetteCorner.TOP_RIGHT,
        PlaquetteCorner.BOTTOM_LEFT,
        PlaquetteCorner.BOTTOM_RIGHT,
    ]

    @abstractmethod
    def draw(
        self,
        id: str,
        show_interaction_order: bool = True,
        show_hook_errors: bool = True,
        show_data_qubit_reset_measurements: bool = True,
        configuration: PlaquetteDrawerConfiguration = PlaquetteDrawerConfiguration(),
    ) -> svg.Element:
        pass

    @staticmethod
    def get_corner_enum(corner: complex) -> PlaquetteCorner:
        for enum_value, coords in zip(
            SVGPlaquetteDrawer._CORNERS_ENUM, SVGPlaquetteDrawer._CORNERS
        ):
            if _is_close(corner, coords):
                return enum_value
        raise TQECDrawingException(f"Cannot find the coorner for point {corner}.")

    @staticmethod
    def get_square_shape(
        fill: str = "none",
        configuration: PlaquetteDrawerConfiguration = PlaquetteDrawerConfiguration(),
    ) -> svg.Path:
        return svg_path_enclosing_points(
            SVGPlaquetteDrawer._CORNERS, fill, configuration
        )

    @staticmethod
    def get_triangle_shape(
        place: PlaquetteCorner,
        fill: str = "none",
        configuration: PlaquetteDrawerConfiguration = PlaquetteDrawerConfiguration(),
    ) -> svg.G:
        _CORNS: Final = SVGPlaquetteDrawer._CORNERS
        default_corners = [_CORNS[i] for i in [1, 2, 3]]
        t = configuration.plaquette_overfill_lerp_coefficient
        shoulders = [lerp(_CORNS[1], _CORNS[0], t), lerp(_CORNS[2], _CORNS[0], t)]
        default_triangular_path = svg_path_enclosing_points(
            default_corners + shoulders, fill, configuration
        )
        rotation_angle: int = {
            PlaquetteCorner.TOP_LEFT: 0,
            PlaquetteCorner.TOP_RIGHT: 90,
            PlaquetteCorner.BOTTOM_LEFT: 270,
            PlaquetteCorner.BOTTOM_RIGHT: 180,
        }[place]
        return svg.G(
            transform=[
                svg.Rotate(
                    rotation_angle,
                    SVGPlaquetteDrawer._CENTER_COORDINATE.real,
                    SVGPlaquetteDrawer._CENTER_COORDINATE.imag,
                )
            ],
            elements=[default_triangular_path],
        )

    @staticmethod
    def get_half_circle_shape(
        orientation: PlaquetteOrientation,
        fill: str = "none",
        configuration: PlaquetteDrawerConfiguration = PlaquetteDrawerConfiguration(),
    ) -> svg.G:
        PO = PlaquetteOrientation
        rotation_angle: int = {PO.UP: 0, PO.DOWN: 180, PO.LEFT: 270, PO.RIGHT: 90}[
            orientation
        ]
        default_half_circle_path = svg.Path(
            d=[
                svg.M(0, 1),
                svg.Arc(0.5, 0.5, 180, True, True, 1, 1),
                svg.Z(),
            ],
            fill=fill,
            stroke=configuration.stroke_color,
            stroke_width=configuration.stroke_width,
        )
        return svg.G(
            transform=[
                svg.Rotate(
                    rotation_angle,
                    SVGPlaquetteDrawer._CENTER_COORDINATE.real,
                    SVGPlaquetteDrawer._CENTER_COORDINATE.imag,
                )
            ],
            elements=[default_half_circle_path],
        )

    @staticmethod
    def get_reset_shape(
        place: PlaquetteCorner,
        fill: str = "none",
        configuration: PlaquetteDrawerConfiguration = PlaquetteDrawerConfiguration(),
    ) -> svg.Rect:
        r = configuration.reset_square_radius
        PC = PlaquetteCorner
        return svg.Rect(
            x=0 if place in [PC.TOP_LEFT, PC.BOTTOM_LEFT] else 1 - r,
            y=0 if place in [PC.TOP_LEFT, PC.TOP_RIGHT] else 1 - r,
            width=r,
            height=r,
            fill=fill,
            stroke=configuration.stroke_color,
            stroke_width=configuration.stroke_width,
        )

    @staticmethod
    def get_measurement_shape(
        place: PlaquetteCorner,
        fill: str = "none",
        configuration: PlaquetteDrawerConfiguration = PlaquetteDrawerConfiguration(),
    ) -> svg.G:
        rotation_angle: int = {
            PlaquetteCorner.TOP_LEFT: 0,
            PlaquetteCorner.TOP_RIGHT: 270,
            PlaquetteCorner.BOTTOM_LEFT: 90,
            PlaquetteCorner.BOTTOM_RIGHT: 180,
        }[place]
        r = configuration.measurement_circle_radius
        return svg.G(
            elements=[
                svg.Path(
                    d=[
                        svg.M(0, 0),
                        svg.L(0, r),
                        svg.Arc(r, r, 90, False, False, r, 0),
                        svg.Z(),
                    ],
                    stroke=configuration.stroke_color,
                    stroke_width=configuration.stroke_width,
                    fill=fill,
                )
            ],
            transform=[svg.Rotate(rotation_angle, 0, 0)],
        )

    @staticmethod
    def get_colour(basis: PauliBasis | ExtendedBasis) -> str:
        match basis.value.upper():
            case "X":
                return TQECColor.X.rgba.to_hex()
            case "Y":
                return TQECColor.Y.rgba.to_hex()
            case "Z":
                return TQECColor.Z.rgba.to_hex()
            case _:
                return "none"


class EmptySVGPlaquetteDrawer(SVGPlaquetteDrawer):
    @override
    def draw(
        self,
        id: str,
        show_interaction_order: bool = True,
        show_hook_errors: bool = True,
        show_data_qubit_reset_measurements: bool = True,
        configuration: PlaquetteDrawerConfiguration = PlaquetteDrawerConfiguration(),
    ) -> svg.Element:
        return svg.G()


def _sort_by_angle(center: complex, points: list[complex]) -> list[complex]:
    translated_points = [p - center for p in points]
    sorted_translated_points = sorted(
        translated_points, key=lambda c: math.atan2(c.imag, c.real)
    )
    return [tp + center for tp in sorted_translated_points]


def svg_path_enclosing_points(
    points: list[complex],
    fill: str = "none",
    configuration: PlaquetteDrawerConfiguration = PlaquetteDrawerConfiguration(),
) -> svg.Path:
    """Draw a path enclosing all the provided points.

    Args:
        points:
        configuration:

    Returns:
        a closed path enclosing all the provided ``points``.
    """
    center_point: complex = sum(points) / len(points)
    first, *others = _sort_by_angle(center_point, points)
    pathdata: list[svg.PathData] = [svg.M(first.real, first.imag)]
    for p in others:
        pathdata.append(svg.L(p.real, p.imag))
    pathdata.append(svg.Z())
    return svg.Path(
        d=pathdata,
        fill=fill,
        stroke=configuration.stroke_color,
        stroke_width=configuration.stroke_width,
    )
