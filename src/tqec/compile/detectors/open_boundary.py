"""Open logical ports without discarding boundary stabilizer constraints."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import stim

from tqec.compile.blocks.layers.atomic.layout import LayoutLayer
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
from tqec.utils.position import Direction3D

if TYPE_CHECKING:
    from tqec.compile.tree.node import LayerNode
    from tqec.compile.tree.tree import LayerTree


@dataclass(frozen=True)
class _OpenBoundaryAnalysis:
    circuit: stim.Circuit
    # Each analysis measurement is a parity of the original circuit's records.
    measurement_map: tuple[int, ...]
    # Correlations with explicit input/output Paulis, in analysis record coordinates.
    logical_flows: tuple[stim.Flow, ...]
    logical_supports: tuple[int, ...]


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


def _boundary_decoder(
    tree: LayerTree, node: LayerNode, cube: Cube, k: int
) -> tuple[stim.Circuit, set[int], set[int], int]:
    """Decode the logical Pauli pair onto its single intersection qubit.

    In the readout basis, first gather the logical-Z parity onto the pivot,
    then undo the logical-X fanout. Conjugating X/Z by this Clifford maps the
    physical logical pair to pivot X/Z. Its inverse is an input encoder. All
    remaining readouts commute with both logical operators.
    """
    if tree._observable_builder not in (
        FIXED_BULK_OBSERVABLE_BUILDER,
        FIXED_BOUNDARY_OBSERVABLE_BUILDER,
    ):
        raise ValueError("No boundary encoder for this convention.")
    kind = cube.kind
    assert isinstance(kind, ZXCube)
    assert isinstance(node._layer, LayoutLayer)
    template, _ = node._layer.to_template_and_plaquettes()
    qubit_map = tree._get_annotation(k).qubit_map
    assert qubit_map is not None

    def line(basis: Basis) -> set[int]:
        assert qubit_map is not None
        orientation = Orientation.VERTICAL if kind.y == basis else Orientation.HORIZONTAL
        coords = build_regular_cube_top_readout_qubits(template.element_shape(k), orientation)
        qubits = ObservableBuilder.transform_coords_into_grid(k, template, coords, cube.position)
        if not qubits or any(q not in qubit_map.qubits for q in qubits):
            raise ValueError("Logical boundary extends outside the patch.")
        return {qubit_map[q] for q in qubits}

    readout, conjugate = line(kind.z), line(kind.z.flipped())
    if len(readout & conjugate) != 1:
        raise ValueError("Logical boundary operators must intersect once.")
    pivot = next(iter(readout & conjugate))
    decoder = stim.Circuit()
    pairs = [(q, pivot) for q in sorted(readout - {pivot})]
    pairs += [(pivot, q) for q in sorted(conjugate - {pivot})]
    for control, target in pairs:
        decoder.append("CX", [control, target] if kind.z == Basis.Z else [target, control])
    return decoder, readout, conjugate, pivot


def _boundary_operations(
    instructions: list[stim.CircuitInstruction],
    interval: tuple[int, int],
    qubits: set[int],
    initialization: bool,
    basis: Basis,
) -> tuple[int, dict[int, int]]:
    """Locate a boundary's reset/readout moment and its original measurement records."""
    start, end = interval
    seen = 0
    found: dict[int, int] = {}
    records: dict[int, int] = {}
    name = ("R" if initialization else "M") + ("X" if basis == Basis.X else "")
    for index, instruction in enumerate(instructions):
        if start <= seen < end and instruction.name == name:
            for offset, target in enumerate(instruction.targets_copy()):
                if target.value in qubits:
                    if target.is_inverted_result_target:
                        raise ValueError("Inverted boundary readouts are not supported.")
                    found[target.value] = index
                    records[target.value] = seen + offset
        single = stim.Circuit()
        single.append(instruction)
        seen += single.num_measurements
    if set(found) != qubits:
        raise ValueError("Cannot locate all logical boundary operations.")
    lower, upper = min(found.values()), max(found.values())
    if any(instructions[i].name not in ("R", "RX", "M", "MX") for i in range(lower, upper)):
        raise ValueError("Logical boundary operations do not form one reset/readout moment.")
    return (upper + 1 if initialization else lower), records


