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


def _get_coordinates(
    targets: list[stim.GateTargetWithCoords],
) -> tuple[float, float, float | None, float | None]:
    match len(targets):
        case 1:
            qx, qy = targets[0].coords
            return qx, qy, None, None
        case 2:
            qx, qy = targets[0].coords
            qx2, qy2 = targets[1].coords
            return qx, qy, qx2, qy2
        case 0:
            raise TQECDrawingException("Could not extract coordinates from an empty list.")
        case _:
            raise TQECDrawingException(
                f"Could not extract coordinates from a list with {len(targets)}."
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
        top_left_qubit: coordinates of the qubit at the very top-left of the
            visualisation canva. Used to correctly offset qubit values from the
            provided ``errors``.
        plaquette_width: width (in SVG dimensions) of a regular square plaquette.
        plaquette_height: height (in SVG dimensions) of a regular square plaquette.
        size: size (in SVG dimensions) of the crosses used to mark errors.
        stroke_color: color used to draw the crosses representing each error.
        stroke_width_multiplier: multiplier applied to ``size`` to get the stroke
            width used to draw the crosses representing errors.

    Returns:
        a SVG element containing as many sub-elements as there are errors in the
        provided ``errors`` list, each representing one of the provided errors.

    Raises:
        TQECDrawingError: if at least one of the provided ``errors`` has both an
            empty ``flipped_measurement`` list AND an empty ``flipped_pauli_product``
            list.

    """
    width_between_qubits: float = plaquette_width / 2
    height_between_qubits: float = plaquette_height / 2
    cross_svg = _get_error_cross_svg(size, stroke_color, stroke_width_multiplier)
    crosses: list[svg.Element] = []
    for error in errors:
        # We take the first error location. All the error locations in error.circuit_error_locations
        # are valid and could be picked, but we need to take one here.
        location = error.circuit_error_locations[0]
        # Get the x and y coordinates in qubit-coordinates.
        # For 2-qubit errors, we get also the second qubit x and y coordinates.
        flipped_measurement = location.flipped_measurement
        flipped_pauli_product = location.flipped_pauli_product
        if flipped_pauli_product:
            qx, qy, qx2, qy2 = _get_coordinates(flipped_pauli_product)
        elif flipped_measurement:
            qx, qy, qx2, qy2 = _get_coordinates(flipped_measurement.observable)
        else:
            raise TQECDrawingException("Could not draw the following error:\n" + str(error))
        # Make the coordinates relative to the top-left qubit.
        qx -= top_left_qubit.x
        qy -= top_left_qubit.y
        # Plot the cross for a single-qubit error.
        error_svg: list[svg.Element] = [
            svg.G(
                elements=[cross_svg],
                transform=[svg.Translate(qx * width_between_qubits, qy * height_between_qubits)],
            )
        ]
        # Plot the additional SVG lines if we have a 2-qubit error.
        if qx2 is not None and qy2 is not None:
            qx2 -= top_left_qubit.x
            qy2 -= top_left_qubit.y
            error_svg.append(
                svg.G(
                    elements=[cross_svg],
                    transform=[
                        svg.Translate(qx2 * width_between_qubits, qy2 * height_between_qubits)
                    ],
                )
            )
            error_svg.append(
                svg.Line(
                    x1=qx * width_between_qubits,
                    x2=qx2 * width_between_qubits,
                    y1=qy * height_between_qubits,
                    y2=qy2 * height_between_qubits,
                    stroke=stroke_color,
                    stroke_width=size * stroke_width_multiplier,
                )
            )
        crosses.append(svg.G(elements=error_svg))
    return svg.G(elements=crosses)
