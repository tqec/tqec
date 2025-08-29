from collections.abc import Iterable

import gen
import stim
from gen._layers._det_obs_annotation_layer import DetObsAnnotationLayer
from gen._layers._empty_layer import EmptyLayer
from gen._layers._layer import Layer
from tqecd.fragment import Fragment, FragmentLoop, split_stim_circuit_into_fragments

from tqec.compile.blocks.injected_block import Alignment, InjectedBlock
from tqec.utils.position import BlockPosition2D


class InejctionBuilder:
    def __init__(self, k: int, q2i: dict[complex, int]) -> None:
        """Create a helper class to build the circuit weaved with injected blocks."""
        self._k = k
        self._q2i = q2i

        self._prev_circuit = stim.Circuit()
        self._cur_circuit = stim.Circuit()

        self._prev_flows: list[gen.FlowSemiAuto] = []
        self._cur_flows: list[gen.FlowSemiAuto] = []
        self._next_flows: list[gen.FlowSemiAuto] = []

        self._chunks: list[gen.Chunk] = []

        self._main_circuit_global_mids: list[int] = []
        self._main_circuit_global_mids_buffer: list[int] = []
        self._main_circuit_local_mids: set[int] = set()
        self._num_global_meas = 0

        self._injected: bool = False

    def finish(self) -> stim.Circuit:
        """Finalize the building process and return the resulting circuit."""
        # commit 2 times for prev and cur circuits
        for _ in range(2):
            self.append_circuit(stim.Circuit())
        return gen.compile_chunks_into_circuit(self._chunks)  # type: ignore

    def _commit_prev_chunk(self) -> None:
        if self._prev_circuit:
            fragments = _split_circuit_into_fragment_circuits(self._prev_circuit)
            for i, fragment in enumerate(fragments):
                flows = []
                if i == 0:
                    flows.extend(flow for flow in self._prev_flows if flow.start)
                if i == len(fragments) - 1:
                    flows.extend(flow for flow in self._prev_flows if flow.end)
                chunk = gen.ChunkSemiAuto(
                    circuit=fragment,
                    flows=flows,
                    q2i=self._q2i,
                    o2i={},
                ).solve()
                chunk.verify()
                self._chunks.append(chunk)

        self._prev_circuit = self._cur_circuit
        self._prev_flows = self._cur_flows
        self._cur_flows = self._next_flows
        self._next_flows = []

    def append_circuit(self, circuit: stim.Circuit) -> None:
        """Set the current target time slice of circuit to inject the blocks."""
        self._commit_prev_chunk()
        self._main_circuit_global_mids.extend(self._main_circuit_global_mids_buffer)
        if not self._injected:
            self._num_global_meas += len(self._main_circuit_global_mids_buffer)
        self._main_circuit_global_mids_buffer = list(
            i + self._num_global_meas for i in range(circuit.num_measurements)
        )
        self._main_circuit_local_mids = set(range(circuit.num_measurements))

        self._cur_circuit = circuit.flattened()
        self._injected = False

    def inject(self, position: BlockPosition2D, block: InjectedBlock) -> None:
        """Inject the given block at the specified position."""
        block_qubit_shape = block.scalable_shape.to_numpy_shape(self._k)

        def transform(q: complex) -> complex:
            return complex(
                q.real + position.x * (block_qubit_shape[0] - 1),
                q.imag + position.y * (block_qubit_shape[1] - 1),
            )

        circuit_with_interface = block.injection_factory(self._k, include_observable=False)
        circuit = self._reindex_circuit(
            gen.stim_circuit_with_transformed_coords(circuit_with_interface.circuit, transform)
        )
        interface = circuit_with_interface.interface.with_transformed_coords(transform)
        self._add_semi_auto_flows(interface, block.alignment)
        if not self._cur_circuit:
            self._cur_circuit = circuit
        else:
            self._cur_circuit = self._weave_into_cur_circuit(circuit, block.alignment)
        self._injected = True

    def _add_semi_auto_flows(self, interface: gen.ChunkInterface, alignment: Alignment) -> None:
        ports = interface.ports
        if alignment == Alignment.HEAD:
            _add_flows_if_not_exist(
                [gen.FlowSemiAuto(end=port, mids="auto") for port in ports], self._prev_flows
            )
            _add_flows_if_not_exist(
                [gen.FlowSemiAuto(start=port, mids="auto") for port in ports], self._cur_flows
            )
        else:
            _add_flows_if_not_exist(
                [gen.FlowSemiAuto(end=port, mids="auto") for port in ports], self._cur_flows
            )
            _add_flows_if_not_exist(
                [gen.FlowSemiAuto(start=port, mids="auto") for port in ports], self._next_flows
            )

    def _weave_into_cur_circuit(
        self,
        circuit: stim.Circuit,
        alignment: Alignment,
    ) -> stim.Circuit:
        layers0 = gen.LayerCircuit.from_stim_circuit(self._cur_circuit)
        layers1 = gen.LayerCircuit.from_stim_circuit(circuit.flattened())
        paired_layers0, paired_layers1 = _pair_layer_circuits(layers0, layers1, alignment)
        stacked_layers: list[Layer] = []

        self._main_circuit_global_mids_buffer.clear()
        c0_global_mids: list[int] = list(self._main_circuit_global_mids)
        c1_global_mids: list[int] = []
        updated_local_mids: set[int] = set()
        num_local_meas: int = 0
        for l0, l1 in zip(paired_layers0.layers, paired_layers1.layers):
            for layer, global_mids, track_local in [
                (l0, c0_global_mids, True),
                (l1, c1_global_mids, False),
            ]:
                if isinstance(layer, EmptyLayer):
                    continue
                if isinstance(layer, DetObsAnnotationLayer):
                    layer_circuit = stim.Circuit()
                    for inst in layer.circuit:
                        assert isinstance(inst, stim.CircuitInstruction)
                        targets = [
                            stim.target_rec(
                                lookback_index=self._global_lookback(
                                    local_lookback=t.value, global_mids=global_mids
                                )
                            )
                            for t in inst.targets_copy()
                            if t.is_measurement_record_target
                        ]
                        layer_circuit.append(inst.name, targets, inst.gate_args_copy())
                    stacked_layers.append(DetObsAnnotationLayer(circuit=layer_circuit))
                    continue
                if isinstance(layer, gen.MeasureLayer):
                    for _ in layer.targets:
                        self._add_global_measurement(global_mids)
                        if track_local:
                            if num_local_meas in self._main_circuit_local_mids:
                                updated_local_mids.add(num_local_meas)
                                self._main_circuit_global_mids_buffer.append(global_mids[-1])
                            num_local_meas += 1

                stacked_layers.append(layer)
        self._main_circuit_local_mids = updated_local_mids
        return gen.LayerCircuit(stacked_layers).with_locally_optimized_layers().to_stim_circuit()

    def _add_global_measurement(self, mid_records: list[int]):
        mid_records.append(self._num_global_meas)
        self._num_global_meas += 1

    def _global_lookback(self, local_lookback: int, global_mids: list[int]) -> int:
        return global_mids[local_lookback] - self._num_global_meas

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


