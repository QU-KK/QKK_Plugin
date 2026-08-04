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

from .operator import UVPM4_OT_ShowTexelDensity, UVPM4_OT_SetTexelDensity, UVPM4_OT_AdjustTexelDensityToUnselected
from ..panel import UVPM4_PT_Generic
from ..presets import UVPM4_PT_Presets
from ..multi_panel import TexelDensityMultiPanel
from ..operator_islands import IParamEditUI
from ..utils import get_main_props, PropertyWrapper
from ..id_collection.ui import IdCollectionDrawer
from .tier import TDensityTierAccess


class UVPM4_PT_GenericTexelDensity(UVPM4_PT_Generic):

    PARENT_M_PANEL_ID = TexelDensityMultiPanel.M_PANEL_ID


class UVPM4_PT_TexelDensity(UVPM4_PT_GenericTexelDensity):

    bl_idname = 'UVPM4_PT_TexelDensity'
    bl_label = 'Texel Density'

    PRESET_PANEL = UVPM4_PT_Presets
    HELP_URL_SUFFIX = '/37-texel-density'

    ENABLE_MENU_LABEL = 'TD Features'
    PANEL_PRIORITY = 100
    
    def draw_impl(self, context):
        layout = self.layout
        col = layout.column(align=True)
        self.draw_main_prop_sets(col)

        self.draw_pixel_margin_tex_size(col)

        row = col.row(align=True)
        self.main_props.tdensity_to_set.draw(row)

        col.separator()

        col.operator(UVPM4_OT_SetTexelDensity.bl_idname)
        col.operator(UVPM4_OT_ShowTexelDensity.bl_idname)
        col.operator(UVPM4_OT_AdjustTexelDensityToUnselected.bl_idname)


class UVPM4_PT_TexelDensityBeforePack(UVPM4_PT_GenericTexelDensity):

    bl_idname = 'UVPM4_PT_TexelDensityBeforePack'
    bl_label = 'Set TD Before Packing'

    bl_parent_id = UVPM4_PT_TexelDensity.bl_idname

    HELP_URL_SUFFIX = '/37-texel-density#set-td-before-packing'

    def warning_msg(self, context):
        return get_main_props(context).tdensity_before_pack_validate_fail_msg()
    
    def get_main_property(self):
        return PropertyWrapper(get_main_props(self.context), 'tdensity_set_before_pack')

    def draw_impl(self, context):
        layout = self.layout
        col = layout.column(align=True)

        self.main_props.tdensity_packing.draw(col.row(align=True))

        box = col.box()
        box.row(align=True).prop(self.main_props, "island_tdensity_set_before_pack")

        if self.main_props.island_tdensity_before_pack_enabled():
            IParamEditUI(self.context, self.main_props, 'TexelDensityPackingIParamInfo').draw(box.column(align=True))


class UVPM4_PT_TexelDensityTiers(UVPM4_PT_GenericTexelDensity):

    bl_idname = 'UVPM4_PT_TexelDensityTiers'
    bl_label = 'Texel Density Tiers'

    HELP_URL_SUFFIX = '/37-texel-density#texel-density-tiers'

    PANEL_PRIORITY = 200

    def draw_impl(self, context):
        layout = self.layout
        col = layout.column(align=True)
        IdCollectionDrawer(access=TDensityTierAccess(self.context, ui_drawing=True), draw_item=True).draw(col)
