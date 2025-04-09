"""NetworkX / Matplotlib functions to create quick 3D visualisations of algorithmic progress into a blockgraph.
This file is an absolute mess at the moment. It works though.
"""

import numpy as np
import networkx as nx
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d.art3d import Poly3DCollection

# CONSTANTS
node_hex_map = {
    "xxz": ["#d7a4a1", "#d7a4a1", "#b9cdff"],
    "xzz": ["#d7a4a1", "#b9cdff", "#b9cdff"],
    "xzx": ["#d7a4a1", "#b9cdff", "#d7a4a1"],
    "zzx": ["#b9cdff", "#b9cdff", "#d7a4a1"],
    "zxx": ["#b9cdff", "#d7a4a1", "#d7a4a1"],
    "zxz": ["#b9cdff", "#d7a4a1", "#b9cdff"],
    "zxo": ["#b9cdff", "#d7a4a1", "gray"],
    "xzo": ["#d7a4a1", "#b9cdff", "gray"],
    "oxz": ["gray", "#d7a4a1", "#b9cdff"],
    "ozx": ["gray", "#b9cdff", "#d7a4a1"],
    "xoz": ["#d7a4a1", "gray", "#b9cdff"],
    "zox": ["#b9cdff", "gray", "#d7a4a1"],
    "zxoh": ["#b9cdff", "#d7a4a1", "gray"],
    "xzoh": ["#d7a4a1", "#b9cdff", "gray"],
    "oxzh": ["gray", "#d7a4a1", "#b9cdff"],
    "ozxh": ["gray", "#b9cdff", "#d7a4a1"],
    "xozh": ["#d7a4a1", "gray", "#b9cdff"],
    "zoxh": ["#b9cdff", "gray", "#d7a4a1"],
    "xxx": ["red", "red", "red"],
    "yyy": ["green", "green", "green"],
    "zzz": ["blue", "blue", "blue"],
}


# MISC FUNCTIONS
def get_vertices(x, y, z, size_x, size_y, size_z):
    """
    Calculates the coordinates of the eight vertices of a cuboid.

    Args:
        - x: x-coordinate of the center of the cuboid.
        - y: y-coordinate of the center of the cuboid.
        - z: z-coordinate of the center of the cuboid.
        - size_x: length of the cuboid along the x-axis.
        - size_y: length of the cuboid along the y-axis.
        - size_z: length of the cuboid along the z-axis.

    Returns:
        numpy.ndarray: A NumPy array of shape (8, 3) where each row represents the
                       (x, y, z) coordinates of a vertex of the cuboid. The order
                       of the vertices is consistent with how Matplotlib's
                       Poly3DCollection expects them for defining faces.
    """
    half_size_x = size_x / 2
    half_size_y = size_y / 2
    half_size_z = size_z / 2
    return np.array(
        [
            [x - half_size_x, y - half_size_y, z - half_size_z],
            [x + half_size_x, y - half_size_y, z - half_size_z],
            [x + half_size_x, y + half_size_y, z - half_size_z],
            [x - half_size_x, y + half_size_y, z - half_size_z],
            [x - half_size_x, y - half_size_y, z + half_size_z],
            [x + half_size_x, y - half_size_y, z + half_size_z],
            [x + half_size_x, y + half_size_y, z + half_size_z],
            [x - half_size_x, y + half_size_y, z + half_size_z],
        ]
    )


def get_faces(vertices):
    """
    Defines the faces of a cuboid based on its vertices.

    Args:
        - vertices: A NumPy array of shape (8, 3) containing the
                                  coordinates of the cuboid's vertices, as returned
                                  by the `get_vertices` function. The order of
                                  vertices is assumed to be consistent with that
                                  function's output.

    Returns:
        list: A list of lists, where each inner list represents a face of the
              cuboid and contains the coordinates of the four vertices that form
              that face. The order of faces typically corresponds to:
              [bottom, top, front, back, right, left].
    """

    return [
        [vertices[0], vertices[1], vertices[2], vertices[3]],
        [vertices[4], vertices[5], vertices[6], vertices[7]],
        [vertices[0], vertices[1], vertices[5], vertices[4]],
        [vertices[2], vertices[3], vertices[7], vertices[6]],
        [vertices[1], vertices[2], vertices[6], vertices[5]],
        [vertices[0], vertices[3], vertices[7], vertices[4]],
    ]


