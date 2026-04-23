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

    @abstractmethod
    def parse(
        self,
        raw_str: str | None,
        filepath: str | Path | None = None,
        io_str: StringIO | None = None,
        input_in_other_format: Any | None = None,
    ) -> dict[str, Any]:
        """Abstract method any subclass must implement.

        Args:
            raw_str: external input given as a regular string.
            filepath (optional): The path to the input file.
            io_str (optional): An IO string with the contents of a file.
            input_in_other_format (optional): Input in any other format.

        Returns:
            parsed_data: The data in the source parsed as a dict representation of a blockgraph.

        Note:
            To use the concrete :method:`.load` made available as part of this ABC class,
            this method should return a dictionary with the following structure:
                `` parsed_data = {
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

            For an example see :py:class:`~tqec.interop.bgraph.LoadFromBgraph`.

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

        # Build blockgraph
        block_graph = BlockGraph(parsed_data["name"])

        # Add cubes
        pipe_length = parsed_data.get("pipe_length", 0.0)
        try:
            for cube_id, cube_info in parsed_data["cubes"].items():
                # Extract specific fields
                raw_pos, kind, label = cube_info.values()

                # Reposition cube given kind and pipe_length
                if "Y" in kind.upper():
                    kind = "Y"
                    if isinstance(block_kind_from_str(kind), YHalfCube):
                        position = int_position_before_scale(
                            offset_y_cube_position(FloatPosition3D(*raw_pos), pipe_length),
                            pipe_length,
                        )
                    else:
                        raise TQECError("Error repositioning from parsed data: Invalid Y kind.")
                else:
                    kind = "P" if kind.upper() == "OOO" else kind.upper()
                    position = int_position_before_scale(FloatPosition3D(*raw_pos), pipe_length)
                parsed_data["cubes"][cube_id]["position"] = position

                # Add to blockgraph
                block_graph.add_cube(position=position, kind=kind, label=label)

        except Exception as e:
            raise TQECError("Error repositioning parsed cubes from parsed data.") from e

        # Add pipes
        try:
            for (src_id, tgt_id), pipe_info in parsed_data["pipes"].items():
                block_graph.add_pipe(
                    pos1=parsed_data["cubes"][src_id]["position"],
                    pos2=parsed_data["cubes"][tgt_id]["position"],
                    kind=pipe_info["kind"],
                )

        except Exception as e:
            raise TQECError("Error repositioning pipes from parsed data.") from e

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
