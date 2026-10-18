from collections.abc import Callable

import pytest
import pyzx as zx

from tqec.computation.block_graph import BlockGraph
from tqec.gallery import cnot, cz, move_rotation, three_cnots


@pytest.mark.parametrize(
    "graph_fn, inputs, outputs, qasm",
    [
        (cnot, (0, 6), (3, 9), "qreg q[2]; cx q[0], q[1];"),
        (cz, (0, 3), (2, 5), "qreg q[2]; cz q[0], q[1];"),
        (move_rotation, (0,), (4,), "qreg q[1];"),
        (
            three_cnots,
            (1, 4, 8),
            (0, 7, 11),
            "qreg q[3]; cx q[0], q[1]; cx q[1], q[2]; cx q[0], q[2];",
        ),
    ],
    ids=["cnot", "cz", "move_rotation", "three_cnots"],
)
def test_gallery_tensor_equivalence(
    graph_fn: Callable[[], BlockGraph],
    inputs: tuple[int, ...],
    outputs: tuple[int, ...],
    qasm: str,
) -> None:
    g = graph_fn().to_zx_graph().g
    g.set_inputs(inputs)
    g.set_outputs(outputs)

    c = zx.qasm(qasm)
    assert zx.compare_tensors(c, g)
