import bpy
from ...base_node import SN_ScriptingBaseNode

class AddAndLinkNodesOperator3(bpy.types.Operator):
    bl_idname = "node.add_and_link_nodes3"
    bl_label = "Add and Link Nodes 3"

    def execute(self, context):
        node_tree = context.space_data.edit_tree

        try:
            # Add first node
            bpy.ops.node.add_node(use_transform=True, type="SN_PanelNode")
            first_node = context.active_node

            # Add second node
            bpy.ops.node.add_node(use_transform=True, type="SN_LabelNodeNew")
            second_node = context.active_node
            
            # Adjust the location of the second node
            second_node.location.x += 300  # Adjust the value as needed

            # Link nodes
            links = node_tree.links
            links.new(first_node.outputs[0], second_node.inputs[0])
        except Exception as e:
            self.report({'ERROR'}, f"Failed to add and link nodes: {e}")
            return {'CANCELLED'}

        return {'FINISHED'}
    
class AddAndLinkNodesOperator2(bpy.types.Operator):
    bl_idname = "node.add_and_link_nodes2"
    bl_label = "Add and Link Nodes 2"

    def execute(self, context):
        node_tree = context.space_data.edit_tree

        try:
            # Add first node
            bpy.ops.node.add_node(use_transform=True, type="SN_FunctionNode")
            first_node = context.active_node

            # Add second node
            bpy.ops.node.add_node(use_transform=True, type="SN_FunctionReturnNode")
            second_node = context.active_node
            
            # Adjust the location of the second node
            second_node.location.x += 300  # Adjust the value as needed

            # Link nodes
            links = node_tree.links
            links.new(first_node.outputs[0], second_node.inputs[0])
        except Exception as e:
            self.report({'ERROR'}, f"Failed to add and link nodes: {e}")
            return {'CANCELLED'}

        return {'FINISHED'}

class AddAndLinkNodesOperator(bpy.types.Operator):
    bl_idname = "node.add_and_link_nodes"
    bl_label = "Add and Link Nodes"

    def execute(self, context):
        node_tree = context.space_data.edit_tree

        try:
            # Add first node
            bpy.ops.node.add_node(use_transform=True, type="SN_TriggerNode")
            first_node = context.active_node

            # Add second node
            bpy.ops.node.add_node(use_transform=True, type="SN_PrintNode")
            second_node = context.active_node

            # Adjust the location of the second node
            second_node.location.x += 300  # Adjust the value as needed

            # Link nodes
            links = node_tree.links
            links.new(first_node.outputs[0], second_node.inputs[0])
        except Exception as e:
            self.report({'ERROR'}, f"Failed to add and link nodes: {e}")
            return {'CANCELLED'}

        return {'FINISHED'}

class ChangeNodeColorOperator(bpy.types.Operator):
    bl_idname = "node.change_node_color"
    bl_label = "Change Node Color"

    node_name: bpy.props.StringProperty()
    color: bpy.props.FloatVectorProperty(subtype='COLOR', size=3, min=0.0, max=1.0)

    def execute(self, context):
        node_tree = context.space_data.edit_tree
        if self.node_name in node_tree.nodes:
            node = node_tree.nodes[self.node_name]
            node.use_custom_color = True
            node.color = self.color[:3]
        return {'FINISHED'}

class ChangeNodeLabelOperator(bpy.types.Operator):
    bl_idname = "node.change_node_label"
    bl_label = "Change Node Label"

    node_name: bpy.props.StringProperty()
    new_label: bpy.props.StringProperty()

    def execute(self, context):
        node_tree = context.space_data.edit_tree
        if self.node_name in node_tree.nodes:
            node = node_tree.nodes[self.node_name]
            node.label = self.new_label
        return {'FINISHED'}

class SelectNodeOperator(bpy.types.Operator):
    bl_idname = "node.select_node"
    bl_label = "Select Node"

    node_name: bpy.props.StringProperty()

    def execute(self, context):
        node_tree = context.space_data.edit_tree
        if self.node_name in node_tree.nodes:
            for node in node_tree.nodes:
                node.select = False
            node = node_tree.nodes[self.node_name]
            node.select = True
            node_tree.nodes.active = node
        return {'FINISHED'}

class ViewNodeOperator(bpy.types.Operator):
    bl_idname = "node.view_node"
    bl_label = "View Node"

    node_name: bpy.props.StringProperty()

    def execute(self, context):
        node_tree = context.space_data.edit_tree
        if self.node_name in node_tree.nodes:
            for node in node_tree.nodes:
                node.select = False
            node = node_tree.nodes[self.node_name]
            node.select = True
            node_tree.nodes.active = node

            for area in context.screen.areas:
                if area.type == 'NODE_EDITOR':
                    for region in area.regions:
                        if region.type == 'WINDOW':
                            override = {'area': area, 'region': region, 'space': area.spaces.active, 'edit_tree': node_tree}
                            with context.temp_override(**override):
                                bpy.ops.node.view_selected()
                            break
                    break
        return {'FINISHED'}

class DuplicateNodeOperator(bpy.types.Operator):
    bl_idname = "node.duplicate_node"
    bl_label = "Duplicate Node"

    node_name: bpy.props.StringProperty()

    def execute(self, context):
        node_tree = context.space_data.edit_tree
        if self.node_name in node_tree.nodes:
            bpy.ops.node.select_all(action='DESELECT')
            node = node_tree.nodes[self.node_name]
            node.select = True
            bpy.ops.node.duplicate()
        return {'FINISHED'}

