"""Internal compilation of external logical Paulis into circuit perturbations."""

from __future__ import annotations

import warnings
from typing import TYPE_CHECKING

import stim

from tqec.compile.blocks.layers.atomic.layout import LayoutLayer
from tqec.compile.detectors.exact import _instruction_measurement_count, _strip_annotations
from tqec.compile.detectors.space import GF2Basis
from tqec.compile.observables.builder import ObservableBuilder
from tqec.compile.observables.fixed_boundary_builder import FIXED_BOUNDARY_OBSERVABLE_BUILDER
from tqec.compile.observables.fixed_bulk_builder import (
    FIXED_BULK_OBSERVABLE_BUILDER,
    build_regular_cube_top_readout_qubits,
)
from tqec.compile.tree.annotators.observables import (
    get_ordered_leaves,
    resolve_observable_measurements,
)
from tqec.computation.cube import Cube, ZXCube
from tqec.utils.enums import Basis, Orientation
from tqec.utils.exceptions import TQECError
from tqec.utils.position import Direction3D

if TYPE_CHECKING:
    from tqec.compile.tree.node import LayerNode
    from tqec.compile.tree.tree import LayerTree


def _measurement_intervals(root: LayerNode, k: int) -> dict[LayerNode, tuple[int, int]]:
    intervals = {}
    seen = 0

    def visit(node: LayerNode) -> None:
        nonlocal seen
        start = seen
        if node.is_leaf:
            circuit = node.get_annotations(k).circuit
            assert circuit is not None
            seen += circuit.get_circuit().num_measurements
        else:
            for child in node.children:
                visit(child)
            if node.repetitions is not None:
                seen = start + (seen - start) * node.repetitions.integer_eval(k)
        intervals[node] = (start, seen)

    visit(root)
    return intervals


def _build_logical_pauli_support(
    tree: LayerTree, k: int, cube: Cube, basis: Basis, node: LayerNode
) -> list[int]:
    """Use the observable builders' regular-patch logical-line convention."""
    if tree._observable_builder not in (
        FIXED_BULK_OBSERVABLE_BUILDER,
        FIXED_BOUNDARY_OBSERVABLE_BUILDER,
    ):
        raise ValueError("No logical string builder for this convention.")
    if not isinstance(cube.kind, ZXCube) or cube.is_spatial:
        raise ValueError("No physical logical string builder for this leaf kind.")
    if not isinstance(node._layer, LayoutLayer):
        raise ValueError("Logical boundary is not a patch layout.")
    template, _ = node._layer.to_template_and_plaquettes()
    orientation = Orientation.VERTICAL if cube.kind.y == basis else Orientation.HORIZONTAL
    coords = build_regular_cube_top_readout_qubits(template.element_shape(k), orientation)
    qubits = ObservableBuilder.transform_coords_into_grid(k, template, coords, cube.position)
    qubit_map = tree._get_annotation(k).qubit_map
    assert qubit_map is not None
    if not qubits or any(q not in qubit_map.qubits for q in qubits):
        raise ValueError("Physical logical string is outside the patch.")
    return sorted(qubit_map[q] for q in qubits)


def _insertion_point(
    instructions: list[stim.CircuitInstruction],
    intervals: dict[LayerNode, tuple[int, int]],
    node: LayerNode,
    targets: list[int],
    initialization: bool,
) -> int:
    start, end = intervals[node]
    seen = 0
    found = {}
    for index, instruction in enumerate(instructions):
        count = _instruction_measurement_count(instruction)
        if start <= seen < end:
            names = ("R", "RX", "RY") if initialization else ("M", "MX", "MY")
            if instruction.name in names:
                for target in instruction.targets_copy():
                    if target.value in targets:
                        found[target.value] = index
        seen += count
    if set(found) != set(targets):
        raise ValueError("Cannot locate the full logical string at the boundary.")
    # All data resets/readouts must be in one moment: inserting part of a logical
    # string on either side of a stabilizer interaction could create syndrome.
    lower, upper = min(found.values()), max(found.values())
    if any(instructions[i].name == "TICK" for i in range(lower, upper)):
        raise ValueError("Logical boundary operations span multiple moments.")
    return upper + 1 if initialization else lower


def build_logical_perturbations(
    tree: LayerTree, k: int, circuit: stim.Circuit
) -> tuple[list[stim.Circuit] | None, list[int] | None]:
    """Compile a symplectic dual of the complete external stabilizer generators.

    Failure is explicit and disables completion; local detector candidates never
    supply missing logical semantics.
    """
    graph = tree._logical_block_graph
    surfaces = tree._logical_surfaces
    observables = tree._logical_observables
    if graph is None or surfaces is None or observables is None:
        return None, None
    try:
        intervals = _measurement_intervals(tree._root, k)
        supports = []
        for observable in observables:
            row = 0
            for node, bound in resolve_observable_measurements(
                tree._root,
                k,
                observable,
                0,
                tree._observable_builder,
                tree._slices_with_temporal_hadamard_layer,
            ):
                for offset in bound.measurement_offsets:
                    row ^= 1 << (intervals[node][1] + offset)
            supports.append(row)
        leaves = graph.leaf_cubes if len(graph.cubes) > 1 else graph.cubes
        external = [surface.external_stabilizer_on_graph(graph) for surface in surfaces]
        if any(len(paulis) != len(leaves) for paulis in external):
            raise ValueError("External stabilizer boundary size mismatch.")
        stripped, _, _ = _strip_annotations(circuit.without_noise())
        instructions = [
            instruction
            for instruction in stripped.flattened()
            if isinstance(instruction, stim.CircuitInstruction)
        ]
        columns = GF2Basis()
        physical = []
        for i, cube in enumerate(leaves):
            pipes = graph.pipes_at(cube.position)
            initialization = bool(
                pipes and pipes[0].direction == Direction3D.Z and pipes[0].u == cube
            )
            nodes = get_ordered_leaves(tree._root.children[cube.position.z])
            node = (
                nodes[0]
                if initialization
                else nodes[
                    -2 if cube.position.z in tree._slices_with_temporal_hadamard_layer else -1
                ]
            )
            for basis in (Basis.X, Basis.Z):
                response = sum(
                    (p[i] not in ("I", "_", basis.value)) << j for j, p in enumerate(external)
                )
                if not response or columns.contains(response):
                    continue
                try:
                    targets = _build_logical_pauli_support(tree, k, cube, basis, node)
                    point = _insertion_point(instructions, intervals, node, targets, initialization)
                except ValueError:
                    # A dual is not unique. Other boundary qubits may provide
                    # this direction even when this leaf has no string builder.
                    continue
                columns.add(response)
                physical.append((point, basis.value, targets))
        if columns.rank != len(surfaces):
            raise ValueError("External stabilizers do not have a complete physical dual.")
        perturbations = []
        for j in range(len(surfaces)):
            coefficients = columns.decompose(1 << j)
            if coefficients is None:
                raise ValueError("Cannot construct the logical symplectic dual.")
            insertions: dict[int, list[tuple[str, list[int]]]] = {}
            for i, (point, basis, targets) in enumerate(physical):
                if coefficients >> i & 1:
                    insertions.setdefault(point, []).append((basis, targets))
            perturbed = stim.Circuit()
            for index in range(len(instructions) + 1):
                for basis, targets in insertions.get(index, []):
                    perturbed.append(basis, targets)
                if index < len(instructions):
                    perturbed.append(instructions[index])
            perturbations.append(perturbed)
        return perturbations, supports
    except (ValueError, TQECError, NotImplementedError) as error:
        warnings.warn(f"Exact detector completion disabled: {error}", stacklevel=2)
        return None, None
