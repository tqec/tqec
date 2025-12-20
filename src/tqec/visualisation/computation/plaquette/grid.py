from collections.abc import Sequence

import stim
import svg

from tqec.circuit.qubit import GridQubit
from tqec.compile.observables.builder import Observable
from tqec.utils.frozendefaultdict import FrozenDefaultDict
from tqec.visualisation.computation.errors import get_errors_svg
from tqec.visualisation.computation.observable import get_observable_svg
from tqec.visualisation.computation.plaquette.base import SVGPlaquetteDrawer
from tqec.visualisation.configuration import DrawerConfiguration


def plaquette_grid_to_svg(
    grid: Sequence[Sequence[int]],
    drawers: FrozenDefaultDict[int, SVGPlaquetteDrawer],
    top_left_qubit: GridQubit,
    width: float,
    height: float,
    show_interaction_order: bool = True,
    show_hook_errors: bool = True,
    show_data_qubit_reset_measurements: bool = True,
    borders: tuple[float, float] = (0, 0),
    errors: Sequence[stim.ExplainedError] = tuple(),
    configuration: DrawerConfiguration = DrawerConfiguration(),
    observable: Observable | None = None,
) -> svg.Element:
    """Draws the provided plaquette grid and returns it as an SVG.

    The returned SVG is composed of 2 main parts:

    1. a first part that defines pieces of SVG that will be repeated across the drawing.
    2. a second part that uses the defined pieces by translating them to their expected place.

    Args:
        grid: a 2-dimensional array of integer corresponding to plaquettes indices that can be
            used to index the provided ``drawers``.
        drawers: a default dictionary containing a SVG drawer for each of the plaquette indices
            provided in ``grid``. If an index is not present, the default value is used.
        top_left_qubit: coordinates of the qubit at the very top-left of the
            visualisation canva. Used to correctly offset qubit values from the
            provided ``errors``.
        width: width of the resulting SVG.
        height: height of the resulting SVG.
        show_interaction_order: if ``True``, numbers representing the timestep(s) at which each
            corner qubit is touched by a 2-qubit gates are added on the corners of each plqauette.
            Else, nothing is added.
        show_hook_errors: if ``True``, a dark line is added between the 2 qubits that may be
            vulnerable to a hook error. Else, nothing is added.
        show_data_qubit_reset_measurements: if ``True``, small squares/quarter circles will be added
            to each data qubit when they are reset/measured.
        borders: additional blank space reserved for border at the left/right and bottom/top. The
            width (resp. height) of the drawing area will be ``width - 2 * borders[0]`` (resp.
            ``height - 2 * borders[1]``).
        errors: a collection of errors that should be drawn on the resulting SVG.
        configuration: drawing configuration.
        observable: an observable that is being visualised. If provided, the SVG will be
            annotated with the observable information.

    Returns:
        a SVG element representing the provided plaquette grid.

    """
    if not grid:
        return svg.G()
    n, m = len(grid[0]), len(grid)
    xborder, yborder = borders
    pw, ph = (width - 2 * xborder) / n, (height - 2 * yborder) / m
    # Start by constructing an index of drawings that will be re-used.
    element_id_template = "plaquette_drawing_{}"
    drawing_lines: list[svg.Element] = [
        svg.Defs(
            elements=[
                drawer.draw(
                    element_id_template.format(i),
                    show_interaction_order,
                    show_hook_errors,
                    show_data_qubit_reset_measurements,
                    configuration,
                )
                for i, drawer in drawers.items()
            ]
            + (
                []
                if drawers.default_value is None
                else [
                    drawers.default_value.draw(
                        element_id_template.format("default"),
                        show_interaction_order,
                        show_hook_errors,
                        show_data_qubit_reset_measurements,
                        configuration,
                    )
                ]
            )
        )
    ]
    for i, line in enumerate(grid):
        y = ph * (i + yborder)
        for j, value in enumerate(line):
            x = pw * (j + xborder)
            if value == 0:
                continue
            key = str(value) if value in drawers else "default"
            template_id = element_id_template.format(key)
            drawing_lines.append(svg.Use(x=x, y=y, href=f"#{template_id}"))
    if errors:
        drawing_lines.append(get_errors_svg(errors, top_left_qubit, pw, ph, size=(pw + ph) / 12))
    if observable is not None:
        drawing_lines.append(get_observable_svg(observable, top_left_qubit, pw, ph))
    return svg.G(elements=drawing_lines)


