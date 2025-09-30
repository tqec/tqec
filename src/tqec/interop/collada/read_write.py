"""Read and write block graphs to and from Collada DAE files."""

from __future__ import annotations

import json
import pathlib
from collections.abc import Iterable
from dataclasses import dataclass
from typing import BinaryIO, cast

import collada
import collada.source
import numpy as np
import numpy.typing as npt

from tqec.computation.block_graph import BlockGraph, BlockKind, block_kind_from_str
from tqec.computation.correlation import CorrelationSurface
from tqec.computation.cube import CubeKind, Port, YHalfCube
from tqec.computation.pipe import PipeKind
from tqec.interop.collada._geometry import BlockGeometries, Face, get_correlation_surface_geometry
from tqec.interop.color import TQECColor
from tqec.utils.enums import Basis
from tqec.utils.exceptions import TQECError
from tqec.utils.position import FloatPosition3D, Position3D, SignedDirection3D
from tqec.utils.rotations import adjust_hadamards_direction, get_axes_directions, rotate_on_import
from tqec.utils.scale import round_or_fail

_ASSET_AUTHOR = "TQEC Community"
_ASSET_AUTHORING_TOOL_TQEC = "https://github.com/tqec/tqec"
_ASSET_UNIT_NAME = "inch"
_ASSET_UNIT_METER = 0.02539999969303608

_MATERIAL_SYMBOL = "MaterialSymbol"
_CORRELATION_SUFFIX = "_CORRELATION"


# SHARED FUNCTIONS
def _int_position_before_scale(pos: FloatPosition3D, pipe_length: float) -> Position3D:
    return Position3D(
        x=round_or_fail(pos.x / (1 + pipe_length), atol=0.35),
        y=round_or_fail(pos.y / (1 + pipe_length), atol=0.35),
        z=round_or_fail(pos.z / (1 + pipe_length), atol=0.35),
    )


def _offset_y_cube_position(pos: FloatPosition3D, pipe_length: float) -> FloatPosition3D:
    if np.isclose(pos.z - 0.5, np.floor(pos.z), atol=1e-9):
        pos = pos.shift_by(dz=-0.5)
    return FloatPosition3D(pos.x, pos.y, pos.z / (1 + pipe_length))


