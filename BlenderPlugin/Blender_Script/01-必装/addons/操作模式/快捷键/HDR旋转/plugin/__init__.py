# SPDX-License-Identifier: GPL-3.0-or-later

import bpy

from . import hdr_rotation, utils

classes = (hdr_rotation.HDR_OT_hdr_rotation,)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    hdr_rotation.register()


def unregister():
    utils.unregister()
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