class DeleteNodeOperator(bpy.types.Operator):
    bl_idname = "node.delete_node"
    bl_label = "Delete Node"

    node_name: bpy.props.StringProperty()

    def execute(self, context):
        node_tree = context.space_data.edit_tree
        if self.node_name in node_tree.nodes:
            node = node_tree.nodes[self.node_name]
            node_tree.nodes.remove(node)
        return {'FINISHED'}

class ViewNodePropertiesOperator(bpy.types.Operator):
    bl_idname = "node.view_node_properties"
    bl_label = "View Node Properties"

    node_name: bpy.props.StringProperty()

    def execute(self, context):
        node_tree = context.space_data.edit_tree
        if self.node_name in node_tree.nodes:
            node = node_tree.nodes[self.node_name]
            for prop in dir(node):
                if not prop.startswith("__") and not callable(getattr(node, prop)):
                    self.report({'INFO'}, f"{prop}: {getattr(node, prop)}")
        return {'FINISHED'}

class AlignNodesOperator(bpy.types.Operator):
    bl_idname = "node.align_nodes"
    bl_label = "Align Nodes"

    def execute(self, context):
        node_tree = context.space_data.edit_tree
        x, y = 0, 0
        for node in node_tree.nodes:
            node.location = (x, y)
            x += node.width + 50  # Adjust spacing as needed
        return {'FINISHED'}

class SN_SKD_Node_Actions(SN_ScriptingBaseNode, bpy.types.Node):
    bl_idname = "SN_SKD_Node_Actions"
    bl_label = "Node Actions"
    bl_width_default = 380
    node_color = "STRING"
    node_color = (0.14, 0.17, 0.19)

    selected_node: bpy.props.EnumProperty(
        name="Node",
        description="Select a node",
        items=lambda self, context: [(node.name, node.name, "") for node in self.id_data.nodes]
    )

    color_picker: bpy.props.FloatVectorProperty(
        name="Color",
        description="Color Picker",
        subtype='COLOR',
        default=(0.234085, 0.343199, 1.0),  # Default color including alpha
        size=3,
        min=0.0,
        max=1.0
    )

    new_label: bpy.props.StringProperty(
        name="New Label",
        description="Enter a new label for the selected node",
        default=""
    )
    
    show_box: bpy.props.BoolProperty(
        name="Show Box",
        description="Show or hide the box layout",
        default=True
    )

    show_additional_box: bpy.props.BoolProperty(
        name="Show Additional Box",
        description="Show or hide the additional box layout",
        default=True
    )

    view_properties_text: bpy.props.StringProperty(
        name="Node Properties",
        description="Properties of the selected node",
        default=""
    )

    def draw_buttons(self, context, layout):
        row = layout.row()
        if self.show_box:
            row.prop(self, "show_box", icon="TRIA_DOWN", text="Node", emboss=False)
        else:
            row.prop(self, "show_box", icon="TRIA_RIGHT", text="Node", emboss=False)

        if self.show_box:
            box = layout.box()
            box.label(text=f"Tree: {self.id_data.name}")

            # Dropdown list of nodes
            box.prop(self, "selected_node")
            
            # Create a row for color picker and button
            row = box.row(align=True)
            # Color picker
            row.prop(self, "color_picker")

            # Button to change node color
            op_color = row.operator("node.change_node_color", text="", icon="BACK")
            op_color.node_name = self.selected_node
            op_color.color = self.color_picker
            
            # Input field for new label and button
            row = box.row(align=True)
            row.prop(self, "new_label", text="New Label")
            op_label = row.operator("node.change_node_label", text="", icon="BACK")
            op_label.node_name = self.selected_node
            op_label.new_label = self.new_label

            # Text box displaying node properties
            box.label(text="Node Properties:")
            box.label(text=self.view_properties_text)

        row = layout.row()
        if self.show_additional_box:
            row.prop(self, "show_additional_box", icon="TRIA_DOWN", text="Quick Actions", emboss=False)
        else:
            row.prop(self, "show_additional_box", icon="TRIA_RIGHT", text="Quick Actions", emboss=False)

        if self.show_additional_box:
            additional_box = layout.box()

            additional_row = additional_box.row()
            select_node_op = additional_row.operator("node.select_node", text="Select", icon="RESTRICT_SELECT_OFF")
            select_node_op.node_name = self.selected_node
            
            view_node_op = additional_row.operator("node.view_node", text="Show", icon="ZOOM_SELECTED")
            view_node_op.node_name = self.selected_node

            duplicate_node_op = additional_row.operator("node.duplicate_node", text="Copy", icon="COPYDOWN")
            duplicate_node_op.node_name = self.selected_node

            delete_node_op = additional_row.operator("node.delete_node", text="Delete", icon="X")
            delete_node_op.node_name = self.selected_node

            view_properties_op = additional_row.operator("node.view_node_properties", text="Properties", icon="INFO")
            view_properties_op.node_name = self.selected_node

            align_nodes_op = additional_box.operator("node.align_nodes", text="Align Nodes", icon="GRIP")
            
      
            # Button to add and link nodes
            additional_box.operator("node.add_and_link_nodes", text="Quick Print", icon="BLENDER")
            additional_box.operator("node.add_and_link_nodes2", text="Quick Function", icon="BLENDER")
            additional_box.operator("node.add_and_link_nodes3", text="Quick Panel", icon="BLENDER")

        # Create a grid with 3 icon buttons
        row = layout.row()
        row.alignment = 'CENTER'
        row = layout.row(align=True)
        # Add icon buttons
        row.operator("wm.url_open", text="", icon='QUESTION').url = "https://joshuaknauber.notion.site/555efb921f50426ea4d5812f1aa3e462?v=d781b590cc8f47449cb20812deab0cc6"
        row.operator("wm.url_open", text="", icon='HELP').url = "https://docs.blender.org/manual/en/latest/"