# DAE EXPORTER/IMPORTER
def read_block_graph_from_dae_file(
    filepath: str | pathlib.Path,
    graph_name: str = "",
) -> BlockGraph:
    """Read a Collada DAE file and construct a :class:`.BlockGraph` from it.

    Args:
        filepath: The input dae file path.
        graph_name: The name of the block graph. Default is an empty string.
        fix_shadowed_faces: Whether to fix the shadowed faces in the block graph. See
            :py:meth:`.BlockGraph.fix_shadowed_faces` for more details. Default is True.

    Returns:
        The constructed :py:class:`~tqec.computation.block_graph.BlockGraph` object.

    Raises:
        TQECError: If the COLLADA model cannot be parsed and converted to a block graph.

    """
    # Bring the mesh in
    mesh = collada.Collada(str(filepath))

    # Check some invariants about the DAE file
    if mesh.scene is None:
        raise TQECError("No scene found in the DAE file.")
    scene: collada.scene.Scene = mesh.scene

    if not (len(scene.nodes) == 1 and scene.nodes[0].name == "SketchUp"):
        raise TQECError(
            "The <visual_scene> node must have a single child node with the name 'SketchUp'."
        )

    sketchup_node: collada.scene.Node = scene.nodes[0]
    pipe_length: float | None = None
    parsed_cubes: list[tuple[FloatPosition3D, CubeKind, dict[str, int]]] = []
    parsed_pipes: list[tuple[FloatPosition3D, PipeKind, dict[str, int]]] = []

    # Handle nodes in scene/sketchup_node
    for node in sketchup_node.children:
        # If everything needed is present
        if (
            isinstance(node, collada.scene.Node)
            and node.matrix is not None
            and node.children is not None
            and len(node.children) == 1
            and isinstance(node.children[0], collada.scene.NodeNode)
        ):
            # Extract key info from collada scene
            instance = cast(collada.scene.NodeNode, node.children[0])
            library_node: collada.scene.Node = instance.node
            name: str = library_node.name

            # Skip the correlation surface nodes
            if name.endswith(_CORRELATION_SUFFIX):
                continue

            # Extract transformation and translation matrix
            transformation = _Transformation.from_4d_affine_matrix(node.matrix)
            translation = FloatPosition3D(*transformation.translation)
            axes_directions = get_axes_directions(transformation.rotation)
            kind = block_kind_from_str(name)

            # Rotations step 1. Skip if node's matrix not rotated
            # - If node's matrix YES rotated: check closer & make necessary adjustments
            if not np.allclose(transformation.rotation, np.eye(3), atol=1e-9):
                translation, kind = rotate_on_import(
                    transformation.rotation,
                    transformation.translation,
                    transformation.scale,
                    kind,
                )

            # Rotations step 2. Skip if hadamard points in positive direction
            if isinstance(kind, PipeKind):
                if axes_directions[str(kind.direction)] == -1 and "H" in str(kind):
                    kind = adjust_hadamards_direction(kind)

            # Direction, scaling and checks for pipes
            if isinstance(kind, PipeKind):
                # Get direction and scale of pipe
                pipe_direction = kind.direction
                scale = transformation.scale[pipe_direction.value]
                # Checks
                if pipe_length is None:
                    pipe_length = scale * 2.0
                elif not np.isclose(pipe_length, scale * 2.0, atol=1e-9):
                    raise TQECError("All pipes must have the same length.")
                expected_scale = np.ones(3)
                expected_scale[pipe_direction.value] = scale
                if not np.allclose(transformation.scale, expected_scale, atol=1e-9):
                    raise TQECError(
                        "Only the dimension along the pipe can be scaled, "
                        f"which is not the case at {translation}."
                    )
                # Append
                parsed_pipes.append((translation, kind, axes_directions))

            else:
                # Checks
                if not np.allclose(transformation.scale, np.ones(3), atol=1e-9):
                    raise TQECError(f"Cube at {translation} has a non-identity scale.")
                # Append
                parsed_cubes.append((translation, kind, axes_directions))

    pipe_length = 2.0 if pipe_length is None else pipe_length

    # Construct graph
    # Create graph
    graph = BlockGraph(graph_name)

    # Add cubes
    for pos, cube_kind, axes_directions in parsed_cubes:
        if isinstance(cube_kind, YHalfCube):
            graph.add_cube(
                _int_position_before_scale(_offset_y_cube_position(pos, pipe_length), pipe_length),
                cube_kind,
            )
        else:
            graph.add_cube(_int_position_before_scale(pos, pipe_length), cube_kind)
    port_index = 0

    # Add pipes
    for pos, pipe_kind, axes_directions in parsed_pipes:
        # Draw pipes in +1/-1 direction using position, kind of pipe, and directional pointers
        # from previous operations
        directional_multiplier = axes_directions[str(pipe_kind.direction)]
        head_pos = _int_position_before_scale(
            pos.shift_in_direction(pipe_kind.direction, -1 * directional_multiplier),
            pipe_length,
        )
        tail_pos = head_pos.shift_in_direction(pipe_kind.direction, 1 * directional_multiplier)

        # Add pipe
        if head_pos not in graph:
            graph.add_cube(head_pos, Port(), label=f"Port{port_index}")
            port_index += 1
        if tail_pos not in graph:
            graph.add_cube(tail_pos, Port(), label=f"Port{port_index}")
            port_index += 1
        graph.add_pipe(head_pos, tail_pos, pipe_kind)

    return graph


