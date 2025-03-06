"""Defines the data structures to represent the logical computations.

This module provides high-level abstractions to represent the fault-
tolerant logical computations protected by surface code.
"""

from tqec.computation.block_graph import BlockGraph as BlockGraph
from tqec.computation.block_graph import BlockKind as BlockKind
from tqec.computation.cube import Cube as Cube
from tqec.computation.cube import CubeKind as CubeKind
from tqec.computation.cube import Port as Port
from tqec.computation.cube import YHalfCube as YHalfCube
from tqec.computation.cube import ZXCube as ZXCube
from tqec.computation.pipe import Pipe as Pipe
from tqec.computation.pipe import PipeKind as PipeKind
from tqec.computation.correlation import CorrelationSurface as CorrelationSurface
