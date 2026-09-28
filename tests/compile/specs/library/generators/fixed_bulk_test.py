import pytest
import stim

from tqec.compile.specs.enums import PipeCubeArmConfig
from tqec.compile.specs.library.generators.fixed_bulk import (
    FixedBulkConventionGenerator,
    make_fixed_bulk_realignment_plaquette,
)
from tqec.plaquette.compilation.base import IdentityPlaquetteCompiler
from tqec.plaquette.qubit import SquarePlaquetteQubits
from tqec.plaquette.rpng.rpng import PauliBasis
from tqec.plaquette.rpng.translators.default import DefaultRPNGTranslator
from tqec.templates.qubit import QubitHorizontalBorders
from tqec.utils.enums import Basis, Orientation


@pytest.fixture(scope="session", name="generator")
def fixture_generator() -> FixedBulkConventionGenerator:
    translator = DefaultRPNGTranslator()
    compiler = IdentityPlaquetteCompiler
    return FixedBulkConventionGenerator(translator, compiler)


def test_fixed_bulk_realignment_plaquette() -> None:
    plaquette = make_fixed_bulk_realignment_plaquette(
        stabilizer_basis=Basis.X,
        z_orientation=Orientation.VERTICAL,
        mq_reset=Basis.X,
        mq_measurement=Basis.Z,
        debug_basis=PauliBasis.X,
    )
    assert plaquette.qubits == SquarePlaquetteQubits()
    assert len(plaquette.circuit.schedule) == 6
    assert plaquette.circuit.get_circuit(include_qubit_coords=False) == stim.Circuit("""
RX 4
TICK
CX 4 0
TICK
TICK
CX 4 2
TICK
CX 1 4
TICK
CX 0 4
TICK
MZ 4
H 0 1 2 3
""")
    assert plaquette.debug_information.get_polygons() == PauliBasis.X

    plaquette = make_fixed_bulk_realignment_plaquette(
        stabilizer_basis=Basis.Z,
        z_orientation=Orientation.HORIZONTAL,
        mq_reset=Basis.Z,
        mq_measurement=Basis.X,
        debug_basis=PauliBasis.Z,
    )
    assert plaquette.qubits == SquarePlaquetteQubits()
    assert len(plaquette.circuit.schedule) == 6
    assert plaquette.circuit.get_circuit(include_qubit_coords=False) == stim.Circuit("""
RZ 4
TICK
CX 0 4
TICK
TICK
CX 2 4
TICK
CX 4 1
TICK
CX 4 0
TICK
MX 4
H 0 1 2 3
""")
    assert plaquette.debug_information.get_polygons() == PauliBasis.Z


def test_spatial_horizontal_hadamard_uses_extended_stabilisers(generator) -> None:
    """Reuse the extended-stabiliser spatial Hadamard for the Y-direction pipe.

    The Y-direction (horizontal) regular-pipe spatial Hadamard reuses the
    extended-stabiliser implementation from #774.
    """
    plqts = generator.get_spatial_extended_stabiliser_hadamard_plqts(
        Basis.X,
        PipeCubeArmConfig.NLNL,  # regular pipe (no arms) with sbb=X
        reset=Basis.Z,
        measurement=None,
    )
    assert len(plqts.collection) == 6
    # The template is the horizontal borders one (Y-axis pipe).
    assert isinstance(
        generator.get_spatial_extended_stabiliser_hadamard_raw_template(),
        QubitHorizontalBorders,
    )


def test_spatial_horizontal_hadamard_reuses_nrnr_for_z_sbb(generator) -> None:
    """For sbb=Z the arm configuration is NRNR."""
    plqts = generator.get_spatial_extended_stabiliser_hadamard_plqts(
        Basis.Z,
        PipeCubeArmConfig.NRNR,
        reset=Basis.Z,
        measurement=None,
    )
    assert len(plqts.collection) == 6