def write_block_graph_to_dae_file(
    block_graph: BlockGraph,
    file_like: str | pathlib.Path | BinaryIO,
    pipe_length: float = 2.0,
    pop_faces_at_directions: Iterable[SignedDirection3D | str] = (),
    show_correlation_surface: CorrelationSurface | None = None,
) -> None:
    """Write a :py:class:`~tqec.computation.block_graph.BlockGraph` to a Collada DAE file.

    Args:
        block_graph: The block graph to write to the DAE file.
        file_like: The output file path or file-like object that supports binary write.
        pipe_length: The length of the pipes in the COLLADA model. Default is 2.0.
        pop_faces_at_directions: Remove the faces at the given directions for all the blocks.
            This is useful for visualizing the internal structure of the blocks. Default is None.
        show_correlation_surface: The :py:class:`~tqec.computation.correlation.CorrelationSurface`
            to show in the block graph. Default is None.

    """
    directions: list[SignedDirection3D] = []
    for direction in pop_faces_at_directions:
        if isinstance(direction, str):
            directions.append(SignedDirection3D.from_string(direction))
        else:
            directions.append(direction)
    base = _BaseColladaData(directions)

    def scale_position(pos: Position3D) -> FloatPosition3D:
        return FloatPosition3D(*(p * (1 + pipe_length) for p in pos.as_tuple()))

    for cube in block_graph.cubes:
        if cube.is_port:
            continue

        scaled_position = scale_position(cube.position)
        if cube.is_y_cube and block_graph.has_pipe_between(
            cube.position, cube.position.shift_by(dz=1)
        ):
            scaled_position = scaled_position.shift_by(dz=0.5)

        matrix = np.eye(4, dtype=np.float32)
        matrix[:3, 3] = scaled_position.as_array()
        pop_directions = [
            SignedDirection3D(pipe.direction, cube == pipe.u)
            for pipe in block_graph.pipes_at(cube.position)
        ]
        base.add_block_instance(matrix, cube.kind, pop_directions)

    for pipe in block_graph.pipes:
        head_pos = scale_position(pipe.u.position)
        pipe_pos = head_pos.shift_in_direction(pipe.direction, 1.0)

        matrix = np.eye(4, dtype=np.float32)
        matrix[:3, 3] = pipe_pos.as_array()
        scales = [1.0, 1.0, 1.0]

        # We divide the scaling by 2.0 because the pipe's default length is 2.0.
        scales[pipe.direction.value] = pipe_length / 2.0
        matrix[:3, :3] = np.diag(scales)

        base.add_block_instance(matrix, pipe.kind)

    if show_correlation_surface is not None:
        base.add_correlation_surface(block_graph, show_correlation_surface, pipe_length)

    base.mesh.write(file_like)


