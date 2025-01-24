"""Internal module defining a few useful functions to test the template library."""

from tqec.compile.specs.enums import SpatialArms
from tqec.enums import Basis
from tqec.templates.enums import ZObservableOrientation
from tqec.templates.indices.qubit import (
    QubitHorizontalBorders,
    QubitSpatialCubeTemplate,
    QubitTemplate,
    QubitVerticalBorders,
)
from tqec.templates.library.hadamard import (
    get_spatial_horizontal_hadamard_raw_template,
    get_spatial_horizontal_hadamard_rpng_descriptions,
    get_spatial_vertical_hadamard_raw_template,
    get_spatial_vertical_hadamard_rpng_descriptions,
    get_temporal_hadamard_raw_template,
    get_temporal_hadamard_rpng_descriptions,
)
from tqec.templates.library.memory import (
    get_memory_horizontal_boundary_raw_template,
    get_memory_horizontal_boundary_rpng_descriptions,
    get_memory_qubit_raw_template,
    get_memory_qubit_rpng_descriptions,
    get_memory_vertical_boundary_raw_template,
    get_memory_vertical_boundary_rpng_descriptions,
)
from tqec.templates.library.spatial import (
    get_spatial_cube_arm_raw_template,
    get_spatial_cube_arm_rpng_descriptions,
    get_spatial_cube_qubit_raw_template,
    get_spatial_cube_qubit_rpng_descriptions,
)
from tqec.templates.rpng import RPNGTemplate


def get_temporal_hadamard_rpng_template(
    orientation: ZObservableOrientation = ZObservableOrientation.HORIZONTAL,
) -> RPNGTemplate[QubitTemplate]:
    return RPNGTemplate(
        template=get_temporal_hadamard_raw_template(),
        mapping=get_temporal_hadamard_rpng_descriptions(orientation),
    )


def get_spatial_horizontal_hadamard_rpng_template(
    top_left_is_z_stabilizer: bool,
    reset: Basis | None = None,
    measurement: Basis | None = None,
) -> RPNGTemplate[QubitHorizontalBorders]:
    return RPNGTemplate(
        template=get_spatial_horizontal_hadamard_raw_template(),
        mapping=get_spatial_horizontal_hadamard_rpng_descriptions(
            top_left_is_z_stabilizer, reset, measurement
        ),
    )


def get_spatial_vertical_hadamard_rpng_template(
    top_left_is_z_stabilizer: bool,
    reset: Basis | None = None,
    measurement: Basis | None = None,
) -> RPNGTemplate[QubitVerticalBorders]:
    return RPNGTemplate(
        template=get_spatial_vertical_hadamard_raw_template(),
        mapping=get_spatial_vertical_hadamard_rpng_descriptions(
            top_left_is_z_stabilizer, reset, measurement
        ),
    )


def get_memory_qubit_rpng_template(
    orientation: ZObservableOrientation = ZObservableOrientation.HORIZONTAL,
    reset: Basis | None = None,
    measurement: Basis | None = None,
) -> RPNGTemplate[QubitTemplate]:
    return RPNGTemplate(
        template=get_memory_qubit_raw_template(),
        mapping=get_memory_qubit_rpng_descriptions(orientation, reset, measurement),
    )


def get_memory_vertical_boundary_rpng_template(
    orientation: ZObservableOrientation = ZObservableOrientation.HORIZONTAL,
    reset: Basis | None = None,
    measurement: Basis | None = None,
) -> RPNGTemplate[QubitVerticalBorders]:
    return RPNGTemplate(
        template=get_memory_vertical_boundary_raw_template(),
        mapping=get_memory_vertical_boundary_rpng_descriptions(
            orientation, reset, measurement
        ),
    )


def get_memory_horizontal_boundary_rpng_template(
    orientation: ZObservableOrientation = ZObservableOrientation.HORIZONTAL,
    reset: Basis | None = None,
    measurement: Basis | None = None,
) -> RPNGTemplate[QubitHorizontalBorders]:
    return RPNGTemplate(
        template=get_memory_horizontal_boundary_raw_template(),
        mapping=get_memory_horizontal_boundary_rpng_descriptions(
            orientation, reset, measurement
        ),
    )


def get_spatial_cube_qubit_rpng_template(
    spatial_boundary_basis: Basis,
    arms: SpatialArms,
    reset: Basis | None = None,
    measurement: Basis | None = None,
) -> RPNGTemplate[QubitSpatialCubeTemplate]:
    return RPNGTemplate(
        template=get_spatial_cube_qubit_raw_template(),
        mapping=get_spatial_cube_qubit_rpng_descriptions(
            spatial_boundary_basis, arms, reset, measurement
        ),
    )


def get_spatial_cube_arm_rpng_template(
    spatial_boundary_basis: Basis,
    arm: SpatialArms,
    reset: Basis | None = None,
    measurement: Basis | None = None,
) -> RPNGTemplate[QubitVerticalBorders | QubitHorizontalBorders]:
    return RPNGTemplate(
        template=get_spatial_cube_arm_raw_template(arm),
        mapping=get_spatial_cube_arm_rpng_descriptions(
            spatial_boundary_basis, arm, reset, measurement
        ),
    )
