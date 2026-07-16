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
    "name" : "环境配置_v2",
    "author" : "渠奎奎", 
    "description" : "环境配置_v2",
    "blender" : (4, 2, 0),
    "version" : (3, 0, 0),
    "location" : "",
    "warning" : "",
    "doc_url": "", 
    "tracker_url": "", 
    "category" : "A_工具插件" 
}


import bpy
import bpy.utils.previews
import os




def string_to_int(value):
    if value.isdigit():
        return int(value)
    return 0


def string_to_icon(value):
    if value in bpy.types.UILayout.bl_rna.functions["prop"].parameters["icon"].enum_items.keys():
        return bpy.types.UILayout.bl_rna.functions["prop"].parameters["icon"].enum_items[value].value
    return string_to_int(value)


def string_to_type(value, to_type, default):
    try:
        value = to_type(value)
    except:
        value = default
    return value


addon_keymaps = {}
_icons = None
node_tree = {'sna_hdr_iocn': [], }


def property_exists(prop_path, glob, loc):
    try:
        eval(prop_path, glob, loc)
        return True
    except:
        return False


_item_map = dict()


def make_enum_item(_id, name, descr, preview_id, uid):
    lookup = str(_id)+"\0"+str(name)+"\0"+str(descr)+"\0"+str(preview_id)+"\0"+str(uid)
    if not lookup in _item_map:
        _item_map[lookup] = (_id, name, descr, preview_id, uid)
    return _item_map[lookup]


def sna_update_sna_hdr_iocn_A4BA6(self, context):
    sna_updated_prop = self.sna_hdr_iocn
    print('开始切换HDR')
    for i_8FAE0 in range(2):
        print('开始解包HDR图片')
        bpy.context.blend_data.worlds['环境配置_HDR'].node_tree.nodes['HDR纹理'].image.unpack()
        print('更改图片引用路径')
        bpy.context.blend_data.worlds['环境配置_HDR'].node_tree.nodes['HDR纹理'].image.filepath = sna_updated_prop
        print('开始打包HDR图片')
        bpy.context.blend_data.worlds['环境配置_HDR'].node_tree.nodes['HDR纹理'].image.pack()
        if ('CYCLES' == bpy.context.scene.render.engine):
            bpy.context.scene.render.engine = 'CYCLES'
        print('完毕')


def sna_update_sna_hdr_asset_library_65F7F(self, context):
    sna_updated_prop = self.sna_hdr_asset_library
    node_tree['sna_hdr_iocn'] = []
    for i_FA335 in range(len([os.path.join(os.path.join(r'D:\Blender_HDR_Assets',), f) for f in os.listdir(os.path.join(r'D:\Blender_HDR_Assets',)) if os.path.isfile(os.path.join(os.path.join(r'D:\Blender_HDR_Assets',), f))])):
        node_tree['sna_hdr_iocn'].append([[os.path.join(os.path.join(r'D:\Blender_HDR_Assets',), f) for f in os.listdir(os.path.join(r'D:\Blender_HDR_Assets',)) if os.path.isfile(os.path.join(os.path.join(r'D:\Blender_HDR_Assets',), f))][i_FA335], [os.path.join(os.path.join(r'D:\Blender_HDR_Assets',), f) for f in os.listdir(os.path.join(r'D:\Blender_HDR_Assets',)) if os.path.isfile(os.path.join(os.path.join(r'D:\Blender_HDR_Assets',), f))][i_FA335], os.path.basename([os.path.join(os.path.join(r'D:\Blender_HDR_Assets',), f) for f in os.listdir(os.path.join(r'D:\Blender_HDR_Assets',)) if os.path.isfile(os.path.join(os.path.join(r'D:\Blender_HDR_Assets',), f))][i_FA335]), load_preview_icon([os.path.join(os.path.join(r'D:\Blender_HDR_Assets',), f) for f in os.listdir(os.path.join(r'D:\Blender_HDR_Assets',)) if os.path.isfile(os.path.join(os.path.join(r'D:\Blender_HDR_Assets',), f))][i_FA335])])


def load_preview_icon(path):
    global _icons
    if not path in _icons:
        if os.path.exists(path):
            _icons.load(path, path, "IMAGE")
        else:
            return 0
    return _icons[path].icon_id


handler_CE237 = []
class SNA_PT_environment_configuration_0D4F8(bpy.types.Panel):
    bl_label = '环境配置'
    bl_idname = 'SNA_PT_environment_configuration_0D4F8'
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_context = ''
    bl_category = '便捷功能'
    bl_order = 0
    bl_ui_units_x=0

    @classmethod
    def poll(cls, context):
        return not (False)

    def draw_header(self, context):
        layout = self.layout

    def draw(self, context):
        layout = self.layout
        split_9D88F = layout.split(factor=0.800000011920929, align=True)
        split_9D88F.alert = False
        split_9D88F.enabled = True
        split_9D88F.active = True
        split_9D88F.use_property_split = False
        split_9D88F.use_property_decorate = False
        split_9D88F.scale_x = 1.0
        split_9D88F.scale_y = 1.0
        split_9D88F.alignment = 'Expand'.upper()
        if not True: split_9D88F.operator_context = "EXEC_DEFAULT"
        split_2D7AD = split_9D88F.split(factor=0.800000011920929, align=True)
        split_2D7AD.alert = False
        split_2D7AD.enabled = True
        split_2D7AD.active = True
        split_2D7AD.use_property_split = False
        split_2D7AD.use_property_decorate = False
        split_2D7AD.scale_x = 1.0
        split_2D7AD.scale_y = 1.0
        split_2D7AD.alignment = 'Expand'.upper()
        if not True: split_2D7AD.operator_context = "EXEC_DEFAULT"
        col_A79B7 = split_2D7AD.column(heading='', align=True)
        col_A79B7.alert = False
        col_A79B7.enabled = property_exists("bpy.context.scene.camera.data", globals(), locals())
        col_A79B7.active = True
        col_A79B7.use_property_split = False
        col_A79B7.use_property_decorate = False
        col_A79B7.scale_x = 1.0
        col_A79B7.scale_y = 2.0
        col_A79B7.alignment = 'Expand'.upper()
        col_A79B7.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
        if property_exists("bpy.data.images['Render Result']", globals(), locals()):
            op = col_A79B7.operator('sna.my_generic_operator_1a77d', text='渲染', icon_value=string_to_icon('RENDER_STILL'), emboss=True, depress=False)
            op.sna_new_property = False
        else:
            op = col_A79B7.operator('render.render', text='渲染', icon_value=string_to_icon('RENDER_STILL'), emboss=True, depress=False)
            op.animation = False
        col_0A4A9 = split_2D7AD.column(heading='', align=True)
        col_0A4A9.alert = False
        col_0A4A9.enabled = True
        col_0A4A9.active = True
        col_0A4A9.use_property_split = False
        col_0A4A9.use_property_decorate = False
        col_0A4A9.scale_x = 1.0
        col_0A4A9.scale_y = 1.0
        col_0A4A9.alignment = 'Expand'.upper()
        col_0A4A9.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
        op = col_0A4A9.operator('render.opengl', text='', icon_value=string_to_icon('RESTRICT_VIEW_OFF'), emboss=True, depress=False)
        col_DA622 = col_0A4A9.column(heading='', align=True)
        col_DA622.alert = False
        col_DA622.enabled = (property_exists("bpy.context.scene.camera.data", globals(), locals()) and property_exists("bpy.data.images['Render Result']", globals(), locals()))
        col_DA622.active = True
        col_DA622.use_property_split = False
        col_DA622.use_property_decorate = False
        col_DA622.scale_x = 1.0
        col_DA622.scale_y = 1.0
        col_DA622.alignment = 'Expand'.upper()
        col_DA622.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
        op = col_DA622.operator('sna.my_generic_operator_1a77d', text='', icon_value=string_to_icon('RENDER_ANIMATION'), emboss=True, depress=False)
        op.sna_new_property = True
        col_F1913 = split_9D88F.column(heading='', align=True)
        col_F1913.alert = False
        col_F1913.enabled = True
        col_F1913.active = True
        col_F1913.use_property_split = False
        col_F1913.use_property_decorate = False
        col_F1913.scale_x = 1.0
        col_F1913.scale_y = 1.0
        col_F1913.alignment = 'Expand'.upper()
        col_F1913.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
        op = col_F1913.operator('render.view_show', text='', icon_value=string_to_icon('NODE_COMPOSITING'), emboss=True, depress=False)
        col_F1913.prop(bpy.context.scene, 'sna_hdr_render_slot', text='', icon_value=0, emboss=True)
        layout_function = layout
        sna_func_38E40(layout_function, )


