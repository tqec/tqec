"""Defines some helper functions to plot into insets."""

# required for "3d" projection even though not explicitly used
import sinter
from matplotlib.axes import Axes
from matplotlib.ticker import ScalarFormatter
from mpl_toolkits.mplot3d.axes3d import Axes3D

from tqec.computation.correlation import CorrelationSurface
from tqec.interop.pyzx.plot import (
    draw_correlation_surface_on,
    draw_positioned_zx_graph_on,
)
from tqec.interop.pyzx.positioned import PositionedZX


def add_inset_axes3d(
    ax_target: Axes, bounds: tuple[float, float, float, float]
) -> Axes3D:
    """Wrapper around `fig.add_axes` to achieve `ax.inset_axes` functionality
    that works also for insetting 3D plot on 2D ax/figures."""
    ax = ax_target.inset_axes(bounds, projection="3d")
    assert isinstance(ax, Axes3D)
    return ax


def plot_observable_as_inset(
    ax_target: Axes,
    zx_graph: PositionedZX,
    observable: CorrelationSurface,
    bounds: tuple[float, float, float, float] = (0.55, 0.0, 0.45, 0.45),
) -> None:
    """Plot the provided observable as an inset in the provided ax.

    Args:
        ax_target: the ax to insert an inset in to plot the correlation surface.
        bounds: (x0, y0, width, height) where (x0, y0) is the position of the
            lower-left corner of the inset. All coordinates are normalized to
            [0, 1] meaning that an input of (0, 0, 1, 1) will span the whole
            `ax_target`.
        zx_graph: ZX graph used.
        observable: correlation surface over the provided `zx_graph` to
            draw.
    """
    inset_ax = add_inset_axes3d(ax_target, bounds)
    inset_ax.set_axis_off()
    draw_positioned_zx_graph_on(zx_graph, inset_ax, node_size=50)
    draw_correlation_surface_on(observable, zx_graph, inset_ax)
    inset_ax.set_facecolor((0.0, 0.0, 0.0, 0.0))


def plot_threshold_as_inset(
    ax_target: Axes,
    stats: list[sinter.TaskStats],
    zoom_bounds: tuple[float, float, float, float],
    inset_bounds: tuple[float, float, float, float] = (0.53, 0.45, 0.4, 0.4),
) -> None:
    # Creating the inset
    inset_ax = ax_target.inset_axes(
        inset_bounds,
        xlim=(zoom_bounds[0], zoom_bounds[2]),
        ylim=(zoom_bounds[1], zoom_bounds[3]),
    )
    # Configuring the inset to look nice
    # 1. This is a loglog plot.
    inset_ax.loglog()
    # 2. Ticks management.
    # 2.1. Because we expect the logical error-rate at the threshold to be high
    #      we can format the Y-axis ticks using that knowledge.
    inset_ax.invert_yaxis()
    inset_ax.yaxis.set_label_position("right")
    inset_ax.yaxis.tick_right()
    inset_ax.yaxis.set_minor_formatter(ScalarFormatter())
    inset_ax.yaxis.set_major_formatter(ScalarFormatter())
    inset_ax.tick_params(axis="y", which="minor", labelsize=7)
    inset_ax.tick_params(axis="y", which="major", labelsize=7)
    # 2.2. The physical error-rate at which the threshold is located should be
    #      quite small (below 10**-2 from experiments), so keep the scientific
    #      notation here.
    inset_ax.tick_params(axis="x", which="major", labelsize=7)
    inset_ax.tick_params(axis="x", which="minor", labelsize=7)
    # 3. Make the grid apparent.
    inset_ax.grid(which="both", axis="both")
    # 4. Annotate the inset correctly.
    _, (lower_left, upper_left, lower_right, upper_right) = (
        ax_target.indicate_inset_zoom(inset_ax, edgecolor="black", alpha=0.8)
    )  # type: ignore
    lower_left.set_visible(True)
    upper_right.set_visible(True)
    lower_right.set_visible(False)
    upper_left.set_visible(False)

    # Plotting the data
    sinter.plot_error_rate(
        ax=inset_ax,
        stats=stats,
        x_func=lambda stat: stat.json_metadata["p"],
        group_func=lambda stat: stat.json_metadata["d"],
        plot_args_func=lambda index, group_key, group_stats: {"markersize": 3},
    )
