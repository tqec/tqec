from collections import deque
from collections.abc import Iterable
from dataclasses import dataclass, field

import gen
import stim
from gen._layers._det_obs_annotation_layer import DetObsAnnotationLayer
from gen._layers._empty_layer import EmptyLayer
from gen._layers._layer import Layer
from tqecd.fragment import Fragment, FragmentLoop, split_stim_circuit_into_fragments

from tqec.compile.blocks.block import InjectedBlock
from tqec.compile.blocks.enums import Alignment
from tqec.utils.exceptions import TQECError
from tqec.utils.position import BlockPosition2D


class InjectionBuilder:
    """Incrementally weave injected blocks into tree-generated circuit slices.

    The builder maintains three moving windows of circuit data (previous,
    current, next) so that semi-auto flows, detector lookbacks, and measurement
    indices remain consistent as blocks are injected between tree layers.  It
    exposes a minimal API mirroring the tree traversal: append a raw tree slice,
    optionally inject blocks at specific positions, and finally produce the
    composed ``stim.Circuit`` once all slices are processed.
    """

    def __init__(
        self,
        k: int,
        q2i: dict[complex, int],
        o2i: dict[int, int],
    ) -> None:
        """Create a helper class to inject blocks into the layered circuits.

        Args:
            k: The scaling factor of the scalable circuit.
            q2i: A mapping from qubit coordinates to global qubit indices.
            o2i: A mapping from observable keys to observable indices.

        """
        self._k = k
        self._q2i = q2i
        self._o2i = o2i
        self._chunks: list[gen.Chunk] = []

        # Track the previous and current time slice (different z) circuits
        self._prev_circuit = stim.Circuit()
        self._cur_circuit = stim.Circuit()

        # Track the semi-auto open flows for the previous, current, and next circuits
        self._prev_flows: list[gen.FlowSemiAuto] = []
        self._cur_flows: list[gen.FlowSemiAuto] = []
        self._next_flows: list[gen.FlowSemiAuto] = []

        # For those measurements from the tree circuits, i.e. circuits excluding
        # all the injected blocks, track their global indices in the built circuit
        # so far to correctly fix the lookback indices of detectors/observables
        self._mtracker = _TreeMeasurementTracker()
        self._num_global_measurements = 0

        self._current_slice_has_injection: bool = False
        self._out = stim.Circuit()

    def finish(self) -> stim.Circuit:
        """Finalize the building process and return the resulting circuit.

        Two no-op commits flush any remaining buffered slices (``prev`` and
        ``cur``) through the chunk compiler before producing the final circuit.
        """
        # commit 2 extra times for prev and cur circuits
        for _ in range(2):
            self._commit_prev_circuit()
        return gen.compile_chunks_into_circuit(self._chunks)  # type: ignore

    def _commit_prev_circuit(self) -> None:
        """Commit the previous circuit slice and related metadata.

        This resolves semi-auto flows into a concrete chunk, persists detector
        bookkeeping from the tree portion, and rolls the window forward so the
        builder is ready for the next slice.
        """
        if self._prev_circuit:
            fragments = _split_circuit_into_fragment_circuits(self._prev_circuit)
            for i, fragment in enumerate(fragments):
                flows = []
                if i == 0:
                    flows.extend(flow for flow in self._prev_flows if flow.start)
                if i == len(fragments) - 1:
                    flows.extend(flow for flow in self._prev_flows if flow.end)
                # solve the measurement indices that should be included in the flows
                chunk = gen.ChunkSemiAuto(
                    circuit=fragment,
                    flows=flows,
                    q2i=self._q2i,
                    o2i=self._o2i,
                ).solve()
                chunk.verify()
                self._chunks.append(chunk)

        # commit the measurement indices from the tree circuit
        num_commit_measurements = self._mtracker.commit_current_slice()
        if not self._current_slice_has_injection:
            self._num_global_measurements += num_commit_measurements

        self._prev_circuit = self._cur_circuit
        self._prev_flows = self._cur_flows
        self._cur_flows = self._next_flows
        self._next_flows = []

    def append_tree_circuit(self, circuit: stim.Circuit) -> None:
        """Append a new time slice of circuit from the layer tree.

        The slice becomes the active ``cur`` circuit. Tree measurements are
        registered with the tracker so that subsequent injections can safely
        remap their lookbacks against the updated global indices.
        """
        # commit the previous circuit
        self._commit_prev_circuit()
        self._mtracker.start_new_slice(circuit.num_measurements)
        self._cur_circuit = circuit.flattened()
        self._current_slice_has_injection = False
        self._remap_tree_circuit_det_obs()

    def inject(
        self,
        position: BlockPosition2D,
        block: InjectedBlock,
        observable_indices: list[int],
    ) -> None:
        """Inject the given block at the specified position.

        The block's coordinates are translated to align with the requested tree
        position, reindexed against the global qubit map, and then woven into
        the current slice according to the block alignment.
        """
        block_qubit_shape = block.scalable_shape.to_numpy_shape(self._k)

        def transform(q: complex) -> complex:
            return complex(
                q.real + position.x * (block_qubit_shape[0] - 1),
                q.imag + position.y * (block_qubit_shape[1] - 1),
            )

        circuit_with_interface = block.injection_factory(
            self._k, observable_indices
        ).with_transformed_coords(transform)
        circuit = self._reindex_circuit(circuit_with_interface.circuit)
        self._add_semi_auto_det_flows(circuit_with_interface.interface, block.alignment)
        if not self._cur_circuit:
            self._cur_circuit = circuit.flattened()
        else:
            self._cur_circuit = self._weave_into_cur_circuit(circuit, block.alignment)
        self._current_slice_has_injection = True

    def _add_semi_auto_det_flows(self, interface: gen.ChunkInterface, alignment: Alignment) -> None:
        """Register semi-auto flows emitted by the injected block.

        For ``HEAD`` alignment, the block terminates flows begun in the previous
        slice and introduces new ones starting in the current slice. ``TAIL``
        alignment shifts the window forward so the next slice will terminate the
        newly created flows.
        """
        ports = interface.ports
        if alignment == Alignment.HEAD:
            _add_unique_flows(
                [gen.FlowSemiAuto(end=port, mids="auto") for port in ports], self._prev_flows
            )
            _add_unique_flows(
                [gen.FlowSemiAuto(start=port, mids="auto") for port in ports], self._cur_flows
            )
        else:
            _add_unique_flows(
                [gen.FlowSemiAuto(end=port, mids="auto") for port in ports], self._cur_flows
            )
            _add_unique_flows(
                [gen.FlowSemiAuto(start=port, mids="auto") for port in ports], self._next_flows
            )

    def _weave_into_cur_circuit(
        self,
        circuit: stim.Circuit,
        alignment: Alignment,
    ) -> stim.Circuit:
        """Merge the injected circuit into the current tree slice.

        The method pairs layer sequences, remaps detector lookbacks, and updates
        measurement tracking so that subsequent slices observe the correct
        global indices when referencing tree measurements.
        """
        layers0 = gen.LayerCircuit.from_stim_circuit(self._cur_circuit)
        layers1 = gen.LayerCircuit.from_stim_circuit(circuit.flattened())
        paired_layers0, paired_layers1 = _pair_layer_circuits(layers0, layers1, alignment)
        stacked_layers: list[Layer] = []

        self._mtracker.begin_processing()
        c0_global_mids: list[int] = self._mtracker.history_copy()
        c1_global_mids: list[int] = []
        num_local_meas = 0

        # ``track_local`` distinguishes the original tree slice (True) from the
        # injected circuit (False); only the former contributes to the tracker.
        def handle_layer(layer: Layer, global_mids: list[int], track_local: bool) -> None:
            nonlocal num_local_meas
            if isinstance(layer, EmptyLayer):
                return
            if isinstance(layer, DetObsAnnotationLayer):
                stacked_layers.append(
                    self._remap_det_obs_layer(
                        layer=layer,
                        global_mids=global_mids,
                        total_measurements_so_far=self._num_global_measurements,
                    )
                )
                return
            if isinstance(layer, gen.MeasureLayer):
                for _ in layer.targets:
                    mid = self._add_global_measurement(global_mids)
                    if track_local:
                        self._mtracker.note_measurement(num_local_meas, mid)
                        num_local_meas += 1
                stacked_layers.append(layer)
                return
            stacked_layers.append(layer)

        for layer0, layer1 in zip(paired_layers0.layers, paired_layers1.layers):
            handle_layer(layer0, c0_global_mids, True)
            handle_layer(layer1, c1_global_mids, False)

        self._mtracker.finish_processing()
        return gen.LayerCircuit(stacked_layers).with_locally_optimized_layers().to_stim_circuit()

    def _remap_tree_circuit_det_obs(self) -> None:
        """Rebuild detector/observable layers for the active tree slice.

        When no injection occurs, the tree circuit still needs its annotations
        refreshed because earlier injections may have shifted global measurement
        indices. The tracker supplies the canonical history to rewrite each
        ``rec[-k]`` reference relative to the latest totals.
        """
        if not self._cur_circuit:
            self._mtracker.clear_current_slice()
            return

        layer_circuit = gen.LayerCircuit.from_stim_circuit(self._cur_circuit)
        stacked_layers: list[Layer] = []
        global_mids = self._mtracker.history_copy()
        processed_measurements = 0
        next_mid = self._num_global_measurements
        self._mtracker.begin_processing()

        for layer in layer_circuit.layers:
            # Skip placeholder layers entirely; they carry no detector metadata.
            if isinstance(layer, EmptyLayer):
                continue
            if isinstance(layer, DetObsAnnotationLayer):
                total_measurements = self._num_global_measurements + processed_measurements
                stacked_layers.append(
                    self._remap_det_obs_layer(
                        layer=layer,
                        global_mids=global_mids,
                        total_measurements_so_far=total_measurements,
                    )
                )
                continue
            if isinstance(layer, gen.MeasureLayer):
                for _ in layer.targets:
                    mid = next_mid
                    next_mid += 1
                    global_mids.append(mid)
                    self._mtracker.note_measurement(processed_measurements, mid)
                    processed_measurements += 1
                stacked_layers.append(layer)
                continue
            stacked_layers.append(layer)

        self._mtracker.finish_processing()
        self._cur_circuit = (
            gen.LayerCircuit(stacked_layers).with_locally_optimized_layers().to_stim_circuit()
        )

    def _remap_det_obs_layer(
        self,
        layer: DetObsAnnotationLayer,
        global_mids: list[int],
        total_measurements_so_far: int,
    ) -> DetObsAnnotationLayer:
        """Return a copy of ``layer`` with measurement lookbacks rewritten.

        Stim stores detector targets as negative indices relative to the number
        of measurements seen so far. The helper translates those local indices
        into global history offsets produced by the tracker.
        """
        layer_circuit = stim.Circuit()
        for inst in layer.circuit:
            assert isinstance(inst, stim.CircuitInstruction)
            targets = [
                stim.target_rec(
                    lookback_index=self._global_lookback(
                        local_lookback=t.value,
                        global_mids=global_mids,
                        total_measurements_so_far=total_measurements_so_far,
                    )
                )
                for t in inst.targets_copy()
                if t.is_measurement_record_target
            ]
            layer_circuit.append(inst.name, targets, inst.gate_args_copy())
        return DetObsAnnotationLayer(circuit=layer_circuit)

    def _add_global_measurement(self, mid_records: list[int]) -> int:
        """Append a new global measurement id and return it for convenience."""
        mid = self._num_global_measurements
        mid_records.append(mid)
        self._num_global_measurements += 1
        return mid

    def _global_lookback(
        self,
        local_lookback: int,
        global_mids: list[int],
        total_measurements_so_far: int | None = None,
    ) -> int:
        if total_measurements_so_far is None:
            total_measurements_so_far = self._num_global_measurements
        return global_mids[local_lookback] - total_measurements_so_far

    def _reindex_circuit(self, circuit: stim.Circuit) -> stim.Circuit:
        """Reindex the qubits of the given circuit according to the global qubit map.

        If a qubit is not in the global qubit map, a new index is assigned to it.
        """
        reindexed_circuit = stim.Circuit()
        index_map: dict[int, int] = {}
        for i, coords in circuit.get_final_qubit_coordinates().items():
            q = complex(*coords)
            if q in self._q2i:
                index_map[i] = self._q2i[q]
            else:
                ni = len(self._q2i)
                self._q2i[q] = ni
                index_map[i] = ni
        gen.append_reindexed_content_to_circuit(
            out_circuit=reindexed_circuit, content=circuit, qubit_i2i=index_map, obs_i2i={}
        )
        return reindexed_circuit


