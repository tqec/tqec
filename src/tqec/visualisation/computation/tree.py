from __future__ import annotations

import warnings
from dataclasses import dataclass
from typing import Sequence

import stim
import svg
from typing_extensions import override

from tqec.circuit.qubit import GridQubit
from tqec.compile.blocks.layers.atomic.layout import LayoutLayer
from tqec.compile.observables.builder import Observable
from tqec.compile.tree.node import LayerNode, NodeWalker
from tqec.utils.exceptions import TQECException
from tqec.visualisation.computation.plaquette.grid import plaquette_grid_svg_viewer


@dataclass(frozen=True)
class VisualisationData:
    layer: LayoutLayer
    start_moment: int
    end_moment: int
    observable: Observable | None = None

    def __post_init__(self) -> None:
        assert self.start_moment <= self.end_moment

    def with_duration_offset(self, offset: int) -> VisualisationData:
        return VisualisationData(
            self.layer, self.start_moment + offset, self.end_moment + offset, self.observable
        )


class LayerVisualiser(NodeWalker):
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
            raise TQECException(
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
        start = self.current_tick
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
    def current_tick(self) -> int:
        if self._stack[-1]:
            return self._stack[-1][-1].end_moment
        elif len(self._stack) > 1 and self._stack[-2]:
            return self._stack[-2][-1].end_moment
        else:
            return 0

    def get_moment_text(self, start: int, end: int) -> svg.Text:
        return svg.Text(
            x=0,
            y=0,
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
        if len(self._stack) > 1:
            warnings.warn(
                "Trying to get the layer visualisations but the stack contains more than one "
                "element. You may get incorrect results. Did you forget to close a REPEAT block?"
            )
        if self._observable_index and not any(data.observable for data in self._stack[0]):
            raise TQECException(
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
