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

from ...panel import UVPM4_PT_Generic
from ...multi_panel import PreferencesMultiPanel, UtilMultiPanel, StatisticsMultiPanel
from ...utils import in_debug_mode
from ..operators.util_operator import UVPM4_OT_MeasureArea, UVPM4_OT_OverlapCheck
from ...app_iface import *


class UVPM4_PT_AddonPreferences(UVPM4_PT_Generic):

    bl_idname = 'UVPM4_PT_AddonPreferences'
    bl_context = ''
    bl_order = 0
    bl_label = 'Add-on Preferences'

    PARENT_M_PANEL_ID = PreferencesMultiPanel.M_PANEL_ID


    def draw_impl(self, context):
        layout = self.layout
        col = layout.column(align=True)
        
        self.prefs.draw_addon_preferences(col)

        if in_debug_mode():
            col.separator()

            dopt_layout = col
            dopt_layout.label(text="Debug options:")

            box = dopt_layout.box() 
            row = box.row(align=True)
            row.prop(self.prefs, "script_allow_execution")

            box = dopt_layout.box()
            row = box.row(align=True)
            row.prop(self.prefs, "write_to_file")

            box = dopt_layout.box() 
            row = box.row(align=True)
            row.prop(self.prefs, "wait_for_debugger")

            row = dopt_layout.row(align=True)
            row.prop(self.prefs, "seed")
            row = dopt_layout.row(align=True)
            row.prop(self.prefs, "test_param")

            self.prefs.dis_msgs.draw(dopt_layout.box())

            from ...debug import UVPM4_OT_Debug
            dopt_layout.operator(UVPM4_OT_Debug.bl_idname)
       

class UVPM4_PT_SceneOptions(UVPM4_PT_Generic):

    bl_idname = 'UVPM4_PT_SceneOptions'
    bl_context = ''
    bl_order = 0
    bl_label = 'Scene Options'

    PARENT_M_PANEL_ID = PreferencesMultiPanel.M_PANEL_ID


    def draw_impl(self, context):
        layout = self.layout
        col = layout.column(align=True)

        col.box().prop(self.scene_props, 'arrange_non_packed')

        box = col.box()
        row = box.row()
        row.prop(self.scene_props, 'main_prop_sets_enable')

        from ...id_collection.main_props import MainPropSetAccess
        self._draw_help_operator(row, MainPropSetAccess.HELP_URL_SUFFIX)

        col.separator()

        adv_op_layout = col # adv_op_box.column(align=True)
        adv_op_layout.label(text='Expert options:')

        from ...prefs import UVPM4_OT_ShowHideAdvancedOptions
        UVPM4_OT_ShowHideAdvancedOptions.draw_operator(context, adv_op_layout)
        if self.scene_props.show_expert_options:
            box = adv_op_layout.box()
            box.label(text='Change expert options only if it is really required', icon='ERROR')
            
            if AppInterface.HIGHPREC_TOPO_ANALYSIS_SUPPORTED:
                box = adv_op_layout.box()
                row = box.row(align=True)
                row.prop(self.scene_props, 'highprec_topo_analysis')

            box = adv_op_layout.box()
            row = box.row(align=True)
            row.prop(self.scene_props, 'disable_immediate_uv_update')
    

class UVPM4_PT_Utilities(UVPM4_PT_Generic):

    bl_idname = 'UVPM4_PT_Utilities'
    bl_label = 'Utilities'
    bl_context = ''

    PARENT_M_PANEL_ID = UtilMultiPanel.M_PANEL_ID

    def draw_impl(self, context):
        layout = self.layout
        col = layout.column(align=True)

        row = col.row(align=True)
        row.operator(UVPM4_OT_OverlapCheck.bl_idname)

        row = col.row(align=True)
        split = row.split(factor=0.7, align=True)

        row = split.row(align=True)
        op = row.operator(UVPM4_OT_MeasureArea.bl_idname)
        op.merged = False

        row = split.row(align=True)
        op = row.operator(UVPM4_OT_MeasureArea.bl_idname, text='(Merged)')
        op.merged = True


class UVPM4_PT_Statistics(UVPM4_PT_Generic):

    bl_idname = 'UVPM4_PT_Statistics'
    bl_label = 'Statistics'

    PARENT_M_PANEL_ID = StatisticsMultiPanel.M_PANEL_ID

    def draw_impl(self, context):
        layout = self.layout
        col = layout.column(align=True)
        box = col.box()
        box.label(text='Last operation statistics:')

        for idx, dev in enumerate(self.prefs.device_array()):
            col.separator()
            col.label(text=dev.name)
            box = col.box()
            box.label(text='Iteration count: ' + str(dev.bench_entry.iter_count))

            box = col.box()
            box.label(text='Total packing time: ' + str(dev.bench_entry.total_time) + ' ms')

            box = col.box()
            box.label(text='Average iteration time: ' + str(dev.bench_entry.avg_time) + ' ms')
            