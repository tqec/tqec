from pyzx.graph.graph_s import GraphS
from pyzx.utils import VertexType

from tqec.interop.pyzx.synthesis import greedy_bfs_block_synthesis

g = GraphS()
g.add_vertices(8)
# z_vertices = [0, 4, 5, 6]
# x_vertices = [1, 2, 3, 7]
z_vertices = [0, 4, 5, 6]
x_vertices = [1, 2, 3, 7]
for n in z_vertices:
    g.set_type(n, VertexType.Z)
for n in x_vertices:
    g.set_type(n, VertexType.X)

edges = [
    (0, 1),
    (0, 2),
    (0, 3),
    (1, 4),
    (2, 5),
    (3, 6),
    (4, 7),
    (5, 7),
    (6, 7),
    # (0, 8),
    # (1, 9),
    # (2, 10),
    # (3, 11),
    # (4, 12),
    # (5, 13),
    # (6, 14),
]
g.add_edges(edges)
# g = GraphS()
# g.add_vertices(24)
# z_vertices = [2, 3, 4, 5, 6, 8, 10, 11, 16, 17]
# x_vertices = [0, 1, 7, 9, 12, 13, 14, 15]
# for n in z_vertices:
#     g.set_type(n, VertexType.Z)
# for n in x_vertices:
#     g.set_type(n, VertexType.X)
#
# edges = [
#     (0, 1),
#     (0, 2),
#     (0, 3),
#     (0, 4),
#     (1, 5),
#     (1, 6),
#     (2, 3),
#     (2, 7),
#     (3, 8),
#     (4, 9),
#     (4, 10),
#     (4, 12),
#     (5, 7),
#     (5, 11),
#     (5, 13),
#     (6, 12),
#     (7, 9),
#     (7, 17),
#     (8, 9),
#     (8, 13),
#     (10, 14),
#     (10, 15),
#     (11, 12),
#     (12, 16),
#     (13, 15),
#     (13, 17),
#     (14, 15),
#     (14, 17),
#     (16, 17),
#     (3, 18),
#     (16, 19),
#     (6, 20),
#     (11, 21),
#     (11, 22),
#     (15, 23),
# ]
# g.add_edges(edges)
# g.set_edge_type((2, 3), EdgeType.HADAMARD)
# g.set_edge_type((14, 15), EdgeType.HADAMARD)

bg = greedy_bfs_block_synthesis(g)

bg.view_as_html("greedy_bfs_synthesis.html")
