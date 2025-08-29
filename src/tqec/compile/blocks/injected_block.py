"""Representation of temporally injected blocks like ``YHalfCube``.

Some blocks like ``YHalfCube`` are connected to the computation in time direction
and do not have timestep schedules that are consistent with the rest of the
blocks if represented as a sequence of layers. This module provides a direct
circuit representation of such blocks that can be injected into the computation
during compilation.
"""

from enum import Enum
from typing import Protocol

import gen
import stim
from pygltflib import dataclass

from tqec.utils.scale import LinearFunction, PhysicalQubitScalable2D


class Alignment(Enum):
    HEAD = "head"
    TAIL = "tail"


@dataclass(frozen=True)
class CircuitWithInterface:
    circuit: stim.Circuit
    interface: gen.ChunkInterface


class InjectionFactory(Protocol):
    def __call__(self, k: int, include_observable: bool) -> CircuitWithInterface:
        """Generate a scalable quantum circuit from the scaling factor.

        Args:
            k: The scaling factor.
            include_observable: whether to include the observable in the generated circuit.
                Currently, only a single possible observable in the injected block
                is supported.

        Returns:
            A quantum circuit with expected interface.

        """
        ...


class InjectedBlock:
    def __init__(
        self,
        injection_factory: InjectionFactory,
        scalable_timesteps: LinearFunction,
        scalable_shape: PhysicalQubitScalable2D,
        alignment: Alignment,
    ) -> None:
        """Represent a block that is injected in time during the computation."""
        self._injection_factory = injection_factory
        self._scalable_timesteps = scalable_timesteps
        self._scalable_shape = scalable_shape
        self._alignment = alignment

    @property
    def scalable_timesteps(self) -> LinearFunction:
        """Get the scalable timesteps of the injected block."""
        return self._scalable_timesteps

    @property
    def scalable_shape(self) -> PhysicalQubitScalable2D:
        """Get the scalable shape of the injected block."""
        return self._scalable_shape

    @property
    def injection_factory(self) -> InjectionFactory:
        """Get the callable used to generate a scalable quantum circuit from the scaling factor."""
        return self._injection_factory

    @property
    def alignment(self) -> Alignment:
        """Get the alignment of the injected block."""
        return self._alignment
