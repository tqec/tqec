from tqec.circuit.qubit import GridQubit
from tqec.compile.observables.abstract_observable import AbstractObservable, CubeWithArms
from tqec.compile.observables.builder import ObservableBuilder, ObservableComponent
from tqec.compile.specs.enums import SpatialArms
from tqec.computation.cube import Cube, ZXCube
from tqec.templates.layout import LayoutTemplate
from tqec.templates.qubit import QubitTemplate
from tqec.utils.position import (
    BlockPosition2D,
    Position3D,
)


def test_transform_coords_into_grid() -> None:
    template = LayoutTemplate(
        {
            BlockPosition2D(0, 0): QubitTemplate(),
            BlockPosition2D(1, 0): QubitTemplate(),
            BlockPosition2D(1, 1): QubitTemplate(),
        }
    )
    qubits = ObservableBuilder.transform_coords_into_grid(
        5,
        template,
        local_coords=[(2, 2)],
        block_position=Position3D(1, 1, 0),
    )
    assert qubits == {GridQubit(27, 27)}

    qubits = ObservableBuilder.transform_coords_into_grid(
        12,
        template,
        local_coords=[(3, 1)],
        block_position=Position3D(0, 1, 0),
    )
    x = -1 + 3 * 2
    y = (12 * 2 + 2) * 2 - 1 + 1 * 2
    assert qubits == {GridQubit(x, y)}


def test_top_readouts_use_same_cube_parity_and_different_cube_union() -> None:
    cube = Cube(Position3D(0, 0, 0), ZXCube.from_str("ZZX"))
    first = CubeWithArms(cube, SpatialArms.LEFT | SpatialArms.DOWN)
    second = CubeWithArms(cube, SpatialArms.RIGHT | SpatialArms.UP)
    neighbor = CubeWithArms(Cube(Position3D(1, 0, 0), ZXCube.from_str("XZX")))
    coords = {
        first: [(4, 1), (2, 1)],
        second: [(2, 1), (3, 1)],
        neighbor: [(0, 1), (1, 1)],
    }
    builder = ObservableBuilder(
        cube_top_readouts_builder=lambda shape, cube: coords[cube],
        pipe_top_readouts_builder=lambda shape, pipe: (),
        cube_bottom_stabilizers_builder=lambda shape, cube: (),
        pipe_bottom_stabilizers_builder=lambda shape, pipe: (),
        pipe_temporal_hadamard_builder=lambda shape, pipe: (),
    )
    template = LayoutTemplate({BlockPosition2D(0, 0): QubitTemplate()})

    qubits = builder.build(
        1,
        template,
        AbstractObservable(top_readout_cubes=frozenset(coords)),
        ObservableComponent.TOP_READOUTS,
    )

    # (3, 1) cancels within the first cube; (7, 1) is shared by both cubes and stays.
    assert qubits == {GridQubit(5, 1), GridQubit(7, 1), GridQubit(9, 1)}
