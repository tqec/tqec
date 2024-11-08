from __future__ import annotations

from typing import Mapping, Sequence

from tqec.circuit.qubit import GridQubit
from tqec.exceptions import TQECException
from tqec.plaquette.plaquette import Plaquette
from tqec.position import Displacement
from tqec.templates.base import Template
from tqec.templates.enums import TemplateOrientation


def observable_qubits_from_template(
    template: Template,
    k: int,
    plaquettes: Sequence[Plaquette] | Mapping[int, Plaquette],
    orientation: TemplateOrientation = TemplateOrientation.HORIZONTAL,
) -> Sequence[tuple[GridQubit, int]]:
    """Return the default observable qubits for the given template and its
    plaquettes.

    Args:
        template: The template to get the default observable qubits from.
        k: scaling parameter used to instantiate the provided template.
        plaquettes: The plaquettes to use to get the accurate positions of the
            observable qubits.
        orientation: Whether to get the observable qubits from the horizontal or
            vertical midline. Defaults to horizontal.

    Raises:
        TQECException: If the number of plaquettes does not match the expected
            number.
        TQECException: If the plaquettes are provided as a dictionary and 0 is
            in the keys.
        TQECException: If the template does not have a definable midline.

    Returns:
        The sequence of qubits and offsets for the observable qubits.
    """
    if len(plaquettes) != template.expected_plaquettes_number:
        raise TQECException(
            f"{len(plaquettes)} plaquettes have been provided, but "
            f"{template.expected_plaquettes_number} were expected."
        )
    if isinstance(plaquettes, Mapping) and 0 in plaquettes:
        raise TQECException(
            "If using a dictionary, the input plaquettes parameter should not "
            f"contain the entry 0. Found a value ({plaquettes[0]}) at entry 0."
        )

    if isinstance(plaquettes, list):
        plaquettes = {i + 1: plaquette for i, plaquette in enumerate(plaquettes)}

    _indices = list(range(1, len(plaquettes) + 1))
    template_plaquettes = template.instantiate(k, _indices)
    increments = template.get_increments()

    try:
        midline_indices = template.get_midline_plaquettes(k, orientation)
    except TQECException as e:
        raise TQECException(
            "The template does not have a midline. "
            "The observable qubits cannot be defined."
        ) from e

    observable_qubits = []
    for row_index, column_index in midline_indices:
        plaquette_index = template_plaquettes[row_index][column_index]
        if plaquette_index == 0:
            continue
        plaquette = plaquettes[plaquette_index]
        # GridQubits are indexed as (row, col), so (y, x)
        offset = Displacement(
            column_index * increments.x + plaquette.origin.x,
            row_index * increments.y + plaquette.origin.y,
        )
        observable_qubits += [
            (qubit + offset, 0)
            for qubit in plaquette.qubits.get_edge_qubits(orientation)
        ]
    return sorted(set(observable_qubits))
