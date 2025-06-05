import stim

from tqec.post_processing.remove import remove_empty_moments


def test_trivial() -> None:
    assert remove_empty_moments(stim.Circuit()) == stim.Circuit()
    assert remove_empty_moments(stim.Circuit("TICK")) == stim.Circuit()
    assert remove_empty_moments(stim.Circuit("TICK\nTICK")) == stim.Circuit()
    assert (
        remove_empty_moments(stim.Circuit("\n".join("TICK" for _ in range(890)))) == stim.Circuit()
    )


def test_single_gate() -> None:
    assert remove_empty_moments(stim.Circuit("TICK\nH 0\nTICK")) == stim.Circuit("H 0")
    assert remove_empty_moments(stim.Circuit("TICK\nCX 0 1\nTICK")) == stim.Circuit("CX 0 1")


def test_remove_leading_trailing_tick() -> None:
    c = stim.Circuit("TICK\nH 0\nTICK")
    assert remove_empty_moments(c, remove_leading_tick=False) == stim.Circuit("TICK\nH 0")
    assert remove_empty_moments(c, remove_trailing_tick=False) == stim.Circuit("H 0\nTICK")
    assert remove_empty_moments(
        c, remove_trailing_tick=False, remove_leading_tick=False
    ) == stim.Circuit("TICK\nH 0\nTICK")


def test_within_circuit() -> None:
    assert remove_empty_moments(stim.Circuit("TICK\nH 0\nTICK\nTICK\nH 1")) == stim.Circuit(
        "H 0\nTICK\nH 1"
    )


def test_repeat_block_conventions() -> None:
    assert remove_empty_moments(
        stim.Circuit("H 0\nTICK\nREPEAT 5 {\nH 0\nTICK\n}\nTICK\nH 0")
    ) == stim.Circuit("H 0\nREPEAT 5 {\nTICK\nH 0\n}\nTICK\nH 0")
