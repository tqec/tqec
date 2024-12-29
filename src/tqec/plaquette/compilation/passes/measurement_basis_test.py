import pytest
import stim

from tqec.exceptions import TQECException
from tqec.plaquette.compilation.passes.measurement_basis import (
    ChangeMeasurementBasisPass,
)
from tqec.plaquette.enums import MeasurementBasis


def test_compilation_pass_creation() -> None:
    ChangeMeasurementBasisPass(MeasurementBasis.X)
    ChangeMeasurementBasisPass(MeasurementBasis.Z)


def test_simple_reset_basis() -> None:
    compilation_pass = ChangeMeasurementBasisPass(MeasurementBasis.Z)
    assert compilation_pass.run(stim.Circuit("M 0")) == stim.Circuit("M 0")
    assert compilation_pass.run(stim.Circuit("MZ 0")) == stim.Circuit("MZ 0")
    assert compilation_pass.run(stim.Circuit("M 12")) == stim.Circuit("M 12")
    assert compilation_pass.run(stim.Circuit("MX 0")) == stim.Circuit("H 0\nTICK\nMZ 0")
    assert compilation_pass.run(stim.Circuit("MX 9")) == stim.Circuit("H 9\nTICK\nMZ 9")

    with pytest.raises(
        TQECException, match="^Found a MY instruction, that is not supported.$"
    ):
        compilation_pass.run(stim.Circuit("MY 0"))


def test_x_reset_basis() -> None:
    compilation_pass = ChangeMeasurementBasisPass(MeasurementBasis.X)
    assert compilation_pass.run(stim.Circuit("M 0")) == stim.Circuit("H 0\nTICK\nMX 0")
    assert compilation_pass.run(stim.Circuit("MZ 0")) == stim.Circuit("H 0\nTICK\nMX 0")
    assert compilation_pass.run(stim.Circuit("MX 12")) == stim.Circuit("MX 12")
    assert compilation_pass.run(stim.Circuit("MX 0")) == stim.Circuit("MX 0")
    assert compilation_pass.run(stim.Circuit("MZ 9")) == stim.Circuit("H 9\nTICK\nMX 9")

    with pytest.raises(
        TQECException, match="^Found a MY instruction, that is not supported.$"
    ):
        compilation_pass.run(stim.Circuit("MY 0"))


def test_edge_cases_reset_basis() -> None:
    compilation_pass = ChangeMeasurementBasisPass(MeasurementBasis.Z)
    assert compilation_pass.run(stim.Circuit("H 0")) == stim.Circuit("H 0")
    assert compilation_pass.run(stim.Circuit()) == stim.Circuit()
