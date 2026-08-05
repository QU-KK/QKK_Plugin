from typing import List
from datetime import datetime
from collections import defaultdict
from bpy.types import Operator, Object
from ...Global.basics import deselect_all_objects, set_active_object
from ..particles.update_rbdlab_object import update_broken_neighbours_and_motions
from ...addon.naming import RBDLabNaming
from .common_functions import obtain_lows_and_highs


class RBDLab_OT_visual_switching(Operator):
    bl_idname = "rbdlab.visual_switching"
    bl_label = "Switch Visibility"
    bl_description = "Switch Visibility"
    bl_options = {'REGISTER', 'UNDO'}

    """ 
        Operador unificado.
        Dependiendo de si ui.visual_switch_type está en modo 'FRAME_SWITCH' o de lo contrario en 'DYNAMIC_SWITCH',
        se usará el current frame y si no los motions 
    """

    def compute_motions(self, context, vs_props, objects: List[Object]) -> None:

        # Calcular motions...
        start_update = datetime.now()
        update_broken_neighbours_and_motions(
            context,
            objects,
            step=1,
            distance_threshold=vs_props.distance_threshold,
            velocity_threshold=vs_props.velocity_threshold,
            max_motions=1,
            flag=vs_props.options)
        print("Update broken/motions: " + str(datetime.now() - start_update))

    def store_prev_status(self, ob: Object) -> None:
        if RBDLabNaming.DSWITCH_VSWITCHING_PREV_EYE_VISIBILITY not in ob:
            ob[RBDLabNaming.DSWITCH_VSWITCHING_PREV_EYE_VISIBILITY] = ob.hide_get()

        if RBDLabNaming.DSWITCH_VSWITCHING_PREV_VIEWPORT_VISIBILITY not in ob:
            ob[RBDLabNaming.DSWITCH_VSWITCHING_PREV_VIEWPORT_VISIBILITY] = getattr(ob, "hide_viewport")

        if RBDLabNaming.DSWITCH_VSWITCHING_PREV_RENDER_VISIBILITY not in ob:
            ob[RBDLabNaming.DSWITCH_VSWITCHING_PREV_RENDER_VISIBILITY] = getattr(ob, "hide_render")

    def anim_visibility(self, ob: Object, frame: int, order: List) -> None:
        for i in order:
            dpath, status_bool, frame = [j for j in i]
            setattr(ob, dpath, status_bool)
            ob.keyframe_insert(data_path=dpath, frame=frame)

    def execute(self, context):

        scn = context.scene
        rbdlab = scn.rbdlab
        ui = rbdlab.ui
        vs_props = rbdlab.physics.dswitch.visual_switching
        tcoll_list = rbdlab.lists.target_coll_list
        tcoll = tcoll_list.active

        # target_chunks tendra los low y los high en caso de haberlos
        target_chunks = obtain_lows_and_highs(self, context, tcoll)

        if ui.visual_switch_type == 'FRAME_SWITCH':
            current_frame = scn.frame_current

        elif ui.visual_switch_type == 'DYNAMIC_SWITCH':
            low_chunks = [ob for ob in tcoll.objects if ob.type == 'MESH' and ob.name in context.view_layer.objects]
            vs_props.offset = 0
            # solo computo los motion en los low:
            self.compute_motions(context, vs_props, low_chunks)

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

        scn.frame_set(scn.frame_start)

        for org_name, chunks in froms_and_chunks.items():

            org_ob = context.view_layer.objects.get(org_name)

            if org_ob is None:
                continue

            # Nota si hubiera highs en el target collection entonces chunks contienen tanto los low como los highs.
            # si no solo tendrá los low.
            low_chunks = list(filter(lambda chunk: "_high_" not in chunk.name, chunks))
            high_chunks = list(filter(lambda chunk: "_high_" in chunk.name and chunk.parent is not None, chunks))

            if ui.visual_switch_type == 'FRAME_SWITCH':
                target_frame = current_frame

            elif ui.visual_switch_type == 'DYNAMIC_SWITCH':

                # todas las variables en None:
                target_frame = broken_target_frame = motion_target_frame = None

                # ------------------------------------------------------------------------------------------------------
                # Broken -----------------------------------------------------------------------------------------------
                if 'BROKEN' in rbdlab.visual_switching.options:

                    if high_chunks:
                        broken_frames = [ob.parent.rbdlab.broken_at_frame for ob in high_chunks
                                         if ob.parent.rbdlab.broken_at_frame != -1]
                    else:
                        broken_frames = [ob.rbdlab.broken_at_frame for ob in low_chunks
                                         if ob.rbdlab.broken_at_frame != -1]

                    if len(broken_frames) > 0:

                        if high_chunks:
                            broken_target_frame = min(
                                [ob.parent.rbdlab.broken_at_frame for ob in high_chunks
                                 if ob.parent.rbdlab.broken_at_frame != -1])
                        else:
                            broken_target_frame = min(
                                [ob.rbdlab.broken_at_frame for ob in low_chunks if ob.rbdlab.broken_at_frame != -1])
                    else:
                        print("No broken frames detected for chunks of " + org_name + " !!")
                # ------------------------------------------------------------------------------------------------------
                # Motion -----------------------------------------------------------------------------------------------
                if 'MOTION' in rbdlab.visual_switching.options:

                    if high_chunks:
                        motion_frames = [motion.range[0] for ob in high_chunks for motion in ob.parent.rbdlab.motions]
                    else:
                        # no es necesario comprobar velocities de nada, los motions ya estan calculados en base
                        # a los parametros del usuario con el velocity velocity_threshold
                        motion_frames = [motion.range[0] for ob in low_chunks for motion in ob.rbdlab.motions]

                    if len(motion_frames) > 0:
                        motion_target_frame = min(motion_frames)

                    if motion_target_frame is None:
                        print("No motion frames detected for chunks of " + org_name + " !!")

                    # print("*** motion_target_frame", motion_target_frame)
                # ------------------------------------------------------------------------------------------------------
                # Conditions -------------------------------------------------------------------------------------------

                if broken_target_frame is not None and motion_target_frame is None:
                    # solo obtenimos broken:
                    target_frame = broken_target_frame

                elif broken_target_frame is None and motion_target_frame is not None:
                    # solo obtenimos movimientos:
                    target_frame = motion_target_frame

                elif broken_target_frame is not None and motion_target_frame is not None:
                    # tiene prioridad el broken, solo si primero fue roto:
                    if broken_target_frame <= motion_target_frame:
                        target_frame = broken_target_frame
                    else:
                        # el que fuera primero:
                        target_frame = min(broken_target_frame, motion_target_frame)

                # print("*** broken_target_frame, motion_target_frame", broken_target_frame, motion_target_frame)
                # print("*** target_frame", target_frame)
                # ------------------------------------------------------------------------------------------------------

            # Nota: si alguno no tiene broken y sale con -1 igualmente sera animada su visibilidad.

            # Si no hay frame determinado para el switcheo skipeamos:
            if target_frame is None:
                continue

            self.store_prev_status(org_ob)

            org_ob.hide_set(False)
            set_active_object(context, chunks[0])

            org_ob_order = [
                ["hide_viewport", False, target_frame],
                ["hide_render", False, target_frame],
                ["hide_viewport", True, target_frame+1],
                ["hide_render", True, target_frame+1],
            ]
            self.anim_visibility(org_ob, target_frame, org_ob_order)

            # como cuando solo había lows:
            low_chunks_order = [
                ["hide_viewport", True, target_frame],
                ["hide_render", True, target_frame],
                ["hide_viewport", False, target_frame+1],
                ["hide_render", False, target_frame+1],
            ]

            # evaluamos si no es none, pero tambien si no es [] void:
            if not high_chunks:
                # Si no hay highs, si se anima el render
                for ob in chunks:
                    self.store_prev_status(ob)
                    self.anim_visibility(ob, target_frame, low_chunks_order)
            else:
                # Si hay highs, a los low no se les anima el render, pero si el monitor
                # Y para los high si se les anima el render
                low_chunks_with_highs_order = [
                    ["hide_viewport", True, target_frame],
                    ["hide_viewport", False, target_frame+1],
                ]
                for ob in chunks:
                    self.store_prev_status(ob)
                    order = low_chunks_order if "_high_" in ob.name and high_chunks else low_chunks_with_highs_order
                    self.anim_visibility(ob, target_frame, order)

            if RBDLabNaming.DSWITCH_VSWITCHING_COMPUTED not in tcoll:
                tcoll[RBDLabNaming.DSWITCH_VSWITCHING_COMPUTED] = True

        scn.frame_set(scn.frame_start)

        deselect_all_objects(context)
        return {'FINISHED'}
