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
