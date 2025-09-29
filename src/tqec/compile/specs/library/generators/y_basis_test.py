import itertools
from typing import Literal

import gen
import pytest
import stim

from tqec.compile.specs.library.generators.y_basis import (
    make_qubit_patch,
    make_y_basis_initialization_chunks,
    make_y_basis_measurement_chunks,
    standard_surface_code_chunk,
)
from tqec.utils.enums import Basis


def make_y_memory_experiment(
    distance: int,
    top_boundary_basis: Basis,
    convention: Literal["fixed_bulk", "fixed_boundary"],
    memory_rounds: int,
    padding_rounds: int,
    noise_strength: float | None = None,
) -> stim.Circuit:
    y_init_chunks = make_y_basis_initialization_chunks(
        distance, top_boundary_basis, convention, padding_rounds
    )
    y_meas_chunks = make_y_basis_measurement_chunks(
        distance, top_boundary_basis, convention, padding_rounds
    )

    half_d = distance // 2
    center_dq = complex(half_d, half_d)
    qubit_obs = gen.PauliMap(
        {
            center_dq: "Y",
            **{
                complex(q, half_d): str(top_boundary_basis.flipped())
                for q in range(distance)
                if q != half_d
            },
            **{complex(half_d, q): str(top_boundary_basis) for q in range(distance) if q != half_d},
        }
    )
    memory_patch = make_qubit_patch(distance, top_boundary_basis, convention)
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


@pytest.mark.parametrize(
    "distance, memory_rounds, top_boundary_basis, convention",
    itertools.product(
        [3, 5],
        [0, 1],
        [Basis.X, Basis.Z],
        ["fixed_bulk", "fixed_boundary"],
    ),
)
def test_make_y_memory_experiment(
    distance: int,
    memory_rounds: int,
    top_boundary_basis: Basis,
    convention: Literal["fixed_bulk", "fixed_boundary"],
) -> None:
    circuit = make_y_memory_experiment(
        distance,
        top_boundary_basis,
        convention,
        memory_rounds,
        padding_rounds=distance // 2,
        noise_strength=1e-3,
    )
    dem = circuit.detector_error_model(
        decompose_errors=True, block_decomposition_from_introducing_remnant_edges=True
    )
    assert dem is not None

    actual_distance = len(circuit.shortest_graphlike_error())
    expected_distance = distance
    assert actual_distance == expected_distance
