from __future__ import annotations

from dataclasses import dataclass

from stim import Circuit as stim_Circuit

from tqec.circuit.qubit_map import QubitMap
from tqec.circuit.schedule import ScheduledCircuit
from tqec.plaquette.plaquette import Plaquette
from tqec.plaquette.qubit import PlaquetteQubits, SquarePlaquetteQubits
from tqec.plaquette.rpng import RG, BasisEnum, ExtendedBasisEnum


@dataclass(frozen=True)
class RAPNG:
    """Organize a single RAPNG value

    The RAPNG format is an extension of the RPNG format.
    In practice, we relax the assumption that the 2Q gate involving the ancilla
    and a data qubit is always conditioned by the ancilla being in the |1> state.

    The extra field (a) is used together with (p) to determine the 2Q gate involving the
    ancilla and data qubits. For example:
    - a=z, p=x --> CNOT controlled by the ancilla and targeting the data
    - a=z, p=z --> CZ   controlled by the ancilla and targeting the data
    - a=y, p=z --> YCZ  controlled by the ancilla in the y basis, conditionally applying Z on the data
    By default a=z.

    Attributes:
        r   data qubit reset basis or h or -
        a   ancilla basis for the controlled operation (x means that the controlled operation is applied if ancilla is in |+>, y if it is in |-y>, z if it is in |1>)
        p   data basis for the controlled operation (assuming a=z, x means CNOT controlled on the ancilla and targeting the data qubit, y means CY, z means CZ)
        n   time step (positive integers, all distinct, typically in 1-5)
        g   data qubit measure basis or h or -
    """

    r: ExtendedBasisEnum | None
    a: BasisEnum | None
    p: BasisEnum | None
    n: int | None
    g: ExtendedBasisEnum | None

    @classmethod
    def from_string(cls, rapng_string: str) -> RAPNG:
        """Initialize the RAPNG object from a 5-character string

        Note that the ancilla basis(a) is the second character, just before (p).

        Note that any character different from a BasisEnum / ExtendedBasisEnum
        value would result in the corresponding field being None.
        """
        if len(rapng_string) != 5:
            raise ValueError("The rapng string must be exactly 5-character long.")
        r_str, a_str, p_str, n_str, g_str = tuple(rapng_string)
        # Convert the characters into the enum attributes (or raise error).
        r = (
            ExtendedBasisEnum(r_str)
            if r_str in ExtendedBasisEnum._value2member_map_
            else None
        )
        a = BasisEnum(a_str) if a_str in BasisEnum._value2member_map_ else None
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
        if not a and a_str != "-":
            raise ValueError("Unacceptable character for the A field.")
        if not p and p_str != "-":
            raise ValueError("Unacceptable character for the P field.")
        if (p and not a) or (a and not p):
            raise ValueError("Both A and P must be set to a basis or none of them.")
        if not n and n_str != "-":
            raise ValueError("Unacceptable character for the N field.")
        if not g and g_str != "-":
            raise ValueError("Unacceptable character for the G field.")
        return cls(r, a, p, n, g)

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


@dataclass
class RAPNGDescription:
    """Organize the description of a plaquette in RAPNG format

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
        corners RAPNG description of the four corners of the plaquette
        ancilla RG description of the ancilla
    """

    corners: tuple[RAPNG, RAPNG, RAPNG, RAPNG]
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
                    raise ValueError("The n values must be larger than 0")
                times.append(rpng.n)
        if len(times) != len(set(times)):
            raise ValueError("The n values for the corners must be unique.")
        elif len(times) not in [0, 2, 4]:
            raise ValueError("Each plaquette must have 0, 2, or 4 2Q gates.")

    @classmethod
    def from_string(cls, corners_rapng_string: str) -> RAPNGDescription:
        """Initialize the RAPNGDescription object from a (20+3)-character string"""
        rapng_objs = tuple(
            [RAPNG.from_string(s) for s in corners_rapng_string.split(" ")]
        )
        if len(rapng_objs) != 4:
            raise ValueError("There must be 4 corners in the RAPNG description.")
        return cls(rapng_objs)

    @classmethod
    def from_extended_string(
        cls, ancilla_and_corners_rapng_string: str
    ) -> RAPNGDescription:
        """Initialize the RAPNGDescription object from a (20+3)-character string"""
        values = ancilla_and_corners_rapng_string.split(" ")
        ancilla_rgn = RG.from_string(values[0])
        rapng_objs = tuple([RAPNG.from_string(s) for s in values[1:]])
        if len(rapng_objs) != 4:
            raise ValueError("There must be 4 corners in the RAPNG description.")
        return cls(rapng_objs, ancilla_rgn)

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
        for q, rapng in enumerate(self.corners):
            # 2Q gates.
            if rapng.n and rapng.p and rapng.a:
                if rapng.n >= meas_time:
                    raise ValueError(
                        "The measurement time must be larger than the 2Q gate time."
                    )
                circuit_as_list[rapng.n] += (
                    f"{rapng.a.value.upper()}C{rapng.p.value.upper()} 4 {q}\n"
                )
            # Data reset or Hadamard.
            if rapng.r:
                circuit_as_list[0] += f"{rapng.get_r_op()} {q}\n"
            # Data measurement or Hadamard.
            if rapng.g:
                circuit_as_list[-1] += f"{rapng.get_g_op()} {q}\n"
        # Ancilla reset and measurement.
        circuit_as_list[0] += f"R{self.ancilla.r.value.upper()} 4\n"
        circuit_as_list[-1] += f"M{self.ancilla.g.value.upper()} 4\n"
        q_map = QubitMap.from_qubits(qubits)
        circuit_as_str = "TICK\n".join(circuit_as_list)
        circuit = stim_Circuit(circuit_as_str)
        scheduled_circuit = ScheduledCircuit.from_circuit(circuit, qubit_map=q_map)
        return Plaquette(name="test", qubits=qubits, circuit=scheduled_circuit)
