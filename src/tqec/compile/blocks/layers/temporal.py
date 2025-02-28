from __future__ import annotations

from abc import ABC, abstractmethod

from tqec.utils.scale import LinearFunction


class WithTemporalFootprint(ABC):
    """Base class providing the interface that should be implemented by objects
    that have a temporal footprint."""

    @property
    @abstractmethod
    def scalable_timesteps(self) -> LinearFunction:
        """Returns the number of timesteps needed to implement the object as an
        exact expression that can then be used to compute the number of
        timesteps for any value of ``k``.

        Returns:
            the number of timesteps needed to implement the object as an
            exact expression that can then be used to compute the number of
            timesteps for any value of ``k``.
        """
        pass

    def timesteps(self, k: int) -> int:
        """Returns the number of timesteps needed to implement the object for
        the provided scaling parameter ``k``.

        Args:
            k: scaling parameter.

        Returns:
            the number of timesteps needed to implement the object for
            the provided scaling parameter ``k``.
        """
        return self.scalable_timesteps.integer_eval(k)
