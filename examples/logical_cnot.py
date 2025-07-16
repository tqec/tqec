"""This is an example of compiling a logical CNOT `.dae` model to
`stim.Circuit`.
"""

from pathlib import Path
from typing import Literal

import matplotlib.pyplot as plt
import numpy
import sinter

from tqec.compile.specs.library.css import CSS_BLOCK_BUILDER, CSS_SUBSTITUTION_BUILDER
from tqec.compile.specs.library.zxxz import (
    ZXXZ_BLOCK_BUILDER,
    ZXXZ_SUBSTITUTION_BUILDER,
)
from tqec.gallery.cnot import cnot
from tqec.simulation.plotting.inset import plot_observable_as_inset
from tqec.simulation.simulation import start_simulation_using_sinter
from tqec.utils.enums import Basis
from tqec.utils.noise_model import NoiseModel

EXAMPLE_FOLDER = Path(__file__).parent
TQEC_FOLDER = EXAMPLE_FOLDER.parent
ASSETS_FOLDER = TQEC_FOLDER / "assets"


def generate_graphs(style: Literal["css", "zxxz"], observable_basis: Basis) -> None:
    # 1 Create `BlockGraph` representing the computation
    block_graph = cnot(observable_basis)
    zx_graph = block_graph.to_zx_graph()

    # 2. Find and choose the logical observables
    correlation_surfaces = block_graph.find_correlation_surfaces()
    # Optional: filter observables here
    # correlation_surfaces = [correlation_surfaces[0]]

    block_builder = CSS_BLOCK_BUILDER if style == "css" else ZXXZ_BLOCK_BUILDER
    substitution_builder = CSS_SUBSTITUTION_BUILDER if style == "css" else ZXXZ_SUBSTITUTION_BUILDER
    stats = start_simulation_using_sinter(
        block_graph,
        range(1, 4),
        list(numpy.logspace(-4, -1, 10)),
        NoiseModel.uniform_depolarizing,
        manhattan_radius=2,
        block_builder=block_builder,
        substitution_builder=substitution_builder,
        observables=correlation_surfaces,
        num_workers=20,
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
        ax.set_title(f"{style.upper()} Logical CNOT Error Rate")
        fig.savefig(
            ASSETS_FOLDER / f"{style}_logical_cnot_result_{observable_basis}_observable_{i}.png"
        )


def main():
    generate_graphs("css", Basis.Z)
    generate_graphs("css", Basis.X)
    generate_graphs("zxxz", Basis.Z)
    generate_graphs("zxxz", Basis.X)


if __name__ == "__main__":
    main()
