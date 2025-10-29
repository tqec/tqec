"""Tests for topologiq space-time diagram to BlockGraph conversion."""

import pytest

from tqec.computation.cube import Port, ZXCube
from tqec.interop.pyzx.topologiq import read_from_lattice_dicts
from tqec.utils.position import Position3D


def test_simple_two_cube_lattice() -> None:
    """Test conversion of a simple two-cube lattice."""
    lattice_nodes = {
        0: ((0, 0, 0), "ZXZ"),
        1: ((3, 0, 0), "ZXX"),
    }
    # Pipe in X direction (O=open=direction): "OXZ" means X-direction pipe
    lattice_edges = {
        (0, 1): "OXZ",
    }

    block_graph = read_from_lattice_dicts(lattice_nodes, lattice_edges, "test_graph")

    # Check number of cubes
    assert block_graph.num_cubes == 2
    assert Position3D(0, 0, 0) in block_graph
    assert Position3D(1, 0, 0) in block_graph


def test_lattice_with_ports() -> None:
    """Test conversion of lattice with port nodes."""
    lattice_nodes = {
        0: ((0, 0, 0), "ooo"),  # Port node
        1: ((3, 0, 0), "ZXZ"),
        2: ((6, 0, 0), "ooo"),  # Port node
    }
    # Pipes in X direction
    lattice_edges = {
        (0, 1): "OZX",
        (1, 2): "OZX",
    }

    block_graph = read_from_lattice_dicts(lattice_nodes, lattice_edges, "port_test")

    # Check that ports were created
    assert Position3D(0, 0, 0) in block_graph
    assert isinstance(block_graph[Position3D(0, 0, 0)].kind, Port)


def test_empty_lattice_nodes_raises_error() -> None:
    """Test that empty lattice_nodes raises ValueError."""
    with pytest.raises(ValueError, match="no nodes/cubes detected"):
        read_from_lattice_dicts({}, {(0, 1): "X"}, "empty_nodes")


def test_empty_lattice_edges_raises_error() -> None:
    """Test that empty lattice_edges raises ValueError."""
    with pytest.raises(ValueError, match="node edges/pipes detected"):
        read_from_lattice_dicts({0: ((0, 0, 0), "ZXZ")}, {}, "empty_edges")


def test_invalid_lattice_nodes_type() -> None:
    """Test that invalid type for lattice_nodes raises ValueError."""
    with pytest.raises(ValueError, match="must be a dictionary"):
        read_from_lattice_dicts([], {(0, 1): "X"}, "invalid")  # type: ignore


def test_invalid_lattice_edges_type() -> None:
    """Test that invalid type for lattice_edges raises ValueError."""
    with pytest.raises(ValueError, match="must be a dictionary"):
        read_from_lattice_dicts({0: ((0, 0, 0), "ZXZ")}, [], "invalid")  # type: ignore


def test_three_cube_chain() -> None:
    """Test a chain of three cubes connected by pipes."""
    lattice_nodes = {
        0: ((0, 0, 0), "ZXZ"),
        1: ((3, 0, 0), "ZXX"),
        2: ((6, 0, 0), "ZZX"),
    }
    # First pipe in X direction, second in X direction
    lattice_edges = {
        (0, 1): "OXZ",
        (1, 2): "OXZ",
    }

    block_graph = read_from_lattice_dicts(lattice_nodes, lattice_edges, "chain_test")

    # Verify all cubes were created
    assert block_graph.num_cubes == 3

    # Verify cube types
    assert isinstance(block_graph[Position3D(0, 0, 0)].kind, ZXCube)
    assert isinstance(block_graph[Position3D(1, 0, 0)].kind, ZXCube)
    assert isinstance(block_graph[Position3D(2, 0, 0)].kind, ZXCube)

    # Verify pipes
    assert block_graph.num_pipes == 2


def test_graph_name_preserved() -> None:
    """Test that the graph name is correctly set."""
    lattice_nodes = {
        0: ((0, 0, 0), "ZXZ"),
        1: ((3, 0, 0), "ZXX"),
    }
    lattice_edges = {
        (0, 1): "OXZ",
    }

    graph_name = "my_custom_graph"
    block_graph = read_from_lattice_dicts(lattice_nodes, lattice_edges, graph_name)

    assert block_graph.name == graph_name


