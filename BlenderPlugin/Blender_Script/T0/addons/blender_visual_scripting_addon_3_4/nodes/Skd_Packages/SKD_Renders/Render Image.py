import bpy 
from ...base_node import SN_ScriptingBaseNode
class SN_SKD_RenderImageNode(SN_ScriptingBaseNode, bpy.types.Node):
    bl_idname = "SN_SKD_RenderImageNode"
    bl_label = "Render Image"
    bl_width_default = 240
    node_color = "PROGRAM"
    
    def on_create(self, context):
        self.add_execute_input()
        self.add_execute_output()
        self.add_string_input("Path").subtype = "DIR_PATH"
        self.add_string_input("File_name").default_value = "My render"
        self.add_integer_input("Seconds").default_value = 5
        self.add_integer_input("Resolution_x").default_value = 500
        self.add_integer_input("Resolution_y").default_value = 500
        self.add_string_input("Scene").default_value = "Scene"

        #["PNG","JPEG","IRIS","BMP","JPEG2000","TARGA","TARGA_RAW"]
    type: bpy.props.EnumProperty(name="",
                                 items=[("PNG", "PNG", "PNG",),
                                        ("JPEG", "JPEG", "JPEG",),
                                        ("IRIS", "IRIS", "IRIS",),
                                        ("BMP", "BMP", "BMP",),
                                        ("JPEG2000", "JPEG2000", "JPEG2000",),
                                        ("TARGA", "TARGA", "TARGA",),
                                        ("TARGA_RAW", "TARGA_RAW", "TARGA_RAW",),
                                        ("WEBP", "WEBP", "WEBP",)
                                        ],
                                 update=SN_ScriptingBaseNode._evaluate)


    def evaluate(self, context):
        
        self.code_import = """
                            import bpy
                            import os
                            """
   
        self.code_imperative = """
                def renders(p_path, p_filename, p_seconds, p_res_x, p_res_y, p_scene, image_type):

                    # Get scene name insert and change to that scene to render
                    scene = bpy.data.scenes.get(p_scene)
                    bpy.context.window.scene = scene

                    # Get the render settings of the selected scene
                    Current_Seconds = bpy.data.scenes[p_scene].cycles.time_limit
                    Current_Res_x = bpy.data.scenes[p_scene].render.resolution_x
                    Current_Res_y = bpy.data.scenes[p_scene].render.resolution_y


                    # Check file path is correct and render
                    if os.path.exists(p_path):
                        file_name = p_filename
                    
                        if os.path.exists(os.path.join(p_path,'',p_filename)):
                            os.remove(os.path.join(p_path,'',p_filename))

                        # Set the render settings user set and render image
                        bpy.data.scenes[p_scene].cycles.time_limit = p_seconds
                        bpy.data.scenes[p_scene].render.resolution_x = p_res_x
                        bpy.data.scenes[p_scene].render.resolution_y = p_res_y

                        my_sn_Im_list = ["PNG","JPEG","IRIS","BMP","JPEG2000","TARGA","TARGA_RAW", "WEBP"]

                        if image_type in my_sn_Im_list:
                            bpy.data.scenes[p_scene].render.image_settings.file_format = image_type
                        else:
                            bpy.data.scenes[p_scene].render.image_settings.file_format = "PNG"
                            #print("Not a valid image type defaulted to PNG")

                        bpy.data.scenes[p_scene].render.filepath = os.path.join(p_path,'',p_filename).format()

                        # Set back the scene settings to normal values
                        bpy.ops.render.render(write_still=True, use_viewport=True)
                        bpy.data.scenes[p_scene].cycles.time_limit = Current_Seconds
                        bpy.data.scenes[p_scene].render.resolution_x = Current_Res_x
                        bpy.data.scenes[p_scene].render.resolution_y = Current_Res_y
                    """
        
        self.code = f"""renders({self.inputs[1].python_value},
                                                  {self.inputs[2].python_value},
                                                  {self.inputs[3].python_value},
                                                  {self.inputs[4].python_value},
                                                  {self.inputs[5].python_value},
                                                  {self.inputs[6].python_value},
                                                  "{self.type}")"""
        self.code += f'\n{self.outputs[0].python_value}'

    def draw_node(self, context, layout):
        layout.prop(self, "type", text="Select format")