class SNA_OT_My_Generic_Operator_1A77D(bpy.types.Operator):
    bl_idname = "sna.my_generic_operator_1a77d"
    bl_label = "渲染"
    bl_description = "渲染"
    bl_options = {"REGISTER", "UNDO"}
    sna_new_property: bpy.props.BoolProperty(name='动画渲染', description='', options={'HIDDEN'}, default=False)

    @classmethod
    def poll(cls, context):
        if bpy.app.version >= (3, 0, 0) and True:
            cls.poll_message_set('')
        return not False

    def execute(self, context):
        slot_id = int(string_to_type(bpy.context.scene.sna_hdr_render_slot[1:], float, 0) + -1.0)
        # 设置要创建的渲染槽编号
        render_slot_index = slot_id
        # 获取渲染结果图像
        image = bpy.data.images['Render Result']
        # 设置为活动渲染槽
        image.render_slots.active_index = render_slot_index
        bpy.ops.render.render('INVOKE_DEFAULT', animation=self.sna_new_property)
        return {"FINISHED"}

    def invoke(self, context, event):
        return self.execute(context)


class SNA_OT_My_Generic_Operator_Def26(bpy.types.Operator):
    bl_idname = "sna.my_generic_operator_def26"
    bl_label = "创建日光"
    bl_description = "创建日光"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        if bpy.app.version >= (3, 0, 0) and True:
            cls.poll_message_set('')
        return not False

    def execute(self, context):
        import math
        # 创建日光
        sun = bpy.data.lights.new(name='环境配置_日光', type='SUN')
        sun.color = (1.0, 1.0, 1.0)  # 设置颜色为白色
        sun.energy = 8  # 设置强度为6
        #sun.use_contact_shadow = True  # 开启接触阴影
        # 创建日光灯对象
        sun_obj = bpy.data.objects.new(name='环境配置_日光', object_data=sun)
        # 将日光灯对象添加到场景中
        bpy.context.collection.objects.link(sun_obj)
        # 设置日光灯对象的位置
        sun_obj.location = (0.0, 0.0, 0.0)
        # 设置日光灯对象的旋转
        sun_obj.rotation_euler = (math.radians(45), 0, math.radians(-45))
        # 选中日光灯对象
        bpy.context.view_layer.objects.active = sun_obj
        sun_obj.select_set(True)
        # 移出选中的物体
        # 获取场景集合
        uid = bpy.context.scene.collection.session_uid
        bpy.ops.object.move_to_collection(collection_uid=uid,is_new=False,new_collection_name='')
        self.report({'INFO'}, message='新增日光成功！')
        return {"FINISHED"}

    def invoke(self, context, event):
        return self.execute(context)


class SNA_OT_My_Generic_Operator_94Cb8(bpy.types.Operator):
    bl_idname = "sna.my_generic_operator_94cb8"
    bl_label = "清理日光"
    bl_description = "清理日光"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        if bpy.app.version >= (3, 0, 0) and True:
            cls.poll_message_set('')
        return not False

    def execute(self, context):
        bpy.context.blend_data.lights.remove(light=bpy.data.lights['环境配置_日光'], )
        self.report({'INFO'}, message='清理日光成功！')
        return {"FINISHED"}

    def invoke(self, context, event):
        return self.execute(context)


class SNA_OT_Hdr_D7B66(bpy.types.Operator):
    bl_idname = "sna.hdr_d7b66"
    bl_label = "加载HDR"
    bl_description = "加载HDR"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        if bpy.app.version >= (3, 0, 0) and True:
            cls.poll_message_set('')
        return not False

    def execute(self, context):
        print('开始加载World')
        before_data = list(bpy.data.worlds)
        bpy.ops.wm.append(directory=bpy.path.abspath(os.path.join(os.path.dirname(__file__), 'assets', 'HDR_Assets.blend')) + r'\World', filename='环境配置_HDR', link=False)
        new_data = list(filter(lambda d: not d in before_data, list(bpy.data.worlds)))
        appended_FB358 = None if not new_data else new_data[0]
        print('加载World成功')
        bpy.context.scene.world = bpy.data.worlds.get('环境配置_HDR')
        print('使用World成功')
        self.report({'INFO'}, message='加载HDR成功！')
        return {"FINISHED"}

    def invoke(self, context, event):
        return self.execute(context)


class SNA_OT_Hdr_343Ec(bpy.types.Operator):
    bl_idname = "sna.hdr_343ec"
    bl_label = "清理HDR"
    bl_description = "清理HDR"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        if bpy.app.version >= (3, 0, 0) and True:
            cls.poll_message_set('')
        return not False

    def execute(self, context):
        print('开始清理环境')
        bpy.context.blend_data.worlds.remove(world=bpy.data.worlds['环境配置_HDR'], )
        print('World清理成功')
        bpy.context.blend_data.images.remove(image=bpy.data.images['HDR.png'], )
        print('HDR图片清理成功')
        self.report({'INFO'}, message='清理HDR成功！')
        return {"FINISHED"}

    def invoke(self, context, event):
        return self.execute(context)


class SNA_OT_My_Generic_Operator_B64C6(bpy.types.Operator):
    bl_idname = "sna.my_generic_operator_b64c6"
    bl_label = "一键配置_环境"
    bl_description = "一键配置环境"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        if bpy.app.version >= (3, 0, 0) and True:
            cls.poll_message_set('')
        return not False

    def execute(self, context):
        # 色彩空间
        bpy.context.scene.view_settings.view_transform = 'ACES 2.0'
        # 渲染像素精度
        bpy.context.scene.render.filter_size = 0

        if (property_exists("bpy.data.objects['环境配置_日光']", globals(), locals()) and property_exists("bpy.data.lights['环境配置_日光']", globals(), locals())):
            pass
        else:
            bpy.ops.sna.my_generic_operator_def26()
        if property_exists("bpy.data.worlds['环境配置_HDR']", globals(), locals()):
            pass
        else:
            bpy.ops.sna.hdr_d7b66()
        return {"FINISHED"}

    def invoke(self, context, event):
        return self.execute(context)


class SNA_OT_My_Generic_Operator_3Dc96(bpy.types.Operator):
    bl_idname = "sna.my_generic_operator_3dc96"
    bl_label = "一键清理_环境"
    bl_description = "一键清理环境"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        if bpy.app.version >= (3, 0, 0) and True:
            cls.poll_message_set('')
        return not False

    def execute(self, context):
        if (property_exists("bpy.data.objects['环境配置_日光']", globals(), locals()) and property_exists("bpy.data.lights['环境配置_日光']", globals(), locals())):
            bpy.ops.sna.my_generic_operator_94cb8()
        if property_exists("bpy.data.worlds['环境配置_HDR']", globals(), locals()):
            bpy.ops.sna.hdr_343ec()
        return {"FINISHED"}

    def invoke(self, context, event):
        return self.execute(context)


class SNA_OT_Open_Hdr_Path_0029A(bpy.types.Operator):
    bl_idname = "sna.open_hdr_path_0029a"
    bl_label = "open_hdr_path"
    bl_description = "打开目录"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        if bpy.app.version >= (3, 0, 0) and True:
            cls.poll_message_set('')
        return not False

    def execute(self, context):
        if os.path.isdir(os.path.join(r'D:\Blender_HDR_Assets',)):
            pass
        else:
            if not os.path.exists(os.path.join(r'D:', '/Blender_HDR_Assets')):
                os.mkdir(os.path.join(r'D:', '/Blender_HDR_Assets'))
            self.report({'INFO'}, message='首次创建仓库成功！')
        hdr_path = os.path.join(r'D:\Blender_HDR_Assets',)
        os.system(f'explorer {hdr_path}')
        self.report({'INFO'}, message='打开仓库成功！')
        return {"FINISHED"}

    def invoke(self, context, event):
        return self.execute(context)


