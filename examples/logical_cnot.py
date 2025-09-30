"""Example of compiling a logical CNOT `.dae` model to `stim.Circuit`."""

from pathlib import Path

import matplotlib.pyplot as plt
import numpy
import sinter

from tqec.compile.convention import FIXED_BOUNDARY_CONVENTION, FIXED_BULK_CONVENTION, Convention
from tqec.gallery.cnot import cnot
from tqec.simulation.plotting.inset import plot_observable_as_inset
from tqec.simulation.simulation import start_simulation_using_sinter
from tqec.utils.enums import Basis
from tqec.utils.noise_model import NoiseModel

EXAMPLE_FOLDER = Path(__file__).parent
TQEC_FOLDER = EXAMPLE_FOLDER.parent
ASSETS_FOLDER = TQEC_FOLDER / "assets"


def generate_graphs(convention: Convention, observable_basis: Basis) -> None:
    """Generate the logical error-rate graphs from a convention and a basis."""
    # 1 Create `BlockGraph` representing the computation
    block_graph = cnot(observable_basis)
    zx_graph = block_graph.to_zx_graph()

    # 2. Find and choose the logical observables
    correlation_surfaces = block_graph.find_correlation_surfaces()
    # Optional: filter observables here
    # correlation_surfaces = [correlation_surfaces[0]]

    stats = start_simulation_using_sinter(
        block_graph,
        range(1, 4),
        list(numpy.logspace(-4, -1, 10)),
        NoiseModel.uniform_depolarizing,
        manhattan_radius=2,
        convention=convention,
        observables=correlation_surfaces,
        max_shots=10_000_000,
        max_errors=5_000,
        decoders=["pymatching"],
        print_progress=True,
    )

    for i, stat in enumerate(stats):
        fig, ax = plt.subplots()
        sinter.plot_error_rate(
            ax=ax,
            stats=stat,
            x_func=lambda stat: stat.json_metadata["p"],
            group_func=lambda stat: stat.json_metadata["d"],
        )
        plot_observable_as_inset(ax, zx_graph, correlation_surfaces[i])
        ax.grid(axis="both")
        ax.legend()
        ax.loglog()
        ax.set_title(f"{convention.name} Logical CNOT Error Rate")
        fig.savefig(
            ASSETS_FOLDER
            / f"{convention.name}_logical_cnot_result_{observable_basis}_observable_{i}.png"
        )


def main():
    """Generate the 4 different error rate graphs."""
    generate_graphs(FIXED_BOUNDARY_CONVENTION, Basis.Z)
    generate_graphs(FIXED_BOUNDARY_CONVENTION, Basis.X)
    generate_graphs(FIXED_BULK_CONVENTION, Basis.Z)
    generate_graphs(FIXED_BULK_CONVENTION, Basis.X)


if __name__ == "__main__":
    main()
