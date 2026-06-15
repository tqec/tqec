import re

from tqec import Basis, BlockGraph, compile_block_graph
from tqec.compile.convention import FIXED_BOUNDARY_CONVENTION, FIXED_BULK_CONVENTION
from tqec.compile.specs.library.generators.extended_stabilizers import ExtendedPlaquetteCollection
from tqec.gallery.move_rotation import move_rotation
from tqec.utils.position import Position3D
from tqec.visualisation.computation.plaquette.extended import ExtendedPlaquetteDrawer

_EXTENDED_BULK_PATTERN = re.compile(
    r'<rect x="0" y="0" width="1.0" height="1.0" fill="#[0-9a-f]+"/>'
    r'<line stroke="black"[^/]*/><line stroke="grey"'
)


def test_move_rotation_fixed_boundary_layer_renders_extended_plaquettes() -> None:
    """Regression test for #657 using the issue's move_rotation SVG snippet."""
    compiled = compile_block_graph(move_rotation(Basis.Z), FIXED_BOUNDARY_CONVENTION)
    svg_text = compiled.to_layer_tree().layers_to_svg(k=3)[7]

    assert len(_EXTENDED_BULK_PATTERN.findall(svg_text)) >= 2
    assert 'width="0.5" height="1.0"' in svg_text


def test_spatial_hadamard_layer_renders_extended_plaquettes() -> None:
    """Regression test for spatial Hadamard extended stabilisers (#774 / #657)."""
    block_graph = BlockGraph()
    n0 = block_graph.add_cube(Position3D(0, 0, 0), "ZZX", "")
    n1 = block_graph.add_cube(Position3D(0, 1, 0), "XXZ", "")
    block_graph.add_pipe(n0, n1)

    compiled = compile_block_graph(
        block_graph,
        observables=block_graph.find_correlation_surfaces(),
        convention=FIXED_BULK_CONVENTION,
    )
    svg_text = compiled.to_layer_tree().layers_to_svg(k=1)[1]

    assert 'width="1.0" height="1.0" fill' in svg_text
    assert 'stroke="grey"' in svg_text


def test_extended_plaquette_collection_wires_drawers_through_compilation_path() -> None:
    """Extended stabilizer plaquettes used by generators expose the SVG drawer."""
    collection = ExtendedPlaquetteCollection.from_basis(Basis.X, None, None, is_reversed=False)
    for plaquette in (
        collection.bulk,
        collection.bottom_right_triangle,
        collection.bottom_left_triangle,
        collection.top_right_triangle,
    ):
        for part in (plaquette.top, plaquette.bottom):
            assert isinstance(part.debug_information.get_svg_drawer(), ExtendedPlaquetteDrawer)
