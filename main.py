import subprocess
from pathlib import Path
from typing import Any

from lassynth import LatticeSurgerySynthesizer

from tqec.interop.lassynth.lasre import convert_lasre_to_block_graph


def resolve_kissat_path():
    """Resolves the path to the kissat binary using the 'which' command.

    Returns:
      str: The path to the kissat binary, or None if not found.
    """
    try:
        result = subprocess.run(
            ["which", "kissat"], capture_output=True, text=True, check=True
        )
        return str(Path(result.stdout.strip()).resolve().parent)
    except subprocess.CalledProcessError:
        return None


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
input_dict: dict[str, Any] = {"max_i": 3, "max_j": 3, "max_k": 4}
input_dict["ports"] = [
    {"location": [0, 0, 4], "direction": "-K", "z_basis_direction": "J"},
    {"location": [1, 0, 4], "direction": "-K", "z_basis_direction": "J"},
    {"location": [2, 0, 4], "direction": "-K", "z_basis_direction": "J"},
    {"location": [0, 2, 4], "direction": "-K", "z_basis_direction": "J"},
    {"location": [1, 2, 4], "direction": "-K", "z_basis_direction": "J"},
    {"location": [2, 2, 4], "direction": "-K", "z_basis_direction": "J"},
    {"location": [0, 1, 4], "direction": "-K", "z_basis_direction": "J"},
]
input_dict["stabilizers"] = [
    "XXXX...",
    "XX..XX.",
    "X.X.X.X",
    "ZZZZ...",
    "ZZ..ZZ.",
    "Z.Z.Z.Z",
]

if __name__ == "__main__":
    # Resolve kissat path
    kissat_path = resolve_kissat_path()
    solver = "kissat" if kissat_path is not None else "picosat"

    las_synth = LatticeSurgerySynthesizer(
        solver="kissat",
        kissat_dir=kissat_path,
    )
    result = las_synth.optimize_depth(
        specification=input_dict, color_ij=False, start_depth=2
    )
    assert result is not None
    result = result.after_default_optimizations()
    result.save_lasre(f"{subroutine}.lasre.json")
    bg = convert_lasre_to_block_graph(f"{subroutine}.lasre.json")
    bg.view_as_html(
        f"{subroutine}.html",
    )

    with open("steane_zx.json", "w") as f:
        f.write(bg.to_zx_graph().g.to_json())
