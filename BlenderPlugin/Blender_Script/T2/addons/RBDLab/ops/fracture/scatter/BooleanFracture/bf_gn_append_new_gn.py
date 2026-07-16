import bpy
from uuid import uuid4
from os.path import join
from datetime import datetime
from bpy.types import Operator
from .....Global.basics import rm_ob
from .....addon.paths import RBDLabPaths
from .....addon.naming import RBDLabNaming
from .boolfracture_name_increment import name_increment
from .....Global.geometry_nodes import set_exposed_attributes_of_gn
from .....Global.functions import set_active_collection_by_name, move_objects_to_collection, remove_collection


class BFRACTURE_OT_append(Operator):
    bl_idname = "rbdlab.boolean_fracture_append"
    bl_label = "Boolean Fracture"
    bl_description = "Add Extra Boolean Fracture"
    bl_options = {'REGISTER', 'UNDO'}


    def execute(self, context):
        
        start = datetime.now()
        
        scn = context.scene
        rbdlab = scn.rbdlab
        bfracture_gn_list = rbdlab.lists.bfracture_gn_list
        object_name = RBDLabNaming.BOOLFRACTURE_GN_OB
        tcoll_list = rbdlab.lists.target_coll_list
        tcoll = tcoll_list.active

        set_active_collection_by_name(context, RBDLabNaming.BOOLFRACTURE_GN_OB)

        blend_file = "BooleanFracture.blend"
        lib_path = join(RBDLabPaths.LIBS, blend_file)
        inner_path = "Object"
        file_path = join(lib_path, inner_path, object_name)
        directory = join(lib_path, inner_path)
        bpy.ops.wm.append(
            filepath=file_path,
            directory=directory,
            filename=object_name
        )

        GN_ob = context.view_layer.objects.get(object_name)
        if not GN_ob:
            self.report({'ERROR'}, "Not GN Object!")
            return {'CANCELLED'}
        
        to_fracture_obs = bfracture_gn_list.get_objects_to_fracture
        
        item_id = str(uuid4())[:6]
        if item_id not in GN_ob.name:
            GN_ob.name = GN_ob.name + "_" + item_id
        
        gn_coll = move_objects_to_collection(context, [GN_ob], RBDLabNaming.BF_GN_COLL)

        for ob_to_fracture in to_fracture_obs:
            
            GN_ob.matrix_world = ob_to_fracture.matrix_world
            
            # tmp_coll = bpy.data.collections.get(item_id)
            valid_colls = [coll for coll in bpy.data.collections if RBDLabNaming.BF_COLL_ID in coll]
            tmp_coll = next((coll for coll in valid_colls if coll[RBDLabNaming.BF_COLL_ID] == item_id), None)
            if not tmp_coll:
                tmp_coll = bpy.data.collections.new(item_id)
                tmp_coll[RBDLabNaming.BF_COLL_ID] = item_id
                gn_coll.children.link(tmp_coll)

            tmp_coll.objects.link(ob_to_fracture)    

        # si ya existe el nombre lo incrementamos con 0x:
        new_name = name_increment(bfracture_gn_list)

        DEBUG = False
        if DEBUG:
            if item_id not in new_name:
                new_name = new_name + "_" + item_id

        bfracture_gn_list.add_item(new_name, item_id, tcoll, base_planes=[GN_ob], objects_to_fracture=to_fracture_obs)

        GN_mod = GN_ob.modifiers.get(RBDLabNaming.BOOLFRACTURE_GN_OB)
        # tmp_coll = bpy.data.collections.get(item_id)
        valid_colls = [coll for coll in bpy.data.collections if RBDLabNaming.BF_COLL_ID in coll]
        tmp_coll = next((coll for coll in valid_colls if coll[RBDLabNaming.BF_COLL_ID] == item_id), None)
        
        set_exposed_attributes_of_gn(GN_mod, "Collection", tmp_coll, debug=False)
        tmp_coll[RBDLabNaming.BF_COLL_ID] = item_id
        
        # El dummy es un cubo en el BooleanFracture.blend para poder hacer cambiso al GN en desarrollo:
        dummy_ob = bpy.data.objects.get("Dummy")
        if dummy_ob:
            rm_ob(dummy_ob)
        
        dummy_coll = bpy.data.collections.get("Dummy")
        if dummy_coll:
            remove_collection(context, dummy_coll)

        print("[boolean_fracture.append] End: " + str(datetime.now() - start))
        return {'FINISHED'}

