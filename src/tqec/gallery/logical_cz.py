"""Build computation graphs that represent a logical CZ gate."""

import stim

from tqec.computation.block_graph import BlockGraph
from tqec.computation.zx_graph import ZXKind, ZXGraph, ZXNode
from tqec.position import Position3D
from tqec.exceptions import TQECException


def logical_cz_zx_graph(support_flows: str | list[str] | None = None) -> ZXGraph:
    """Create a ZX graph for the logical CZ gate.

    By default, the Hadamard edge in the CZ gate will be horizontal. If you
    want to use vertical Hadamard edges, you can rotate the graph by 90 degrees
    by calling `~tqec.computation.zx_graph.ZXGraph.rotate`.

    Args:
        support_flows: The stabilizer flow supported by the logical CZ gate. It
            determines the node kind at the ports of the graph. It can be either
            a single string like "XI -> XZ" or an iterable of strings like
            ["XI -> XZ", "IZ -> IZ"] or None. If multiple flows are provided,
            a valid graph will be computed or an error will be raised if no
            valid graph can be found. If None, the graph will have open ports.

    Returns:
        A :py:class:`~tqec.computation.zx_graph.ZXGraph` instance representing the
        logical CZ gate.

    Raises:
        TQECException: If there is Y Pauli operator in the stabilizer flows, or
            if provided stabilizer flows are not valid for the CZ gate, or
            if no valid graph can be found for the given stabilizer flows.
    """
    g = ZXGraph("Logical CZ")
    g.add_edge(
        ZXNode(Position3D(0, 0, 0), ZXKind.P, "In_1"),
        ZXNode(Position3D(0, 0, 1), ZXKind.Z),
    )
    g.add_edge(
        ZXNode(Position3D(0, 0, 1), ZXKind.Z),
        ZXNode(Position3D(0, 0, 2), ZXKind.P, "Out_1"),
    )
    g.add_edge(
        ZXNode(Position3D(0, 0, 1), ZXKind.Z),
        ZXNode(Position3D(1, 0, 1), ZXKind.Z),
        has_hadamard=True,
    )
    g.add_edge(
        ZXNode(Position3D(1, 0, 1), ZXKind.Z),
        ZXNode(Position3D(1, -1, 1), ZXKind.P, "In_2"),
    )
    g.add_edge(
        ZXNode(Position3D(1, 0, 1), ZXKind.Z),
        ZXNode(Position3D(1, 1, 1), ZXKind.P, "Out_2"),
    )

    if support_flows is not None:
        flows = (
            [f.upper() for f in support_flows]
            if isinstance(support_flows, list)
            else [support_flows.upper()]
        )
        resolved_ports = _resolve_ports(flows)
        g.fill_ports(dict(zip(["In_1", "In_2", "Out_1", "Out_2"], resolved_ports)))
    return g


def _resolve_ports(flows: list[str]) -> list[ZXKind]:
    if any("Y" in f for f in flows):
        raise TQECException(
            "Y basis initialization/measurements are not supported yet."
        )

    stim_flows = [stim.Flow(f) for f in flows]
    cz = stim.Circuit("CZ 0 1")
    for f in stim_flows:
        if not cz.has_flow(f):
            raise TQECException(f"{f} is not a valid flow for the CZ gate.")

    ports = ["_"] * 4
    for f in stim_flows:
        for i, p in enumerate(str(f.input_copy() + f.output_copy())[1:]):
            if ports[i] == "_":
                ports[i] = p
            elif p != "_" and p != ports[i]:
                raise TQECException(
                    f"Port {i} fails to support both {ports[i]} and {p} observable."
                )
    # If there are left "I" in the ports, we choose fill them with "Z" ("X" should also work).
    for i in range(4):
        if ports[i] == "_":
            ports[i] = "Z"
    # note that node kind is opposite to the supported observable basis
    return [ZXKind(p).with_zx_flipped() for p in ports]


def logical_cz_block_graph(support_flows: str | list[str] | None = None) -> BlockGraph:
    """Create a block graph for the logical CZ gate.

    By default, the Hadamard edge in the CZ gate will be horizontal. If you
    want to use vertical Hadamard edges, you can rotate the graph by 90 degrees
    by calling `~tqec.computation.block_graph.BlockGraph.rotate`.

    Args:
        support_flows: The stabilizer flow supported by the logical CZ gate. It
            determines the node kind at the ports of the graph. It can be either
            a single string like "XI -> XZ" or an iterable of strings like
            ["XI -> XZ", "IZ -> IZ"] or None. If multiple flows are provided,
            a valid graph will be computed or an error will be raised if no
            valid graph can be found. If None, the graph will have open ports.

    Returns:
        A :py:class:`~tqec.computation.block_graph.BlockGraph` instance representing the
        logical CZ gate.

    Raises:
        TQECException: If there is Y Pauli operator in the stabilizer flows, or
            if provided stabilizer flows are not valid for the CZ gate, or
            if no valid graph can be found for the given stabilizer flows.
    """
    zx_graph = logical_cz_zx_graph(support_flows)
    return zx_graph.to_block_graph("Logical CZ")
