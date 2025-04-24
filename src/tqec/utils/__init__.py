"""Defines a few core data-structures that are independent of other ``tqec`` modules.

The goal of this module is to host data-structures that do not clearly belong to
another existing ``tqec`` sub-module and that also do not import any code from
the other ``tqec`` sub-modules.
"""

from .enums import Basis as Basis
from .enums import Orientation as Orientation
from .enums import PatchStyle as PatchStyle
from .exceptions import TQECException as TQECException
from .noise_model import NoiseModel as NoiseModel
from .position import BlockPosition2D as BlockPosition2D
from .position import Direction3D as Direction3D
from .position import PhysicalQubitPosition2D as PhysicalQubitPosition2D
from .position import PlaquettePosition2D as PlaquettePosition2D
from .position import Position3D as Position3D
from .position import Shift2D as Shift2D
from .position import SignedDirection3D as SignedDirection3D
from .scale import LinearFunction as LinearFunction
from .scale import round_or_fail as round_or_fail
