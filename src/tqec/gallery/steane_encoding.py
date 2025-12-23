"""Block graph that represents a logical stability experiment."""

from tqec.computation.block_graph import BlockGraph, ZXCube
from tqec.utils.enums import Basis
from tqec.utils.paths import GALLERY_DAE_DIR

STEANE_CODE_DAE = GALLERY_DAE_DIR / "steane_encoding.dae"


def steane_encoding(observable_basis: Basis | None = None) -> BlockGraph:
    """Create a block graph that represents a Steane encoding circuit.

    The block graph is created from a DAE file that describes the circuit.

    Args:
        observable_basis: The observable basis that the block graph can support. If
            None, the block graph will have open ports. Otherwise, the ports will be
            filled with the given observable basis.

    Returns:
        A :py:class:`~tqec.computation.block_graph.BlockGraph` instance.

    """
    graph = BlockGraph.from_dae_file(STEANE_CODE_DAE)
    if observable_basis is not None:
        graph.fill_ports(
            {f"Port{port}": ZXCube(Basis.Z, Basis.X, observable_basis) for port in (3, 4)}
        )
        graph.fill_ports(
            {f"Port{port}": ZXCube(Basis.X, Basis.Z, observable_basis) for port in (1, 2, 5, 6)}
        )
        graph.fill_ports(ZXCube(observable_basis, Basis.X, Basis.Z))
    return graph
