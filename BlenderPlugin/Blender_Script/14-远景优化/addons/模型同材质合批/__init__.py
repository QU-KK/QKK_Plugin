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
    "name" : "mat_mod merge",
    "author" : "qkk", 
    "description" : "",
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


addon_keymaps = {}
_icons = None
node_tree = {'sna_autophy_s': [], 'sna_autophy': [], }
node_tree_002 = {'sna_obj': [], 'sna_obj_autophy': [], 'sna_kongwuti': [], }


def property_exists(prop_path, glob, loc):
    try:
        eval(prop_path, glob, loc)
        return True
    except:
        return False


def sna_func_190A0(obj_autophy):
    if (len(obj_autophy) > 0):
        bpy.ops.object.select_all(action='DESELECT')
        for i_5E4FA in range(len(obj_autophy)):
            bpy.ops.object.select_pattern(pattern=obj_autophy[i_5E4FA], case_sensitive=True, extend=True)
        bpy.context.view_layer.objects.active = bpy.data.objects[obj_autophy[i_5E4FA]]
        node_tree['sna_autophy_s'] = []
        node_tree['sna_autophy'] = []
        for i_B024A in range(len(bpy.context.view_layer.objects.selected)):
            if '_autophy' in bpy.context.view_layer.objects.selected[i_B024A].name:
                if '_autophy_s' in bpy.context.view_layer.objects.selected[i_B024A].name:
                    node_tree['sna_autophy_s'].append(bpy.context.view_layer.objects.selected[i_B024A].name)
                else:
                    node_tree['sna_autophy'].append(bpy.context.view_layer.objects.selected[i_B024A].name)
        for i_FDF35 in range(len([node_tree['sna_autophy_s'], node_tree['sna_autophy']])):
            bpy.ops.object.select_all(action='DESELECT')
            for i_7CB00 in range(len([node_tree['sna_autophy_s'], node_tree['sna_autophy']][i_FDF35])):
                bpy.ops.object.select_pattern(pattern=[node_tree['sna_autophy_s'], node_tree['sna_autophy']][i_FDF35][i_7CB00], case_sensitive=True, extend=True)
            bpy.context.view_layer.objects.active = bpy.data.objects[[node_tree['sna_autophy_s'], node_tree['sna_autophy']][i_FDF35][i_7CB00]]
            bpy.ops.object.join()
            bpy.context.view_layer.objects.active.name = bpy.context.scene.sna_mod_name + ('_autophy' if bool(i_FDF35) else '_autophy_s')
            bpy.ops.object.material_slot_remove_unused()


class SNA_PT_ACA_70EA6(bpy.types.Panel):
    bl_label = '同材质合并'
    bl_idname = 'SNA_PT_ACA_70EA6'
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
        layout.prop(bpy.context.scene, 'sna_mod_name', text='名称', icon_value=0, emboss=True)
        col_F0DC3 = layout.column(heading='', align=True)
        col_F0DC3.alert = False
        col_F0DC3.enabled = True
        col_F0DC3.active = True
        col_F0DC3.use_property_split = False
        col_F0DC3.use_property_decorate = False
        col_F0DC3.scale_x = 1.0
        col_F0DC3.scale_y = 1.5
        col_F0DC3.alignment = 'Expand'.upper()
        col_F0DC3.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
        op = col_F0DC3.operator('sna.run_0a2de', text='同材质合并', icon_value=0, emboss=True, depress=False)
        col_EA07A = layout.column(heading='', align=True)
        col_EA07A.alert = False
        col_EA07A.enabled = True
        col_EA07A.active = True
        col_EA07A.use_property_split = False
        col_EA07A.use_property_decorate = False
        col_EA07A.scale_x = 1.0
        col_EA07A.scale_y = 1.0
        col_EA07A.alignment = 'Expand'.upper()
        col_EA07A.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
        split_F8E15 = col_EA07A.split(factor=0.5, align=True)
        split_F8E15.alert = False
        split_F8E15.enabled = True
        split_F8E15.active = True
        split_F8E15.use_property_split = False
        split_F8E15.use_property_decorate = False
        split_F8E15.scale_x = 1.0
        split_F8E15.scale_y = 1.0
        split_F8E15.alignment = 'Expand'.upper()
        if not True: split_F8E15.operator_context = "EXEC_DEFAULT"
        split_F8E15.prop(bpy.context.scene, 'sna_c1', text='拆分C1  C2', icon_value=0, emboss=True)
        if bpy.context.scene.sna_c1:
            split_F8E15.prop(bpy.context.scene, 'sna_lod', text='生成lod', icon_value=0, emboss=True)
        col_EA07A.prop(bpy.context.scene, 'sna_mer', text='合并碰撞', icon_value=0, emboss=True)


