from typing import Sequence

import stim
import svg

from tqec.utils.frozendefaultdict import FrozenDefaultDict
from tqec.visualisation.computation.errors import get_errors_svg
from tqec.visualisation.computation.plaquette.base import (
    PlaquetteDrawerConfiguration,
    SVGPlaquetteDrawer,
)


def plaquette_grid_to_svg(
    grid: Sequence[Sequence[int]],
    drawers: FrozenDefaultDict[int, SVGPlaquetteDrawer],
    width: float,
    height: float,
    show_interaction_order: bool = True,
    show_hook_errors: bool = True,
    show_data_qubit_reset_measurements: bool = True,
    borders: tuple[float, float] = (0, 0),
    errors: Sequence[stim.ExplainedError] = tuple(),
    configuration: PlaquetteDrawerConfiguration = PlaquetteDrawerConfiguration(),
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
            width (resp. height) of the drawing area will be ``width - borders[0]`` (resp.
            ``height - borders[1]``).
        errors: a collection of errors that should be drawn on the resulting SVG.
        configuration: drawing configuration.

    Returns:
        a SVG element representing the provided plaquette grid.
    """
    if not grid:
        return svg.G()
    N, M = len(grid[0]), len(grid)
    xborder, yborder = borders
    pw, ph = (width - 2 * xborder) / N, (height - 2 * yborder) / M
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
        drawing_lines.append(get_errors_svg(errors, pw, ph, size=(pw + ph) / 10))
    return svg.G(elements=drawing_lines)


def plaquette_grid_svg_viewer(
    grid: Sequence[Sequence[int]],
    drawers: FrozenDefaultDict[int, SVGPlaquetteDrawer],
    width: float | None = None,
    height: float | None = None,
    show_interaction_order: bool = True,
    show_hook_errors: bool = True,
    show_data_qubit_reset_measurements: bool = True,
    borders: tuple[float, float] = (0, 0),
    errors: Sequence[stim.ExplainedError] = tuple(),
    configuration: PlaquetteDrawerConfiguration = PlaquetteDrawerConfiguration(),
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
        height = len(grid) * (width / len(grid[0]))
    return svg.SVG(
        viewBox=svg.ViewBoxSpec(0, 0, width, height),
        elements=[
            plaquette_grid_to_svg(
                grid,
                drawers,
                width,
                height,
                show_interaction_order,
                show_hook_errors,
                show_data_qubit_reset_measurements,
                borders,
                errors,
                configuration,
            )
        ],
    )
