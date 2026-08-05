bl_info = {
    "name" : "可视化检查工具",
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

import math
import bpy
import numpy as np
import bpy
import bpy
from bpy.app.handlers import persistent
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
id = {}
lod = {'sna_lod': 0, }
pbr = {}
uv = {'sna_uv': False, 'sna_id': 1, }
uv_001 = {}
node_tree = {}
node_tree_001 = {}
node_tree = {}
node_tree_001 = {'sna_data_set': [], }
node_tree_001 = {}
node_tree_001 = {'sna_lod': False, 'sna_id': 1, 'sna_tongji': [], }
node_tree = {}


def sna_update_sna_g108_lod_switch_DE004(self, context):
    sna_updated_prop = self.sna_g108_lod_switch
    bpy.ops.sna.id_e72da('INVOKE_DEFAULT', )
def sna_update_sna_g108_modid_D68E5(self, context):
    sna_updated_prop = self.sna_g108_modid
    bpy.ops.sna.id_e72da('INVOKE_DEFAULT', )
def property_exists(prop_path):
    try:
        eval(prop_path)
        return True
    except:
        return False
def property_exists(prop_path):
    try:
        eval(prop_path)
        return True
    except:
        return False
def sna_update_sna_g108_1uaccuracy_69059(self, context):
    sna_updated_prop = self.sna_g108_1uaccuracy
    bpy.data.materials['Z-UV检查'].node_tree.nodes['1u'].outputs[0].default_value = sna_updated_prop
def sna_update_sna_g108_2uaccuracy_53502(self, context):
    sna_updated_prop = self.sna_g108_2uaccuracy
    bpy.data.materials['Z-UV检查'].node_tree.nodes['2u'].outputs[0].default_value = sna_updated_prop
def sna_update_sna_g108_bounding_box_9CDA1(self, context):
    sna_updated_prop = self.sna_g108_bounding_box
    for i_6F12C in range(len(bpy.data.objects)):
        if 'lod' in bpy.data.objects[i_6F12C].name:
            bpy.data.objects[i_6F12C].show_texture_space = sna_updated_prop
        else:
            pass
def sna_update_sna_g108_wireframe_150BE(self, context):
    sna_updated_prop = self.sna_g108_wireframe
    for i_9E275 in range(len(bpy.data.objects)):
        if 'lod' in bpy.data.objects[i_9E275].name:
            bpy.data.objects[i_9E275].show_wire = sna_updated_prop
        else:
            pass
_item_map = dict()
def make_enum_item(_id, name, descr, preview_id, uid):
    lookup = str(_id)+"\0"+str(name)+"\0"+str(descr)+"\0"+str(preview_id)+"\0"+str(uid)
    if not lookup in _item_map:
        _item_map[lookup] = (_id, name, descr, preview_id, uid)
    return _item_map[lookup]
def sna_update_sna_g108_datamat_AB115(self, context):
    sna_updated_prop = self.sna_g108_datamat
    bpy.context.active_object.material_slots[bpy.context.view_layer.objects.active.active_material_index].material = bpy.data.materials[sna_updated_prop]
def property_exists(prop_path):
    try:
        eval(prop_path)
        return True
    except:
        return False
def property_exists(prop_path):
    try:
        eval(prop_path)
        return True
    except:
        return False
def get_id_preview_id(data):
    if hasattr(data, "preview"):
        if not data.preview:
            data.preview_ensure()
        if hasattr(data.preview, "icon_id"):
            return data.preview.icon_id
    return 0
def property_exists(prop_path):
    try:
        eval(prop_path)
        return True
    except:
        return False
def property_exists(prop_path):
    try:
        eval(prop_path)
        return True
    except:
        return False
def property_exists(prop_path):
    try:
        eval(prop_path)
        return True
    except:
        return False
def property_exists(prop_path):
    try:
        eval(prop_path)
        return True
    except:
        return False
def property_exists(prop_path):
    try:
        eval(prop_path)
        return True
    except:
        return False
def property_exists(prop_path):
    try:
        eval(prop_path)
        return True
    except:
        return False
def property_exists(prop_path):
    try:
        eval(prop_path)
        return True
    except:
        return False
def property_exists(prop_path):
    try:
        eval(prop_path)
        return True
    except:
        return False
def property_exists(prop_path):
    try:
        eval(prop_path)
        return True
    except:
        return False
def property_exists(prop_path):
    try:
        eval(prop_path)
        return True
    except:
        return False
def property_exists(prop_path):
    try:
        eval(prop_path)
        return True
    except:
        return False
def property_exists(prop_path):
    try:
        eval(prop_path)
        return True
    except:
        return False
def property_exists(prop_path):
    try:
        eval(prop_path)
        return True
    except:
        return False
def property_exists(prop_path):
    try:
        eval(prop_path)
        return True
    except:
        return False
def property_exists(prop_path):
    try:
        eval(prop_path)
        return True
    except:
        return False
def property_exists(prop_path):
    try:
        eval(prop_path)
        return True
    except:
        return False
def property_exists(prop_path):
    try:
        eval(prop_path)
        return True
    except:
        return False
def property_exists(prop_path):
    try:
        eval(prop_path)
        return True
    except:
        return False
def property_exists(prop_path):
    try:
        eval(prop_path)
        return True
    except:
        return False
def sna_update_sna_g108_lod_switch_4C72D(self, context):
    sna_updated_prop = self.sna_g108_lod_switch
    if node_tree_001['sna_lod']:
        for i_BC81E in range(len(bpy.data.meshes)):
            for i_25A06 in range(len(bpy.data.meshes)):
                if '统计_' in str(bpy.data.meshes[i_25A06]):
                    bpy.context.blend_data.meshes.remove(mesh=bpy.data.meshes[i_25A06], )
                    break
                else:
                    pass
        for i_9528E in range(len(bpy.data.collections)):
            if '_pre' in str(bpy.data.collections[i_9528E]):
                bpy.ops.mesh.primitive_plane_add('INVOKE_DEFAULT', )
                if ('统计缓存' in bpy.data.collections):
                    a = int(bpy.data.collections.find('统计缓存') + 1)
                    bpy.ops.object.move_to_collection(collection_index=a)
                else:
                    bpy.ops.object.move_to_collection(collection_index=0, is_new=True, new_collection_name="统计缓存")
                bpy.context.active_object.name = '统计_面数_' + bpy.data.collections[i_9528E].name
                bpy.context.active_object.data.name = '统计_面数_' + bpy.data.collections[i_9528E].name
                bpy.context.active_object.location = bpy.data.collections[i_9528E].objects[0].location
                modifier_C5D35 = bpy.context.active_object.modifiers.new(name='z_面数统计', type='NODES', )
                bpy.context.active_object.modifiers['z_面数统计'].node_group = bpy.data.node_groups['z_面数统计']
                bpy.context.view_layer.objects.active.modifiers['z_面数统计']['Input_3'] = bpy.data.collections[i_9528E]
                if '_autophy' in str(bpy.data.collections[i_9528E].objects.keys()):
                    for i_5A740 in range(len(bpy.data.collections[i_9528E].objects)):
                        if '_autophy' in str(bpy.data.collections[i_9528E].objects[i_5A740]):
                            bpy.context.view_layer.objects.active.modifiers['z_面数统计']['Input_4'] = bpy.data.collections[i_9528E].objects[i_5A740]
                        else:
                            pass
                else:
                    pass
                node_tree_001['sna_tongji'] = []
                for i_4B3C2 in range(len(bpy.data.collections[i_9528E].objects)):
                    if '_lod' + str(bpy.context.scene.sna_g108_lod_switch) in bpy.data.collections[i_9528E].objects[i_4B3C2].name:
                        node_tree_001['sna_tongji'].append(len(bpy.data.collections[i_9528E].objects[i_4B3C2].data.polygons.values()))
                        bpy.context.view_layer.objects.active.modifiers['z_面数统计']['Input_2'] = 'Lod' + str(bpy.context.scene.sna_g108_lod_switch) + '=' + str(int(string_to_type(node_tree_001['sna_tongji'][0] if property_exists("node_tree_001['sna_tongji'][0]") else '0', float, 0) + string_to_type(node_tree_001['sna_tongji'][1] if property_exists("node_tree_001['sna_tongji'][1]") else '0', float, 0) + string_to_type(node_tree_001['sna_tongji'][2] if property_exists("node_tree_001['sna_tongji'][2]") else '0', float, 0) + string_to_type(node_tree_001['sna_tongji'][3] if property_exists("node_tree_001['sna_tongji'][3]") else '0', float, 0) + string_to_type(node_tree_001['sna_tongji'][4] if property_exists("node_tree_001['sna_tongji'][4]") else '0', float, 0) + string_to_type(node_tree_001['sna_tongji'][5] if property_exists("node_tree_001['sna_tongji'][5]") else '0', float, 0) + string_to_type(node_tree_001['sna_tongji'][6] if property_exists("node_tree_001['sna_tongji'][6]") else '0', float, 0) + string_to_type(node_tree_001['sna_tongji'][7] if property_exists("node_tree_001['sna_tongji'][7]") else '0', float, 0) + string_to_type(node_tree_001['sna_tongji'][8] if property_exists("node_tree_001['sna_tongji'][8]") else '0', float, 0) + string_to_type(node_tree_001['sna_tongji'][9] if property_exists("node_tree_001['sna_tongji'][9]") else '0', float, 0) + string_to_type(node_tree_001['sna_tongji'][10] if property_exists("node_tree_001['sna_tongji'][10]") else '0', float, 0) + string_to_type(node_tree_001['sna_tongji'][11] if property_exists("node_tree_001['sna_tongji'][11]") else '0', float, 0) + string_to_type(node_tree_001['sna_tongji'][12] if property_exists("node_tree_001['sna_tongji'][12]") else '0', float, 0) + string_to_type(node_tree_001['sna_tongji'][13] if property_exists("node_tree_001['sna_tongji'][13]") else '0', float, 0) + string_to_type(node_tree_001['sna_tongji'][14] if property_exists("node_tree_001['sna_tongji'][14]") else '0', float, 0) + string_to_type(node_tree_001['sna_tongji'][15] if property_exists("node_tree_001['sna_tongji'][15]") else '0', float, 0)))
                    else:
                        pass
            else:
                pass
    else:
        pass
def property_exists(prop_path):
    try:
        eval(prop_path)
        return True
    except:
        return False
def property_exists(prop_path):
    try:
        eval(prop_path)
        return True
    except:
        return False
def property_exists(prop_path):
    try:
        eval(prop_path)
        return True
    except:
        return False
def property_exists(prop_path):
    try:
        eval(prop_path)
        return True
    except:
        return False
def property_exists(prop_path):
    try:
        eval(prop_path)
        return True
    except:
        return False
def property_exists(prop_path):
    try:
        eval(prop_path)
        return True
    except:
        return False
def property_exists(prop_path):
    try:
        eval(prop_path)
        return True
    except:
        return False
def property_exists(prop_path):
    try:
        eval(prop_path)
        return True
    except:
        return False
def property_exists(prop_path):
    try:
        eval(prop_path)
        return True
    except:
        return False
def property_exists(prop_path):
    try:
        eval(prop_path)
        return True
    except:
        return False
def property_exists(prop_path):
    try:
        eval(prop_path)
        return True
    except:
        return False
def property_exists(prop_path):
    try:
        eval(prop_path)
        return True
    except:
        return False
def property_exists(prop_path):
    try:
        eval(prop_path)
        return True
    except:
        return False
def property_exists(prop_path):
    try:
        eval(prop_path)
        return True
    except:
        return False
def property_exists(prop_path):
    try:
        eval(prop_path)
        return True
    except:
        return False
def property_exists(prop_path):
    try:
        eval(prop_path)
        return True
    except:
        return False

def sna_id_2FC3D(layout_function, ):
    pass
    box_F1D07 = layout_function.box()
    box_F1D07.alert = False
    box_F1D07.enabled = True
    box_F1D07.use_property_split = False
    box_F1D07.use_property_decorate = False
    box_F1D07.alignment = 'Expand'.upper()
    box_F1D07.scale_x = 1.0
    box_F1D07.scale_y = 1.0
    col_7E6A3 = box_F1D07.column(heading='', align=False)
    col_7E6A3.alert = False
    col_7E6A3.enabled = True
    col_7E6A3.use_property_split = False
    col_7E6A3.use_property_decorate = False
    col_7E6A3.scale_x = 1.0
    col_7E6A3.scale_y = 1.0
    col_7E6A3.alignment = 'Expand'.upper()
    split_AB8BA = col_7E6A3.split(factor=0.5, align=True)
    split_AB8BA.alert = False
    split_AB8BA.enabled = True
    split_AB8BA.use_property_split = False
    split_AB8BA.use_property_decorate = False
    split_AB8BA.scale_x = 1.0
    split_AB8BA.scale_y = 1.5
    split_AB8BA.alignment = 'Expand'.upper()
    op = split_AB8BA.operator('sna.my_generic_operator_95c4a', text='开启', icon_value=0, emboss=True, depress=bpy.context.scene.sna_g108_modidswitch)
    op = split_AB8BA.operator('sna.my_generic_operator_3c6ec', text='关闭', icon_value=0, emboss=True, depress=False)
    split_8E216 = col_7E6A3.split(factor=0.5, align=True)
    split_8E216.alert = False
    split_8E216.enabled = True
    split_8E216.use_property_split = False
    split_8E216.use_property_decorate = False
    split_8E216.scale_x = 1.0
    split_8E216.scale_y = 1.5
    split_8E216.alignment = 'Expand'.upper()
    col_6D3D6 = split_8E216.column(heading='', align=False)
    col_6D3D6.alert = False
    col_6D3D6.enabled = True
    col_6D3D6.use_property_split = False
    col_6D3D6.use_property_decorate = False
    col_6D3D6.scale_x = 1.0
    col_6D3D6.scale_y = 1.0
    col_6D3D6.alignment = 'Expand'.upper()
    col_6D3D6.label(text='当前显示：' + '_c' + str(bpy.context.scene.sna_g108_modid) + '_lod' + str(bpy.context.scene.sna_g108_lod_switch), icon_value=0)
    split_8E216.prop(bpy.context.scene, 'sna_g108_modid', text='C', icon_value=0, emboss=True)
class SNA_OT_Z_Id_1B5Df(bpy.types.Operator):
    bl_idname = "sna.z_id_1b5df"
    bl_label = "移除z_id遮罩"
    bl_description = ""
    bl_options = {"REGISTER", "UNDO"}
    
    
    @classmethod
    def poll(cls, context):
        return not False
    def execute(self, context):
        for i_9FFD6 in range(len(bpy.data.collections)):
            if '_pre' in bpy.data.collections[i_9FFD6].name:
                for i_61508 in range(len(bpy.data.collections[i_9FFD6].objects)):
                    if 'z_id遮罩' in str(bpy.data.collections[i_9FFD6].objects[i_61508].modifiers.keys()):
                        bpy.data.collections[i_9FFD6].objects[i_61508].modifiers.remove(modifier=bpy.data.collections[i_9FFD6].objects[i_61508].modifiers['z_id遮罩'], )
                    else:
                        pass
            else:
                pass
        return {"FINISHED"}
    
    def invoke(self, context, event):
        
        
        return self.execute(context)
class SNA_OT_Id_E72Da(bpy.types.Operator):
    bl_idname = "sna.id_e72da"
    bl_label = "模型id切换"
    bl_description = ""
    bl_options = {"REGISTER", "UNDO"}
    
    
    @classmethod
    def poll(cls, context):
        return not False
    def execute(self, context):
        if bpy.context.scene.sna_g108_modidswitch:
            bpy.ops.sna.z_id_1b5df('INVOKE_DEFAULT', )
            for i_623AF in range(len(bpy.data.collections)):
                if '_pre' in bpy.data.collections[i_623AF].name:
                    for i_8302E in range(len(bpy.data.collections[i_623AF].objects)):
                        if  not '_c' + str(bpy.context.scene.sna_g108_modid) + '_' in bpy.data.collections[i_623AF].objects[i_8302E].name and '_lod' + str(bpy.context.scene.sna_g108_lod_switch) in bpy.data.collections[i_623AF].objects[i_8302E].name:
                            modifier_AE456 = bpy.data.collections[i_623AF].objects[i_8302E].modifiers.new(name='z_id遮罩', type='NODES', )
                            modifier_AE456.node_group = bpy.data.node_groups['z_id遮罩']
                        else:
                            pass
                else:
                    pass
        else:
            pass
        return {"FINISHED"}
    
    def invoke(self, context, event):
        
        
        return self.execute(context)
class SNA_OT_My_Generic_Operator_3C6Ec(bpy.types.Operator):
    bl_idname = "sna.my_generic_operator_3c6ec"
    bl_label = "关闭"
    bl_description = ""
    bl_options = {"REGISTER", "UNDO"}
    
    
    @classmethod
    def poll(cls, context):
        return not False
    def execute(self, context):
        bpy.context.scene.sna_g108_modidswitch = False
        bpy.ops.sna.z_id_1b5df('INVOKE_DEFAULT', )
        return {"FINISHED"}
    
    def invoke(self, context, event):
        
        
        return self.execute(context)
class SNA_OT_My_Generic_Operator_95C4A(bpy.types.Operator):
    bl_idname = "sna.my_generic_operator_95c4a"
    bl_label = "开启"
    bl_description = ""
    bl_options = {"REGISTER", "UNDO"}
    
    
    @classmethod
    def poll(cls, context):
        return not False
    def execute(self, context):
        bpy.context.scene.sna_g108_modidswitch = True
        bpy.ops.sna.id_e72da('INVOKE_DEFAULT', )
        return {"FINISHED"}
    
    def invoke(self, context, event):
        
        
        return self.execute(context)
class SNA_OT_Lod1_5De1D(bpy.types.Operator):
    bl_idname = "sna.lod1_5de1d"
    bl_label = "lod1"
    bl_description = ""
    bl_options = {"REGISTER", "UNDO"}
    
    
    @classmethod
    def poll(cls, context):
        return not False
    def execute(self, context):
        for i_0004F in range(len(bpy.data.objects)):
            bpy.data.objects[i_0004F].hide_viewport = '_lod0' in str(bpy.data.objects[i_0004F].name) or '_lod2' in str(bpy.data.objects[i_0004F].name) or '_lod3' in str(bpy.data.objects[i_0004F].name) or '_autophy' in str(bpy.data.objects[i_0004F].name)
            bpy.data.objects[i_0004F].hide_render = '_lod0' in str(bpy.data.objects[i_0004F].name) or '_lod2' in str(bpy.data.objects[i_0004F].name) or '_lod3' in str(bpy.data.objects[i_0004F].name) or '_autophy' in str(bpy.data.objects[i_0004F].name)
        bpy.context.scene.sna_g108_lod_switch = 1
        bpy.ops.sna.uv_62070('INVOKE_DEFAULT', )
        return {"FINISHED"}
    
    def invoke(self, context, event):
        
        
        return self.execute(context)
class SNA_OT_Lod0_979B2(bpy.types.Operator):
    bl_idname = "sna.lod0_979b2"
    bl_label = "lod0"
    bl_description = ""
    bl_options = {"REGISTER", "UNDO"}
    
    
    @classmethod
    def poll(cls, context):
        return not False
    def execute(self, context):
        for i_8CE26 in range(len(bpy.data.objects)):
            bpy.data.objects[i_8CE26].hide_viewport = '_lod1' in str(bpy.data.objects[i_8CE26].name) or '_lod2' in str(bpy.data.objects[i_8CE26].name) or '_lod3' in str(bpy.data.objects[i_8CE26].name) or '_autophy' in str(bpy.data.objects[i_8CE26].name)
            bpy.data.objects[i_8CE26].hide_render = '_lod1' in str(bpy.data.objects[i_8CE26].name) or '_lod2' in str(bpy.data.objects[i_8CE26].name) or '_lod3' in str(bpy.data.objects[i_8CE26].name) or '_autophy' in str(bpy.data.objects[i_8CE26].name)
        bpy.context.scene.sna_g108_lod_switch = 0
        bpy.ops.sna.uv_62070('INVOKE_DEFAULT', )
        return {"FINISHED"}
    
    def invoke(self, context, event):
        
        
        return self.execute(context)
class SNA_OT_Lod2_5Ccf6(bpy.types.Operator):
    bl_idname = "sna.lod2_5ccf6"
    bl_label = "lod2"
    bl_description = ""
    bl_options = {"REGISTER", "UNDO"}
    
    
    @classmethod
    def poll(cls, context):
        return not False
    def execute(self, context):
        for i_0A714 in range(len(bpy.data.objects)):
            bpy.data.objects[i_0A714].hide_viewport = '_lod0' in str(bpy.data.objects[i_0A714].name) or '_lod1' in str(bpy.data.objects[i_0A714].name) or '_lod3' in str(bpy.data.objects[i_0A714].name) or '_autophy' in str(bpy.data.objects[i_0A714].name)
            bpy.data.objects[i_0A714].hide_render = '_lod0' in str(bpy.data.objects[i_0A714].name) or '_lod1' in str(bpy.data.objects[i_0A714].name) or '_lod3' in str(bpy.data.objects[i_0A714].name) or '_autophy' in str(bpy.data.objects[i_0A714].name)
        bpy.context.scene.sna_g108_lod_switch = 2
        bpy.ops.sna.uv_62070('INVOKE_DEFAULT', )
        return {"FINISHED"}
    
    def invoke(self, context, event):
        
        
        return self.execute(context)
class SNA_OT_Lod3_497C0(bpy.types.Operator):
    bl_idname = "sna.lod3_497c0"
    bl_label = "lod3"
    bl_description = ""
    bl_options = {"REGISTER", "UNDO"}
    
    
    @classmethod
    def poll(cls, context):
        return not False
    def execute(self, context):
        for i_EC75E in range(len(bpy.data.objects)):
            bpy.data.objects[i_EC75E].hide_viewport = '_lod0' in str(bpy.data.objects[i_EC75E].name) or '_lod1' in str(bpy.data.objects[i_EC75E].name) or '_lod2' in str(bpy.data.objects[i_EC75E].name) or '_autophy' in str(bpy.data.objects[i_EC75E].name)
            bpy.data.objects[i_EC75E].hide_render = '_lod0' in str(bpy.data.objects[i_EC75E].name) or '_lod1' in str(bpy.data.objects[i_EC75E].name) or '_lod2' in str(bpy.data.objects[i_EC75E].name) or '_autophy' in str(bpy.data.objects[i_EC75E].name)
        bpy.context.scene.sna_g108_lod_switch = 3
        bpy.ops.sna.uv_62070('INVOKE_DEFAULT', )
        return {"FINISHED"}
    
    def invoke(self, context, event):
        
        
        return self.execute(context)
class SNA_OT_My_Generic_Operator_3684F(bpy.types.Operator):
    bl_idname = "sna.my_generic_operator_3684f"
    bl_label = "全部显示"
    bl_description = ""
    bl_options = {"REGISTER", "UNDO"}
    
    
    @classmethod
    def poll(cls, context):
        return not False
    def execute(self, context):
        for i_57413 in range(len(bpy.data.objects)):
            bpy.data.objects[i_57413].hide_viewport = False
            bpy.data.objects[i_57413].hide_render = False
        return {"FINISHED"}
    
    def invoke(self, context, event):
        
        
        return self.execute(context)
def sna_lod_29A25(layout_function, ):
    pass
    box_092AE = layout_function.box()
    box_092AE.alert = False
    box_092AE.enabled = True
    box_092AE.use_property_split = False
    box_092AE.use_property_decorate = False
    box_092AE.alignment = 'Expand'.upper()
    box_092AE.scale_x = 1.0
    box_092AE.scale_y = 1.0
    col_AC459 = box_092AE.column(heading='', align=False)
    col_AC459.alert = False
    col_AC459.enabled = True
    col_AC459.use_property_split = False
    col_AC459.use_property_decorate = False
    col_AC459.scale_x = 1.0
    col_AC459.scale_y = 1.2000000476837158
    col_AC459.alignment = 'Expand'.upper()
    op = col_AC459.operator('sna.my_generic_operator_3684f', text='全部显示', icon_value=0, emboss=True, depress=False)
    op = col_AC459.operator('sna.lod0_979b2', text='lod0', icon_value=0, emboss=True, depress=False)
    op = col_AC459.operator('sna.lod1_5de1d', text='lod1', icon_value=0, emboss=True, depress=False)
    op = col_AC459.operator('sna.lod2_5ccf6', text='lod2', icon_value=0, emboss=True, depress=False)
    op = col_AC459.operator('sna.lod3_497c0', text='lod3', icon_value=0, emboss=True, depress=False)
    layout_function = col_AC459
    sna_func_396EB(layout_function, )
class SNA_OT_Ao_Cccb1(bpy.types.Operator):
    bl_idname = "sna.ao_cccb1"
    bl_label = "AO"
    bl_description = ""
    bl_options = {"REGISTER", "UNDO"}
    
    
    @classmethod
    def poll(cls, context):
        return not False
    def execute(self, context):
        if property_exists("bpy.data.node_groups['Z_顶点混合材质'].nodes['pbr切换'].outputs[0].default_value"):
            bpy.data.node_groups['Z_顶点混合材质'].nodes['pbr切换'].outputs[0].default_value = 4.0
        else:
            pass
        if property_exists("bpy.data.node_groups['Z_PBR_材质'].nodes['pbr切换'].outputs[0].default_value"):
            bpy.data.node_groups['Z_PBR_材质'].nodes['pbr切换'].outputs[0].default_value = 4.0
        else:
            pass
        return {"FINISHED"}
    
    def invoke(self, context, event):
        
        
        return self.execute(context)
def sna_pbr_92959(layout_function, ):
    pass
    box_FA6E7 = layout_function.box()
    box_FA6E7.alert = False
    box_FA6E7.enabled = True
    box_FA6E7.use_property_split = False
    box_FA6E7.use_property_decorate = False
    box_FA6E7.alignment = 'Expand'.upper()
    box_FA6E7.scale_x = 1.0
    box_FA6E7.scale_y = 1.0
    col_54B8D = box_FA6E7.column(heading='', align=False)
    col_54B8D.alert = False
    col_54B8D.enabled = True
    col_54B8D.use_property_split = False
    col_54B8D.use_property_decorate = False
    col_54B8D.scale_x = 1.0
    col_54B8D.scale_y = 1.0
    col_54B8D.alignment = 'Expand'.upper()
    col_54752 = col_54B8D.column(heading='', align=False)
    col_54752.alert = False
    col_54752.enabled = True
    col_54752.use_property_split = False
    col_54752.use_property_decorate = False
    col_54752.scale_x = 1.0
    col_54752.scale_y = 1.5
    col_54752.alignment = 'Expand'.upper()
    op = col_54752.operator('sna.pbr_0d0f8', text='PBR默认', icon_value=0, emboss=True, depress=False)
    split_6AFCF = col_54B8D.split(factor=0.5, align=True)
    split_6AFCF.alert = False
    split_6AFCF.enabled = True
    split_6AFCF.use_property_split = False
    split_6AFCF.use_property_decorate = False
    split_6AFCF.scale_x = 1.0
    split_6AFCF.scale_y = 1.2000000476837158
    split_6AFCF.alignment = 'Expand'.upper()
    col_72A1C = split_6AFCF.column(heading='', align=True)
    col_72A1C.alert = False
    col_72A1C.enabled = True
    col_72A1C.use_property_split = False
    col_72A1C.use_property_decorate = False
    col_72A1C.scale_x = 1.0
    col_72A1C.scale_y = 1.0
    col_72A1C.alignment = 'Expand'.upper()
    op = col_72A1C.operator('sna.my_generic_operator_91d9b', text='固有色', icon_value=0, emboss=True, depress=False)
    op = col_72A1C.operator('sna.my_generic_operator_2965d', text='粗糙度', icon_value=0, emboss=True, depress=False)
    op = col_72A1C.operator('sna.my_generic_operator_cf834', text='金属度', icon_value=0, emboss=True, depress=False)
    col_57A11 = split_6AFCF.column(heading='', align=True)
    col_57A11.alert = False
    col_57A11.enabled = True
    col_57A11.use_property_split = False
    col_57A11.use_property_decorate = False
    col_57A11.scale_x = 1.0
    col_57A11.scale_y = 1.0
    col_57A11.alignment = 'Expand'.upper()
    op = col_57A11.operator('sna.ao_cccb1', text='AO', icon_value=0, emboss=True, depress=False)
    op = col_57A11.operator('sna.my_generic_operator_359f7', text='法线', icon_value=0, emboss=True, depress=False)
    op = col_57A11.operator('sna.my_generic_operator_2307d', text='顶点色', icon_value=0, emboss=True, depress=False)
class SNA_OT_My_Generic_Operator_91D9B(bpy.types.Operator):
    bl_idname = "sna.my_generic_operator_91d9b"
    bl_label = "固有色"
    bl_description = ""
    bl_options = {"REGISTER", "UNDO"}
    
    
    @classmethod
    def poll(cls, context):
        return not False
    def execute(self, context):
        if property_exists("bpy.data.node_groups['Z_顶点混合材质'].nodes['pbr切换'].outputs[0].default_value"):
            bpy.data.node_groups['Z_顶点混合材质'].nodes['pbr切换'].outputs[0].default_value = 1.0
        else:
            pass
        if property_exists("bpy.data.node_groups['Z_PBR_材质'].nodes['pbr切换'].outputs[0].default_value"):
            bpy.data.node_groups['Z_PBR_材质'].nodes['pbr切换'].outputs[0].default_value = 1.0
        else:
            pass
        return {"FINISHED"}
    
    def invoke(self, context, event):
        
        
        return self.execute(context)
class SNA_OT_My_Generic_Operator_2965D(bpy.types.Operator):
    bl_idname = "sna.my_generic_operator_2965d"
    bl_label = "粗糙度"
    bl_description = ""
    bl_options = {"REGISTER", "UNDO"}
    
    
    @classmethod
    def poll(cls, context):
        return not False
    def execute(self, context):
        if property_exists("bpy.data.node_groups['Z_顶点混合材质'].nodes['pbr切换'].outputs[0].default_value"):
            bpy.data.node_groups['Z_顶点混合材质'].nodes['pbr切换'].outputs[0].default_value = 2.0
        else:
            pass
        if property_exists("bpy.data.node_groups['Z_PBR_材质'].nodes['pbr切换'].outputs[0].default_value"):
            bpy.data.node_groups['Z_PBR_材质'].nodes['pbr切换'].outputs[0].default_value = 2.0
        else:
            pass
        return {"FINISHED"}
    
    def invoke(self, context, event):
        
        
        return self.execute(context)
class SNA_OT_My_Generic_Operator_Cf834(bpy.types.Operator):
    bl_idname = "sna.my_generic_operator_cf834"
    bl_label = "金属度"
    bl_description = ""
    bl_options = {"REGISTER", "UNDO"}
    
    
    @classmethod
    def poll(cls, context):
        return not False
    def execute(self, context):
        if property_exists("bpy.data.node_groups['Z_顶点混合材质'].nodes['pbr切换'].outputs[0].default_value"):
            bpy.data.node_groups['Z_顶点混合材质'].nodes['pbr切换'].outputs[0].default_value = 3.0
        else:
            pass
        if property_exists("bpy.data.node_groups['Z_PBR_材质'].nodes['pbr切换'].outputs[0].default_value"):
            bpy.data.node_groups['Z_PBR_材质'].nodes['pbr切换'].outputs[0].default_value = 3.0
        else:
            pass
        return {"FINISHED"}
    
    def invoke(self, context, event):
        
        
        return self.execute(context)
class SNA_OT_My_Generic_Operator_359F7(bpy.types.Operator):
    bl_idname = "sna.my_generic_operator_359f7"
    bl_label = "法线"
    bl_description = ""
    bl_options = {"REGISTER", "UNDO"}
    
    
    @classmethod
    def poll(cls, context):
        return not False
    def execute(self, context):
        if property_exists("bpy.data.node_groups['Z_顶点混合材质'].nodes['pbr切换'].outputs[0].default_value"):
            bpy.data.node_groups['Z_顶点混合材质'].nodes['pbr切换'].outputs[0].default_value = 5.0
        else:
            pass
        if property_exists("bpy.data.node_groups['Z_PBR_材质'].nodes['pbr切换'].outputs[0].default_value"):
            bpy.data.node_groups['Z_PBR_材质'].nodes['pbr切换'].outputs[0].default_value = 5.0
        else:
            pass
        return {"FINISHED"}
    
    def invoke(self, context, event):
        
        
        return self.execute(context)
class SNA_OT_My_Generic_Operator_2307D(bpy.types.Operator):
    bl_idname = "sna.my_generic_operator_2307d"
    bl_label = "顶点色"
    bl_description = ""
    bl_options = {"REGISTER", "UNDO"}
    
    
    @classmethod
    def poll(cls, context):
        return not False
    def execute(self, context):
        if property_exists("bpy.data.node_groups['Z_顶点混合材质'].nodes['pbr切换'].outputs[0].default_value"):
            bpy.data.node_groups['Z_顶点混合材质'].nodes['pbr切换'].outputs[0].default_value = 6.0
        else:
            pass
        if property_exists("bpy.data.node_groups['Z_PBR_材质'].nodes['pbr切换'].outputs[0].default_value"):
            bpy.data.node_groups['Z_PBR_材质'].nodes['pbr切换'].outputs[0].default_value = 6.0
        else:
            pass
        return {"FINISHED"}
    
    def invoke(self, context, event):
        
        
        return self.execute(context)
class SNA_OT_Pbr_0D0F8(bpy.types.Operator):
    bl_idname = "sna.pbr_0d0f8"
    bl_label = "PBR默认"
    bl_description = ""
    bl_options = {"REGISTER", "UNDO"}
    
    
    @classmethod
    def poll(cls, context):
        return not False
    def execute(self, context):
        if property_exists("bpy.data.node_groups['Z_顶点混合材质'].nodes['pbr切换'].outputs[0].default_value"):
            bpy.data.node_groups['Z_顶点混合材质'].nodes['pbr切换'].outputs[0].default_value = 0.0
        else:
            pass
        if property_exists("bpy.data.node_groups['Z_PBR_材质'].nodes['pbr切换'].outputs[0].default_value"):
            bpy.data.node_groups['Z_PBR_材质'].nodes['pbr切换'].outputs[0].default_value = 0.0
        else:
            pass
        return {"FINISHED"}
    
    def invoke(self, context, event):
        
        
        return self.execute(context)
class SNA_OT_My_Generic_Operator_35D4E(bpy.types.Operator):
    bl_idname = "sna.my_generic_operator_35d4e"
    bl_label = "线面"
    bl_description = ""
    bl_options = {"REGISTER", "UNDO"}
    
    
    @classmethod
    def poll(cls, context):
        return not False
    def execute(self, context):
        bpy.data.node_groups['z_uv可视化'].nodes['uv显示模式'].outputs[0].default_value = 1.0
        return {"FINISHED"}
    
    def invoke(self, context, event):
        
        
        return self.execute(context)
class SNA_OT_My_Generic_Operator_27112(bpy.types.Operator):
    bl_idname = "sna.my_generic_operator_27112"
    bl_label = "面"
    bl_description = ""
    bl_options = {"REGISTER", "UNDO"}
    
    
    @classmethod
    def poll(cls, context):
        return not False
    def execute(self, context):
        bpy.data.node_groups['z_uv可视化'].nodes['uv显示模式'].outputs[0].default_value = 3.0
        return {"FINISHED"}
    
    def invoke(self, context, event):
        
        
        return self.execute(context)
class SNA_OT_U_52F33(bpy.types.Operator):
    bl_idname = "sna.u_52f33"
    bl_label = "1u"
    bl_description = ""
    bl_options = {"REGISTER", "UNDO"}
    
    
    @classmethod
    def poll(cls, context):
        return not False
    def execute(self, context):
        bpy.data.node_groups['z_uv可视化'].nodes['UV通道切换'].inputs[0].default_value = False
        uv['sna_uv'] = True
        bpy.ops.sna.uv_62070('INVOKE_DEFAULT', )
        return {"FINISHED"}
    
    def invoke(self, context, event):
        
        
        return self.execute(context)
class SNA_OT_U_74C11(bpy.types.Operator):
    bl_idname = "sna.u_74c11"
    bl_label = "2u"
    bl_description = ""
    bl_options = {"REGISTER", "UNDO"}
    
    
    @classmethod
    def poll(cls, context):
        return not False
    def execute(self, context):
        bpy.data.node_groups['z_uv可视化'].nodes['UV通道切换'].inputs[0].default_value = True
        uv['sna_uv'] = True
        bpy.ops.sna.uv_62070('INVOKE_DEFAULT', )
        return {"FINISHED"}
    
    def invoke(self, context, event):
        
        
        return self.execute(context)
def sna_uv_FD89B(layout_function, ):
    pass
    box_D794B = layout_function.box()
    box_D794B.alert = False
    box_D794B.enabled = True
    box_D794B.use_property_split = False
    box_D794B.use_property_decorate = False
    box_D794B.alignment = 'Expand'.upper()
    box_D794B.scale_x = 1.0
    box_D794B.scale_y = 1.0
    col_03FD5 = box_D794B.column(heading='', align=False)
    col_03FD5.alert = False
    col_03FD5.enabled = True
    col_03FD5.use_property_split = False
    col_03FD5.use_property_decorate = False
    col_03FD5.scale_x = 1.0
    col_03FD5.scale_y = 1.2000000476837158
    col_03FD5.alignment = 'Expand'.upper()
    col_7941E = col_03FD5.column(heading='', align=False)
    col_7941E.alert = False
    col_7941E.enabled = True
    col_7941E.use_property_split = False
    col_7941E.use_property_decorate = False
    col_7941E.scale_x = 1.0
    col_7941E.scale_y = 1.2999999523162842
    col_7941E.alignment = 'Expand'.upper()
    op = col_7941E.operator('sna.uv_e31ce', text='关闭UV可视化', icon_value=0, emboss=True, depress=False)
    split_D787A = col_03FD5.split(factor=0.5, align=True)
    split_D787A.alert = False
    split_D787A.enabled = True
    split_D787A.use_property_split = False
    split_D787A.use_property_decorate = False
    split_D787A.scale_x = 1.0
    split_D787A.scale_y = 1.0
    split_D787A.alignment = 'Expand'.upper()
    op = split_D787A.operator('sna.u_52f33', text='1U', icon_value=0, emboss=True, depress=False)
    op = split_D787A.operator('sna.u_74c11', text='2U', icon_value=0, emboss=True, depress=False)
    row_EC67F = col_03FD5.row(heading='', align=True)
    row_EC67F.alert = False
    row_EC67F.enabled = True
    row_EC67F.use_property_split = False
    row_EC67F.use_property_decorate = False
    row_EC67F.scale_x = 1.0
    row_EC67F.scale_y = 1.0
    row_EC67F.alignment = 'Expand'.upper()
    op = row_EC67F.operator('sna.my_generic_operator_b6304', text='线', icon_value=0, emboss=True, depress=False)
    op = row_EC67F.operator('sna.my_generic_operator_35d4e', text='线面', icon_value=0, emboss=True, depress=False)
    op = row_EC67F.operator('sna.my_generic_operator_27112', text='面', icon_value=0, emboss=True, depress=False)
    col_58E84 = col_03FD5.column(heading='', align=True)
    col_58E84.alert = False
    col_58E84.enabled = True
    col_58E84.use_property_split = False
    col_58E84.use_property_decorate = False
    col_58E84.scale_x = 1.0
    col_58E84.scale_y = 1.0
    col_58E84.alignment = 'Expand'.upper()
    row_50254 = col_58E84.row(heading='', align=True)
    row_50254.alert = False
    row_50254.enabled = True
    row_50254.use_property_split = False
    row_50254.use_property_decorate = False
    row_50254.scale_x = 1.0
    row_50254.scale_y = 1.0
    row_50254.alignment = 'Expand'.upper()
    for i_9707D in range(8):
        op = row_50254.operator('sna.id_36dc1', text='c' + str(int(i_9707D + 1.0)), icon_value=0, emboss=True, depress=int(i_9707D + 1.0) == uv['sna_id'])
        op.sna_id = int(i_9707D + 1.0)
    row_B207F = col_58E84.row(heading='', align=True)
    row_B207F.alert = False
    row_B207F.enabled = True
    row_B207F.use_property_split = False
    row_B207F.use_property_decorate = False
    row_B207F.scale_x = 1.0
    row_B207F.scale_y = 1.0
    row_B207F.alignment = 'Expand'.upper()
    for i_64209 in range(8):
        op = row_B207F.operator('sna.id_36dc1', text='c' + str(int(i_64209 + 9.0)), icon_value=0, emboss=True, depress=int(i_64209 + 9.0) == uv['sna_id'])
        op.sna_id = int(i_64209 + 9.0)
class SNA_OT_My_Generic_Operator_B6304(bpy.types.Operator):
    bl_idname = "sna.my_generic_operator_b6304"
    bl_label = "线"
    bl_description = ""
    bl_options = {"REGISTER", "UNDO"}
    
    
    @classmethod
    def poll(cls, context):
        return not False
    def execute(self, context):
        bpy.data.node_groups['z_uv可视化'].nodes['uv显示模式'].outputs[0].default_value = 0.0
        return {"FINISHED"}
    
    def invoke(self, context, event):
        
        
        return self.execute(context)
class SNA_OT_Uv_62070(bpy.types.Operator):
    bl_idname = "sna.uv_62070"
    bl_label = "开启uv可视"
    bl_description = ""
    bl_options = {"REGISTER", "UNDO"}
    
    
    @classmethod
    def poll(cls, context):
        return not False
    def execute(self, context):
        if uv['sna_uv']:
            bpy.ops.sna.uv_176be('INVOKE_DEFAULT', )
            for i_7E470 in range(len(bpy.data.collections)):
                if '_pre' in str(bpy.data.collections[i_7E470]):
                    for i_68EBB in range(len(bpy.data.collections[i_7E470].objects)):
                        if '_c' + str(uv['sna_id']) + '_lod' + str(bpy.context.scene.sna_g108_lod_switch) in bpy.data.collections[i_7E470].objects[i_68EBB].name or  not '_c' in bpy.data.collections[i_7E470].objects[i_68EBB].name[-9:] and '_lod' + str(bpy.context.scene.sna_g108_lod_switch) in bpy.data.collections[i_7E470].objects[i_68EBB].name and uv['sna_id'] == 1:
                            if len(bpy.data.collections[i_7E470].objects[i_68EBB].data.uv_layers.values()) >= 1:
                                bpy.data.collections[i_7E470].objects[i_68EBB].data.uv_layers[0].name = '1U'
                                if len(bpy.data.collections[i_7E470].objects[i_68EBB].data.uv_layers.values()) >= 2:
                                    bpy.data.collections[i_7E470].objects[i_68EBB].data.uv_layers[1].name = '2U'
                                else:
                                    pass
                                modifier_18D01 = bpy.data.collections[i_7E470].objects[i_68EBB].modifiers.new(name='z_uv可视化', type='NODES', )
                                modifier_18D01.node_group = bpy.data.node_groups['z_uv可视化']
                                if '_autophy_s' in str(bpy.data.collections[i_7E470].objects.keys()):
                                    bpy.data.collections[i_7E470].objects[i_68EBB].modifiers['z_uv可视化']['Input_3'] = bpy.data.objects[bpy.data.collections[i_7E470].name[:-4] + '_autophy_s']
                                else:
                                    pass
                            else:
                                pass
                        else:
                            pass
                else:
                    pass
        else:
            pass
        return {"FINISHED"}
    
    def invoke(self, context, event):
        
        
        return self.execute(context)
class SNA_OT_Uv_176Be(bpy.types.Operator):
    bl_idname = "sna.uv_176be"
    bl_label = "清理uv可视"
    bl_description = ""
    bl_options = {"REGISTER", "UNDO"}
    
    
    @classmethod
    def poll(cls, context):
        return not False
    def execute(self, context):
        for i_EE99D in range(len(bpy.data.collections)):
            if '_pre' in bpy.data.collections[i_EE99D].name:
                for i_7FD71 in range(len(bpy.data.collections[i_EE99D].objects)):
                    if 'z_uv可视化' in str(bpy.data.collections[i_EE99D].objects[i_7FD71].modifiers.keys()):
                        bpy.data.collections[i_EE99D].objects[i_7FD71].modifiers.remove(modifier=bpy.data.collections[i_EE99D].objects[i_7FD71].modifiers['z_uv可视化'], )
                    else:
                        pass
            else:
                pass
        return {"FINISHED"}
    
    def invoke(self, context, event):
        
        
        return self.execute(context)
class SNA_OT_Uv_E31Ce(bpy.types.Operator):
    bl_idname = "sna.uv_e31ce"
    bl_label = "关闭uv可视"
    bl_description = ""
    bl_options = {"REGISTER", "UNDO"}
    
    
    @classmethod
    def poll(cls, context):
        return not False
    def execute(self, context):
        uv['sna_uv'] = False
        bpy.ops.sna.uv_176be('INVOKE_DEFAULT', )
        return {"FINISHED"}
    
    def invoke(self, context, event):
        
        
        return self.execute(context)
class SNA_OT_Id_36Dc1(bpy.types.Operator):
    bl_idname = "sna.id_36dc1"
    bl_label = "id切换"
    bl_description = ""
    bl_options = {"REGISTER", "UNDO"}
    
    
    sna_id: bpy.props.IntProperty(name='id', description='', options={'HIDDEN'}, default=0, subtype='NONE', min=1, max=18)
    
    @classmethod
    def poll(cls, context):
        return not False
    def execute(self, context):
        uv['sna_id'] = self.sna_id
        bpy.ops.sna.uv_62070('INVOKE_DEFAULT', )
        return {"FINISHED"}
    
    def invoke(self, context, event):
        
        
        return self.execute(context)
class SNA_OT_Uv_67090(bpy.types.Operator):
    bl_idname = "sna.uv_67090"
    bl_label = "uv精度开启"
    bl_description = ""
    bl_options = {"REGISTER", "UNDO"}
    
    
    @classmethod
    def poll(cls, context):
        return not False
    def execute(self, context):
        bpy.ops.sna.uv_515ee('INVOKE_DEFAULT', )
        for i_F4862 in range(len(bpy.data.collections)):
            if '_pre' in str(bpy.data.collections[i_F4862]):
                for i_7B735 in range(len(bpy.data.collections[i_F4862].objects)):
                    if len(bpy.data.collections[i_F4862].objects[i_7B735].data.uv_layers.values()) >= 1:
                        bpy.data.collections[i_F4862].objects[i_7B735].data.uv_layers[0].name = '1U'
                        if len(bpy.data.collections[i_F4862].objects[i_7B735].data.uv_layers.values()) >= 2:
                            bpy.data.collections[i_F4862].objects[i_7B735].data.uv_layers[1].name = '2U'
                            if '_autophy' in str(bpy.data.collections[i_F4862].objects[i_7B735]):
                                pass
                            else:
                                modifier_34474 = bpy.data.collections[i_F4862].objects[i_7B735].modifiers.new(name='z_uv精度可视', type='NODES', )
                                modifier_34474.node_group = bpy.data.node_groups['z_uv精度可视']
                        else:
                            pass
                    else:
                        pass
            else:
                pass
        return {"FINISHED"}
    
    def invoke(self, context, event):
        
        
        return self.execute(context)
class SNA_OT_U_18E4B(bpy.types.Operator):
    bl_idname = "sna.u_18e4b"
    bl_label = "2u"
    bl_description = ""
    bl_options = {"REGISTER", "UNDO"}
    
    
    @classmethod
    def poll(cls, context):
        return not False
    def execute(self, context):
        bpy.data.materials['Z-UV检查'].node_tree.nodes['UV精度'].outputs[0].default_value = 1.0
        bpy.ops.sna.uv_67090()
        return {"FINISHED"}
    
    def invoke(self, context, event):
        
        
        return self.execute(context)
class SNA_OT_U_1Ad31(bpy.types.Operator):
    bl_idname = "sna.u_1ad31"
    bl_label = "1u"
    bl_description = ""
    bl_options = {"REGISTER", "UNDO"}
    
    
    @classmethod
    def poll(cls, context):
        return not False
    def execute(self, context):
        bpy.data.materials['Z-UV检查'].node_tree.nodes['UV精度'].outputs[0].default_value = 0.0
        bpy.ops.sna.uv_67090()
        return {"FINISHED"}
    
    def invoke(self, context, event):
        
        
        return self.execute(context)
class SNA_OT_Uv_515Ee(bpy.types.Operator):
    bl_idname = "sna.uv_515ee"
    bl_label = "uv精度关闭"
    bl_description = ""
    bl_options = {"REGISTER", "UNDO"}
    
    
    @classmethod
    def poll(cls, context):
        return not False
    def execute(self, context):
        for i_E506B in range(len(bpy.data.collections)):
            if '_pre' in bpy.data.collections[i_E506B].name:
                for i_59901 in range(len(bpy.data.collections[i_E506B].objects)):
                    if 'z_uv精度可视' in str(bpy.data.collections[i_E506B].objects[i_59901].modifiers.keys()):
                        bpy.data.collections[i_E506B].objects[i_59901].modifiers.remove(modifier=bpy.data.collections[i_E506B].objects[i_59901].modifiers['z_uv精度可视'], )
                    else:
                        pass
            else:
                pass
        return {"FINISHED"}
    
    def invoke(self, context, event):
        
        
        return self.execute(context)
def sna_uv_83FC6(layout_function, ):
    pass
    box_FC3EB = layout_function.box()
    box_FC3EB.alert = False
    box_FC3EB.enabled = True
    box_FC3EB.use_property_split = False
    box_FC3EB.use_property_decorate = False
    box_FC3EB.alignment = 'Expand'.upper()
    box_FC3EB.scale_x = 1.0
    box_FC3EB.scale_y = 1.0
    col_C8A21 = box_FC3EB.column(heading='', align=False)
    col_C8A21.alert = False
    col_C8A21.enabled = True
    col_C8A21.use_property_split = False
    col_C8A21.use_property_decorate = False
    col_C8A21.scale_x = 1.0
    col_C8A21.scale_y = 1.0
    col_C8A21.alignment = 'Expand'.upper()
    col_05219 = col_C8A21.column(heading='', align=False)
    col_05219.alert = False
    col_05219.enabled = True
    col_05219.use_property_split = False
    col_05219.use_property_decorate = False
    col_05219.scale_x = 1.0
    col_05219.scale_y = 1.5
    col_05219.alignment = 'Expand'.upper()
    op = col_05219.operator('sna.uv_515ee', text='关闭UV精度', icon_value=0, emboss=True, depress=False)
    split_A6EB0 = col_C8A21.split(factor=0.5, align=True)
    split_A6EB0.alert = False
    split_A6EB0.enabled = True
    split_A6EB0.use_property_split = False
    split_A6EB0.use_property_decorate = False
    split_A6EB0.scale_x = 1.0
    split_A6EB0.scale_y = 1.2999999523162842
    split_A6EB0.alignment = 'Expand'.upper()
    op = split_A6EB0.operator('sna.u_1ad31', text='1U精度', icon_value=0, emboss=True, depress=False)
    op = split_A6EB0.operator('sna.u_18e4b', text='2U精度', icon_value=0, emboss=True, depress=False)
    split_720F9 = col_C8A21.split(factor=0.5, align=True)
    split_720F9.alert = False
    split_720F9.enabled = True
    split_720F9.use_property_split = False
    split_720F9.use_property_decorate = False
    split_720F9.scale_x = 1.0
    split_720F9.scale_y = 1.2000000476837158
    split_720F9.alignment = 'Expand'.upper()
    split_720F9.prop(bpy.context.scene, 'sna_g108_1uaccuracy', text='', icon_value=0, emboss=True)
    split_720F9.prop(bpy.context.scene, 'sna_g108_2uaccuracy', text='', icon_value=0, emboss=True)
class SNA_OT_My_Generic_Operator_64510(bpy.types.Operator):
    bl_idname = "sna.my_generic_operator_64510"
    bl_label = "行走碰撞"
    bl_description = ""
    bl_options = {"REGISTER", "UNDO"}
    
    
    @classmethod
    def poll(cls, context):
        return not False
    def execute(self, context):
        for i_F9763 in range(len(bpy.data.collections)):
            for i_CBA6C in range(len(bpy.data.collections[i_F9763].objects)):
                if '_autophy_s' in str(bpy.data.collections[i_F9763].objects[i_CBA6C]):
                    bpy.data.collections[i_F9763].objects[i_CBA6C].hide_viewport = False
                    bpy.data.collections[i_F9763].objects[i_CBA6C].modifiers.clear()
                    modifier_E9700 = bpy.data.collections[i_F9763].objects[i_CBA6C].modifiers.new(name='z_行走碰撞', type='NODES', )
                    modifier_E9700.node_group = bpy.data.node_groups['z_行走碰撞']
                else:
                    pass
        return {"FINISHED"}
    
    def invoke(self, context, event):
        
        
        return self.execute(context)
class SNA_OT_My_Generic_Operator_0E33A(bpy.types.Operator):
    bl_idname = "sna.my_generic_operator_0e33a"
    bl_label = "子弹碰撞"
    bl_description = ""
    bl_options = {"REGISTER", "UNDO"}
    
    
    @classmethod
    def poll(cls, context):
        return not False
    def execute(self, context):
        for i_15DEB in range(len(bpy.data.collections)):
            for i_4E581 in range(len(bpy.data.collections[i_15DEB].objects)):
                if '_autophy' in str(bpy.data.collections[i_15DEB].objects[i_4E581]) and  not '_autophy_s' in str(bpy.data.collections[i_15DEB].objects[i_4E581]):
                    bpy.data.collections[i_15DEB].objects[i_4E581].hide_viewport = False
                    bpy.data.collections[i_15DEB].objects[i_4E581].modifiers.clear()
                    modifier_E5952 = bpy.data.collections[i_15DEB].objects[i_4E581].modifiers.new(name='z_子弹碰撞', type='NODES', )
                    modifier_E5952.node_group = bpy.data.node_groups['z_子弹碰撞']
                else:
                    pass
        return {"FINISHED"}
    
    def invoke(self, context, event):
        
        
        return self.execute(context)
class SNA_OT_My_Generic_Operator_B6263(bpy.types.Operator):
    bl_idname = "sna.my_generic_operator_b6263"
    bl_label = "清空碰撞可视化"
    bl_description = ""
    bl_options = {"REGISTER", "UNDO"}
    
    
    @classmethod
    def poll(cls, context):
        return not False
    def execute(self, context):
        for i_48B08 in range(len(bpy.data.collections)):
            for i_B24E6 in range(len(bpy.data.collections[i_48B08].objects)):
                if '_autophy' in str(bpy.data.collections[i_48B08].objects[i_B24E6]):
                    bpy.data.collections[i_48B08].objects[i_B24E6].hide_viewport = True
                    bpy.data.collections[i_48B08].objects[i_B24E6].modifiers.clear()
                else:
                    pass
        return {"FINISHED"}
    
    def invoke(self, context, event):
        
        
        return self.execute(context)
def sna_func_5BBCB(layout_function, ):
    pass
    box_8D48F = layout_function.box()
    box_8D48F.alert = False
    box_8D48F.enabled = True
    box_8D48F.use_property_split = False
    box_8D48F.use_property_decorate = False
    box_8D48F.alignment = 'Expand'.upper()
    box_8D48F.scale_x = 1.0
    box_8D48F.scale_y = 1.0
    col_61A1A = box_8D48F.column(heading='', align=False)
    col_61A1A.alert = False
    col_61A1A.enabled = True
    col_61A1A.use_property_split = False
    col_61A1A.use_property_decorate = False
    col_61A1A.scale_x = 1.0
    col_61A1A.scale_y = 1.0
    col_61A1A.alignment = 'Expand'.upper()
    col_87217 = col_61A1A.column(heading='', align=False)
    col_87217.alert = False
    col_87217.enabled = True
    col_87217.use_property_split = False
    col_87217.use_property_decorate = False
    col_87217.scale_x = 1.0
    col_87217.scale_y = 1.5
    col_87217.alignment = 'Expand'.upper()
    op = col_87217.operator('sna.my_generic_operator_b6263', text='关闭碰撞可视化', icon_value=0, emboss=True, depress=False)
    split_B2F4F = col_61A1A.split(factor=0.5, align=True)
    split_B2F4F.alert = False
    split_B2F4F.enabled = True
    split_B2F4F.use_property_split = False
    split_B2F4F.use_property_decorate = False
    split_B2F4F.scale_x = 1.0
    split_B2F4F.scale_y = 1.5
    split_B2F4F.alignment = 'Expand'.upper()
    op = split_B2F4F.operator('sna.my_generic_operator_64510', text='行走碰撞', icon_value=0, emboss=True, depress=False)
    op = split_B2F4F.operator('sna.my_generic_operator_0e33a', text='子弹碰撞', icon_value=0, emboss=True, depress=False)
def sna_add_to_view3d_mt_editor_menus_98DAC(self, context):
    if not (False):
        layout = self.layout
        layout.popover('SNA_PT_NEW_PANEL_07F13', text='显示', icon_value=0)
class SNA_PT_NEW_PANEL_07F13(bpy.types.Panel):
    bl_label = 'New Panel'
    bl_idname = 'SNA_PT_NEW_PANEL_07F13'
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'WINDOW'
    bl_context = ''
    
    bl_order = 0
    
    
    @classmethod
    def poll(cls, context):
        return not (False)
    
    def draw_header(self, context):
        layout = self.layout
        
    def draw(self, context):
        layout = self.layout
        layout_function = layout
        sna_lod_29A25(layout_function, )
        layout_function = layout
        sna_pbr_92959(layout_function, )
def sna_func_396EB(layout_function, ):
    pass
    row_11C56 = layout_function.row(heading='', align=True)
    row_11C56.alert = False
    row_11C56.enabled = True
    row_11C56.use_property_split = False
    row_11C56.use_property_decorate = False
    row_11C56.scale_x = 1.0
    row_11C56.scale_y = 1.100000023841858
    row_11C56.alignment = 'Expand'.upper()
    row_11C56.prop(bpy.context.scene, 'sna_g108_wireframe', text='线框', icon_value=0, emboss=True, toggle=True)
    row_11C56.prop(bpy.context.scene, 'sna_g108_bounding_box', text='包围框', icon_value=0, emboss=True, toggle=True)
class SNA_OT_My_Generic_Operator_07104(bpy.types.Operator):
    bl_idname = "sna.my_generic_operator_07104"
    bl_label = "贴图可视化清理"
    bl_description = ""
    bl_options = {"REGISTER", "UNDO"}
    
    
    @classmethod
    def poll(cls, context):
        return not False
    def execute(self, context):
        for i_7DBBD in range(len(bpy.data.meshes)):
            for i_4CBCC in range(len(bpy.data.meshes)):
                if '贴图可视' in str(bpy.data.meshes[i_4CBCC]):
                    bpy.context.blend_data.meshes.remove(mesh=bpy.data.meshes[i_4CBCC], )
                    break
                else:
                    pass
        if '贴图可视' in str(bpy.data.collections.keys()):
            bpy.context.blend_data.collections.remove(collection=bpy.data.collections['贴图可视'], )
        else:
            pass
        return {"FINISHED"}
    
    def invoke(self, context, event):
        
        
        return self.execute(context)
class SNA_OT_My_Generic_Operator_9Bd9C(bpy.types.Operator):
    bl_idname = "sna.my_generic_operator_9bd9c"
    bl_label = "2：1"
    bl_description = ""
    bl_options = {"REGISTER", "UNDO"}
    
    
    @classmethod
    def poll(cls, context):
        return not False
    def execute(self, context):
        bpy.context.active_object.scale = (1.0, 1.0, 2.0)
        return {"FINISHED"}
    
    def invoke(self, context, event):
        
        
        return self.execute(context)
class SNA_OT_My_Generic_Operator_B6166(bpy.types.Operator):
    bl_idname = "sna.my_generic_operator_b6166"
    bl_label = "1：1"
    bl_description = ""
    bl_options = {"REGISTER", "UNDO"}
    
    
    @classmethod
    def poll(cls, context):
        return not False
    def execute(self, context):
        bpy.context.active_object.scale = (1.0, 1.0, 1.0)
        return {"FINISHED"}
    
    def invoke(self, context, event):
        
        
        return self.execute(context)
class SNA_OT_My_Generic_Operator_880Fd(bpy.types.Operator):
    bl_idname = "sna.my_generic_operator_880fd"
    bl_label = "4：1"
    bl_description = ""
    bl_options = {"REGISTER", "UNDO"}
    
    
    @classmethod
    def poll(cls, context):
        return not False
    def execute(self, context):
        bpy.context.active_object.scale = (1.0, 1.0, 4.0)
        return {"FINISHED"}
    
    def invoke(self, context, event):
        
        
        return self.execute(context)
class SNA_OT_My_Generic_Operator_F808B(bpy.types.Operator):
    bl_idname = "sna.my_generic_operator_f808b"
    bl_label = "创建贴图载体"
    bl_description = ""
    bl_options = {"REGISTER", "UNDO"}
    
    
    @classmethod
    def poll(cls, context):
        return not False
    def execute(self, context):
        bpy.ops.mesh.primitive_plane_add('INVOKE_DEFAULT', rotation=(math.radians(90.0), 0.0, 0.0))
        bpy.ops.object.material_slot_add('INVOKE_DEFAULT', )
        bpy.ops.object.transform_apply('INVOKE_DEFAULT', rotation=True, scale=True, properties=True)
        bpy.ops.object.align('INVOKE_DEFAULT', bb_quality=True, align_mode='OPT_1', relative_to='OPT_1', align_axis=set(['Z']))
        from mathutils import Matrix, Vector
        def origin_to_bottom(ob, matrix=Matrix(), use_verts=False):
            me = ob.data
            mw = ob.matrix_world
            if use_verts:
                data = (v.co for v in me.vertices)
            else:
                data = (Vector(v) for v in ob.bound_box)
            coords = np.array([matrix @ v for v in data])
            z = coords.T[2]
            mins = np.take(coords, np.where(z == z.min())[0], axis=0)
            o = Vector(np.mean(mins, axis=0))
            o = matrix.inverted() @ o
            me.transform(Matrix.Translation(-o))
            mw.translation = mw @ o  
            
        for o in bpy.context.selected_objects:
            if o.type == 'MESH':
                origin_to_bottom(o)
                
        if ('贴图可视' in bpy.data.collections):
            a = int(bpy.data.collections.find('贴图可视') + 1)
            bpy.ops.object.move_to_collection(collection_index=a)
        else:
            bpy.ops.object.move_to_collection(collection_index=0, is_new=True, new_collection_name="贴图可视")
        bpy.context.active_object.name = '贴图可视'
        bpy.context.active_object.data.name = '贴图可视'
        self.report({'INFO'}, message='成功创建贴图板')
        return {"FINISHED"}
    
    def invoke(self, context, event):
        
        
        return self.execute(context)
def sna_g108_datamat_enum_items(self, context):
    enum_items = node_tree_001['sna_data_set']
    return [make_enum_item(item[0], item[1], item[2], item[3], i) for i, item in enumerate(enum_items)]
def sna_func_2520D(layout_function, ):
    pass
    box_D0F8A = layout_function.box()
    box_D0F8A.alert = False
    box_D0F8A.enabled = True
    box_D0F8A.use_property_split = False
    box_D0F8A.use_property_decorate = False
    box_D0F8A.alignment = 'Expand'.upper()
    box_D0F8A.scale_x = 1.0
    box_D0F8A.scale_y = 1.0
    col_F7398 = box_D0F8A.column(heading='', align=False)
    col_F7398.alert = False
    col_F7398.enabled = True
    col_F7398.use_property_split = False
    col_F7398.use_property_decorate = False
    col_F7398.scale_x = 1.0
    col_F7398.scale_y = 1.0
    col_F7398.alignment = 'Expand'.upper()
    split_29E5A = col_F7398.split(factor=0.699999988079071, align=True)
    split_29E5A.alert = False
    split_29E5A.enabled = True
    split_29E5A.use_property_split = False
    split_29E5A.use_property_decorate = False
    split_29E5A.scale_x = 1.0
    split_29E5A.scale_y = 1.7999999523162842
    split_29E5A.alignment = 'Expand'.upper()
    op = split_29E5A.operator('sna.my_generic_operator_f808b', text='创建贴图板', icon_value=0, emboss=True, depress=False)
    op = split_29E5A.operator('sna.my_generic_operator_88f4f', text='清理贴图板', icon_value=0, emboss=True, depress=False)
    if property_exists("bpy.context.active_object.name") and '贴图可视' in bpy.context.active_object.name:
        col_C0002 = col_F7398.column(heading='', align=False)
        col_C0002.alert = False
        col_C0002.enabled = True
        col_C0002.use_property_split = False
        col_C0002.use_property_decorate = False
        col_C0002.scale_x = 1.0
        col_C0002.scale_y = 1.0
        col_C0002.alignment = 'Expand'.upper()
        col_BBF4E = col_C0002.column(heading='', align=False)
        col_BBF4E.alert = False
        col_BBF4E.enabled = True
        col_BBF4E.use_property_split = False
        col_BBF4E.use_property_decorate = False
        col_BBF4E.scale_x = 1.0
        col_BBF4E.scale_y = 1.0
        col_BBF4E.alignment = 'Expand'.upper()
        col_BBF4E.prop(bpy.context.scene, 'sna_g108_datamat', text='', icon_value=0, emboss=True)
        col_BBF4E.template_icon_view(bpy.context.scene, 'sna_g108_datamat', show_labels=True, scale=7.0, scale_popup=4.0)
        row_4D628 = col_C0002.row(heading='', align=True)
        row_4D628.alert = False
        row_4D628.enabled = True
        row_4D628.use_property_split = False
        row_4D628.use_property_decorate = False
        row_4D628.scale_x = 1.0
        row_4D628.scale_y = 1.2999999523162842
        row_4D628.alignment = 'Expand'.upper()
        op = row_4D628.operator('sna.my_generic_operator_b6166', text='1:1', icon_value=0, emboss=True, depress=False)
        op = row_4D628.operator('sna.my_generic_operator_9bd9c', text='2:1', icon_value=0, emboss=True, depress=False)
        op = row_4D628.operator('sna.my_generic_operator_880fd', text='4:1', icon_value=0, emboss=True, depress=False)
    else:
        pass
@persistent
def depsgraph_update_post_handler_46A22(dummy):
    if property_exists("bpy.data.collections['贴图可视']") and property_exists("bpy.context.view_layer.objects.active") and '贴图可视' in bpy.context.view_layer.objects.active.name:
        node_tree_001['sna_data_set'] = []
        for i_16E21 in range(len(bpy.data.materials)):
            if '_mat' in bpy.data.materials[i_16E21].name:
                node_tree_001['sna_data_set'].append([bpy.data.materials[i_16E21].name, bpy.data.materials[i_16E21].name, '', get_id_preview_id(bpy.data.materials[bpy.data.materials[i_16E21].name])])
            else:
                pass
    else:
        pass
    if property_exists("bpy.data.collections['贴图可视']") and property_exists("bpy.context.view_layer.objects.active") and '贴图可视' in bpy.context.view_layer.objects.active.name:
        bpy.context.scene.sna_g108_datamat = bpy.context.active_object.material_slots[bpy.context.view_layer.objects.active.active_material_index].material.name
    else:
        pass
class SNA_OT_My_Generic_Operator_88F4F(bpy.types.Operator):
    bl_idname = "sna.my_generic_operator_88f4f"
    bl_label = "！清空全部！"
    bl_description = ""
    bl_options = {"REGISTER", "UNDO"}
    
    
    @classmethod
    def poll(cls, context):
        return not False
    def execute(self, context):
        bpy.ops.sna.my_generic_operator_07104('INVOKE_DEFAULT', )
        self.report({'INFO'}, message='成功清理贴图板')
        return {"FINISHED"}
    
    def invoke(self, context, event):
        
        
        return context.window_manager.invoke_confirm(self, event)
class SNA_OT_My_Generic_Operator_E59Ea(bpy.types.Operator):
    bl_idname = "sna.my_generic_operator_e59ea"
    bl_label = "卸载所有资产"
    bl_description = ""
    bl_options = {"REGISTER", "UNDO"}
    
    
    @classmethod
    def poll(cls, context):
        return not False
    def execute(self, context):
        for i_E7B04 in range(len(bpy.data.node_groups)):
            for i_DA26B in range(len(bpy.data.node_groups)):
                if 'z_uv可视化' in str(bpy.data.node_groups[i_DA26B]) or 'z_id统计' in str(bpy.data.node_groups[i_DA26B]) or 'z_uv精度可视' in str(bpy.data.node_groups[i_DA26B]) or 'z_子弹碰撞' in str(bpy.data.node_groups[i_DA26B]) or 'z_行走碰撞' in str(bpy.data.node_groups[i_DA26B]) or 'z_面数统计' in str(bpy.data.node_groups[i_DA26B]) or 'z_id遮罩' in str(bpy.data.node_groups[i_DA26B]):
                    bpy.context.blend_data.node_groups.remove(tree=bpy.data.node_groups[i_DA26B], )
                    break
                else:
                    pass
        for i_AFD6B in range(len(bpy.data.materials)):
            for i_75CDC in range(len(bpy.data.materials)):
                if 'Z-UV可视化材质' in str(bpy.data.materials[i_75CDC]) or 'Z-UV检查' in str(bpy.data.materials[i_75CDC]) or 'Z-子弹碰撞' in str(bpy.data.materials[i_75CDC]) or 'Z-行走碰撞' in str(bpy.data.materials[i_75CDC]) or 'Z_id遮罩材质' in str(bpy.data.materials[i_75CDC]):
                    bpy.context.blend_data.materials.remove(material=bpy.data.materials[i_75CDC], )
                    break
                else:
                    pass
        for i_05409 in range(len(bpy.data.images)):
            for i_B58E4 in range(len(bpy.data.images)):
                if '1U检查栅格图' in str(bpy.data.images[i_B58E4]):
                    bpy.context.blend_data.images.remove(image=bpy.data.images[i_B58E4], )
                    break
                else:
                    pass
        for i_12D4B in range(len(bpy.data.fonts)):
            for i_CCA0C in range(len(bpy.data.fonts)):
                if 'Bfont Regular' in str(bpy.data.fonts[i_CCA0C]) and bpy.data.fonts[i_CCA0C].users == 0:
                    bpy.context.blend_data.fonts.remove(vfont=bpy.data.fonts[i_CCA0C], )
                    break
                else:
                    pass
        return {"FINISHED"}
    
    def invoke(self, context, event):
        
        
        return self.execute(context)
class SNA_OT_My_Generic_Operator_23C6E(bpy.types.Operator):
    bl_idname = "sna.my_generic_operator_23c6e"
    bl_label = "加载所有资产"
    bl_description = ""
    bl_options = {"REGISTER", "UNDO"}
    
    
    @classmethod
    def poll(cls, context):
        return not False
    def execute(self, context):
        if property_exists("bpy.data.node_groups['z_uv可视化']"):
            pass
        else:
            bpy.ops.wm.append(directory=os.path.join(os.path.dirname(__file__), 'assets', '可视化检查工具资产3.5.blend') + r'\NodeTree', filename='z_uv可视化', link=False)
        if property_exists("bpy.data.node_groups['z_id统计']"):
            pass
        else:
            bpy.ops.wm.append(directory=os.path.join(os.path.dirname(__file__), 'assets', '可视化检查工具资产3.5.blend') + r'\NodeTree', filename='z_id统计', link=False)
        if property_exists("bpy.data.node_groups['z_uv精度可视']"):
            pass
        else:
            bpy.ops.wm.append(directory=os.path.join(os.path.dirname(__file__), 'assets', '可视化检查工具资产3.5.blend') + r'\NodeTree', filename='z_uv精度可视', link=False)
        if property_exists("bpy.data.node_groups['z_子弹碰撞']"):
            pass
        else:
            bpy.ops.wm.append(directory=os.path.join(os.path.dirname(__file__), 'assets', '可视化检查工具资产3.5.blend') + r'\NodeTree', filename='z_子弹碰撞', link=False)
        if property_exists("bpy.data.node_groups['z_行走碰撞']"):
            pass
        else:
            bpy.ops.wm.append(directory=os.path.join(os.path.dirname(__file__), 'assets', '可视化检查工具资产3.5.blend') + r'\NodeTree', filename='z_行走碰撞', link=False)
        if property_exists("bpy.data.node_groups['z_面数统计']"):
            pass
        else:
            bpy.ops.wm.append(directory=os.path.join(os.path.dirname(__file__), 'assets', '可视化检查工具资产3.5.blend') + r'\NodeTree', filename='z_面数统计', link=False)
        if property_exists("bpy.data.node_groups['z_id遮罩']"):
            pass
        else:
            bpy.ops.wm.append(directory=os.path.join(os.path.dirname(__file__), 'assets', '可视化检查工具资产3.5.blend') + r'\NodeTree', filename='z_id遮罩', link=False)
        bpy.data.node_groups['z_id遮罩'].use_fake_user = True
        bpy.data.node_groups['z_uv可视化'].use_fake_user = True
        bpy.data.node_groups['z_id统计'].use_fake_user = True
        bpy.data.node_groups['z_uv精度可视'].use_fake_user = True
        bpy.data.node_groups['z_子弹碰撞'].use_fake_user = True
        bpy.data.node_groups['z_行走碰撞'].use_fake_user = True
        bpy.data.node_groups['z_面数统计'].use_fake_user = True
        bpy.data.materials['Z-UV可视化材质'].use_fake_user = True
        bpy.data.materials['Z-UV检查'].use_fake_user = True
        bpy.data.materials['Z-子弹碰撞'].use_fake_user = True
        bpy.data.materials['Z-行走碰撞'].use_fake_user = True
        bpy.data.materials['Z_id遮罩材质'].use_fake_user = True
        return {"FINISHED"}
    
    def invoke(self, context, event):
        
        
        return self.execute(context)
def sna_func_94954(layout_function, ):
    pass
    box_30C6C = layout_function.box()
    box_30C6C.alert = False
    box_30C6C.enabled = True
    box_30C6C.use_property_split = False
    box_30C6C.use_property_decorate = False
    box_30C6C.alignment = 'Expand'.upper()
    box_30C6C.scale_x = 1.0
    box_30C6C.scale_y = 1.0
    col_A23D8 = box_30C6C.column(heading='', align=False)
    col_A23D8.alert = False
    col_A23D8.enabled = True
    col_A23D8.use_property_split = False
    col_A23D8.use_property_decorate = False
    col_A23D8.scale_x = 1.0
    col_A23D8.scale_y = 1.0
    col_A23D8.alignment = 'Expand'.upper()
    split_0E745 = col_A23D8.split(factor=0.5, align=True)
    split_0E745.alert = False
    split_0E745.enabled = True
    split_0E745.use_property_split = False
    split_0E745.use_property_decorate = False
    split_0E745.scale_x = 1.0
    split_0E745.scale_y = 1.5
    split_0E745.alignment = 'Expand'.upper()
    op = split_0E745.operator('sna.my_generic_operator_23c6e', text='加载所有资产', icon_value=0, emboss=True, depress=False)
    op = split_0E745.operator('sna.my_generic_operator_e59ea', text='卸载所有资产', icon_value=0, emboss=True, depress=False)
    box_D9902 = col_A23D8.box()
    box_D9902.alert = False
    box_D9902.enabled = True
    box_D9902.use_property_split = False
    box_D9902.use_property_decorate = False
    box_D9902.alignment = 'Expand'.upper()
    box_D9902.scale_x = 1.0
    box_D9902.scale_y = 1.0
    box_D9902.label(text='几何节点组状态：', icon_value=0)
    col_883B0 = box_D9902.column(heading='', align=False)
    col_883B0.alert = False
    col_883B0.enabled = True
    col_883B0.use_property_split = False
    col_883B0.use_property_decorate = False
    col_883B0.scale_x = 1.0
    col_883B0.scale_y = 1.0
    col_883B0.alignment = 'Expand'.upper()
    col_883B0.label(text='z_uv可视化：' + str('正常' if property_exists("bpy.data.node_groups['z_uv可视化']") else '异常'), icon_value=0)
    col_883B0.label(text='z_面数统计：' + str('正常' if property_exists("bpy.data.node_groups['z_面数统计']") else '异常'), icon_value=0)
    col_883B0.label(text='z_id统计：' + str('正常' if property_exists("bpy.data.node_groups['z_id统计']") else '异常'), icon_value=0)
    col_883B0.label(text='z_子弹碰撞：' + str('正常' if property_exists("bpy.data.node_groups['z_子弹碰撞']") else '异常'), icon_value=0)
    col_883B0.label(text='z_行走碰撞：' + str('正常' if property_exists("bpy.data.node_groups['z_行走碰撞']") else '异常'), icon_value=0)
    col_883B0.label(text='z_uv精度可视：' + str('正常' if property_exists("bpy.data.node_groups['z_uv精度可视']") else '异常'), icon_value=0)
    col_883B0.label(text='z_id遮罩：' + str('正常' if property_exists("bpy.data.node_groups['z_id遮罩']") else '异常'), icon_value=0)
    box_3E0AE = col_A23D8.box()
    box_3E0AE.alert = False
    box_3E0AE.enabled = True
    box_3E0AE.use_property_split = False
    box_3E0AE.use_property_decorate = False
    box_3E0AE.alignment = 'Expand'.upper()
    box_3E0AE.scale_x = 1.0
    box_3E0AE.scale_y = 1.0
    box_3E0AE.label(text='材质状态：', icon_value=0)
    col_EAE66 = box_3E0AE.column(heading='', align=False)
    col_EAE66.alert = False
    col_EAE66.enabled = True
    col_EAE66.use_property_split = False
    col_EAE66.use_property_decorate = False
    col_EAE66.scale_x = 1.0
    col_EAE66.scale_y = 1.0
    col_EAE66.alignment = 'Expand'.upper()
    col_EAE66.label(text='Z-UV可视化材质：' + str('正常' if property_exists("bpy.data.materials['Z-UV可视化材质']") else '异常'), icon_value=0)
    col_EAE66.label(text='Z-UV检查：' + str('正常' if property_exists("bpy.data.materials['Z-UV检查']") else '异常'), icon_value=0)
    col_EAE66.label(text='Z-子弹碰撞：' + str('正常' if property_exists("bpy.data.materials['Z-子弹碰撞']") else '异常'), icon_value=0)
    col_EAE66.label(text='Z-行走碰撞：' + str('正常' if property_exists("bpy.data.materials['Z-行走碰撞']") else '异常'), icon_value=0)
    col_EAE66.label(text='Z_id遮罩材质：' + str('正常' if property_exists("bpy.data.materials['Z_id遮罩材质']") else '异常'), icon_value=0)
def sna_func_622F7(layout_function, ):
    pass
    box_FE3FC = layout_function.box()
    box_FE3FC.alert = False
    box_FE3FC.enabled = True
    box_FE3FC.use_property_split = False
    box_FE3FC.use_property_decorate = False
    box_FE3FC.alignment = 'Expand'.upper()
    box_FE3FC.scale_x = 1.0
    box_FE3FC.scale_y = 1.0
    row_E7B99 = box_FE3FC.row(heading='', align=True)
    row_E7B99.alert = False
    row_E7B99.enabled = True
    row_E7B99.use_property_split = False
    row_E7B99.use_property_decorate = False
    row_E7B99.scale_x = 1.0
    row_E7B99.scale_y = 1.5
    row_E7B99.alignment = 'Expand'.upper()
    op = row_E7B99.operator('sna.my_generic_operator_f6f7f', text='面数统计', icon_value=0, emboss=True, depress='统计_面数' in str(bpy.data.objects.keys()))
    op = row_E7B99.operator('sna.id_fa001', text='ID统计', icon_value=0, emboss=True, depress='统计_id' in str(bpy.data.objects.keys()))
    op = row_E7B99.operator('sna.my_generic_operator_a0f18', text='清理统计', icon_value=0, emboss=True, depress=False)
    
class SNA_OT_My_Generic_Operator_A0F18(bpy.types.Operator):
    bl_idname = "sna.my_generic_operator_a0f18"
    bl_label = "清理统计数据"
    bl_description = ""
    bl_options = {"REGISTER", "UNDO"}
    
    
    @classmethod
    def poll(cls, context):
        return not False
    def execute(self, context):
        node_tree_001['sna_lod'] = False
        for i_DEFE1 in range(len(bpy.data.meshes)):
            for i_D5AAC in range(len(bpy.data.meshes)):
                if '统计_' in str(bpy.data.meshes[i_D5AAC]):
                    bpy.context.blend_data.meshes.remove(mesh=bpy.data.meshes[i_D5AAC], )
                    break
                else:
                    pass
        if property_exists("bpy.data.collections['统计缓存']"):
            bpy.context.blend_data.collections.remove(collection=bpy.data.collections['统计缓存'], )
        else:
            pass
        return {"FINISHED"}
    
    def invoke(self, context, event):
        
        
        return self.execute(context)
class SNA_OT_Id_Fa001(bpy.types.Operator):
    bl_idname = "sna.id_fa001"
    bl_label = "id统计"
    bl_description = ""
    bl_options = {"REGISTER", "UNDO"}
    
    
    @classmethod
    def poll(cls, context):
        return not False
    def execute(self, context):
        node_tree_001['sna_lod'] = False
        for i_62081 in range(len(bpy.data.meshes)):
            for i_507FB in range(len(bpy.data.meshes)):
                if '统计_' in str(bpy.data.meshes[i_507FB]):
                    bpy.context.blend_data.meshes.remove(mesh=bpy.data.meshes[i_507FB], )
                    break
                else:
                    pass
        for i_30EF4 in range(len(bpy.data.collections)):
            if '_pre' in str(bpy.data.collections[i_30EF4]):
                node_tree_001['sna_id'] = 1
                for i_991E9 in range(len(bpy.data.collections[i_30EF4].objects)):
                    if '_c' + str(i_991E9) in str(bpy.data.collections[i_30EF4].objects.keys()):
                        node_tree_001['sna_id'] = i_991E9
                    else:
                        pass
                bpy.ops.mesh.primitive_plane_add('INVOKE_DEFAULT', )
                if ('统计缓存' in bpy.data.collections):
                    a = int(bpy.data.collections.find('统计缓存') + 1)
                    bpy.ops.object.move_to_collection(collection_index=a)
                else:
                    bpy.ops.object.move_to_collection(collection_index=0, is_new=True, new_collection_name="统计缓存")
                bpy.context.active_object.name = '统计_id_' + bpy.data.collections[i_30EF4].name
                bpy.context.active_object.data.name = '统计_id_' + bpy.data.collections[i_30EF4].name
                bpy.context.active_object.location = bpy.data.collections[i_30EF4].objects[0].location
                modifier_B5F6F = bpy.context.active_object.modifiers.new(name='z_id统计', type='NODES', )
                bpy.context.active_object.modifiers['z_id统计'].node_group = bpy.data.node_groups['z_id统计']
                bpy.context.view_layer.objects.active.modifiers['z_id统计']['Input_2'] = node_tree_001['sna_id']
                if '_autophy' in str(bpy.data.collections[i_30EF4].objects.keys()):
                    for i_DD764 in range(len(bpy.data.collections[i_30EF4].objects)):
                        if '_autophy' in str(bpy.data.collections[i_30EF4].objects[i_DD764]):
                            bpy.context.view_layer.objects.active.modifiers['z_id统计']['Input_4'] = bpy.data.collections[i_30EF4].objects[i_DD764]
                        else:
                            pass
                else:
                    pass
                bpy.context.view_layer.objects.active.modifiers['z_id统计']['Input_3'] = bpy.data.collections[i_30EF4]
            else:
                pass
        return {"FINISHED"}
    
    def invoke(self, context, event):
        
        
        return self.execute(context)
class SNA_OT_My_Generic_Operator_F6F7F(bpy.types.Operator):
    bl_idname = "sna.my_generic_operator_f6f7f"
    bl_label = "面数可视化"
    bl_description = ""
    bl_options = {"REGISTER", "UNDO"}
    
    
    @classmethod
    def poll(cls, context):
        return not False
    def execute(self, context):
        node_tree_001['sna_lod'] = True
        bpy.context.scene.sna_g108_lod_switch = 0
        return {"FINISHED"}
    
    def invoke(self, context, event):
        
        
        return self.execute(context)
class SNA_OT_My_Generic_Operator_40218(bpy.types.Operator):
    bl_idname = "sna.my_generic_operator_40218"
    bl_label = "重置所有检查"
    bl_description = ""
    bl_options = {"REGISTER", "UNDO"}
    
    
    @classmethod
    def poll(cls, context):
        return not False
    def execute(self, context):
        bpy.ops.sna.my_generic_operator_23c6e('INVOKE_DEFAULT', )
        bpy.ops.sna.my_generic_operator_a0f18('INVOKE_DEFAULT', )
        bpy.ops.sna.my_generic_operator_b6263('INVOKE_DEFAULT', )
        bpy.ops.sna.my_generic_operator_3684f('INVOKE_DEFAULT', )
        bpy.ops.sna.uv_e31ce('INVOKE_DEFAULT', )
        bpy.ops.sna.uv_515ee('INVOKE_DEFAULT', )
        bpy.ops.sna.my_generic_operator_3c6ec('INVOKE_DEFAULT', )
        bpy.ops.sna.pbr_0d0f8('INVOKE_DEFAULT', )
        return {"FINISHED"}
    
    def invoke(self, context, event):
        
        
        return self.execute(context)
class SNA_PT_V20_C611B(bpy.types.Panel):
    bl_label = '可视化检查 v2.0'
    bl_idname = 'SNA_PT_V20_C611B'
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_context = ''
    bl_category = 'G108'
    bl_order = 7
    bl_options = {'DEFAULT_CLOSED'}
    
    @classmethod
    def poll(cls, context):
        return not (False)
    
    def draw_header(self, context):
        layout = self.layout
        
    def draw(self, context):
        layout = self.layout
        col_C106B = layout.column(heading='', align=False)
        col_C106B.alert = False
        col_C106B.enabled = True
        col_C106B.use_property_split = False
        col_C106B.use_property_decorate = False
        col_C106B.scale_x = 1.0
        col_C106B.scale_y = 1.100000023841858
        col_C106B.alignment = 'Expand'.upper()
        col_CAFDF = col_C106B.column(heading='', align=False)
        col_CAFDF.alert = False if property_exists("bpy.data.node_groups['z_uv可视化']") and property_exists("bpy.data.node_groups['z_面数统计']") and property_exists("bpy.data.node_groups['z_id统计']") and property_exists("bpy.data.node_groups['z_子弹碰撞']") and property_exists("bpy.data.node_groups['z_行走碰撞']") and property_exists("bpy.data.node_groups['z_uv精度可视']") and property_exists("bpy.data.node_groups['z_id遮罩']") and property_exists("bpy.data.materials['Z-UV可视化材质']") and property_exists("bpy.data.materials['Z-UV检查']") and property_exists("bpy.data.materials['Z-子弹碰撞']") and property_exists("bpy.data.materials['Z-行走碰撞']") and property_exists("bpy.data.materials['Z_id遮罩材质']") else True
        col_CAFDF.enabled = True
        col_CAFDF.use_property_split = False
        col_CAFDF.use_property_decorate = False
        col_CAFDF.scale_x = 1.0
        col_CAFDF.scale_y = 2.0
        col_CAFDF.alignment = 'Expand'.upper()
        op = col_CAFDF.operator('sna.my_generic_operator_40218', text='重置所有检查', icon_value=0, emboss=True, depress=False)
        col_CAFDF.separator(factor=1.0)
        col_FAA3F = col_C106B.column(heading='', align=False)
        col_FAA3F.alert = False
        col_FAA3F.enabled = True
        col_FAA3F.use_property_split = False
        col_FAA3F.use_property_decorate = False
        col_FAA3F.scale_x = 1.0
        col_FAA3F.scale_y = 1.0
        col_FAA3F.alignment = 'Expand'.upper()
        split_EA73D = col_FAA3F.split(factor=0.05000000074505806, align=False)
        split_EA73D.alert = False
        split_EA73D.enabled = True
        split_EA73D.use_property_split = False
        split_EA73D.use_property_decorate = False
        split_EA73D.scale_x = 1.0
        split_EA73D.scale_y = 1.100000023841858
        split_EA73D.alignment = 'Expand'.upper()
        split_EA73D.prop(bpy.context.scene, 'sna_g108_lod', text='', icon_value=0, emboss=True)
        split_EA73D.label(text='LOD切换', icon_value=0)
        if bpy.context.scene.sna_g108_lod:
            layout_function = col_FAA3F
            sna_lod_29A25(layout_function, )
        else:
            pass
        col_FD5E4 = col_C106B.column(heading='', align=False)
        col_FD5E4.alert = False
        col_FD5E4.enabled =  not False if property_exists("bpy.data.node_groups['z_uv可视化']") and property_exists("bpy.data.node_groups['z_面数统计']") and property_exists("bpy.data.node_groups['z_id统计']") and property_exists("bpy.data.node_groups['z_子弹碰撞']") and property_exists("bpy.data.node_groups['z_行走碰撞']") and property_exists("bpy.data.node_groups['z_uv精度可视']") and property_exists("bpy.data.node_groups['z_id遮罩']") and property_exists("bpy.data.materials['Z-UV可视化材质']") and property_exists("bpy.data.materials['Z-UV检查']") and property_exists("bpy.data.materials['Z-子弹碰撞']") and property_exists("bpy.data.materials['Z-行走碰撞']") and property_exists("bpy.data.materials['Z_id遮罩材质']") else True == False
        col_FD5E4.use_property_split = False
        col_FD5E4.use_property_decorate = False
        col_FD5E4.scale_x = 1.0
        col_FD5E4.scale_y = 1.0
        col_FD5E4.alignment = 'Expand'.upper()
        col_4EED5 = col_FD5E4.column(heading='', align=False)
        col_4EED5.alert = False
        col_4EED5.enabled = True
        col_4EED5.use_property_split = False
        col_4EED5.use_property_decorate = False
        col_4EED5.scale_x = 1.0
        col_4EED5.scale_y = 1.0
        col_4EED5.alignment = 'Expand'.upper()
        split_D682D = col_4EED5.split(factor=0.05000000074505806, align=False)
        split_D682D.alert = False
        split_D682D.enabled = True
        split_D682D.use_property_split = False
        split_D682D.use_property_decorate = False
        split_D682D.scale_x = 1.0
        split_D682D.scale_y = 1.100000023841858
        split_D682D.alignment = 'Expand'.upper()
        split_D682D.prop(bpy.context.scene, 'sna_g108_modidchoice', text='', icon_value=0, emboss=True)
        split_D682D.label(text='模型ID显示', icon_value=0)
        if bpy.context.scene.sna_g108_modidchoice:
            layout_function = col_4EED5
            sna_id_2FC3D(layout_function, )
        else:
            pass
        col_9FEA9 = col_FD5E4.column(heading='', align=False)
        col_9FEA9.alert = False
        col_9FEA9.enabled = True
        col_9FEA9.use_property_split = False
        col_9FEA9.use_property_decorate = False
        col_9FEA9.scale_x = 1.0
        col_9FEA9.scale_y = 1.0
        col_9FEA9.alignment = 'Expand'.upper()
        split_DC5D8 = col_9FEA9.split(factor=0.05000000074505806, align=False)
        split_DC5D8.alert = False
        split_DC5D8.enabled = True
        split_DC5D8.use_property_split = False
        split_DC5D8.use_property_decorate = False
        split_DC5D8.scale_x = 1.0
        split_DC5D8.scale_y = 1.100000023841858
        split_DC5D8.alignment = 'Expand'.upper()
        split_DC5D8.prop(bpy.context.scene, 'sna_g108_information', text='', icon_value=0, emboss=True)
        split_DC5D8.label(text='信息统计', icon_value=0)
        if bpy.context.scene.sna_g108_information:
            layout_function = col_9FEA9
            sna_func_622F7(layout_function, )
        else:
            pass
        col_6214A = col_FD5E4.column(heading='', align=False)
        col_6214A.alert = False
        col_6214A.enabled = True
        col_6214A.use_property_split = False
        col_6214A.use_property_decorate = False
        col_6214A.scale_x = 1.0
        col_6214A.scale_y = 1.0
        col_6214A.alignment = 'Expand'.upper()
        split_A69D8 = col_6214A.split(factor=0.05000000074505806, align=False)
        split_A69D8.alert = False
        split_A69D8.enabled = True
        split_A69D8.use_property_split = False
        split_A69D8.use_property_decorate = False
        split_A69D8.scale_x = 1.0
        split_A69D8.scale_y = 1.100000023841858
        split_A69D8.alignment = 'Expand'.upper()
        split_A69D8.prop(bpy.context.scene, 'sna_g108_collision', text='', icon_value=0, emboss=True)
        split_A69D8.label(text='碰撞可视', icon_value=0)
        if bpy.context.scene.sna_g108_collision:
            layout_function = col_6214A
            sna_func_5BBCB(layout_function, )
        else:
            pass
        col_82BA2 = col_FD5E4.column(heading='', align=False)
        col_82BA2.alert = False
        col_82BA2.enabled = True
        col_82BA2.use_property_split = False
        col_82BA2.use_property_decorate = False
        col_82BA2.scale_x = 1.0
        col_82BA2.scale_y = 1.0
        col_82BA2.alignment = 'Expand'.upper()
        split_EB690 = col_82BA2.split(factor=0.05000000074505806, align=False)
        split_EB690.alert = False
        split_EB690.enabled = True
        split_EB690.use_property_split = False
        split_EB690.use_property_decorate = False
        split_EB690.scale_x = 1.0
        split_EB690.scale_y = 1.100000023841858
        split_EB690.alignment = 'Expand'.upper()
        split_EB690.prop(bpy.context.scene, 'sna_g108_uv_accuracy', text='', icon_value=0, emboss=True)
        split_EB690.label(text='UV精度可视', icon_value=0)
        if bpy.context.scene.sna_g108_uv_accuracy:
            layout_function = col_82BA2
            sna_uv_83FC6(layout_function, )
        else:
            pass
        col_BF1C6 = col_FD5E4.column(heading='', align=False)
        col_BF1C6.alert = False
        col_BF1C6.enabled = True
        col_BF1C6.use_property_split = False
        col_BF1C6.use_property_decorate = False
        col_BF1C6.scale_x = 1.0
        col_BF1C6.scale_y = 1.0
        col_BF1C6.alignment = 'Expand'.upper()
        split_6C9B5 = col_BF1C6.split(factor=0.05000000074505806, align=False)
        split_6C9B5.alert = False
        split_6C9B5.enabled = True
        split_6C9B5.use_property_split = False
        split_6C9B5.use_property_decorate = False
        split_6C9B5.scale_x = 1.0
        split_6C9B5.scale_y = 1.100000023841858
        split_6C9B5.alignment = 'Expand'.upper()
        split_6C9B5.prop(bpy.context.scene, 'sna_g108_uv_visualization', text='', icon_value=0, emboss=True)
        split_6C9B5.label(text='UV可视化', icon_value=0)
        if bpy.context.scene.sna_g108_uv_visualization:
            layout_function = col_BF1C6
            sna_uv_FD89B(layout_function, )
        else:
            pass
        col_1C64B = col_C106B.column(heading='', align=False)
        col_1C64B.alert = False
        col_1C64B.enabled = True
        col_1C64B.use_property_split = False
        col_1C64B.use_property_decorate = False
        col_1C64B.scale_x = 1.0
        col_1C64B.scale_y = 1.0
        col_1C64B.alignment = 'Expand'.upper()
        split_99173 = col_1C64B.split(factor=0.05000000074505806, align=False)
        split_99173.alert = False
        split_99173.enabled = True
        split_99173.use_property_split = False
        split_99173.use_property_decorate = False
        split_99173.scale_x = 1.0
        split_99173.scale_y = 1.100000023841858
        split_99173.alignment = 'Expand'.upper()
        split_99173.prop(bpy.context.scene, 'sna_g108_pbr_preview', text='', icon_value=0, emboss=True)
        split_99173.label(text='PBR通道', icon_value=0)
        if bpy.context.scene.sna_g108_pbr_preview:
            layout_function = col_1C64B
            sna_pbr_92959(layout_function, )
        else:
            pass
        col_F3A6B = col_C106B.column(heading='', align=False)
        col_F3A6B.alert = False
        col_F3A6B.enabled = True
        col_F3A6B.use_property_split = False
        col_F3A6B.use_property_decorate = False
        col_F3A6B.scale_x = 1.0
        col_F3A6B.scale_y = 1.0
        col_F3A6B.alignment = 'Expand'.upper()
        split_42B69 = col_F3A6B.split(factor=0.05000000074505806, align=False)
        split_42B69.alert = False
        split_42B69.enabled = True
        split_42B69.use_property_split = False
        split_42B69.use_property_decorate = False
        split_42B69.scale_x = 1.0
        split_42B69.scale_y = 1.100000023841858
        split_42B69.alignment = 'Expand'.upper()
        split_42B69.prop(bpy.context.scene, 'sna_g108_map_check', text='', icon_value=0, emboss=True)
        split_42B69.label(text='贴图检查', icon_value=0)
        if bpy.context.scene.sna_g108_map_check:
            layout_function = col_F3A6B
            sna_func_2520D(layout_function, )
        else:
            pass
        col_AF4E2 = col_C106B.column(heading='', align=False)
        col_AF4E2.alert = False
        col_AF4E2.enabled = True
        col_AF4E2.use_property_split = False
        col_AF4E2.use_property_decorate = False
        col_AF4E2.scale_x = 1.0
        col_AF4E2.scale_y = 1.0
        col_AF4E2.alignment = 'Expand'.upper()
        split_7C783 = col_AF4E2.split(factor=0.05000000074505806, align=False)
        split_7C783.alert = False
        split_7C783.enabled = True
        split_7C783.use_property_split = False
        split_7C783.use_property_decorate = False
        split_7C783.scale_x = 1.0
        split_7C783.scale_y = 1.100000023841858
        split_7C783.alignment = 'Expand'.upper()
        split_7C783.prop(bpy.context.scene, 'sna_g108_plugin_check', text='', icon_value=0, emboss=True)
        split_7C783.label(text='插件检查', icon_value=0)
        if bpy.context.scene.sna_g108_plugin_check:
            layout_function = col_AF4E2
            sna_func_94954(layout_function, )
        else:
            pass









def sna_update_sna_g108_lod_switch(self, context):
    sna_update_sna_g108_lod_switch_DE004(self, context)
    sna_update_sna_g108_lod_switch_4C72D(self, context)











def register():
    
    global _icons
    _icons = bpy.utils.previews.new()
    bpy.types.Scene.sna_g108_lod = bpy.props.BoolProperty(name='G108_lod', description='', default=False)
    bpy.types.Scene.sna_g108_modidchoice = bpy.props.BoolProperty(name='G108_modidchoice', description='', default=False)
    bpy.types.Scene.sna_g108_information = bpy.props.BoolProperty(name='G108_Information', description='', default=False)
    bpy.types.Scene.sna_g108_collision = bpy.props.BoolProperty(name='G108_collision', description='', default=False)
    bpy.types.Scene.sna_g108_uv_accuracy = bpy.props.BoolProperty(name='G108_uv accuracy', description='', default=False)
    bpy.types.Scene.sna_g108_uv_visualization = bpy.props.BoolProperty(name='G108_uv visualization', description='', default=False)
    bpy.types.Scene.sna_g108_pbr_preview = bpy.props.BoolProperty(name='G108_pbr preview', description='', default=False)
    bpy.types.Scene.sna_g108_map_check = bpy.props.BoolProperty(name='G108_map check', description='', default=False)
    bpy.types.Scene.sna_g108_plugin_check = bpy.props.BoolProperty(name='G108_plugin check', description='', default=False)
    bpy.types.Scene.sna_g108_lod_switch = bpy.props.IntProperty(name='G108_lod switch', description='', default=0, subtype='NONE', update=sna_update_sna_g108_lod_switch)
    bpy.types.Scene.sna_g108_wireframe = bpy.props.BoolProperty(name='G108_wireframe', description='', default=False, update=sna_update_sna_g108_wireframe_150BE)
    bpy.types.Scene.sna_g108_bounding_box = bpy.props.BoolProperty(name='G108_bounding box', description='', default=False, update=sna_update_sna_g108_bounding_box_9CDA1)
    bpy.types.Scene.sna_g108_modid = bpy.props.IntProperty(name='G108_modid', description='', default=0, subtype='NONE', min=1, max=18, update=sna_update_sna_g108_modid_D68E5)
    bpy.types.Scene.sna_g108_modidswitch = bpy.props.BoolProperty(name='G108_modidswitch', description='', default=False)
    bpy.types.Scene.sna_g108_1uaccuracy = bpy.props.FloatProperty(name='G108_1uaccuracy', description='', default=1.0, subtype='NONE', unit='NONE', min=0.009999999776482582, max=10.0, step=1, precision=2, update=sna_update_sna_g108_1uaccuracy_69059)
    bpy.types.Scene.sna_g108_2uaccuracy = bpy.props.FloatProperty(name='G108_2uaccuracy', description='', default=1.0, subtype='NONE', unit='NONE', min=0.009999999776482582, max=10.0, step=1, precision=2, update=sna_update_sna_g108_2uaccuracy_53502)
    bpy.types.Scene.sna_g108_datamat = bpy.props.EnumProperty(name='G108_Datamat', description='', items=sna_g108_datamat_enum_items, update=sna_update_sna_g108_datamat_AB115)
    
    
    bpy.utils.register_class(SNA_OT_Z_Id_1B5Df)
    bpy.utils.register_class(SNA_OT_Id_E72Da)
    bpy.utils.register_class(SNA_OT_My_Generic_Operator_3C6Ec)
    bpy.utils.register_class(SNA_OT_My_Generic_Operator_95C4A)
    bpy.utils.register_class(SNA_OT_Lod1_5De1D)
    bpy.utils.register_class(SNA_OT_Lod0_979B2)
    bpy.utils.register_class(SNA_OT_Lod2_5Ccf6)
    bpy.utils.register_class(SNA_OT_Lod3_497C0)
    bpy.utils.register_class(SNA_OT_My_Generic_Operator_3684F)
    bpy.utils.register_class(SNA_OT_Ao_Cccb1)
    bpy.utils.register_class(SNA_OT_My_Generic_Operator_91D9B)
    bpy.utils.register_class(SNA_OT_My_Generic_Operator_2965D)
    bpy.utils.register_class(SNA_OT_My_Generic_Operator_Cf834)
    bpy.utils.register_class(SNA_OT_My_Generic_Operator_359F7)
    bpy.utils.register_class(SNA_OT_My_Generic_Operator_2307D)
    bpy.utils.register_class(SNA_OT_Pbr_0D0F8)
    bpy.utils.register_class(SNA_OT_My_Generic_Operator_35D4E)
    bpy.utils.register_class(SNA_OT_My_Generic_Operator_27112)
    bpy.utils.register_class(SNA_OT_U_52F33)
    bpy.utils.register_class(SNA_OT_U_74C11)
    bpy.utils.register_class(SNA_OT_My_Generic_Operator_B6304)
    bpy.utils.register_class(SNA_OT_Uv_62070)
    bpy.utils.register_class(SNA_OT_Uv_176Be)
    bpy.utils.register_class(SNA_OT_Uv_E31Ce)
    bpy.utils.register_class(SNA_OT_Id_36Dc1)
    bpy.utils.register_class(SNA_OT_Uv_67090)
    bpy.utils.register_class(SNA_OT_U_18E4B)
    bpy.utils.register_class(SNA_OT_U_1Ad31)
    bpy.utils.register_class(SNA_OT_Uv_515Ee)
    bpy.utils.register_class(SNA_OT_My_Generic_Operator_64510)
    bpy.utils.register_class(SNA_OT_My_Generic_Operator_0E33A)
    bpy.utils.register_class(SNA_OT_My_Generic_Operator_B6263)
    bpy.types.VIEW3D_MT_editor_menus.prepend(sna_add_to_view3d_mt_editor_menus_98DAC)
    bpy.utils.register_class(SNA_PT_NEW_PANEL_07F13)
    bpy.utils.register_class(SNA_OT_My_Generic_Operator_07104)
    bpy.utils.register_class(SNA_OT_My_Generic_Operator_9Bd9C)
    bpy.utils.register_class(SNA_OT_My_Generic_Operator_B6166)
    bpy.utils.register_class(SNA_OT_My_Generic_Operator_880Fd)
    bpy.utils.register_class(SNA_OT_My_Generic_Operator_F808B)
    bpy.app.handlers.depsgraph_update_post.append(depsgraph_update_post_handler_46A22)
    bpy.utils.register_class(SNA_OT_My_Generic_Operator_88F4F)
    bpy.utils.register_class(SNA_OT_My_Generic_Operator_E59Ea)
    bpy.utils.register_class(SNA_OT_My_Generic_Operator_23C6E)
    bpy.utils.register_class(SNA_OT_My_Generic_Operator_A0F18)
    bpy.utils.register_class(SNA_OT_Id_Fa001)
    bpy.utils.register_class(SNA_OT_My_Generic_Operator_F6F7F)
    bpy.utils.register_class(SNA_OT_My_Generic_Operator_40218)
    bpy.utils.register_class(SNA_PT_V20_C611B)

def unregister():
    
    global _icons
    bpy.utils.previews.remove(_icons)
    
    wm = bpy.context.window_manager
    kc = wm.keyconfigs.addon
    for km, kmi in addon_keymaps.values():
        km.keymap_items.remove(kmi)
    addon_keymaps.clear()
    del bpy.types.Scene.sna_g108_datamat
    del bpy.types.Scene.sna_g108_2uaccuracy
    del bpy.types.Scene.sna_g108_1uaccuracy
    del bpy.types.Scene.sna_g108_modidswitch
    del bpy.types.Scene.sna_g108_modid
    del bpy.types.Scene.sna_g108_bounding_box
    del bpy.types.Scene.sna_g108_wireframe
    del bpy.types.Scene.sna_g108_lod_switch
    del bpy.types.Scene.sna_g108_plugin_check
    del bpy.types.Scene.sna_g108_map_check
    del bpy.types.Scene.sna_g108_pbr_preview
    del bpy.types.Scene.sna_g108_uv_visualization
    del bpy.types.Scene.sna_g108_uv_accuracy
    del bpy.types.Scene.sna_g108_collision
    del bpy.types.Scene.sna_g108_information
    del bpy.types.Scene.sna_g108_modidchoice
    del bpy.types.Scene.sna_g108_lod
    
    
    bpy.utils.unregister_class(SNA_OT_Z_Id_1B5Df)
    bpy.utils.unregister_class(SNA_OT_Id_E72Da)
    bpy.utils.unregister_class(SNA_OT_My_Generic_Operator_3C6Ec)
    bpy.utils.unregister_class(SNA_OT_My_Generic_Operator_95C4A)
    bpy.utils.unregister_class(SNA_OT_Lod1_5De1D)
    bpy.utils.unregister_class(SNA_OT_Lod0_979B2)
    bpy.utils.unregister_class(SNA_OT_Lod2_5Ccf6)
    bpy.utils.unregister_class(SNA_OT_Lod3_497C0)
    bpy.utils.unregister_class(SNA_OT_My_Generic_Operator_3684F)
    bpy.utils.unregister_class(SNA_OT_Ao_Cccb1)
    bpy.utils.unregister_class(SNA_OT_My_Generic_Operator_91D9B)
    bpy.utils.unregister_class(SNA_OT_My_Generic_Operator_2965D)
    bpy.utils.unregister_class(SNA_OT_My_Generic_Operator_Cf834)
    bpy.utils.unregister_class(SNA_OT_My_Generic_Operator_359F7)
    bpy.utils.unregister_class(SNA_OT_My_Generic_Operator_2307D)
    bpy.utils.unregister_class(SNA_OT_Pbr_0D0F8)
    bpy.utils.unregister_class(SNA_OT_My_Generic_Operator_35D4E)
    bpy.utils.unregister_class(SNA_OT_My_Generic_Operator_27112)
    bpy.utils.unregister_class(SNA_OT_U_52F33)
    bpy.utils.unregister_class(SNA_OT_U_74C11)
    bpy.utils.unregister_class(SNA_OT_My_Generic_Operator_B6304)
    bpy.utils.unregister_class(SNA_OT_Uv_62070)
    bpy.utils.unregister_class(SNA_OT_Uv_176Be)
    bpy.utils.unregister_class(SNA_OT_Uv_E31Ce)
    bpy.utils.unregister_class(SNA_OT_Id_36Dc1)
    bpy.utils.unregister_class(SNA_OT_Uv_67090)
    bpy.utils.unregister_class(SNA_OT_U_18E4B)
    bpy.utils.unregister_class(SNA_OT_U_1Ad31)
    bpy.utils.unregister_class(SNA_OT_Uv_515Ee)
    bpy.utils.unregister_class(SNA_OT_My_Generic_Operator_64510)
    bpy.utils.unregister_class(SNA_OT_My_Generic_Operator_0E33A)
    bpy.utils.unregister_class(SNA_OT_My_Generic_Operator_B6263)
    bpy.types.VIEW3D_MT_editor_menus.remove(sna_add_to_view3d_mt_editor_menus_98DAC)
    bpy.utils.unregister_class(SNA_PT_NEW_PANEL_07F13)
    bpy.utils.unregister_class(SNA_OT_My_Generic_Operator_07104)
    bpy.utils.unregister_class(SNA_OT_My_Generic_Operator_9Bd9C)
    bpy.utils.unregister_class(SNA_OT_My_Generic_Operator_B6166)
    bpy.utils.unregister_class(SNA_OT_My_Generic_Operator_880Fd)
    bpy.utils.unregister_class(SNA_OT_My_Generic_Operator_F808B)
    bpy.app.handlers.depsgraph_update_post.remove(depsgraph_update_post_handler_46A22)
    bpy.utils.unregister_class(SNA_OT_My_Generic_Operator_88F4F)
    bpy.utils.unregister_class(SNA_OT_My_Generic_Operator_E59Ea)
    bpy.utils.unregister_class(SNA_OT_My_Generic_Operator_23C6E)
    bpy.utils.unregister_class(SNA_OT_My_Generic_Operator_A0F18)
    bpy.utils.unregister_class(SNA_OT_Id_Fa001)
    bpy.utils.unregister_class(SNA_OT_My_Generic_Operator_F6F7F)
    bpy.utils.unregister_class(SNA_OT_My_Generic_Operator_40218)
    bpy.utils.unregister_class(SNA_PT_V20_C611B)

