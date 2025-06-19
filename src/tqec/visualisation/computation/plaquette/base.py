import math
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import ClassVar, Final

import svg
from typing_extensions import override

from tqec.interop.color import TQECColor
from tqec.plaquette.enums import PlaquetteOrientation
from tqec.plaquette.rpng.rpng import ExtendedBasis, PauliBasis


def lerp(a: complex, b: complex, t: float) -> complex:
    """Linear interpolation between ``a`` and ``b``.

    Returns:
        a linear interpolation between ``a`` and ``b`` according to the provided
        ``t``: ``(1 - t) * a + t * b``.

    """
    return (1 - t) * a + t * b


@dataclass(frozen=True)
class PlaquetteDrawerConfiguration:
    """Drawing configuration with sensible defaults that can be modified by the user.

    Attributes:
        stroke_width: default stroke width used for all the drawing, except for
            error crosses.
        stroke_color: default stroke color used for all the drawing, except for
            error crosses.
        font_size: default font size of all the text in the drawing except the
            overlaid "Moments: XX -> YY" text.
        hook_error_line_lerp_coefficient: a coefficient in [0, 1] that defines how close
            the hook error line should be from the borders of the plaquette. As an
            implementation detail, that number is also the hook error line length
            compared to the full plaquette width or height. A value of ``0.9`` means
            that the hook error line is closer to the plaquette border than to the
            plaquette center.
        plaquette_overflow_lerp_coefficient: coefficient in [0, 1] that defines how
            some plaquettes overflow from the regular convex hull of the involved
            data qubits. This is currently used for triangular plaquettes, but might
            be used for other plaquettes later. A value of ``0`` means "no overflow"
            whereas a value of ``1`` means "full overflow up to the missing data qubit".
        text_lerp_coefficient: coefficient in [0, 1] that defines where data-qubit
            interaction orders are written in the plaquette. A value of ``0`` means
            "on their respective data-qubit" whereas a value of ``1`` means "on the
            plaquette center".
        mixed_basis_color: color used to plot plaquettes measuring a non-uniform
            Pauli basis (e.g. ``ZXXZ``).
        reset_square_radius: representative size (in SVG coordinates) of the square used
            to represent data-qubit reset.
        measurement_circle_radius: representative size (in SVG coordinates) of the circle
            used to represent data-qubit measurement.

    """

    stroke_width: float = 0.01
    stroke_color: str = "black"
    font_size: float = 0.1
    hook_error_line_lerp_coefficient: float = 0.9
    plaquette_overflow_lerp_coefficient: float = 0.2
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
    """Base class for plaquette drawers that output to SVG.

    A few static helper methods are defined in this class and can be re-used by
    sub-classes, for example to get a SVG path from a set of points.
    """

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
    def get_square_shape(
        fill: str = "none",
        configuration: PlaquetteDrawerConfiguration = PlaquetteDrawerConfiguration(),
    ) -> svg.Path:
        """Get the shape of a regular square plaquette."""
        return svg_path_enclosing_points(SVGPlaquetteDrawer._CORNERS, fill, configuration)

    @staticmethod
    def get_triangle_shape(
        missing_qubit_corner: PlaquetteCorner,
        fill: str = "none",
        configuration: PlaquetteDrawerConfiguration = PlaquetteDrawerConfiguration(),
    ) -> svg.G:
        """Get the shape of a triangular plaquette only involving 3 data qubits.

        Args:
            missing_qubit_corner: the plaquette corner the missing qubit is located on.
            fill: SVG colour to use to fill the triangle.
            configuration: drawing configuration.

        """
        # Draw a TOP_LEFT corner 3-qubit triangular plaquette by default.
        _CORNS: Final = SVGPlaquetteDrawer._CORNERS
        default_corners = [_CORNS[i] for i in [1, 2, 3]]
        t = configuration.plaquette_overflow_lerp_coefficient
        shoulders = [lerp(_CORNS[1], _CORNS[0], t), lerp(_CORNS[2], _CORNS[0], t)]
        default_triangular_path = svg_path_enclosing_points(
            default_corners + shoulders, fill, configuration
        )
        # Rotate the drawn plaquette if needed.
        rotation_angle: int = {
            PlaquetteCorner.TOP_LEFT: 0,
            PlaquetteCorner.TOP_RIGHT: 90,
            PlaquetteCorner.BOTTOM_LEFT: 270,
            PlaquetteCorner.BOTTOM_RIGHT: 180,
        }[missing_qubit_corner]
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
        """Get the shape of a half-circle plaquette only involving 2 data qubits.

        Args:
            orientation: half circle plaquette orientation. ``UP`` means that the circular part is
                pointing up.
            fill: SVG colour to use to fill the square.
            configuration: drawing configuration.

        """
        PO = PlaquetteOrientation
        rotation_angle: int = {PO.UP: 0, PO.DOWN: 180, PO.LEFT: 270, PO.RIGHT: 90}[orientation]
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
        """Returns a small square with its origin at the opposite of ``place``.

        Args:
            place: the plaquette corner the reset is located on.
            fill: SVG colour to use to fill the square.
            configuration: drawing configuration.

        Returns:
            the reset shape (a small square) that can then be applied the appropriate offset to be
            placed in the ``place`` corner of the plaquette.

        """
        r = configuration.reset_square_radius
        PC = PlaquetteCorner
        return svg.Rect(
            x=0 if place in [PC.TOP_LEFT, PC.BOTTOM_LEFT] else -r,
            y=0 if place in [PC.TOP_LEFT, PC.TOP_RIGHT] else -r,
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
        """Returns a small quarter circle with its origin at the opposite of ``place``.

        Args:
            place: the plaquette corner the measurement is located on.
            fill: SVG colour to use to fill the quarter circle.
            configuration: drawing configuration.

        Returns:
            the measurement shape (a small quarter circle) that can then be applied the appropriate
            offset to be placed in the ``place`` corner of the plaquette.

        """
        rotation_angle: int = {
            PlaquetteCorner.TOP_LEFT: 0,
            PlaquetteCorner.BOTTOM_LEFT: 270,
            PlaquetteCorner.TOP_RIGHT: 90,
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
        """Helper to get a SVG-compatible hexadecimal color from a basis."""
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
    """SVG plaquete drawer that always returns an empty drawing."""

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
    """Sort the given ``points`` according to the angle they form with respect to
    the provided ``center``.
    """
    translated_points = [p - center for p in points]
    sorted_translated_points = sorted(translated_points, key=lambda c: math.atan2(c.imag, c.real))
    return [tp + center for tp in sorted_translated_points]


def svg_path_enclosing_points(
    points: list[complex],
    fill: str = "none",
    configuration: PlaquetteDrawerConfiguration = PlaquetteDrawerConfiguration(),
) -> svg.Path:
    """Draw a path enclosing all the provided points.

    Args:
        points: a list of points that will be linked together.
        configuration: drawing configuration.

    Warning:
        This function does **NOT** returns the convex hull of the provided points
        as a SVP path. It simply links the provided points one after the other
        after ordering them according to the angle they form with respect to their
        average (equivalent to their center of mass where each point has a mass
        of ``1``).

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
