import bpy
from bpy.types import Object
from datetime import datetime
from ...Global.functions import (
    add_fluid_modifier_to_active_object,
    copy_modifier_by_name_from_active_to_selected,
    # get_array_data_from_obj,
    normalize,
    remove_all_keyframes_in_action,
    set_interpolation_curve_to,
    create_modifier
)
from ...Global.animation import check_if_have_previous_kf
from ..particles.update_rbdlab_object import update_broken_neighbours_and_motions
from ...Global.basics import set_active_object, deselect_all_objects
# from ...addon.paths import RBDLabPreferences
from ...addon.naming import RBDLabNaming


def get_frames_and_speeds(ob: Object):
    # necesito todos los frames y todos los speeds en 2 listados:
    obj_all_frames = []
    obj_all_speeds = []

    # por cada objeto actual recolecto sus frames y sus velocities para meterlo en un
    for motion in ob.rbdlab.motions:
        for velocity in motion.velocities:

            # guardo todos los frames de cada objeto:
            # si tiene offset respetamos el offset que tenga:
            if RBDLabNaming.SMOKE_FRAME_OFFSET in ob:
                v_frame = velocity.frame + ob[RBDLabNaming.SMOKE_FRAME_OFFSET]
            else:
                v_frame = velocity.frame

            obj_all_frames.append(v_frame)

            # guardo todas las velocidades de cada objeto:
            obj_all_speeds.append(velocity.speed)

    return obj_all_frames, obj_all_speeds


def common_anim_props(rbdlab, ob, smoke_mod, prop_type, dpath, obj_all_frames, obj_all_speeds):
    for frame, speed in zip(obj_all_frames, obj_all_speeds):

        if float(speed) <= 0:
            continue

        # hago esto primero para no perder el primer keyframe inicial
        # smoke_mod.flow_settings.density=normalize(velocity.speed, 0, 1) * rbdlab.smoke.density_multiplier
        # normalizo los valores entre 0 y 1:

        if prop_type == "density":
            multiplier = rbdlab.smoke.density_multiplier

        elif prop_type == "fuel_amount":
            multiplier = rbdlab.smoke.fuel_multiplier

        # Pongo (siempre, no solo en el primero) un keyframe a 0 en un frame anterior 
        # (si estan muy juntos los keyframes por ejemplo cuando emito por mesh, evito pisarse entre si y dejar todos en 0)
        # ckequeo los dos frames previos para descartar que es un movimiento:
        chk1_kf = check_if_have_previous_kf(ob=ob, frame=frame-1, dpath=dpath)
        if not chk1_kf:
            chk2_kf = check_if_have_previous_kf(ob=ob, frame=frame-2, dpath=dpath)
            if not chk2_kf:
                setattr(smoke_mod.flow_settings, prop_type, 0)
                ob.keyframe_insert(data_path=dpath, frame=frame-1)

        setattr(smoke_mod.flow_settings, prop_type, normalize(
            normalize(
                speed,
                min(obj_all_speeds),
                max(obj_all_speeds)
            ), 0, 1
        ) * multiplier)

        ob.keyframe_insert(
            data_path=dpath,
            frame=frame
        )
        # si es el primero pongo un keyframe a 0 en un frame anterior:
        # if frame == min(obj_all_frames):
        #     setattr(smoke_mod.flow_settings, prop_type, 0)
        #     ob.keyframe_insert(
        #         data_path=dpath,
        #         frame=(frame-1)
        #     )

        set_interpolation_curve_to(ob, dpath, 'LINEAR')


def anim_smoke_mod_density(context, rbdlab, ob, smoke_mod, obj_all_frames, obj_all_speeds, rm_previous: bool = False):
    """ ESTA FUNCTION TAMBIEN ES USADA EN EL UPDATE DE PARTICLES """

    dpath = 'modifiers["' + RBDLabNaming.SMOKE_MOD + '"].flow_settings.density'
    if rm_previous:
        remove_all_keyframes_in_action(context, ob, dpath)

    prop_type = "density"
    common_anim_props(rbdlab, ob, smoke_mod, prop_type, dpath, obj_all_frames, obj_all_speeds)


def anim_smoke_mod_fuel(context, rbdlab, ob, smoke_mod, obj_all_frames, obj_all_speeds, rm_previous: bool = False):
    """ ESTA FUNCTION TAMBIEN ES USADA EN EL UPDATE DE PARTICLES """

    dpath = 'modifiers["' + RBDLabNaming.SMOKE_MOD + '"].flow_settings.fuel_amount'
    if rm_previous:
        remove_all_keyframes_in_action(context, ob, dpath)

    prop_type = "fuel_amount"
    common_anim_props(rbdlab, ob, smoke_mod, prop_type, dpath, obj_all_frames, obj_all_speeds)


