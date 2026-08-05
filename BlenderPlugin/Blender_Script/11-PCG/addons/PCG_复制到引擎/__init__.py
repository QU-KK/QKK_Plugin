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
    "name" : "PCG_Export Data_v1",
    "author" : "渠奎奎", 
    "description" : "导出PCG参数",
    "blender" : (3, 5, 0),
    "version" : (1, 0, 0),
    "location" : "",
    "warning" : "",
    "doc_url": "", 
    "tracker_url": "", 
    "category" : "PCG_工具" 
}


import bpy
import bpy.utils.previews
import pyperclip


addon_keymaps = {}
_icons = None
pcg = {'sna_pcg_list_variable': [], 'sna_pcg_listrepot': [], }
node_tree = {'sna_pcg_quantitycache': 0, 'sna_pcg_switchout': False, }


def property_exists(prop_path, glob, loc):
    try:
        eval(prop_path, glob, loc)
        return True
    except:
        return False


def sna_remove_custom_properties_DF779_3FD29(Objects, RemoveAll, PropertyName):
    for i_A8566 in range(len(Objects)):
        Objectz = Objects[i_A8566]
        propertyName = PropertyName
        remove_allz = RemoveAll
        # Get the object
        obj = Objectz
        # Set this to True to remove all custom properties, or False to remove a specific property by name
        remove_all = remove_allz
        # Set this to the name of the custom property to remove (only used if remove_all is False)
        property_name = propertyName
        if remove_all:
            # Remove all custom properties
            custom_properties = [prop for prop in obj.keys() if prop not in obj.bl_rna.properties]
            # Delete the custom properties
            for prop in custom_properties:
                del obj[prop]
        else:
            # Remove a specific custom property by name
            if property_name in obj:
                del obj[property_name]
    return


class SNA_PT_PCG_43AC0(bpy.types.Panel):
    bl_label = 'PCG导入'
    bl_idname = 'SNA_PT_PCG_43AC0'
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_context = ''
    bl_category = 'PCG'
    bl_order = 100
    bl_options = {'DEFAULT_CLOSED'}
    bl_ui_units_x=0

    @classmethod
    def poll(cls, context):
        return not (False)

    def draw_header(self, context):
        layout = self.layout

    def draw(self, context):
        layout = self.layout
        box_0A1DF = layout.box()
        box_0A1DF.alert = False
        box_0A1DF.enabled = True
        box_0A1DF.active = True
        box_0A1DF.use_property_split = False
        box_0A1DF.use_property_decorate = False
        box_0A1DF.alignment = 'Expand'.upper()
        box_0A1DF.scale_x = 1.0
        box_0A1DF.scale_y = 1.0
        if not True: box_0A1DF.operator_context = "EXEC_DEFAULT"
        if (bpy.context.view_layer.objects.active == None):
            box_0A1DF.label(text='未选中物体', icon_value=33)
        else:
            layout_function = box_0A1DF
            sna_func_29E7D(layout_function, )


class SNA_OT_My_Generic_Operator_F5871(bpy.types.Operator):
    bl_idname = "sna.my_generic_operator_f5871"
    bl_label = "实例参数"
    bl_description = "获取guid+transform"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        if bpy.app.version >= (3, 0, 0) and False:
            cls.poll_message_set()
        return not False

    def execute(self, context):
        pcg['sna_pcg_listrepot'] = []
        node_tree['sna_pcg_switchout'] = False
        for i_D77FE in range(len(bpy.context.view_layer.objects.selected)):
            if property_exists("bpy.context.view_layer.objects.selected[i_D77FE]['Messiah_GUID']", globals(), locals()):
                pass
            else:
                node_tree['sna_pcg_switchout'] = True
                pcg['sna_pcg_listrepot'].append("不存在'Messiah_GUID'数据：" + bpy.context.view_layer.objects.selected[i_D77FE].name)
                self.report({'WARNING'}, message="不存在'Messiah_GUID'数据：" + bpy.context.view_layer.objects.selected[i_D77FE].name)
        if node_tree['sna_pcg_switchout']:
            pass
        else:
            bpy.ops.sna.my_generic_operator_90637()
            self.report({'INFO'}, message='获取成功_详细：' + str(pcg['sna_pcg_list_variable']))
        return {"FINISHED"}

    def invoke(self, context, event):
        return self.execute(context)


