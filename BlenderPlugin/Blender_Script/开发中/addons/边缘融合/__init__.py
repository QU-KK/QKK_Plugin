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
    "name" : "Edge_Blending_v1",
    "author" : "QKK", 
    "description" : "One-click edge blending, processed with the compositor, without modifying any materials",
    "blender" : (4, 5, 0),
    "version" : (1, 0, 0),
    "location" : "",
    "warning" : "",
    "doc_url": "", 
    "tracker_url": "https://superhivemarket.com/creators/qkk", 
    "category" : "3D View" 
}


import bpy
import bpy.utils.previews
import os
import webbrowser




def string_to_int(value):
    if value.isdigit():
        return int(value)
    return 0


def string_to_icon(value):
    if value in bpy.types.UILayout.bl_rna.functions["prop"].parameters["icon"].enum_items.keys():
        return bpy.types.UILayout.bl_rna.functions["prop"].parameters["icon"].enum_items[value].value
    return string_to_int(value)


addon_keymaps = {}
_icons = None
node_tree = {'sna_mat_name': [], }


def property_exists(prop_path, glob, loc):
    try:
        eval(prop_path, glob, loc)
        return True
    except:
        return False


class SNA_PT_EDGE_BLENDING_B91C1(bpy.types.Panel):
    bl_label = 'Edge_Blending'
    bl_idname = 'SNA_PT_EDGE_BLENDING_B91C1'
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_context = ''
    bl_category = 'Edge_Blending'
    bl_order = 0
    bl_ui_units_x=0

    @classmethod
    def poll(cls, context):
        return not (False)

    def draw_header(self, context):
        layout = self.layout

    def draw(self, context):
        layout = self.layout
        col_C6C3A = layout.column(heading='', align=False)
        col_C6C3A.alert = False
        col_C6C3A.enabled = True
        col_C6C3A.active = True
        col_C6C3A.use_property_split = False
        col_C6C3A.use_property_decorate = False
        col_C6C3A.scale_x = 1.0
        col_C6C3A.scale_y = 1.0
        col_C6C3A.alignment = 'Expand'.upper()
        col_C6C3A.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
        split_B5B38 = col_C6C3A.split(factor=0.800000011920929, align=True)
        split_B5B38.alert = False
        split_B5B38.enabled = True
        split_B5B38.active = True
        split_B5B38.use_property_split = False
        split_B5B38.use_property_decorate = False
        split_B5B38.scale_x = 1.0
        split_B5B38.scale_y = 1.0
        split_B5B38.alignment = 'Expand'.upper()
        if not True: split_B5B38.operator_context = "EXEC_DEFAULT"
        split_B5B38.separator(factor=1.0)
        op = split_B5B38.operator('sna.open_18498', text='', icon_value=string_to_icon('INTERNET'), emboss=True, depress=False)
        col_4135C = col_C6C3A.column(heading='', align=False)
        col_4135C.alert = False
        col_4135C.enabled = True
        col_4135C.active = True
        col_4135C.use_property_split = False
        col_4135C.use_property_decorate = False
        col_4135C.scale_x = 1.0
        col_4135C.scale_y = 1.5
        col_4135C.alignment = 'Expand'.upper()
        col_4135C.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
        op = col_4135C.operator('sna.initialization_9fcd7', text='Initialization', icon_value=string_to_icon('TIME'), emboss=True, depress=False)
        if (property_exists("bpy.context.scene.node_tree.nodes", globals(), locals()) and 'Pix_Blend' in bpy.context.scene.node_tree.nodes):
            box_ABA28 = layout.box()
            box_ABA28.alert = False
            box_ABA28.enabled = True
            box_ABA28.active = True
            box_ABA28.use_property_split = False
            box_ABA28.use_property_decorate = False
            box_ABA28.alignment = 'Expand'.upper()
            box_ABA28.scale_x = 1.0
            box_ABA28.scale_y = 1.0
            if not True: box_ABA28.operator_context = "EXEC_DEFAULT"
            col_B8761 = box_ABA28.column(heading='', align=False)
            col_B8761.alert = False
            col_B8761.enabled = True
            col_B8761.active = True
            col_B8761.use_property_split = False
            col_B8761.use_property_decorate = False
            col_B8761.scale_x = 1.0
            col_B8761.scale_y = 1.0
            col_B8761.alignment = 'Expand'.upper()
            col_B8761.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
            col_B8761.prop(bpy.context.scene.node_tree.nodes['Pix_Blend'].inputs['Blend'], 'default_value', text='Blend', icon_value=0, emboss=True)
            split_C6008 = col_B8761.split(factor=0.5, align=True)
            split_C6008.alert = False
            split_C6008.enabled = True
            split_C6008.active = True
            split_C6008.use_property_split = False
            split_C6008.use_property_decorate = False
            split_C6008.scale_x = 1.0
            split_C6008.scale_y = 1.0
            split_C6008.alignment = 'Expand'.upper()
            if not True: split_C6008.operator_context = "EXEC_DEFAULT"
            op = split_C6008.operator('sna.add_24f8e', text='', icon_value=48, emboss=True, depress=False)
            op = split_C6008.operator('sna.delete_c9546', text='', icon_value=91, emboss=True, depress=False)