def get_particles_systems_from_name(ob):
    if ob:
        psystems = [ps for ps in ob.particle_systems if "_smoke_motion_" in ps.name]
        return psystems


def determine_which_chunks_have_velocities(context, tcoll, retry: bool = False):
    
    if tcoll is not None:
        valid_objects = [ob for ob in tcoll.objects if ob.type == 'MESH' and ob.visible_get() and RBDLabNaming.PASSIVE not in ob]
        # print("valid objects count", len(valid_objects))
        # for chunk_ob in valid_objects:
        #     print(chunk_ob.name, chunk_ob.rbdlab.has_motions)
        chunks_with_velocities = [chunk_ob for chunk_ob in valid_objects if chunk_ob.rbdlab.has_motions]
        # print("chunks with vel count:", len(chunks_with_velocities))
        # print("chunks_with_velocities", chunks_with_velocities)
        if chunks_with_velocities:
            return chunks_with_velocities
        else:
            if retry:
                return []

            # Calcular motions...
            start_update = datetime.now()
            update_broken_neighbours_and_motions(
                context,
                valid_objects,
                step=1,
                distance_threshold=.04,
                # condition=p_create.condition,
                velocity_threshold=.2,
                max_motions=1,
                flag={'BROKEN', 'MOTION'}
            )
            
            print("Update broken/motions: " + str(datetime.now() - start_update))
            tcoll[RBDLabNaming.HAS_BROKEN], tcoll[RBDLabNaming.HAS_MOTIONS], tcoll[RBDLabNaming.VELOCITIES] = 1.0, 1.0, 1.0

            return determine_which_chunks_have_velocities(context, tcoll, retry=True)


def colors_acction(context, ob, col_smoke):
    remove_all_keyframes_in_action(context, ob, "color")
    ob.color_stack.add_color(col_smoke)
    ob.color = col_smoke
    if ob.parent:
        remove_all_keyframes_in_action(context, ob.parent, "color")
        ob.parent.color_stack.add_color(col_smoke)
        ob.parent.color = col_smoke


