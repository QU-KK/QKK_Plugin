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


from ...operator import UVPM4_OT_Engine
from ...operator_islands import UVPM4_OT_ShowManualGroupIParamBase
from ...grouping_scheme import TargetGroupingSchemeMixin, GroupingSchemeAccess
from ..engine.types import UvpmIParamFlags, UvpmLogType
from ..engine.props import MainProps
from ...group import UVPM4_GroupInfo
from .grouping_editor_operator import UVPM4_OT_EditGroupingSchemeInEditor
from ..modes.align_mode import UVPM4_Mode_SelectSimilar, UVPM4_Mode_AlignSimilar
from ...app_iface import *


class UVPM4_OT_AlignGeneric(UVPM4_OT_Engine):

    pass


class UVPM4_OT_SelectSimilar(UVPM4_OT_AlignGeneric):

    bl_idname = 'uvpackmaster4.select_similar'
    bl_label = 'Select Similar'
    bl_description = "From all unselected islands, selects all islands which have similar shape to at least one island which is currently selected. For more info regarding similarity detection click the help button"

    MODE_ID = UVPM4_Mode_SelectSimilar.MODE_ID


class UVPM4_OT_AlignSimilar(UVPM4_OT_AlignGeneric):

    bl_idname = 'uvpackmaster4.align_similar'
    bl_label = 'Align Similar (Stack)'
    bl_description = "Align the selected islands, so islands which are similar are stacked on the top of each other. For more info regarding similarity detection click the help button"

    MODE_ID = UVPM4_Mode_AlignSimilar.MODE_ID



def _simi_group_name(group_num):
    return 'S{}'.format(group_num)


class UVPM4_OT_GroupBySimilarity(TargetGroupingSchemeMixin, UVPM4_OT_ShowManualGroupIParamBase, UVPM4_OT_AlignGeneric):

    bl_idname = 'uvpackmaster4.group_by_similarity'
    bl_label = 'Group By Similarity'
    bl_description = 'Group all selected islands by similarity and save generated groups in a grouping scheme'

    SCENARIO_ID = 'align_split_by_similarity'
    GS_ACCESS_DESC_ID = 'editor'

    min_group_size : IntProperty(
        name='Minimum Group Size',
        description='All similarity groups of size lower than the value of this parameter will be ignored and their islands will be reassigned to the default group ({}). If the functionality is not used (value set to 1), the default group will be empty'.format(_simi_group_name(UVPM4_GroupInfo.DEFAULT_GROUP_NUM)),
        min=1,
        max=100,
        default=1)

    def target_scheme_name_impl(self, context):
        return "Scheme 'Similarity'"
    
    def draw_impl(self, context, layout):

        if (not self.create_new_g_scheme()) and (len(self.gs_access.get_g_schemes()) > 0):
            box = layout.box()
            row = box.row()
            row.label(text='WARNING: operation will overwrite all groups in the existing scheme.')

        row = layout.row(align=True)
        row.prop(self, 'min_group_size')

    def use_default_operation_done_status(self):
        return False

    def pre_operation(self):
        target_g_scheme = self.get_target_g_scheme()

        idx = 0
        while idx < len(target_g_scheme.groups):
            group = target_g_scheme.groups[idx]

            if not group.is_default():
                target_g_scheme.remove_group(idx)
            else:
                idx = idx + 1

        assert len(target_g_scheme.groups) == 1
        def_group = target_g_scheme.groups[0]
        def_group.name = _simi_group_name(def_group.num)
        
        super().pre_operation()

    def post_operation(self):
        self.gs_access = GroupingSchemeAccess(self.context, desc_id=GroupingSchemeAccess.get_desc_id_from_obj(self))
        UVPM4_OT_EditGroupingSchemeInEditor.execute_impl(self.context, self.gs_access.get_active_g_scheme_uuid(), select_editor_with_shift=True)
        self.log_manager.log(UvpmLogType.STATUS, UVPM4_OT_EditGroupingSchemeInEditor.CONFIRMATION_MSG)
        super().post_operation()

    def get_save_iparam_handler(self):
        def save_iparam_handler(iparam_info, g_num):
            group = self.gs_access.active_g_scheme.get_group_by_num(g_num)
            if not group:
                self.gs_access.active_g_scheme.add_group_with_target_box(_simi_group_name(g_num), g_num)

        return save_iparam_handler
    
    def setup_engine_params(self):
        self.target_iparam_name = self.gs_access.active_g_scheme.get_iparam_info().script_name
        return super().setup_engine_params()


class UVPM4_OT_SplitOverlappingGeneric(UVPM4_OT_Engine):
 
    def split_offset_iparam_flags(self):
        return 0

    def operation_done_hint(self):
        return ''
    
    def get_iparam_serializers(self):
        output = []

        from ...island_params import VColorIParamSerializer
        from ..engine.island_params import SplitOffsetXIParamInfo, SplitOffsetYIParamInfo

        serializer = VColorIParamSerializer(SplitOffsetXIParamInfo())
        serializer.flags |= self.split_offset_iparam_flags()
        output.append(serializer)

        serializer = VColorIParamSerializer(SplitOffsetYIParamInfo())
        serializer.flags |= self.split_offset_iparam_flags()
        output.append(serializer)

        return output


class UVPM4_OT_SplitOverlapping(UVPM4_OT_SplitOverlappingGeneric):

    bl_idname = 'uvpackmaster4.split_overlapping'
    bl_label = 'Split Overlapping Islands'
    bl_description = 'Methodically move overlapping islands to adjacent tiles (in the +X axis direction), so that no selected islands are overlapping each other after the operation is done'

    SCENARIO_ID = 'align_split_overlapping'

    @staticmethod
    def dont_split_priorities_validate_fail_msg(main_props : MainProps):
        if main_props.split_props.dont_split_priorities and not main_props.align_priority_enabled():
            from ...utils import PropertyWrapper
            return "'{}' requires Align Priority enabled".format(PropertyWrapper(main_props.split_props, 'dont_split_priorities').get_name())
        
        return None
    
    def validate_operation(self):
        msg = self.dont_split_priorities_validate_fail_msg(self.main_props)
        if msg is not None:
            raise RuntimeError(msg)

    def split_offset_iparam_flags(self):
        return UvpmIParamFlags.CONSISTENCY_CHECK_DISABLE
    
    def get_iparam_serializers(self):
        output = super().get_iparam_serializers()

        from ...island_params import VColorIParamSerializer
        from ..engine.island_params import AlignPriorityIParamInfo

        if self.main_props.align_priority_enabled():
            output.append(VColorIParamSerializer(AlignPriorityIParamInfo()))

        return output


class UVPM4_OT_UndoIslandSplit(UVPM4_OT_SplitOverlappingGeneric):

    bl_idname = 'uvpackmaster4.undo_island_split'
    bl_label = 'Undo Island Split'
    bl_description = 'Undo the last island split operation - move all selected islands to their original locations before split. WARNING: the operation only process currently selected islands so in order to move an island to its original location, you have to make sure the island is selected when an Undo operation is run'

    SCENARIO_ID = 'align_undo_island_split'

    def skip_topology_parsing(self):
        return True
