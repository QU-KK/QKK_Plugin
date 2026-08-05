import bpy
from ...base_node import SN_ScriptingBaseNode


class SN_Display_World_Properties_Node(SN_ScriptingBaseNode, bpy.types.Node):

    bl_idname = "SN_Display_World_Properties_Node"
    bl_label = "MB_Display World Properties (Interface)"
    node_color = "INTERFACE"
    bl_width_default = 200

    def on_create(self, context):
        # create your sockets here

        # inputs
        self.add_interface_input()

        # outputs
        self.add_interface_output()

    def evaluate(self, context):
        # generate the code here

        self.code = f"""
                    def redraw_panel(*args):
                        for window in bpy.context.window_manager.windows:
                            for area in window.screen.areas:
                                if area.type == 'NODE_EDITOR':
                                    area.tag_redraw()

                    bpy.app.handlers.depsgraph_update_post.append(redraw_panel)

                    def panel_node_draw(layout, id_data, output_type, input_name):
                        if not id_data.use_nodes:
                            layout.operator("cycles.use_shading_nodes", icon='NODETREE')
                            return False

                        ntree = id_data.node_tree

                        output_node = None
                        for node in ntree.nodes:
                            if node.type == 'OUTPUT_WORLD':
                                output_node = node
                                break

                        if output_node:
                            input = find_node_input(output_node, input_name)
                            if input:
                                layout.template_node_view(ntree, output_node, input)
                            else:
                                layout.label(text="Incompatible input")
                        else:
                            layout.label(text="No output node")

                        return True

                    def find_node_input(node, input_name):
                        for input in node.inputs:
                            if input.name == input_name:
                                return input
                        return None

                    def draw_surface_panel(context, layout):
                        world = context.scene.world

                        if world:
                            if world.use_nodes:
                                panel_node_draw(layout, world, 'OUTPUT', 'Surface')
                            else:
                                layout.label(text="Node-based shading is disabled for the active World.")
                        else:
                            layout.label(text="No active World found in the scene.")

                    draw_surface_panel(bpy.context, {self.active_layout})

                    {self.indent(self.outputs[0].python_value, 5)}
                    """
