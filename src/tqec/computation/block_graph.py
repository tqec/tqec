"""Block graph representation of a logical computation."""

from __future__ import annotations

import json
import math
import pathlib
from collections.abc import Iterable, Mapping
from copy import deepcopy
from io import BytesIO
from typing import TYPE_CHECKING, Any, cast

import numpy as np
from networkx import Graph, is_connected
from networkx.utils import graphs_equal

from tqec.computation.cube import Cube, CubeKind, Port, YHalfCube, ZXCube, cube_kind_from_string
from tqec.computation.pipe import Pipe, PipeKind
from tqec.utils.enums import Basis
from tqec.utils.exceptions import TQECError
from tqec.utils.position import Direction3D, Position3D, SignedDirection3D

if TYPE_CHECKING:
    from tqec.computation.correlation import CorrelationSurface
    from tqec.computation.open_graph import FilledGraph
    from tqec.interop.collada.html_viewer import _ColladaHTMLViewer
    from tqec.interop.pyzx.positioned import PositionedZX


BlockKind = CubeKind | PipeKind


class BlockGraph:
    _NODE_DATA_KEY: str = "tqec_node_data"
    _EDGE_DATA_KEY: str = "tqec_edge_data"

    def __init__(self, name: str = "") -> None:
        """Block graph representation of a logical computation.

        A block graph consists of building blocks that fully define the boundary
        conditions and topological structures of a logical computation. It corresponds
        to the commonly used 3D spacetime diagram representation of a surface code
        logical computation.

        The graph contains two categories of blocks:

        1. :py:class:`~tqec.computation.cube.Cube`: The fundamental building blocks
        of the computation. A cube represents a block of quantum operations within
        a specific spacetime volume. These operations preserve or manipulate the
        quantum information encoded in the logical qubits. Cubes are represented
        as nodes in the graph.

        2. :py:class:`~tqec.computation.pipe.Pipe`: Connects cubes to form the
        topological structure representing the logical computation. A pipe occupies
        no spacetime volume and only replaces the operations within the cubes it
        connects. Pipes are represented as edges in the graph.

        Args:
            name: user-readable name representing the block-graph. Not used internally, but useful
                to identify :class:`.BlockGraph` instances.

        """
        self._name = name
        self._graph: Graph[Position3D] = Graph()
        self._ports: dict[str, Position3D] = {}

    @property
    def name(self) -> str:
        """Name of the graph."""
        return self._name

    @name.setter
    def name(self, name: str) -> None:
        self._name = name

    @property
    def num_cubes(self) -> int:
        """Number of cubes (nodes) in the graph, including the ports."""
        return self._graph.number_of_nodes()

    @property
    def num_pipes(self) -> int:
        """Number of pipes (edges) in the graph."""
        return self._graph.number_of_edges()

    @property
    def num_ports(self) -> int:
        """Number of ports in the graph."""
        return len([node for node in self.cubes if node.is_port])

    @property
    def num_half_y_cubes(self) -> int:
        """Number of half Y cubes in the graph."""
        return len([node for node in self.cubes if node.is_y_cube])

    @property
    def ordered_ports(self) -> list[str]:
        """Get the labels of the ports in the alphabetical order."""
        return sorted(self._ports.keys())

    @property
    def cubes(self) -> list[Cube]:
        """The list of cubes (nodes) in the graph."""
        return [data[self._NODE_DATA_KEY] for _, data in self._graph.nodes(data=True)]

    @property
    def pipes(self) -> list[Pipe]:
        """The list of pipes (edges) in the graph."""
        return [data[self._EDGE_DATA_KEY] for _, _, data in self._graph.edges(data=True)]

    @property
    def occupied_positions(self) -> list[Position3D]:
        """Get the positions occupied by the cubes in the graph."""
        return list(self._graph.nodes)

    @property
    def is_open(self) -> bool:
        """Whether the graph is an open graph, i.e. the graph has ports."""
        return bool(self._ports)

    @property
    def spacetime_volume(self) -> float:
        """Return the spacetime volume of the computation.

        A port cube and the pipes have no spacetime volume. A half Y cube has a
        spacetime volume of 0.5. Other cubes have a spacetime volume of 1. The
        spacetime volume of the block graph is the sum of the spacetime volumes
        of all the cubes in the graph.

        Returns:
            The spacetime volume of the computation.

        """
        return self.num_cubes - self.num_ports - self.num_half_y_cubes * 0.5

    def bounding_box_size(self) -> tuple[int, int, int]:
        """Return the size of the bounding box of the computation structure.

        Returns:
            A tuple of three integers representing the width along the X, Y, and Z
            directions, respectively.

        """
        positions = self.occupied_positions
        return (
            max(pos.x for pos in positions) - min(pos.x for pos in positions) + 1,
            max(pos.y for pos in positions) - min(pos.y for pos in positions) + 1,
            max(pos.z for pos in positions) - min(pos.z for pos in positions) + 1,
        )

    @property
    def ports(self) -> dict[str, Position3D]:
        """Mapping from port labels to their positions.

        A port is a virtual node with a unique label that represents the input/output of the
        computation. It should be invisible when visualizing the computation model.

        """
        return dict(self._ports)

    def get_degree(self, position: Position3D) -> int:
        """Get the degree of a node in the graph, i.e. the number of edges incident to it."""
        return self._graph.degree(position)  # type: ignore

    @property
    def leaf_cubes(self) -> list[Cube]:
        """Get the leaf cubes of the graph, i.e. the cubes with degree 1."""
        return [node for node in self.cubes if self.get_degree(node.position) == 1]

    def _check_cube_exists(self, position: Position3D) -> None:
        """Check if a cube exists at the given position."""
        if position not in self:
            raise TQECError(f"No cube at position {position}.")

    def _check_pipe_exists(self, pos1: Position3D, pos2: Position3D) -> None:
        """Check if a pipe exists between the given positions."""
        if not self.has_pipe_between(pos1, pos2):
            raise TQECError(f"No pipe between {pos1} and {pos2}.")

    def add_cube(self, position: Position3D, kind: CubeKind | str, label: str = "") -> Position3D:
        """Add a cube to the graph.

        Args:
            position: The position of the cube.
            kind: The kind of the cube. It can be a :py:class:`~tqec.computation.cube.CubeKind`
                instance or a string representation of the cube kind.
            label: The label of the cube. Default is None.

        Returns:
            The position of the cube added to the graph.

        Raises:
            TQECError: If there is already a cube at the same position, or
                if the cube kind is not recognized, or if the cube is a port and
                there is already a port with the same label in the graph.

        """
        if position in self:
            raise TQECError(f"Cube already exists at position {position}.")
        if isinstance(kind, str):
            kind = cube_kind_from_string(kind)
        if kind == Port() and label in self._ports:
            raise TQECError(f"There is already a port with the same label {label} in the graph.")

        self._graph.add_node(position, **{self._NODE_DATA_KEY: Cube(position, kind, label)})
        if kind == Port():
            self._ports[label] = position
        return position

    def add_pipe(
        self, pos1: Position3D, pos2: Position3D, kind: PipeKind | str | None = None
    ) -> None:
        """Add a pipe to the graph.

        .. note::
            The validity of the pipe WILL NOT be checked when adding it to the graph.
            This allows the user to construct the invalid graph and visualize it for whatever
            purpose. To check the validity of the graph, use the
            :py:meth:`~tqec.computation.block_graph.BlockGraph.validate`.

        Args:
            pos1: The position of one end of the pipe.
            pos2: The position of the other end of the pipe.
            kind: The kind of the pipe connecting the cubes. If None, the kind will be
                automatically determined based on the cubes it connects to make the
                boundary conditions consistent. Default is None.

        Raises:
            TQECError: If any of the positions do not have a cube in the graph, or
                if there is already an pipe between the given positions, or
                if the pipe is not compatible with the cubes it connects.

        """
        u, v = self[pos1], self[pos2]
        if self.has_pipe_between(pos1, pos2):
            raise TQECError("There is already a pipe between the given positions in the graph.")
        if kind is None:
            pipe = Pipe.from_cubes(u, v)
        else:
            if isinstance(kind, str):
                kind = PipeKind.from_str(kind)
            pipe = Pipe(u, v, kind)
        self._graph.add_edge(pos1, pos2, **{self._EDGE_DATA_KEY: pipe})

    def remove_cube(self, position: Position3D) -> None:
        """Remove a cube from the graph, as well as the pipes connected to it.

        Args:
            position: The position of the cube to be removed.

        Raises: TQECError: If there is no cube at the given position.

        """
        self._check_cube_exists(position)
        cube = self[position]
        self._graph.remove_node(position)
        if cube.is_port:
            self._ports.pop(cube.label)

    def remove_pipe(self, pos1: Position3D, pos2: Position3D) -> None:
        """Remove a pipe between two positions.

        Args:
            pos1: The position of one end of the pipe.
            pos2: The position of the other end of the pipe.

        Raises:
            TQECError: If there is no pipe between the given positions.

        """
        self._check_pipe_exists(pos1, pos2)
        self._graph.remove_edge(pos1, pos2)

    def has_pipe_between(self, pos1: Position3D, pos2: Position3D) -> bool:
        """Check if there is a pipe between two positions.

        Args:
            pos1: The first endpoint position.
            pos2: The second endpoint position.

        Returns:
            True if there is an pipe between the two positions, False otherwise.

        """
        return self._graph.has_edge(pos1, pos2)

    def get_pipe(self, pos1: Position3D, pos2: Position3D) -> Pipe:
        """Get the pipe by its endpoint positions.

        Args:
            pos1: The first endpoint position.
            pos2: The second endpoint position.

        Returns:
            The pipe between the two positions.

        Raises:
            TQECError: If there is no pipe between the given positions.

        """
        self._check_pipe_exists(pos1, pos2)
        return cast(Pipe, self._graph.edges[pos1, pos2][self._EDGE_DATA_KEY])

    def pipes_at(self, position: Position3D) -> list[Pipe]:
        """Get the pipes incident to a position."""
        if position not in self:
            raise TQECError(f"No cube at position {position}.")
        return [
            cast(Pipe, data[self._EDGE_DATA_KEY])
            for _, _, data in self._graph.edges(position, data=True)
        ]

    def clone(self) -> BlockGraph:
        """Create a data-independent copy of the graph."""
        graph = BlockGraph(self.name + "_clone")
        graph._graph = deepcopy(self._graph)
        graph._ports = dict(self._ports)
        return graph

    def __contains__(self, position: Position3D) -> bool:
        return position in self._graph

    def __getitem__(self, position: Position3D) -> Cube:
        self._check_cube_exists(position)
        return cast(Cube, self._graph.nodes[position][self._NODE_DATA_KEY])

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, BlockGraph):
            return False  # pragma: no cover
        return (
            graphs_equal(self._graph, other._graph)  # type: ignore
            and self._ports == other._ports
        )

    def __hash__(self) -> int:
        return hash(self._name)  # pragma: no cover

    def validate(self) -> None:
        """Check the validity of the block graph to represent a logical computation.

        Refer to the Fig.9 in arXiv:2404.18369. Currently, we ignore the b) and e),
        only check the following conditions:

        - **No fanout:** ports can only have one pipe connected to them.
        - **Time-like Y:** Y Half Cubes can only have time-like pipes connected to them.
        - **No 3D corner:** a cube cannot have pipes in all three directions.
        - **Match color at passthrough:** two pipes in a "pass-through" should have the same
          color orientation.
        - **Match color at turn:** two pipes in a "turn" should have the matching colors on
          faces that are touching.

        Raises:
            TQECError: If the above conditions are not satisfied.

        """
        for cube in self.cubes:
            self._validate_locally_at_cube(cube)

    def _validate_locally_at_cube(self, cube: Cube) -> None:
        """Check the validity of the block structures locally at a cube."""
        pipes = self.pipes_at(cube.position)
        # no fanout at ports
        if cube.is_port:
            if len(pipes) != 1:
                raise TQECError(
                    f"Port at {cube.position} does not have exactly one pipe connected."
                )
            return
        # time-like Y
        if cube.is_y_cube:
            if len(pipes) != 1:
                raise TQECError(
                    f"Y Half Cube at {cube.position} does not have exactly one pipe connected."
                )
            if not pipes[0].direction == Direction3D.Z:
                raise TQECError(f"Y Half Cube at {cube.position} has non-timelike pipes connected.")
            return

        assert isinstance(cube.kind, ZXCube)
        # Check the color matching conditions
        pipes_by_direction: dict[Direction3D, list[Pipe]] = {}
        for pipe in pipes:
            pipes_by_direction.setdefault(pipe.direction, []).append(pipe)
        for direction in Direction3D.all_directions():
            # the pair of faces are shadowed in the direction
            # we do not care about the colors of shadowed faces
            if len(pipes_by_direction.get(direction, [])) == 2:
                continue
            # faces at the same plane should have the same color
            cube_color = cube.kind.get_basis_along(direction)
            for ortho_dir in direction.orthogonal_directions:
                for pipe in pipes_by_direction.get(ortho_dir, []):
                    pipe_color = pipe.kind.get_basis_along(direction, pipe.at_head(cube.position))
                    if pipe_color != cube_color:
                        raise TQECError(f"Cube {cube} has mismatched colors with pipe {pipe}.")

    def to_zx_graph(self) -> PositionedZX:
        """Convert the block graph to a positioned PyZX graph.

        Returns:
            A :py:class:`~tqec.interop.pyzx.positioned.PositionedZX` object
            converted from the block graph.

        """
        # Needs to be imported here to avoid pulling pyzx when importing this module.
        from tqec.interop.pyzx.positioned import PositionedZX  # noqa: PLC0415

        return PositionedZX.from_block_graph(self)

    def to_dae_file(
        self,
        file_path: str | pathlib.Path,
        pipe_length: float = 2.0,
        pop_faces_at_directions: Iterable[SignedDirection3D | str] = (),
        show_correlation_surface: CorrelationSurface | None = None,
    ) -> None:
        """Write the block graph to a Collada DAE file.

        Args:
            file_path: The output file path.
            pipe_length: The length of the pipes. Default is 2.0.
            pop_faces_at_directions: Remove the faces at the given directions for all the blocks.
                This is useful for visualizing the internal structure of the blocks.
                Default is None.
            show_correlation_surface: The correlation surface to show in the block graph.
                Default is None.

        """
        # Needs to be imported here to avoid pulling collada when importing this module.
        from tqec.interop.collada.read_write import write_block_graph_to_dae_file  # noqa: PLC0415

        write_block_graph_to_dae_file(
            self,
            file_path,
            pipe_length,
            pop_faces_at_directions,
            show_correlation_surface,
        )

    @staticmethod
    def from_dae_file(filename: str | pathlib.Path, graph_name: str = "") -> BlockGraph:
        """Construct a block graph from a COLLADA DAE file.

        Args:
            filename: The input ``.dae`` file path.
            graph_name: The name of the block graph. Default is an empty string.

        Returns:
            The :py:class:`~tqec.computation.block_graph.BlockGraph` object
            constructed from the DAE file.

        """
        # Needs to be imported here to avoid pulling collada when importing this module.
        from tqec.interop.collada.read_write import read_block_graph_from_dae_file  # noqa: PLC0415

        return read_block_graph_from_dae_file(filename, graph_name)

    def view_as_html(
        self,
        write_html_filepath: str | pathlib.Path | None = None,
        pipe_length: float = 2.0,
        pop_faces_at_directions: Iterable[SignedDirection3D | str] = (),
        show_correlation_surface: CorrelationSurface | None = None,
    ) -> _ColladaHTMLViewer:
        """View COLLADA model in html with the help of ``three.js``.

        This can display a COLLADA model interactively in IPython compatible environments.

        Args:
            write_html_filepath: The output html file path to write the generated html content
                if provided. Default is None.
            pipe_length: The length of the pipes. Default is 2.0.
            pop_faces_at_directions: Remove the faces at the given directions for all the blocks.
                This is useful for visualizing the internal structure of the blocks.
                Default is None.
            show_correlation_surface: The correlation surface to show in the block graph.
                Default is None.

        Returns:
            A helper class to display the 3D model, which implements the ``_repr_html_`` method and
            can be directly displayed in IPython compatible environments.

        """
        # Needs to be imported here to avoid pulling collada when importing this module.
        from tqec.interop.collada.html_viewer import display_collada_model  # noqa: PLC0415
        from tqec.interop.collada.read_write import write_block_graph_to_dae_file  # noqa: PLC0415

        bytes_buffer = BytesIO()
        write_block_graph_to_dae_file(
            self,
            bytes_buffer,
            pipe_length,
            pop_faces_at_directions,
            show_correlation_surface,
        )
        return display_collada_model(
            filepath_or_bytes=bytes_buffer.getvalue(),
            write_html_filepath=write_html_filepath,
        )

    def shift_by(self, dx: int = 0, dy: int = 0, dz: int = 0) -> BlockGraph:
        """Shift a copy of ``self`` by the given offset in the x, y, z directions and return it.

        Args:
            dx: The offset in the x direction.
            dy: The offset in the y direction.
            dz: The offset in the z direction.

        Returns:
            A new graph with the shifted positions. The new graph will share no data
            with the original graph.

        """
        new_graph = BlockGraph()
        for cube in self.cubes:
            new_graph.add_cube(cube.position.shift_by(dx=dx, dy=dy, dz=dz), cube.kind, cube.label)
        for pipe in self.pipes:
            u, v = pipe.u, pipe.v
            new_graph.add_pipe(
                u.position.shift_by(dx=dx, dy=dy, dz=dz),
                v.position.shift_by(dx=dx, dy=dy, dz=dz),
                pipe.kind,
            )
        return new_graph

    def find_correlation_surfaces(
        self, reduce_to_minimal_generators: bool = True
    ) -> list[CorrelationSurface]:
        """Find the correlation surfaces in the block graph.

        Args:
            reduce_to_minimal_generators: Whether to reduce the correlation
                surfaces to the minimal generators. Other correlation surfaces
                can be obtained by multiplying the generators. The generators
                are chosen to be the smallest in terms of the correlation
                surface area. Default is `True`.

        Returns:
            The list of correlation surfaces.

        """
        # Needs to be imported here to avoid pulling pyzx when importing this module.
        from tqec.interop.pyzx.correlation import find_correlation_surfaces  # noqa: PLC0415

        zx_graph = self.to_zx_graph()

        return find_correlation_surfaces(
            zx_graph.g, reduce_to_minimal_generators=reduce_to_minimal_generators
        )

    def fill_ports(self, fill: Mapping[str, CubeKind] | CubeKind) -> None:
        """Fill the ports at specified positions with cubes of the given kind.

        Args:
            fill: A mapping from the label of the ports to the cube kind to fill.
                If a single kind is given, all the ports will be filled with the
                same kind.

        Raises:
            TQECError: if there is no port with the given label.

        """
        if isinstance(fill, CubeKind):
            fill = {label: fill for label in self._ports}
        for label, kind in fill.items():
            if label not in self._ports:
                raise TQECError(f"There is no port with label {label}.")
            pos = self._ports[label]
            fill_node = Cube(pos, kind)
            # Overwrite the node at the port position
            self._graph.add_node(pos, **{self._NODE_DATA_KEY: fill_node})
            for pipe in self.pipes_at(pos):
                self._graph.remove_edge(pipe.u.position, pipe.v.position)
                other = pipe.u if pipe.v.position == pos else pipe.v
                self._graph.add_edge(
                    other.position,
                    pos,
                    **{self._EDGE_DATA_KEY: Pipe(other, fill_node, pipe.kind)},
                )
            # Delete the port label
            self._ports.pop(label)

    def fill_ports_for_minimal_simulation(self) -> list[FilledGraph]:
        """Fill the ports of the provided ``graph`` to minimize the number of simulation runs.

        Given a block graph with open ports, fill in the ports with the appropriate cubes that
        will minimize the number of simulation runs needed for the complete logical observable set.

        Returns:
            A list of :class:`~tqec.computation.open_graph.FilledGraph` instances, each
            containing a block graph with all ports filled and a set of correlation
            surfaces that can be used as logical observables for the simulation on that
            block graph.

        """
        # Needs to be imported here to avoid pulling pyzx when importing this module.
        from tqec.computation.open_graph import fill_ports_for_minimal_simulation  # noqa: PLC0415

        return fill_ports_for_minimal_simulation(self)

    def compose(self, other: BlockGraph, self_port: str, other_port: str) -> BlockGraph:
        """Compose the current graph with another graph.

        The other graph will be shifted to match the ports in the current graph
        and the two graphs will be composed at the corresponding ports.

        The two ports provided to this method will serve as an "anchor", and other
        overlapping ports will be detected and glued automatically.

        Args:
            other: The other graph to be composed with the current graph.
            self_port: The label of the port to be connected in the current graph.
            other_port: The label of the port to be connected in the other graph.

        Returns:
            A new graph that is the composition of the current graph with the other graph.

        Raises:
            TQECError: If the ports are not in the graphs, or if the two graphs
                cannot be composed because overlapping spacetime extents or incompatible
                cube kinds.

        """
        if self_port not in self.ports:
            raise TQECError(f"Port {self_port} is not in the current graph.")
        if other_port not in other.ports:
            raise TQECError(f"Port {other_port} is not in the other graph.")

        p1, p2 = self.ports[self_port], other.ports[other_port]
        shift = (p1.x - p2.x, p1.y - p2.y, p1.z - p2.z)
        shifted_g = other.shift_by(*shift)

        ports_need_fill: dict[str, Position3D] = {}
        # Check if there is overlapping spacetime extent
        for cube in self.cubes:
            pos = cube.position
            if pos in shifted_g:
                if cube.is_port and shifted_g[pos].is_port:
                    ports_need_fill[cube.label] = pos
                    continue
                raise TQECError(
                    f"Cube at position {cube.position} is overlapping between the two graphs."
                )
        composed_g = self.clone()
        # Resolve the cube kinds at the ports
        for label, port in ports_need_fill.items():
            bases: list[Basis] = []
            # port is guaranteed to only have one pipe connected
            pipe1 = self.pipes_at(port)[0]
            pipe2 = shifted_g.pipes_at(port)[0]
            for d in Direction3D.all_directions():
                b1 = pipe1.kind.get_basis_along(d, pipe1.at_head(port))
                b2 = pipe2.kind.get_basis_along(d, pipe2.at_head(port))
                if b1 is not None and b2 is not None and b1 != b2:
                    raise TQECError(
                        f"Port at {port} cannot be filled with a cube that has "
                        "valid boundary conditions."
                    )
                # choose Z basis boundary for the walls that can have arbitrary boundary
                bases.append(b1 or b2 or Basis.Z)
            cube_kind = ZXCube(*bases)
            composed_g.fill_ports({label: cube_kind})
        # Compose the graphs
        for cube in shifted_g.cubes:
            # Connecting ports have been filled
            if cube.position in composed_g:
                continue
            composed_g.add_cube(cube.position, cube.kind, cube.label)
        for pipe in shifted_g.pipes:
            u, v = pipe.u.position, pipe.v.position
            composed_g.add_pipe(u, v, pipe.kind)
        composed_g.ports.update({s: p for s, p in shifted_g.ports.items() if composed_g[p].is_port})
        composed_g.name = f"{self.name}_composed_with_{other.name}"
        return composed_g

    def is_single_connected(self) -> bool:
        """Check if the graph is single connected.

        A block graph is single-connected if there is only one connected component in the graph.
        """
        return bool(is_connected(self._graph))

    def rotate(
        self,
        rotation_axis: Direction3D,
        counterclockwise: bool = True,
        num_90_degree_rotation: int = 1,
    ) -> BlockGraph:
        """Rotate a copy of ``self`` around an axis by a multiple of 90 degrees and return it.

        Args:
            rotation_axis: The axis to rotate around.
            counterclockwise: Whether to rotate counterclockwise. Default is True.
            num_90_degree_rotation: The number of 90-degree rotations. Default is 1.

        Returns:
            A new graph with the rotated positions. The new graph will share no data
            with the original graph.

        """
        # Needs to be imported here to avoid pulling scipy when importing this module.
        from tqec.utils.rotations import (  # noqa: PLC0415
            get_rotation_matrix,
            rotate_block_kind_by_matrix,
            rotate_position_by_matrix,
        )

        rotated = BlockGraph(self.name + "_rotated")
        rotation_matrix = get_rotation_matrix(
            rotation_axis, counterclockwise, num_90_degree_rotation * math.pi / 2
        )
        pos_map: dict[Position3D, Position3D] = {}
        for cube in self.cubes:
            rotated_kind = rotate_block_kind_by_matrix(cube.kind, rotation_matrix)
            rotated_pos = rotate_position_by_matrix(cube.position, rotation_matrix)
            rotated.add_cube(rotated_pos, cast(CubeKind, rotated_kind), cube.label)
            pos_map[cube.position] = rotated_pos

        for pipe in self.pipes:
            rotated_kind = rotate_block_kind_by_matrix(pipe.kind, rotation_matrix)
            rotated.add_pipe(
                pos_map[pipe.u.position],
                pos_map[pipe.v.position],
                cast(PipeKind, rotated_kind),
            )
        return rotated

    def fix_shadowed_faces(self) -> BlockGraph:
        """Fix the basis of those shadowed faces of the cubes in the graph.

        A pair of face can be shadowed if the cube is connected to two pipes
        in the same direction. Though these faces are not visible in the 3D
        visualization, they are still identified by the cube kind and can
        affect the circuit compilation.

        The basis of the cube is enforced to match the pipes connected to it.
        If there is unmatched shadowed faces, we try to fix their basis. This
        will leave some freedom in constructing the model in SketchUp and make
        everyones' life easier.

        Additionally, for a spatial pass-through, i.e. a cube only connected to
        two pipes in the same direction, we will fix the cube kind to not be a
        spatial cube.

        Note that the fixed graph is still not guaranteed to be valid as some
        other conditions may be violated. You still need to call
        :py:meth:`~tqec.computation.block_graph.BlockGraph.validate` to check
        the validity of the graph.

        Returns:
            A new graph with the shadowed faces fixed.

        """
        fixed_cubes: dict[Cube, Cube] = {}
        for cube in self.cubes:
            if not isinstance(cube.kind, ZXCube):
                continue
            # Group connected pipes by direction
            pipes_by_direction: dict[Direction3D, list[Pipe]] = {}
            for pipe in self.pipes_at(cube.position):
                pipes_by_direction.setdefault(pipe.direction, []).append(pipe)
            # No need to handle the case `len(pipes_by_direction) == 0` as there
            # is no pipes connected to the cube.
            # No need to handle the case `len(pipes_by_direction) == 3` as it's
            # a 3D corner that cannot be a valid structure.
            # Spatial pass-through, ensure that the cube is not a spatial cube
            if len(pipes_by_direction) in [0, 3]:
                continue
            shadowed_directions = {d for d, ps in pipes_by_direction.items() if len(ps) == 2}
            if not shadowed_directions:
                continue
            new_kind = cube.kind
            for shadowed_direction in shadowed_directions:
                # Spatial pass-through, ensure that the cube is not a spatial cube
                if (
                    len(pipes_by_direction) == 1
                    and shadowed_direction != Direction3D.Z
                    and cube.is_spatial
                ):
                    kind = cube.kind
                    assert isinstance(kind, ZXCube)
                    basis = kind.get_basis_along(shadowed_direction)
                    new_kind = kind.with_basis_along(shadowed_direction, basis.flipped())
                    new_cube = Cube(cube.position, new_kind, cube.label)
                    fixed_cubes[cube] = new_cube
                # T-shape or X-shape connections, can be either in space or time
                # Ensure the shadowed faces match the pipe faces that are in the
                # same plane.
                elif len(pipes_by_direction) == 2:
                    other_direction = next(d for d in pipes_by_direction if d != shadowed_direction)
                    need_match_pipe = next(iter(pipes_by_direction[other_direction]))
                    pipe_basis = need_match_pipe.kind.get_basis_along(
                        shadowed_direction, need_match_pipe.at_head(cube.position)
                    )
                    assert pipe_basis is not None
                    new_kind = new_kind.with_basis_along(shadowed_direction, pipe_basis)

            if new_kind != cube.kind:
                new_cube = Cube(cube.position, new_kind, cube.label)
                fixed_cubes[cube] = new_cube
        new_graph = BlockGraph(self.name)
        for cube in self.cubes:
            new_cube = fixed_cubes.get(cube, cube)
            new_graph.add_cube(cube.position, new_cube.kind, new_cube.label)
        for pipe in self.pipes:
            new_graph.add_pipe(pipe.u.position, pipe.v.position, pipe.kind)
        return new_graph

    def get_cubes_by_label(self, label: str) -> list[Cube]:
        """Find cubes with the specified label in the BlockGraph.

        Args:
            label: The label of the cubes.

        Returns:
            The cube instances that have the specified label.

        """
        return [cube for cube in self.cubes if cube.label == label]

    def to_dict(self) -> dict[str, Any]:
        """Return a dictionary representation of the block graph."""
        return {
            "name": self.name,
            "cubes": [cube.to_dict() for cube in self.cubes],
            "pipes": [pipe.to_dict() for pipe in self.pipes],
            "ports": {label: pos.as_tuple() for label, pos in self.ports.items()},
        }

    @staticmethod
    def from_dict(data: dict[str, Any]) -> BlockGraph:
        """Construct a block graph from a dictionary representation."""
        graph = BlockGraph(data["name"])
        for cube in data["cubes"]:
            graph.add_cube(
                position=Position3D(*cube["position"]),
                kind=cube["kind"],
                label=cube["label"],
            )
        for pipe in data["pipes"]:
            graph.add_pipe(
                pos1=Position3D(*pipe["u"]),
                pos2=Position3D(*pipe["v"]),
                kind=pipe["kind"],
            )
        return graph

    def to_json(
        self,
        file_path: str | pathlib.Path | None = None,
        *,
        indent: int | None = 2,
    ) -> str | None:
        """Serialize the block graph to a JSON string or write it to a file.

        Args:
            file_path: The output file path. If None, the JSON string will be returned.
            indent: The indentation level for pretty printing, passed to
                `json.dumps`. Default is 2.

        Returns:
            The JSON string representation of the block graph if `file_path` is None,
            otherwise None.

        """
        # Get dictionary from blockgraph
        obj_dict = self.to_dict()

        # Add transform matrix to keep schema symmetric
        for cube in obj_dict["cubes"]:
            cube["transform"] = np.eye(3, dtype=int).tolist()

        for pipe in obj_dict["pipes"]:
            pipe["transform"] = np.eye(3, dtype=int).tolist()

        # Return or write
        if file_path is None:
            return json.dumps(obj_dict, indent=indent)
        with open(file_path, "w") as fp:
            json.dump(obj_dict, fp, indent=indent)
            return None

    @staticmethod
    def from_json(filename: str | pathlib.Path, graph_name: str = "") -> BlockGraph:
        """Construct a block graph from a JSON file.

        Args:
            filename: The input ``.json`` file path.
            graph_name: The name of the block graph. Default is an empty string.

        Returns:
            The :py:class:`~tqec.computation.block_graph.BlockGraph` object
            constructed from the DAE file.

        """
        # Needs to be imported here to avoid pulling collada when importing this module.
        from tqec.interop.collada.read_write import read_block_graph_from_json  # noqa: PLC0415

        return read_block_graph_from_json(filename, graph_name)

    def relabel_cubes(self, label_mapping: Mapping[Position3D | str, str]) -> None:
        """Relabel cubes in the block graph.

        This method updates the labels of cubes in the graph, based on a mapping
        from either a cube position or its existing label to a new label.

        Args:
            label_mapping: A mapping from either Position3D or current cube label (str)
                to the new label to assign.

        Raises:
            TQECError: If a cube is not found for the given key, if a port label
                is reused, or if the new label conflicts with existing port labels.

        """
        port_labels = {cube.label for cube in self.cubes if cube.is_port}
        assigned_new_labels: set[str] = set()

        for key, new_label in label_mapping.items():
            if not new_label:
                raise TQECError("New label must be non-empty.")

            if isinstance(key, Position3D):
                matching_cubes = [cube for cube in self.cubes if cube.position == key]
            elif isinstance(key, str):
                matching_cubes = [cube for cube in self.cubes if cube.label == key]
            else:
                raise TQECError(f"Invalid identifier '{key}'. Must be Position3D or str.")

            if not matching_cubes:
                raise TQECError(f"No cube found for identifier '{key}'.")

            is_port_relabel = any(cube.is_port for cube in matching_cubes)

            if is_port_relabel:
                if new_label in port_labels:
                    raise TQECError(
                        f"Port label '{new_label}' is already assigned to another port."
                    )
                if new_label in assigned_new_labels:
                    raise TQECError(f"Port label '{new_label}' is reused multiple times.")
                assigned_new_labels.add(new_label)
                self._ports[new_label] = self._ports.pop(matching_cubes[0].label)
            elif new_label in port_labels:
                raise TQECError(
                    f"The label '{new_label}' belongs to a port and "
                    "cannot be reused by a non-port cube."
                )

            for cube in matching_cubes:
                updated_cube = Cube(position=cube.position, kind=cube.kind, label=new_label)
                self._graph.add_node(cube.position, **{self._NODE_DATA_KEY: updated_cube})


def block_kind_from_str(string: str) -> BlockKind:
    """Parse a block kind from a string."""
    string = string.upper()
    if "O" in string:
        return PipeKind.from_str(string)
    elif string == "Y":
        return YHalfCube()
    else:
        return ZXCube.from_str(string)
