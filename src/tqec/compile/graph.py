"""Defines :class:`TopologicalComputationGraph` that represents a topological
computation.

## Design choices

A few choices have been made during the design phase of this code, and they
deeply impact the public interface. This section explains what are those choices
and why they have been made.

### Substitution VS removal

Before the introduction of :mod:`tqec.compile.blocks`, pipes (or junctions) were
never strictly instantiated in any public-facing data-structure. Internally, the
pipe implementation was instantiated but was directly used to **replace**
plaquettes from the 2 blocks that were touched by the pipe. This replacement
was encoded as a "substitution" that was a mapping from (potentially negative)
layer indices to a mapping of plaquettes (i.e., a mapping from indices found in
template instantiation to :class:`~tqec.plaquette.plaquette.Plaquette` instances).

With the introduction of layers as the base data-structure to represent QEC
rounds, the substitution approach started to show weaknesses. For example when
the layer schedules of a cube and one of its spatial pipe do not match.

This situation arise with spatial junctions: the central cube implements a
schedule that is

1. initialisation layer,
2. repeat [memory layer],
3. measurement layer,

whereas some of the pipes need to implement

1. initialisation layer,
2. repeat [memory layer 1 alternated with memory layer 2],
3. measurement layer.

The fact that the repeated layer have a different body rules out any possibility
to substitute plaquettes.

To solve that issue, spatial pipes do not substitute plaquettes in cubes but
rather remove the cube boundary and implement its own layers.

For temporal pipes, the layers are replaced in-place within block instances.
"""

from typing import Final

from tqec.compile.blocks.block import Block, merge_parallel_block_layers
from tqec.compile.blocks.enums import (
    SpatialBlockBorder,
    TemporalBlockBorder,
    border_from_signed_direction,
)
from tqec.compile.blocks.layers.composed.sequenced import SequencedLayers
from tqec.compile.blocks.layers.tree import LayerTree
from tqec.compile.blocks.positioning import LayoutPosition2D, LayoutPosition3D
from tqec.utils.exceptions import TQECException
from tqec.utils.position import BlockPosition3D, Direction3D, SignedDirection3D
from tqec.utils.scale import PhysicalQubitScalable2D


