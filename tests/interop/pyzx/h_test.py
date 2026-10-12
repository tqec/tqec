import pyzx as zx

from tqec.gallery.h import h


def test_h_open_zx() -> None:
    g = h().to_zx_graph().g
    g.set_inputs((0,))
    g.set_outputs((3,))

    c = zx.qasm("""
qreg q[1];
h q[0];
""")
    assert zx.compare_tensors(c, g)
