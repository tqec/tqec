from dataclasses import dataclass

from tqec.compile.observables.builder import ObservableBuilder
from tqec.compile.observables.fixed_bulk_builder import FIXED_BULK_OBSERVABLE_BUILDER
from tqec.compile.observables.fixed_parity_builder import (
    FIXED_PARITY_OBSERVABLE_BUILDER,
)
from tqec.compile.specs.base import CubeBuilder, PipeBuilder
from tqec.compile.specs.library.fixed_bulk import (
    FIXED_BULK_CUBE_BUILDER,
    FIXED_BULK_PIPE_BUILDER,
)


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
    """Represents a convention to implement blocks."""

    name: str
    triplet: ConventionTriplet


FIXED_BULK_CONVENTION = Convention(
    "fixed_bulk",
    ConventionTriplet(
        FIXED_BULK_CUBE_BUILDER, FIXED_BULK_PIPE_BUILDER, FIXED_BULK_OBSERVABLE_BUILDER
    ),
)

FIXED_PARITY_CONVENTION = Convention(
    "fixed_parity",
    ConventionTriplet(
        FIXED_BULK_CUBE_BUILDER,
        FIXED_BULK_PIPE_BUILDER,
        FIXED_PARITY_OBSERVABLE_BUILDER,
    ),
)

ALL_CONVENTIONS = {conv.name: conv for conv in [FIXED_BULK_CONVENTION]}
