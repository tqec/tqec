import os
import tempfile

from tqec.gallery.cnot import cnot
from tqec.interop.bgraph import read_bgraph
from tqec.interop.collada import read_block_graph_from_dae_file
from tqec.interop.converters import bgraph_to_dae, dae_to_bgraph
from tqec.utils.enums import Basis


def test_dae_to_bgraph() -> None:
    graph = cnot(Basis.X)
    with tempfile.NamedTemporaryFile(suffix=".dae", delete=False) as dae_f:
        dae_path = dae_f.name
    with tempfile.NamedTemporaryFile(suffix=".bgraph", delete=False) as bgraph_f:
        bgraph_path = bgraph_f.name
    try:
        graph.to_dae_file(dae_path)
        dae_to_bgraph(dae_path, bgraph_path)
        result = read_bgraph(bgraph_path)
    finally:
        os.remove(dae_path)
        os.remove(bgraph_path)
    assert result == graph


def test_bgraph_to_dae() -> None:
    graph = cnot(Basis.X)
    with tempfile.NamedTemporaryFile(suffix=".bgraph", delete=False) as bgraph_f:
        bgraph_path = bgraph_f.name
    with tempfile.NamedTemporaryFile(suffix=".dae", delete=False) as dae_f:
        dae_path = dae_f.name
    try:
        graph.to_bgraph(bgraph_path)
        bgraph_to_dae(bgraph_path, dae_path)
        result = read_block_graph_from_dae_file(dae_path)
    finally:
        os.remove(bgraph_path)
        os.remove(dae_path)
    assert result == graph


def test_dae_bgraph_dae_roundtrip() -> None:
    graph = cnot(Basis.X)
    with tempfile.NamedTemporaryFile(suffix=".dae", delete=False) as f1:
        dae_path1 = f1.name
    with tempfile.NamedTemporaryFile(suffix=".bgraph", delete=False) as bgraph_f:
        bgraph_path = bgraph_f.name
    with tempfile.NamedTemporaryFile(suffix=".dae", delete=False) as f2:
        dae_path2 = f2.name
    try:
        graph.to_dae_file(dae_path1)
        dae_to_bgraph(dae_path1, bgraph_path)
        bgraph_to_dae(bgraph_path, dae_path2)
        result = read_block_graph_from_dae_file(dae_path2)
    finally:
        os.remove(dae_path1)
        os.remove(bgraph_path)
        os.remove(dae_path2)
    assert result == graph
