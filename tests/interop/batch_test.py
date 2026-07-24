"""Tests for batch processing of files holding several disjoint block graphs."""

import argparse
from pathlib import Path

import collada
import pytest

from tqec._cli.subcommands.dae2batch import Dae2BatchTQECSubCommand
from tqec.computation.block_graph import BlockGraph
from tqec.gallery.cnot import cnot
from tqec.interop.batch import (
    BatchImportFailure,
    batch_dae_to_bgraph,
    batch_member_stem,
    split_dae_batch,
)
from tqec.interop.collada import read_block_graph_from_dae_file
from tqec.interop.collada.read_write import _CORRELATION_SUFFIX
from tqec.utils.enums import Basis
from tqec.utils.exceptions import TQECError
from tqec.utils.position import Position3D


def _count_correlation_instances(dae_path: Path) -> int:
    """Count correlation-surface instance nodes in a written DAE scene."""
    mesh = collada.Collada(str(dae_path))
    assert mesh.scene is not None
    count = 0
    for node in mesh.scene.nodes[0].children:
        if (
            node.children
            and isinstance(node.children[0], collada.scene.NodeNode)
            and node.children[0].node.name.endswith(_CORRELATION_SUFFIX)
        ):
            count += 1
    return count


# Eight Y-half-cube structures laid out side by side in a single SketchUp export. This is
# the file behind https://github.com/tqec/tqec/issues/967: every structure was placed
# independently and so carries its own world-space translation.
DISJOINT_GADGETS_DAE = (
    Path(__file__).parent / "collada" / "test_files" / "disjoint_y_gadgets.dae"
)


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


def test_partition() -> None:
    components = _two_disjoint_structures().partition()

    assert [c.name for c in components] == ["pair_batch01", "pair_batch02"]
    assert [(c.num_cubes, c.num_pipes) for c in components] == [(2, 1), (2, 1)]
    assert all(c.is_single_connected() for c in components)


def test_partition_on_connected_graph() -> None:
    graph = BlockGraph("single")
    graph.add_cube(Position3D(0, 0, 0), "ZXZ")
    graph.add_cube(Position3D(1, 0, 0), "ZXZ")
    graph.add_pipe(Position3D(0, 0, 0), Position3D(1, 0, 0))

    components = graph.partition()

    assert len(components) == 1
    assert components[0].num_cubes == graph.num_cubes
    assert components[0].num_pipes == graph.num_pipes


def test_partition_carries_ports_per_component() -> None:
    """Each component must keep its own ports and none of the others'."""
    graph = BlockGraph("ports")
    graph.add_cube(Position3D(0, 0, 0), "P", "in_a")
    graph.add_cube(Position3D(1, 0, 0), "ZXZ")
    graph.add_pipe(Position3D(0, 0, 0), Position3D(1, 0, 0), "OXZ")
    graph.add_cube(Position3D(9, 0, 0), "P", "in_b")
    graph.add_cube(Position3D(10, 0, 0), "ZXZ")
    graph.add_pipe(Position3D(9, 0, 0), Position3D(10, 0, 0), "OXZ")

    first, second = graph.partition()

    assert first.ports == {"in_a": Position3D(0, 0, 0)}
    assert second.ports == {"in_b": Position3D(9, 0, 0)}
    first.validate()
    second.validate()


def test_partition_on_empty_graph() -> None:
    assert BlockGraph("empty").partition() == []


def test_add_pipes_automatically_keeps_gapped_gadgets_separate() -> None:
    """Gadget identity is connectivity: a one-site gap survives auto-connection and split.

    Two cubes one empty lattice position apart are not lattice-adjacent, so
    ``add_pipes_automatically`` adds no pipe between them and they remain two components.
    This is the documented way to keep neighbouring gadgets separate.
    """
    graph = BlockGraph("gapped")
    graph.add_cube(Position3D(0, 0, 0), "ZXZ")
    graph.add_cube(Position3D(2, 0, 0), "ZXZ")  # one empty site at x == 1

    graph.add_pipes_automatically()
    components = graph.partition()

    assert graph.num_pipes == 0
    assert [c.num_cubes for c in components] == [1, 1]


