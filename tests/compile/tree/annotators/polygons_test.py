from typing import Final

from tqec.compile.blocks.layers.atomic.layout import LayoutLayer
from tqec.compile.blocks.layers.atomic.plaquettes import PlaquetteLayer
from tqec.compile.blocks.positioning import LayoutPosition2D
from tqec.compile.tree.annotators.polygons import generate_polygons_for_layout_layer
from tqec.plaquette.debug import DrawPolygon, PlaquetteDebugInformation
from tqec.plaquette.plaquette import Plaquette, Plaquettes
from tqec.plaquette.rpng.rpng import PauliBasis, RPNGDescription
from tqec.plaquette.rpng.translators.default import DefaultRPNGTranslator
from tqec.templates._testing import FixedTemplate
from tqec.utils.frozendefaultdict import FrozenDefaultDict
from tqec.utils.position import BlockPosition2D, Shift2D
from tqec.utils.scale import LinearFunction, PhysicalQubitScalable2D

_TRANSLATOR: Final = DefaultRPNGTranslator()
_EMPTY_PLAQUETTE = _TRANSLATOR.translate(RPNGDescription.empty())
_ELEMENT_SHAPE: Final = PhysicalQubitScalable2D(LinearFunction(4, 5), LinearFunction(4, 5))


def _make_layout_layer(
    plaquette: Plaquette,
    block_x: int = 0,
    block_y: int = 0,
) -> LayoutLayer:
    template = FixedTemplate([[1]])
    plaquette_layer = PlaquetteLayer(
        template,
        Plaquettes(FrozenDefaultDict({2: plaquette}, default_value=_EMPTY_PLAQUETTE)),
    )
    position = LayoutPosition2D.from_block_position(BlockPosition2D(block_x, block_y))
    return LayoutLayer({position: plaquette_layer}, _ELEMENT_SHAPE)


def test_empty_plaquette_produces_no_polygons() -> None:
    layer = _make_layout_layer(_EMPTY_PLAQUETTE)

    assert generate_polygons_for_layout_layer(layer, 1) == []


def test_plaquette_without_polygon_information_produces_no_polygons() -> None:
    plaquette = _TRANSLATOR.translate(RPNGDescription.from_string("-x1- -z2- -x3- -z4-"))
    layer = _make_layout_layer(plaquette)

    assert generate_polygons_for_layout_layer(layer, 1) == []


def test_explicit_polygon_information_is_preserved() -> None:
    plaquette = _TRANSLATOR.translate(RPNGDescription.from_string("-x1- -x2- -x3- -x4-"))
    qubits = list(plaquette.qubits.data_qubits)

    plaquette = type(plaquette)(
        plaquette.name,
        plaquette.qubits,
        plaquette.circuit,
        plaquette.mergeable_instructions,
        PlaquetteDebugInformation(draw_polygons=DrawPolygon({PauliBasis.X: qubits})),
    )

    layer = _make_layout_layer(plaquette)
    polygons = generate_polygons_for_layout_layer(layer, 1)

    assert len(polygons) == 1
    assert polygons[0].basis == PauliBasis.X
    assert polygons[0].qubits == frozenset(qubits)


def test_single_basis_rpng_generates_polygon_automatically() -> None:
    plaquette = _TRANSLATOR.translate(RPNGDescription.from_string("-x1- -x2- -x3- -x4-"))
    layer = _make_layout_layer(plaquette)

    polygons = generate_polygons_for_layout_layer(layer, 1)

    assert len(polygons) == 1
    assert polygons[0].basis == PauliBasis.X
    assert polygons[0].qubits == frozenset(plaquette.qubits.data_qubits)


def test_polygon_coordinates_include_layout_offset() -> None:
    plaquette = _TRANSLATOR.translate(RPNGDescription.from_string("-x1- -x2- -x3- -x4-"))
    qubits = frozenset(plaquette.qubits.data_qubits)
    layer = _make_layout_layer(plaquette, block_x=1, block_y=2)

    polygons = generate_polygons_for_layout_layer(layer, 1)

    assert len(polygons) == 1
    assert polygons[0].basis == PauliBasis.X
    expected_qubits = frozenset(q + Shift2D(8, 16) for q in qubits)
    assert polygons[0].qubits == expected_qubits


def test_explicit_polygons_support_multiple_bases() -> None:
    plaquette = _TRANSLATOR.translate(RPNGDescription.from_string("-x1- -x2- -x3- -x4-"))
    qubits = list(plaquette.qubits.data_qubits)

    plaquette = type(plaquette)(
        plaquette.name,
        plaquette.qubits,
        plaquette.circuit,
        plaquette.mergeable_instructions,
        PlaquetteDebugInformation(
            draw_polygons=DrawPolygon(
                {
                    PauliBasis.X: qubits[:2],
                    PauliBasis.Z: qubits[2:],
                }
            )
        ),
    )

    layer = _make_layout_layer(plaquette)
    polygons = generate_polygons_for_layout_layer(layer, 1)

    assert len(polygons) == 2
    polygons_by_basis = {polygon.basis: polygon.qubits for polygon in polygons}
    assert polygons_by_basis[PauliBasis.X] == frozenset(qubits[:2])
    assert polygons_by_basis[PauliBasis.Z] == frozenset(qubits[2:])