class SNA_OT_My_Generic_Operator_9Fe61(bpy.types.Operator):
    bl_idname = "sna.my_generic_operator_9fe61"
    bl_label = "定位物体"
    bl_description = "定位物体"
    bl_options = {"REGISTER", "UNDO"}
    sna_object_name: bpy.props.StringProperty(name='Object_name', description='', options={'HIDDEN'}, default='', subtype='NONE', maxlen=0)

    @classmethod
    def poll(cls, context):
        if bpy.app.version >= (3, 0, 0) and True:
            cls.poll_message_set('')
        return not False

    def execute(self, context):
        bpy.ops.object.select_all(action='DESELECT')
        bpy.context.view_layer.objects.active = bpy.data.objects[self.sna_object_name]
        bpy.ops.object.select_pattern(pattern=self.sna_object_name, case_sensitive=False, extend=False)
        self.report({'INFO'}, message='定位成功！')
        return {"FINISHED"}

    def invoke(self, context, event):
        return self.execute(context)


def sna_hdr_iocn_enum_items(self, context):
    enum_items = node_tree['sna_hdr_iocn']
    return [make_enum_item(item[0], item[1], item[2], item[3], i) for i, item in enumerate(enum_items)]


def sna_func_A203C(layout_function, ):
    box_1AF80 = layout_function.box()
    box_1AF80.alert = False
    box_1AF80.enabled = True
    box_1AF80.active = True
    box_1AF80.use_property_split = False
    box_1AF80.use_property_decorate = False
    box_1AF80.alignment = 'Expand'.upper()
    box_1AF80.scale_x = 1.0
    box_1AF80.scale_y = 1.0
    if not True: box_1AF80.operator_context = "EXEC_DEFAULT"
    col_33A08 = box_1AF80.column(heading='', align=False)
    col_33A08.alert = False
    col_33A08.enabled = True
    col_33A08.active = True
    col_33A08.use_property_split = False
    col_33A08.use_property_decorate = False
    col_33A08.scale_x = 1.0
    col_33A08.scale_y = 1.0
    col_33A08.alignment = 'Expand'.upper()
    col_33A08.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
    split_ECE54 = col_33A08.split(factor=0.75, align=True)
    split_ECE54.alert = False
    split_ECE54.enabled = True
    split_ECE54.active = True
    split_ECE54.use_property_split = False
    split_ECE54.use_property_decorate = False
    split_ECE54.scale_x = 1.0
    split_ECE54.scale_y = 2.0
    split_ECE54.alignment = 'Expand'.upper()
    if not True: split_ECE54.operator_context = "EXEC_DEFAULT"
    op = split_ECE54.operator('sna.my_generic_operator_b64c6', text='一键配置', icon_value=string_to_icon('TRIA_RIGHT'), emboss=True, depress=False)
    op = split_ECE54.operator('sna.my_generic_operator_3dc96', text='清理', icon_value=string_to_icon('PANEL_CLOSE'), emboss=True, depress=False)
    split_F74A5 = col_33A08.split(factor=0.5, align=True)
    split_F74A5.alert = False
    split_F74A5.enabled = True
    split_F74A5.active = True
    split_F74A5.use_property_split = False
    split_F74A5.use_property_decorate = False
    split_F74A5.scale_x = 1.0
    split_F74A5.scale_y = 1.2000000476837158
    split_F74A5.alignment = 'Expand'.upper()
    if not True: split_F74A5.operator_context = "EXEC_DEFAULT"
    if (property_exists("bpy.data.objects['环境配置_日光']", globals(), locals()) and property_exists("bpy.data.lights['环境配置_日光']", globals(), locals())):
        op = split_F74A5.operator('sna.my_generic_operator_94cb8', text='清理日光', icon_value=string_to_icon('CANCEL'), emboss=True, depress=False)
    else:
        op = split_F74A5.operator('sna.my_generic_operator_def26', text='创建日光', icon_value=string_to_icon('LIGHT_SUN'), emboss=True, depress=False)
    if property_exists("bpy.data.worlds['环境配置_HDR']", globals(), locals()):
        op = split_F74A5.operator('sna.hdr_343ec', text='清理HDR', icon_value=string_to_icon('CANCEL'), emboss=True, depress=False)
    else:
        op = split_F74A5.operator('sna.hdr_d7b66', text='加载HDR', icon_value=string_to_icon('WORLD'), emboss=True, depress=False)
    if (property_exists("bpy.data.objects['环境配置_日光']", globals(), locals()) and property_exists("bpy.data.lights['环境配置_日光']", globals(), locals())):
        box_463B5 = col_33A08.box()
        box_463B5.alert = False
        box_463B5.enabled = True
        box_463B5.active = True
        box_463B5.use_property_split = False
        box_463B5.use_property_decorate = False
        box_463B5.alignment = 'Expand'.upper()
        box_463B5.scale_x = 1.0
        box_463B5.scale_y = 1.0
        if not True: box_463B5.operator_context = "EXEC_DEFAULT"
        col_82373 = box_463B5.column(heading='', align=False)
        col_82373.alert = False
        col_82373.enabled = True
        col_82373.active = True
        col_82373.use_property_split = False
        col_82373.use_property_decorate = False
        col_82373.scale_x = 1.0
        col_82373.scale_y = 1.0
        col_82373.alignment = 'Expand'.upper()
        col_82373.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
        col_82373.label(text='日光配置：', icon_value=0)
        split_52561 = col_82373.split(factor=0.15000000596046448, align=True)
        split_52561.alert = False
        split_52561.enabled = True
        split_52561.active = True
        split_52561.use_property_split = False
        split_52561.use_property_decorate = False
        split_52561.scale_x = 1.0
        split_52561.scale_y = 1.0
        split_52561.alignment = 'Expand'.upper()
        if not True: split_52561.operator_context = "EXEC_DEFAULT"
        op = split_52561.operator('sna.my_generic_operator_9fe61', text='', icon_value=string_to_icon('LIGHT_SUN'), emboss=True, depress=False)
        op.sna_object_name = '环境配置_日光'
        split_9FC0B = split_52561.split(factor=0.800000011920929, align=True)
        split_9FC0B.alert = False
        split_9FC0B.enabled = True
        split_9FC0B.active = True
        split_9FC0B.use_property_split = False
        split_9FC0B.use_property_decorate = False
        split_9FC0B.scale_x = 1.0
        split_9FC0B.scale_y = 1.0
        split_9FC0B.alignment = 'Expand'.upper()
        if not True: split_9FC0B.operator_context = "EXEC_DEFAULT"
        split_9FC0B.prop(bpy.data.lights['环境配置_日光'], 'energy', text='强度', icon_value=0, emboss=True)
        split_9FC0B.prop(bpy.data.lights['环境配置_日光'], 'color', text='', icon_value=0, emboss=True)
        col_82373.prop(bpy.data.objects['环境配置_日光'], 'rotation_euler', text='', icon_value=0, emboss=True)
    if property_exists("bpy.data.worlds['环境配置_HDR']", globals(), locals()):
        box_66E61 = col_33A08.box()
        box_66E61.alert = False
        box_66E61.enabled = True
        box_66E61.active = True
        box_66E61.use_property_split = False
        box_66E61.use_property_decorate = False
        box_66E61.alignment = 'Expand'.upper()
        box_66E61.scale_x = 1.0
        box_66E61.scale_y = 1.0
        if not True: box_66E61.operator_context = "EXEC_DEFAULT"
        col_24DAE = box_66E61.column(heading='', align=False)
        col_24DAE.alert = False
        col_24DAE.enabled = True
        col_24DAE.active = True
        col_24DAE.use_property_split = False
        col_24DAE.use_property_decorate = False
        col_24DAE.scale_x = 1.0
        col_24DAE.scale_y = 1.0
        col_24DAE.alignment = 'Expand'.upper()
        col_24DAE.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
        col_24DAE.label(text='HDR配置：', icon_value=0)        
        col_24DAE.prop(bpy.data.worlds['环境配置_HDR'].node_tree.nodes['HDR强度'].outputs[0], 'default_value', text='强度', icon_value=0, emboss=True)
        col_24DAE.prop(bpy.data.worlds['环境配置_HDR'].node_tree.nodes['HDR旋转'].inputs[0], 'default_value', text='旋转', icon_value=0, emboss=True)
        row_D3236 = col_24DAE.row(heading='', align=True)
        row_D3236.alert = False
        row_D3236.enabled = True
        row_D3236.active = True
        row_D3236.use_property_split = False
        row_D3236.use_property_decorate = False
        row_D3236.scale_x = 1.0
        row_D3236.scale_y = 1.0
        row_D3236.alignment = 'Expand'.upper()
        row_D3236.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
        row_D3236.prop(bpy.data.worlds['环境配置_HDR'].node_tree.nodes['分界'].inputs[1], 'default_value', text='分界', icon_value=0, emboss=True)
        row_D3236.prop(bpy.data.worlds['环境配置_HDR'].node_tree.nodes['Gamma'].inputs[1], 'default_value', text='伽马', icon_value=0, emboss=True)
        row_25089 = col_24DAE.row(heading='', align=True)
        row_25089.alert = False
        row_25089.enabled = True
        row_25089.active = True
        row_25089.use_property_split = False
        row_25089.use_property_decorate = False
        row_25089.scale_x = 1.0
        row_25089.scale_y = 1.0
        row_25089.alignment = 'Expand'.upper()
        row_25089.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
        row_25089.prop(bpy.context.scene.render, 'film_transparent', text='透明', icon_value=0, emboss=True)
        row_25089.prop(bpy.context.scene, 'sna_hdr_asset_library', text='HDR', icon_value=0, emboss=True)
        row_25089.prop(bpy.data.images['HDR.png'].colorspace_settings, 'name', text='', icon_value=0, emboss=True)
        if bpy.context.scene.sna_hdr_asset_library:
            box_2749A = col_24DAE.box()
            box_2749A.alert = False
            box_2749A.enabled = True
            box_2749A.active = True
            box_2749A.use_property_split = False
            box_2749A.use_property_decorate = False
            box_2749A.alignment = 'Expand'.upper()
            box_2749A.scale_x = 1.0
            box_2749A.scale_y = 1.0
            if not True: box_2749A.operator_context = "EXEC_DEFAULT"
            col_7340A = box_2749A.column(heading='', align=False)
            col_7340A.alert = False
            col_7340A.enabled = True
            col_7340A.active = True
            col_7340A.use_property_split = False
            col_7340A.use_property_decorate = False
            col_7340A.scale_x = 1.0
            col_7340A.scale_y = 1.0
            col_7340A.alignment = 'Expand'.upper()
            col_7340A.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
            if (os.path.isdir(os.path.join(r'D:\Blender_HDR_Assets',)) and bpy.context.scene.sna_hdr_asset_library):
                grid_5CB37 = col_7340A.grid_flow(columns=4, row_major=True, even_columns=False, even_rows=False, align=True)
                grid_5CB37.enabled = True
                grid_5CB37.active = True
                grid_5CB37.use_property_split = False
                grid_5CB37.use_property_decorate = False
                grid_5CB37.alignment = 'Expand'.upper()
                grid_5CB37.scale_x = 1.0
                grid_5CB37.scale_y = 1.0
                if not True: grid_5CB37.operator_context = "EXEC_DEFAULT"
                grid_5CB37.template_icon_view(bpy.context.scene, 'sna_hdr_iocn', show_labels=False, scale=8.0, scale_popup=6.0)
            op = col_7340A.operator('sna.open_hdr_path_0029a', text='打开HDR仓库', icon_value=string_to_icon('IMAGE_RGB_ALPHA'), emboss=True, depress=False)


