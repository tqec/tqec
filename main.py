from tqec import BlockGraph, compile_block_graph
from tqec.utils.position import Position3D


g = BlockGraph("Test Temporal Hadamard")
n1 = g.add_cube(Position3D(0, 0, 0), "XZZ")
n2 = g.add_cube(Position3D(0, 0, 1), "ZXX")
g.add_pipe(n1, n2)

compiled = compile_block_graph(g)
print(compiled.generate_crumble_url(k=3, add_polygons=True, manhattan_radius=0))
