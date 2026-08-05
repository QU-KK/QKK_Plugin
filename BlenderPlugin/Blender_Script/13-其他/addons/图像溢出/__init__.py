bl_info = {
    "name" : "贴图溢出合并",
    "author" : "渠奎奎", 
    "description" : "",
    "blender" : (3, 5, 0),
    "version" : (3, 5, 0),
    "location" : "",
    "waring" : "",
    "doc_url": "", 
    "tracker_url": "", 
    "category" : "A_工具插件" 
}


import bpy
import bpy.utils.previews

import os
import os
import os
import os
import os
import os
import os
import os
import os
from PIL import Image
import os
import os
import os
import os
import os
from PIL import Image, ImageOps
import os
import os
import os
import os
import os
import os
import os
import os
import os
import os
import os
import os
import os
import os
import os
import os
import os
import os
import os
import os
import os
import os
import os
import os
import os
import os
import os
import os
import os
import os
import os
import os
import os
import os
import os
import os
import os
import os
import os
import os
import os
import os
import os
import os
import os
import os
import os
import os
import os
import os
import os


def string_to_int(value):
    if value.isdigit():
        return int(value)
    return 0

def string_to_icon(value):
    if value in bpy.types.UILayout.bl_rna.functions["prop"].parameters["icon"].enum_items.keys():
        return bpy.types.UILayout.bl_rna.functions["prop"].parameters["icon"].enum_items[value].value
    return string_to_int(value)
    
def icon_to_string(value):
    for icon in bpy.types.UILayout.bl_rna.functions["prop"].parameters["icon"].enum_items:
        if icon.value == value:
            return icon.name
    return "NONE"
    
def enum_set_to_string(value):
    if type(value) == set:
        if len(value) > 0:
            return "[" + (", ").join(list(value)) + "]"
        return "[]"
    return value
    
def string_to_type(value, to_type, default):
    try:
        value = to_type(value)
    except:
        value = default
    return value

addon_keymaps = {}
_icons = None
node_tree = {'sna_img1': [], 'sna_img2': [], 'sna_img3': [], 'sna_img4': [], }
node_tree = {}
node_tree_001 = {}


def load_preview_icon(path):
    global _icons
    if not path in _icons:
        if os.path.exists(path):
            _icons.load(path, path, "IMAGE")
        else:
            return 0
    return _icons[path].icon_id
def load_preview_icon(path):
    global _icons
    if not path in _icons:
        if os.path.exists(path):
            _icons.load(path, path, "IMAGE")
        else:
            return 0
    return _icons[path].icon_id
def load_preview_icon(path):
    global _icons
    if not path in _icons:
        if os.path.exists(path):
            _icons.load(path, path, "IMAGE")
        else:
            return 0
    return _icons[path].icon_id
def load_preview_icon(path):
    global _icons
    if not path in _icons:
        if os.path.exists(path):
            _icons.load(path, path, "IMAGE")
        else:
            return 0
    return _icons[path].icon_id
def load_preview_icon(path):
    global _icons
    if not path in _icons:
        if os.path.exists(path):
            _icons.load(path, path, "IMAGE")
        else:
            return 0
    return _icons[path].icon_id
def load_preview_icon(path):
    global _icons
    if not path in _icons:
        if os.path.exists(path):
            _icons.load(path, path, "IMAGE")
        else:
            return 0
    return _icons[path].icon_id
def load_preview_icon(path):
    global _icons
    if not path in _icons:
        if os.path.exists(path):
            _icons.load(path, path, "IMAGE")
        else:
            return 0
    return _icons[path].icon_id
def load_preview_icon(path):
    global _icons
    if not path in _icons:
        if os.path.exists(path):
            _icons.load(path, path, "IMAGE")
        else:
            return 0
    return _icons[path].icon_id
def load_preview_icon(path):
    global _icons
    if not path in _icons:
        if os.path.exists(path):
            _icons.load(path, path, "IMAGE")
        else:
            return 0
    return _icons[path].icon_id
def load_preview_icon(path):
    global _icons
    if not path in _icons:
        if os.path.exists(path):
            _icons.load(path, path, "IMAGE")
        else:
            return 0
    return _icons[path].icon_id
def load_preview_icon(path):
    global _icons
    if not path in _icons:
        if os.path.exists(path):
            _icons.load(path, path, "IMAGE")
        else:
            return 0
    return _icons[path].icon_id
def load_preview_icon(path):
    global _icons
    if not path in _icons:
        if os.path.exists(path):
            _icons.load(path, path, "IMAGE")
        else:
            return 0
    return _icons[path].icon_id
def load_preview_icon(path):
    global _icons
    if not path in _icons:
        if os.path.exists(path):
            _icons.load(path, path, "IMAGE")
        else:
            return 0
    return _icons[path].icon_id
def load_preview_icon(path):
    global _icons
    if not path in _icons:
        if os.path.exists(path):
            _icons.load(path, path, "IMAGE")
        else:
            return 0
    return _icons[path].icon_id
def load_preview_icon(path):
    global _icons
    if not path in _icons:
        if os.path.exists(path):
            _icons.load(path, path, "IMAGE")
        else:
            return 0
    return _icons[path].icon_id
def load_preview_icon(path):
    global _icons
    if not path in _icons:
        if os.path.exists(path):
            _icons.load(path, path, "IMAGE")
        else:
            return 0
    return _icons[path].icon_id

