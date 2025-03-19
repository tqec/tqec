"""NetworkX / Matplotlib functions to create a quick visualisation of a 3D graph.
A computationally inexpensive way of checking progress in any 2D PyZX graph -> TQEC journey.

"""

import numpy as np
import networkx as nx
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker


def create_3d_graph(nodes, edges):
    """
    Creates a NetworkX graph from 3D nodes and edges.

    Args:
        - nodes: A list of tuples containing, each:
            -- node id,
            -- (x,y,z) node's position,
            -- node type.
        - edges: A list of tuples containing, each, an edge connecting nodes (by node id)

    Returns:
        - A NetworkX Graph object.
    """

    graph = nx.Graph()

    # Add nodes
    for node_id, pos, t in nodes:
        graph.add_node(node_id, pos=pos, type=t)

    # Add edges
    for src, tgt, t in edges:
        graph.add_edge(src, tgt, type=t)

    return graph


def visualize_3d_graph(
    graph,
    node_colour_map={
        "X": "red",
        "Y": "green",
        "Z": "blue",
        "H_BOX": "yellow",
        "BOUNDARY": "black",
    },
    edge_colour_map={"SIMPLE": "black", "HADAMARD": "lightblue"},
):
    """
    Visualizes a 3D NetworkX graph.

    Args:
        - graph: The NetworkX graph object.
        - node_colour_map: A map of colours for the nodes.
        - edge_colour_map: A map of colours for the edges.
    """

    pos = nx.get_node_attributes(graph, "pos")
    node_types = nx.get_node_attributes(graph, "type")
    node_colours = [node_colour_map[node_types[node]] for node in graph.nodes()]
    edge_types = nx.get_edge_attributes(graph, "type")

    fig = plt.figure()
    ax = fig.add_subplot(111, projection="3d")

    # Draw edges with colours
    for edge in graph.edges():
        x = [pos[edge[0]][0], pos[edge[1]][0]]
        y = [pos[edge[0]][1], pos[edge[1]][1]]
        z = [pos[edge[0]][2], pos[edge[1]][2]]

        edge_type = edge_types[edge]  # Get the edge type.
        edge_colour = edge_colour_map[edge_type]  # Get the edge colour.

        ax.plot(x, y, z, color=edge_colour)

    # Draw nodes with colours
    nodes = []
    for node, position in pos.items():
        ax.scatter(
            position[0],
            position[1],
            position[2],
            c=node_colours[list(graph.nodes()).index(node)],
            s=100,
        )
        ax.text(position[0], position[1], position[2], s=str(node), fontsize=12)
        nodes.append((position[0], position[1], position[2]))

    # Enforce integer ticks on the axes
    ax.xaxis.set_major_locator(ticker.MaxNLocator(integer=True))
    ax.yaxis.set_major_locator(ticker.MaxNLocator(integer=True))

    # Handle the Z-axis specifically
    if np.all([node[2] == 0 for node in nodes]):
        ax.set_zticks([0])  # Force Z-axis to show only 0
    else:
        ax.zaxis.set_major_locator(
            ticker.MaxNLocator(integer=True)
        )  # if there are other z values, use integer ticks.

    # Axes adjustments
    ax.set_xlabel("X")
    ax.set_ylabel("Y")
    ax.set_zlabel("Z")
    ax.view_init(elev=-50, azim=-25, roll=-69)

    plt.show()
