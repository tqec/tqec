from typing import Protocol

from tqec.compile.blocks.block import Block
from tqec.compile.blocks.layers.atomic.base import BaseLayer
from tqec.compile.blocks.layers.atomic.plaquettes import PlaquetteLayer
from tqec.compile.blocks.layers.composed.base import BaseComposedLayer
from tqec.compile.blocks.layers.composed.repeated import RepeatedLayer
from tqec.compile.blocks.layers.composed.sequenced import SequencedLayers
from tqec.plaquette.plaquette import Plaquettes
from tqec.templates.base import RectangularTemplate
from tqec.utils.enums import Basis
from tqec.utils.scale import LinearFunction


class _PlaquettesGenerator(Protocol):
    def __call__(
        self, reversed: bool, reset: Basis | None, measurement: Basis | None, /
    ) -> Plaquettes: ...


def _get_block(
    z_basis: Basis | None,
    has_spatial_junction_in_timeslice: bool,
    template: RectangularTemplate,
    plaquettes_generator: _PlaquettesGenerator,
    repetitions: LinearFunction,
) -> Block:
    """Get the block implemented with the provided ``template`` and ``plaquettes_generator``.

    This helper handles generating a :class:`.Block` instance, especially when a spatial junction
    needs alternating plaquettes, including in REPEAT blocks.

    Raises:
        NotImplementedError: if ``repetitions.slope`` is odd and a spatial junction is present.

    """
    # Naming convention: {f,b}{init,memory,meas}
    # f: forward
    # b: backward
    # init: initialisation plaquette (with data-qubit resets)
    # memory: memory plaquette (no data-qubit reset/measurement)
    # meas: measurement plaquette (with data-qubit measurements)
    finit = plaquettes_generator(False, z_basis, None)
    fmemory = plaquettes_generator(False, None, None)
    fmeas = plaquettes_generator(False, None, z_basis)
    bmemory = plaquettes_generator(True, None, None)
    bmeas = plaquettes_generator(True, None, z_basis)

    if not has_spatial_junction_in_timeslice:
        return Block(
            [
                PlaquetteLayer(template, finit),
                RepeatedLayer(PlaquetteLayer(template, fmemory), repetitions),
                PlaquetteLayer(template, fmeas),
            ]
        )
    # else
    # Here, we need to implement the block by alternating forward/backward
    # schedules. To do so, we need to repeat the REPEAT block body only half the
    # initial number of repetitions. Basically, we need to compute
    # `repetitions // 2` and `repetitions % 2`. The problem is that a simple
    # `LinearFunction` instance is not enough to encode the result of these
    # operations. See for example `LinearFunction(3, 0) // 2` that should give
    # `1` for `k=1`, `3` for `k=2` and `4` for `k=3`. These three points are
    # not forming a straight line, so a `LinearFunction` instance cannot
    # represent them. Circumventing this issue could be done by adding more
    # classes (e.g., ModFunction), but it seems simpler for the moment to just
    # raise on unsupported inputs.
    if repetitions.slope % 2 == 1:
        raise NotImplementedError(
            "Cannot have an odd slope for the number of repetitions when a "
            "spatial junction is present."
        )
    halved_repetitions = LinearFunction(repetitions.slope // 2, repetitions.offset // 2)
    remainder = repetitions.offset % 2
    loop_replacement: list[BaseLayer | BaseComposedLayer] = [
        RepeatedLayer(
            SequencedLayers([PlaquetteLayer(template, bmemory), PlaquetteLayer(template, fmemory)]),
            halved_repetitions,
        )
    ]
    if remainder == 1:  # Note that remainder can only be 0 or 1.
        loop_replacement.append(PlaquetteLayer(template, bmemory))

    return Block(
        [
            PlaquetteLayer(template, finit),
            SequencedLayers(loop_replacement),
            PlaquetteLayer(template, fmeas if remainder == 1 else bmeas),
        ]
    )
