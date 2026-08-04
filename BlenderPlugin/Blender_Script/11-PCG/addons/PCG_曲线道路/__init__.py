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
    "name" : "PCG_Curved Road_v2",
    "author" : "渠奎奎", 
    "description" : "曲线道路v2",
    "blender" : (4, 2, 0),
    "version" : (2, 0, 0),
    "location" : "",
    "warning" : "",
    "doc_url": "", 
    "tracker_url": "", 
    "category" : "PCG_工具" 
}


import bpy
import bpy.utils.previews
import os


addon_keymaps = {}
_icons = None
node_tree_001 = {'sna_pcg_modname': '', }


def property_exists(prop_path, glob, loc):
    try:
        eval(prop_path, glob, loc)
        return True
    except:
        return False


class SNA_OT_My_Generic_Operator_07439(bpy.types.Operator):
    bl_idname = "sna.my_generic_operator_07439"
    bl_label = "清空曲线道路_修改器"
    bl_description = ""
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        if bpy.app.version >= (3, 0, 0) and False:
            cls.poll_message_set()
        return not False

    def execute(self, context):
        bpy.context.view_layer.objects.active.modifiers.clear()
        return {"FINISHED"}

    def invoke(self, context, event):
        return context.window_manager.invoke_confirm(self, event)


