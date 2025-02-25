"""Provides an implementation of various standard templates found when using
topological quantum error correction."""

from .hadamard import (
    get_spatial_horizontal_hadamard_plaquettes as get_spatial_horizontal_hadamard_plaquettes,
)
from .hadamard import (
    get_spatial_horizontal_hadamard_raw_template as get_spatial_horizontal_hadamard_raw_template,
)
from .hadamard import (
    get_spatial_vertical_hadamard_plaquettes as get_spatial_vertical_hadamard_plaquettes,
)
from .hadamard import (
    get_spatial_vertical_hadamard_raw_template as get_spatial_vertical_hadamard_raw_template,
)
from .hadamard import (
    get_temporal_hadamard_plaquettes as get_temporal_hadamard_plaquettes,
)
from .hadamard import (
    get_temporal_hadamard_raw_template as get_temporal_hadamard_raw_template,
)
from .memory import (
    get_memory_horizontal_boundary_plaquettes as get_memory_horizontal_boundary_plaquettes,
)
from .memory import (
    get_memory_horizontal_boundary_raw_template as get_memory_horizontal_boundary_raw_template,
)
from .memory import (
    get_memory_qubit_plaquettes as get_memory_qubit_plaquettes,
)
from .memory import (
    get_memory_qubit_raw_template as get_memory_qubit_raw_template,
)
from .memory import (
    get_memory_vertical_boundary_plaquettes as get_memory_vertical_boundary_plaquettes,
)
from .memory import (
    get_memory_vertical_boundary_raw_template as get_memory_vertical_boundary_raw_template,
)
from .spatial import (
    get_spatial_cube_arm_plaquettes as get_spatial_cube_arm_plaquettes,
)
from .spatial import (
    get_spatial_cube_arm_raw_template as get_spatial_cube_arm_raw_template,
)
from .spatial import (
    get_spatial_cube_qubit_plaquettes as get_spatial_cube_qubit_plaquettes,
)
from .spatial import (
    get_spatial_cube_qubit_raw_template as get_spatial_cube_qubit_raw_template,
)
