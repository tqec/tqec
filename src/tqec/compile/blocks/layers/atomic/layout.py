from __future__ import annotations

from collections.abc import Iterable
from functools import cached_property
from typing import Final, TypeGuard

from typing_extensions import override

from tqec.circuit.schedule.circuit import ScheduledCircuit
from tqec.compile.blocks.enums import SpatialBlockBorder
from tqec.compile.blocks.layers.atomic.base import BaseLayer
from tqec.compile.blocks.layers.atomic.plaquettes import PlaquetteLayer
from tqec.compile.blocks.positioning import (
    LayoutCubePosition2D,
    LayoutPipePosition2D,
    LayoutPosition2D,
)
from tqec.compile.generation import generate_circuit
from tqec.plaquette.plaquette import Plaquettes
from tqec.templates.enums import TemplateBorder
from tqec.templates.layout import LayoutTemplate
from tqec.utils.exceptions import TQECError
from tqec.utils.position import BlockPosition2D, Direction3D, Shift2D
from tqec.utils.scale import LinearFunction, PhysicalQubitScalable2D

DEFAULT_SHARED_QUBIT_DEPTH_AT_BORDER: Final[int] = 1
"""Default number of qubits that are shared between two neighbouring layers."""


def contains_only_plaquette_layers(
    layers: dict[LayoutPosition2D, BaseLayer],
) -> TypeGuard[dict[LayoutPosition2D, PlaquetteLayer]]:
    """Ensure correct typing when used in a conditional block."""
    return all(isinstance(layer, PlaquetteLayer) for layer in layers.values())