class SNA_OT_My_Generic_Operator_7A4Df(bpy.types.Operator):
    bl_idname = "sna.my_generic_operator_7a4df"
    bl_label = "合并"
    bl_description = ""
    bl_options = {"REGISTER", "UNDO"}
    
    
    @classmethod
    def poll(cls, context):
        return not False
    def execute(self, context):
        if not os.path.exists(os.path.join(bpy.path.abspath(bpy.context.scene.sna_lujing_q),'合并')):
            os.mkdir(os.path.join(bpy.path.abspath(bpy.context.scene.sna_lujing_q),'合并'))
        for i_7F950 in range(len(['_d.tga', '_m.tga', '_n.tga'])):
            node_tree['sna_img1'] = []
            node_tree['sna_img2'] = []
            node_tree['sna_img3'] = []
            node_tree['sna_img4'] = []
            for i_5CD8F in range(4):
                if os.path.exists(os.path.join(bpy.path.abspath(bpy.context.scene.sna_lujing_q),str(int(i_5CD8F + 1.0)) + ['_d.tga', '_m.tga', '_n.tga'][i_7F950])):
                    node_tree['sna_img1'].append(os.path.join(bpy.path.abspath(bpy.context.scene.sna_lujing_q),str(int(i_5CD8F + 1.0)) + ['_d.tga', '_m.tga', '_n.tga'][i_7F950]))
                else:
                    node_tree['sna_img1'].append(bpy.path.abspath(os.path.join(os.path.dirname(__file__), 'assets', '背景.png')))
            for i_E44B3 in range(4):
                if os.path.exists(os.path.join(bpy.path.abspath(bpy.context.scene.sna_lujing_q),str(int(i_E44B3 + 5.0)) + ['_d.tga', '_m.tga', '_n.tga'][i_7F950])):
                    node_tree['sna_img2'].append(os.path.join(bpy.path.abspath(bpy.context.scene.sna_lujing_q),str(int(i_E44B3 + 5.0)) + ['_d.tga', '_m.tga', '_n.tga'][i_7F950]))
                else:
                    node_tree['sna_img2'].append(bpy.path.abspath(os.path.join(os.path.dirname(__file__), 'assets', '背景.png')))
            for i_A368A in range(4):
                if os.path.exists(os.path.join(bpy.path.abspath(bpy.context.scene.sna_lujing_q),str(int(i_A368A + 9.0)) + ['_d.tga', '_m.tga', '_n.tga'][i_7F950])):
                    node_tree['sna_img3'].append(os.path.join(bpy.path.abspath(bpy.context.scene.sna_lujing_q),str(int(i_A368A + 9.0)) + ['_d.tga', '_m.tga', '_n.tga'][i_7F950]))
                else:
                    node_tree['sna_img3'].append(bpy.path.abspath(os.path.join(os.path.dirname(__file__), 'assets', '背景.png')))
            for i_DA586 in range(4):
                if os.path.exists(os.path.join(bpy.path.abspath(bpy.context.scene.sna_lujing_q),str(int(i_DA586 + 13.0)) + ['_d.tga', '_m.tga', '_n.tga'][i_7F950])):
                    node_tree['sna_img4'].append(os.path.join(bpy.path.abspath(bpy.context.scene.sna_lujing_q),str(int(i_DA586 + 13.0)) + ['_d.tga', '_m.tga', '_n.tga'][i_7F950]))
                else:
                    node_tree['sna_img4'].append(bpy.path.abspath(os.path.join(os.path.dirname(__file__), 'assets', '背景.png')))
            save_name = os.path.join(os.path.join(bpy.path.abspath(bpy.context.scene.sna_lujing_q),'合并'),'合并' + ['_d.tga', '_m.tga', '_n.tga'][i_7F950])
            img_name1 = node_tree['sna_img1']
            img_name2 = node_tree['sna_img2']
            img_name3 = node_tree['sna_img3']
            img_name4 = node_tree['sna_img4']
            siz = bpy.context.scene.sna_hebingdaoxiao_q
            # 打开多个图像并设置大小
            img1 = Image.open(img_name1[0]).resize((siz, siz))
            img2 = Image.open(img_name1[1]).resize((siz, siz))
            img3 = Image.open(img_name1[2]).resize((siz, siz))
            img4 = Image.open(img_name1[3]).resize((siz, siz))
            img5 = Image.open(img_name2[0]).resize((siz, siz))
            img6 = Image.open(img_name2[1]).resize((siz, siz))
            img7 = Image.open(img_name2[2]).resize((siz, siz))
            img8 = Image.open(img_name2[3]).resize((siz, siz))
            img9 = Image.open(img_name3[0]).resize((siz, siz))
            img10 = Image.open(img_name3[1]).resize((siz, siz))
            img11 = Image.open(img_name3[2]).resize((siz, siz))
            img12 = Image.open(img_name3[3]).resize((siz, siz))
            img13 = Image.open(img_name4[0]).resize((siz, siz))
            img14 = Image.open(img_name4[1]).resize((siz, siz))
            img15 = Image.open(img_name4[2]).resize((siz, siz))
            img16 = Image.open(img_name4[3]).resize((siz, siz))
            # 获取图像的尺寸
            width = siz
            height = siz
            # 创建新的图像
            new_img = Image.new('RGBA', (width*4, height*4))
            # 将多个图像拼接到新的图像上
            fruits1=[img1, img2, img3, img4]
            fruits2=[img5, img6, img7, img8]
            fruits3=[img9, img10, img11, img12]
            fruits4=[img13, img14, img15, img16]
            fruits = [fruits1, fruits2, fruits3, fruits4]
            for i, qkk in enumerate(fruits):
                for j, b in enumerate(qkk):
                    region = (width*j, height*i, width*(j+1), height*(i+1))
                    new_img.paste(b, region)
                
            # 保存拼接后的图像
            new_img.save(save_name)
        return {"FINISHED"}
    
    def invoke(self, context, event):
        
        
        return self.execute(context)
class SNA_PT__80822(bpy.types.Panel):
    bl_label = '贴图溢出合并'
    bl_idname = 'SNA_PT__80822'
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_context = ''
    bl_category = '图像处理'
    bl_order = 0
    bl_options = {'DEFAULT_CLOSED'}
    
    @classmethod
    def poll(cls, context):
        return not (False)
    
    def draw_header(self, context):
        layout = self.layout
        
    def draw(self, context):
        layout = self.layout
        layout_function = layout
        sna_func_B550A(layout_function, )
        box_F4FE3 = layout.box()
        box_F4FE3.alert = False
        box_F4FE3.enabled = True
        box_F4FE3.use_property_split = False
        box_F4FE3.use_property_decorate = False
        box_F4FE3.alignment = 'Expand'.upper()
        box_F4FE3.scale_x = 1.0
        box_F4FE3.scale_y = 1.0
        col_A0951 = box_F4FE3.column(heading='', align=False)
        col_A0951.alert = False
        col_A0951.enabled = os.path.exists(bpy.path.abspath(bpy.context.scene.sna_lujing_q))
        col_A0951.use_property_split = False
        col_A0951.use_property_decorate = False
        col_A0951.scale_x = 1.0
        col_A0951.scale_y = 1.0
        col_A0951.alignment = 'Expand'.upper()
        col_6561F = col_A0951.column(heading='', align=False)
        col_6561F.alert = False
        col_6561F.enabled = True
        col_6561F.use_property_split = False
        col_6561F.use_property_decorate = False
        col_6561F.scale_x = 1.0
        col_6561F.scale_y = 1.0
        col_6561F.alignment = 'Expand'.upper()
        col_6561F.prop(bpy.context.scene, 'sna_zidonghebing_q', text='自动合并', icon_value=0, emboss=True)
        split_2054C = col_6561F.split(factor=0.5, align=False)
        split_2054C.alert = False
        split_2054C.enabled = True
        split_2054C.use_property_split = False
        split_2054C.use_property_decorate = False
        split_2054C.scale_x = 1.0
        split_2054C.scale_y = 1.0
        split_2054C.alignment = 'Expand'.upper()
        col_C1BC5 = split_2054C.column(heading='', align=False)
        col_C1BC5.alert = False
        col_C1BC5.enabled = not bpy.context.scene.sna_zidonghebing_q
        col_C1BC5.use_property_split = False
        col_C1BC5.use_property_decorate = False
        col_C1BC5.scale_x = 1.0
        col_C1BC5.scale_y = 2.0
        col_C1BC5.alignment = 'Expand'.upper()
        op = col_C1BC5.operator('sna.my_generic_operator_7a4df', text='合并', icon_value=754, emboss=True, depress=False)
        split_481D1 = split_2054C.split(factor=0.20000000298023224, align=False)
        split_481D1.alert = False
        split_481D1.enabled = True
        split_481D1.use_property_split = False
        split_481D1.use_property_decorate = False
        split_481D1.scale_x = 1.0
        split_481D1.scale_y = 1.0
        split_481D1.alignment = 'Expand'.upper()
        split_481D1.label(text='每块尺寸：', icon_value=0)
        col_A9D88 = split_481D1.column(heading='', align=False)
        col_A9D88.alert = False
        col_A9D88.enabled = True
        col_A9D88.use_property_split = False
        col_A9D88.use_property_decorate = False
        col_A9D88.scale_x = 1.0
        col_A9D88.scale_y = 1.0
        col_A9D88.alignment = 'Expand'.upper()
        col_A9D88.prop(bpy.context.scene, 'sna_hebingdaoxiao_q', text='', icon_value=0, emboss=True, slider=True)
        col_A9D88.label(text=str(bpy.context.scene.sna_hebingdaoxiao_q) + 'x4=' + str(int(4.0 * bpy.context.scene.sna_hebingdaoxiao_q)), icon_value=0)
        layout_function = layout
        sna_func_EA604(layout_function, )
