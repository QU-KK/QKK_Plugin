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
    "name" : "PBR_Mat_Merge",
    "author" : "QKK", 
    "description" : "PBR材质合并",
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
import os


addon_keymaps = {}
_icons = None


def property_exists(prop_path, glob, loc):
    try:
        eval(prop_path, glob, loc)
        return True
    except:
        return False


class SNA_PT_PBR_4AF85(bpy.types.Panel):
    bl_label = 'PBR材质合并'
    bl_idname = 'SNA_PT_PBR_4AF85'
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_context = ''
    bl_category = '远景工具'
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
        col_862AB = layout.column(heading='', align=False)
        col_862AB.alert = False
        col_862AB.enabled = True
        col_862AB.active = True
        col_862AB.use_property_split = False
        col_862AB.use_property_decorate = False
        col_862AB.scale_x = 1.0
        col_862AB.scale_y = 1.0
        col_862AB.alignment = 'Expand'.upper()
        col_862AB.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
        col_F579F = col_862AB.column(heading='', align=False)
        col_F579F.alert = False
        col_F579F.enabled = True
        col_F579F.active = True
        col_F579F.use_property_split = False
        col_F579F.use_property_decorate = False
        col_F579F.scale_x = 1.0
        col_F579F.scale_y = 1.0
        col_F579F.alignment = 'Expand'.upper()
        col_F579F.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
        col_F579F.prop(bpy.context.scene, 'sna_mat_merge_path', text='路径', icon_value=0, emboss=True)
        col_F579F.prop(bpy.context.scene, 'sna_mat_merge_name', text='名称', icon_value=0, emboss=True)
        split_BF47D = col_862AB.split(factor=0.8500000238418579, align=True)
        split_BF47D.alert = False
        split_BF47D.enabled = True
        split_BF47D.active = True
        split_BF47D.use_property_split = False
        split_BF47D.use_property_decorate = False
        split_BF47D.scale_x = 1.0
        split_BF47D.scale_y = 1.0
        split_BF47D.alignment = 'Expand'.upper()
        if not True: split_BF47D.operator_context = "EXEC_DEFAULT"
        op = split_BF47D.operator('sna.my_generic_operator_72e40', text='打开目录', icon_value=0, emboss=True, depress=False)
        op.sna_open_path = bpy.path.abspath(bpy.context.scene.sna_mat_merge_path)
        op = split_BF47D.operator('sna.my_generic_operator_72e40', text='', icon_value=752, emboss=True, depress=False)
        op.sna_open_path = os.path.dirname(bpy.path.abspath(os.path.join(os.path.dirname(__file__), 'assets', 'Bake Wrangler 1.6.1_CN.zip')))
        col_862AB.separator(factor=2.0)
        split_7C5CF = col_862AB.split(factor=0.699999988079071, align=True)
        split_7C5CF.alert = False
        split_7C5CF.enabled = True
        split_7C5CF.active = True
        split_7C5CF.use_property_split = False
        split_7C5CF.use_property_decorate = False
        split_7C5CF.scale_x = 1.0
        split_7C5CF.scale_y = 2.0
        split_7C5CF.alignment = 'Expand'.upper()
        if not True: split_7C5CF.operator_context = "EXEC_DEFAULT"
        col_9E858 = split_7C5CF.column(heading='', align=True)
        col_9E858.alert = False
        col_9E858.enabled = (((1 == len(bpy.context.view_layer.objects.selected)) and (2 == len(bpy.context.view_layer.objects.active.data.uv_layers))) if property_exists("bpy.context.view_layer.objects.active.data.uv_layers", globals(), locals()) else False)
        col_9E858.active = True
        col_9E858.use_property_split = False
        col_9E858.use_property_decorate = False
        col_9E858.scale_x = 1.0
        col_9E858.scale_y = 1.0
        col_9E858.alignment = 'Expand'.upper()
        col_9E858.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
        op = col_9E858.operator('sna.my_generic_operator_e1d11', text='开始合并', icon_value=73, emboss=True, depress=False)
        op = split_7C5CF.operator('bake_wrangler.bake_stop', text='中断', icon_value=0, emboss=True, depress=False)
        op.tree = 'QKK_PBR材质合并'
        op.node = '开始烘焙'
        box_9CA1F = col_862AB.box()
        box_9CA1F.alert = False
        box_9CA1F.enabled = True
        box_9CA1F.active = True
        box_9CA1F.use_property_split = False
        box_9CA1F.use_property_decorate = False
        box_9CA1F.alignment = 'Expand'.upper()
        box_9CA1F.scale_x = 1.0
        box_9CA1F.scale_y = 1.0
        if not True: box_9CA1F.operator_context = "EXEC_DEFAULT"
        col_1A144 = box_9CA1F.column(heading='', align=True)
        col_1A144.alert = False
        col_1A144.enabled = True
        col_1A144.active = True
        col_1A144.use_property_split = False
        col_1A144.use_property_decorate = False
        col_1A144.scale_x = 1.0
        col_1A144.scale_y = 1.0
        col_1A144.alignment = 'Expand'.upper()
        col_1A144.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
        split_DB393 = col_1A144.split(factor=0.5, align=True)
        split_DB393.alert = False
        split_DB393.enabled = True
        split_DB393.active = True
        split_DB393.use_property_split = False
        split_DB393.use_property_decorate = False
        split_DB393.scale_x = 1.0
        split_DB393.scale_y = 1.0
        split_DB393.alignment = 'Expand'.upper()
        if not True: split_DB393.operator_context = "EXEC_DEFAULT"
        split_DB393.prop(bpy.context.scene, 'sna_mat_merge_pixel', text='尺寸', icon_value=0, emboss=True)
        split_DB393.prop(bpy.context.scene, 'sna_mat_merge_img_size', text='格式', icon_value=0, emboss=True)
        split_A4CD0 = col_1A144.split(factor=0.5, align=True)
        split_A4CD0.alert = False
        split_A4CD0.enabled = True
        split_A4CD0.active = True
        split_A4CD0.use_property_split = False
        split_A4CD0.use_property_decorate = False
        split_A4CD0.scale_x = 1.0
        split_A4CD0.scale_y = 1.0
        split_A4CD0.alignment = 'Expand'.upper()
        if not True: split_A4CD0.operator_context = "EXEC_DEFAULT"
        split_A4CD0.prop(bpy.context.scene, 'sna_mat_merge_saml', text='采样', icon_value=0, emboss=True)
        split_A4CD0.prop(bpy.context.scene, 'sna_mat_merge_distance', text='包裹', icon_value=0, emboss=True)
        col_1A144.prop(bpy.context.scene, 'sna_mat_merge_invert_roughness', text='反转粗糙度', icon_value=0, emboss=True)


