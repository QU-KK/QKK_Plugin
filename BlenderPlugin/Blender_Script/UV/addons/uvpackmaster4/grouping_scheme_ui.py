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


from .grouping_scheme_access import GroupingSchemeAccess, GSAccessDescIdAttrMixin
from .app_iface import *


class UVPM4_OT_BrowseGroupingSchemes(Operator, GSAccessDescIdAttrMixin):

    bl_options = {'INTERNAL'}
    bl_idname = 'uvpackmaster4.browse_grouping_schemes'
    bl_label = 'Browse Grouping Schemes'
    bl_description = "Browse Grouping Schemes"

    active_g_scheme_uuid : StringProperty(name='', description='', default='')

    def execute(self, context):
        gs_access = GroupingSchemeAccess(context, **GroupingSchemeAccess.get_desc_kwargs(self, context))
        gs_access.set_active_g_scheme_uuid(self.active_g_scheme_uuid)
        return {'FINISHED'}


class UVPM4_MT_BrowseGroupingSchemes(Menu):

    bl_label = "Grouping Schemes"
    bl_idname = 'UVPM4_MT_BrowseGroupingSchemes'

    def draw(self, context):
        gs_access = GroupingSchemeAccess(context, ui_drawing=True, desc=GroupingSchemeAccess.get_desc_from_context(context))
        g_schemes = gs_access.get_g_schemes()

        enumerated_g_schemes = list(enumerate(g_schemes))
        enumerated_g_schemes.sort(key=lambda i: i[1].name)

        layout = self.layout

        gs_access.layout_init_desc(layout)

        for idx, g_scheme in enumerated_g_schemes:
            operator = layout.operator(UVPM4_OT_BrowseGroupingSchemes.bl_idname, text=g_scheme.name)
            operator.active_g_scheme_uuid = g_scheme.uuid


class UVPM4_UL_GroupInfo(UIList):

    bl_idname = 'UVPM4_UL_GroupInfo'

    def draw_item(self, _context, layout, _data, item, icon, _active_data, _active_propname, _index):
        group_info = item

        if self.layout_type in {'DEFAULT', 'COMPACT'}:
            split = layout.split(factor=0.2)
            split.prop(group_info, "color", text="", emboss=True)
            row = split.row().split(factor=0.8)
            row.prop(group_info, "name", text="", emboss=False)
            row.label(text="[D]" if group_info.is_default() else "   ")

        elif self.layout_type == 'GRID':
            layout.alignment = 'CENTER'
            layout.label(text="", icon_value=icon)


class UVPM4_UL_TargetBoxes(UIList):

    bl_idname = 'UVPM4_UL_TargetBoxes'
    
    def draw_item(self, _context, layout, _data, item, icon, _active_data, _active_propname, _index):
        target_box = item

        if self.layout_type in {'DEFAULT', 'COMPACT'}:
            layout.label(text="Box {}: {}".format(_index, target_box.label()))

        elif self.layout_type == 'GRID':
            layout.alignment = 'CENTER'
            layout.label(text="", icon_value=icon)
