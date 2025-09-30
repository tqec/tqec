"""Defines :class:`TopologicalComputationGraph` that represents a topological computation.

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

from pathlib import Path
from typing import Final

import stim

from tqec.compile.blocks.block import Block, merge_parallel_block_layers
from tqec.compile.blocks.enums import (
    SpatialBlockBorder,
    TemporalBlockBorder,
    border_from_signed_direction,
)
from tqec.compile.blocks.layers.atomic.base import BaseLayer
from tqec.compile.blocks.layers.atomic.plaquettes import PlaquetteLayer
from tqec.compile.blocks.layers.composed.sequenced import SequencedLayers
from tqec.compile.blocks.positioning import (
    LayoutPipePosition2D,
    LayoutPosition2D,
    LayoutPosition3D,
)
from tqec.compile.detectors.database import DetectorDatabase
from tqec.compile.observables.abstract_observable import AbstractObservable
from tqec.compile.observables.builder import ObservableBuilder
from tqec.compile.tree.tree import LayerTree
from tqec.templates.enums import TemplateBorder
from tqec.utils.exceptions import TQECError
from tqec.utils.noise_model import NoiseModel
from tqec.utils.paths import DEFAULT_DETECTOR_DATABASE_PATH
from tqec.utils.position import BlockPosition3D, Direction3D, SignedDirection3D
from tqec.utils.scale import PhysicalQubitScalable2D


def substitute_plaquettes(
    target: PlaquetteLayer, source: PlaquetteLayer, source_border: TemplateBorder
) -> PlaquetteLayer:
    """Perform plaquette substitution on the provided layers.

    Note:
        Most of the time the ``target`` layer will represent a logical qubit and the ``source``
        layer will be a spatial junction template.

    Args:
        target: layer that will have one or more of its :class:`.Plaquette` overwritten.
        source: layer containing the :class:`.Plaquette` instances that will be copied over to
            ``target``.
        source_border: spatial border of the source that should be used. The opposite border will
            be used to update plaquettes on the target layer.

    Returns:
        a copy of ``target`` with plaquettes from ``source`` at its ``source_border.opposite()``
        border.

    """
    source_border_indices = source.template.get_border_indices(source_border)
    target_border_indices = target.template.get_border_indices(source_border.opposite())
    indices_mapping = source_border_indices.to(target_border_indices)
    plaquettes_mapping = {
        ti: target.plaquettes.collection[si]
        for si, ti in indices_mapping.items()
        if si in target.plaquettes.collection
    }
    new_plaquettes = target.plaquettes.with_updated_plaquettes(plaquettes_mapping)
    return PlaquetteLayer(target.template, new_plaquettes, target.trimmed_spatial_borders)


class TopologicalComputationGraph:
    def __init__(
        self,
        scalable_qubit_shape: PhysicalQubitScalable2D,
        observable_builder: ObservableBuilder,
        observables: list[AbstractObservable] | None = None,
    ) -> None:
        """Represent a topological computation with :class:`.Block` instances."""
        self._blocks: dict[LayoutPosition3D, Block] = {}
        # For fixed-bulk convention, temporal Hadamard pipe has its on space-time
        # extent. We need to keep track of the temporal pipes that are at the
        # same layer of at least one temporal Hadamard pipe.
        # We use the bottom cube position `z` to store the temporal pipe, s.t.
        # the pipe is actually at the position `z+0.5`
        self._temporal_pipes_at_hadamard_layer: dict[LayoutPosition3D, Block] = {}
        self._scalable_qubit_shape: Final[PhysicalQubitScalable2D] = scalable_qubit_shape
        self._observables: list[AbstractObservable] | None = observables
        self._observable_builder = observable_builder

    def add_cube(self, position: BlockPosition3D, block: Block) -> None:
        """Add a new cube at ``position`` implemented by the provided ``block``."""
        if not block.is_cube:
            raise TQECError(
                f"Cannot add the block as a cube. The provided block({block}) "
                "has at least one non-scalable dimension."
            )
        self._check_block_spatial_shape(block)
        layout_position = LayoutPosition3D.from_block_position(position)
        if layout_position in self._blocks:
            raise TQECError(
                "Cannot override a block with ``add_cube``. There is already "
                f"an entry at {layout_position}."
            )
        self._blocks[layout_position] = block

    def get_cube(self, position: BlockPosition3D) -> Block:
        """Recover the :class:`.Block` instance at the provided ``position``.

        Args:
            position: position of the block to recover.

        Raises:
            KeyError: if the provided ``position`` has no block associated.

        Returns:
            the :class:`.Block` instance at the provided ``position``.

        """
        layout_position = LayoutPosition3D.from_block_position(position)
        return self._blocks[layout_position]

    def _check_any_pipe(self, source: BlockPosition3D, sink: BlockPosition3D) -> None:
        """Check the validity of a pipe between ``source`` and ``sink``.

        Args:
            source: source of the pipe. Should be the "smallest" position.
            sink: destination of the pipe. Should be the "largest" position.

        Raises:
            TQECError: if ``source`` and ``sink`` are not neighbouring
                positions.
            TQECError: if ``not source < sink``.
            TQECError: if either ``source`` or ``sink`` has not been added
                to the graph.

        """
        if not source.is_neighbour(sink):
            raise TQECError(
                f"Trying to add a pipe between {source} and {sink} that are "
                "not neighbouring positions."
            )
        if not source < sink:
            raise TQECError(
                f"Trying to add a pipe between {source:=} and {sink:=} that "
                "are not correctly ordered. The following should be verified: "
                "source < sink."
            )
        source_layout_position = LayoutPosition3D.from_block_position(source)
        if source_layout_position not in self._blocks:
            raise TQECError(
                f"Cannot add a pipe between {source:=} and {sink:=}: the "
                "source is not in the graph."
            )
        sink_layout_position = LayoutPosition3D.from_block_position(sink)
        if sink_layout_position not in self._blocks:
            raise TQECError(
                f"Cannot add a pipe between {source:=} and {sink:=}: the sink is not in the graph."
            )

    def _check_spatial_pipe(self, source: BlockPosition3D, sink: BlockPosition3D) -> None:
        """Check the validity of a spatial pipe between ``source`` and ``sink``.

        Args:
            source: source of the pipe. Should be the "smallest" position.
            sink: destination of the pipe. Should be the "largest" position.

        Raises:
            TQECError: if ``source`` and ``sink`` are not neighbouring
                positions.
            TQECError: if ``not source < sink``.
            TQECError: if either ``source`` or ``sink`` has not been added
                to the graph.
            TQECError: if there is already a pipe between ``source`` and
                ``sink``.

        """
        self._check_any_pipe(source, sink)
        layout_position = LayoutPosition3D.from_pipe_position((source, sink))
        if layout_position in self._blocks:
            raise TQECError(
                "Cannot override a pipe with ``add_pipe``. "
                f"There is already a pipe at {layout_position}."
            )

    def _check_block_spatial_shape(self, block: Block) -> None:
        if block.scalable_shape != self._scalable_qubit_shape:
            raise TQECError(
                f"Expected a block shaped like a logical qubit "
                f"({self._scalable_qubit_shape}) but got {block.scalable_shape}."
            )

    def _trim_cube_spatial_borders(self, source: BlockPosition3D, sink: BlockPosition3D) -> None:
        """Trim the correct border from the cubes in ``source`` and ``sink``.

        This method trims 1 border on each of the cubes at the provided
        ``source`` and ``sink``.

        Args:
            source: source of the pipe. Should be the "smallest" position.
            sink: destination of the pipe. Should be the "largest" position.

        Raises:
            TQECError: if ``source`` and ``sink`` are not neighbouring
                positions.
            TQECError: if ``not source < sink``.
            TQECError: if either ``source`` or ``sink`` has not been added
                to the graph.
            TQECError: if there is already a pipe between ``source`` and
                ``sink``.

        """
        self._check_spatial_pipe(source, sink)
        juncdir = Direction3D.from_neighbouring_positions(source, sink)
        if juncdir not in Direction3D.spatial_directions():
            raise TQECError(
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
        self._blocks[psource] = self._blocks[psource].with_spatial_borders_trimmed([source_border])
        self._blocks[psink] = self._blocks[psink].with_spatial_borders_trimmed([sink_border])

    def _substitute_part_of_spatial_pipe(
        self,
        pipe_pos: LayoutPosition3D[LayoutPipePosition2D],
        neighbouring_block_layer: PlaquetteLayer,
        spatial_block_border: SpatialBlockBorder,
        temporal_pipe_border: TemporalBlockBorder,
    ) -> None:
        """Substitute the plaquettes of the pipe at ``pipe_pos`` using ``neighbouring_block_layer``.

        The pipe in ``pipe_pos`` is modified in-line.

        Args:
            pipe_pos: position of the pipe that should be modified.
            neighbouring_block_layer: layer of the neighbouring block that
                should partially override the pipe.
            spatial_block_border: spatial border **of the block** that is being
                replaced by the pipe at ``pipe_pos``.
            temporal_pipe_border: temporal border of the pipe that should be
                partially replaced by ``neighbouring_block_layer``.

        Raises:
            KeyError: if ``pipe_pos not in self._blocks``.
            NotImplementError: if the pipe layer that should be partially
                substituted is not an instance of ``PlaquetteLayer``.

        """
        pipe_block = self._blocks[pipe_pos]
        pipe_layer_to_replace = pipe_block.get_temporal_layer_on_border(temporal_pipe_border)
        if not isinstance(pipe_layer_to_replace, PlaquetteLayer):
            raise NotImplementedError(
                "Due to the insertion of a temporal pipe, we need to replace "
                f"part of a pipe {temporal_pipe_border} border with part of the "
                f"temporal pipe. That is not possible because the "
                f"{temporal_pipe_border} spatial pipe border is not an instance "
                f"of {PlaquetteLayer.__name__}. Found an instance of "
                f"{type(pipe_layer_to_replace).__name__}."
            )
        # We now replace part of pipe_layer_to_replace
        replaced_pipe_layer = substitute_plaquettes(
            pipe_layer_to_replace,
            neighbouring_block_layer,
            spatial_block_border.to_template_border(),
        )
        replaced_block = pipe_block.with_temporal_borders_replaced(
            {temporal_pipe_border: replaced_pipe_layer}
        )
        assert replaced_block is not None, "No layer was removed"
        self._blocks[pipe_pos] = replaced_block

    def _replace_temporal_border(
        self,
        block_pos: BlockPosition3D,
        block_border: TemporalBlockBorder,
        layer: BaseLayer,
    ) -> None:
        pblock = LayoutPosition3D.from_block_position(block_pos)
        block = self._blocks[pblock]

        # First replace the layer on the temporal border of the block.
        layer_on_top_of_block = layer
        if block.trimmed_spatial_borders:
            layer_on_top_of_block = layer.with_spatial_borders_trimmed(
                block.trimmed_spatial_borders
            )
        new_block = block.with_temporal_borders_replaced({block_border: layer_on_top_of_block})
        assert new_block is not None, "No layer removal happened, only replacement"
        self._blocks[pblock] = new_block
        # Then, if the block has no trimmed spatial border (i.e., no spatial
        # pipes), we can return because the replacement is over.
        if not block.trimmed_spatial_borders:
            return
        # Else, we also need to replace part of the spatial pipe. Note that for
        # the moment this requires both the block and the spatial pipes to be
        # implemented using template / plaquettes.
        if not isinstance(layer, PlaquetteLayer):
            raise NotImplementedError(
                "Cannot substitute spatial pipe piece from a layer that is "
                f"not a {PlaquetteLayer.__name__} instance."
            )
        for trimmed_spatial_border in block.trimmed_spatial_borders:
            pipe_pos = LayoutPosition3D.from_block_and_signed_direction(
                block_pos, trimmed_spatial_border.value
            )
            self._substitute_part_of_spatial_pipe(
                pipe_pos, layer, trimmed_spatial_border, block_border
            )

    def _replace_temporal_borders(
        self, source: BlockPosition3D, sink: BlockPosition3D, block: Block
    ) -> None:
        self._check_any_pipe(source, sink)
        juncdir = Direction3D.from_neighbouring_positions(source, sink)
        if juncdir not in Direction3D.temporal_directions():
            raise TQECError(
                f"The provided {source:=} and {sink:=} are not describing a "
                "valid temporal pipe. Spatial and temporal pipes should "
                "be handled separately."
            )
        # Source
        self._replace_temporal_border(
            source,
            TemporalBlockBorder.Z_POSITIVE,
            block.get_atomic_temporal_border(TemporalBlockBorder.Z_NEGATIVE),
        )
        # Sink
        self._replace_temporal_border(
            sink,
            TemporalBlockBorder.Z_NEGATIVE,
            block.get_atomic_temporal_border(TemporalBlockBorder.Z_POSITIVE),
        )

    def add_pipe(self, source: BlockPosition3D, sink: BlockPosition3D, block: Block) -> None:
        """Add the provided block as a pipe between ``source`` and ``sink``.

        Raises:
            TQECError: if ``source`` and ``sink`` are not neighbouring
                positions.
            TQECError: if ``not source < sink``.
            TQECError: if there is already a pipe between ``source`` and
                ``sink``.
            TQECError: if ``block`` is not a valid pipe (i.e., has not
                exactly 2 scalable dimensions).

        """
        if not block.is_pipe:
            raise TQECError(
                "Cannot add as a pipe a block that is not a pipe. The provided "
                f"block ({block}) is not a pipe (i.e., does not have exactly 2 "
                "scalable dimensions)."
            )
        if block.is_temporal_pipe:
            self._check_block_spatial_shape(block)
            self._replace_temporal_borders(source, sink, block)
            block_trimmed_temporal_borders = block.with_temporal_borders_replaced(
                {
                    TemporalBlockBorder.Z_NEGATIVE: None,
                    TemporalBlockBorder.Z_POSITIVE: None,
                }
            )
            if block_trimmed_temporal_borders:
                u_pos = LayoutPosition3D.from_block_position(source)
                # We use the bottom cube position `z` to store the temporal pipe, s.t.
                # the pipe is actually at the position `z+0.5`
                self._temporal_pipes_at_hadamard_layer[u_pos] = block_trimmed_temporal_borders
        else:  # block is a spatial pipe
            self._trim_cube_spatial_borders(source, sink)
            key = LayoutPosition3D.from_pipe_position((source, sink))
            self._blocks[key] = block

    def to_layer_tree(self) -> LayerTree:
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
        blocks_by_z: list[dict[LayoutPosition2D, Block]] = [{} for _ in range(min_z, max_z + 1)]
        temporal_pipes_by_z: list[dict[LayoutPosition2D, Block]] = [
            {} for _ in range(min_z, max_z + 1)
        ]
        for pos, block in self._blocks.items():
            blocks_by_z[pos.z - min_z][pos.as_2d()] = block
        for pos, pipe in self._temporal_pipes_at_hadamard_layer.items():
            temporal_pipes_by_z[pos.z - min_z][pos.as_2d()] = pipe
        return LayerTree(
            SequencedLayers(
                [
                    SequencedLayers(
                        merge_parallel_block_layers(blocks, self._scalable_qubit_shape)
                        + merge_parallel_block_layers(pipes, self._scalable_qubit_shape),
                    )
                    for blocks, pipes in zip(blocks_by_z, temporal_pipes_by_z)
                ]
            ),
            abstract_observables=self._observables,
            observable_builder=self._observable_builder,
        )

    def generate_stim_circuit(
        self,
        k: int,
        noise_model: NoiseModel | None = None,
        manhattan_radius: int = 2,
        detector_database: DetectorDatabase | None = None,
        database_path: str | Path = DEFAULT_DETECTOR_DATABASE_PATH,
        do_not_use_database: bool = False,
        only_use_database: bool = False,
    ) -> stim.Circuit:
        """Generate the ``stim.Circuit`` from the compiled graph.

        Args:
            k: scale factor of the templates.
            noise_model: noise model to be applied to the circuit.
            manhattan_radius: radius considered to compute detectors.
                Detectors are not computed and added to the circuit if this
                argument is negative.
            detector_database: an instance to retrieve from / store in detectors
                that are computed as part of the circuit generation. If not given,
                the detectors are retrieved from/stored in the provided
                ``database_path``.
            database_path: specify where to save to after the calculation. This
                defaults to :data:`.DEFAULT_DETECTOR_DATABASE_PATH`
                if not specified. If detector_database is not passed in, the code
                attempts to retrieve the database from this location. The user
                may pass in the path either in str format, or as a Path instance.
            do_not_use_database: if ``True``, even the default database will not be used.
            only_use_database: if ``True``, only detectors from the database
                will be used. An error will be raised if a situation that is not
                registered in the database is encountered.

        Returns:
            A compiled stim circuit.

        """
        circuit = self.to_layer_tree().generate_circuit(
            k,
            manhattan_radius=manhattan_radius,
            detector_database=detector_database,
            database_path=database_path,
            do_not_use_database=do_not_use_database,
            only_use_database=only_use_database,
        )
        # If provided, apply the noise model.
        if noise_model is not None:
            circuit = noise_model.noisy_circuit(circuit)
        return circuit

    def generate_crumble_url(
        self,
        k: int,
        manhattan_radius: int = 2,
        detector_database: DetectorDatabase | None = None,
        add_polygons: bool = False,
    ) -> str:
        """Generate the Crumble URL from the compiled graph.

        Args:
            k: scaling factor.
            manhattan_radius: Parameter for the automatic computation of detectors.
                Should be large enough so that flows canceling each other to
                form a detector are strictly contained in plaquettes that are at
                most at a distance of ``manhattan_radius`` from the central
                plaquette. Detector computation runtime grows with this parameter,
                so you should try to keep it to its minimum. A value too low might
                produce invalid detectors.
            detector_database: existing database of detectors that is used to
                avoid computing detectors if the database already contains them.
                Default to `None` which result in not using any kind of database
                and unconditionally performing the detector computation.
            add_polygons: whether to include polygons in the Crumble URL. If
                ``True``, the polygons representing the stabilizers will be generated
                based on the RPNG information of underlying plaquettes and add
                to the Crumble URL.

        Returns:
            a string representing the Crumble URL of the quantum circuit.

        """
        return self.to_layer_tree().generate_crumble_url(  # pragma: no cover
            k, manhattan_radius, detector_database, add_polygons=add_polygons
        )
