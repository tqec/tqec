import itertools

import pytest

from tqec.compile.blocks.layers.atomic.plaquettes import PlaquetteLayer
from tqec.compile.blocks.layers.composed.repeated import RepeatedLayer
from tqec.compile.blocks.layers.composed.sequenced import SequencedLayers
from tqec.compile.specs.base import CubeSpec, YHalfCubeSpec
from tqec.compile.specs.library.generators.y_basis_fixed_bulk import (
    _role_map,
    _YRoundTemplate,
    get_y_half_cube_block,
    y_corner_local_coord,
    y_observable_local_coords,
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


_ROUND_PARAMS = list(itertools.product(("X", "Z"), ("switch", "pad", "final"), (False, True)))


def test_y_round_templates_compare_by_parameters() -> None:
    # ``PlaquetteLayer.__eq__`` compares templates, so templates of different rounds must differ.
    templates = [_YRoundTemplate(*params) for params in _ROUND_PARAMS]  # type: ignore[arg-type]
    for a, b in itertools.combinations(templates, 2):
        assert a != b
    for params in _ROUND_PARAMS:
        a = _YRoundTemplate(*params)  # type: ignore[arg-type]
        b = _YRoundTemplate(*params)  # type: ignore[arg-type]
        assert a == b
        assert hash(a) == hash(b)


def _round_of(layer: object) -> tuple[str, bool]:
    assert isinstance(layer, PlaquetteLayer)
    template = layer.template
    assert isinstance(template, _YRoundTemplate)
    return template.kind, template._reverse


@pytest.mark.parametrize(("basis", "top"), [(Basis.X, "X"), (Basis.Z, "Z")])
def test_initialization_half_cube_is_the_time_reversed_measurement(basis: Basis, top: str) -> None:
    spec = YHalfCubeSpec(horizontal_boundary_basis=basis, initialization=True)
    block = get_y_half_cube_block(spec, pad_repetitions=LinearFunction(2, -1))
    final, pad, switch = block.layer_sequence
    assert _round_of(final) == ("final", True)
    assert isinstance(pad, RepeatedLayer)
    assert pad.repetitions == LinearFunction(2, -1)
    assert _round_of(pad.internal_layer) == ("pad", True)
    assert _round_of(switch) == ("switch", True)
    for layer in (final, pad.internal_layer, switch):
        assert isinstance(layer, PlaquetteLayer)
        assert isinstance(layer.template, _YRoundTemplate)
        assert layer.template.top == top


@pytest.mark.parametrize("params", _ROUND_PARAMS)
def test_y_round_template_instantiates_within_its_plaquette_indices(params: tuple) -> None:
    template = _YRoundTemplate(*params)  # type: ignore[arg-type]
    array = template.instantiate(1)
    # ``scalable_shape`` is ``2k + 2`` plaquettes on each side.
    assert array.shape == (4, 4)
    assert array.min() >= 0
    assert array.max() <= template.expected_plaquettes_number
    assert array.max() > 0


# At d = 3 the code gives, in patch coordinates (local coordinates are these plus (1, 1)):
# - the corner ``MY`` target ``(0, d - 1)`` for an X top and ``(d - 1, 0)`` for a Z top;
# - the upper-right measure qubits (real > 1, imag < 1) that are on the top row or measure the
#   basis other than the top one: (1.5, -0.5) and (2.5, 0.5) for X, (1.5, -0.5) and (1.5, 0.5)
#   for Z, as ``_checkerboard_basis`` gives X when ``int(real + imag)`` is even and Z otherwise;
# - the lower-left measure qubits (real < 1, imag > 1) that are on the left column or measure the
#   top basis: (-0.5, 1.5) and (0.5, 1.5) for X, (-0.5, 1.5) and (0.5, 2.5) for Z.
@pytest.mark.parametrize(
    ("top", "corner", "others"),
    [
        ("X", (1.0, 3.0), {(2.5, 0.5), (3.5, 1.5), (0.5, 2.5), (1.5, 2.5)}),
        ("Z", (3.0, 1.0), {(2.5, 0.5), (2.5, 1.5), (0.5, 2.5), (1.5, 3.5)}),
    ],
)
def test_y_observable_local_coords_at_distance_3(
    top: str, corner: tuple[float, float], others: set[tuple[float, float]]
) -> None:
    assert y_corner_local_coord(3, top) == corner  # type: ignore[arg-type]
    coords = y_observable_local_coords(3, top)  # type: ignore[arg-type]
    assert len(coords) == len(set(coords))
    assert set(coords) == {corner} | others