def render_hadamard(ax, node_info, node_hex_map, edge_col):
    """
    Renders a split and color-rotated 'h' node along its long axis.

    Args:
        - ax: The Matplotlib 3D subplot object.
        - node_info: A dictionary containing node information (position, type, size, long_axis_index).
        - node_hex_map: The map of (HEX) colours for the nodes.
        - edge_color: The color of the edges.
    """

    x, y, z = node_info["position"]
    size_x, size_y, size_z = node_info["size"]
    long_axis_index = node_info["long_axis_index"]
    node_type = node_info["node_type"]
    base_type = node_type.replace("h", "")
    size_outer = []
    size_center = []
    center_lower = []
    center_upper = []
    center_middle = []

    black_edge_color = "black"
    central_yellow_color = "#e0e317"

    # Correct for longer length of pipes along z-axis
    if size_z == 2.0:
        z -= 0.5

    # --- Calculate dimensions and centers of the three blocks ---
    if long_axis_index == 0:  # Split along x
        len_x_outer = 0.4 * size_x
        len_x_center = 0.2 * size_x
        size_outer = [len_x_outer, size_y, size_z]
        size_center = [len_x_center, size_y, size_z]
        center_lower = [x - 0.3 * size_x, y, z]
        center_upper = [x + 0.3 * size_x, y, z]
        center_middle = [x, y, z]
    elif long_axis_index == 1:  # Split along y
        len_y_outer = 0.4 * size_y
        len_y_center = 0.2 * size_y
        size_outer = [size_x, len_y_outer, size_z]
        size_center = [size_x, len_y_center, size_z]
        center_lower = [x, y - 0.3 * size_y, z]
        center_upper = [x, y + 0.3 * size_y, z]
        center_middle = [x, y, z]
    elif long_axis_index == 2:  # Split along z
        len_z_outer = 0.4 * size_z
        len_z_center = 0.2 * size_z
        size_outer = [size_x, size_y, len_z_outer]
        size_center = [size_x, size_y, len_z_center]
        center_lower = [x, y, z - 0.3 * size_z]
        center_upper = [x, y, z + 0.3 * size_z]
        center_middle = [x, y, z]
        if size_z == 2.0:
            center_lower[2] = z + 0.4
            center_middle[2] = z + 1.0
            center_upper[2] = z + 1.6

    # LOWER BLOCK RENDERING
    lx, ly, lz = center_lower
    lsx, lsy, lsz = size_outer
    lower_vertices = get_vertices(lx, ly, lz, lsx, lsy, lsz)
    lower_faces = get_faces(lower_vertices)
    lower_colors = node_hex_map.get(base_type, ["gray"] * 3)
    lower_face_colors = (
        [lower_colors[2]] * 2 + [lower_colors[1]] * 2 + [lower_colors[0]] * 2
    )
    lower_poly_collection = Poly3DCollection(
        lower_faces,
        facecolors=lower_face_colors,
        linewidths=1,
        edgecolors=black_edge_color,
        alpha=1,
    )
    ax.add_collection3d(lower_poly_collection)

    # CENTRAL (YELLOW) RING RENDERING
    mx, my, mz = center_middle
    msx, msy, msz = size_center
    middle_vertices = get_vertices(mx, my, mz, msx, msy, msz)
    middle_faces = get_faces(middle_vertices)
    middle_face_colors = [central_yellow_color] * 6
    middle_poly_collection = Poly3DCollection(
        middle_faces,
        facecolors=middle_face_colors,
        linewidths=1,
        edgecolors=black_edge_color,
        alpha=1,
    )
    ax.add_collection3d(middle_poly_collection)

    # UPPER BLOCK RENDERING
    ux, uy, uz = center_upper
    usx, usy, usz = size_outer
    upper_vertices = get_vertices(ux, uy, uz, usx, usy, usz)
    upper_faces = get_faces(upper_vertices)

    rotated_type = ""
    for char in base_type:
        if char == "x":
            rotated_type += "z"
        elif char == "z":
            rotated_type += "x"
        else:
            rotated_type += char

    upper_colors = node_hex_map.get(rotated_type, ["gray"] * 3)
    upper_face_colors = (
        [upper_colors[2]] * 2 + [upper_colors[1]] * 2 + [upper_colors[0]] * 2
    )
    upper_poly_collection = Poly3DCollection(
        upper_faces,
        facecolors=upper_face_colors,
        linewidths=1,
        edgecolors=black_edge_color,
        alpha=1,
    )
    ax.add_collection3d(upper_poly_collection)