def plaquette_grid_svg_viewer(
    grid: Sequence[Sequence[int]],
    drawers: FrozenDefaultDict[int, SVGPlaquetteDrawer],
    top_left_used_qubit: GridQubit,
    view_box_top_left_qubit: GridQubit | None = None,
    view_box_bottom_right_qubit: GridQubit | None = None,
    width: float | None = None,
    height: float | None = None,
    show_interaction_order: bool = True,
    show_hook_errors: bool = True,
    show_data_qubit_reset_measurements: bool = True,
    borders: tuple[float, float] = (0, 0),
    errors: Sequence[stim.ExplainedError] = tuple(),
    configuration: DrawerConfiguration = DrawerConfiguration(),
    observable: Observable | None = None,
) -> svg.SVG:
    """Draws the provided plaquette grid and returns it as an SVG.

    The returned SVG is composed of 2 main parts:

    1. a first part that defines pieces of SVG that will be repeated across the drawing.
    2. a second part that uses the defined pieces by translating them to their expected place.

    Args:
        grid: a 2-dimensional array of integer corresponding to plaquettes indices that can be
            used to index the provided ``drawers``.
        drawers: a default dictionary containing a SVG drawer for each of the plaquette indices
            provided in ``grid``. If an index is not present, the default value is used.
        top_left_used_qubit: coordinates of the top-left most qubit being used by the provided
            ``grid``. This is used to correctly offset qubit values from the provided ``errors``.
        view_box_top_left_qubit: top-left qubit of the drawing frame. Can be used to change the view
            box of the returned drawing. Contrary to ``width``, this parameter does **not** change
            the size of the plaquettes that are drawn, but changes the view box.
        view_box_bottom_right_qubit: bottom-right qubit of the drawing frame. Can be used to change
            the view box of the returned drawing. Contrary to ``height``, this parameter does
            **not** change the size of the plaquettes that are drawn, but changes the view box.
        width: width of the resulting SVG. If ``None``, defaults to ``len(grid[0])``.
        height: height of the resulting SVG. If ``None``, defaults to ``len(grid)``.
        show_interaction_order: if ``True``, numbers representing the timestep(s) at which each
            corner qubit is touched by a 2-qubit gates are added on the corners of each plqauette.
            Else, nothing is added.
        show_hook_errors: if ``True``, a dark line is added between the 2 qubits that may be
            vulnerable to a hook error. Else, nothing is added.
        show_data_qubit_reset_measurements: if ``True``, small squares/quarter circles will be added
            to each data qubit when they are reset/measured.
        borders: additional blank space reserved for border at the left/right and bottom/top. The
            width (resp. height) of the drawing area will be ``width - borders[0]`` (resp.
            ``height - borders[1]``).
        errors: a collection of errors that should be drawn on the resulting SVG.
        configuration: drawing configuration.
        observable: an observable that is being visualised. If provided, the SVG will be
            annotated with the observable information.

    Returns:
        a ``<svg>`` element that can be directly written to a ``.svg`` file and representing the
        provided plaquette grid.

    """
    if width is None and height is None:
        height, width = len(grid), len(grid[0])
    elif width is None:
        assert height is not None  # For type checkers
        width = len(grid[0]) * (height / len(grid))
    elif height is None:
        assert width is not None  # For type checkers
        height = len(grid) * (width / len(grid[0]))

    assert width is not None and height is not None

    # By default, if either the top-left or top-right qubits is not provided, we stick to the
    # [0, 0] x [width, height] viewbox.
    viewbox = svg.ViewBoxSpec(0, 0, width, height)
    if view_box_top_left_qubit is not None and view_box_bottom_right_qubit is not None:
        # Compute viewbox bounds top-left [x1, y1] and bottom-right [x2, y2] knowing that by
        # convention we have ``top_left_used_qubit`` at the coordinate ``(0, 0)``.
        width_between_qubits = width / (2 * len(grid[0]))
        height_between_qubits = height / (2 * len(grid))
        x1 = (view_box_top_left_qubit.x - top_left_used_qubit.x) * width_between_qubits
        x2 = (view_box_bottom_right_qubit.x - view_box_top_left_qubit.x) * width_between_qubits
        y1 = (view_box_top_left_qubit.y - top_left_used_qubit.y) * height_between_qubits
        y2 = (view_box_bottom_right_qubit.y - view_box_top_left_qubit.y) * height_between_qubits
        viewbox = svg.ViewBoxSpec(x1, y1, x2, y2)

    return svg.SVG(
        viewBox=viewbox,
        elements=[
            plaquette_grid_to_svg(
                grid,
                drawers,
                top_left_used_qubit,
                width,
                height,
                show_interaction_order,
                show_hook_errors,
                show_data_qubit_reset_measurements,
                borders,
                errors,
                configuration,
                observable,
            )
        ],
    )
