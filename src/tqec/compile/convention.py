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
from tqec.compile.specs.library.fixed_bulk import (
    FIXED_BULK_CUBE_BUILDER,
    FIXED_BULK_PIPE_BUILDER,
)

if TYPE_CHECKING:
    from tqec.compile.observables.builder import ObservableBuilder
    from tqec.compile.specs.base import CubeBuilder, PipeBuilder


@dataclass(frozen=True)
class ConventionTriplet:
    """Stores the 3 builders needed to implement a new convention.

    In order to implement a new way of generating plaquettes and implementing
    blocks, a new :class:`Convention` should be created. This involves
    implementing the interfaces for each of the 3 attributes below.

    """

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


FIXED_BULK_CONVENTION = Convention(
    "fixed_bulk",
    ConventionTriplet(
        FIXED_BULK_CUBE_BUILDER, FIXED_BULK_PIPE_BUILDER, FIXED_BULK_OBSERVABLE_BUILDER
    ),
)

FIXED_BOUNDARY_CONVENTION = Convention(
    "fixed_boundary",
    ConventionTriplet(
        FIXED_BOUNDARY_CUBE_BUILDER,
        FIXED_BOUNDARY_PIPE_BUILDER,
        FIXED_BOUNDARY_OBSERVABLE_BUILDER,
    ),
)

ALL_CONVENTIONS = {conv.name: conv for conv in [FIXED_BULK_CONVENTION, FIXED_BOUNDARY_CONVENTION]}