class SNA_OT_My_Generic_Operator_90637(bpy.types.Operator):
    bl_idname = "sna.my_generic_operator_90637"
    bl_label = "复制参数"
    bl_description = ""
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        if bpy.app.version >= (3, 0, 0) and False:
            cls.poll_message_set()
        return not False

    def execute(self, context):
        import mathutils
        # 获取场景中选中的所有物体
        selected_objects = bpy.context.selected_objects
        # 遍历选中的物体，并设置为四元数旋转
        for obj in selected_objects:
            obj.rotation_mode = 'QUATERNION'
            obj.rotation_mode = 'YXZ'
        pcg['sna_pcg_list_variable'] = []
        for i_F6FA0 in range(len(bpy.context.view_layer.objects.selected)):
            x1_in = float(bpy.context.view_layer.objects.selected[i_F6FA0].location[0] * -1.0)
            y1_in = bpy.context.view_layer.objects.selected[i_F6FA0].location[1]
            z1_in = bpy.context.view_layer.objects.selected[i_F6FA0].location[2]
            x2_in = float(bpy.context.view_layer.objects.selected[i_F6FA0].rotation_euler[0] * -1.0)
            y2_in = bpy.context.view_layer.objects.selected[i_F6FA0].rotation_euler[1]
            z2_in = bpy.context.view_layer.objects.selected[i_F6FA0].rotation_euler[2]
            x3_in = bpy.context.view_layer.objects.selected[i_F6FA0].scale[0]
            y3_in = bpy.context.view_layer.objects.selected[i_F6FA0].scale[1]
            z3_in = bpy.context.view_layer.objects.selected[i_F6FA0].scale[2]
            x1_out = None
            y1_out = None
            z1_out = None
            x2_out = None
            y2_out = None
            z2_out = None
            x3_out = None
            y3_out = None
            z3_out = None
            x1_out = format(x1_in, '.6f')
            y1_out = format(y1_in, '.6f')
            z1_out = format(z1_in, '.6f')
            x2_out = format(x2_in, '.6f')
            y2_out = format(y2_in, '.6f')
            z2_out = format(z2_in, '.6f')
            x3_out = format(x3_in, '.6f')
            y3_out = format(y3_in, '.6f')
            z3_out = format(z3_in, '.6f')
            pcg['sna_pcg_list_variable'].append('[' + "'" + bpy.context.view_layer.objects.selected[i_F6FA0]['Messiah_GUID'] + "'" + ',' + "'" + str(x1_out) + ',' + str(z1_out) + ',' + str(y1_out) + "'" + ',' + "'" + str(x2_out) + ',' + str(z2_out) + ',' + str(y2_out) + "'" + ',' + "'" + str(x3_out) + ',' + str(z3_out) + ',' + str(y3_out) + "'" + ']')
            text = pcg['sna_pcg_list_variable']
            output = '\n'.join(text)
            pyperclip.copy(output)
        return {"FINISHED"}

    def invoke(self, context, event):
        return self.execute(context)


class SNA_OT_Guid_F0D9C(bpy.types.Operator):
    bl_idname = "sna.guid_f0d9c"
    bl_label = "设置guid"
    bl_description = "设置guid"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        if bpy.app.version >= (3, 0, 0) and True:
            cls.poll_message_set('')
        return not False

    def execute(self, context):
        sna_remove_custom_properties_DF779_3FD29(bpy.context.view_layer.objects.selected, True, '')
        GUID = bpy.context.scene.sna_pcg_guid
        # 获取当前场景
        scene = bpy.context.scene
        # 获取当前选择的物体
        selected_objects = bpy.context.selected_objects
        # 确保至少有一个物体被选中
        if selected_objects:
            # 遍历选中的每个物体
            for obj in selected_objects:
                # 设置自定义属性
                obj["Messiah_GUID"] = GUID
        return {"FINISHED"}

    def invoke(self, context, event):
        return self.execute(context)


