import pytest

from tqec.compile.blocks.layers.composed.repeated import RepeatedLayer
from tqec.compile.blocks.layers.composed.sequenced import SequencedLayers
from tqec.compile.specs.base import CubeSpec, YHalfCubeSpec
from tqec.compile.specs.library.generators.y_basis_fixed_bulk import (
    _role_map,
    get_y_half_cube_block,
)
from tqec.computation.block_graph import BlockGraph
from tqec.computation.cube import LeafCubeKind
from tqec.utils.enums import Basis
from tqec.utils.exceptions import TQECError
from tqec.utils.position import Position3D
from tqec.utils.scale import LinearFunction


def test_measurement_half_cube_emits_first_pad_round_outside_the_repetition() -> None:
    spec = YHalfCubeSpec(
        horizontal_boundary_basis=Basis.Z,
        initialization=False,
    )
    block = get_y_half_cube_block(spec, pad_repetitions=LinearFunction(2, -1))
    _, pad, _ = block.layer_sequence
    assert isinstance(pad, SequencedLayers)
    _, repeated_pad = pad.layer_sequence
    assert isinstance(repeated_pad, RepeatedLayer)
    assert repeated_pad.repetitions == LinearFunction(2, -2)
    # The temporal schedule is the one of an ordinary cube, so that blocks can be merged.
    assert [layer.scalable_timesteps for layer in block.layer_sequence] == [
        LinearFunction(0, 1),
        LinearFunction(2, -1),
        LinearFunction(0, 1),
    ]


def test_constant_pad_repetitions_below_one_are_rejected() -> None:
    spec = YHalfCubeSpec(horizontal_boundary_basis=Basis.Z, initialization=False)
    with pytest.raises(ValueError, match="at least one PAD round"):
        get_y_half_cube_block(spec, pad_repetitions=LinearFunction(0, 0))


@pytest.mark.parametrize(("pipe_kind", "basis"), [("ZXO", Basis.X), ("XZO", Basis.Z)])
def test_y_half_cube_spec_from_cube(pipe_kind: str, basis: Basis) -> None:
    g = BlockGraph()
    bottom = g.add_cube(Position3D(0, 0, 0), "Y")
    top = g.add_cube(Position3D(0, 0, 1), "Y")
    g.add_pipe(bottom, top, pipe_kind)
    assert YHalfCubeSpec.from_cube(g[bottom], g) == YHalfCubeSpec(True, basis)
    assert YHalfCubeSpec.from_cube(g[top], g) == YHalfCubeSpec(False, basis)
    spec = CubeSpec.from_cube(g[top], g)
    assert spec.is_y_cube
    assert spec.y_half_cube_spec == YHalfCubeSpec(False, basis)


def test_cube_spec_requires_y_half_cube_spec_for_y_cubes() -> None:
    with pytest.raises(TQECError, match="y_half_cube_spec"):
        CubeSpec(LeafCubeKind.Y_HALF_CUBE)


@pytest.mark.parametrize("kind", ["switch", "pad", "final"])
@pytest.mark.parametrize("reverse", [False, True])
def test_y_plaquette_names_differ_between_orientations(kind: str, reverse: bool) -> None:
    # Plaquette equality and the detector database key on the name, so two different circuits
    # must never share one.
    _, x_top = _role_map("X", kind, reverse)  # type: ignore[arg-type]
    _, z_top = _role_map("Z", kind, reverse)  # type: ignore[arg-type]
    x_names = {p.name for p in x_top.values()}
    z_names = {p.name for p in z_top.values()}
    assert x_names.isdisjoint(z_names)