def test_vertical_pipe_connection() -> None:
    """Test a vertical pipe connection (Y direction)."""
    lattice_nodes = {
        0: ((0, 0, 0), "ZXZ"),
        1: ((0, 3, 0), "ZXX"),
    }
    # Pipe in Y direction: XOZ
    lattice_edges = {
        (0, 1): "XOZ",
    }

    block_graph = read_from_lattice_dicts(lattice_nodes, lattice_edges, "vertical_test")

    assert block_graph.num_cubes == 2
    assert block_graph.num_pipes == 1
    # Check that the pipe exists (we can't easily check the kind without iterating)
    pipes = block_graph.pipes
    assert len(pipes) == 1


def test_time_axis_pipe_connection() -> None:
    """Test a time axis pipe connection (Z direction)."""
    lattice_nodes = {
        0: ((0, 0, 0), "ZXZ"),
        1: ((0, 0, 3), "ZXX"),
    }
    # Pipe in Z direction (time): XZO
    lattice_edges = {
        (0, 1): "XZO",
    }

    block_graph = read_from_lattice_dicts(lattice_nodes, lattice_edges, "time_test")

    assert block_graph.num_cubes == 2
    assert block_graph.num_pipes == 1
    # Check that the pipe exists
    pipes = block_graph.pipes
    assert len(pipes) == 1


def test_complex_lattice_structure() -> None:
    """Test a more complex lattice structure with multiple connections."""
    lattice_nodes = {
        0: ((0, 0, 0), "ZXZ"),
        1: ((3, 0, 0), "ZXX"),
        2: ((0, 3, 0), "ZXZ"),
        3: ((3, 3, 0), "ZZX"),
    }
    # Pipes: OXZ=X-dir, XOZ=Y-dir
    lattice_edges = {
        (0, 1): "OXZ",
        (0, 2): "XOZ",
        (1, 3): "XOZ",
        (2, 3): "OXZ",
    }

    block_graph = read_from_lattice_dicts(lattice_nodes, lattice_edges, "complex_test")

    # Verify all cubes created
    assert block_graph.num_cubes == 4

    # Verify all pipes created
    assert block_graph.num_pipes == 4


def test_port_nodes_converted_to_port_cubes() -> None:
    """Test that nodes marked as 'ooo' in topologiq are converted to Port cubes.

    In topologiq's output, port nodes are marked with kind='ooo'. Our conversion
    function should recognize these and create Port() cubes at those positions.
    This happens via the automatic creation mechanism in lines 194-200 of
    topologiq.py when processing pipe endpoints.
    """
    # Single port at start
    lattice_nodes = {
        0: ((0, 0, 0), "ooo"),  # Port marked by topologiq
        1: ((3, 0, 0), "ZXZ"),
    }
    lattice_edges = {
        (0, 1): "OZX",
    }

    block_graph = read_from_lattice_dicts(lattice_nodes, lattice_edges, "port_creation")

    # Verify port was created
    assert block_graph.num_cubes == 2
    assert block_graph.num_ports == 1

    port_cube = block_graph[Position3D(0, 0, 0)]
    assert port_cube.is_port
    assert port_cube.label.startswith("Port")  # Auto-generated label

    # Regular cube should not be a port
    regular_cube = block_graph[Position3D(1, 0, 0)]
    assert not regular_cube.is_port


def test_multiple_ports_in_circuit() -> None:
    """Test circuits with multiple port nodes (input and output ports)."""
    lattice_nodes = {
        0: ((0, 0, 0), "ooo"),  # Input port
        1: ((3, 0, 0), "ZXZ"),
        2: ((6, 0, 0), "ZXX"),
        3: ((9, 0, 0), "ooo"),  # Output port
    }
    lattice_edges = {
        (0, 1): "OZX",
        (1, 2): "OZX",
        (2, 3): "OZX",
    }

    block_graph = read_from_lattice_dicts(lattice_nodes, lattice_edges, "multiple_ports")

    # Verify structure
    assert block_graph.num_cubes == 4
    assert block_graph.num_ports == 2
    assert block_graph.num_pipes == 3

    # Verify both ends are ports
    assert block_graph[Position3D(0, 0, 0)].is_port
    assert block_graph[Position3D(3, 0, 0)].is_port

    # Verify middle cubes are not ports
    assert not block_graph[Position3D(1, 0, 0)].is_port
    assert not block_graph[Position3D(2, 0, 0)].is_port


