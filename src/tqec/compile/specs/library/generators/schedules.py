from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType

from tqec.utils.enums import Basis, Orientation


@dataclass(frozen=True)
class PlaquetteSchedule:
    """Two-qubit gate schedules indexed by square-plaquette corner."""

    top_left: int
    top_right: int
    bottom_left: int
    bottom_right: int

    @property
    def values(self) -> tuple[int, int, int, int]:
        """Return schedules in RPNG corner order."""
        return self.top_left, self.top_right, self.bottom_left, self.bottom_right

    def reversed(self) -> PlaquetteSchedule:
        """Return a new schedule with reversed corner order."""
        return PlaquetteSchedule(
            self.bottom_right,
            self.bottom_left,
            self.top_right,
            self.top_left,
        )

    def __getitem__(self, index: int) -> int:
        return self.values[index]


@dataclass(frozen=True)
class PlaquetteScheduleFamily:
    """Two-qubit gate schedule policy for fixed-bulk plaquettes.

    Attributes:
        name: Human-readable name of the timing policy.
        measurement_schedule: Absolute timestep used for measurement operations.
            This must be later than every two-qubit gate timestep.
        gate_schedules: Two-qubit gate schedules indexed by stabilizer basis
            and hook orientation.

    """

    name: str
    measurement_schedule: int
    gate_schedules: Mapping[Basis, Mapping[Orientation, PlaquetteSchedule]]

    def __post_init__(self) -> None:
        """Validate that every plaquette has a complete, valid timing policy."""
        for basis in Basis:
            orientations = self.gate_schedules.get(basis)
            if orientations is None or set(orientations) != set(Orientation):
                raise ValueError(f"Missing gate schedules for {basis.value}-basis plaquettes.")
            for orientation, schedule in orientations.items():
                values = schedule.values
                if len(set(values)) != len(values):
                    raise ValueError(
                        f"Gate schedules must be unique for {basis.value}-basis "
                        f"{orientation.value} plaquettes."
                    )
                if any(value <= 0 or value >= self.measurement_schedule for value in values):
                    raise ValueError("Gate schedules must be positive and precede measurement.")
        immutable_schedules = {
            basis: MappingProxyType(dict(orientations))
            for basis, orientations in self.gate_schedules.items()
        }
        object.__setattr__(
            self,
            "gate_schedules",
            MappingProxyType(immutable_schedules),
        )


DEFAULT_SCHEDULE_FAMILY = PlaquetteScheduleFamily(
    name="default",
    measurement_schedule=6,
    gate_schedules={
        Basis.X: {
            Orientation.VERTICAL: PlaquetteSchedule(1, 4, 3, 5),
            Orientation.HORIZONTAL: PlaquetteSchedule(1, 2, 3, 5),
        },
        Basis.Z: {
            Orientation.VERTICAL: PlaquetteSchedule(1, 4, 3, 5),
            Orientation.HORIZONTAL: PlaquetteSchedule(1, 2, 3, 5),
        },
    },
)

#: Diagonal syndrome-extraction schedule from Gilad Kishony and Austin Fowler,
#: "Surface code off-the-hook: diagonal syndrome-extraction scheduling",
#: https://arxiv.org/abs/2602.09099.
DIAGONAL_SCHEDULE_FAMILY = PlaquetteScheduleFamily(
    name="diagonal",
    measurement_schedule=8,
    gate_schedules={
        Basis.X: {
            Orientation.VERTICAL: PlaquetteSchedule(7, 5, 4, 6),
            Orientation.HORIZONTAL: PlaquetteSchedule(7, 5, 4, 6),
        },
        Basis.Z: {
            Orientation.VERTICAL: PlaquetteSchedule(1, 3, 4, 2),
            Orientation.HORIZONTAL: PlaquetteSchedule(1, 3, 4, 2),
        },
    },
)
