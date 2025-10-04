"""Read and write block graphs to and from Collada DAE files."""

from __future__ import annotations

from tqec.computation.block_graph import BlockGraph, block_kind_from_str
from tqec.computation.cube import CubeKind, Port, YHalfCube
from tqec.computation.pipe import PipeKind
from tqec.interop.shared import int_position_before_scale, offset_y_cube_position
from tqec.utils.position import FloatPosition3D


def read_from_lattice_dicts(
    lattice_nodes: dict[int, tuple[tuple[int, int, int], str]],
    lattice_edges: dict[tuple[int, int], str],
    graph_name: str = "",
) -> BlockGraph:
    """Construct a :class:`.BlockGraph` from a space-time diagram produced by topologiq.

    Args:
        lattice_nodes: {id: ((x, y, z), kind)} for each node (cube) in intended blockgraph
        lattice_edges: {(source_id, target_id): kind} for each edge (pipes) in intended blockgraph
        graph_name: The name of the block graph. Default is an empty string.


    Returns:
        The constructed :py:class:`~tqec.computation.block_graph.BlockGraph` object.

    Raises:
        ValueError: If incoming objects cannot be parsed and converted to a block graph.

    """
    # Reject malforned inputs
    if not lattice_nodes.values():
        raise ValueError(
            "Lattice surgery objects not appropriately constructed: no nodes/cubes detected"
        )

    if not lattice_edges.values():
        raise ValueError(
            "Lattice surgery objects not appropriately constructed: node edges/pipes detected"
        )

    # Helper variables
    pipe_length: float | None = None
    parsed_ports: list[FloatPosition3D] = []
    parsed_cubes: list[tuple[FloatPosition3D, CubeKind]] = []
    parsed_pipes: list[tuple[FloatPosition3D, PipeKind, int]] = []

    # Unpack nodes/cubes
    try:
        for v in lattice_nodes.values():
            coords = v[0]
            translation = FloatPosition3D(*coords)
            if v[1] != "ooo":
                kind = block_kind_from_str(v[1].upper())
                if isinstance(kind, CubeKind):
                    parsed_cubes.append((translation, kind))

            else:
                parsed_ports.append(translation)
    except (ValueError, TypeError, IndexError, KeyError) as e:
        raise ValueError("Error reading nodes/cubes from lattice_nodes dictionary:", e)

    try:
        for (src, tgt), v in lattice_edges.items():
            kind = block_kind_from_str(v.upper())
            if isinstance(kind, PipeKind):
                src_pos = lattice_nodes[src][0]
                tgt_pos = lattice_nodes[tgt][0]

                shift_coords_from_src = tuple([(u - v) / 3 for u, v in zip(tgt_pos, src_pos)])
                directional_multiplier = int(sum(shift_coords_from_src))

                coords = [u + v for u, v in zip(src_pos, shift_coords_from_src)]
                translation = FloatPosition3D(*coords)

                parsed_pipes.append((translation, kind, directional_multiplier))
    except (ValueError, TypeError, IndexError, KeyError) as e:
        raise ValueError("Error reading edges/pipes from lattice_edges dictionary:", e)

    # Construct graph
    # Create graph
    block_graph = BlockGraph(graph_name)
    pipe_length = 2.0

    # Add cubes
    try:
        for pos, cube_kind in parsed_cubes:
            if isinstance(cube_kind, YHalfCube):
                block_graph.add_cube(
                    int_position_before_scale(
                        offset_y_cube_position(pos, pipe_length), pipe_length
                    ),
                    cube_kind,
                )
            else:
                block_graph.add_cube(int_position_before_scale(pos, pipe_length), cube_kind)
        port_index = 0
    except (ValueError, TypeError, IndexError, KeyError) as e:
        raise ValueError("Error converting lattice_nodes to block_graph cubes:", e)

    # Add pipes
    try:
        for pos, pipe_kind, directional_multiplier in parsed_pipes:
            head_pos = int_position_before_scale(
                pos.shift_in_direction(pipe_kind.direction, -1 * directional_multiplier),
                pipe_length,
            )
            tail_pos = head_pos.shift_in_direction(pipe_kind.direction, 1 * directional_multiplier)

            if head_pos not in block_graph:
                block_graph.add_cube(head_pos, Port(), label=f"Port{port_index}")
                port_index += 1
            if tail_pos not in block_graph:
                block_graph.add_cube(tail_pos, Port(), label=f"Port{port_index}")
                port_index += 1
            block_graph.add_pipe(head_pos, tail_pos, pipe_kind)
    except (ValueError, TypeError, IndexError, KeyError) as e:
        raise ValueError("Error converting lattice_edges to block_graph pipes:", e)

    return block_graph
