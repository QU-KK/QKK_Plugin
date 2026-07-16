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

# Copyright 2023, Alex Zhornyak, alexander.zhornyak@gmail.com


from ZenUV.ui.pie.mesh_pie import ZUV_OT_PieCallerRight, ZUV_OT_PieCallerLeft


def register():
    print('Starting Zen UV user script...')

    ZUV_OT_PieCallerRight.template_items = {
        'Default': 'uv.zenuv_mark_seams(True, action="MARK")',
        'CTRL': 'uv.zenuv_tag_finished(True)',
        'SHIFT': 'mesh.mark_sharp(True, clear=False)',
        'ALT': 'mesh.zenuv_mirror_seams(True, axis="TOPOLOGY")'
    }
    ZUV_OT_PieCallerLeft.template_items = {
        'Default': 'uv.zenuv_mark_seams(True, action="UNMARK")',
        'CTRL': 'uv.zenuv_untag_finished(True)',
        'SHIFT': 'mesh.mark_sharp(True, clear=True)',
        'ALT': 'uv.zenuv_unmark_all(True)'
    }


def unregister():
    print('Finishing Zen UV user script...')
