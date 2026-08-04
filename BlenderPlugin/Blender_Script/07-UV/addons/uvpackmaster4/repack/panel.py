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

from ..app_iface import *
from ..utils import PanelUtilsMixin
from ..spipeline.panels.other_panels import UVPM4_PT_GenericOther

from .props import is_valid_obj, get_uvpm4_props, UvMapRepackCollectionAccess
from .operator import UVPM4_OT_AutoRepack
from .cluster import RepackClusterAccess
from ..multi_panel import UVPM4_PT_MAIN_NAME

class UVPM4_PT_ViewportGeneric(Panel, PanelUtilsMixin):

    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_context = ''
    bl_category = UVPM4_PT_MAIN_NAME

    def draw(self, context):
        self.init_draw(context)
        self.draw_impl()


class UVPM4_PT_ObjectOptions(UVPM4_PT_ViewportGeneric):

    bl_label = 'Object Options'

    @classmethod
    def poll(cls, context):
        return context.active_object and is_valid_obj(context.active_object)

    def draw_impl(self):
        obj = self.context.active_object
        obj_props = get_uvpm4_props(obj)
        repack_props = obj_props.repack_props

        col = self.layout.column(align=True)
        col.label(text='Auto repacking:')

        def draw(col):
            self.prop_with_help(repack_props, 'repack_enable', col.box(), help_url_suffix=UVPM4_PT_AutoRepack.HELP_URL_SUFFIX)

            if repack_props.repack_enable:
                col.box().row(align=True).prop(repack_props, 'force_repack')

                uv_collection = UvMapRepackCollectionAccess(self.context, obj.name)
                uv_collection.draw(col)

        self.draw_check_supported(
            col,
            AppInterface.auto_repack_not_supported_msg(self.context),
            draw
        )


class UVPM4_PT_AutoRepack(UVPM4_PT_GenericOther):

    HELP_URL_SUFFIX = '/40-miscellaneous-functionalities/30-auto-repacking/'

    if AppInterface.REGISTER_AUTO_REPACK:
        bl_idname = 'UVPM4_PT_AutoRepack'
    bl_label = 'Auto Repacking'

    def draw_impl(self, context):
        layout = self.layout
        col = layout.column(align=True)
        repack_props = self.scene_props.repack_props

        def draw(col):
            col.box().row(align=True).prop(repack_props, 'force_repack')
            col.box().row(align=True).prop(repack_props, 'show_results')

            from ..id_collection.ui import IdCollectionDrawer
            IdCollectionDrawer(access=RepackClusterAccess(self.context, ui_drawing=True),
                               label_plural_form=True,
                               draw_item=True).draw(col.box())

            col.separator()
            col.operator(UVPM4_OT_AutoRepack.bl_idname)

        self.draw_check_supported(
            col,
            AppInterface.auto_repack_not_supported_msg(self.context),
            draw
        )
