"""Internal module defining a few useful functions to test the template library."""

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Generic, TypeVar

from tqec.compile.specs.enums import SpatialArms
from tqec.compile.specs.library.generators.memory import (
    get_memory_horizontal_boundary_raw_template,
    get_memory_horizontal_boundary_rpng_descriptions,
    get_memory_qubit_raw_template,
    get_memory_qubit_rpng_descriptions,
    get_memory_vertical_boundary_raw_template,
    get_memory_vertical_boundary_rpng_descriptions,
)
from tqec.compile.specs.library.generators.spatial import (
    get_spatial_cube_arm_raw_template,
    get_spatial_cube_arm_rpng_descriptions,
    get_spatial_cube_qubit_raw_template,
    get_spatial_cube_qubit_rpng_descriptions,
)
from tqec.plaquette.rpng import RPNGDescription
from tqec.templates.base import Template
from tqec.templates.qubit import (
    QubitHorizontalBorders,
    QubitSpatialCubeTemplate,
    QubitTemplate,
    QubitVerticalBorders,
)
from tqec.utils.enums import Basis, Orientation
from tqec.utils.frozendefaultdict import FrozenDefaultDict
from tqec.utils.position import PlaquettePosition2D, PlaquetteShape2D, Shift2D
from tqec.utils.scale import PlaquetteScalable2D

T = TypeVar("T", bound=Template, covariant=True)


@dataclass
class RPNGTemplate(Generic[T]):
    template: T
    mapping: FrozenDefaultDict[int, RPNGDescription]

    def instantiate(self, k: int) -> list[list[RPNGDescription]]:
        indices = self.template.instantiate(k)
        return [[self.mapping[i] for i in row] for row in indices]

    def shape(self, k: int) -> PlaquetteShape2D:
        """Returns the current template shape."""
        return self.template.shape(k)

    @property
    def scalable_shape(self) -> PlaquetteScalable2D:
        """Returns a scalable version of the template shape."""
        return self.template.scalable_shape

    def get_increments(self) -> Shift2D:
        """Get the default increments of the template.

        Returns:
            a displacement of the default increments in the x and y directions.
        """
        return self.template.get_increments()

    def instantiation_origin(self, k: int) -> PlaquettePosition2D:
        """Coordinates of the top-left entry origin.

        This property returns the coordinates of the origin of the plaquette
        (:class:`~tqec.plaquette.plaquette.Plaquette.origin`) that corresponds
        to the top-left entry of the array returned by
        :meth:`~tqec.templates.base.Template.instantiate`.

        Note:
            the returned coordinates are in plaquette coordinates. That means
            that, if you want to get the coordinates of the top-left plaquette
            origin (which is a qubit), you should multiply the coordinates
            returned by this method by the tiling increments.

        Args:
            k: scaling parameter used to instantiate the template.

        Returns:
            the coordinates of the origin of the plaquette
            (:class:`~tqec.plaquette.plaquette.Plaquette.origin`) that corresponds
            to the top-left entry of the array returned by
            :meth:`~tqec.templates.base.Template.instantiate`.
        """
        return self.template.instantiation_origin(k)

    def view_as_svg(
        self,
        k: int,
        write_to_filepath: str | Path | None = None,
        canvas_height: int = 500,
        opacity: float = 1.0,
        show_rg_fields: bool = True,
        show_plaquette_indices: bool = True,
        show_interaction_order: bool = True,
        show_hook_error: Callable[[RPNGDescription], bool] = lambda _: False,
    ) -> str:
        """Visualize the template as an SVG image.

        Args:
            k: scaling parameter used to instantiate the template.
            canvas_height: The height of the canvas in pixels.
            opacity: The opacity of the plaquettes.
            show_rg_fields: Whether to show the R/G fields on the data qubits. If True, the R
                field is shown as a small rectangle at the position of the data qubit, whose color
                corresponds to the basis. The G field is shown as a small circle at the position
                of the data qubit, whose color corresponds to the basis.
            show_plaquette_indices: Whether to show the indices of the plaquettes. If True, the
                indices are shown at the center of the plaquettes.
            show_interaction_order: Whether to show the interaction order of the plaquettes. If
                True, the interaction order is shown at each corner of the plaquette.
            show_hook_error: A predicate function that takes an RPNGDescription and returns True
                if the plaquette should be highlighted with the hook error. The hook error is
                shown as a black line along the hook edge.

        Returns:
            The SVG string of the visualization.
        """
        from tqec.plaquette.rpng.visualisation import rpng_svg_viewer

        svg_str = rpng_svg_viewer(
            self.instantiate(k),
            canvas_height=canvas_height,
            plaquette_indices=self.template.instantiate(k).tolist(),
            opacity=opacity,
            show_rg_fields=show_rg_fields,
            show_plaquette_indices=show_plaquette_indices,
            show_interaction_order=show_interaction_order,
            show_hook_error=show_hook_error,
        )
        if write_to_filepath is not None:
            with open(write_to_filepath, "w") as f:
                f.write(svg_str)
        return svg_str


def display_rpng_instantiation(instantiation: list[list[RPNGDescription]]) -> None:
    print(
        "\n".join(
            "  ".join(str(rpng) for rpng in rpng_list) for rpng_list in instantiation
        )
    )


def get_memory_qubit_rpng_template(
    orientation: Orientation = Orientation.HORIZONTAL,
    reset: Basis | None = None,
    measurement: Basis | None = None,
) -> RPNGTemplate[QubitTemplate]:
    return RPNGTemplate(
        template=get_memory_qubit_raw_template(),
        mapping=get_memory_qubit_rpng_descriptions(orientation, reset, measurement),
    )


def get_memory_vertical_boundary_rpng_template(
    orientation: Orientation = Orientation.HORIZONTAL,
    reset: Basis | None = None,
    measurement: Basis | None = None,
) -> RPNGTemplate[QubitVerticalBorders]:
    return RPNGTemplate(
        template=get_memory_vertical_boundary_raw_template(),
        mapping=get_memory_vertical_boundary_rpng_descriptions(
            orientation, reset, measurement
        ),
    )


def get_memory_horizontal_boundary_rpng_template(
    orientation: Orientation = Orientation.HORIZONTAL,
    reset: Basis | None = None,
    measurement: Basis | None = None,
) -> RPNGTemplate[QubitHorizontalBorders]:
    return RPNGTemplate(
        template=get_memory_horizontal_boundary_raw_template(),
        mapping=get_memory_horizontal_boundary_rpng_descriptions(
            orientation, reset, measurement
        ),
    )


def get_spatial_cube_qubit_rpng_template(
    spatial_boundary_basis: Basis,
    arms: SpatialArms,
    reset: Basis | None = None,
    measurement: Basis | None = None,
) -> RPNGTemplate[QubitSpatialCubeTemplate]:
    return RPNGTemplate(
        template=get_spatial_cube_qubit_raw_template(),
        mapping=get_spatial_cube_qubit_rpng_descriptions(
            spatial_boundary_basis, arms, reset, measurement
        ),
    )


def get_spatial_cube_arm_rpng_template(
    spatial_boundary_basis: Basis,
    arm: SpatialArms,
    reset: Basis | None = None,
    measurement: Basis | None = None,
) -> RPNGTemplate[QubitVerticalBorders | QubitHorizontalBorders]:
    return RPNGTemplate(
        template=get_spatial_cube_arm_raw_template(arm),
        mapping=get_spatial_cube_arm_rpng_descriptions(
            spatial_boundary_basis, arm, reset, measurement
        ),
    )