def _pair_layer_circuits(
    c0: gen.LayerCircuit, c1: gen.LayerCircuit, alignment: Alignment
) -> tuple[gen.LayerCircuit, gen.LayerCircuit]:
    """Pair two layer circuits by padding empty layers to the proper positions."""
    # perform some local optimizations to merge some same-type consecutive layers
    c0 = c0.with_locally_optimized_layers()
    c1 = c1.with_locally_optimized_layers()

    wait_for_matching_reset_layer = alignment == Alignment.HEAD
    wait_for_matching_measure_layer = alignment == Alignment.TAIL

    step = 1 if alignment == Alignment.HEAD else -1
    layers0 = c0.layers[::step]
    layers1 = c1.layers[::step]
    paired_layers0: list[Layer] = []
    paired_layers1: list[Layer] = []

    while layers0 or layers1:
        layer0 = layers0.pop(0) if layers0 else EmptyLayer()
        layer1 = layers1.pop(0) if layers1 else EmptyLayer()
        cls0, cls1 = layer0.__class__, layer1.__class__
        if cls0 == cls1:
            paired_layers0.append(layer0)
            paired_layers1.append(layer1)
            if cls0 == gen.ResetLayer:
                wait_for_matching_reset_layer = False
                wait_for_matching_measure_layer = True
            elif cls0 == gen.MeasureLayer:
                wait_for_matching_reset_layer = True
                wait_for_matching_measure_layer = False
        elif EmptyLayer in (cls0, cls1):
            paired_layers0.append(layer0)
            paired_layers1.append(layer1)
        elif cls0 == DetObsAnnotationLayer:
            paired_layers0.append(layer0)
            paired_layers1.append(EmptyLayer())
            layers1.insert(0, layer1)
        elif cls1 == DetObsAnnotationLayer:
            paired_layers0.append(EmptyLayer())
            paired_layers1.append(layer1)
            layers0.insert(0, layer0)
        elif cls0 == gen.ResetLayer:
            if wait_for_matching_reset_layer:
                paired_layers0.append(EmptyLayer())
                paired_layers1.append(layer1)
                layers0.insert(0, layer0)
            else:
                paired_layers0.append(layer0)
                paired_layers1.append(EmptyLayer())
                layers1.insert(0, layer1)
        elif cls1 == gen.ResetLayer:
            if wait_for_matching_reset_layer:
                paired_layers0.append(layer0)
                paired_layers1.append(EmptyLayer())
                layers1.insert(0, layer1)
            else:
                paired_layers0.append(EmptyLayer())
                paired_layers1.append(layer1)
                layers0.insert(0, layer0)
        elif cls0 == gen.MeasureLayer:
            if wait_for_matching_measure_layer:
                paired_layers0.append(EmptyLayer())
                paired_layers1.append(layer1)
                layers0.insert(0, layer0)
            else:
                paired_layers0.append(layer0)
                paired_layers1.append(EmptyLayer())
                layers1.insert(0, layer1)
        elif cls1 == gen.MeasureLayer:
            if wait_for_matching_measure_layer:
                paired_layers0.append(layer0)
                paired_layers1.append(EmptyLayer())
                layers1.insert(0, layer1)
            else:
                paired_layers0.append(EmptyLayer())
                paired_layers1.append(layer1)
                layers0.insert(0, layer0)
        elif cls0 == gen.InteractLayer and cls1 == gen.RotationLayer:
            if wait_for_matching_reset_layer:
                paired_layers0.append(layer0)
                paired_layers1.append(EmptyLayer())
                layers1.insert(0, layer1)
            else:
                paired_layers0.append(EmptyLayer())
                paired_layers1.append(layer1)
                layers0.insert(0, layer0)
        elif cls0 == gen.RotationLayer and cls1 == gen.InteractLayer:
            if wait_for_matching_reset_layer:
                paired_layers0.append(EmptyLayer())
                paired_layers1.append(layer1)
                layers0.insert(0, layer0)
            else:
                paired_layers0.append(layer0)
                paired_layers1.append(EmptyLayer())
                layers1.insert(0, layer1)
        else:
            raise NotImplementedError(f"Cannot weave layers of type {cls0} and {cls1} together.")

    assert len(paired_layers0) == len(paired_layers1)
    for l0, l1 in zip(paired_layers0, paired_layers1):
        if l0.touched().intersection(l1.touched()):
            raise ValueError("The two circuits to weave are not fully spatially disjoint.")
    return gen.LayerCircuit(paired_layers0[::step]), gen.LayerCircuit(paired_layers1[::step])


def _add_flows_if_not_exist(
    flows: Iterable[gen.FlowSemiAuto], add_to: list[gen.FlowSemiAuto]
) -> None:
    for flow in flows:
        if flow not in add_to:
            add_to.append(flow)


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
