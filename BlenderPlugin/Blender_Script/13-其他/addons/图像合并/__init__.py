bl_info = {
    "name" : "合并图像",
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

from PIL import Image
from PIL import Image
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
node_tree = {}


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

class SNA_OT_My_Generic_Operator_08F15(bpy.types.Operator):
    bl_idname = "sna.my_generic_operator_08f15"
    bl_label = "合并"
    bl_description = ""
    bl_options = {"REGISTER", "UNDO"}
    
    
    @classmethod
    def poll(cls, context):
        return not False
    def execute(self, context):
        if bpy.context.scene.sna_rgba_a_switch:
            out = os.path.join(bpy.path.abspath(bpy.context.scene.sna_out),bpy.context.scene.sna_rgba_name + '.tga')
            rgba_r = bpy.path.abspath(bpy.context.scene.sna_rgba_r)
            rgba_g = bpy.path.abspath(bpy.context.scene.sna_rgba_g)
            rgba_b = bpy.path.abspath(bpy.context.scene.sna_rgba_b)
            rgba_a = bpy.path.abspath(bpy.context.scene.sna_rgba_a)
            img_color = Image.open(rgba_r)
            img_gray = img_color.convert('L')
            r = img_gray
            img_color = Image.open(rgba_g)
            img_gray = img_color.convert('L')
            g = img_gray
            img_color = Image.open(rgba_b)
            img_gray = img_color.convert('L')
            b = img_gray
            img_color = Image.open(rgba_a)
            img_gray = img_color.convert('L')
            a = img_gray
            # 打开四个图像并合并RGBA通道
            img = Image.merge('RGBA', (r, g, b, a))
            # 保存合并后的图像
            img.save(out)
            self.report({'INFO'}, message='合并成功')
        else:
            out = os.path.join(bpy.path.abspath(bpy.context.scene.sna_out),bpy.context.scene.sna_rgba_name + '.tga')
            rgba_r = bpy.path.abspath(bpy.context.scene.sna_rgba_r)
            rgba_g = bpy.path.abspath(bpy.context.scene.sna_rgba_g)
            rgba_b = bpy.path.abspath(bpy.context.scene.sna_rgba_b)
            img_color = Image.open(rgba_r)
            img_gray = img_color.convert('L')
            r = img_gray
            img_color = Image.open(rgba_g)
            img_gray = img_color.convert('L')
            g = img_gray
            img_color = Image.open(rgba_b)
            img_gray = img_color.convert('L')
            b = img_gray
            img = Image.merge('RGB', (r, g, b))
            # 保存合并后的图像
            img.save(out)
            self.report({'INFO'}, message='合并成功')
        return {"FINISHED"}
    
    def invoke(self, context, event):
        
        
        return self.execute(context)
class SNA_PT_RGBA_1B919(bpy.types.Panel):
    bl_label = '合并RGBA'
    bl_idname = 'SNA_PT_RGBA_1B919'
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
        col_5AC4E = layout.column(heading='', align=False)
        col_5AC4E.alert = False
        col_5AC4E.enabled = True
        col_5AC4E.use_property_split = False
        col_5AC4E.use_property_decorate = False
        col_5AC4E.scale_x = 1.0
        col_5AC4E.scale_y = 1.5
        col_5AC4E.alignment = 'Expand'.upper()
        op = col_5AC4E.operator('sna.my_generic_operator_08f15', text='合并', icon_value=249, emboss=True, depress=False)
        col_59508 = layout.column(heading='', align=False)
        col_59508.alert = False
        col_59508.enabled = True
        col_59508.use_property_split = False
        col_59508.use_property_decorate = False
        col_59508.scale_x = 1.0
        col_59508.scale_y = 1.0
        col_59508.alignment = 'Expand'.upper()
        col_59508.prop(bpy.context.scene, 'sna_out', text='输出路径', icon_value=0, emboss=True)
        col_59508.prop(bpy.context.scene, 'sna_rgba_name', text='输出名称', icon_value=0, emboss=True)
        col_59508.prop(bpy.context.scene, 'sna_rgba_a_switch', text='A通道', icon_value=0, emboss=True)
        col_24414 = layout.column(heading='', align=True)
        col_24414.alert = False
        col_24414.enabled = True
        col_24414.use_property_split = False
        col_24414.use_property_decorate = False
        col_24414.scale_x = 1.0
        col_24414.scale_y = 1.0
        col_24414.alignment = 'Expand'.upper()
        split_E6991 = col_24414.split(factor=0.5, align=True)
        split_E6991.alert = False
        split_E6991.enabled = True
        split_E6991.use_property_split = False
        split_E6991.use_property_decorate = False
        split_E6991.scale_x = 1.0
        split_E6991.scale_y = 1.0
        split_E6991.alignment = 'Expand'.upper()
        box_9BF37 = split_E6991.box()
        box_9BF37.alert = False
        box_9BF37.enabled = True
        box_9BF37.use_property_split = False
        box_9BF37.use_property_decorate = False
        box_9BF37.alignment = 'Expand'.upper()
        box_9BF37.scale_x = 1.0
        box_9BF37.scale_y = 1.0
        col_65315 = box_9BF37.column(heading='', align=False)
        col_65315.alert = False
        col_65315.enabled = True
        col_65315.use_property_split = False
        col_65315.use_property_decorate = False
        col_65315.scale_x = 1.0
        col_65315.scale_y = 1.0
        col_65315.alignment = 'Expand'.upper()
        col_65315.label(text='R', icon_value=0)
        col_65315.template_icon(icon_value=load_preview_icon(bpy.path.abspath(bpy.context.scene.sna_rgba_r)), scale=6.909999847412109)
        col_65315.prop(bpy.context.scene, 'sna_rgba_r', text='', icon_value=0, emboss=True)
        box_97C70 = split_E6991.box()
        box_97C70.alert = False
        box_97C70.enabled = True
        box_97C70.use_property_split = False
        box_97C70.use_property_decorate = False
        box_97C70.alignment = 'Expand'.upper()
        box_97C70.scale_x = 1.0
        box_97C70.scale_y = 1.0
        col_3E9BB = box_97C70.column(heading='', align=False)
        col_3E9BB.alert = False
        col_3E9BB.enabled = True
        col_3E9BB.use_property_split = False
        col_3E9BB.use_property_decorate = False
        col_3E9BB.scale_x = 1.0
        col_3E9BB.scale_y = 1.0
        col_3E9BB.alignment = 'Expand'.upper()
        col_3E9BB.label(text='G', icon_value=0)
        col_3E9BB.template_icon(icon_value=load_preview_icon(bpy.path.abspath(bpy.context.scene.sna_rgba_g)), scale=6.909999847412109)
        col_3E9BB.prop(bpy.context.scene, 'sna_rgba_g', text='', icon_value=0, emboss=True)
        split_97804 = col_24414.split(factor=0.5, align=True)
        split_97804.alert = False
        split_97804.enabled = True
        split_97804.use_property_split = False
        split_97804.use_property_decorate = False
        split_97804.scale_x = 1.0
        split_97804.scale_y = 1.0
        split_97804.alignment = 'Expand'.upper()
        box_676AC = split_97804.box()
        box_676AC.alert = False
        box_676AC.enabled = True
        box_676AC.use_property_split = False
        box_676AC.use_property_decorate = False
        box_676AC.alignment = 'Expand'.upper()
        box_676AC.scale_x = 1.0
        box_676AC.scale_y = 1.0
        col_B7D4B = box_676AC.column(heading='', align=False)
        col_B7D4B.alert = False
        col_B7D4B.enabled = True
        col_B7D4B.use_property_split = False
        col_B7D4B.use_property_decorate = False
        col_B7D4B.scale_x = 1.0
        col_B7D4B.scale_y = 1.0
        col_B7D4B.alignment = 'Expand'.upper()
        col_B7D4B.label(text='B', icon_value=0)
        col_B7D4B.template_icon(icon_value=load_preview_icon(bpy.path.abspath(bpy.context.scene.sna_rgba_b)), scale=6.909999847412109)
        col_B7D4B.prop(bpy.context.scene, 'sna_rgba_b', text='', icon_value=0, emboss=True)
        box_02D10 = split_97804.box()
        box_02D10.alert = False
        box_02D10.enabled = True
        box_02D10.use_property_split = False
        box_02D10.use_property_decorate = False
        box_02D10.alignment = 'Expand'.upper()
        box_02D10.scale_x = 1.0
        box_02D10.scale_y = 1.0
        col_7B85D = box_02D10.column(heading='', align=False)
        col_7B85D.alert = False
        col_7B85D.enabled = bpy.context.scene.sna_rgba_a_switch
        col_7B85D.use_property_split = False
        col_7B85D.use_property_decorate = False
        col_7B85D.scale_x = 1.0
        col_7B85D.scale_y = 1.0
        col_7B85D.alignment = 'Expand'.upper()
        col_7B85D.label(text='A', icon_value=0)
        col_7B85D.template_icon(icon_value=load_preview_icon(bpy.path.abspath(bpy.context.scene.sna_rgba_a)), scale=6.909999847412109)
        col_7B85D.prop(bpy.context.scene, 'sna_rgba_a', text='', icon_value=0, emboss=True)










def register():
    
    global _icons
    _icons = bpy.utils.previews.new()
    bpy.types.Scene.sna_out = bpy.props.StringProperty(name='out', description='', options={'HIDDEN'}, default='', subtype='DIR_PATH', maxlen=0)
    bpy.types.Scene.sna_rgba_r = bpy.props.StringProperty(name='rgba_r', description='', options={'HIDDEN'}, default='', subtype='FILE_PATH', maxlen=0)
    bpy.types.Scene.sna_rgba_g = bpy.props.StringProperty(name='rgba_g', description='', options={'HIDDEN'}, default='', subtype='FILE_PATH', maxlen=0)
    bpy.types.Scene.sna_rgba_b = bpy.props.StringProperty(name='rgba_b', description='', options={'HIDDEN'}, default='', subtype='FILE_PATH', maxlen=0)
    bpy.types.Scene.sna_rgba_a = bpy.props.StringProperty(name='rgba_a', description='', options={'HIDDEN'}, default='', subtype='FILE_PATH', maxlen=0)
    bpy.types.Scene.sna_rgba_name = bpy.props.StringProperty(name='rgba_name', description='', options={'HIDDEN'}, default='', subtype='NONE', maxlen=0)
    bpy.types.Scene.sna_rgba_a_switch = bpy.props.BoolProperty(name='rgba_a_switch', description='', options={'HIDDEN'}, default=False)
    
    
    bpy.utils.register_class(SNA_OT_My_Generic_Operator_08F15)
    bpy.utils.register_class(SNA_PT_RGBA_1B919)

def unregister():
    
    global _icons
    bpy.utils.previews.remove(_icons)
    
    wm = bpy.context.window_manager
    kc = wm.keyconfigs.addon
    for km, kmi in addon_keymaps.values():
        km.keymap_items.remove(kmi)
    addon_keymaps.clear()
    del bpy.types.Scene.sna_rgba_a_switch
    del bpy.types.Scene.sna_rgba_name
    del bpy.types.Scene.sna_rgba_a
    del bpy.types.Scene.sna_rgba_b
    del bpy.types.Scene.sna_rgba_g
    del bpy.types.Scene.sna_rgba_r
    del bpy.types.Scene.sna_out
    
    
    bpy.utils.unregister_class(SNA_OT_My_Generic_Operator_08F15)
    bpy.utils.unregister_class(SNA_PT_RGBA_1B919)

