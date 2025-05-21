"""Defines a few core data-structures that are independent of other ``tqec`` modules.

The goal of this module is to host data-structures that do not clearly belong to
another existing ``tqec`` sub-module and that also do not import any code from
the other ``tqec`` sub-modules.
"""

from .enums import Basis
from .enums import Orientation
from .exceptions import TQECException
from .noise_model import NoiseModel
