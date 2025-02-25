from tqec.plaquette.library.spatial import _SpatialCubeArmPlaquetteBuilder
from tqec.utils.enums import Basis


def test_make_spatial_cube_arm_plaquette():
    builder = _SpatialCubeArmPlaquetteBuilder(Basis.Z, "UP")
    assert builder._get_plaquette_name() == "SPATIAL_CUBE_ARM_Z_UP"
