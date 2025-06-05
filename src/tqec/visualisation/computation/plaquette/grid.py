from typing import Sequence

import svg

from tqec.utils.frozendefaultdict import FrozenDefaultDict
from tqec.visualisation.computation.plaquette.base import SVGPlaquetteDrawer


def plaquette_grid_to_svg(
    grid: Sequence[Sequence[int]],
    drawers: FrozenDefaultDict[int, SVGPlaquetteDrawer | None],
    width: float,
    height: float,
    show_interaction_order: bool = True,
    show_hook_errors: bool = False,
    borders: tuple[float, float] = (0, 0),
) -> svg.Element:
    if not grid:
        return svg.G()
    N, M = len(grid[0]), len(grid)
    xborder, yborder = borders
    pw, ph = (width - 2 * xborder) / N, (height - 2 * yborder) / M
    drawing_lines: list[svg.Element] = []
    for i, line in enumerate(grid):
        y = ph * (i + yborder)
        for j, value in enumerate(line):
            x = pw * (j + xborder)
            drawer = drawers[value]
            if drawer is None:
                continue
            layers = drawer.draw(
                pw, ph, f"{i}_{j}", show_interaction_order, show_hook_errors
            )
            drawing_lines.append(
                svg.G(transform=[svg.Translate(x, y)], elements=layers.flatten())
            )
    return svg.G(elements=drawing_lines)


def plaquette_grid_svg_viewer(
    grid: Sequence[Sequence[int]],
    drawers: FrozenDefaultDict[int, SVGPlaquetteDrawer | None],
    width: float | None = None,
    height: float | None = None,
    show_interaction_order: bool = True,
    show_hook_errors: bool = True,
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
                grid, drawers, width, height, show_interaction_order, show_hook_errors
            )
        ],
    )
