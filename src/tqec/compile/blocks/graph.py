"""Defines :class:`TopologicalComputationGraph` that represents a topological
computation.

## Design choices

A few choices have been made during the design phase of this code, and they
deeply impact the public interface. This section explains what are those choices
and why they have been made.

### Substitution VS removal

Before the introduction of :mod:`tqec.compile.blocks`, junctions (or pipes) were
never strictly instantiated in any public-facing data-structure. Internally, the
junction implementation was instantiated but was directly used to **replace**
plaquettes from the 2 blocks that were touched by the junction. This replacement
was encoded as a "substitution" that was a mapping from (potentially negative)
layer indices to a mapping of plaquettes (i.e., a mapping from indices found in
template instantiation to :class:`~tqec.plaquette.plaquette.Plaquette` instances).

This implementation is correct and worked for a moment, but is strictly less
capable than the chosen implementation in this module.

In this module, junctions are instantiated as
:class:`~tqec.compile.blocks.block.Block` instances, just like cubes, and the
neighbouring cubes have their corresponding boundary being stripped off.
That is exactly equivalent to performing a substitution in the case where each
of the 2 cubes and the junction are represented by templates and plaquettes. But
this method also allows to arbitrary mix cube and junction implementations
without requiring all of them to use templates and plaquettes.

Basically, the junction could potentially be implemented using a scalable raw
quantum circuit, and it would work just fine* with any implementation of the
neighbouring cubes.

*: some care should be used for the qubits on the corner between a junction in
the time dimension and one in the space dimension.

For this reason, this module implements the "removal" technique rather than the
substitution one.
"""

from tqec.compile.blocks.block import Block
from tqec.compile.blocks.enums import border_from_signed_direction
from tqec.compile.blocks.layers.atomic.layout import LayoutLayer
from tqec.compile.blocks.layers.composed.base import BaseComposedLayer
from tqec.compile.blocks.layers.merge import merge_parallel_block_layers
from tqec.compile.blocks.positioning import LayoutPosition2D, LayoutPosition3D
from tqec.utils.exceptions import TQECException
from tqec.utils.position import BlockPosition3D, Direction3D, SignedDirection3D


class TopologicalComputationGraph:
    def __init__(self) -> None:
        """Represents a topological computation with
        :class:`~tqec.compile.blocks.block.Block` instances."""
        self._blocks: dict[LayoutPosition3D, Block] = {}

    def add_cube(self, position: BlockPosition3D, block: Block) -> None:
        if not block.is_cube:
            raise TQECException(
                "Cannot add as a cube a block that is not a cube. The provided "
                f"block ({block}) is not a cube (i.e., has at least one "
                "non-scalable dimension)."
            )
        layout_position = LayoutPosition3D.from_block_position(position)
        if layout_position in self._blocks:
            raise TQECException(
                "Cannot override a block with add_block. There is already an "
                f"entry at {layout_position}."
            )
        self._blocks[layout_position] = block

    def _check_junction(self, source: BlockPosition3D, sink: BlockPosition3D) -> None:
        """Check the validity of a junction between ``source`` and ``sink``.

        Args:
            source: source of the junction. Should be the "smallest" position.
            sink: destination of the junction. Should be the "largest" position.

        Raises:
            TQECException: if ``source`` and ``sink`` are not neighbouring
                positions.
            TQECException: if ``not source < sink``.
            TQECException: if there is already a junction between ``source`` and
                ``sink``.
        """
        if not source.is_neighbour(sink):
            raise TQECException(
                f"Trying to add a junction between {source} and {sink} that are "
                "not neighbouring positions."
            )
        if not source < sink:
            raise TQECException(
                f"Trying to add a junction between {source:=} and {sink:=} that "
                "are not correctly ordered. The following should be verified: "
                "source < sink."
            )
        layout_position = LayoutPosition3D.from_junction_position((source, sink))
        if layout_position in self._blocks:
            raise TQECException(
                "Cannot override a junction with add_junction. There is already "
                f"a junction at {layout_position}."
            )

    def _trim_junctioned_cubes(
        self, source: BlockPosition3D, sink: BlockPosition3D
    ) -> None:
        """Trim the correct border from the cubes in ``source`` and ``sink``.

        This method trims 1 border on each of the cubes at the provided
        ``source`` and ``sink``.

        Args:
            source: source of the junction. Should be the "smallest" position.
            sink: destination of the junction. Should be the "largest" position.

        Raises:
            TQECException: if ``source`` and ``sink`` are not neighbouring
                positions.
            TQECException: if ``not source < sink``.
            TQECException: if there is already a junction between ``source`` and
                ``sink``.
        """
        self._check_junction(source, sink)
        junction_direction = Direction3D.from_neighbouring_positions(source, sink)
        source_pos = LayoutPosition3D.from_block_position(source)
        sink_pos = LayoutPosition3D.from_block_position(sink)
        # Note that below the value of the ``toward_positive`` attribute of
        # SignedDirection3D is fixed by the condition that ``source < sink``.
        self._blocks[source_pos] = self._blocks[source_pos].with_borders_trimmed(
            [border_from_signed_direction(SignedDirection3D(junction_direction, True))]
        )
        self._blocks[sink_pos] = self._blocks[sink_pos].with_borders_trimmed(
            [border_from_signed_direction(SignedDirection3D(junction_direction, False))]
        )

    def add_pipe(
        self, source: BlockPosition3D, sink: BlockPosition3D, block: Block
    ) -> None:
        """Add the provided block as a pipe between ``source`` and ``sink``.

        Raises:
            TQECException: if ``source`` and ``sink`` are not neighbouring
                positions.
            TQECException: if ``not source < sink``.
            TQECException: if there is already a junction between ``source`` and
                ``sink``.
            TQECException: if ``block`` is not a valid pipe (i.e., has not
                exactly 2 scalable dimensions).
        """
        if not block.is_pipe:
            raise TQECException(
                "Cannot add as a pipe a block that is not a pipe. The provided "
                f"block ({block}) is not a pipe (i.e., does not have exactly 2 "
                "scalable dimensions)."
            )
        self._trim_junctioned_cubes(source, sink)
        self._blocks[LayoutPosition3D.from_junction_position((source, sink))] = block

    def layout_layers(
        self,
    ) -> list[list[LayoutLayer | BaseComposedLayer[LayoutLayer]]]:
        """Merge layers happening in parallel at each time step.

        This method considers all the layers contained in added blocks (cubes and
        pipes) and merges them into a sequence of
        :class:`~tqec.compile.blocks.layers.atomic.layout.LayoutLayer` or
        :class:`~tqec.compile.blocks.layers.composed.base.BaseComposedLayer`
        wrapping :class:`~tqec.compile.blocks.layers.atomic.layout.LayoutLayer`
        instances.

        Returns:
            a list of lists of layers. There are 
        """
        zs = [pos.z_ordering for pos in self._blocks.keys()]
        min_z, max_z = min(zs), max(zs)
        blocks_by_z: list[dict[LayoutPosition2D, Block]] = [
            {} for _ in range(min_z, max_z + 1)
        ]
        for pos, block in self._blocks.items():
            blocks_by_z[pos.z_ordering - min_z][pos.as_2d()] = block
        return [merge_parallel_block_layers(blocks) for blocks in blocks_by_z]
