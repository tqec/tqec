"""Visualize the RPNG plaquettes as SVG."""

from collections.abc import Callable, Iterable
import math
from tqec.exceptions import TQECException
from tqec.interop.color import TQECColor
from tqec.plaquette.rpng import RPNG, ExtendedBasisEnum, RPNGDescription


def rpng_svg_viewer(
    rpng_object: RPNGDescription | list[list[RPNGDescription]],
    canvas_height: int = 500,
    plaquette_indices: list[list[int]] | None = None,
    opacity: float = 1.0,
    show_rg_fields: bool = True,
    show_plaquette_indices: bool = False,
) -> str:
    """Visualize the RPNG plaquettes as SVG.

    Args:
        rpng_object: The RPNG object to visualize.
        canvas_width: The width of the canvas. Defaults to 500.
    """
    data_qubits: set[complex] = set()
    plaquettes: dict[complex, dict[complex, RPNG]] = {}
    merged_r: dict[complex, ExtendedBasisEnum | None] = {}
    merged_g: dict[complex, ExtendedBasisEnum | None] = {}

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
            plaquettes[center] = plaquette

    # Calculate the bounding box and scale the qubits to fit the canvas
    min_c, max_c = _get_bounding_box(data_qubits)
    min_c -= 1 + 1j
    max_c += 1 + 1j
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
    text_layer: list[str] = []

    # Draw the plaquettes
    clip_path_id = 0
    for center, plaquette in plaquettes.items():
        _draw_plaquette(
            fill_layer, text_layer, center, plaquette, clip_path_id, q2p, opacity
        )
        clip_path_id += 1

    # Draw the R/G fields on the data qubits
    # _draw_rg_fields()

    lines.extend(fill_layer)
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
    text_layer: list[str],
    center: complex,
    plaquette: dict[complex, RPNG],
    clip_path_id: int,
    q2p: Callable[[complex], complex],
    opacity: float,
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
        fill_layer.append(
            f'<rect clip-path="url(#clipPath{clip_path_id})" '
            f'x="{a.real}" y="{a.imag}" '
            f'width="{abs(diag.real)}" height="{abs(diag.imag)}" '
            f'fill="{fill}" '
            f'opacity="{opacity}" '
            'stroke="none"/>'
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
            raise TQECException("Invalid number of corners")


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
    shoulders = [c + (missing_node - c) * 0.3 for c in plaquette if c != antinode]
    sorted_corners = sorted(
        list(plaquette.keys()) + shoulders,
        key=lambda p2: math.atan2(p2.imag - center.imag, p2.real - center.real),
    )
    directions = f"M {_complex_str((q2p(sorted_corners[-1])))} "
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
    directions = f"M {_complex_str((q2p(sorted_corners[-1])))} "
    for c in sorted_corners:
        directions += f"L {_complex_str(q2p(c))} "
    return directions


def _draw_rg_fields(
    out_lines: list[str],
    rs: dict[complex, ExtendedBasisEnum | None],
    gs: dict[complex, ExtendedBasisEnum | None],
    r_circle_radius: float,
    g_circle_radius: float,
) -> None:
    pass


def _complex_str(c: complex) -> str:
    return f"{c.real},{c.imag}"
