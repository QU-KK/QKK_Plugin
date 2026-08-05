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

import os
import multiprocessing
from pathlib import Path
from collections import namedtuple

from .utils import PanelUtilsMixin, PropertyWrapper
from .spipeline.engine.types import GroupingMethod
from .spipeline.engine.labels import Labels 
from .spipeline.engine.types import ChildPanelMode
from .grouping_scheme import UVPM4_GroupingScheme
from .box_utils import disable_box_rendering
from .register_utils import UVPM4_OT_SetEnginePath
from .multi_panel import UVPM4_SavedMultiPanelSettings, UVPM4_SavedMultiPanelAddonSettings
from .multi_panel_manager import UVPM4_SavedPanelSettings
from .app_iface import *
from .pgroup import standalone_property_group
from .panel import PanelUtilsMixin
from .repack.props import UVPM4_SceneRepackProps
from .tdensity.tier import UVPM4_SceneTDensityProps
from .operator_generic import UVPM4_OT_GenericHandler


@standalone_property_group
class UVPM4_DeviceSettings:

    enabled : BoolProperty(name='enabled', default=True)


DeviceMetadata = namedtuple('DeviceMetadata', ('enabled_default', 'help_url_suffix'), defaults=(None, None))


@standalone_property_group
class UVPM4_SavedDeviceSettings:

    DEVICE_METADATA = [
        ('vulkan_', DeviceMetadata(
                        enabled_default=False,
                        help_url_suffix='48-other-topics/20-vulkan-gpu-acceleration')
        )
    ]

    dev_id : StringProperty(name="", default="")
    settings : PointerProperty(type=UVPM4_DeviceSettings)
    
    def get_metadata(self):
        for id_prefix, metadata in self.DEVICE_METADATA:
            if self.dev_id.startswith(id_prefix):
                return metadata
            
        return DeviceMetadata()

    def init(self, dev_id):
        self.dev_id = dev_id

        metadata = self.get_metadata()
        if metadata.enabled_default is not None:
            self.settings.enabled = metadata.enabled_default


from .id_collection.main_props import UVPM4_MainPropIdCollection, UVPM4_MainProps
from .id_collection import UVPM4_IdCollectionAccessDescriptor

def _update_main_prop_sets_enable(self, context):
    from .id_collection.main_props import MainPropSetAccess
    main_prop_access = MainPropSetAccess(bpy.context)

    if self.main_prop_sets_enable:
        if len(main_prop_access) == 0:
            main_prop_access.create_item(set_active=True)

        main_prop_access.ensure_selected()

    main_prop_access.state_changed_handler()


class UVPM4_SceneProps(PropertyGroup):

    main_prop_access_desc : PointerProperty(type=UVPM4_IdCollectionAccessDescriptor)
    main_prop_sets : PointerProperty(type=UVPM4_MainPropIdCollection)

    main_prop_sets_enable : BoolProperty(
        name=Labels.MAIN_PROP_SETS_ENABLE_NAME,
        description=Labels.MAIN_PROP_SETS_ENABLE_DESC,
        default=False,
        update=_update_main_prop_sets_enable)
    default_main_props : PointerProperty(type=UVPM4_MainProps)

    saved_m_panel_settings : CollectionProperty(type=UVPM4_SavedMultiPanelSettings)
    saved_panel_settings : CollectionProperty(type=UVPM4_SavedPanelSettings)
    grouping_schemes : CollectionProperty(name="Grouping Schemes", type=UVPM4_GroupingScheme)

    group_method_editor : EnumProperty(
        items=GroupingMethod.to_blend_items(),
        name="{} (Editor)".format(Labels.GROUP_METHOD_NAME),
        description=Labels.GROUP_METHOD_DESC,
        default=GroupingMethod.MANUAL.value(),
        update=disable_box_rendering)
    
    repack_props : PointerProperty(type=UVPM4_SceneRepackProps) if AppInterface.REGISTER_AUTO_REPACK else None

    tdensity_props : PointerProperty(type=UVPM4_SceneTDensityProps)

    arrange_non_packed : BoolProperty(
        name=Labels.ARRANGE_NON_PACKED_NAME,
        description=Labels.ARRANGE_NON_PACKED_DESC,
        default=True
    )

    # Expert options
    show_expert_options : BoolProperty(
        name=Labels.SHOW_EXPERT_OPTIONS_NAME,
        description=Labels.SHOW_EXPERT_OPTIONS_DESC,
        default=False
    )

    highprec_topo_analysis : BoolProperty(
        name=Labels.HIGHPREC_TOPO_ANALYSIS_NAME,
        description=Labels.HIGHPREC_TOPO_ANALYSIS_DESC,
        default=False
    )

    disable_immediate_uv_update : BoolProperty(
        name=Labels.DISABLE_IMMEDIATE_UV_UPDATE_NAME,
        description=Labels.DISABLE_IMMEDIATE_UV_UPDATE_DESC,
        default=False
    )


