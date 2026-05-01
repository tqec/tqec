from pathlib import Path

import pytest

from tqec.interop.bgraph.read_write import load_bgraph, write_bgraph
from tqec.utils.enums import Basis
from tqec.utils.exceptions import TQECError


@pytest.mark.parametrize(
    "input",
    [{0: "this is this", 1: "that is that"}, "common string", "BLOCKGRAPH but misformatted"],
)
def test_load_bgraph_rejects_invalid_input(input) -> None:
    with pytest.raises((AttributeError, AssertionError, TQECError, TypeError)):
        _ = load_bgraph(input)


@pytest.mark.parametrize("test_type", ["filepath"])
def test_bgraph_load_write(test_type: str) -> None:

    # Parse from assets file
    graph_name = "cnots"
    assets_folder = Path(__file__).parent.parent.parent.parent / "assets"
    filepath = assets_folder / f"{graph_name}.bgraph"

    # Load
    if test_type == "filepath":
        graph = load_bgraph(filepath)
    elif test_type == "str_of_filepath":
        graph = load_bgraph(str(filepath))
    else:
        with open(filepath) as f:
            bgraph_str = f.read()
        graph = load_bgraph(bgraph_str)

    # Write to string
    bgraph_out_str = write_bgraph(
        graph,
        graph_name=graph_name,
    )

    # Re-load and compare
    # String comparison not possible: IDs can change if source/output not by/from same tool
    graph_re = load_bgraph(bgraph_out_str)
    assert graph == graph_re


@pytest.mark.parametrize(
    "test_name, input_data, expected_success",
    [
        # INPUT DATA FORMAT: (source, name, cube line, pipe line, label)
        # METADATA LENIENCE
        # Expect computation to be correct despite blockgraph ending up with an ugly name.
        ("bad_source", ("tq;ec;", ";er;ts", "0;0;0;0;ZXX;;", "0;1;ZXO;", ""), True),
        ("spaced_source", ("tq ec;", ";er;ts", "0;0;0;0;ZXX;;", "0;1;ZXO;", ""), True),
        ("punctuated_source", ("t.q;e,c;", ";er;ts", "0;0;0;0;ZXX;;", "0;1;ZXO;", ""), True),
        ("bad_name", ("tqec", ";er;ts", "0;0;0;0;ZXX;;", "0;1;ZXO;", ""), True),
        ("other_bad_name", ("tqec", "circuit_name", "0;0;0;0;ZXX;;", "0;1;ZXO;", ""), True),
        ("spaced_name", ("tqec", "cir cuit _n ame", "0;0;0;0;ZXX;;", "0;1;ZXO;", ""), True),
        ("punctuated_name", ("tqec", "c.i,,rc-u*it_name..", "0;0;0;0;ZXX;;", "0;1;ZXO;", ""), True),
        ("pipe_name", ("tqec", "pipe_length", "0;0;0;0;ZXX;;", "0;1;ZXO;", ""), True),
        ("float_id", ("tqec", "circuit", "4.5;0;0;0;ZXX;;", "4.5;1;ZXO;", ""), True),
        ("string_id", ("tqec", "circuit", "FOur;0;0;0;ZXX;;", "FOur;1;ZXO;", ""), True),
        ("terribly_bad_name", ("tqec", ";;;;;;;", "FOur;0;0;0;ZXX;;", "FOur;1;ZXO;", ""), True),
        (
            "bad_source_and_name",
            ("pipe_length;", "circuit_name", "0;0;0;0;ZXX;;", "0;1;ZXO;", ""),
            True,
        ),
        # STRUCTURAL INTEGRITY
        # Expect failure due to malforming of critical fields.
        ("float_pos", ("TQEC", "bad", "0;0;0.0;0;ZXX;;", "0;(0, 0, 8);ZXO;", ""), False),
        ("non_numeric_pos", ("TQEC", "bad", "0;abc;0;0;ZXX;;", "0;(0, 0, 8);ZXO;", ""), False),
        # FORMATTING INTEGRITY
        # Expect failure due to malforming of critical fields.
        ("less_fields_cube", ("TQEC", "pretty", "0;0;0;0;ZXX;", "0;1;ZXO;", ""), False),
        ("less_fields_pipe", ("TQEC", "good", "0;0;0;0;ZXX;;", "0;(0, 0, 8);", ""), False),
        ("extra_fields_cube", ("TQEC", "pretty", "0;0;;0;0;ZXX;;", "0;1;ZXO;", ""), False),
        ("extra_fields_pipe", ("TQEC", "good", "0;0;0;0;ZXX;;", "0;;(0, 0, 8);ZXO;", ""), False),
        # SEMANTIC
        # Failures due to missing critical info
        ("unknown_cube_kind", ("tqec", "circui", "0;0;0;0;invalid_kind;;", "0;1;ZXO;", ""), False),
        (
            "dangerous_cube_kind",
            ("tqec", "circui", "0;0;0;0;circuit_name;;", "0;1;ZXO;", ""),
            False,
        ),
        ("unknown_pipe_kind", ("tqec", "circui", "0;0;0;0;invalid_kind;;", "0;1;abc;", ""), False),
        (
            "dangerous_pipe_kind",
            ("tqec", "circui", "0;0;0;0;invalid_kind;;", "0;1;pipe_length;", ""),
            False,
        ),
        ("loop_pipe", ("tq;ec;", "circuit", "0;0;0;0;ZXX;;", "0;0;ZXO;", ""), False),
    ],
)
def test_bgraph_parse_robustness(
    test_name: str, input_data: list[str], expected_success: bool
) -> None:

    from tqec.gallery.move_rotation import move_rotation  # noqa: PLC0415

    # Parse from assets file
    source_str, circuit_str, cube_item, pipe_item, label_item = input_data

    # Small example to test comms between blockgraph and loader/writer
    # The actual read/write operation is tested elsewhere
    reference_graph = move_rotation(Basis.X)

    bgraph_str = f"""BLOCKGRAPH 0.1.0;
    METADATA: attr_name; value;
    source; {source_str}.
    circuit_name; {circuit_str};

    CUBES: index;x;y;z;kind;label;
    {cube_item}
    1;0;0;1;ZXX;;
    2;0;1;1;ZZX;;
    3;1;1;1;XZX;{label_item};
    4;1;1;2;XZX;;

    PIPES: src;tgt;kind;
    {pipe_item}
    1;2;ZOX;
    2;3;OZX;
    3;4;XZO;
    """

    if test_name in [
        "bad_source",
        "spaced_source",
        "punctuated_source",
        "bad_name",
        "other_bad_name",
        "spaced_name",
        "punctuated_name",
        "pipe_name",
        "float_id",
        "string_id",
        "terribly_bad_name",
        "bad_source_and_name",
    ]:
        graph = load_bgraph(bgraph_str)
        assert graph == reference_graph
    else:
        with pytest.raises(TQECError):
            graph = load_bgraph(bgraph_str)
