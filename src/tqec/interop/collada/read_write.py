"""Read and write block graphs to and from Collada DAE files."""

from __future__ import annotations

import pathlib
from dataclasses import dataclass
from typing import BinaryIO, Iterable, cast

import collada
import collada.source
import numpy as np
import numpy.typing as npt

from tqec.computation.block_graph import BlockGraph, BlockKind, block_kind_from_str
from tqec.computation.cube import CubeKind, Port, YHalfCube
from tqec.computation.pipe import PipeKind
from tqec.utils.enums import Basis
from tqec.utils.exceptions import TQECException
from tqec.interop.collada._geometry import (
    BlockGeometries,
    Face,
    get_correlation_surface_geometry,
)
from tqec.interop.color import TQECColor
from tqec.computation.correlation import CorrelationSurface
from tqec.utils.position import FloatPosition3D, Position3D, SignedDirection3D
from tqec.utils.rotations import (
    calc_rotation_angles,
    get_axes_directions,
    rotate_block_kind_by_matrix,
)
from tqec.utils.scale import round_or_fail

_ASSET_AUTHOR = "TQEC Community"
_ASSET_AUTHORING_TOOL_TQEC = "https://github.com/tqec/tqec"
_ASSET_UNIT_NAME = "inch"
_ASSET_UNIT_METER = 0.02539999969303608

_MATERIAL_SYMBOL = "MaterialSymbol"
_CORRELATION_SUFFIX = "_CORRELATION"


