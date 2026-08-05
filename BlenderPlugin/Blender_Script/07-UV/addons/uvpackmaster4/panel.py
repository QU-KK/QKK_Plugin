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

import sys

from .app_iface import *
from .utils import PanelUtilsMixin, split_by_chars, print_backtrace_if_debug, get_multi_panel_manager


class UVPM4_PT_Generic(PanelUtilsMixin):

    PANEL_PRIORITY = sys.maxsize
    ENABLE_MENU_LABEL = 'Enable Feature'

    @classmethod
    def poll(cls, context):
        if not hasattr(cls, 'poll_impl'):
            return True
        
        try:
            cls.active_mode = cls.get_active_mode(context)
            return cls.poll_impl(context)
        except Exception as ex:
            print_backtrace_if_debug(ex)

        return False
    
    @classmethod
    def enable_child_panel_menu_name(cls):
        return UVPM4_MT_EnableChildPanel.__name__ + '_' + cls.bl_idname
    
    def not_supported_msg(self, context):
        return None
    
    def warning_msg(self, context):
        return None

    def get_main_property(self):
        return None
    
    def is_child(self):
        return hasattr(self, 'bl_parent_id')
    
    def enable_menu_target(self):
        return self.is_child() and self.get_main_property() is not None

    def draw(self, context):
        main_property = self.get_main_property()

        if main_property is not None:
            self.layout.enabled = main_property.get()
        
        self.draw_impl(context)

    @classmethod
    def operator_with_help(cls, op_idname, layout, text=None, help_url_suffix=None):
        row = layout.row(align=True)
        kwargs = {}
        if text:
            kwargs['text'] = text

        op = row.operator(op_idname, **kwargs)

        if help_url_suffix:
            cls._draw_help_operator(row, help_url_suffix)

        return op

    @classmethod
    def operator_attach_mode(cls, op_idname, mode_id, layout, text=None, help_url_suffix=None):
        op = cls.operator_with_help(op_idname, layout, text=text, help_url_suffix=help_url_suffix)
        if (hasattr(op, 'mode_id')):
            op.mode_id = mode_id

        return op

    def handle_prop_enum(self, obj, prop_name, prop_label, supported, not_supported_msg, layout):
        prop_label_colon = prop_label + ':'

        if supported:
            layout.label(text=prop_label_colon)
        else:
            split = layout.split(factor=0.4)
            col_s = split.column()
            col_s.label(text=prop_label_colon)
            col_s = split.column()
            col_s.label(text=not_supported_msg)

        layout.prop(obj, prop_name, text='')
        layout.enabled = supported

    def messages_in_boxes(self, ui_elem, messages):
        for msg in messages:
            box = ui_elem.box()

            msg_split = split_by_chars(msg, 60)
            if len(msg_split) > 0:
                # box.separator()
                for msg_part in msg_split:
                    box.label(text=msg_part)
                # box.separator()
        

class UVPM4_PT_IParamEditMixin:

    def get_main_property(self):
        from .operator_islands import UVPM4_OT_StdIParamGeneric
        return UVPM4_OT_StdIParamGeneric.get_iparam_info_impl(self.IPARAM_INFO_TYPE).enabled_property_s(self.context)

    def draw_impl(self, context):
        from .operator_islands import IParamEditUI
        IParamEditUI(context, self.main_props, self.IPARAM_INFO_TYPE, self.HELP_URL_SUFFIX if self.props_with_help else None).draw(self.layout)


class UVPM4_OT_EnablePanel(Operator):

    bl_label = ''
    bl_idname = 'uvpackmaster4.enable_panel'

    panel_id : StringProperty(name='', default='')
    enable : BoolProperty(name='', default=False)

    @classmethod
    def description(cls, context, properties):
        return 'Enable feature' if properties.enable else 'Disable feature'

    def execute(self, context):
        mp_manager = get_multi_panel_manager(context)
        panel_data = mp_manager.get_panel_data(self.panel_id)

        panel = panel_data.create_instance(context)
        main_prop = panel.get_main_property()

        if main_prop is not None:
            main_prop.set(self.enable)

        if self.enable:
            bpy.ops.uvpackmaster4.expand_panel(panel_id=self.panel_id, expand=True)

        return {'FINISHED'}


class UVPM4_MT_EnableChildPanel(Menu):

    PANEL_ID : str


    def draw(self, context):
        mp_manager = get_multi_panel_manager(context)
        panel_data = mp_manager.get_panel_data(self.PANEL_ID)

        layout = self.layout
    
        for ch_panel_data in panel_data.ch_panels:
            ch_panel = ch_panel_data.create_instance(context)

            if not ch_panel_data.panel_t.poll(context):
                continue

            if not ch_panel.enable_menu_target():
                continue

            if ch_panel.get_main_property().get():
                continue

            op = layout.operator(UVPM4_OT_EnablePanel.bl_idname, text=ch_panel_data.panel_t.bl_label)
            op.panel_id = ch_panel_data.panel_t.bl_idname
            op.enable = True
