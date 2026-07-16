bl_info = {
    "name" : "贴图拆分",
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
from PIL import Image
from PIL import Image
from PIL import Image
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
visual_scripting = {}


def load_preview_icon(path):
    global _icons
    if not path in _icons:
        if os.path.exists(path):
            _icons.load(path, path, "IMAGE")
        else:
            return 0
    return _icons[path].icon_id

class SNA_PT_RGBA_3494E(bpy.types.Panel):
    bl_label = '拆分RGBA'
    bl_idname = 'SNA_PT_RGBA_3494E'
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
        col_B4A3B = layout.column(heading='', align=False)
        col_B4A3B.alert = False
        col_B4A3B.enabled = True
        col_B4A3B.use_property_split = False
        col_B4A3B.use_property_decorate = False
        col_B4A3B.scale_x = 1.0
        col_B4A3B.scale_y = 1.5
        col_B4A3B.alignment = 'Expand'.upper()
        op = col_B4A3B.operator('sna.my_generic_operator_d3995', text='拆分', icon_value=249, emboss=True, depress=False)
        layout.prop(bpy.context.scene, 'sna_in', text='文件', icon_value=0, emboss=True)
        box_D68B3 = layout.box()
        box_D68B3.alert = False
        box_D68B3.enabled = True
        box_D68B3.use_property_split = False
        box_D68B3.use_property_decorate = False
        box_D68B3.alignment = 'Expand'.upper()
        box_D68B3.scale_x = 1.0
        box_D68B3.scale_y = 1.0
        box_D68B3.template_icon(icon_value=load_preview_icon(bpy.path.abspath(bpy.context.scene.sna_in)), scale=8.0)
        
class SNA_OT_My_Generic_Operator_D3995(bpy.types.Operator):
    bl_idname = "sna.my_generic_operator_d3995"
    bl_label = "操作项"
    bl_description = ""
    bl_options = {"REGISTER", "UNDO"}
    
    
    @classmethod
    def poll(cls, context):
        return not False
    def execute(self, context):
        a = bpy.path.abspath(bpy.context.scene.sna_in)
        switch = None
        # 打开图像并检查Alpha通道
        img = Image.open(a)
        switch = img.mode.endswith('A')
        if switch:
            a = bpy.path.abspath(bpy.context.scene.sna_in)
            rr = bpy.path.abspath(bpy.context.scene.sna_in)[:int(len(os.path.splitext(bpy.path.abspath(bpy.context.scene.sna_in))[1]) * -1.0)] + '_R.tga'
            gg = bpy.path.abspath(bpy.context.scene.sna_in)[:int(len(os.path.splitext(bpy.path.abspath(bpy.context.scene.sna_in))[1]) * -1.0)] + '_G.tga'
            bb = bpy.path.abspath(bpy.context.scene.sna_in)[:int(len(os.path.splitext(bpy.path.abspath(bpy.context.scene.sna_in))[1]) * -1.0)] + '_B.tga'
            aa = bpy.path.abspath(bpy.context.scene.sna_in)[:int(len(os.path.splitext(bpy.path.abspath(bpy.context.scene.sna_in))[1]) * -1.0)] + '_A.tga'
            # 打开PNG图像
            image = Image.open(a)
            # 分离RGB通道
            r, g, b, a = image.split()
            # 保存单通道图像
            r.save(rr)
            g.save(gg)
            b.save(bb)
            a.save(aa)
            self.report({'INFO'}, message='拆分成功')
        else:
            a = bpy.path.abspath(bpy.context.scene.sna_in)
            rr = bpy.path.abspath(bpy.context.scene.sna_in)[:int(len(os.path.splitext(bpy.path.abspath(bpy.context.scene.sna_in))[1]) * -1.0)] + '_R.tga'
            gg = bpy.path.abspath(bpy.context.scene.sna_in)[:int(len(os.path.splitext(bpy.path.abspath(bpy.context.scene.sna_in))[1]) * -1.0)] + '_G.tga'
            bb = bpy.path.abspath(bpy.context.scene.sna_in)[:int(len(os.path.splitext(bpy.path.abspath(bpy.context.scene.sna_in))[1]) * -1.0)] + '_B.tga'
            # 打开PNG图像
            image = Image.open(a)
            # 分离RGB通道
            r, g, b = image.split()
            # 保存单通道图像
            r.save(rr)
            g.save(gg)
            b.save(bb)
            self.report({'INFO'}, message='拆分成功')
        return {"FINISHED"}
    
    def invoke(self, context, event):
        
        
        return self.execute(context)




def register():
    
    global _icons
    _icons = bpy.utils.previews.new()
    bpy.types.Scene.sna_in = bpy.props.StringProperty(name='in', description='', options={'HIDDEN'}, default='', subtype='FILE_PATH', maxlen=0)
    
    
    bpy.utils.register_class(SNA_PT_RGBA_3494E)
    bpy.utils.register_class(SNA_OT_My_Generic_Operator_D3995)

def unregister():
    
    global _icons
    bpy.utils.previews.remove(_icons)
    
    wm = bpy.context.window_manager
    kc = wm.keyconfigs.addon
    for km, kmi in addon_keymaps.values():
        km.keymap_items.remove(kmi)
    addon_keymaps.clear()
    del bpy.types.Scene.sna_in
    
    
    bpy.utils.unregister_class(SNA_PT_RGBA_3494E)
    bpy.utils.unregister_class(SNA_OT_My_Generic_Operator_D3995)

