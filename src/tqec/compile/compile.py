"""Defines :class:`~.compile.CompiledGraph` and
:func:`~.compile.compile_block_graph`."""

import itertools
import warnings
from dataclasses import dataclass
from typing import Literal, Sequence, cast

import stim

from tqec.circuit.coordinates import StimCoordinates
from tqec.circuit.measurement_map import MeasurementRecordsMap
from tqec.circuit.qubit_map import QubitMap
from tqec.circuit.schedule import ScheduledCircuit
from tqec.compile.block import BlockLayout, CompiledBlock
from tqec.compile.detectors.compute import compute_detectors_for_fixed_radius
from tqec.compile.detectors.database import DetectorDatabase
from tqec.compile.detectors.detector import Detector
from tqec.compile.observables.abstract_observable import (
    AbstractObservable,
    compile_correlation_surface_to_abstract_observable,
)
from tqec.compile.observables.builder import inplace_add_observable
from tqec.compile.specs.base import (
    BlockBuilder,
    CubeSpec,
    PipeSpec,
    SubstitutionBuilder,
)
from tqec.compile.specs.library.standard import (
    STANDARD_BLOCK_BUILDER,
    STANDARD_SUBSTITUTION_BUILDER,
)
from tqec.computation.block_graph import BlockGraph
from tqec.computation.correlation import CorrelationSurface
from tqec.computation.zx_graph import ZXEdge, ZXNode
from tqec.exceptions import TQECException, TQECWarning
from tqec.noise_model import NoiseModel
from tqec.plaquette.plaquette import Plaquettes, RepeatedPlaquettes
from tqec.position import Direction3D, Position3D
from tqec.scale import round_or_fail
from tqec.templates.indices.base import Template
from tqec.templates.indices.layout import LayoutTemplate


