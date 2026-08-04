# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTIBILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU
# General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program. If not, see <http://www.gnu.org/licenses/>.

bl_info = {
    "name" : "key_management",
    "author" : "qkk", 
    "description" : "",
    "blender" : (4, 2, 0),
    "version" : (1, 0, 0),
    "location" : "",
    "warning" : "",
    "doc_url": "", 
    "tracker_url": "", 
    "category" : "3D View" 
}


import bpy
import bpy.utils.previews


addon_keymaps = {}
_icons = None


def property_exists(prop_path, glob, loc):
    try:
        eval(prop_path, glob, loc)
        return True
    except:
        return False


def sna_key_interface_89B70(layout_function, attribute, name):
    col_64751 = layout_function.column(heading='', align=True)
    col_64751.alert = False
    col_64751.enabled = True
    col_64751.active = True
    col_64751.use_property_split = False
    col_64751.use_property_decorate = False
    col_64751.scale_x = 1.0
    col_64751.scale_y = 1.0
    col_64751.alignment = 'Expand'.upper()
    col_64751.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
    row_281CF = col_64751.row(heading='', align=True)
    row_281CF.alert = False
    row_281CF.enabled = True
    row_281CF.active = True
    row_281CF.use_property_split = False
    row_281CF.use_property_decorate = False
    row_281CF.scale_x = 1.0
    row_281CF.scale_y = 1.0
    row_281CF.alignment = 'Expand'.upper()
    row_281CF.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
    row_281CF.prop(attribute, 'show_expanded', text='', icon_value=0, emboss=False)
    row_281CF.prop(attribute, 'active', text='', icon_value=0, emboss=True, toggle=False)
    row_281CF.label(text=attribute.name, icon_value=0)
    row_281CF.label(text=name, icon_value=0)
    if attribute.show_expanded:
        col_F4A13 = col_64751.column(heading='', align=False)
        col_F4A13.alert = False
        col_F4A13.enabled = True
        col_F4A13.active = True
        col_F4A13.use_property_split = False
        col_F4A13.use_property_decorate = False
        col_F4A13.scale_x = 1.0
        col_F4A13.scale_y = 1.0
        col_F4A13.alignment = 'Expand'.upper()
        col_F4A13.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
        row_B5704 = col_F4A13.row(heading='', align=True)
        row_B5704.alert = False
        row_B5704.enabled = True
        row_B5704.active = True
        row_B5704.use_property_split = False
        row_B5704.use_property_decorate = False
        row_B5704.scale_x = 1.0
        row_B5704.scale_y = 1.0
        row_B5704.alignment = 'Expand'.upper()
        row_B5704.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
        row_B5704.prop(attribute, 'type', text='键', icon_value=0, emboss=True)
        row_B5704.prop(attribute, 'value', text='', icon_value=0, emboss=True)
        row_B5704.prop(attribute, 'map_type', text='', icon_value=0, emboss=True, toggle=False)
        split_8FE44 = col_F4A13.split(factor=0.4000000059604645, align=True)
        split_8FE44.alert = False
        split_8FE44.enabled = True
        split_8FE44.active = True
        split_8FE44.use_property_split = False
        split_8FE44.use_property_decorate = False
        split_8FE44.scale_x = 1.0
        split_8FE44.scale_y = 1.0
        split_8FE44.alignment = 'Expand'.upper()
        if not True: split_8FE44.operator_context = "EXEC_DEFAULT"
        split_8FE44.separator(factor=1.0)
        row_704A5 = split_8FE44.row(heading='', align=True)
        row_704A5.alert = False
        row_704A5.enabled = True
        row_704A5.active = True
        row_704A5.use_property_split = False
        row_704A5.use_property_decorate = False
        row_704A5.scale_x = 1.0
        row_704A5.scale_y = 1.0
        row_704A5.alignment = 'Expand'.upper()
        row_704A5.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
        row_704A5.prop(attribute, 'any', text='任意', icon_value=0, emboss=True, toggle=True)
        row_704A5.prop(attribute, 'shift_ui', text='Shift ', icon_value=0, emboss=True, toggle=True)
        row_704A5.prop(attribute, 'ctrl_ui', text='Ctrl', icon_value=0, emboss=True, toggle=True)
        row_704A5.prop(attribute, 'alt_ui', text='Alt', icon_value=0, emboss=True, toggle=True)
        row_704A5.prop(attribute, 'oskey_ui', text='Win', icon_value=0, emboss=True, toggle=True)


