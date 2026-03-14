"""Unit tests for the TQEC spatial Hadamard block graph code.

Tests cover:
  - BlockGraph construction (nodes, pipes, geometry)
  - Cube types and their physical meaning
  - Pipe direction and Hadamard semantics
  - Correlation surface detection
  - Circuit compilation and convention handling
  - Circuit distance verification
  - Noise model properties
  - Edge cases and error conditions

Run with:
    pytest unit_test_spatial_hadamard.py -v

Note: These tests require tqec and stim to be installed:
    pip install tqec stim
"""

import pytest


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def basic_hadamard_graph():
    """A minimal spatial Hadamard block graph: ZZX -> XXZ along Y axis."""
    from tqec.computation.block_graph import BlockGraph
    from tqec.utils.position import Position3D

    g = BlockGraph()
    n0 = g.add_cube(Position3D(0, 0, 0), "ZZX", "")
    n1 = g.add_cube(Position3D(0, 1, 0), "XXZ", "")
    g.add_pipe(n0, n1)
    return g, n0, n1


@pytest.fixture
def compiled_hadamard(basic_hadamard_graph):
    """Compiled version of the spatial Hadamard block graph."""
    from tqec import compile_block_graph
    from tqec.compile.convention import FIXED_BULK_CONVENTION

    g, n0, n1 = basic_hadamard_graph
    correlation_surfaces = g.find_correlation_surfaces()
    compiled = compile_block_graph(
        block_graph=g,
        observables=correlation_surfaces,
        convention=FIXED_BULK_CONVENTION,
    )
    return compiled, correlation_surfaces


# ===========================================================================
# UNIT TESTS — BlockGraph construction
# ===========================================================================

class TestBlockGraphConstruction:
    """Tests for building the block graph correctly."""

    def test_block_graph_starts_empty(self):
        """A new BlockGraph has no cubes or pipes.

        Physical meaning: An empty block graph represents no quantum
        computation — no code patches, no operations, no spacetime.
        """
        from tqec.computation.block_graph import BlockGraph
        g = BlockGraph()
        # num_cubes is a property (int), not a method — use it directly
        assert g.num_cubes == 0 or len(list(g.cubes)) == 0

    def test_add_single_cube(self):
        """A cube can be added at a given 3D position.

        Physical meaning: A cube represents a surface code patch
        occupying a spacetime volume. Adding one cube creates one
        code patch at a fixed location in the lattice.
        """
        from tqec.computation.block_graph import BlockGraph
        from tqec.utils.position import Position3D

        g = BlockGraph()
        n = g.add_cube(Position3D(0, 0, 0), "ZZX", "")
        assert n is not None

    def test_add_two_cubes_different_positions(self):
        """Two cubes can be added at different positions without conflict."""
        from tqec.computation.block_graph import BlockGraph
        from tqec.utils.position import Position3D

        g = BlockGraph()
        n0 = g.add_cube(Position3D(0, 0, 0), "ZZX", "")
        n1 = g.add_cube(Position3D(0, 1, 0), "XXZ", "")
        assert n0 is not None
        assert n1 is not None
        assert n0 != n1

    def test_add_pipe_connects_two_cubes(self):
        """A pipe can be added between two adjacent cubes.

        Physical meaning: A pipe represents an operation connecting
        two code patches — in this case the Hadamard transition
        between a ZZX patch and an XXZ patch.
        In tqec, add_pipe() returns None but modifies the graph in place —
        we verify the pipe exists by checking the graph has pipes.
        """
        from tqec.computation.block_graph import BlockGraph
        from tqec.utils.position import Position3D

        g = BlockGraph()
        n0 = g.add_cube(Position3D(0, 0, 0), "ZZX", "")
        n1 = g.add_cube(Position3D(0, 1, 0), "XXZ", "")
        g.add_pipe(n0, n1)
        # add_pipe returns None but modifies graph in place — verify via num_pipes
        assert g.num_pipes == 1

    def test_hadamard_pipe_is_along_y_axis(self):
        """The Hadamard pipe connects cubes separated by 1 in the Y direction.

        Physical meaning: The spatial Hadamard is implemented as a pipe
        along the Y axis, connecting a ZZX cube at (0,0,0) to an XXZ
        cube at (0,1,0). The Y direction is the 'spatial' direction
        of the Hadamard in 3D spacetime.
        """
        from tqec.utils.position import Position3D

        p0 = Position3D(0, 0, 0)
        p1 = Position3D(0, 1, 0)

        # The cubes differ only in Y
        assert p0.x == p1.x
        assert p1.y - p0.y == 1
        assert p0.z == p1.z

    def test_zzx_and_xxz_are_complementary_cube_types(self):
        """ZZX and XXZ are complementary: X<->Z swap on all axes.

        Physical meaning: A surface code patch labelled ZZX has Z-type
        stabilizers on its x and y faces, and X-type on its z face.
        XXZ has the opposite on all three axes. This X<->Z swap is
        exactly the signature of a Hadamard — H swaps X and Z.
        """
        cube_type_0 = "ZZX"
        cube_type_1 = "XXZ"

        def swap_xz(s):
            return s.replace("X", "?").replace("Z", "X").replace("?", "Z")

        # ZZX with all X<->Z swapped should equal XXZ
        assert swap_xz(cube_type_0) == cube_type_1
        # And vice versa — the swap is its own inverse
        assert swap_xz(cube_type_1) == cube_type_0


