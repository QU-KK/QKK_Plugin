# ##### BEGIN GPL LICENSE BLOCK #####
#
#  This program is free software; you can redistribute it and/or
#  modify it under the terms of the GNU General Public License
#  as published by the Free Software Foundation; either version 2
#  of the License, or (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program; if not, write to the Free Software Foundation,
#  Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301, USA.
#
# ##### END GPL LICENSE BLOCK #####

""" Zen UV The batch transformation is dependent on the Trim module UI"""

# Copyright 2023, Valeriy Yatsenko

from .directional_hotspot import register as register_directional_hotspot
from .directional_hotspot import unregister as unregister_directional_hotspot

import bpy

from .hotspot import ZUV_OT_TrHotspot
from .hotspot import register as register_hotspot
from .hotspot import unregister as unregister_hotspot

from .selections import ZUV_OT_TrimSelectByFace, ZUV_OT_TrimSelectIslandsByTrim
from .selections import register as register_selections
from .selections import unregister as unregister_selections

from .trim_to_mesh import register as register_trim_to_mesh
from .trim_to_mesh import unregister as unregister_trim_to_mesh

from ZenUV.ico import icon_get
from ZenUV.prop.zuv_preferences import get_prefs


def draw_trim_batch_ops(self, context: bpy.types.Context, layout: bpy.types.UILayout):
    ''' @Draw Trim Batch Operators '''

    from ZenUV.ops.trimsheets.trimsheet_transform import ZUV_OT_SetActiveTrimMouseover
    from ZenUV.ops.trimsheets.trimsheet_preview import ZUV_OT_TrimPreview
    from ZenUV.ops.trimsheets.trimsheet_utils import ZuvTrimsheetUtils

    layout.operator(ZUV_OT_TrHotspot.bl_idname, icon_value=icon_get("hotspot-mapping"))

    col = layout.column(align=True)
    row = col.row(align=True)
    row.operator(ZUV_OT_TrimSelectByFace.bl_idname, icon="RESTRICT_SELECT_OFF", text='Trim by Face')
    row.operator(ZUV_OT_TrimSelectIslandsByTrim.bl_idname, icon="RESTRICT_SELECT_OFF", text='Islands by Trim')

    addon_prefs = get_prefs()
    if addon_prefs.trimsheet.mode == 'IMAGE':
        p_image = ZuvTrimsheetUtils.getActiveImage(context)
        if p_image:
            col.operator(ZUV_OT_TrimPreview.bl_idname, icon="RESTRICT_SELECT_OFF")

    if context.area.type == 'IMAGE_EDITOR':
        row = col.row(align=True)
        row.operator(ZUV_OT_SetActiveTrimMouseover.bl_idname, icon='EYEDROPPER', text='Trim by Eyedropper')


def register_trim_batch_ops():
    register_hotspot()
    register_directional_hotspot()
    register_selections()
    register_trim_to_mesh()


def unregister_trim_batch_ops():
    unregister_hotspot()
    unregister_directional_hotspot()
    unregister_selections()
    unregister_trim_to_mesh()
