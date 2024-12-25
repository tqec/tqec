"""Visualize the RPNG plaquettes as SVG."""

from collections.abc import Callable, Iterable
import math
from typing import Literal, cast

from tqec.exceptions import TQECException
from tqec.interop.color import RGBA, TQECColor
from tqec.plaquette.rpng import RPNG, ExtendedBasisEnum, RPNGDescription


def rpng_svg_viewer(
    rpng_object: RPNGDescription | list[list[RPNGDescription]],
    canvas_height: int = 500,
    plaquette_indices: list[list[int]] | None = None,
    opacity: float = 1.0,
    show_rg_fields: bool = True,
    show_plaquette_indices: bool = False,
    show_interaction_order: bool = True,
    show_hook_error: Callable[[RPNGDescription], bool] = lambda _: False,
) -> str:
    """Visualize the RPNG plaquettes as SVG.

    Args:
        rpng_object: The RPNG object to visualize. It can be a single RPNGDescription or
            a 2D list of RPNGDescriptions.
        canvas_height: The height of the canvas in pixels.
        plaquette_indices: The indices of the plaquettes. It must be provided when
            ``show_plaquette_indices`` is True. It must have the same dimensions as
            ``rpng_object``.
        opacity: The opacity of the plaquettes.
        show_rg_fields: Whether to show the R/G fields on the data qubits. If True, the R
            field is shown as a small rectangle at the position of the data qubit, whose color
            corresponds to the basis. The G field is shown as a small circle at the position
            of the data qubit, whose color corresponds to the basis.
        show_plaquette_indices: Whether to show the indices of the plaquettes. If True, the
            indices are shown at the center of the plaquettes.
        show_interaction_order: Whether to show the interaction order of the plaquettes. If
            True, the interaction order is shown at each corner of the plaquette.
        show_hook_error: A predicate function that takes an RPNGDescription and returns True
            if the plaquette should be highlighted with the hook error. The hook error is
            shown as a black line along the hook edge.

    Returns:
        The SVG string representing the RPNG object.
    """
    if show_plaquette_indices:
        if isinstance(rpng_object, RPNGDescription):
            raise TQECException(
                "``rpng_object`` must be a 2D list when ``show_plaquette_indices`` is True."
            )
        if plaquette_indices is None:
            raise TQECException(
                "Plaquette indices must be provided when ``show_plaquette_indices`` is True."
            )
        if not len(rpng_object) == len(plaquette_indices) and all(
            len(row) == len(indices)
            for row, indices in zip(rpng_object, plaquette_indices)
        ):
            raise TQECException(
                "The dimensions of ``rpng_object`` and ``plaquette_indices`` must match."
            )

    data_qubits: set[complex] = set()
    plaquettes: dict[complex, dict[complex, RPNG]] = {}
    hook_error: dict[complex, tuple[complex, complex]] = {}
    merged_r: dict[complex, ExtendedBasisEnum | None] = {}
    merged_g: dict[complex, ExtendedBasisEnum | None] = {}
    indices: dict[complex, int] = {}

    if isinstance(rpng_object, RPNGDescription):
        rpng_object = [[rpng_object]]
    # Iterate over the RPNG object to populate the qubits and merge the R/G fields
    for r, row in enumerate(rpng_object):
        for c, description in enumerate(row):
            center = complex(2 * c + 1, 2 * r + 1)
            plaquette: dict[complex, RPNG] = {}
            for delta, rpng in zip(
                [-1 - 1j, 1 - 1j, -1 + 1j, 1 + 1j], description.corners
            ):
                # filter out the "----" null plaquettes
                if rpng.is_null:
                    continue
                dq = center + delta
                data_qubits.add(dq)
                plaquette[dq] = rpng
                # Merge the R/G fields on each data qubits
                merged_r[dq] = _merge_rg_field(merged_r.get(dq), rpng.r)
                merged_g[dq] = _merge_rg_field(merged_g.get(dq), rpng.g)
            if plaquette:
                plaquettes[center] = plaquette
                if show_plaquette_indices:
                    assert plaquette_indices is not None
                    indices[center] = plaquette_indices[r][c]
                if show_hook_error(description):
                    sorted_corners = sorted(
                        [p for p, rpng in plaquette.items() if rpng.n is not None],
                        key=lambda p: cast(int, plaquette[p].n),
                    )
                    if len(sorted_corners) < 2:
                        continue
                    hook_error[center] = (sorted_corners[-2], sorted_corners[-1])

    # Calculate the bounding box and scale the qubits to fit the canvas
    min_c, max_c = _get_bounding_box(data_qubits)
    min_c -= 2 + 2j
    max_c += 2 + 2j
    box_width = max_c.real - min_c.real
    box_height = max_c.imag - min_c.imag
    scale_factor = canvas_height / box_height
    canvas_width = int(math.ceil(canvas_height * (box_width / box_height)))

    def q2p(q: complex) -> complex:
        return scale_factor * (q - min_c)

    # Collect the SVG lines
    lines = [
        f"""<svg viewBox="0 0 {canvas_width} {canvas_height}" xmlns="http://www.w3.org/2000/svg">"""
    ]
    fill_layer: list[str] = []
    stroke_layer: list[str] = []
    rg_layer: list[str] = []
    text_layer: list[str] = []

    # Draw the plaquettes
    clip_path_id = 0
    for center, plaquette in plaquettes.items():
        _draw_plaquette(
            fill_layer,
            stroke_layer,
            text_layer,
            center,
            plaquette,
            clip_path_id,
            q2p,
            opacity,
            scale_factor,
            show_interaction_order,
            hook_error.get(center),
        )
        clip_path_id += 1
        if show_plaquette_indices:
            index = indices[center]
            _draw_plaquette_index(
                stroke_layer, text_layer, center, index, q2p, scale_factor
            )

    # Draw the R/G fields on the data qubits
    if show_rg_fields:
        _draw_rg_fields(rg_layer, merged_r, merged_g, q2p, scale_factor)

    lines.extend(fill_layer)
    lines.extend(stroke_layer)
    lines.extend(rg_layer)
    lines.extend(text_layer)
    lines.append("</svg>")
    return "\n".join(lines)