def sna_func_B550A(layout_function, ):
    pass
    box_BF373 = layout_function.box()
    box_BF373.alert = False
    box_BF373.enabled = True
    box_BF373.use_property_split = False
    box_BF373.use_property_decorate = False
    box_BF373.alignment = 'Expand'.upper()
    box_BF373.scale_x = 1.0
    box_BF373.scale_y = 1.0
    split_213D3 = box_BF373.split(factor=0.699999988079071, align=False)
    split_213D3.alert = False
    split_213D3.enabled = True
    split_213D3.use_property_split = False
    split_213D3.use_property_decorate = False
    split_213D3.scale_x = 1.0
    split_213D3.scale_y = 1.2000000476837158
    split_213D3.alignment = 'Expand'.upper()
    split_213D3.prop(bpy.context.scene, 'sna_lujing_q', text='输出路径', icon_value=0, emboss=True)
    col_32B0C = split_213D3.column(heading='', align=True)
    col_32B0C.alert = False
    col_32B0C.enabled = os.path.exists(bpy.path.abspath(bpy.context.scene.sna_lujing_q))
    col_32B0C.use_property_split = False
    col_32B0C.use_property_decorate = False
    col_32B0C.scale_x = 1.0
    col_32B0C.scale_y = 1.0
    col_32B0C.alignment = 'Expand'.upper()
    op = col_32B0C.operator('sna.my_generic_operator_0b9b5', text='打开目录', icon_value=112, emboss=True, depress=False)
    split_A6B7E = box_BF373.split(factor=0.5, align=True)
    split_A6B7E.alert = False
    split_A6B7E.enabled = os.path.exists(bpy.path.abspath(bpy.context.scene.sna_lujing_q))
    split_A6B7E.use_property_split = False
    split_A6B7E.use_property_decorate = False
    split_A6B7E.scale_x = 1.0
    split_A6B7E.scale_y = 2.0
    split_A6B7E.alignment = 'Expand'.upper()
    op = split_A6B7E.operator('sna.my_generic_operator_fc2f6', text='溢出处理', icon_value=75, emboss=True, depress=False)
    split_228E8 = split_A6B7E.split(factor=0.5, align=True)
    split_228E8.alert = False
    split_228E8.enabled = True
    split_228E8.use_property_split = False
    split_228E8.use_property_decorate = False
    split_228E8.scale_x = 1.0
    split_228E8.scale_y = 1.0
    split_228E8.alignment = 'Expand'.upper()
    split_228E8.prop(bpy.context.scene, 'sna_dim_q', text='输出尺寸：', icon_value=0, emboss=True, slider=True)
    split_228E8.prop(bpy.context.scene, 'sna_pixel_q', text='溢出像素：', icon_value=0, emboss=True, slider=True)
    
class SNA_OT_My_Generic_Operator_0B9B5(bpy.types.Operator):
    bl_idname = "sna.my_generic_operator_0b9b5"
    bl_label = "打开目录"
    bl_description = ""
    bl_options = {"REGISTER", "UNDO"}
    
    
    @classmethod
    def poll(cls, context):
        return not False
    def execute(self, context):
        a = bpy.path.abspath(bpy.context.scene.sna_lujing_q)
        folder_path = a
        os.startfile(folder_path)
        return {"FINISHED"}
    
    def invoke(self, context, event):
        
        
        return self.execute(context)
