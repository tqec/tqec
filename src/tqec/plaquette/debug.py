from __future__ import annotations

from dataclasses import dataclass

from tqec.plaquette.enums import PlaquetteOrientation
from tqec.plaquette.rpng.rpng import RPNG, RPNGDescription


@dataclass(frozen=True)
class PlaquetteDebugInformation:
    rpng: RPNGDescription | None = None

    def project_on_boundary(
        self, projected_orientation: PlaquetteOrientation
    ) -> PlaquetteDebugInformation:
        if self.rpng is None:
            return self
        corners: list[RPNG] = list(self.rpng.corners)
        empty_rpng = RPNG.from_string("----")
        match projected_orientation:
            case PlaquetteOrientation.UP:
                corners[0] = corners[1] = empty_rpng
            case PlaquetteOrientation.DOWN:
                corners[2] = corners[3] = empty_rpng
            case PlaquetteOrientation.LEFT:
                corners[1] = corners[3] = empty_rpng
            case PlaquetteOrientation.RIGHT:
                corners[0] = corners[2] = empty_rpng
        return PlaquetteDebugInformation(
            RPNGDescription(
                (corners[0], corners[1], corners[2], corners[3]), self.rpng.ancilla
            )
        )