class SNA_OT_My_Generic_Operator_E1D11(bpy.types.Operator):
    bl_idname = "sna.my_generic_operator_e1d11"
    bl_label = "开始合并"
    bl_description = "选中模型数量=1，UV数量=2"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        if bpy.app.version >= (3, 0, 0) and True:
            cls.poll_message_set('')
        return not False

    def execute(self, context):
        if property_exists("bpy.data.node_groups['QKK_PBR材质合并']", globals(), locals()):
            pass
        else:
            before_data = list(bpy.data.node_groups)
            bpy.ops.wm.append(directory=os.path.join(os.path.dirname(__file__), 'assets', 'asset.blend') + r'\NodeTree', filename='QKK_PBR材质合并', link=False)
            new_data = list(filter(lambda d: not d in before_data, list(bpy.data.node_groups)))
            appended_38D85 = None if not new_data else new_data[0]
            bpy.context.blend_data.node_groups['QKK_PBR材质合并'].use_fake_user = True
        bpy.data.node_groups['QKK_PBR材质合并'].nodes['保存路径'].inputs[0].disp_path = bpy.context.scene.sna_mat_merge_path
        bpy.data.node_groups['QKK_PBR材质合并'].nodes['保存路径'].inputs[0].img_name = bpy.context.scene.sna_mat_merge_name
        bpy.data.node_groups['QKK_PBR材质合并'].nodes['网格设置'].ray_dist = bpy.context.scene.sna_mat_merge_distance
        bpy.data.node_groups['QKK_PBR材质合并'].nodes['通道设置'].res_bake_x = bpy.context.scene.sna_mat_merge_pixel
        bpy.data.node_groups['QKK_PBR材质合并'].nodes['通道设置'].res_bake_y = bpy.context.scene.sna_mat_merge_pixel
        bpy.data.node_groups['QKK_PBR材质合并'].nodes['输出设置A'].img_xres = bpy.context.scene.sna_mat_merge_pixel
        bpy.data.node_groups['QKK_PBR材质合并'].nodes['输出设置A'].img_yres = bpy.context.scene.sna_mat_merge_pixel
        bpy.data.node_groups['QKK_PBR材质合并'].nodes['输出设置B'].img_xres = bpy.context.scene.sna_mat_merge_pixel
        bpy.data.node_groups['QKK_PBR材质合并'].nodes['输出设置B'].img_yres = bpy.context.scene.sna_mat_merge_pixel
        bpy.data.node_groups['QKK_PBR材质合并'].nodes['输出设置A'].img_type = bpy.context.scene.sna_mat_merge_img_size
        bpy.data.node_groups['QKK_PBR材质合并'].nodes['输出设置B'].img_type = bpy.context.scene.sna_mat_merge_img_size
        bpy.data.node_groups['QKK_PBR材质合并'].nodes['采样设置'].bake_samples = bpy.context.scene.sna_mat_merge_saml
        bpy.data.node_groups['QKK_PBR材质合并'].nodes['反转粗糙度'].inputs[0].value_fac = (1.0 if bpy.context.scene.sna_mat_merge_invert_roughness else 0.0)
        for i_9AFC5 in range(2):
            bpy.data.node_groups['QKK_PBR材质合并'].nodes['烘焙目标'].inputs[int(i_9AFC5 + 1.0)].value = bpy.context.view_layer.objects.active
            bpy.data.node_groups['QKK_PBR材质合并'].nodes['烘焙目标'].inputs[int(i_9AFC5 + 1.0)].pick_uv = True
            bpy.data.node_groups['QKK_PBR材质合并'].nodes['烘焙目标'].inputs[int(i_9AFC5 + 1.0)].uv_map = bpy.context.view_layer.objects.active.data.uv_layers[int(1.0 - i_9AFC5)].name
        bpy.ops.bake_wrangler.bake_pass(tree='QKK_PBR材质合并', node='开始烘焙')
        return {"FINISHED"}

    def invoke(self, context, event):
        return self.execute(context)


