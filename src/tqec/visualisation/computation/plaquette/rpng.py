import math
from typing import Iterable
import svg
from tqec.interop.color import TQECColor
from tqec.plaquette.rpng.rpng import RPNG, PauliBasis, RPNGDescription
from tqec.visualisation.computation.plaquette.base import (
    SVGLayers,
    SVGPlaquetteDrawer,
    svg_path_enclosing_points,
)
from typing_extensions import override

from tqec.visualisation.exception import TQECDrawingException


def close_to(c1: complex, c2: complex, atol: float = 1e-8) -> bool:
    return abs(c1 - c2) < atol


def _get_bounding_box(coords: Iterable[complex]) -> tuple[complex, complex]:
    min_x = min(c.real for c in coords)
    max_x = max(c.real for c in coords)
    min_y = min(c.imag for c in coords)
    max_y = max(c.imag for c in coords)
    return complex(min_x, min_y), complex(max_x, max_y)


def _get_2_corners_shape(center: complex, corners: list[complex]) -> svg.Path:
    assert len(corners) == 2
    # Due to the behaviour of the "A" command in SVG path specification, we
    # need to sort a and b such that a is "before" b when drawing the
    # half-circle clock-wise.
    a, b = corners
    da = a - center
    db = b - center
    angle = math.atan2(da.imag, da.real) - math.atan2(db.imag, db.real)
    angle %= math.pi * 2
    if angle < math.pi:
        a, b = b, a

    return svg.Path(
        d=[
            svg.M(a.real, a.imag),
            svg.Arc(0.5, 0.5, 0, True, False, b.real, b.imag),
            svg.Z(),
        ],
        fill="none",
        stroke="black",
        stroke_width=0.01,
    )


def _get_3_corners_shape(center: complex, corners: list[complex]) -> svg.Path:
    assert len(corners) == 3
    # Find the corner that is not in the shape
    missing_corner: complex = next(
        c
        for c in RPNGPlaquetteDrawer._CORNERS
        if all(not close_to(c, present_corner) for present_corner in corners)
    )
    # Its opposite corner should not participate in the "shoulders"
    anti_corner = 2 * center - missing_corner
    shoulders = [
        c + (missing_corner - c) * 0.2 for c in corners if not close_to(c, anti_corner)
    ]
    return svg_path_enclosing_points(corners + shoulders)


def _get_4_corners_shape(center: complex, corners: list[complex]) -> svg.Path:
    assert len(corners) == 4
    return svg_path_enclosing_points(corners)


def get_plaquette_shape_path(center: complex, corners: list[complex]) -> svg.Path:
    match len(corners):
        case 2:
            return _get_2_corners_shape(center, corners)
        case 3:
            return _get_3_corners_shape(center, corners)
        case 4:
            return _get_4_corners_shape(center, corners)
        case _:
            raise TQECDrawingException(
                f"Got a plaquette with {len(corners)} corners. Only 2, 3 "
                "or 4 corners are supported."
            )


def get_fill_layer(
    center: complex,
    corners: list[complex],
    rpngs: list[RPNG],
    uuid: str,
    uniform_basis: PauliBasis | None = None,
) -> list[svg.Element]:
    if uniform_basis is not None:
        top_left, bot_right = _get_bounding_box([center, *corners])
        return [
            svg.Rect(
                x=top_left.real,
                y=top_left.imag,
                width=(bot_right.real - top_left.real),
                height=(bot_right.imag - top_left.imag),
                fill=TQECColor(uniform_basis.value.upper()).rgba.to_hex(),
                stroke=None,
                clip_path=f"url(#{uuid})",
            )
        ]
    fill_layer: list[svg.Element] = []
    for corner, rpng in zip(corners, rpngs):
        top_left, bot_right = _get_bounding_box([center, corner])
        fill = (
            "gray" if rpng.p is None else TQECColor(rpng.p.value.upper()).rgba.to_hex()
        )
        fill_layer.append(
            svg.Rect(
                x=top_left.real,
                y=top_left.imag,
                width=(bot_right.real - top_left.real),
                height=(bot_right.imag - top_left.imag),
                fill=fill,
                stroke=None,
                clip_path=f"url(#{uuid})",
            )
        )
    return fill_layer


def get_interaction_order_text(
    center: complex, corners: list[complex], rpngs: list[RPNG]
) -> list[svg.Text]:
    interaction_order_texts: list[svg.Text] = []
    for corner, rpng in zip(corners, rpngs):
        if rpng.n is None:
            continue
        f = 0.8
        text_position = f * corner + (1 - f) * center
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
    center: complex, corners: list[complex], rpngs: list[RPNG]
) -> svg.Line | None:
    if len(corners) != 4:
        return None
    sorted_rpngs = sorted([(rpng.n, i) for i, rpng in enumerate(rpngs)])
    f = 0.9
    a = f * corners[sorted_rpngs[-1][1]] + (1 - f) * center
    b = f * corners[sorted_rpngs[-2][1]] + (1 - f) * center
    return svg.Line(
        x1=a.real, x2=b.real, y1=a.imag, y2=b.imag, stroke="black", stroke_width=0.01
    )


class RPNGPlaquetteDrawer(SVGPlaquetteDrawer):
    def __init__(self, description: RPNGDescription) -> None:
        super().__init__()
        self._description = description
        bases = {rpng.p for rpng in description.corners if rpng.p is not None}
        self._uniform_basis: PauliBasis | None = (
            next(iter(bases)) if len(bases) == 1 else None
        )

    def scaled_points(
        self, width: float, height: float
    ) -> tuple[complex, list[complex], list[RPNG]]:
        scaled_corners: list[complex] = []
        rpngs: list[RPNG] = []
        for coords, corner in zip(
            RPNGPlaquetteDrawer._CORNERS, self._description.corners
        ):
            if not corner.is_null:
                scaled_corners.append(
                    RPNGPlaquetteDrawer.scale_point(coords, width, height)
                )
                rpngs.append(corner)
        scaled_center = RPNGPlaquetteDrawer.scale_point(
            RPNGPlaquetteDrawer._CENTER_COORDINATE, width, height
        )
        return scaled_center, scaled_corners, rpngs

    @override
    def draw(
        self,
        width: float,
        height: float,
        uuid: str,
        show_interaction_order: bool = True,
        show_hook_errors: bool = False,
    ) -> SVGLayers:
        center, corners, rpngs = self.scaled_points(width, height)
        if len(corners) == 0:
            return SVGLayers()
        # Set the default values that will always be needed whatever the provided
        # parameters.
        shape_path = get_plaquette_shape_path(center, corners)
        fill_layer: list[svg.Element] = [
            svg.ClipPath(id=uuid, elements=[shape_path])
        ] + get_fill_layer(center, corners, rpngs, uuid, self._uniform_basis)
        draw_layer: list[svg.Element] = [shape_path]
        text_layer: list[svg.Element] = []
        # Add things if needed.
        if show_interaction_order:
            text_layer.extend(get_interaction_order_text(center, corners, rpngs))
        if show_hook_errors:
            line = get_hook_error_line(center, corners, rpngs)
            if line is not None:
                draw_layer.append(line)
        return SVGLayers(fill=fill_layer, draw=draw_layer, text=text_layer)
