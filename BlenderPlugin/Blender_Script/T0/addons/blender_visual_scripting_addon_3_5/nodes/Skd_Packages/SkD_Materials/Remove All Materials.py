import bpy
from ...base_node import SN_ScriptingBaseNode

class SN_SKD_Remove_All_Materials(bpy.types.Node, SN_ScriptingBaseNode):

    bl_idname = "SN_SKD_Remove_All_Materials"
    bl_label = "Removal All Materials"
    node_color = "BOOLEAN"

    def on_create(self, context):
        self.add_execute_input()
        self.add_execute_output()
        self.add_collection_property_input("Objects Collection")
        self.add_boolean_input("VOLUME")
        self.add_boolean_input("FONT")
        self.add_boolean_input("METABALL")
        self.add_boolean_input("SURFACE")
        self.add_boolean_input("CURVE")
        self.add_boolean_input("MESH")



    type: bpy.props.EnumProperty(name="",
                                 items=[("Collection", "Collection", "",),
                                        ("Single Object", "Single Object", "",)
                                        ],
                                 update=SN_ScriptingBaseNode._evaluate)

    def evaluate(self, context):
        self.code_import = """
                            import bpy
                            """

        self.code_imperative = """
            def removers(type_er, obz, VOLUME, FONT, META, SURFACE, CURVE, MESH):

                if type_er == "Collection":

                    for obj in obz:
                        if obj.type == 'VOLUME' and VOLUME:
                            obj.data.materials.clear()
                        if obj.type == 'FONT' and FONT:
                            obj.data.materials.clear()
                        if obj.type == 'META' and META:
                            obj.data.materials.clear()
                        if obj.type == 'SURFACE' and SURFACE:
                            obj.data.materials.clear()
                        if obj.type == 'CURVE' and CURVE:
                            obj.data.materials.clear()
                        if obj.type == 'MESH' and MESH:
                            obj.data.materials.clear()


                if type_er == "Single Object":
                    obj = obz

                    if obj.type == 'VOLUME' and VOLUME:
                        obj.data.materials.clear()
                    if obj.type == 'FONT' and FONT:
                        obj.data.materials.clear()
                    if obj.type == 'META' and META:
                        obj.data.materials.clear()
                    if obj.type == 'SURFACE' and SURFACE:
                        obj.data.materials.clear()
                    if obj.type == 'CURVE' and CURVE:
                        obj.data.materials.clear()
                    if obj.type == 'MESH' and MESH:
                        obj.data.materials.clear()

            """
        self.code = f"""removers("{self.type}", {self.inputs[1].python_value}, {self.inputs[2].python_value}, {self.inputs[3].python_value}, {self.inputs[4].python_value}, {self.inputs[5].python_value}, {self.inputs[6].python_value}, {self.inputs[7].python_value} )"""
        self.code += f'\n{self.outputs[0].python_value}'

    def draw_node(self, context, layout):
        layout.prop(self, "type", text="Select Option")