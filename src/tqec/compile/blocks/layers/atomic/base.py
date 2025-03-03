from __future__ import annotations

from typing import Mapping

from typing_extensions import override

from tqec.compile.blocks.enums import TemporalBlockBorder
from tqec.compile.blocks.layers.spatial import WithSpatialFootprint
from tqec.compile.blocks.layers.temporal import WithTemporalFootprint
from tqec.utils.exceptions import TQECException
from tqec.utils.scale import LinearFunction


class BaseLayer(WithSpatialFootprint, WithTemporalFootprint):
    """Base class representing a "layer".

    A "layer" is defined as a quantum circuit implementing a single round of
    quantum error correction. It can span an arbitrarily large spatial area and
    implement a (time)slice of an arbitrarily complex quantum error corrected
    computation.
    """

    @property
    @override
    def scalable_timesteps(self) -> LinearFunction:
        # By definition of a "layer":
        return LinearFunction(0, 1)

    def with_temporal_borders_replaced(
        self, border_replacements: Mapping[TemporalBlockBorder, BaseLayer | None]
    ) -> BaseLayer | None:
        """Returns ``self`` with the provided temporal borders replaced.

        Args:
            borders: a mapping from temporal borders to replace to their
                replacement. A value of ``None`` as a replacement means that the
                border is removed.

        Returns:
            a copy of ``self`` with the provided ``borders`` replaced, or ``None``
            if replacing the provided ``borders`` from ``self`` result in an
            empty temporal footprint.
        """
        if not border_replacements:
            return self
        if len(border_replacements) > 1 and any(
            replacement is not None for replacement in border_replacements.values()
        ):
            raise TQECException(
                "Unclear semantic: trying to replace the two temporal borders of "
                "an atomic layer that, by definition, only contain one layer."
            )
        return next(iter(border_replacements.values()))
