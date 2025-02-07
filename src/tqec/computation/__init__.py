"""Defines the data structures to represent the logical computations.

This module provides high-level abstractions to represent the fault-tolerant logical
computations protected by surface code. There are two representations of the logical
computation:

- :py:class:`~tqec.computation.zx_graph.ZXGraph`: A restricted form of the ZX diagram from
  the ZX-calculus.
- :py:class:`~tqec.computation.block_graph.BlockGraph`: A graph consisting of individual
  building blocks that fully specify the boundary conditions and topological structures
  of the logical computation. It corresponds to the commonly used 3D spacetime diagram
  representation of a surface code logical computation.
"""

from tqec.computation.block_graph import BlockGraph as BlockGraph
from tqec.computation.block_graph import BlockKind as BlockKind
from tqec.computation.cube import Cube as Cube
from tqec.computation.cube import CubeKind as CubeKind
from tqec.computation.cube import Port as Port
from tqec.computation.cube import YCube as YCube
from tqec.computation.cube import ZXCube as ZXCube
from tqec.computation.pipe import Pipe as Pipe
from tqec.computation.pipe import PipeKind as PipeKind
from tqec.computation.correlation import CorrelationSurface as CorrelationSurface
