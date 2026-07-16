import bpy
from datetime import datetime
from bpy.types import Operator
from .....addon.naming import RBDLabNaming
from bpy.props import StringProperty
from .....Global.basics import rm_ob
from .....Global.functions import remove_collection, remove_collection_if_is_empty


class BFRACTURE_OT_rm(Operator):
    bl_idname = "rbdlab.boolean_fracture_rm"
    bl_label = "Boolean Fracture"
    bl_description = "Boolean Fracture"
    bl_options = {'REGISTER', 'UNDO'}

    id_to_rm: StringProperty(default="")


    def execute(self, context):
        
        start = datetime.now()

        scn = context.scene
        rbdlab = scn.rbdlab
        ui = rbdlab.ui
        tcoll_list = rbdlab.lists.target_coll_list
        bfracture_gn_list = rbdlab.lists.bfracture_gn_list
        item_id = self.id_to_rm

        # Si es el ultimo item y lo borramos desde el listado manualmente, borrara el tcoll también:
        # pero si llamamos a este operador por código en el Apply (fase SETTINGS_BOOL_MOD) conservaremos el tcoll
        # fases  'NONE', 'SETTINGS_GN', 'SETTINGS_BOOL_MOD', 'NONE'
        if bfracture_gn_list.length == 1 and ui.boolean_method_phase == 'SETTINGS_GN':
            item = tcoll_list.active_item
            bpy.ops.rbdlab.rm_target_coll_from_list(to_rm = item.id_name)

        # tmp_coll = bpy.data.collections.get(item_id)
        valid_colls = [coll for coll in bpy.data.collections if RBDLabNaming.BF_COLL_ID in coll]
        tmp_coll = next((coll for coll in valid_colls if coll[RBDLabNaming.BF_COLL_ID] == item_id), None)
        if tmp_coll:
            remove_collection(context, tmp_coll)
        
        item = bfracture_gn_list.get_item_from_id(item_id)
        if item:
        
            base_plane = next((bp.ob for bp in item.stored_base_planes), None)
            if base_plane:
                rm_ob(base_plane)
    
            RBDLab_GN_coll = bpy.data.collections.get(RBDLabNaming.BF_GN_COLL)
            if RBDLab_GN_coll:
                remove_collection_if_is_empty(context, RBDLabNaming.BF_GN_COLL)
                    
            item.remove = True

        if bfracture_gn_list.is_void:
            ui.boolean_method_phase = 'NONE'
            bf_ng = bpy.data.node_groups.get(RBDLabNaming.BOOLFRACTURE_GN_OB)
            if bf_ng:
                 bpy.data.node_groups.remove(bf_ng)

        print("[boolean_fracture.rm] End: " + str(datetime.now() - start))
        return {'FINISHED'}