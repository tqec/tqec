from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass, field
from typing import Final, Protocol

import gen
import stim
from typing_extensions import override

from tqec.compile.blocks.enums import Alignment, SpatialBlockBorder, TemporalBlockBorder
from tqec.compile.blocks.layers.atomic.base import BaseLayer
from tqec.compile.blocks.layers.atomic.layout import LayoutLayer
from tqec.compile.blocks.layers.composed.base import BaseComposedLayer
from tqec.compile.blocks.layers.composed.sequenced import SequencedLayers
from tqec.compile.blocks.layers.merge import (
    contains_only_base_layers,
    contains_only_composed_layers,
    merge_base_layers,
    merge_composed_layers,
)
from tqec.compile.blocks.positioning import LayoutPosition2D
from tqec.utils.exceptions import TQECError
from tqec.utils.scale import LinearFunction, PhysicalQubitScalable2D


class Block(ABC):
    """Base class for all block instantiations in the compilation framework.

    A block represents a unit of quantum computation with a defined spatial
    and temporal footprint that scales with the scaling factor ``k``.
    """

    @property
    @abstractmethod
    def scalable_timesteps(self) -> LinearFunction:
        """Get the scalable timesteps (temporal extent) of the block."""
        pass

    @property
    @abstractmethod
    def scalable_shape(self) -> PhysicalQubitScalable2D:
        """Get the scalable shape (spatial extent) of the block."""
        pass

    @property
    @abstractmethod
    def is_cube(self) -> bool:
        """Return ``True`` if ``self`` represents a cube, else ``False``."""
        pass

    @property
    @abstractmethod
    def is_pipe(self) -> bool:
        """Return ``True`` if ``self`` represents a pipe, else ``False``."""
        pass


class LayeredBlock(SequencedLayers, Block):
    """Encodes the implementation of a block with a sequence of layers.

    This data structure is voluntarily very generic. It represents blocks as a
    sequence of layers that can be instances of either
    :class:`~tqec.compile.blocks.layers.atomic.base.BaseLayer` or
    :class:`~tqec.compile.blocks.layers.composed.base.BaseComposedLayer`.

    Depending on the stored layers, this class can be used to represent regular
    cubes (i.e. scaling in the 3 dimensions with ``k``) as well as pipes (i.e.
    scaling in only 2 dimension with ``k``).

    """

    @override
    def with_spatial_borders_trimmed(self, borders: Iterable[SpatialBlockBorder]) -> LayeredBlock:
        return LayeredBlock(
            self._layers_with_spatial_borders_trimmed(borders),
            self.trimmed_spatial_borders | frozenset(borders),
        )

    @override
    def with_temporal_borders_replaced(
        self,
        border_replacements: Mapping[TemporalBlockBorder, BaseLayer | None],
    ) -> LayeredBlock | None:
        if not border_replacements:
            return self
        layers = self._layers_with_temporal_borders_replaced(border_replacements)
        return LayeredBlock(layers) if layers else None

    def get_atomic_temporal_border(self, border: TemporalBlockBorder) -> BaseLayer:
        """Get the layer at the provided temporal ``border``.

        This method is different to :meth:`get_temporal_layer_on_border` in that it raises when the
        border is not an atomic layer.

        Raises:
            TQECError: if the layer at the provided temporal ``border`` is not atomic (i.e., an
                instance of :class:`.BaseLayer`).

        """
        layer_index: int
        match border:
            case TemporalBlockBorder.Z_NEGATIVE:
                layer_index = 0
            case TemporalBlockBorder.Z_POSITIVE:
                layer_index = -1
        layer = self.layer_sequence[layer_index]
        if not isinstance(layer, BaseLayer):
            raise TQECError(
                "Expected to recover a temporal **border** (i.e. an atomic "
                f"layer) but got an instance of {type(layer).__name__} instead."
            )
        return layer

    @property
    def dimensions(self) -> tuple[LinearFunction, LinearFunction, LinearFunction]:
        """Return the dimensions of ``self``.

        Returns:
            a 3-dimensional tuple containing the width for each of the
            ``(x, y, z)`` dimensions.

        """
        spatial_shape = self.scalable_shape
        return spatial_shape.x, spatial_shape.y, self.scalable_timesteps

    @property
    def is_cube(self) -> bool:
        """Return ``True`` if ``self`` represents a cube, else ``False``.

        A cube is defined as a block with all its 3 dimensions that are scalable.

        """
        return all(dim.is_scalable() for dim in self.dimensions)

    @property
    def is_pipe(self) -> bool:
        """Return ``True`` if ``self`` represents a pipe, else ``False``.

        A pipe is defined as a block with all but one of its 3 dimensions that are scalable.

        """
        return sum(dim.is_scalable() for dim in self.dimensions) == 2

    @property
    def is_temporal_pipe(self) -> bool:
        """Return ``True`` if ``self`` is a temporal pipe, else ``False``.

        A temporal pipe is a pipe (exactly 2 scalable dimensions) for which the non-scalable
        dimension is the third one (time dimension).

        """
        return self.is_pipe and self.dimensions[2].is_constant()

    def __eq__(self, value: object) -> bool:
        return isinstance(value, LayeredBlock) and super().__eq__(value)

    def __hash__(self) -> int:
        raise NotImplementedError(f"Cannot hash efficiently a {type(self).__name__}.")