class SNA_PT_PCG__97FEF(bpy.types.Panel):
    bl_label = 'PCG_曲线道路'
    bl_idname = 'SNA_PT_PCG__97FEF'
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_context = ''
    bl_category = 'PCG'
    bl_order = 0
    bl_options = {'DEFAULT_CLOSED'}
    bl_ui_units_x=0

    @classmethod
    def poll(cls, context):
        return not (False)

    def draw_header(self, context):
        layout = self.layout

    def draw(self, context):
        layout = self.layout
        if (bpy.context.view_layer.objects.active != None):
            col_4B7E7 = layout.column(heading='', align=True)
            col_4B7E7.alert = False
            col_4B7E7.enabled = property_exists("bpy.context.view_layer.objects.active.data.splines", globals(), locals())
            col_4B7E7.active = True
            col_4B7E7.use_property_split = False
            col_4B7E7.use_property_decorate = False
            col_4B7E7.scale_x = 1.0
            col_4B7E7.scale_y = 1.0
            col_4B7E7.alignment = 'Expand'.upper()
            col_4B7E7.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
            if property_exists("bpy.context.view_layer.objects.active.data.splines", globals(), locals()):
                col_4B7E7.label(text='选中曲线：' + bpy.context.view_layer.objects.active.name, icon_value=236)
            else:
                col_4B7E7.label(text='非曲线：' + bpy.context.view_layer.objects.active.name, icon_value=3)
            col_4B7E7.separator(factor=2.0)
            if property_exists("bpy.context.object.modifiers['PCG_道路节点_v2'].node_group.name", globals(), locals()):
                col_E230A = col_4B7E7.column(heading='', align=True)
                col_E230A.alert = False
                col_E230A.enabled = True
                col_E230A.active = True
                col_E230A.use_property_split = False
                col_E230A.use_property_decorate = False
                col_E230A.scale_x = 1.0
                col_E230A.scale_y = 1.0
                col_E230A.alignment = 'Expand'.upper()
                col_E230A.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
                split_F3ED3 = col_E230A.split(factor=0.5, align=True)
                split_F3ED3.alert = False
                split_F3ED3.enabled = True
                split_F3ED3.active = True
                split_F3ED3.use_property_split = False
                split_F3ED3.use_property_decorate = False
                split_F3ED3.scale_x = 1.0
                split_F3ED3.scale_y = 1.2000000476837158
                split_F3ED3.alignment = 'Expand'.upper()
                if not True: split_F3ED3.operator_context = "EXEC_DEFAULT"
                op = split_F3ED3.operator('sna.my_generic_operator_07439', text='清空', icon_value=33, emboss=True, depress=False)
                col_B4EA7 = split_F3ED3.column(heading='', align=True)
                col_B4EA7.alert = False
                col_B4EA7.enabled = (len(list(bpy.context.view_layer.objects.selected)) == 1)
                col_B4EA7.active = True
                col_B4EA7.use_property_split = False
                col_B4EA7.use_property_decorate = False
                col_B4EA7.scale_x = 1.0
                col_B4EA7.scale_y = 1.0
                col_B4EA7.alignment = 'Expand'.upper()
                col_B4EA7.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
                op = col_B4EA7.operator('sna.my_generic_operator_e343b', text='应用', icon_value=36, emboss=True, depress=False)
                col_86248 = col_E230A.column(heading='', align=True)
                col_86248.alert = False
                col_86248.enabled = True
                col_86248.active = True
                col_86248.use_property_split = False
                col_86248.use_property_decorate = False
                col_86248.scale_x = 1.0
                col_86248.scale_y = 1.0
                col_86248.alignment = 'Expand'.upper()
                col_86248.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
                op = col_86248.operator('sna.my_generic_operator_ef8e8', text='删除曲线点', icon_value=21, emboss=True, depress=False)
                box_07801 = col_E230A.box()
                box_07801.alert = False
                box_07801.enabled = True
                box_07801.active = True
                box_07801.use_property_split = False
                box_07801.use_property_decorate = False
                box_07801.alignment = 'Expand'.upper()
                box_07801.scale_x = 1.0
                box_07801.scale_y = 1.0
                if not True: box_07801.operator_context = "EXEC_DEFAULT"
                col_B2F75 = box_07801.column(heading='', align=False)
                col_B2F75.alert = False
                col_B2F75.enabled = True
                col_B2F75.active = True
                col_B2F75.use_property_split = False
                col_B2F75.use_property_decorate = False
                col_B2F75.scale_x = 1.0
                col_B2F75.scale_y = 1.2000000476837158
                col_B2F75.alignment = 'Expand'.upper()
                col_B2F75.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
                attr_812E2 = '["' + str('Input_2' + '"]') 
                col_B2F75.prop(bpy.context.view_layer.objects.active.modifiers['PCG_道路节点_v2'], attr_812E2, text='地表', icon_value=0, emboss=True)
                split_358FA = col_B2F75.split(factor=0.5, align=True)
                split_358FA.alert = False
                split_358FA.enabled = True
                split_358FA.active = True
                split_358FA.use_property_split = False
                split_358FA.use_property_decorate = False
                split_358FA.scale_x = 1.0
                split_358FA.scale_y = 1.0
                split_358FA.alignment = 'Expand'.upper()
                if not True: split_358FA.operator_context = "EXEC_DEFAULT"
                attr_CAB51 = '["' + str('Input_9' + '"]') 
                split_358FA.prop(bpy.context.view_layer.objects.active.modifiers['PCG_道路节点_v2'], attr_CAB51, text='路宽', icon_value=0, emboss=True)
                attr_D6569 = '["' + str('Input_4' + '"]') 
                split_358FA.prop(bpy.context.view_layer.objects.active.modifiers['PCG_道路节点_v2'], attr_D6569, text='宽度细分', icon_value=0, emboss=True)
                attr_4A34D = '["' + str('Input_5' + '"]') 
                col_B2F75.prop(bpy.context.view_layer.objects.active.modifiers['PCG_道路节点_v2'], attr_4A34D, text='长度细分间隔', icon_value=0, emboss=True)
                attr_86709 = '["' + str('Input_10' + '"]') 
                col_B2F75.prop(bpy.context.view_layer.objects.active.modifiers['PCG_道路节点_v2'], attr_86709, text='垂直贴合偏移', icon_value=0, emboss=True)
                col_31374 = col_B2F75.column(heading='', align=True)
                col_31374.alert = False
                col_31374.enabled = True
                col_31374.active = True
                col_31374.use_property_split = False
                col_31374.use_property_decorate = False
                col_31374.scale_x = 1.0
                col_31374.scale_y = 1.0
                col_31374.alignment = 'Expand'.upper()
                col_31374.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
                col_31374.label(text='UV比例：', icon_value=0)
                row_4F558 = col_31374.row(heading='', align=True)
                row_4F558.alert = False
                row_4F558.enabled = True
                row_4F558.active = True
                row_4F558.use_property_split = False
                row_4F558.use_property_decorate = False
                row_4F558.scale_x = 1.0
                row_4F558.scale_y = 1.0
                row_4F558.alignment = 'Expand'.upper()
                row_4F558.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
                op = row_4F558.operator('sna.uv_962af', text='1:1', icon_value=0, emboss=True, depress=(bpy.context.view_layer.objects.active.modifiers['PCG_道路节点_v2']['Socket_0'] == 0))
                op.sna_uv = 0
                op = row_4F558.operator('sna.uv_962af', text='2:1', icon_value=0, emboss=True, depress=(bpy.context.view_layer.objects.active.modifiers['PCG_道路节点_v2']['Socket_0'] == 1))
                op.sna_uv = 1
                op = row_4F558.operator('sna.uv_962af', text='4:1', icon_value=0, emboss=True, depress=(bpy.context.view_layer.objects.active.modifiers['PCG_道路节点_v2']['Socket_0'] == 2))
                op.sna_uv = 2
                box_89F88 = col_B2F75.box()
                box_89F88.alert = False
                box_89F88.enabled = True
                box_89F88.active = True
                box_89F88.use_property_split = False
                box_89F88.use_property_decorate = False
                box_89F88.alignment = 'Expand'.upper()
                box_89F88.scale_x = 1.0
                box_89F88.scale_y = 1.0
                if not True: box_89F88.operator_context = "EXEC_DEFAULT"
                col_02EAA = box_89F88.column(heading='', align=False)
                col_02EAA.alert = False
                col_02EAA.enabled = True
                col_02EAA.active = True
                col_02EAA.use_property_split = False
                col_02EAA.use_property_decorate = False
                col_02EAA.scale_x = 1.0
                col_02EAA.scale_y = 1.0
                col_02EAA.alignment = 'Expand'.upper()
                col_02EAA.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
                attr_994F6 = '["' + str('Input_13' + '"]') 
                col_02EAA.prop(bpy.context.view_layer.objects.active.modifiers['PCG_道路节点_v2'], attr_994F6, text='使用定位点生成', icon_value=0, emboss=True)
                if bpy.context.view_layer.objects.active.modifiers['PCG_道路节点_v2']['Input_13']:
                    col_7BFFC = col_02EAA.column(heading='', align=False)
                    col_7BFFC.alert = False
                    col_7BFFC.enabled = True
                    col_7BFFC.active = True
                    col_7BFFC.use_property_split = False
                    col_7BFFC.use_property_decorate = False
                    col_7BFFC.scale_x = 1.0
                    col_7BFFC.scale_y = 1.0
                    col_7BFFC.alignment = 'Expand'.upper()
                    col_7BFFC.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
                    op = col_7BFFC.operator('sna.my_generic_operator_ca4f6', text='更新定位点', icon_value=0, emboss=True, depress=False)
                    col_7BFFC.prop(bpy.context.scene, 'sna_pcg_anchor_point', text='定位点', icon_value=0, emboss=True)
                    box_6599F = col_7BFFC.box()
                    box_6599F.alert = False
                    box_6599F.enabled = True
                    box_6599F.active = True
                    box_6599F.use_property_split = False
                    box_6599F.use_property_decorate = False
                    box_6599F.alignment = 'Expand'.upper()
                    box_6599F.scale_x = 1.0
                    box_6599F.scale_y = 1.0
                    if not True: box_6599F.operator_context = "EXEC_DEFAULT"
                    col_5B2CD = box_6599F.column(heading='', align=False)
                    col_5B2CD.alert = False
                    col_5B2CD.enabled = True
                    col_5B2CD.active = True
                    col_5B2CD.use_property_split = False
                    col_5B2CD.use_property_decorate = False
                    col_5B2CD.scale_x = 1.0
                    col_5B2CD.scale_y = 1.0
                    col_5B2CD.alignment = 'Expand'.upper()
                    col_5B2CD.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
                    col_5B2CD.label(text='定位点连接方式：', icon_value=0)
                    split_143A8 = col_5B2CD.split(factor=0.5, align=True)
                    split_143A8.alert = False
                    split_143A8.enabled = True
                    split_143A8.active = True
                    split_143A8.use_property_split = False
                    split_143A8.use_property_decorate = False
                    split_143A8.scale_x = 1.0
                    split_143A8.scale_y = 1.0
                    split_143A8.alignment = 'Expand'.upper()
                    if not True: split_143A8.operator_context = "EXEC_DEFAULT"
                    attr_2D4A4 = '["' + str('Socket_1' + '"]') 
                    split_143A8.prop(bpy.context.view_layer.objects.active.modifiers['PCG_道路节点_v2'], attr_2D4A4, text='自动连接', icon_value=0, emboss=True, invert_checkbox=True)
                    attr_0E749 = '["' + str('Socket_1' + '"]') 
                    split_143A8.prop(bpy.context.view_layer.objects.active.modifiers['PCG_道路节点_v2'], attr_0E749, text='名称顺序连接', icon_value=0, emboss=True)
                    col_5B2CD.label(text='说明：名称顺序连接更加稳定', icon_value=0)
            else:
                col_C47DD = col_4B7E7.column(heading='', align=True)
                col_C47DD.alert = False
                col_C47DD.enabled = True
                col_C47DD.active = True
                col_C47DD.use_property_split = False
                col_C47DD.use_property_decorate = False
                col_C47DD.scale_x = 1.0
                col_C47DD.scale_y = 2.0
                col_C47DD.alignment = 'Expand'.upper()
                col_C47DD.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
                op = col_C47DD.operator('sna.my_generic_operator_3d66b', text='曲线道路', icon_value=4, emboss=True, depress=False)


