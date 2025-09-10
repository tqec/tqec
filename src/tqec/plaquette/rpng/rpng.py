from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from tqec.circuit.schedule.schedule import Schedule
from tqec.utils.enums import Basis


class PauliBasis(Enum):
    X = "x"
    Y = "y"
    Z = "z"

    def __str__(self) -> str:
        return self.value  # pragma: no cover

    def to_extended_basis(self) -> ExtendedBasis:
        """Return ``self`` as an extended basis."""
        return ExtendedBasis(self.value)


class ExtendedBasis(Enum):
    X = PauliBasis.X.value
    Y = PauliBasis.Y.value
    Z = PauliBasis.Z.value
    H = "h"

    def __str__(self) -> str:
        return self.value  # pragma: no cover


@dataclass(frozen=True)
class RPNG:
    """Represent a single ``RPNG`` string.

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

    r: ExtendedBasis | None
    p: PauliBasis | None
    n: int | None
    g: ExtendedBasis | None

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
        r = ExtendedBasis(r_str) if r_str in ExtendedBasis._value2member_map_ else None
        p = PauliBasis(p_str) if p_str in PauliBasis._value2member_map_ else None
        n = int(n_str) if n_str.isdigit() else None
        g = ExtendedBasis(g_str) if g_str in ExtendedBasis._value2member_map_ else None
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
        """Get the reset operation or Hadamard."""
        op = self.r
        if op is None:
            return None
        elif op.value in PauliBasis._value2member_map_:
            return f"R{op.value.upper()}"
        else:
            return f"{op.value.upper()}"

    def get_g_op(self) -> str | None:
        """Get the measurement operation or Hadamard."""
        op = self.g
        if op is None:
            return None
        elif op.value in PauliBasis._value2member_map_:
            return f"M{op.value.upper()}"
        else:
            return f"{op.value.upper()}"

    @property
    def is_null(self) -> bool:
        """Check if the RPNG object is null, i.e. all fields are None."""
        return str(self) == "----"

    def __str__(self) -> str:
        r = "-" if self.r is None else self.r.value
        p = "-" if self.p is None else self.p.value
        n = "-" if self.n is None else self.n
        g = "-" if self.g is None else self.g.value
        return f"{r}{p}{n}{g}"


@dataclass(frozen=True)
class RG:
    """Reduced format to represent syndrome qubit operations.

    The ``RG`` format is simply the ``RPNG`` format where ``P`` is
    unconditionally ``-`` and ``N`` is unset.

    Attributes:
        r: reset basis (``x``, ``y`` or ``z``), ``h`` or ``-``.
        g: measure basis (``x``, ``y`` or ``z``), ``h`` or ``-``.

    """

    r: PauliBasis | None
    g: PauliBasis | None

    @classmethod
    def from_string(cls, rg_string: str) -> RG:
        """Initialize the ``RG`` object from a 2-character string."""
        if len(rg_string) != 2:
            raise ValueError("The RG string must be exactly 2-character long.")
        r_str, g_str = tuple(rg_string)

        try:
            r = None if r_str == "-" else PauliBasis(r_str)
            g = None if g_str == "-" else PauliBasis(g_str)
            return cls(r, g)
        except ValueError as err:
            raise ValueError(f"Invalid RG string: '{rg_string}'.") from err

    def __str__(self) -> str:
        return f"{'-' if self.r is None else self.r.value}{'-' if self.g is None else self.g.value}"


@dataclass
class RPNGDescription:
    """Organize the description of a plaquette in RPNG format.

    The corners of the square plaquette are listed following the order:
    top-left, top-right, bottom-left, bottom-right.
    This forms a Z-shaped path on the plaquette corners:

    .. code-block:: text

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
    ancilla: RG = field(default=RG(PauliBasis.X, PauliBasis.X))

    def __post_init__(self) -> None:
        """Validate the initialization arguments.

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
        """Initialize the RPNGDescription object from a (16+3)-character string."""
        rpng_objs = tuple([RPNG.from_string(s) for s in corners_rpng_string.split(" ")])
        if len(rpng_objs) != 4:
            raise ValueError("There must be 4 corners in the RPNG description.")
        return cls(rpng_objs)

    @classmethod
    def from_extended_string(cls, ancilla_and_corners_rpng_string: str) -> RPNGDescription:
        """Initialize the RPNGDescription object from a (16+3)-character string."""
        values = ancilla_and_corners_rpng_string.split(" ")
        ancilla_rg = RG.from_string(values[0])
        rpng_objs = tuple([RPNG.from_string(s) for s in values[1:]])
        if len(rpng_objs) != 4:
            raise ValueError("There must be 4 corners in the RPNG description.")
        return cls(rpng_objs, ancilla_rg)

    @classmethod
    def from_basis_and_schedule(
        cls,
        basis: Basis,
        schedule: Sequence[int] | Schedule,
        reset: PauliBasis | None = None,
        measurement: ExtendedBasis | None = None,
    ) -> RPNGDescription:
        """Initialize the RPNGDescription object from a basis and a schedule."""
        r = "-" if reset is None else reset.value
        m = "-" if measurement is None else measurement.value
        rpng_objs = tuple([RPNG.from_string(f"{r}{basis.value.lower()}{s}{m}") for s in schedule])
        if len(rpng_objs) != 4:
            raise ValueError("There must be 4 corners in the RPNG description.")
        return cls(rpng_objs)

    @staticmethod
    def empty() -> RPNGDescription:
        """Return a description of the empty plaquette."""
        return RPNGDescription.from_extended_string("-- ---- ---- ---- ----")

    def get_r_op(self, data_idx: int) -> str | None:
        """Get the reset operation or Hadamard for the specific data qubit."""
        return self.corners[data_idx].get_r_op()

    def get_n(self, data_idx: int) -> int | None:
        """Get the time of the 2Q gate involving the specific data qubit."""
        return self.corners[data_idx].n

    def get_g_op(self, data_idx: int) -> str | None:
        """Get the measurement operation or Hadamard for the specific data qubit."""
        return self.corners[data_idx].get_g_op()

    @property
    def has_reset(self) -> bool:
        """Return ``True`` if ``self`` contains at least one corner with a reset."""
        return any(
            corner.get_r_op()
            not in {
                None,
                "H",
            }
            for corner in self.corners
        )

    @property
    def has_measurement(self) -> bool:
        """Return ``True`` if ``self`` contains at least one corner with a measurement."""
        return any(
            corner.get_g_op()
            not in {
                None,
                "H",
            }
            for corner in self.corners
        )

    def __str__(self) -> str:
        return " ".join(str(rpng) for rpng in self.corners)

    def to_dict(self) -> dict[str, Any]:
        """Return a dictionary representation of the RPNG description.

        The dictionary is intended to be used as a JSON object.

        """
        return {
            "corners": [str(rpng) for rpng in self.corners],
            "ancilla": str(self.ancilla),
        }

    @staticmethod
    def from_dict(data: dict[str, Any]) -> RPNGDescription:
        """Return a RPNGDescription object from its dictionary representation.

        Args:
            data: dictionary with the keys ``corners`` and ``ancilla``.

        Returns:
            a new instance of :class:`RPNGDescription` with the provided
            ``corners`` and ``ancilla``.

        """
        assert len(data["corners"]) == 4, "There must be 4 corners in the RPNG description."
        corners = data["corners"]
        corners = (
            RPNG.from_string(corners[0]),
            RPNG.from_string(corners[1]),
            RPNG.from_string(corners[2]),
            RPNG.from_string(corners[3]),
        )
        ancilla = RG.from_string(data["ancilla"])
        return RPNGDescription(corners, ancilla)
