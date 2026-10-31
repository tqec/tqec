#!/usr/bin/env python

"""Steane Encoding
===============

This example demonstrates Steane encoding using TQEC.

This notebook demonstrates the construction and simulation of a logical Steane encoder
circuit. The Steane code was introduced in [:footcite:t:`Steane_1996`]. In the surface
code, this logical circuit can be used to prepare the magic state for a logical $S$
gate [:footcite:t:`Fowler_2012`].

Construction
------------

``tqec`` provides builtin functions in ``tqec.gallery.steane_encoding`` to construct it.
"""

from multiprocessing import cpu_count
from pathlib import Path

import matplotlib.pyplot as plt
import numpy
import sinter

from tqec import Basis, NoiseModel, compile_block_graph
from tqec.gallery import steane_encoding
from tqec.simulation.plotting.inset import plot_observable_as_inset
from tqec.simulation.simulation import start_simulation_using_sinter

# %%
graph = steane_encoding()
graph.view_as_html()

# %%
# We can use the `find_correlation_surfaces()` method to identify all correlation surfaces,
# and then visualize them using the `view_as_html()` method. In this case, there are a total
# of seven correlation surfaces. For simplicity, only two are shown here.

correlation_surfaces = graph.find_correlation_surfaces()

# %%
graph.view_as_html(
    pop_faces_at_directions=("-Y",),
    show_correlation_surface=correlation_surfaces[0],
)

# %%
graph.view_as_html(
    pop_faces_at_directions=("-Y",),
    show_correlation_surface=correlation_surfaces[1],
)

# %%
# Circuit
# -------
# Here we show an example circuit of Steane encoding circuit with :math:`d=3` that
# is initialized and measured in the :math:`X` basis. The circuit can be downloaded
# :download:`here <../media/gallery/steane_encoding/circuit.stim>` or viewed
# in `Crumble <https://algassert.com/crumble>`_.

graph_x = steane_encoding(Basis.X)
compiled_graph = compile_block_graph(graph_x)
circuit = compiled_graph.generate_stim_circuit(
    k=1, noise_model=NoiseModel.uniform_depolarizing(p=0.001)
)

# %%
# Simulation
# ----------
# Here we show the simulation results for all seven observables under a uniform depolarizing
# noise model.


def generate_graphs(support_observable_basis: Basis) -> None:
    """Generate the logical error-rate graphs corresponding to the provided basis."""
    block_graph = steane_encoding(support_observable_basis)
    zx_graph = block_graph.to_zx_graph()

    surfaces = block_graph.find_correlation_surfaces()

    stats = start_simulation_using_sinter(
        block_graph,
        range(1, 4),
        list(numpy.logspace(-4, -1, 10)),
        NoiseModel.uniform_depolarizing,
        manhattan_radius=2,
        observables=surfaces,
        num_workers=cpu_count(),
        max_shots=1_000_000,
        max_errors=5_000,
        decoders=["pymatching"],
        save_resume_filepath=Path(
            f"../_examples_database/steane_stats_{support_observable_basis.value}.csv"
        ),
        database_path=Path("../_examples_database/database.pkl"),
    )

    for i, stat in enumerate(stats):
        _, ax = plt.subplots()
        sinter.plot_error_rate(
            ax=ax,
            stats=stat,
            x_func=lambda stat: stat.json_metadata["p"],
            failure_units_per_shot_func=lambda stat: stat.json_metadata["d"],
            group_func=lambda stat: stat.json_metadata["d"],
        )
        plot_observable_as_inset(ax, zx_graph, surfaces[i])
        ax.grid(axis="both")
        ax.legend()
        ax.loglog()
        ax.set_title("Steane Encoding Error Rate")
        ax.set_xlabel("Physical Error Rate")
        ax.set_ylabel("Logical Error Rate(per round)")


# %%
# Z Basis and X Basis Simulations

if __name__ == "__main__":
    generate_graphs(Basis.Z)
    generate_graphs(Basis.X)

# %%
# References
# ----------
# .. footbibliography::
