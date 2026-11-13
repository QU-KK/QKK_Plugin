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
    "name" : "Reference_View",
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


class SNA_PT_reference_view_15ED7(bpy.types.Panel):
    bl_label = '关系树'
    bl_idname = 'SNA_PT_reference_view_15ED7'
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_context = ''
    bl_category = '关系树'
    bl_order = 0
    bl_ui_units_x=0

    @classmethod
    def poll(cls, context):
        return not (False)

    def draw_header(self, context):
        layout = self.layout

    def draw(self, context):
        layout = self.layout
        col_FC335 = layout.column(heading='', align=False)
        col_FC335.alert = False
        col_FC335.enabled = True
        col_FC335.active = True
        col_FC335.use_property_split = False
        col_FC335.use_property_decorate = False
        col_FC335.scale_x = 1.0
        col_FC335.scale_y = 1.0
        col_FC335.alignment = 'Expand'.upper()
        col_FC335.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
        col_FC335.label(text='范围：', icon_value=0)
        row_9BD40 = col_FC335.row(heading='', align=True)
        row_9BD40.alert = False
        row_9BD40.enabled = True
        row_9BD40.active = True
        row_9BD40.use_property_split = False
        row_9BD40.use_property_decorate = False
        row_9BD40.scale_x = 1.0
        row_9BD40.scale_y = 1.2000000476837158
        row_9BD40.alignment = 'Expand'.upper()
        row_9BD40.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
        row_9BD40.prop(bpy.context.scene, 'sna_tree_global', text=bpy.context.scene.sna_tree_global, icon_value=0, emboss=True, expand=True)
        col_5FE9C = layout.column(heading='', align=False)
        col_5FE9C.alert = False
        col_5FE9C.enabled = True
        col_5FE9C.active = True
        col_5FE9C.use_property_split = False
        col_5FE9C.use_property_decorate = False
        col_5FE9C.scale_x = 1.0
        col_5FE9C.scale_y = 1.0
        col_5FE9C.alignment = 'Expand'.upper()
        col_5FE9C.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
        if (bpy.context.scene.sna_tree_global == '指定集合'):
            col_5FE9C.prop(bpy.context.scene, 'sna_tree_collection', text='', icon_value=0, emboss=True)
        if (property_exists("bpy.context.scene.sna_tree_collection.all_objects", globals(), locals()) if (bpy.context.scene.sna_tree_global == '指定集合') else True):
            for i_33D7F in range(len((bpy.context.scene.sna_tree_collection.all_objects if (bpy.context.scene.sna_tree_global == '指定集合') else (bpy.context.scene.objects if (bpy.context.scene.sna_tree_global == '全局') else bpy.context.view_layer.objects.selected)))):
                box_BDFE0 = col_5FE9C.box()
                box_BDFE0.alert = False
                box_BDFE0.enabled = True
                box_BDFE0.active = True
                box_BDFE0.use_property_split = False
                box_BDFE0.use_property_decorate = False
                box_BDFE0.alignment = 'Expand'.upper()
                box_BDFE0.scale_x = 1.0
                box_BDFE0.scale_y = 1.0
                if not True: box_BDFE0.operator_context = "EXEC_DEFAULT"
                row_8ECDC = box_BDFE0.row(heading='', align=True)
                row_8ECDC.alert = False
                row_8ECDC.enabled = True
                row_8ECDC.active = True
                row_8ECDC.use_property_split = False
                row_8ECDC.use_property_decorate = False
                row_8ECDC.scale_x = 1.0
                row_8ECDC.scale_y = 1.0
                row_8ECDC.alignment = 'Expand'.upper()
                row_8ECDC.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
                row_8ECDC.prop(bpy.context.scene, 'sna_tree_mat_switch', text='', icon_value=(34 if bpy.context.scene.sna_tree_mat_switch else 33), emboss=False)
                col_6C5D6 = row_8ECDC.column(heading='', align=False)
                col_6C5D6.alert = False
                col_6C5D6.enabled = True
                col_6C5D6.active = True
                col_6C5D6.use_property_split = False
                col_6C5D6.use_property_decorate = False
                col_6C5D6.scale_x = 1.0
                col_6C5D6.scale_y = 1.0
                col_6C5D6.alignment = 'Expand'.upper()
                col_6C5D6.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
                row_DB25A = col_6C5D6.row(heading='', align=False)
                row_DB25A.alert = False
                row_DB25A.enabled = True
                row_DB25A.active = True
                row_DB25A.use_property_split = False
                row_DB25A.use_property_decorate = False
                row_DB25A.scale_x = 1.0
                row_DB25A.scale_y = 1.0
                row_DB25A.alignment = 'Expand'.upper()
                row_DB25A.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
                op = row_DB25A.operator('sna.select_object_90730', text='', icon_value=294, emboss=True, depress=False)
                op.sna_obj_name = (bpy.context.scene.sna_tree_collection.all_objects if (bpy.context.scene.sna_tree_global == '指定集合') else (bpy.context.scene.objects if (bpy.context.scene.sna_tree_global == '全局') else bpy.context.view_layer.objects.selected))[i_33D7F].name
                row_DB25A.label(text=(bpy.context.scene.sna_tree_collection.all_objects if (bpy.context.scene.sna_tree_global == '指定集合') else (bpy.context.scene.objects if (bpy.context.scene.sna_tree_global == '全局') else bpy.context.view_layer.objects.selected))[i_33D7F].name, icon_value=0)
                if bpy.context.scene.sna_tree_mat_switch:
                    if (len((bpy.context.scene.sna_tree_collection.all_objects if (bpy.context.scene.sna_tree_global == '指定集合') else (bpy.context.scene.objects if (bpy.context.scene.sna_tree_global == '全局') else bpy.context.view_layer.objects.selected))[i_33D7F].material_slots) != 0):
                        box_F9852 = col_6C5D6.box()
                        box_F9852.alert = False
                        box_F9852.enabled = True
                        box_F9852.active = True
                        box_F9852.use_property_split = False
                        box_F9852.use_property_decorate = False
                        box_F9852.alignment = 'Expand'.upper()
                        box_F9852.scale_x = 1.0
                        box_F9852.scale_y = 1.0
                        if not True: box_F9852.operator_context = "EXEC_DEFAULT"
                        col_2E401 = box_F9852.column(heading='', align=False)
                        col_2E401.alert = False
                        col_2E401.enabled = True
                        col_2E401.active = True
                        col_2E401.use_property_split = False
                        col_2E401.use_property_decorate = False
                        col_2E401.scale_x = 1.0
                        col_2E401.scale_y = 1.0
                        col_2E401.alignment = 'Expand'.upper()
                        col_2E401.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
                        for i_438D7 in range(len((bpy.context.scene.sna_tree_collection.all_objects if (bpy.context.scene.sna_tree_global == '指定集合') else (bpy.context.scene.objects if (bpy.context.scene.sna_tree_global == '全局') else bpy.context.view_layer.objects.selected))[i_33D7F].material_slots)):
                            row_5EE46 = col_2E401.row(heading='', align=True)
                            row_5EE46.alert = False
                            row_5EE46.enabled = True
                            row_5EE46.active = True
                            row_5EE46.use_property_split = False
                            row_5EE46.use_property_decorate = False
                            row_5EE46.scale_x = 1.0
                            row_5EE46.scale_y = 1.0
                            row_5EE46.alignment = 'Expand'.upper()
                            row_5EE46.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
                            row_5EE46.prop(bpy.context.scene, 'sna_tree_img_switch', text='', icon_value=(34 if bpy.context.scene.sna_tree_img_switch else 33), emboss=False)
                            col_CFC20 = row_5EE46.column(heading='', align=False)
                            col_CFC20.alert = False
                            col_CFC20.enabled = True
                            col_CFC20.active = True
                            col_CFC20.use_property_split = False
                            col_CFC20.use_property_decorate = False
                            col_CFC20.scale_x = 1.0
                            col_CFC20.scale_y = 1.0
                            col_CFC20.alignment = 'Expand'.upper()
                            col_CFC20.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
                            col_64D05 = col_CFC20.column(heading='', align=False)
                            col_64D05.alert = '.0' in (bpy.context.scene.sna_tree_collection.all_objects if (bpy.context.scene.sna_tree_global == '指定集合') else (bpy.context.scene.objects if (bpy.context.scene.sna_tree_global == '全局') else bpy.context.view_layer.objects.selected))[i_33D7F].material_slots[i_438D7].material.name[-4:]
                            col_64D05.enabled = True
                            col_64D05.active = True
                            col_64D05.use_property_split = False
                            col_64D05.use_property_decorate = False
                            col_64D05.scale_x = 1.0
                            col_64D05.scale_y = 1.0
                            col_64D05.alignment = 'Expand'.upper()
                            col_64D05.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
                            col_64D05.label(text=(bpy.context.scene.sna_tree_collection.all_objects if (bpy.context.scene.sna_tree_global == '指定集合') else (bpy.context.scene.objects if (bpy.context.scene.sna_tree_global == '全局') else bpy.context.view_layer.objects.selected))[i_33D7F].material_slots[i_438D7].material.name, icon_value=150)
                            if bpy.context.scene.sna_tree_img_switch:
                                box_2639F = col_CFC20.box()
                                box_2639F.alert = False
                                box_2639F.enabled = True
                                box_2639F.active = True
                                box_2639F.use_property_split = False
                                box_2639F.use_property_decorate = False
                                box_2639F.alignment = 'Expand'.upper()
                                box_2639F.scale_x = 1.0
                                box_2639F.scale_y = 1.0
                                if not True: box_2639F.operator_context = "EXEC_DEFAULT"
                                col_63097 = box_2639F.column(heading='', align=False)
                                col_63097.alert = False
                                col_63097.enabled = True
                                col_63097.active = True
                                col_63097.use_property_split = False
                                col_63097.use_property_decorate = False
                                col_63097.scale_x = 1.0
                                col_63097.scale_y = 1.0
                                col_63097.alignment = 'Expand'.upper()
                                col_63097.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
                                for i_01709 in range(len((bpy.context.scene.sna_tree_collection.all_objects if (bpy.context.scene.sna_tree_global == '指定集合') else (bpy.context.scene.objects if (bpy.context.scene.sna_tree_global == '全局') else bpy.context.view_layer.objects.selected))[i_33D7F].material_slots[i_438D7].material.node_tree.nodes)):
                                    if property_exists("(bpy.context.scene.sna_tree_collection.all_objects if (bpy.context.scene.sna_tree_global == '指定集合') else (bpy.context.scene.objects if (bpy.context.scene.sna_tree_global == '全局') else bpy.context.view_layer.objects.selected))[i_33D7F].material_slots[i_438D7].material.node_tree.nodes[i_01709].image.name", globals(), locals()):
                                        col_44EB7 = col_63097.column(heading='', align=False)
                                        col_44EB7.alert = '.0' in (bpy.context.scene.sna_tree_collection.all_objects if (bpy.context.scene.sna_tree_global == '指定集合') else (bpy.context.scene.objects if (bpy.context.scene.sna_tree_global == '全局') else bpy.context.view_layer.objects.selected))[i_33D7F].material_slots[i_438D7].material.node_tree.nodes[i_01709].image.name[-4:]
                                        col_44EB7.enabled = True
                                        col_44EB7.active = True
                                        col_44EB7.use_property_split = False
                                        col_44EB7.use_property_decorate = False
                                        col_44EB7.scale_x = 1.0
                                        col_44EB7.scale_y = 1.0
                                        col_44EB7.alignment = 'Expand'.upper()
                                        col_44EB7.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
                                        col_44EB7.label(text=(bpy.context.scene.sna_tree_collection.all_objects if (bpy.context.scene.sna_tree_global == '指定集合') else (bpy.context.scene.objects if (bpy.context.scene.sna_tree_global == '全局') else bpy.context.view_layer.objects.selected))[i_33D7F].material_slots[i_438D7].material.node_tree.nodes[i_01709].image.name, icon_value=290)