def render_non_hadamard(
    ax,
    position,
    size,
    node_type,
    node_hex_map,
    alpha: float = 1,
    edge_color=None,
    line_width: float = 1,
):
    """
    Renders a regular (non-'h') node.

    Args:
        - ax: The Matplotlib 3D subplot object.
        - position: The (x, y, z) coordinates of the node.
        - size: The (size_x, size_y, size_z) of the node.
        - node_type: The type string of the node.
        - node_hex_map: The map of (HEX) colours for the nodes.
        - edge_color: The color of the edges.
    """

    x, y, z = position
    size_x, size_y, size_z = size

    vertices = get_vertices(x, y, z, size_x, size_y, size_z)
    faces = get_faces(vertices)

    # ADD COLORS AS PER MAP
    colors = node_hex_map.get(node_type, ["gray"] * 3)
    face_colors = [colors[2]] * 2 + [colors[1]] * 2 + [colors[0]] * 2

    # JOIN
    poly_collection = Poly3DCollection(
        faces,
        facecolors=face_colors if "_visited" not in node_type else "red",
        linewidths=1,
        edgecolors=edge_color,
        alpha=alpha,
    )

    # ADD TO PLOT
    ax.add_collection3d(poly_collection)


def render_colored_cuboid(ax, center, size, face_colors, edge_color, alpha):
    # ESTABLISH CUBOID'S CENTRE & SIZE
    x, y, z = center
    sx, sy, sz = size

    # DETERMINE VERTICES
    vertices = np.array(
        [
            [x - sx / 2, y - sy / 2, z - sz / 2],
            [x + sx / 2, y - sy / 2, z - sz / 2],
            [x + sx / 2, y + sy / 2, z - sz / 2],
            [x - sx / 2, y + sy / 2, z - sz / 2],
            [x - sx / 2, y - sy / 2, z + sz / 2],
            [x + sx / 2, y - sy / 2, z + sz / 2],
            [x + sx / 2, y + sy / 2, z + sz / 2],
            [x - sx / 2, y + sy / 2, z + sz / 2],
        ]
    )

    # ADD FACES
    faces = [
        [0, 1, 2, 3],
        [4, 5, 6, 7],
        [0, 1, 5, 4],
        [2, 3, 7, 6],
        [0, 3, 7, 4],
        [1, 2, 6, 5],
    ]
    face_list = [vertices[face] for face in faces]

    # MAKE COLLECTION
    poly = Poly3DCollection(
        face_list,
        facecolors=face_colors,
        edgecolors=edge_color,
        linewidths=1,
        alpha=alpha,
    )

    # ADD TO PLOT
    ax.add_collection3d(poly)


