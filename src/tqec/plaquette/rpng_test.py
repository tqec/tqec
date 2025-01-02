import pytest
from stim import Circuit

from tqec.plaquette.qubit import SquarePlaquetteQubits
from tqec.plaquette.rpng import RPNGDescription


def test_validate_plaquette_from_rpng_string() -> None:
    # Invalid plaquettes
    rpng_errors = [
        "---- ---- ----",  # wrong length of values
        "---- ---- --- ----",  # wrong length of values
        "-z1- -z4- -z3- -z4-",  # wrong times for the 2Q gates
        "-z1- -z0- -z3- -z4-",  # wrong times for the 2Q gates
    ]
    # Valid plaquettes
    rpng_examples = [
        "---- ---- ---- ----",
        "-z1- -z2- -z3- -z4-",
        "-z5- -x2- -x3- -z1-",
        "-x5h -z2z -x3x hz1-",
        "-z1- -z2- ---- -z4-",
    ]
    for rpng in rpng_errors:
        with pytest.raises(ValueError):
            RPNGDescription.from_string(corners_rpng_string=rpng)
    for rpng in rpng_examples:
        RPNGDescription.from_string(corners_rpng_string=rpng)
    # With explicit RG string for the ancilla qubit.
    rpng_errors = [
        "zz -z1- -z0- -z5- -z4-",  # wrong times for the 2Q gates
        "zz -z1- -z2- -z4- -z4-",  # wrong times for the 2Q gates
    ]
    for rpng in rpng_errors:
        with pytest.raises(ValueError):
            RPNGDescription.from_extended_string(ancilla_and_corners_rpng_string=rpng)


def test_rpng_description_visualization() -> None:
    rpng = RPNGDescription.from_string("-z1h zz2x -z3h zz4x")
    svg_str = rpng.view_as_svg()

    expected_svg = """<svg viewBox="0 0 100 100" xmlns="http://www.w3.org/2000/svg">
<clipPath id="clipPath0">
    <path d="M 33.333333333333336,66.66666666666667 L 33.333333333333336,33.333333333333336 L 66.66666666666667,33.333333333333336 L 66.66666666666667,66.66666666666667 L 33.333333333333336,66.66666666666667 "/>
</clipPath>
<rect clip-path="url(#clipPath0)" x="33.333333333333336" y="33.333333333333336" width="16.666666666666664" height="16.666666666666664" fill="#7396ff" opacity="1.0" stroke="none"/>
<rect clip-path="url(#clipPath0)" x="50.0" y="33.333333333333336" width="16.66666666666667" height="16.666666666666664" fill="#7396ff" opacity="1.0" stroke="none"/>
<rect clip-path="url(#clipPath0)" x="33.333333333333336" y="50.0" width="16.666666666666664" height="16.66666666666667" fill="#7396ff" opacity="1.0" stroke="none"/>
<rect clip-path="url(#clipPath0)" x="50.0" y="50.0" width="16.66666666666667" height="16.66666666666667" fill="#7396ff" opacity="1.0" stroke="none"/>
<path d="M 33.333333333333336,66.66666666666667 L 33.333333333333336,33.333333333333336 L 66.66666666666667,33.333333333333336 L 66.66666666666667,66.66666666666667 L 33.333333333333336,66.66666666666667 " fill="none" stroke="black" stroke-width="0.8333333333333335"/>
<rect x="63.833333333333336" y="30.5" width="5.666666666666668" height="5.666666666666668" fill="#7396ff" stroke="black" stroke-width="0.5"/>
<rect x="63.833333333333336" y="63.833333333333336" width="5.666666666666668" height="5.666666666666668" fill="#7396ff" stroke="black" stroke-width="0.5"/>
<circle cx="33.333333333333336" cy="33.333333333333336" r="2.0" fill="#ffff65" stroke="black" stroke-width="0.5"/>
<circle cx="66.66666666666667" cy="33.333333333333336" r="2.0" fill="#ff7f7f" stroke="black" stroke-width="0.5"/>
<circle cx="33.333333333333336" cy="66.66666666666667" r="2.0" fill="#ffff65" stroke="black" stroke-width="0.5"/>
<circle cx="66.66666666666667" cy="66.66666666666667" r="2.0" fill="#ff7f7f" stroke="black" stroke-width="0.5"/>
<text x="38.333333333333336" y="38.333333333333336" fill="black" font-size="6.666666666666668" text-anchor="middle" dominant-baseline="central">1</text>
<text x="61.66666666666667" y="38.333333333333336" fill="black" font-size="6.666666666666668" text-anchor="middle" dominant-baseline="central">2</text>
<text x="38.333333333333336" y="61.66666666666667" fill="black" font-size="6.666666666666668" text-anchor="middle" dominant-baseline="central">3</text>
<text x="61.66666666666667" y="61.66666666666667" fill="black" font-size="6.666666666666668" text-anchor="middle" dominant-baseline="central">4</text>
</svg>"""

    assert svg_str == expected_svg