class SNA_OT_My_Generic_Operator_9C885(bpy.types.Operator):
    bl_idname = "sna.my_generic_operator_9c885"
    bl_label = "创建相机"
    bl_description = "创建相机"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        if bpy.app.version >= (3, 0, 0) and True:
            cls.poll_message_set('')
        return not False

    def execute(self, context):
        Camera_name = '相机'
        # 创建一个新的相机对象
        new_camera = bpy.data.cameras.new(name=Camera_name)
        # 创建相机对象
        camera_obj = bpy.data.objects.new(name=Camera_name, object_data=new_camera)
        # 将相机对象添加到场景中
        bpy.context.collection.objects.link(camera_obj)
        # 将新相机设置为活动相机
        bpy.context.scene.camera = camera_obj
        prev_context = bpy.context.area.type
        bpy.context.area.type = 'VIEW_3D'
        bpy.ops.view3d.camera_to_view('INVOKE_DEFAULT', )
        bpy.context.area.type = prev_context
        return {"FINISHED"}

    def invoke(self, context, event):
        return self.execute(context)


def sna_func_2277C():
    bpy.ops.ui.eyedropper_depth('INVOKE_DEFAULT', prop_data_path='scene.camera.data.dof.focus_distance')
    if handler_CE237:
        bpy.types.SpaceView3D.draw_handler_remove(handler_CE237[0], 'WINDOW')
        handler_CE237.pop(0)
        for a in bpy.context.screen.areas: a.tag_redraw()


class SNA_OT_Focal_Distance_04929(bpy.types.Operator):
    bl_idname = "sna.focal_distance_04929"
    bl_label = "Focal_distance"
    bl_description = "吸取焦点"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        if bpy.app.version >= (3, 0, 0) and True:
            cls.poll_message_set('')
        return not False

    def execute(self, context):
        handler_CE237.append(bpy.types.SpaceView3D.draw_handler_add(sna_func_2277C, (), 'WINDOW', 'POST_PIXEL'))
        for a in bpy.context.screen.areas: a.tag_redraw()
        return {"FINISHED"}

    def invoke(self, context, event):
        return self.execute(context)


