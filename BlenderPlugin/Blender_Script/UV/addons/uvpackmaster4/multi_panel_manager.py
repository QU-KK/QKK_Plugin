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


from .panel import UVPM4_MT_EnableChildPanel, UVPM4_PT_Generic

from .utils import CollectionPropertyDictWrapper
from .multi_panel import MULTI_PANELS
from .app_iface import *
from .pgroup import standalone_property_group

from . import module_loader 
from .spipeline import panels

from .repack import panel as repack_panel
from .tdensity import panel as tdensity_panel

panel_modules = module_loader.import_submodules(panels)
panel_modules += [repack_panel, tdensity_panel]

panels_classes = module_loader.get_registrable_classes(panel_modules, sub_class=UVPM4_PT_Generic, required_vars=('bl_idname',))
panels_classes.sort(key=lambda x: x.PANEL_PRIORITY)
    

PANELS = [panel_t for panel_t in panels_classes if not hasattr(panel_t, 'bl_parent_id')]
CHILD_PANELS = [panel_t for panel_t in panels_classes if hasattr(panel_t, 'bl_parent_id')]


ENABLE_CHILD_PANEL_MENUS = tuple( type(panel.enable_child_panel_menu_name(), (UVPM4_MT_EnableChildPanel,),
                                    {
                                        'PANEL_ID' : panel.bl_idname,
                                        'bl_idname' : panel.enable_child_panel_menu_name(),
                                        'bl_label': panel.ENABLE_MENU_LABEL
                                    })
                                    for panel in PANELS )


@standalone_property_group
class UVPM4_PanelSettings:

    expanded : BoolProperty(name='expanded', default=True)

    def __init__(self, panel_t=None):
        super(type(self), self).__init__()

        if panel_t is not None and hasattr(panel_t, 'bl_options'):
            self.expanded = 'DEFAULT_CLOSED' not in panel_t.bl_options


class UVPM4_SavedPanelSettings(PropertyGroup):

    panel_id : StringProperty(name="", default="")
    settings : PointerProperty(type=UVPM4_PanelSettings)


class PanelData:

    def __init__(self, panel_t, m_panel):
        self.id = panel_t.bl_idname
        self.panel_t = panel_t
        self.m_panel = m_panel
        self.ch_panels = []
        self.default_settings = UVPM4_PanelSettings.SA(panel_t)

        self.settings = UVPM4_PanelSettings.SA()
        self.saved_settings_dict = None
        self.saved_settings = None
        self.enable_menu_host = False

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
    
    def append_child(self, ch_panel_data):
        if ch_panel_data.create_instance(bpy.context).enable_menu_target():
            self.enable_menu_host = True

        self.ch_panels.append(ch_panel_data)

    def create_instance(self, context):
        panel = self.panel_t()
        panel.init_draw(context)
        return panel

    @property
    def expanded(self):
        return self.settings.expanded

    @expanded.setter
    def expanded(self, value):
        self.settings.expanded = value
        self.save_settings()


class MultiPanelManager:

    __INSTANCE = None

    @classmethod
    def get(cls, context):
        if cls.__INSTANCE is None:
            cls.__INSTANCE = MultiPanelManager()

        cls.__INSTANCE.update_settings(get_scene_props(context))
        return cls.__INSTANCE
    
    @classmethod
    def reset(cls):
        cls.__INSTANCE = None

    def __init__(self):
        self.prefs = get_prefs()
        self.multi_panels = MULTI_PANELS
        self.m_panel_dict = { m_panel.id: m_panel for m_panel in self.multi_panels }
        self.panel_dict = {}

        m_panel_a_settings_dict = CollectionPropertyDictWrapper(self.prefs.saved_m_panel_a_settings, 'panel_id', 'settings')

        for m_panel in self.multi_panels:
            m_panel.reset(m_panel_a_settings_dict)

        for panel_t in PANELS:
            m_panel = self.m_panel_dict[panel_t.PARENT_M_PANEL_ID]
            panel_data = PanelData(panel_t, m_panel)
            m_panel.panels.append(panel_data)
            self.panel_dict[panel_data.id] = panel_data

        for ch_panel_t in CHILD_PANELS:
            panel_data = self.panel_dict[ch_panel_t.bl_parent_id]
            ch_panel_data = PanelData(ch_panel_t, None)
            panel_data.append_child(ch_panel_data)
            self.panel_dict[ch_panel_data.id] = ch_panel_data

    def update_settings(self, scene_props):
        m_panel_settings_dict = CollectionPropertyDictWrapper(scene_props.saved_m_panel_settings, 'panel_id', 'settings')
        panel_settings_dict = CollectionPropertyDictWrapper(scene_props.saved_panel_settings, 'panel_id', 'settings')

        for m_panel in self.multi_panels:
            m_panel.update_settings(m_panel_settings_dict)

        for panel_data in self.panel_dict.values():
            panel_data.update_settings(panel_settings_dict)

    def get_multi_panel(self, m_panel_id):
        return self.m_panel_dict[m_panel_id]

    def get_panel_data(self, panel_id) -> PanelData:
        return self.panel_dict[panel_id]
