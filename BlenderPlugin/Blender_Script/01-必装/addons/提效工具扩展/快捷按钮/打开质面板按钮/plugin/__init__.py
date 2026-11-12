# SPDX-License-Identifier: GPL-3.0-or-later

import bpy

from . import open_mat_panel

classes = (
    open_mat_panel.OPENMATPANEL_OT_open_mat_panel,
    open_mat_panel.OPENMATPANEL_OT_close_panel,
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    open_mat_panel.register()


def unregister():
    open_mat_panel.unregister()
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