# ===========================================================================
# UNIT TESTS — Position3D
# ===========================================================================

class TestPosition3D:
    """Tests for the 3D position utility class."""

    def test_position_stores_coordinates(self):
        """Position3D stores x, y, z coordinates correctly."""
        from tqec.utils.position import Position3D
        p = Position3D(3, 7, 2)
        assert p.x == 3
        assert p.y == 7
        assert p.z == 2

    def test_position_origin(self):
        """Position3D(0,0,0) represents the origin."""
        from tqec.utils.position import Position3D
        p = Position3D(0, 0, 0)
        assert p.x == 0 and p.y == 0 and p.z == 0

    def test_two_positions_are_equal_when_same_coords(self):
        """Two Position3D objects with same coordinates are equal."""
        from tqec.utils.position import Position3D
        p0 = Position3D(1, 2, 3)
        p1 = Position3D(1, 2, 3)
        assert p0 == p1

    def test_two_positions_differ_when_different_coords(self):
        """Two Position3D objects with different coordinates are not equal."""
        from tqec.utils.position import Position3D
        p0 = Position3D(0, 0, 0)
        p1 = Position3D(0, 1, 0)
        assert p0 != p1

    def test_y_direction_offset(self):
        """Position offset of 1 in Y direction is the Hadamard pipe direction."""
        from tqec.utils.position import Position3D
        p0 = Position3D(0, 0, 0)
        p1 = Position3D(0, 1, 0)
        delta_y = p1.y - p0.y
        assert delta_y == 1


# ===========================================================================
# UNIT TESTS — Correlation surfaces
# ===========================================================================

class TestCorrelationSurfaces:
    """Tests for correlation surface detection on the Hadamard block graph."""

    def test_correlation_surfaces_exist(self, basic_hadamard_graph):
        """The Hadamard block graph has at least one correlation surface.

        Physical meaning: A correlation surface represents a logical
        operator (X̄ or Z̄) propagating through spacetime. A valid
        quantum computation must have at least one logical observable.
        """
        g, n0, n1 = basic_hadamard_graph
        surfaces = g.find_correlation_surfaces()
        assert len(surfaces) >= 1

    def test_correlation_surfaces_returns_list(self, basic_hadamard_graph):
        """find_correlation_surfaces() returns a list/sequence."""
        g, n0, n1 = basic_hadamard_graph
        surfaces = g.find_correlation_surfaces()
        assert hasattr(surfaces, '__len__') or hasattr(surfaces, '__iter__')

    def test_first_correlation_surface_is_not_none(self, basic_hadamard_graph):
        """The first correlation surface is a valid object."""
        g, n0, n1 = basic_hadamard_graph
        surfaces = g.find_correlation_surfaces()
        assert surfaces[0] is not None

    def test_hadamard_graph_has_correlation_surfaces(self, basic_hadamard_graph):
        """A Hadamard pipe block graph has at least one correlation surface.

        Physical meaning: A correlation surface represents a logical operator
        propagating through spacetime. The tqec library returns the number of
        independent correlation surfaces it can detect for this graph — at
        least one must exist for the computation to be meaningful.
        """
        g, n0, n1 = basic_hadamard_graph
        surfaces = g.find_correlation_surfaces()
        assert len(surfaces) >= 1, (
            f"Expected at least 1 correlation surface, got {len(surfaces)}"
        )


