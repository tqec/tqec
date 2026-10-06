"""Logical Memory
==============

This example demonstrates the simplest (trivial) form of computation:
logical memory. More specifically, a logical qubit with distance ``d``
remains idle for ``d`` error correction cycles
[<cite data-footcite-t="Acharya_2024"></cite>].

Construction
------------

A memory experiment can be represented with a single cube. The color of
the cube determines the spatial/temporal boundary types.

``tqec`` provides builtin functions in ``tqec.gallery.memory`` to
construct it.
"""

# ruff: noqa: E402

from tqec import Basis
from tqec.gallery import memory

graph = memory(Basis.Z)
# %%

graph.view_as_html()

# %%
# The memory experiment preserves its logical observable through time.

correlation_surfaces = graph.find_correlation_surfaces()
# %%

graph.view_as_html(
    pop_faces_at_directions=("-Y",),
    show_correlation_surface=correlation_surfaces[0],
)

# %%
# Circuit
# -------
#
# You can download the circuit for a ``d=3`` logical ``Z`` memory
# experiment from
# :download:`here <../media/gallery/memory/circuit.stim>`, or generate
# it with the code below. You can also open the circuit in
# `Crumble <https://algassert.com/crumble>`_.
#
# .. note::
#
#    Note that the syndrome extraction circuits used here are of depth
#    7 because we use an extra layer of two-qubit gates to align with
#    the potential spatial cubes. The depth can be reduced to 6 with
#    some post-processing on the circuit.

from tqec import NoiseModel, compile_block_graph

compiled_graph = compile_block_graph(graph)
circuit = compiled_graph.generate_stim_circuit(
    k=1, noise_model=NoiseModel.uniform_depolarizing(p=0.001)
)

# %%
# Simulation
# ----------
#
# Here we show the simulation results of both ``Z``-basis and ``X``-basis
# memory experiments under the **uniform depolarizing** noise model.
#
# The full code used for the simulation is shown below.

from multiprocessing import cpu_count
from pathlib import Path

import matplotlib.pyplot as plt
import numpy
import sinter

from tqec.gallery.memory import memory
from tqec.simulation.plotting.inset import plot_observable_as_inset
from tqec.simulation.simulation import start_simulation_using_sinter
from tqec.utils.enums import Basis


def generate_graphs(support_observable_basis: Basis) -> None:
    """Generate the logical error-rate graphs corresponding to the provided basis."""
    block_graph = memory(support_observable_basis)
    zx_graph = block_graph.to_zx_graph()

    correlation_surfaces = block_graph.find_correlation_surfaces()

    stats = start_simulation_using_sinter(
        block_graph,
        range(1, 4),
        list(numpy.logspace(-4, -1, 10)),
        NoiseModel.uniform_depolarizing,
        manhattan_radius=2,
        observables=correlation_surfaces,
        num_workers=cpu_count(),
        max_shots=1_000_000,
        max_errors=5_000,
        decoders=["pymatching"],
        # note that save_resume_filepath and database_path can help reduce the time taken
        # by the simulation after the database and result statistics have been saved to
        # the chosen path
        save_resume_filepath=Path(
            f"../_examples_database/memory_stats_{support_observable_basis.value}.csv"
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
        plot_observable_as_inset(ax, zx_graph, correlation_surfaces[i])
        ax.grid(axis="both")
        ax.legend()
        ax.loglog()
        ax.set_title("Logical Memory Error Rate")
        ax.set_xlabel("Physical Error Rate")
        ax.set_ylabel("Logical Error Rate(per round)")


# %%
# Z Basis
# -------
#
# Generate the logical memory error-rate graphs for the ``Z`` basis.

generate_graphs(Basis.Z)

# %%
# X Basis
# -------
#
# Generate the logical memory error-rate graphs for the ``X`` basis.

generate_graphs(Basis.X)

# %%
# References
# ----------
#
# .. footbibliography::
