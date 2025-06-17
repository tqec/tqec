from collections.abc import Sequence

import stim
import svg

from tqec.circuit.qubit import GridQubit
from tqec.visualisation.exception import TQECDrawingException


def _get_error_cross_svg(
    size: float = 1, stroke_color: str = "red", stroke_width_multiplier: float = 0.2
) -> svg.Element:
    """Returns a SVG element representing an error."""
    return svg.Path(
        d=[
            svg.M(-size / 2, -size / 2),
            svg.L(size / 2, size / 2),
            svg.M(-size / 2, size / 2),
            svg.L(size / 2, -size / 2),
        ],
        stroke=stroke_color,
        stroke_width=size * stroke_width_multiplier,
    )


def get_errors_svg(
    errors: Sequence[stim.ExplainedError],
    top_left_qubit: GridQubit,
    plaquette_width: float,
    plaquette_height: float,
    size: float = 1,
    stroke_color: str = "red",
    stroke_width_multiplier: float = 0.2,
) -> svg.G:
    """Returns an SVG element with the provided ``errors`` drawn and a transparent
    background.

    Args:
        errors: a sequence of errors to plot. It is often desirable to filter
            errors according to the moment they appear in.
        plaquette_width:
        plaquette_height:
        size:
        stroke_color:
        stroke_width_multiplier:

    """
    width_between_qubits: float = plaquette_width / 2
    height_between_qubits: float = plaquette_height / 2
    cross_svg = _get_error_cross_svg(size, stroke_color, stroke_width_multiplier)
    crosses: list[svg.Element] = []
    for error in errors:
        # Get the x and y coordinates in qubit-coordinates.
        location = error.circuit_error_locations[0]
        flipped_measurement = location.flipped_measurement
        flipped_pauli_product = location.flipped_pauli_product
        if flipped_pauli_product:
            qx, qy = flipped_pauli_product[0].coords
        elif flipped_measurement:
            qx, qy = flipped_measurement.observable[0].coords
        else:
            raise TQECDrawingException("Could not draw the following error:\n" + str(error))
        # Make the coordinates relative to the top-left qubit.
        qx -= top_left_qubit.x
        qy -= top_left_qubit.y
        # Plot the cross.
        crosses.append(
            svg.G(
                elements=[cross_svg],
                transform=[svg.Translate(qx * width_between_qubits, qy * height_between_qubits)],
            )
        )
    return svg.G(elements=crosses)
