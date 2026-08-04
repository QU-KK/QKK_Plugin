from bpy.types import Operator


class RBDLAB_OT_materials_init_collections(Operator):
    bl_idname = "rbdlab.materials_init_collections"
    bl_label = "Load Collections"
    bl_description = "Load Collection List"

    def execute(self, context):
        scn = context.scene
        rbdlab = scn.rbdlab
        rbdlab_materials = rbdlab.materials
        rbdlab_materials.init_coll_list(context)
        return {'FINISHED'}
