import pytest

from tqec.compile.blocks.block import Block
from tqec.compile.blocks.layers.atomic.plaquettes import PlaquetteLayer
from tqec.compile.blocks.layers.composed.repeated import RepeatedLayer
from tqec.compile.graph import TopologicalComputationGraph
from tqec.compile.specs.library.generators.memory import (
    get_memory_horizontal_boundary_plaquettes,
    get_memory_horizontal_boundary_raw_template,
    get_memory_qubit_plaquettes,
    get_memory_qubit_raw_template,
    get_memory_vertical_boundary_plaquettes,
    get_memory_vertical_boundary_raw_template,
)
from tqec.utils.enums import Basis
from tqec.utils.position import BlockPosition3D
from tqec.utils.scale import LinearFunction, PhysicalQubitScalable2D


@pytest.fixture(name="scalable_qubit_shape")
def scalable_qubit_shape_fixture() -> PhysicalQubitScalable2D:
    return PhysicalQubitScalable2D(LinearFunction(4, 5), LinearFunction(4, 5))


@pytest.fixture(name="XZZ")
def XZZ_fixture() -> Block:
    return Block(
        [
            PlaquetteLayer(
                get_memory_qubit_raw_template(),
                get_memory_qubit_plaquettes(reset=Basis.Z),
            ),
            RepeatedLayer(
                PlaquetteLayer(
                    get_memory_qubit_raw_template(), get_memory_qubit_plaquettes()
                ),
                repetitions=LinearFunction(2, -1),
            ),
            PlaquetteLayer(
                get_memory_qubit_raw_template(),
                get_memory_qubit_plaquettes(measurement=Basis.Z),
            ),
        ]
    )


@pytest.fixture(name="XZO")
def XZO_fixture() -> Block:
    return Block(
        [
            PlaquetteLayer(
                get_memory_qubit_raw_template(),
                get_memory_qubit_plaquettes(),
            )
            for _ in range(2)
        ]
    )


@pytest.fixture(name="OZZ")
def OZZ_fixture() -> Block:
    return Block(
        [
            PlaquetteLayer(
                get_memory_vertical_boundary_raw_template(),
                get_memory_vertical_boundary_plaquettes(reset=Basis.Z),
            ),
            RepeatedLayer(
                PlaquetteLayer(
                    get_memory_vertical_boundary_raw_template(),
                    get_memory_vertical_boundary_plaquettes(),
                ),
                repetitions=LinearFunction(2, -1),
            ),
            PlaquetteLayer(
                get_memory_vertical_boundary_raw_template(),
                get_memory_vertical_boundary_plaquettes(measurement=Basis.Z),
            ),
        ]
    )


@pytest.fixture(name="XOZ")
def XOZ_fixture() -> Block:
    return Block(
        [
            PlaquetteLayer(
                get_memory_horizontal_boundary_raw_template(),
                get_memory_horizontal_boundary_plaquettes(reset=Basis.Z),
            ),
            RepeatedLayer(
                PlaquetteLayer(
                    get_memory_horizontal_boundary_raw_template(),
                    get_memory_horizontal_boundary_plaquettes(),
                ),
                repetitions=LinearFunction(2, -1),
            ),
            PlaquetteLayer(
                get_memory_horizontal_boundary_raw_template(),
                get_memory_horizontal_boundary_plaquettes(measurement=Basis.Z),
            ),
        ]
    )


def test_add_temporal_pipe_with_spatial_pipe_existing(
    scalable_qubit_shape: PhysicalQubitScalable2D, XZZ: Block, XOZ: Block, XZO: Block
) -> None:
    graph = TopologicalComputationGraph(scalable_qubit_shape)
    graph.add_cube(BlockPosition3D(0, 0, 0), XZZ)
    graph.add_cube(BlockPosition3D(0, 1, 0), XZZ)
    graph.add_cube(BlockPosition3D(0, 1, 1), XZZ)
    graph.add_pipe(BlockPosition3D(0, 0, 0), BlockPosition3D(0, 1, 0), XOZ)
    graph.add_pipe(BlockPosition3D(0, 1, 0), BlockPosition3D(0, 1, 1), XZO)

    graph.to_layer_tree()