class SNA_PT_D_AAD35(bpy.types.Panel):
    bl_label = '3D操作模型快捷键'
    bl_idname = 'SNA_PT_D_AAD35'
    bl_space_type = 'PREFERENCES'
    bl_region_type = 'WINDOW'
    bl_context = ''
    bl_category = '3D操作模型快捷键'
    bl_order = 0
    bl_options = {'DEFAULT_CLOSED'}
    bl_ui_units_x=0

    @classmethod
    def poll(cls, context):
        return not ((bpy.context.preferences.active_section != 'KEYMAP'))

    def draw_header(self, context):
        layout = self.layout

    def draw(self, context):
        layout = self.layout
        for i_B9916 in range(len(bpy.context.window_manager.keyconfigs.addon.keymaps)):
            for i_5B276 in range(len(bpy.context.window_manager.keyconfigs.addon.keymaps[i_B9916].keymap_items)):
                if '(Qkk_3DMode)' in bpy.context.window_manager.keyconfigs.addon.keymaps[i_B9916].keymap_items[i_5B276].name:
                    box_D8CEB = layout.box()
                    box_D8CEB.alert = False
                    box_D8CEB.enabled = True
                    box_D8CEB.active = True
                    box_D8CEB.use_property_split = False
                    box_D8CEB.use_property_decorate = False
                    box_D8CEB.alignment = 'Expand'.upper()
                    box_D8CEB.scale_x = 1.0
                    box_D8CEB.scale_y = 1.0
                    if not True: box_D8CEB.operator_context = "EXEC_DEFAULT"
                    layout_function = box_D8CEB
                    sna_key_interface_89B70(layout_function, bpy.context.window_manager.keyconfigs.addon.keymaps[i_B9916].keymap_items[i_5B276], '')
                    split_E8262 = box_D8CEB.split(factor=0.10000000149011612, align=True)
                    split_E8262.alert = False
                    split_E8262.enabled = True
                    split_E8262.active = True
                    split_E8262.use_property_split = False
                    split_E8262.use_property_decorate = False
                    split_E8262.scale_x = 1.0
                    split_E8262.scale_y = 1.0
                    split_E8262.alignment = 'Expand'.upper()
                    if not True: split_E8262.operator_context = "EXEC_DEFAULT"
                    split_E8262.separator(factor=1.0)
                    col_4287A = split_E8262.column(heading='', align=True)
                    col_4287A.alert = False
                    col_4287A.enabled = True
                    col_4287A.active = True
                    col_4287A.use_property_split = False
                    col_4287A.use_property_decorate = False
                    col_4287A.scale_x = 1.0
                    col_4287A.scale_y = 1.0
                    col_4287A.alignment = 'Expand'.upper()
                    col_4287A.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
                    for i_9D7EF in range(len(['3D View', 'Object Mode', 'Mesh', 'Curve', 'Curves', 'Frames', 'Vertex Paint'])):
                        if property_exists("bpy.context.window_manager.keyconfigs.active.keymaps[['3D View', 'Object Mode', 'Mesh', 'Curve', 'Curves', 'Frames', 'Vertex Paint'][i_9D7EF]].keymap_items", globals(), locals()):
                            for i_440C1 in range(len(bpy.context.window_manager.keyconfigs.active.keymaps[['3D View', 'Object Mode', 'Mesh', 'Curve', 'Curves', 'Frames', 'Vertex Paint'][i_9D7EF]].keymap_items)):
                                if ([bpy.context.window_manager.keyconfigs.addon.keymaps[i_B9916].keymap_items[i_5B276].type, bpy.context.window_manager.keyconfigs.addon.keymaps[i_B9916].keymap_items[i_5B276].any, bpy.context.window_manager.keyconfigs.addon.keymaps[i_B9916].keymap_items[i_5B276].shift_ui, bpy.context.window_manager.keyconfigs.addon.keymaps[i_B9916].keymap_items[i_5B276].ctrl_ui, bpy.context.window_manager.keyconfigs.addon.keymaps[i_B9916].keymap_items[i_5B276].alt_ui, bpy.context.window_manager.keyconfigs.addon.keymaps[i_B9916].keymap_items[i_5B276].oskey_ui] == [bpy.context.window_manager.keyconfigs.active.keymaps[['3D View', 'Object Mode', 'Mesh', 'Curve', 'Curves', 'Frames', 'Vertex Paint'][i_9D7EF]].keymap_items[i_440C1].type, bpy.context.window_manager.keyconfigs.active.keymaps[['3D View', 'Object Mode', 'Mesh', 'Curve', 'Curves', 'Frames', 'Vertex Paint'][i_9D7EF]].keymap_items[i_440C1].any, bpy.context.window_manager.keyconfigs.active.keymaps[['3D View', 'Object Mode', 'Mesh', 'Curve', 'Curves', 'Frames', 'Vertex Paint'][i_9D7EF]].keymap_items[i_440C1].shift_ui, bpy.context.window_manager.keyconfigs.active.keymaps[['3D View', 'Object Mode', 'Mesh', 'Curve', 'Curves', 'Frames', 'Vertex Paint'][i_9D7EF]].keymap_items[i_440C1].ctrl_ui, bpy.context.window_manager.keyconfigs.active.keymaps[['3D View', 'Object Mode', 'Mesh', 'Curve', 'Curves', 'Frames', 'Vertex Paint'][i_9D7EF]].keymap_items[i_440C1].alt_ui, bpy.context.window_manager.keyconfigs.active.keymaps[['3D View', 'Object Mode', 'Mesh', 'Curve', 'Curves', 'Frames', 'Vertex Paint'][i_9D7EF]].keymap_items[i_440C1].oskey_ui]):
                                    box_397C2 = col_4287A.box()
                                    box_397C2.alert = False
                                    box_397C2.enabled = True
                                    box_397C2.active = True
                                    box_397C2.use_property_split = False
                                    box_397C2.use_property_decorate = False
                                    box_397C2.alignment = 'Expand'.upper()
                                    box_397C2.scale_x = 1.0
                                    box_397C2.scale_y = 1.0
                                    if not True: box_397C2.operator_context = "EXEC_DEFAULT"
                                    layout_function = box_397C2
                                    sna_key_interface_89B70(layout_function, bpy.context.window_manager.keyconfigs.active.keymaps[['3D View', 'Object Mode', 'Mesh', 'Curve', 'Curves', 'Frames', 'Vertex Paint'][i_9D7EF]].keymap_items[i_440C1], ['3D View', 'Object Mode', 'Mesh', 'Curve', 'Curves', 'Frames', 'Vertex Paint'][i_9D7EF])
                        else:
                            col_F8F86 = col_4287A.column(heading='', align=True)
                            col_F8F86.alert = True
                            col_F8F86.enabled = True
                            col_F8F86.active = True
                            col_F8F86.use_property_split = False
                            col_F8F86.use_property_decorate = False
                            col_F8F86.scale_x = 1.0
                            col_F8F86.scale_y = 1.0
                            col_F8F86.alignment = 'Expand'.upper()
                            col_F8F86.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
                            col_F8F86.label(text='缺失类别：' + ['3D View', 'Object Mode', 'Mesh', 'Curve', 'Curves', 'Frames', 'Vertex Paint'][i_9D7EF], icon_value=0)


def register():
    global _icons
    _icons = bpy.utils.previews.new()
    bpy.utils.register_class(SNA_PT_D_AAD35)


def unregister():
    global _icons
    bpy.utils.previews.remove(_icons)
    wm = bpy.context.window_manager
    kc = wm.keyconfigs.addon
    for km, kmi in addon_keymaps.values():
        km.keymap_items.remove(kmi)
    addon_keymaps.clear()
    bpy.utils.unregister_class(SNA_PT_D_AAD35)
