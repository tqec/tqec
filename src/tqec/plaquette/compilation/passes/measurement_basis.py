from tqec.plaquette.compilation.passes.basis_change import ChangeBasisPass
from tqec.plaquette.enums import MeasurementBasis


class ChangeMeasurementBasisPass(ChangeBasisPass):
    def __init__(self, basis: MeasurementBasis):
        super().__init__(basis)