class SNA_OT_Add_24F8E(bpy.types.Operator):
    bl_idname = "sna.add_24f8e"
    bl_label = "Add"
    bl_description = "Enable blending for the selected model's material"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        if bpy.app.version >= (3, 0, 0) and True:
            cls.poll_message_set('')
        return not False

    def execute(self, context):
        for i_35FDA in range(len(bpy.context.view_layer.objects.selected)):
            for i_A08F7 in range(len(bpy.context.view_layer.objects.selected[i_35FDA].material_slots)):
                if property_exists("bpy.context.view_layer.objects.selected[i_35FDA].material_slots[i_A08F7].material.name", globals(), locals()):
                    if bpy.context.view_layer.objects.selected[i_35FDA].material_slots[i_A08F7].material.name in bpy.context.scene.node_tree.nodes['Pix_Blend_Mat'].matte_id.split(','):
                        pass
                    else:
                        bpy.context.scene.node_tree.nodes['Pix_Blend_Mat'].matte_id = bpy.context.scene.node_tree.nodes['Pix_Blend_Mat'].matte_id + ',' + bpy.context.view_layer.objects.selected[i_35FDA].material_slots[i_A08F7].material.name
                        self.report({'INFO'}, message='OK!')
        return {"FINISHED"}

    def invoke(self, context, event):
        return self.execute(context)


class SNA_OT_Delete_C9546(bpy.types.Operator):
    bl_idname = "sna.delete_c9546"
    bl_label = "Delete"
    bl_description = "Disable blending for the selected model's material"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        if bpy.app.version >= (3, 0, 0) and True:
            cls.poll_message_set('')
        return not False

    def execute(self, context):
        for i_74D93 in range(len(bpy.context.view_layer.objects.selected)):
            for i_21744 in range(len(bpy.context.view_layer.objects.selected[i_74D93].material_slots)):
                if property_exists("bpy.context.view_layer.objects.selected[i_74D93].material_slots[i_21744].material.name", globals(), locals()):
                    if bpy.context.view_layer.objects.selected[i_74D93].material_slots[i_21744].material.name in bpy.context.scene.node_tree.nodes['Pix_Blend_Mat'].matte_id.split(','):
                        node_tree['sna_mat_name'] = bpy.context.scene.node_tree.nodes['Pix_Blend_Mat'].matte_id.split(',')
                        node_tree['sna_mat_name'].remove(bpy.context.view_layer.objects.selected[i_74D93].material_slots[i_21744].material.name)
                        bpy.context.scene.node_tree.nodes['Pix_Blend_Mat'].matte_id = str(node_tree['sna_mat_name']).replace('[', '').replace(']', '').replace("'", '')
                        self.report({'INFO'}, message='OK!')
        return {"FINISHED"}

    def invoke(self, context, event):
        return self.execute(context)


class SNA_OT_My_Generic_Operator_31087(bpy.types.Operator):
    bl_idname = "sna.my_generic_operator_31087"
    bl_label = "移出指定材质"
    bl_description = ""
    bl_options = {"REGISTER", "UNDO"}
    sna_mat_name: bpy.props.StringProperty(name='mat_name', description='', options={'HIDDEN'}, default='', subtype='NONE', maxlen=0)

    @classmethod
    def poll(cls, context):
        if bpy.app.version >= (3, 0, 0) and True:
            cls.poll_message_set('')
        return not False

    def execute(self, context):
        node_tree['sna_mat_name'] = bpy.context.scene.node_tree.nodes['Pix_Blend_Mat'].matte_id.split(',')
        node_tree['sna_mat_name'].remove(self.sna_mat_name)
        bpy.context.scene.node_tree.nodes['Pix_Blend_Mat'].matte_id = str(node_tree['sna_mat_name']).replace('[', '').replace(']', '').replace("'", '')
        self.report({'INFO'}, message='OK!')
        return {"FINISHED"}

    def invoke(self, context, event):
        return self.execute(context)