class SNA_OT_Run_0A2De(bpy.types.Operator):
    bl_idname = "sna.run_0a2de"
    bl_label = "同材质合并_run"
    bl_description = "同材质合并"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        if bpy.app.version >= (3, 0, 0) and True:
            cls.poll_message_set('')
        return not False

    def execute(self, context):
        obj_0_60a92, obj_autophy_1_60a92 = sna_func_548B1()
        if bpy.context.scene.sna_mer:
            sna_func_190A0(obj_autophy_1_60a92)
        sna_func_C41BF(obj_0_60a92)
        return {"FINISHED"}

    def invoke(self, context, event):
        return self.execute(context)


def sna_func_C41BF(obj):
    if (len(obj) > 0):
        bpy.ops.object.select_all(action='DESELECT')
        for i_482BB in range(len(obj)):
            bpy.ops.object.select_pattern(pattern=obj[i_482BB], case_sensitive=True, extend=True)
        bpy.context.view_layer.objects.active = bpy.data.objects[obj[i_482BB]]
        for i_ED361 in range(len(bpy.context.view_layer.objects.selected)):
            if (len(bpy.context.view_layer.objects.selected[i_ED361].data.vertex_colors) == 0):
                bpy.context.view_layer.objects.active = bpy.context.view_layer.objects.selected[i_ED361]
                bpy.ops.geometry.color_attribute_add(name='RGB', domain='CORNER', data_type='BYTE_COLOR', color=(0.0, 0.0, 0.0, 0.0))
            else:
                for i_769BA in range(len(bpy.context.view_layer.objects.selected[i_ED361].data.vertex_colors)):
                    bpy.context.view_layer.objects.selected[i_ED361].data.vertex_colors[i_769BA].name = 'RGB'
                for i_D9A94 in range(len(bpy.context.view_layer.objects.selected[i_ED361].data.vertex_colors)):
                    for i_304E7 in range(len(bpy.context.view_layer.objects.selected[i_ED361].data.vertex_colors)):
                        if (bpy.context.view_layer.objects.selected[i_ED361].data.vertex_colors[i_304E7].name != 'RGB'):
                            bpy.context.view_layer.objects.selected[i_ED361].data.vertex_colors.remove(layer=bpy.context.view_layer.objects.selected[i_ED361].data.vertex_colors[i_304E7], )
                            break
        bpy.context.view_layer.objects.selected[i_ED361].data.vertex_colors.active_index = 0
        bpy.context.view_layer.objects.selected[i_ED361].data.vertex_colors.active.active_render = True
        for i_35E47 in range(len(bpy.context.view_layer.objects.selected)):
            for i_B7300 in range(len(bpy.context.view_layer.objects.selected[i_35E47].data.uv_layers)):
                bpy.context.view_layer.objects.selected[i_35E47].data.uv_layers[i_B7300].name = str(int(i_B7300 + 1.0)) + 'U'
            for i_6DEE2 in range(len(bpy.context.view_layer.objects.selected[i_35E47].data.uv_layers)):
                for i_2F963 in range(len(bpy.context.view_layer.objects.selected[i_35E47].data.uv_layers)):
                    if ((bpy.context.view_layer.objects.selected[i_35E47].data.uv_layers[i_2F963].name != '1U') and (bpy.context.view_layer.objects.selected[i_35E47].data.uv_layers[i_2F963].name != '2U')):
                        bpy.context.view_layer.objects.selected[i_35E47].data.uv_layers.remove(layer=bpy.context.view_layer.objects.selected[i_35E47].data.uv_layers[i_2F963], )
                        break
        bpy.context.view_layer.objects.selected[i_35E47].data.uv_layers.active_index = 0
        bpy.context.view_layer.objects.selected[i_35E47].data.uv_layers.active.active_render = True
        bpy.ops.object.join()
        bpy.context.view_layer.objects.active.name = bpy.context.scene.sna_mod_name
        bpy.context.view_layer.objects.active.data.name = bpy.context.scene.sna_mod_name + '_mesh'
        bpy.ops.object.material_slot_remove_unused()
        if bpy.context.scene.sna_c1:
            bpy.ops.sna.my_generic_operator_41ba9()
            if bpy.context.scene.sna_lod:
                bpy.ops.scene.simplygon_generate()