def sna_func_EDB3F(layout_function, ):
    box_CA7FC = layout_function.box()
    box_CA7FC.alert = False
    box_CA7FC.enabled = True
    box_CA7FC.active = True
    box_CA7FC.use_property_split = False
    box_CA7FC.use_property_decorate = False
    box_CA7FC.alignment = 'Expand'.upper()
    box_CA7FC.scale_x = 1.0
    box_CA7FC.scale_y = 1.0
    if not True: box_CA7FC.operator_context = "EXEC_DEFAULT"
    col_5DE67 = box_CA7FC.column(heading='', align=False)
    col_5DE67.alert = False
    col_5DE67.enabled = True
    col_5DE67.active = True
    col_5DE67.use_property_split = False
    col_5DE67.use_property_decorate = False
    col_5DE67.scale_x = 1.0
    col_5DE67.scale_y = 1.0
    col_5DE67.alignment = 'Expand'.upper()
    col_5DE67.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
    col_2A0AE = col_5DE67.column(heading='', align=False)
    col_2A0AE.alert = False
    col_2A0AE.enabled = (not property_exists("bpy.context.scene.camera.data", globals(), locals()))
    col_2A0AE.active = True
    col_2A0AE.use_property_split = False
    col_2A0AE.use_property_decorate = False
    col_2A0AE.scale_x = 1.0
    col_2A0AE.scale_y = 2.0
    col_2A0AE.alignment = 'Expand'.upper()
    col_2A0AE.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
    op = col_2A0AE.operator('sna.my_generic_operator_9c885', text='创建相机', icon_value=string_to_icon('OUTLINER_DATA_CAMERA'), emboss=True, depress=False)
    box_E8BB1 = col_5DE67.box()
    box_E8BB1.alert = False
    box_E8BB1.enabled = True
    box_E8BB1.active = True
    box_E8BB1.use_property_split = False
    box_E8BB1.use_property_decorate = False
    box_E8BB1.alignment = 'Expand'.upper()
    box_E8BB1.scale_x = 1.0
    box_E8BB1.scale_y = 1.100000023841858
    if not True: box_E8BB1.operator_context = "EXEC_DEFAULT"
    col_1CA41 = box_E8BB1.column(heading='', align=False)
    col_1CA41.alert = False
    col_1CA41.enabled = True
    col_1CA41.active = True
    col_1CA41.use_property_split = False
    col_1CA41.use_property_decorate = False
    col_1CA41.scale_x = 1.0
    col_1CA41.scale_y = 1.0
    col_1CA41.alignment = 'Expand'.upper()
    col_1CA41.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
    split_E93D7 = col_1CA41.split(factor=0.5, align=True)
    split_E93D7.alert = False
    split_E93D7.enabled = True
    split_E93D7.active = True
    split_E93D7.use_property_split = False
    split_E93D7.use_property_decorate = False
    split_E93D7.scale_x = 1.0
    split_E93D7.scale_y = 1.0
    split_E93D7.alignment = 'Expand'.upper()
    if not True: split_E93D7.operator_context = "EXEC_DEFAULT"
    split_E93D7.prop(bpy.context.scene, 'camera', text='', icon_value=string_to_icon('OUTLINER_DATA_CAMERA'), emboss=True)
    if property_exists("bpy.context.scene.camera.data", globals(), locals()):
        split_E93D7.prop(bpy.context.scene.camera, 'name', text='', icon_value=0, emboss=True)
    if property_exists("bpy.context.scene.camera.data", globals(), locals()):
        col_ACE24 = col_1CA41.column(heading='', align=False)
        col_ACE24.alert = False
        col_ACE24.enabled = True
        col_ACE24.active = True
        col_ACE24.use_property_split = False
        col_ACE24.use_property_decorate = False
        col_ACE24.scale_x = 1.0
        col_ACE24.scale_y = 1.0
        col_ACE24.alignment = 'Expand'.upper()
        col_ACE24.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
        split_7ACC2 = col_ACE24.split(factor=0.30000001192092896, align=True)
        split_7ACC2.alert = False
        split_7ACC2.enabled = True
        split_7ACC2.active = True
        split_7ACC2.use_property_split = False
        split_7ACC2.use_property_decorate = False
        split_7ACC2.scale_x = 1.0
        split_7ACC2.scale_y = 1.0
        split_7ACC2.alignment = 'Expand'.upper()
        if not True: split_7ACC2.operator_context = "EXEC_DEFAULT"
        split_7ACC2.prop(bpy.context.scene.camera.data, 'type', text='', icon_value=0, emboss=True)
        split_7ACC2.separator(factor=1.0)
        if (bpy.context.scene.camera.data.type == 'PERSP'):
            split_75E4A = col_ACE24.split(factor=0.5, align=True)
            split_75E4A.alert = False
            split_75E4A.enabled = True
            split_75E4A.active = True
            split_75E4A.use_property_split = False
            split_75E4A.use_property_decorate = False
            split_75E4A.scale_x = 1.0
            split_75E4A.scale_y = 1.0
            split_75E4A.alignment = 'Expand'.upper()
            if not True: split_75E4A.operator_context = "EXEC_DEFAULT"
            split_35776 = split_75E4A.split(factor=0.20000000298023224, align=True)
            split_35776.alert = False
            split_35776.enabled = True
            split_35776.active = True
            split_35776.use_property_split = False
            split_35776.use_property_decorate = False
            split_35776.scale_x = 1.0
            split_35776.scale_y = 1.0
            split_35776.alignment = 'Expand'.upper()
            if not True: split_35776.operator_context = "EXEC_DEFAULT"
            op = split_35776.operator('sna.my_generic_operator_9fe61', text='', icon_value=string_to_icon('OUTLINER_DATA_CAMERA'), emboss=True, depress=False)
            op.sna_object_name = bpy.context.scene.camera.name
            if (bpy.context.scene.camera.data.lens_unit == 'FOV'):
                split_35776.prop(bpy.context.scene.camera.data, 'angle', text='', icon_value=0, emboss=True)
            else:
                split_35776.prop(bpy.context.scene.camera.data, 'lens', text='', icon_value=0, emboss=True)
            split_75E4A.prop(bpy.context.scene.camera.data, 'lens_unit', text='', icon_value=0, emboss=True)
        if (bpy.context.scene.camera.data.type == 'ORTHO'):
            split_CA625 = col_ACE24.split(factor=0.5, align=True)
            split_CA625.alert = False
            split_CA625.enabled = True
            split_CA625.active = True
            split_CA625.use_property_split = False
            split_CA625.use_property_decorate = False
            split_CA625.scale_x = 1.0
            split_CA625.scale_y = 1.0
            split_CA625.alignment = 'Expand'.upper()
            if not True: split_CA625.operator_context = "EXEC_DEFAULT"
            split_CA625.prop(bpy.context.scene.camera.data, 'ortho_scale', text='推进', icon_value=0, emboss=True)
            split_CA625.prop(bpy.context.scene, 'sna_orthogona', text='速度', icon_value=0, emboss=True)
        split_61DA8 = col_ACE24.split(factor=0.5, align=True)
        split_61DA8.alert = False
        split_61DA8.enabled = True
        split_61DA8.active = True
        split_61DA8.use_property_split = False
        split_61DA8.use_property_decorate = False
        split_61DA8.scale_x = 1.0
        split_61DA8.scale_y = 1.0
        split_61DA8.alignment = 'Expand'.upper()
        if not True: split_61DA8.operator_context = "EXEC_DEFAULT"
        split_61DA8.prop(bpy.context.scene.camera.data, 'clip_start', text='起点', icon_value=0, emboss=True)
        split_61DA8.prop(bpy.context.scene.camera.data, 'clip_end', text='终点', icon_value=0, emboss=True)
        col_E43F1 = col_ACE24.column(heading='', align=False)
        col_E43F1.alert = False
        col_E43F1.enabled = True
        col_E43F1.active = True
        col_E43F1.use_property_split = False
        col_E43F1.use_property_decorate = False
        col_E43F1.scale_x = 1.0
        col_E43F1.scale_y = 1.0
        col_E43F1.alignment = 'Expand'.upper()
        col_E43F1.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
        col_E43F1.prop(bpy.context.scene.camera.data.dof, 'use_dof', text='景深', icon_value=0, emboss=True)
        if bpy.context.scene.camera.data.dof.use_dof:
            box_CFDEE = col_E43F1.box()
            box_CFDEE.alert = False
            box_CFDEE.enabled = True
            box_CFDEE.active = True
            box_CFDEE.use_property_split = False
            box_CFDEE.use_property_decorate = False
            box_CFDEE.alignment = 'Expand'.upper()
            box_CFDEE.scale_x = 1.0
            box_CFDEE.scale_y = 1.0
            if not True: box_CFDEE.operator_context = "EXEC_DEFAULT"
            col_7F6E4 = box_CFDEE.column(heading='', align=False)
            col_7F6E4.alert = False
            col_7F6E4.enabled = True
            col_7F6E4.active = True
            col_7F6E4.use_property_split = False
            col_7F6E4.use_property_decorate = False
            col_7F6E4.scale_x = 1.0
            col_7F6E4.scale_y = 1.0
            col_7F6E4.alignment = 'Expand'.upper()
            col_7F6E4.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
            split_4FDE8 = col_7F6E4.split(factor=0.5, align=True)
            split_4FDE8.alert = False
            split_4FDE8.enabled = True
            split_4FDE8.active = True
            split_4FDE8.use_property_split = False
            split_4FDE8.use_property_decorate = False
            split_4FDE8.scale_x = 1.0
            split_4FDE8.scale_y = 1.0
            split_4FDE8.alignment = 'Expand'.upper()
            if not True: split_4FDE8.operator_context = "EXEC_DEFAULT"
            split_4FDE8.prop(bpy.context.scene.camera.data.dof, 'aperture_fstop', text='光圈', icon_value=0, emboss=True)
            split_4FDE8.label(text='模糊强度：' + str(int(bpy.context.scene.camera.data.lens / bpy.context.scene.camera.data.dof.aperture_fstop)), icon_value=0)
            split_9982D = col_7F6E4.split(factor=0.5, align=True)
            split_9982D.alert = False
            split_9982D.enabled = (None == bpy.context.scene.camera.data.dof.focus_object)
            split_9982D.active = True
            split_9982D.use_property_split = False
            split_9982D.use_property_decorate = False
            split_9982D.scale_x = 1.0
            split_9982D.scale_y = 1.0
            split_9982D.alignment = 'Expand'.upper()
            if not True: split_9982D.operator_context = "EXEC_DEFAULT"
            split_560E9 = split_9982D.split(factor=0.800000011920929, align=True)
            split_560E9.alert = False
            split_560E9.enabled = True
            split_560E9.active = True
            split_560E9.use_property_split = False
            split_560E9.use_property_decorate = False
            split_560E9.scale_x = 1.0
            split_560E9.scale_y = 1.0
            split_560E9.alignment = 'Expand'.upper()
            if not True: split_560E9.operator_context = "EXEC_DEFAULT"
            split_560E9.prop(bpy.context.scene.camera.data.dof, 'focus_distance', text='焦点', icon_value=0, emboss=True)
            op = split_560E9.operator('sna.focal_distance_04929', text='', icon_value=string_to_icon('EYEDROPPER'), emboss=True, depress=False)
            split_55813 = split_9982D.split(factor=0.5, align=True)
            split_55813.alert = False
            split_55813.enabled = True
            split_55813.active = True
            split_55813.use_property_split = False
            split_55813.use_property_decorate = False
            split_55813.scale_x = 1.0
            split_55813.scale_y = 1.0
            split_55813.alignment = 'Expand'.upper()
            if not True: split_55813.operator_context = "EXEC_DEFAULT"
            split_55813.prop(bpy.context.scene.camera.data, 'show_limits', text='辅助', icon_value=0, emboss=True)
            if bpy.context.scene.camera.data.show_limits:
                split_55813.prop(bpy.context.scene.camera.data, 'display_size', text='', icon_value=0, emboss=True)
            col_7F6E4.prop(bpy.context.scene.camera.data.dof, 'focus_object', text='焦点物体', icon_value=0, emboss=True)
        split_B436F = col_ACE24.split(factor=0.33000001311302185, align=True)
        split_B436F.alert = False
        split_B436F.enabled = True
        split_B436F.active = True
        split_B436F.use_property_split = False
        split_B436F.use_property_decorate = False
        split_B436F.scale_x = 1.0
        split_B436F.scale_y = 1.0
        split_B436F.alignment = 'Expand'.upper()
        if not True: split_B436F.operator_context = "EXEC_DEFAULT"
        split_B436F.prop(bpy.data.cameras[bpy.context.scene.camera.data.name], 'show_passepartout', text='边框', icon_value=0, emboss=True)
        split_B436F.prop(bpy.data.cameras[bpy.context.scene.camera.data.name], 'passepartout_alpha', text='', icon_value=0, emboss=True)


