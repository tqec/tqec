import gen
import pytest
import stim

from tqec.compile.specs.library.generators.y_basis_init_meas import (
    make_xtop_qubit_patch,
    make_y_basis_initialization_chunks,
    make_y_basis_measurement_chunks,
    standard_surface_code_chunk,
)


def make_y_memory_experiment(
    distance: int, memory_rounds: int, padding_rounds: int, noise_strength: float | None = None
) -> stim.Circuit:
    y_init_chunks = make_y_basis_initialization_chunks(distance, padding_rounds)
    y_meas_chunks = make_y_basis_measurement_chunks(distance, padding_rounds)

    qubit_obs = gen.PauliMap(
        {
            0: "Y",
            **{q: "Z" for q in range(1, distance)},
            **{q * 1j: "X" for q in range(1, distance)},
        }
    )
    memory_patch = make_xtop_qubit_patch(distance)
    memory_round = standard_surface_code_chunk(memory_patch, obs=qubit_obs)
    chunks: list[gen.Chunk | gen.ChunkLoop] = [
        *y_init_chunks,
        memory_round.with_repetitions(memory_rounds),
        *y_meas_chunks,
    ]
    compiler = gen.ChunkCompiler()
    for chunk in chunks:
        chunk.verify()
        compiler.append(chunk)
    circuit = compiler.finish_circuit()
    if noise_strength is not None:
        noise_model = gen.NoiseModel.uniform_depolarizing(noise_strength)
        circuit = noise_model.noisy_circuit(circuit)
    return circuit


@pytest.mark.parametrize("distance", range(2, 10))
def test_make_y_memory_experiment(distance: int):
    circuit = make_y_memory_experiment(
        distance, memory_rounds=5, padding_rounds=distance // 2, noise_strength=1e-3
    )
    dem = circuit.detector_error_model(
        decompose_errors=True, block_decomposition_from_introducing_remnant_edges=True
    )
    assert dem is not None

    actual_distance = len(circuit.shortest_graphlike_error())
    expected_distance = distance
    assert actual_distance == expected_distance