class SNA_OT_My_Generic_Operator_Fc2F6(bpy.types.Operator):
    bl_idname = "sna.my_generic_operator_fc2f6"
    bl_label = "图像溢出"
    bl_description = ""
    bl_options = {"REGISTER", "UNDO"}
    
    
    @classmethod
    def poll(cls, context):
        return not False
    def execute(self, context):
        for i_2C772 in range(len([bpy.path.abspath(bpy.context.scene.sna_q), bpy.path.abspath(bpy.context.scene.sna_q_001), bpy.path.abspath(bpy.context.scene.sna_q_002), bpy.path.abspath(bpy.context.scene.sna_q_003), bpy.path.abspath(bpy.context.scene.sna_q_004), bpy.path.abspath(bpy.context.scene.sna_q_005), bpy.path.abspath(bpy.context.scene.sna_q_006), bpy.path.abspath(bpy.context.scene.sna_q_007), bpy.path.abspath(bpy.context.scene.sna_q_008), bpy.path.abspath(bpy.context.scene.sna_q_009), bpy.path.abspath(bpy.context.scene.sna_q_010), bpy.path.abspath(bpy.context.scene.sna_q_011), bpy.path.abspath(bpy.context.scene.sna_q_012), bpy.path.abspath(bpy.context.scene.sna_q_013), bpy.path.abspath(bpy.context.scene.sna_q_014), bpy.path.abspath(bpy.context.scene.sna_q_015)])):
            for i_A47BC in range(len(['d', 'm', 'n'])):
                if os.path.exists(os.path.join(os.path.dirname([bpy.path.abspath(bpy.context.scene.sna_q), bpy.path.abspath(bpy.context.scene.sna_q_001), bpy.path.abspath(bpy.context.scene.sna_q_002), bpy.path.abspath(bpy.context.scene.sna_q_003), bpy.path.abspath(bpy.context.scene.sna_q_004), bpy.path.abspath(bpy.context.scene.sna_q_005), bpy.path.abspath(bpy.context.scene.sna_q_006), bpy.path.abspath(bpy.context.scene.sna_q_007), bpy.path.abspath(bpy.context.scene.sna_q_008), bpy.path.abspath(bpy.context.scene.sna_q_009), bpy.path.abspath(bpy.context.scene.sna_q_010), bpy.path.abspath(bpy.context.scene.sna_q_011), bpy.path.abspath(bpy.context.scene.sna_q_012), bpy.path.abspath(bpy.context.scene.sna_q_013), bpy.path.abspath(bpy.context.scene.sna_q_014), bpy.path.abspath(bpy.context.scene.sna_q_015)][i_2C772]),os.path.basename([bpy.path.abspath(bpy.context.scene.sna_q), bpy.path.abspath(bpy.context.scene.sna_q_001), bpy.path.abspath(bpy.context.scene.sna_q_002), bpy.path.abspath(bpy.context.scene.sna_q_003), bpy.path.abspath(bpy.context.scene.sna_q_004), bpy.path.abspath(bpy.context.scene.sna_q_005), bpy.path.abspath(bpy.context.scene.sna_q_006), bpy.path.abspath(bpy.context.scene.sna_q_007), bpy.path.abspath(bpy.context.scene.sna_q_008), bpy.path.abspath(bpy.context.scene.sna_q_009), bpy.path.abspath(bpy.context.scene.sna_q_010), bpy.path.abspath(bpy.context.scene.sna_q_011), bpy.path.abspath(bpy.context.scene.sna_q_012), bpy.path.abspath(bpy.context.scene.sna_q_013), bpy.path.abspath(bpy.context.scene.sna_q_014), bpy.path.abspath(bpy.context.scene.sna_q_015)][i_2C772])[:int(-1.0 - len(os.path.splitext([bpy.path.abspath(bpy.context.scene.sna_q), bpy.path.abspath(bpy.context.scene.sna_q_001), bpy.path.abspath(bpy.context.scene.sna_q_002), bpy.path.abspath(bpy.context.scene.sna_q_003), bpy.path.abspath(bpy.context.scene.sna_q_004), bpy.path.abspath(bpy.context.scene.sna_q_005), bpy.path.abspath(bpy.context.scene.sna_q_006), bpy.path.abspath(bpy.context.scene.sna_q_007), bpy.path.abspath(bpy.context.scene.sna_q_008), bpy.path.abspath(bpy.context.scene.sna_q_009), bpy.path.abspath(bpy.context.scene.sna_q_010), bpy.path.abspath(bpy.context.scene.sna_q_011), bpy.path.abspath(bpy.context.scene.sna_q_012), bpy.path.abspath(bpy.context.scene.sna_q_013), bpy.path.abspath(bpy.context.scene.sna_q_014), bpy.path.abspath(bpy.context.scene.sna_q_015)][i_2C772])[1]))] + ['d', 'm', 'n'][i_A47BC] + os.path.splitext([bpy.path.abspath(bpy.context.scene.sna_q), bpy.path.abspath(bpy.context.scene.sna_q_001), bpy.path.abspath(bpy.context.scene.sna_q_002), bpy.path.abspath(bpy.context.scene.sna_q_003), bpy.path.abspath(bpy.context.scene.sna_q_004), bpy.path.abspath(bpy.context.scene.sna_q_005), bpy.path.abspath(bpy.context.scene.sna_q_006), bpy.path.abspath(bpy.context.scene.sna_q_007), bpy.path.abspath(bpy.context.scene.sna_q_008), bpy.path.abspath(bpy.context.scene.sna_q_009), bpy.path.abspath(bpy.context.scene.sna_q_010), bpy.path.abspath(bpy.context.scene.sna_q_011), bpy.path.abspath(bpy.context.scene.sna_q_012), bpy.path.abspath(bpy.context.scene.sna_q_013), bpy.path.abspath(bpy.context.scene.sna_q_014), bpy.path.abspath(bpy.context.scene.sna_q_015)][i_2C772])[1])):
                    img_name = os.path.join(os.path.dirname([bpy.path.abspath(bpy.context.scene.sna_q), bpy.path.abspath(bpy.context.scene.sna_q_001), bpy.path.abspath(bpy.context.scene.sna_q_002), bpy.path.abspath(bpy.context.scene.sna_q_003), bpy.path.abspath(bpy.context.scene.sna_q_004), bpy.path.abspath(bpy.context.scene.sna_q_005), bpy.path.abspath(bpy.context.scene.sna_q_006), bpy.path.abspath(bpy.context.scene.sna_q_007), bpy.path.abspath(bpy.context.scene.sna_q_008), bpy.path.abspath(bpy.context.scene.sna_q_009), bpy.path.abspath(bpy.context.scene.sna_q_010), bpy.path.abspath(bpy.context.scene.sna_q_011), bpy.path.abspath(bpy.context.scene.sna_q_012), bpy.path.abspath(bpy.context.scene.sna_q_013), bpy.path.abspath(bpy.context.scene.sna_q_014), bpy.path.abspath(bpy.context.scene.sna_q_015)][i_2C772]),os.path.basename([bpy.path.abspath(bpy.context.scene.sna_q), bpy.path.abspath(bpy.context.scene.sna_q_001), bpy.path.abspath(bpy.context.scene.sna_q_002), bpy.path.abspath(bpy.context.scene.sna_q_003), bpy.path.abspath(bpy.context.scene.sna_q_004), bpy.path.abspath(bpy.context.scene.sna_q_005), bpy.path.abspath(bpy.context.scene.sna_q_006), bpy.path.abspath(bpy.context.scene.sna_q_007), bpy.path.abspath(bpy.context.scene.sna_q_008), bpy.path.abspath(bpy.context.scene.sna_q_009), bpy.path.abspath(bpy.context.scene.sna_q_010), bpy.path.abspath(bpy.context.scene.sna_q_011), bpy.path.abspath(bpy.context.scene.sna_q_012), bpy.path.abspath(bpy.context.scene.sna_q_013), bpy.path.abspath(bpy.context.scene.sna_q_014), bpy.path.abspath(bpy.context.scene.sna_q_015)][i_2C772])[:int(-1.0 - len(os.path.splitext([bpy.path.abspath(bpy.context.scene.sna_q), bpy.path.abspath(bpy.context.scene.sna_q_001), bpy.path.abspath(bpy.context.scene.sna_q_002), bpy.path.abspath(bpy.context.scene.sna_q_003), bpy.path.abspath(bpy.context.scene.sna_q_004), bpy.path.abspath(bpy.context.scene.sna_q_005), bpy.path.abspath(bpy.context.scene.sna_q_006), bpy.path.abspath(bpy.context.scene.sna_q_007), bpy.path.abspath(bpy.context.scene.sna_q_008), bpy.path.abspath(bpy.context.scene.sna_q_009), bpy.path.abspath(bpy.context.scene.sna_q_010), bpy.path.abspath(bpy.context.scene.sna_q_011), bpy.path.abspath(bpy.context.scene.sna_q_012), bpy.path.abspath(bpy.context.scene.sna_q_013), bpy.path.abspath(bpy.context.scene.sna_q_014), bpy.path.abspath(bpy.context.scene.sna_q_015)][i_2C772])[1]))] + ['d', 'm', 'n'][i_A47BC] + os.path.splitext([bpy.path.abspath(bpy.context.scene.sna_q), bpy.path.abspath(bpy.context.scene.sna_q_001), bpy.path.abspath(bpy.context.scene.sna_q_002), bpy.path.abspath(bpy.context.scene.sna_q_003), bpy.path.abspath(bpy.context.scene.sna_q_004), bpy.path.abspath(bpy.context.scene.sna_q_005), bpy.path.abspath(bpy.context.scene.sna_q_006), bpy.path.abspath(bpy.context.scene.sna_q_007), bpy.path.abspath(bpy.context.scene.sna_q_008), bpy.path.abspath(bpy.context.scene.sna_q_009), bpy.path.abspath(bpy.context.scene.sna_q_010), bpy.path.abspath(bpy.context.scene.sna_q_011), bpy.path.abspath(bpy.context.scene.sna_q_012), bpy.path.abspath(bpy.context.scene.sna_q_013), bpy.path.abspath(bpy.context.scene.sna_q_014), bpy.path.abspath(bpy.context.scene.sna_q_015)][i_2C772])[1])
                    save_name = os.path.join(bpy.path.abspath(bpy.context.scene.sna_lujing_q),str(int(i_2C772 + 1.0)) + '_' + ['d', 'm', 'n'][i_A47BC] + '.tga')
                    pixel = bpy.context.scene.sna_pixel_q
                    dim = bpy.context.scene.sna_dim_q
                    # 打开图片
                    img = Image.open(img_name)
                    # 统一比例
                    new_size = (dim-(2*pixel),dim-(2*pixel))
                    # 调整图像尺寸
                    img = img.resize(new_size)
                    # 定义扩展像素数
                    n = pixel
                    # 获取边缘像素
                    left = img.crop((0, 0, 1, img.height))
                    right = img.crop((img.width - 1, 0, img.width, img.height))
                    top = img.crop((0, 0, img.width, 1))
                    bottom = img.crop((0, img.height - 1, img.width, img.height))
                    def get_average_color(img):
                    ##   将图像缩小到1x1大小，以便获取像素的平均值
                        img = img.resize((1, 1))
                        # 获取图像的像素值
                        pixel = img.getpixel((0, 0))
                        # 返回RGB颜色元组
                        return (pixel[0], pixel[1], pixel[2])
                    # 获取平均颜色
                    color = get_average_color(img)
                    # 创建具有扩展边框的新图像. 边框参数设置为 n 以指定扩展边框的像素数，填充参数设置为 （0， 0， 0， 0） 以指定展开边框的颜色（透明黑色）
                    new_img = ImageOps.expand(img, border=n, fill=color)
                    #, fill=(0,0,0)
                    # 填充边缘像素
                    new_img.paste(left, (n, n, n + 1, new_img.height - n))
                    new_img.paste(right, (new_img.width - n - 1, n, new_img.width - n, new_img.height - n))
                    new_img.paste(top, (n, n, new_img.width - n, n + 1))
                    new_img.paste(bottom, (n, new_img.height - n - 1, new_img.width - n, new_img.height - n))
                    # 调整左侧、右侧、顶部和底部图像的大小，以匹配相应边框区域的尺寸
                    left = left.resize((n, new_img.height - 2 * n))
                    right = right.resize((n, new_img.height - 2 * n))
                    top = top.resize((new_img.width - 2 * n, n))
                    bottom = bottom.resize((new_img.width - 2 * n, n))
                    ## 调整大小的边缘图像粘贴到新图像的边框区域
                    new_img.paste(left, (0, n, n, new_img.height - n))
                    new_img.paste(right, (new_img.width - n, n, new_img.width, new_img.height - n))
                    new_img.paste(top, (n, 0, new_img.width - n, n))
                    new_img.paste(bottom, (n, new_img.height - n, new_img.width - n, new_img.height))
                    # 保存图片
                    new_img.save(save_name)
                else:
                    pass
        if bpy.context.scene.sna_zidonghebing_q:
            bpy.ops.sna.my_generic_operator_7a4df()
        else:
            pass
        return {"FINISHED"}
    
    def invoke(self, context, event):
        
        
        return self.execute(context)