# JSON IMPORTER
# Why no JSON exporter? No need. It can be done with blockgraph.to_dict
def read_block_graph_from_json(
    filepath: str | pathlib.Path,
    graph_name: str = "",
) -> BlockGraph:
    """Read a Collada JSON file and construct a :py:class:`.BlockGraph` from it.

    Args:
        filepath: The input dae file path.
        graph_name: The name of the block graph. Default is an empty string.

    Returns:
        The constructed :py:class:`.BlockGraph` object.

    Raises:
        TQECError: If the JSON file cannot be parsed and converted to a block graph.

    """
    # Read JSON file
    try:
        with open(filepath) as f:
            data = json.load(f)
    except Exception:
        raise TQECError("JSON file not found.")

    # Check JSON file has cubes and pipes
    try:
        cubes = data["cubes"]
        pipes = data["pipes"]
        if not len(cubes) > 0 or not len(pipes) > 0:
            raise TQECError("No cubes or pipes found.")
    except Exception:
        raise TQECError("JSON file is not appropriately formatted.")

    # Initialise list of cubes and pipes
    parsed_cubes: list[tuple[FloatPosition3D, CubeKind, dict[str, int]]] = []
    parsed_pipes: list[tuple[FloatPosition3D, FloatPosition3D, PipeKind, dict[str, int]]] = []

    # Get cubes data
    for cube in data["cubes"]:
        # Skip any "PORT" kind (cannot currently import them: error @ `block_kind_from_str` )
        if cube["kind"] == "PORT":
            continue

        # Enforce integers for position and transformation
        if not all([isinstance(i, int) for i in cube["position"]]):
            raise TQECError(
                f"Incorrect positioning for cube at {cube['position']}. All positional "
                "information must be composed of integer values."
            )

        if not all([isinstance(i, int) for row in cube["transform"] for i in row]):
            raise TQECError(
                f"Incorrect transformation matrix for cube at {cube['position']}. All "
                "elements in transformation matrix need to be integers."
            )

        # Get key spatial info
        translation = FloatPosition3D(*cube["position"])
        axes_directions = get_axes_directions(cube["transform"])
        kind = block_kind_from_str(cube["kind"])

        # Rotations step 1. Skip if node's matrix not rotated
        # - If node's matrix YES rotated: check closer & make necessary adjustments
        if not np.allclose(cube["transform"], np.eye(3), atol=1e-9):
            translation, kind = rotate_on_import(
                cube["transform"],
                cube["position"],
                np.array([1.0, 1.0, 1.0]),
                kind,
            )

        # Append to parsed cubes
        if isinstance(kind, CubeKind):
            parsed_cubes.append((translation, kind, axes_directions))

    # Get pipes data
    for pipe in data["pipes"]:
        # Enforce integers for position and transformation
        for pos in [pipe["u"], pipe["v"]]:
            if not all([isinstance(i, int) for i in pos]):
                raise TQECError(
                    f"Incorrect positioning for pipe at ({pipe['u']}). All positional "
                    "information must be composed of integer values."
                )

        if not all([isinstance(i, int) for row in pipe["transform"] for i in row]):
            raise TQECError(
                f"Incorrect transformation for pipe at ({pipe['u']}). All elements in "
                "transformation matrix need to be integers."
            )

        # Get key spatial info
        u_pos = FloatPosition3D(*pipe["u"])  # Equivalent to "translation" in cubes
        v_pos = FloatPosition3D(*pipe["v"])
        axes_directions = get_axes_directions(pipe["transform"])
        kind = block_kind_from_str(pipe["kind"])

        # Rotations step 1. Skip if node's matrix not rotated
        # - If node's matrix YES rotated: check closer & make necessary adjustments
        if not np.allclose(pipe["transform"], np.eye(3), atol=1e-9):
            u_pos, kind = rotate_on_import(
                pipe["transform"],
                pipe["position"],
                np.array([1.0, 1.0, 1.0]),
                kind,
            )

        # Rotations step 2. Skip if hadamard points in positive direction
        # Check kind is pipe
        if isinstance(kind, PipeKind):
            if axes_directions[str(kind.direction)] == -1 and "H" in str(kind):
                kind = adjust_hadamards_direction(kind)

        # Recheck kind since it might have been regenerated
        if isinstance(kind, PipeKind):
            parsed_pipes.append((u_pos, v_pos, kind, axes_directions))

    # Construct graph
    # Create graph
    graph = BlockGraph(graph_name)

    # Add cubes
    for pos, cube_kind, axes_directions in parsed_cubes:
        if isinstance(cube_kind, YHalfCube):
            graph.add_cube(
                _int_position_before_scale(_offset_y_cube_position(pos, 0.0), 0.0), cube_kind
            )
        else:
            graph.add_cube(_int_position_before_scale(pos, 0.0), cube_kind)
    port_index = 0

    # Add pipes
    for u_pos, v_pos, pipe_kind, axes_directions in parsed_pipes:
        # Write head_pos and tail_pos as Position3D
        head_pos = _int_position_before_scale(u_pos, 0)
        tail_pos = _int_position_before_scale(v_pos, 0)

        # Add pipe
        if head_pos not in graph:
            graph.add_cube(head_pos, Port(), label=f"Port{port_index}")
            port_index += 1
        if tail_pos not in graph:
            graph.add_cube(tail_pos, Port(), label=f"Port{port_index}")
            port_index += 1
        graph.add_pipe(head_pos, tail_pos, pipe_kind)

    return graph