class SNA_OT_My_Generic_Operator_Ca4F6(bpy.types.Operator):
    bl_idname = "sna.my_generic_operator_ca4f6"
    bl_label = "更新定位点"
    bl_description = ""
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        if bpy.app.version >= (3, 0, 0) and False:
            cls.poll_message_set()
        return not False

    def execute(self, context):
        bpy.context.view_layer.objects.active.modifiers['PCG_道路节点_v2']['Input_12'] = bpy.context.scene.sna_pcg_anchor_point
        bpy.context.view_layer.objects.active.modifiers['PCG_道路节点_v2'].show_viewport = True
        return {"FINISHED"}

    def invoke(self, context, event):
        return self.execute(context)


class SNA_OT_Uv_962Af(bpy.types.Operator):
    bl_idname = "sna.uv_962af"
    bl_label = "uv比例设置"
    bl_description = "使用贴图的高:宽"
    bl_options = {"REGISTER", "UNDO"}
    sna_uv: bpy.props.IntProperty(name='UV', description='', options={'HIDDEN'}, default=0, subtype='NONE')

    @classmethod
    def poll(cls, context):
        if bpy.app.version >= (3, 0, 0) and True:
            cls.poll_message_set('')
        return not False

    def execute(self, context):
        bpy.context.view_layer.objects.active.modifiers['PCG_道路节点_v2']['Socket_0'] = self.sna_uv
        bpy.context.view_layer.objects.active.modifiers['PCG_道路节点_v2'].show_viewport = True
        return {"FINISHED"}

    def invoke(self, context, event):
        return self.execute(context)


