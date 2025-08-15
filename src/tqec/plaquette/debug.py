from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from tqec.circuit.qubit import GridQubit
from tqec.plaquette.enums import PlaquetteOrientation
from tqec.plaquette.rpng.rpng import RPNG, PauliBasis, RPNGDescription
from tqec.visualisation.computation.plaquette.base import (
    EmptySVGPlaquetteDrawer,
    SVGPlaquetteDrawer,
)
from tqec.visualisation.computation.plaquette.rpng import RPNGPlaquetteDrawer


@dataclass
class DrawPolygon:
    qubits_by_basis: dict[PauliBasis, list[GridQubit]] | PauliBasis

    def to_json(self) -> dict[str, Any]:  # pragma: no cover
        """Serialize ``self`` as a JSON-like dictionary."""
        if isinstance(self.qubits_by_basis, PauliBasis):
            return {"basis": self.qubits_by_basis.value}
        return {
            str(basis): [qubit.to_dict() for qubit in qubits]
            for basis, qubits in self.qubits_by_basis.items()
        }

    @staticmethod
    def from_json(data: dict[str, Any]) -> DrawPolygon:  # pragma: no cover
        """Deserialize ``self`` from a JSON-like dictionary."""
        if "basis" in data:
            return DrawPolygon(PauliBasis(data["basis"]))
        return DrawPolygon(
            {
                PauliBasis(basis): [GridQubit.from_dict(q) for q in qubits]
                for basis, qubits in data.items()
            }
        )


@dataclass(frozen=True)
class PlaquetteDebugInformation:
    rpng: RPNGDescription | None = None
    draw_polygons: DrawPolygon | None = None
    drawer: SVGPlaquetteDrawer | None = None

    def get_polygons(self) -> dict[PauliBasis, list[GridQubit]] | PauliBasis | None:
        """Getter method to get the polygon information for Crumble outputs.

        A polygon is one of Crumble annotation that allows to plot coloured polygons when exploring
        a quantum circuit with Crumble. That is useful to annotate stabilizers and their basis.

        Returns:
            a mapping from measurement basis to the data-qubits that are measured in each basis. If
            the debug information does not exists, returns ``None``. If all the data-qubits are
            measured in the same basis, returns that basis as a simplification.

        """
        if self.draw_polygons is not None:
            return self.draw_polygons.qubits_by_basis
        if self.rpng is not None:
            bases = {rpng.p for rpng in self.rpng.corners if rpng.p is not None}
            if len(bases) == 1:
                return bases.pop()
        return None

    def with_data_qubits_removed(self, removed_data_qubits: list[int]) -> PlaquetteDebugInformation:
        """Return a copy of ``self`` without any information on ``removed_data_qubits``."""
        if self.rpng is None:
            return self
        corners: list[RPNG] = list(self.rpng.corners)
        empty_rpng = RPNG.from_string("----")
        return PlaquetteDebugInformation(
            RPNGDescription(
                (
                    corners[0] if 0 not in removed_data_qubits else empty_rpng,
                    corners[1] if 1 not in removed_data_qubits else empty_rpng,
                    corners[2] if 2 not in removed_data_qubits else empty_rpng,
                    corners[3] if 3 not in removed_data_qubits else empty_rpng,
                ),
                self.rpng.ancilla,
            )
        )

    def project_on_boundary(
        self, projected_orientation: PlaquetteOrientation
    ) -> PlaquetteDebugInformation:
        """Project the debug information on the provided ``projected_orientation``."""
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
            RPNGDescription((corners[0], corners[1], corners[2], corners[3]), self.rpng.ancilla),
            self.draw_polygons,
        )

    def to_dict(self) -> dict[str, Any]:
        """Return a dictionary representing ``self``."""
        return {
            "rpng": self.rpng.to_dict() if self.rpng is not None else None,
            "draw_polygons": (
                self.draw_polygons.to_json() if self.draw_polygons is not None else None
            ),
        }

    @staticmethod
    def from_dict(data: dict[str, Any]) -> PlaquetteDebugInformation:
        """Initialise a :class:`.DebugInformation` instance from a dictionary."""
        return PlaquetteDebugInformation(
            (RPNGDescription.from_dict(data["rpng"]) if data["rpng"] is not None else None),
            (
                DrawPolygon.from_json(data["draw_polygons"])
                if data["draw_polygons"] is not None
                else None
            ),
        )

    def get_svg_drawer(self) -> SVGPlaquetteDrawer:  # pragma: no cover
        """Get a drawer to draw the plaquette associated to ``self``."""
        if self.drawer is not None:
            return self.drawer
        if self.rpng is not None:
            return RPNGPlaquetteDrawer(self.rpng)
        return EmptySVGPlaquetteDrawer()