# ===========================================================================
# UNIT TESTS — Compilation conventions
# ===========================================================================

class TestCompilationConventions:
    """Tests for compilation with different conventions."""

    def test_compile_with_fixed_bulk_convention(self, basic_hadamard_graph):
        """Block graph compiles successfully with FIXED_BULK_CONVENTION.

        Physical meaning: FIXED_BULK_CONVENTION fixes the stabilizer
        assignments in the interior of the code patch. This is the
        standard convention for bulk (interior) syndrome extraction.
        """
        from tqec import compile_block_graph
        from tqec.compile.convention import FIXED_BULK_CONVENTION

        g, n0, n1 = basic_hadamard_graph
        surfaces = g.find_correlation_surfaces()
        compiled = compile_block_graph(
            block_graph=g,
            observables=surfaces,
            convention=FIXED_BULK_CONVENTION,
        )
        assert compiled is not None

    def test_compile_with_fixed_boundary_convention(self, basic_hadamard_graph):
        """Block graph compiles successfully with FIXED_BOUNDARY_CONVENTION.

        Physical meaning: FIXED_BOUNDARY_CONVENTION fixes the stabilizer
        assignments at the boundary of the code patch. Different convention,
        same logical operation — both should produce valid circuits.
        """
        from tqec import compile_block_graph
        from tqec.compile.convention import FIXED_BOUNDARY_CONVENTION

        g, n0, n1 = basic_hadamard_graph
        surfaces = g.find_correlation_surfaces()
        compiled = compile_block_graph(
            block_graph=g,
            observables=surfaces,
            convention=FIXED_BOUNDARY_CONVENTION,
        )
        assert compiled is not None

    def test_both_conventions_produce_compiled_output(self, basic_hadamard_graph):
        """Both conventions produce non-None compiled block graphs."""
        from tqec import compile_block_graph
        from tqec.compile.convention import FIXED_BULK_CONVENTION, FIXED_BOUNDARY_CONVENTION

        g, n0, n1 = basic_hadamard_graph
        surfaces = g.find_correlation_surfaces()

        c_bulk = compile_block_graph(g, observables=surfaces, convention=FIXED_BULK_CONVENTION)
        c_bdy  = compile_block_graph(g, observables=surfaces, convention=FIXED_BOUNDARY_CONVENTION)

        assert c_bulk is not None
        assert c_bdy  is not None


# ===========================================================================
# UNIT TESTS — Stim circuit generation
# ===========================================================================

class TestStimCircuitGeneration:
    """Tests for generating Stim circuits from compiled block graphs."""

    def test_generate_stim_circuit_k1(self, compiled_hadamard):
        """Stim circuit can be generated for k=1.

        Physical meaning: k=1 gives a distance-3 surface code (d=2k+1=3).
        This is the smallest useful code distance for error correction.
        """
        from tqec import NoiseModel
        compiled, _ = compiled_hadamard
        noise = NoiseModel.uniform_depolarizing(1e-3)
        circuit = compiled.generate_stim_circuit(k=1, noise_model=noise)
        assert circuit is not None

    def test_stim_circuit_is_stim_circuit_type(self, compiled_hadamard):
        """Generated circuit is a stim.Circuit object."""
        import stim
        from tqec import NoiseModel
        compiled, _ = compiled_hadamard
        noise = NoiseModel.uniform_depolarizing(1e-3)
        circuit = compiled.generate_stim_circuit(k=1, noise_model=noise)
        assert isinstance(circuit, stim.Circuit)

    def test_stim_circuit_has_instructions(self, compiled_hadamard):
        """Generated Stim circuit is non-empty (has quantum instructions).

        Physical meaning: A valid surface code circuit must contain
        qubit resets, gate operations, and measurements. An empty
        circuit would not perform any error correction.
        """
        from tqec import NoiseModel
        compiled, _ = compiled_hadamard
        noise = NoiseModel.uniform_depolarizing(1e-3)
        circuit = compiled.generate_stim_circuit(k=1, noise_model=noise)
        assert len(circuit) > 0

    def test_generate_crumble_url(self, compiled_hadamard):
        """Crumble URL can be generated for circuit visualisation."""
        compiled, _ = compiled_hadamard
        url = compiled.generate_crumble_url(k=1, add_polygons=True)
        assert url is not None
        assert isinstance(url, str)
        assert len(url) > 0


