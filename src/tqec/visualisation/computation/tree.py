"""Contains helpers to visualise a :class:`~tqec.compile.tree.tree.LayerTree` instance."""

from __future__ import annotations

import warnings
from collections.abc import Sequence
from dataclasses import dataclass

import stim
import svg
from typing_extensions import override

from tqec.circuit.qubit import GridQubit
from tqec.compile.blocks.layers.atomic.layout import LayoutLayer
from tqec.compile.observables.builder import Observable
from tqec.compile.tree.node import LayerNode, NodeWalker
from tqec.utils.exceptions import TQECError
from tqec.visualisation.computation.plaquette.grid import plaquette_grid_svg_viewer


@dataclass(frozen=True)
class VisualisationData:
    """Holds visualisation data for one layer.

    This dataclass holds data that will then be used to visualise one layer of the visualised
    :class:`~tqec.compile.tree.tree.LayerTree` instance.

    """

    layer: LayoutLayer
    start_moment: int
    end_moment: int
    observable: Observable | None = None

    def __post_init__(self) -> None:
        """Check that the instance is valid.

        Raises:
            AssertionError: when ``self.start_moment <= self.end_moment``.

        """
        assert self.start_moment <= self.end_moment

    def with_duration_offset(self, offset: int) -> VisualisationData:
        """Add a time offset to the time-related data in ``self``.

        This method is used to get a new instance of :class:`.VisualisationData` with a modified
        offset in time, for example when visualising each repetitions in a REPEAT loop.

        """
        return VisualisationData(
            self.layer,
            self.start_moment + offset,
            self.end_moment + offset,
            self.observable,
        )


class LayerVisualiser(NodeWalker):
    """A node walker that draws the visited :class:`~tqec.compile.tree.tree.LayerTree` instance."""

    def __init__(
        self,
        k: int,
        errors: Sequence[stim.ExplainedError] = tuple(),
        show_observable: int | None = None,
        font_size: float = 0.5,
        font_color: str = "red",
        top_left_qubit: GridQubit | None = None,
        bottom_right_qubit: GridQubit | None = None,
    ):
        """Create a :class:`.LayerVisualiser` instance.

        Args:
            k: scaling factor.
            errors: a (possibly empty) sequence of errors to draw on the resulting SVG
                representation.
            show_observable: also visualise the observable at the provided index if not None.
            font_size: size of the font used to write the moment range of each layer that is drawn.
            font_color: color of the font used to write the moment range of each layer that is
                drawn.
            top_left_qubit: qubit that should be at the top-left corner of the viewport. Can be used
                top only visualise part of a computation, or to add empty border. If not provided,
                the top-left qubit is automatically computed from the drawn computation.
            bottom_right_qubit: qubit that should be at the bottom-right corner of the viewport. Can
                be used top only visualise part of a computation, or to add empty border. If not
                provided, the bottom-right qubit is automatically computed from the drawn
                computation.

        """
        super().__init__()
        self._k = k
        self._stack: list[list[VisualisationData]] = [[]]
        self._errors: list[stim.ExplainedError] = list(errors)
        self._observable_index = show_observable
        self._font_size = font_size
        self._font_color = font_color
        self._top_left_qubit = top_left_qubit
        self._bottom_right_qubit = bottom_right_qubit

    @override
    def enter_node(self, node: LayerNode) -> None:
        if node.is_repeated:
            self._stack.append([])

    @override
    def exit_node(self, node: LayerNode) -> None:
        if not node.is_repeated:
            return
        if len(self._stack) < 2:
            raise TQECError(
                "Logical error: exiting a repeated node with less than 2 entries in the stack."
            )
        assert node.repetitions is not None
        repetitions = node.repetitions.integer_eval(self._k)
        elements = self._stack.pop()
        duration = elements[-1].end_moment - elements[0].start_moment
        # Repeat the body of the REPEAT loop.
        for r in range(repetitions):
            for e in elements:
                self._stack[-1].append(e.with_duration_offset(r * duration))

    @override
    def visit_node(self, node: LayerNode) -> None:
        if not node.is_leaf:
            return
        layer = node._layer
        assert isinstance(layer, LayoutLayer)
        start = self.current_moment
        end = start + layer.num_moments(self._k)
        observable: Observable | None = None
        if self._observable_index is not None:
            annotations = node._annotations.get(self._k)
            if annotations is not None:
                observable = next(
                    (
                        obs
                        for obs in node.get_annotations(self._k).observables
                        if obs.observable_index == self._observable_index
                    ),
                    None,
                )
        self._stack[-1].append(VisualisationData(layer, start, end, observable))

    @property
    def current_moment(self) -> int:
        """Return the index of the first moment on which something can be scheduled.

        Returns:
            1 + the index of the last used moment.

        """
        if self._stack[-1]:
            return self._stack[-1][-1].end_moment
        elif len(self._stack) > 1 and self._stack[-2]:
            return self._stack[-2][-1].end_moment
        else:
            return 0

    def get_moment_text(self, start: int, end: int) -> svg.Text:
        """Return an SVG representation of a text indicating the moments covered by [start, end].

        Args:
            start: initial moment.
            end: final (exclusive) moment.

        """
        return svg.Text(
            x=0.25,
            y=0.15,
            fill=self._font_color,
            font_size=self._font_size,
            text_anchor="start",
            dominant_baseline="hanging",
            text=f"Moments: {start} -> {end}",
        )

    def _get_errors_within(self, start: int, end: int) -> list[stim.ExplainedError]:
        return [
            err
            for err in self._errors
            if (start <= err.circuit_error_locations[0].tick_offset < end)
        ]

    @property
    def visualisations(self) -> list[str]:
        """Build and returns a list of SVG strings representing ``self``.

        Warning:
            Even though this is a property, non-trivial computations are made here. It is advised
            to only use that property once, when the visualisation is needed.

        """
        if len(self._stack) > 1:
            warnings.warn(
                "Trying to get the layer visualisations but the stack contains more than one "
                "element. You may get incorrect results. Did you forget to close a REPEAT block?"
            )
        if self._observable_index and not any(data.observable for data in self._stack[0]):
            raise TQECError(
                f"Observable index {self._observable_index} requested, but no observable "
                "with this index was found to be annotated in the layer visualisation data."
            )
        ret: list[str] = []
        for element in self._stack[0]:
            template, plaquettes = element.layer.to_template_and_plaquettes()
            instantiation = template.instantiate_list(self._k)
            drawers = plaquettes.collection.map_values(
                lambda plaq: plaq.debug_information.get_svg_drawer()
            )
            tlq, _ = element.layer.qubit_bounds

            svg_element = plaquette_grid_svg_viewer(
                instantiation,
                drawers,
                top_left_used_qubit=tlq.to_grid_qubit(self._k),
                view_box_top_left_qubit=self._top_left_qubit,
                view_box_bottom_right_qubit=self._bottom_right_qubit,
                errors=self._get_errors_within(element.start_moment, element.end_moment),
                observable=element.observable,
            )
            # Adding text to mark which TICKs are concerned.
            assert svg_element.elements is not None
            svg_element.elements.append(
                self.get_moment_text(element.start_moment, element.end_moment)
            )
            ret.append(svg_element.as_str())
        return ret
