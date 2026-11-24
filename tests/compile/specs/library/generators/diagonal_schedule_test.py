import pytest
import stim

from tqec.circuit.qubit import GridQubit
from tqec.circuit.schedule import relabel_circuits_qubit_indices
from tqec.circuit.schedule.manipulation import merge_scheduled_circuits
from tqec.compile.specs.library.generators.diagonal_spatial_hadamard import (
    SpatialHadamardFlagMode,
    make_diagonal_spatial_hadamard_extended_plaquettes,
    make_diagonal_spatial_hadamard_plaquette_pair,
)
from tqec.compile.specs.library.generators.fixed_bulk import FixedBulkConventionGenerator
from tqec.compile.specs.library.generators.schedules import DIAGONAL_SCHEDULE_FAMILY
from tqec.plaquette.compilation.base import IdentityPlaquetteCompiler
from tqec.plaquette.enums import PlaquetteOrientation
from tqec.plaquette.plaquette import Plaquette
from tqec.plaquette.rpng import RPNGDescription
from tqec.plaquette.rpng.translators.default import DefaultRPNGTranslator
from tqec.utils.enums import Basis, Orientation


def _make_generator() -> FixedBulkConventionGenerator:
    return FixedBulkConventionGenerator(
        DefaultRPNGTranslator(DIAGONAL_SCHEDULE_FAMILY.measurement_schedule),
        IdentityPlaquetteCompiler,
        DIAGONAL_SCHEDULE_FAMILY,
    )


def test_fixed_bulk_generator_uses_diagonal_bulk_orders() -> None:
    generator = _make_generator()
    assert generator.get_bulk_rpng_descriptions() == {
        Basis.X: {
            Orientation.VERTICAL: RPNGDescription.from_string("-x7- -x5- -x4- -x6-"),
            Orientation.HORIZONTAL: RPNGDescription.from_string("-x7- -x5- -x4- -x6-"),
        },
        Basis.Z: {
            Orientation.VERTICAL: RPNGDescription.from_string("-z1- -z3- -z4- -z2-"),
            Orientation.HORIZONTAL: RPNGDescription.from_string("-z1- -z3- -z4- -z2-"),
        },
    }


def test_fixed_bulk_generator_derives_diagonal_boundary_descriptions() -> None:
    generator = _make_generator()

    assert generator.get_2_body_rpng_descriptions() == {
        Basis.X: {
            PlaquetteOrientation.DOWN: RPNGDescription.from_string("-x7- -x5- ---- ----"),
            PlaquetteOrientation.LEFT: RPNGDescription.from_string("---- -x5- ---- -x6-"),
            PlaquetteOrientation.UP: RPNGDescription.from_string("---- ---- -x4- -x6-"),
            PlaquetteOrientation.RIGHT: RPNGDescription.from_string("-x7- ---- -x4- ----"),
        },
        Basis.Z: {
            PlaquetteOrientation.DOWN: RPNGDescription.from_string("-z1- -z3- ---- ----"),
            PlaquetteOrientation.LEFT: RPNGDescription.from_string("---- -z3- ---- -z2-"),
            PlaquetteOrientation.UP: RPNGDescription.from_string("---- ---- -z4- -z2-"),
            PlaquetteOrientation.RIGHT: RPNGDescription.from_string("-z1- ---- -z4- ----"),
        },
    }


def test_diagonal_stretched_stabilizer_gate_schedule() -> None:
    top, bottom = make_diagonal_spatial_hadamard_plaquette_pair(Basis.Z)
    assert top.circuit.get_circuit(include_qubit_coords=False) == stim.Circuit("""
        RX 2
        TICK
        CX 2 3
        TICK
        CZ 2 1
        TICK
        CZ 2 0
        TICK
        TICK
        TICK
        CX 3 2
        TICK
        TICK
        M 2
    """)
    assert bottom.circuit.get_circuit(include_qubit_coords=False) == stim.Circuit("""
        R 2
        TICK
        TICK
        CX 3 2
        TICK
        CX 2 0
        TICK
        CX 2 1
        TICK
        TICK
        TICK
        CX 2 3
        TICK
        MX 2
    """)


