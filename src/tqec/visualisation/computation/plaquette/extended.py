from __future__ import annotations

from enum import Enum, auto
from typing import cast

import svg
from typing_extensions import override

from tqec.plaquette.rpng import PauliBasis
from tqec.utils.enums import Basis
from tqec.visualisation.computation.plaquette.base import (
    PlaquetteCorner,
    SVGPlaquetteDrawer,
    lerp,
    svg_path_enclosing_points,
)
from tqec.visualisation.configuration import DrawerConfiguration
from tqec.visualisation.exception import TQECDrawingError


class ExtendedPlaquettePosition(Enum):
    UP = "UP"
    DOWN = "DOWN"
    LEFT = "LEFT"
    RIGHT = "RIGHT"

    def flip(self) -> ExtendedPlaquettePosition:
        """Return the opposite direction."""
        match self:
            case ExtendedPlaquettePosition.UP:
                return ExtendedPlaquettePosition.DOWN
            case ExtendedPlaquettePosition.DOWN:
                return ExtendedPlaquettePosition.UP
            case ExtendedPlaquettePosition.LEFT:
                return ExtendedPlaquettePosition.RIGHT
            case ExtendedPlaquettePosition.RIGHT:
                return ExtendedPlaquettePosition.LEFT
            # wildcard entry added as it was flagged by ty
            case _:
                raise ValueError("Unexpected input provided.")


class ExtendedPlaquetteType(Enum):
    BULK = auto()
    BOTTOM_RIGHT_TRIANGLE = auto()
    RIGHT_HALF_RECTANGLE = auto()
    TOP_LEFT_TRIANGLE = auto()
    LEFT_HALF_RECTANGLE = auto()
    BOTTOM_LEFT_TRIANGLE = auto()
    TOP_RIGHT_TRIANGLE = auto()


