"""
In this file, we import, visualise, and compare simulations for two CNOT models exported from SketchUp as .dae (COLLADA) files.
One of the models is unrotated, the other is rotated 90 degrees along the 'x' axis.

"""

# IMPORTS
import matplotlib.pyplot as plt
import numpy as np
import sinter
from multiprocessing import cpu_count
from tqec import BlockGraph, compile_block_graph
from tqec.utils.noise_model import NoiseModel
from tqec.simulation.simulation import start_simulation_using_sinter
from tqec.simulation.plotting.inset import plot_observable_as_inset


# IMPORT / CONSTRUCT LOGICAL COMPUTATIONS
# To use the computation with the tqec library, you need to import it using tqec.BlockGraph
def write_to_html(filename, html):
    with open(f"{filename}.html", "w") as f:
        f.write(str(html))
        f.close()


block_graph = BlockGraph.from_dae_file("../assets/logical_cnot.dae")
write_to_html("logical_cnot", block_graph.view_as_html())

block_graph_rotated = BlockGraph.from_dae_file("../assets/cnot_rotate_x_90.dae")
write_to_html("logical_cnot_rotated", block_graph_rotated.view_as_html())


# CHOOSE OBSERVABLES OF INTEREST
# The tqec library can automatically search for valid observables in the imported computation.
# To get a list of all the valid observables, you can use the following code
correlation_surfaces = block_graph.find_correlation_surfaces()
correlation_surfaces_rotated = block_graph_rotated.find_correlation_surfaces()


# COMPILE & EXPORT COMPUTATION
# to get a stim.Circuit instance, the computation first need to be compiled.
compiled_computation = compile_block_graph(
    block_graph, observables=[correlation_surfaces[1]]
)
compiled_computation_rotated = compile_block_graph(
    block_graph, observables=[correlation_surfaces[1]]
)


# GENERATE STIM CIRCUIT OF TARGET CODE DISTANCE
circuit = compiled_computation.generate_stim_circuit(
    # k = (d-1)/2 is the scale factor. Large values are computationally intensive.
    k=2,
    # The noise applied and noise levels can be changed.
    noise_model=NoiseModel.uniform_depolarizing(0.001),
)

circuit_rotated = compiled_computation_rotated.generate_stim_circuit(
    # k = (d-1)/2 is the scale factor. Large values are computationally intensive.
    k=2,
    # The noise applied and noise levels can be changed.
    noise_model=NoiseModel.uniform_depolarizing(0.001),
)


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

stats_rotated = start_simulation_using_sinter(
    block_graph,
    ks=range(1, 4),  # k values for the code distance
    ps=list(np.logspace(-4, -1, 10)),  # error rates
    noise_model_factory=NoiseModel.uniform_depolarizing,  # noise model
    manhattan_radius=2,  # parameter for automatic detector computation
    observables=[correlation_surfaces_rotated[1]],  # observable of interest
    decoders=["pymatching"],
    num_workers=cpu_count(),
    max_shots=10_000_000,
    max_errors=5_000,
    print_progress=True,
)

# SIMULATE & PLOT RESULTS
# Simulation results can be plotted with matplolib using the plot_simulation_results.

# UNROTATED
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
ax.set_title("Logical CNOT Error Rate")
fig.savefig(f"logical_cnot_observable_{1}.png")


# ROTATED
zx_graph = block_graph.to_zx_graph()
fig, ax = plt.subplots()

sinter.plot_error_rate(
    ax=ax,
    stats=next(stats_rotated),
    x_func=lambda stat: stat.json_metadata["p"],
    group_func=lambda stat: stat.json_metadata["d"],
)

plot_observable_as_inset(ax, zx_graph, correlation_surfaces_rotated[1])
ax.grid(axis="both")
ax.legend()
ax.loglog()
ax.set_title("Rotated logical CNOT Error Rate")
fig.savefig(f"logical_cnot_rotated_observable_{1}.png")
