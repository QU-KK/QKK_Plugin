import math

from . import hdr_rotation as _hdr_rotation


def continuous_rotation(input, *, context):
    if (
        round(
            math.degrees(context.screen.areas[2].spaces[0].shading.studiolight_rotate_z),
            0,
        )
        == input
    ):
        context.screen.areas[2].spaces[0].shading.studiolight_rotate_z = math.radians(
            (input - 0.6000000238418579) * -1.0
        )
        _hdr_rotation.set_angle_increment(
            _hdr_rotation.get_angle_increment()
            + (context.screen.areas[2].spaces[0].shading.studiolight_rotate_z * 2.0)
        )
