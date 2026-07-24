"""Tests that splitting the SketchUp template catalog DAE works.

``assets/template.dae`` is the authoring template
shipped with the project. It's a one ``.dae`` file
with all blocks laid out side by side in SketchUp.

These tests cover splitting, import, and validation of the catalog only. They deliberately
say nothing about compilation, circuits, or benchmark outcomel.

The template is a catalog, not a set of complete gadgets, so some of the emission may not correspond to
valid computations/block graphs/gadgets. Those parts are
failed individually (see ``_EXPECTED_INVALID_PARTS``) rather than weakening the whole test.
"""

from __future__ import annotations

from pathlib import Path

import collada
import numpy as np
import pytest

from tqec.interop.batch import _world_bounds, split_dae_batch
from tqec.interop.collada import read_block_graph_from_dae_file

ASSETS_DIR = Path(__file__).parent.parent.parent / "assets"

# Characterized empirically by splitting assets/template.dae (not guessed): the catalog
# partitions into exactly this many geometry components under the touch-rule adjacency.
EXPECTED_COUNT = 23

# The last five catalog entries are standalone swatches that cannot import or validate as a
# complete computation. Reasons were read off the raised errors during characterization.
# TODO: route every block besides 21 to some minimally
# valid gadget that includes that gadget; that would be beyond the scope of
# this module, which just tests that the template can be partitioned into each
# block, and each of the blocks experience validation.
_EXPECTED_INVALID_PARTS = {
    19: "standalone Y half cube with no connecting time-like pipe",
    20: "patch rotation block",
    21: "open-port block",
    22: "'T' basis placeholder block",
    23: "second 'T' basis placeholder block",
}


def _importable_indices() -> list[int]:
    """Return the one-based indices of the parts expected to import and validate."""
    return [i for i in range(1, EXPECTED_COUNT + 1) if i not in _EXPECTED_INVALID_PARTS]


def test_template_nested_port_geometry_is_discoverable(tmp_path: Path) -> None:
    """The recursion fix must find geometry nested inside ``port`` sub-nodes.

    Before the fix this raised ``Could not read geometry vertices for DAE node ID631``
    because only the immediate children of the referenced library node were inspected.
    """
    parts = split_dae_batch(ASSETS_DIR / "template.dae", tmp_path)
    assert parts


def test_component_count_and_names_are_locked(tmp_path: Path) -> None:
    """Lock the component count and the exact ordered output filenames."""
    parts = split_dae_batch(ASSETS_DIR / "template.dae", tmp_path)
    assert [p.name for p in parts] == [
        f"template_batch{i:02d}.dae" for i in range(1, EXPECTED_COUNT + 1)
    ]


def test_split_is_deterministic(tmp_path: Path) -> None:
    """Two independent splits must produce identical ordered files and identical graphs."""
    first = split_dae_batch(ASSETS_DIR / "template.dae", tmp_path / "first")
    second = split_dae_batch(ASSETS_DIR / "template.dae", tmp_path / "second")

    assert [p.name for p in first] == [p.name for p in second]

    for index in _importable_indices():
        left = read_block_graph_from_dae_file(first[index - 1], graph_name="g").to_json()
        right = read_block_graph_from_dae_file(second[index - 1], graph_name="g").to_json()
        assert left == right


@pytest.mark.parametrize(
    "index",
    [
        pytest.param(
            i,
            marks=pytest.mark.xfail(
                reason=_EXPECTED_INVALID_PARTS[i], strict=True, raises=Exception
            ),
        )
        if i in _EXPECTED_INVALID_PARTS
        else i
        for i in range(1, EXPECTED_COUNT + 1)
    ],
)
def test_each_template_part_imports_and_validates(tmp_path: Path, index: int) -> None:
    """Every catalog part must import and validate, except the known placeholder swatches.

    The placeholder swatches are xfailed individually (strict) so that a change which made
    one of them import cleanly would surface as an unexpected pass rather than silently.
    """
    parts = split_dae_batch(ASSETS_DIR / "template.dae", tmp_path)
    part = parts[index - 1]
    read_block_graph_from_dae_file(part, graph_name=part.stem).validate()


def _build_nested_geometry_node(
    translation: tuple[float, float, float],
) -> collada.scene.Node:


    Args:
        translation: World-space translation applied by the top block node's matrix.

    Returns:
        The top-level block :py:class:`~collada.scene.Node`.

    """
    mesh = collada.Collada()
    # A unit square in the geometry's own local frame.
    vertices = np.array([0, 0, 0, 1, 0, 0, 1, 1, 0, 0, 1, 0], dtype=np.float32)
    vertex_source = collada.source.FloatSource("vsrc", vertices, ("X", "Y", "Z"))
    geometry = collada.geometry.Geometry(mesh, "geom0", "geom0", [vertex_source])
    input_list = collada.source.InputList()
    input_list.addInput(0, "VERTEX", "#vsrc")
    indices = np.array([0, 1, 2, 0, 2, 3], dtype=np.int32)
    geometry.primitives.append(geometry.createTriangleSet(indices, input_list, "mat"))

    geometry_node = collada.scene.GeometryNode(geometry, [])
    port_lib = collada.scene.Node("port_lib", children=[geometry_node], name="port")
    inner_block = collada.scene.Node(
        "inner_block",
        children=[collada.scene.NodeNode(port_lib)],
        name="SketchUp_Instance_inner",
    )
    ooo_lib = collada.scene.Node("ooo_lib", children=[inner_block], name="ooo")
    transform = collada.scene.MatrixTransform(
        np.array(
            [
                [1, 0, 0, translation[0]],
                [0, 1, 0, translation[1]],
                [0, 0, 1, translation[2]],
                [0, 0, 0, 1],
            ],
            dtype=np.float32,
        ).flatten()
    )
    return collada.scene.Node(
        "block",
        children=[collada.scene.NodeNode(ooo_lib)],
        transforms=[transform],
        name="SketchUp_Instance_outer",
    )


def test_world_bounds_reads_nested_geometry() -> None:
    """``_world_bounds`` composes nested transforms and finds deeply nested geometry.

    This is the synthetic cover for the recursion, independent of the large asset.
    """
    node = _build_nested_geometry_node((10.0, 5.0, -2.0))

    low, high = _world_bounds(node)

    assert low.dtype == np.float64
    assert high.dtype == np.float64
    # Unit square (0..1, 0..1, 0) shifted by the block node's translation.
    assert np.allclose(low, [10.0, 5.0, -2.0])
    assert np.allclose(high, [11.0, 6.0, -2.0])