def test_add_pipes_automatically_merges_adjacent_gadgets() -> None:
    """The flip side: cubes with no gap are connected and merged into one component.

    ``add_pipes_automatically`` connects every lattice-adjacent compatible pair, so two
    gadgets that happen to sit next to each other are merged with no recoverable boundary.
    """
    graph = BlockGraph("adjacent")
    graph.add_cube(Position3D(0, 0, 0), "ZXZ")
    graph.add_cube(Position3D(1, 0, 0), "ZXZ")  # lattice-adjacent, no gap

    graph.add_pipes_automatically()
    components = graph.partition()

    assert graph.num_pipes == 1
    assert len(components) == 1


def test_split_dae_batch_merges_touching_bounding_boxes(tmp_path: Path) -> None:
    """The DAE route groups by touching world-space bounding boxes, not by pipes.

    Two independent single-cube gadgets whose geometry gives axis-aligned bounding boxes which overlap within ``_ADJACENCY_TOLERANCE`` are merged into one component even
    though no pipe connects them, whereas a clear gap keeps them separate. This documents
    the false-merge risk for geometrically close but semantically separate structures.
    """
    # A tiny pipe length places lattice-adjacent unit cubes face-to-face in world space.
    touching = BlockGraph("touching")
    touching.add_cube(Position3D(0, 0, 0), "ZXZ")
    touching.add_cube(Position3D(1, 0, 0), "ZXZ")
    touching_source = tmp_path / "touching.dae"
    touching.to_dae_file(touching_source, 1e-7)
    assert len(split_dae_batch(touching_source, tmp_path / "touching_out")) == 1

    # A clear gap keeps the same two cubes in separate components.
    gapped = BlockGraph("gapped")
    gapped.add_cube(Position3D(0, 0, 0), "ZXZ")
    gapped.add_cube(Position3D(5, 0, 0), "ZXZ")
    gapped_source = tmp_path / "gapped.dae"
    gapped.to_dae_file(gapped_source, 2.0)
    assert len(split_dae_batch(gapped_source, tmp_path / "gapped_out")) == 2


def test_split_dae_batch_roundtrips_each_component(tmp_path: Path) -> None:
    source = tmp_path / "pair.dae"
    _two_disjoint_structures().to_dae_file(source)

    components = split_dae_batch(source, tmp_path / "out")

    assert [p.name for p in components] == ["pair_batch01.dae", "pair_batch02.dae"]
    imported = [read_block_graph_from_dae_file(p) for p in components]
    assert sorted((g.num_cubes, g.num_pipes) for g in imported) == [(2, 1), (2, 1)]
    assert all(g.is_single_connected() for g in imported)


def test_split_dae_batch_preserves_correlation_surface_in_every_output(
    tmp_path: Path,
) -> None:
    """Correlation-surface nodes belong to no component but must survive into every output.

    Regression: correlation instances carry an ``id``, are in no component, and were
    therefore dropped from every output, silently losing the surface the file documents.
    """
    graph = cnot(Basis.X)
    surface = graph.find_correlation_surfaces()[0]
    # A far-away, disjoint structure so the file splits into two components. It takes no
    # part in the correlation surface, which spans only the cnot geometry.
    graph.add_cube(Position3D(20, 0, 0), "ZXZ")
    graph.add_cube(Position3D(21, 0, 0), "ZXZ")
    graph.add_pipe(Position3D(20, 0, 0), Position3D(21, 0, 0))

    source = tmp_path / "corr.dae"
    graph.to_dae_file(source, 2.0, show_correlation_surface=surface)
    source_correlation_count = _count_correlation_instances(source)
    assert source_correlation_count > 0

    components = split_dae_batch(source, tmp_path / "out")

    assert len(components) == 2
    for component in components:
        assert _count_correlation_instances(component) == source_correlation_count


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
    _two_disjoint_structures().partition()[0].to_dae_file(good)
    bad = tmp_path / "bad.dae"
    bad.write_text("<not-collada/>")

    written, failures = batch_dae_to_bgraph([good, bad], tmp_path / "bgs")

    assert [p.name for p in written] == ["good.bgraph"]
    assert len(failures) == 1
    assert isinstance(failures[0], BatchImportFailure)
    assert failures[0].path == bad
    assert "bad.dae" in str(failures[0])