def sna_func_EA604(layout_function, ):
    pass
    col_6D9D9 = layout_function.column(heading='', align=True)
    col_6D9D9.alert = False
    col_6D9D9.enabled = True
    col_6D9D9.use_property_split = False
    col_6D9D9.use_property_decorate = False
    col_6D9D9.scale_x = 1.0
    col_6D9D9.scale_y = 1.0
    col_6D9D9.alignment = 'Expand'.upper()
    row_D7D3E = col_6D9D9.row(heading='', align=True)
    row_D7D3E.alert = False
    row_D7D3E.enabled = True
    row_D7D3E.use_property_split = False
    row_D7D3E.use_property_decorate = False
    row_D7D3E.scale_x = 1.0
    row_D7D3E.scale_y = 1.5
    row_D7D3E.alignment = 'Expand'.upper()
    row_D7D3E.prop(bpy.context.scene, 'sna_qiehuan_q', text=' ', icon_value=0, emboss=True, expand=True)
    row_FBA66 = col_6D9D9.row(heading='', align=True)
    row_FBA66.alert = False
    row_FBA66.enabled = True
    row_FBA66.use_property_split = False
    row_FBA66.use_property_decorate = False
    row_FBA66.scale_x = 1.0
    row_FBA66.scale_y = 1.0
    row_FBA66.alignment = 'Expand'.upper()
    box_F5A34 = row_FBA66.box()
    box_F5A34.alert = False
    box_F5A34.enabled = True
    box_F5A34.use_property_split = False
    box_F5A34.use_property_decorate = False
    box_F5A34.alignment = 'Expand'.upper()
    box_F5A34.scale_x = 1.0
    box_F5A34.scale_y = 1.0
    box_F5A34.template_icon(icon_value=load_preview_icon(os.path.join(os.path.dirname(bpy.path.abspath(bpy.context.scene.sna_q)),os.path.basename(bpy.path.abspath(bpy.context.scene.sna_q))[:int(-1.0 - len(os.path.splitext(bpy.path.abspath(bpy.context.scene.sna_q))[1]))] + bpy.context.scene.sna_qiehuan_q + os.path.splitext(bpy.path.abspath(bpy.context.scene.sna_q))[1])), scale=6.0)
    box_F5A34.prop(bpy.context.scene, 'sna_q', text='', icon_value=0, emboss=True)
    box_6D865 = row_FBA66.box()
    box_6D865.alert = False
    box_6D865.enabled = True
    box_6D865.use_property_split = False
    box_6D865.use_property_decorate = False
    box_6D865.alignment = 'Expand'.upper()
    box_6D865.scale_x = 1.0
    box_6D865.scale_y = 1.0
    box_6D865.template_icon(icon_value=load_preview_icon(os.path.join(os.path.dirname(bpy.path.abspath(bpy.context.scene.sna_q_001)),os.path.basename(bpy.path.abspath(bpy.context.scene.sna_q_001))[:int(-1.0 - len(os.path.splitext(bpy.path.abspath(bpy.context.scene.sna_q_001))[1]))] + bpy.context.scene.sna_qiehuan_q + os.path.splitext(bpy.path.abspath(bpy.context.scene.sna_q_001))[1])), scale=6.0)
    box_6D865.prop(bpy.context.scene, 'sna_q_001', text='', icon_value=0, emboss=True)
    box_CCB37 = row_FBA66.box()
    box_CCB37.alert = False
    box_CCB37.enabled = True
    box_CCB37.use_property_split = False
    box_CCB37.use_property_decorate = False
    box_CCB37.alignment = 'Expand'.upper()
    box_CCB37.scale_x = 1.0
    box_CCB37.scale_y = 1.0
    box_CCB37.template_icon(icon_value=load_preview_icon(os.path.join(os.path.dirname(bpy.path.abspath(bpy.context.scene.sna_q_002)),os.path.basename(bpy.path.abspath(bpy.context.scene.sna_q_002))[:int(-1.0 - len(os.path.splitext(bpy.path.abspath(bpy.context.scene.sna_q_002))[1]))] + bpy.context.scene.sna_qiehuan_q + os.path.splitext(bpy.path.abspath(bpy.context.scene.sna_q_002))[1])), scale=6.0)
    box_CCB37.prop(bpy.context.scene, 'sna_q_002', text='', icon_value=0, emboss=True)
    box_7E4D2 = row_FBA66.box()
    box_7E4D2.alert = False
    box_7E4D2.enabled = True
    box_7E4D2.use_property_split = False
    box_7E4D2.use_property_decorate = False
    box_7E4D2.alignment = 'Expand'.upper()
    box_7E4D2.scale_x = 1.0
    box_7E4D2.scale_y = 1.0
    box_7E4D2.template_icon(icon_value=load_preview_icon(os.path.join(os.path.dirname(bpy.path.abspath(bpy.context.scene.sna_q_003)),os.path.basename(bpy.path.abspath(bpy.context.scene.sna_q_003))[:int(-1.0 - len(os.path.splitext(bpy.path.abspath(bpy.context.scene.sna_q_003))[1]))] + bpy.context.scene.sna_qiehuan_q + os.path.splitext(bpy.path.abspath(bpy.context.scene.sna_q_003))[1])), scale=6.0)
    box_7E4D2.prop(bpy.context.scene, 'sna_q_003', text='', icon_value=0, emboss=True)
    row_CFE04 = col_6D9D9.row(heading='', align=True)
    row_CFE04.alert = False
    row_CFE04.enabled = True
    row_CFE04.use_property_split = False
    row_CFE04.use_property_decorate = False
    row_CFE04.scale_x = 1.0
    row_CFE04.scale_y = 1.0
    row_CFE04.alignment = 'Expand'.upper()
    box_7A602 = row_CFE04.box()
    box_7A602.alert = False
    box_7A602.enabled = True
    box_7A602.use_property_split = False
    box_7A602.use_property_decorate = False
    box_7A602.alignment = 'Expand'.upper()
    box_7A602.scale_x = 1.0
    box_7A602.scale_y = 1.0
    box_7A602.template_icon(icon_value=load_preview_icon(os.path.join(os.path.dirname(bpy.path.abspath(bpy.context.scene.sna_q_004)),os.path.basename(bpy.path.abspath(bpy.context.scene.sna_q_004))[:int(-1.0 - len(os.path.splitext(bpy.path.abspath(bpy.context.scene.sna_q_004))[1]))] + bpy.context.scene.sna_qiehuan_q + os.path.splitext(bpy.path.abspath(bpy.context.scene.sna_q_004))[1])), scale=6.0)
    box_7A602.prop(bpy.context.scene, 'sna_q_004', text='', icon_value=0, emboss=True)
    box_05D5D = row_CFE04.box()
    box_05D5D.alert = False
    box_05D5D.enabled = True
    box_05D5D.use_property_split = False
    box_05D5D.use_property_decorate = False
    box_05D5D.alignment = 'Expand'.upper()
    box_05D5D.scale_x = 1.0
    box_05D5D.scale_y = 1.0
    box_05D5D.template_icon(icon_value=load_preview_icon(os.path.join(os.path.dirname(bpy.path.abspath(bpy.context.scene.sna_q_005)),os.path.basename(bpy.path.abspath(bpy.context.scene.sna_q_005))[:int(-1.0 - len(os.path.splitext(bpy.path.abspath(bpy.context.scene.sna_q_005))[1]))] + bpy.context.scene.sna_qiehuan_q + os.path.splitext(bpy.path.abspath(bpy.context.scene.sna_q_005))[1])), scale=6.0)
    box_05D5D.prop(bpy.context.scene, 'sna_q_005', text='', icon_value=0, emboss=True)
    box_0FEFC = row_CFE04.box()
    box_0FEFC.alert = False
    box_0FEFC.enabled = True
    box_0FEFC.use_property_split = False
    box_0FEFC.use_property_decorate = False
    box_0FEFC.alignment = 'Expand'.upper()
    box_0FEFC.scale_x = 1.0
    box_0FEFC.scale_y = 1.0
    box_0FEFC.template_icon(icon_value=load_preview_icon(os.path.join(os.path.dirname(bpy.path.abspath(bpy.context.scene.sna_q_006)),os.path.basename(bpy.path.abspath(bpy.context.scene.sna_q_006))[:int(-1.0 - len(os.path.splitext(bpy.path.abspath(bpy.context.scene.sna_q_006))[1]))] + bpy.context.scene.sna_qiehuan_q + os.path.splitext(bpy.path.abspath(bpy.context.scene.sna_q_006))[1])), scale=6.0)
    box_0FEFC.prop(bpy.context.scene, 'sna_q_006', text='', icon_value=0, emboss=True)
    box_6C963 = row_CFE04.box()
    box_6C963.alert = False
    box_6C963.enabled = True
    box_6C963.use_property_split = False
    box_6C963.use_property_decorate = False
    box_6C963.alignment = 'Expand'.upper()
    box_6C963.scale_x = 1.0
    box_6C963.scale_y = 1.0
    box_6C963.template_icon(icon_value=load_preview_icon(os.path.join(os.path.dirname(bpy.path.abspath(bpy.context.scene.sna_q_007)),os.path.basename(bpy.path.abspath(bpy.context.scene.sna_q_007))[:int(-1.0 - len(os.path.splitext(bpy.path.abspath(bpy.context.scene.sna_q_007))[1]))] + bpy.context.scene.sna_qiehuan_q + os.path.splitext(bpy.path.abspath(bpy.context.scene.sna_q_007))[1])), scale=6.0)
    box_6C963.prop(bpy.context.scene, 'sna_q_007', text='', icon_value=0, emboss=True)
    row_0CBE3 = col_6D9D9.row(heading='', align=True)
    row_0CBE3.alert = False
    row_0CBE3.enabled = True
    row_0CBE3.use_property_split = False
    row_0CBE3.use_property_decorate = False
    row_0CBE3.scale_x = 1.0
    row_0CBE3.scale_y = 1.0
    row_0CBE3.alignment = 'Expand'.upper()
    box_65939 = row_0CBE3.box()
    box_65939.alert = False
    box_65939.enabled = True
    box_65939.use_property_split = False
    box_65939.use_property_decorate = False
    box_65939.alignment = 'Expand'.upper()
    box_65939.scale_x = 1.0
    box_65939.scale_y = 1.0
    box_65939.template_icon(icon_value=load_preview_icon(os.path.join(os.path.dirname(bpy.path.abspath(bpy.context.scene.sna_q_008)),os.path.basename(bpy.path.abspath(bpy.context.scene.sna_q_008))[:int(-1.0 - len(os.path.splitext(bpy.path.abspath(bpy.context.scene.sna_q_008))[1]))] + bpy.context.scene.sna_qiehuan_q + os.path.splitext(bpy.path.abspath(bpy.context.scene.sna_q_008))[1])), scale=6.0)
    box_65939.prop(bpy.context.scene, 'sna_q_008', text='', icon_value=0, emboss=True)
    box_F82CC = row_0CBE3.box()
    box_F82CC.alert = False
    box_F82CC.enabled = True
    box_F82CC.use_property_split = False
    box_F82CC.use_property_decorate = False
    box_F82CC.alignment = 'Expand'.upper()
    box_F82CC.scale_x = 1.0
    box_F82CC.scale_y = 1.0
    box_F82CC.template_icon(icon_value=load_preview_icon(os.path.join(os.path.dirname(bpy.path.abspath(bpy.context.scene.sna_q_009)),os.path.basename(bpy.path.abspath(bpy.context.scene.sna_q_009))[:int(-1.0 - len(os.path.splitext(bpy.path.abspath(bpy.context.scene.sna_q_009))[1]))] + bpy.context.scene.sna_qiehuan_q + os.path.splitext(bpy.path.abspath(bpy.context.scene.sna_q_009))[1])), scale=6.0)
    box_F82CC.prop(bpy.context.scene, 'sna_q_009', text='', icon_value=0, emboss=True)
    box_15894 = row_0CBE3.box()
    box_15894.alert = False
    box_15894.enabled = True
    box_15894.use_property_split = False
    box_15894.use_property_decorate = False
    box_15894.alignment = 'Expand'.upper()
    box_15894.scale_x = 1.0
    box_15894.scale_y = 1.0
    box_15894.template_icon(icon_value=load_preview_icon(os.path.join(os.path.dirname(bpy.path.abspath(bpy.context.scene.sna_q_010)),os.path.basename(bpy.path.abspath(bpy.context.scene.sna_q_010))[:int(-1.0 - len(os.path.splitext(bpy.path.abspath(bpy.context.scene.sna_q_010))[1]))] + bpy.context.scene.sna_qiehuan_q + os.path.splitext(bpy.path.abspath(bpy.context.scene.sna_q_010))[1])), scale=6.0)
    box_15894.prop(bpy.context.scene, 'sna_q_010', text='', icon_value=0, emboss=True)
    box_A26BC = row_0CBE3.box()
    box_A26BC.alert = False
    box_A26BC.enabled = True
    box_A26BC.use_property_split = False
    box_A26BC.use_property_decorate = False
    box_A26BC.alignment = 'Expand'.upper()
    box_A26BC.scale_x = 1.0
    box_A26BC.scale_y = 1.0
    box_A26BC.template_icon(icon_value=load_preview_icon(os.path.join(os.path.dirname(bpy.path.abspath(bpy.context.scene.sna_q_011)),os.path.basename(bpy.path.abspath(bpy.context.scene.sna_q_011))[:int(-1.0 - len(os.path.splitext(bpy.path.abspath(bpy.context.scene.sna_q_011))[1]))] + bpy.context.scene.sna_qiehuan_q + os.path.splitext(bpy.path.abspath(bpy.context.scene.sna_q_011))[1])), scale=6.0)
    box_A26BC.prop(bpy.context.scene, 'sna_q_011', text='', icon_value=0, emboss=True)
    row_2F965 = col_6D9D9.row(heading='', align=True)
    row_2F965.alert = False
    row_2F965.enabled = True
    row_2F965.use_property_split = False
    row_2F965.use_property_decorate = False
    row_2F965.scale_x = 1.0
    row_2F965.scale_y = 1.0
    row_2F965.alignment = 'Expand'.upper()
    box_8F3CB = row_2F965.box()
    box_8F3CB.alert = False
    box_8F3CB.enabled = True
    box_8F3CB.use_property_split = False
    box_8F3CB.use_property_decorate = False
    box_8F3CB.alignment = 'Expand'.upper()
    box_8F3CB.scale_x = 1.0
    box_8F3CB.scale_y = 1.0
    box_8F3CB.template_icon(icon_value=load_preview_icon(os.path.join(os.path.dirname(bpy.path.abspath(bpy.context.scene.sna_q_012)),os.path.basename(bpy.path.abspath(bpy.context.scene.sna_q_012))[:int(-1.0 - len(os.path.splitext(bpy.path.abspath(bpy.context.scene.sna_q_012))[1]))] + bpy.context.scene.sna_qiehuan_q + os.path.splitext(bpy.path.abspath(bpy.context.scene.sna_q_012))[1])), scale=6.0)
    box_8F3CB.prop(bpy.context.scene, 'sna_q_012', text='', icon_value=0, emboss=True)
    box_2A867 = row_2F965.box()
    box_2A867.alert = False
    box_2A867.enabled = True
    box_2A867.use_property_split = False
    box_2A867.use_property_decorate = False
    box_2A867.alignment = 'Expand'.upper()
    box_2A867.scale_x = 1.0
    box_2A867.scale_y = 1.0
    box_2A867.template_icon(icon_value=load_preview_icon(os.path.join(os.path.dirname(bpy.path.abspath(bpy.context.scene.sna_q_013)),os.path.basename(bpy.path.abspath(bpy.context.scene.sna_q_013))[:int(-1.0 - len(os.path.splitext(bpy.path.abspath(bpy.context.scene.sna_q_013))[1]))] + bpy.context.scene.sna_qiehuan_q + os.path.splitext(bpy.path.abspath(bpy.context.scene.sna_q_013))[1])), scale=6.0)
    box_2A867.prop(bpy.context.scene, 'sna_q_013', text='', icon_value=0, emboss=True)
    box_445E1 = row_2F965.box()
    box_445E1.alert = False
    box_445E1.enabled = True
    box_445E1.use_property_split = False
    box_445E1.use_property_decorate = False
    box_445E1.alignment = 'Expand'.upper()
    box_445E1.scale_x = 1.0
    box_445E1.scale_y = 1.0
    box_445E1.template_icon(icon_value=load_preview_icon(os.path.join(os.path.dirname(bpy.path.abspath(bpy.context.scene.sna_q_014)),os.path.basename(bpy.path.abspath(bpy.context.scene.sna_q_014))[:int(-1.0 - len(os.path.splitext(bpy.path.abspath(bpy.context.scene.sna_q_014))[1]))] + bpy.context.scene.sna_qiehuan_q + os.path.splitext(bpy.path.abspath(bpy.context.scene.sna_q_014))[1])), scale=6.0)
    box_445E1.prop(bpy.context.scene, 'sna_q_014', text='', icon_value=0, emboss=True)
    box_D0FB1 = row_2F965.box()
    box_D0FB1.alert = False
    box_D0FB1.enabled = True
    box_D0FB1.use_property_split = False
    box_D0FB1.use_property_decorate = False
    box_D0FB1.alignment = 'Expand'.upper()
    box_D0FB1.scale_x = 1.0
    box_D0FB1.scale_y = 1.0
    box_D0FB1.template_icon(icon_value=load_preview_icon(os.path.join(os.path.dirname(bpy.path.abspath(bpy.context.scene.sna_q_015)),os.path.basename(bpy.path.abspath(bpy.context.scene.sna_q_015))[:int(-1.0 - len(os.path.splitext(bpy.path.abspath(bpy.context.scene.sna_q_015))[1]))] + bpy.context.scene.sna_qiehuan_q + os.path.splitext(bpy.path.abspath(bpy.context.scene.sna_q_015))[1])), scale=6.0)
    box_D0FB1.prop(bpy.context.scene, 'sna_q_015', text='', icon_value=0, emboss=True)