@dataclass
class CompiledGraph:
    """Represents a compiled block graph.

    This class should be easy to scale and generate circuits directly.

    Attributes:
        layout_slices: a list of :class:`~tqec.templates.indices.layout.BlockLayout`
            instances that represent the compiled blocks at contiguous time
            slices.
        observables: a list of
            :class:`~tqec.compile.observables.AbstractObservable`
            instances that represent the observables to be included in the
            compiled circuit.
    """

    layout_slices: list[BlockLayout]
    """Timeslices of compiled blocks arranged as 2-dimensional slices."""

    observables: list[AbstractObservable]
    """Observables to be included in the final ``stim.Circuit`` instance."""

    def __post_init__(self) -> None:
        if len(self.layout_slices) == 0:
            raise TQECException(
                "The compiled graph should have at least one time slice "
                "but got an empty layout_slices."
            )
        # Use warning instead of exception because a qec circuit without observable
        # may still be useful, e.g. do statistics on the detection events.
        if len(self.observables) == 0:
            warnings.warn("The compiled graph includes no observable.", TQECWarning)

    def generate_stim_circuit(
        self,
        k: int,
        noise_model: NoiseModel | None = None,
        manhattan_radius: int = 2,
        detector_database: DetectorDatabase | None = None,
        only_use_database: bool = False,
    ) -> stim.Circuit:
        """Generate the ``stim.Circuit`` from the compiled graph.

        Args:
            k: scale factor of the templates.
            noise_models: noise models to be applied to the circuit.
            manhattan_radius: radius considered to compute detectors.
                Detectors are not computed and added to the circuit if this
                argument is negative.
            detector_database: an instance to retrieve from / store in detectors
                that are computed as part of the circuit generation.
            only_use_database: if ``True``, only detectors from the database
                will be used. An error will be raised if a situation that is not
                registered in the database is encountered.

        Returns:
            A compiled stim circuit.
        """
        # Generate the quantum circuits, time slice by time slice, layer by layer.
        # Note that the circuits have to be shifted to their correct position.
        circuits: list[list[ScheduledCircuit]] = []
        for layout in self.layout_slices:
            circuits.append(layout.get_shifted_circuits(k))
        # The generated circuits cannot, for the moment, be merged together because
        # the qubit indices used are likely inconsistent between circuits (a given
        # index `i` might be used for different qubits in different circuits).
        # Fix that now so that we do not have to think about it later.
        global_qubit_map = self._relabel_circuits_qubit_indices_inplace(circuits)

        # Construct the observables and add them in-place to the built circuits.
        for observable_index, observable in enumerate(self.observables):
            inplace_add_observable(
                k,
                circuits,
                template_slices=[layout.template for layout in self.layout_slices],
                abstract_observable=observable,
                observable_index=observable_index,
            )

        # Compute the detectors and add them in-place in circuits
        flattened_circuits: list[ScheduledCircuit] = sum(
            circuits, start=cast(list[ScheduledCircuit], [])
        )
        flattened_templates: list[LayoutTemplate] = sum(
            (
                [layout.template for _ in range(layout.num_layers)]
                for layout in self.layout_slices
            ),
            start=cast(list[LayoutTemplate], []),
        )
        flattened_plaquettes: list[Plaquettes] = sum(
            (layout.layers for layout in self.layout_slices),
            start=cast(list[Plaquettes], []),
        )
        if manhattan_radius >= 0:
            self._inplace_add_detectors_to_circuits(
                flattened_circuits,
                flattened_templates,
                flattened_plaquettes,
                k,
                manhattan_radius,
                detector_database=detector_database,
                only_use_database=only_use_database,
            )
        # Assemble the circuits.
        circuit = global_qubit_map.to_circuit()
        for circ, plaq in zip(flattened_circuits[:-1], flattened_plaquettes[:-1]):
            if isinstance(plaq, RepeatedPlaquettes):
                circuit += circ.get_repeated_circuit(
                    round_or_fail(plaq.repetitions(k)), include_qubit_coords=False
                )
            else:
                circuit += circ.get_circuit(include_qubit_coords=False)
            circuit.append("TICK", [], [])
        circuit += flattened_circuits[-1].get_circuit(include_qubit_coords=False)

        # If provided, apply the noise model.
        if noise_model is not None:
            circuit = noise_model.noisy_circuit(circuit)
        return circuit

    @staticmethod
    def _relabel_circuits_qubit_indices_inplace(
        circuits: Sequence[Sequence[ScheduledCircuit]],
    ) -> QubitMap:
        """Equivalent to :func:`relabel_circuits_qubit_indices` but applied to
        nested lists and performing the modifications in-place in the provided
        ``circuits``.

        Args:
            circuits: circuit instances to remap. This parameter is mutated by
                this function.

        Returns:
            qubit map used to remap the qubit indices that is valid for all the
            circuits provided as input after this method executed.
        """
        used_qubits = frozenset(
            # Using itertools to avoid the edge case where there is no circuit
            itertools.chain.from_iterable(
                [c.qubits for clayer in circuits for c in clayer]
            )
        )
        global_qubit_map = QubitMap.from_qubits(sorted(used_qubits))
        global_q2i = global_qubit_map.q2i
        for circuit in itertools.chain.from_iterable(circuits):
            local_indices_to_global_indices = {
                local_index: global_q2i[q]
                for local_index, q in circuit.qubit_map.items()
            }
            circuit.map_qubit_indices(local_indices_to_global_indices, inplace=True)
        return global_qubit_map

    @staticmethod
    def _inplace_add_detectors_to_circuits(
        circuits: Sequence[ScheduledCircuit],
        templates: Sequence[Template],
        plaquettes: Sequence[Plaquettes],
        k: int,
        manhattan_radius: int = 2,
        detector_database: DetectorDatabase | None = None,
        only_use_database: bool = False,
    ) -> None:
        """Compute and add in-place to ``circuits`` valid detectors.

        Args:
            circuits: circuits to add detectors to. Should have the same number
                of entries as ``templates`` and ``plaquettes``.
            templates: templates used to generate the provided ``circuits``. Should
                have the same number of entries as ``circuits`` and ``plaquettes``.
            plaquettes: plaquettes used to generate the provided ``circuits``.
                Should have the same number of entries as ``circuits`` and
                ``templates``.
            k: scaling parameter that has been used to generate the provided
                ``circuits``.
            manhattan_radius: radius considered to compute detectors. Defaults
                to 2.
            detector_database: a database associating "situations" (subtemplate
                and plaquettes) to already computed detectors. Defaults to None,
                meaning that no database is provided and all the detectors should
                be re-computed.
            only_use_database: if True, only detectors present in the provided
                database are used. If the database is `None` or if a "situation"
                that is not in the database is encountered, an exception will be
                raised. Defaults to False, meaning that encountered "situations"
                that are not present in the database will be analysed to find
                detectors.
        """
        # Start with the first circuit, as this is a special case.
        first_template = templates[0]
        first_plaquettes = plaquettes[0]
        first_slice_detectors = compute_detectors_for_fixed_radius(
            (first_template,),
            k,
            (first_plaquettes,),
            manhattan_radius,
            detector_database,
            only_use_database,
        )
        # Initialise the measurement records map with the first circuit.
        mrecords_map = MeasurementRecordsMap.from_scheduled_circuit(circuits[0])
        # Add the detectors to the first circuit
        CompiledGraph._inplace_add_detectors_to_circuit(
            circuits[0], mrecords_map, first_slice_detectors
        )

        # Now, iterate over all the pairs of circuits.
        for i in range(1, len(circuits)):
            current_circuit = circuits[i]
            slice_detectors = compute_detectors_for_fixed_radius(
                (templates[i - 1], templates[i]),
                k,
                (plaquettes[i - 1], plaquettes[i]),
                manhattan_radius,
                detector_database,
                only_use_database,
            )
            mrecords_map = mrecords_map.with_added_measurements(
                MeasurementRecordsMap.from_scheduled_circuit(current_circuit)
            )
            CompiledGraph._inplace_add_detectors_to_circuit(
                current_circuit,
                mrecords_map,
                slice_detectors,
                shift_coords_by=StimCoordinates(0, 0, 1),
            )
        # We are now over, all the detectors should be added inplace to the end
        # of the last circuit containing a measurement involved in the detector.

    @staticmethod
    def _inplace_add_detectors_to_circuit(
        circuit: ScheduledCircuit,
        mrecords_map: MeasurementRecordsMap,
        detectors: Sequence[Detector],
        shift_coords_by: StimCoordinates | None = None,
    ) -> None:
        """Add the provided ``detectors`` to the provided ``circuits``,
        inserting a ``SHIFT_COORDS`` instruction before ``DETECTOR``
        instructions if required.

        Args:
            circuit: circuit to modify in-place.
            mrecords_map: a measurement record map containing at least all the
                measurements in the provided ``detectors``.
            detectors: all the detectors that should be added at the end of the
                provided ``circuit``.
            shift_coords_by: if not None, used to insert a ``SHIFT_COORDS``
                instruction before inserting the ``DETECTOR`` instructions.
                Defaults to None.
        """
        if shift_coords_by is not None:
            circuit.append_annotation(
                stim.CircuitInstruction(
                    "SHIFT_COORDS", [], shift_coords_by.to_stim_coordinates()
                )
            )
        for d in sorted(detectors, key=lambda d: d.coordinates):
            circuit.append_annotation(d.to_instruction(mrecords_map))


