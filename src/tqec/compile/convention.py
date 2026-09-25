from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from tqec.compile.observables.fixed_boundary_builder import (
    FIXED_BOUNDARY_OBSERVABLE_BUILDER,
)
from tqec.compile.observables.fixed_bulk_builder import FIXED_BULK_OBSERVABLE_BUILDER
from tqec.compile.specs.library.fixed_boundary import (
    FIXED_BOUNDARY_CUBE_BUILDER,
    FIXED_BOUNDARY_PIPE_BUILDER,
)
from tqec.compile.specs.library.fixed_bulk import FixedBulkCubeBuilder, FixedBulkPipeBuilder
from tqec.compile.specs.library.generators.schedules import (
    DEFAULT_SCHEDULE_FAMILY,
    DIAGONAL_SCHEDULE_FAMILY,
    PlaquetteScheduleFamily,
)

if TYPE_CHECKING:
    from tqec.compile.observables.builder import ObservableBuilder
    from tqec.compile.specs.base import CubeBuilder, PipeBuilder


@dataclass(frozen=True)
class ConventionTriplet:
    """Store the builders that implement a compilation convention."""

    cube_builder: CubeBuilder
    pipe_builder: PipeBuilder
    observable_builder: ObservableBuilder


@dataclass(frozen=True)
class Convention:
    """Represent a convention to implement blocks."""

    name: str
    triplet: ConventionTriplet

    def __str__(self) -> str:
        return self.name  # pragma: no cover


def fixed_bulk_convention(
    schedule_family: PlaquetteScheduleFamily = DEFAULT_SCHEDULE_FAMILY,
) -> Convention:
    """Create a fixed-bulk convention configured with a plaquette schedule."""
    name = (
        "fixed_bulk"
        if schedule_family == DEFAULT_SCHEDULE_FAMILY
        else f"fixed_bulk[{schedule_family.name}]"
    )
    return Convention(
        name,
        ConventionTriplet(
            FixedBulkCubeBuilder(schedule_family=schedule_family),
            FixedBulkPipeBuilder(schedule_family=schedule_family),
            FIXED_BULK_OBSERVABLE_BUILDER,
        ),
    )


FIXED_BULK_CONVENTION = fixed_bulk_convention()
DIAGONAL_FIXED_BULK_CONVENTION = fixed_bulk_convention(DIAGONAL_SCHEDULE_FAMILY)
FIXED_BOUNDARY_CONVENTION = Convention(
    "fixed_boundary",
    ConventionTriplet(
        FIXED_BOUNDARY_CUBE_BUILDER,
        FIXED_BOUNDARY_PIPE_BUILDER,
        FIXED_BOUNDARY_OBSERVABLE_BUILDER,
    ),
)

ALL_CONVENTIONS = {
    conv.name: conv
    for conv in [
        FIXED_BULK_CONVENTION,
        FIXED_BOUNDARY_CONVENTION,
    ]
}
