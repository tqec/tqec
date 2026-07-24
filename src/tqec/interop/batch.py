"""Batch processing of files holding several disjoint block graphs.

A model authored in a 3D GUI often contains several block graphs disconnected from one
another. ``tqec`` treats one :py:class:`~tqec.computation.block_graph.BlockGraph` as one
computation, so such a file has to be split into its connected components before any of
them can be compiled. "Batch" throughout this module means one input file describing many
independent block graphs.

Two routes are available, and they are not interchangeable:

- :py:func:`split_dae_batch` operates on the DAE itself, partitioning the Collada scene by
  the rendered geometry and writing one DAE per component. Each component is then imported
  on its own.
- :py:meth:`~tqec.computation.block_graph.BlockGraph.split_block_graph_batch`
  operates on an already imported graph. It is cheaper and exact, but it can only be
  reached if the whole file imports.

Prefer the DAE route for anything authored in a GUI. Structures placed independently in a
3D editor each acquire their own arbitrary world-space translation, and
:py:func:`~tqec.interop.collada.read_write.read_block_graph_from_dae_file` infers a single
lattice offset per axis for the whole file. One offset cannot cancel several different
ones, so a file of independently placed structures typically fails to import as a whole
even though every one of its components imports cleanly once separated. Splitting first
also isolates *post-split* conversion failures: once the component files are written,
:py:func:`batch_dae_to_bgraph` records a member that fails to import and continues with
the rest. Failures *during* discovery are not isolated--a node with unreadable geometry
raises from :py:func:`split_dae_batch` and aborts the whole split before any file is
written; structured discovery failures are deferred to the orchestration layer.

Outputs are named ``{source stem}_batch{NN}``, two-digit and one-based, so that a batch
member always carries the name of the file it came from.

Gadgets are identified by the locality of their geometry; there is no separate grouping
signal. The two routes above decide membership slightly differently, and both can merge
structures that were meant to be separate gadgets:

- The graph route
  (:py:meth:`~tqec.computation.block_graph.BlockGraph.split_block_graph_batch`)
  partitions by the current pipe edges. :py:meth:`add_pipes_automatically` connects every
  lattice-adjacent compatible pair, so it must be called before partitioning to group
  adjacent cubes, and it can merge two gadgets that happen to be lattice-adjacent. Keep
  gadgets separate by leaving at least one empty lattice position between them before
  connecting automatically. See that method's docstring for the canonical workflow.
- The DAE route (:py:func:`split_dae_batch`) infers components from geometry alone: two
  block nodes are grouped when their axis-aligned world-space bounding boxes overlap
  within ``_ADJACENCY_TOLERANCE`` ("touching"). Two structures that are geometrically
  close enough for their bounding boxes to touch are therefore merged into one component,
  even if they were authored as separate gadgets. Leave a clear gap between structures in
  the source model.

Explicit group identifiers are a possible future enhancement if adjacent-but-separate
gadgets ever need supporting. At the time of writing, spatial separation is the only way
to express that a neighbouring pair is two gadgets rather than one.
"""

from __future__ import annotations

import copy
import xml.etree.ElementTree as ET
from collections import deque
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import cast

import collada
import numpy as np
import numpy.typing as npt

from tqec.interop.collada.read_write import _CORRELATION_SUFFIX
from tqec.interop.converters import dae_to_bgraph
from tqec.utils.exceptions import TQECError

__all__ = [
    "BatchImportFailure",
    "batch_dae_to_bgraph",
    "batch_member_stem",
    "split_dae_batch",
]

# Two DAE blocks belong to the same structure when their rendered geometry touches. The
# tolerance absorbs the floating-point noise a GUI exporter leaves in vertex coordinates.
_ADJACENCY_TOLERANCE = 1e-6


def batch_member_stem(source_stem: str, index: int) -> str:
    """Return the file stem of one member of a batch.

    Args:
        source_stem: Stem of the file the batch was split out of.
        index: One-based index of the member within the batch.

    Returns:
        The member stem, for example ``batch_member_stem("gadgets", 3) == "gadgets_batch03"``.

    """
    return f"{source_stem}_batch{index:02d}"


@dataclass(frozen=True)
class BatchImportFailure:
    """One member of a batch that could not be imported.

    Batch conversion is deliberately not all-or-nothing: a single malformed structure
    should not discard the rest of the file. Failures are returned as data so the caller
    decides whether to report, skip, or raise.
    """

    path: Path
    """The input file that failed."""

    error: str
    """Type name of the raised exception, for example ``"TQECError"``."""

    message: str
    """The exception message."""

    def __str__(self) -> str:
        return f"{self.path.name}: {self.error}: {self.message}"