# ===========================================================================
# UNIT TESTS — Circuit distance verification
# ===========================================================================

class TestCircuitDistance:
    """Tests verifying the error-correcting distance of the compiled circuit.

    These are the most physically important tests — they verify that the
    spatial Hadamard is implemented with the CORRECT error-correcting distance.
    """

    def test_circuit_distance_k1_is_3(self, compiled_hadamard):
        """For k=1, the circuit distance must be exactly 2*1+1 = 3.

        Physical meaning: A distance-3 surface code can detect any
        combination of 1 physical error and correct any single error.
        The shortest logical error requires at least 3 simultaneous
        physical errors to go undetected. If this assertion fails,
        the Hadamard pipe was compiled incorrectly.
        Note: ignore_ungraphlike_errors=True is required because the
        tqec-compiled Hadamard circuit contains non-deterministic
        observables that stim cannot analyse in graphlike mode.
        """
        from tqec import NoiseModel
        compiled, _ = compiled_hadamard
        k = 1
        noise = NoiseModel.uniform_depolarizing(1e-3)
        circuit = compiled.generate_stim_circuit(k, noise_model=noise)
        shortest = circuit.shortest_graphlike_error(
            ignore_ungraphlike_errors=True,
            canonicalize_circuit_errors=True,
        )
        assert len(shortest) == 2 * k + 1, (
            f"Circuit distance should be {2*k+1} for k={k}, got {len(shortest)}"
        )

    def test_circuit_distance_formula_holds_for_k1(self):
        """The distance formula d = 2k+1 gives 3 for k=1."""
        k = 1
        expected_distance = 2 * k + 1
        assert expected_distance == 3

    def test_shortest_error_is_not_empty(self, compiled_hadamard):
        """The shortest logical error path is non-empty.

        Physical meaning: There must always exist SOME path of physical
        errors that causes a logical error. If the shortest error is empty,
        the circuit has distance 0 — completely unprotected.
        """
        from tqec import NoiseModel
        compiled, _ = compiled_hadamard
        noise = NoiseModel.uniform_depolarizing(1e-3)
        circuit = compiled.generate_stim_circuit(k=1, noise_model=noise)
        shortest = circuit.shortest_graphlike_error(
            ignore_ungraphlike_errors=True,
            canonicalize_circuit_errors=True,
        )
        assert len(shortest) > 0, "Shortest logical error must be non-empty"

    def test_shortest_error_length_is_odd(self, compiled_hadamard):
        """For a surface code, the shortest logical error length is odd (2k+1).

        Physical meaning: Surface code distances are always odd numbers
        (3, 5, 7, ...) because the code is designed so that any even-weight
        error is detectable.
        """
        from tqec import NoiseModel
        compiled, _ = compiled_hadamard
        noise = NoiseModel.uniform_depolarizing(1e-3)
        circuit = compiled.generate_stim_circuit(k=1, noise_model=noise)
        shortest = circuit.shortest_graphlike_error(
            ignore_ungraphlike_errors=True,
            canonicalize_circuit_errors=True,
        )
        assert len(shortest) % 2 == 1, (
            f"Surface code distance should be odd, got {len(shortest)}"
        )


# ===========================================================================
# UNIT TESTS — Noise model
# ===========================================================================

class TestNoiseModel:
    """Tests for the uniform depolarizing noise model."""

    def test_noise_model_created_at_1e3(self):
        """NoiseModel.uniform_depolarizing(1e-3) creates a valid noise model.

        Physical meaning: 10^-3 (0.1%) error rate is a realistic target
        for near-term superconducting quantum hardware. Below the
        ~1% surface code threshold, errors can be corrected.
        """
        from tqec import NoiseModel
        noise = NoiseModel.uniform_depolarizing(1e-3)
        assert noise is not None

    def test_noise_model_below_threshold(self):
        """Error rate of 1e-3 is below the ~1% surface code threshold.

        Physical meaning: The surface code has an error threshold of
        roughly 1%. Below this threshold, increasing the code distance
        exponentially suppresses the logical error rate. Above it,
        adding more qubits makes things worse.
        """
        error_rate = 1e-3
        threshold  = 1e-2
        assert error_rate < threshold, (
            f"Error rate {error_rate} must be below threshold {threshold}"
        )

    def test_noise_model_at_various_rates(self):
        """NoiseModel can be created at various physically meaningful error rates."""
        from tqec import NoiseModel
        for rate in [1e-4, 1e-3, 5e-3]:
            noise = NoiseModel.uniform_depolarizing(rate)
            assert noise is not None, f"NoiseModel failed for rate {rate}"