class SNA_OT_My_Generic_Operator_360C5(bpy.types.Operator):
    bl_idname = "sna.my_generic_operator_360c5"
    bl_label = "正交镜头缩放"
    bl_description = ""
    bl_options = {"REGISTER", "UNDO"}
    sna_new_property: bpy.props.FloatProperty(name='速率', description='', options={'HIDDEN'}, default=0.0, subtype='NONE', unit='NONE', step=3, precision=6)

    @classmethod
    def poll(cls, context):
        if bpy.app.version >= (3, 0, 0) and True:
            cls.poll_message_set('')
        return not False

    def execute(self, context):
        if (property_exists("bpy.context.scene.camera.data", globals(), locals()) and (bpy.context.scene.camera.data.type == 'ORTHO')):
            bpy.context.scene.camera.data.ortho_scale = float(bpy.context.scene.camera.data.ortho_scale + float(self.sna_new_property * bpy.context.scene.sna_orthogona))
        return {"FINISHED"}

    def invoke(self, context, event):
        return self.execute(context)


def sna_func_09AB0(layout_function, ):
    box_8AC00 = layout_function.box()
    box_8AC00.alert = False
    box_8AC00.enabled = True
    box_8AC00.active = True
    box_8AC00.use_property_split = False
    box_8AC00.use_property_decorate = False
    box_8AC00.alignment = 'Expand'.upper()
    box_8AC00.scale_x = 1.0
    box_8AC00.scale_y = 1.100000023841858
    if not True: box_8AC00.operator_context = "EXEC_DEFAULT"
    col_41AF2 = box_8AC00.column(heading='', align=True)
    col_41AF2.alert = False
    col_41AF2.enabled = True
    col_41AF2.active = True
    col_41AF2.use_property_split = False
    col_41AF2.use_property_decorate = False
    col_41AF2.scale_x = 1.0
    col_41AF2.scale_y = 1.0
    col_41AF2.alignment = 'Expand'.upper()
    col_41AF2.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
    box_920E9 = col_41AF2.box()
    box_920E9.alert = False
    box_920E9.enabled = True
    box_920E9.active = True
    box_920E9.use_property_split = False
    box_920E9.use_property_decorate = False
    box_920E9.alignment = 'Expand'.upper()
    box_920E9.scale_x = 1.0
    box_920E9.scale_y = 1.0
    if not True: box_920E9.operator_context = "EXEC_DEFAULT"
    col_0BB61 = box_920E9.column(heading='', align=False)
    col_0BB61.alert = False
    col_0BB61.enabled = True
    col_0BB61.active = True
    col_0BB61.use_property_split = False
    col_0BB61.use_property_decorate = False
    col_0BB61.scale_x = 1.0
    col_0BB61.scale_y = 1.0
    col_0BB61.alignment = 'Expand'.upper()
    col_0BB61.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
    col_0BB61.label(text='引擎：', icon_value=0)
    col_0BB61.prop(bpy.context.scene.render, 'engine', text='', icon_value=string_to_icon('SCENE'), emboss=True)
    if (bpy.context.scene.render.engine == 'BLENDER_EEVEE_NEXT'):
        col_65FFD = col_0BB61.column(heading='', align=False)
        col_65FFD.alert = False
        col_65FFD.enabled = True
        col_65FFD.active = True
        col_65FFD.use_property_split = False
        col_65FFD.use_property_decorate = False
        col_65FFD.scale_x = 1.0
        col_65FFD.scale_y = 1.0
        col_65FFD.alignment = 'Expand'.upper()
        col_65FFD.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
        split_07652 = col_65FFD.split(factor=0.5, align=True)
        split_07652.alert = False
        split_07652.enabled = True
        split_07652.active = True
        split_07652.use_property_split = False
        split_07652.use_property_decorate = False
        split_07652.scale_x = 1.0
        split_07652.scale_y = 1.2000000476837158
        split_07652.alignment = 'Expand'.upper()
        if not True: split_07652.operator_context = "EXEC_DEFAULT"
        split_07652.prop(bpy.context.scene.eevee, 'taa_render_samples', text='渲染采样', icon_value=0, emboss=True)
        split_07652.prop(bpy.context.scene.eevee, 'taa_samples', text='视图采样', icon_value=0, emboss=True)
        row_F7D3F = col_65FFD.row(heading='', align=False)
        row_F7D3F.alert = False
        row_F7D3F.enabled = True
        row_F7D3F.active = True
        row_F7D3F.use_property_split = False
        row_F7D3F.use_property_decorate = False
        row_F7D3F.scale_x = 1.0
        row_F7D3F.scale_y = 1.0
        row_F7D3F.alignment = 'Expand'.upper()
        row_F7D3F.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
        row_F7D3F.prop(bpy.context.scene.eevee, 'use_raytracing', text='光线追踪', icon_value=0, emboss=True)
    if (bpy.context.scene.render.engine == 'CYCLES'):
        col_4029D = col_0BB61.column(heading='', align=False)
        col_4029D.alert = False
        col_4029D.enabled = True
        col_4029D.active = True
        col_4029D.use_property_split = False
        col_4029D.use_property_decorate = False
        col_4029D.scale_x = 1.0
        col_4029D.scale_y = 1.0
        col_4029D.alignment = 'Expand'.upper()
        col_4029D.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
        col_4029D.prop(bpy.context.scene.cycles, 'device', text='设备', icon_value=0, emboss=True)
        split_008E7 = col_4029D.split(factor=0.5, align=False)
        split_008E7.alert = False
        split_008E7.enabled = True
        split_008E7.active = True
        split_008E7.use_property_split = False
        split_008E7.use_property_decorate = False
        split_008E7.scale_x = 1.0
        split_008E7.scale_y = 1.0
        split_008E7.alignment = 'Expand'.upper()
        if not True: split_008E7.operator_context = "EXEC_DEFAULT"
        split_008E7.prop(bpy.context.scene.cycles, 'preview_samples', text='视图采样', icon_value=0, emboss=True)
        split_A511C = split_008E7.split(factor=0.5, align=False)
        split_A511C.alert = False
        split_A511C.enabled = True
        split_A511C.active = True
        split_A511C.use_property_split = False
        split_A511C.use_property_decorate = False
        split_A511C.scale_x = 1.0
        split_A511C.scale_y = 1.0
        split_A511C.alignment = 'Expand'.upper()
        if not True: split_A511C.operator_context = "EXEC_DEFAULT"
        split_A511C.prop(bpy.context.scene.cycles, 'use_preview_denoising', text='降噪', icon_value=0, emboss=True)
        split_A511C.prop(bpy.context.scene.cycles, 'preview_denoising_use_gpu', text='GPU', icon_value=0, emboss=True)
        split_7F2C3 = col_4029D.split(factor=0.5, align=False)
        split_7F2C3.alert = False
        split_7F2C3.enabled = True
        split_7F2C3.active = True
        split_7F2C3.use_property_split = False
        split_7F2C3.use_property_decorate = False
        split_7F2C3.scale_x = 1.0
        split_7F2C3.scale_y = 1.0
        split_7F2C3.alignment = 'Expand'.upper()
        if not True: split_7F2C3.operator_context = "EXEC_DEFAULT"
        split_7F2C3.prop(bpy.context.scene.cycles, 'samples', text='渲染采样', icon_value=0, emboss=True)
        split_8788A = split_7F2C3.split(factor=0.5, align=True)
        split_8788A.alert = False
        split_8788A.enabled = True
        split_8788A.active = True
        split_8788A.use_property_split = False
        split_8788A.use_property_decorate = False
        split_8788A.scale_x = 1.0
        split_8788A.scale_y = 1.0
        split_8788A.alignment = 'Expand'.upper()
        if not True: split_8788A.operator_context = "EXEC_DEFAULT"
        split_8788A.prop(bpy.context.scene.cycles, 'use_denoising', text='降噪', icon_value=0, emboss=True)
        split_8788A.prop(bpy.context.scene.cycles, 'denoising_use_gpu', text='GPU', icon_value=0, emboss=True)
        col_4029D.prop(bpy.context.scene, 'sna_optical_switch', text='光程配置', icon_value=0, emboss=True)
        if bpy.context.scene.sna_optical_switch:
            box_42929 = col_4029D.box()
            box_42929.alert = False
            box_42929.enabled = True
            box_42929.active = True
            box_42929.use_property_split = False
            box_42929.use_property_decorate = False
            box_42929.alignment = 'Expand'.upper()
            box_42929.scale_x = 1.0
            box_42929.scale_y = 1.0
            if not True: box_42929.operator_context = "EXEC_DEFAULT"
            col_76CA5 = box_42929.column(heading='', align=True)
            col_76CA5.alert = False
            col_76CA5.enabled = True
            col_76CA5.active = True
            col_76CA5.use_property_split = False
            col_76CA5.use_property_decorate = False
            col_76CA5.scale_x = 1.0
            col_76CA5.scale_y = 0.8999999761581421
            col_76CA5.alignment = 'Expand'.upper()
            col_76CA5.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
            col_76CA5.prop(bpy.context.scene.cycles, 'max_bounces', text='总数', icon_value=0, emboss=True)
            col_76CA5.separator(factor=0.5)
            col_76CA5.prop(bpy.context.scene.cycles, 'diffuse_bounces', text='漫射', icon_value=0, emboss=True)
            col_76CA5.prop(bpy.context.scene.cycles, 'glossy_bounces', text='光泽', icon_value=0, emboss=True)
            col_76CA5.prop(bpy.context.scene.cycles, 'transmission_bounces', text='透射', icon_value=0, emboss=True)
            col_76CA5.prop(bpy.context.scene.cycles, 'volume_bounces', text='体积', icon_value=0, emboss=True)
            col_76CA5.prop(bpy.context.scene.cycles, 'transparent_max_bounces', text='透明', icon_value=0, emboss=True)
    box_91E84 = col_41AF2.box()
    box_91E84.alert = False
    box_91E84.enabled = True
    box_91E84.active = True
    box_91E84.use_property_split = False
    box_91E84.use_property_decorate = False
    box_91E84.alignment = 'Expand'.upper()
    box_91E84.scale_x = 1.0
    box_91E84.scale_y = 1.100000023841858
    if not True: box_91E84.operator_context = "EXEC_DEFAULT"
    col_2D3D4 = box_91E84.column(heading='', align=True)
    col_2D3D4.alert = False
    col_2D3D4.enabled = True
    col_2D3D4.active = True
    col_2D3D4.use_property_split = False
    col_2D3D4.use_property_decorate = False
    col_2D3D4.scale_x = 1.0
    col_2D3D4.scale_y = 1.0
    col_2D3D4.alignment = 'Expand'.upper()
    col_2D3D4.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
    col_2D3D4.label(text='尺寸：', icon_value=0)
    split_C989C = col_2D3D4.split(factor=0.5, align=True)
    split_C989C.alert = False
    split_C989C.enabled = True
    split_C989C.active = True
    split_C989C.use_property_split = False
    split_C989C.use_property_decorate = False
    split_C989C.scale_x = 1.0
    split_C989C.scale_y = 1.0
    split_C989C.alignment = 'Expand'.upper()
    if not True: split_C989C.operator_context = "EXEC_DEFAULT"
    split_C989C.prop(bpy.context.scene.render, 'resolution_x', text='', icon_value=0, emboss=True)
    split_C989C.prop(bpy.context.scene.render, 'resolution_y', text='', icon_value=0, emboss=True)
    col_2D3D4.prop(bpy.context.scene.render, 'resolution_percentage', text='', icon_value=0, emboss=True)
    box_0CDAB = col_41AF2.box()
    box_0CDAB.alert = False
    box_0CDAB.enabled = True
    box_0CDAB.active = True
    box_0CDAB.use_property_split = False
    box_0CDAB.use_property_decorate = False
    box_0CDAB.alignment = 'Expand'.upper()
    box_0CDAB.scale_x = 1.0
    box_0CDAB.scale_y = 1.0
    if not True: box_0CDAB.operator_context = "EXEC_DEFAULT"
    col_8D0F2 = box_0CDAB.column(heading='', align=True)
    col_8D0F2.alert = False
    col_8D0F2.enabled = True
    col_8D0F2.active = True
    col_8D0F2.use_property_split = False
    col_8D0F2.use_property_decorate = False
    col_8D0F2.scale_x = 1.0
    col_8D0F2.scale_y = 1.0
    col_8D0F2.alignment = 'Expand'.upper()
    col_8D0F2.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
    col_8D0F2.label(text='动画：', icon_value=0)
    split_90BF2 = col_8D0F2.split(factor=0.5, align=True)
    split_90BF2.alert = False
    split_90BF2.enabled = True
    split_90BF2.active = True
    split_90BF2.use_property_split = False
    split_90BF2.use_property_decorate = False
    split_90BF2.scale_x = 1.0
    split_90BF2.scale_y = 1.0
    split_90BF2.alignment = 'Expand'.upper()
    if not True: split_90BF2.operator_context = "EXEC_DEFAULT"
    split_90BF2.prop(bpy.context.scene.render, 'fps', text='帧率', icon_value=0, emboss=True)
    split_8A33B = split_90BF2.split(factor=0.5, align=True)
    split_8A33B.alert = False
    split_8A33B.enabled = True
    split_8A33B.active = True
    split_8A33B.use_property_split = False
    split_8A33B.use_property_decorate = False
    split_8A33B.scale_x = 1.0
    split_8A33B.scale_y = 1.0
    split_8A33B.alignment = 'Expand'.upper()
    if not True: split_8A33B.operator_context = "EXEC_DEFAULT"
    split_8A33B.prop(bpy.context.scene, 'frame_start', text='', icon_value=0, emboss=True)
    split_8A33B.prop(bpy.context.scene, 'frame_end', text='', icon_value=0, emboss=True)
    box_4E54D = col_41AF2.box()
    box_4E54D.alert = False
    box_4E54D.enabled = True
    box_4E54D.active = True
    box_4E54D.use_property_split = False
    box_4E54D.use_property_decorate = False
    box_4E54D.alignment = 'Expand'.upper()
    box_4E54D.scale_x = 1.0
    box_4E54D.scale_y = 1.0
    if not True: box_4E54D.operator_context = "EXEC_DEFAULT"
    col_F006A = box_4E54D.column(heading='', align=True)
    col_F006A.alert = False
    col_F006A.enabled = True
    col_F006A.active = True
    col_F006A.use_property_split = False
    col_F006A.use_property_decorate = False
    col_F006A.scale_x = 1.0
    col_F006A.scale_y = 1.0
    col_F006A.alignment = 'Expand'.upper()
    col_F006A.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
    col_F006A.label(text='通用：', icon_value=0)
    split_40ACC = col_F006A.split(factor=0.5, align=True)
    split_40ACC.alert = False
    split_40ACC.enabled = True
    split_40ACC.active = True
    split_40ACC.use_property_split = False
    split_40ACC.use_property_decorate = False
    split_40ACC.scale_x = 1.0
    split_40ACC.scale_y = 1.0
    split_40ACC.alignment = 'Expand'.upper()
    if not True: split_40ACC.operator_context = "EXEC_DEFAULT"
    split_B57CC = split_40ACC.split(factor=0.5, align=True)
    split_B57CC.alert = False
    split_B57CC.enabled = True
    split_B57CC.active = True
    split_B57CC.use_property_split = False
    split_B57CC.use_property_decorate = False
    split_B57CC.scale_x = 1.0
    split_B57CC.scale_y = 1.0
    split_B57CC.alignment = 'Expand'.upper()
    if not True: split_B57CC.operator_context = "EXEC_DEFAULT"
    split_B57CC.prop(bpy.context.scene.view_settings, 'view_transform', text='', icon_value=0, emboss=True)
    split_B57CC.prop(bpy.context.scene.view_settings, 'look', text='', icon_value=0, emboss=True)
    split_40ACC.prop(bpy.context.scene.view_settings, 'exposure', text='曝光', icon_value=0, emboss=True)
    row_B458F = col_F006A.row(heading='', align=True)
    row_B458F.alert = False
    row_B458F.enabled = True
    row_B458F.active = True
    row_B458F.use_property_split = False
    row_B458F.use_property_decorate = False
    row_B458F.scale_x = 1.0
    row_B458F.scale_y = 1.0
    row_B458F.alignment = 'Expand'.upper()
    row_B458F.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
    row_B458F.prop(bpy.context.scene.render, 'use_motion_blur', text='动态模糊', icon_value=0, emboss=True)
    row_B458F.prop(bpy.context.scene.render, 'film_transparent', text='背景透明', icon_value=0, emboss=True)


