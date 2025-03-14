from __future__ import annotations

from typing import Literal

from tqec.plaquette.enums import PlaquetteOrientation
from tqec.plaquette.rpng.rpng import RPNGDescription
from tqec.utils.enums import Basis, Orientation


def get_bulk_plaquettes(
    reset: Basis | None = None,
    measurement: Basis | None = None,
    reset_and_measured_indices: tuple[Literal[0, 1, 2, 3], ...] = (0, 1, 2, 3),
) -> dict[Basis, dict[Orientation, RPNGDescription]]:
    """Get plaquettes that are supposed to be used in the bulk.

    This function returns the four 4-body stabilizer measurement plaquettes
    containing 5 rounds that can be arbitrarily tiled without any gate schedule
    clash. These plaquettes are organised by basis and hook orientation.

    Args:
        reset: basis of the reset operation performed on data-qubits. Defaults
            to ``None`` that translates to no reset being applied on data-qubits.
        measurement: basis of the measurement operation performed on data-qubits.
            Defaults to ``None`` that translates to no measurement being applied
            on data-qubits.
        reset_and_measured_indices: data-qubit indices that should be impacted
            by the provided ``reset`` and ``measurement`` values.

    Returns:
        a mapping with 4 plaquettes: one for each basis (either ``X`` or ``Z``)
        and for each hook orientation (either ``HORIZONTAL`` or ``VERTICAL``).
    """
    # _r/_m: reset/measurement basis applied to each data-qubit in
    # reset_and_measured_indices
    _r = reset.value.lower() if reset is not None else "-"
    _m = measurement.value.lower() if measurement is not None else "-"
    # rs/ms: resets/measurements basis applied for each data-qubit
    rs = [_r if i in reset_and_measured_indices else "-" for i in range(4)]
    ms = [_m if i in reset_and_measured_indices else "-" for i in range(4)]
    # 2-qubit gate schedules
    vsched, hsched = (1, 4, 3, 5), (1, 2, 3, 5)
    return {
        Basis.X: {
            Orientation.VERTICAL: RPNGDescription.from_string(
                " ".join(f"{r}x{s}{m}" for r, s, m in zip(rs, vsched, ms))
            ),
            Orientation.HORIZONTAL: RPNGDescription.from_string(
                " ".join(f"{r}x{s}{m}" for r, s, m in zip(rs, hsched, ms))
            ),
        },
        Basis.Z: {
            Orientation.VERTICAL: RPNGDescription.from_string(
                " ".join(f"{r}z{s}{m}" for r, s, m in zip(rs, vsched, ms))
            ),
            Orientation.HORIZONTAL: RPNGDescription.from_string(
                " ".join(f"{r}z{s}{m}" for r, s, m in zip(rs, hsched, ms))
            ),
        },
    }


def get_3_body_plaquettes(
    reset: Basis | None = None,
    measurement: Basis | None = None,
) -> tuple[RPNGDescription, RPNGDescription, RPNGDescription, RPNGDescription]:
    # r/m: reset/measurement basis applied to each data-qubit
    r = reset.value.lower() if reset is not None else "-"
    m = measurement.value.lower() if measurement is not None else "-"
    # Note: the schedule of CNOT gates in corner plaquettes is less important
    # because hook errors do not exist on 3-body stabilizers. We arbitrarily
    # chose the schedule of the plaquette group the corner belongs to.
    # Note that we include resets and measurements on all the used data-qubits.
    # That should be fine because this plaquette only touches cubes and pipes
    # that are related to the spatial junction being implemented, and it is not
    # valid to have a temporal pipe comming from below a spatial junction, hence
    # the data-qubits cannot be already initialised to a value we would like to
    # keep and that would be destroyed by reset/measurement.
    return (
        RPNGDescription.from_string(f"---- {r}z4{m} {r}z3{m} {r}z5{m}"),
        RPNGDescription.from_string(f"{r}x1{m} ---- {r}x3{m} {r}x5{m}"),
        RPNGDescription.from_string(f"{r}x1{m} {r}x2{r} ---- {r}x5{r}"),
        RPNGDescription.from_string(f"{r}z1{m} {r}z4{m} {r}z3{m} ----"),
    )


def get_2_body_plaquettes(
    reset: Basis | None = None,
    measurement: Basis | None = None,
) -> dict[Basis, dict[PlaquetteOrientation, RPNGDescription]]:
    """Get plaquettes that are supposed to be used on the boundaries.

    This function returns the eight 2-body stabilizer measurement plaquettes
    that can be used on the 5-round plaquettes returned by
    :meth:`get_bulk_plaquettes`.

    Note:
        The 2-body stabilizer measurement plaquettes returned by this function
        all follow the same schedule: ``1-2-3-5``.

    Warning:
        This function uses the :class:`~tqec.plaquette.enums.PlaquetteOrientation`
        class. For a 2-body stabilizer measurement plaquette, the "orientation"
        corresponds to the direction in which the rounded side is pointing.
        So a plaquette with the orientation ``PlaquetteOrientation.DOWN`` has the
        following properties:

        - it measures the 2 data-qubits on the **top** side of the usual 4-body
          stabilizer measurement plaquette,
        - it can be used for a bottom boundary,
        - its rounded side points downwards.

    Args:
        reset: basis of the reset operation performed on data-qubits. Defaults
            to ``None`` that translates to no reset being applied on data-qubits.
        measurement: basis of the measurement operation performed on data-qubits.
            Defaults to ``None`` that translates to no measurement being applied
            on data-qubits.

    Returns:
        a mapping with 8 plaquettes: one for each basis (either ``X`` or ``Z``)
        and for each plaquette orientation (``UP``, ``DOWN``, ``LEFT`` or
        ``RIGHT``).
    """
    # r/m: reset/measurement basis applied to each data-qubit
    r = reset.value.lower() if reset is not None else "-"
    m = measurement.value.lower() if measurement is not None else "-"
    PO = PlaquetteOrientation
    return {
        Basis.X: {
            PO.DOWN: RPNGDescription.from_string(f"{r}x1{m} {r}x2{m} ---- ----"),
            PO.LEFT: RPNGDescription.from_string(f"---- {r}x2{m} ---- {r}x5{m}"),
            PO.UP: RPNGDescription.from_string(f"---- ---- {r}x3{m} {r}x5{m}"),
            PO.RIGHT: RPNGDescription.from_string(f"{r}x1{m} ---- {r}x3{m} ----"),
        },
        Basis.Z: {
            PO.DOWN: RPNGDescription.from_string(f"{r}z1{m} {r}z2{m} ---- ----"),
            PO.LEFT: RPNGDescription.from_string(f"---- {r}x2{m} ---- {r}x5{m}"),
            PO.UP: RPNGDescription.from_string(f"---- ---- {r}x3{m} {r}x5{m}"),
            PO.RIGHT: RPNGDescription.from_string(f"{r}x1{m} ---- {r}x3{m} ----"),
        },
    }
