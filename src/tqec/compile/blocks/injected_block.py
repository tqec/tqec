"""Representation of temporally injected blocks like ``YHalfCube``.

Some blocks like ``YHalfCube`` are connected to the computation in time direction
and do not have timestep schedules that are consistent with the rest of the
blocks if represented as a sequence of layers. This module provides a direct
circuit representation of such blocks that can be injected into the computation
during compilation.
"""

from collections.abc import Callable
from enum import Enum

import gen

from tqec.utils.scale import LinearFunction, PhysicalQubitScalable2D


class Alignment(Enum):
    HEAD = "head"
    TAIL = "tail"


class InjectedBlock:
    def __init__(
        self,
        chunks_factory: Callable[[int], list[gen.Chunk | gen.ChunkLoop]],
        scalable_timesteps: LinearFunction,
        scalable_shape: PhysicalQubitScalable2D,
        alignment: Alignment,
    ) -> None:
        """Represent a block that is injected in time during the computation."""
        self._chunks_factory = chunks_factory
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
    def chunks_factory(self) -> Callable[[int], list[gen.Chunk | gen.ChunkLoop]]:
        """Get the callable used to generate a scalable quantum circuit from the scaling factor."""
        return self._chunks_factory

    @property
    def alignment(self) -> Alignment:
        """Get the alignment of the injected block."""
        return self._alignment