def sna_qiehuan_q_enum_items(self, context):
    return [("No Items", "No Items", "No generate enum items node found to create items!", "ERROR", 0)]
























def register():
    
    global _icons
    _icons = bpy.utils.previews.new()
    bpy.types.Scene.sna_pixel_q = bpy.props.IntProperty(name='pixel_q', description='', options={'HIDDEN'}, default=16, subtype='NONE', soft_min=4, soft_max=32)
    bpy.types.Scene.sna_dim_q = bpy.props.IntProperty(name='dim_q', description='', options={'HIDDEN'}, default=512, subtype='NONE', soft_min=128, soft_max=1024)
    bpy.types.Scene.sna_qiehuan_q = bpy.props.EnumProperty(name='qiehuan_q', description='', options={'HIDDEN'}, items=[('d', 'd', '', 0, 0), ('m', 'm', '', 0, 1), ('n', 'n', '', 0, 2)])
    bpy.types.Scene.sna_q = bpy.props.StringProperty(name='1_q', description='', options={'HIDDEN'}, default='', subtype='FILE_PATH', maxlen=0)
    bpy.types.Scene.sna_q_001 = bpy.props.StringProperty(name='2_q', description='', options={'HIDDEN'}, default='', subtype='FILE_PATH', maxlen=0)
    bpy.types.Scene.sna_q_002 = bpy.props.StringProperty(name='3_q', description='', options={'HIDDEN'}, default='', subtype='FILE_PATH', maxlen=0)
    bpy.types.Scene.sna_q_003 = bpy.props.StringProperty(name='4_q', description='', options={'HIDDEN'}, default='', subtype='FILE_PATH', maxlen=0)
    bpy.types.Scene.sna_q_004 = bpy.props.StringProperty(name='5_q', description='', options={'HIDDEN'}, default='', subtype='FILE_PATH', maxlen=0)
    bpy.types.Scene.sna_q_005 = bpy.props.StringProperty(name='6_q', description='', options={'HIDDEN'}, default='', subtype='FILE_PATH', maxlen=0)
    bpy.types.Scene.sna_q_006 = bpy.props.StringProperty(name='7_q', description='', options={'HIDDEN'}, default='', subtype='FILE_PATH', maxlen=0)
    bpy.types.Scene.sna_q_007 = bpy.props.StringProperty(name='8_q', description='', options={'HIDDEN'}, default='', subtype='FILE_PATH', maxlen=0)
    bpy.types.Scene.sna_q_008 = bpy.props.StringProperty(name='9_q', description='', options={'HIDDEN'}, default='', subtype='FILE_PATH', maxlen=0)
    bpy.types.Scene.sna_q_009 = bpy.props.StringProperty(name='10_q', description='', options={'HIDDEN'}, default='', subtype='FILE_PATH', maxlen=0)
    bpy.types.Scene.sna_q_010 = bpy.props.StringProperty(name='11_q', description='', options={'HIDDEN'}, default='', subtype='FILE_PATH', maxlen=0)
    bpy.types.Scene.sna_q_011 = bpy.props.StringProperty(name='12_q', description='', options={'HIDDEN'}, default='', subtype='FILE_PATH', maxlen=0)
    bpy.types.Scene.sna_q_012 = bpy.props.StringProperty(name='13_q', description='', options={'HIDDEN'}, default='', subtype='FILE_PATH', maxlen=0)
    bpy.types.Scene.sna_q_013 = bpy.props.StringProperty(name='14_q', description='', options={'HIDDEN'}, default='', subtype='FILE_PATH', maxlen=0)
    bpy.types.Scene.sna_q_014 = bpy.props.StringProperty(name='15_q', description='', options={'HIDDEN'}, default='', subtype='FILE_PATH', maxlen=0)
    bpy.types.Scene.sna_q_015 = bpy.props.StringProperty(name='16_q', description='', options={'HIDDEN'}, default='', subtype='FILE_PATH', maxlen=0)
    bpy.types.Scene.sna_lujing_q = bpy.props.StringProperty(name='lujing_q', description='', options={'HIDDEN'}, default='', subtype='DIR_PATH', maxlen=0)
    bpy.types.Scene.sna_name_q = bpy.props.StringProperty(name='name_q', description='', options={'HIDDEN'}, default='', subtype='NONE', maxlen=0)
    bpy.types.Scene.sna_zidonghebing_q = bpy.props.BoolProperty(name='zidonghebing_q', description='', options={'HIDDEN'}, default=True)
    bpy.types.Scene.sna_hebingdaoxiao_q = bpy.props.IntProperty(name='hebingdaoxiao_q', description='', options={'HIDDEN'}, default=512, subtype='NONE', soft_min=128, soft_max=1024)
    
    
    bpy.utils.register_class(SNA_OT_My_Generic_Operator_7A4Df)
    bpy.utils.register_class(SNA_PT__80822)
    bpy.utils.register_class(SNA_OT_My_Generic_Operator_0B9B5)
    bpy.utils.register_class(SNA_OT_My_Generic_Operator_Fc2F6)

