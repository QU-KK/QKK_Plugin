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

from ...panel_islands import UVPM4_PT_StackGroups
from ..engine.types import UvpmSimilarityMode, UvpmAxis
from ..operators.align_operator import UVPM4_OT_SplitOverlapping, UVPM4_OT_UndoIslandSplit


from ...multi_panel import AlignMultiPanel
from ...presets import UVPM4_PT_Presets
from ...panel import UVPM4_PT_Generic, UVPM4_PT_IParamEditMixin
from ..operators.align_operator import UVPM4_OT_SelectSimilar, UVPM4_OT_AlignSimilar, UVPM4_OT_GroupBySimilarity


class UVPM4_PT_GenericAlign(UVPM4_PT_Generic):

    PARENT_M_PANEL_ID = AlignMultiPanel.M_PANEL_ID

    @classmethod
    def get_active_mode(cls, context):
        return None


class UVPM4_PT_MainAlign(UVPM4_PT_GenericAlign):

    bl_idname = 'UVPM4_PT_MainAlign'
    bl_label = 'Aligning'
    bl_context = ''

    HELP_URL_SUFFIX = '35-aligning-functionalities'
    PRESET_PANEL = UVPM4_PT_Presets

    PANEL_PRIORITY = 100


    def draw_header_preset(self, _context):
        UVPM4_PT_Presets.draw_panel_header(self.layout)

    def draw_impl(self, context):
        operators = [UVPM4_OT_SelectSimilar, UVPM4_OT_AlignSimilar, UVPM4_OT_GroupBySimilarity]

        layout = self.layout
        col = layout.column(align=True)
        self.draw_main_prop_sets(col)

        for op in operators:
            row = col.row(align=True)
            row.operator(op.bl_idname)
        
    
class UVPM4_PT_AligningOptions(UVPM4_PT_GenericAlign):

    bl_idname = 'UVPM4_PT_AligningOptions'
    bl_label = 'Aligning Options'


    ENABLE_MENU_LABEL = 'Aligning Features'
    PANEL_PRIORITY = 200


    def draw_impl(self, context):
        layout = self.layout
        col = layout.column(align=True)

        simi_props = self.main_props.simi_props
        mode_col = self.draw_enum_in_box(simi_props, "simi_mode", col)

        if UvpmSimilarityMode.is_vertex_based(simi_props.simi_mode):
            box = mode_col.box()
            row = box.row()
            row.prop(simi_props, 'correct_vertices')

            row = mode_col.row(align=True)
            row.prop(simi_props, 'vertex_threshold')

        else:
            mode_col.prop(self.main_props, "precision")

            row = mode_col.row(align=True)
            row.prop(simi_props, 'threshold')

            box = mode_col.box()
            row = box.row(align=True)
            row.prop(simi_props, 'check_holes')


        box = col.box()
        row = box.row(align=True)
        row.prop(self.main_props, 'flipping_enable')

        box = col.box()
        row = box.row(align=True)
        row.prop(simi_props, 'adjust_scale')

        if simi_props.adjust_scale:
            row = box.row(align=True)
            row.prop(simi_props, 'non_uniform_scaling_tolerance')

        match_col = self.draw_enum_in_box(simi_props, "match_3d_axis", col, expand=True)
        match_space_col = self.draw_enum_in_box(simi_props, "match_3d_axis_space", match_col, prop_name='', expand=True)
        match_space_col.enabled = simi_props.match_3d_axis != UvpmAxis.NONE


class UVPM4_PT_SubPanelAlign(UVPM4_PT_GenericAlign):
    
    bl_parent_id = UVPM4_PT_AligningOptions.bl_idname


class UVPM4_PT_IParamEditAlign(UVPM4_PT_IParamEditMixin, UVPM4_PT_SubPanelAlign):

    pass


class UVPM4_PT_AlignPriority(UVPM4_PT_IParamEditAlign):

    bl_idname = 'UVPM4_PT_AlignPriority'
    bl_label = 'Align Priority'

    PANEL_PRIORITY = 3000
    IPARAM_INFO_TYPE = 'AlignPriorityIParamInfo'
    HELP_URL_SUFFIX = '35-aligning-functionalities#align-priority'


class UVPM4_PT_StackGroupsAlign(UVPM4_PT_StackGroups, UVPM4_PT_SubPanelAlign):

    bl_idname = 'UVPM4_PT_StackGroupsAlign'
    PANEL_PRIORITY = 4700


class UVPM4_PT_SplitOverlapping(UVPM4_PT_GenericAlign):

    bl_idname = 'UVPM4_PT_SplitOverlapping'
    bl_label = 'Split Overlapping'

    PANEL_PRIORITY = 300


    def draw_impl(self, context):
        layout = self.layout
        col = layout.column(align=True)

        split_props = self.main_props.split_props
        self.draw_enum_in_box(split_props, "detection_mode", col)

        row = col.row(align=True)
        row.prop(split_props, 'max_tile_x')

        self.handle_prop(split_props,
                         'dont_split_priorities',
                         col.box(),
                         warning_msg=UVPM4_OT_SplitOverlapping.dont_split_priorities_validate_fail_msg(self.main_props))

        col.separator()

        row = col.row(align=True)
        row.operator(UVPM4_OT_SplitOverlapping.bl_idname)

        row = col.row(align=True)
        row.operator(UVPM4_OT_UndoIslandSplit.bl_idname)
