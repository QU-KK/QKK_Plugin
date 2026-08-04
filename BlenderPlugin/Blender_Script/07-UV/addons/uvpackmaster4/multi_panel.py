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


from .pgroup import standalone_property_group
from .utils import PanelUtilsMixin, print_backtrace_if_debug, snake_to_camel_case, get_multi_panel_manager
from .app_iface import *
from .spipeline.engine.types import EnumValue, enum_decorator
from .box_utils import disable_box_rendering


UVPM4_PT_SPACE_TYPE = 'IMAGE_EDITOR'
UVPM4_PT_REGION_TYPE = 'UI'
UVPM4_PT_CONTEXT = ''

UVPM4_PT_MAIN_NAME = 'UVPackmaster4'


class UVPM4_PT_UVEditor(Panel, PanelUtilsMixin):

    bl_space_type = UVPM4_PT_SPACE_TYPE
    bl_region_type = UVPM4_PT_REGION_TYPE
    bl_context = UVPM4_PT_CONTEXT
    bl_order = 1

    @staticmethod
    def panel_name_with_prefix(name, short=False):
        return ('U4 ' if short else UVPM4_PT_MAIN_NAME + ' ') + name


class UVPM4_PT_MainCategory(UVPM4_PT_UVEditor):

    bl_category = UVPM4_PT_MAIN_NAME


class UVPM4_PT_MultiPanels(UVPM4_PT_MainCategory):

    bl_idname = 'UVPM4_PT_MultiPanels'
    bl_label = 'Main'

    @classmethod
    def poll(cls, context):
        for m_panel in get_multi_panel_manager(context).multi_panels:
            if m_panel.display_mode() == MultiPanelDisplayMode.EMBEDDED:
                return True
            
        return False

    def draw(self, context):
        prefs = get_prefs()
        layout = self.layout

        hori_multi_panel_toggles = not prefs.vert_multi_panel_toggles

        main_cont = layout.column(align=False) if hori_multi_panel_toggles else layout.row(align=False)
        toggle_cont = main_cont.row() if hori_multi_panel_toggles else main_cont.column()

        if hori_multi_panel_toggles:
            toggle_cont.alignment = 'LEFT'
            main_cont.separator()

        panel_col = main_cont.column(align=False)
        mp_manager = get_multi_panel_manager(context)

        for m_panel in mp_manager.multi_panels:
            if m_panel.display_mode() != MultiPanelDisplayMode.EMBEDDED:
                continue

            if not m_panel.poll(context):
                continue

            toggle_row = toggle_cont.row()
            toggle_row.alignment = 'CENTER'
            toggle_op = toggle_row.operator(
                        UVPM4_OT_SelectMultiPanel.bl_idname,
                        icon=m_panel.icon if m_panel.icon else 'NONE',
                        depress=m_panel.selected,
                        emboss=True,
                        text="")
            
            toggle_op.panel_id = m_panel.id

            if not m_panel.selected:
                continue

            m_panel.draw(context, panel_col)


@enum_decorator
class MultiPanelDisplayMode:

    EMBEDDED = EnumValue('0', 'Embedded', "Embed the multi panel in the '{}' panel of the '{}' tab".format(UVPM4_PT_MultiPanels.bl_label , UVPM4_PT_MainCategory.bl_category))
    DETACHED = EnumValue('1', 'Detached', "Display the multi panel as a separate panel in the '{}' tab".format(UVPM4_PT_MainCategory.bl_category))
    TAB = EnumValue('2', 'Tab', 'Display the multi panel in a separate tab in the N panel of the UV Editor')


@standalone_property_group
class UVPM4_MultiPanelSettings:

    selected : BoolProperty(name='selected', default=True)


class UVPM4_SavedMultiPanelSettings(PropertyGroup):

    panel_id : StringProperty(name="", default="")
    settings : PointerProperty(type=UVPM4_MultiPanelSettings)


@standalone_property_group
class UVPM4_MultiPanelAddonSettings:

    display_mode : EnumProperty(
        name='Display Mode',
        items=lambda self, context: MultiPanelDisplayMode.to_blend_items()
    )


class UVPM4_SavedMultiPanelAddonSettings(PropertyGroup):

    panel_id : StringProperty(name="", default="")
    settings : PointerProperty(type=UVPM4_MultiPanelAddonSettings)



class PanelIdAttributeMixin:

    panel_id : StringProperty(name='', default='')


class UVPM4_OT_ExpandPanel(Operator, PanelIdAttributeMixin):

    bl_idname = 'uvpackmaster4.expand_panel'
    bl_label = 'Exapnd Panel'
    bl_description = 'Expand/hide the panel'

    expand : BoolProperty(name='', default=False)

    def execute(self, context):
        mp_manager = get_multi_panel_manager(context)
        panel_data = mp_manager.get_panel_data(self.panel_id)
        panel_data.expanded = self.expand

        return {'FINISHED'}
    

