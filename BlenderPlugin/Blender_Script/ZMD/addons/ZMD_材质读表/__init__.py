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
    "name" : "ZMD_Mat_Excel",
    "author" : "QKK", 
    "description" : "",
    "blender" : (5, 2, 0),
    "version" : (1, 0, 0),
    "location" : "",
    "warning" : "",
    "doc_url": "", 
    "tracker_url": "", 
    "category" : "3D View" 
}


import bpy
import bpy.utils.previews
import openpyxl


addon_keymaps = {}
_icons = None
class SNA_PT_material_reading_table_16553(bpy.types.Panel):
    bl_label = '材质读表'
    bl_idname = 'SNA_PT_material_reading_table_16553'
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_context = ''
    bl_category = 'ZMD'
    bl_order = 0
    bl_ui_units_x=0

    @classmethod
    def poll(cls, context):
        return not (False)

    def draw_header(self, context):
        layout = self.layout

    def draw(self, context):
        layout = self.layout
        op = layout.operator('sna.read_operator_fb9c6', text='材质读表', icon_value=0, emboss=True, depress=False)
        layout.prop(bpy.context.scene, 'sna_zmd_excel_path', text='', icon_value=0, emboss=True)


class SNA_OT_Read_Operator_Fb9C6(bpy.types.Operator):
    bl_idname = "sna.read_operator_fb9c6"
    bl_label = "Read_Operator"
    bl_description = ""
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        if bpy.app.version >= (3, 0, 0) and True:
            cls.poll_message_set('')
        return not False

    def execute(self, context):
        file_path = bpy.path.abspath(bpy.context.scene.sna_zmd_excel_path)
        import os

        def Set_Shader(Mat,Shader_Name):
            #Shader_Name = 'ZMD_Lit_Two'
            Blender_Path = 'C:\\Blender_Shader\\ZMD_Lit_Two.blend\\Material\\'
            # 清理重名的旧材质，防止冲突
            Old_Mat = bpy.data.materials.get(Shader_Name)
            if Old_Mat:
                bpy.data.materials.remove(Old_Mat)
            # 追加外部材质并修正节点组引用
            bpy.ops.wm.append(directory=Blender_Path, filename=Shader_Name, link=False)
            New_Mat = bpy.data.materials.get(Shader_Name)
            Node_Name = New_Mat.node_tree.nodes['Shader'].node_tree.name
            if Node_Name != Shader_Name:
                New_Mat.node_tree.nodes['Shader'].node_tree = bpy.data.node_groups[Shader_Name]
                bpy.data.node_groups.remove(bpy.data.node_groups[Node_Name])
            # 创建载体
            bpy.ops.mesh.primitive_cone_add()
            obj = bpy.context.active_object
            mesh = obj.data
            bpy.ops.object.material_slot_add()
            obj.material_slots[0].material = New_Mat
            # 切换至材质编辑器，复制新材质的节点
            bpy.context.area.ui_type = 'ShaderNodeTree'
            bpy.ops.node.select_all(action='SELECT')
            bpy.ops.node.clipboard_copy()
            # 删除临时材质
            bpy.context.blend_data.materials.remove(material=New_Mat)
            # 清空原材质节点,将复制的节点粘贴到原材质中，并切回3D视图
            Mat.node_tree.nodes.clear()
            obj.material_slots[0].material = Mat
            bpy.context.area.ui_type = 'ShaderNodeTree'
            bpy.ops.node.select_all(action='SELECT')
            bpy.ops.node.clipboard_paste()
            bpy.context.area.ui_type = 'VIEW_3D'
            # 删除载体
            bpy.context.blend_data.objects.remove(object=obj)
            bpy.context.blend_data.meshes.remove(mesh=mesh)

        def Img_Space():
            # 直接遍历 Blender 里的所有图像文件
            for img in bpy.data.images:
                # 统一将A通道设置为 “通道打包”
                img.alpha_mode = 'CHANNEL_PACKED'
                # 直接使用原始名称进行字符串包含判断
                if ("_N." in img.name) or ("_NRO." in img.name) or ("_M." in img.name):
                    img.colorspace_settings.name = 'Non-Color'
                    print(f"贴图 [{img.name}] 已直接设置为: Non-Color")
                elif ("_D." in img.name) or ("_E." in img.name):
                    img.colorspace_settings.name = 'sRGB'
                    print(f"贴图 [{img.name}] 已直接设置为: sRGB")
        print('Start')
        # 加载Excel文件
        #file_path = 
        workbook = openpyxl.load_workbook(file_path,data_only=True) # data_only=True 获取单元格的值而非公式
        sheet = workbook.worksheets[0]
        # 添加 min_row=2 参数，直接从第二行开始读取，跳过第一行
        for row in sheet.iter_rows(min_row=2, max_col=10,values_only=True):
            # 如果第一列（索引为 0）为空，则跳过这一行
            if row[0] is not None:
                Mat = bpy.context.blend_data.materials.get(row[0])
                if Mat:
                    print('qkk')
                    Shader_Name = row[1]
                    Set_Shader(Mat,Shader_Name)
                    # 贴图名称列表
                    Img_Name_List = [row[2],row[3],row[4],row[5],row[6]]
                    for Img_Name in Img_Name_List:
                        # 导入贴图
                        img = bpy.data.images.get(str(Img_Name) + '.tga')
                        image_path = os.path.dirname(file_path ) + '\\' + str(Img_Name) + '.tga'
                        if os.path.exists(image_path) and img == None:
                            bpy.data.images.load(image_path)
                    Mat.node_tree.nodes['Color'].image = bpy.data.images.get(str(row[2]) + '.tga')
                    Mat.node_tree.nodes['NRO'].image = bpy.data.images.get(str(row[3]) + '.tga')
                    Mat.node_tree.nodes['本体法线'].image = bpy.data.images.get(str(row[4]) + '.tga')
                    Mat.node_tree.nodes['三通道_MASK'].image = bpy.data.images.get(str(row[5]) + '.tga')
                    Mat.node_tree.nodes['自发光'].image = bpy.data.images.get(str(row[6]) + '.tga')
        Img_Space()
        print('END')
        return {"FINISHED"}

    def invoke(self, context, event):
        return self.execute(context)


def register():
    global _icons
    _icons = bpy.utils.previews.new()
    bpy.types.Scene.sna_zmd_excel_path = bpy.props.StringProperty(name='zmd_excel_path', description='', default='', subtype='FILE_PATH', maxlen=0)
    bpy.utils.register_class(SNA_PT_material_reading_table_16553)
    bpy.utils.register_class(SNA_OT_Read_Operator_Fb9C6)


def unregister():
    global _icons
    bpy.utils.previews.remove(_icons)
    wm = bpy.context.window_manager
    kc = wm.keyconfigs.addon
    for km, kmi in addon_keymaps.values():
        km.keymap_items.remove(kmi)
    addon_keymaps.clear()
    del bpy.types.Scene.sna_zmd_excel_path
    bpy.utils.unregister_class(SNA_PT_material_reading_table_16553)
    bpy.utils.unregister_class(SNA_OT_Read_Operator_Fb9C6)