# CLASSES
@dataclass(frozen=True)
class _BlockLibraryKey:
    """The key to access the library node in the Collada DAE file."""

    kind: BlockKind
    pop_faces_at_directions: frozenset[SignedDirection3D] = frozenset()

    def __str__(self) -> str:
        string = f"{self.kind}"
        if self.pop_faces_at_directions:
            string += "-without-"
            string += "-".join(str(d) for d in self.pop_faces_at_directions)
        return string


class _BaseColladaData:
    def __init__(
        self,
        pop_faces_at_directions: Iterable[SignedDirection3D] = (),
    ) -> None:
        """Encode the base model template.

        This class includes the definition of all the library nodes and the necessary material,
        geometry definitions.
        """
        self.mesh = collada.Collada()
        self.geometries = BlockGeometries()

        self.materials: dict[TQECColor, collada.material.Material] = {}
        self.geometry_nodes: dict[Face, collada.scene.GeometryNode] = {}
        self.root_node = collada.scene.Node("SketchUp", name="SketchUp")
        self.block_library: dict[_BlockLibraryKey, collada.scene.Node] = {}
        self.surface_library: dict[Basis, collada.scene.Node] = {}
        self._pop_faces_at_directions: frozenset[SignedDirection3D] = frozenset(
            pop_faces_at_directions
        )
        self._num_instances: int = 0

        self._create_scene()
        self._add_asset_info()
        self._add_materials()

    def _create_scene(self) -> None:
        scene = collada.scene.Scene("scene", [self.root_node])
        self.mesh.scenes.append(scene)
        self.mesh.scene = scene

    def _add_asset_info(self) -> None:
        if self.mesh.assetInfo is None:
            return
        self.mesh.assetInfo.contributors.append(
            collada.asset.Contributor(
                author=_ASSET_AUTHOR, authoring_tool=_ASSET_AUTHORING_TOOL_TQEC
            ),
        )
        self.mesh.assetInfo.unitmeter = _ASSET_UNIT_METER
        self.mesh.assetInfo.unitname = _ASSET_UNIT_NAME
        self.mesh.assetInfo.upaxis = collada.asset.UP_AXIS.Z_UP

    def _add_materials(self) -> None:
        """Add all the materials for different faces."""
        for face_color in TQECColor:
            rgba = face_color.rgba.as_floats()
            effect = collada.material.Effect(
                f"{face_color.value}_effect",
                [],
                "lambert",
                diffuse=rgba,
                emission=None,
                specular=None,
                transparent=rgba,
                transparency=rgba[3],
                ambient=None,
                reflective=None,
                double_sided=True,
            )
            self.mesh.effects.append(effect)

            material = collada.material.Material(
                f"{face_color.value}_material", f"{face_color.value}_material", effect
            )
            self.mesh.materials.append(material)
            self.materials[face_color] = material

    def _add_face_geometry_node(self, face: Face) -> collada.scene.GeometryNode:
        if face in self.geometry_nodes:
            return self.geometry_nodes[face]
        # Create geometry
        id_str = f"FaceID{len(self.geometry_nodes)}"
        positions = collada.source.FloatSource(
            id_str + "_positions", face.get_vertices(), ("X", "Y", "Z")
        )
        normals = collada.source.FloatSource(
            id_str + "_normals", face.get_normal_vectors(), ("X", "Y", "Z")
        )

        geom = collada.geometry.Geometry(self.mesh, id_str, id_str, [positions, normals])
        input_list = collada.source.InputList()
        input_list.addInput(0, "VERTEX", "#" + positions.id)
        input_list.addInput(1, "NORMAL", "#" + normals.id)
        triset = geom.createTriangleSet(Face.get_triangle_indices(), input_list, _MATERIAL_SYMBOL)
        geom.primitives.append(triset)
        self.mesh.geometries.append(geom)
        # Create geometry node
        inputs = [("UVSET0", "TEXCOORD", "0")]
        material = self.materials[face.color]
        geom_node = collada.scene.GeometryNode(
            geom, [collada.scene.MaterialNode(_MATERIAL_SYMBOL, material, inputs)]
        )
        self.geometry_nodes[face] = geom_node
        return geom_node

    def _add_block_library_node(
        self,
        block_kind: BlockKind,
        pop_faces_at_directions: Iterable[SignedDirection3D] = (),
    ) -> _BlockLibraryKey:
        pop_faces_at_directions = frozenset(pop_faces_at_directions) | self._pop_faces_at_directions
        key = _BlockLibraryKey(block_kind, pop_faces_at_directions)
        if key in self.block_library:
            return key
        faces = self.geometries.get_geometry(block_kind, pop_faces_at_directions)
        children = [self._add_face_geometry_node(face) for face in faces]
        key_str = str(key)
        node = collada.scene.Node(key_str, children, name=str(key.kind))
        self.mesh.nodes.append(node)
        self.block_library[key] = node
        return key

    def add_block_instance(
        self,
        transform_matrix: npt.NDArray[np.float32],
        block_kind: BlockKind,
        pop_faces_at_directions: Iterable[SignedDirection3D] = (),
    ) -> None:
        """Add an instance node to the root node."""
        key = self._add_block_library_node(block_kind, pop_faces_at_directions)
        child_node = collada.scene.Node(
            f"ID{self._num_instances}",
            name=f"instance_{self._num_instances}",
            transforms=[collada.scene.MatrixTransform(transform_matrix.flatten())],
        )
        point_to_node = self.block_library[key]
        instance_node = collada.scene.NodeNode(point_to_node)
        child_node.children.append(instance_node)
        self.root_node.children.append(child_node)
        self._num_instances += 1

    def _add_surface_library_node(self, basis: Basis) -> None:
        if basis in self.surface_library:
            return
        surface = get_correlation_surface_geometry(basis)
        geometry_node = self._add_face_geometry_node(surface)
        node = collada.scene.Node(surface.color.value, [geometry_node], name=surface.color.value)
        self.mesh.nodes.append(node)
        self.surface_library[basis] = node

    def add_correlation_surface(
        self,
        block_graph: BlockGraph,
        correlation_surface: CorrelationSurface,
        pipe_length: float = 2.0,
    ) -> None:
        # Needs to be imported here to avoid a circular import when importing tqec.interop
        from tqec.interop.collada._correlation import (  # noqa: PLC0415
            CorrelationSurfaceTransformationHelper,
        )

        helper = CorrelationSurfaceTransformationHelper(block_graph, pipe_length)

        for (
            basis,
            transformation,
        ) in helper.get_transformations_for_correlation_surface(correlation_surface):
            self._add_surface_library_node(basis)
            child_node = collada.scene.Node(
                f"ID{self._num_instances}",
                name=f"instance_{self._num_instances}_correlation_surface",
                transforms=[
                    collada.scene.MatrixTransform(transformation.to_4d_affine_matrix().flatten())
                ],
            )
            point_to_node = self.surface_library[basis]
            instance_node = collada.scene.NodeNode(point_to_node)
            child_node.children.append(instance_node)
            self.root_node.children.append(child_node)
            self._num_instances += 1


@dataclass(frozen=True)
class _Transformation:
    """Stores the translation, scale, rotation, and the composed affine matrix.

    For the reference of the transformation matrix, see https://en.wikipedia.org/wiki/Transformation_matrix.

    Attributes:
        translation: The length-3 translation vector.
        scale: The length-3 scaling vector, which is the scaling factor along each axis.
        rotation: The 3x3 rotation matrix.

    """

    translation: npt.NDArray[np.float32]
    scale: npt.NDArray[np.float32]
    rotation: npt.NDArray[np.float32]

    @staticmethod
    def from_4d_affine_matrix(mat: npt.NDArray[np.float32]) -> _Transformation:
        translation = mat[:3, 3]
        scale = np.linalg.norm(mat[:3, :3], axis=1)
        rotation = mat[:3, :3] / scale[None, :]
        return _Transformation(translation, scale, rotation)

    def to_4d_affine_matrix(self) -> npt.NDArray[np.float32]:
        mat = np.eye(4, dtype=np.float32)
        mat[:3, :3] = self.rotation * self.scale[None, :]
        mat[:3, 3] = self.translation
        return mat
