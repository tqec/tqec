import math
from abc import ABC, abstractmethod
from enum import Enum
from typing import ClassVar, Final

import svg
from typing_extensions import override

from tqec.interop.color import TQECColor
from tqec.plaquette.enums import PlaquetteOrientation
from tqec.plaquette.rpng.rpng import ExtendedBasis, PauliBasis
from tqec.utils.enums import Basis
from tqec.visualisation.configuration import DrawerConfiguration


def lerp(a: complex, b: complex, t: float) -> complex:
    """Linear interpolation between ``a`` and ``b``.

    Returns:
        a linear interpolation between ``a`` and ``b`` according to the provided
        ``t``: ``(1 - t) * a + t * b``.

    """
    return (1 - t) * a + t * b


class PlaquetteCorner(Enum):
    TOP_LEFT = "TL"
    TOP_RIGHT = "TR"
    BOTTOM_LEFT = "BL"
    BOTTOM_RIGHT = "BR"


class SVGPlaquetteDrawer(ABC):
    """Base class for plaquette drawers that output to SVG.

    A few static helper methods are defined in this class and can be re-used by sub-classes, for
    example to get a SVG path from a set of points.

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
        configuration: DrawerConfiguration = DrawerConfiguration(),
    ) -> svg.Element:
        """Draw the plaquette and return the drawing as a SVG element.

        Args:
            id: a unique ID representing the drawing. Used internally to reference the drawing. A
                good default value could be the name of the drawn plaquette.
            show_interaction_order: if ``True``, the time steps at which data-qubits interact with
                the syndrome qubit(s) is written on the drawing.
            show_hook_errors: if ``True``, a line is drawn to represent the hook error when it
                exists.
            show_data_qubit_reset_measurements: if ``True``, small symbols are used on data-qubits
                when a reset or a measurement is applied.
            configuration: drawing configuration.

        Returns:
            the drawing as a SVG element.

        """
        pass

    @staticmethod
    def get_square_shape(
        fill: str = "none",
        configuration: DrawerConfiguration = DrawerConfiguration(),
    ) -> svg.Path:
        """Get the shape of a regular square plaquette."""
        return svg_path_enclosing_points(SVGPlaquetteDrawer._CORNERS, fill, configuration)

    @staticmethod
    def get_triangle_shape(
        missing_qubit_corner: PlaquetteCorner,
        fill: str = "none",
        configuration: DrawerConfiguration = DrawerConfiguration(),
    ) -> svg.G:
        """Get the shape of a triangular plaquette only involving 3 data qubits.

        Args:
            missing_qubit_corner: the plaquette corner the missing qubit is located on.
            fill: SVG colour to use to fill the triangle.
            configuration: drawing configuration.

        """
        # Draw a TOP_LEFT corner 3-qubit triangular plaquette by default.
        _corners: Final[list[complex]] = SVGPlaquetteDrawer._CORNERS
        default_corners = [_corners[i] for i in [1, 2, 3]]
        t = configuration.plaquette_overflow_lerp_coefficient
        shoulders = [lerp(_corners[1], _corners[0], t), lerp(_corners[2], _corners[0], t)]
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
        configuration: DrawerConfiguration = DrawerConfiguration(),
    ) -> svg.Path:
        """Get the shape of a half-circle plaquette only involving 2 data qubits.

        Args:
            orientation: half circle plaquette orientation. ``UP`` means that the circular part is
                pointing up.
            fill: SVG colour to use to fill the square.
            configuration: drawing configuration.

        """
        match orientation:
            case PlaquetteOrientation.UP:
                start, end, sweep = (0, 1), (1, 1), True
            case PlaquetteOrientation.DOWN:
                start, end, sweep = (0, 0), (1, 0), False
            case PlaquetteOrientation.LEFT:
                start, end, sweep = (1, 0), (1, 1), False
            case _:
                start, end, sweep = (0, 0), (0, 1), True

        return svg.Path(
            d=[
                svg.M(*start),
                svg.Arc(0.5, 0.5, 180, True, sweep, *end),
                svg.Z(),
            ],
            fill=fill,
            stroke=configuration.stroke_color,
            stroke_width=configuration.stroke_width,
        )

    @staticmethod
    def get_reset_shape(
        place: PlaquetteCorner,
        fill: str = "none",
        configuration: DrawerConfiguration = DrawerConfiguration(),
    ) -> svg.Rect:
        """Return a small square with its origin at the opposite of ``place``.

        Args:
            place: the plaquette corner the reset is located on.
            fill: SVG colour to use to fill the square.
            configuration: drawing configuration.

        Returns:
            the reset shape (a small square) that can then be applied the appropriate offset to be
            placed in the ``place`` corner of the plaquette.

        """
        r = configuration.reset_square_radius
        return svg.Rect(
            x=0 if place in [PlaquetteCorner.TOP_LEFT, PlaquetteCorner.BOTTOM_LEFT] else -r,
            y=0 if place in [PlaquetteCorner.TOP_LEFT, PlaquetteCorner.TOP_RIGHT] else -r,
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
        configuration: DrawerConfiguration = DrawerConfiguration(),
    ) -> svg.G:
        """Return a small quarter circle with its origin at the opposite of ``place``.

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
    def get_colour(basis: Basis | PauliBasis | ExtendedBasis) -> str:
        """Get an SVG-compatible hexadecimal color from a basis."""
        match basis.value.upper():
            case "X":
                return TQECColor.X.rgba.to_hex()
            case "Y":
                return TQECColor.Y.rgba.to_hex()
            case "Z":
                return TQECColor.Z.rgba.to_hex()
            case _:
                return "none"

    @staticmethod
    def get_corner_coordinates(corner: PlaquetteCorner) -> complex:
        """Get the coordinates of the point corresponding the provided ``corner``."""
        match corner:
            case PlaquetteCorner.TOP_LEFT:
                return SVGPlaquetteDrawer._CORNERS[0]
            case PlaquetteCorner.TOP_RIGHT:
                return SVGPlaquetteDrawer._CORNERS[1]
            case PlaquetteCorner.BOTTOM_LEFT:
                return SVGPlaquetteDrawer._CORNERS[2]
            case PlaquetteCorner.BOTTOM_RIGHT:
                return SVGPlaquetteDrawer._CORNERS[3]


class EmptySVGPlaquetteDrawer(SVGPlaquetteDrawer):
    """SVG plaquete drawer that always returns an empty drawing."""

    @override
    def draw(
        self,
        id: str,
        show_interaction_order: bool = True,
        show_hook_errors: bool = True,
        show_data_qubit_reset_measurements: bool = True,
        configuration: DrawerConfiguration = DrawerConfiguration(),
    ) -> svg.Element:
        return svg.G()


def _sort_by_angle(center: complex, points: list[complex]) -> list[complex]:
    """Sort the given ``points`` w.r.t to the angle they form with the provided ``center``."""
    translated_points = [p - center for p in points]
    sorted_translated_points = sorted(translated_points, key=lambda c: math.atan2(c.imag, c.real))
    return [tp + center for tp in sorted_translated_points]


def svg_path_enclosing_points(
    points: list[complex],
    fill: str = "none",
    configuration: DrawerConfiguration = DrawerConfiguration(),
) -> svg.Path:
    """Draw a path enclosing all the provided points.

    Args:
        points: a list of points that will be linked together.
        fill: hexadecimal colour used to fill the produced path.
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
    pathdata.extend(svg.L(p.real, p.imag) for p in others)
    pathdata.append(svg.Z())
    return svg.Path(
        d=pathdata,
        fill=fill,
        stroke=configuration.stroke_color,
        stroke_width=configuration.stroke_width,
    )