def merge_parallel_block_layers(
    blocks_in_parallel: Mapping[LayoutPosition2D, LayeredBlock],
    scalable_qubit_shape: PhysicalQubitScalable2D,
) -> list[LayoutLayer | BaseComposedLayer]:
    """Merge several stacks of layers executed in parallel into one stack of larger layers.

    Args:
        blocks_in_parallel: a 2-dimensional arrangement of blocks. Each of the
            provided block MUST have the exact same duration (also called
            "temporal footprint", or number of atomic layers).
        scalable_qubit_shape: scalable shape of a scalable qubit. Considered
            valid across the whole domain.

    Returns:
        a stack of layers representing the same slice of computation as the
        provided ``blocks_in_parallel``.

    Raises:
        TQECError: if two items from the provided ``blocks_in_parallel`` do
            not have the same temporal footprint.
        NotImplementedError: if the provided blocks cannot be merged due to a
            code branch not being implemented yet (and not due to a logical
            error making the blocks unmergeable).

    """
    if not blocks_in_parallel:
        return []
    internal_layers_schedules = frozenset(
        tuple(layer.scalable_timesteps for layer in block.layer_sequence)
        for block in blocks_in_parallel.values()
    )
    if len(internal_layers_schedules) != 1:
        raise NotImplementedError(
            "merge_parallel_block_layers only supports merging blocks that have "
            "layers with a matching temporal schedule. Found the following "
            "different temporal schedules in the provided blocks: "
            f"{internal_layers_schedules}."
        )
    schedule: Final = next(iter(internal_layers_schedules))
    merged_layers: list[LayoutLayer | BaseComposedLayer] = []
    for i in range(len(schedule)):
        layers = {pos: block.layer_sequence[i] for pos, block in blocks_in_parallel.items()}
        if contains_only_base_layers(layers):
            merged_layers.append(merge_base_layers(layers, scalable_qubit_shape))
        elif contains_only_composed_layers(layers):
            merged_layers.append(merge_composed_layers(layers, scalable_qubit_shape))
        else:
            raise RuntimeError(
                f"Found a mix of {BaseLayer.__name__} instances and "
                f"{BaseComposedLayer.__name__} instances in a single temporal "
                f"layer. This should be already checked before. This is a "
                "logical error in the code, please open an issue. Found layers:"
                f"\n{list(layers.values())}"
            )
    return merged_layers


@dataclass(frozen=True)
class CircuitWithInterface:
    """A quantum circuit with its expected flow interface.

    Attributes:
        circuit: the quantum circuit.
        interface: the expected flow interface of the circuit.

    """

    circuit: stim.Circuit
    interface: gen.ChunkInterface = field(default_factory=lambda: gen.ChunkInterface(()))

    def __post_init__(self) -> None:
        if not self.circuit:
            raise TQECError("The provided circuit is empty.")

    def with_transformed_coords(
        self, transform: Callable[[complex], complex]
    ) -> CircuitWithInterface:
        """Return a copy of ``self`` with transformed coordinates.

        Args:
            transform: the coordinate transformation to apply to the detector and observable flows.

        Returns:
            a copy of ``self`` with transformed coordinates.

        """
        return CircuitWithInterface(
            gen.stim_circuit_with_transformed_coords(self.circuit, transform),
            self.interface.with_transformed_coords(transform),
        )


class InjectionFactory(Protocol):
    def __call__(
        self,
        k: int,
        annotate_observables: list[int] | None,
    ) -> CircuitWithInterface:
        """Generate the quantum circuit with expected flow interface from the scaling factor.

        Args:
            k: The scaling factor.
            annotate_observables: If provided, the list of observables will be annotated
                in the generated circuit. Note that the injection block will typically
                only support a single unique observable flow. Therefore, if multiple
                observables are provided, they will be replicates of the same observable flow
                with different observable ids.

        Returns:
            A quantum circuit with expected flow interface.

        """
        ...


class InjectedBlock(Block):
    """Represent temporally injected block like ``YHalfCube``.

    Some blocks like ``YHalfCube`` are connected to the computation in time
    direction and do not have timestep schedules that are consistent with
    the rest of the blocks if represented as a sequence of layers. This class
    provides a direct circuit representation of such blocks that can be
    injected into the computation during compilation.
    """

    def __init__(
        self,
        injection_factory: InjectionFactory,
        scalable_timesteps: LinearFunction,
        scalable_shape: PhysicalQubitScalable2D,
        alignment: Alignment,
    ) -> None:
        """Initialize an instance of ``InjectedBlock``.

        Args:
            injection_factory: a callable that generates a quantum circuit
                with expected flow interface from the scaling factor.
            scalable_timesteps: the duration of the injected block as a
                function of the scaling factor ``k``.
            scalable_shape: the scalable shape of the injected block.
            alignment: the alignment of the injected block with the computation
                it is injected into. If ``Alignment.HEAD``, the first timestep
                of the injected block follows the last timestep of the block
                preceding it. If ``Alignment.TAIL``, the last timestep of the
                injected block precedes the first timestep of the block
                following it.

        Returns:
            An instance of ``InjectedBlock``.

        """
        self._injection_factory = injection_factory
        self._scalable_timesteps = scalable_timesteps
        self._scalable_shape = scalable_shape
        self._alignment = alignment

    @property
    @override
    def scalable_timesteps(self) -> LinearFunction:
        return self._scalable_timesteps

    @property
    @override
    def scalable_shape(self) -> PhysicalQubitScalable2D:
        return self._scalable_shape

    @property
    def injection_factory(self) -> InjectionFactory:
        """Get the callable used to generate a scalable quantum circuit from the scaling factor."""
        return self._injection_factory

    @property
    def alignment(self) -> Alignment:
        """Get the alignment of the injected block."""
        return self._alignment

    @property
    @override
    def is_cube(self) -> bool:
        return True

    @property
    @override
    def is_pipe(self) -> bool:
        return False
