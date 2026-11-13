from __future__ import annotations

from typing import TYPE_CHECKING

from tqec.circuit.measurement_map import MeasurementRecordsMap
from tqec.compile.blocks.layers.atomic.layout import LayoutLayer
from tqec.compile.blocks.layers.composed.sequenced import SequencedLayers
from tqec.compile.observables.abstract_observable import AbstractObservable
from tqec.compile.observables.builder import (
    ObservableBuilder,
    ObservableComponent,
    get_observable_with_measurement_records,
)
from tqec.utils.position import BlockPosition2D

if TYPE_CHECKING:
    from typing import Literal

    from tqec.compile.tree.node import LayerNode


def get_ordered_leaves(root: LayerNode) -> list[LayerNode]:
    """Return the leaves of the tree in time order."""
    if root.is_leaf:
        return [root]
    return [n for child in root.children for n in get_ordered_leaves(child)]


def get_subtree_z(subtree_root: LayerNode, index: int) -> int:
    """Return the block graph z coordinate of a child of the tree root.

    The z coordinate of the child's :class:`.SequencedLayers` is used when it is set. Else, the
    position ``index`` of the child in the root is used.

    Args:
        subtree_root: a child of the tree root, covering the timespan of one cube.
        index: the position of ``subtree_root`` in the children of the tree root.

    Returns:
        the z coordinate of the time slice that ``subtree_root`` implements.

    """
    layer = subtree_root._layer
    if isinstance(layer, SequencedLayers) and layer.z_coordinate is not None:
        return layer.z_coordinate
    return index


def annotate_observable(
    root: LayerNode,
    k: int,
    observable: AbstractObservable,
    observable_index: int,
    observable_builder: ObservableBuilder,
    slices_with_temporal_hadamard_layer: set[int],
) -> None:
    """Annotates the observables on the tree.

    Args:
        root: root node of the tree.
        k: distance parameter.
        observable: observable to annotate.
        observable_index: index of the observable in the circuit.
        observable_builder: builder that computes and constructs qubits whose
            measurements will be included in the logical observable.
        slices_with_temporal_hadamard_layer: z slices containing a temporal
            Hadamard layer.

    """
    for index, subtree_root in enumerate(root.children):
        z = get_subtree_z(subtree_root, index)
        leaves = get_ordered_leaves(subtree_root)
        obs_slice = observable.slice_at_z(z)

        # Annotate the observable at the bottom of the blocks
        _annotate_observable_at_node(
            leaves[0],
            obs_slice,
            k,
            observable_index,
            observable_builder,
            ObservableComponent.BOTTOM_STABILIZERS,
        )

        readout_layer = leaves[-1]
        if z in slices_with_temporal_hadamard_layer:
            readout_layer = leaves[-2]

            if obs_slice.temporal_hadamard_pipes:
                _annotate_observable_at_node(
                    leaves[-1],
                    obs_slice,
                    k,
                    observable_index,
                    observable_builder,
                    ObservableComponent.REALIGNMENT,
                )

        # Annotate the observable at the top of the blocks
        _annotate_observable_at_node(
            readout_layer,
            obs_slice,
            k,
            observable_index,
            observable_builder,
            ObservableComponent.TOP_READOUTS,
        )

        y_transition = find_y_transition_leaf(leaves) if obs_slice.y_half_cubes else None
        if y_transition is not None:
            y_leaf, top_by_position = y_transition
            _annotate_y_observable_at_node(
                y_leaf, obs_slice, k, observable_index, observable_builder, top_by_position
            )


def _annotate_observable_at_node(
    node: LayerNode,
    obs_slice: AbstractObservable,
    k: int,
    observable_index: int,
    observable_builder: ObservableBuilder,
    component: ObservableComponent,
) -> None:
    circuit = node.get_annotations(k).circuit
    assert circuit is not None
    measurement_record = MeasurementRecordsMap.from_scheduled_circuit(circuit)
    assert isinstance(node._layer, LayoutLayer)
    template, _ = node._layer.to_template_and_plaquettes()
    obs_qubits = observable_builder.build(k, template, obs_slice, component)
    if obs_qubits:
        obs_annotation = get_observable_with_measurement_records(
            obs_qubits, measurement_record, observable_index
        )
        node.get_annotations(k).observables.append(obs_annotation)


