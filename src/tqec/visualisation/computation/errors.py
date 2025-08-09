from collections.abc import Sequence

import stim
import svg

from tqec.circuit.qubit import GridQubit
from tqec.interop.color import TQECColor
from tqec.visualisation.exception import TQECDrawingError


def _get_error_cross_svg(
    size: float = 1, stroke_color: str = "red", stroke_width_multiplier: float = 0.2
) -> svg.Element:
    """Return an SVG element representing an error."""
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
            raise TQECDrawingError("Could not extract coordinates from an empty list.")
        case _:
            raise TQECDrawingError(
                f"Could not extract coordinates from a list with {len(targets)}."
            )


def get_errors_svg(
    errors: Sequence[stim.ExplainedError],
    top_left_qubit: GridQubit,
    plaquette_width: float,
    plaquette_height: float,
    size: float = 1,
    add_detectors_from_errors: bool = True,
) -> svg.G:
    """Return an SVG element with the provided ``errors`` drawn and a transparent background.

    Args:
        errors: a sequence of errors to plot. It is often desirable to filter
            errors according to the moment they appear in.
        top_left_qubit: coordinates of the qubit at the very top-left of the
            visualisation canva. Used to correctly offset qubit values from the
            provided ``errors``.
        plaquette_width: width (in SVG dimensions) of a regular square plaquette.
        plaquette_height: height (in SVG dimensions) of a regular square plaquette.
        size: size (in SVG dimensions) of the crosses used to mark errors.
        add_detectors_from_errors: add a visualisation of detectors from the provided errors.

    Returns:
        a SVG element containing as many sub-elements as there are errors in the
        provided ``errors`` list, each representing one of the provided errors.

    Raises:
        TQECDrawingError: if at least one of the provided ``errors`` has both an
            empty ``flipped_measurement`` list AND an empty ``flipped_pauli_product``
            list.

    """
    # Default value for the moment
    stroke_width_multiplier = 0.2
    width_between_qubits: float = plaquette_width / 2
    height_between_qubits: float = plaquette_height / 2
    stroke_width: float = size * stroke_width_multiplier
    layer: list[svg.Element] = []
    # Start by adding the detectors
    detectors: dict[int, stim.DemTargetWithCoords] = {}
    if add_detectors_from_errors:
        # List the detectors that need to be drawn
        for error in errors:
            for target in error.dem_error_terms:
                if target.dem_target.is_relative_detector_id():
                    detectors[target.dem_target.val] = target
        # Draw each of them once
        for detector in detectors.values():
            x, y, t, *_ = detector.coords
            layer.append(
                svg.G(
                    elements=[
                        svg.Circle(
                            cx=0,
                            cy=0,
                            r=0.15,
                            stroke="black",
                            fill="transparent",
                            stroke_width=0.01,
                        ),
                        svg.Text(
                            x=0,
                            y=0,
                            text=f"D{detector.dem_target.val} ({int(t)})",
                            fill="black",
                            font_size=0.08,
                            text_anchor="middle",
                            dominant_baseline="middle",
                        ),
                    ],
                    transform=[
                        svg.Translate(
                            (x - top_left_qubit.x) * width_between_qubits,
                            (y - top_left_qubit.y) * height_between_qubits,
                        )
                    ],
                )
            )
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
            basis = flipped_pauli_product[0].gate_target.pauli_type
        elif flipped_measurement:
            qx, qy, qx2, qy2 = _get_coordinates(flipped_measurement.observable)
            basis = flipped_measurement.observable[0].gate_target.pauli_type
        else:
            raise TQECDrawingError("Could not draw the following error:\n" + str(error))
        color = TQECColor(f"{basis}_CORRELATION").rgba.to_hex()
        # Make the coordinates relative to the top-left qubit.
        qx -= top_left_qubit.x
        qy -= top_left_qubit.y
        # Plot the cross for a single-qubit error.
        tick_text_svg = svg.Text(
            x=0,
            y=-size,
            text=str(location.tick_offset),
            fill=color,
            font_size=0.3,
            font_weight="bold",
            text_anchor="middle",
            dominant_baseline="auto",
        )
        cross_svg = _get_error_cross_svg(size, color, stroke_width_multiplier)
        error_svg: list[svg.Element] = [
            svg.G(
                elements=[cross_svg, tick_text_svg],
                transform=[svg.Translate(qx * width_between_qubits, qy * height_between_qubits)],
            ),
        ]
        detector_arrow_source = qx * width_between_qubits, qy * height_between_qubits
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
                    stroke=color,
                    stroke_width=stroke_width,
                )
            )
            detector_arrow_source = (
                (qx + qx2) * width_between_qubits / 2,
                (qy + qy2) * height_between_qubits / 2,
            )
        # Plot lines to link detectors and errors.
        if add_detectors_from_errors:
            for dem_error_term in error.dem_error_terms:
                if not dem_error_term.dem_target.is_relative_detector_id():
                    continue
                x, y, t, *_ = dem_error_term.coords
                error_svg.append(
                    svg.Line(
                        x1=detector_arrow_source[0],
                        y1=detector_arrow_source[1],
                        x2=(x - top_left_qubit.x) * width_between_qubits,
                        y2=(y - top_left_qubit.y) * height_between_qubits,
                        stroke="black",
                        stroke_width=0.01,
                    )
                )
        layer.append(svg.G(elements=error_svg))
    return svg.G(elements=layer)