class SNA_OT_My_Generic_Operator_880A8(bpy.types.Operator):
    bl_idname = "sna.my_generic_operator_880a8"
    bl_label = "获取参数数据"
    bl_description = "只识别实例修生成节点"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        if bpy.app.version >= (3, 0, 0) and False:
            cls.poll_message_set()
        return not False

    def execute(self, context):
        bpy.ops.object.duplicates_make_real()
        node_tree['sna_pcg_quantitycache'] = len(list(bpy.context.view_layer.objects.selected))
        bpy.ops.sna.my_generic_operator_f5871()
        bpy.ops.object.delete()
        if node_tree['sna_pcg_switchout']:
            for i_2C47A in range(len(pcg['sna_pcg_listrepot'])):
                self.report({'WARNING'}, message=pcg['sna_pcg_listrepot'][i_2C47A])
        else:
            self.report({'INFO'}, message='资产数量：' + str(node_tree['sna_pcg_quantitycache']))
        return {"FINISHED"}

    def invoke(self, context, event):
        return self.execute(context)


def sna_func_29E7D(layout_function, ):
    col_D87C3 = layout_function.column(heading='', align=False)
    col_D87C3.alert = False
    col_D87C3.enabled = True
    col_D87C3.active = True
    col_D87C3.use_property_split = False
    col_D87C3.use_property_decorate = False
    col_D87C3.scale_x = 1.0
    col_D87C3.scale_y = 1.0
    col_D87C3.alignment = 'Expand'.upper()
    col_D87C3.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
    col_D87C3.label(text='选中：' + bpy.context.view_layer.objects.active.name, icon_value=292)
    col_D87C3.label(text='节点：' + (bpy.context.view_layer.objects.active.modifiers.active.name if (property_exists("bpy.context.view_layer.objects.active.modifiers.active.name", globals(), locals()) and (len(list(bpy.context.view_layer.objects.selected)) == 1)) else '无'), icon_value=368)
    col_FBFFC = col_D87C3.column(heading='', align=True)
    col_FBFFC.alert = False
    col_FBFFC.enabled = (property_exists("bpy.context.view_layer.objects.active.modifiers.active.name", globals(), locals()) and (len(list(bpy.context.view_layer.objects.selected)) == 1))
    col_FBFFC.active = True
    col_FBFFC.use_property_split = False
    col_FBFFC.use_property_decorate = False
    col_FBFFC.scale_x = 1.0
    col_FBFFC.scale_y = 2.0
    col_FBFFC.alignment = 'Expand'.upper()
    col_FBFFC.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
    op = col_FBFFC.operator('sna.my_generic_operator_880a8', text='PCG获取参数', icon_value=746, emboss=True, depress=False)


