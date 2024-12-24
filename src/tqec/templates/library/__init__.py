"""Provides an implementation of various standard templates found when using
topological quantum error correction."""

from .hadamard import (
    get_spatial_horizontal_hadamard_template as get_spatial_horizontal_hadamard_template,
)
from .hadamard import (
    get_spatial_vertical_hadamard_template as get_spatial_vertical_hadamard_template,
)
from .hadamard import get_temporal_hadamard_template as get_temporal_hadamard_template
from .memory import (
    get_memory_horizontal_boundary_template as get_memory_horizontal_boundary_template,
)
from .memory import get_memory_qubit_template as get_memory_qubit_template
from .memory import (
    get_memory_vertical_boundary_template as get_memory_vertical_boundary_template,
)