def split_dae_batch(
    source: str | Path,
    output_dir: str | Path,
    *,
    clean: bool = False,
) -> list[Path]:
    """Split a DAE holding several disjoint structures into one DAE per structure.

    The split is performed on the Collada scene graph rather than on an imported
    :py:class:`~tqec.computation.block_graph.BlockGraph`, so it works even when the file as
    a whole cannot be imported. Components are ordered by their first appearance in the
    source file, which keeps the numbering stable across runs.

    Correlation surface nodes are ignored when working out adjacency, but are copied into
    every output file, exactly as they appear in the source.

    Args:
        source: Path to the ``.dae`` file to split.
        output_dir: Directory the component files are written to. Created if missing.
        clean: When ``True``, remove pre-existing ``.dae`` files from ``output_dir`` first.

    Returns:
        The written files, in component order.

    Raises:
        TQECError: If the file does not hold exactly one Collada scene node, if the
            expected ``SketchUp`` visual scene node is absent, or if a block node carries
            no readable geometry.

    """
    source_path = Path(source)
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    if clean:
        for stale in output_path.glob("*.dae"):
            stale.unlink()

    mesh = collada.Collada(str(source_path))
    scene_node = _single_scene_node(mesh)
    block_nodes = _block_nodes(scene_node)
    correlation_ids = _correlation_node_ids(scene_node)
    components = _source_ordered_components(
        _geometry_components(block_nodes), block_nodes
    )

    tree = ET.parse(source_path)
    root = tree.getroot()
    namespace = {"c": root.tag.split("}")[0].strip("{")}
    scene_xml = _find_scene_xml(root, namespace)
    original_children = list(scene_xml)

    written: list[Path] = []
    for index, component in enumerate(components, start=1):
        component_root = copy.deepcopy(root)
        component_scene = _find_scene_xml(component_root, namespace)
        for child in list(component_scene):
            component_scene.remove(child)
        for child in original_children:
            # Children without an id are shared scaffolding and belong in every output.
            # Correlation-surface instances belong to no component but are preserved in
            # every output, as documented above.
            child_id = child.attrib.get("id")
            if child_id is None or child_id in component or child_id in correlation_ids:
                component_scene.append(copy.deepcopy(child))

        destination = output_path / f"{batch_member_stem(source_path.stem, index)}.dae"
        ET.ElementTree(component_root).write(
            destination, encoding="utf-8", xml_declaration=True
        )
        written.append(destination)
    return written


def batch_dae_to_bgraph(
    dae_paths: Iterable[str | Path],
    output_dir: str | Path,
    *,
    clean: bool = False,
) -> tuple[list[Path], list[BatchImportFailure]]:
    """Convert a batch of DAE files to BGRAPH files, collecting failures rather than raising.

    Args:
        dae_paths: The ``.dae`` files to convert, typically the return value of
            :py:func:`split_dae_batch`.
        output_dir: Directory the ``.bgraph`` files are written to. Created if missing.
        clean: When ``True``, remove pre-existing ``.bgraph`` files from ``output_dir`` first.

    Returns:
        A ``(written, failures)`` pair. ``written`` holds the successfully converted files
        in input order; ``failures`` describes each input that could not be imported.

    """
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    if clean:
        for stale in output_path.glob("*.bgraph"):
            stale.unlink()

    written: list[Path] = []
    failures: list[BatchImportFailure] = []
    for dae_path in dae_paths:
        path = Path(dae_path)
        destination = output_path / f"{path.stem}.bgraph"
        try:
            dae_to_bgraph(path, destination, graph_name=path.stem)
        # An import failure is reported as data, never raised: one malformed member must
        # not discard the rest of the batch. Only the expected import/conversion errors are
        # caught--a malformed Collada scene (collada.DaeError) or a graph tqec rejects
        # (TQECError). Programming errors, interrupts and filesystem errors propagate so
        # they are not silently reported as a mere batch-member failure.
        except (TQECError, collada.DaeError) as exc:
            failures.append(BatchImportFailure(path, type(exc).__name__, str(exc)))
        else:
            written.append(destination)
    return written, failures


def _single_scene_node(mesh: collada.Collada) -> collada.scene.Node:
    if mesh.scene is None or len(mesh.scene.nodes) != 1:
        raise TQECError(
            "Expected the DAE file to contain exactly one Collada scene node, found "
            f"{0 if mesh.scene is None else len(mesh.scene.nodes)}."
        )
    return mesh.scene.nodes[0]


def _block_nodes(scene_node: collada.scene.Node) -> list[collada.scene.Node]:
    """Return the instantiated block nodes, skipping correlation surfaces."""
    nodes: list[collada.scene.Node] = []
    for node in scene_node.children:
        if not (
            isinstance(node, collada.scene.Node)
            and node.matrix is not None
            and node.children
            and isinstance(node.children[0], collada.scene.NodeNode)
        ):
            continue
        library_node = cast(collada.scene.NodeNode, node.children[0]).node
        if not library_node.name.endswith(_CORRELATION_SUFFIX):
            nodes.append(node)
    return nodes


