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

from .props import EngineSceneProps
from .grouping import GroupingConfig
from .spipeline.engine.props import MainProps
from .app_iface import *

import sys


class ModeType:
    HIDDEN = 0
    PACK = 1


class UVPM4_Mode_Generic:

    MODE_PRIORITY = sys.maxsize
    MODE_TYPE = ModeType.HIDDEN
    MODE_HELP_URL_SUFFIX = None

    AUTO_REPACK_GROUPING_UUID = 'e705249ab45d4ee08a331162ec6548cb'
    auto_repack = False
    g_scheme = None

    main_props : MainProps
    

    @classmethod
    def enum_name(cls):
        return cls.MODE_NAME

    def subpanels_base(self):
        output = self.subpanels()
        return output

    def subpanels(self):
        return []

    def __init__(self, context):
        self.context = context
        self.scene_props = get_scene_props(context)
        self.e_scene_props = EngineSceneProps(context)
        self.main_props = get_main_props(context)
        self.app_state = AppState(context)
        self.prefs = get_prefs()
        self.op = None
        self.grouping_config = self.get_grouping_config()

    def get_grouping_config(self):
        return GroupingConfig(self.context)
    
    def target_boxes_not_editable_msg(self, group):
        return None
    
    def target_boxes_editable(self, group):
        return self.target_boxes_not_editable_msg(group) is None

    def pre_operation(self, op):
        self.op = op

        if self.grouping_config.grouping_enabled:
            self.g_scheme = self.init_g_scheme()

    def get_iparam_serializers(self):
        output = []

        if self.g_scheme is not None:
            output.append(self.g_scheme.get_iparam_serializer())

        return output
    
    def init_g_scheme_in(self, p_context, skip_default_group=False):
        from .grouping_scheme_access import GroupingSchemeAccess
        from .grouping_scheme import UVPM4_GroupingScheme
        from .operator import NoUvFaceSelectedError
        from .spipeline.engine.types import GroupingMethod

        g_scheme = UVPM4_GroupingScheme.SA()
        g_method = self.grouping_config.group_method_prop.get()

        if GroupingMethod.auto_grouping_enabled(g_method):
            if self.auto_repack:
                g_scheme.uuid = self.AUTO_REPACK_GROUPING_UUID
                
            g_scheme.options.copy_from(self.main_props.auto_group_options)
            g_scheme.init_group_map(p_context, g_method, skip_default_group)

        else:
            gs_access = GroupingSchemeAccess(self.context, desc_id=GroupingSchemeAccess.get_desc_id_from_obj(self))
            g_scheme.copy_from(gs_access.get_active_g_scheme_safe())

        if len(g_scheme.groups) == 0:
            raise NoUvFaceSelectedError(send_pinned=False)

        return g_scheme
    
    def init_g_scheme(self):
        return self.init_g_scheme_in(self.op.p_context, skip_default_group=False)
    
    def setup_engine_params(self):
        from .prefs_scripted_utils import EngineParams
        params = EngineParams()
        from .spipeline.engine.scenario import get_scenario_annotations
        from .spipeline.engine.param import EngineParamUtils
        EngineParamUtils.to_params(self, get_scenario_annotations(self.op.get_scenario_id()), params)

        return params


class UVPM4_OT_SelectPackMode(Operator):

    bl_options = {'INTERNAL'}
    bl_idname = 'uvpackmaster4.select_pack_mode'
    bl_label = 'Select Packing Mode'
    bl_description = "Select an active packing mode"

    mode_id : StringProperty(name='', description='', default='')

    def execute(self, context):
        get_prefs().set_active_pack_mode(context, self.mode_id)
        return {'FINISHED'}


class UVPM4_MT_BrowsePackModes(Menu):
    
    bl_idname = "UVPM4_MT_BrowsePackModes"
    bl_label = "Packing Modes"

    def draw(self, context):
        prefs = get_prefs()
        mode_list = prefs.get_modes(ModeType.PACK)
        layout = self.layout

        layout.label(text='Packing Mode')
        layout.separator()

        for mode_id, mode in mode_list:
            operator = layout.operator(UVPM4_OT_SelectPackMode.bl_idname, text=mode.MODE_NAME)
            operator.mode_id = mode.MODE_ID
