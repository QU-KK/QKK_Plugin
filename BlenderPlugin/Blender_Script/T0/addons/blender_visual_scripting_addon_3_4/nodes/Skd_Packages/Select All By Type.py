import bpy
from ..base_node import SN_ScriptingBaseNode

class SN_SKD_Select_All_By_Type(bpy.types.Node, SN_ScriptingBaseNode):

    bl_idname = "SN_SKD_Select_All_By_Type"
    bl_label = "Select All By Type"
    node_color = "BOOLEAN"

    def on_create(self, context):
        self.add_execute_input()
        self.add_execute_output()
        self.add_collection_property_input("Objects Collection")
        self.add_boolean_input("SPEAKER")
        self.add_boolean_input("CAMERA")
        self.add_boolean_input("LIGHTPROBE")
        self.add_boolean_input("LIGHT")
        self.add_boolean_input("EMPTY")
        self.add_boolean_input("LATTICE")
        self.add_boolean_input("ARMATURE")
        self.add_boolean_input("GREASEPENCIL")
        self.add_boolean_input("VOLUME")
        self.add_boolean_input("POINTCLOUD")
        self.add_boolean_input("HAIR")
        self.add_boolean_input("FONT")
        self.add_boolean_input("METABALL")
        self.add_boolean_input("SURFACE")
        self.add_boolean_input("CURVE")
        self.add_boolean_input("MESH")

    type: bpy.props.EnumProperty(name="",
                                items=[("Select", "Select", "",),
                                    ("UnSelect", "UnSelect", "",)
                                    ],
                                update=SN_ScriptingBaseNode._evaluate)

    def evaluate(self, context):
        self.code_import = """
                            import bpy
                            """

        self.code_imperative = """
            def Select_types(pass_type, obz, SPEAKER, CAMERA, LIGHT_PROBE, LIGHT, EMPTY, LATTICE, ARMATURE, GPENCIL, VOLUME, POINTCLOUD, HAIR, FONT, META, SURFACE, CURVE, MESH ):
                
                scene_objects = bpy.context.scene.objects

                if pass_type == "Select":
                
                    for obj in obz:

                        # Check if object is in scene
                        if obj.name not in scene_objects:
                            continue

                        # Skip objects that should not be selected
                        if obj.type == 'SPEAKER' and not SPEAKER:
                            continue
                        if obj.type == 'CAMERA' and not CAMERA:
                            continue
                        if obj.type == 'LIGHT_PROBE' and not LIGHT_PROBE:
                            continue
                        if obj.type == 'LIGHT' and not LIGHT:
                            continue
                        if obj.type == 'EMPTY' and not EMPTY:
                            continue
                        if obj.type == 'LATTICE' and not LATTICE:
                            continue
                        if obj.type == 'ARMATURE' and not ARMATURE:
                            continue
                        if obj.type == 'GPENCIL' and not GPENCIL:
                            continue
                        if obj.type == 'VOLUME' and not VOLUME:
                            continue
                        if obj.type == 'POINTCLOUD' and not POINTCLOUD:
                            continue
                        if obj.type == 'HAIR' and not HAIR:
                            continue
                        if obj.type == 'FONT' and not FONT:
                            continue
                        if obj.type == 'META' and not META:
                            continue
                        if obj.type == 'SURFACE' and not SURFACE:
                            continue
                        if obj.type == 'CURVE' and not CURVE:
                            continue
                        if obj.type == 'MESH' and not MESH:
                            continue

                        # Select by type
                        obj.select_set(True)

                if pass_type == "UnSelect":
                    for obj in obz:

                        # Check if object is in scene
                        if obj.name not in scene_objects:
                            continue
                        # Skip objects that should not be selected
                        if obj.type == 'SPEAKER' and not SPEAKER:
                            continue
                        if obj.type == 'CAMERA' and not CAMERA:
                            continue
                        if obj.type == 'LIGHT_PROBE' and not LIGHT_PROBE:
                            continue
                        if obj.type == 'LIGHT' and not LIGHT:
                            continue
                        if obj.type == 'EMPTY' and not EMPTY:
                            continue
                        if obj.type == 'LATTICE' and not LATTICE:
                            continue
                        if obj.type == 'ARMATURE' and not ARMATURE:
                            continue
                        if obj.type == 'GPENCIL' and not GPENCIL:
                            continue
                        if obj.type == 'VOLUME' and not VOLUME:
                            continue
                        if obj.type == 'POINTCLOUD' and not POINTCLOUD:
                            continue
                        if obj.type == 'HAIR' and not HAIR:
                            continue
                        if obj.type == 'FONT' and not FONT:
                            continue
                        if obj.type == 'META' and not META:
                            continue
                        if obj.type == 'SURFACE' and not SURFACE:
                            continue
                        if obj.type == 'CURVE' and not CURVE:
                            continue
                        if obj.type == 'MESH' and not MESH:
                            continue

                        # Select by type
                        obj.select_set(False)
            """
     
        self.code = f"""Select_types("{self.type}", {self.inputs[1].python_value} ,{self.inputs[2].python_value},{self.inputs[3].python_value},{self.inputs[4].python_value},{self.inputs[5].python_value},{self.inputs[6].python_value},{self.inputs[7].python_value},{self.inputs[8].python_value},{self.inputs[9].python_value},{self.inputs[10].python_value},{self.inputs[11].python_value},{self.inputs[12].python_value},{self.inputs[13].python_value},{self.inputs[14].python_value},{self.inputs[15].python_value},{self.inputs[16].python_value},{self.inputs[17].python_value})"""
        self.code += f'\n{self.outputs[0].python_value}'

    def draw_node(self, context, layout):
        layout.prop(self, "type", text="Select")