import pytest

from tqec.compile.blocks.positioning import LayoutPosition2D
from tqec.utils.position import BlockPosition2D


def test_creation() -> None:
    LayoutPosition2D.from_block_position(BlockPosition2D(0, 0))
    LayoutPosition2D.from_pipe_position((BlockPosition2D(0, 0), BlockPosition2D(1, 0)))
    LayoutPosition2D.from_pipe_position((BlockPosition2D(1, 0), BlockPosition2D(0, 0)))


def test_creation_raises() -> None:
    with pytest.raises(AssertionError):
        LayoutPosition2D.from_pipe_position(
            (BlockPosition2D(0, 0), BlockPosition2D(2, 0))
        )
    with pytest.raises(AssertionError):
        LayoutPosition2D.from_pipe_position(
            (BlockPosition2D(0, 0), BlockPosition2D(0, 0))
        )


@pytest.mark.parametrize("x,y", ((0, 0), (1, 0), (-1, 98), (-98, 6)))
def test_to_block_position(x: int, y: int) -> None:
    bp = BlockPosition2D(x, y)
    assert LayoutPosition2D.from_block_position(bp).to_block_position() == bp


@pytest.mark.parametrize(
    "x,y,shift",
    (
        (0, 0, (1, 0)),
        (1, 0, (0, 1)),
        (-1, 98, (-1, 0)),
        (-98, 6, (0, -1)),
    ),
)
def test_to_pipe(x: int, y: int, shift: tuple[int, int]) -> None:
    bp = BlockPosition2D(x, y)
    neighbouring_bp = BlockPosition2D(bp.x + shift[0], bp.y + shift[1])
    pipe = (bp, neighbouring_bp)
    assert LayoutPosition2D.from_pipe_position(pipe).to_pipe() == tuple(sorted(pipe))
