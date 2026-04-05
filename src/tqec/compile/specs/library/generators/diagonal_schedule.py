"""Generator for diagonal schedule convention.

This module provides the DiagonalScheduleGenerator class that implements
diagonal syndrome extraction schedules for surface code plaquettes.
"""

from __future__ import annotations

from typing import Literal

from tqec.compile.specs.library.generators.fixed_bulk import FixedBulkConventionGenerator
from tqec.plaquette.compilation.base import PlaquetteCompiler
from tqec.plaquette.compilation.passes.scheduling import ChangeSchedulePass
from tqec.plaquette.compilation.passes.sort_targets import SortTargetsPass
from tqec.plaquette.rpng import RPNGDescription
from tqec.plaquette.rpng.translators.default import DefaultRPNGTranslator
from tqec.utils.enums import Basis, Orientation
from tqec.plaquette.enums import PlaquetteOrientation
from tqec.utils.frozendefaultdict import FrozenDefaultDict
from tqec.compile.specs.enums import SpatialArms


def create_diagonal_schedule_compiler() -> PlaquetteCompiler:
    """Create a compiler that handles schedule 7 (for qubit index 6) but keeps original basis."""
    return PlaquetteCompiler(
        "DiagonalScheduleIdentity",
        [
            # Compact schedule map: {0: 0, 1: 1, 2: 2, 3: 3, 4: 4, 5: 5, 6: 6, 7: 7}
            # No gaps - direct mapping to avoid idle moments
            ChangeSchedulePass({i: i for i in range(8)}),
            # Sort the instruction targets to normalize the circuits.
            SortTargetsPass(),
        ],
        mergeable_instructions_modifier=lambda x: x | frozenset(["H"]),
    )


