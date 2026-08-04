from bpy.types import Operator
from ....addon.naming import RBDLabNaming
from ....Global.functions import move_objects_to_collection


class RBDLAB_OT_metalsoft_add_original_mesh(Operator):
    bl_idname = "rbdlab.metalsoft_creation_add_original_mesh"
    bl_label = "Set Original Meshes"
    bl_options = {'REGISTER', 'UNDO'}


    @classmethod
    def description(cls, _context, properties):
        return "Set Original Meshes"
    

    def execute(self, context):

        # Obtén la referencia al "view_layer" actual
        view_layer = context.view_layer

        # Filtra los objetos seleccionados por tipo "MESH"
        selected_mesh_objects = [obj for obj in view_layer.objects.selected if obj.type == 'MESH']

        if not selected_mesh_objects:
            self.report({'WARNING'}, "No valid objects were detected in your selection!!")
            return {'CANCELLED'}
        
        move_objects_to_collection(context, selected_mesh_objects, RBDLabNaming.ORIGINALS, False)

        # Los oculto:
        [ob.hide_set(True) for ob in selected_mesh_objects] 

        return {'FINISHED'}
