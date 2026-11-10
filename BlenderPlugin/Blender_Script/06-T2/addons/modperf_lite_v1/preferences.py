# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Supra3D
"""Add-on preferences (shortcut, and what ModPerf Pro adds)."""

import bpy

from .keymap import PREFERENCES_OT_modperf_lite_key_reset, _toggle_kmi
from .operators import _pro_enabled

PRO_FEATURES = (
    ('OUTLINER', "Built-in outliner: select, hide, rename and organise objects"),
    ('COPYDOWN', "Copy and paste whole modifier stacks onto other objects"),
    ('SOLO_ON', "Five favourite modifier stacks, added in one click"),
    ('CHECKMARK', "Apply All: apply the whole stack in one click"),
)


class MODPERF_LITE_AddonPreferences(bpy.types.AddonPreferences):
    bl_idname = __package__ or __name__

    def draw(self, context):
        layout = self.layout
        col = layout.column()
        if _pro_enabled():
            col.label(text="ModPerf Pro is enabled, so the shortcut opens Pro. "
                           "You can disable or remove ModPerf Lite.", icon='INFO')
            col.separator()
        km, kmi = _toggle_kmi()
        box = col.box()
        if km is not None and kmi is not None:
            row = box.row(align=True)
            split = row.split(factor=0.4)
            split.label(text="Open / Close Shortcut", icon='KEYINGSET')
            r2 = split.row(align=True)
            r2.prop(kmi, "type", text="", full_event=True)
            r2.operator(PREFERENCES_OT_modperf_lite_key_reset.bl_idname, text="",
                        icon='LOOP_BACK')
        else:
            box.label(text="Shortcut not found - re-enable the add-on to restore it.",
                      icon='ERROR')
        layout.separator()
        box = layout.box()
        box.label(text="ModPerf Pro adds:", icon='MODIFIER')
        c = box.column(align=True)
        for icon, text in PRO_FEATURES:
            c.label(text=text, icon=icon)
        box.label(text="Get ModPerf Pro on Superhive (search \"ModPerf\").")
