from tqec.circuit.qubit import GridQubit
from tqec.compile.observables.builder import (
    _transform_coords_into_grid,
)
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
    qubit = _transform_coords_into_grid(
        template,
        local_coords=(2, 2),
        block_position=Position3D(1, 1, 0),
        k=5,
    )
    assert qubit == GridQubit(27, 27)

    qubit = _transform_coords_into_grid(
        template,
        local_coords=(3, 1),
        block_position=Position3D(0, 1, 0),
        k=12,
    )
    x = -1 + 3 * 2
    y = (12 * 2 + 2) * 2 - 1 + 1 * 2
    assert qubit == GridQubit(x, y)
