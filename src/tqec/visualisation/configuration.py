from dataclasses import dataclass

from tqec.interop.color import TQECColor


@dataclass(frozen=True)
class DrawerConfiguration:
    """Drawing configuration with sensible defaults that can be modified by the user.

    Attributes:
        stroke_width: default stroke width used for all the drawing, except for
            error crosses.
        stroke_color: default stroke color used for all the drawing, except for
            error crosses.
        thin_stroke_color: color used to draw stroke that should appear thinner,
            for example between the UP and DOWN plaquette of an extended plaquette.
        font_size: default font size of all the text in the drawing except the
            overlaid "Moments: XX -> YY" text.
        hook_error_line_lerp_coefficient: a coefficient in [0, 1] that defines how close
            the hook error line should be from the borders of the plaquette. As an
            implementation detail, that number is also the hook error line length
            compared to the full plaquette width or height. A value of ``0.9`` means
            that the hook error line is closer to the plaquette border than to the
            plaquette center.
        plaquette_overflow_lerp_coefficient: coefficient in [0, 1] that defines how
            some plaquettes overflow from the regular convex hull of the involved
            data qubits. This is currently used for triangular plaquettes, but might
            be used for other plaquettes later. A value of ``0`` means "no overflow"
            whereas a value of ``1`` means "full overflow up to the missing data qubit".
        text_lerp_coefficient: coefficient in [0, 1] that defines where data-qubit
            interaction orders are written in the plaquette. A value of ``0`` means
            "on their respective data-qubit" whereas a value of ``1`` means "on the
            plaquette center".
        mixed_basis_color: color used to plot plaquettes measuring a non-uniform
            Pauli basis (e.g. ``ZXXZ``).
        observable_fill_opacity: opacity of the color used to fill observable stars.
        observable_stroke_width_multiplier: multiplier used on the plaquette width to obtain the
            stroke width that should be used to draw observables.
        observable_star_color: color used to draw the observable stars.
        reset_square_radius: representative size (in SVG coordinates) of the square used
            to represent data-qubit reset.
        measurement_circle_radius: representative size (in SVG coordinates) of the circle
            used to represent data-qubit measurement.

    """

    # Default stroke parameters
    stroke_width: float = 0.01
    stroke_color: str = "black"
    thin_stroke_color: str = "grey"
    # Default font parameters
    font_size: float = 0.1
    # Default placement parameters, used as coefficients to perform a linear interpolation
    hook_error_line_lerp_coefficient: float = 0.9
    plaquette_overflow_lerp_coefficient: float = 0.2
    text_lerp_coefficient: float = 0.8
    # Default colors used for different contents when drawing
    mixed_basis_color: str = "gray"
    # Observable-related drawing parameters
    observable_fill_opacity: float = 0.5
    observable_stroke_width_multiplier: float = 0.01
    observable_star_color: TQECColor = TQECColor.H
    # Default size of some of the elements drawn
    reset_square_radius: float = 0.05
    measurement_circle_radius: float = 0.1