class SNA_OT_Select_Object_90730(bpy.types.Operator):
    bl_idname = "sna.select_object_90730"
    bl_label = "Select_Object"
    bl_description = ""
    bl_options = {"REGISTER", "UNDO"}
    sna_obj_name: bpy.props.StringProperty(name='obj_name', description='', options={'HIDDEN'}, default='', subtype='NONE', maxlen=0)

    @classmethod
    def poll(cls, context):
        if bpy.app.version >= (3, 0, 0) and True:
            cls.poll_message_set('')
        return not False

    def execute(self, context):
        bpy.context.view_layer.objects.active = bpy.data.objects[self.sna_obj_name]
        bpy.ops.object.select_pattern(pattern=self.sna_obj_name, case_sensitive=True, extend=False)
        return {"FINISHED"}

    def invoke(self, context, event):
        return self.execute(context)


def register():
    global _icons
    _icons = bpy.utils.previews.new()
    bpy.types.Scene.sna_tree_mat_switch = bpy.props.BoolProperty(name='tree_mat_switch', description='', default=True)
    bpy.types.Scene.sna_tree_img_switch = bpy.props.BoolProperty(name='tree_img_switch', description='', default=False)
    bpy.types.Scene.sna_tree_global = bpy.props.EnumProperty(name='tree_global', description='', items=[('选择项', '选择项', '', 0, 0), ('全局', '全局', '', 0, 1), ('指定集合', '指定集合', '', 0, 2)])
    bpy.types.Scene.sna_tree_collection = bpy.props.PointerProperty(name='tree_collection', description='', type=bpy.types.Collection)
    bpy.utils.register_class(SNA_PT_reference_view_15ED7)
    bpy.utils.register_class(SNA_OT_Select_Object_90730)


def unregister():
    global _icons
    bpy.utils.previews.remove(_icons)
    wm = bpy.context.window_manager
    kc = wm.keyconfigs.addon
    for km, kmi in addon_keymaps.values():
        km.keymap_items.remove(kmi)
    addon_keymaps.clear()
    del bpy.types.Scene.sna_tree_collection
    del bpy.types.Scene.sna_tree_global
    del bpy.types.Scene.sna_tree_img_switch
    del bpy.types.Scene.sna_tree_mat_switch
    bpy.utils.unregister_class(SNA_PT_reference_view_15ED7)
    bpy.utils.unregister_class(SNA_OT_Select_Object_90730)
