"""Defines several widely used plaquettes for re-use.

This module goal is to centralise the definition of several widely used
plaquettes in order to avoid each user the hassle of re-defining their
own plaquettes.
"""

from .builder import PlaquetteBuilder as PlaquetteBuilder
from .css import make_css_surface_code_plaquette as make_css_surface_code_plaquette
from .empty import empty_plaquette as empty_plaquette
from .empty import empty_square_plaquette as empty_square_plaquette
from .zxxz import make_zxxz_surface_code_plaquette as make_zxxz_surface_code_plaquette
from .spatial import make_spatial_cube_arm_plaquette as make_spatial_cube_arm_plaquette
