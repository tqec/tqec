from __future__ import annotations

from enum import Enum, auto
from typing import cast

import svg
from typing_extensions import override

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

    def flip(self) -> ExtendedPlaquettePosition:
        """Return the opposite direction."""
        match self:
            case ExtendedPlaquettePosition.UP:
                return ExtendedPlaquettePosition.DOWN
            case ExtendedPlaquettePosition.DOWN:
                return ExtendedPlaquettePosition.UP
            # wildcard entry added as it was flagged by ty
            case _:
                raise ValueError("Unexpected input provided.")


class ExtendedPlaquetteType(Enum):
    BULK = auto()
    LEFT_WITH_ARM = auto()
    LEFT_WITHOUT_ARM = auto()
    RIGHT_WITH_ARM = auto()
    RIGHT_WITHOUT_ARM = auto()


class ExtendedPlaquetteDrawer(SVGPlaquetteDrawer):
    def __init__(
        self,
        plaquette_type: ExtendedPlaquetteType,
        position: ExtendedPlaquettePosition,
        basis: Basis,
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
            schedule[0:2] if position == ExtendedPlaquettePosition.UP else schedule[2:4]
        )
        self._reset = reset
        self._measurement = measurement

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
        if plaquette_type == ExtendedPlaquetteType.LEFT_WITHOUT_ARM:
            tl, bl = (tl + tr) / 2, (bl + br) / 2
        elif plaquette_type == ExtendedPlaquetteType.RIGHT_WITHOUT_ARM:
            tr, br = (tl + tr) / 2, (bl + br) / 2

        up_stroke_color, down_stroke_color = (
            configuration.stroke_color,
            configuration.thin_stroke_color,
        )
        if position == ExtendedPlaquettePosition.DOWN:
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
        if position == ExtendedPlaquettePosition.DOWN:
            return svg.G()
        _, tr, bl, br = SVGPlaquetteDrawer._CORNERS
        bl += 1j
        br += 1j
        center = 0.5 + 1j
        side_length = configuration.plaquette_overflow_lerp_coefficient

        vs = [bl, bl - side_length * 1j, tr - side_length, tr, br]
        if plaquette_type == ExtendedPlaquetteType.RIGHT_WITH_ARM:
            vs = [2 * center - v for v in vs]
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
        fill = SVGPlaquetteDrawer.get_colour(self._basis)
        match self._plaquette_type:
            case (
                ExtendedPlaquetteType.BULK
                | ExtendedPlaquetteType.LEFT_WITHOUT_ARM
                | ExtendedPlaquetteType.RIGHT_WITHOUT_ARM
            ):
                return ExtendedPlaquetteDrawer._get_extended_plaquette_square_shape(
                    self._position, self._plaquette_type, fill, configuration
                )
            case ExtendedPlaquetteType.LEFT_WITH_ARM | ExtendedPlaquetteType.RIGHT_WITH_ARM:
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
        s1, s2 = self._schedule
        data_corners: list[complex]
        schedules: list[int]
        match self._plaquette_type:
            case ExtendedPlaquetteType.BULK:
                data_corners = (
                    [tl, tr] if self._position == ExtendedPlaquettePosition.UP else [bl, br]
                )
                schedules = [s1, s2]
            case ExtendedPlaquetteType.LEFT_WITH_ARM:
                data_corners = [tr] if self._position == ExtendedPlaquettePosition.UP else [bl, br]
                schedules = [s2] if self._position == ExtendedPlaquettePosition.UP else [s1, s2]
            case ExtendedPlaquetteType.RIGHT_WITH_ARM:
                data_corners = [tl, tr] if self._position == ExtendedPlaquettePosition.UP else [bl]
                schedules = [s1, s2] if self._position == ExtendedPlaquettePosition.UP else [s1]
            case ExtendedPlaquetteType.LEFT_WITHOUT_ARM:
                data_corners = [tr] if self._position == ExtendedPlaquettePosition.UP else [br]
                schedules = [s2]
            case ExtendedPlaquetteType.RIGHT_WITHOUT_ARM:
                data_corners = [tl] if self._position == ExtendedPlaquettePosition.UP else [bl]
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
            ExtendedPlaquetteType.LEFT_WITHOUT_ARM,
            ExtendedPlaquetteType.RIGHT_WITHOUT_ARM,
        ]:
            return None
        if (
            self._plaquette_type == ExtendedPlaquetteType.LEFT_WITH_ARM
            and self._position == ExtendedPlaquettePosition.UP
        ) or (
            self._plaquette_type == ExtendedPlaquetteType.RIGHT_WITH_ARM
            and self._position == ExtendedPlaquettePosition.DOWN
        ):
            return None

        if (
            self._plaquette_type == ExtendedPlaquetteType.BULK
            and self._position == ExtendedPlaquettePosition.UP
        ):
            return None

        tl, tr, bl, br = SVGPlaquetteDrawer._CORNERS
        c1, c2 = (tl, tr) if self._position == ExtendedPlaquettePosition.UP else (bl, br)
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
                    if self._position == ExtendedPlaquettePosition.UP
                    else [PlaquetteCorner.BOTTOM_LEFT, PlaquetteCorner.BOTTOM_RIGHT]
                )
            case ExtendedPlaquetteType.LEFT_WITH_ARM:
                places = (
                    [PlaquetteCorner.TOP_RIGHT]
                    if self._position == ExtendedPlaquettePosition.UP
                    else [PlaquetteCorner.BOTTOM_LEFT, PlaquetteCorner.BOTTOM_RIGHT]
                )
            case ExtendedPlaquetteType.RIGHT_WITH_ARM:
                places = (
                    [PlaquetteCorner.TOP_LEFT, PlaquetteCorner.TOP_RIGHT]
                    if self._position == ExtendedPlaquettePosition.UP
                    else [PlaquetteCorner.BOTTOM_LEFT]
                )
            case ExtendedPlaquetteType.LEFT_WITHOUT_ARM:
                places = (
                    [PlaquetteCorner.TOP_RIGHT]
                    if self._position == ExtendedPlaquettePosition.UP
                    else [PlaquetteCorner.BOTTOM_RIGHT]
                )
            case ExtendedPlaquetteType.RIGHT_WITHOUT_ARM:
                places = (
                    [PlaquetteCorner.TOP_LEFT]
                    if self._position == ExtendedPlaquettePosition.UP
                    else [PlaquetteCorner.BOTTOM_LEFT]
                )
        reset_measurement_svgs: list[svg.Element] = []
        for place in places:
            corner_coords = self.get_corner_coordinates(place)
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