def _merge_rg_field(
    value1: ExtendedBasisEnum | None, value2: ExtendedBasisEnum | None
) -> ExtendedBasisEnum | None:
    if value1 is None:
        return value2
    if value2 is None:
        return value1
    if value1 == value2:
        return value1
    raise TQECException(f"Conflicting R/G values: {value1} vs {value2}")


def _get_bounding_box(coords: Iterable[complex]) -> tuple[complex, complex]:
    min_x = min(c.real for c in coords)
    max_x = max(c.real for c in coords)
    min_y = min(c.imag for c in coords)
    max_y = max(c.imag for c in coords)
    return complex(min_x, min_y), complex(max_x, max_y)


def _draw_plaquette(
    fill_layer: list[str],
    stroke_layer: list[str],
    text_layer: list[str],
    center: complex,
    plaquette: dict[complex, RPNG],
    clip_path_id: int,
    q2p: Callable[[complex], complex],
    opacity: float,
    scale_factor: float,
    show_interaction_order: bool,
    hook_error: tuple[complex, complex] | None,
) -> None:
    path_directions = _svg_path_directions(center, plaquette, q2p)
    # Add clip path
    fill_layer.append(f"""<clipPath id="clipPath{clip_path_id}">""")
    fill_layer.append(f"""    <path d="{path_directions}"/>""")
    fill_layer.append("""</clipPath>""")
    # Fill the plaquette with color corresponding to the bases
    for dq, rpng in plaquette.items():
        top_left, bot_right = _get_bounding_box([center, dq])
        a = q2p(top_left)
        b = q2p(bot_right)
        diag = b - a
        if rpng.p is not None:
            rgba = TQECColor(rpng.p.value.upper()).rgba
            fill = rgba.to_hex()
            opacity *= rgba.a
        else:
            fill = "gray"
        # Fill each corner by a rectangle
        fill_layer.append(
            f'<rect clip-path="url(#clipPath{clip_path_id})" '
            f'x="{a.real}" y="{a.imag}" '
            f'width="{abs(diag.real)}" height="{abs(diag.imag)}" '
            f'fill="{fill}" '
            f'opacity="{opacity}" '
            'stroke="none"/>'
        )
        # Add the interaction order texts
        if show_interaction_order:
            if rpng.n is None:
                continue
            f = 0.7
            text_pos = q2p(f * dq + (1 - f) * center)
            text_layer.append(
                "<text "
                f'x="{text_pos.real}" '
                f'y="{text_pos.imag}" '
                f'fill="black" '
                f'font-size="{0.4 * scale_factor}" '
                'text-anchor="middle" '
                'dominant-baseline="middle">'
                f"{rpng.n}</text>"
            )
    # stroke around the polygon
    stroke_layer.append(
        f'<path d="{path_directions}" '
        f'fill="none" stroke="black" stroke-width="{0.05 * scale_factor}"/>'
    )
    # Add the hook error
    if hook_error is not None:
        p1, p2 = q2p(hook_error[0]), q2p(hook_error[1])
        p1 += (q2p(center) - p1) * 0.008 * scale_factor
        p2 += (q2p(center) - p2) * 0.008 * scale_factor
        stroke_layer.append(
            f'<line x1="{p1.real}" y1="{p1.imag}" '
            f'x2="{p2.real}" y2="{p2.imag}" '
            f'stroke="black" stroke-width="{0.06 * scale_factor}"/>'
        )