class ExtendedPlaquetteDrawer(SVGPlaquetteDrawer):
    def __init__(
        self,
        plaquette_type: ExtendedPlaquetteType,
        position: ExtendedPlaquettePosition,
        basis: Basis | PauliBasis | None,
        schedule: tuple[int, int, int, int],
        reset: Basis | None = None,
        measurement: Basis | None = None,
    ) -> None:
        """SVG plaquette drawer for extended plaquettes."""
        super().__init__()
        self._plaquette_type = plaquette_type
        self._position = position
        self._basis = basis
        self._schedule = (
            schedule[0:2]
            if position
            in (ExtendedPlaquettePosition.UP, ExtendedPlaquettePosition.LEFT)
            else schedule[2:4]
        )
        self._reset = reset
        self._measurement = measurement

    @staticmethod
    def _is_first(position: ExtendedPlaquettePosition) -> bool:
        """Whether the position is the first of a (UP, DOWN) or (LEFT, RIGHT) pair."""
        return position in (
            ExtendedPlaquettePosition.UP,
            ExtendedPlaquettePosition.LEFT,
        )

    @staticmethod
    def _transform_point(
        position: ExtendedPlaquettePosition, point: complex
    ) -> complex:
        """Transpose a point for horizontal (LEFT/RIGHT) positions.

        Horizontal extended plaquettes are drawn by transposing the vertical
        layout inside the same drawing domain: the top edge becomes the left
        edge and the bottom edge becomes the right edge.
        """
        if position in (
            ExtendedPlaquettePosition.LEFT,
            ExtendedPlaquettePosition.RIGHT,
        ):
            return complex(point.imag / 2, 2 * point.real)
        return point

    @override
    def draw(
        self,
        id: str,
        show_interaction_order: bool = True,
        show_hook_errors: bool = True,
        show_data_qubit_reset_measurements: bool = True,
        configuration: DrawerConfiguration = DrawerConfiguration(),
    ) -> svg.Element:
        # Build iteratively the different layers that we need to represent the
        # plaquette.
        shape_path = self.get_plaquette_shape_path(configuration)
        layers: list[svg.Element] = []
        # If the plaquette has a uniform color, the shape include that color with
        # its "fill" attribute and so we do not need to clip. If that is not the
        # case, the filling colours will be added with get_fill_layer, but it is
        # simpler for the implementation to clip.
        layers.append(shape_path)
        if show_data_qubit_reset_measurements:
            layers.append(self.get_data_qubit_reset_measurements_layers(configuration))
        if show_hook_errors:
            if (line := self.get_hook_error_line(configuration)) is not None:
                layers.append(line)
        if show_interaction_order:
            layers.extend(self.get_interaction_order_text(configuration))
        return svg.G(id=id, elements=layers)

    @staticmethod
    def _get_extended_plaquette_square_shape(
        position: ExtendedPlaquettePosition,
        plaquette_type: ExtendedPlaquetteType,
        fill: str = "none",
        configuration: DrawerConfiguration = DrawerConfiguration(),
    ) -> svg.G:
        tl, tr, bl, br = SVGPlaquetteDrawer._CORNERS
        if position in (
            ExtendedPlaquettePosition.LEFT,
            ExtendedPlaquettePosition.RIGHT,
        ):
            tl, tr, bl, br = (
                ExtendedPlaquetteDrawer._transform_point(position, tl),
                ExtendedPlaquetteDrawer._transform_point(position, tr),
                ExtendedPlaquetteDrawer._transform_point(position, bl),
                ExtendedPlaquetteDrawer._transform_point(position, br),
            )
        if plaquette_type == ExtendedPlaquetteType.RIGHT_HALF_RECTANGLE:
            tl, bl = (tl + tr) / 2, (bl + br) / 2
        elif plaquette_type == ExtendedPlaquetteType.LEFT_HALF_RECTANGLE:
            tr, br = (tl + tr) / 2, (bl + br) / 2

        up_stroke_color, down_stroke_color = (
            configuration.stroke_color,
            configuration.thin_stroke_color,
        )
        if position in (
            ExtendedPlaquettePosition.DOWN,
            ExtendedPlaquettePosition.RIGHT,
        ):
            up_stroke_color, down_stroke_color = down_stroke_color, up_stroke_color
        return svg.G(
            elements=[
                # Filling
                svg.Rect(
                    x=tl.real,
                    y=tl.imag,
                    width=(br.real - tl.real),
                    height=(br.imag - tl.imag),
                    fill=fill,
                ),
                # UP
                svg.Line(
                    x1=tl.real,
                    y1=tl.imag,
                    x2=tr.real,
                    y2=tr.imag,
                    stroke=up_stroke_color,
                    stroke_width=configuration.stroke_width,
                ),
                # DOWN
                svg.Line(
                    x1=bl.real,
                    y1=bl.imag,
                    x2=br.real,
                    y2=br.imag,
                    stroke=down_stroke_color,
                    stroke_width=configuration.stroke_width,
                ),
                # LEFT
                svg.Line(
                    x1=tl.real,
                    y1=tl.imag,
                    x2=bl.real,
                    y2=bl.imag,
                    stroke=configuration.stroke_color,
                    stroke_width=configuration.stroke_width,
                ),
                # RIGHT
                svg.Line(
                    x1=tr.real,
                    y1=tr.imag,
                    x2=br.real,
                    y2=br.imag,
                    stroke=configuration.stroke_color,
                    stroke_width=configuration.stroke_width,
                ),
            ]
        )

    @staticmethod
    def _get_weight_three_extended_plaquette_shape(
        position: ExtendedPlaquettePosition,
        plaquette_type: ExtendedPlaquetteType,
        fill: str = "none",
        configuration: DrawerConfiguration = DrawerConfiguration(),
    ) -> svg.Element:
        if position in (
            ExtendedPlaquettePosition.DOWN,
            ExtendedPlaquettePosition.RIGHT,
        ):
            return svg.G()
        _, tr, bl, br = SVGPlaquetteDrawer._CORNERS
        bl += 1j
        br += 1j
        center = 0.5 + 1j
        side_length = configuration.plaquette_overflow_lerp_coefficient

        vs = [bl, bl - side_length * 1j, tr - side_length, tr, br]
        match plaquette_type:
            case ExtendedPlaquetteType.BOTTOM_RIGHT_TRIANGLE:
                pass
            case ExtendedPlaquetteType.BOTTOM_LEFT_TRIANGLE:
                vs = [complex(1 - v.real, v.imag) for v in vs]
            case ExtendedPlaquetteType.TOP_LEFT_TRIANGLE:
                vs = [2 * center - v for v in vs]
            case ExtendedPlaquetteType.TOP_RIGHT_TRIANGLE:
                vs = [complex(1 - v.real, v.imag) for v in (2 * center - v for v in vs)]
            case _:
                raise ValueError("Unsupported triangle plaquette type provided.")
        if position == ExtendedPlaquettePosition.LEFT:
            vs = [ExtendedPlaquetteDrawer._transform_point(position, v) for v in vs]
        return svg_path_enclosing_points(vs, fill, configuration)

    def get_plaquette_shape_path(
        self,
        configuration: DrawerConfiguration = DrawerConfiguration(),
    ) -> svg.Element:
        """Return the plaquette shape, uniformly filled with the appropriate color.

        Args:
            configuration: drawing configuration.

        Returns:
            The plaquette shape. It is filled with the appropriate colour corresponding to
            the value of ``self._basis``.

        """
        fill = "none" if self._basis is None else SVGPlaquetteDrawer.get_colour(self._basis)
        match self._plaquette_type:
            case (
                ExtendedPlaquetteType.BULK
                | ExtendedPlaquetteType.RIGHT_HALF_RECTANGLE
                | ExtendedPlaquetteType.LEFT_HALF_RECTANGLE
            ):
                return ExtendedPlaquetteDrawer._get_extended_plaquette_square_shape(
                    self._position, self._plaquette_type, fill, configuration
                )
            case (
                ExtendedPlaquetteType.BOTTOM_RIGHT_TRIANGLE
                | ExtendedPlaquetteType.TOP_LEFT_TRIANGLE
                | ExtendedPlaquetteType.BOTTOM_LEFT_TRIANGLE
                | ExtendedPlaquetteType.TOP_RIGHT_TRIANGLE
            ):
                return ExtendedPlaquetteDrawer._get_weight_three_extended_plaquette_shape(
                    self._position, self._plaquette_type, fill, configuration
                )
            # wildcard entry added as it was flagged by ty
            case _:
                raise ValueError("Unsupported input provided.")

    def get_interaction_order_text(
        self,
        configuration: DrawerConfiguration = DrawerConfiguration(),
    ) -> list[svg.Text]:
        """Return a SVG element containing data-qubit interaction orders as text.

        This function returns one SVG element per non-empty corners, each containing a text element
        with the time slice at which a 2-qubit operation is applied on the corner qubit.

        Args:
            configuration: drawing configuration.

        Returns:
            One SVG element per non-empty corners, each containing a text
            element with the time slice at which a 2-qubit operation is applied
            on the corner qubit.

        """
        interaction_order_texts: list[svg.Text] = []
        tl, tr, bl, br = SVGPlaquetteDrawer._CORNERS
        if self._position in (
            ExtendedPlaquettePosition.LEFT,
            ExtendedPlaquettePosition.RIGHT,
        ):
            tl, tr, bl, br = (
                ExtendedPlaquetteDrawer._transform_point(self._position, tl),
                ExtendedPlaquetteDrawer._transform_point(self._position, tr),
                ExtendedPlaquetteDrawer._transform_point(self._position, bl),
                ExtendedPlaquetteDrawer._transform_point(self._position, br),
            )
        s1, s2 = self._schedule
        data_corners: list[complex]
        schedules: list[int]
        match self._plaquette_type:
            case ExtendedPlaquetteType.BULK:
                data_corners = (
                    [tl, tr]
                    if ExtendedPlaquetteDrawer._is_first(self._position)
                    else [bl, br]
                )
                schedules = [s1, s2]
            case ExtendedPlaquetteType.BOTTOM_RIGHT_TRIANGLE:
                data_corners = (
                    [tr] if ExtendedPlaquetteDrawer._is_first(self._position) else [bl, br]
                )
                schedules = (
                    [s2] if ExtendedPlaquetteDrawer._is_first(self._position) else [s1, s2]
                )
            case ExtendedPlaquetteType.TOP_LEFT_TRIANGLE:
                data_corners = (
                    [tl, tr] if ExtendedPlaquetteDrawer._is_first(self._position) else [bl]
                )
                schedules = (
                    [s1, s2]
                    if ExtendedPlaquetteDrawer._is_first(self._position)
                    else [s1]
                )
            case ExtendedPlaquetteType.BOTTOM_LEFT_TRIANGLE:
                data_corners = (
                    [tl] if ExtendedPlaquetteDrawer._is_first(self._position) else [bl, br]
                )
                schedules = (
                    [s1] if ExtendedPlaquetteDrawer._is_first(self._position) else [s1, s2]
                )
            case ExtendedPlaquetteType.TOP_RIGHT_TRIANGLE:
                data_corners = (
                    [tl, tr] if ExtendedPlaquetteDrawer._is_first(self._position) else [br]
                )
                schedules = (
                    [s1, s2]
                    if ExtendedPlaquetteDrawer._is_first(self._position)
                    else [s2]
                )
            case ExtendedPlaquetteType.RIGHT_HALF_RECTANGLE:
                data_corners = (
                    [tr] if ExtendedPlaquetteDrawer._is_first(self._position) else [br]
                )
                schedules = [s2]
            case ExtendedPlaquetteType.LEFT_HALF_RECTANGLE:
                data_corners = (
                    [tl] if ExtendedPlaquetteDrawer._is_first(self._position) else [bl]
                )
                schedules = [s1]

        for corner, schedule in zip(data_corners, schedules):
            if not schedule:
                continue
            text_position = lerp(
                SVGPlaquetteDrawer._CENTER_COORDINATE, corner, configuration.text_lerp_coefficient
            )
            interaction_order_texts.append(
                svg.Text(
                    x=text_position.real,
                    y=text_position.imag,
                    fill="black",
                    font_size=0.1,
                    text_anchor="middle",
                    dominant_baseline="central",
                    text=str(schedule),
                )
            )
        return interaction_order_texts

    def get_hook_error_line(
        self,
        configuration: DrawerConfiguration = DrawerConfiguration(),
    ) -> svg.Line | None:
        """Return a SVG line showing the direction of the hook error.

        Args:
            configuration: drawing configuration.

        Returns:
            A SVG line showing the direction of the hook error, or ``None`` if
            there is no hook error.

        """
        # No hook error for these.
        if self._plaquette_type in [
            ExtendedPlaquetteType.RIGHT_HALF_RECTANGLE,
            ExtendedPlaquetteType.LEFT_HALF_RECTANGLE,
        ]:
            return None
        if (
            (
                self._plaquette_type == ExtendedPlaquetteType.BOTTOM_RIGHT_TRIANGLE
                and ExtendedPlaquetteDrawer._is_first(self._position)
            )
            or (
                self._plaquette_type == ExtendedPlaquetteType.TOP_LEFT_TRIANGLE
                and not ExtendedPlaquetteDrawer._is_first(self._position)
            )
            or (
                self._plaquette_type == ExtendedPlaquetteType.BOTTOM_LEFT_TRIANGLE
                and ExtendedPlaquetteDrawer._is_first(self._position)
            )
            or (
                self._plaquette_type == ExtendedPlaquetteType.TOP_RIGHT_TRIANGLE
                and not ExtendedPlaquetteDrawer._is_first(self._position)
            )
        ):
            return None

        if (
            self._plaquette_type == ExtendedPlaquetteType.BULK
            and ExtendedPlaquetteDrawer._is_first(self._position)
        ):
            return None

        tl, tr, bl, br = SVGPlaquetteDrawer._CORNERS
        if self._position in (
            ExtendedPlaquettePosition.LEFT,
            ExtendedPlaquettePosition.RIGHT,
        ):
            tl, tr, bl, br = (
                ExtendedPlaquetteDrawer._transform_point(self._position, tl),
                ExtendedPlaquetteDrawer._transform_point(self._position, tr),
                ExtendedPlaquetteDrawer._transform_point(self._position, bl),
                ExtendedPlaquetteDrawer._transform_point(self._position, br),
            )
        c1, c2 = (
            (tl, tr)
            if ExtendedPlaquetteDrawer._is_first(self._position)
            else (bl, br)
        )
        f = configuration.hook_error_line_lerp_coefficient
        a = lerp(SVGPlaquetteDrawer._CENTER_COORDINATE, c1, f)
        b = lerp(SVGPlaquetteDrawer._CENTER_COORDINATE, c2, f)
        return svg.Line(
            x1=a.real,
            x2=b.real,
            y1=a.imag,
            y2=b.imag,
            stroke=configuration.stroke_color,
            stroke_width=configuration.stroke_width,
        )

    def get_data_qubit_reset_measurements_layers(
        self,
        configuration: DrawerConfiguration = DrawerConfiguration(),
    ) -> svg.G:
        """Return a SVG layer containing a representation of data-qubit resets/measurements.

        Args:
            configuration: drawing configuration.

        Returns:
            a SVG element containing all the reset or measurements on the
            plaquette drawn by ``self``.

        """
        if self._reset is None and self._measurement is None:
            return svg.G()
        if self._reset is not None and self._measurement is not None:
            raise TQECDrawingError("Cannot draw both reset and measurement.")
        basis = self._reset if self._reset is not None else cast(Basis, self._measurement)
        fill = SVGPlaquetteDrawer.get_colour(basis)
        match self._plaquette_type:
            case ExtendedPlaquetteType.BULK:
                places = (
                    [PlaquetteCorner.TOP_LEFT, PlaquetteCorner.TOP_RIGHT]
                    if ExtendedPlaquetteDrawer._is_first(self._position)
                    else [PlaquetteCorner.BOTTOM_LEFT, PlaquetteCorner.BOTTOM_RIGHT]
                )
            case ExtendedPlaquetteType.BOTTOM_RIGHT_TRIANGLE:
                places = (
                    [PlaquetteCorner.TOP_RIGHT]
                    if ExtendedPlaquetteDrawer._is_first(self._position)
                    else [PlaquetteCorner.BOTTOM_LEFT, PlaquetteCorner.BOTTOM_RIGHT]
                )
            case ExtendedPlaquetteType.TOP_LEFT_TRIANGLE:
                places = (
                    [PlaquetteCorner.TOP_LEFT, PlaquetteCorner.TOP_RIGHT]
                    if ExtendedPlaquetteDrawer._is_first(self._position)
                    else [PlaquetteCorner.BOTTOM_LEFT]
                )
            case ExtendedPlaquetteType.BOTTOM_LEFT_TRIANGLE:
                places = (
                    [PlaquetteCorner.TOP_LEFT]
                    if ExtendedPlaquetteDrawer._is_first(self._position)
                    else [PlaquetteCorner.BOTTOM_LEFT, PlaquetteCorner.BOTTOM_RIGHT]
                )
            case ExtendedPlaquetteType.TOP_RIGHT_TRIANGLE:
                places = (
                    [PlaquetteCorner.TOP_LEFT, PlaquetteCorner.TOP_RIGHT]
                    if ExtendedPlaquetteDrawer._is_first(self._position)
                    else [PlaquetteCorner.BOTTOM_RIGHT]
                )
            case ExtendedPlaquetteType.RIGHT_HALF_RECTANGLE:
                places = (
                    [PlaquetteCorner.TOP_RIGHT]
                    if ExtendedPlaquetteDrawer._is_first(self._position)
                    else [PlaquetteCorner.BOTTOM_RIGHT]
                )
            case ExtendedPlaquetteType.LEFT_HALF_RECTANGLE:
                places = (
                    [PlaquetteCorner.TOP_LEFT]
                    if ExtendedPlaquetteDrawer._is_first(self._position)
                    else [PlaquetteCorner.BOTTOM_LEFT]
                )
        reset_measurement_svgs: list[svg.Element] = []
        for place in places:
            corner_coords = self.get_corner_coordinates(place)
            if self._position in (
                ExtendedPlaquettePosition.LEFT,
                ExtendedPlaquettePosition.RIGHT,
            ):
                corner_coords = ExtendedPlaquetteDrawer._transform_point(
                    self._position, corner_coords
                )
            reset_measurement_svgs.append(
                svg.G(
                    elements=[
                        self.get_reset_shape(place, fill, configuration)
                        if self._reset is not None
                        else self.get_measurement_shape(place, fill, configuration)
                    ],
                    transform=[svg.Translate(x=corner_coords.real, y=corner_coords.imag)],
                )
            )
        return svg.G(elements=reset_measurement_svgs)