@dataclass
class _TreeMeasurementTracker:
    """Track measurement indices emitted by the tree circuits.

    ``_TreeMeasurementTracker`` isolates the bookkeeping required to adjust
    detector lookbacks after injections change the total number of measurements
    produced by the composite circuit. It records global measurement ids for
    each slice, tracks which local measurement offsets remain relevant, and
    exposes lifecycle hooks consumed by ``InjectionBuilder``.

    Attributes:
        history: The global measurement ids emitted by prior tree slices.
        pending: The global measurement ids produced while processing the current
            slice.
        tracked_locals: The local measurement indices that still need remapping
            in future passes.
        seen_this_pass: The local indices observed during the active remap pass.

    """

    history: list[int] = field(default_factory=list)
    pending: list[int] = field(default_factory=list)
    tracked_locals: set[int] = field(default_factory=set)
    seen_this_pass: set[int] = field(default_factory=set)

    def start_new_slice(self, num_measurements: int) -> None:
        """Begin tracking a fresh tree slice with ``num_measurements`` locals."""
        self.tracked_locals = set(range(num_measurements))
        self.pending.clear()
        self.seen_this_pass.clear()

    def clear_current_slice(self) -> None:
        """Reset transient state for slices that produced no measurements."""
        self.pending.clear()
        self.tracked_locals.clear()
        self.seen_this_pass.clear()

    def begin_processing(self) -> None:
        """Prepare to process a slice, discarding stale transient data."""
        self.pending.clear()
        self.seen_this_pass.clear()

    def note_measurement(self, local_index: int, global_mid: int) -> None:
        """Record that ``local_index`` maps to ``global_mid`` in this slice."""
        if local_index in self.tracked_locals:
            self.pending.append(global_mid)
            self.seen_this_pass.add(local_index)

    def finish_processing(self) -> None:
        """Persist only the locals touched this pass for the remainder of the slice."""
        self.tracked_locals = set(self.seen_this_pass)

    def history_copy(self) -> list[int]:
        """Return the accumulated global measurement ids so far."""
        return list(self.history)

    def commit_current_slice(self) -> int:
        """Finalize the slice and return the number of committed measurement."""
        num_add_measurements = len(self.pending)
        self.history.extend(self.pending)
        self.clear_current_slice()
        return num_add_measurements