class UVPM4_OT_SelectMultiPanel(Operator, PanelIdAttributeMixin):

    bl_idname = 'uvpackmaster4.select_multi_panel'
    bl_label = 'Select Multi Panel'

    shift : BoolProperty(name='', default=False)
    force_select : BoolProperty(name='', default=False)

    @classmethod
    def description(cls, context, properties):
        m_panel = get_multi_panel_manager(context).get_multi_panel(properties.panel_id)

        return '{} (press with Shift to select multiple)'.format(m_panel.name)

    def invoke(self, context, event):
        self.shift = event.shift
        return self.execute(context)

    def execute(self, context):
        disable_box_rendering(None, context)

        selected_count = 0
        target_panel = None

        mp_manager = get_multi_panel_manager(context)

        for m_panel in mp_manager.multi_panels:

            if m_panel.selected:
                selected_count += 1

            if m_panel.id == self.panel_id:
                target_panel = m_panel

            if not self.shift:
                m_panel.selected = False

        if not target_panel:
            return {'CANCELLED'}
        
        if self.shift:
            if target_panel.selected and selected_count == 1:
                return {'CANCELLED'}
            
            select = True if self.force_select else not target_panel.selected
            target_panel.selected = select
        
        else:
            target_panel.selected = True

        return {'FINISHED'}


