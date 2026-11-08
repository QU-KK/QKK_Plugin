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

import bpy
import bmesh
from ..utils.generic import (
    ensure_facemap,
    set_face_int_tag,
    remove_facemap,
    HOPS_SHOW_UV_FACEMAP_NAME,
)
from ..utils.uv_factory import UvIslandUtils
from ..utils.iter_utils import IterUtils
from ..utils.blender_zen_utils import ZenPolls


def draw_hops_popup(self, context: bpy.types.Context):
    ''' @Draw Hard Ops Popup '''
    layout: bpy.types.UILayout = self.layout
    addon_prefs = context.preferences.addons[ZenPolls.ADDON_PACKAGE].preferences
    layout.label(text="It looks like HOps addon")
    layout.label(text="is not installed on your system.")
    layout.operator("wm.url_open",
                    text="Buy HOps addon",
                    icon="HELP").url = "https://gumroad.com/l/hardops"
    layout.separator()
    layout.label(text="To disable the notification ")
    layout.label(text="turn off option:")
    layout.prop(addon_prefs, "hops_uv_activate")


def show_hops_widget(context: bpy.types.Context, use_selected_meshes, use_selected_faces, use_tagged_faces):
    objs = context.objects_in_mode
    for obj, bm, uv_layer in IterUtils.iter_objs_with_bmesh_uv(objs, context, skip_obj_if_no_uv=True):
        hops_show_uv_facemap = ensure_facemap(bm, HOPS_SHOW_UV_FACEMAP_NAME)
        int_tag = 1
        islands_for_process = UvIslandUtils.get_selected_uv_islands(context, bm, uv_layer)
        if not islands_for_process:
            islands_for_process = UvIslandUtils.get_all_uv_islands(context, bm, uv_layer)
            int_tag = 0
        set_face_int_tag(islands_for_process, hops_show_uv_facemap, int_tag=int_tag)
        bmesh.update_edit_mesh(obj.data, loop_triangles=False)
    try:
        bpy.ops.hops.draw_uv_launcher(
            use_selected_meshes=use_selected_meshes,
            use_selected_faces=use_selected_faces,
            use_tagged_faces=use_tagged_faces,
            show_all_and_highlight_sel=True
        )
    except Exception:
        print("Zen UV: Hard Ops have no such attributes.")
        print("        Perhaps the Hard Ops version does not meet the requirements.")
        print("        The ability to display a UV widget is supported since Hard Ops 00987.")

    bpy.ops.object.mode_set(mode='EDIT')

    # Remove Facemap for display
    objs = context.objects_in_mode
    for obj, bm, uv_layer in IterUtils.iter_objs_with_bmesh_uv(objs, context, skip_obj_if_no_uv=True):
        remove_facemap(bm, HOPS_SHOW_UV_FACEMAP_NAME)
        bmesh.update_edit_mesh(obj.data, loop_triangles=False)


def show_uv_in_3dview(context: bpy.types.Context, use_selected_meshes, use_selected_faces, use_tagged_faces):
    """
    Shows UV map in View 3D using HOPS module ops.hops.draw_uv_launcher
    Conditions: Image Editon not in areas and ops.hops.draw_uv_launcher is
    activated.
    """
    addon_prefs = context.preferences.addons[ZenPolls.ADDON_PACKAGE].preferences
    if addon_prefs.hops_uv_activate:
        if not hasattr(bpy.types, bpy.ops.hops.draw_uv_launcher.idname()):
            context.window_manager.popup_menu(draw_hops_popup, title="Zen UV", icon='INFO')
        else:
            uv_editor_opened = 'IMAGE_EDITOR' in [area.type for area in context.screen.areas]
            show_widget_always = addon_prefs.hops_uv_context
            if show_widget_always:
                show_hops_widget(context, use_selected_meshes, use_selected_faces, use_tagged_faces)
            else:
                if not uv_editor_opened:
                    show_hops_widget(context, use_selected_meshes, use_selected_faces, use_tagged_faces)
