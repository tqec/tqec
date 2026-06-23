"""Converter tests using pytest's ``tmp_path`` fixture.

These tests use Steane encoding because it is the most visually complex gallery
example available.
"""

from tqec.gallery.steane_encoding import steane_encoding
from tqec.interop.bgraph import read_bgraph
from tqec.interop.collada import read_block_graph_from_dae_file
from tqec.interop.converters import bgraph_to_dae, dae_to_bgraph
from tqec.utils.enums import Basis


def test_dae_to_bgraph(tmp_path) -> None:
    graph = steane_encoding(Basis.X)
    dae_path = tmp_path / "input.dae"
    bgraph_path = tmp_path / "output.bgraph"

    graph.to_dae_file(dae_path)
    dae_to_bgraph(dae_path, bgraph_path)
    result = read_bgraph(bgraph_path)

    assert result == graph


def test_bgraph_to_dae(tmp_path) -> None:
    graph = steane_encoding(Basis.X)
    dae_path = tmp_path / "output.dae"
    bgraph_path = tmp_path / "input.bgraph"

    graph.to_bgraph(bgraph_path)
    bgraph_to_dae(bgraph_path, dae_path)
    result = read_block_graph_from_dae_file(dae_path)

    assert result == graph


def test_dae_bgraph_dae_roundtrip(tmp_path) -> None:
    expected = steane_encoding(Basis.X)
    input_dae_path = tmp_path / "input.dae"
    bgraph_path = tmp_path / "middleman.bgraph"
    output_dae_path = tmp_path / "output.dae"

    expected.to_dae_file(input_dae_path)
    dae_to_bgraph(input_dae_path, bgraph_path)
    bgraph_to_dae(bgraph_path, output_dae_path)
    result = read_block_graph_from_dae_file(output_dae_path)

    assert result == expected