class MultiPanel(PanelUtilsMixin):

    def __init__(self):
        self.id = self.M_PANEL_ID
        self.name = self.M_PANEL_NAME
        self.icon = self.M_PANEL_ICON
        self.panels = []
        self.default_settings = UVPM4_MultiPanelSettings.SA(selected=self.M_PANEL_SELECTED)

        self.a_settings = None
        self.settings = UVPM4_MultiPanelSettings.SA()
        self.saved_settings_dict = None
        self.saved_settings = None

    @classmethod
    def poll(cls, context):
        return True

    def reset(self, saved_a_settings_dict):
        self.panels = []
        self.a_settings = saved_a_settings_dict[self.id]

    def update_settings(self, saved_settings_dict):
        self.saved_settings_dict = saved_settings_dict
        self.saved_settings = self.saved_settings_dict.get(self.id)

        if self.saved_settings:
            self.settings.copy_from(self.saved_settings)
        else:
            self.settings.copy_from(self.default_settings)

    def save_settings(self):
        assert self.saved_settings_dict is not None

        if not self.saved_settings:
            self.saved_settings = self.saved_settings_dict[self.id]

        self.saved_settings.copy_from(self.settings)

    def settings_popover_name(self):
        return UVPM4_PT_MultiPanelSettingsPopover.__name__ + snake_to_camel_case(self.id)
    
    def label(self):
        return "{} (Multi Panel)".format(self.name)
    
    def tab_panel_name(self):
        return UVPM4_PT_MultiPanelTab.__name__ + snake_to_camel_case(self.id)
    
    def detached_panel_name(self):
        return UVPM4_PT_MultiPanelDetached.__name__ + snake_to_camel_case(self.id)
    
    def display_mode(self):
        return self.a_settings.display_mode

    @property
    def selected(self):
        return self.settings.selected

    @selected.setter
    def selected(self, value):
        self.settings.selected = value
        self.save_settings()

    def draw_panel_header(self, context, panel_data, panel, layout, first_panel=False):
        enable_menu_target = self.prefs.use_enable_menu() and panel.enable_menu_target()

        header_row_outer = layout.row(align=True)
        header_row_outer.scale_y = 0.8
        header_row = header_row_outer.row(align=True)

        panel_t = panel_data.panel_t
        expanded = panel_data.expanded
        not_supported_msg = panel.not_supported_msg(context)
        warning_msg = panel.warning_msg(context)
        supported = not_supported_msg is None
        expanded &= supported

        header_row.enabled = supported

        if hasattr(panel_t, 'draw_header'):
            panel.layout = header_row
            panel.draw_header(context)

        if not enable_menu_target:
            main_property = panel.get_main_property()
            if main_property is not None:
                row = header_row.row()
                main_property.draw(row, text='')

        expand_row = header_row.row()
        expand_row.alignment = 'LEFT'
        expand_op = expand_row.operator(UVPM4_OT_ExpandPanel.bl_idname, 
                                        text=panel_t.bl_label,
                                        icon='TRIA_DOWN' if expanded else 'TRIA_RIGHT',
                                        emboss=False)
        
        expand_op.panel_id = panel_data.id
        expand_op.expand = not expanded

        filler_row = header_row.row()

        if hasattr(panel_t, 'PRESET_PANEL'):
            preset_row = header_row.row()
            preset_row.alignment = 'RIGHT'

            preset_row.emboss = 'NONE'
            preset_row.popover(panel=panel_t.PRESET_PANEL.__name__, icon='PRESET', text="")

        if hasattr(panel_t, 'HELP_URL_SUFFIX'):
            help_row = header_row.row()
            help_row.alignment = 'RIGHT'
            self._draw_help_operator(help_row, panel_t.HELP_URL_SUFFIX)

        warning_text = not_supported_msg if not supported else warning_msg

        if warning_text is not None:
            warning_row = header_row_outer.row()
            warning_row.alignment = 'RIGHT'
            from .help import UVPM4_OT_WarningPopup
            UVPM4_OT_WarningPopup.draw_operator(warning_row, text=warning_text)

        if first_panel and panel_data.m_panel is not None:
            settings_row = header_row.row()
            settings_row.alignment = 'RIGHT'

            settings_row.emboss = 'NONE'
            settings_row.popover(panel=panel_data.m_panel.settings_popover_name(), icon=UVPM4_PT_MultiPanelSettingsPopover.ICON, text="")

        if enable_menu_target:
            from .panel import UVPM4_OT_EnablePanel
            disable_row = header_row_outer.row()
            disable_row.alignment = 'RIGHT'
            op = disable_row.operator(UVPM4_OT_EnablePanel.bl_idname, text='', icon='PANEL_CLOSE', emboss=False)
            op.panel_id = panel.bl_idname
            op.enable = False

        return expanded

    def draw(self, context, layout):
        self.init_draw(context)
        panel_col = layout.column(align=False)

        first_panel = True

        for panel_data in self.panels:
            try:
                panel_t = panel_data.panel_t

                if hasattr(panel_t, 'poll') and not panel_t.poll(context):
                    continue

                panel_box = panel_col.box()

                panel = panel_data.create_instance(context)

                expanded = self.draw_panel_header(context, panel_data, panel, panel_box, first_panel=first_panel)
                first_panel = False

                if expanded:

                    panel.layout = panel_box
                    self.draw_engine_status(self.prefs, panel.layout)
                    panel.draw(context)

                    if self.prefs.use_enable_menu() and panel_data.enable_menu_host:
                        panel_box.menu(panel_t.enable_child_panel_menu_name())

                    for ch_panel_data in panel_data.ch_panels:
                        try:
                            ch_panel_t = ch_panel_data.panel_t

                            if hasattr(ch_panel_t, 'poll') and not ch_panel_t.poll(context):
                                continue

                            ch_panel = ch_panel_data.create_instance(context)
                            if self.prefs.use_enable_menu() and ch_panel.enable_menu_target() and not ch_panel.get_main_property().get():
                                continue

                            panel_col.separator(factor=0.5)
                            intend_factor = 0.001

                            if intend_factor > 0.0:
                                ch_panel_split = panel_col.split(factor=intend_factor)
                                margin_row = ch_panel_split.row()
                                ch_panel_box = ch_panel_split.box()
                            else:
                                ch_panel_box = panel_col.box()

                            
                            expanded = self.draw_panel_header(context, ch_panel_data, ch_panel, ch_panel_box)
                            
                            if not expanded:
                                continue

                            intend_factor = 0.0

                            if intend_factor > 0.0:
                                ch_panel_split = ch_panel_box.split(factor=intend_factor)
                                margin_row = ch_panel_split.row()
                                ch_panel_col = ch_panel_split.column(align=True)
                            else:
                                ch_panel_col = ch_panel_box.column(align=True)
                            
                            ch_panel.layout = ch_panel_col
                            ch_panel.draw(context)

                        except Exception as ex:
                            print_backtrace_if_debug(ex)

            except Exception as ex:
                print_backtrace_if_debug(ex)

            panel_col.separator(factor=1.0)


class UtilMultiPanel(MultiPanel):

    M_PANEL_ID = 'util'
    M_PANEL_NAME = 'Utilities'
    M_PANEL_ICON = 'TOOL_SETTINGS'
    M_PANEL_SELECTED = True


class PackMultiPanel(MultiPanel):

    M_PANEL_ID = 'pack'
    M_PANEL_NAME = 'Packing'
    M_PANEL_ICON = 'EVENT_P'
    M_PANEL_SELECTED = True


class GroupingPackMultiPanel(MultiPanel):

    M_PANEL_ID = 'grouping_pack'
    M_PANEL_NAME = 'Grouping (Packing)'
    M_PANEL_ICON = 'GROUP_VERTEX'
    M_PANEL_SELECTED = False

    @classmethod
    def poll(cls, context):
        return get_prefs().get_active_pack_mode(context).grouping_config.grouping_enabled


class AlignMultiPanel(MultiPanel):

    M_PANEL_ID = 'align'
    M_PANEL_NAME = 'Aligning'
    M_PANEL_ICON = 'EVENT_A'
    M_PANEL_SELECTED = False


