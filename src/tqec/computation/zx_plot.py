"""Defines functions to plot ZX graphs and correlation surfaces on 3D axes with
``matplotlib``."""

from dataclasses import astuple
from typing import cast

from matplotlib.figure import Figure
import numpy
import numpy.typing as npt
from mpl_toolkits.mplot3d.axes3d import Axes3D

from tqec.computation.correlation import CorrelationSurface
from tqec.interop.color import RGBA, TQECColor
from tqec.position import Position3D
from tqec.computation.zx_graph import ZXKind, ZXGraph, ZXNode

NODE_COLOR: dict[ZXKind, RGBA] = {
    ZXKind.X: TQECColor.X.rgba,
    ZXKind.Y: TQECColor.Y.rgba,
    ZXKind.Z: TQECColor.Z.rgba,
}


def _positions_array(*positions: Position3D) -> npt.NDArray[numpy.int_]:
    return numpy.array([astuple(p) for p in positions]).T


def draw_zx_graph_on(
    graph: ZXGraph,
    ax: Axes3D,
    *,
    node_size: int = 400,
    hadamard_size: int = 200,
    edge_width: int = 1,
    annotate_ports: bool = True,
) -> None:
    """Draw the :py:class:`~tqec.computation.zx_graph.ZXGraph` on the provided
    axes.

    Args:
        graph: The ZX graph to draw.
        ax: a 3-dimensional ax to draw on.
        node_size: The size of the node. Default is 400.
        hadamard_size: The size of the Hadamard transition. Default is 200.
        edge_width: The width of the edge. Default is 1.
        annotate_ports: Whether to annotate the ports if they are present. Default is True.
    """
    vis_nodes = [n for n in graph.nodes if not n.is_port]
    vis_nodes_array = _positions_array(*[n.position for n in vis_nodes])
    if vis_nodes_array.size > 0:
        ax.scatter(
            *vis_nodes_array,
            s=node_size,
            c=[NODE_COLOR[n.kind].as_floats() for n in vis_nodes],
            alpha=1.0,
            edgecolors="black",
        )
    if graph.ports and annotate_ports:
        for label, port in graph.ports.items():
            ax.text(
                *port.as_tuple(),
                s=label,
                color="black",
                fontsize=15,
                ha="center",
                va="center",
            )

    for edge in graph.edges:
        pos_array = _positions_array(edge.u.position, edge.v.position)
        ax.plot(
            *pos_array,
            color="tab:gray",
            linewidth=edge_width,
        )
        if edge.has_hadamard:
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

    plot_radius = 0.5 * max(
        abs(limits[1] - limits[0]) for limits in [x_limits, y_limits, z_limits]
    )

    ax.set_xlim3d(
        [numpy.mean(x_limits) - plot_radius, numpy.mean(x_limits) + plot_radius]
    )
    ax.set_ylim3d(
        [numpy.mean(y_limits) - plot_radius, numpy.mean(y_limits) + plot_radius]
    )
    ax.set_zlim3d(
        [numpy.mean(z_limits) - plot_radius, numpy.mean(z_limits) + plot_radius]
    )


def draw_correlation_surface_on(
    correlation_surface: CorrelationSurface,
    ax: Axes3D,
    correlation_edge_width: int = 3,
) -> None:
    """Draw the correlation surface on the provided axes.

    Args:
        correlation_surface: The correlation surface to draw.
        ax: The 3-dimensional ax to draw on.
        correlation_edge_width: The width of the correlation edges. Default is 3.
    """
    span = correlation_surface.span
    if isinstance(span, ZXNode):
        return
    correlation_types = correlation_surface.node_correlation_types
    processed_edges: set[tuple[Position3D, Position3D]] = set()
    for edge in span:
        positions = (edge.u.position, edge.v.position)
        if positions in processed_edges:
            continue
        types = tuple(correlation_types[p] for p in positions)
        pos_array = _positions_array(*positions)
        if not edge.has_hadamard or all(t == ZXKind.Y for t in types):
            if any(t == ZXKind.Z for t in types):
                correlation = ZXKind.Z
            elif any(t == ZXKind.X for t in types):
                correlation = ZXKind.X
            else:
                correlation = ZXKind.Y
            ax.plot(
                *pos_array,
                color=NODE_COLOR[correlation].as_floats(),
                linewidth=correlation_edge_width,
            )
        else:
            hadamard_position = numpy.mean(pos_array, axis=1)
            for i in [0, 1]:
                if types[i] != ZXKind.Y:
                    correlation = types[i]
                else:
                    correlation = types[1 - i].with_zx_flipped()
                ax.plot(
                    *numpy.hstack(
                        [
                            hadamard_position.reshape(3, 1),
                            _positions_array(positions[i]),
                        ]
                    ),
                    color=NODE_COLOR[correlation].as_floats(),
                    linewidth=correlation_edge_width,
                )
        processed_edges.add(positions)


def plot_zx_graph(
    graph: ZXGraph,
    *,
    figsize: tuple[float, float] = (5, 6),
    title: str | None = None,
    node_size: int = 400,
    hadamard_size: int = 200,
    edge_width: int = 1,
    annotate_ports: bool = True,
) -> tuple[Figure, Axes3D]:
    """Plot the :py:class:`~tqec.computation.zx_graph.ZXGraph` using
    matplotlib.

    Args:
        graph: The ZX graph to plot.
        figsize: The figure size. Default is (5, 6).
        title: The title of the plot. Default to the name of the graph.
        node_size: The size of the node in the plot. Default is 400.
        hadamard_size: The size of the Hadamard square in the plot. Default is 200.
        edge_width: The width of the edge in the plot. Default is 1.
        annotate_ports: Whether to annotate the ports if they are present. Default is True.

    Returns:
        A tuple of the figure and the axes.
    """
    import matplotlib.pyplot as plt

    fig = plt.figure(figsize=figsize)
    ax = cast(Axes3D, fig.add_subplot(111, projection="3d"))

    draw_zx_graph_on(
        graph,
        ax,
        node_size=node_size,
        hadamard_size=hadamard_size,
        edge_width=edge_width,
        annotate_ports=annotate_ports,
    )

    ax.set_title(title or graph.name)
    fig.tight_layout()
    return fig, ax