def sna_func_38E40(layout_function, ):
    layout_function.separator(factor=0.5)
    row_38BF7 = layout_function.row(heading='', align=True)
    row_38BF7.alert = False
    row_38BF7.enabled = True
    row_38BF7.active = True
    row_38BF7.use_property_split = False
    row_38BF7.use_property_decorate = False
    row_38BF7.scale_x = 1.0
    row_38BF7.scale_y = 1.5
    row_38BF7.alignment = 'Expand'.upper()
    row_38BF7.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
    row_38BF7.prop(bpy.context.scene, 'sna_class_switch', text=bpy.context.scene.sna_class_switch, icon_value=0, emboss=True, expand=True)
    if (bpy.context.scene.sna_class_switch == '日光'):
        layout_function = layout_function
        sna_func_A203C(layout_function, )
    if (bpy.context.scene.sna_class_switch == '相机'):
        layout_function = layout_function
        sna_func_EDB3F(layout_function, )
    if (bpy.context.scene.sna_class_switch == '配置'):
        layout_function = layout_function
        sna_func_09AB0(layout_function, )


def register():
    global _icons
    _icons = bpy.utils.previews.new()
    bpy.types.Scene.sna_hdr_asset_library = bpy.props.BoolProperty(name='hdr_asset_library', description='', default=False, update=sna_update_sna_hdr_asset_library_65F7F)
    bpy.types.Scene.sna_hdr_render_slot = bpy.props.EnumProperty(name='hdr_render_slot', description='', items=[('槽1', '槽1', '', 0, 0), ('槽2', '槽2', '', 0, 1), ('槽3', '槽3', '', 0, 2), ('槽4', '槽4', '', 0, 3), ('槽5', '槽5', '', 0, 4), ('槽6', '槽6', '', 0, 5), ('槽7', '槽7', '', 0, 6), ('槽8', '槽8', '', 0, 7)])
    bpy.types.Scene.sna_hdr_iocn = bpy.props.EnumProperty(name='hdr_iocn', description='', items=sna_hdr_iocn_enum_items, update=sna_update_sna_hdr_iocn_A4BA6)
    bpy.types.Scene.sna_class_switch = bpy.props.EnumProperty(name='class_switch', description='', items=[('日光', '日光', '', 'LIGHT_SUN', 0), ('相机', '相机', '', 'CAMERA_DATA', 1), ('配置', '配置', '', 'OPTIONS', 2)])
    bpy.types.Scene.sna_optical_switch = bpy.props.BoolProperty(name='optical_switch', description='', default=False)
    bpy.types.Scene.sna_orthogona = bpy.props.FloatProperty(name='orthogona', description='', default=1.0, subtype='NONE', unit='NONE', soft_min=0.0, soft_max=5.0, step=1, precision=2)
    bpy.utils.register_class(SNA_PT_environment_configuration_0D4F8)
    bpy.utils.register_class(SNA_OT_My_Generic_Operator_1A77D)
    bpy.utils.register_class(SNA_OT_My_Generic_Operator_Def26)
    bpy.utils.register_class(SNA_OT_My_Generic_Operator_94Cb8)
    bpy.utils.register_class(SNA_OT_Hdr_D7B66)
    bpy.utils.register_class(SNA_OT_Hdr_343Ec)
    bpy.utils.register_class(SNA_OT_My_Generic_Operator_B64C6)
    bpy.utils.register_class(SNA_OT_My_Generic_Operator_3Dc96)
    bpy.utils.register_class(SNA_OT_Open_Hdr_Path_0029A)
    bpy.utils.register_class(SNA_OT_My_Generic_Operator_9Fe61)
    bpy.utils.register_class(SNA_OT_My_Generic_Operator_9C885)
    bpy.utils.register_class(SNA_OT_Focal_Distance_04929)
    bpy.utils.register_class(SNA_OT_My_Generic_Operator_360C5)
    kc = bpy.context.window_manager.keyconfigs.addon
    km = kc.keymaps.new(name='3D View', space_type='VIEW_3D')
    kmi = km.keymap_items.new('wm.call_panel', 'W', 'PRESS',
        ctrl=True, alt=False, shift=False, repeat=False)
    kmi.properties.name = 'SNA_PT_environment_configuration_0D4F8'
    kmi.properties.keep_open = True
    addon_keymaps['4DE6C'] = (km, kmi)
    kc = bpy.context.window_manager.keyconfigs.addon
    km = kc.keymaps.new(name='3D View', space_type='VIEW_3D')
    kmi = km.keymap_items.new('sna.my_generic_operator_360c5', 'WHEELDOWNMOUSE', 'ANY',
        ctrl=True, alt=False, shift=False, repeat=False)
    kmi.properties.sna_new_property = 1.0
    addon_keymaps['3A288'] = (km, kmi)
    kc = bpy.context.window_manager.keyconfigs.addon
    km = kc.keymaps.new(name='3D View', space_type='VIEW_3D')
    kmi = km.keymap_items.new('sna.my_generic_operator_360c5', 'WHEELUPMOUSE', 'ANY',
        ctrl=True, alt=False, shift=False, repeat=False)
    kmi.properties.sna_new_property = -1.0
    addon_keymaps['EC1A5'] = (km, kmi)


