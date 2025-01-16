from typing import Literal, Protocol

from tqec.enums import Basis
from tqec.plaquette.enums import PlaquetteSide
from tqec.plaquette.plaquette import Plaquette


class PlaquetteBuilder(Protocol):
    """Protocol for functions building a `Plaquette`."""

    def __call__(
        self,
        basis: Literal["X", "Z"],
        data_initialization: Basis | None = None,
        data_measurement: Basis | None = None,
        x_boundary_orientation: Literal["HORIZONTAL", "VERTICAL"] = "HORIZONTAL",
        init_meas_only_on_side: PlaquetteSide | None = None,
    ) -> Plaquette: ...
