from tqec import BlockGraph, compile_block_graph
from tqec.utils.noise_model import NoiseModel
from tqec.utils.position import Position3D


g = BlockGraph("Test Temporal Hadamard")
n1 = g.add_cube(Position3D(0, 0, 0), "ZXZ")
n2 = g.add_cube(Position3D(0, 0, 1), "XZX")
g.add_pipe(n1, n2)

compiled = compile_block_graph(g)
print(compiled.generate_crumble_url(k=2, add_polygons=True))
# circuit = compiled.generate_stim_circuit(k=2, noise_model=NoiseModel.uniform_depolarizing(0.001))
# print(len(circuit.shortest_graphlike_error()))