def _pair_layer_circuits(
    c0: gen.LayerCircuit, c1: gen.LayerCircuit, alignment: Alignment
) -> tuple[gen.LayerCircuit, gen.LayerCircuit]:
    """Pair two layer circuits by padding empty layers to the proper positions.

    The pairing algorithm walks both layer sequences in lockstep, inserting
    ``EmptyLayer`` placeholders to satisfy ordering constraints (resets before
    interactions, measures after rotations, etc.) while ensuring the two
    circuits remain spatially disjoint.
    """
    # perform some local optimizations to merge some same-type consecutive layers
    c0 = c0.with_locally_optimized_layers()
    c1 = c1.with_locally_optimized_layers()

    wait_for_matching_reset_layer = alignment == Alignment.HEAD
    wait_for_matching_measure_layer = alignment == Alignment.TAIL

    step = 1 if alignment == Alignment.HEAD else -1
    layers0 = deque(c0.layers[::step])
    layers1 = deque(c1.layers[::step])
    paired_layers0: list[Layer] = []
    paired_layers1: list[Layer] = []

    def append_layers(
        out0: Layer,
        out1: Layer,
        requeue0: Layer | None = None,
        requeue1: Layer | None = None,
    ) -> None:
        paired_layers0.append(out0)
        paired_layers1.append(out1)
        if requeue0 is not None:
            layers0.appendleft(requeue0)
        if requeue1 is not None:
            layers1.appendleft(requeue1)

    while layers0 or layers1:
        layer0 = layers0.popleft() if layers0 else EmptyLayer()
        layer1 = layers1.popleft() if layers1 else EmptyLayer()
        cls0, cls1 = layer0.__class__, layer1.__class__

        if cls0 == cls1:
            append_layers(layer0, layer1)
            if cls0 == gen.ResetLayer:
                wait_for_matching_reset_layer = False
                wait_for_matching_measure_layer = True
            elif cls0 == gen.MeasureLayer:
                wait_for_matching_reset_layer = True
                wait_for_matching_measure_layer = False
            continue

        if isinstance(layer0, EmptyLayer) or isinstance(layer1, EmptyLayer):
            append_layers(layer0, layer1)
            continue

        if isinstance(layer0, DetObsAnnotationLayer):
            append_layers(layer0, EmptyLayer(), requeue1=layer1)
            continue
        if isinstance(layer1, DetObsAnnotationLayer):
            append_layers(EmptyLayer(), layer1, requeue0=layer0)
            continue

        if gen.ResetLayer in (cls0, cls1):
            if cls0 == gen.ResetLayer:
                if wait_for_matching_reset_layer:
                    append_layers(EmptyLayer(), layer1, requeue0=layer0)
                else:
                    append_layers(layer0, EmptyLayer(), requeue1=layer1)
            elif wait_for_matching_reset_layer:
                append_layers(layer0, EmptyLayer(), requeue1=layer1)
            else:
                append_layers(EmptyLayer(), layer1, requeue0=layer0)
            continue

        if gen.MeasureLayer in (cls0, cls1):
            if cls0 == gen.MeasureLayer:
                if wait_for_matching_measure_layer:
                    append_layers(EmptyLayer(), layer1, requeue0=layer0)
                else:
                    append_layers(layer0, EmptyLayer(), requeue1=layer1)
            elif wait_for_matching_measure_layer:
                append_layers(layer0, EmptyLayer(), requeue1=layer1)
            else:
                append_layers(EmptyLayer(), layer1, requeue0=layer0)
            continue

        if {cls0, cls1} == {gen.InteractLayer, gen.RotationLayer}:
            interact_on_0 = cls0 == gen.InteractLayer
            if wait_for_matching_reset_layer:
                if interact_on_0:
                    append_layers(layer0, EmptyLayer(), requeue1=layer1)
                else:
                    append_layers(EmptyLayer(), layer1, requeue0=layer0)
            elif interact_on_0:
                append_layers(EmptyLayer(), layer1, requeue0=layer0)
            else:
                append_layers(layer0, EmptyLayer(), requeue1=layer1)
            continue

        raise TQECError(f"Cannot weave layers of type {cls0} and {cls1} together.")

    assert len(paired_layers0) == len(paired_layers1)
    for l0, l1 in zip(paired_layers0, paired_layers1):
        if l0.touched().intersection(l1.touched()):
            raise TQECError("The two circuits to weave are not fully spatially disjoint.")
    return gen.LayerCircuit(paired_layers0[::step]), gen.LayerCircuit(paired_layers1[::step])


def _add_unique_flows(flows: Iterable[gen.FlowSemiAuto], add_to: list[gen.FlowSemiAuto]) -> None:
    add_to.extend(flow for flow in flows if flow not in add_to)


def _split_circuit_into_fragment_circuits(circuit: stim.Circuit) -> list[stim.Circuit]:
    """Split a stim circuit into a list of fragment circuits."""
    fragments = split_stim_circuit_into_fragments(circuit)
    return [_get_fragment_circuit(f) for f in fragments]


def _get_fragment_circuit(fragment: Fragment | FragmentLoop) -> stim.Circuit:
    if isinstance(fragment, Fragment):
        return fragment.circuit
    circuit = stim.Circuit()
    for f in fragment.fragments:
        circuit += _get_fragment_circuit(f)
    return circuit * fragment.repetitions
