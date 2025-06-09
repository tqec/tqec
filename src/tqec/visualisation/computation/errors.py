from collections.abc import Sequence
import stim
import svg

from tqec.visualisation.exception import TQECDrawingException


def _get_error_cross_svg(
    size: float = 1, stroke_color: str = "red", stroke_width_multiplier: float = 0.1
) -> svg.Element:
    return svg.Path(
        d=[
            svg.M(-size / 2, -size / 2),
            svg.L(size / 2, size / 2),
            svg.M(0, size / 2),
            svg.L(size / 2, 0),
        ],
        stroke=stroke_color,
        stroke_width=size * stroke_width_multiplier,
    )


def get_errors_svg(
    errors: Sequence[stim.ExplainedError],
    plaquette_width: float,
    plaquette_height: float,
    size: float = 1,
    stroke_color: str = "red",
    stroke_width_multiplier: float = 0.1,
) -> svg.G:
    width_between_qubits: float = plaquette_width / 2
    height_between_qubits: float = plaquette_height / 2
    cross_svg = _get_error_cross_svg(size, stroke_color, stroke_width_multiplier)
    crosses: list[svg.Element] = []
    for error in errors:
        location = error.circuit_error_locations[0]
        flipped_measurement = location.flipped_measurement
        flipped_pauli_product = location.flipped_pauli_product
        if flipped_pauli_product is not None:
            qx, qy = flipped_pauli_product[0].coords
        elif flipped_measurement is None:
            raise TQECDrawingException(
                "Could not draw the following error:\n" + str(error)
            )
        else:
            qx, qy = flipped_measurement.observable[0].coords

        crosses.append(
            svg.G(
                elements=[cross_svg],
                transform=[
                    svg.Translate(qx * width_between_qubits, qy * height_between_qubits)
                ],
            )
        )
    return svg.G(elements=crosses)