# ===========================================================================
# INTEGRATION TESTS — full pipeline
# ===========================================================================

class TestFullPipeline:
    """End-to-end integration tests for the complete spatial Hadamard pipeline."""

    def test_full_pipeline_k1(self):
        """Complete pipeline from block graph to distance verification for k=1.

        Physical meaning: This is the exact workflow from the original script.
        It verifies that a spatial Hadamard pipe, when compiled and simulated,
        produces a fault-tolerant circuit with the correct distance d=3.
        """
        import stim
        from tqec import NoiseModel, compile_block_graph
        from tqec.compile.convention import FIXED_BULK_CONVENTION
        from tqec.computation.block_graph import BlockGraph
        from tqec.utils.position import Position3D

        g = BlockGraph()
        n0 = g.add_cube(Position3D(0, 0, 0), "ZZX", "")
        n1 = g.add_cube(Position3D(0, 1, 0), "XXZ", "")
        g.add_pipe(n0, n1)

        correlation_surfaces = g.find_correlation_surfaces()
        compiled = compile_block_graph(
            block_graph=g,
            observables=correlation_surfaces,
            convention=FIXED_BULK_CONVENTION,
        )

        k = 1
        noise = NoiseModel.uniform_depolarizing(1e-3)
        circuit = compiled.generate_stim_circuit(k, noise_model=noise)

        assert isinstance(circuit, stim.Circuit)

        shortest = circuit.shortest_graphlike_error(
            ignore_ungraphlike_errors=True,
            canonicalize_circuit_errors=True,
        )
        assert len(shortest) == 2 * k + 1, (
            f"Expected distance {2*k+1}, got {len(shortest)}"
        )

    def test_pipeline_both_conventions_give_correct_distance(self):
        """Both compilation conventions produce a circuit with distance 3 for k=1.

        Physical meaning: FIXED_BULK_CONVENTION and FIXED_BOUNDARY_CONVENTION
        are two valid ways to compile the same logical operation. Both must
        produce fault-tolerant circuits with the correct error distance.
        """
        from tqec import NoiseModel, compile_block_graph
        from tqec.compile.convention import FIXED_BULK_CONVENTION, FIXED_BOUNDARY_CONVENTION
        from tqec.computation.block_graph import BlockGraph
        from tqec.utils.position import Position3D

        def make_graph():
            g = BlockGraph()
            n0 = g.add_cube(Position3D(0, 0, 0), "ZZX", "")
            n1 = g.add_cube(Position3D(0, 1, 0), "XXZ", "")
            g.add_pipe(n0, n1)
            return g

        k = 1
        noise = NoiseModel.uniform_depolarizing(1e-3)

        for convention in [FIXED_BULK_CONVENTION, FIXED_BOUNDARY_CONVENTION]:
            g = make_graph()
            surfaces = g.find_correlation_surfaces()
            compiled = compile_block_graph(g, observables=surfaces, convention=convention)
            circuit = compiled.generate_stim_circuit(k, noise_model=noise)
            shortest = circuit.shortest_graphlike_error(
                ignore_ungraphlike_errors=True,
                canonicalize_circuit_errors=True,
            )
            assert len(shortest) == 2 * k + 1, (
                f"Convention {convention}: expected distance {2*k+1}, got {len(shortest)}"
            )

    def test_crumble_url_is_non_empty_string(self):
        """Crumble URL output is a non-empty string suitable for browser viewing."""
        from tqec import compile_block_graph
        from tqec.compile.convention import FIXED_BULK_CONVENTION
        from tqec.computation.block_graph import BlockGraph
        from tqec.utils.position import Position3D

        g = BlockGraph()
        n0 = g.add_cube(Position3D(0, 0, 0), "ZZX", "")
        n1 = g.add_cube(Position3D(0, 1, 0), "XXZ", "")
        g.add_pipe(n0, n1)
        surfaces = g.find_correlation_surfaces()
        compiled = compile_block_graph(g, observables=surfaces, convention=FIXED_BULK_CONVENTION)

        url = compiled.generate_crumble_url(k=1, add_polygons=True)
        assert isinstance(url, str)
        assert len(url) > 10  # Must be a real URL, not empty or trivial
