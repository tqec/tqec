"""Defines the data structures to represent the logical computations.

This module provides high-level abstractions to represent the fault-tolerant logical
computations protected by surface code. There are two representations of the logical
computation:

- :py:class:`~tqec.computation.zx_graph.ZXGraph`: A restricted form of the ZX graph from
  the ZX-calculus. Rewriting rules from the ZX-calculus can be applied to the graph to
  verify the functionality of the computation.
- :py:class:`~tqec.computation.block_graph.BlockGraph`: A graph consisting of individual
  building blocks that fully specify the boundary conditions and topological structures
  of the logical computation. It corresponds to the commonly used 3D spacetime diagram
  representation of a surface code logical computation.
"""

from tqec.computation.zx_graph import ZXKind, ZXEdge, ZXGraph, ZXNode
from tqec.computation.cube import Cube, CubeKind, ZXCube, Port, YCube
from tqec.computation.pipe import Pipe, PipeKind
from tqec.computation.block_graph import BlockGraph, BlockKind
