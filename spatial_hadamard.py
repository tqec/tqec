import stim
from tqec import NoiseModel, compile_block_graph
from tqec.compile.convention import FIXED_BOUNDARY_CONVENTION, FIXED_BULK_CONVENTION
from tqec.computation.block_graph import BlockGraph
from tqec.utils.position import Position3D

if __name__ == "__main__":
    g = BlockGraph()
    n0 = g.add_cube(Position3D(0, 0, 0), "ZZX", "")
    n1 = g.add_cube(Position3D(0, 1, 0), "XXZ", "")
    g.add_pipe(n0, n1)

    correlation_surfaces = g.find_correlation_surfaces()
    g.view_as_html(
        write_html_filepath="spatial_hadamard.html",
        pop_faces_at_directions=("-Y",),
        show_correlation_surface=correlation_surfaces[0],
    )

    # Use only the FIRST correlation surface for a single observable
    compiled_g = compile_block_graph(
        block_graph=g,
        observables=[correlation_surfaces[0]],  # <-- FIX 1: only one observable
        convention=FIXED_BULK_CONVENTION,        # <-- FIX 2: back to BULK convention
    )

    k = 1
    with open("url_old_fxd_bdy.crumble", "w") as f:
        f.write(compiled_g.generate_crumble_url(k=k, add_polygons=True))

    noise_model = NoiseModel.uniform_depolarizing(1e-3)
    circuit = compiled_g.generate_stim_circuit(k, noise_model=noise_model)

    # FIX 3: Save circuit to file so we can inspect if needed
    with open("spatial_hadamard.stim", "w") as f:
        f.write(str(circuit))
    print("✅ Circuit generated and saved to spatial_hadamard.stim")

    # FIX 4: Verify circuit is valid before shortest_graphlike_error
    try:
        circuit.detector_error_model(decompose_errors=True)
        print("✅ Detector error model valid")
    except Exception as e:
        print(f"❌ Detector error model failed: {e}")
        print("   Inspect spatial_hadamard.stim and the crumble URL for issues.")
        raise SystemExit(1)

    shortest_logical_error = circuit.shortest_graphlike_error(
        ignore_ungraphlike_errors=True,
        canonicalize_circuit_errors=True
    )

    assert len(shortest_logical_error) == 2 * k + 1, (
        f"Circuit distance {len(shortest_logical_error)} does not match expected {2*k+1}!"
    )
    print(f"✅ Success! Shortest logical error has {len(shortest_logical_error)} faults (expected {2*k+1})")