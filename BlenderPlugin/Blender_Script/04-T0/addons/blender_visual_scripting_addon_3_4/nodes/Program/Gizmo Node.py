import bpy
from ..base_node import SN_ScriptingBaseNode

class SN_OT_UpdateGizmoNode(bpy.types.Operator):
    bl_idname = "sn.updategizmonode"
    bl_label = "Update Gizmo Node"

    node_tree_name: bpy.props.StringProperty()
    node_name: bpy.props.StringProperty()

    def execute(self, context):
        print("Gizmo Update")
        node_tree = bpy.data.node_groups.get(self.node_tree_name)

        if node_tree:
            node = node_tree.nodes.get(self.node_name)
            if node and isinstance(node, SN_GizmoNode):
                node._evaluate(context)

        return {'FINISHED'}

def update_gizmo(self, context):
    for node in self.id_data.nodes:
        if isinstance(node, SN_GizmoNode):
            for item in node.gizmo_collection:
                if item == self:
                    node.update_gizmo(context)
                    return

# Define a PropertyGroup for Gizmo Items
class GizmoItem(bpy.types.PropertyGroup):
    # Define properties for each gizmo
    name: bpy.props.StringProperty(name="Name", default="Gizmo", update=update_gizmo)
    icon: bpy.props.StringProperty(name="Icon", default="QUESTION", update=update_gizmo)
    alpha: bpy.props.FloatProperty(name="Alpha", default=1.0, min=0.0, max=1.0, update=update_gizmo)
    color: bpy.props.FloatVectorProperty(name="Color", subtype='COLOR', size=3, default=(0.094, 0.094, 0.094), min=0.0, max=1.0, update=update_gizmo)
    color_highlight: bpy.props.FloatVectorProperty(name="Color Highlight", subtype='COLOR', size=3, default=(0.22, 0.22, 0.22), min=0.0, max=1.0, update=update_gizmo)
    alpha_highlight: bpy.props.FloatProperty(name="Alpha Highlight", default=1.0, min=0.0, max=1.0, update=update_gizmo)
    scale_basis: bpy.props.FloatProperty(name="Scale Basis", default=14.0, update=update_gizmo)
    use_tooltip: bpy.props.BoolProperty(name="Use Tooltip (Operator Description)", default=True, update=update_gizmo)
    show_drag: bpy.props.BoolProperty(name="Show Drag", default=True, update=update_gizmo)
    use_draw_value: bpy.props.BoolProperty(name="Use Draw Value", default=True, update=update_gizmo)
    use_grab_cursor: bpy.props.BoolProperty(name="Use Grab Cursor", default=False, update=update_gizmo)
    
    
    operator: bpy.props.StringProperty(name="Operator", default="sn.dummy_button_operator", update=update_gizmo)


# Operators for adding and removing gizmos
class SN_OT_AddGizmo(bpy.types.Operator):
    bl_idname = "sn.add_gizmo"
    bl_label = "Add Gizmo"

    node_tree_name: bpy.props.StringProperty()
    node_name: bpy.props.StringProperty()

    def execute(self, context):
        node_tree = bpy.data.node_groups.get(self.node_tree_name)
        if node_tree:
            node = node_tree.nodes.get(self.node_name)
            if node and isinstance(node, SN_GizmoNode):
                gizmo_item = node.gizmo_collection.add()
                gizmo_item.name = f"Gizmo {len(node.gizmo_collection)}"
                node.gizmo_index = len(node.gizmo_collection) - 1
        return {'FINISHED'}

class SN_OT_RemoveGizmo(bpy.types.Operator):
    bl_idname = "sn.remove_gizmo"
    bl_label = "Remove Gizmo"

    node_tree_name: bpy.props.StringProperty()
    node_name: bpy.props.StringProperty()

    def execute(self, context):
        node_tree = bpy.data.node_groups.get(self.node_tree_name)
        if node_tree:
            node = node_tree.nodes.get(self.node_name)
            if node and isinstance(node, SN_GizmoNode):
                if node.gizmo_collection:
                    node.gizmo_collection.remove(node.gizmo_index)
                    node.gizmo_index = min(max(0, node.gizmo_index - 1), len(node.gizmo_collection) - 1)
        return {'FINISHED'}
    