class SNA_PT_ccc_1B501(bpy.types.Panel):
    bl_label = '高级'
    bl_idname = 'SNA_PT_ccc_1B501'
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_context = ''
    bl_order = 0
    bl_options = {'DEFAULT_CLOSED'}
    bl_parent_id = 'SNA_PT_PCG_43AC0'
    bl_ui_units_x=0

    @classmethod
    def poll(cls, context):
        return not (False)

    def draw_header(self, context):
        layout = self.layout

    def draw(self, context):
        layout = self.layout
        col_C7B29 = layout.column(heading='', align=True)
        col_C7B29.alert = False
        col_C7B29.enabled = True
        col_C7B29.active = True
        col_C7B29.use_property_split = False
        col_C7B29.use_property_decorate = False
        col_C7B29.scale_x = 1.0
        col_C7B29.scale_y = 1.0
        col_C7B29.alignment = 'Expand'.upper()
        col_C7B29.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
        col_418C7 = col_C7B29.column(heading='', align=False)
        col_418C7.alert = False
        col_418C7.enabled = (len(list(bpy.context.view_layer.objects.selected)) != 0)
        col_418C7.active = True
        col_418C7.use_property_split = False
        col_418C7.use_property_decorate = False
        col_418C7.scale_x = 1.0
        col_418C7.scale_y = 1.0
        col_418C7.alignment = 'Expand'.upper()
        col_418C7.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
        split_29739 = col_418C7.split(factor=0.800000011920929, align=True)
        split_29739.alert = False
        split_29739.enabled = True
        split_29739.active = True
        split_29739.use_property_split = False
        split_29739.use_property_decorate = False
        split_29739.scale_x = 1.0
        split_29739.scale_y = 1.0
        split_29739.alignment = 'Expand'.upper()
        if not True: split_29739.operator_context = "EXEC_DEFAULT"
        split_29739.prop(bpy.context.scene, 'sna_pcg_guid', text='GUID', icon_value=0, emboss=True)
        op = split_29739.operator('sna.guid_f0d9c', text='设置', icon_value=0, emboss=True, depress=False)
        col_418C7.separator(factor=0.5)
        col_37D5A = col_C7B29.column(heading='', align=False)
        col_37D5A.alert = False
        col_37D5A.enabled = True
        col_37D5A.active = True
        col_37D5A.use_property_split = False
        col_37D5A.use_property_decorate = False
        col_37D5A.scale_x = 1.0
        col_37D5A.scale_y = 2.0
        col_37D5A.alignment = 'Expand'.upper()
        col_37D5A.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
        op = col_37D5A.operator('sna.my_generic_operator_f5871', text='实体参数获取', icon_value=235, emboss=True, depress=False)
        box_BFD24 = col_C7B29.box()
        box_BFD24.alert = False
        box_BFD24.enabled = True
        box_BFD24.active = True
        box_BFD24.use_property_split = False
        box_BFD24.use_property_decorate = False
        box_BFD24.alignment = 'Expand'.upper()
        box_BFD24.scale_x = 1.0
        box_BFD24.scale_y = 1.0
        if not True: box_BFD24.operator_context = "EXEC_DEFAULT"
        col_DB4A2 = box_BFD24.column(heading='', align=True)
        col_DB4A2.alert = False
        col_DB4A2.enabled = True
        col_DB4A2.active = True
        col_DB4A2.use_property_split = False
        col_DB4A2.use_property_decorate = False
        col_DB4A2.scale_x = 1.0
        col_DB4A2.scale_y = 1.0
        col_DB4A2.alignment = 'Expand'.upper()
        col_DB4A2.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
        col_DB4A2.label(text='选中数量：' + str(len(list(bpy.context.view_layer.objects.selected))), icon_value=0)
        for i_19DEB in range(len(bpy.context.view_layer.objects.selected)):
            col_DB4A2.label(text=bpy.context.view_layer.objects.selected[i_19DEB].name, icon_value=0)


def register():
    global _icons
    _icons = bpy.utils.previews.new()
    bpy.types.Scene.sna_pcg_guid = bpy.props.StringProperty(name='PCG_GUID', description='', default='', subtype='NONE', maxlen=0)
    bpy.utils.register_class(SNA_PT_PCG_43AC0)
    bpy.utils.register_class(SNA_OT_My_Generic_Operator_F5871)
    bpy.utils.register_class(SNA_OT_My_Generic_Operator_90637)
    bpy.utils.register_class(SNA_OT_Guid_F0D9C)
    bpy.utils.register_class(SNA_OT_My_Generic_Operator_880A8)
    bpy.utils.register_class(SNA_PT_ccc_1B501)


def unregister():
    global _icons
    bpy.utils.previews.remove(_icons)
    wm = bpy.context.window_manager
    kc = wm.keyconfigs.addon
    for km, kmi in addon_keymaps.values():
        km.keymap_items.remove(kmi)
    addon_keymaps.clear()
    del bpy.types.Scene.sna_pcg_guid
    bpy.utils.unregister_class(SNA_PT_PCG_43AC0)
    bpy.utils.unregister_class(SNA_OT_My_Generic_Operator_F5871)
    bpy.utils.unregister_class(SNA_OT_My_Generic_Operator_90637)
    bpy.utils.unregister_class(SNA_OT_Guid_F0D9C)
    bpy.utils.unregister_class(SNA_OT_My_Generic_Operator_880A8)
    bpy.utils.unregister_class(SNA_PT_ccc_1B501)