def visualise_3d_graph(
    graph, node_hex_map=node_hex_map, save_to_file=False, filename=None
):
    # HELPER VARIABLES
    # red_hex = "#d7a4a1"
    # blue_hex = "#b9cdff"
    gray_hex = "gray"
    yellow_hex = "#e0e317"
    # violet_hex = "violet"

    # CREATE FOUNDATIONAL MATPLOTLIB
    fig = plt.figure()
    ax = fig.add_subplot(111, projection="3d")

    # GET POSITIONS AND TYPES
    node_positions = nx.get_node_attributes(graph, "pos")
    node_types = nx.get_node_attributes(graph, "type")
    edge_types = nx.get_edge_attributes(graph, "pipe_type")

    # RENDER CUBES (NODES)
    for node_id in graph.nodes():
        node_type = node_types.get(node_id)
        if node_type and "o" not in node_type:
            position = node_positions.get(node_id)
            if position:
                size = [1.0, 1.0, 1.0]
                edge_color = "black"
                alpha = 1.0

                if "b" in node_type:
                    size = [0.9, 0.9, 0.9]
                    edge_color = "teal"
                    alpha = 0.7

                if "*" in node_type:
                    edge_color = "white"
                    alpha = 0.7

                elif "_visited" in node_type:
                    size = [0.5, 0.5, 0.5]
                    edge_color = gray_hex
                    alpha = 0.8  # Adjust alpha as needed

                if "h" in node_type:
                    node_info = {
                        "position": position,
                        "node_type": node_type.replace("*", ""),
                        "size": size,
                        "long_axis_index": -1,
                        "edge_color": "white" if "*" in node_type else "black",
                        "alpha": 0.7 if "*" in node_type else 1,
                    }

                    render_hadamard(ax, node_info, node_hex_map, "black")
                else:
                    render_non_hadamard(
                        ax,
                        position,
                        size,
                        node_type[:3],
                        node_hex_map,
                        alpha=alpha,
                        edge_color=edge_color,
                        line_width=0.5 if "_visited" in node_type else 1,
                    )

    # RENDER PIPES (EDGES)
    for u, v in graph.edges():
        pos_u = np.array(node_positions.get(u))
        pos_v = np.array(node_positions.get(v))
        if pos_u is not None and pos_v is not None:
            midpoint = (pos_u + pos_v) / 2

            delta = pos_v - pos_u
            original_length = np.linalg.norm(delta)
            adjusted_length = original_length - 1.0

            if adjusted_length > 0:
                orientation = np.argmax(np.abs(delta))
                size = [1.0, 1.0, 1.0]
                size[orientation] = int(adjusted_length)

                # Initialize all colours to gray
                pipe_type = edge_types.get((u, v), "gray")
                face_colors = [gray_hex] * 6

                if pipe_type:
                    alpha = 0.7 if "*" in pipe_type else 1
                    edge_color = "white" if "*" in pipe_type else "black"

                    color = node_hex_map.get(pipe_type.replace("*", ""), ["gray"] * 3)
                    color_x = color[0]
                    color_y = color[1]
                    color_z = color[2]

                    face_colors[4] = color_x  # right (+x)
                    face_colors[5] = color_x  # left (-x)
                    face_colors[2] = color_y  # front (-y)
                    face_colors[3] = color_y  # back (+y)
                    face_colors[0] = color_z  # bottom (-z)
                    face_colors[1] = color_z  # top (+z)

                    if "h" in pipe_type:
                        # Hadamards split into three: two coloured ends and a yellow ring at the middle
                        if adjusted_length > 0:
                            yellow_length = 0.1 * adjusted_length
                            colored_length = 0.45 * adjusted_length

                            # Skip if lengths are invalid
                            if colored_length < 0 or yellow_length < 0:
                                continue

                            size_colored = [1.0, 1.0, 1.0]
                            size_yellow = [1.0, 1.0, 1.0]
                            size_colored[orientation] = float(colored_length)
                            size_yellow[orientation] = float(yellow_length)

                            offset1 = np.zeros(3)
                            # offset2 = np.zeros(3)
                            offset3 = np.zeros(3)

                            offset1[orientation] = -(
                                yellow_length / 2 + colored_length / 2
                            )
                            offset3[orientation] = (
                                yellow_length / 2 + colored_length / 2
                            )

                            center1 = midpoint + offset1
                            center2 = midpoint
                            center3 = midpoint + offset3

                            face_colors_colored = list(face_colors)
                            face_colors_yellow = [yellow_hex] * 6  # Yellow color

                            render_colored_cuboid(
                                ax,
                                center1,
                                size_colored,
                                face_colors_colored,
                                edge_color,
                                alpha,
                            )
                            render_colored_cuboid(
                                ax,
                                center2,
                                size_yellow,
                                face_colors_yellow,
                                edge_color,
                                alpha,
                            )
                            render_colored_cuboid(
                                ax,
                                center3,
                                size_colored,
                                face_colors_colored,
                                edge_color,
                                alpha,
                            )
                    else:
                        render_colored_cuboid(
                            ax, midpoint, size, face_colors, edge_color, alpha
                        )

                # Don't render if pipe_type is None
                else:
                    pass

    # Adjust plot limits
    all_positions = np.array(list(node_positions.values()))
    if all_positions.size > 0:
        max_range = np.ptp(all_positions, axis=0).max() / 2.0
        mid = np.mean(all_positions, axis=0)
        ax.set_xlim(mid[0] - max_range - 1, mid[0] + max_range + 1)
        ax.set_ylim(mid[1] - max_range - 1, mid[1] + max_range + 1)
        ax.set_zlim(mid[2] - max_range - 1, mid[2] + max_range + 1)
    else:
        ax.set_xlim([-2, 2])
        ax.set_ylim([-2, 2])
        ax.set_zlim([-2, 2])

    # Set labels
    ax.set_xlabel("X")
    ax.set_ylabel("Y")
    ax.set_zlabel("Z")

    # Pop visualisation or save to file
    if save_to_file:
        plt.savefig(
            f"./src/tqec/interop/pyzx/synthesis/two_stage_greedy_bfs/grapher/plots/{filename}.png"
        )

        plt.close()
    else:
        plt.show()