class SNA_OT_My_Generic_Operator_72E40(bpy.types.Operator):
    bl_idname = "sna.my_generic_operator_72e40"
    bl_label = "打开目录"
    bl_description = "打开目录"
    bl_options = {"REGISTER", "UNDO"}
    sna_open_path: bpy.props.StringProperty(name='open_path', description='', options={'HIDDEN'}, default='', subtype='NONE', maxlen=0)

    @classmethod
    def poll(cls, context):
        if bpy.app.version >= (3, 0, 0) and True:
            cls.poll_message_set('')
        return not False

    def execute(self, context):
        folder_path = self.sna_open_path
        os.startfile(folder_path) if os.name == 'nt' else os.system(f'open "{folder_path}"' if os.uname().sysname == 'Darwin' else f'xdg-open "{folder_path}"')
        return {"FINISHED"}

    def invoke(self, context, event):
        return self.execute(context)


def register():
    global _icons
    _icons = bpy.utils.previews.new()
    bpy.types.Scene.sna_mat_merge_path = bpy.props.StringProperty(name='mat_merge_path', description='保存路径', default='', subtype='DIR_PATH', maxlen=0)
    bpy.types.Scene.sna_mat_merge_name = bpy.props.StringProperty(name='mat_merge_name', description='名称', default='', subtype='NONE', maxlen=0)
    bpy.types.Scene.sna_mat_merge_pixel = bpy.props.IntProperty(name='mat_merge_pixel', description='', default=1024, subtype='PIXEL', soft_min=256, soft_max=8192)
    bpy.types.Scene.sna_mat_merge_distance = bpy.props.FloatProperty(name='mat_merge_distance', description='', default=0.009999999776482582, subtype='DISTANCE', unit='NONE', min=0.0, soft_max=1.0, step=1, precision=2)
    bpy.types.Scene.sna_mat_merge_img_size = bpy.props.EnumProperty(name='mat_merge_img_size', description='', items=[('TARGA', 'TARGA', 'Tga', 0, 0), ('PNG', 'PNG', 'Png', 0, 1)])
    bpy.types.Scene.sna_mat_merge_saml = bpy.props.IntProperty(name='mat_merge_saml', description='', default=128, subtype='NONE', soft_min=16, soft_max=1024)
    bpy.types.Scene.sna_mat_merge_invert_roughness = bpy.props.BoolProperty(name='mat_merge_invert_roughness', description='', default=False)
    bpy.utils.register_class(SNA_PT_PBR_4AF85)
    bpy.utils.register_class(SNA_OT_My_Generic_Operator_E1D11)
    bpy.utils.register_class(SNA_OT_My_Generic_Operator_72E40)


def unregister():
    global _icons
    bpy.utils.previews.remove(_icons)
    wm = bpy.context.window_manager
    kc = wm.keyconfigs.addon
    for km, kmi in addon_keymaps.values():
        km.keymap_items.remove(kmi)
    addon_keymaps.clear()
    del bpy.types.Scene.sna_mat_merge_invert_roughness
    del bpy.types.Scene.sna_mat_merge_saml
    del bpy.types.Scene.sna_mat_merge_img_size
    del bpy.types.Scene.sna_mat_merge_distance
    del bpy.types.Scene.sna_mat_merge_pixel
    del bpy.types.Scene.sna_mat_merge_name
    del bpy.types.Scene.sna_mat_merge_path
    bpy.utils.unregister_class(SNA_PT_PBR_4AF85)
    bpy.utils.unregister_class(SNA_OT_My_Generic_Operator_E1D11)
    bpy.utils.unregister_class(SNA_OT_My_Generic_Operator_72E40)
