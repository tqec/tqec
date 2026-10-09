#!/usr/bin/env python

"""Logical Hadamard
=================

This example demonstrates the construction and simulation of a logical Hadamard gate using
lattice surgery.

Construction
------------

A logical Hadamard between an input and an output port is implemented by
stacking a ``ZXZ`` cube and an ``XZX`` cube along time. The temporal pipe
between them is a Hadamard pipe (``ZXOH``), which ``add_pipe`` infers from the
swapped wall bases. It maps the logical ``X`` observable at the input to the
logical ``Z`` observable at the output and vice versa.
"""

from tqec.gallery import h

# %%
graph = h()
graph.view_as_html()


# %%
# The logical Hadamard has two independent stabilizer flow generators:
#
# * ``X -> Z``
# * ``Z -> X``
#
# Here we show the correlation surfaces corresponding to these flows.

correlation_surfaces = graph.find_correlation_surfaces()
stab_to_surface = {s.external_stabilizer_on_graph(graph): s for s in correlation_surfaces}


# %%
# ``X -> Z``
# -----------

graph.view_as_html(
    pop_faces_at_directions=("-Y",),
    show_correlation_surface=stab_to_surface["XZ"],
)


# %%
# ``Z -> X``
# -----------

graph.view_as_html(
    pop_faces_at_directions=("-Y",),
    show_correlation_surface=stab_to_surface["ZX"],
)


# %%
# Example Circuit
# ---------------
#
# Here we show an example circuit of the logical Hadamard with :math:`d=7` surface
# code that is initialized in the :math:`X` basis and measured in the :math:`Z` basis.

from tqec import Basis, NoiseModel, compile_block_graph  # noqa: E402

graph = h(Basis.X)
compiled_graph = compile_block_graph(graph)
circuit = compiled_graph.generate_stim_circuit(
    k=3,
    noise_model=NoiseModel.uniform_depolarizing(p=0.001),
)

print(circuit)


# %%
# Simulation
# ----------
#
# Here we show the simulation results for both observables under a
# uniform depolarizing noise model.

from multiprocessing import cpu_count  # noqa: E402
from pathlib import Path  # noqa: E402

import matplotlib.pyplot as plt  # noqa: E402
import numpy  # noqa: E402
import sinter  # noqa: E402

from tqec.simulation.plotting.inset import plot_observable_as_inset  # noqa: E402
from tqec.simulation.simulation import start_simulation_using_sinter  # noqa: E402
from tqec.utils.enums import Basis  # noqa: E402


def generate_graphs(support_observable_basis: Basis) -> None:
    """Generate logical error-rate graphs for the provided basis."""
    block_graph = h(support_observable_basis)
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
        save_resume_filepath=Path(
            f"../_examples_database/h_stats_{support_observable_basis.value}.csv"
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
        ax.set_title("Logical Hadamard Error Rate")
        ax.set_xlabel("Physical Error Rate")
        ax.set_ylabel("Logical Error Rate(per round)")


# %%
# Z Basis
# -------

generate_graphs(Basis.Z)


# %%
# X Basis
# -------

generate_graphs(Basis.X)


# %%
# .. note::
#     See :ref:`reading_error_plots` for help reading logical error-rate plots
#     like the ones above.
