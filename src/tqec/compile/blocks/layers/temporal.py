from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Mapping
from typing import TYPE_CHECKING

from tqec.compile.blocks.enums import TemporalBlockBorder
from tqec.utils.scale import LinearFunction

if TYPE_CHECKING:
    # Avoid circular dependency just because of typing annotations.
    from tqec.compile.blocks.layers.atomic.base import BaseLayer
    from tqec.compile.blocks.layers.composed.base import BaseComposedLayer


class WithTemporalFootprint(ABC):
    """Base class providing the interface implemented by objects that have a temporal footprint."""

    @property
    @abstractmethod
    def scalable_timesteps(self) -> LinearFunction:
        """Return the number of timesteps needed to implement the object.

        Returns:
            the number of timesteps needed to implement the object as an
            exact expression that can then be used to compute the number of
            timesteps for any value of ``k``.

        """
        pass

    def timesteps(self, k: int) -> int:
        """Return the number of timesteps needed for the provided scaling parameter ``k``.

        Args:
            k: scaling parameter.

        Returns:
            the number of timesteps needed to implement the object for
            the provided scaling parameter ``k``.

        """
        return self.scalable_timesteps.integer_eval(k)  # pragma: no cover

    @abstractmethod
    def with_temporal_borders_replaced(
        self, border_replacements: Mapping[TemporalBlockBorder, BaseLayer | None]
    ) -> BaseLayer | BaseComposedLayer | None:
        """Return ``self`` with the provided temporal borders replaced.

        Args:
            border_replacements: a mapping from temporal borders to replace to their replacement. A
                value of ``None`` as a replacement means that the border is removed.

        Returns:
            a copy of ``self`` with the provided ``borders`` replaced, or ``None``
            if replacing the provided ``borders`` from ``self`` result in an
            empty temporal footprint.

        """
        pass

    @abstractmethod
    def get_temporal_layer_on_border(self, border: TemporalBlockBorder) -> BaseLayer:
        """Return the :class:`.BaseLayer` on the provided ``border``.

        This method can be used to get the temporal extremal layers of a temporal pipe to replace
        the linked cube temporal extremal layers.

        """
        pass

    @property
    @abstractmethod
    def scalable_num_moments(self) -> LinearFunction:
        """Return the number of moments needed to implement the object,.

        Returns:
            the number of moments needed to implement the object as an
            exact expression that can then be used to compute the number of
            moments for any value of ``k``.

        """
        pass

    def num_moments(self, k: int) -> int:
        """Return the number of moments needed for the provided scaling parameter ``k``.

        Args:
            k: scaling parameter.

        Returns:
            the number of moments needed to implement the object for
            the provided scaling parameter ``k``.

        """
        return self.scalable_num_moments.integer_eval(k)  # pragma: no cover
