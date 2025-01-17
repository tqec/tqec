from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path


class BasisEnum(Enum):
    X = "x"
    Y = "y"
    Z = "z"

    def __str__(self) -> str:
        return self.value

    def to_extended_basis(self) -> ExtendedBasisEnum:
        return ExtendedBasisEnum(self.value)


class ExtendedBasisEnum(Enum):
    X = BasisEnum.X.value
    Y = BasisEnum.Y.value
    Z = BasisEnum.Z.value
    H = "h"

    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True)
class RPNG:
    """Represents a single ``RPNG`` string.

    ## Format specification

    The ``RPNG`` string is a standard format used in ``tqec`` to unambiguously
    describe the action(s) being performed on a single data qubit. It is a
    4-character string. See each attribute docstring for more details on the
    possible values for each character.

    ## Example

    The following ::

        -z1-
        rpng

    represents a data-qubit with a ``CZ`` gate applied at timestep ``1``.

    Attributes:
        r: reset basis (``x``, ``y`` or ``z``), ``h`` or ``-``.
        p: controlled operation target basis (``x`` means ``CNOT`` controlled
            on the ancilla and targeting the data qubit, ``y`` means ``CY``,
            ``z`` means ``CZ``).
        n: time step at which the 2-qubit operation described by ``p`` should
            be applied. Should be a 1-digit positive integer, typically in
            ``[1, 5]``.
        g: measure basis (``x``, ``y`` or ``z``), ``h`` or ``-``.
    """

    r: ExtendedBasisEnum | None
    p: BasisEnum | None
    n: int | None
    g: ExtendedBasisEnum | None

    @classmethod
    def from_string(cls, rpng_string: str) -> RPNG:
        """Initialize the RPNG object from a 4-character string.

        Raises:
            ValueError: if an invalid ``rpng_string`` is provided.
        """
        if len(rpng_string) != 4:
            raise ValueError("The rpng string must be exactly 4-character long.")
        r_str, p_str, n_str, g_str = tuple(rpng_string)
        # Convert the characters into the enum attributes (or raise error).
        r = (
            ExtendedBasisEnum(r_str)
            if r_str in ExtendedBasisEnum._value2member_map_
            else None
        )
        p = BasisEnum(p_str) if p_str in BasisEnum._value2member_map_ else None
        n = int(n_str) if n_str.isdigit() else None
        g = (
            ExtendedBasisEnum(g_str)
            if g_str in ExtendedBasisEnum._value2member_map_
            else None
        )
        # Raise error if anythiong but '-' was used to indicate None.
        if not r and r_str != "-":
            raise ValueError("Unacceptable character for the R field.")
        if not p and p_str != "-":
            raise ValueError("Unacceptable character for the P field.")
        if not n and n_str != "-":
            raise ValueError("Unacceptable character for the N field.")
        if not g and g_str != "-":
            raise ValueError("Unacceptable character for the G field.")
        return cls(r, p, n, g)

    def get_r_op(self) -> str | None:
        """Get the reset operation or Hadamard"""
        op = self.r
        if op is None:
            return None
        elif op.value in BasisEnum._value2member_map_:
            return f"R{op.value.upper()}"
        else:
            return f"{op.value.upper()}"

    def get_g_op(self) -> str | None:
        """Get the measurement operation or Hadamard"""
        op = self.g
        if op is None:
            return None
        elif op.value in BasisEnum._value2member_map_:
            return f"M{op.value.upper()}"
        else:
            return f"{op.value.upper()}"

    @property
    def is_null(self) -> bool:
        """Check if the RPNG object is null, i.e. all fields are None"""
        return str(self) == "----"

    def __str__(self) -> str:
        return f"{'-' if self.r is None else self.r.value}{'-' if self.p is None else self.p.value}{'-' if self.n is None else self.n}{'-' if self.g is None else self.g.value}"


@dataclass(frozen=True)
class RG:
    """Reduced format to represent syndrome qubit operations.

    The ``RG`` format is simply the ``RPNG`` format where ``P`` is
    unconditionally ``-`` and ``N`` is unset.

    Attributes:
        r: reset basis (``x``, ``y`` or ``z``), ``h`` or ``-``.
        g: measure basis (``x``, ``y`` or ``z``), ``h`` or ``-``.
    """

    r: BasisEnum | None
    g: BasisEnum | None

    @classmethod
    def from_string(cls, rg_string: str) -> RG:
        """Initialize the ``RG`` object from a 2-character string"""
        if len(rg_string) != 2:
            raise ValueError("The RG string must be exactly 2-character long.")
        r_str, g_str = tuple(rg_string)

        try:
            r = None if r_str == "-" else BasisEnum(r_str)
            g = None if g_str == "-" else BasisEnum(g_str)
            return cls(r, g)
        except ValueError as err:
            raise ValueError(f"Invalid RG string: '{rg_string}'.") from err

    def __str__(self) -> str:
        return f"{'-' if self.r is None else self.r.value}{'-' if self.g is None else self.g.value}"


