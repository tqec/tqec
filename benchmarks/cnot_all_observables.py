import argparse
from pathlib import Path

import stim
from tqecd.construction import annotate_detectors_automatically

from tqec.compile.compile import CompiledGraph, compile_block_graph
from tqec.compile.specs.library.css import CSS_BLOCK_BUILDER, CSS_SUBSTITUTION_BUILDER
from tqec.utils.noise_model import NoiseModel
from tqec.gallery import logical_cnot_block_graph

BENCHMARK_FOLDER = Path(__file__).resolve().parent
TQEC_FOLDER = BENCHMARK_FOLDER.parent
ASSETS_FOLDER = TQEC_FOLDER / "assets"
CNOT_DAE_FILE = ASSETS_FOLDER / "logical_cnot.dae"


def generate_stim_circuit(
    compiled_graph: CompiledGraph, k: int, p: float
) -> stim.Circuit:
    circuit_without_detectors = compiled_graph.generate_stim_circuit(
        k, noise_model=NoiseModel.uniform_depolarizing(p)
    )
    # For now, we annotate the detectors as post-processing step
    return annotate_detectors_automatically(circuit_without_detectors)


def generate_cnot_circuits(*ks: int) -> None:
    # 1 Create `BlockGraph` representing the computation
    block_graph = logical_cnot_block_graph("X")

    # 2. (Optional) Find and choose the logical observables
    correlation_surfaces = block_graph.find_correlation_surfaces()

    # 3. Compile the `BlockGraph`
    compiled_graph = compile_block_graph(
        block_graph,
        block_builder=CSS_BLOCK_BUILDER,
        substitution_builder=CSS_SUBSTITUTION_BUILDER,
        observables=[correlation_surfaces[1]],
    )

    for k in ks:
        _ = generate_stim_circuit(compiled_graph, k, 0.001)


def main() -> None:
    parser = argparse.ArgumentParser(description="")
    parser.add_argument(
        "-k",
        help="The scale factors applied to the circuits.",
        nargs="+",
        type=int,
        required=True,
    )
    args = parser.parse_args()
    generate_cnot_circuits(*args.k)


if __name__ == "__main__":
    main()
