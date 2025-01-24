from __future__ import annotations

from abc import ABC, abstractmethod

from tqec.position import Shape2D
from tqec.scale import Scalable2D


class WithSpatialFootprint(ABC):
    @property
    @abstractmethod
    def scalable_shape(self) -> Scalable2D:
        pass

    def shape(self, k: int) -> Shape2D:
        return self.scalable_shape.to_shape_2d(k)