def build_open_boundary_analysis_circuit(
    tree: LayerTree, k: int, circuit: stim.Circuit
) -> _OpenBoundaryAnalysis:
    """Expose quantum logical ports and preserve the original measurement parity mapping.

    Inputs are swapped from fresh, unreset port qubits into a patch encoder.
    Outputs are decoded and swapped to fresh port qubits before readout. The
    vacated pivot is measured deterministically; its record maps to zero.
    Other measurements are syndromes, with an explicit linear map back to the
    original records. No physical Pauli perturbations or flow queries are used.

    Spatial leaves without a regular-patch encoder remain closed. The caller
    must verify that the exposed boundary still distinguishes *all* independent
    correlation surfaces before enabling completion.
    """
    graph, surfaces, observables = (
        tree._logical_block_graph,
        tree._logical_surfaces,
        tree._logical_observables,
    )
    if graph is None or surfaces is None or observables is None:
        raise ValueError("Full logical boundary metadata is unavailable.")
    if len(surfaces) != len(observables):
        raise ValueError("Incomplete correlation-surface measurement binding.")
    instructions = [
        instruction
        for instruction in circuit.without_noise().flattened()
        if isinstance(instruction, stim.CircuitInstruction)
        and instruction.name not in ("DETECTOR", "OBSERVABLE_INCLUDE")
    ]
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

    measurement_map = [1 << i for i in range(circuit.num_measurements)]
    original_to_analysis = measurement_map.copy()
    edits: dict[int, stim.Circuit] = {}
    analysis = stim.Circuit()
    ports: list[tuple[int, bool, int]] = []
    next_qubit = circuit.num_qubits
    leaves = graph.cubes if len(graph.cubes) == 1 else graph.leaf_cubes
    for leaf_index, cube in enumerate(leaves):
        if not isinstance(cube.kind, ZXCube) or cube.is_spatial:
            continue
        pipes = graph.pipes_at(cube.position)
        roles = (
            [True, False]
            if len(graph.cubes) == 1
            else [bool(pipes and pipes[0].direction == Direction3D.Z and pipes[0].u == cube)]
        )
        nodes = get_ordered_leaves(tree._root.children[cube.position.z])
        for initialization in roles:
            node = (
                nodes[0]
                if initialization
                else nodes[
                    -2 if cube.position.z in tree._slices_with_temporal_hadamard_layer else -1
                ]
            )
            decoder, readout, conjugate, pivot = _boundary_decoder(tree, node, cube, k)
            point, records = _boundary_operations(
                instructions, intervals[node], readout | conjugate, initialization, cube.kind.z
            )
            port = next_qubit
            next_qubit += 1
            change = stim.Circuit()
            if initialization:
                change.append("SWAP", [pivot, port])
                change += decoder.inverse()
            else:
                analysis.append("R" if cube.kind.z == Basis.Z else "RX", [port])
                change += decoder
                change.append("SWAP", [pivot, port])
                logical_readout = sum(1 << records[q] for q in readout)
                for q in conjugate:
                    index = records[q]
                    measurement_map[index] = 0 if q == pivot else (1 << index) ^ logical_readout
                    original_to_analysis[index] = (
                        logical_readout ^ (1 << index) if q == pivot else 1 << index
                    )
            edits[point] = edits.get(point, stim.Circuit()) + change
            ports.append((leaf_index, initialization, port))
    for index in range(len(instructions) + 1):
        analysis += edits.get(index, stim.Circuit())
        if index < len(instructions):
            analysis.append(instructions[index])

    logical_flows = []
    for surface, support in zip(surfaces, supports):
        external = surface.external_stabilizer_on_graph(graph)
        if len(external) != len(leaves):
            raise ValueError("External stabilizer boundary size mismatch.")
        inp, out = stim.PauliString(next_qubit), stim.PauliString(next_qubit)
        for leaf_index, initialization, port in ports:
            (inp if initialization else out)[port] = external[leaf_index]
        measurements = 0
        for i, row in enumerate(original_to_analysis):
            if support >> i & 1:
                measurements ^= row
        logical_flows.append(
            stim.Flow(
                input=inp,
                output=out,
                measurements=[i for i in range(circuit.num_measurements) if measurements >> i & 1],
            )
        )
    return _OpenBoundaryAnalysis(
        analysis, tuple(measurement_map), tuple(logical_flows), tuple(supports)
    )