def compile_block_graph(
    block_graph: BlockGraph,
    block_builder: BlockBuilder = STANDARD_BLOCK_BUILDER,
    substitution_builder: SubstitutionBuilder = STANDARD_SUBSTITUTION_BUILDER,
    observables: list[CorrelationSurface] | Literal["auto"] | None = "auto",
) -> CompiledGraph:
    """Compile a block graph.

    Args:
        block_graph: The block graph to compile.
        block_builder: A callable that specifies how to build the
            :class:`~.block.CompiledBlock` from the specified
            :class:`~.specs.base.CubeSpecs`. Defaults to the block builder for
            the CSS type surface code.
        substitution_builder: A callable that specifies how to build the
            substitution plaquettes from the specified
            :class:`~.specs.base.PipeSpec`. Defaults to the substitution builder
            for the CSS type surface code.
        observables: correlation surfaces that should be compiled into
            observables and included in the compiled circuit.
            If set to ``"auto"``, the correlation surfaces will be automatically
            determined from the block graph. If a list of correlation surfaces
            is provided, only those surfaces will be compiled into observables
            and included in the compiled circuit. If set to ``None``, no
            observables will be included in the compiled circuit.

    Returns:
        A :class:`CompiledGraph` object that can be used to generate a
        ``stim.Circuit`` and scale easily.
    """
    if block_graph.num_ports != 0:
        raise TQECException(
            "Can not compile a block graph with open ports into circuits."
        )
    cube_specs = {
        cube: CubeSpec.from_cube(cube, block_graph) for cube in block_graph.nodes
    }

    # 0. Set the minimum z of block graph to 0.(time starts from zero)
    shift_z = -min(cube.position.z for cube in block_graph.nodes)
    block_graph = block_graph.shift_min_z_to_zero()

    # 1. Get the base compiled blocks before applying the substitution rules.
    blocks: dict[Position3D, CompiledBlock] = {}
    for cube in block_graph.nodes:
        spec = cube_specs[cube]
        blocks[cube.position] = block_builder(spec)

    # 2. Apply the substitution rules to the compiled blocks inplace.
    pipes = block_graph.edges
    time_pipes = [pipe for pipe in pipes if pipe.direction == Direction3D.Z]
    space_pipes = [pipe for pipe in pipes if pipe.direction != Direction3D.Z]
    # Note that the order of the pipes to apply the substitution rules is important.
    # To keep the time-direction substitution rules from removing the extra resets
    # added by the space-direction substitution rules, we first apply the time-direction
    # substitution rules.
    for pipe in time_pipes + space_pipes:
        u, v = pipe.u, pipe.v
        upos, vpos = u.position, v.position
        key = PipeSpec(
            (cube_specs[u], cube_specs[v]),
            (blocks[upos].template, blocks[vpos].template),
            pipe.kind,
        )
        substitution = substitution_builder(key)
        blocks[upos].update_layers(substitution.src)
        blocks[vpos].update_layers(substitution.dst)

    # 3. Collect by time and create the blocks layout.
    assert blocks  # Additional check to make the type checker happier.
    min_z = min(pos.z for pos in blocks.keys())
    max_z = max(pos.z for pos in blocks.keys())
    layout_slices: list[BlockLayout] = [
        BlockLayout({pos.as_2d(): block for pos, block in blocks.items() if pos.z == z})
        for z in range(min_z, max_z + 1)
    ]

    # 4. Get the abstract observables to be included in the compiled circuit.
    obs_included: list[AbstractObservable] = []
    if observables is not None:
        if observables == "auto":
            observables = block_graph.find_correlation_surfaces()
        elif shift_z != 0:  # need to shift the provided correlation surfaces as well
            observables = [
                _shift_z_of_correlation_surface(observable, shift_z)
                for observable in observables
            ]
        obs_included = [
            compile_correlation_surface_to_abstract_observable(block_graph, surface)
            for surface in observables
        ]

    return CompiledGraph(layout_slices, obs_included)


def _shift_z_of_correlation_surface(
    correlation_surface: CorrelationSurface, shift_z: int
) -> CorrelationSurface:
    """Shift the z coordinate of the nodes in the correlation surface by the specified amount."""

    def _shift_node(node: ZXNode) -> ZXNode:
        return ZXNode(node.position.shift_by(dz=shift_z), node.kind, node.label)

    def _shift_edge(edge: ZXEdge) -> ZXEdge:
        return ZXEdge(_shift_node(edge.u), _shift_node(edge.v), edge.has_hadamard)

    return CorrelationSurface(
        nodes=frozenset(_shift_node(node) for node in correlation_surface.nodes),
        span=frozenset(_shift_edge(edge) for edge in correlation_surface.span),
        external_stabilizer=correlation_surface.external_stabilizer,
    )
