from tqec import BlockGraph, compile_block_graph
from tqec.compile.blocks.layers.composed.sequenced import SequencedLayers
from tqec.compile.tree.tree import LayerTree
from tqec.utils.position import Position3D


def test_annotate_observable_without_z_coordinate_uses_slice_index() -> None:
    graph = BlockGraph("Memory")
    graph.add_cube(Position3D(0, 0, 0), "ZXZ")
    graph.add_cube(Position3D(0, 0, 1), "ZXZ")
    graph.add_pipe(Position3D(0, 0, 0), Position3D(0, 0, 1))
    tree = compile_block_graph(graph).to_layer_tree()

    root = tree._root._layer
    assert isinstance(root, SequencedLayers)
    slices = [layer for layer in root.layer_sequence if isinstance(layer, SequencedLayers)]
    assert [layer.z_coordinate for layer in slices] == [0, 1]
    hand_built = LayerTree(
        SequencedLayers([SequencedLayers(layer.layer_sequence) for layer in slices]),
        tree._observable_builder,
        tree._abstract_observables,
        slices_with_temporal_hadamard_layer=tree._slices_with_temporal_hadamard_layer,
    )

    # generate_crumble_url with polygons annotates the tree with annotate_observable.
    expected = tree.generate_crumble_url(1, manhattan_radius=-1)
    assert "OI(0)" in expected
    assert hand_built.generate_crumble_url(1, manhattan_radius=-1) == expected
