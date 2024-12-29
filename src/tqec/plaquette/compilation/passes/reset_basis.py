from tqec.plaquette.compilation.passes.basis_change import ChangeBasisPass
from tqec.plaquette.enums import ResetBasis


class ChangeResetBasisPass(ChangeBasisPass):
    def __init__(self, basis: ResetBasis):
        super().__init__(basis)
