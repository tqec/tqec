from __future__ import annotations

from typing import Iterable, Mapping, TypeVar, cast

from typing_extensions import Self, override

from tqec.compile.blocks.enums import TemporalBlockBorder
from tqec.compile.blocks.spatial import WithSpatialFootprint
from tqec.compile.blocks.temporal import WithTemporalFootprint
from tqec.utils.exceptions import TQECException
from tqec.utils.scale import LinearFunction

T = TypeVar("T", bound="BaseLayer")


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

    def with_temporal_borders_trimmed(
        self, borders: Iterable[TemporalBlockBorder]
    ) -> Self | None:
        """Returns ``self`` with the provided temporal borders removed.

        Args:
            borders: temporal borders to remove.

        Returns:
            a copy of ``self`` with the provided ``borders`` removed, or ``None``
            if removing the provided ``borders`` from ``self`` result in an
            empty temporal footprint.
        """
        return cast(
            # The below type is known for sure because the replacement mapping
            # values are exclusively of type "None" (no need to consider
            # "BaseLayer").
            Self | None,
            self.with_temporal_borders_replaced({border: None for border in borders}),
        )

    def with_temporal_borders_replaced(
        self: BaseLayer,
        border_replacements: Mapping[TemporalBlockBorder, T | None],
    ) -> T | None:
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
            # Cast seems to be required. I do not understand the type error
            # returned by both mypy and pyright when removing the cast below.
            return cast(T, self)
        if len(border_replacements) > 1 and any(
            replacement is not None for replacement in border_replacements.values()
        ):
            raise TQECException(
                "Unclear semantic: trying to replace the two temporal borders of "
                "an atomic layer that, by definition, only contain one layer."
            )
        return next(iter(border_replacements.values()))
