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


import webbrowser

from .operator_generic import UVPM4_OT_Generic
from .panel import PanelUtilsMixin
from .app_iface import *


class UrlSuffixMixin:

    url_suffix : StringProperty(default='', name='')


class UVPM4_OT_HelpGeneric(UVPM4_OT_Generic):

    from .version import UvpmVersionInfo

    HELP_BASEURL = "https://uvpackmaster.com/doc4/{}/{}/".format(AppInterface.APP_ID, UvpmVersionInfo.addon_version_string())
    ATTRS_TO_CHECK = ['URL_SUFFIX', 'url_suffix']

    ICON = 'QUESTION'
    
    def execute(self, context):
        url_suffix = None

        for attr in self.ATTRS_TO_CHECK:
            if hasattr(self, attr):
                url_suffix = getattr(self, attr)
                break

        if not url_suffix:
            return {'CANCELLED'}

        webbrowser.open(self.HELP_BASEURL + url_suffix)
        return {'FINISHED'}


class UVPM4_OT_Help(UVPM4_OT_HelpGeneric, UrlSuffixMixin):

    bl_label = 'Show Help'
    bl_idname = 'uvpackmaster4.help'
    bl_description = "Show help for the given functionality"


class UVPM4_OT_PackModeHelp(UVPM4_OT_HelpGeneric, UrlSuffixMixin):

    bl_label = 'Show Mode Help'
    bl_idname = 'uvpackmaster4.pack_mode_help'
    bl_description = "Show help for the currently selected packing mode"


class UVPM4_OT_SetupHelp(UVPM4_OT_HelpGeneric):

    bl_label = 'UVPackmaster Setup Help'
    bl_idname = 'uvpackmaster4.uvpm_setup_help'
    bl_description = "Show help for UVPackmaster setup"

    URL_SUFFIX = "10-uvpackmaster-setup"


class PopupAttributeMixin:

    text : StringProperty(name='', default='', description='')
    header : StringProperty(name='', default='', description='')


class UVPM4_OT_GenericPopup(UVPM4_OT_Generic, PanelUtilsMixin):

    bl_description = "Show a popup"

    WIDTH = 600

    @classmethod
    def draw_operator(cls, layout, text, header=''):
        op = layout.operator(cls.bl_idname, text='', icon=cls.ICON)
        op.header = header
        op.text = text

    @classmethod
    def description(cls, context, properties):
        return properties.text

    def invoke(self, context, event):
        wm = context.window_manager
        return wm.invoke_popup(self, width=self.WIDTH)

    def draw(self, context):
        layout = self.layout
        header = self.header if self.header else self.bl_label

        row = layout.row()
        row.label(text=header)

        box = layout.box()
        self._draw_multiline_label(box, str(self.text) + '.', self.WIDTH)

    def execute(self, context):
        return {'FINISHED'}
    

class UVPM4_OT_HelpPopup(UVPM4_OT_GenericPopup, PopupAttributeMixin):

    bl_label = 'HELP'
    bl_idname = 'uvpackmaster4.help_popup'

    ICON = UVPM4_OT_HelpGeneric.ICON


class UVPM4_OT_WarningPopup(UVPM4_OT_GenericPopup, PopupAttributeMixin):

    bl_label = 'WARNING'
    bl_idname = 'uvpackmaster4.warning_popup'

    ICON = 'ERROR'
