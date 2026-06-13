"""Provides a factory to instantiate builders based on convention and schedule."""

from abc import ABC, abstractmethod
from collections.abc import Callable
from typing import ClassVar

from tqec.compile.convention import Convention
from tqec.compile.observables.builder import ObservableBuilder
from tqec.compile.observables.fixed_boundary_builder import (
    FIXED_BOUNDARY_OBSERVABLE_BUILDER,
)
from tqec.compile.observables.fixed_bulk_builder import FIXED_BULK_OBSERVABLE_BUILDER
from tqec.compile.specs.base import CubeBuilder, PipeBuilder
from tqec.compile.specs.library.fixed_boundary import (
    FIXED_BOUNDARY_CUBE_BUILDER,
    FIXED_BOUNDARY_PIPE_BUILDER,
)
from tqec.compile.specs.library.fixed_bulk import (
    FIXED_BULK_CUBE_BUILDER,
    FIXED_BULK_PIPE_BUILDER,
    FixedBulkCubeBuilder,
    FixedBulkPipeBuilder,
)
from tqec.compile.specs.library.generators.diagonal_schedule import (
    create_diagonal_schedule_compiler,
)
from tqec.compile.specs.library.generators.schedules import PlaquetteScheduleFamily
from tqec.plaquette.rpng.translators.default import DefaultRPNGTranslator
from tqec.utils.exceptions import TQECError

_BuilderTuple = tuple[CubeBuilder, PipeBuilder, ObservableBuilder]


class BuilderProvider(ABC):
    """Abstract base class for providing builders."""

    @abstractmethod
    def get_builders(self, schedule_family: PlaquetteScheduleFamily) -> _BuilderTuple:
        """Return the builders for the specified schedule family."""
        pass


class BuilderFactory:
    """Factory object to manage and instantiate builders for conventions and schedules."""

    _registry: ClassVar[dict[tuple[str, str], type[BuilderProvider]]] = {}

    @classmethod
    def register(
        cls, convention_name: str, schedule_name: str
    ) -> Callable[[type[BuilderProvider]], type[BuilderProvider]]:
        """Register a builder provider class."""

        def decorator(provider_cls: type[BuilderProvider]) -> type[BuilderProvider]:
            cls._registry[(convention_name, schedule_name)] = provider_cls
            return provider_cls

        return decorator

    @classmethod
    def get_builders(
        cls,
        convention: Convention,
        schedule_family: PlaquetteScheduleFamily,
    ) -> _BuilderTuple:
        """Get the appropriate builders for the given convention and schedule family.

        Args:
            convention: The convention to use.
            schedule_family: The schedule family to use.

        Returns:
            A tuple of (CubeBuilder, PipeBuilder, ObservableBuilder).

        Raises:
            TQECError: If the schedule_family is not supported by the given convention.

        """
        key = (convention.name, schedule_family.name)
        if key not in cls._registry:
            raise TQECError(
                f"Unsupported schedule family '{schedule_family.name}' "
                f"for convention '{convention.name}'."
            )
        provider = cls._registry[key]()
        return provider.get_builders(schedule_family)


@BuilderFactory.register("fixed_bulk", "default")
class FixedBulkDefaultBuilderProvider(BuilderProvider):
    """Provides the builders for the fixed_bulk convention with default schedule."""

    def get_builders(self, schedule_family: PlaquetteScheduleFamily) -> _BuilderTuple:
        """Return the builders for the fixed_bulk convention with default schedule."""
        return (
            FIXED_BULK_CUBE_BUILDER,
            FIXED_BULK_PIPE_BUILDER,
            FIXED_BULK_OBSERVABLE_BUILDER,
        )


@BuilderFactory.register("fixed_bulk", "diagonal")
class FixedBulkDiagonalBuilderProvider(BuilderProvider):
    """Provides the builders for the fixed_bulk convention with diagonal schedule."""

    def get_builders(self, schedule_family: PlaquetteScheduleFamily) -> _BuilderTuple:
        """Return the builders for the fixed_bulk convention with diagonal schedule."""
        cube_builder = FixedBulkCubeBuilder(
            create_diagonal_schedule_compiler(),
            DefaultRPNGTranslator(schedule_family=schedule_family),
            schedule_family=schedule_family,
        )
        pipe_builder = FixedBulkPipeBuilder(
            create_diagonal_schedule_compiler(),
            DefaultRPNGTranslator(schedule_family=schedule_family),
            schedule_family=schedule_family,
        )
        return cube_builder, pipe_builder, FIXED_BULK_OBSERVABLE_BUILDER


@BuilderFactory.register("fixed_boundary", "default")
class FixedBoundaryDefaultBuilderProvider(BuilderProvider):
    """Provides the builders for the fixed_boundary convention with default schedule."""

    def get_builders(self, schedule_family: PlaquetteScheduleFamily) -> _BuilderTuple:
        """Return the builders for the fixed_boundary convention with default schedule."""
        return (
            FIXED_BOUNDARY_CUBE_BUILDER,
            FIXED_BOUNDARY_PIPE_BUILDER,
            FIXED_BOUNDARY_OBSERVABLE_BUILDER,
        )
