"""Defines a few core data-structures that are independent of other ``tqec`` modules.

The goal of this module is to host data-structures that do not clearly belong to
another existing ``tqec`` sub-module and that also do not import any code from
the other ``tqec`` sub-modules.

"""

from .enums import Basis as Basis
from .enums import Orientation as Orientation
from .exceptions import TQECError as TQECError
from .noise_model import NoiseModel as NoiseModel
