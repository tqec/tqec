import pytest

from tqec.compile.blocks.block import LayeredBlock
from tqec.compile.blocks.enums import TemporalBlockBorder
from tqec.compile.blocks.layers.atomic.plaquettes import PlaquetteLayer
from tqec.compile.graph import TopologicalComputationGraph
from tqec.compile.observables.builder import ObservableBuilder
from tqec.compile.observables.fixed_bulk_builder import FIXED_BULK_OBSERVABLE_BUILDER
from tqec.compile.specs.base import CubeSpec, PipeSpec
from tqec.compile.specs.library.fixed_bulk import (
    FIXED_BULK_CUBE_BUILDER,
    FIXED_BULK_PIPE_BUILDER,
)
from tqec.computation.cube import ZXCube
from tqec.computation.pipe import PipeKind
from tqec.utils.position import BlockPosition3D
from tqec.utils.scale import LinearFunction, PhysicalQubitScalable2D


@pytest.fixture(name="observable_builder")
def observable_builder_fixture() -> ObservableBuilder:
    return FIXED_BULK_OBSERVABLE_BUILDER


@pytest.fixture(name="scalable_qubit_shape")
def scalable_qubit_shape_fixture() -> PhysicalQubitScalable2D:
    return PhysicalQubitScalable2D(LinearFunction(4, 5), LinearFunction(4, 5))


@pytest.fixture(name="xzz")
def xzz_fixture() -> LayeredBlock:
    block = FIXED_BULK_CUBE_BUILDER(CubeSpec(ZXCube.from_str("xzz")))
    assert isinstance(block, LayeredBlock)
    return block


@pytest.fixture(name="xzo")
def xzo_fixture(xzz: LayeredBlock) -> LayeredBlock:
    spec = CubeSpec(ZXCube.from_str("xzz"))
    first_layer = xzz.get_atomic_temporal_border(TemporalBlockBorder.Z_NEGATIVE)
    assert isinstance(first_layer, PlaquetteLayer)
    template = first_layer.template
    return FIXED_BULK_PIPE_BUILDER(
        PipeSpec((spec, spec), (template, template), PipeKind.from_str("xzo"))
    )


@pytest.fixture(name="ozz")
def ozz_fixture(xzz: LayeredBlock) -> LayeredBlock:
    spec = CubeSpec(ZXCube.from_str("xzz"))
    first_layer = xzz.get_atomic_temporal_border(TemporalBlockBorder.Z_NEGATIVE)
    assert isinstance(first_layer, PlaquetteLayer)
    template = first_layer.template
    return FIXED_BULK_PIPE_BUILDER(
        PipeSpec((spec, spec), (template, template), PipeKind.from_str("OZZ"))
    )


@pytest.fixture(name="xoz")
def xoz_fixture(xzz: LayeredBlock) -> LayeredBlock:
    spec = CubeSpec(ZXCube.from_str("xzz"))
    first_layer = xzz.get_atomic_temporal_border(TemporalBlockBorder.Z_NEGATIVE)
    assert isinstance(first_layer, PlaquetteLayer)
    template = first_layer.template
    return FIXED_BULK_PIPE_BUILDER(
        PipeSpec((spec, spec), (template, template), PipeKind.from_str("xoz"))
    )


def test_add_temporal_pipe_with_spatial_pipe_existing(
    observable_builder: ObservableBuilder,
    scalable_qubit_shape: PhysicalQubitScalable2D,
    xzz: LayeredBlock,
    xoz: LayeredBlock,
    xzo: LayeredBlock,
) -> None:
    graph = TopologicalComputationGraph(scalable_qubit_shape, observable_builder)
    graph.add_cube(BlockPosition3D(0, 0, 0), xzz)
    graph.add_cube(BlockPosition3D(0, 1, 0), xzz)
    graph.add_cube(BlockPosition3D(0, 1, 1), xzz)
    graph.add_pipe(BlockPosition3D(0, 0, 0), BlockPosition3D(0, 1, 0), xoz)
    graph.add_pipe(BlockPosition3D(0, 1, 0), BlockPosition3D(0, 1, 1), xzo)

    graph.to_layer_tree()


def test_sequenced_layers_with_layout_layers_of_different_shapes(
    observable_builder: ObservableBuilder,
    scalable_qubit_shape: PhysicalQubitScalable2D,
    xzz: LayeredBlock,
    xoz: LayeredBlock,
    xzo: LayeredBlock,
) -> None:
    graph = TopologicalComputationGraph(scalable_qubit_shape, observable_builder)
    graph.add_cube(BlockPosition3D(0, 0, 0), xzz)
    graph.add_cube(BlockPosition3D(0, 0, 1), xzz)
    graph.add_cube(BlockPosition3D(0, 1, 1), xzz)
    graph.add_pipe(BlockPosition3D(0, 0, 0), BlockPosition3D(0, 0, 1), xzo)
    graph.add_pipe(BlockPosition3D(0, 0, 1), BlockPosition3D(0, 1, 1), xoz)

    graph.to_layer_tree()
