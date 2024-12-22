from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from stim import Circuit as stim_Circuit

from tqec.circuit.qubit_map import QubitMap
from tqec.circuit.schedule import ScheduledCircuit
from tqec.plaquette.plaquette import Plaquette
from tqec.plaquette.qubit import PlaquetteQubits, SquarePlaquetteQubits


class BasisEnum(Enum):
    X = "x"
    Y = "y"
    Z = "z"


class ExtendedBasisEnum(Enum):
    X = BasisEnum.X.value
    Y = BasisEnum.Y.value
    Z = BasisEnum.Z.value
    H = "h"


@dataclass(frozen=True)
class RPNG:
    """Organize a single RPNG value

    -z1-
    rpng

    (r) data qubit reset basis or h or -
    (p) data basis for the controlled operation (x means CNOT controlled on the ancilla and targeting the data qubit, y means CY, z means CZ)
    (n) time step (positive integers, all distinct, typically in 1-5)
    (g) data qubit measure basis or h or -

    Assumptions on the circuit:
    - if not otherwise stated, a basis can be {x,y,z}
    - the ancilla is always the control qubit for the CNOT, CY, or CZ gates
    - time step of r same as ancilla reset (always 0)
    - time step of g same as ancilla measurement (by default 6)

    Attributes:
        r   data qubit reset basis or h or -
        p   data basis for the controlled operation (assuming a=z, x means CNOT controlled on the ancilla and targeting the data qubit, y means CY, z means CZ)
        n   time step (positive integers, all distinct, typically in 1-5)
        g   data qubit measure basis or h or -
    """

    r: ExtendedBasisEnum | None
    p: BasisEnum | None
    n: int | None
    g: ExtendedBasisEnum | None

    @classmethod
    def from_string(cls, rpng_string: str) -> RPNG:
        """Initialize the RPNG object from a 4-character string

        Note that any character different from a BasisEnum / ExtendedBasisEnum
        value would result in the corresponding field being None.
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


@dataclass(frozen=True)
class RG:
    """Organize the prep and meas bases for the ancilla, together with the meas time

    The initialization time is assumed to be 0.
    The measurement time is not provided explicitly but determined by the time of circuit creation.

    Attributes:
        r   ancillaqubit reset basis
        g   ancilla qubit measure basis
    """

    r: BasisEnum = BasisEnum.X
    g: BasisEnum = BasisEnum.X

    @classmethod
    def from_string(cls, rg_string: str) -> RG:
        """Initialize the RGN object from a 3-character string"""
        if len(rg_string) != 2:
            raise ValueError("The rg string must be exactly 2-character long.")
        r_str, g_str = tuple(rg_string)

        try:
            r = BasisEnum(r_str)
            g = BasisEnum(g_str)
            return cls(r, g)
        except ValueError as err:
            raise ValueError("Invalid rg string.") from err


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
        corners RPNG description of the four corners of the plaquette
        ancilla RG description of the ancilla
    """

    corners: tuple[RPNG, RPNG, RPNG, RPNG]
    ancilla: RG = RG()

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
        elif len(times) not in [0, 2, 4]:
            raise ValueError("Each plaquette must have 0, 2, or 4 2Q gates.")

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

    def get_r_op(self, data_idx: int) -> str | None:
        """Get the reset operation or Hadamard for the specific data qubit"""
        return self.corners[data_idx].get_r_op()

    def get_n(self, data_idx: int) -> int | None:
        """Get the time of the 2Q gate involving the specific data qubit"""
        return self.corners[data_idx].n

    def get_g_op(self, data_idx: int) -> str | None:
        """Get the measurement operation or Hadamard for the specific data qubit"""
        return self.corners[data_idx].get_g_op()

    def get_plaquette(
        self, meas_time: int = 6, qubits: PlaquetteQubits = SquarePlaquetteQubits()
    ) -> Plaquette:
        """Get the plaquette corresponding to the RPNG description

        Note that the ancilla qubit is the last among the PlaquetteQubits and thus
        has index 4, while the data qubits have indices 0-3.
        """
        prep_time = 0
        circuit_as_list = [""] * (meas_time - prep_time + 1)
        for q, rpng in enumerate(self.corners):
            # 2Q gates.
            if rpng.n and rpng.p:
                if rpng.n >= meas_time:
                    raise ValueError(
                        "The measurement time must be larger than the 2Q gate time."
                    )
                circuit_as_list[rpng.n] += f"C{rpng.p.value.upper()} 4 {q}\n"
            # Data reset or Hadamard.
            if rpng.r:
                circuit_as_list[0] += f"{rpng.get_r_op()} {q}\n"
            # Data measurement or Hadamard.
            if rpng.g:
                circuit_as_list[-1] += f"{rpng.get_g_op()} {q}\n"
        # Ancilla reset and measurement.
        circuit_as_list[0] += f"R{self.ancilla.r.value.upper()} 4\n"
        circuit_as_list[-1] += f"M{self.ancilla.g.value.upper()} 4\n"
        q_map = QubitMap.from_qubits(qubits)
        circuit_as_str = "TICK\n".join(circuit_as_list)
        circuit = stim_Circuit(circuit_as_str)
        scheduled_circuit = ScheduledCircuit.from_circuit(circuit, qubit_map=q_map)
        return Plaquette(name="test", qubits=qubits, circuit=scheduled_circuit)