def smoke_common(self, context, tcoll, method_type) -> bool:
    # start0 = datetime.now()

    scn = context.scene
    rbdlab = scn.rbdlab

    # addon_preferences = RBDLabPreferences.get_prefs(context)
    valid_objects = []
    # col_smoke = list(addon_preferences.col_smoke)

    # check_if_have_velocities_and_add_if_not_have()
    if RBDLabNaming.CMPUTD_VELOCITIES not in tcoll:
        bpy.ops.rbdlab.compute_velocities()

    # objetenemos los chunks con velocidades:
    chunks_with_velocities = determine_which_chunks_have_velocities(context, tcoll)

    # intentamos abortar si hay chunks con velocities:
    if not chunks_with_velocities:
        print("Not chunks with velocities avalidable!")
        return False

    if method_type == 'PARTICLES':
        # ahora obtengo el nombre real del sistema de particulas:
        deselect_all_objects(context)

        # a parte de tener velocities el objeto activo tiene q tener particulas RBDLabNaming.INNER_EMISOR
        ob_active = False
        i = 0

        # buscando los childs de los chunks con particles de tipo smoke:
        if method_type == 'PARTICLES':
   
            chunks_with_childs = set()            
            for ob in chunks_with_velocities: 
                
                if RBDLabNaming.CHUNK_PART_CHILD not in ob:
                    continue
                
                for child in ob[RBDLabNaming.CHUNK_PART_CHILD]:
                    chunks_with_childs.add(child)

        else:
            chunks_with_childs = [child for ob in chunks_with_childs if RBDLabNaming.CHUNK_PART_CHILD in ob for child in ob[RBDLabNaming.CHUNK_PART_CHILD] if child in context.view_layer.objects]

        childs_with_ps = [child for child in chunks_with_childs if RBDLabNaming.INNER_EMISOR in child]

        childs_with_ps_smoke = []
        for child in childs_with_ps:
            for ps in child.particle_systems:
                if "_smoke_motion_" in ps.name:
                    childs_with_ps_smoke.append(child)

        # en este caso es mas rapido en 2 loop for normales que dos comprehension.
        # childs_with_ps_smoke = [child for child in childs_with_ps if [
        #     child for ps in child.particle_systems if "_smoke_motion_" in ps.name]]

        # print("childs_with_ps_smoke", childs_with_ps_smoke)

        if len(childs_with_ps_smoke) > 0:
            ob_active = childs_with_ps_smoke[0]
            chunks_with_velocities = childs_with_ps_smoke
        else:
            print("Cant get chunk childrens with emision particles!")

    else:  # from CHUNKS:
        ob_active = chunks_with_velocities[0]

    # print("ob_active", ob_active.name)

    if not ob_active:
        return False

    set_active_object(context, ob_active)

    if ob_active not in valid_objects:
        valid_objects.append(ob_active)

    # if method_type == 'PARTICLES':
    #     psystems = get_particles_systems_from_name(ob_active)
    #     if not psystems:
    #         print("Cant get any Particle system from: ", ob_active.name)
    #         return False


    # start1 = datetime.now()

    if method_type == 'PARTICLES':
        

        # les ponemos el modifier smoke a todos:
        for ob in childs_with_ps_smoke:
            
            psystems = get_particles_systems_from_name(ob)
            for ps in psystems:

                smoke_mod = ob.modifiers.get(RBDLabNaming.SMOKE_MOD)
                if not smoke_mod:
                    smoke_mod = create_modifier(ob, RBDLabNaming.SMOKE_MOD, 'FLUID')
                    smoke_mod.fluid_type = 'FLOW'
                
                if smoke_mod:
                    smoke_mod.flow_settings.flow_source = 'PARTICLES'
                    smoke_mod.flow_settings.particle_system = ps
        
        [(ob.select_set(True), valid_objects.append(ob)) for ob in chunks_with_velocities if ob_active.name != ob.name and len(ob.particle_systems) > 0]
        
    else:

        # si no tiene smoke lo creamos y si tiene lo capturamos:
        smoke_mod = ob_active.modifiers.get(RBDLabNaming.SMOKE_MOD)
        if not smoke_mod:
            smoke_mod = add_fluid_modifier_to_active_object(context, 'FLOW')

        # si no hay smoke intentamos abortar:
        if not smoke_mod:
            print(ob_active.name + " not have " + RBDLabNaming.SMOKE_MOD + " modifier!")
            return False

        # print("capturando smoke mod: " + str(datetime.now() - start1))

        # start2 = datetime.now()
        # selecciono el resto que no sean el activo:
        [(ob.select_set(True), valid_objects.append(ob)) for ob in chunks_with_velocities if ob_active.name != ob.name]

        # le copioo los modifiers al resto de mi whitelist:
        copy_modifier_by_name_from_active_to_selected(context, [smoke_mod.name])
        # bpy.ops.object.make_links_data(type='MODIFIERS')

    # print("copiando modifiers: " + str(datetime.now() - start2))

    # # configuramos las particulas:
    # # falta opr hacer

    # start3 = datetime.now()

    if method_type == 'PARTICLES':

        # smoke_modifiers = []
        # for ob in childs_with_ps_smoke:
        #     if RBDLabNaming.INNER_EMISOR in ob:
        #         for mod in ob.modifiers:
        #             if mod.name.endswith("_Smoke"):
        #                 smoke_modifiers.append[mod]

        smoke_modifiers = [mod for ob in childs_with_ps_smoke if RBDLabNaming.INNER_EMISOR in ob for mod in ob.modifiers if mod.name.endswith("_Smoke")]

    else:
        smoke_modifiers = [ob.modifiers.get(smoke_mod.name) for ob in valid_objects if smoke_mod.name in ob.modifiers]

    for smoke_mod in smoke_modifiers:

        smoke_mod.flow_settings.flow_type = 'SMOKE'
        smoke_mod.flow_settings.flow_behavior = 'INFLOW'
        smoke_mod.flow_settings.density = 0

        flow_source = 'PARTICLES' if method_type == 'PARTICLES' else 'MESH'
        if smoke_mod.flow_settings.flow_source != flow_source:
            smoke_mod.flow_settings.flow_source = 'PARTICLES' if method_type == 'PARTICLES' else 'MESH'
        
        smoke_mod.flow_settings.surface_distance = rbdlab.smoke.emiter.surface_distance
        smoke_mod.flow_settings.use_initial_velocity = True

    # print("1 configurando las particulas: " + str(datetime.now() - start3))

    # start4 = datetime.now()

    # configuramos el smoke:
    # print("valid_objects", valid_objects)

    for ob in valid_objects:

        smoke_mod = ob.modifiers.get(smoke_mod.name)
        if not smoke_mod:
            continue

        # colors_acction(context, ob, col_smoke)

        # if hasattr(obj, "vertex_groups"):
        #     if "Interior" in obj.vertex_groups:
        #         smoke_mod.flow_settings.density_vertex_group = "Interior"

        # necesito todos los frames y todos los speeds en 2 listados:
        obj_all_frames, obj_all_speeds = get_frames_and_speeds(ob)

        # print(obj_all_frames)
        # print(obj_all_speeds)

        #################################################################################################
        # Density
        #################################################################################################
        anim_smoke_mod_density(context, rbdlab, ob, smoke_mod, obj_all_frames, obj_all_speeds, False)

        #################################################################################################
        # Fuel
        #################################################################################################
        anim_smoke_mod_fuel(context, rbdlab, ob, smoke_mod, obj_all_frames, obj_all_speeds, False)

    return True