class DismissableMessage:

    class Type:
        TIP = 1
        WARN = 2

    class TypeMetadata:
        def __init__(self, label, icon):
            self.label = label
            self.icon = icon

    TYPE_METADATA = {
        Type.TIP: TypeMetadata(label='TIP', icon='FAKE_USER_ON'),
        Type.WARN: TypeMetadata(label='WARNING', icon='ERROR'),
    }
    
    def __init__(self, id, msg, type):
        self.id = id
        self.msg = msg
        self.type = type
        self.t_metadata = self.TYPE_METADATA[self.type]

    def dismissed_prop_id(self):
        return self.id + '_dismissed'


PIXEL_MARGIN_DIS_MSG = DismissableMessage(
    id='pixel_margin',
    msg='The following options may have different meaning than in other 3D tools. Check the option hints or documentation before using them.',
    type=DismissableMessage.Type.WARN
)

from .multi_panel import GroupingPackMultiPanel, PackMultiPanel, GroupingEditorMultiPanel

GROUPING_PACK_DIS_MSG = DismissableMessage(
    id='grouping_pack',
    msg="To configure grouping for a group-based packing mode, go to the '{0}' multi panel (next to the '{1}' multi panel). The '{0}' multi panel is displayed only if a group-based packing mode is selected.".format(GroupingPackMultiPanel.M_PANEL_NAME, PackMultiPanel.M_PANEL_NAME),
    type=DismissableMessage.Type.TIP
)

GROUPING_EDITOR_DIS_MSG = DismissableMessage(
    id='grouping_editor',
    msg="The '{0}' multi panel is used to edit grouping schemes independently of the packing mode logic. Grouping in a group-based packing mode is NOT configured here but in the '{1}' multi panel (displayed only if a group-based packing mode is selected).".format(GroupingEditorMultiPanel.M_PANEL_NAME, GroupingPackMultiPanel.M_PANEL_NAME),
    type=DismissableMessage.Type.TIP
)


from .spipeline.engine.types import T

def dismissable_messages_decorator(new_cls : T) -> T:
    annotations = {}
    msg_by_id = {}

    for obj in globals().values():
        if not isinstance(obj, DismissableMessage):
            continue

        dis_msg = obj
        annotations[dis_msg.dismissed_prop_id()] = BoolProperty(default=False, name=dis_msg.id)
        msg_by_id[dis_msg.id] = dis_msg
    
    cls = type(new_cls.__name__, (PropertyGroup,) + new_cls.__bases__, dict(new_cls.__dict__, __annotations__=annotations, MSG_BY_ID=msg_by_id))
    return cls


class UVPM4_OT_DismissMessage(UVPM4_OT_GenericHandler):

    bl_label = 'Dismiss'
    bl_idname = 'uvpackmaster4.dismiss_message'

    dis_msg_id : StringProperty(name='', default='')

    def execute_impl(self, context):
        self.prefs.dis_msgs.dismiss(self.dis_msg_id)
        return {'FINISHED'}
    

@dismissable_messages_decorator
class UVPM4_DismissableMessages:
    
    def handle(self, dis_msg : DismissableMessage, layout, add_separator=True):
        dismissed_prop = PropertyWrapper(self, dis_msg.dismissed_prop_id())

        if dismissed_prop.get():
            return
        
        main_col = layout.column(align=True)
        box = main_col.box()
        col = box.column(align=True)
        col.label(text=dis_msg.t_metadata.label + ':', icon=dis_msg.t_metadata.icon)

        PanelUtilsMixin._draw_multiline_label(col, dis_msg.msg, width=300)

        col.separator()
        op = col.operator(UVPM4_OT_DismissMessage.bl_idname)
        op.dis_msg_id = dis_msg.id

        if add_separator:
            main_col.separator()

    def dismiss(self, dis_msg_id):
        dis_msg : DismissableMessage = self.MSG_BY_ID[dis_msg_id]
        PropertyWrapper(self, dis_msg.dismissed_prop_id()).set(True)

        save_prefs_op = AppInterface.save_preferences_operator()
        if save_prefs_op:
            AppInterface.exec_operator(save_prefs_op.bl_idname)

    def draw(self, layout):
        col = layout.column(align=True)

        col.label(text='Dismissable messages:')
        for dis_msg in self.MSG_BY_ID.values():
            dis_msg : DismissableMessage
            col.prop(self, dis_msg.dismissed_prop_id())

    
