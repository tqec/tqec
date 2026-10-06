"""Block graph that represents a logical patch rotation operation."""

from tqec.computation.block_graph import BlockGraph
from tqec.computation.cube import LeafCubeKind, PatchRotationKind, ZXCube
from tqec.computation.pipe import PipeKind
from tqec.utils.enums import Basis
from tqec.utils.position import Position3D


def patch_rotation(observable_basis: Basis | None = None) -> BlockGraph:
    """Create a block graph for a temporally aligned patch rotation operation.

    Args:
        observable_basis: The observable basis that the block graph can support. If None,
            the ports are left open. Otherwise, the ports are filled with the given basis.

    Returns:
        A :py:class:`~tqec.computation.block_graph.BlockGraph` instance representing
        the temporally aligned patch rotation operation.

    """
    g = BlockGraph("Temporally Aligned Patch Rotation")
    in_pos = Position3D(0, 0, 0)
    pr_pos = Position3D(0, 0, 1)
    out_pos = Position3D(0, 0, 2)

    g.add_cube(in_pos, LeafCubeKind.PORT, label="In")
    g.add_cube(pr_pos, PatchRotationKind.PR)
    g.add_cube(out_pos, LeafCubeKind.PORT, label="Out")

    g.add_pipe(in_pos, pr_pos, PipeKind.from_str("ZXO"))
    g.add_pipe(pr_pos, out_pos, PipeKind.from_str("XZO"))

    if observable_basis == Basis.Z:
        g.fill_ports({"In": ZXCube.from_str("ZXZ"), "Out": ZXCube.from_str("XZZ")})
    elif observable_basis == Basis.X:
        g.fill_ports({"In": ZXCube.from_str("ZXX"), "Out": ZXCube.from_str("XZX")})

    return g


def spatially_aligned_patch_rotation(observable_basis: Basis | None = None) -> BlockGraph:
    """Create a block graph for a spatially aligned patch rotation operation.

    Args:
        observable_basis: The observable basis that the block graph can support. If None,
            the ports are left open. Otherwise, the ports are filled with the given basis.

    Returns:
        A :py:class:`~tqec.computation.block_graph.BlockGraph` instance representing
        the spatially aligned patch rotation operation.

    """
    g = BlockGraph("Spatially Aligned Patch Rotation")
    in_pos = Position3D(0, 0, 0)
    pr_pos = Position3D(1, 0, 0)
    out_pos = Position3D(2, 0, 0)

    g.add_cube(in_pos, LeafCubeKind.PORT, label="In")
    g.add_cube(pr_pos, PatchRotationKind.PR)
    g.add_cube(out_pos, LeafCubeKind.PORT, label="Out")

    g.add_pipe(in_pos, pr_pos, PipeKind.from_str("OXZ"))
    g.add_pipe(pr_pos, out_pos, PipeKind.from_str("OZX"))

    if observable_basis == Basis.Z:
        g.fill_ports({"In": ZXCube.from_str("ZXZ"), "Out": ZXCube.from_str("ZZX")})
    elif observable_basis == Basis.X:
        g.fill_ports({"In": ZXCube.from_str("XXZ"), "Out": ZXCube.from_str("XZX")})

    return g