class LayoutLayer(BaseLayer):
    def __init__(
        self,
        layers: dict[LayoutPosition2D, BaseLayer],
        element_shape: PhysicalQubitScalable2D,
    ) -> None:
        """Glue several other layers together on a 2-dimensional grid.

        Args:
            layers: a mapping from positions on the 2-dimensional space to
                blocks implementing the circuit that should be present at that
                position.
                The mapping is expected to represent a connected computation.
            element_shape: scalable shape (in qubit coordinates) of each entry
                in the provided ``layers``.

        Raises:
            TQECError: if ``layers`` is empty.
            TQECError: if ``trimmed_spatial_borders`` is not empty.

        """
        super().__init__(frozenset())
        self._layers = layers
        self._element_shape = element_shape
        self._post_init_check()

    def _post_init_check(self) -> None:
        if not self.layers:
            raise TQECError(f"An instance of {type(self).__name__} should have at least one layer.")
        if self.trimmed_spatial_borders:
            raise TQECError(f"{LayoutLayer.__name__} cannot have trimmed spatial borders.")

    @property
    def layers(self) -> dict[LayoutPosition2D, BaseLayer]:
        """Return the layers composing ``self``."""
        return self._layers

    @property
    def element_shape(self) -> PhysicalQubitScalable2D:
        """Return the scalable shape of each stored elements."""
        return self._element_shape

    @cached_property
    def bounds(self) -> tuple[BlockPosition2D, BlockPosition2D]:
        """Get the top-left and bottom-right corners of the bounding box of ``self``.

        Returns:
            a tuple containing the corners of ``self``'s bounding box as positions
            containing the two minimum (top-left corner) or maximum (bottom-right
            corner) coordinates found in ``self``.

        """
        xs = [pos._x for pos in self.layers.keys()]
        ys = [pos._y for pos in self.layers.keys()]
        minx, maxx = min(xs), max(xs)
        miny, maxy = min(ys), max(ys)
        # We know for sure that the minima and maxima above are located on cube
        # positions and so are multiples of 2.
        return (
            BlockPosition2D(minx // 2, miny // 2),
            BlockPosition2D(maxx // 2, maxy // 2),
        )

    @property
    @override
    def scalable_shape(self) -> PhysicalQubitScalable2D:
        minp, maxp = self.bounds
        shapex, shapey = (maxp.x - minp.x) + 1, (maxp.y - minp.y) + 1
        return PhysicalQubitScalable2D(
            shapex * (self.element_shape.x - DEFAULT_SHARED_QUBIT_DEPTH_AT_BORDER)
            + DEFAULT_SHARED_QUBIT_DEPTH_AT_BORDER,
            shapey * (self.element_shape.y - DEFAULT_SHARED_QUBIT_DEPTH_AT_BORDER)
            + DEFAULT_SHARED_QUBIT_DEPTH_AT_BORDER,
        )

    @override
    def with_spatial_borders_trimmed(self, borders: Iterable[SpatialBlockBorder]) -> LayoutLayer:
        raise TQECError(f"Cannot trim spatial borders of a {type(self).__name__} instance.")

    def __eq__(self, value: object) -> bool:
        return (
            isinstance(value, LayoutLayer)
            and self.element_shape == value.element_shape
            and self.layers == value.layers
        )

    def __hash__(self) -> int:
        raise NotImplementedError(f"Cannot hash efficiently a {type(self).__name__}.")

    def to_template_and_plaquettes(self) -> tuple[LayoutTemplate, Plaquettes]:
        """Return an equivalent representation of ``self`` with a template and some plaquettes.

        Raises:
            NotImplementedError: if not all layers composing ``self`` are instances
                of :class:`~tqec.compile.blocks.layers.atomic.plaquette.PlaquetteLayer`.

        Returns:
            a tuple ``(template, plaquettes)`` that is ready to be used with
            :meth:`~tqec.compile.generation.generate_circuit` to obtain the quantum
            circuit representing ``self``.

        """
        if not contains_only_plaquette_layers(self.layers):
            raise NotImplementedError(
                f"Found a layer that is not an instance of {PlaquetteLayer.__name__}. "
                "Detector computation is not implemented (yet) for this case."
            )
        cubes: dict[BlockPosition2D, PlaquetteLayer] = {
            pos.to_block_position(): layer
            for pos, layer in self.layers.items()
            if isinstance(pos, LayoutCubePosition2D) and isinstance(layer, PlaquetteLayer)
        }
        template_dict: Final = {pos: layer.template for pos, layer in cubes.items()}
        plaquettes_dict = {pos: layer.plaquettes for pos, layer in cubes.items()}

        # Add plaquettes from each pipe to the plaquette_dict.
        pipes: dict[tuple[BlockPosition2D, BlockPosition2D], PlaquetteLayer] = {
            pos.to_pipe(): layer
            for pos, layer in self.layers.items()
            if isinstance(pos, LayoutPipePosition2D) and isinstance(layer, PlaquetteLayer)
        }
        for (u, v), pipe_layer in pipes.items():
            pipe_direction = Direction3D.from_neighbouring_positions(u.to_3d(), v.to_3d())
            # {u,v}_border: border of the respective node that is touched by the
            # the pipe.
            u_border: TemplateBorder
            v_border: TemplateBorder
            match pipe_direction:
                case Direction3D.X:
                    u_border, v_border = TemplateBorder.RIGHT, TemplateBorder.LEFT
                case Direction3D.Y:
                    u_border, v_border = TemplateBorder.BOTTOM, TemplateBorder.TOP
                case Direction3D.Z:
                    raise TQECError("Should not happen. This is a logical error.")

            # Updating plaquettes in plaquettes_dict
            for pos, (cube_border, pipe_border) in [
                (u, (u_border, v_border)),
                (v, (v_border, u_border)),
            ]:
                plaquette_indices_mapping = pipe_layer.template.get_border_indices(pipe_border).to(
                    template_dict[pos].get_border_indices(cube_border)
                )
                pipe_plaquette_collection = pipe_layer.plaquettes.collection
                plaquettes_dict[pos] = plaquettes_dict[pos].with_updated_plaquettes(
                    {
                        plaquette_indices_mapping[pipe_plaquette_index]: plaquette
                        for pipe_plaquette_index, plaquette in pipe_plaquette_collection.items()
                        # Filtering only plaquette indices that are on the side we are
                        # interested in.
                        if pipe_plaquette_index in plaquette_indices_mapping
                    }
                )

        template = LayoutTemplate(template_dict)
        return template, template.get_global_plaquettes(plaquettes_dict)

    def to_circuit(self, k: int) -> ScheduledCircuit:
        """Return the quantum circuit representing the layer.

        Args:
            k: scaling factor.

        Returns:
            quantum circuit representing the layer.

        """
        template, plaquettes = self.to_template_and_plaquettes()
        scheduled_circuit = generate_circuit(template, k, plaquettes)
        # Shift the qubits of the returned scheduled circuit
        mincube, _ = self.bounds
        eshape = self.element_shape.to_shape_2d(k)
        # See: https://github.com/tqec/tqec/issues/525
        # This is a temporary fix to the above issue, we may need a utility function
        # to calculate shift to avoid similar issues in the future.
        shift = Shift2D(mincube.x * (eshape.x - 1), mincube.y * (eshape.y - 1))
        shifted_circuit = scheduled_circuit.map_to_qubits(lambda q: q + shift)
        return shifted_circuit

    @property
    @override
    def scalable_num_moments(self) -> LinearFunction:
        return LinearFunction.unambiguous_max_on_positives(
            layer.scalable_num_moments for layer in self.layers.values()
        )

    @property
    def qubit_bounds(self) -> tuple[PhysicalQubitScalable2D, PhysicalQubitScalable2D]:
        """Return the top-left and bottom-right qubits representing the bounding box of ``self``.

        Returns:
            the ``(top_left, bottom_right)`` qubits.

        """
        tlb, brb = self.bounds
        eshape = self.element_shape
        increments = PhysicalQubitScalable2D(eshape.x, eshape.y) - (1, 1)
        tlq = PhysicalQubitScalable2D(tlb.x * increments.x, tlb.y * increments.y)
        brq = PhysicalQubitScalable2D((brb.x + 1) * increments.x, (brb.y + 1) * increments.y)
        # Note: for the moment, plaquette origin is defined as the CENTER of the
        # plaquette, which lead the above computations to be off-by-1. Correct that
        # before returning.
        shift = (-1, -1)
        return tlq + shift, brq + shift