class SNA_OT_Initialization_9Fcd7(bpy.types.Operator):
    bl_idname = "sna.initialization_9fcd7"
    bl_label = "Initialization"
    bl_description = "Automatically enable related configurations"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        if bpy.app.version >= (3, 0, 0) and True:
            cls.poll_message_set('')
        return not False

    def execute(self, context):
        bpy.context.scene.use_nodes = True
        bpy.context.view_layer.use_pass_cryptomatte_object = True
        bpy.context.view_layer.use_pass_cryptomatte_material = True
        bpy.context.view_layer.use_pass_z = True
        bpy.context.view_layer.pass_cryptomatte_depth = 2
        bpy.context.space_data.shading.use_compositor = 'ALWAYS'
        bpy.context.scene.render.compositor_device = 'GPU'
        bpy.context.scene.render.compositor_denoise_device = 'GPU'
        bpy.context.scene.render.compositor_precision = 'FULL'
        if property_exists("bpy.data.node_groups['Pix_Blend']", globals(), locals()):
            pass
        else:
            before_data = list(bpy.data.node_groups)
            bpy.ops.wm.append(directory=bpy.path.abspath(os.path.join(os.path.dirname(__file__), 'assets', 'ass.blend')) + r'\NodeTree', filename='Pix_Blend', link=False)
            new_data = list(filter(lambda d: not d in before_data, list(bpy.data.node_groups)))
            appended_78692 = None if not new_data else new_data[0]
        tree = bpy.context.scene.node_tree
        if 'Render Layers' not in tree.nodes:
            Render_Layers = tree.nodes.new(type='CompositorNodeRLayers')
            Render_Layers.name = 'Render Layers'
            Render_Layers.location = (-300, 0)
        if 'Viewer' not in tree.nodes:
            Viewer = tree.nodes.new(type='CompositorNodeViewer')
            Viewer.name = 'Viewer'
            Viewer.location = (500, -100)
        if 'Composite' not in tree.nodes:
            Composite = tree.nodes.new(type='CompositorNodeComposite')
            Composite.name = 'Composite'
            Composite.location = (500, 0)
        if 'Pix_Blend_Obj' not in tree.nodes:
            Cryptomatte_obj = tree.nodes.new(type='CompositorNodeCryptomatteV2')
            Cryptomatte_obj.name = 'Pix_Blend_Obj'
            Cryptomatte_obj.location = (0, 0)
            Cryptomatte_obj.layer_name = 'ViewLayer.CryptoObject'
        if 'Pix_Blend_Mat' not in tree.nodes:
            Cryptomatte_mat = tree.nodes.new(type='CompositorNodeCryptomatteV2')
            Cryptomatte_mat.name = 'Pix_Blend_Mat'
            Cryptomatte_mat.location = (0, -250)
            Cryptomatte_mat.layer_name = 'ViewLayer.CryptoMaterial'
        if 'Pix_Blend' not in tree.nodes:
            Pix_Blend = tree.nodes.new(type='CompositorNodeGroup')
            Pix_Blend.name = 'Pix_Blend'
            Pix_Blend.location = (300, 0)
            Pix_Blend.node_tree = bpy.data.node_groups['Pix_Blend']
        Cryptomatte_obj = tree.nodes['Pix_Blend_Obj']
        Cryptomatte_obj_input = Cryptomatte_obj.inputs['Image']
        Cryptomatte_obj_output = Cryptomatte_obj.outputs['Pick']
        Cryptomatte_mat = tree.nodes['Pix_Blend_Mat']
        Cryptomatte_mat_input = Cryptomatte_mat.inputs['Image']
        Cryptomatte_mat_output = Cryptomatte_mat.outputs['Matte']
        Pix_Blend = tree.nodes['Pix_Blend']
        Pix_Blend_input_ID = Pix_Blend.inputs['ID']
        Pix_Blend_input_Mask = Pix_Blend.inputs['Mask']
        Pix_Blend_input_Image = Pix_Blend.inputs['Image']
        Pix_Blend_input_Z = Pix_Blend.inputs['Z']
        Pix_Blend_output = Pix_Blend.outputs['Image']
        render_layers_node = tree.nodes['Render Layers']
        render_layers_output_img = render_layers_node.outputs['Image']
        render_layers_output_z = render_layers_node.outputs['Depth']
        Viewer = tree.nodes['Viewer']
        Composite = tree.nodes['Composite']
        Viewer_input = Viewer.inputs['Image']
        Composite_input = Composite.inputs['Image']
        tree.links.new(Cryptomatte_obj_output, Pix_Blend_input_ID)
        tree.links.new(Cryptomatte_mat_output, Pix_Blend_input_Mask)
        tree.links.new(render_layers_output_img, Cryptomatte_obj_input)
        tree.links.new(render_layers_output_img, Cryptomatte_mat_input)
        tree.links.new(render_layers_output_img, Pix_Blend_input_Image)
        tree.links.new(render_layers_output_z, Pix_Blend_input_Z)
        tree.links.new(Pix_Blend_output, Viewer_input)
        tree.links.new(Pix_Blend_output, Composite_input)
        self.report({'INFO'}, message='OK!')
        return {"FINISHED"}

    def invoke(self, context, event):
        return self.execute(context)


