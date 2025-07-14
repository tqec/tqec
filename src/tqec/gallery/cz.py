"""Block graph that represents a CZ gate."""

import stim

from tqec.computation.block_graph import BlockGraph
from tqec.computation.cube import ZXCube
from tqec.utils.exceptions import TQECError
from tqec.utils.position import Position3D


def cz(support_flows: str | list[str] | None = None) -> BlockGraph:
    """Create a block graph representing the logical CZ gate.

    By default, the Hadamard edge in the CZ gate will be horizontal. If you
    want to use vertical Hadamard edges, you can rotate the graph by 90 degrees
    by calling :py:meth:`~tqec.computation.block_graph.BlockGraph.rotate`.

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
        TQECError: If there is Y Pauli operator in the stabilizer flows, or
            if provided stabilizer flows are not valid for the CZ gate, or
            if no valid graph can be found for the given stabilizer flows.

    """
    g = BlockGraph("Logical CZ")
    nodes = [
        (Position3D(0, 0, 0), "P", "In_1"),
        (Position3D(0, 0, 1), "XZX", ""),
        (Position3D(0, 0, 2), "P", "Out_1"),
        (Position3D(1, 0, 1), "XXZ", ""),
        (Position3D(1, -1, 1), "P", "In_2"),
        (Position3D(1, 1, 1), "P", "Out_2"),
    ]
    for pos, kind, label in nodes:
        g.add_cube(pos, kind, label)

    pipes = [(0, 1), (1, 2), (1, 3), (3, 4), (3, 5)]
    for p0, p1 in pipes:
        g.add_pipe(nodes[p0][0], nodes[p1][0])

    if support_flows is not None:
        flows = (
            [f.upper() for f in support_flows]
            if isinstance(support_flows, list)
            else [support_flows.upper()]
        )
        resolved_ports = _resolve_ports(flows)
        g.fill_ports(dict(zip(["In_1", "In_2", "Out_1", "Out_2"], resolved_ports)))
    return g


def _resolve_ports(flows: list[str]) -> list[ZXCube]:
    if any("Y" in f for f in flows):
        raise TQECError("Y basis initialization/measurements are not supported yet.")

    stim_flows = [stim.Flow(f) for f in flows]
    cz = stim.Circuit("CZ 0 1")
    for f in stim_flows:
        if not cz.has_flow(f):
            raise TQECError(f"{f} is not a valid flow for the CZ gate.")

    ports = ["_"] * 4
    for f in stim_flows:
        for i, p in enumerate(str(f.input_copy() + f.output_copy())[1:]):
            if ports[i] == "_":
                ports[i] = p
            elif p != "_" and p != ports[i]:
                raise TQECError(f"Port {i} fails to support both {ports[i]} and {p} observable.")
    # If there are left "I" in the ports, we choose fill them with "Z" ("X" should also work).
    for i in range(4):
        if ports[i] == "_":
            ports[i] = "Z"

    def _vkind(p: str) -> ZXCube:
        return ZXCube.from_str(f"XZ{p}")

    def _hkind(p: str) -> ZXCube:
        return ZXCube.from_str(f"X{p}Z")

    return [_vkind(ports[0]), _hkind(ports[1]), _vkind(ports[2]), _hkind(ports[3])]
