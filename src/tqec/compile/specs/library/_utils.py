from typing import Literal

from tqec.compile.block import CompiledBlock
from tqec.compile.specs.base import CubeSpec, PipeSpec, Substitution
from tqec.computation.cube import CubeKind, ZXBasis, ZXCube
from tqec.plaquette.enums import (
    MeasurementBasis,
    PlaquetteOrientation,
    PlaquetteSide,
    ResetBasis,
)
from tqec.plaquette.frozendefaultdict import FrozenDefaultDict
from tqec.plaquette.library import PlaquetteBuilder, empty_square_plaquette
from tqec.plaquette.plaquette import Plaquette, Plaquettes
from tqec.position import Direction3D
from tqec.scale import LinearFunction
from tqec.templates.indices.qubit import QubitTemplate

_DEFAULT_BLOCK_REPETITIONS = LinearFunction(2, -1)


def default_compiled_block_builder(
    spec: CubeSpec, *, plaquette_builder: PlaquetteBuilder
) -> CompiledBlock:
    """Default rule for generating a `CompiledBlock` based on a `CubeSpec`."""
    if spec.is_regular:
        assert isinstance(spec.kind, ZXCube)
        return _build_regular_block(
            plaquette_builder,
            spec.kind.z,
            _get_x_boundary_orientation(spec.kind),
        )
    raise NotImplementedError("Irregular cubes are not implemented yet.")


def default_substitution_builder(
    pipe_spec: PipeSpec, *, plaquette_builder: PlaquetteBuilder
) -> Substitution:
    """Default rule for generating a `Substitution` based on a `PipeSpec`."""
    pipe_type = pipe_spec.pipe_kind
    if pipe_type.has_hadamard:
        raise NotImplementedError("Hadamard pipes are not implemented yet.")
    # pipe in time direction
    if pipe_type.direction == Direction3D.Z:
        return _build_substitution_in_time_direction(pipe_spec, plaquette_builder)
    # pipe in space
    return _build_substitution_in_space(pipe_spec, plaquette_builder)


def _build_plaquette_for_different_basis(
    builder: PlaquetteBuilder,
    x_boundary_orientation: Literal["VERTICAL", "HORIZONTAL"],
    *,
    temporal_basis: ZXBasis | None = None,
    data_init: bool = False,
    data_meas: bool = False,
    init_meas_only_on_side: PlaquetteSide | None = None,
) -> tuple[Plaquette, Plaquette]:
    """Build the two type of plaquettes for the bulk of surface code.

    The two plaquettes are in different basis(X/Z) and form the
    checkerboard pattern of the surface code. The two plaquettes are
    returned in a tuple. By convention, the first one of the returned
    tuple is the plaquette at the left top corner of the square bulk of
    surface code.
    """
    b1: Literal["X", "Z"]
    b2: Literal["X", "Z"]
    b1, b2 = ("X", "Z") if x_boundary_orientation == "HORIZONTAL" else ("Z", "X")

    def factory(b: Literal["X", "Z"]) -> Plaquette:
        return builder(
            basis=b,
            data_initialization=ResetBasis(str(temporal_basis)) if data_init else None,
            data_measurement=MeasurementBasis(str(temporal_basis))
            if data_meas
            else None,
            x_boundary_orientation=x_boundary_orientation,
            init_meas_only_on_side=init_meas_only_on_side,
        )

    return factory(b1), factory(b2)


def _build_plaquettes_for_rotated_surface_code(
    builder: PlaquetteBuilder,
    x_boundary_orientation: Literal["VERTICAL", "HORIZONTAL"],
    *,
    temporal_basis: ZXBasis | None = None,
    data_init: bool = False,
    data_meas: bool = False,
    repetitions: LinearFunction | None = None,
) -> Plaquettes:
    """Build the plaquettes for a rotated surface code.

    The plaquettes can be fit into the `QubitTemplate` by the corresponding indices.
    """
    p1, p2 = _build_plaquette_for_different_basis(
        builder,
        x_boundary_orientation,
        temporal_basis=temporal_basis,
        data_init=data_init,
        data_meas=data_meas,
    )
    plaquettes = Plaquettes(
        FrozenDefaultDict(
            {
                6: p1.project_on_boundary(PlaquetteOrientation.UP),
                7: p2.project_on_boundary(PlaquetteOrientation.LEFT),
                9: p1,
                10: p2,
                12: p2.project_on_boundary(PlaquetteOrientation.RIGHT),
                13: p1.project_on_boundary(PlaquetteOrientation.DOWN),
            },
            default_factory=empty_square_plaquette,
        )
    )
    if repetitions is not None:
        plaquettes = plaquettes.repeat(repetitions)
    return plaquettes


def _build_regular_block(
    builder: PlaquetteBuilder,
    temporal_basis: ZXBasis,
    x_boundary_orientation: Literal["VERTICAL", "HORIZONTAL"],
    repetitions: LinearFunction = _DEFAULT_BLOCK_REPETITIONS,
) -> CompiledBlock:
    """Build a compiled block for a regular cube."""
    layers = [
        _build_plaquettes_for_rotated_surface_code(
            builder,
            x_boundary_orientation,
            temporal_basis=temporal_basis,
            data_init=init,
            data_meas=meas,
            repetitions=repeat,
        )
        for init, meas, repeat in [
            (True, False, None),
            (False, False, repetitions),
            (False, True, None),
        ]
    ]
    return CompiledBlock(template=QubitTemplate(), layers=layers)


