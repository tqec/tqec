import math

import svg

from tqec.circuit.qubit import GridQubit
from tqec.compile.observables.builder import Observable
from tqec.visualisation.configuration import DrawerConfiguration


def _get_observable_star_svg(
    r_outer: float,
    r_inner: float,
    fill: str = "none",
    fill_opacity: float = 0.5,
    stroke_color: str = "red",
    stroke_width: float = 0.5,
) -> svg.Polygon:
    points: list[tuple[float, float]] = []
    n = 5
    angle = math.pi / n
    for i in range(2 * n):
        r = r_outer if i % 2 == 0 else r_inner
        theta = i * angle - math.pi / 2
        x = r * math.cos(theta)
        y = r * math.sin(theta)
        points.append((x, y))
    return svg.Polygon(
        points=points,  # type: ignore[arg-type]
        fill=fill,
        stroke=stroke_color,
        stroke_width=stroke_width,
        fill_opacity=fill_opacity,
    )


def get_observable_svg(
    observable: Observable,
    top_left_qubit: GridQubit,
    plaquette_width: float,
    plaquette_height: float,
    configuration: DrawerConfiguration = DrawerConfiguration(),
) -> svg.G:
    """Return an SVG element with the provided ``observable`` drawn and a transparent background.

    Args:
        observable: the observable to plot. It is represented as a list of qubits
            whose measurements are included in the observable.
        top_left_qubit: coordinates of the qubit at the very top-left of the
            visualisation canva. Used to correctly offset qubit values from the
            provided ``errors``.
        plaquette_width: width (in SVG dimensions) of a regular square plaquette.
        plaquette_height: height (in SVG dimensions) of a regular square plaquette.
        configuration: drawing configuration.

    Returns:
        a SVG element containing as many sub-elements as there are measurements in the
        provided ``observable``.

    """
    width_between_qubits: float = plaquette_width / 2
    height_between_qubits: float = plaquette_height / 2

    layer: list[svg.Element] = []

    for q in observable.measured_qubits:
        qx, qy = q.x, q.y
        color = configuration.observable_star_color.rgba.to_hex()
        # Make the coordinates relative to the top-left qubit.
        qx -= top_left_qubit.x
        qy -= top_left_qubit.y
        # Plot the star for a single-qubit measurement.
        star_svg = _get_observable_star_svg(
            r_outer=0.15 * plaquette_width,
            r_inner=0.07 * plaquette_width,
            fill=color,
            fill_opacity=configuration.observable_fill_opacity,
            stroke_color=color,
            stroke_width=configuration.observable_stroke_width_multiplier * plaquette_width,
        )
        layer.append(
            svg.G(
                elements=[star_svg],
                transform=[svg.Translate(qx * width_between_qubits, qy * height_between_qubits)],
            )
        )
    return svg.G(elements=layer)