def unregister():
    
    global _icons
    bpy.utils.previews.remove(_icons)
    
    wm = bpy.context.window_manager
    kc = wm.keyconfigs.addon
    for km, kmi in addon_keymaps.values():
        km.keymap_items.remove(kmi)
    addon_keymaps.clear()
    del bpy.types.Scene.sna_hebingdaoxiao_q
    del bpy.types.Scene.sna_zidonghebing_q
    del bpy.types.Scene.sna_name_q
    del bpy.types.Scene.sna_lujing_q
    del bpy.types.Scene.sna_q_015
    del bpy.types.Scene.sna_q_014
    del bpy.types.Scene.sna_q_013
    del bpy.types.Scene.sna_q_012
    del bpy.types.Scene.sna_q_011
    del bpy.types.Scene.sna_q_010
    del bpy.types.Scene.sna_q_009
    del bpy.types.Scene.sna_q_008
    del bpy.types.Scene.sna_q_007
    del bpy.types.Scene.sna_q_006
    del bpy.types.Scene.sna_q_005
    del bpy.types.Scene.sna_q_004
    del bpy.types.Scene.sna_q_003
    del bpy.types.Scene.sna_q_002
    del bpy.types.Scene.sna_q_001
    del bpy.types.Scene.sna_q
    del bpy.types.Scene.sna_qiehuan_q
    del bpy.types.Scene.sna_dim_q
    del bpy.types.Scene.sna_pixel_q
    
    
    bpy.utils.unregister_class(SNA_OT_My_Generic_Operator_7A4Df)
    bpy.utils.unregister_class(SNA_PT__80822)
    bpy.utils.unregister_class(SNA_OT_My_Generic_Operator_0B9B5)
    bpy.utils.unregister_class(SNA_OT_My_Generic_Operator_Fc2F6)