class SNA_OT_Open_18498(bpy.types.Operator):
    bl_idname = "sna.open_18498"
    bl_label = "Open"
    bl_description = "Open the webpage"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        if bpy.app.version >= (3, 0, 0) and True:
            cls.poll_message_set('')
        return not False

    def execute(self, context):
        url = 'https://superhivemarket.com/creators/qkk'
        webbrowser.open(url)
        self.report({'INFO'}, message='OK!')
        return {"FINISHED"}

    def invoke(self, context, event):
        return self.execute(context)


class SNA_PT_MAT_17018(bpy.types.Panel):
    bl_label = 'Mat'
    bl_idname = 'SNA_PT_MAT_17018'
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_context = ''
    bl_order = 0
    bl_options = {'DEFAULT_CLOSED'}
    bl_parent_id = 'SNA_PT_EDGE_BLENDING_B91C1'
    bl_ui_units_x=0

    @classmethod
    def poll(cls, context):
        return not ((not (property_exists("bpy.context.scene.node_tree.nodes", globals(), locals()) and 'Pix_Blend' in bpy.context.scene.node_tree.nodes)))

    def draw_header(self, context):
        layout = self.layout

    def draw(self, context):
        layout = self.layout
        if (0 != len(bpy.context.scene.node_tree.nodes['Pix_Blend_Mat'].matte_id)):
            col_D607D = layout.column(heading='', align=True)
            col_D607D.alert = False
            col_D607D.enabled = True
            col_D607D.active = True
            col_D607D.use_property_split = False
            col_D607D.use_property_decorate = False
            col_D607D.scale_x = 1.0
            col_D607D.scale_y = 1.0
            col_D607D.alignment = 'Expand'.upper()
            col_D607D.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
            for i_E7DB5 in range(len(bpy.context.scene.node_tree.nodes['Pix_Blend_Mat'].matte_id.split(','))):
                box_0A92B = col_D607D.box()
                box_0A92B.alert = False
                box_0A92B.enabled = True
                box_0A92B.active = True
                box_0A92B.use_property_split = False
                box_0A92B.use_property_decorate = False
                box_0A92B.alignment = 'Expand'.upper()
                box_0A92B.scale_x = 1.0
                box_0A92B.scale_y = 1.0
                if not True: box_0A92B.operator_context = "EXEC_DEFAULT"
                split_1484F = box_0A92B.split(factor=0.800000011920929, align=True)
                split_1484F.alert = False
                split_1484F.enabled = True
                split_1484F.active = True
                split_1484F.use_property_split = False
                split_1484F.use_property_decorate = False
                split_1484F.scale_x = 1.0
                split_1484F.scale_y = 1.0
                split_1484F.alignment = 'Expand'.upper()
                if not True: split_1484F.operator_context = "EXEC_DEFAULT"
                split_1484F.label(text=bpy.context.scene.node_tree.nodes['Pix_Blend_Mat'].matte_id.split(',')[i_E7DB5], icon_value=string_to_icon('MATERIAL_DATA'))
                op = split_1484F.operator('sna.my_generic_operator_31087', text='', icon_value=string_to_icon('PANEL_CLOSE'), emboss=True, depress=False)
                op.sna_mat_name = bpy.context.scene.node_tree.nodes['Pix_Blend_Mat'].matte_id.split(',')[i_E7DB5]


def register():
    global _icons
    _icons = bpy.utils.previews.new()
    bpy.utils.register_class(SNA_PT_EDGE_BLENDING_B91C1)
    bpy.utils.register_class(SNA_OT_Add_24F8E)
    bpy.utils.register_class(SNA_OT_Delete_C9546)
    bpy.utils.register_class(SNA_OT_My_Generic_Operator_31087)
    bpy.utils.register_class(SNA_OT_Initialization_9Fcd7)
    bpy.utils.register_class(SNA_OT_Open_18498)
    bpy.utils.register_class(SNA_PT_MAT_17018)


def unregister():
    global _icons
    bpy.utils.previews.remove(_icons)
    wm = bpy.context.window_manager
    kc = wm.keyconfigs.addon
    for km, kmi in addon_keymaps.values():
        km.keymap_items.remove(kmi)
    addon_keymaps.clear()
    bpy.utils.unregister_class(SNA_PT_EDGE_BLENDING_B91C1)
    bpy.utils.unregister_class(SNA_OT_Add_24F8E)
    bpy.utils.unregister_class(SNA_OT_Delete_C9546)
    bpy.utils.unregister_class(SNA_OT_My_Generic_Operator_31087)
    bpy.utils.unregister_class(SNA_OT_Initialization_9Fcd7)
    bpy.utils.unregister_class(SNA_OT_Open_18498)
    bpy.utils.unregister_class(SNA_PT_MAT_17018)
