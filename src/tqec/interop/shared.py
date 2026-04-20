"""Defines transformations used across TQEC interops folders."""

from abc import ABC, abstractmethod
from io import StringIO
from pathlib import Path
from typing import Any

import numpy as np

from tqec.computation.block_graph import BlockGraph, block_kind_from_str
from tqec.computation.cube import YHalfCube
from tqec.utils.exceptions import TQECError
from tqec.utils.position import FloatPosition3D, Position3D
from tqec.utils.scale import round_or_fail


# ABC TEMPLATES
class LoadFromAnywhere(ABC):
    """ABC template for subclasses that create :py:class:`~.BlockGraph` from external source."""

    _instance = None

    def __new__(cls):
        """Instantiate ABC class if/when ever called first."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    @abstractmethod
    def parse(
        self,
        raw_str: str | None,
        filepath: str | Path | None = None,
        io_str: StringIO | None = None,
        input_in_other_format: Any | None = None,
    ) -> dict[str, Any]:
        """Abstract method any subclass must implement.

        What matters in this abstract method is that any implementation returns
        the parsed data exactly as described below. If so, then :method:`.load`
        of :class:`.LoadFromAnywhere` (this ABC class), inherited by any subclass,
        will be callable. For the same reason, the abstract method is purposely
        agnostic of input.

        For an example subclass see :py:class:`~tqec.interop.bgraph.LoadFromBgraph`:

        Args:
            raw_str: external input given as a regular string.
            filepath (optional): The path to the input file.
            io_str (optional): An IO string with the contents of a file.
            input_in_other_format (optional): Input in any other format.

        Returns:
            parsed_data: The data in the source parsed as a dict representation of a blockgraph.
                `` {
                        name: str,  # The name for the blockgraph.
                        pipe_length,  # The length of the pipes/edges in blockgraph.
                        cubes: {
                            cube_id: {
                                position: tuple[int, int, int],  # The position of the cube.
                                kind: str, # The kind of cube.
                                label: str,  # Optional label to specify ports.
                            }
                        }
                        pipe: {
                            (src_id, tgt_id): {
                                kind: str,  # The kind of pipe.
                            }
                        }
                    }
                ``

        """
        pass

    def load(
        self,
        raw_str: str | None,
        filepath: str | Path | None = None,
        io_str: StringIO | None = None,
        input_in_other_format: Any | None = None,
        override_graph_name: str | None = None,
    ) -> BlockGraph:
        """Construct a block graph from data parsed in abstract method.

        This concrete method is inherited by any implementing subclass.
        The method will be callable from the implementing subclass.

        Args:
            raw_str: external input given as a regular string.
            filepath (optional): The path to an input file.
            io_str (optional): An IO string with the contents of a file.
            input_in_other_format (optional): Input in any other format.
            override_graph_name (optional): Explicit name to give the blockgraph.

        """
        # Parse data using the implemented version of this ABC class abstract's method
        parsed_data = self.parse(
            raw_str=raw_str,
            filepath=filepath,
            io_str=io_str,
            input_in_other_format=input_in_other_format,
        )

        # Some tools do not allow saving name explicitly so parser needs a default
        if override_graph_name:
            parsed_data["name"] = override_graph_name

        # Build minified dictionary with repositioned pipes
        blockgraph_dict = {"name": parsed_data["name"], "cubes": [], "pipes": []}
        pipe_length = parsed_data["pipe_length"] if "pipe_length" in parsed_data else 0.0

        try:
            for cube_id, cube_info in parsed_data["cubes"].items():
                raw_pos, kind, label = cube_info.values()
                if "y" in kind:
                    if isinstance(block_kind_from_str(kind), YHalfCube):
                        position = int_position_before_scale(
                            offset_y_cube_position(FloatPosition3D(*raw_pos), pipe_length),
                            pipe_length,
                        )
                    else:
                        raise TQECError("Error repositioning from parsed data: Invalid Y kind.")
                else:
                    position = int_position_before_scale(FloatPosition3D(*raw_pos), pipe_length)

                parsed_data["cubes"][cube_id]["position"] = position.as_tuple()
                blockgraph_dict["cubes"].append(
                    {
                        "position": position.as_tuple(),
                        "kind": kind,
                        "label": label,
                    }
                )
        except Exception as e:
            raise TQECError(f"Error repositioning parsed cubes from parsed data: {e}.")

        try:
            for (src_id, tgt_id), pipe_info in parsed_data["pipes"].items():
                blockgraph_dict["pipes"].append(
                    {
                        "u": parsed_data["cubes"][src_id]["position"],
                        "v": parsed_data["cubes"][tgt_id]["position"],
                        "kind": pipe_info["kind"],
                    }
                )
        except Exception as e:
            raise TQECError(f"Error repositioning pipes from parsed data: {e}.")

        # Build and return blockgraph
        try:
            block_graph = BlockGraph.from_dict(blockgraph_dict)
        except Exception as e:
            raise TQECError(f"Error creating blockgraph from parsed data: {e}.")

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
