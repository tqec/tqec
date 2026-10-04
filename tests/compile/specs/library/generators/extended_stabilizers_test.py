import numpy
import pytest
import stim
import svg

from tqec.compile.generation import generate_circuit_from_instantiation
from tqec.compile.specs.library.generators.constants import EXTENDED_PLAQUETTE_SCHEDULES
from tqec.compile.specs.library.generators.extended_stabilizers import (
    ExtendedPlaquette,
    ExtendedPlaquetteCollection,
    ExtendedPlaquetteDataOperations,
    _with_extended_plaquette_drawer,
    get_extended_plaquette,
)
from tqec.plaquette.debug import DrawPolygon, PlaquetteDebugInformation
from tqec.plaquette.plaquette import Plaquettes
from tqec.plaquette.rpng.rpng import PauliBasis, RPNGDescription
from tqec.utils.enums import Basis
from tqec.utils.exceptions import TQECError
from tqec.utils.frozendefaultdict import FrozenDefaultDict
from tqec.utils.position import Shift2D
from tqec.visualisation.computation.plaquette.extended import (
    ExtendedPlaquetteDrawer,
    ExtendedPlaquettePosition,
    ExtendedPlaquetteType,
)


def _path_points(path: svg.Path) -> set[tuple[float, float]]:
    points: set[tuple[float, float]] = set()
    for element in path.d or []:
        x = getattr(element, "x", None)
        y = getattr(element, "y", None)
        if x is not None and y is not None:
            points.add((round(float(x), 10), round(float(y), 10)))
    return points


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


def test_extended_plaquette_drawer_preserves_existing_debug_information() -> None:
    description = RPNGDescription.from_basis_and_schedule(
        Basis.X, EXTENDED_PLAQUETTE_SCHEDULES[False]
    )
    up, _ = get_extended_plaquette(description, is_reversed=False)
    debug_information = PlaquetteDebugInformation(
        rpng=description,
        draw_polygons=DrawPolygon(PauliBasis.X),
    )
    plaquette = up.with_debug_information(debug_information)

    decorated_plaquette = _with_extended_plaquette_drawer(
        plaquette,
        ExtendedPlaquetteType.BULK,
        ExtendedPlaquettePosition.UP,
        PauliBasis.X,
        (2, 3, 4, 5),
        data_operations=ExtendedPlaquetteDataOperations(),
    )

    assert decorated_plaquette.debug_information.rpng == description
    assert decorated_plaquette.debug_information.draw_polygons == debug_information.draw_polygons
    assert isinstance(decorated_plaquette.debug_information.drawer, ExtendedPlaquetteDrawer)


@pytest.mark.parametrize(
    "plaquette_type,expected_points",
    [
        (
            ExtendedPlaquetteType.BOTTOM_RIGHT_TRIANGLE,
            {(0.8, 0.0), (1.0, 0.0), (1.0, 2.0), (0.0, 2.0), (0.0, 1.8)},
        ),
        (
            ExtendedPlaquetteType.BOTTOM_LEFT_TRIANGLE,
            {(0.0, 0.0), (0.2, 0.0), (1.0, 1.8), (1.0, 2.0), (0.0, 2.0)},
        ),
        (
            ExtendedPlaquetteType.TOP_LEFT_TRIANGLE,
            {(0.0, 0.0), (1.0, 0.0), (1.0, 0.2), (0.2, 2.0), (0.0, 2.0)},
        ),
        (
            ExtendedPlaquetteType.TOP_RIGHT_TRIANGLE,
            {(0.0, 0.2), (0.0, 0.0), (1.0, 0.0), (1.0, 2.0), (0.8, 2.0)},
        ),
    ],
)
def test_weight_three_extended_plaquette_shapes_match_corner_orientation(
    plaquette_type: ExtendedPlaquetteType,
    expected_points: set[tuple[float, float]],
) -> None:
    shape = ExtendedPlaquetteDrawer._get_weight_three_extended_plaquette_shape(
        ExtendedPlaquettePosition.UP, plaquette_type
    )

    assert isinstance(shape, svg.Path)
    assert _path_points(shape) == expected_points


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