@pytest.mark.parametrize("mode", tuple(SpatialHadamardFlagMode))
@pytest.mark.parametrize("initial,final", [(True, False), (False, False), (False, True)])
def test_flag_measurement_lifecycle(
    mode: SpatialHadamardFlagMode, initial: bool, final: bool
) -> None:
    top, bottom = make_diagonal_spatial_hadamard_plaquette_pair(
        Basis.Z, Basis.Z if initial else None, Basis.Z if final else None, mode
    )
    auxiliary, shared = tuple(top.qubits.syndrome_qubits_indices)
    reset = top.circuit.moment_at_schedule(0).circuit
    readout = (
        top.circuit.moment_at_schedule(8).circuit if 8 in top.circuit.schedule else stim.Circuit()
    )
    reset_targets = {
        t.value
        for i in reset
        if isinstance(i, stim.CircuitInstruction) and i.name == "R"
        for t in i.targets_copy()
    }
    measurement_targets = {
        t.value
        for i in readout
        if isinstance(i, stim.CircuitInstruction) and i.name == "M"
        for t in i.targets_copy()
    }
    assert (shared in reset_targets) == (initial or mode != SpatialHadamardFlagMode.PARTIAL)
    assert (shared in measurement_targets) == (
        mode == SpatialHadamardFlagMode.ALL or (mode == SpatialHadamardFlagMode.PARTIAL and final)
    )
    assert (auxiliary in measurement_targets) == (mode != SpatialHadamardFlagMode.NONE)
    assert any(i.name == "MX" for i in bottom.circuit.moment_at_schedule(8).circuit)


def test_flag_metadata_survives_projection_compilation_and_serialization() -> None:
    top, _ = make_diagonal_spatial_hadamard_plaquette_pair(Basis.Z)
    projected = top.project_on_data_qubit_indices([1])
    compiled = IdentityPlaquetteCompiler.compile(projected)
    recovered = Plaquette.from_dict(compiled.to_dict())
    assert recovered.has_flagged_stabilizer
    assert recovered.circuit.get_circuit() == projected.circuit.get_circuit()


@pytest.mark.parametrize("orientation", tuple(Orientation))
def test_extended_plaquette_preview_follows_interface_orientation(orientation: Orientation) -> None:
    collection = make_diagonal_spatial_hadamard_extended_plaquettes(orientation=orientation)
    drawing = str(collection[Basis.Z].bulk.top.debug_information.get_svg_drawer().draw("interface"))
    assert ("matrix(0 1 1 0 0 0)" in drawing) == (orientation == Orientation.HORIZONTAL)
    assert "text" in drawing


@pytest.mark.parametrize("fault_half", [0, 1])
def test_partial_flags_detect_both_auxiliary_hook_faults(fault_half: int) -> None:
    rounds = []
    flag_offsets = []
    for initial in (True, False):
        top, bottom = make_diagonal_spatial_hadamard_plaquette_pair(
            Basis.Z, Basis.Z if initial else None
        )
        halves, qubit_map = relabel_circuits_qubit_indices(
            [
                top.circuit,
                bottom.circuit.map_to_qubits(lambda q: GridQubit(q.x, q.y + 2)),
            ]
        )
        round_circuit = merge_scheduled_circuits(
            halves, qubit_map, top.mergeable_instructions
        ).get_circuit()
        auxiliary = qubit_map.q2i[GridQubit(0, 2 * fault_half)]
        faulty_round = stim.Circuit()
        timestep = 0
        for instruction in round_circuit:
            faulty_round.append(instruction)
            if instruction.name == "TICK":
                timestep += 1
                if initial and timestep == (2 if fault_half == 0 else 3):
                    faulty_round.append("X_ERROR", [auxiliary], [1])
        rounds.append(faulty_round)
        flag_offsets.append(sum(c.num_measurements for c in rounds) - 2)
    circuit = rounds[0] + stim.Circuit("TICK") + rounds[1]
    for offset in flag_offsets:
        circuit.append("DETECTOR", [stim.target_rec(offset - circuit.num_measurements)])
    noiseless = stim.Circuit()
    for instruction in circuit:
        if instruction.name != "X_ERROR":
            noiseless.append(instruction)
    noiseless_detectors, _ = noiseless.compile_detector_sampler().sample(
        16, separate_observables=True
    )
    faulty_detectors, _ = circuit.compile_detector_sampler().sample(16, separate_observables=True)
    assert not noiseless_detectors.any()
    assert faulty_detectors.any(axis=1).all()
