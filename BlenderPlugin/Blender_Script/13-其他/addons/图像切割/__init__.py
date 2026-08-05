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
    "name" : "Cut image",
    "author" : "QKK", 
    "description" : "切割图像",
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
from PIL import Image


addon_keymaps = {}
_icons = None
class SNA_PT_cut_image_A55BD(bpy.types.Panel):
    bl_label = '切割图像'
    bl_idname = 'SNA_PT_cut_image_A55BD'
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_context = ''
    bl_category = '图像处理'
    bl_order = 0
    bl_ui_units_x=0

    @classmethod
    def poll(cls, context):
        return not (False)

    def draw_header(self, context):
        layout = self.layout

    def draw(self, context):
        layout = self.layout
        col_AAD11 = layout.column(heading='', align=False)
        col_AAD11.alert = False
        col_AAD11.enabled = True
        col_AAD11.active = True
        col_AAD11.use_property_split = False
        col_AAD11.use_property_decorate = False
        col_AAD11.scale_x = 1.0
        col_AAD11.scale_y = 1.0
        col_AAD11.alignment = 'Expand'.upper()
        col_AAD11.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
        col_AAD11.prop(bpy.context.scene, 'sna_image_file_path', text='', icon_value=0, emboss=True)
        col_AAD11.prop(bpy.context.scene, 'sna_name', text='名称', icon_value=0, emboss=True)
        col_CB84F = col_AAD11.column(heading='', align=False)
        col_CB84F.alert = False
        col_CB84F.enabled = True
        col_CB84F.active = True
        col_CB84F.use_property_split = False
        col_CB84F.use_property_decorate = False
        col_CB84F.scale_x = 1.0
        col_CB84F.scale_y = 1.5
        col_CB84F.alignment = 'Expand'.upper()
        col_CB84F.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
        op = col_CB84F.operator('sna.my_generic_operator_35be5', text='切割图像', icon_value=0, emboss=True, depress=False)
        box_1A2FD = col_AAD11.box()
        box_1A2FD.alert = False
        box_1A2FD.enabled = True
        box_1A2FD.active = True
        box_1A2FD.use_property_split = False
        box_1A2FD.use_property_decorate = False
        box_1A2FD.alignment = 'Expand'.upper()
        box_1A2FD.scale_x = 1.0
        box_1A2FD.scale_y = 1.0
        if not True: box_1A2FD.operator_context = "EXEC_DEFAULT"
        col_12154 = box_1A2FD.column(heading='', align=True)
        col_12154.alert = False
        col_12154.enabled = True
        col_12154.active = True
        col_12154.use_property_split = False
        col_12154.use_property_decorate = False
        col_12154.scale_x = 1.0
        col_12154.scale_y = 1.0
        col_12154.alignment = 'Expand'.upper()
        col_12154.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
        col_12154.prop(bpy.context.scene, 'sna_splitsid', text='拆分' + '    ' + str(bpy.context.scene.sna_splitsid) + 'x' + str(bpy.context.scene.sna_splitsid), icon_value=0, emboss=True)
        col_12154.prop(bpy.context.scene, 'sna_indented', text='像素缩进', icon_value=0, emboss=True)
        row_5B745 = col_12154.row(heading='', align=True)
        row_5B745.alert = False
        row_5B745.enabled = True
        row_5B745.active = True
        row_5B745.use_property_split = False
        row_5B745.use_property_decorate = False
        row_5B745.scale_x = 1.0
        row_5B745.scale_y = 1.0
        row_5B745.alignment = 'Expand'.upper()
        row_5B745.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
        row_5B745.prop(bpy.context.scene, 'sna_size', text='保存尺寸', icon_value=0, emboss=True)


class SNA_OT_My_Generic_Operator_35Be5(bpy.types.Operator):
    bl_idname = "sna.my_generic_operator_35be5"
    bl_label = "切割图像"
    bl_description = ""
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        if bpy.app.version >= (3, 0, 0) and True:
            cls.poll_message_set('')
        return not False

    def execute(self, context):
        image_file_path = bpy.path.abspath(bpy.context.scene.sna_image_file_path)
        splitsID = bpy.context.scene.sna_splitsid
        Indented = bpy.context.scene.sna_indented
        SizeX = bpy.context.scene.sna_size[0]
        SizeY = bpy.context.scene.sna_size[1]
        name = bpy.context.scene.sna_name
        import os
        #splitsID = 4
        #Indented = 16
        #SizeX = 256
        #SizeY = 256
        #name = "ddd"
        # 打开图像
        img = Image.open(image_file_path)
        # 获取图像的宽度和高度
        width, height = img.size
        # 计算每个小图的宽度和高度
        tile_width = width // splitsID
        tile_height = height // splitsID
        # 获取原始文件夹路径
        original_folder = os.path.dirname(image_file_path)
        # 切割并保存图像
        for i in range(splitsID):
            for j in range(splitsID):
                # 计算每个小图的位置
                left = j * tile_width
                upper = i * tile_height
                right = left + tile_width
                lower = upper + tile_height
                # 内缩 16 像素
                left += Indented
                upper += Indented
                right -= Indented
                lower -= Indented
                # 确保边界不越界
                left = max(left, 0)
                upper = max(upper, 0)
                right = min(right, width)
                lower = min(lower, height)
                # 裁剪图像
                tile = img.crop((left, upper, right, lower))
                # 如果裁剪后的图像尺寸大于 0，则进行调整
                if tile.size[0] > 0 and tile.size[1] > 0:
                    # 调整图像尺寸
                    tile = tile.resize((SizeX, SizeY), Image.LANCZOS)            
                    # 保存图像
                    tile.save(os.path.join(original_folder, f"{i * 4 + j}_{name}.png"))
        return {"FINISHED"}

    def invoke(self, context, event):
        return self.execute(context)


def register():
    global _icons
    _icons = bpy.utils.previews.new()
    bpy.types.Scene.sna_image_file_path = bpy.props.StringProperty(name='image_file_path', description='', default='', subtype='FILE_PATH', maxlen=0)
    bpy.types.Scene.sna_splitsid = bpy.props.IntProperty(name='splitsID', description='', default=2, subtype='NONE', soft_min=2, soft_max=4)
    bpy.types.Scene.sna_indented = bpy.props.IntProperty(name='Indented', description='', default=8, subtype='PIXEL', soft_min=2, soft_max=32)
    bpy.types.Scene.sna_size = bpy.props.IntVectorProperty(name='Size', description='', size=2, default=(512, 512), subtype='XYZ', soft_min=128, soft_max=2048)
    bpy.types.Scene.sna_name = bpy.props.StringProperty(name='name', description='', default='', subtype='NONE', maxlen=0)
    bpy.utils.register_class(SNA_PT_cut_image_A55BD)
    bpy.utils.register_class(SNA_OT_My_Generic_Operator_35Be5)


def unregister():
    global _icons
    bpy.utils.previews.remove(_icons)
    wm = bpy.context.window_manager
    kc = wm.keyconfigs.addon
    for km, kmi in addon_keymaps.values():
        km.keymap_items.remove(kmi)
    addon_keymaps.clear()
    del bpy.types.Scene.sna_name
    del bpy.types.Scene.sna_size
    del bpy.types.Scene.sna_indented
    del bpy.types.Scene.sna_splitsid
    del bpy.types.Scene.sna_image_file_path
    bpy.utils.unregister_class(SNA_PT_cut_image_A55BD)
    bpy.utils.unregister_class(SNA_OT_My_Generic_Operator_35Be5)
