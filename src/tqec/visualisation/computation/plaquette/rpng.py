from collections.abc import Iterable
from typing import cast

import svg
from typing_extensions import override

from tqec.plaquette.enums import PlaquetteOrientation
from tqec.plaquette.rpng.rpng import RPNG, ExtendedBasis, PauliBasis, RPNGDescription
from tqec.visualisation.computation.plaquette.base import PlaquetteCorner, SVGPlaquetteDrawer, lerp
from tqec.visualisation.configuration import DrawerConfiguration
from tqec.visualisation.exception import TQECDrawingError


def _get_bounding_box(coords: Iterable[complex]) -> tuple[complex, complex]:
    min_x = min(c.real for c in coords)
    max_x = max(c.real for c in coords)
    min_y = min(c.imag for c in coords)
    max_y = max(c.imag for c in coords)
    return complex(min_x, min_y), complex(max_x, max_y)


class RPNGPlaquetteDrawer(SVGPlaquetteDrawer):
    def __init__(self, description: RPNGDescription) -> None:
        """SVG plaquette drawer for RPNG descriptions.

        Args:
            description: :class:`RPNGDescription` that should be drawn by this drawer.

        """
        super().__init__()
        self._description = description
        self._center = RPNGPlaquetteDrawer._CENTER_COORDINATE
        bases = {rpng.p for rpng in description.corners if rpng.p is not None}
        uniform_basis: PauliBasis | None = next(iter(bases)) if len(bases) == 1 else None
        self._uniform_colour = (
            SVGPlaquetteDrawer.get_colour(uniform_basis) if uniform_basis is not None else None
        )
        self._sorted_corner_indices: list[int] = []
        self._corners: list[complex] = []
        self._corners_enum: list[PlaquetteCorner] = []
        self._rpngs: list[RPNG] = []
        for i, (coords, corner_enum, rpng) in enumerate(
            zip(
                RPNGPlaquetteDrawer._CORNERS,
                RPNGPlaquetteDrawer._CORNERS_ENUM,
                description.corners,
            )
        ):
            if rpng.is_null:
                continue
            self._sorted_corner_indices.append(i)
            self._corners.append(coords)
            self._corners_enum.append(corner_enum)
            self._rpngs.append(rpng)
        self._uuid: str = "_".join(
            [
                str(self._description.ancilla),
                *[str(corner) for corner in description.corners],
            ]
        )

    @override
    def draw(
        self,
        id: str,
        show_interaction_order: bool = True,
        show_hook_errors: bool = True,
        show_data_qubit_reset_measurements: bool = True,
        configuration: DrawerConfiguration = DrawerConfiguration(),
    ) -> svg.Element:
        # Return an empty SVG element if there are no corners.
        if len(self._corners) == 0:
            return svg.G(id=id, elements=[])
        # Build iteratively the different layers that we need to represent the
        # plaquette.
        shape_path = self.get_plaquette_shape_path(configuration)
        layers: list[svg.Element] = []
        # If the plaquette has a uniform color, the shape include that color with
        # its "fill" attribute and so we do not need to clip. If that is not the
        # case, the filling colours will be added with get_fill_layer, but it is
        # simpler for the implementation to clip.
        if self._uniform_colour is None:
            layers.append(svg.ClipPath(id=self._uuid, elements=[shape_path]))
            layers.extend(self.get_fill_layers(configuration))
        # Second layer: the strokes (with filling if self._uniform_colour is set)
        layers.append(shape_path)
        if show_data_qubit_reset_measurements:
            layers.append(self.get_data_qubit_reset_measurements_layers(configuration))
        if show_hook_errors:
            if (line := self.get_hook_error_line(configuration)) is not None:
                layers.append(line)
        # Third layer: the text.
        if show_interaction_order:
            layers.extend(self.get_interaction_order_text(configuration))
        return svg.G(id=id, elements=layers)

    def get_plaquette_shape_path(
        self,
        configuration: DrawerConfiguration = DrawerConfiguration(),
    ) -> svg.Element:
        """Return the plaquette shape, filled iff it measures in a uniform Pauli basis.

        This method returns the plaquette shape as an SVG path. It might also fill this shape if
        ``self`` represents a plaquette measuring its qubits in the same Pauli basis, else without
        fill at all.

        Args:
            configuration: drawing configuration.

        Returns:
            The plaquette shape. It is filled with the appropriate colour if the
            stabilizer measured in ``self`` measures in the same Pauli basis for
            all the qubits (e.g. ``XXXX``). If different bases are present (e.g.
            ``ZXXZ``), the returned SVG element does not contain any fill, and
            the colours should be added later.

        """
        fill = "none" if self._uniform_colour is None else self._uniform_colour
        match len(self._corners):
            case 2:
                # Find the plaquette orientation
                orientation: PlaquetteOrientation
                match self._sorted_corner_indices:
                    case [0, 1]:
                        orientation = PlaquetteOrientation.DOWN
                    case [0, 2]:
                        orientation = PlaquetteOrientation.RIGHT
                    case [1, 3]:
                        orientation = PlaquetteOrientation.LEFT
                    case [2, 3]:
                        orientation = PlaquetteOrientation.UP
                    case _:
                        raise TQECDrawingError(
                            "Could not find the orientation of a plaquette containing the "
                            f"corner indices {self._sorted_corner_indices}."
                        )
                # Return the corresponding shape
                return self.get_half_circle_shape(orientation, fill, configuration)

            case 3:
                # Find the plaquette placement
                place: PlaquetteCorner
                match self._sorted_corner_indices:
                    case [1, 2, 3]:
                        place = PlaquetteCorner.TOP_LEFT
                    case [0, 2, 3]:
                        place = PlaquetteCorner.TOP_RIGHT
                    case [0, 1, 3]:
                        place = PlaquetteCorner.BOTTOM_LEFT
                    case [0, 1, 2]:
                        place = PlaquetteCorner.BOTTOM_RIGHT
                    case _:
                        raise TQECDrawingError(
                            "Could not find the placement of a plaquette containing the "
                            f"corner indices {self._sorted_corner_indices}."
                        )
                return self.get_triangle_shape(place, fill, configuration)
            case 4:
                return self.get_square_shape(fill, configuration)
            case num:
                raise TQECDrawingError(
                    f"Got a plaquette with {num} corners. Only 2, 3 or 4 corners are supported."
                )

    def get_fill_layers(
        self,
        configuration: DrawerConfiguration = DrawerConfiguration(),
    ) -> list[svg.Element]:
        """Return one SVG element per non-empty corners filling each corresponding quarter.

        This method should only be called if the plaquette drawn by self measures data-qubits in a
        non-uniform Pauli basis (e.g. ZXXZ).

        Note:
            The returned filled rectangles are clipped with the clipPath with
            id ``self._uuid`` that should be created before following the
            plaquette shape path.

        Args:
            configuration: drawing configuration.

        Returns:
            A list of ``len(self._corners)`` SVG elements, each filling a
            quarter of the square plaquette and clipping to the clipPath with
            id ``self._uuid``.

        """
        # Draw one rectangle for each corner
        fill_layer: list[svg.Element] = []
        for corner, rpng in zip(self._corners, self._rpngs):
            tl, br = _get_bounding_box([self._center, corner])
            basis = rpng.p
            fill = configuration.mixed_basis_color if basis is None else self.get_colour(basis)
            fill_layer.append(
                svg.Rect(
                    x=tl.real,
                    y=tl.imag,
                    width=(br.real - tl.real),
                    height=(br.imag - tl.imag),
                    fill=fill,
                    stroke=None,
                    clip_path=f"url(#{self._uuid})",
                )
            )
        return fill_layer

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
        for corner, rpng in zip(self._corners, self._rpngs):
            if rpng.n is None:
                continue
            text_position = lerp(self._center, corner, configuration.text_lerp_coefficient)
            interaction_order_texts.append(
                svg.Text(
                    x=text_position.real,
                    y=text_position.imag,
                    fill="black",
                    font_size=0.1,
                    text_anchor="middle",
                    dominant_baseline="central",
                    text=str(rpng.n),
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
        if len(self._corners) != 4:
            return None
        sorted_rpngs = sorted([(rpng.n, i) for i, rpng in enumerate(self._rpngs)])
        f = configuration.hook_error_line_lerp_coefficient
        a = lerp(self._center, self._corners[sorted_rpngs[-1][1]], f)
        b = lerp(self._center, self._corners[sorted_rpngs[-2][1]], f)
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
        reset_measurement_elements: list[svg.Element] = []
        for corner, place, rpng in zip(self._corners, self._corners_enum, self._rpngs):
            r, m = rpng.r, rpng.g
            r_is_basis = r is not None
            m_is_basis = m is not None and m != ExtendedBasis.H
            if not r_is_basis and not m_is_basis:
                continue
            if r_is_basis and m_is_basis:
                raise TQECDrawingError(
                    "Found an RPNG with both reset and measurement. That is not "
                    "supported in the drawer."
                )
            assert r_is_basis ^ m_is_basis
            fill = self.get_colour(r if r is not None else cast(ExtendedBasis, m))
            shape = (
                self.get_reset_shape(place, fill, configuration)
                if r_is_basis
                else self.get_measurement_shape(place, fill, configuration)
            )
            reset_measurement_elements.append(
                svg.G(
                    elements=[shape],
                    transform=[svg.Translate(corner.real, corner.imag)],
                )
            )
        return svg.G(elements=reset_measurement_elements)
