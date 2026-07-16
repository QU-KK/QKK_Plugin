import bpy
from bpy.types import Operator
from ....addon.naming import RBDLabNaming
from ....Global.functions import move_objects_to_collection, create_originals_coll_if_not_exist, create_coll_if_not_exist
from ....Global.get_common_vars import get_common_vars


class RBDLAB_OT_metalsoft_add_proxy_mesh(Operator):
    bl_idname = "rbdlab.metalsoft_creation_add_proxy_mesh"
    bl_label = "Set Proxy Meshes"
    bl_options = {'REGISTER', 'UNDO'}


    @classmethod
    def description(cls, _context, properties):
        return "Set Proxy Meshes"
    

    def execute(self, context):

        rbdlab = get_common_vars(context, get_rbdlab=True)

        # Obtén la referencia al "view_layer" actual
        view_layer = context.view_layer

        # Filtra los objetos seleccionados por tipo "MESH"
        selected_mesh_objects = [obj for obj in view_layer.objects.selected if obj.type == 'MESH']

        if not selected_mesh_objects:
            self.report({'WARNING'}, "No valid objects were detected in your selection!!")
            return {'CANCELLED'}
        
        originals_coll = create_originals_coll_if_not_exist(context, rbdlab)
        create_coll_if_not_exist(context, rbdlab, originals_coll, RBDLabNaming.METAL_SOFT_PROXYS)

        move_objects_to_collection(context, selected_mesh_objects, RBDLabNaming.METAL_SOFT_PROXYS, False)

        # Los oculto:
        [ob.hide_set(True) for ob in selected_mesh_objects] 

        return {'FINISHED'}