class SNA_OT_My_Generic_Operator_Ef8E8(bpy.types.Operator):
    bl_idname = "sna.my_generic_operator_ef8e8"
    bl_label = "删除曲线点"
    bl_description = "删除曲线点"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        if bpy.app.version >= (3, 0, 0) and True:
            cls.poll_message_set('')
        return not False

    def execute(self, context):
        bpy.ops.object.mode_set(mode='EDIT', toggle=False)
        bpy.ops.curve.select_all(action='SELECT')
        bpy.ops.curve.delete(type='VERT')
        bpy.ops.object.mode_set(mode='OBJECT', toggle=False)
        self.report({'INFO'}, message='删除曲线点成功！')
        return {"FINISHED"}

    def invoke(self, context, event):
        return self.execute(context)


class SNA_OT_My_Generic_Operator_3D66B(bpy.types.Operator):
    bl_idname = "sna.my_generic_operator_3d66b"
    bl_label = "加载曲线道路修改器"
    bl_description = ""
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        if bpy.app.version >= (3, 0, 0) and False:
            cls.poll_message_set()
        return not False

    def execute(self, context):
        bpy.context.view_layer.objects.active.modifiers.clear()
        bpy.ops.object.modifier_add(type='NODES')
        bpy.context.view_layer.objects.active.modifiers[0].name = 'PCG_道路节点_v2'
        bpy.context.view_layer.objects.active.modifiers['PCG_道路节点_v2'].node_group = bpy.data.node_groups['PCG_道路节点_v2']
        return {"FINISHED"}

    def invoke(self, context, event):
        if property_exists("bpy.data.node_groups['PCG_道路节点_v2']", globals(), locals()):
            pass
        else:
            before_data = list(bpy.data.node_groups)
            bpy.ops.wm.append(directory=bpy.path.abspath(os.path.join(os.path.dirname(__file__), 'assets', 'PCG_GN_WAY.blend')) + r'\NodeTree', filename='PCG_道路节点_v2', link=False)
            new_data = list(filter(lambda d: not d in before_data, list(bpy.data.node_groups)))
            appended_69CD7 = None if not new_data else new_data[0]
        return self.execute(context)


