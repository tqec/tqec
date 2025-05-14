from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from tqec.plaquette.enums import PlaquetteOrientation
from tqec.plaquette.rpng.rpng import RPNG, PauliBasis, RPNGDescription


@dataclass(frozen=True)
class PlaquetteDebugInformation:
    rpng: RPNGDescription | None = None
    basis: PauliBasis | None = None

    def get_basis(self) -> PauliBasis | None:
        if self.basis is not None:
            return self.basis
        if self.rpng is not None:
            bases = {rpng.p for rpng in self.rpng.corners if rpng.p is not None}
            if len(bases) == 1:
                return bases.pop()
        return None

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
            ),
            self.basis,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "rpng": self.rpng.to_dict() if self.rpng is not None else None,
            "basis": self.basis.to_dict() if self.basis is not None else None,
        }

    @staticmethod
    def from_dict(data: dict[str, Any]) -> PlaquetteDebugInformation:
        return PlaquetteDebugInformation(
            RPNGDescription.from_dict(data["rpng"])
            if data["rpng"] is not None
            else None,
            PauliBasis.from_dict(data["basis"]) if data["basis"] is not None else None,
        )