def _svg_path_directions(
    center: complex,
    plaquette: dict[complex, RPNG],
    q2p: Callable[[complex], complex],
) -> str:
    match len(plaquette):
        case 2:
            return _svg_path_directions_2_corners(center, plaquette, q2p)
        case 3:
            return _svg_path_directions_3_corners(center, plaquette, q2p)
        case 4:
            return _svg_path_directions_4_corners(center, plaquette, q2p)
        case _:
            raise TQECException("Invalid number of corners.")


def _svg_path_directions_2_corners(
    center: complex,
    plaquette: dict[complex, RPNG],
    q2p: Callable[[complex], complex],
) -> str:
    a, b = plaquette.keys()
    da = a - center
    db = b - center
    angle = math.atan2(da.imag, da.real) - math.atan2(db.imag, db.real)
    angle %= math.pi * 2
    if angle < math.pi:
        a, b = b, a
    pa = q2p(a)

    def transform_dif(d: complex) -> complex:
        return q2p(d) - q2p(0)

    pba = transform_dif(b - a)
    return (
        f"M {_complex_str(pa)} "
        f"a 1,1 0 0,0 {_complex_str(pba)} "
        f"L {_complex_str(pa)}"
    )


def _svg_path_directions_3_corners(
    center: complex,
    plaquette: dict[complex, RPNG],
    q2p: Callable[[complex], complex],
) -> str:
    antinode = [c for c in plaquette if (2 * center - c) not in plaquette][0]
    missing_node = 2 * center - antinode
    shoulders = [c + (missing_node - c) * 0.2 for c in plaquette if c != antinode]
    sorted_corners = sorted(
        list(plaquette.keys()) + shoulders,
        key=lambda p2: math.atan2(p2.imag - center.imag, p2.real - center.real),
    )
    directions = f"M {_complex_str(q2p(sorted_corners[-1]))} "
    for c in sorted_corners:
        directions += f"L {_complex_str(q2p(c))} "
    return directions


def _svg_path_directions_4_corners(
    center: complex,
    plaquette: dict[complex, RPNG],
    q2p: Callable[[complex], complex],
) -> str:
    sorted_corners = sorted(
        list(plaquette.keys()),
        key=lambda p2: math.atan2(p2.imag - center.imag, p2.real - center.real),
    )
    directions = f"M {_complex_str(q2p(sorted_corners[-1]))} "
    for c in sorted_corners:
        directions += f"L {_complex_str(q2p(c))} "
    return directions


def _draw_plaquette_index(
    stroke_layer: list[str],
    text_layer: list[str],
    center: complex,
    index: int,
    q2p: Callable[[complex], complex],
    scale_factor: float,
) -> None:
    center_pos = q2p(center)
    stroke_layer.append(
        f'<circle cx="{center_pos.real}" cy="{center_pos.imag}" r="{0.35 * scale_factor}" '
        f'fill="{RGBA(240, 240, 240, 1.0).to_hex()}" '
        'stroke="black" '
        f'stroke-width="2"/>'
    )
    text_layer.append(
        "<text "
        f'x="{center_pos.real}" '
        f'y="{center_pos.imag}" '
        f'fill="black" '
        f'font-size="{0.4 * scale_factor}" '
        'text-anchor="middle" '
        'dominant-baseline="middle">'
        f"{index}</text>"
    )


def _draw_rg_fields(
    rg_lines: list[str],
    rs: dict[complex, ExtendedBasisEnum | None],
    gs: dict[complex, ExtendedBasisEnum | None],
    q2p: Callable[[complex], complex],
    scale_factor: float,
) -> None:
    _draw_rg_field(rg_lines, rs, q2p, scale_factor, 0.17, "rect")
    _draw_rg_field(rg_lines, gs, q2p, scale_factor, 0.12, "circle")


def _draw_rg_field(
    rg_lines: list[str],
    mapping: dict[complex, ExtendedBasisEnum | None],
    q2p: Callable[[complex], complex],
    scale_factor: float,
    radius: float,
    shape: Literal["circle", "rect"],
) -> None:
    for q, b in mapping.items():
        if b is None:
            continue
        p = q2p(q)
        r = radius * scale_factor
        color = TQECColor(b.value.upper()).rgba.to_hex()
        if shape == "circle":
            rg_lines.append(
                f'<circle cx="{p.real}" cy="{p.imag}" r="{r}" '
                f'fill="{color}" stroke="black" stroke-width="{0.03 * scale_factor}"/>'
            )
        else:
            rg_lines.append(
                f'<rect x="{p.real - r}" y="{p.imag - r}" width="{2 * r}" height="{2 * r}" '
                f'fill="{color}" stroke="black" stroke-width="{0.03 * scale_factor}"/>'
            )


def _complex_str(c: complex) -> str:
    return f"{c.real},{c.imag}"