def sna_func_548B1():
    if property_exists("bpy.data.collections[bpy.context.scene.sna_mod_name + '_pre']", globals(), locals()):
        pass
    else:
        uid = bpy.context.scene.collection.session_uid
        collection_name = bpy.context.scene.sna_mod_name + '_pre'
        bpy.ops.object.move_to_collection(collection_uid=uid, is_new=True, new_collection_name=collection_name)
    bpy.ops.object.parent_clear(type='CLEAR_KEEP_TRANSFORM')
    node_tree_002['sna_kongwuti'] = []
    node_tree_002['sna_obj'] = []
    node_tree_002['sna_obj_autophy'] = []
    for i_30084 in range(len(bpy.context.view_layer.objects.selected)):
        if (bpy.context.view_layer.objects.selected[i_30084].type == 'MESH'):
            if '_autophy' in bpy.context.view_layer.objects.selected[i_30084].name:
                node_tree_002['sna_obj_autophy'].append(bpy.context.view_layer.objects.selected[i_30084].name)
            else:
                node_tree_002['sna_obj'].append(bpy.context.view_layer.objects.selected[i_30084].name)
        else:
            node_tree_002['sna_kongwuti'].append(bpy.context.view_layer.objects.selected[i_30084].name)
    bpy.ops.object.select_all(action='DESELECT')
    for i_94D34 in range(len(node_tree_002['sna_kongwuti'])):
        bpy.ops.object.select_pattern(pattern=node_tree_002['sna_kongwuti'][i_94D34], case_sensitive=True, extend=True)
    bpy.ops.object.delete(use_global=False, confirm=True)
    return [node_tree_002['sna_obj'], node_tree_002['sna_obj_autophy']]


def register():
    global _icons
    _icons = bpy.utils.previews.new()
    bpy.types.Scene.sna_mod_name = bpy.props.StringProperty(name='mod_name', description='', default='', subtype='NONE', maxlen=0)
    bpy.types.Scene.sna_c1 = bpy.props.BoolProperty(name='c1', description='', default=False)
    bpy.types.Scene.sna_mer = bpy.props.BoolProperty(name='mer', description='', default=False)
    bpy.types.Scene.sna_lod = bpy.props.BoolProperty(name='lod', description='', default=False)
    bpy.utils.register_class(SNA_PT_ACA_70EA6)
    bpy.utils.register_class(SNA_OT_Run_0A2De)


def unregister():
    global _icons
    bpy.utils.previews.remove(_icons)
    wm = bpy.context.window_manager
    kc = wm.keyconfigs.addon
    for km, kmi in addon_keymaps.values():
        km.keymap_items.remove(kmi)
    addon_keymaps.clear()
    del bpy.types.Scene.sna_lod
    del bpy.types.Scene.sna_mer
    del bpy.types.Scene.sna_c1
    del bpy.types.Scene.sna_mod_name
    bpy.utils.unregister_class(SNA_PT_ACA_70EA6)
    bpy.utils.unregister_class(SNA_OT_Run_0A2De)