@dataclass
class RPNGDescription:
    """Organize the description of a plaquette in RPNG format

    The corners of the square plaquette are listed following the order:
    top-left, top-right, bottom-left, bottom-right.
    This forms a Z-shaped path on the plaquette corners:

        +------------+
        | 1 -----> 2 |
        |        /   |
        |      /     |
        |    ∟       |
        | 3 -----> 4 |
        +------------+

    If the ancilla RG description is not specified, it is assumed 'xx'

    Attributes:
        corners: one ``RPNG`` description for each of the four corners of the
            plaquette.
        ancilla: ``RG`` description of the syndrome qubit.
    """

    corners: tuple[RPNG, RPNG, RPNG, RPNG]
    ancilla: RG = RG(BasisEnum.X, BasisEnum.X)

    def __post_init__(self) -> None:
        """Validation of the initialization arguments

        Constraints:
        - the n values for the corners must be unique
        - the n values for the corners must be larger than 0
        """
        times = []
        for rpng in self.corners:
            if rpng.n:
                if rpng.n < 1:
                    raise ValueError("All n values must be larger than 0.")
                times.append(rpng.n)
        if len(times) != len(set(times)):
            raise ValueError("The n values for the corners must be unique.")

    @classmethod
    def from_string(cls, corners_rpng_string: str) -> RPNGDescription:
        """Initialize the RPNGDescription object from a (16+3)-character string"""
        rpng_objs = tuple([RPNG.from_string(s) for s in corners_rpng_string.split(" ")])
        if len(rpng_objs) != 4:
            raise ValueError("There must be 4 corners in the RPNG description.")
        return cls(rpng_objs)

    @classmethod
    def from_extended_string(
        cls, ancilla_and_corners_rpng_string: str
    ) -> RPNGDescription:
        """Initialize the RPNGDescription object from a (16+3)-character string"""
        values = ancilla_and_corners_rpng_string.split(" ")
        ancilla_rg = RG.from_string(values[0])
        rpng_objs = tuple([RPNG.from_string(s) for s in values[1:]])
        if len(rpng_objs) != 4:
            raise ValueError("There must be 4 corners in the RPNG description.")
        return cls(rpng_objs, ancilla_rg)

    @staticmethod
    def empty() -> RPNGDescription:
        return RPNGDescription.from_extended_string("-- ---- ---- ---- ----")

    def get_r_op(self, data_idx: int) -> str | None:
        """Get the reset operation or Hadamard for the specific data qubit"""
        return self.corners[data_idx].get_r_op()

    def get_n(self, data_idx: int) -> int | None:
        """Get the time of the 2Q gate involving the specific data qubit"""
        return self.corners[data_idx].n

    def get_g_op(self, data_idx: int) -> str | None:
        """Get the measurement operation or Hadamard for the specific data qubit"""
        return self.corners[data_idx].get_g_op()

    @property
    def has_reset(self) -> bool:
        return any(corner.get_r_op() not in {None, "H"} for corner in self.corners)

    @property
    def has_measurement(self) -> bool:
        return any(corner.get_g_op() not in {None, "H"} for corner in self.corners)

    def __str__(self) -> str:
        return " ".join(str(rpng) for rpng in self.corners)

    def view_as_svg(
        self,
        write_to_filepath: str | Path | None = None,
        canvas_height: int = 100,
        opacity: float = 1.0,
        show_rg_fields: bool = True,
        show_interaction_order: bool = True,
        show_hook_error: bool = False,
    ) -> str:
        """Visualize the RPNG description as an SVG image.

        Args:
            write_to_filepath: the path to write the SVG image to.
            canvas_height: The height of the canvas in pixels.
            opacity: The opacity of the plaquettes.
            show_rg_fields: Whether to show the R/G fields on the data qubits. If True, the R
                field is shown as a small rectangle at the position of the data qubit, whose color
                corresponds to the basis. The G field is shown as a small circle at the position
                of the data qubit, whose color corresponds to the basis.
            show_interaction_order: Whether to show the interaction order of the plaquettes. If
                True, the interaction order is shown at each corner of the plaquette.
            show_hook_error: Whether to highlight the plaquette with the hook error. If True, the
                hook error is shown as a black line along the hook edge.


        Returns:
            The SVG string representing the visualization.
        """
        from tqec.templates.viz_rpng import rpng_svg_viewer

        svg_str = rpng_svg_viewer(
            self,
            canvas_height=canvas_height,
            opacity=opacity,
            show_rg_fields=show_rg_fields,
            show_interaction_order=show_interaction_order,
            show_hook_error=lambda _: show_hook_error,
        )
        if write_to_filepath is not None:
            with open(write_to_filepath, "w") as f:
                f.write(svg_str)
        return svg_str