class TopologicalComputationGraph:
    def __init__(self, scalable_qubit_shape: PhysicalQubitScalable2D) -> None:
        """Represents a topological computation with
        :class:`~tqec.compile.blocks.block.Block` instances."""
        self._blocks: dict[LayoutPosition3D, Block] = {}
        self._scalable_qubit_shape: Final[PhysicalQubitScalable2D] = (
            scalable_qubit_shape
        )

    def add_cube(self, position: BlockPosition3D, block: Block) -> None:
        if not block.is_cube:
            raise TQECException(
                "Cannot add the block as a cube. The provided block"
                f"({block}) has at least one non-scalable dimension."
            )
        self._check_block_spatial_shape(block)
        layout_position = LayoutPosition3D.from_block_position(position)
        if layout_position in self._blocks:
            raise TQECException(
                "Cannot override a block with ``add_cube``. There is already an "
                f"entry at {layout_position}."
            )
        self._blocks[layout_position] = block

    def _check_any_pipe(self, source: BlockPosition3D, sink: BlockPosition3D) -> None:
        """Check the validity of a pipe between ``source`` and ``sink``.

        Args:
            source: source of the pipe. Should be the "smallest" position.
            sink: destination of the pipe. Should be the "largest" position.

        Raises:
            TQECException: if ``source`` and ``sink`` are not neighbouring
                positions.
            TQECException: if ``not source < sink``.
            TQECException: if either ``source`` or ``sink`` has not been added
                to the graph.
        """
        if not source.is_neighbour(sink):
            raise TQECException(
                f"Trying to add a pipe between {source} and {sink} that are "
                "not neighbouring positions."
            )
        if not source < sink:
            raise TQECException(
                f"Trying to add a pipe between {source:=} and {sink:=} that "
                "are not correctly ordered. The following should be verified: "
                "source < sink."
            )
        source_layout_position = LayoutPosition3D.from_block_position(source)
        if source_layout_position not in self._blocks:
            raise TQECException(
                f"Cannot add a pipe between {source:=} and {sink:=}: the source "
                "is not in the graph."
            )
        sink_layout_position = LayoutPosition3D.from_block_position(sink)
        if sink_layout_position not in self._blocks:
            raise TQECException(
                f"Cannot add a pipe between {source:=} and {sink:=}: the sink "
                "is not in the graph."
            )

    def _check_spatial_pipe(
        self, source: BlockPosition3D, sink: BlockPosition3D
    ) -> None:
        """Check the validity of a spatial pipe between ``source`` and
        ``sink``.

        Args:
            source: source of the pipe. Should be the "smallest" position.
            sink: destination of the pipe. Should be the "largest" position.

        Raises:
            TQECException: if ``source`` and ``sink`` are not neighbouring
                positions.
            TQECException: if ``not source < sink``.
            TQECException: if either ``source`` or ``sink`` has not been added
                to the graph.
            TQECException: if there is already a pipe between ``source`` and
                ``sink``.
        """
        self._check_any_pipe(source, sink)
        layout_position = LayoutPosition3D.from_pipe_position((source, sink))
        if layout_position in self._blocks:
            raise TQECException(
                "Cannot override a pipe with ``add_pipe``. There is already "
                f"a pipe at {layout_position}."
            )

    def _check_block_spatial_shape(self, block: Block) -> None:
        if block.scalable_shape != self._scalable_qubit_shape:
            raise TQECException(
                f"Expected a block shaped like a logical qubit "
                f"({self._scalable_qubit_shape}) but got {block.scalable_shape}."
            )

    def _trim_cube_spatial_borders(
        self, source: BlockPosition3D, sink: BlockPosition3D
    ) -> None:
        """Trim the correct border from the cubes in ``source`` and ``sink``.

        This method trims 1 border on each of the cubes at the provided
        ``source`` and ``sink``.

        Args:
            source: source of the pipe. Should be the "smallest" position.
            sink: destination of the pipe. Should be the "largest" position.

        Raises:
            TQECException: if ``source`` and ``sink`` are not neighbouring
                positions.
            TQECException: if ``not source < sink``.
            TQECException: if either ``source`` or ``sink`` has not been added
                to the graph.
            TQECException: if there is already a pipe between ``source`` and
                ``sink``.
        """
        self._check_spatial_pipe(source, sink)
        juncdir = Direction3D.from_neighbouring_positions(source, sink)
        if juncdir not in Direction3D.spatial_directions():
            raise TQECException(
                f"The provided {source:=} and {sink:=} are not describing a "
                "valid spatial pipe. Spatial and temporal pipes should "
                "be handled separately."
            )
        psource = LayoutPosition3D.from_block_position(source)
        psink = LayoutPosition3D.from_block_position(sink)
        # Note that below the value of the ``toward_positive`` attribute of
        # SignedDirection3D is fixed by the condition that ``source < sink``.
        source_border = border_from_signed_direction(SignedDirection3D(juncdir, True))
        sink_border = border_from_signed_direction(SignedDirection3D(juncdir, False))
        assert isinstance(source_border, SpatialBlockBorder)
        assert isinstance(sink_border, SpatialBlockBorder)
        self._blocks[psource] = self._blocks[psource].with_spatial_borders_trimmed(
            [source_border]
        )
        self._blocks[psink] = self._blocks[psink].with_spatial_borders_trimmed(
            [sink_border]
        )

    def _replace_temporal_borders(
        self, source: BlockPosition3D, sink: BlockPosition3D, block: Block
    ) -> None:
        self._check_any_pipe(source, sink)
        juncdir = Direction3D.from_neighbouring_positions(source, sink)
        if juncdir not in Direction3D.temporal_directions():
            raise TQECException(
                f"The provided {source:=} and {sink:=} are not describing a "
                "valid temporal pipe. Spatial and temporal pipes should "
                "be handled separately."
            )
        # Source
        psource = LayoutPosition3D.from_block_position(source)
        new_source = self._blocks[psource].with_temporal_borders_replaced(
            {
                TemporalBlockBorder.Z_POSITIVE: block.get_temporal_border(
                    TemporalBlockBorder.Z_POSITIVE
                )
            }
        )
        assert new_source is not None, "We did not remove any layers."
        self._blocks[psource] = new_source
        # Sink
        psink = LayoutPosition3D.from_block_position(sink)
        new_sink = self._blocks[psink].with_temporal_borders_replaced(
            {
                TemporalBlockBorder.Z_NEGATIVE: block.get_temporal_border(
                    TemporalBlockBorder.Z_NEGATIVE
                )
            }
        )
        assert new_sink is not None, "We did not remove any layers."
        self._blocks[psink] = new_sink

    def add_pipe(
        self, source: BlockPosition3D, sink: BlockPosition3D, block: Block
    ) -> None:
        """Add the provided block as a pipe between ``source`` and ``sink``.

        Raises:
            TQECException: if ``source`` and ``sink`` are not neighbouring
                positions.
            TQECException: if ``not source < sink``.
            TQECException: if there is already a pipe between ``source`` and
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
        if block.is_temporal_pipe:
            self._check_block_spatial_shape(block)
            self._replace_temporal_borders(source, sink, block)
        else:  # block is a spatial pipe
            self._trim_cube_spatial_borders(source, sink)
            key = LayoutPosition3D.from_pipe_position((source, sink))
            self._blocks[key] = block

    def to_layout_tree(self) -> LayerTree:
        """Merge layers happening in parallel at each time step.

        This method considers all the layers contained in added blocks (cubes and
        pipes) and merges them into a sequence of
        :class:`~tqec.compile.blocks.layers.atomic.layout.LayoutLayer` or
        :class:`~tqec.compile.blocks.layers.composed.base.BaseComposedLayer`
        wrapping :class:`~tqec.compile.blocks.layers.atomic.layout.LayoutLayer`
        instances.

        Returns:
            A tree representing the topological computation.

            The root node of the returned tree is an instance of
            :class:`~tqec.compile.blocks.layers.composed.sequenced.SequencedLayers`.
            Each child of the root node represents the computation happening during
            one block of time.

            Each child of the root node is also an instance of
            :class:`~tqec.compile.blocks.layers.composed.sequenced.SequencedLayers`.
        """

        zs = [pos.z for pos in self._blocks.keys()]
        min_z, max_z = min(zs), max(zs)
        blocks_by_z: list[dict[LayoutPosition2D, Block]] = [
            {} for _ in range(min_z, max_z + 1)
        ]
        for pos, block in self._blocks.items():
            blocks_by_z[pos.z - min_z][pos.as_2d()] = block
        return LayerTree(
            SequencedLayers(
                [
                    SequencedLayers(
                        merge_parallel_block_layers(blocks, self._scalable_qubit_shape)
                    )
                    for blocks in blocks_by_z
                ]
            )
        )
