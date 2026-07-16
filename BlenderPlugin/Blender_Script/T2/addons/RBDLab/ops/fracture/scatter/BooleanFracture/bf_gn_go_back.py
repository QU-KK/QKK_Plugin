import bpy
from datetime import datetime
from bpy.types import Operator
from .....addon.naming import RBDLabNaming
from .....Global.functions import remove_collection


class BFRACTURE_OT_go_back(Operator):
    bl_idname = "rbdlab.boolean_fracture_go_back"
    bl_label = "Go Back"
    bl_description = "Go Back"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        
        start = datetime.now()

        scn = context.scene
        rbdlab = scn.rbdlab
        
        ui = rbdlab.ui
        bfracture_gn_list = rbdlab.lists.bfracture_gn_list

        base_planes_coll_tmp = bpy.data.collections.get(RBDLabNaming.BF_BASE_PLANES_COLL_TMP)
        if not base_planes_coll_tmp:
            self.report({'ERROR'}, "No " + RBDLabNaming.BF_BASE_PLANES_COLL_TMP + " collection in scene!")
            return {'CANCELLED'}
        
        bf_gn_coll = bpy.data.collections.get(RBDLabNaming.BF_GN_COLL)
        if not bf_gn_coll:
            self.report({'ERROR'}, "No " + RBDLabNaming.BF_GN_COLL + " collection in scene!")
            return {'CANCELLED'}

        for GN_ob in base_planes_coll_tmp.objects:
            
            # deslinko de donde esten:
            for coll in GN_ob.users_collection:
                coll.objects.unlink(GN_ob)

            # lo metemos en su collection:
            bf_gn_coll.objects.link(GN_ob)

            # y volvemos a habilitarlos:
            GN_mod = GN_ob.modifiers.get(RBDLabNaming.BOOLFRACTURE_GN_OB)
            if GN_mod:
                GN_mod.show_viewport = True
                GN_mod.show_render = True
                GN_mod.show_in_editmode = True
            
            GN_ob.hide_set(False)
            GN_ob.hide_viewport = False
            GN_ob.hide_render = False

        # Recorrermos todos los objects to fracture, para borrarles el bool_mod, ya que en la etapa anterior no los tenían
        to_fracture = bfracture_gn_list.get_objects_to_fracture
        for ob in to_fracture:
            mod = ob.modifiers.get(RBDLabNaming.BOOLEAN_MOD)
            if mod:
                ob.modifiers.remove(mod)
        
        # borramos la collection BF_Base_Planes_Tmp:
        if base_planes_coll_tmp: 
            remove_collection(context, base_planes_coll_tmp)
        
        # borramos la collection BF_Bool_Objects:
        bool_obs_coll = bpy.data.collections.get(RBDLabNaming.BOOL_OBS)
        if bool_obs_coll: 
            remove_collection(context, bool_obs_coll)

        # volvemos a la fase anterior:
        ui.boolean_method_phase = 'SETTINGS_GN'

        # seteamos los settings de visualiación a solid:
        context.space_data.shading.type = 'SOLID'

        print("[boolean_fracture.go_back] End: " + str(datetime.now() - start))
        return {'FINISHED'}
