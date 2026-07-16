from bpy.types import PropertyGroup
from collections import defaultdict
from ....addon.naming import RBDLabNaming
from bpy.props import FloatProperty, EnumProperty, IntProperty
from ....ops.visual_switching.common_functions import obtain_lows_and_highs


class RBDLab_PG_visual_switching_props(PropertyGroup):

    options: EnumProperty(
        name="Options",
        items=(
            ('BROKEN', "Broken", "Wheter the chunk is broken based in the distance threshold / separation with neighboring chunks"),
            ('MOTION', "Motion", "Whether the chunk surpasses the velocity threshold")
        ),
        # default={'BROKEN', 'MOTION'},
        default={'MOTION'},
        options={'ENUM_FLAG'}
    )

    distance_threshold: FloatProperty(
        name="Distance Threshold",
        description="If the chunk is separated this distance (in meters) from any neighbor chunk it will switching at the time the separation is performed",
        min=0.01, max=10, soft_max=1, default=0.15, unit='LENGTH')

    velocity_threshold: FloatProperty(
        name="Velocity Threshold",
        description="Velocity threshold (in m/s). If the chunk velocity exceeds this threshold, will start switching",
        default=0.4,
        min=0,
        soft_min=0.01,
        soft_max=10,
        unit='VELOCITY',
        max=1000)

    def offset_keyframes(self, wm, ob):
        if not ob.animation_data or not ob.animation_data.action:
            return

        action = ob.animation_data.action

        # creamos los default dicts
        key_viewport = f"{ob.name}_hide_viewport"
        key_render = f"{ob.name}_hide_render"

        if key_viewport not in wm:
            wm[key_viewport] = defaultdict(tuple)
        if key_render not in wm:
            wm[key_render] = defaultdict(tuple)

        for fcu in action.fcurves:
            if "hide_viewport" in fcu.data_path or "hide_render" in fcu.data_path:
                key = key_viewport if "hide_viewport" in fcu.data_path else key_render

                for i, kp in enumerate(fcu.keyframe_points):
                    if str(i) not in wm[key]:
                        wm[key][str(i)] = (kp.co.x, kp.handle_left.x, kp.handle_right.x)

        # ajustamos los keyframes
        for fcu in action.fcurves:
            if "hide_viewport" in fcu.data_path or "hide_render" in fcu.data_path:

                key = key_viewport if "hide_viewport" in fcu.data_path else key_render

                for i, kp in enumerate(fcu.keyframe_points):
                    if self.offset == 0:  # devolver los valores originales
                        kp.co.x, kp.handle_left.x, kp.handle_right.x = wm[key][str(i)]
                    else:
                        loc, loc_handle_left, loc_handle_right = wm[key][str(i)]
                        kp.co.x = loc + self.offset
                        kp.handle_left.x = loc_handle_left + self.offset
                        kp.handle_right.x = loc_handle_right + self.offset

    def offset_update(self, context) -> None:
        scn = context.scene
        rbdlab = scn.rbdlab

        wm = context.window_manager

        tcoll_list = rbdlab.lists.target_coll_list
        tcoll = tcoll_list.active
        # porque get_current_active_tcoll_valild_objects busca solo los visibles:
        # list_chunks = [ob for ob in tcoll.objects if ob.type == 'MESH' and ob.name in context.view_layer.objects]
        target_chunks = obtain_lows_and_highs(self, context, tcoll)

        if len(target_chunks) < 1:
            self.report({'ERROR'}, "No valid Meshes in Current Target Collection!")
            return

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

            # para los original objects:
            self.offset_keyframes(wm, org_ob)

            # para los chunks:
            for ob in chunks:
                self.offset_keyframes(wm, ob)

    offset: IntProperty(
        name="Keyframe Offset",
        description="Offset visual switching keyframes",
        soft_min=-5,
        soft_max=5,
        update=offset_update
    )
