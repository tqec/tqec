"""Tests for batch processing of files holding several disjoint block graphs."""

from pathlib import Path

import pytest

from tqec.computation.block_graph import BlockGraph
from tqec.interop.batch import (
    BatchImportFailure,
    batch_dae_to_bgraph,
    batch_member_stem,
    split_dae_batch,
)
from tqec.interop.collada import read_block_graph_from_dae_file
from tqec.utils.exceptions import TQECError
from tqec.utils.position import Position3D

# Eight Y-half-cube structures laid out side by side in a single SketchUp export. This is
# the file behind https://github.com/tqec/tqec/issues/967: every structure was placed
# independently and so carries its own world-space translation.
DISJOINT_GADGETS_DAE = Path(__file__).parent / "collada" / "test_files" / "disjoint_y_gadgets.dae"


def _two_disjoint_structures() -> BlockGraph:
    """Build a graph with two components far enough apart that their geometry cannot touch."""
    graph = BlockGraph("pair")
    graph.add_cube(Position3D(0, 0, 0), "ZXZ")
    graph.add_cube(Position3D(1, 0, 0), "ZXZ")
    graph.add_pipe(Position3D(0, 0, 0), Position3D(1, 0, 0))

    graph.add_cube(Position3D(8, 0, 0), "ZXZ")
    graph.add_cube(Position3D(8, 0, 1), "ZXX")
    graph.add_pipe(Position3D(8, 0, 0), Position3D(8, 0, 1))
    return graph


def test_batch_member_stem() -> None:
    assert batch_member_stem("gadgets", 1) == "gadgets_batch01"
    assert batch_member_stem("gadgets", 12) == "gadgets_batch12"
    assert batch_member_stem("u", 100) == "u_batch100"


def test_split_into_connected_components() -> None:
    components = _two_disjoint_structures().split_into_connected_components()

    assert [c.name for c in components] == ["pair_batch01", "pair_batch02"]
    assert [(c.num_cubes, c.num_pipes) for c in components] == [(2, 1), (2, 1)]
    assert all(c.is_single_connected() for c in components)


def test_split_into_connected_components_on_connected_graph() -> None:
    graph = BlockGraph("single")
    graph.add_cube(Position3D(0, 0, 0), "ZXZ")
    graph.add_cube(Position3D(1, 0, 0), "ZXZ")
    graph.add_pipe(Position3D(0, 0, 0), Position3D(1, 0, 0))

    components = graph.split_into_connected_components()

    assert len(components) == 1
    assert components[0].num_cubes == graph.num_cubes
    assert components[0].num_pipes == graph.num_pipes


def test_split_into_connected_components_carries_ports_per_component() -> None:
    """Each component must keep its own ports and none of the others'."""
    graph = BlockGraph("ports")
    graph.add_cube(Position3D(0, 0, 0), "P", "in_a")
    graph.add_cube(Position3D(1, 0, 0), "ZXZ")
    graph.add_pipe(Position3D(0, 0, 0), Position3D(1, 0, 0), "OXZ")
    graph.add_cube(Position3D(9, 0, 0), "P", "in_b")
    graph.add_cube(Position3D(10, 0, 0), "ZXZ")
    graph.add_pipe(Position3D(9, 0, 0), Position3D(10, 0, 0), "OXZ")

    first, second = graph.split_into_connected_components()

    assert first.ports == {"in_a": Position3D(0, 0, 0)}
    assert second.ports == {"in_b": Position3D(9, 0, 0)}
    first.validate()
    second.validate()


def test_split_into_connected_components_on_empty_graph() -> None:
    assert BlockGraph("empty").split_into_connected_components() == []


def test_split_dae_batch_roundtrips_each_component(tmp_path: Path) -> None:
    source = tmp_path / "pair.dae"
    _two_disjoint_structures().to_dae_file(source)

    components = split_dae_batch(source, tmp_path / "out")

    assert [p.name for p in components] == ["pair_batch01.dae", "pair_batch02.dae"]
    imported = [read_block_graph_from_dae_file(p) for p in components]
    assert sorted((g.num_cubes, g.num_pipes) for g in imported) == [(2, 1), (2, 1)]
    assert all(g.is_single_connected() for g in imported)


def test_split_dae_batch_clean_removes_stale_outputs(tmp_path: Path) -> None:
    source = tmp_path / "pair.dae"
    _two_disjoint_structures().to_dae_file(source)
    out = tmp_path / "out"
    out.mkdir()
    stale = out / "stale.dae"
    stale.write_text("")

    split_dae_batch(source, out, clean=True)

    assert not stale.exists()


def test_split_dae_batch_rejects_non_sketchup_file(tmp_path: Path) -> None:
    source = tmp_path / "not_collada.dae"
    source.write_text("<not-collada/>")

    with pytest.raises(TQECError, match="exactly one Collada scene node"):
        split_dae_batch(source, tmp_path / "out")


def test_batch_dae_to_bgraph_reports_failures_without_raising(tmp_path: Path) -> None:
    good = tmp_path / "good.dae"
    _two_disjoint_structures().split_into_connected_components()[0].to_dae_file(good)
    bad = tmp_path / "bad.dae"
    bad.write_text("<not-collada/>")

    written, failures = batch_dae_to_bgraph([good, bad], tmp_path / "bgs")

    assert [p.name for p in written] == ["good.bgraph"]
    assert len(failures) == 1
    assert isinstance(failures[0], BatchImportFailure)
    assert failures[0].path == bad
    assert "bad.dae" in str(failures[0])


def test_disjoint_gadgets_dae_splits_into_eight_importable_components(tmp_path: Path) -> None:
    """Regression for #967: rotated Y-half-cube structures must import once separated."""
    components = split_dae_batch(DISJOINT_GADGETS_DAE, tmp_path / "dae")
    assert len(components) == 8

    for component in components:
        graph = read_block_graph_from_dae_file(component, graph_name=component.stem)
        # Each structure is a single connected gadget with at least one Y half cube.
        assert graph.is_single_connected()
        assert graph.num_half_y_cubes > 0
        # Y half cubes may only carry time-like pipes; validate() enforces that, so a
        # wrong lattice offset that still landed on integers would be caught here.
        graph.validate()
        # An independent encoding of the same graph, as a check on cube positions.
        assert BlockGraph.from_bgraph(graph.to_bgraph(graph_name=component.stem)) == graph


def test_disjoint_gadgets_dae_batch_converts_to_bgraph(tmp_path: Path) -> None:
    components = split_dae_batch(DISJOINT_GADGETS_DAE, tmp_path / "dae")
    written, failures = batch_dae_to_bgraph(components, tmp_path / "bgs")

    assert failures == []
    assert [p.name for p in written] == [
        f"disjoint_y_gadgets_batch{index:02d}.bgraph" for index in range(1, 9)
    ]


def test_whole_file_import_of_independently_placed_structures_is_not_supported() -> None:
    """The monolith cannot import: one inferred lattice offset cannot cancel eight.

    This documents *why* :py:func:`split_dae_batch` exists rather than being a convenience
    wrapper around a whole-file import. If this ever starts passing, the DAE importer has
    learned per-component offsets and this test should become an equivalence check.
    """
    with pytest.raises(TQECError):
        read_block_graph_from_dae_file(DISJOINT_GADGETS_DAE)
