from tqec import BlockGraph, NoiseModel, compile_block_graph
from tqec.compile.convention import FIXED_BOUNDARY_CONVENTION
from tqec.utils.position import Position3D

g = BlockGraph()

n0 = g.add_cube(Position3D(0, 0, 0), "ZZX")
n1 = g.add_cube(Position3D(1, 0, 0), "XZX")
n2 = g.add_cube(Position3D(-1, 0, 0), "XZX")
n3 = g.add_cube(Position3D(0, 1, 0), "ZXX")
n4 = g.add_cube(Position3D(0, -1, 0), "ZXX")

n5 = g.add_cube(Position3D(1, 0, 1), "Y")
n6 = g.add_cube(Position3D(-1, 0, 1), "Y")
n7 = g.add_cube(Position3D(0, 1, 1), "Y")
n8 = g.add_cube(Position3D(0, -1, 1), "Y")

g.add_pipe(n0, n1)
g.add_pipe(n0, n2)
g.add_pipe(n0, n3)
g.add_pipe(n0, n4)
g.add_pipe(n1, n5)
g.add_pipe(n2, n6)
g.add_pipe(n3, n7)
g.add_pipe(n4, n8)

correlation_surface = g.find_correlation_surfaces()[0]
g.view_as_html(
    "test.html", show_correlation_surface=correlation_surface, pop_faces_at_directions=("+Z", "-Y")
)

cg = compile_block_graph(g, observables=[correlation_surface], convention=FIXED_BOUNDARY_CONVENTION)
circuit = cg.generate_stim_circuit(k=3)

# circuit.to_file("sliding_annotated.stim")
noisy_circuit = NoiseModel.uniform_depolarizing(1e-3).noisy_circuit(circuit)
# noisy_circuit.detector_error_model().to_file("sliding.dem")
# explained = noisy_circuit.explain_detector_error_model_errors(
#     dem_filter=stim.DetectorErrorModel("error(0.001931182734310662227) D1 D3 D20 D22")
# )

# noisy_circuit.to_file("test2.stim")
# noisy_circuit.detector_error_model().to_file("test.dem")
# noisy_circuit.detector_error_model(
#     decompose_errors=True, block_decomposition_from_introducing_remnant_edges=True
# )
# errors = noisy_circuit.explain_detector_error_model_errors(
#     dem_filter=stim.DetectorErrorModel("error(6.669779853440971351e-05) D494 D604 D611 D640 D673")
# )
# print(errors[0])


logical_error = noisy_circuit.shortest_graphlike_error(
    ignore_ungraphlike_errors=False, canonicalize_circuit_errors=True
)
# html_str = gen.stim_circuit_html_viewer(noisy_circuit, known_error=explained)
# html_str = gen.stim_circuit_html_viewer(noisy_circuit, known_error=logical_error)
# with open("stim_circuit.html", "w") as f:
#     print(html_str, file=f)
print("Length of shortest graphlike error:", len(logical_error))


# SAVE_DIR = Path("results")
#
#
# def generate_graphs() -> None:
#     zx_graph = g.to_zx_graph()
#
#     stats = start_simulation_using_sinter(
#         g,
#         range(1, 4),
#         list(numpy.logspace(-4, -1, 10)),
#         NoiseModel.uniform_depolarizing,
#         manhattan_radius=2,
#         observables=[correlation_surface],
#         num_workers=cpu_count(),
#         max_shots=1_000_000,
#         max_errors=5_000,
#         decoders=["pymatching"],
#         print_progress=True,
#     )
#
#     for i, stat in enumerate(stats):
#         fig, ax = plt.subplots()
#         sinter.plot_error_rate(
#             ax=ax,
#             stats=stat,
#             x_func=lambda stat: stat.json_metadata["p"],
#             group_func=lambda stat: stat.json_metadata["d"],
#         )
#         plot_observable_as_inset(ax, zx_graph, correlation_surface)
#         ax.grid(axis="both")
#         ax.legend()
#         ax.loglog()
#         ax.set_title("Logical CNOT Error Rate")
#         ax.set_xlabel("Physical Error Rate")
#         ax.set_ylabel("Logical Error Rate")
#         fig.savefig(SAVE_DIR / f"ghz_result_observable_{i}.png")
#
#
# def main():
#     SAVE_DIR.mkdir(exist_ok=True)
#     generate_graphs()
#
#
# if __name__ == "__main__":
#     main()