def test_port_labels_are_unique() -> None:
    """Test that auto-generated port labels are unique.

    When multiple ports are created, each should get a unique label
    (Port0, Port1, Port2, etc.) to distinguish them in the BlockGraph.
    """
    # Create a linear chain with ports at both ends
    lattice_nodes = {
        0: ((0, 0, 0), "ooo"),  # Port at start
        1: ((3, 0, 0), "ZXZ"),
        2: ((6, 0, 0), "ZXX"),
        3: ((9, 0, 0), "ooo"),  # Port at end
        4: ((12, 0, 0), "ooo"),  # Another port
    }
    lattice_edges = {
        (0, 1): "OZX",
        (1, 2): "OZX",
        (2, 3): "OZX",
        (3, 4): "OZX",
    }

    block_graph = read_from_lattice_dicts(lattice_nodes, lattice_edges, "unique_ports")

    # Collect all port labels
    port_labels = [cube.label for cube in block_graph.cubes if cube.is_port]

    # Verify we have 3 ports
    assert len(port_labels) == 3

    # Verify all labels are unique (no duplicates)
    assert len(set(port_labels)) == 3

    # Verify all labels follow the Port{N} pattern
    assert all(label.startswith("Port") for label in port_labels)
    assert all(label[4:].isdigit() for label in port_labels)  # Port0, Port1, etc.


def test_coordinate_transformation() -> None:
    """Test that coordinates are correctly transformed from topologiq space to TQEC space."""
    # topologiq uses multiples of 3 for spacing
    lattice_nodes = {
        0: ((0, 0, 0), "ZXZ"),
        1: ((3, 0, 0), "ZXX"),  # Should become Position3D(1, 0, 0)
        2: ((6, 0, 0), "ZXZ"),  # Should become Position3D(2, 0, 0)
    }
    lattice_edges = {
        (0, 1): "OXZ",
        (1, 2): "OXZ",
    }

    block_graph = read_from_lattice_dicts(lattice_nodes, lattice_edges, "transform_test")

    # Check that positions are correctly scaled
    assert Position3D(0, 0, 0) in block_graph
    assert Position3D(1, 0, 0) in block_graph
    assert Position3D(2, 0, 0) in block_graph


def test_all_cube_types() -> None:
    """Test that all cube types are correctly parsed."""
    cube_types = ["ZXZ", "ZXX", "ZZX", "XXZ", "XZX", "XZZ"]
    lattice_nodes = {i: ((i * 3, 0, 0), cube_type) for i, cube_type in enumerate(cube_types)}
    lattice_edges = {(i, i + 1): "OXZ" for i in range(len(cube_types) - 1)}

    block_graph = read_from_lattice_dicts(lattice_nodes, lattice_edges, "all_types_test")

    assert block_graph.num_cubes == len(cube_types)
    for i, cube_type in enumerate(cube_types):
        cube = block_graph[Position3D(i, 0, 0)]
        assert isinstance(cube.kind, ZXCube)


def test_steane_like_structure() -> None:
    """Test a structure similar to Steane encoding (simplified)."""
    # Create a simplified Steane-like structure
    # This represents a valid lattice surgery pattern with proper adjacency
    lattice_nodes = {
        0: ((0, 0, 0), "ooo"),  # Input port
        1: ((3, 0, 0), "ZXZ"),
        2: ((6, 0, 0), "ZXX"),
        3: ((9, 0, 0), "ZZX"),
        4: ((3, 3, 0), "ZXX"),
        5: ((6, 3, 0), "ZZX"),
        6: ((9, 3, 0), "ZXZ"),  # Changed from output port to cube
        7: ((12, 0, 0), "ooo"),  # Output port
    }
    lattice_edges = {
        (0, 1): "OZX",  # X-direction
        (1, 2): "OZX",  # X-direction
        (2, 3): "OZX",  # X-direction
        (1, 4): "ZOX",  # Y-direction
        (4, 5): "OZX",  # X-direction
        (5, 6): "OZX",  # X-direction
        (3, 6): "ZOX",  # Y-direction
        (3, 7): "OZX",  # X-direction
    }

    block_graph = read_from_lattice_dicts(lattice_nodes, lattice_edges, "steane_like")

    # Verify structure
    assert block_graph.num_cubes >= 7  # May have auto-created ports
    assert block_graph.num_pipes >= 8
