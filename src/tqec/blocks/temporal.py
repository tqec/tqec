from __future__ import annotations

from abc import ABC, abstractmethod

from tqec.scale import LinearFunction


class WithTemporalFootprint(ABC):
    @property
    @abstractmethod
    def scalable_timesteps(self) -> LinearFunction:
        pass

    def timesteps(self, k: int) -> int:
        return self.scalable_timesteps.integer_eval(k)
