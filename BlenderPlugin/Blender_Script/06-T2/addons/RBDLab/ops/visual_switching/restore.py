from bpy.types import Operator
from collections import defaultdict
from ...addon.naming import RBDLabNaming
from ...Global.functions import remove_all_keyframes_in_action
from ...Global.basics import deselect_all_objects
from .common_functions import obtain_lows_and_highs


class RBDLab_OT_visual_switching_restore(Operator):
    bl_idname = "rbdlab.visual_switching_restore"
    bl_label = "Restore Visibility"
    bl_description = "Restore Visibility"
    bl_options = {'REGISTER', 'UNDO'}

    def restore_visibility(self, context, ob) -> None:
        # eliminamos los diccionarios con info creados por el offset también:
        wm = context.window_manager
        key_viewport = f"{ob.name}_hide_viewport"
        key_render = f"{ob.name}_hide_render"

        if key_viewport in wm:
            del wm[key_viewport]
        if key_render in wm:
            del wm[key_render]

        # restauramos las visibilidades:
        if RBDLabNaming.DSWITCH_VSWITCHING_PREV_EYE_VISIBILITY in ob:
            ob.hide_set(ob[RBDLabNaming.DSWITCH_VSWITCHING_PREV_EYE_VISIBILITY])
            del ob[RBDLabNaming.DSWITCH_VSWITCHING_PREV_EYE_VISIBILITY]

        if RBDLabNaming.DSWITCH_VSWITCHING_PREV_VIEWPORT_VISIBILITY in ob:
            dpath = "hide_viewport"
            remove_all_keyframes_in_action(context, ob, dpath)
            setattr(ob, dpath, ob[RBDLabNaming.DSWITCH_VSWITCHING_PREV_VIEWPORT_VISIBILITY])
            del ob[RBDLabNaming.DSWITCH_VSWITCHING_PREV_VIEWPORT_VISIBILITY]

        if RBDLabNaming.DSWITCH_VSWITCHING_PREV_RENDER_VISIBILITY in ob:
            dpath = "hide_render"
            remove_all_keyframes_in_action(context, ob, dpath)
            setattr(ob, dpath, ob[RBDLabNaming.DSWITCH_VSWITCHING_PREV_RENDER_VISIBILITY])
            del ob[RBDLabNaming.DSWITCH_VSWITCHING_PREV_RENDER_VISIBILITY]

    def execute(self, context):
        scn = context.scene
        rbdlab = scn.rbdlab

        tcoll_list = rbdlab.lists.target_coll_list
        # porque get_current_active_tcoll_valild_objects busca solo los visibles:
        tcoll = tcoll_list.active
        # list_chunks = [ob for ob in tcoll.objects if ob.type == 'MESH' and ob.name in context.view_layer.objects]

        # target_chunks tendra los low y los high en caso de haberlos
        target_chunks = obtain_lows_and_highs(self, context, tcoll)

        if len(target_chunks) < 1:
            self.report({'ERROR'}, "No valid Meshes in Current Target Collection!")
            return {'CANCELLED'}

        # el defaultdict crea un diccionario y si no existe la clave previamente la crea.
        froms_and_chunks = defaultdict(list)
        for ob in target_chunks:
            if RBDLabNaming.FROM in ob:

                # si fuera un inner lo ignoramos:
                if RBDLabNaming.INNER_CHUNK in ob:
                    continue

                key = ob[RBDLabNaming.FROM]
                # usamos append por si existiera previamente la clave, ir acumulando y no sobrescribiendo.
                froms_and_chunks[key].append(ob)

        for org_name, chunks in froms_and_chunks.items():

            org_ob = context.view_layer.objects.get(org_name)

            if org_ob is None:
                continue

            self.restore_visibility(context, org_ob)

            for ob in chunks:
                self.restore_visibility(context, ob)

        if RBDLabNaming.DSWITCH_VSWITCHING_COMPUTED in tcoll:
            del tcoll[RBDLabNaming.DSWITCH_VSWITCHING_COMPUTED]

        scn.frame_set(scn.frame_start)
        deselect_all_objects(context)
        return {'FINISHED'}