def make_graph_from_edge_paths(edge_paths: dict) -> nx.Graph:
    final_graph = nx.Graph()
    node_counter = 0
    for edge, path_data in edge_paths.items():
        primary_node_and_edges = []
        path_nodes = path_data["path_nodes"]
        if path_nodes == "error":
            continue
        node_index_map = {}

        for pos, kind in path_nodes:
            if (pos, kind) not in node_index_map:
                node_index_map[(pos, kind)] = node_counter
                primary_node_and_edges.append([node_counter, pos, kind])
                node_counter += 1
            else:
                index_to_use = node_index_map[(pos, kind)]

                found = False
                for entry in primary_node_and_edges:
                    if entry[0] == index_to_use:
                        entry[1] = pos
                        found = True
                        break
                if not found:
                    primary_node_and_edges.append([index_to_use, pos, kind])

        # Add nodes
        for index, pos, node_type in primary_node_and_edges:
            if index not in final_graph:
                final_graph.add_node(index, pos=pos, type=node_type)

        # Add edges
        for i in range(len(primary_node_and_edges)):
            index, pos, node_type = primary_node_and_edges[i]
            if "o" in node_type:
                prev_index_path = i - 1
                next_index_path = i + 1
                if 0 <= prev_index_path < len(
                    primary_node_and_edges
                ) and 0 <= next_index_path < len(primary_node_and_edges):
                    prev_node_index = primary_node_and_edges[prev_index_path][0]
                    next_node_index = primary_node_and_edges[next_index_path][0]
                    if (
                        prev_node_index in final_graph
                        and next_node_index in final_graph
                    ):
                        final_graph.add_edge(
                            prev_node_index, next_node_index, pipe_type=node_type
                        )

    return final_graph


def make_graph_from_pathfinding(primary_node_and_edges, secondary_nodes=[]):
    graph = nx.Graph()

    for index, pos, node_type in primary_node_and_edges:
        graph.add_node(index, pos=pos, type=node_type)

    for i in range(len(primary_node_and_edges)):
        _, pos, node_type = primary_node_and_edges[i]
        if "o" in node_type:
            prev_index = i - 1
            next_index = i + 1
            if 0 <= prev_index < len(primary_node_and_edges) and 0 <= next_index < len(
                primary_node_and_edges
            ):
                graph.add_edge(prev_index, next_index, pipe_type=node_type)

    if secondary_nodes:
        start_index = len(primary_node_and_edges)
        for i, (pos, node_type) in enumerate(secondary_nodes):
            index = start_index + i
            graph.add_node(index, pos=pos, type=node_type)

            if "o" in node_type:
                prev_index = index - 1
                next_index = index + 1
                if 0 <= prev_index < start_index + len(
                    secondary_nodes
                ) and 0 <= next_index < start_index + len(secondary_nodes):
                    graph.add_edge(prev_index, next_index, pipe_type=node_type)

    return graph
