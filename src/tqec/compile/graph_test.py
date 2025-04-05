import pytest

from tqec.compile.blocks.block import Block
from tqec.compile.blocks.enums import TemporalBlockBorder
from tqec.compile.blocks.layers.atomic.plaquettes import PlaquetteLayer
from tqec.compile.graph import TopologicalComputationGraph
from tqec.compile.specs.base import CubeSpec, PipeSpec
from tqec.compile.specs.library.standard import (
    STANDARD_CUBE_BUILDER,
    STANDARD_PIPE_BUILDER,
)
from tqec.computation.cube import ZXCube
from tqec.computation.pipe import PipeKind
from tqec.utils.position import BlockPosition3D
from tqec.utils.scale import LinearFunction, PhysicalQubitScalable2D


@pytest.fixture(name="scalable_qubit_shape")
def scalable_qubit_shape_fixture() -> PhysicalQubitScalable2D:
    return PhysicalQubitScalable2D(LinearFunction(4, 5), LinearFunction(4, 5))


@pytest.fixture(name="XZZ")
def XZZ_fixture() -> Block:
    return STANDARD_CUBE_BUILDER(CubeSpec(ZXCube.from_str("XZZ")))


@pytest.fixture(name="XZO")
def XZO_fixture(XZZ: Block) -> Block:
    spec = CubeSpec(ZXCube.from_str("XZZ"))
    first_layer = XZZ.get_temporal_border(TemporalBlockBorder.Z_NEGATIVE)
    assert isinstance(first_layer, PlaquetteLayer)
    template = first_layer.template
    return STANDARD_PIPE_BUILDER(
        PipeSpec((spec, spec), (template, template), PipeKind.from_str("XZO"))
    )


@pytest.fixture(name="OZZ")
def OZZ_fixture(XZZ: Block) -> Block:
    spec = CubeSpec(ZXCube.from_str("XZZ"))
    first_layer = XZZ.get_temporal_border(TemporalBlockBorder.Z_NEGATIVE)
    assert isinstance(first_layer, PlaquetteLayer)
    template = first_layer.template
    return STANDARD_PIPE_BUILDER(
        PipeSpec((spec, spec), (template, template), PipeKind.from_str("OZZ"))
    )


@pytest.fixture(name="XOZ")
def XOZ_fixture(XZZ: Block) -> Block:
    spec = CubeSpec(ZXCube.from_str("XZZ"))
    first_layer = XZZ.get_temporal_border(TemporalBlockBorder.Z_NEGATIVE)
    assert isinstance(first_layer, PlaquetteLayer)
    template = first_layer.template
    return STANDARD_PIPE_BUILDER(
        PipeSpec((spec, spec), (template, template), PipeKind.from_str("XOZ"))
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


def test_sequenced_layers_with_layout_layers_of_different_shapes(
    scalable_qubit_shape: PhysicalQubitScalable2D, XZZ: Block, XOZ: Block, XZO: Block
) -> None:
    graph = TopologicalComputationGraph(scalable_qubit_shape)
    graph.add_cube(BlockPosition3D(0, 0, 0), XZZ)
    graph.add_cube(BlockPosition3D(0, 0, 1), XZZ)
    graph.add_cube(BlockPosition3D(0, 1, 1), XZZ)
    graph.add_pipe(BlockPosition3D(0, 0, 0), BlockPosition3D(0, 0, 1), XZO)
    graph.add_pipe(BlockPosition3D(0, 0, 1), BlockPosition3D(0, 1, 1), XOZ)

    graph.to_layer_tree()
