import bpy 
from ...base_node import SN_ScriptingBaseNode
class SN_SKD_Matrix_bone(SN_ScriptingBaseNode, bpy.types.Node):
    bl_idname = "SN_SKD_Matrix_bone"
    bl_label = "Matrix Bone"
    bl_width_default = 240
    node_color = "PROGRAM"
    
    def on_create(self, context):
        self.add_execute_input()
        self.add_execute_output()
        self.add_property_input("Object")
        self.add_float_vector_output("Location")
        self.add_float_vector_output("Scale")
        self.add_float_vector_output("Rotation Euler")

  
        
    def evaluate(self, context):
        
        self.code_import = f"""
                            import bpy
                            """
   
        self.code_imperative = f"""
                def matrix_bone(object):
                    obj = object
                    matrix_local = obj.matrix_local
                    location, rotation, scale = matrix_local.decompose()
                    rotation_euler = rotation.to_euler('XYZ')
                    return location, scale, rotation_euler
                    """
        
        self.code = f"""matrix_bone_{self.static_uid} = matrix_bone({self.inputs[1].python_value})"""
        self.outputs[1].python_value = f"matrix_bone({self.inputs[1].python_value})[0]"
        self.outputs[2].python_value = f"matrix_bone({self.inputs[1].python_value})[1]"
        self.outputs[3].python_value = f"matrix_bone({self.inputs[1].python_value})[2]"
        self.code += f'\n{self.outputs[0].python_value}'
