"""Defines functions to plot positioned ZX graphs and correlation surfaces on 3D axes."""

from dataclasses import astuple

import matplotlib.pyplot as plt
import numpy
import numpy.typing as npt
from matplotlib.figure import Figure
from mpl_toolkits.mplot3d.axes3d import Axes3D
from pyzx import draw_3d
from pyzx.graph.graph_s import GraphS
from pyzx.pauliweb import PauliWeb

from tqec.computation.correlation import CorrelationSurface
from tqec.interop.color import RGBA, TQECColor
from tqec.interop.pyzx.positioned import PositionedZX
from tqec.interop.pyzx.utils import is_boundary, is_hardmard, is_s, is_z_no_phase
from tqec.utils.position import Position3D


def _node_color(g: GraphS, v: int) -> RGBA:  # pragma: no cover
    assert not is_boundary(g, v)
    if is_s(g, v):
        return TQECColor.Y.rgba
    if is_z_no_phase(g, v):
        return TQECColor.Z.rgba
    return TQECColor.X.rgba


def _positions_array(*positions: Position3D) -> npt.NDArray[numpy.int_]:  # pragma: no cover
    return numpy.array([astuple(p) for p in positions]).T


def draw_positioned_zx_graph_on(
    graph: PositionedZX,
    ax: Axes3D,
    *,
    node_size: int = 400,
    hadamard_size: int = 200,
    edge_width: int = 1,
) -> None:
    """Draw the :py:class:`~tqec.interop.pyzx.PositionedZX` on the provided axes.

    Args:
        graph: The positioned ZX graph to draw.
        ax: a 3-dimensional ax to draw on.
        node_size: The size of the node. Default is 400.
        hadamard_size: The size of the Hadamard transition. Default is 200.
        edge_width: The width of the edge. Default is 1.

    """
    g = graph.g
    pmap = graph.positions
    vis_nodes = [n for n in g.vertices() if not is_boundary(g, n)]
    vis_nodes_array = _positions_array(*[pmap[n] for n in vis_nodes])
    if vis_nodes_array.size > 0:
        ax.scatter(
            *vis_nodes_array,
            s=node_size,
            c=[_node_color(g, n).as_floats() for n in vis_nodes],
            alpha=1.0,
            edgecolors="black",
        )

    for edge in g.edges():
        pos_array = _positions_array(pmap[edge[0]], pmap[edge[1]])
        ax.plot(
            *pos_array,
            color="tab:gray",
            linewidth=edge_width,
        )
        if is_hardmard(g, edge):
            hadamard_position = numpy.mean(pos_array, axis=1)
            # use yellow square to indicate Hadamard transition
            ax.scatter(
                *hadamard_position,
                s=hadamard_size,
                c="yellow",
                alpha=1.0,
                edgecolors="black",
                marker="s",
            )
    ax.grid(False)
    for dim in (ax.xaxis, ax.yaxis, ax.zaxis):
        dim.set_ticks([])
    x_limits, y_limits, z_limits = ax.get_xlim3d(), ax.get_ylim3d(), ax.get_zlim3d()  # type: ignore

    plot_radius = 0.5 * max(abs(limits[1] - limits[0]) for limits in [x_limits, y_limits, z_limits])

    ax.set_xlim3d([numpy.mean(x_limits) - plot_radius, numpy.mean(x_limits) + plot_radius])
    ax.set_ylim3d([numpy.mean(y_limits) - plot_radius, numpy.mean(y_limits) + plot_radius])
    ax.set_zlim3d([numpy.mean(z_limits) - plot_radius, numpy.mean(z_limits) + plot_radius])


def draw_correlation_surface_on(
    correlation_surface: CorrelationSurface,
    graph: PositionedZX,
    ax: Axes3D,
    correlation_edge_width: int = 3,
) -> None:
    """Draw the correlation surface on the provided axes.

    Args:
        correlation_surface: The correlation surface to draw.
        graph: The positioned ZX graph to draw the correlation surface on.
        ax: The 3-dimensional ax to draw on.
        correlation_edge_width: The width of the correlation edges. Default is 3.

    """
    if correlation_surface.is_single_node:
        return

    pmap = graph.positions
    pauli_web = correlation_surface.to_pauli_web(graph.g)

    for edge, pauli in pauli_web.half_edges().items():
        up, vp = pmap[edge[0]], pmap[edge[1]]
        pos_array = _positions_array(up, vp)
        middle = numpy.mean(pos_array, axis=1).reshape(3, 1)
        start = _positions_array(up)
        ax.plot(
            *numpy.hstack([start, middle]),
            color=TQECColor(pauli).rgba.as_floats(),
            linewidth=correlation_edge_width,
        )


def plot_positioned_zx_graph(
    graph: PositionedZX,
    *,
    figsize: tuple[float, float] = (5, 6),
    title: str | None = None,
    node_size: int = 400,
    hadamard_size: int = 200,
    edge_width: int = 1,
) -> tuple[Figure, Axes3D]:
    """Plot the :py:class:`~tqec.interop.pyzx.positioned.PositionedZX` using matplotlib.

    Args:
        graph: The positioned ZX graph to plot.
        figsize: The figure size. Default is (5, 6).
        title: The title of the plot. Default to the name of the graph.
        node_size: The size of the node in the plot. Default is 400.
        hadamard_size: The size of the Hadamard square in the plot. Default is 200.
        edge_width: The width of the edge in the plot. Default is 1.

    Returns:
        A tuple of the figure and the axes.

    """
    fig = plt.figure(figsize=figsize)
    ax = fig.add_subplot(111, projection="3d")

    draw_positioned_zx_graph_on(
        graph,
        ax,
        node_size=node_size,
        hadamard_size=hadamard_size,
        edge_width=edge_width,
    )

    if title:
        ax.set_title(title)
    fig.tight_layout()
    return fig, ax


def pyzx_draw_positioned_zx_3d(
    g: PositionedZX,
    id_labels: bool = True,
    pauli_web: PauliWeb[int, tuple[int, int]] | None = None,
) -> None:
    """Draw the positioned ZX graph in 3D with ``pyzx.draw_3d``.

    Args:
        g: The positioned ZX graph to draw.
        id_labels: Whether to show the vertex id labels. Default is True.
        pauli_web: The Pauli web to draw. Default is None.

    """
    plot_g = g.g.clone()
    for v in plot_g.vertices():
        position = g.positions[v]
        plot_g.set_qubit(v, position.x)
        plot_g.set_row(v, position.y)
        plot_g.set_vdata(v, "z", position.z)
    draw_3d(plot_g, labels=id_labels, pauli_web=pauli_web)