class GroupingEditorMultiPanel(MultiPanel):

    M_PANEL_ID = 'grouping_editor'
    M_PANEL_NAME = 'Grouping Editor'
    M_PANEL_ICON = 'EVENT_G'
    M_PANEL_SELECTED = False


class TexelDensityMultiPanel(MultiPanel):

    M_PANEL_ID = 'texel_density'
    M_PANEL_NAME = 'Texel Density'
    M_PANEL_ICON = 'EVENT_T'
    M_PANEL_SELECTED = False


class OtherToolsMultiPanel(MultiPanel):

    M_PANEL_ID = 'other_tools'
    M_PANEL_NAME = 'Other Tools'
    M_PANEL_ICON = 'EVENT_O'
    M_PANEL_SELECTED = False


class StatisticsMultiPanel(MultiPanel):

    M_PANEL_ID = 'statistics'
    M_PANEL_NAME = 'Statistics'
    M_PANEL_ICON = 'PROPERTIES'
    M_PANEL_SELECTED = False


class PreferencesMultiPanel(MultiPanel):

    M_PANEL_ID = 'preferences'
    M_PANEL_NAME = 'Preferences'
    M_PANEL_ICON = 'SETTINGS'
    M_PANEL_SELECTED = False


MULTI_PANELS = (
    UtilMultiPanel(),
    PackMultiPanel(),
    GroupingPackMultiPanel(),
    AlignMultiPanel(),
    GroupingEditorMultiPanel(),
    TexelDensityMultiPanel(),
    OtherToolsMultiPanel(),
    StatisticsMultiPanel(),
    PreferencesMultiPanel()
)


class UVPM4_PT_MultiPanelSettingsPopover(Panel, PanelUtilsMixin, PresetPanel):

    ICON = 'SETTINGS'

    def draw(self, context):
        self.init_draw(context)

        mp_manager = get_multi_panel_manager(context)
        m_panel = mp_manager.get_multi_panel(self.PARENT_M_PANEL_ID)
        a_settings = m_panel.a_settings

        layout = self.layout
        col = layout.column(align=True)
        col.label(text=self.bl_label)
        self.draw_enum_in_box(a_settings, 'display_mode', col)

        
MULTI_PANEL_SETTINGS_POPOVERS = tuple( type(m_panel.settings_popover_name(), (UVPM4_PT_MultiPanelSettingsPopover,),
                                            {
                                                'PARENT_M_PANEL_ID' : m_panel.id,
                                                'bl_label' : "Multi Panel Settings: {}".format(m_panel.name)
                                            })
                                            for m_panel in MULTI_PANELS )


class UVPM4_PT_MultiPanelDetached(UVPM4_PT_MainCategory):

    @classmethod
    def get_multi_panel(cls, context):
        mp_manager = get_multi_panel_manager(context)
        return mp_manager.get_multi_panel(cls.PARENT_M_PANEL_ID)

    @classmethod
    def poll(cls, context):
        m_panel = cls.get_multi_panel(context)
        return m_panel.display_mode() == MultiPanelDisplayMode.DETACHED and m_panel.poll(context)

    def draw(self, context):
        self.get_multi_panel(context).draw(context, self.layout)


MULTI_PANEL_DETACHED_PANELS = tuple( type(m_panel.detached_panel_name(), (UVPM4_PT_MultiPanelDetached,),
                                    {
                                        'PARENT_M_PANEL_ID' : m_panel.id,
                                        'bl_idname' : m_panel.detached_panel_name(),
                                        'bl_label' : m_panel.label()
                                    })
                                    for m_panel in MULTI_PANELS )


class UVPM4_PT_MultiPanelTab(UVPM4_PT_UVEditor):

    @classmethod
    def get_multi_panel(cls, context):
        mp_manager = get_multi_panel_manager(context)
        return mp_manager.get_multi_panel(cls.PARENT_M_PANEL_ID)

    @classmethod
    def poll(cls, context):
        m_panel = cls.get_multi_panel(context)
        return m_panel.display_mode() == MultiPanelDisplayMode.TAB and m_panel.poll(context)

    def draw(self, context):
        self.get_multi_panel(context).draw(context, self.layout)


MULTI_PANEL_TAB_PANELS = tuple( type(m_panel.tab_panel_name(), (UVPM4_PT_MultiPanelTab,),
                                    {
                                        'PARENT_M_PANEL_ID' : m_panel.id,
                                        'bl_category' : UVPM4_PT_UVEditor.panel_name_with_prefix(m_panel.name, short=True),
                                        'bl_idname' : m_panel.tab_panel_name(),
                                        'bl_label' : m_panel.label()
                                    })
                                    for m_panel in MULTI_PANELS )


MULTI_PANEL_ALL_PANELS = MULTI_PANEL_DETACHED_PANELS + MULTI_PANEL_TAB_PANELS
