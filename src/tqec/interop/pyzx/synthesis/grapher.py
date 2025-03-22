"""NetworkX / Matplotlib functions to create a quick visualisation of a 3D graph.
A computationally inexpensive way of checking progress in any 2D PyZX graph -> TQEC journey.

"""

import numpy as np
import networkx as nx
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d.art3d import Poly3DCollection
from tqec.gallery.cnot import cnot
from tqec.utils.enums import Basis
from tqec.utils.position import FloatPosition3D

# SOME CONSTANTS NEEDED IN FUNCTIONS
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
}


def get_vertices(x, y, z, size_x, size_y, size_z):
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
    return [
        [vertices[0], vertices[1], vertices[2], vertices[3]],
        [vertices[4], vertices[5], vertices[6], vertices[7]],
        [vertices[0], vertices[1], vertices[5], vertices[4]],
        [vertices[2], vertices[3], vertices[7], vertices[6]],
        [vertices[1], vertices[2], vertices[6], vertices[5]],
        [vertices[0], vertices[3], vertices[7], vertices[4]],
    ]


# FUNCTIONS
def create_graph_object(nodes):
    # GRAPH OBJECT
    graph = nx.Graph()

    # ADD NODES TO GRAPH
    for node_id, pos, t in nodes:
        graph.add_node(node_id, pos=pos, type=t)

    # RETURN GRAPH WITH NODES
    return graph


def visualise_3d_graph(
    graph,
    node_hex_map=node_hex_map,
):
    """
    Visualizes a 3D NetworkX graph.

    ! Note. HADAMARDS not yet fully implemented.
    ! Note. Need to tune positioning to account for pipe length not eating into blocks.

    Args:
        - graph: The NetworkX graph object.
        - node_hex_map: A map of (HEX) colours for the nodes.
    """

    # PREPARE PLOT
    fig = plt.figure()
    ax = fig.add_subplot(111, projection="3d")

    # EXTRACT NODE POSITIONS & TYPES
    node_positions = nx.get_node_attributes(graph, "pos")
    node_types = nx.get_node_attributes(graph, "type")

    # PLOT COLOURED CUBES
    for node_id in graph.nodes():
        # Get the current node position and type
        position = node_positions[node_id]
        node_type = node_types[node_id]

        # Default to size 1, scale to 2 if node is pipe
        size_x, size_y, size_z = 1.0, 1.0, 1.0
        if "o" in node_type:
            o_index = node_type.find("o")
            if o_index == 0:
                size_x = 2.0
            elif o_index == 1:
                size_y = 2.0
            elif o_index == 2:
                size_z = 2.0

        # Pin vertices from position and sizing & match faces
        x, y, z = position
        vertices = get_vertices(x, y, z, size_x, size_y, size_z)
        faces = get_faces(vertices)

        # Add colors
        colors = node_hex_map.get(node_type, ["gray"] * 3)
        face_colors = [colors[2]] * 2 + [colors[1]] * 2 + [colors[0]] * 2
        edge_col = "black" if "h" not in node_type else "#e0e317"

        # Join
        poly_collection = Poly3DCollection(
            faces, facecolors=face_colors, linewidths=1, edgecolors=edge_col, alpha=1
        )

        # Add to plot
        ax.add_collection3d(poly_collection)

    # ADJUST PLOT TO ENCOMPASS ALL CUBES
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

    # SET LABELS
    ax.set_xlabel("X")
    ax.set_ylabel("Y")
    ax.set_zlabel("Z")

    # DISPLAY PLOT
    plt.show()


def visualise_progress(path_dict, current_node_info):
    # BUILD NODES ARRAY FROM PATH DICTIONARY
    nodes = []
    full_path = path_dict[tuple(current_node_info)]
    for i, ele in enumerate(full_path):
        nodes.append([i, ele[0], ele[1]])

    # BUILD GRAPH FROM NODES ARRAY
    graph = create_graph_object(nodes)

    # VISUALISE USING MATPLOTLIB
    visualise_3d_graph(graph)


# The functions in this file are designed to visualise objects in other processes rather than be run by themselves.
# That said, it is also possible to also run file to test generation of all possible types.
if __name__ == "__main__":
    # TEST USING SYNTAX OF A PATH FROM AN ALGORITHM I AM CURRENTLY BUILDING

    # path_dict = {
    #    ((0, 0, 0), "zxx"): [
    #        [(0, 0, 0), "xzz"],
    #        [(0, 0, 2), "xzx"],
    #        [(0, 0, 4), "zzx"],
    #        [(0, 0, 6), "zxx"],
    #        [(0, 0, 8), "zxz"],
    #        [(3, 0, 0), "zxo"],
    #        [(3, 0, 3), "xzo"],
    #        [(3, 0, 6), "oxz"],
    #        [(3, 0, 9), "ozx"],
    #        [(3, 0, 12), "xoz"],
    #        [(3, 0, 15), "zox"],
    #        [(6, 0, 0), "zxoh"],
    #        [(6, 0, 3), "xzoh"],
    #        [(6, 0, 6), "oxzh"],
    #        [(6, 0, 9), "ozxh"],
    #        [(6, 0, 12), "xozh"],
    #        [(6, 0, 15), "zoxh"],
    #    ],
    # }
    # current_node_info = [(0, 0, 0), "zxx"]
    # path = path_dict[tuple(current_node_info)]
    # visualise_progress(path_dict, current_node_info)

    # TEST USING AN INTERNALLY-GENERATED TQEC BLOCKGRAPH
    # Helper variables
    nodes = []

    # Loop over graph to get a minimalist list of positions and types
    g = cnot(Basis.Z)
    pipe_length: float = 2.0
    for cube in g.cubes:
        if cube.is_port:
            continue
        scaled_position = FloatPosition3D(
            *(p * (0.5 + pipe_length) for p in cube.position.as_tuple())
        )
        if cube.is_y_cube and g.has_pipe_between(
            cube.position, cube.position.shift_by(dz=1)
        ):
            scaled_position = scaled_position.shift_by(dz=0.5)
        matrix = np.eye(4, dtype=np.float32)
        matrix[:3, 3] = scaled_position.as_array()
        pop_faces_at_directions = []
        nodes.append([tuple(matrix[:3, 3]), str(cube.kind).lower()])

    for pipe in g.pipes:
        head_pos = FloatPosition3D(
            *(p * (0.5 + pipe_length) for p in pipe.u.position.as_tuple())
        )
        print(head_pos)
        pipe_pos = head_pos.shift_in_direction(pipe.direction, pipe_length / 2)
        print(pipe_pos)
        print()
        matrix = np.eye(4, dtype=np.float32)
        matrix[:3, 3] = pipe_pos.as_array()
        scales = [1.0, 1.0, 1.0]
        # We divide the scaling by 2.0 because the pipe's default length is 2.0.
        scales[pipe.direction.value] = pipe_length / 2.0
        matrix[:3, :3] = np.diag(scales)
        nodes.append([tuple(matrix[:3, 3]), str(pipe.kind).lower()])

    # Send nodes to visualiser
    path_dict = {tuple(nodes[0]): nodes}
    visualise_progress(path_dict, tuple(nodes[0]))
