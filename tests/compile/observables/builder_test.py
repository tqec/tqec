from tqec.circuit.measurement_map import MeasurementRecordsMap
from tqec.circuit.qubit import GridQubit
from tqec.compile.observables.builder import (
    ObservableBuilder,
    get_observable_with_measurement_records,
)
from tqec.templates.layout import LayoutTemplate
from tqec.templates.qubit import QubitTemplate
from tqec.utils.position import (
    BlockPosition2D,
    Position3D,
)


def test_transform_coords_into_grid() -> None:
    template = LayoutTemplate(
        {
            BlockPosition2D(0, 0): QubitTemplate(),
            BlockPosition2D(1, 0): QubitTemplate(),
            BlockPosition2D(1, 1): QubitTemplate(),
        }
    )
    qubits = ObservableBuilder.transform_coords_into_grid(
        5,
        template,
        local_coords=[(2, 2)],
        block_position=Position3D(1, 1, 0),
    )
    assert qubits == {GridQubit(27, 27)}

    qubits = ObservableBuilder.transform_coords_into_grid(
        12,
        template,
        local_coords=[(3, 1)],
        block_position=Position3D(0, 1, 0),
    )
    x = -1 + 3 * 2
    y = (12 * 2 + 2) * 2 - 1 + 1 * 2
    assert qubits == {GridQubit(x, y)}


def test_get_observable_with_measurement_records_sorts_qubits() -> None:
    q0 = GridQubit(0, 0)
    q1 = GridQubit(1, 0)
    unmeasured_qubit = GridQubit(2, 0)
    measurement_records = MeasurementRecordsMap({q1: [-1], q0: [-2]})

    observable = get_observable_with_measurement_records(
        {q1, unmeasured_qubit, q0},
        measurement_records,
        observable_index=0,
    )

    assert observable.measured_qubits == [q0, q1]
    assert observable.measurement_offsets == [-2, -1]