def y_switch_top_by_position(leaf: LayerNode) -> dict[BlockPosition2D, Literal["X", "Z"]]:
    """Map each Y half cube's block position to its transition (SWITCH) top boundary basis.

    The fixed-bulk Y logical (midline) is measured during the transition round, so a non-empty
    result also identifies the interior layer at which it should be annotated. A spatial junction
    can host Y cubes of *both* boundary bases at the same z-slice, so the midline geometry must be
    resolved per cube (each ``_YRoundTemplate`` carries its own ``top``), not once per leaf.
    Returns an empty mapping for any layer that is not a Y transition round.
    """
    # Lazy imports: keep the generic annotator free of a convention-specific dependency.
    from tqec.compile.blocks.positioning import LayoutCubePosition2D  # noqa: PLC0415
    from tqec.compile.specs.library.generators.y_basis_fixed_bulk import (  # noqa: PLC0415
        _YRoundTemplate,
    )

    result: dict[BlockPosition2D, Literal["X", "Z"]] = {}
    layer = leaf._layer
    if not isinstance(layer, LayoutLayer):
        return result
    for position, plaquette_layer in layer.layers.items():
        template = getattr(plaquette_layer, "template", None)
        if (
            isinstance(template, _YRoundTemplate)
            and template.kind == "switch"
            and isinstance(position, LayoutCubePosition2D)
        ):
            result[position.to_block_position()] = template.top
    return result


def find_y_transition_leaf(
    leaves: list[LayerNode],
) -> tuple[LayerNode, dict[BlockPosition2D, Literal["X", "Z"]]] | None:
    """Return the first Y transition round among ``leaves``, with its top basis per position.

    The fixed-bulk Y logical (midline) is measured during the transition round, an interior layer
    of a Y half cube, so it is annotated there and not with the top and bottom face components.
    Both :func:`annotate_observable` and the streaming circuit generation use this function, so
    they annotate the Y logical at the same leaf.

    Returns:
        ``(leaf, top_by_position)`` for the first leaf that is a Y transition round, or ``None``
        if no leaf is one.

    """
    for leaf in leaves:
        top_by_position = y_switch_top_by_position(leaf)
        if top_by_position:
            return leaf, top_by_position
    return None


def _annotate_y_observable_at_node(
    node: LayerNode,
    obs_slice: AbstractObservable,
    k: int,
    observable_index: int,
    observable_builder: ObservableBuilder,
    top_by_position: dict[BlockPosition2D, Literal["X", "Z"]],
    component: ObservableComponent | None = None,
) -> None:
    """Annotate the fixed-bulk Y-basis logical (midline) at the transition (SWITCH) round node.

    The Y logical is the product of the single-corner ``MY`` and the two orthogonal midline
    stabiliser measurements, all measured during the transition round -- an interior layer of the
    Y half-cube block, not covered by the top/bottom face annotations. Each Y cube uses the top
    boundary basis of *its own* transition (``top_by_position``), so that a junction mixing X- and
    Z-oriented Y cubes annotates each midline correctly.
    """
    # Lazy import: keep the generic annotator free of a convention-specific dependency.
    from tqec.compile.specs.library.generators.y_basis_fixed_bulk import (  # noqa: PLC0415
        y_corner_local_coord,
        y_observable_local_coords,
    )

    circuit = node.get_annotations(k).circuit
    assert circuit is not None
    records = MeasurementRecordsMap.from_scheduled_circuit(circuit)
    assert isinstance(node._layer, LayoutLayer)
    layout_template, _ = node._layer.to_template_and_plaquettes()
    # Sort by position: ``y_half_cubes`` is a frozenset, and its order follows the hash seed.
    for cube in sorted(obs_slice.y_half_cubes, key=lambda c: c.position):
        y_top = top_by_position.get(BlockPosition2D(cube.position.x, cube.position.y))
        if y_top is None:
            continue
        # The Y logical is read out only by the measurement half cube, whose single-corner ``MY``
        # is measured; the initialization half cube prepares the state (its corner is reset).
        corner_local = [y_corner_local_coord(2 * k + 1, y_top)]
        corner = observable_builder.transform_coords_into_grid(
            k, layout_template, corner_local, cube.position
        )
        if not any(c in records for c in corner):
            continue
        local_coords = y_observable_local_coords(2 * k + 1, y_top)
        qubits = observable_builder.transform_coords_into_grid(
            k, layout_template, local_coords, cube.position
        )
        obs_annotation = get_observable_with_measurement_records(qubits, records, observable_index)
        node.get_annotations(k).observables.append(obs_annotation)
