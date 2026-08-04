import bpy
from ..base_node import SN_ScriptingBaseNode


class SN_SKD_Hide_Show_Viewport(bpy.types.Node, SN_ScriptingBaseNode):

    bl_idname = "SN_SKD_Hide_Show_Viewport"
    bl_label = "Hide Show Viewport Objects"
    node_color = "BOOLEAN"

    def on_create(self, context):
        self.add_execute_input()
        self.add_execute_output()
        self.add_collection_property_input("Objects Collection")
        self.add_boolean_input("Hide Viewport").default_value = False
        self.add_boolean_input("Hide Render").default_value = False
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
                                 items=[("Object In A Collection", "Object In A Collection", "",),
                                        ("Collection Of Object", "Collection Of Object", "",),
                                        ("Single Object", "Single Object", "",),
                                        ("Collection", "Collection", "",)
                                        ],
                                 update=SN_ScriptingBaseNode._evaluate)

    def evaluate(self, context):
        self.code_import = """
                            import bpy
                            """

        self.code_imperative = """
            def hiders(typers, obz, Hide_viewport, Hide_Render, SPEAKER, CAMERA , LIGHT_PROBE, LIGHT, EMPTY, LATTICE, ARMATURE, GPENCIL, VOLUME, POINTCLOUD, HAIR, FONT, META, SURFACE, CURVE, MESH ):

                scene_objects = bpy.context.scene.objects

                if typers == "Collection Of Object":

                    for obj in obz:
                        
                        # Check if object is in scene
                        if obj.name not in scene_objects:
                            continue
                        # Skip objects that should not be hidden
                        if obj.type == 'SPEAKER' and SPEAKER is False:
                            continue
                        if obj.type == 'CAMERA' and CAMERA is False:
                            continue
                        if obj.type == 'LIGHT_PROBE' and LIGHT_PROBE is False:
                            continue
                        if obj.type == 'LIGHT' and LIGHT is False:
                            continue
                        if obj.type == 'EMPTY' and EMPTY is False:
                            continue
                        if obj.type == 'LATTICE' and LATTICE is False:
                            continue
                        if obj.type == 'ARMATURE' and ARMATURE is False:
                            continue
                        if obj.type == 'GPENCIL' and GPENCIL is False:
                            continue
                        if obj.type == 'VOLUME' and VOLUME is False:
                            continue
                        if obj.type == 'POINTCLOUD' and POINTCLOUD is False:
                            continue
                        if obj.type == 'HAIR' and HAIR is False:
                            continue
                        if obj.type == 'FONT' and FONT is False:
                            continue
                        if obj.type == 'META' and META is False:
                            continue
                        if obj.type == 'SURFACE' and SURFACE is False:
                            continue
                        if obj.type == 'CURVE' and CURVE is False:
                            continue
                        if obj.type == 'MESH' and MESH is False:
                            continue

                        # Set the object's visibility to False
                        if Hide_viewport is False: obj.hide_set(False)
                        if Hide_Render is False: obj.hide_render = False

                        # Do something with the object
                        if Hide_viewport is True: obj.hide_set(True)
                        if Hide_Render is True: obj.hide_render = True 

                if typers == "Object In A Collection":
               
                    collection_name = obz
                    if collection_name in bpy.data.collections:
                        collection = bpy.data.collections[collection_name]
                        for obj in collection.objects:
                    
                            # Check if object is in scene
                            if obj.name not in scene_objects:
                                continue
                            # Skip objects that should not be hidden
                            if obj.type == 'SPEAKER' and SPEAKER is False:
                                continue
                            if obj.type == 'CAMERA' and CAMERA is False:
                                continue
                            if obj.type == 'LIGHT_PROBE' and LIGHT_PROBE is False:
                                continue
                            if obj.type == 'LIGHT' and LIGHT is False:
                                continue
                            if obj.type == 'EMPTY' and EMPTY is False:
                                continue
                            if obj.type == 'LATTICE' and LATTICE is False:
                                continue
                            if obj.type == 'ARMATURE' and ARMATURE is False:
                                continue
                            if obj.type == 'GPENCIL' and GPENCIL is False:
                                continue
                            if obj.type == 'VOLUME' and VOLUME is False:
                                continue
                            if obj.type == 'POINTCLOUD' and POINTCLOUD is False:
                                continue
                            if obj.type == 'HAIR' and HAIR is False:
                                continue
                            if obj.type == 'FONT' and FONT is False:
                                continue
                            if obj.type == 'META' and META is False:
                                continue
                            if obj.type == 'SURFACE' and SURFACE is False:
                                continue
                            if obj.type == 'CURVE' and CURVE is False:
                                continue
                            if obj.type == 'MESH' and MESH is False:
                                continue

                            # Set the object's visibility to False
                            if Hide_viewport is False: obj.hide_set(False)
                            if Hide_Render is False: obj.hide_render = False

                            # Do something with the object
                            if Hide_viewport is True: obj.hide_set(True)
                            if Hide_Render is True: obj.hide_render = True        

                if typers == "Single Object":
                    
                    obj = obz

                    skip_object = (
                        (obj.type == 'SPEAKER' and not SPEAKER) or
                        (obj.type == 'CAMERA' and not CAMERA) or
                        (obj.type == 'LIGHT_PROBE' and not LIGHT_PROBE) or
                        (obj.type == 'LIGHT' and not LIGHT) or
                        (obj.type == 'EMPTY' and not EMPTY) or
                        (obj.type == 'LATTICE' and not LATTICE) or
                        (obj.type == 'ARMATURE' and not ARMATURE) or
                        (obj.type == 'GPENCIL' and not GPENCIL) or
                        (obj.type == 'VOLUME' and not VOLUME) or
                        (obj.type == 'POINTCLOUD' and not POINTCLOUD) or
                        (obj.type == 'HAIR' and not HAIR) or
                        (obj.type == 'FONT' and not FONT) or
                        (obj.type == 'META' and not META) or
                        (obj.type == 'SURFACE' and not SURFACE) or
                        (obj.type == 'CURVE' and not CURVE) or
                        (obj.type == 'MESH' and not MESH)
                    )
                    if not skip_object:
                    
                        # Set the object's visibility to False
                        if Hide_viewport is False: obj.hide_set(False)
                        if Hide_Render is False: obj.hide_render = False

                        # Do something with the object
                        if Hide_viewport is True: obj.hide_set(True)
                        if Hide_Render is True: obj.hide_render = True 


                if typers == "Collection":
                    
                    collection_name = obz
                    if collection_name in bpy.data.collections:
                        collection = bpy.data.collections[collection_name]

                        # Set the entire collection's visibility
                        if Hide_viewport is False:
                            collection.hide_viewport = False
                        if Hide_Render is False:
                            collection.hide_render = False
                        
                        # Hide or show the collection
                        if Hide_viewport is True:
                            collection.hide_viewport = True
                        if Hide_Render is True:
                            collection.hide_render = True
                       
            """
        
        self.code = f"""hiders("{self.type}", {self.inputs[1].python_value},{self.inputs[2].python_value}, {self.inputs[3].python_value}, {self.inputs[4].python_value}, {self.inputs[5].python_value}, {self.inputs[6].python_value}, {self.inputs[7].python_value},{self.inputs[8].python_value},{self.inputs[9].python_value},{self.inputs[10].python_value},{self.inputs[11].python_value},{self.inputs[12].python_value},{self.inputs[13].python_value},{self.inputs[14].python_value},{self.inputs[15].python_value},{self.inputs[16].python_value},{self.inputs[17].python_value},{self.inputs[18].python_value},{self.inputs[19].python_value})"""
        self.code += f'\n{self.outputs[0].python_value}'
    
    def draw_node(self, context, layout):
        layout.prop(self, "type", text="Select Option")