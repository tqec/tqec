"""
In this file, we import, visualise, and compare simulations for two CNOT models exported from SketchUp as .dae (COLLADA) files.
One of the models is unrotated, the other is rotated 90 degrees along the 'x' axis.

"""

# IMPORTS
import matplotlib.pyplot as plt
import numpy as np
import sinter
from pathlib import Path
from multiprocessing import cpu_count
from tqec import BlockGraph, compile_block_graph
from tqec.utils.noise_model import NoiseModel
from tqec.simulation.simulation import start_simulation_using_sinter
from tqec.simulation.plotting.inset import plot_observable_as_inset
from tqec import SignedDirection3D, Direction3D

# FOLDERS
EXAMPLE_FOLDER = Path(__file__).parent
TQEC_FOLDER = EXAMPLE_FOLDER.parent
ASSETS_FOLDER = TQEC_FOLDER / "assets"

# IMPORT / CONSTRUCT LOGICAL COMPUTATIONS
# To use the computation with the tqec library, you need to import it using tqec.BlockGraph
# The tqec library can automatically search for valid observables in the imported computation.
# To get a list of all the valid observables, you can use the following code


def write_to_html(filename, html):
    with open(f"{filename}.html", "w") as f:
        f.write(str(html))
        f.close()


def write_circuit_to_file(filename, circuit):
    with open(f"{filename}.txt", "w") as f:
        f.write(str(circuit))
        f.close()


def generate_graphs(filename: str) -> None:
    # IMPORT TO BLOCKGRAPH
    # Import
    block_graph = BlockGraph.from_dae_file(ASSETS_FOLDER / f"{filename}.dae")
    correlation_surfaces = block_graph.find_correlation_surfaces()

    # Write to file
    write_to_html(
        filename,
        block_graph.view_as_html(
            pop_faces_at_direction=SignedDirection3D(Direction3D.Z, True),
            show_correlation_surface=correlation_surfaces[1],
        ),
    )

    # COMPILE & EXPORT COMPUTATION
    # To get a stim.Circuit instance, the computation first need to be compiled.
    compiled_computation = compile_block_graph(
        block_graph, observables=[correlation_surfaces[1]]
    )

    # You can then generate the circuit
    circuit = compiled_computation.generate_stim_circuit(
        k=2,  # k = (d-1)/2 is the scale factor (computationally intensive - large vals will take time).
        noise_model=NoiseModel.uniform_depolarizing(0.001),
    )
    write_circuit_to_file(filename, circuit)

    # SIMULATE MULTIPLE EXPERIMENTS
    # Returns a iterator
    stats = start_simulation_using_sinter(
        block_graph,
        ks=range(1, 4),  # k values for the code distance
        ps=list(np.logspace(-4, -1, 10)),  # error rates
        noise_model_factory=NoiseModel.uniform_depolarizing,  # noise model
        manhattan_radius=2,  # parameter for automatic detector computation
        observables=[correlation_surfaces[1]],  # observable of interest
        decoders=["pymatching"],
        num_workers=cpu_count(),
        max_shots=10_000_000,
        max_errors=5_000,
        print_progress=True,
    )

    # SIMULATE & PLOT RESULTS
    # Simulation results can be plotted with matplolib using the plot_simulation_results.
    zx_graph = block_graph.to_zx_graph()
    fig, ax = plt.subplots()

    sinter.plot_error_rate(
        ax=ax,
        stats=next(stats),
        x_func=lambda stat: stat.json_metadata["p"],
        group_func=lambda stat: stat.json_metadata["d"],
    )

    plot_observable_as_inset(ax, zx_graph, correlation_surfaces[1])
    ax.grid(axis="both")
    ax.legend()
    ax.loglog()
    ax.set_title(f"Error Rate, {filename}")
    fig.savefig(f"{filename}.png")


def main(filename):
    generate_graphs(filename)


if __name__ == "__main__":
    filename = "rotated_cnot_x_180"
    main(filename)