def _build_substitution_in_time_direction(
    pipe_spec: PipeSpec, plaquette_builder: PlaquetteBuilder
) -> Substitution:
    """Build a substitution for a pipe in the time direction."""
    # substitute the final layer of the src block
    src = {
        -1: _build_plaquettes_for_rotated_surface_code(
            plaquette_builder,
            _get_x_boundary_orientation(pipe_spec.spec1.kind),
        )
    }
    # substitute the first layer of the dst block
    dst = {
        0: _build_plaquettes_for_rotated_surface_code(
            plaquette_builder,
            _get_x_boundary_orientation(pipe_spec.spec2.kind),
        )
    }
    return Substitution(src, dst)


def _build_plaquettes_for_space_regular_pipe(
    builder: PlaquetteBuilder,
    substitution_side: PlaquetteSide,
    x_boundary_orientation: Literal["VERTICAL", "HORIZONTAL"],
    *,
    temporal_basis: ZXBasis | None = None,
    data_init: bool = False,
    data_meas: bool = False,
    repetitions: LinearFunction | None = None,
) -> Plaquettes:
    """Build the plaquettes for a pipe connecting two regular cubes in
    space."""
    p1, p2 = _build_plaquette_for_different_basis(
        builder,
        x_boundary_orientation,
        temporal_basis=temporal_basis,
        data_init=data_init,
        data_meas=data_meas,
        init_meas_only_on_side=substitution_side,
    )
    mapping: dict[int, Plaquette]
    if substitution_side == PlaquetteSide.LEFT:
        mapping = {
            1: p1.project_on_boundary(PlaquetteOrientation.UP),
            7: p2,
            8: p1,
        }
    elif substitution_side == PlaquetteSide.UP:
        mapping = {
            2: p2.project_on_boundary(PlaquetteOrientation.RIGHT),
            5: p2,
            6: p1,
        }
    elif substitution_side == PlaquetteSide.RIGHT:
        mapping = {
            4: p1.project_on_boundary(PlaquetteOrientation.DOWN),
            11: p1,
            12: p2,
        }
    else:  # substitution_side == PlaquetteSide.DOWN
        mapping = {
            3: p2.project_on_boundary(PlaquetteOrientation.LEFT),
            13: p1,
            14: p2,
        }
    plaquettes = Plaquettes(
        FrozenDefaultDict(
            mapping,
            default_factory=empty_square_plaquette,
        )
    )
    if repetitions is not None:
        plaquettes = plaquettes.repeat(repetitions)
    return plaquettes


def _build_substitution_in_space(
    pipe_spec: PipeSpec,
    plaquette_builder: PlaquetteBuilder,
) -> Substitution:
    """Build a substitution for a pipe in space."""
    if pipe_spec.spec1.is_regular and pipe_spec.spec2.is_regular:
        return _build_substitution_in_space_with_regular_cubes(
            pipe_spec, plaquette_builder
        )
    raise NotImplementedError("Pipes between irregular cubes are not implemented yet.")


def _build_substitution_in_space_with_regular_cubes(
    pipe_spec: PipeSpec,
    plaquette_builder: PlaquetteBuilder,
) -> Substitution:
    """Build a substitution for a pipe in space connecting two regular
    cubes."""
    pipe_type = pipe_spec.pipe_kind
    temporal_basis = pipe_type.z
    # No hadamard: the two cubes have the same orientation
    orientation = _get_x_boundary_orientation(pipe_spec.spec1.kind)
    # In `tqec` library, the positive y-axis is the downward direction
    substitute_side1 = (
        PlaquetteSide.RIGHT
        if pipe_spec.pipe_kind.direction == Direction3D.X
        else PlaquetteSide.DOWN
    )
    substitute_side2 = substitute_side1.opposite()

    def build_substitution(side: PlaquetteSide) -> dict[int, Plaquettes]:
        return {
            i: _build_plaquettes_for_space_regular_pipe(
                plaquette_builder,
                side,
                orientation,
                temporal_basis=temporal_basis,
                data_init=data_init,
                data_meas=data_meas,
                repetitions=repetitions,
            )
            for i, (data_init, data_meas, repetitions) in enumerate(
                [
                    (True, False, None),
                    (False, False, _DEFAULT_BLOCK_REPETITIONS),
                    (False, True, None),
                ]
            )
        }

    return Substitution(
        src=build_substitution(substitute_side1),
        dst=build_substitution(substitute_side2),
    )


def _get_x_boundary_orientation(
    cube_kind: CubeKind,
) -> Literal["VERTICAL", "HORIZONTAL"]:
    assert isinstance(cube_kind, ZXCube)
    return "VERTICAL" if cube_kind.x == ZXBasis.X else "HORIZONTAL"
