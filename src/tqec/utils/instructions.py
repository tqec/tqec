"""Defines a few functions to analyse and create ``stim.CircuitInstruction``
instances."""

import stim

COMBINED_RESET_AND_MEASUREMENT_INSTRUCTION_NAMES: frozenset[str] = frozenset(
    ["MR", "MRX", "MRY", "MRZ"]
)

SINGLE_QUBIT_MEASUREMENT_INSTRUCTION_NAMES: frozenset[str] = (
    frozenset(["M", "MX", "MY", "MZ"])
    | COMBINED_RESET_AND_MEASUREMENT_INSTRUCTION_NAMES
)
MULTIPLE_QUBIT_MEASUREMENT_INSTRUCTION_NAMES: frozenset[str] = frozenset(
    ["MXX", "MYY", "MZZ", "MPP"]
)

MEASUREMENT_INSTRUCTION_NAMES = (
    SINGLE_QUBIT_MEASUREMENT_INSTRUCTION_NAMES
    | MULTIPLE_QUBIT_MEASUREMENT_INSTRUCTION_NAMES
)

ANNOTATION_INSTRUCTION_NAMES: frozenset[str] = frozenset(
    ["DETECTOR", "MPAD", "OBSERVABLE_INCLUDE", "QUBIT_COORDS", "SHIFT_COORDS", "TICK"]
)

RESET_INSTRUCTION_NAMES: frozenset[str] = frozenset(["R", "RX", "RY", "RZ"])


def is_combined_reset_and_measurement_instruction(
    instruction: stim.CircuitInstruction,
) -> bool:
    return instruction.name in COMBINED_RESET_AND_MEASUREMENT_INSTRUCTION_NAMES


def is_measurement_instruction(instruction: stim.CircuitInstruction) -> bool:
    return instruction.name in MEASUREMENT_INSTRUCTION_NAMES


def is_single_qubit_measurement_instruction(
    instruction: stim.CircuitInstruction,
) -> bool:
    return instruction.name in SINGLE_QUBIT_MEASUREMENT_INSTRUCTION_NAMES


def is_multi_qubit_measurement_instruction(
    instruction: stim.CircuitInstruction,
) -> bool:
    return instruction.name in MULTIPLE_QUBIT_MEASUREMENT_INSTRUCTION_NAMES


def is_annotation_instruction(instruction: stim.CircuitInstruction) -> bool:
    return instruction.name in ANNOTATION_INSTRUCTION_NAMES


def is_reset_instruction(instruction: stim.CircuitInstruction) -> bool:
    return instruction.name in RESET_INSTRUCTION_NAMES