@pytest.mark.parametrize("is_reversed", [False, True])
@pytest.mark.parametrize("basis", list(Basis))
@pytest.mark.parametrize("part_name", ["up", "down"])
@pytest.mark.parametrize("operation", ["reset", "measurement"])
def test_extended_plaquette_data_operations(
    is_reversed: bool, basis: Basis, part_name: str, operation: str
) -> None:
    operations = ExtendedPlaquetteDataOperations(
        up_reset=basis if part_name == "up" and operation == "reset" else None,
        up_measurement=basis if part_name == "up" and operation == "measurement" else None,
        down_reset=basis if part_name == "down" and operation == "reset" else None,
        down_measurement=basis if part_name == "down" and operation == "measurement" else None,
    )
    up, down = get_extended_plaquette(
        RPNGDescription.from_basis_and_schedule(Basis.X, EXTENDED_PLAQUETTE_SCHEDULES[is_reversed]),
        reset=Basis.X,
        measurement=Basis.X,
        is_reversed=is_reversed,
        data_operations=operations,
    )
    gate = ("R" if operation == "reset" else "M") + basis.value
    # Stim canonicalizes Z-basis gates as R/M.
    gate = stim.Circuit(f"{gate} 0")[0].name
    for position, part in [("up", up), ("down", down)]:
        circuit = part.circuit.get_circuit()
        data_targets = set(part.qubits.data_qubits_indices)
        actual_targets = {
            target.value
            for instruction in circuit
            if isinstance(instruction, stim.CircuitInstruction) and instruction.name == gate
            for target in instruction.targets_copy()
            if target.value in data_targets
        }
        assert actual_targets == (data_targets if position == part_name else set())
        moments = str(circuit).split("TICK")
        expected_moment = moments[0] if operation == "reset" else moments[-1]
        if position == part_name:
            assert any(
                isinstance(instruction, stim.CircuitInstruction)
                and instruction.name == gate
                and data_targets <= {target.value for target in instruction.targets_copy()}
                for instruction in stim.Circuit(expected_moment)
            )


@pytest.mark.parametrize(
    "collection_name",
    [
        "bulk",
        "bottom_right_triangle",
        "right_half_rectangle",
        "top_left_triangle",
        "left_half_rectangle",
        "bottom_left_triangle",
        "top_right_triangle",
    ],
)
@pytest.mark.parametrize("part_name", [None, "up", "down"])
@pytest.mark.parametrize("operation", ["reset", "measurement"])
def test_extended_plaquette_drawer_uses_actual_data_operations(
    collection_name: str, part_name: str | None, operation: str
) -> None:
    operations = ExtendedPlaquetteDataOperations(
        up_reset=Basis.X if part_name == "up" and operation == "reset" else None,
        up_measurement=Basis.X if part_name == "up" and operation == "measurement" else None,
        down_reset=Basis.X if part_name == "down" and operation == "reset" else None,
        down_measurement=Basis.X if part_name == "down" and operation == "measurement" else None,
    )
    collection = ExtendedPlaquetteCollection.from_basis(
        Basis.X,
        reset=Basis.X,
        measurement=Basis.X,
        is_reversed=False,
        data_operations=operations,
    )
    plaquette = getattr(collection, collection_name)
    for position, part in [("up", plaquette.top), ("down", plaquette.bottom)]:
        drawer = part.debug_information.drawer
        assert isinstance(drawer, ExtendedPlaquetteDrawer)
        assert drawer._reset == getattr(operations, f"{position}_reset")
        assert drawer._measurement == getattr(operations, f"{position}_measurement")
        assert bool(drawer.get_data_qubit_reset_measurements_layers().elements) == (
            position == part_name
        )
