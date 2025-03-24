from pathlib import Path
from typing import Literal

import matplotlib.pyplot as plt
import numpy
import sinter

from tqec.compile.specs.library import ALL_SPECS
from tqec.computation.block_graph import BlockGraph
from tqec.simulation.plotting.inset import plot_observable_as_inset
from tqec.simulation.simulation import start_simulation_using_sinter
from tqec.utils.noise_model import NoiseModel

TQEC_FOLDER = Path(__file__).parent
ASSETS_FOLDER = TQEC_FOLDER / "assets"
OPEN_MODEL_DAE = "/home/inm/Downloads/steane_volume12.dae"
model_name = "steane_volume12_encoding"


def generate_graphs(style: Literal["STANDARD"]) -> None:
    block_graph = BlockGraph.from_dae_file(OPEN_MODEL_DAE)
    block_graph.validate()
    zx_graph = block_graph.to_zx_graph()

    filled_graphs = block_graph.fill_ports_for_minimal_simulation()

    block_builder, substitution_builder = ALL_SPECS[style]
    for run, fg in enumerate(filled_graphs):
        stats = start_simulation_using_sinter(
            fg.graph,
            range(1, 4),
            list(numpy.logspace(-4, -1, 10)),
            NoiseModel.uniform_depolarizing,
            manhattan_radius=2,
            block_builder=block_builder,
            substitution_builder=substitution_builder,
            observables=fg.observables,
            num_workers=30,
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
            plot_observable_as_inset(ax, zx_graph, fg.observables[i])
            ax.grid(axis="both")
            ax.legend()
            ax.loglog()
            ax.set_title(f"{style.upper()} Logical 3-CNOT Error Rate")
            fig.savefig(
                ASSETS_FOLDER
                / f"{model_name}_result_simulation_run_{run}_observable_{i}.png"
            )


def main():
    generate_graphs("STANDARD")


if __name__ == "__main__":
    main()
