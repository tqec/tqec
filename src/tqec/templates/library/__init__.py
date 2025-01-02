"""Provides an implementation of various standard templates found when using
topological quantum error correction."""

from .hadamard import (
    get_spatial_horizontal_hadamard_rpng_template as get_spatial_horizontal_hadamard_rpng_template,
)
from .hadamard import (
    get_spatial_vertical_hadamard_rpng_template as get_spatial_vertical_hadamard_rpng_template,
)
from .hadamard import (
    get_temporal_hadamard_rpng_template as get_temporal_hadamard_rpng_template,
)
from .memory import (
    get_memory_horizontal_boundary_rpng_template as get_memory_horizontal_boundary_rpng_template,
)
from .memory import get_memory_qubit_rpng_template as get_memory_qubit_rpng_template
from .memory import (
    get_memory_vertical_boundary_rpng_template as get_memory_vertical_boundary_rpng_template,
)
from .spatial import (
    get_spatial_junction_arm_template as get_spatial_junction_arm_template,
)
from .spatial import (
    get_spatial_junction_qubit_rpng_template as get_spatial_junction_qubit_rpng_template,
)
