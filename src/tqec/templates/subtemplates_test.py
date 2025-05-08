import itertools

import numpy
import numpy.typing as npt
import pytest

from tqec.templates.base import Template
from tqec.templates.layout import LayoutTemplate
from tqec.templates.qubit import QubitSpatialCubeTemplate, QubitTemplate
from tqec.templates.subtemplates import (
    get_spatially_distinct_3d_subtemplates,
    get_spatially_distinct_subtemplates,
)
from tqec.utils.position import BlockPosition2D

_TEMPLATES_TO_TEST = [
    QubitTemplate(),
    QubitSpatialCubeTemplate(),
    LayoutTemplate(
        {BlockPosition2D(0, 0): QubitTemplate(), BlockPosition2D(1, 1): QubitTemplate()}
    ),
]
_VALUES_OF_K_TO_TEST = [1, 10]
_VALUES_OF_MANHATTAN_RADIUS_TO_TEST = [0, 1, 3]


@pytest.mark.filterwarnings("ignore:Instantiating Qubit4WayJunctionTemplate")
@pytest.mark.parametrize(
    "template,k,r,avoid_zero_plaquettes",
    itertools.product(
        _TEMPLATES_TO_TEST,
        _VALUES_OF_K_TO_TEST,
        _VALUES_OF_MANHATTAN_RADIUS_TO_TEST,
        [True, False],
    ),
)
def test_get_spatially_distinct_subtemplates(
    template: Template, k: int, r: int, avoid_zero_plaquettes: bool
) -> None:
    instantiation = template.instantiate(k)
    n, m = instantiation.shape
    unique_subtemplates = get_spatially_distinct_subtemplates(
        instantiation, r, avoid_zero_plaquettes
    )

    # Check that the radius is correctly recovered.
    assert unique_subtemplates.manhattan_radius == r

    # Try to reconstruct the template instantiation from the computed sub-templates.
    instantiation_reconstruction: npt.NDArray[numpy.int_] = numpy.zeros(
        (n + 2 * r, m + 2 * r), dtype=numpy.int_
    )
    # The below line is not strictly needed, but makes type checkers happy with
    # type inference. See https://numpy.org/doc/stable/reference/typing.html#d-arrays
    # for more information on why this should be done.
    subtemplate_indices_list: list[list[int]] = (
        unique_subtemplates.subtemplate_indices.tolist()
    )
    for i, row in enumerate(subtemplate_indices_list):
        for j, subtemplate_index in enumerate(row):
            if subtemplate_index == 0:
                continue
            subtemplate = unique_subtemplates.subtemplates[subtemplate_index]
            ir_subarray = instantiation_reconstruction[
                i : i + 2 * r + 1,
                j : j + 2 * r + 1,
            ]
            # Try to superimpose `subtemplate` on `ir_subarray`.
            # Any non-zero entry in `ir_subarray` should exactly match with the
            # corresponding entry in `subtemplate`. Any zero entry can be
            # overridden by anything.
            nzx, nzy = ir_subarray.nonzero()
            numpy.testing.assert_array_equal(
                subtemplate[nzx, nzy], ir_subarray[nzx, nzy]
            )
            instantiation_reconstruction[
                i : i + 2 * r + 1,
                j : j + 2 * r + 1,
            ] = subtemplate
    # `instantiation` should now be exactly reconstructed in the inner part of
    # `instantiation_reconstruction`.
    numpy.testing.assert_array_equal(
        instantiation,
        instantiation_reconstruction[r : r + n, r : r + m],
    )
    # The borders of `instantiation_reconstruction` should be filled with zeros.
    top_border = instantiation_reconstruction[:r, :]
    bottom_border = instantiation_reconstruction[r + n :, :]
    left_border = instantiation_reconstruction[:, :r]
    right_border = instantiation_reconstruction[:, r + m :]
    for border in [top_border, bottom_border, left_border, right_border]:
        numpy.testing.assert_array_equal(border, numpy.zeros_like(border))


