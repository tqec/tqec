from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from tqec.plaquette.enums import PlaquetteOrientation
from tqec.plaquette.rpng import RPNGDescription
from tqec.utils.enums import Basis, Orientation

_BoundaryIndices = {
    PlaquetteOrientation.DOWN: (0, 1),
    PlaquetteOrientation.LEFT: (1, 3),
    PlaquetteOrientation.UP: (2, 3),
    PlaquetteOrientation.RIGHT: (0, 2),
}
_CornerOmissions = {
    "top_left": 0,
    "top_right": 1,
    "bottom_left": 2,
    "bottom_right": 3,
}


@dataclass(frozen=True)
class PlaquetteScheduleFamily:
    """Schedule data used to derive plaquette RPNG descriptions."""

    name: str
    measurement_schedule: int
    bulk_orders: dict[Basis, dict[Orientation, tuple[int, int, int, int]]]
    boundary_source_orders: dict[Basis, tuple[int, int, int, int]]
    corner_source_orders: dict[Basis, tuple[int, int, int, int]]

    def bulk_descriptions(
        self,
        reset: Basis | None = None,
        measurement: Basis | None = None,
        reset_and_measured_indices: tuple[Literal[0, 1, 2, 3], ...] = (0, 1, 2, 3),
    ) -> dict[Basis, dict[Orientation, RPNGDescription]]:
        """Return the 4-body plaquette descriptions for this schedule family."""
        reset_marker = reset.value.lower() if reset is not None else "-"
        meas_marker = measurement.value.lower() if measurement is not None else "-"
        resets = [reset_marker if i in reset_and_measured_indices else "-" for i in range(4)]
        measurements = [
            meas_marker if i in reset_and_measured_indices else "-" for i in range(4)
        ]
        return {
            basis: {
                orientation: RPNGDescription.from_string(
                    " ".join(
                        f"{r}{basis.value.lower()}{sched}{m}"
                        for r, sched, m in zip(resets, order, measurements)
                    )
                )
                for orientation, order in orientations.items()
            }
            for basis, orientations in self.bulk_orders.items()
        }

    def boundary_descriptions(
        self,
    ) -> dict[Basis, dict[PlaquetteOrientation, RPNGDescription]]:
        """Return the 2-body plaquette descriptions for this schedule family."""
        return {
            basis: {
                orientation: RPNGDescription.from_string(
                    " ".join(
                        _format_corner(
                            basis,
                            self.boundary_source_orders[basis][corner_index],
                            corner_index in active_indices,
                        )
                        for corner_index in range(4)
                    )
                )
                for orientation, active_indices in _BoundaryIndices.items()
            }
            for basis in Basis
        }

    def corner_descriptions(
        self,
        reset: Basis | None = None,
        measurement: Basis | None = None,
    ) -> tuple[RPNGDescription, RPNGDescription, RPNGDescription, RPNGDescription]:
        """Return the 3-body plaquette descriptions for this schedule family."""
        reset_marker = reset.value.lower() if reset is not None else "-"
        meas_marker = measurement.value.lower() if measurement is not None else "-"
        return tuple(
            RPNGDescription.from_string(
                " ".join(
                    (
                        "----"
                        if corner_index == omitted_corner
                        else f"{reset_marker}{basis.value.lower()}"
                        f"{self.corner_source_orders[basis][corner_index]}{meas_marker}"
                    )
                    for corner_index in range(4)
                )
            )
            for basis, omitted_corner in (
                (Basis.Z, _CornerOmissions["top_left"]),
                (Basis.X, _CornerOmissions["top_right"]),
                (Basis.X, _CornerOmissions["bottom_left"]),
                (Basis.Z, _CornerOmissions["bottom_right"]),
            )
        )


def _format_corner(basis: Basis, schedule: int, include: bool) -> str:
    if not include:
        return "----"
    return f"-{basis.value.lower()}{schedule}-"


DEFAULT_SCHEDULE_FAMILY = PlaquetteScheduleFamily(
    name="default",
    measurement_schedule=6,
    bulk_orders={
        Basis.X: {
            Orientation.VERTICAL: (1, 4, 3, 5),
            Orientation.HORIZONTAL: (1, 2, 3, 5),
        },
        Basis.Z: {
            Orientation.VERTICAL: (1, 4, 3, 5),
            Orientation.HORIZONTAL: (1, 2, 3, 5),
        },
    },
    boundary_source_orders={
        Basis.X: (1, 2, 3, 5),
        Basis.Z: (1, 2, 3, 5),
    },
    corner_source_orders={
        Basis.X: (1, 2, 3, 5),
        Basis.Z: (1, 4, 3, 5),
    },
)

DIAGONAL_SCHEDULE_FAMILY = PlaquetteScheduleFamily(
    name="diagonal",
    measurement_schedule=8,
    bulk_orders={
        Basis.X: {
            Orientation.VERTICAL: (7, 5, 4, 6),
            Orientation.HORIZONTAL: (7, 5, 4, 6),
        },
        Basis.Z: {
            Orientation.VERTICAL: (1, 3, 4, 2),
            Orientation.HORIZONTAL: (1, 3, 4, 2),
        },
    },
    boundary_source_orders={
        Basis.X: (7, 5, 4, 6),
        Basis.Z: (1, 3, 4, 2),
    },
    corner_source_orders={
        Basis.X: (7, 5, 4, 6),
        Basis.Z: (1, 3, 4, 2),
    },
)
