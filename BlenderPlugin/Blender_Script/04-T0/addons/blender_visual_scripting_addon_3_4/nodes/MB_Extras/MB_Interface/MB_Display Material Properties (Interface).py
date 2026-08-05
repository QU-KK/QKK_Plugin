import bpy
from ...base_node import SN_ScriptingBaseNode


class SN_Display_Mat_Surf_Properties_Node(SN_ScriptingBaseNode, bpy.types.Node):

    bl_idname = "SN_Display_Mat_Surf_Properties_Node"
    bl_label = "MB_Display Material/Surface Properties (Interface)"
    node_color = "INTERFACE"
    bl_width_default = 200

    def on_create(self, context):
        # create your sockets here

        # inputs
        self.add_interface_input()
        self.add_boolean_input('Hide Material Properties').default_value = False
        self.add_boolean_input('Hide Surface Properties').default_value = False

        # outputs
        self.add_interface_output()

    def evaluate(self, context):
		# generate the code here
        self.code = f"""
        
                    bool1 = {self.inputs[1].python_value}
                    bool2 = {self.inputs[2].python_value}

                    if bool1 != True:
                        # Get the active object
                        obj = bpy.context.active_object
                
                        # Check if the active object is a mesh, curve, surface, meta, font, or volume object
                        if obj and obj.type in {'MESH', 'CURVE', 'SURFACE', 'META', 'FONT', 'VOLUME'}:
                            {self.active_layout}
                
                            row = layout.row()
                
                            # Create a list of materials
                            materials = obj.material_slots
                
                            # Create a UIList to display the materials
                            row.template_list("MATERIAL_UL_matslots", "", obj, "material_slots", obj, "active_material_index")
                
                            col = row.column(align=True)
                            col.operator("object.material_slot_add", icon='ADD', text="")
                            col.operator("object.material_slot_remove", icon='REMOVE', text="")
                            col.separator()
                            col.menu("MATERIAL_MT_context_menu", icon='DOWNARROW_HLT', text="")
                
                            if len(materials) > 1:
                                col.separator()
                                col.operator("object.material_slot_move", icon='TRIA_UP', text="").direction = 'UP'
                                col.operator("object.material_slot_move", icon='TRIA_DOWN', text="").direction = 'DOWN'
                
                            if obj.mode == 'EDIT':
                                row = layout.row(align=True)
                                row.operator("object.material_slot_assign", text="Assign")
                                row.operator("object.material_slot_select", text="Select")
                                row.operator("object.material_slot_deselect", text="Deselect")
                
                            row = layout.row()
                
                            if obj:
                                row.template_ID(obj, "active_material", new="material.new")
                
                                slot = getattr(bpy.context, 'material_slot', None)
                                if slot:
                                    icon_link = 'MESH_DATA' if slot.link == 'DATA' else 'OBJECT_DATA'
                                    row.prop(slot, "link", text="", icon=icon_link, icon_only=True)
                
                            elif mat:
                                layout.template_ID(bpy.context.space_data, "pin_id")
                                layout.separator()
                    else:
                        pass
                    
                    if bool2 != True:
                        def find_node_input(node, input_name):
                            for input in node.inputs:
                                if input.name == input_name:
                                    return input
                            return None
        
                        def panel_node_draw(layout, id_data, output_type, input_name):
                            if not id_data.use_nodes:
                                layout.operator("cycles.use_shading_nodes", icon='NODETREE')
                                return False
            
                            ntree = id_data.node_tree
            
                            node = ntree.get_output_node(output_type)
                            if node:
                                input = find_node_input(node, input_name)
                                if input:
                                    layout.template_node_view(ntree, node, input)
                                else:
                                    layout.label(text="Incompatible output node")
                            else:
                                layout.label(text="No output node")
            
                            return True
            
                        # Get the active object
                        obj = bpy.context.active_object
            
                        # Check if the active object is a mesh, curve, surface, meta, font, or volume object
                        if obj and obj.type in {'MESH', 'CURVE', 'SURFACE', 'META', 'FONT', 'VOLUME'}:
                            mat = obj.active_material
                            if mat and mat.use_nodes:
                                {self.active_layout}
                                output_type = 'CYCLES'
                                input_name = 'Surface'
                                panel_node_draw(layout, mat, output_type, input_name)
                    else:
                        pass

                    {self.indent(self.outputs[0].python_value, 5)}
                    """