class DiagonalScheduleGenerator(FixedBulkConventionGenerator):
    """Generator with diagonal plaquette configurations for syndrome extraction.
    
    This generator implements diagonal schedules:
    - X-basis bulk: schedules [1, 4, 3, 2] (instead of [1, 2, 3, 5])
    - Z-basis bulk: schedules [6, 4, 3, 5] (instead of [1, 2, 3, 5])
    
    The diagonal schedule enables diagonal syndrome extraction patterns.
    """
    
    def __init__(
        self,
        translator=None,
        compiler=None,
    ):
        """Initialize the diagonal schedule generator.
        
        Args:
            translator: RPNG translator instance. Defaults to DefaultRPNGTranslator.
            compiler: Plaquette compiler instance. Defaults to diagonal schedule compiler.
        """
        if translator is None:
            translator = DefaultRPNGTranslator()
        if compiler is None:
            compiler = create_diagonal_schedule_compiler()
        super().__init__(translator, compiler)
    
    def get_diagonal_bulk_rpng_descriptions(
        self,
        reset: Basis | None = None,
        measurement: Basis | None = None,
        reset_and_measured_indices: tuple[Literal[0, 1, 2, 3], ...] = (0, 1, 2, 3),
    ) -> dict[Basis, dict[Orientation, RPNGDescription]]:
        """Get diagonal plaquettes with custom schedules.
        
        Args:
            reset: basis of the reset operation performed on data-qubits
            measurement: basis of the measurement operation performed on data-qubits
            reset_and_measured_indices: data-qubit indices that should be impacted
            
        Returns:
            a mapping with 4 plaquettes: X and Z basis, both orientations
        """
        # _r/_m: reset/measurement basis applied to each data-qubit
        _r = reset.value.lower() if reset is not None else "-"
        _m = measurement.value.lower() if measurement is not None else "-"
        
        # rs/ms: resets/measurements basis applied for each data-qubit
        rs = [_r if i in reset_and_measured_indices else "-" for i in range(4)]
        ms = [_m if i in reset_and_measured_indices else "-" for i in range(4)]
        
        # Diagonal schedules:
        # X: [1, 4, 3, 2] (instead of original [1, 2, 3, 5])
        # Z: [6, 4, 3, 5] (instead of original [1, 2, 3, 5])
        return {
            Basis.X: {
                Orientation.VERTICAL: RPNGDescription.from_string(
                    " ".join(f"{r}x{s}{m}" for r, s, m in zip(rs, [1, 4, 3, 2], ms))
                ),
                Orientation.HORIZONTAL: RPNGDescription.from_string(
                    " ".join(f"{r}x{s}{m}" for r, s, m in zip(rs, [1, 4, 3, 2], ms))
                ),
            },
            Basis.Z: {
                Orientation.VERTICAL: RPNGDescription.from_string(
                    " ".join(f"{r}z{s}{m}" for r, s, m in zip(rs, [6, 4, 3, 5], ms))
                ),
                Orientation.HORIZONTAL: RPNGDescription.from_string(
                    " ".join(f"{r}z{s}{m}" for r, s, m in zip(rs, [6, 4, 3, 5], ms))
                ),
            },
        }
    
    def get_diagonal_2_body_rpng_descriptions(
        self,
    ) -> dict[Basis, dict[PlaquetteOrientation, RPNGDescription]]:
        """Get diagonal 2-body boundary plaquettes.
        
        These are derived from the diagonal bulk plaquettes by omitting qubits.
        """
        return {
            Basis.X: {
                # Derived from "-x1- -x4- -x3- -x2-"
                PlaquetteOrientation.DOWN: RPNGDescription.from_string("-x1- -x4- ---- ----"),
                PlaquetteOrientation.LEFT: RPNGDescription.from_string("---- -x4- ---- -x2-"),
                PlaquetteOrientation.UP: RPNGDescription.from_string("---- ---- -x3- -x2-"),
                PlaquetteOrientation.RIGHT: RPNGDescription.from_string("-x1- ---- -x3- ----"),
            },
            Basis.Z: {
                # Derived from "-z6- -z4- -z3- -z5-"
                PlaquetteOrientation.DOWN: RPNGDescription.from_string("-z6- -z4- ---- ----"),
                PlaquetteOrientation.LEFT: RPNGDescription.from_string("---- -z4- ---- -z5-"),
                PlaquetteOrientation.UP: RPNGDescription.from_string("---- ---- -z3- -z5-"),
                PlaquetteOrientation.RIGHT: RPNGDescription.from_string("-z6- ---- -z3- ----"),
            },
        }
    
    def get_2_body_rpng_descriptions(
        self,
        reset: Basis | None = None,
        measurement: Basis | None = None,
    ) -> dict[Basis, dict[PlaquetteOrientation, RPNGDescription]]:
        """Get 2-body boundary plaquettes (wrapper for diagonal version)."""
        return self.get_diagonal_2_body_rpng_descriptions()
    
    def get_bulk_rpng_descriptions(
        self,
        reset: Basis | None = None,
        measurement: Basis | None = None,
        reset_and_measured_indices: tuple[Literal[0, 1, 2, 3], ...] = (0, 1, 2, 3),
    ) -> dict[Basis, dict[Orientation, RPNGDescription]]:
        """Get bulk plaquettes (wrapper for diagonal version)."""
        return self.get_diagonal_bulk_rpng_descriptions(reset, measurement, reset_and_measured_indices)
    
    def get_3_body_rpng_descriptions(
        self,
        reset: Basis | None = None,
        measurement: Basis | None = None,
    ) -> tuple[RPNGDescription, RPNGDescription, RPNGDescription, RPNGDescription]:
        """Return the four 3-body stabilizer measurement plaquettes for diagonal schedule.
        
        These correspond to corner plaquettes where two adjacent arms are missing.
        Each connects to 3 data qubits (omitting one qubit, indicated by ----).
        
        For diagonal schedule:
        - Z plaquettes use schedule [6,4,3,5] instead of [1,4,3,5]
        - X plaquettes use schedule [1,4,3,2] instead of [1,2,3,5]
        """
        r = reset.value.lower() if reset is not None else "-"
        m = measurement.value.lower() if measurement is not None else "-"
        
        # Diagonal 3-body plaquettes
        return (
            RPNGDescription.from_string(f"---- {r}z4{m} {r}z3{m} {r}z5{m}"),  # Top-left Z
            RPNGDescription.from_string(f"{r}x1{m} ---- {r}x3{m} {r}x2{m}"),  # Top-right X
            RPNGDescription.from_string(f"{r}x1{m} {r}x4{m} ---- {r}x2{m}"),  # Bottom-left X
            RPNGDescription.from_string(f"{r}z6{m} {r}z4{m} {r}z3{m} ----"),  # Bottom-right Z
        )
    
    def get_memory_qubit_rpng_descriptions(
        self,
        z_orientation: Orientation = Orientation.HORIZONTAL,
        reset: Basis | None = None,
        measurement: Basis | None = None,
    ) -> FrozenDefaultDict[int, RPNGDescription]:
        """Override to use diagonal plaquettes."""
        # Border plaquette indices
        up, down, left, right = (
            (6, 13, 7, 12) if z_orientation == Orientation.VERTICAL else (5, 14, 8, 11)
        )
        # Basis for top/bottom and left/right boundary plaquettes
        hbasis = Basis.Z if z_orientation == Orientation.HORIZONTAL else Basis.X
        vbasis = hbasis.flipped()
        # Hook errors orientations
        zhook = z_orientation.flip()
        xhook = zhook.flip()
        
        # Get diagonal plaquette descriptions
        bulk_descriptions = self.get_diagonal_bulk_rpng_descriptions(reset, measurement)
        two_body_descriptions = self.get_diagonal_2_body_rpng_descriptions()
        
        # Return a FrozenDefaultDict like the original
        return FrozenDefaultDict(
            {
                up: two_body_descriptions[vbasis][PlaquetteOrientation.UP],
                left: two_body_descriptions[hbasis][PlaquetteOrientation.LEFT],
                # Bulk - using diagonal configurations
                9: bulk_descriptions[Basis.Z][zhook],
                10: bulk_descriptions[Basis.X][xhook],
                right: two_body_descriptions[hbasis][PlaquetteOrientation.RIGHT],
                down: two_body_descriptions[vbasis][PlaquetteOrientation.DOWN],
            },
            default_value=RPNGDescription.empty(),
        )
    
    def get_spatial_cube_qubit_rpng_descriptions(
        self,
        spatial_boundary_basis: Basis,
        arms: SpatialArms,
        reset: Basis | None = None,
        measurement: Basis | None = None,
    ) -> FrozenDefaultDict[int, RPNGDescription]:
        """Return RPNG descriptions for spatial cube qubit plaquettes with diagonal schedule."""
        from tqec.utils.exceptions import TQECError
        
        # Check if arms is invalid
        if len(arms) == 0 or len(arms) == 1:
            raise TQECError(
                f"Spatial cube must have at least 2 arms. Got {arms}."
            )
        if arms in SpatialArms.I_shaped_arms():
            raise TQECError(
                "I-shaped spatial junctions should not use get_spatial_cube_qubit_template."
            )
        
        # Get parity information
        boundary_is_z = spatial_boundary_basis == Basis.Z
        
        # Pre-define collection of plaquette descriptions
        corner_descriptions = self.get_3_body_rpng_descriptions(reset, measurement)
        bulk_descriptions = self.get_diagonal_bulk_rpng_descriptions(reset, measurement)
        two_body_descriptions = self.get_diagonal_2_body_rpng_descriptions()
        
        mapping: dict[int, RPNGDescription] = {}
        
        ####################
        #    Boundaries    #
        ####################
        # Fill boundaries that have no arms
        _sbb = spatial_boundary_basis
        if SpatialArms.UP not in arms:
            corner, bulk = (1, 10) if boundary_is_z else (2, 9)
            mapping[corner] = mapping[bulk] = two_body_descriptions[_sbb][PlaquetteOrientation.UP]
        if SpatialArms.RIGHT not in arms:
            corner, bulk = (4, 21) if boundary_is_z else (2, 22)
            mapping[corner] = mapping[bulk] = two_body_descriptions[_sbb][PlaquetteOrientation.RIGHT]
        if SpatialArms.DOWN not in arms:
            corner, bulk = (4, 23) if boundary_is_z else (3, 24)
            mapping[corner] = mapping[bulk] = two_body_descriptions[_sbb][PlaquetteOrientation.DOWN]
        if SpatialArms.LEFT not in arms:
            corner, bulk = (1, 12) if boundary_is_z else (3, 11)
            mapping[corner] = mapping[bulk] = two_body_descriptions[_sbb][PlaquetteOrientation.LEFT]
        
        # Remove corner if both adjacent arms missing
        if SpatialArms.LEFT not in arms and SpatialArms.UP not in arms and boundary_is_z:
            del mapping[1]
        if SpatialArms.UP not in arms and SpatialArms.RIGHT not in arms and not boundary_is_z:
            del mapping[2]
        if SpatialArms.DOWN not in arms and SpatialArms.LEFT not in arms and not boundary_is_z:
            del mapping[3]
        if SpatialArms.RIGHT not in arms and SpatialArms.DOWN not in arms and boundary_is_z:
            del mapping[4]
        
        ####################
        #       Bulk       #
        ####################
        # Hook orientations based on arms
        zup = zdown = Orientation.VERTICAL if boundary_is_z else Orientation.HORIZONTAL
        zright = zleft = zup.flip()
        
        # Flip hook error orientation if arm is missing
        zup = zup if SpatialArms.UP in arms else zup.flip()
        zdown = zdown if SpatialArms.DOWN in arms else zdown.flip()
        zright = zright if SpatialArms.RIGHT in arms else zright.flip()
        zleft = zleft if SpatialArms.LEFT in arms else zleft.flip()
        
        xup, xdown, xright, xleft = (zup.flip(), zdown.flip(), zright.flip(), zleft.flip())
        
        # Set bulk Z plaquettes
        mapping[5] = mapping[13] = bulk_descriptions[Basis.Z][zup]
        mapping[8] = mapping[15] = bulk_descriptions[Basis.Z][zdown]
        mapping[14] = bulk_descriptions[Basis.Z][zright]
        mapping[16] = bulk_descriptions[Basis.Z][zleft]
        
        # Set bulk X plaquettes
        mapping[6] = mapping[17] = bulk_descriptions[Basis.X][xup]
        mapping[7] = mapping[19] = bulk_descriptions[Basis.X][xdown]
        mapping[18] = bulk_descriptions[Basis.X][xright]
        mapping[20] = bulk_descriptions[Basis.X][xleft]
        
        # Override corner plaquettes to 3-body when both adjacent arms missing
        if SpatialArms.LEFT not in arms and SpatialArms.UP not in arms and boundary_is_z:
            mapping[5] = corner_descriptions[0]
        if SpatialArms.UP not in arms and SpatialArms.RIGHT not in arms and not boundary_is_z:
            mapping[6] = corner_descriptions[1]
        if SpatialArms.DOWN not in arms and SpatialArms.LEFT not in arms and not boundary_is_z:
            mapping[7] = corner_descriptions[2]
        if SpatialArms.RIGHT not in arms and SpatialArms.DOWN not in arms and boundary_is_z:
            mapping[8] = corner_descriptions[3]
        
        # Sanity check
        bulk_plaquette_indices = set(range(5, 9)) | set(range(13, 21))
        missing_bulk_plaquette_indices = bulk_plaquette_indices - mapping.keys()
        assert not missing_bulk_plaquette_indices, (
            "Some plaquette(s) in the bulk were not correctly assigned to a "
            f"RPNGDescription. Missing indices: {missing_bulk_plaquette_indices}."
        )
        
        return FrozenDefaultDict(mapping, default_value=RPNGDescription.empty())
    
    def get_spatial_cube_arm_rpng_descriptions(
        self,
        spatial_boundary_basis: Basis,
        arms: SpatialArms,
        linked_cubes: tuple,
        reset: Basis | None = None,
        measurement: Basis | None = None,
    ) -> FrozenDefaultDict[int, RPNGDescription]:
        """Return RPNG descriptions for spatial cube arm plaquettes with diagonal schedule."""
        from tqec.utils.exceptions import TQECError
        
        if len(arms) == 2 and arms not in SpatialArms.I_shaped_arms():
            raise TQECError(
                f"The two provided arms cannot form a spatial pipe. Got {arms} but "
                f"expected either a single {SpatialArms.__name__} or two but in a "
                f"line (e.g., {SpatialArms.I_shaped_arms()})."
            )
        
        if arms in [SpatialArms.LEFT, SpatialArms.RIGHT, SpatialArms.LEFT | SpatialArms.RIGHT]:
            return self._get_left_right_spatial_cube_arm_rpng_descriptions(
                spatial_boundary_basis, arms, linked_cubes, reset, measurement
            )
        if arms in [SpatialArms.UP, SpatialArms.DOWN, SpatialArms.UP | SpatialArms.DOWN]:
            return self._get_up_down_spatial_cube_arm_rpng_descriptions(
                spatial_boundary_basis, arms, linked_cubes, reset, measurement
            )
        raise TQECError(f"Got an invalid arm: {arms}.")
    
    def _get_left_right_spatial_cube_arm_rpng_descriptions(
        self,
        spatial_boundary_basis: Basis,
        arms: SpatialArms,
        linked_cubes: tuple,
        reset: Basis | None = None,
        measurement: Basis | None = None,
    ) -> FrozenDefaultDict[int, RPNGDescription]:
        """Left-right spatial cube arm RPNG descriptions with diagonal schedule."""
        # Bulk plaquettes for left and right parts with different reset/measure indices
        left_boundary_descriptions = self.get_diagonal_bulk_rpng_descriptions(reset, measurement, (1, 3))
        right_boundary_descriptions = self.get_diagonal_bulk_rpng_descriptions(reset, measurement, (0, 2))
        two_body_descriptions = self.get_diagonal_2_body_rpng_descriptions()
        
        # Hook errors adapted to boundary basis
        zhook = Orientation.HORIZONTAL if spatial_boundary_basis == Basis.Z else Orientation.VERTICAL
        xhook = zhook.flip()
        
        # Plaquette indices
        up = 2 if spatial_boundary_basis == Basis.Z else 1
        down = 3 if spatial_boundary_basis == Basis.Z else 4
        
        mapping = {
            up: two_body_descriptions[spatial_boundary_basis][PlaquetteOrientation.UP],
            down: two_body_descriptions[spatial_boundary_basis][PlaquetteOrientation.DOWN],
            5: left_boundary_descriptions[Basis.Z][zhook],
            6: left_boundary_descriptions[Basis.X][xhook],
            7: right_boundary_descriptions[Basis.X][xhook],
            8: right_boundary_descriptions[Basis.Z][zhook],
        }
        
        # Handle 3-body corner plaquettes
        _corners = self.get_3_body_rpng_descriptions(reset, measurement)
        u, v = linked_cubes
        _sbb = spatial_boundary_basis
        
        # Replace top plaquette if it should be a 3-body stabilizer
        if SpatialArms.LEFT in arms and _sbb == Basis.Z and SpatialArms.UP in v.spatial_arms:
            mapping[up] = _corners[0]
        if SpatialArms.RIGHT in arms and _sbb == Basis.X and SpatialArms.UP in u.spatial_arms:
            mapping[up] = _corners[1]
        # Replace bottom plaquette if it should be a 3-body stabilizer
        if SpatialArms.LEFT in arms and _sbb == Basis.X and SpatialArms.DOWN in v.spatial_arms:
            mapping[down] = _corners[2]
        if SpatialArms.RIGHT in arms and _sbb == Basis.Z and SpatialArms.DOWN in u.spatial_arms:
            mapping[down] = _corners[3]
        
        return FrozenDefaultDict(mapping, default_value=RPNGDescription.empty())
    
    def _get_up_down_spatial_cube_arm_rpng_descriptions(
        self,
        spatial_boundary_basis: Basis,
        arms: SpatialArms,
        linked_cubes: tuple,
        reset: Basis | None = None,
        measurement: Basis | None = None,
    ) -> FrozenDefaultDict[int, RPNGDescription]:
        """Up-down spatial cube arm RPNG descriptions with diagonal schedule."""
        # Bulk plaquettes for up and down parts
        up_bulk_descriptions = self.get_diagonal_bulk_rpng_descriptions(reset, measurement, (2, 3))
        down_bulk_descriptions = self.get_diagonal_bulk_rpng_descriptions(reset, measurement, (0, 1))
        two_body_descriptions = self.get_diagonal_2_body_rpng_descriptions()
        
        # Hook errors adapted to boundary basis
        zhook = Orientation.VERTICAL if spatial_boundary_basis == Basis.Z else Orientation.HORIZONTAL
        xhook = zhook.flip()
        
        # Plaquette indices
        left = 3 if spatial_boundary_basis == Basis.Z else 1
        right = 2 if spatial_boundary_basis == Basis.Z else 4
        
        mapping = {
            left: two_body_descriptions[spatial_boundary_basis][PlaquetteOrientation.LEFT],
            right: two_body_descriptions[spatial_boundary_basis][PlaquetteOrientation.RIGHT],
            5: up_bulk_descriptions[Basis.Z][zhook],
            6: up_bulk_descriptions[Basis.X][xhook],
            7: down_bulk_descriptions[Basis.X][xhook],
            8: down_bulk_descriptions[Basis.Z][zhook],
        }
        
        # Handle 3-body corner plaquettes
        _corners = self.get_3_body_rpng_descriptions(reset, measurement)
        u, v = linked_cubes
        _sbb = spatial_boundary_basis
        
        # Replace left plaquette if it should be a 3-body stabilizer
        if SpatialArms.UP in arms and _sbb == Basis.Z and SpatialArms.LEFT in v.spatial_arms:
            mapping[left] = _corners[0]
        if SpatialArms.DOWN in arms and _sbb == Basis.X and SpatialArms.LEFT in u.spatial_arms:
            mapping[left] = _corners[2]
        # Replace right plaquette if it should be a 3-body stabilizer
        if SpatialArms.UP in arms and _sbb == Basis.X and SpatialArms.RIGHT in v.spatial_arms:
            mapping[right] = _corners[1]
        if SpatialArms.DOWN in arms and _sbb == Basis.Z and SpatialArms.RIGHT in u.spatial_arms:
            mapping[right] = _corners[3]
        
        return FrozenDefaultDict(mapping, default_value=RPNGDescription.empty())
    
    def get_memory_qubit_raw_template(self):
        """Return the template instance needed to implement a standard memory operation on a logical qubit."""
        from tqec.templates.qubit import QubitTemplate
        return QubitTemplate()
    
    def get_spatial_cube_qubit_raw_template(self):
        """Return the template instance needed to implement a spatial cube qubit."""
        from tqec.templates.qubit import QubitSpatialCubeTemplate
        return QubitSpatialCubeTemplate()
    
    def get_spatial_cube_arm_raw_template(self, arms: SpatialArms):
        """Return the template instance needed to implement the given spatial arms."""
        from tqec.utils.exceptions import TQECError
        from tqec.templates.qubit import QubitVerticalBorders, QubitHorizontalBorders
        
        if (
            len(arms) == 0
            or len(arms) > 2
            or (len(arms) == 2 and arms not in SpatialArms.I_shaped_arms())
        ):
            raise TQECError(
                f"The two provided arms cannot form a spatial pipe. Got {arms} but "
                f"expected either a single {SpatialArms.__name__} or two but in a "
                f"line (e.g., {SpatialArms.I_shaped_arms()})."
            )
        if SpatialArms.LEFT in arms or SpatialArms.RIGHT in arms:
            return QubitVerticalBorders()
        elif SpatialArms.UP in arms or SpatialArms.DOWN in arms:
            return QubitHorizontalBorders()
        else:
            raise TQECError(f"Unrecognized spatial arm(s): {arms}.")
    
    def get_memory_qubit_plaquettes(
        self,
        z_orientation: Orientation = Orientation.HORIZONTAL,
        reset: Basis | None = None,
        measurement: Basis | None = None,
    ):
        """Return the plaquettes needed to implement a standard memory operation on a logical qubit."""
        return self._mapper(self.get_memory_qubit_rpng_descriptions)(
            z_orientation, reset, measurement
        )
    
    def get_spatial_cube_qubit_plaquettes(
        self,
        spatial_boundary_basis: Basis,
        arms: SpatialArms,
        reset: Basis | None = None,
        measurement: Basis | None = None,
    ):
        """Return the plaquettes needed to implement a spatial cube qubit."""
        return self._mapper(self.get_spatial_cube_qubit_rpng_descriptions)(
            spatial_boundary_basis, arms, reset, measurement
        )
    
    def get_spatial_cube_arm_plaquettes(
        self,
        spatial_boundary_basis: Basis,
        arms: SpatialArms,
        linked_cubes: tuple,
        reset: Basis | None = None,
        measurement: Basis | None = None,
    ):
        """Return the plaquettes needed to implement one pipe connecting to a spatial cube."""
        return self._mapper(self.get_spatial_cube_arm_rpng_descriptions)(
            spatial_boundary_basis, arms, linked_cubes, reset, measurement
        )

