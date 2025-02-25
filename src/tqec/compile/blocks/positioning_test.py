import pytest

from tqec.compile.blocks.positioning import LayoutPosition2D
from tqec.utils.position import BlockPosition2D
from tqec.utils.scale import LinearFunction, PhysicalQubitScalable2D


def test_creation() -> None:
    LayoutPosition2D.from_block_position(BlockPosition2D(0, 0))
    LayoutPosition2D.from_junction_position(
        (BlockPosition2D(0, 0), BlockPosition2D(1, 0))
    )
    LayoutPosition2D.from_junction_position(
        (BlockPosition2D(1, 0), BlockPosition2D(0, 0))
    )


def test_creation_raises() -> None:
    with pytest.raises(AssertionError):
        LayoutPosition2D.from_junction_position(
            (BlockPosition2D(0, 0), BlockPosition2D(2, 0))
        )
    with pytest.raises(AssertionError):
        LayoutPosition2D.from_junction_position(
            (BlockPosition2D(0, 0), BlockPosition2D(0, 0))
        )


@pytest.mark.parametrize("x,y", [(0, 0), (1, 0), (0, -1), (5, 198)])
def test_origin_qubit_block(x: int, y: int) -> None:
    qubit_width = LinearFunction(4, 5)
    element_shape = PhysicalQubitScalable2D(qubit_width, qubit_width)
    border_size = 2

    block_pos = LayoutPosition2D.from_block_position(BlockPosition2D(x, y))
    assert block_pos.origin_qubit(
        element_shape, border_size
    ) == PhysicalQubitScalable2D(x * qubit_width, y * qubit_width)


def test_origin_qubit_pipe() -> None:
    qubit_width = LinearFunction(4, 5)
    element_shape = PhysicalQubitScalable2D(qubit_width, qubit_width)
    border_size = 2

    pipe_pos = LayoutPosition2D.from_junction_position(
        (BlockPosition2D(0, 0), BlockPosition2D(1, 0))
    )
    assert pipe_pos.origin_qubit(element_shape, border_size) == PhysicalQubitScalable2D(
        qubit_width - border_size, LinearFunction(0, 0)
    )

    pipe_pos = LayoutPosition2D.from_junction_position(
        (BlockPosition2D(0, -1), BlockPosition2D(0, 0))
    )
    assert pipe_pos.origin_qubit(element_shape, border_size) == PhysicalQubitScalable2D(
        LinearFunction(0, 0), LinearFunction(0, -border_size)
    )