def test_batch_dae_to_bgraph_does_not_swallow_unexpected_errors(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Only expected import/conversion errors become failures; the rest must propagate.

    A programming error such as ``AttributeError`` is not an import failure and must not be
    reported as a mere batch-member failure, or automation would never learn of the bug.
    """
    good = tmp_path / "good.dae"
    _two_disjoint_structures().partition()[0].to_dae_file(good)

    def _boom(*_args: object, **_kwargs: object) -> None:
        raise AttributeError("simulated programming error")

    monkeypatch.setattr("tqec.interop.batch.dae_to_bgraph", _boom)

    with pytest.raises(AttributeError, match="simulated programming error"):
        batch_dae_to_bgraph([good], tmp_path / "bgs")


def test_dae2batch_cli_exits_nonzero_and_reports_failures_on_stderr(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """A reported (not raised) conversion failure exits nonzero, with details on stderr.

    The split runs for real; only the innermost conversion is forced to reject one member,
    exercising the batch failure-collection, the CLI exit-code wiring, and the stream
    routing that keeps failure noise off stdout for scheduler logs and pipelines.
    """
    source = tmp_path / "pair.dae"
    _two_disjoint_structures().to_dae_file(source)

    def _reject(*_args: object, **_kwargs: object) -> None:
        raise TQECError("simulated import failure")

    monkeypatch.setattr("tqec.interop.batch.dae_to_bgraph", _reject)

    args = argparse.Namespace(
        dae_file=source, out_dir=tmp_path / "out", bgraph=True, clean=False
    )
    with pytest.raises(SystemExit) as exit_info:
        Dae2BatchTQECSubCommand.execute(args)
    assert exit_info.value.code == 1

    captured = capsys.readouterr()
    # The partial-failure summary and the per-member failures are on stderr, not stdout.
    assert "failed:" in captured.err
    assert "simulated import failure" in captured.err
    assert "failed:" not in captured.out
    # The successful split summary stays on stdout.
    assert "component .dae files" in captured.out


def test_dae2batch_cli_exits_zero_when_all_convert(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A fully successful bgraph conversion must not exit nonzero and stays on stdout."""
    source = tmp_path / "pair.dae"
    _two_disjoint_structures().to_dae_file(source)

    args = argparse.Namespace(
        dae_file=source, out_dir=tmp_path / "out", bgraph=True, clean=False
    )
    # Returns normally (no SystemExit) when every component converts.
    Dae2BatchTQECSubCommand.execute(args)

    captured = capsys.readouterr()
    assert "Converted 2/2 components to .bgraph" in captured.out
    assert captured.err == ""


def test_disjoint_gadgets_dae_splits_into_eight_importable_components(
    tmp_path: Path,
) -> None:
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
        assert (
            BlockGraph.from_bgraph(graph.to_bgraph(graph_name=component.stem)) == graph
        )


def test_disjoint_gadgets_dae_batch_converts_to_bgraph(tmp_path: Path) -> None:
    components = split_dae_batch(DISJOINT_GADGETS_DAE, tmp_path / "dae")
    written, failures = batch_dae_to_bgraph(components, tmp_path / "bgs")

    assert failures == []
    assert [p.name for p in written] == [
        f"disjoint_y_gadgets_batch{index:02d}.bgraph" for index in range(1, 9)
    ]


def test_whole_file_import_of_independently_placed_structures_is_not_supported() -> (
    None
):
    """The monolith cannot import: one inferred lattice offset cannot cancel eight.

    This documents *why* :py:func:`split_dae_batch` exists rather than being a convenience
    wrapper around a whole-file import. If this ever starts passing, the DAE importer has
    learned per-component offsets and this test should become an equivalence check.
    """
    with pytest.raises(TQECError):
        read_block_graph_from_dae_file(DISJOINT_GADGETS_DAE)
