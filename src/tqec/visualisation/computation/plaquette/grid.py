from typing import Sequence

import svg

from tqec.utils.frozendefaultdict import FrozenDefaultDict
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
    configuration: PlaquetteDrawerConfiguration = PlaquetteDrawerConfiguration(),
) -> svg.Element:
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
    return svg.G(elements=drawing_lines)


def plaquette_grid_svg_viewer(
    grid: Sequence[Sequence[int]],
    drawers: FrozenDefaultDict[int, SVGPlaquetteDrawer],
    width: float | None = None,
    height: float | None = None,
    show_interaction_order: bool = True,
    show_hook_errors: bool = True,
    show_data_qubit_reset_measurements: bool = True,
) -> svg.SVG:
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
            )
        ],
    )
