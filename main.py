import gen
import stim
import tqecd

from tqec import compile_block_graph
from tqec.compile.convention import FIXED_BOUNDARY_CONVENTION, FIXED_BULK_CONVENTION
from tqec.compile.detectors.database import DetectorDatabase
from tqec.computation.block_graph import BlockGraph
from tqec.gallery import s_gate_teleportation
from tqec.plaquette.rpng.rpng import PauliBasis
from tqec.utils.noise_model import NoiseModel
from tqec.utils.position import Position3D


def _remove_detectors(circuit: stim.Circuit) -> stim.Circuit:
    out = stim.Circuit()
    for inst in circuit:
        if isinstance(inst, stim.CircuitRepeatBlock):
            out.append(
                stim.CircuitRepeatBlock(inst.repeat_count, _remove_detectors(inst.body_copy()))
            )
        elif inst.name == "DETECTOR":
            continue
        else:
            out.append(inst)
    return out


g = s_gate_teleportation(in_observable_basis=PauliBasis.Y)

# g = BlockGraph("Y Move")
# nodes = [
#     (Position3D(0, 0, 0), "Y", ""),
#     (Position3D(0, 0, 1), "ZXZ", ""),
#     # (Position3D(1, 0, 1), "XZX", ""),
#     (Position3D(0, 0, 2), "Y", ""),
# ]
# for pos, kind, label in nodes:
#     g.add_cube(pos, kind, label)
#
# pipes = [(0, 1), (1, 2)]
# for p0, p1 in pipes:
#     g.add_pipe(nodes[p0][0], nodes[p1][0])

# g = BlockGraph()
# n1 = g.add_cube(Position3D(0, 0, 0), "Y")
# n2 = g.add_cube(Position3D(0, 0, 1), "Y")
# g.add_pipe(n1, n2, "XZO")

if __name__ == "__main__":
    compiled_g = compile_block_graph(g, convention=FIXED_BULK_CONVENTION)
    layer_tree = compiled_g.to_layer_tree()
    circuit = layer_tree.generate_circuit(k=2)
    print(circuit)
    # with open("wrong.html", "w") as f:
    #     html = gen.stim_circuit_html_viewer(circuit)
    #     f.write(str(html))
    # circuit.to_file("ymemory_wrong.stim")
    # circuit = stim.Circuit.from_file("ymemory_wrong.stim")

    # circuit = tqecd.annotate_detectors_automatically(_remove_detectors(circuit))

    noise = NoiseModel.uniform_depolarizing(1e-3)
    noisy_circuit = noise.noisy_circuit(circuit)
    logical_error = noisy_circuit.shortest_graphlike_error(canonicalize_circuit_errors=True)
    print(f"Circuit Distance = {len(logical_error)}")
    # print("Logical Error:")
    # for error in logical_error:
    #     print(f"  {error}")
    # surfaces = g.find_correlation_surfaces()
    # g.view_as_html(
    #     "s_gate_teleportation.html",
    #     pop_faces_at_directions=("-Y",),
    #     show_correlation_surface=surfaces[0],
    # )
