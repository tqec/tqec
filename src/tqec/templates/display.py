"""Provides functions to pretty-print :class:`~tqec.templates.base.Template` instances."""

from __future__ import annotations

import typing as ty

import numpy
import numpy.typing as npt

from tqec.templates.base import Template


def display_template(
    template: Template, k: int, plaquette_indices: ty.Sequence[int] | None = None
) -> None:
    """Display a template instance with ASCII output.

    Args:
        template: the Template instance to display.
        k: scaling factor.
        plaquette_indices: the plaquette indices that are forwarded to the call
            to `template.instantiate` to get the actual template representation.
            If None, default to ``range(1, template.expected_plaquettes_number + 1)``.

    """
    if plaquette_indices is None:
        plaquette_indices = tuple(range(1, template.expected_plaquettes_number + 1))
    display_template_from_instantiation(template.instantiate(k, plaquette_indices))


def display_template_from_instantiation(
    instantiation: npt.NDArray[numpy.int_],
) -> None:  # pragma: no cover
    """Display an array representing a template instantiation with ASCII output.

    Args:
        instantiation: the integer array obtained from the `Template.instantiate`
            method.

    """
    print(get_template_representation_from_instantiation(instantiation))


def get_template_representation_from_instantiation(
    instantiation: npt.NDArray[numpy.int_],
) -> str:
    """Get the pretty-string representation of a template instantiation."""
    max_integer = numpy.max(instantiation)
    pad = len(str(max_integer)) + 1
    return "\n".join(
        " ".join((str(num) if num != 0 else ".").rjust(pad) for num in line)
        for line in instantiation
    )
