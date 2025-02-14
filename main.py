from typing import Any
from lassynth import LatticeSurgerySynthesizer

from tqec.interop.lassynth.lasre import convert_lasre_to_block_graph
from tqec.utils.position import Position3D

# CNOT
# subroutine = "cnot"
# input_dict: dict[str, Any] = {"max_i": 2, "max_j": 2, "max_k": 3}
# input_dict["ports"] = [
#     {"location": [1, 0, 0], "direction": "+K", "z_basis_direction": "J"},
#     {"location": [0, 1, 0], "direction": "+K", "z_basis_direction": "J"},
#     {"location": [1, 0, 3], "direction": "-K", "z_basis_direction": "J"},
#     {"location": [0, 1, 3], "direction": "-K", "z_basis_direction": "J"},
# ]
# input_dict["stabilizers"] = ["Z.Z.", ".ZZZ", "X.XX", ".X.X"]

# CZ
# subroutine = "cz"
# input_dict: dict[str, Any] = {"max_i": 2, "max_j": 2, "max_k": 2}
# input_dict["ports"] = [
#     {"location": [0, 1, 0], "direction": "+K", "z_basis_direction": "J"},
#     {"location": [0, 1, 2], "direction": "-K", "z_basis_direction": "J"},
#     {"location": [1, 0, 1], "direction": "+J", "z_basis_direction": "K"},
#     {"location": [1, 2, 1], "direction": "-J", "z_basis_direction": "K"},
# ]
# input_dict["stabilizers"] = ["ZZ..", "XX.Z", "..ZZ", ".ZXX"]

# Steane
subroutine = "steane"
# input_dict: dict[str, Any] = {"max_i": 3, "max_j": 3, "max_k": 3}
# input_dict["ports"] = [
#     {"location": [0, 1, 0], "direction": "+K", "z_basis_direction": "J"},
#     {"location": [1, 2, 1], "direction": "-J", "z_basis_direction": "K"},
#     {"location": [2, 2, 0], "direction": "+K", "z_basis_direction": "J"},
#     {"location": [3, 0, 1], "direction": "-I", "z_basis_direction": "K"},
#     {"location": [2, 1, 2], "direction": "-K", "z_basis_direction": "J"},
#     {"location": [0, 1, 2], "direction": "-K", "z_basis_direction": "J"},
#     {"location": [0, 2, 2], "direction": "-K", "z_basis_direction": "J"},
# ]
input_dict: dict[str, Any] = {"max_i": 3, "max_j": 3, "max_k": 3}
input_dict["ports"] = [
    {"location": [0, 0, 3], "direction": "-K", "z_basis_direction": "J"},
    {"location": [1, 0, 3], "direction": "-K", "z_basis_direction": "J"},
    {"location": [2, 0, 3], "direction": "-K", "z_basis_direction": "J"},
    {"location": [0, 2, 3], "direction": "-K", "z_basis_direction": "J"},
    {"location": [1, 2, 3], "direction": "-K", "z_basis_direction": "J"},
    {"location": [2, 2, 3], "direction": "-K", "z_basis_direction": "J"},
    {"location": [0, 1, 3], "direction": "-K", "z_basis_direction": "J"},
]
# input_dict: dict[str, Any] = {"max_i": 7, "max_j": 3, "max_k": 2}
# input_dict["ports"] = [
#     {"location": [0, 3, 0], "direction": "-J", "z_basis_direction": "K"},
#     {"location": [1, 3, 0], "direction": "-J", "z_basis_direction": "K"},
#     {"location": [2, 3, 0], "direction": "-J", "z_basis_direction": "K"},
#     {"location": [3, 3, 0], "direction": "-J", "z_basis_direction": "K"},
#     {"location": [4, 3, 0], "direction": "-J", "z_basis_direction": "K"},
#     {"location": [5, 3, 0], "direction": "-J", "z_basis_direction": "K"},
#     {"location": [6, 3, 0], "direction": "-J", "z_basis_direction": "K"},
# ]
input_dict["stabilizers"] = [
    "XXXX...",
    "XX..XX.",
    "X.X.X.X",
    "ZZZZ...",
    "ZZ..ZZ.",
    "Z.Z.Z.Z",
]

if __name__ == "__main__":
    las_synth = LatticeSurgerySynthesizer(
        solver="kissat", kissat_dir="/home/inm/Downloads/kissat/build/"
    )
    # result = las_synth.solve(specification=input_dict, color_ij=False)
    result = las_synth.optimize_depth(
        specification=input_dict, color_ij=False, start_depth=2
    )
    result = result.after_default_optimizations()
    result.save_lasre(f"{subroutine}.lasre.json")
    result.to_3d_model_gltf(f"{subroutine}.gltf", attach_axes=True)

    bg = convert_lasre_to_block_graph(f"{subroutine}.lasre.json")
    p2v = bg.to_zx_graph().p2v
    io_ports = [p2v[Position3D(*port["location"])] for port in input_dict["ports"]]
    correlation_surfaces = bg.find_correlation_surfaces()
    external_stabilizers = [
        s.external_stabilizer(io_ports) for s in correlation_surfaces
    ]
    vis_xxxx = correlation_surfaces[external_stabilizers.index("XXXXIII")]
    print(external_stabilizers)
    bg.view_as_html(
        f"{subroutine}.html",
        pop_faces_at_direction="-Y",
        show_correlation_surface=vis_xxxx,
    )
