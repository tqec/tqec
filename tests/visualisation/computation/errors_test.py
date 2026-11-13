import pytest

from tqec.compile.compile import compile_block_graph
from tqec.gallery import memory
from tqec.utils.enums import Basis
from tqec.utils.noise_model import NoiseModel


@pytest.mark.parametrize("pauli", ["X", "Y", "Z"])
def test_layers_to_svg_draws_errors_of_each_pauli(pauli: str) -> None:
    g = memory(Basis.Z)
    tree = compile_block_graph(g, observables=g.find_correlation_surfaces()).to_layer_tree()
    circuit = NoiseModel.uniform_depolarizing(1e-3).noisy_circuit(tree.generate_circuit(1))
    errors = [
        e
        for e in circuit.explain_detector_error_model_errors()
        if e.circuit_error_locations[0].flipped_pauli_product
        and e.circuit_error_locations[0].flipped_pauli_product[0].gate_target.pauli_type == pauli
    ]
    assert errors
    svgs = tree.layers_to_svg(1, errors=errors[:1])
    assert svgs