_TEMPLATE_PAIRS_TO_TEST = [
    (QubitTemplate(), QubitSpatialCubeTemplate()),
    (
        LayoutTemplate(
            {
                BlockPosition2D(0, 0): QubitTemplate(),
                BlockPosition2D(1, 1): QubitSpatialCubeTemplate(),
            }
        ),
        LayoutTemplate(
            {
                BlockPosition2D(0, 0): QubitSpatialCubeTemplate(),
                BlockPosition2D(1, 1): QubitTemplate(),
            }
        ),
    ),
]


@pytest.mark.filterwarnings("ignore:Instantiating Qubit4WayJunctionTemplate")
@pytest.mark.parametrize(
    "templates,k,r,avoid_zero_plaquettes",
    itertools.product(
        _TEMPLATE_PAIRS_TO_TEST,
        _VALUES_OF_K_TO_TEST,
        _VALUES_OF_MANHATTAN_RADIUS_TO_TEST,
        [True, False],
    ),
)
def test_get_spatially_distinct_3d_subtemplates(
    templates: tuple[Template, ...],
    k: int,
    r: int,
    avoid_zero_plaquettes: bool,
) -> None:
    instantiations = tuple(t.instantiate(k) for t in templates)
    instantiation_3d = numpy.stack(instantiations, axis=2)
    unique_3d_subtemplates = get_spatially_distinct_3d_subtemplates(
        instantiations, r, avoid_zero_plaquettes
    )
    # Check that the radius is correctly recovered.
    assert unique_3d_subtemplates.manhattan_radius == r

    # Try to reconstruct the templates instantiation from the computed sub-templates.
    n, m, t = instantiation_3d.shape
    instantiation_reconstruction: npt.NDArray[numpy.int_] = numpy.zeros(
        (n + 2 * r, m + 2 * r, t), dtype=numpy.int_
    )
    # The below line is not strictly needed, but makes type checkers happy with
    # type inference. See https://numpy.org/doc/stable/reference/typing.html#d-arrays
    # for more information on why this should be done.
    subtemplate_indices_list: list[list[list[int]]] = (
        unique_3d_subtemplates.subtemplate_indices.tolist()
    )
    for i, row in enumerate(subtemplate_indices_list):
        for j, subtemplate_index_arr in enumerate(row):
            if all(subti == 0 for subti in subtemplate_index_arr):
                continue
            subt_index_tup = tuple(subtemplate_index_arr)
            subtemplate = unique_3d_subtemplates.subtemplates[subt_index_tup]
            ir_subarray = instantiation_reconstruction[
                i : i + 2 * r + 1, j : j + 2 * r + 1, :
            ]
            # Try to superimpose `subtemplate` on `ir_subarray`.
            # Any non-zero entry in `ir_subarray` should exactly match with the
            # corresponding entry in `subtemplate`. Any zero entry can be
            # overridden by anything.
            nzx, nzy, nzt = ir_subarray.nonzero()
            numpy.testing.assert_array_equal(
                subtemplate[nzx, nzy, nzt], ir_subarray[nzx, nzy, nzt]
            )
            instantiation_reconstruction[i : i + 2 * r + 1, j : j + 2 * r + 1, :] = (
                subtemplate
            )
    # `instantiation` should now be exactly reconstructed in the inner part of
    # `instantiation_reconstruction`.
    numpy.testing.assert_array_equal(
        instantiation_3d,
        instantiation_reconstruction[r : r + n, r : r + m, :],
    )
    # The borders of `instantiation_reconstruction` should be filled with zeros.
    top_border = instantiation_reconstruction[:r, :, :]
    bottom_border = instantiation_reconstruction[r + n :, :, :]
    left_border = instantiation_reconstruction[:, :r, :]
    right_border = instantiation_reconstruction[:, r + m :, :]
    for border in [top_border, bottom_border, left_border, right_border]:
        numpy.testing.assert_array_equal(border, numpy.zeros_like(border))
