#!/usr/bin/env python

"""Logical CNOT
============

This example demonstrates the construction and simulation of a logical CNOT gate using
lattice surgery.

CNOT
----

This notebook shows the construction and simulation results of the logical
CNOT gate between two logical qubits with lattice surgery.

Construction
------------

A logical CNOT between two logical qubits can be implemented with the help
of an ancilla qubit. It can be accomplished with the following construction.
"""

from multiprocessing import cpu_count
from pathlib import Path

import matplotlib.pyplot as plt
import numpy
import sinter

from tqec import Basis, NoiseModel, compile_block_graph
from tqec.gallery import cnot
from tqec.simulation.plotting.inset import plot_observable_as_inset
from tqec.simulation.simulation import start_simulation_using_sinter

# %%
graph = cnot()
graph.view_as_html()

# %%
# The logical CNOT has four independent stabilizer flow generators:
#
# * `XX -> XI`
# * `XI -> XX`
# * `ZI -> ZI`
# * `ZZ -> IZ`
#
# Here we show the correlation surfaces corresponding to these flows.

correlation_surfaces = graph.find_correlation_surfaces()
stab_to_surface = {s.external_stabilizer_on_graph(graph): s for s in correlation_surfaces}

# %%
# `XX -> XI`

graph.view_as_html(
    pop_faces_at_directions=("-Y",),
    show_correlation_surface=stab_to_surface["XXXI"],
)

# %%
# `XI -> XX`

graph.view_as_html(
    pop_faces_at_directions=("-Y",),
    show_correlation_surface=stab_to_surface["XIXX"],
)

# %%
# `ZI -> ZI`

graph.view_as_html(
    pop_faces_at_directions=("-Y",),
    show_correlation_surface=stab_to_surface["ZIZI"],
)

# %%
# `ZZ -> IZ`

graph.view_as_html(
    pop_faces_at_directions=("-Y",),
    show_correlation_surface=stab_to_surface["ZZIZ"],
)

# %%
# Example Circuit
# ---------------
# Here we show an example circuit of logical CNOT with :math:`d=3` surface code
# that is initialized and measured in the :math:`X` basis.

graph_x = cnot(Basis.X)
compiled_graph = compile_block_graph(graph_x)
circuit = compiled_graph.generate_stim_circuit(
    k=3,
    noise_model=NoiseModel.uniform_depolarizing(p=0.001),
)

print(circuit)

# %%
# Simulation
# ----------
# Here we show the simulation results for all four observables under a
# uniform depolarizing noise model.


def generate_graphs(support_observable_basis: Basis) -> None:
    """Generate logical error-rate graphs for the provided basis."""
    block_graph = cnot(support_observable_basis)
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
            f"../_examples_database/cnot_stats_{support_observable_basis.value}.csv"
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
        ax.set_title("Logical CNOT Error Rate")
        ax.set_xlabel("Physical Error Rate")
        ax.set_ylabel("Logical Error Rate(per round)")


# %%
# Z Basis and X Basis Simulations

if __name__ == "__main__":
    generate_graphs(Basis.Z)
    generate_graphs(Basis.X)

# %%
# .. note::
#     See :ref:`reading_error_plots` for help reading logical error-rate plots
#     like the ones above.
