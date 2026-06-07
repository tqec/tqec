import numpy
import pytest
import stim

from tqec.compile.generation import generate_circuit_from_instantiation
from tqec.compile.specs.library.generators.constants import EXTENDED_PLAQUETTE_SCHEDULES
from tqec.compile.specs.library.generators.extended_stabilizers import (
    ExtendedPlaquette,
    ExtendedPlaquetteCollection,
    get_extended_plaquette,
)
from tqec.plaquette.plaquette import Plaquettes
from tqec.plaquette.rpng.rpng import RPNGDescription
from tqec.utils.enums import Basis
from tqec.utils.exceptions import TQECError
from tqec.utils.frozendefaultdict import FrozenDefaultDict
from tqec.utils.position import Shift2D
from tqec.visualisation.computation.plaquette.extended import (
    ExtendedPlaquetteDrawer,
    ExtendedPlaquettePosition,
    ExtendedPlaquetteType,
)


@pytest.mark.parametrize(
    "basis,is_reversed",
    [(Basis.X, False), (Basis.Z, False), (Basis.X, True), (Basis.Z, True)],
)
def test_extended_plaquette(basis: Basis, is_reversed: bool) -> None:
    up, down = get_extended_plaquette(
        RPNGDescription.from_basis_and_schedule(basis, EXTENDED_PLAQUETTE_SCHEDULES[is_reversed]),
        is_reversed=is_reversed,
    )
    scheduled_circuit = generate_circuit_from_instantiation(
        numpy.array([[1], [2]]),
        Plaquettes(FrozenDefaultDict({1: up, 2: down})),
        increments=Shift2D(2, 2),
    )
    circuit = scheduled_circuit.get_circuit()
    b = basis.value.upper() if basis is not None else "_"
    lf, rf = ("", "_") if is_reversed else ("_", "")
    assert circuit.has_flow(stim.Flow(f"1 -> {b}{lf}{b}__{b}{rf}{b} xor rec[0]"))
    assert circuit.has_flow(stim.Flow(f"{b}{lf}{b}__{b}{rf}{b} -> rec[0]"))


@pytest.mark.parametrize(
    "description",
    [
        RPNGDescription.empty(),
        RPNGDescription.from_string("-x2- ---- ---- -x5-"),
    ],
)
def test_extended_plaquette_collection_rejects_undefined_corners(
    description: RPNGDescription,
) -> None:
    with pytest.raises(TQECError, match="must define all four data-qubit interactions"):
        ExtendedPlaquetteCollection.from_description(
            description,
            reset=None,
            measurement=None,
            is_reversed=False,
        )


@pytest.mark.parametrize("reset,measurement", [(None, None), (Basis.X, None), (None, Basis.Z)])
@pytest.mark.parametrize(
    "collection_name,expected_type",
    [
        ("bulk", ExtendedPlaquetteType.BULK),
        ("bottom_right_triangle", ExtendedPlaquetteType.BOTTOM_RIGHT_TRIANGLE),
        ("right_half_rectangle", ExtendedPlaquetteType.RIGHT_HALF_RECTANGLE),
        ("top_left_triangle", ExtendedPlaquetteType.TOP_LEFT_TRIANGLE),
        ("left_half_rectangle", ExtendedPlaquetteType.LEFT_HALF_RECTANGLE),
        ("bottom_left_triangle", ExtendedPlaquetteType.BOTTOM_LEFT_TRIANGLE),
        ("top_right_triangle", ExtendedPlaquetteType.TOP_RIGHT_TRIANGLE),
    ],
)
def test_extended_plaquettes_have_svg_drawers(
    collection_name: str,
    expected_type: ExtendedPlaquetteType,
    reset: Basis | None,
    measurement: Basis | None,
) -> None:
    collection = ExtendedPlaquetteCollection.from_basis(
        Basis.X,
        reset=reset,
        measurement=measurement,
        is_reversed=False,
    )
    plaquette = getattr(collection, collection_name)
    assert isinstance(plaquette, ExtendedPlaquette)

    for position, part in [
        (ExtendedPlaquettePosition.UP, plaquette.top),
        (ExtendedPlaquettePosition.DOWN, plaquette.bottom),
    ]:
        drawer = part.debug_information.drawer
        assert isinstance(drawer, ExtendedPlaquetteDrawer)
        assert drawer._plaquette_type is expected_type
        assert drawer._position is position
        assert drawer.draw("extended-plaquette")
