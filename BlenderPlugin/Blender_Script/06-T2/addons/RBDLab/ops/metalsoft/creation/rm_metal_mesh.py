import bpy
import ast
from bpy.types import Operator
from ....addon.naming import RBDLabNaming
from ....Global.functions import remove_collection, rm_ob, unhide_collection_in_viewport
from bpy.props import StringProperty
from ....Global.get_common_vars import get_common_vars


class RBDLAB_OT_rm_metal_mesh(Operator):
    bl_idname = "rbdlab.metalsoft_creation_rm_metal_mesh"
    bl_label = "Remove Metal Mesh"
    bl_options = {'REGISTER', 'UNDO'}


    @classmethod
    def description(cls, _context, properties):
        return "Remove Metal Mesh"
    
    id_to_rm: StringProperty(default="")


    def execute(self, context):

        tcoll_list = get_common_vars(context, get_tcoll_list=True)

        # tiene q ser por el click no por el active:
        metal_coll_id, tcoll_id = ast.literal_eval(self.id_to_rm)

        tcoll_item = tcoll_list.get_item_by_id_name(tcoll_id)
        if not tcoll_item:
            self.report({'ERROR'}, "Not valid Target Collection!!")
            return {'CANCELLED'}
        
        tcoll = tcoll_item.coll
        metal_list = tcoll_item.metal_list
        item = metal_list.active

        # tcoll_item = tcoll_list.active_item
        # metal_list = tcoll_item.metal_list
        
        if not item:
            self.report({'ERROR'}, "Not valid item list!!")
            return {'CANCELLED'}
        

        # eliminamos las link collections: 
        links_colls = [c.coll for c in item.stored_collections]
        for c in links_colls:
            remove_collection(context, c)

        # eliminamos los objetos Geometry nodes:
        GN_obs = [gn_ob.ob for gn_ob in item.stored_gn_ob if gn_ob.ob is not None]
        for GN_ob in GN_obs:
            rm_ob(GN_ob)
        
        # eliminamos metal links collection maestra padre 1
        metal_links_coll = bpy.data.collections.get(RBDLabNaming.METAL_LINKS_COLL)
        if metal_links_coll:
            if len(metal_links_coll.children) == 0:
                remove_collection(context, metal_links_coll)

        # eliminamos metal meshes collection maestra padre 2
        metal_meshes_coll = bpy.data.collections.get(RBDLabNaming.METAL_MESHES)
        if metal_meshes_coll:
            if len(metal_meshes_coll.children) == 0:
                remove_collection(context, metal_meshes_coll)

        # Le quitamos los modifiers RBDLab_Displace_For_SurfaceDeform y RBDLab_SurfaceDeform a los originales:
        org_obs = [org_ob.ob for org_ob in item.stored_originals if org_ob.ob is not None]
        for ob in org_obs:
            displace_mod = ob.modifiers.get(RBDLabNaming.DISPLACE_FOR_DDFORM)
            if displace_mod:
                ob.modifiers.remove(displace_mod)
            
            surface_deform_mod = ob.modifiers.get(RBDLabNaming.SURFACE_DEFORM)
            if surface_deform_mod:
                ob.modifiers.remove(surface_deform_mod)
            
            ob.hide_set(True)
        
        unhide_collection_in_viewport(context, tcoll.name)

        # quitamos el item de la lista:
        metal_list.remove_item(metal_coll_id)

        return {'FINISHED'}