@addon_preferences
class UVPM4_Preferences(PanelUtilsMixin):

    bl_idname = __package__

    MAX_TILES_IN_ROW = 1000
    INCONSISTENT_ISLANDS_HELP_URL_SUFFIX = '/48-other-topics/5-inconsistent-islands-error-handling/'
    CH_PANEL_MODE_HELP_URL_SUFFIX = '/13-user-interface/#subpanels'

    modes_dict = None

    def reset_box_params(self):
        self.box_rendering = False
        self.group_scheme_boxes_editing = False
        self.custom_target_box_editing = False
        self.boxes_dirty = False

    def reset_stats(self):
        for dev in self.device_array():
            dev.reset()

    def reset(self):
        self.engine_path = ''
        self.enabled = True
        self.engine_initialized = False
        self.engine_status_msg = ''
        self.thread_count = multiprocessing.cpu_count()
        self.operation_counter = -1
        self.write_to_file = False
        self.seed = 0

        self.enable_vulkan_saved = self.enable_vulkan

        self.reset_stats()
        self.reset_device_array()
        self.reset_box_params()

    def draw_engine_status(self, layout):
        row = layout.row(align=True)
        self.draw_engine_status_message(row, icon_only=False)
        self.draw_engine_status_help_button(row)

    def draw_engine_status_message(self, layout, icon_only):
        icon = 'ERROR' if not self.engine_initialized else 'NONE'
        layout.label(text="" if icon_only else self.engine_status_msg, icon=icon)

    def draw_engine_status_help_button(self, layout):
        if not self.engine_initialized:
            from .help import UVPM4_OT_SetupHelp
            layout.operator(UVPM4_OT_SetupHelp.bl_idname, icon='QUESTION', text='')

    def draw_addon_preferences(self, layout):
        col = layout.column(align=True)
        col.label(text='General options:')

        row = col.row(align=True)
        row.prop(self, "thread_count")

        box = col.box()
        row = box.row(align=True)
        row.prop(self, 'orient_aware_uv_islands')

        from .panel import PanelUtilsMixin
        box = col.box()
        PanelUtilsMixin.prop_with_help(self, 'allow_inconsistent_islands', box, help_url_suffix=self.INCONSISTENT_ISLANDS_HELP_URL_SUFFIX)

        box = col.box()
        row = box.row(align=True)
        row.prop(self, 'dont_transform_pinned_uvs')

        if self.dont_transform_pinned_uvs:
            box = col.box()
            row = box.row(align=True)
            row.prop(self, 'pinned_uvs_as_others')

        self.draw_prop_saved_state(self, 'enable_vulkan', col.box())
        
        col.separator()
        col.label(text='UI options:')

        PanelUtilsMixin.draw_enum_in_box(self, 'ch_panel_mode', col, help_url_suffix=self.CH_PANEL_MODE_HELP_URL_SUFFIX)

        box = col.box()
        row = box.row(align=True)
        row.prop(self, 'vert_multi_panel_toggles')

        box = col.box()
        row = box.row(align=True)
        row.prop(self, "disable_tips")

        row = col.row(align=True)
        row.prop(self, "font_size_text_output")

        row = col.row(align=True)
        row.prop(self, "font_size_uv_overlay")

        row = col.row(align=True)
        row.prop(self, "box_render_line_width")
        
        box = col.box()
        row = box.row(align=True)
        row.prop(self, "short_island_operator_names")

        col.separator()
        col.separator()

        col.label(text='Packing devices:')
        dev_main = col.column(align=True)

        dev_factors = (0.8,)
        dev_cols = self.create_split_columns(dev_main.box(), factors=dev_factors)

        dev_cols[0].label(text='Name')
        dev_cols[1].label(text='Enabled')

        dev_cols = self.create_split_columns(dev_main.box(), factors=dev_factors)

        for dev in self.device_array():
            settings = dev.settings
            row = dev_cols[0].row()
            row.label(text=dev.name)

            row = dev_cols[1].row()
            row.prop(settings, 'enabled', text='')

            help_url_suffix = dev.help_url_suffix()

            if help_url_suffix is not None:
                self._draw_help_operator(row, help_url_suffix)

        save_operator = AppInterface.save_preferences_operator()
        if save_operator:
            col.separator()
            col.operator(save_operator.bl_idname)

    def draw(self, context):
        layout = self.layout

        # main_box = layout.box()
        main_col = layout.column(align=True)
        main_col.label(text='Engine status:')
        box = main_col.box()
        self.draw_engine_status(box)

        col = box.column(align=True)
        row = col.row(align=True)
        row.label(text="Path to the UVPM engine:")
        row = col.row(align=True)
        row.enabled = False
        row.prop(self, 'engine_path')

        row = col.row(align=True)
        row.operator(UVPM4_OT_SetEnginePath.bl_idname)

        main_col.separator()
        main_col.separator()

        self.draw_addon_preferences(main_col)

    def get_engine_args(self):
        args = []

        if self.enable_vulkan:
            args.append('-v')

        return args

    def get_mode(self, mode_id, context, **mode_kwargs):
        if self.modes_dict is None:
            raise RuntimeError("Mods are not initialized.")
        try:
            return next(m(context, **mode_kwargs) for m_list in self.modes_dict.values() for (m_id, m) in m_list if m_id == mode_id)
        except StopIteration:
            raise KeyError("The '{}' mode not found".format(mode_id))

    def get_modes(self, mode_type):
        return self.modes_dict[mode_type]

    def get_active_pack_mode(self, context):
        try:
            return self.get_mode(get_main_props(context).active_pack_mode_id, context)
        except KeyError:
            pass

        from .spipeline.modes.pack_modes import UVPM4_Mode_SingleTile
        return self.get_mode(UVPM4_Mode_SingleTile.MODE_ID, context)

    def set_active_pack_mode(self, context, mode_id):
        get_main_props(context).active_pack_mode_id = mode_id


    operation_counter : IntProperty(
        name='',
        description='',
        default=-1)

    box_rendering : BoolProperty(
        name='',
        description='',
        default=False)

    boxes_dirty : BoolProperty(
        name='',
        description='',
        default=False)

    group_scheme_boxes_editing : BoolProperty(
        name='',
        description='',
        default=False)

    custom_target_box_editing : BoolProperty(
        name='',
        description='',
        default=False)

    engine_retcode : IntProperty(
        name='',
        description='',
        default=0)

    engine_path : StringProperty(
        name='',
        description='',
        default='')

    engine_initialized : BoolProperty(
        name='',
        description='',
        default=False)

    engine_status_msg : StringProperty(
        name='',
        description='',
        default='')

    thread_count : IntProperty(
        name=Labels.THREAD_COUNT_NAME,
        description=Labels.THREAD_COUNT_DESC,
        default=multiprocessing.cpu_count(),
        min=1,
        max=multiprocessing.cpu_count())

    seed : IntProperty(
        name=Labels.SEED_NAME,
        description='',
        default=0,
        min=0,
        max=10000)

    test_param : IntProperty(
        name=Labels.TEST_PARAM_NAME,
        description='',
        default=0,
        min=0,
        max=10000)

    write_to_file : BoolProperty(
        name=Labels.WRITE_TO_FILE_NAME,
        description='',
        default=False)

    wait_for_debugger : BoolProperty(
        name=Labels.WAIT_FOR_DEBUGGER_NAME,
        description='',
        default=False)
    
    vert_multi_panel_toggles : BoolProperty(
        name=Labels.VERT_MULTI_PANEL_TOGGLES_NAME,
        description=Labels.VERT_MULTI_PANEL_TOGGLES_DESC,
        default=False)

    orient_aware_uv_islands : BoolProperty(
        name=Labels.ORIENT_AWARE_UV_ISLANDS_NAME,
        description=Labels.ORIENT_AWARE_UV_ISLANDS_DESC,
        default=False)

    allow_inconsistent_islands : BoolProperty(
        name=Labels.ALLOW_INCONSISTENT_ISLANDS_NAME,
        description=Labels.ALLOW_INCONSISTENT_ISLANDS_DESC,
        default=True)
    
    dont_transform_pinned_uvs : BoolProperty(
        name=Labels.DONT_TRANSFORM_PINNED_UVS_NAME,
        description=Labels.DONT_TRANSFORM_PINNED_UVS_DESC,
        default=True)
    
    pinned_uvs_as_others : BoolProperty(
        name=Labels.PINNED_UVS_AS_OTHERS_NAME,
        description=Labels.PINNED_UVS_AS_OTHERS_DESC,
        default=True)
    
    enable_vulkan : BoolProperty(
        name='Enable Vulkan',
        description='Enable Vulkan devices for packing (if available in the system)',
        default=True
    )

    enable_vulkan_saved : BoolProperty(
        name='',
        default=True
    )

    def use_enable_menu(self):
        return self.ch_panel_mode == ChildPanelMode.ENABLE_MENU

    # UI options
    disable_tips : BoolProperty(
        name=Labels.DISABLE_TIPS_NAME,
        description=Labels.DISABLE_TIPS_DESC,
        default=False)

    font_size_text_output : IntProperty(
        name=Labels.FONT_SIZE_TEXT_OUTPUT_NAME,
        description=Labels.FONT_SIZE_TEXT_OUTPUT_DESC,
        default=15,
        min=5,
        max=100)

    font_size_uv_overlay : IntProperty(
        name=Labels.FONT_SIZE_UV_OVERLAY_NAME,
        description=Labels.FONT_SIZE_UV_OVERLAY_DESC,
        default=20,
        min=5,
        max=100)

    box_render_line_width : FloatProperty(
        name=Labels.BOX_RENDER_LINE_WIDTH_NAME,
        description=Labels.BOX_RENDER_LINE_WIDTH_DESC,
        default=4.0,
        min=1.0,
        max=10.0,
        step=5.0)
    
    short_island_operator_names : BoolProperty(
        name=Labels.SHORT_ISLAND_OPERATOR_NAMES_NAME,
        description=Labels.SHORT_ISLAND_OPERATOR_NAMES_DESC,
        default=False)
    
    ch_panel_mode : EnumProperty(
        name='Subpanel Mode',
        items=ChildPanelMode.to_blend_items()
    )

    dis_msgs : PointerProperty(type=UVPM4_DismissableMessages)

    saved_m_panel_a_settings : CollectionProperty(type=UVPM4_SavedMultiPanelAddonSettings)

    script_allow_execution : BoolProperty(name='Allow Script Execution', default=False)

    dev_array = []
    saved_dev_settings : CollectionProperty(type=UVPM4_SavedDeviceSettings)

    def device_array(self):
        return type(self).dev_array

    def reset_device_array(self):
        type(self).dev_array = []

    @classmethod
    def get_userdata_path(cls):
        from .os_iface import os_get_userdata_path
        os_userdata_path = os_get_userdata_path()
        path = os.path.join(os_userdata_path, AppInterface.APP_ID, 'engine4')
        Path(path).mkdir(parents=True, exist_ok=True)
        return path

    @classmethod
    def get_main_preset_path(cls):
        preset_path = os.path.join(cls.get_userdata_path(), 'presets')
        Path(preset_path).mkdir(parents=True, exist_ok=True)
        return preset_path

    @classmethod
    def get_g_schemes_preset_path(cls):
        preset_path = os.path.join(cls.get_userdata_path(), 'grouping_schemes')
        Path(preset_path).mkdir(parents=True, exist_ok=True)
        return preset_path

    @classmethod
    def get_preferences_filepath(cls):
        return os.path.join(cls.get_userdata_path(), 'prefs.json')


class UVPM4_OT_ShowHideAdvancedOptions(Operator):

    bl_label = 'Show Expert Options'
    bl_idname = 'uvpackmaster4.show_hide_expert_options'

    @staticmethod
    def get_label(context):
        return 'Hide Expert Options' if get_scene_props(context).show_expert_options else 'Show Expert Options'

    @classmethod
    def draw_operator(cls, context, layout):
        layout.operator(cls.bl_idname, text=cls.get_label(context))

    def draw(self, context):
        layout = self.layout
        col = layout.column()

        for label in self.confirmation_labels:
            col.label(text=label)

    def execute(self, context):
        scene_props = get_scene_props(context)
        scene_props.show_expert_options = not scene_props.show_expert_options

        from .utils import redraw_ui
        redraw_ui(context)

        return {'FINISHED'}

    def invoke(self, context, event):
        scene_props = get_scene_props(context)

        if not scene_props.show_expert_options:
            self.confirmation_labels =\
                [ 'WARNING: expert options should never be changed under the standard packer usage.',
                  'You should only change them if you really know why you are doing it for.',
                  'Are you sure you want to show the expert options?' ]

            wm = context.window_manager
            return wm.invoke_props_dialog(self, width=700)

        return self.execute(context)
