r"""Logical S Gate
==============

This example demonstrates a logical S gate by gate teleportation. The Y basis
measurement is done inplace, as in :footcite:t:`Gidney_inplace_access_2024`.

Construction
------------

The S gate is teleported in two steps:

- an :math:`M_{ZZ}` measurement between the target qubit and an ancilla qubit
  initialized in the :math:`|+\rangle` state,
- a Y basis measurement of the ancilla qubit, done by a Y half cube (see
  :doc:`/user_guide/terminology`).

The target qubit carries the output, and the ancilla is consumed by the Y
measurement. ``tqec`` provides the builtin function ``tqec.gallery.s_gate_teleportation``
to construct it. The ``In`` port is at the bottom of the block graph and the ``Out``
port is at the top. With a basis argument, as here, the ports are closed, so each flow
is checked by a deterministic observable rather than teleporting an arbitrary state.
The short green block is the Y half cube. The ``X`` graph has two: the ancilla's
and the ``Out`` port.
"""

# ruff: noqa: E402

from tqec import PauliBasis
from tqec.gallery import s_gate_teleportation

graph = s_gate_teleportation(PauliBasis.X)
# %%

graph.view_as_html()

# %%
# Up to signs, the S gate maps :math:`X` to :math:`Y` and :math:`Z` to :math:`Z`.
# In this graph ``In`` is initialized in the :math:`X` basis and ``Out`` is closed
# with a Y half cube, which measures the output in the :math:`Y` basis. The
# correlation surface below shows :math:`X` at the input, at the bottom, and
# :math:`Y` at the output, at the top. It also reaches the ancilla's Y half cube,
# so that measurement outcome enters the observable.
#
# On the 3D view, the :math:`Y` part of a correlation surface is drawn as
# overlapping :math:`X` (red) and :math:`Z` (blue) surfaces. The inset in the plots
# below draws :math:`Y` in green.

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
# The code below generates the circuit for a ``d=3`` S gate and builds a link that opens
# the same circuit, without noise, in Crumble.

from IPython.display import HTML

from tqec import NoiseModel, compile_block_graph

compiled_graph = compile_block_graph(graph)
circuit = compiled_graph.generate_stim_circuit(
    k=1, noise_model=NoiseModel.uniform_depolarizing(p=0.001)
)
HTML(f'<a href="{compiled_graph.generate_crumble_url(k=1)}">Open the d=3 circuit in Crumble</a>')

# %%
# Simulation
# ----------
#
# Here we show the simulation results of the :math:`X \rightarrow Y` and
# :math:`Z \rightarrow Z` flows under the **uniform depolarizing** noise model. The
# observable of :math:`X \rightarrow Y` is ``XYY``: :math:`X` on ``In``, :math:`Y` on the
# ancilla and :math:`Y` on ``Out``. The observable of :math:`Z \rightarrow Z` is ``ZIZ``:
# the ancilla is not involved.

from multiprocessing import cpu_count
from pathlib import Path

import matplotlib.pyplot as plt
import numpy
import sinter

from tqec.simulation.plotting.inset import plot_observable_as_inset
from tqec.simulation.simulation import start_simulation_using_sinter


def generate_graphs(in_observable_basis: PauliBasis, flow: str) -> None:
    """Generate the logical error-rate graphs corresponding to the provided basis."""
    block_graph = s_gate_teleportation(in_observable_basis)
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
            f"../_examples_database/s_gate_stats_{in_observable_basis.value}.csv"
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
        ax.set_title(f"S gate: {flow}")
        ax.set_xlabel("Physical Error Rate")
        ax.set_ylabel("Logical Error Rate (per round)")


# %%
# :math:`X \rightarrow Y` and :math:`Z \rightarrow Z` Simulations

if __name__ == "__main__":
    generate_graphs(PauliBasis.X, "X -> Y (XYY)")
    generate_graphs(PauliBasis.Z, "Z -> Z (ZIZ)")

# %%
# .. note::
#     See :ref:`reading_error_plots` for help reading logical error-rate plots
#     like the ones above.

# %%
# References
# ----------
#
# .. footbibliography::