class SN_GizmoNode(SN_ScriptingBaseNode, bpy.types.Node):
    bl_idname = "SN_GizmoNode"
    bl_label = "Gizmo Group"
    bl_width_default = 260
    node_color = "PROGRAM"
    is_trigger = True

    def update_gizmo_index(self, context):
        if self.gizmo_collection and len(self.gizmo_collection) > 0:
            gizmo = self.gizmo_collection[self.gizmo_index]
            self.icon_name = gizmo.icon
            
            # Find the integer value for the icon
            for icon in bpy.types.UILayout.bl_rna.functions["prop"].parameters["icon"].enum_items:
                if icon.name == gizmo.icon:
                    self["icon"] = icon.value  # Use ["icon"] to avoid triggering update_selected
                    break
            else:
                self["icon"] = 0  # Default to 0 if icon not found
                
    
    gizmo_type: bpy.props.EnumProperty(items=[("VIEW_3D", "View 3D", "Equal"),
                                            ("IMAGE_EDITOR", "Image Editor", "Not equal"), 
                                            ("NODE_EDITOR", "Node Editor", "Smaller than"), 
                                            ("SEQUENCE_EDITOR", "Sequence Editor", "Bigger than"), 
                                            ("CLIP_EDITOR", "Clip Editor", "Smaller or equal to"), 
                                            ("DOPESHEET_EDITOR", "Dopesheet", "Smaller or equal to"), 
                                            ("GRAPH_EDITOR", "Graph Editor", "Smaller or equal to"), 
                                            ("NLA_EDITOR", "NLA Editor", "Smaller or equal to"), 
                                            ("TEXT_EDITOR", "Text Editor", "Smaller or equal to"), 
                                            ("TOPBAR", "Top Bar", "Smaller or equal to"), 
                                            ("STATUSBAR", "Status Bar", "Smaller or equal to"), 
                                            ("OUTLINER", "Outliner", "Smaller or equal to"), 
                                            ("PROPERTIES", "Properties", "Smaller or equal to"), 
                                            ("SPREADSHEET", "Spreadsheet", "Smaller or equal to"), 
                                            ("PREFERENCES", "Preferences", "Smaller or equal to")],
                                    name="Operation",
                                    description="Operation to perform on the input data",
                                    default="VIEW_3D",
                                    update=SN_ScriptingBaseNode._evaluate)
    draw_area: bpy.props.EnumProperty(
        name="Draw Area",
        description="The type of drawing that should be started",
        items=[("WINDOW", "Window", ""), 
               ("HEADER", "Header", ""), 
               ("CHANNELS", "Channels", ""), 
               ("TEMPORARY", "Temporary", ""), 
               ("UI", "Ui", ""), 
               ("TOOLS", "Tools", ""), 
               ("TOOL_PROPS", "Tool Props", ""), 
               ("ASSET_SHELF", "Asset Shelf", ""), 
               ("ASSET_SHELF_HEADER", "Asset Shelf Header", ""), 
               ("PREVIEW", "Preview", ""), 
               ("HUD", "Hud", ""), 
               ("NAVIGATION_BAR", "Navigation Bar", ""), 
               ("EXECUTE", "Execute", ""), 
               ("FOOTER", "Footer", ""), 
               ("TOOL_HEADER", "Tool Header", ""), 
               ("XR", "Xr", "")],
        default="WINDOW",
        update=SN_ScriptingBaseNode._evaluate)
    

    gizmo_collection: bpy.props.CollectionProperty(type=GizmoItem)
    gizmo_index: bpy.props.IntProperty(name="Gizmo Index", default=0, update=update_gizmo_index)
    
    
    def update_gizmo(self, context):
       
        self._evaluate(context)

    def on_create(self, context):
        # Create input sockets
        self.add_boolean_input("Disable")

        inp = self.add_string_input("GizmoGroup Bl_idname")
        inp.default_value = "my_gizmo_group"
        inp.set_hide(True)

        inp = self.add_string_input("GizmoGroup Label")
        inp.default_value = "My Gizmo Group"
        inp.set_hide(True)

        inp = self.add_float_vector_input("Location")
        inp.size = 2
        inp.default_value[0] = 100
        inp.default_value[1] = 100
        inp.default_value[2] = 0

        self.add_float_input("X Offset").default_value = 46
        self.add_float_input("Y Offset")
        self.ref_ntree = self.node_tree
        self.add_default_gizmo()

    def add_default_gizmo(self):
        gizmo_item = self.gizmo_collection.add()
        gizmo_item.name = "Gizmo 1"
        gizmo_item.icon = "QUESTION"
        gizmo_item.operator = "sn.dummy_button_operator"
        self.gizmo_index = 0  # Set the index to the newly added gizmo
        self.update_gizmo_index(bpy.context)  # Update the icon

    def evaluate(self, context):

        gizmo_group_idname = self.inputs['GizmoGroup Bl_idname'].python_value.strip("'")
        gizmo_group_label = self.inputs['GizmoGroup Label'].python_value.strip("'")
        
        location = self.inputs['Location'].python_value
        x_offset = self.inputs['X Offset'].python_value
        y_offset = self.inputs['Y Offset'].python_value
        
        self.code_import = f"""
        import bpy
        import mathutils
        from bpy.utils import register_class, unregister_class
        from bpy_extras import view3d_utils
            
        """
        
        
        self.code_imperative = f"""

        class {gizmo_group_idname}_{self.static_uid}(bpy.types.GizmoGroup):
            bl_idname = "{gizmo_group_idname}_{self.static_uid}"
            bl_label = "{gizmo_group_label}"
            bl_space_type = "{self.gizmo_type}"
            bl_region_type = "{self.draw_area}"
            bl_options = {{'PERSISTENT', 'SCALE', 'SHOW_MODAL_ALL'}}


            @classmethod
            def poll(cls, context):
                area = context.area
                if area and area.spaces and hasattr(area.spaces[0], "show_gizmo"):
                    return area.spaces[0].show_gizmo and not {self.inputs[0].python_value}
                return False

            def draw_prepare(self, context):
                # Location
                r_xpos, y_pos = {location}
                # Spacing
                x_offset = {x_offset}
                y_offset = {y_offset}

                for gizmo in self.gizmos:
                    gizmo.matrix_basis[0][3], gizmo.matrix_basis[1][3] = r_xpos, y_pos
                    r_xpos += x_offset
                    y_pos += y_offset
            
            def setup(self, context):
            
        """
        

        # Loop over the gizmo collection and add code for each gizmo
        gizmo_code = ""
        for index, gizmo in enumerate(self.gizmo_collection):
            # Convert colors to tuples
            color = tuple(gizmo.color)
            color_highlight = tuple(gizmo.color_highlight)
            # Name each gizmo uniquely
            gizmo_name = f"gizmo_{index}"
            gizmo_code += f"""
                mpr = self.gizmos.new("GIZMO_GT_button_2d")
                mpr.bl_idname = "{gizmo_name}"
                mpr.draw_options = {{'BACKDROP', 'OUTLINE'}}
                mpr.icon = '{gizmo.icon}'
                mpr.alpha = {gizmo.alpha}
                mpr.color = {color}
                mpr.color_highlight = {color_highlight}
                mpr.alpha_highlight = {gizmo.alpha_highlight}
                mpr.scale_basis = {gizmo.scale_basis}
                mpr.use_tooltip = {gizmo.use_tooltip}
                mpr.show_drag = {gizmo.show_drag}
                mpr.use_draw_value = {gizmo.use_draw_value}
                mpr.use_grab_cursor = {gizmo.use_grab_cursor}


                mpr.target_set_operator("{gizmo.operator}")
            """

        self.code_imperative += gizmo_code

        self.code_register = f"""
            classes = [{gizmo_group_idname}_{self.static_uid}]
            for cls in classes:
                register_class(cls)
        """

        self.code_unregister = f"""
            classes = [{gizmo_group_idname}_{self.static_uid}]
            for cls in reversed(classes):
                unregister_class(cls)
        """

        

    def update_custom_operator(self, context):
        """ Updates the nodes settings when a new parent panel is selected """

        if self.ref_ntree and self.ref_SN_OperatorNode in self.ref_ntree.nodes:
            parent = self.ref_ntree.nodes[self.ref_SN_OperatorNode]
            for prop in parent.properties:
                if prop.property_type in ["Integer", "Float", "Boolean"] and prop.settings.is_vector:
                    socket = self._add_input(self.socket_names[prop.property_type + " Vector"], prop.name)
                    socket.size = prop.settings.size
                    socket.can_be_disabled = True
                elif prop.property_type == "Enum":
                    if prop.stngs_enum.enum_flag:
                        socket = self._add_input(self.socket_names["Enum Set"], prop.name)
                    else:
                        socket = self._add_input(self.socket_names[prop.property_type], prop.name)
                    socket.items = str(list(map(lambda item: item.name, prop.stngs_enum.items)))
                else:
                    self._add_input(self.socket_names[prop.property_type], prop.name).can_be_disabled = True

            gizmo = self.gizmo_collection[self.gizmo_index]
            op_node = self.ref_ntree.nodes[self.ref_SN_OperatorNode]
            op_node = op_node.operator_python_name
            gizmo.operator = f"sna.{op_node}"



        self._evaluate(context)

    def update_source_type(self, context):
        pass

    ref_ntree: bpy.props.PointerProperty(type=bpy.types.NodeTree,
                                    name="Panel Node Tree",
                                    description="The node tree to select the operator from",
                                    poll=SN_ScriptingBaseNode.ntree_poll,
                                    update=SN_ScriptingBaseNode._evaluate)

    source_type: bpy.props.EnumProperty(name="Source Type",
                                    description="Use a custom operator or a blender internal",
                                    items=[("BLENDER", "Blender", "Blender", "BLENDER", 0),
                                        ("CUSTOM", "Custom", "Custom", "FILE_SCRIPT", 1)],
                                    default="CUSTOM" ,
                                    update=update_source_type)

    ref_SN_OperatorNode: bpy.props.StringProperty(name="Custom Operator",
                                    description="The operator ran by this button",
                                    update=update_custom_operator)


    
    
    def update_selected(self, context):
        for icon in bpy.types.UILayout.bl_rna.functions["prop"].parameters["icon"].enum_items:
            if icon.value == self.icon:
                self.icon_name = icon.name
                gizmo = self.gizmo_collection[self.gizmo_index]
                gizmo.icon = self.icon_name
                return
        self.icon_name = "NONE"
        self["icon"] = 0

    icon: bpy.props.IntProperty(name="Value", description="Value of this socket", update=update_selected)
    icon_name: bpy.props.StringProperty(default="NONE" ,update=SN_ScriptingBaseNode._evaluate)
    

            
    def draw_node(self, context, layout):
        # Display the gizmo collection and operators
        row = layout.row()
        row.label(text="Gizmos:")

        row = layout.row()
        row.template_list("UI_UL_list", "gizmos", self, "gizmo_collection", self, "gizmo_index", item_dyntip_propname="name")
        col = row.column(align=True)
        op = col.operator("sn.add_gizmo", icon='ADD', text="")
        op.node_tree_name = self.id_data.name
        op.node_name = self.name
        op = col.operator("sn.remove_gizmo", icon='REMOVE', text="")
        op.node_tree_name = self.id_data.name
        op.node_name = self.name

        if self.gizmo_collection and len(self.gizmo_collection) > 0:
            gizmo = self.gizmo_collection[self.gizmo_index]
            
            row = layout.row()
            
            # Create a box layout for gizmo properties
            box = layout.box()
            col = box.column(align=False)
            col.label(text=f"{gizmo.name} Properties")
            col.prop(gizmo, "name")
            # col.prop(gizmo, "icon")

            inp = col.operator("sn.select_icon", text="Choose Icon", icon_value=self.icon)
            inp.icon_data_path = f"bpy.data.node_groups['{self.node_tree.name}'].nodes['{self.name}']"

            col = box.column(align=False)
            col.prop(gizmo, "color")
            col.prop(gizmo, "color_highlight")
            col.prop(gizmo, "alpha")
            col.prop(gizmo, "alpha_highlight")
            col.prop(gizmo, "scale_basis")
            col.prop(gizmo, "use_tooltip")
            col.prop(gizmo, "show_drag")
            col.prop(gizmo, "use_draw_value")
            col.prop(gizmo, "use_grab_cursor")
            

            col.separator()
            col2 = col.box()
            if gizmo.operator == "":
                col2.alert = True
                col2.label(text=f"Assign an operator to {gizmo.name}")
            else:
                col2.alert = False
                col2.prop(gizmo, "operator", emboss=False)

            row = col2.row(align=True)
            
            if self.source_type == "BLENDER":
                name = "Paste Operator"
                if self.pasted_operator:
                    if self.pasted_name:
                        name = self.pasted_name
                    elif len(self.pasted_operator.split(".")) > 2:
                        name = self.pasted_operator.split(".")[3].split("(")[0].replace("_", " ").title()
                    else:
                        name = self.pasted_operator
                op = row.operator("sn.paste_operator", text=name, icon="PASTEDOWN")
                op.node_tree = self.node_tree.name
                op.node = self.name

            elif self.source_type == "CUSTOM":
                parent_tree = self.ref_ntree if self.ref_ntree else self.node_tree
                row.prop_search(self, "ref_ntree", bpy.data, "node_groups", text="")
                subrow = row.row(align=True)
                subrow.enabled = self.ref_ntree is not None
                subrow.prop_search(self, "ref_SN_OperatorNode", bpy.data.node_groups[parent_tree.name].node_collection("SN_OperatorNode"), "refs", text="")

                subrow = row.row()
                subrow.enabled = self.ref_ntree is not None and self.ref_SN_OperatorNode in self.ref_ntree.nodes


        # Create a separate box for GizmoGroup properties
        gizmo_group_box = layout.box()
        gizmo_group_box.prop(self.inputs["GizmoGroup Bl_idname"], "default_value", text="ID Name")
        gizmo_group_box.prop(self.inputs["GizmoGroup Label"], "default_value", text="Label")
        gizmo_group_box.prop(self, "gizmo_type", text='')
        gizmo_group_box.prop(self, "draw_area", text='')