class SNA_OT_My_Generic_Operator_E343B(bpy.types.Operator):
    bl_idname = "sna.my_generic_operator_e343b"
    bl_label = "应用曲线道路修改器"
    bl_description = ""
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        if bpy.app.version >= (3, 0, 0) and False:
            cls.poll_message_set()
        return not False

    def execute(self, context):
        bpy.ops.object.duplicate_move()
        bpy.ops.object.convert()
        bpy.ops.object.transform_apply(location=False, rotation=True, scale=True, properties=False, isolate_users=False)
        return {"FINISHED"}

    def invoke(self, context, event):
        return context.window_manager.invoke_confirm(self, event)


def register():
    global _icons
    _icons = bpy.utils.previews.new()
    bpy.types.Scene.sna_pcg_anchor_point = bpy.props.PointerProperty(name='pcg_anchor_point', description='', type=bpy.types.Collection)
    bpy.utils.register_class(SNA_OT_My_Generic_Operator_07439)
    bpy.utils.register_class(SNA_PT_PCG__97FEF)
    bpy.utils.register_class(SNA_OT_My_Generic_Operator_Ca4F6)
    bpy.utils.register_class(SNA_OT_Uv_962Af)
    bpy.utils.register_class(SNA_OT_My_Generic_Operator_Ef8E8)
    bpy.utils.register_class(SNA_OT_My_Generic_Operator_3D66B)
    bpy.utils.register_class(SNA_OT_My_Generic_Operator_E343B)


def unregister():
    global _icons
    bpy.utils.previews.remove(_icons)
    wm = bpy.context.window_manager
    kc = wm.keyconfigs.addon
    for km, kmi in addon_keymaps.values():
        km.keymap_items.remove(kmi)
    addon_keymaps.clear()
    del bpy.types.Scene.sna_pcg_anchor_point
    bpy.utils.unregister_class(SNA_OT_My_Generic_Operator_07439)
    bpy.utils.unregister_class(SNA_PT_PCG__97FEF)
    bpy.utils.unregister_class(SNA_OT_My_Generic_Operator_Ca4F6)
    bpy.utils.unregister_class(SNA_OT_Uv_962Af)
    bpy.utils.unregister_class(SNA_OT_My_Generic_Operator_Ef8E8)
    bpy.utils.unregister_class(SNA_OT_My_Generic_Operator_3D66B)
    bpy.utils.unregister_class(SNA_OT_My_Generic_Operator_E343B)
