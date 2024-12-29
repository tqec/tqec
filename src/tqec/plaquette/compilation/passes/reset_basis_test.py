import pytest
import stim

from tqec.exceptions import TQECException
from tqec.plaquette.compilation.passes.reset_basis import ChangeResetBasisPass
from tqec.plaquette.enums import ResetBasis


def test_compilation_pass_creation() -> None:
    ChangeResetBasisPass(ResetBasis.X)
    ChangeResetBasisPass(ResetBasis.Z)


def test_simple_reset_basis() -> None:
    compilation_pass = ChangeResetBasisPass(ResetBasis.Z)
    assert compilation_pass.run(stim.Circuit("R 0")) == stim.Circuit("R 0")
    assert compilation_pass.run(stim.Circuit("RZ 0")) == stim.Circuit("RZ 0")
    assert compilation_pass.run(stim.Circuit("R 12")) == stim.Circuit("R 12")
    assert compilation_pass.run(stim.Circuit("RX 0")) == stim.Circuit("RZ 0\nTICK\nH 0")
    assert compilation_pass.run(stim.Circuit("RX 9")) == stim.Circuit("RZ 9\nTICK\nH 9")

    with pytest.raises(
        TQECException, match="^Found a RY instruction, that is not supported.$"
    ):
        compilation_pass.run(stim.Circuit("RY 0"))


def test_x_reset_basis() -> None:
    compilation_pass = ChangeResetBasisPass(ResetBasis.X)
    assert compilation_pass.run(stim.Circuit("R 0")) == stim.Circuit("RX 0\nTICK\nH 0")
    assert compilation_pass.run(stim.Circuit("RZ 0")) == stim.Circuit("RX 0\nTICK\nH 0")
    assert compilation_pass.run(stim.Circuit("RX 12")) == stim.Circuit("RX 12")
    assert compilation_pass.run(stim.Circuit("RX 0")) == stim.Circuit("RX 0")
    assert compilation_pass.run(stim.Circuit("RZ 9")) == stim.Circuit("RX 9\nTICK\nH 9")

    with pytest.raises(
        TQECException, match="^Found a RY instruction, that is not supported.$"
    ):
        compilation_pass.run(stim.Circuit("RY 0"))


def test_edge_cases_reset_basis() -> None:
    compilation_pass = ChangeResetBasisPass(ResetBasis.Z)
    assert compilation_pass.run(stim.Circuit("H 0")) == stim.Circuit("H 0")
    assert compilation_pass.run(stim.Circuit()) == stim.Circuit()
