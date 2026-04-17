"""Defines transformations used across TQEC interops folders."""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

import numpy as np

from tqec.computation.block_graph import BlockGraph
from tqec.utils.position import FloatPosition3D, Position3D
from tqec.utils.scale import round_or_fail


# ABC TEMPLATES
class LoadFromFile(ABC):
    """ABC template to create a :class:`.BlockGraph` from an external source."""

    _instance = None

    def __new__(cls):
        """Instantiate ABC class if/when ever called first."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    @abstractmethod
    def parse(self, filepath: str | Path) -> dict[str, Any]:
        """Abstract method any subclass must implement.

        Args:
            filepath: The path to the input file.

        Returns:
            parsed_data: The data in the source parsed as a dict representation of a blockgraph.
                `` {
                        name: str,  # The name for the blockgraph
                        cubes: [{
                            position: tuple[int, int, int],  # The position of the target cube.
                            kind: str, # The kind of cube.
                            label: str,  # Optional label to specify ports.
                        }]
                        pipe: [{
                            u: tuple[int, int, int],  # The position of source cube.
                            v: tuple[int, int, int],  # The position of target cube.
                            kind: str,  # The kind of pipe.
                        }]
                    }
                ``

        """
        pass

    def load(self, filepath: str | Path) -> BlockGraph:
        """Construct a block graph from data parsed in abstract method.

        Args:
            filepath: The path to the input file.

        """
        parsed_data = self.parse(filepath)
        block_graph = BlockGraph.from_dict(parsed_data)
        return block_graph


# TRANSFORMATIONS
def int_position_before_scale(pos: FloatPosition3D, pipe_length: float) -> Position3D:
    """Exchanges a float-based position with an integer-based position considering length of pipes.

    Args:
        pos: (x, y, z) position where x, y, and z are floats.
        pipe_length: the length of the pipes in the model.

    Returns:
        An (x, y, z)  position where x, y, and z are integers.

    """
    return Position3D(
        x=round_or_fail(pos.x / (1 + pipe_length), atol=0.35),
        y=round_or_fail(pos.y / (1 + pipe_length), atol=0.35),
        z=round_or_fail(pos.z / (1 + pipe_length), atol=0.35),
    )


def offset_y_cube_position(pos: FloatPosition3D, pipe_length: float) -> FloatPosition3D:
    """Offsets the position of a Y-cube according to the length of pipes in the model.

    Args:
        pos: (x, y, z) position where x, y, and z are floats.
        pipe_length: the length of the pipes in the model.

    Returns:
        An offset (x, y, z)  position where x, y, and z are floats.

    """
    if np.isclose(pos.z - 0.5, np.floor(pos.z), atol=1e-9):
        pos = pos.shift_by(dz=-0.5)
    return FloatPosition3D(pos.x, pos.y, pos.z / (1 + pipe_length))
