"""Graph representation of a 3D logical computation by explicit blocks."""

from __future__ import annotations

import pathlib
from typing import TYPE_CHECKING
from copy import deepcopy
from io import BytesIO

from tqec.computation._base_graph import ComputationGraph
from tqec.exceptions import TQECException
from tqec.position import Direction3D, SignedDirection3D
from tqec.computation.cube import Cube, CubeKind
from tqec.computation.pipe import Pipe, PipeKind
from tqec.computation.zx_graph import ZXGraph
from tqec.computation.correlation import CorrelationSurface

if TYPE_CHECKING:
    from tqec.interop.collada.html_viewer import _ColladaHTMLViewer
    from tqec.computation.abstract_observable import AbstractObservable


BlockKind = CubeKind | PipeKind
"""Valid block types in the library."""


class BlockGraph(ComputationGraph[Cube, Pipe]):
    """An undirected graph representation of a logical computation.

    The block graph specifies the explicit block structures of the
    spacetime diagram, including the layout of the code patches, the
    boundary types and the connectivity of the patches across the
    spacetime. The block graph can be compiled and used to generate the
    concrete circuits that implement the logical computation.

    The nodes in the graph are the cubes that represent a unit of code
    patch in the spacetime. The edges in the graph are the pipes that
    connect the cubes. The pipes guide the logical computation and the
    information flow between the code patches over spacetime.
    """

    def add_edge(self, u: Cube, v: Cube, kind: PipeKind | None = None) -> None:
        """Add an edge to the graph. If the nodes do not exist in the graph,
        the nodes will be created and added to the graph.

        Args:
            edge: The edge to add to the graph.

        Raises:
            TQECException: For each node in the edge, if there is already a node which is not
                equal to it at the same position, or the node is a port but there is already a
                different port with the same label in the graph.
        """
        if kind is None:
            pipe = Pipe.from_cubes(u, v)
        else:
            pipe = Pipe(u, v, kind)
        self._add_edge_and_nodes_with_checks(u, v, pipe)

    def validate(self) -> None:
        """Check the validity of the block structures represented by the graph.

        Refer to the Fig.9 in arXiv:2404.18369. Currently, we ignore the b) and e),
        only check the following conditions:

        a) no fanout: ports can only have one pipe connected to them.
        c) time-like Y: Y cubes can only have time-like pipes connected to them.
        d) no 3D corner: a cube cannot have pipes in all three directions.
        f) match color at passthrough: two pipes in a "pass-through" should have the same
        color orientation.
        g) match color at turn: two pipes in a "turn" should have the matching colors on
        faces that are touching.

        Args:
            allow_virtual_node: Whether to allow the virtual node in the graph. A virtual node is an open
                port of a pipe. It is not a physical cube but a placeholder for the pipe to connect to the
                boundary of the graph. Default is True.
        """
        for cube in self.nodes:
            self._validate_locally_at_cube(cube)

    def _validate_locally_at_cube(self, cube: Cube) -> None:
        """Check the validity of the block structures locally at a cube."""
        pipes = self.edges_at(cube.position)
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
            pipe.validate()

    def to_zx_graph(self, name: str | None = None) -> ZXGraph:
        """Convert the block graph to a
        :py:class:`~tqec.computation.zx_graph.ZXGraph`.

        The conversion process is as follows:

        1. For each cube in the block graph, convert it to a ZX node by calling :py:meth:`~tqec.computation.cube.Cube.to_zx_node`.
        2. For each pipe in the block graph, add an edge to the ZX graph with the corresponding endpoints and Hadamard flag.

        Args:
            block_graph: The block graph to be converted to a ZX graph.
            name: The name of the new ZX graph. If None, the name of the block graph will be used.

        Returns:
            The :py:class:`~tqec.computation.zx_graph.ZXGraph` object converted from the block graph.
        """
        from tqec.computation.conversion import (
            convert_block_graph_to_zx_graph,
        )

        return convert_block_graph_to_zx_graph(self, name)

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
        """Construct a block graph from a DAE file."""
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
        from tqec.interop.collada.read_write import write_block_graph_to_dae_file
        from tqec.interop.collada.html_viewer import display_collada_model

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

    def get_abstract_observables(
        self,
        correlation_surfaces: list[CorrelationSurface] | None = None,
    ) -> tuple[list[AbstractObservable], list[CorrelationSurface]]:
        """Get all the abstract observables from the block graph.

        Args:
            correlation_surfaces: The correlation surfaces to convert to abstract observables. If not
                provided, the correlation surfaces will be constructed from the corresponding ZX graph
                of the block graph.

        Returns:
            The list of abstract observables and the list of correlation surfaces corresponding to the
            observables.
        """
        from tqec.computation.abstract_observable import (
            correlation_surface_to_abstract_observable,
        )

        self.validate()

        if correlation_surfaces is None:
            correlation_surfaces = self.to_zx_graph().find_correration_surfaces()
        abstract_observables: list[AbstractObservable] = [
            correlation_surface_to_abstract_observable(self, surface)
            for surface in correlation_surfaces
        ]

        return abstract_observables, correlation_surfaces

    def shift_min_z_to_zero(self) -> BlockGraph:
        """Shift the whole graph in the z direction to make the minimum z equal
        zero.

        Returns:
            A new graph with the minimum z position of the cubes equal to zero. The new graph
            will share no data with the original graph.
        """
        minz = min(cube.position.z for cube in self.nodes)
        if minz == 0:
            return deepcopy(self)
        new_graph = BlockGraph(self.name)
        for pipe in self.edges:
            u, v = pipe.u, pipe.v
            new_graph.add_edge(
                Cube(u.position.shift_by(dz=-minz), u.kind, u.label),
                Cube(v.position.shift_by(dz=-minz), v.kind, v.label),
                pipe.kind,
            )
        return new_graph
