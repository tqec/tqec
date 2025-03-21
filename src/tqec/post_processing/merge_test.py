import stim

from tqec.post_processing.merge import merge_adjacent_moments


def test_empty() -> None:
    assert merge_adjacent_moments(stim.Circuit()) == stim.Circuit()


def test_no_merge_possible() -> None:
    assert merge_adjacent_moments(stim.Circuit("H 0")) == stim.Circuit("H 0")
    assert merge_adjacent_moments(stim.Circuit("H 0\nTICK\nH 0")) == stim.Circuit(
        "H 0\nTICK\nH 0"
    )
    assert merge_adjacent_moments(
        stim.Circuit("H 0\nTICK\nCX 0 1\nTICK\nH 1")
    ) == stim.Circuit("H 0\nTICK\nCX 0 1\nTICK\nH 1")


def test_merge_possible() -> None:
    assert merge_adjacent_moments(stim.Circuit("H 0\nTICK\nH 1")) == stim.Circuit(
        "H 0 1"
    )
    assert merge_adjacent_moments(
        stim.Circuit("CX 0 1\nTICK\nH 3\nTICK\nCX 2 4")
    ) == stim.Circuit("CX 0 1 2 4\nH 3")


def test_merge_repeat_simple() -> None:
    assert merge_adjacent_moments(
        stim.Circuit(
            """\
REPEAT 3 {
    TICK
    H 0
    TICK
    CX 0 1
    TICK
    H 1
}"""
        )
    ) == stim.Circuit(
        """\
H 0
TICK
CX 0 1
REPEAT 2 {
    TICK
    H 0 1
    TICK
    CX 0 1
}
TICK
H 1
"""
    )
