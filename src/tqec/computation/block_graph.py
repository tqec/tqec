"""Block graph representation of a logical computation."""

from __future__ import annotations

from collections.abc import Mapping
import pathlib
from copy import deepcopy
from io import BytesIO
from typing import TYPE_CHECKING, cast

import networkx as nx

from tqec.computation.cube import Cube, CubeKind, Port, cube_kind_from_string
from tqec.computation.pipe import Pipe, PipeKind
from tqec.utils.exceptions import TQECException
from tqec.utils.position import Direction3D, Position3D, SignedDirection3D

if TYPE_CHECKING:
    from tqec.interop.collada.html_viewer import _ColladaHTMLViewer
    from tqec.interop.pyzx.positioned import PositionedZX
    from tqec.computation.correlation import CorrelationSurface


BlockKind = CubeKind | PipeKind


class BlockGraph:
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
    """

    _NODE_DATA_KEY: str = "tqec_node_data"
    _EDGE_DATA_KEY: str = "tqec_edge_data"

    def __init__(self, name: str = "") -> None:
        self._name = name
        self._graph: nx.Graph[Position3D] = nx.Graph()
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
    def cubes(self) -> list[Cube]:
        """The list of cubes (nodes) in the graph."""
        return [data[self._NODE_DATA_KEY] for _, data in self._graph.nodes(data=True)]

    @property
    def pipes(self) -> list[Pipe]:
        """The list of pipes (edges) in the graph."""
        return [
            data[self._EDGE_DATA_KEY] for _, _, data in self._graph.edges(data=True)
        ]

    @property
    def ports(self) -> dict[str, Position3D]:
        """Mapping from port labels to their positions.

        A port is a virtual node with unique label that represents the
        input/output of the computation. It should be invisible when visualizing
        the computation model.
        """
        return dict(self._ports)

    def get_degree(self, position: Position3D) -> int:
        """Get the degree of a node in the graph, i.e. the number of edges
        incident to it."""
        return self._graph.degree(position)  # type: ignore

    @property
    def leaf_cubes(self) -> list[Cube]:
        """Get the leaf cubes of the graph, i.e. the cubes with degree 1."""
        return [node for node in self.cubes if self.get_degree(node.position) == 1]

    def add_cube(
        self,
        position: Position3D,
        kind: CubeKind | str,
        label: str = "",
    ) -> Position3D:
        """Add a cube to the graph.

        Args:
            position: The position of the cube.
            kind: The kind of the cube. It can be a :py:class:`~tqec.computation.cube.CubeKind`
                instance or a string representation of the cube kind.
            label: The label of the cube. Default is None.

        Returns:
            The position of the cube added to the graph.

        Raises:
            TQECException: If there is already a cube at the same position, or
                if the cube kind is not recognized, or if the cube is a port and
                there is already a port with the same label in the graph.
        """
        if position in self:
            raise TQECException(f"Cube already exists at position {position}.")
        if isinstance(kind, str):
            kind = cube_kind_from_string(kind)
        if kind == Port() and label in self._ports:
            raise TQECException(
                "There is already a port with the same label in the graph."
            )

        self._graph.add_node(
            position, **{self._NODE_DATA_KEY: Cube(position, kind, label)}
        )
        if kind == Port():
            self._ports[label] = position
        return position

    def add_pipe(
        self, pos1: Position3D, pos2: Position3D, kind: PipeKind | str | None = None
    ) -> None:
        """Add a pipe to the graph.

        Args:
            pos1: The position of one end of the pipe.
            pos2: The position of the other end of the pipe.
            kind: The kind of the pipe connecting the cubes. If None, the kind will be
                automatically determined based on the cubes it connects to make the
                boundary conditions consistent. Default is None.

        Raises:
            TQECException: If any of the positions do not have a cube in the graph, or
                if there is already an pipe between the given positions, or
                if the pipe is not compatible with the cubes it connects.
        """
        u, v = self[pos1], self[pos2]
        if self.has_pipe_between(pos1, pos2):
            raise TQECException(
                "There is already a pipe between the given positions in the graph."
            )
        if kind is None:
            pipe = Pipe.from_cubes(u, v)
        else:
            if isinstance(kind, str):
                kind = PipeKind.from_str(kind)
            pipe = Pipe(u, v, kind)
        self._graph.add_edge(pos1, pos2, **{self._EDGE_DATA_KEY: pipe})

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
        """Get the pipe by its endpoint positions. If there is no pipe between
        the given positions, an exception will be raised.

        Args:
            pos1: The first endpoint position.
            pos2: The second endpoint position.

        Returns:
            The pipe between the two positions.

        Raises:
            TQECException: If there is no pipe between the given positions.
        """
        if not self.has_pipe_between(pos1, pos2):
            raise TQECException("No pipe between the given positions is in the graph.")
        return cast(Pipe, self._graph.edges[pos1, pos2][self._EDGE_DATA_KEY])

    def pipes_at(self, position: Position3D) -> list[Pipe]:
        """Get the pipes incident to a position."""
        if position not in self:
            return []
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
        if position not in self:
            raise TQECException(f"No cube at position {position}.")
        return cast(Cube, self._graph.nodes[position][self._NODE_DATA_KEY])

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, BlockGraph):
            return False
        return (
            nx.utils.graphs_equal(self._graph, other._graph)  # type: ignore
            and self._ports == other._ports
        )

    def validate(self) -> None:
        """Check the validity of the block graph to represent a logical
        computation.

        Refer to the Fig.9 in arXiv:2404.18369. Currently, we ignore the b) and e),
        only check the following conditions:

        - **No fanout:** ports can only have one pipe connected to them.
        - **Time-like Y:** Y cubes can only have time-like pipes connected to them.
        - **No 3D corner:** a cube cannot have pipes in all three directions.
        - **Match color at passthrough:** two pipes in a "pass-through" should have the same
          color orientation.
        - **Match color at turn:** two pipes in a "turn" should have the matching colors on
          faces that are touching.

        Additionally, the following conditions are checked:

        - **Port as IO:** all the port cubes should be either inputs or outputs, and all
            the inputs/outputs should be ports.

        Raises:
            TQECException: If the above conditions are not satisfied.
        """
        for cube in self.cubes:
            self._validate_locally_at_cube(cube)

    def _validate_locally_at_cube(self, cube: Cube) -> None:
        """Check the validity of the block structures locally at a cube."""
        pipes = self.pipes_at(cube.position)
        # a). no fanout
        if cube.is_port:
            if len(pipes) != 1:
                raise TQECException(
                    f"Port at {cube.position} does not have exactly one pipe connected."
                )
            return
        # c). time-like Y
        if cube.is_y_cube:
            if len(pipes) != 1:
                raise TQECException(
                    f"Y cube at {cube.position} does not have exactly one pipe connected."
                )
            if not pipes[0].direction == Direction3D.Z:
                raise TQECException(
                    f"Y cube at {cube.position} has non-timelike pipes connected."
                )
            return

        # Check the color matching conditions
        pipes_by_direction: dict[Direction3D, list[Pipe]] = {}
        for pipe in pipes:
            pipes_by_direction.setdefault(pipe.direction, []).append(pipe)
        # d), f), g). Match color
        for pipe in pipes:
            pipe.check_compatible_with_cubes()

    def to_zx_graph(self) -> PositionedZX:
        """Convert the block graph to a positioned PyZX graph.

        Returns:
            A :py:class:`~tqec.interop.pyzx.positioned.PositionedZX` object converted from the block graph.
        """
        from tqec.interop.pyzx.positioned import PositionedZX

        return PositionedZX.from_block_graph(self)

    def to_dae_file(
        self,
        file_path: str | pathlib.Path,
        pipe_length: float = 2.0,
        pop_faces_at_direction: SignedDirection3D | None = None,
        show_correlation_surface: CorrelationSurface | None = None,
    ) -> None:
        """Write the block graph to a Collada DAE file.

        Args:
            file_path: The output file path.
            pipe_length: The length of the pipes. Default is 2.0.
            pop_faces_at_direction: Remove the faces at the given direction for all the blocks.
                This is useful for visualizing the internal structure of the blocks. Default is None.
            show_correlation_surface: The correlation surface to show in the block graph. Default is None.
        """
        from tqec.interop.collada.read_write import write_block_graph_to_dae_file

        write_block_graph_to_dae_file(
            self,
            file_path,
            pipe_length,
            pop_faces_at_direction,
            show_correlation_surface,
        )

    @staticmethod
    def from_dae_file(filename: str | pathlib.Path, graph_name: str = "") -> BlockGraph:
        """Construct a block graph from a COLLADA DAE file.

        Args:
            filename: The input ``.dae`` file path.
            graph_name: The name of the block graph. Default is an empty string.

        Returns:
            The :py:class:`~tqec.computation.block_graph.BlockGraph` object constructed from the DAE file.
        """
        from tqec.interop.collada.read_write import read_block_graph_from_dae_file

        return read_block_graph_from_dae_file(filename, graph_name)

    def view_as_html(
        self,
        write_html_filepath: str | pathlib.Path | None = None,
        pipe_length: float = 2.0,
        pop_faces_at_direction: SignedDirection3D | None = None,
        show_correlation_surface: CorrelationSurface | None = None,
    ) -> _ColladaHTMLViewer:
        """View COLLADA model in html with the help of ``three.js``.

        This can display a COLLADA model interactively in IPython compatible environments.

        Args:
            write_html_filepath: The output html file path to write the generated html content
                if provided. Default is None.
            pipe_length: The length of the pipes. Default is 2.0.
            pop_faces_at_direction: Remove the faces at the given direction for all the blocks.
                This is useful for visualizing the internal structure of the blocks. Default is None.
            show_correlation_surface: The correlation surface to show in the block graph. Default is None.

        Returns:
            A helper class to display the 3D model, which implements the ``_repr_html_`` method and
            can be directly displayed in IPython compatible environments.
        """
        from tqec.interop.collada.html_viewer import display_collada_model
        from tqec.interop.collada.read_write import write_block_graph_to_dae_file

        bytes_buffer = BytesIO()
        write_block_graph_to_dae_file(
            self,
            bytes_buffer,
            pipe_length,
            pop_faces_at_direction,
            show_correlation_surface,
        )
        return display_collada_model(
            filepath_or_bytes=bytes_buffer.getvalue(),
            write_html_filepath=write_html_filepath,
        )

    def shift_by(self, dx: int = 0, dy: int = 0, dz: int = 0) -> BlockGraph:
        """Shift the whole graph by the given offset in the x, y, z directions and
        creat a new graph with the shifted positions.

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
            new_graph.add_cube(
                cube.position.shift_by(dx=dx, dy=dy, dz=dz), cube.kind, cube.label
            )
        for pipe in self.pipes:
            u, v = pipe.u, pipe.v
            new_graph.add_pipe(
                u.position.shift_by(dx=dx, dy=dy, dz=dz),
                v.position.shift_by(dx=dx, dy=dy, dz=dz),
                pipe.kind,
            )
        return new_graph

    def find_correlation_surfaces(self) -> list[CorrelationSurface]:
        """Find the correlation surfaces in the block graph.

        Returns:
            The list of correlation surfaces.
        """
        from tqec.interop.pyzx.correlation import find_correlation_surfaces

        zx_graph = self.to_zx_graph()

        return find_correlation_surfaces(zx_graph.g)

    def fill_ports(self, fill: Mapping[str, CubeKind] | CubeKind) -> None:
        """Fill the ports at specified positions with cubes of the given kind.

        Args:
            fill: A mapping from the label of the ports to the cube kind to fill.
                If a single kind is given, all the ports will be filled with the
                same kind.

        Raises:
            TQECException: if there is no port with the given label.
        """
        if isinstance(fill, CubeKind):
            fill = {label: fill for label in self._ports}
        for label, kind in fill.items():
            if label not in self._ports:
                raise TQECException(f"There is no port with label {label}.")
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

    def rotate(
        self,
        rotation_axis: Direction3D = Direction3D.Y,
        num_90_degree_rotation: int = 1,
        counterclockwise: bool = True,
    ) -> BlockGraph:
        """Rotate the graph around an axis by ``num_90_degree_rotation * 90`` degrees and
        return a new rotated graph.

        Args:
            rotation_axis: The axis around which to rotate the graph.
            num_90_degree_rotation: The number of 90-degree rotations to apply to the graph.
            counterclockwise: Whether to rotate the graph counterclockwise. If set to False,
                the graph will be rotated clockwise. Defaults to True.

        Returns:
            A data-independent copy of the graph rotated by the given number of 90-degree rotations.
        """
        n = num_90_degree_rotation % 4

        if n == 0:
            return self.clone()
        g = self.to_zx_graph()
        rotated_g = g.rotate(rotation_axis, n, counterclockwise)
        return rotated_g.to_block_graph()
