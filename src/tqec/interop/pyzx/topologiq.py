"""Read and write block graphs to and from topologiq space-time diagrams.

This module provides interoperability between topologiq's lattice surgery
representation and TQEC's BlockGraph representation. The primary function
`read_from_lattice_dicts` converts topologiq's output (lattice nodes and edges)
into a TQEC BlockGraph that can be compiled and simulated.

Typical usage:
    ```python
    from topologiq.scripts.runner import runner
    from topologiq.utils.interop_pyzx import pyzx_g_to_simple_g
    from tqec.interop.pyzx.topologiq import read_from_lattice_dicts

    # Convert PyZX graph to topologiq format
    simple_graph = pyzx_g_to_simple_g(zx_graph)

    # Run topologiq
    _, _, lattice_nodes, lattice_edges = runner(simple_graph, "circuit_name")

    # Convert to TQEC BlockGraph
    lattice_edges_min = dict([(k, v[0]) for k, v in lattice_edges.items()])
    block_graph = read_from_lattice_dicts(lattice_nodes, lattice_edges_min)
    ```
"""

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

    This function converts topologiq's lattice surgery representation into TQEC's
    BlockGraph format. It handles coordinate transformations, node/edge parsing,
    and automatic port creation for boundary nodes.

    The conversion process:
    1. Validates input dictionaries
    2. Parses nodes (cubes) and their positions
    3. Parses edges (pipes) and calculates their positions
    4. Creates a BlockGraph with appropriate transformations
    5. Automatically adds Port cubes for boundary connections

    Args:
        lattice_nodes: Dictionary mapping node IDs to (position, kind) tuples.
            - ID: Unique integer identifier for the node
            - position: (x, y, z) coordinate tuple in topologiq space
            - kind: String identifier for cube type (e.g., 'ZXZ', 'ZXX', 'ooo' for ports)
            Example: {0: ((0, 0, 0), 'ZXZ'), 1: ((3, 0, 0), 'ZXX')}

        lattice_edges: Dictionary mapping (source_id, target_id) pairs to pipe kinds.
            - source_id, target_id: Node IDs from lattice_nodes
            - kind: String identifier for pipe type (e.g., 'X', 'Z')
            Example: {(0, 1): 'X', (1, 2): 'Z'}
            Note: topologiq typically returns lists as values; extract first element
                  before passing to this function

        graph_name: Optional name for the resulting BlockGraph. Used for visualization
            and debugging. Default is an empty string.

    Returns:
        BlockGraph: A fully constructed BlockGraph with:
            - All cubes positioned and typed correctly
            - All pipes connecting cubes
            - Port cubes automatically added at boundaries
            - Coordinates transformed from topologiq space to TQEC space

    Raises:
        ValueError: If input validation fails or conversion encounters errors:
            - Empty lattice_nodes or lattice_edges
            - Invalid node/edge format (wrong types, missing keys)
            - Unknown cube or pipe kinds
            - Coordinate transformation failures

    Example:
        ```python
        # After running topologiq
        _, _, lattice_nodes, lattice_edges = runner(simple_graph, "my_circuit")

        # Convert edges format (topologiq returns lists)
        edges_min = {k: v[0] for k, v in lattice_edges.items()}

        # Create BlockGraph
        try:
            block_graph = read_from_lattice_dicts(
                lattice_nodes,
                edges_min,
                graph_name="my_steane_circuit"
            )
            # Visualize
            html = block_graph.view_as_html()
        except ValueError as e:
            print(f"Failed to convert lattice to BlockGraph: {e}")
        ```

    Note:
        - Port cubes ('ooo' nodes in topologiq) are converted to placeholder Ports
        - YHalfCube positions are automatically offset for correct placement
        - Pipe coordinates are calculated as midpoints between connected nodes
        - The pipe_length parameter (2.0) is used for all coordinate scaling

    """
    # Validate inputs
    if not isinstance(lattice_nodes, dict):
        raise ValueError(f"lattice_nodes must be a dictionary, got {type(lattice_nodes).__name__}")
    if not isinstance(lattice_edges, dict):
        raise ValueError(f"lattice_edges must be a dictionary, got {type(lattice_edges).__name__}")
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
    parsed_cubes: list[tuple[FloatPosition3D, CubeKind]] = []
    parsed_pipes: list[tuple[FloatPosition3D, FloatPosition3D, PipeKind]] = []

    # Unpack nodes/cubes
    # Note: Nodes marked as "ooo" (ports) are NOT added to parsed_cubes here.
    # They will be automatically created as Port() cubes when processing pipes
    # (see lines 194-200 below).
    try:
        for v in lattice_nodes.values():
            coords = v[0]
            translation = FloatPosition3D(*coords)
            if v[1] != "ooo":  # Skip port nodes - they're created automatically later
                kind = block_kind_from_str(v[1].upper())
                if isinstance(kind, CubeKind):
                    parsed_cubes.append((translation, kind))
    except (ValueError, TypeError, IndexError, KeyError) as e:
        raise ValueError("Error reading nodes/cubes from lattice_nodes dictionary:", e)

    try:
        for (src, tgt), v in lattice_edges.items():
            kind = block_kind_from_str(v.upper())
            if isinstance(kind, PipeKind):
                src_pos = lattice_nodes[src][0]
                tgt_pos = lattice_nodes[tgt][0]

                # Store source and target positions directly, not a midpoint
                # We'll connect the actual cube positions after coordinate transformation
                parsed_pipes.append((FloatPosition3D(*src_pos), FloatPosition3D(*tgt_pos), kind))
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
        for src_pos, tgt_pos, pipe_kind in parsed_pipes:
            # Transform both source and target positions to TQEC coordinate system
            head_pos = int_position_before_scale(src_pos, pipe_length)
            tail_pos = int_position_before_scale(tgt_pos, pipe_length)

            # Ensure cubes exist at both endpoints (create ports if needed)
            if head_pos not in block_graph:
                block_graph.add_cube(head_pos, Port(), label=f"Port{port_index}")
                port_index += 1
            if tail_pos not in block_graph:
                block_graph.add_cube(tail_pos, Port(), label=f"Port{port_index}")
                port_index += 1

            # Add the pipe connecting the two cubes
            block_graph.add_pipe(head_pos, tail_pos, pipe_kind)
    except (ValueError, TypeError, IndexError, KeyError) as e:
        raise ValueError("Error converting lattice_edges to block_graph pipes:", e)

    return block_graph
