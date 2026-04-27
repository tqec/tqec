import stim
from tqec import NoiseModel, compile_block_graph, BlockGraph
from tqec.computation.block_graph import BlockGraph
from tqec.computation.cube import ZXCube
from tqec.utils.position import Position3D
from tqec.compile.convention import FIXED_BULK_CONVENTION

if __name__ == "__main__":
    g = BlockGraph()

    # FIX: Use ZXCube.from_str() with correct 3-char strings
    # ZXZ and XZX are the correct opposing cube types for a temporal Hadamard
    n0 = g.add_cube(Position3D(0, 0, 0), ZXCube.from_str("ZXZ"), "")
    n1 = g.add_cube(Position3D(0, 0, 1), ZXCube.from_str("XZX"), "")  # Z+1 = temporal
    g.add_pipe(n0, n1)

    correlation_surfaces = g.find_correlation_surfaces()
    g.view_as_html(
        write_html_filepath="temporal_hadamard.html",
        pop_faces_at_directions=("-Y",),
        show_correlation_surface=correlation_surfaces[0],
    )

    compiled_g = compile_block_graph(
        block_graph=g,
        observables=[correlation_surfaces[0]],
        convention=FIXED_BULK_CONVENTION,
    )

    k = 1
    with open("temporal_hadamard.crumble", "w") as f:
        f.write(compiled_g.generate_crumble_url(k=k, add_polygons=True))
    print("✅ Crumble URL written.")

    noise_model = NoiseModel.uniform_depolarizing(1e-3)
    circuit = compiled_g.generate_stim_circuit(k, noise_model=noise_model)

    with open("temporal_hadamard.stim", "w") as f:
        f.write(str(circuit))
    print("✅ Circuit saved to temporal_hadamard.stim")

    try:
        circuit.detector_error_model(decompose_errors=True)
        print("✅ Detector error model valid")
    except Exception as e:
        print(f"❌ Detector error model failed: {e}")
        raise SystemExit(1)

    shortest_logical_error = circuit.shortest_graphlike_error(
        ignore_ungraphlike_errors=True,
        canonicalize_circuit_errors=True
    )

    assert len(shortest_logical_error) == 2 * k + 1, (
        f"Distance {len(shortest_logical_error)} does not match expected {2*k+1}!"
    )
    print(f"✅ Success! Shortest logical error: {len(shortest_logical_error)} faults (expected {2*k+1})")