def read_block_graph_from_dae_file(
    filepath: str | pathlib.Path,
    graph_name: str = "",
) -> BlockGraph:
    """Read a Collada DAE file and construct a
    :py:class:`~tqec.computation.block_graph.BlockGraph` from it.

    Args:
        filepath: The input dae file path.
        graph_name: The name of the block graph. Default is an empty string.

    Returns:
        The constructed :py:class:`~tqec.computation.block_graph.BlockGraph` object.

    Raises:
        TQECException: If the COLLADA model cannot be parsed and converted to a block graph.
    """

    # Bring the mesh in
    mesh = collada.Collada(str(filepath))

    # Check some invariants about the DAE file
    if mesh.scene is None:
        raise TQECException("No scene found in the DAE file.")
    scene: collada.scene.Scene = mesh.scene

    if not (len(scene.nodes) == 1 and scene.nodes[0].name == "SketchUp"):
        raise TQECException(
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

            # Rotation health checks
            # - If node's matrix NOT rotated: proceed automatically
            # - If node's matrix YES rotated: check closer & make necessary adjustments
            if not np.allclose(transformation.rotation, np.eye(3), atol=1e-9):
                # Calculate rotation
                rotation_angles = calc_rotation_angles(transformation.rotation)

                # Reject invalid rotations for all other cubes/pipes:
                if (
                    # Any rotation with angle not an integer multiply of 90 degrees: partially rotated block/pipe
                    any([int(angle) not in [0, 90, 180] for angle in rotation_angles])
                    # At least 1 * 180-deg or 2 * 90-deg rotation to avoid dimensional collapse
                    # (A single 90-deg rotation would put the rotated vector on the plane made by the other two axes)
                    or sum([angle for angle in rotation_angles]) < 180
                ):
                    raise TQECException(
                        f"There is an invalid rotation for {kind} block at position {translation}."
                    )

                # Rotate node name
                # Calculate rotated kind and directions for all axes in case it is needed
                kind = rotate_block_kind_by_matrix(kind, transformation.rotation)

                # Shift nodes slightly according to rotation
                translation = FloatPosition3D(
                    *transformation.translation
                    + transformation.rotation.dot(transformation.scale)
                )

            # Adjust hadamards if pipe direction is negative
            if isinstance(kind, PipeKind):
                if axes_directions[str(kind.direction)] == -1 and "H" in str(kind):
                    hdm_equivalences = {"ZXOH": "XZOH", "XOZH": "ZOXH", "OXZH": "OZXH"}
                    if str(kind) in hdm_equivalences.keys():
                        kind = block_kind_from_str(hdm_equivalences[str(kind)])
                    else:
                        inv_equivalences = {
                            value: key for key, value in hdm_equivalences.items()
                        }
                        kind = block_kind_from_str(inv_equivalences[str(kind)])

            # Direction, scaling and checks for pipes
            if isinstance(kind, PipeKind):
                # Get direction and scale of pipe
                pipe_direction = kind.direction
                scale = transformation.scale[pipe_direction.value]
                # Checks
                if pipe_length is None:
                    pipe_length = scale * 2.0
                elif not np.isclose(pipe_length, scale * 2.0, atol=1e-9):
                    raise TQECException("All pipes must have the same length.")
                expected_scale = np.ones(3)
                expected_scale[pipe_direction.value] = scale
                if not np.allclose(transformation.scale, expected_scale, atol=1e-9):
                    raise TQECException(
                        f"Only the dimension along the pipe can be scaled, which is not the case at {translation}."
                    )
                # Append
                parsed_pipes.append((translation, kind, axes_directions))

            else:
                # Checks
                if not np.allclose(transformation.scale, np.ones(3), atol=1e-9):
                    raise TQECException(
                        f"Cube at {translation} has a non-identity scale."
                    )
                # Append
                parsed_cubes.append((translation, kind, axes_directions))

    pipe_length = 2.0 if pipe_length is None else pipe_length

    def int_position_before_scale(pos: FloatPosition3D) -> Position3D:
        return Position3D(
            x=round_or_fail(pos.x / (1 + pipe_length), atol=0.35),
            y=round_or_fail(pos.y / (1 + pipe_length), atol=0.35),
            z=round_or_fail(pos.z / (1 + pipe_length), atol=0.35),
        )

    def offset_y_cube_position(pos: FloatPosition3D) -> FloatPosition3D:
        if np.isclose(pos.z - 0.5, np.floor(pos.z), atol=1e-9):
            pos = pos.shift_by(dz=-0.5)
        return FloatPosition3D(pos.x, pos.y, pos.z / (1 + pipe_length))

    # Construct graph
    # Create graph
    graph = BlockGraph(graph_name)

    # Add cubes
    for pos, cube_kind, axes_directions in parsed_cubes:
        if isinstance(cube_kind, YHalfCube):
            pos = offset_y_cube_position(pos)
        graph.add_cube(int_position_before_scale(pos), cube_kind)
    port_index = 0

    # Add pipes
    for pos, pipe_kind, axes_directions in parsed_pipes:
        # Draw pipes in +1/-1 direction using position, kind of pipe, and directional pointers from previous operations
        directional_multiplier = axes_directions[str(pipe_kind.direction)]
        head_pos = int_position_before_scale(
            pos.shift_in_direction(pipe_kind.direction, -1 * directional_multiplier)
        )
        tail_pos = head_pos.shift_in_direction(
            pipe_kind.direction, 1 * directional_multiplier
        )

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
    pop_faces_at_direction: SignedDirection3D | str | None = None,
    show_correlation_surface: CorrelationSurface | None = None,
) -> None:
    """Write a :py:class:`~tqec.computation.block_graph.BlockGraph` to a
    Collada DAE file.

    Args:
        block_graph: The block graph to write to the DAE file.
        file: The output file path or file-like object that supports binary write.
        pipe_length: The length of the pipes in the COLLADA model. Default is 2.0.
        pop_faces_at_direction: Remove the faces at the given direction for all the blocks.
            This is useful for visualizing the internal structure of the blocks. Default is None.
        show_correlation_surface: The :py:class:`~tqec.computation.correlation.CorrelationSurface` to show in the block graph. Default is None.
    """
    if isinstance(pop_faces_at_direction, str):
        pop_faces_at_direction = SignedDirection3D.from_string(pop_faces_at_direction)
    base = _BaseColladaData(pop_faces_at_direction)

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
        pop_faces_at_directions = []
        for pipe in block_graph.pipes_at(cube.position):
            pop_faces_at_directions.append(
                SignedDirection3D(pipe.direction, cube == pipe.u)
            )
        base.add_block_instance(matrix, cube.kind, pop_faces_at_directions)
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
        pop_faces_at_direction: SignedDirection3D | None = None,
    ) -> None:
        """The base model template including the definition of all the library
        nodes and the necessary material, geometry definitions."""
        self.mesh = collada.Collada()
        self.geometries = BlockGeometries()

        self.materials: dict[TQECColor, collada.material.Material] = {}
        self.geometry_nodes: dict[Face, collada.scene.GeometryNode] = {}
        self.root_node = collada.scene.Node("SketchUp", name="SketchUp")
        self.block_library: dict[_BlockLibraryKey, collada.scene.Node] = {}
        self.surface_library: dict[Basis, collada.scene.Node] = {}
        self._pop_faces_at_direction: frozenset[SignedDirection3D] = (
            frozenset({pop_faces_at_direction})
            if pop_faces_at_direction
            else frozenset()
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

        geom = collada.geometry.Geometry(
            self.mesh, id_str, id_str, [positions, normals]
        )
        input_list = collada.source.InputList()
        input_list.addInput(0, "VERTEX", "#" + positions.id)
        input_list.addInput(1, "NORMAL", "#" + normals.id)
        triset = geom.createTriangleSet(
            Face.get_triangle_indices(), input_list, _MATERIAL_SYMBOL
        )
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
        pop_faces_at_directions = (
            frozenset(pop_faces_at_directions) | self._pop_faces_at_direction
        )
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
        node = collada.scene.Node(
            surface.color.value, [geometry_node], name=surface.color.value
        )
        self.mesh.nodes.append(node)
        self.surface_library[basis] = node

    def add_correlation_surface(
        self,
        block_graph: BlockGraph,
        correlation_surface: CorrelationSurface,
        pipe_length: float = 2.0,
    ) -> None:
        from tqec.interop.collada._correlation import (
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
                    collada.scene.MatrixTransform(
                        transformation.to_4d_affine_matrix().flatten()
                    )
                ],
            )
            point_to_node = self.surface_library[basis]
            instance_node = collada.scene.NodeNode(point_to_node)
            child_node.children.append(instance_node)
            self.root_node.children.append(child_node)
            self._num_instances += 1


@dataclass(frozen=True)
class _Transformation:
    """Transformation data class to store the translation, scale, rotation, and
    the composed affine matrix.

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