def _correlation_node_ids(scene_node: collada.scene.Node) -> set[str]:
    """Return the ids of correlation-surface instance nodes.

    Correlation surfaces belong to no structure in particular; they are copied into every
    output file. Their instances are identified by the library node they reference, whose
    name ends with :py:data:`~tqec.interop.collada.read_write._CORRELATION_SUFFIX`.
    """
    ids: set[str] = set()
    for node in scene_node.children:
        if not (
            isinstance(node, collada.scene.Node)
            and node.matrix is not None
            and node.children
            and isinstance(node.children[0], collada.scene.NodeNode)
        ):
            continue
        library_node = cast(collada.scene.NodeNode, node.children[0]).node
        if library_node.name.endswith(_CORRELATION_SUFFIX) and node.id is not None:
            ids.add(node.id)
    return ids


def _geometry_components(nodes: list[collada.scene.Node]) -> list[set[str]]:
    """Group block nodes into connected components by touching world-space bounding boxes."""
    bounds = [_world_bounds(node) for node in nodes]
    adjacency: list[set[int]] = [set() for _ in nodes]
    for i, box in enumerate(bounds):
        for j in range(i + 1, len(bounds)):
            if _touches(box, bounds[j]):
                adjacency[i].add(j)
                adjacency[j].add(i)

    components: list[set[str]] = []
    unseen = set(range(len(nodes)))
    while unseen:
        start = min(unseen)
        unseen.remove(start)
        component = {nodes[start].id}
        queue: deque[int] = deque([start])
        while queue:
            index = queue.popleft()
            for other in sorted(adjacency[index]):
                if other in unseen:
                    unseen.remove(other)
                    component.add(nodes[other].id)
                    queue.append(other)
        components.append(component)
    return components


def _source_ordered_components(
    components: list[set[str]], nodes: list[collada.scene.Node]
) -> list[set[str]]:
    """Order components by the first node of each, as they appear in the source file."""
    node_order = {node.id: index for index, node in enumerate(nodes)}
    return sorted(
        components,
        key=lambda component: min(node_order[node_id] for node_id in component),
    )


def _collect_world_points(
    obj: object,
    transform: npt.NDArray[np.float64],
    points: list[npt.NDArray[np.float64]],
) -> None:
    """Gather world-space geometry vertices under a scene-graph object.

    A block node's geometry is not always a direct child of the referenced library node:
    ports and other decorations nest it one or more :py:class:`~collada.scene.NodeNode`
    levels deeper, each level potentially carrying its own transform. This walks the whole
    subtree, composing the accumulated 4x4 transform at every level, so that geometry at
    any depth is placed in world space.

    Args:
        obj: The scene-graph object to descend into. A
            :py:class:`~collada.scene.NodeNode` is followed into the library node it
            references; a :py:class:`~collada.scene.Node` composes its own ``matrix`` (when
            present) and recurses into its children; a
            :py:class:`~collada.scene.GeometryNode` contributes its transformed vertices.
        transform: The accumulated world transform of ``obj``'s parent.
        points: Accumulator the world-space vertex arrays are appended to.

    """
    if isinstance(obj, collada.scene.NodeNode):
        _collect_world_points(obj.node, transform, points)
        return
    if isinstance(obj, collada.scene.Node):
        matrix = obj.matrix
        node_transform = transform if matrix is None else transform @ matrix
        for child in obj.children:
            _collect_world_points(child, node_transform, points)
        return
    geometry = getattr(obj, "geometry", None)
    if geometry is None:
        return
    for primitive in geometry.primitives:
        vertices = getattr(primitive, "vertex", None)
        if vertices is None:
            continue
        vertices = np.asarray(vertices, dtype=np.float64)
        homogeneous = np.hstack([vertices, np.ones((len(vertices), 1))])
        points.append((transform @ homogeneous.T).T[:, :3])


def _world_bounds(
    node: collada.scene.Node,
) -> tuple[npt.NDArray[np.float64], npt.NDArray[np.float64]]:
    """Return the axis-aligned world-space bounding box of a block node's geometry.

    Geometry is collected recursively from the whole subtree under ``node`` so that
    vertices nested inside decoration sub-nodes (for example a ``port``) are found and
    placed in world space, not only geometry attached directly to the referenced library
    node.
    """
    points: list[npt.NDArray[np.float64]] = []
    _collect_world_points(node, np.identity(4, dtype=np.float64), points)
    if not points:
        raise TQECError(f"Could not read geometry vertices for DAE node {node.id}.")
    stacked = np.vstack(points)
    return stacked.min(axis=0), stacked.max(axis=0)


def _touches(
    a: tuple[npt.NDArray[np.float64], npt.NDArray[np.float64]],
    b: tuple[npt.NDArray[np.float64], npt.NDArray[np.float64]],
) -> bool:
    return bool(
        np.all(a[1] + _ADJACENCY_TOLERANCE >= b[0])
        and np.all(b[1] + _ADJACENCY_TOLERANCE >= a[0])
    )


def _find_scene_xml(root: ET.Element, namespace: dict[str, str]) -> ET.Element:
    scene = root.find(
        ".//c:library_visual_scenes/c:visual_scene/c:node[@name='SketchUp']", namespace
    )
    if scene is None:
        raise TQECError(
            "Could not find the 'SketchUp' visual scene node in the DAE file. Only files "
            "exported with the TQEC SketchUp template can be split into batches."
        )
    return scene