def unregister():
    global _icons
    bpy.utils.previews.remove(_icons)
    wm = bpy.context.window_manager
    kc = wm.keyconfigs.addon
    for km, kmi in addon_keymaps.values():
        km.keymap_items.remove(kmi)
    addon_keymaps.clear()
    del bpy.types.Scene.sna_orthogona
    del bpy.types.Scene.sna_optical_switch
    del bpy.types.Scene.sna_class_switch
    del bpy.types.Scene.sna_hdr_iocn
    del bpy.types.Scene.sna_hdr_render_slot
    del bpy.types.Scene.sna_hdr_asset_library
    bpy.utils.unregister_class(SNA_PT_environment_configuration_0D4F8)
    bpy.utils.unregister_class(SNA_OT_My_Generic_Operator_1A77D)
    bpy.utils.unregister_class(SNA_OT_My_Generic_Operator_Def26)
    bpy.utils.unregister_class(SNA_OT_My_Generic_Operator_94Cb8)
    bpy.utils.unregister_class(SNA_OT_Hdr_D7B66)
    bpy.utils.unregister_class(SNA_OT_Hdr_343Ec)
    bpy.utils.unregister_class(SNA_OT_My_Generic_Operator_B64C6)
    bpy.utils.unregister_class(SNA_OT_My_Generic_Operator_3Dc96)
    bpy.utils.unregister_class(SNA_OT_Open_Hdr_Path_0029A)
    bpy.utils.unregister_class(SNA_OT_My_Generic_Operator_9Fe61)
    bpy.utils.unregister_class(SNA_OT_My_Generic_Operator_9C885)
    bpy.utils.unregister_class(SNA_OT_Focal_Distance_04929)
    if handler_CE237:
        bpy.types.SpaceView3D.draw_handler_remove(handler_CE237[0], 'WINDOW')
        handler_CE237.pop(0)
    bpy.utils.unregister_class(SNA_OT_My_Generic_Operator_360C5)
