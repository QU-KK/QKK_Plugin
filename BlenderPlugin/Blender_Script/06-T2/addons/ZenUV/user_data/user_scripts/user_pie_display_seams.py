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

# Copyright 2025, Alex Zhornyak, alexander.zhornyak@gmail.com


from ZenUV.ui.pie.mesh_pie import ZUV_OT_PieCallerTopRight


def register():
    print('Starting Zen UV user script...')

    ZUV_OT_PieCallerTopRight.bl_label = "Mark By Angle | Toggle Seams"

    s_text = """from ZenUV.utils.blender_zen_utils import show_message_box; \
        from ZenUV.ui.pie import ZsPieFactory; bpy.ops.wm.context_toggle(data_path='space_data.overlay.show_edge_seams') \
        if C.space_data.type == 'VIEW_3D' else \
        (ZsPieFactory.mark_pie_cancelled(), show_message_box(message='Available only in 3D Viewport', title='WARNING', icon='ERROR'))"""

    ZUV_OT_PieCallerTopRight.template_items = {
        'Default': 'uv.zenuv_mark_seams(True, action="MARK")',
        'CTRL': (
            'wm.zenuv_script_exec(script="' + s_text + '", desc="Toggle Seams in 3D Viewport")'
        ),
        'SHIFT': 'wm.context_toggle_enum(data_path="scene.zen_uv.ui.draw_mode_UV", value_1="SEAMS", value_2="NONE")',
    }

    ZUV_OT_PieCallerTopRight.template_display_items = {
        'Default': "Mark Seams By Angle",
        'CTRL': "Toggle Seams (3D)",
        'SHIFT': "Toggle Seams (UV)"
    }


def unregister():
    print('Finishing Zen UV user script...')
