import bpy
import bmesh
import numpy as np
from typing import List, Union
from math import degrees
from random import uniform
from datetime import datetime
from bpy.props import EnumProperty
from mathutils import Vector, Euler
from mathutils.bvhtree import BVHTree
from bpy.types import Operator, Object, Depsgraph
from ...addon.naming import RBDLabNaming
# from ...Global.functions import apply_transfroms_low_level
from ...Global.basics import deselect_all_objects
from ...Global.math import smoothstep #, distance_between
from ...Global.animation import check_if_have_previous_kf
from ...Global.get_common_vars import get_common_vars
# from mathutils import Matrix
# from statistics import median
from ...addon.paths import RBDLabPreferences



class ACTIVATORS_OT_recording(Operator):
    bl_idname = "rbdlab.act_record"
    bl_label = "Recording"
    bl_description = "Record Keyframes on the Layers Marked for Recording"
    bl_options = {'REGISTER', 'UNDO'}

    objs_min_max = {}

    mode: EnumProperty(
        name="Activators record mode",
        items=(('NORMAL', "Normal", "", 0), ('FORCE_PREVIEW', "Preview", "", 1)),
        default='NORMAL',
    )

    @classmethod
    def poll(cls, context):
        # scn = context.scene
        ACTIVATORS_OBJECTS = [obj for obj in context.view_layer.objects if RBDLabNaming.ACTIVATORS_OBJECTS in obj]
        if len(ACTIVATORS_OBJECTS) < 1:
            return False
        return True


    def get_mins_maxs(self, ob:Object) -> tuple:

        mw = ob.matrix_world
        coords = [mw @ v.co for v in ob.data.vertices]
        
        x_co = [co.x for co in coords]
        y_co = [co.y for co in coords]
        z_co = [co.z for co in coords]
        
        x_min, x_max = min(x_co), max(x_co)
        y_min, y_max = min(y_co), max(y_co)
        z_min, z_max = min(z_co), max(z_co)
        
        # print(x_min, x_max)
        # print(y_min, y_max)
        # print(z_min, z_max)
        
        return (x_min, x_max, y_min, y_max, z_min, z_max)


    def add_debug_curve(self, new_name:str, ray_start:Vector, ray_end:Vector) -> None:
        # RBDLab collection:
        rbdlab_coll_name = RBDLabNaming._RBDLab_name
        rbdlab_coll = bpy.data.collections.get(rbdlab_coll_name)
        if not rbdlab_coll:
            rbdlab_coll = bpy.data.collections.new(rbdlab_coll_name)
        
        # Crea una colección para las curvas de debug:
        curves_collection = bpy.data.collections.get(RBDLabNaming.ACTVTRS_RAY_CAST_DB)
        if not curves_collection:
            curves_collection = bpy.data.collections.new(RBDLabNaming.ACTVTRS_RAY_CAST_DB)
            rbdlab_coll.children.link(curves_collection)

        # Crea una nueva curva de tipo "Bezier"
        curve = bpy.data.curves.new(name="RayCurve", type='CURVE')
        curve.resolution_u = 1
        curve.dimensions = '3D'
        spline = curve.splines.new(type='BEZIER')
        spline.bezier_points.add(1)
        spline.bezier_points[0].co = ray_start
        spline.bezier_points[1].co = ray_end
        ob_curve = bpy.data.objects.new("RayCurve", curve)
        curves_collection.objects.link(ob_curve)
        ob_curve.select_set(False)
        ob_curve.name = new_name + "_db"
    

    def sphere_intersection_method(self, frame, activator: Object, chunk: Object, activator_margin: float, debug:bool=False) -> bool:
        # print("exec sphere intersection method")

        #sphere_center = sphere.location
        sphere_center = activator.matrix_world.translation

        #sphere_radius = activator.scale.x        # Suponemos que la esfera es uniforme
        sphere_radius = activator.dimensions.x    # Suponemos que la esfera es uniforme
        # print("activator.dimensions", activator.dimensions.x)
        
        # Obtener la matriz de transformación global del chunk
        # chunk_center = chunk.location
        # uso el chunk sin evaluar, ya que no parece estar funcionando igualmente el eval:
        chunk_center = chunk.matrix_world.translation

        # Calcular la dirección desde la esfera hacia el chunk
        ray_direction = Vector((chunk_center - sphere_center))
        distance = ray_direction.length
        
        half_sphere = sphere_radius/2
        
        collide = distance <= (half_sphere + activator_margin)
        
        # DEBUG:
        if debug and collide:
            
            # NOTA IMPORTANTE, en el ejemplo de "pelotas emitidas desde particulas contra un muro", a partir de un frame x dejan de ser kinematics para ser simulación, si
            # ese ultimo frame están demasiado lejos del muro, y si tienes el "automatic frame range" activado (por defecto lo está), es muy posible que 
            # nunca tengas colisión, porque el "automatic range" computa hasta el ultimo frame animado donde estuviera la esfera, por lo tanto 
            # lo que suceda despues en la simulación no lo sabemos y no se computará, por lo tanto se debería de usar el rango completo de la simulación.
                        
            print(frame, collide)
            ray_end = sphere_center + (distance + activator_margin) * ray_direction.normalized()
            self.add_debug_curve(activator.name, sphere_center, ray_end)

        return collide
    

    def cube_intersection_method(self, x_min, x_max, y_min, y_max, z_min, z_max, chunk_origin: Vector, activator_margin: float) -> bool:
        
        # Disminuye los valores mínimos
        x_min -= activator_margin
        y_min -= activator_margin
        z_min -= activator_margin

        # Aumenta los valores máximos
        x_max += activator_margin
        y_max += activator_margin
        z_max += activator_margin

        return all([x_min <= chunk_origin.x <= x_max, y_min <= chunk_origin.y <= y_max, z_min <= chunk_origin.z <= z_max])


    
    def intersection_method(self, activator_now_bvh: Object, chunk: Object) -> list:
        # uso objetos evaluados para probar:
        # eval_chunk = chunk.evaluated_get(dg)

        bm1 = bmesh.new()
        bm1.from_mesh(chunk.data)
        bm1.transform(chunk.matrix_world)

        previous_chunk_bvh = BVHTree.FromBMesh(bm1)
        bm1.free()

        # Get intersecting pairs
        # --------------------------------------------------------------------------------

        # NOTA: Con overlap en algunos casos estaba skipeando algunos activator_now
        # pruebas:
        # inter = activator_now.closest_point_on_mesh(eval_chunk.location)
        # inter = activator_now_bvh.find_nearest(eval_chunk.matrix_world.translation, 0)
        
        # si detecta la intercceción, bien, sino lo buscamos por distancia con un thresold:
        intersection = activator_now_bvh.overlap(previous_chunk_bvh)
        return intersection


    def get_valid_chunks(self, ac_layers_list) -> List[Object]:
        
        # Guardo los activators en sus chunks:
        ac_layers_list.store_activators_in_chunks

        # obtengo los chunks:
        return ac_layers_list.get_all_computable_includes
        
        # Los chuks de su active Layer list:
        # return ac_layers_list.get_all_computable_includes_from_active


    def animation_color(self, chunk, frame, color):

        # el color q sea le meto un keyframe anterior:
        if not check_if_have_previous_kf(chunk, frame-1, "color"):
            chunk.keyframe_insert(
                data_path="color",
                frame=(frame-1)
            )

        # seteo el color rojo y le meto el keyframe:
        if not check_if_have_previous_kf(chunk, frame, "color"):
            chunk.color = color
            chunk.keyframe_insert(
                data_path="color",
                frame=(frame)
            )


    def intersection_check(
                            self, 
                            context, 
                            tcoll,
                            active_item,
                            current_type,
                            min_frame, 
                            user_substeps, 
                            ACTIVATORS_OBJECTS, objects: list = [],
                            all_computable_constraints: list = []
                        ) -> list[object]:

        global sphere_origin, sphere_radius
        loc_with_keyframes = False
        rot_with_keyframes = False
        explode_with_keyframes = False


        # para usar objetos evaluados:
        dg = context.evaluated_depsgraph_get()

        if not ACTIVATORS_OBJECTS:
            return None

        if objects is None:
            return None

        if len(ACTIVATORS_OBJECTS) == 0 or len(objects) == 0:  # or len(context.selected_objects) == 0:
            return None
        
        addon_preferences = RBDLabPreferences.get_prefs(context)
        red_color = addon_preferences.col_activator_actived

        deactivation_recorded = False
        kinematic_recorded = False
        constraints_recorded = False
        dynamic_recorded = False

        wm = context.window_manager
        scn = context.scene
        rbdlab = scn.rbdlab
        ui = rbdlab.ui

        # activator_now_bvh = None
        # x_min = None
        # x_max = None
        # y_min = None
        # y_max = None
        # z_min = None
        # z_max = None
        # sphere_origin = None
        # sphere_radius = None

        intersected_chunks = []

        # first frame with keyframes in activators object:
        min_frame = int(min_frame)
        scn.frame_current = min_frame

        scn_objects = scn.objects

        # progress from [0 - 100]
        wm.progress_begin(0, 100)

        # substeps = [0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0]
        # total = len(substeps)
        total = 11
        substeps = np.linspace(0.0, 1.0, total)

        skip_substeps = False

        x_min_loc = rbdlab.activators.force_x_min_loc_rand
        x_max_loc = rbdlab.activators.force_x_max_loc_rand
        y_min_loc = rbdlab.activators.force_y_min_loc_rand
        y_max_loc = rbdlab.activators.force_y_max_loc_rand
        z_min_loc = rbdlab.activators.force_z_min_loc_rand
        z_max_loc = rbdlab.activators.force_z_max_loc_rand

        x_min_rot = rbdlab.activators.force_x_min_rot_rand
        x_max_rot = rbdlab.activators.force_x_max_rot_rand
        y_min_rot = rbdlab.activators.force_y_min_rot_rand
        y_max_rot = rbdlab.activators.force_y_max_rot_rand
        z_min_rot = rbdlab.activators.force_z_min_rot_rand
        z_max_rot = rbdlab.activators.force_z_max_rot_rand

        force_mult = rbdlab.activators.force_loc_scale
        explode_mult = rbdlab.activators.force_explode_scale
        rot_mult = rbdlab.activators.force_rot_scale

        ease_in_loc = rbdlab.activators.force_loc_ease_in / 100
        ease_out_loc = rbdlab.activators.force_loc_ease_out / 100

        ease_in_exp = rbdlab.activators.force_exp_ease_in / 100
        ease_out_exp = rbdlab.activators.force_exp_ease_out / 100

        ease_in_rot = rbdlab.activators.force_rot_ease_in / 100
        ease_out_rot = rbdlab.activators.force_rot_ease_out / 100

        ######################################################################################################
        # Preparando los diccionarios donde relaciono los activators con los chunks y sus rangos de animación.
        # El hilo conductor para relacionarlos es el activator.
        #-----------------------------------------------------------------------------------------------------
        
        # Activators And Chunks = {act: [chunks]}
        # print("objects", objects)

        activators_and_chunks = {}
        for chunk in objects:

            if RBDLabNaming.CHUNK_ACTIVATORS not in chunk:
                # print(RBDLabNaming.CHUNK_ACTIVATORS, " Not in chunk ", chunk.name)
                continue

            for act in chunk[RBDLabNaming.CHUNK_ACTIVATORS]:
                
                if "min_max_keyframnes" not in act:
                    # print("min_max_keyframnes not in activator", act.name)
                    continue

                if act not in activators_and_chunks:
                    activators_and_chunks[act] = [chunk]
                else:
                    activators_and_chunks[act].append(chunk)
        
        # print("activators_and_chunks:", activators_and_chunks)

        # Activators And Ranges = {act: (range)}
        activators_ranges = {}
        for act in activators_and_chunks.keys():

            act_range = (int(act["min_max_keyframnes"][0]), int(act["min_max_keyframnes"][1]))
            if act not in activators_ranges:
                activators_ranges[act] = act_range

        # print("Activators ranges:", activators_ranges)

        #-----------------------------------------------------------------------------------------------------
        ######################################################################################################
        
        # Por cada Activator y por su Rango de frames:
        for activator_now, act_range in activators_ranges.items():

            if activator_now not in ACTIVATORS_OBJECTS:
                continue
        
            # print(f"Procesando {activator_now.name}", act_range)

            # print(f"Procesando {act.name} en el rango de frames: {act_range}")

            act_frame_start = int(act_range[0])
            act_frame_end = int(act_range[1])

            for frame in range(act_frame_start, act_frame_end + 1):
                
                # print("Frame -> ", frame)

                for sbtps_index in range(0, total, round(total / user_substeps)):
                    subframe = substeps[sbtps_index]
                    # print("SubFrame -> ", round(subframe, 2)) 

                    scn.frame_set(frame, subframe=subframe)

                    # print(scn.frame_current)
                    
                    # Por cada Chunk del activator correspondiente:                    
                    for chunk in activators_and_chunks[activator_now]:
                        
                        activator_now_bvh = None
                        previous_chunk_bvh = None

                        if RBDLabNaming.CHUNK_ACTIVATORS not in chunk:
                            continue 

                        # Si no tiene guardada la opcion de computar o no, lo skipeamos:
                        if RBDLabNaming.ACT_OB_COMPUTE not in activator_now:
                            continue

                        # Si no tiene activa la opcion de computar, lo skipeamos:
                        if not activator_now[RBDLabNaming.ACT_OB_COMPUTE]:
                            continue

                        activator_type = activator_now["activator"] if "activator" in activator_now else 'MESH' # acrivator_type sera uno de estos (SPHERE, CUBE, MESH)
                        activators_frame_duration = act_frame_end - act_frame_start
                        
                        # activator_now = activator_now.evaluated_get(dg) # el evaluated no tiene min_max_keyframnes 

                        # Calcular los frames de entrada y salida (ease in/out) para el activators actual.
                        # location:
                        activators_ease_in_loc = (act_frame_start, act_frame_start + ease_in_loc * activators_frame_duration)
                        activators_ease_out_loc = (act_frame_end - ease_out_loc * activators_frame_duration, act_frame_end)

                        # explode:
                        activators_ease_in_exp = (act_frame_start, act_frame_start + ease_in_exp * activators_frame_duration)
                        activators_ease_out_exp = (act_frame_end - ease_out_exp * activators_frame_duration, act_frame_end)

                        # rotation:
                        activators_ease_in_rot = (act_frame_start, act_frame_start + ease_in_rot * activators_frame_duration)
                        activators_ease_out_rot = (act_frame_end - ease_out_rot * activators_frame_duration, act_frame_end)

                        # Asegurar de que no compartan frames el in y el out.
                        # location:
                        if activators_ease_in_loc[1] >= activators_ease_out_loc[0]:
                            activators_ease_out_loc = (activators_ease_in_loc[1] + 1, act_frame_end)

                        # explode:
                        if activators_ease_in_exp[1] >= activators_ease_out_exp[0]:
                            activators_ease_out_exp = (activators_ease_in_exp[1] + 1, act_frame_end)

                        # rotation:
                        if activators_ease_in_rot[1] >= activators_ease_out_rot[0]:
                            activators_ease_out_rot = (activators_ease_in_rot[1] + 1, act_frame_end)

                        # Invalida el ease sin ambos frames son iguales.
                        # location:
                        if activators_ease_in_loc[0] >= activators_ease_in_loc[1] or not any(activators_ease_in_loc):
                            activators_ease_in_loc = None
                        if activators_ease_out_loc[0] >= activators_ease_out_loc[1] or not any(activators_ease_out_loc):
                            activators_ease_out_loc = None

                        # explode:
                        if activators_ease_in_exp[0] >= activators_ease_in_exp[1] or not any(activators_ease_in_exp):
                            activators_ease_in_exp = None
                        if activators_ease_out_exp[0] >= activators_ease_out_exp[1] or not any(activators_ease_out_exp):
                            activators_ease_out_exp = None

                        # rotation:
                        if activators_ease_in_rot[0] >= activators_ease_in_rot[1] or not any(activators_ease_in_rot):
                            activators_ease_in_rot = None
                        if activators_ease_out_rot[0] >= activators_ease_out_rot[1] or not any(activators_ease_out_rot):
                            activators_ease_out_rot = None

                        # print("Activators -> ", activator_now)
                        
                        if activator_type == 'MESH':

                            skip_substeps = False

                            # create bmesh object
                            bm2 = bmesh.new()

                            # fill bmesh data from object
                            bm2.from_mesh(activator_now.data)
                            # bm2.transform(activator_now.matrix_world)

                            eval_activator_now = activator_now.evaluated_get(dg)
                            bm2.transform(eval_activator_now.matrix_world)

                            # make BVH tree from BMesh of object
                            activator_now_bvh = BVHTree.FromBMesh(bm2)
                            bm2.free()

                        else:
                            
                            skip_substeps = True

                            if activator_type == 'CUBE':
                                x_min, x_max, y_min, y_max, z_min, z_max = self.get_mins_maxs(activator_now)

                            # elif activator_type == 'SPHERE':
                            #     activator_eval = activator_now.evaluated_get(dg)

                        # Borrar los chunks ya procesados en la vuelta anterior (si los hubiera) al usar use_single_activation:
                        # if intersected_chunks:
                        #     [objects.remove(ob) for ob in intersected_chunks if ob in objects]   
                        #     intersected_chunks.clear()

                        # si ya fue procesado skipeamos:
                        if chunk in intersected_chunks:
                            continue

                        # no_collision = set()
                        # activator_margin = active_item.activator_margin
                        activator_margin = ui.activator_margin

                        # intento fallido de extend:
                        # if rbdlab.ui.activator_extend > 0:
                        #     print("prev len obs", len(objects))
                        #     neighbours = []
                            
                        #     for chunk in objects:

                        #         current_neighbours = [neigh.object for neigh in chunk.neighbor_chunks.chunks.values()]
                        #         neighbours.extend(current_neighbours)

                        #     objects.extend(neighbours)
                        #     print("post len obs", len(objects))

                        # Procesar chunks sobre el activators actual.
                        
                        if activator_type == 'MESH':

                            intersection = self.intersection_method(activator_now_bvh, chunk)
                            # si no hay intersection bvh entonces pruebo por distancia:
                            if not intersection:
                                # no consigo algo mas automatico, asi que el threshold lo elige el usuario por ahora:
                                # threshold_distance = median(activator_now.dimensions) * 0.5
                                nearest = activator_now_bvh.find_nearest_range(chunk.matrix_world.translation, activator_margin)
                                if not nearest:
                                    continue                                    

                        else:

                            # Si tiene parent del handler lo tenemos en cuenta:
                            # chunk_origin = chunk.location @ chunk.parent.matrix_world if chunk.parent else chunk.location
                            # chunk_origin = chunk.location + chunk.parent.location if chunk.parent else chunk.location
                            chunk_origin = chunk.matrix_world.translation + chunk.parent.matrix_world.translation if chunk.parent else chunk.matrix_world.translation
                            
                            # El eval no tiene sentido, porque ademas desactivamos el rbw por performance y no 
                            # se corren las fisicas miestras haces el record.
                            # chunk_eval = chunk.evaluated_get(dg)
                            # chunk_origin = chunk_eval.matrix_world.translation + chunk_eval.parent.matrix_world.translation if chunk.parent else chunk_eval.matrix_world.translation


                            if activator_type == 'SPHERE':
                                # sphere = activator_eval
                                sphere = activator_now

                                sph_collision = self.sphere_intersection_method(frame, sphere , chunk, activator_margin, debug=False)
                                if not sph_collision:
                                    # print(f"SPHERE: {activator_now.name} skip {chunk.name}")
                                    # no_collision.add(chunk)
                                    continue

                            elif activator_type == 'CUBE':

                                cb_collision = self.cube_intersection_method(x_min, x_max, y_min, y_max, z_min, z_max, chunk_origin, activator_margin)
                                if not cb_collision:
                                    # print(f"CUBE: {activator_now.name} skip {chunk.name}")
                                    # no_collision.add(chunk)
                                    continue

                        # Agregar indice del chunk ya procesado (que ha hecho intersect/overlap).
                        # Este chunk será borrado en la siguiente vuelta.
                        
                        # if chunk in no_collision:
                        #     continue

                        # Activarlos solo una vez o constantemente:
                        if ui.use_single_activation:
                            intersected_chunks.append(chunk)

                        # if chunk.name == "Cube_cell.128":
                        #     print("[Activate] in Frame:", frame, activator_now.name.replace("F_activator_sphere_",""), chunk.name)

                        current_frame = scn.frame_current

                        # self.activators_work_with = ["rbdlab_acetonized_deactivation", "rbdlab_acetonized_kineatic", "rbdlab_acetonized_constraints"]

                        custom_properties = list(chunk.keys())
                        to_ignore = False


                        if hasattr(chunk, "rigid_body"):

                            # +++++++++++++++++++++++++++++++++++++++++++++++++
                            # INITIAL VELOCITY: DIRECTION.
                            # +++++++++++++++++++++++++++++++++++++++++++++++++
                            if RBDLabNaming.ACTIVATORS_EXPLODE_DONE not in tcoll and 'KINEMATIC' in current_type and activator_now[RBDLabNaming.ACT_RECORD_TYPE] == 'KINEMATIC':

                                # Location Force:
                                force = rbdlab.activators.force_direction.copy()
                                if rbdlab.ui.activators_force_loc_mode == 'RAND':
                                    force.x = uniform(x_min_loc, x_max_loc)
                                    force.y = uniform(y_min_loc, y_max_loc)
                                    force.z = uniform(z_min_loc, z_max_loc)

                                # Verificar que no sea fuerza nula.
                                if any(force.to_tuple()) and force_mult != 0:
                                    # Aplicar Multiplicador.
                                    force *= force_mult

                                    # Aplicar fuerza y sacar distancia recorrida.
                                    p1 = chunk.location.copy()
                                    p2 = chunk.location.copy() + force
                                    dist = (p2 - p1).length

                                    # offset
                                    if dist == 0 or max(
                                            list(force)) == 0:  # <- fix ZeroDivisionError: float division by zero
                                        loc_frame_offset = 1
                                    elif rbdlab.activators.force_loc_frame_offset == 0:
                                        # Automatic Frame-Offset.
                                        t = dist / max(list(force))
                                        loc_frame_offset = max(1, int(t))
                                    else:
                                        # Manual Frame-Offset.
                                        loc_frame_offset = rbdlab.activators.force_loc_frame_offset

                                    # clamp from start timeline:
                                    loc_start_clamped = current_frame - loc_frame_offset - 1
                                    if loc_start_clamped < act_frame_start:
                                        loc_start_clamped = act_frame_start
                                    if loc_start_clamped == (current_frame - 1):
                                        loc_start_clamped = current_frame - 2

                                    # Suavizar fuerza en Entrada y Salida....
                                    if activators_ease_in_loc and current_frame >= activators_ease_in_loc[0] and current_frame <= activators_ease_in_loc[1]:
                                        force *= smoothstep(*activators_ease_in_loc, current_frame)
                                    elif activators_ease_out_loc and current_frame >= activators_ease_out_loc[0] and current_frame <= activators_ease_out_loc[1]:
                                        force *= (1 - smoothstep(*activators_ease_out_loc, current_frame))

                                    # APPLY KEYFRAMES.
                                    # chunk.keyframe_insert(data_path="location", frame=(current_frame - frame_offset - 1))
                                    chunk.keyframe_insert(data_path="location", frame=loc_start_clamped)
                                    # chunk.keyframe_insert(data_path="location", frame=current_frame-2)
                                    chunk.location += force
                                    chunk.keyframe_insert(data_path="location", frame=current_frame - 1)

                                    if "rbdlab_acetonized_with_loc_force" not in chunk:
                                        chunk["rbdlab_acetonized_with_loc_force"] = True

                                    loc_with_keyframes = True

                            # +++++++++++++++++++++++++++++++++++++++++++++++++
                            # INITIAL VELOCITY: EXPLODE.
                            # +++++++++++++++++++++++++++++++++++++++++++++++++
                            if RBDLabNaming.ACTIVATORS_EXPLODE_DONE in rbdlab.filtered_target_collection and 'KINEMATIC' in current_type: # (kinematic y initial vel al ir juntos no se usa el del ob) and activator_now[RBDLabNaming.ACT_RECORD_TYPE] == 'KINEMATIC':

                                if RBDLabNaming.ACTIVATORS_EXPLODED_DEST not in chunk:
                                    continue

                                # Location Force:
                                force = chunk.matrix_world.translation - Vector(
                                    chunk[RBDLabNaming.ACTIVATORS_EXPLODED_DEST])

                                # Verificar que no sea fuerza nula.
                                if any(force.to_tuple()) and explode_mult != 0:
                                    # Aplicar Multiplicador.
                                    force *= explode_mult

                                    # Aplicar fuerza y sacar distancia recorrida.
                                    p1 = chunk.location.copy()
                                    p2 = chunk.location.copy() + force
                                    dist = (p2 - p1).length

                                    # offset
                                    if dist == 0 or max(
                                            list(force)) == 0:  # <- fix ZeroDivisionError: float division by zero
                                        loc_frame_offset = 1
                                    elif rbdlab.activators.force_explode_frame_offset == 0:
                                        # Automatic Frame-Offset.
                                        t = dist / max(list(force))
                                        loc_frame_offset = max(1, int(t))
                                    else:
                                        # Manual Frame-Offset.
                                        loc_frame_offset = rbdlab.activators.force_explode_frame_offset

                                    # clamp from start timeline:
                                    loc_start_clamped = current_frame - loc_frame_offset - 1
                                    if loc_start_clamped < act_frame_start:
                                        loc_start_clamped = act_frame_start
                                    if loc_start_clamped == (current_frame - 1):
                                        loc_start_clamped = current_frame - 2

                                    # Suavizar fuerza en Entrada y Salida....
                                    # if activators_ease_in_exp and current_frame >= activators_ease_in_exp[0] and current_frame <= activators_ease_in_exp[1]:
                                    #     force *= smoothstep(*activators_ease_in_exp, current_frame)
                                    # elif activators_ease_out_exp and current_frame >= activators_ease_out_exp[0] and current_frame <= activators_ease_out_exp[1]:
                                    #     force *= (1 - smoothstep(*activators_ease_out_exp, current_frame))

                                    # APPLY KEYFRAMES.
                                    # chunk.keyframe_insert(data_path="location", frame=current_frame - 1)
                                    chunk.keyframe_insert(data_path="location", frame=loc_start_clamped)
                                    chunk.matrix_world.translation = chunk[RBDLabNaming.ACTIVATORS_EXPLODED_DEST]
                                    chunk.keyframe_insert(data_path="location", frame=current_frame)

                                    if "rbdlab_acetonized_with_explode_force" not in chunk:
                                        chunk["rbdlab_acetonized_with_explode_force"] = True

                                    explode_with_keyframes = True

                            # +++++++++++++++++++++++++++++++++++++++++++++++++
                            # INITIAL VELOCITY: ROTATION.
                            # +++++++++++++++++++++++++++++++++++++++++++++++++
                            rotation = Vector(tuple(rbdlab.activators.force_rotation))
                            if rbdlab.ui.activators_force_rot_mode == 'RAND':
                                rotation.x = uniform(x_min_rot, x_max_rot)
                                rotation.y = uniform(y_min_rot, y_max_rot)
                                rotation.z = uniform(z_min_rot, z_max_rot)

                            # Verificar que no sea rotación nula.
                            if any(rotation.to_tuple()) and rot_mult != 0:
                                # Apply multiplier.
                                rotation *= rot_mult

                                # Aplicar rotation y sacar distancia recorrida.
                                rot_i = chunk.rotation_euler.to_quaternion()
                                rot_f = Euler(rotation.to_tuple(), 'XYZ').to_quaternion()
                                rot_diff = rot_i.rotation_difference(rot_f)
                                max_angle = max(list(rot_diff.axis))

                                if max_angle == 0:  # <- fix ZeroDivisionError: float division by zero
                                    rot_frame_offset = 1
                                elif rbdlab.activators.force_rot_frame_offset == 0:
                                    # Automatic Frame-Offset.
                                    t = abs(degrees(max_angle) / 30)
                                    rot_frame_offset = max(1, int(t))
                                else:
                                    # Manual Frame-Offset.
                                    rot_frame_offset = rbdlab.activators.force_rot_frame_offset

                                # Clamp frame.
                                rot_start_clamped = current_frame - rot_frame_offset - 1
                                if rot_start_clamped < act_frame_start:
                                    rot_start_clamped = act_frame_start
                                if rot_start_clamped == (current_frame - 1):
                                    rot_start_clamped = current_frame - 2

                                # Rotation Ease In-Out.
                                if activators_ease_in_rot and current_frame >= activators_ease_in_rot[0] and current_frame <= activators_ease_in_rot[1]:
                                    rotation *= smoothstep(*activators_ease_in_rot, current_frame)
                                elif activators_ease_out_rot and current_frame >= activators_ease_out_rot[0] and current_frame <= activators_ease_out_rot[1]:
                                    rotation *= (1 - smoothstep(*activators_ease_out_rot, current_frame))

                                # APPLY KEYFRAMES.
                                # chunk.keyframe_insert(data_path="rotation_euler", frame=current_frame - 2)
                                chunk.keyframe_insert(data_path="rotation_euler", frame=rot_start_clamped)
                                # Create a new euler and apply its rotation to the chunk.
                                euler_rot = Euler(rotation.to_tuple(), 'XYZ')
                                chunk.rotation_euler.rotate(euler_rot)
                                chunk.keyframe_insert(data_path="rotation_euler", frame=current_frame - 1)

                                if "rbdlab_acetonized_with_rot_force" not in chunk:
                                    chunk["rbdlab_acetonized_with_rot_force"] = True

                                rot_with_keyframes = True

                            # +++++++++++++++++++++++++++++++++++++++++++++++++

                            #-----------------------------------------------------------------
                            # DEACTIVATION:
                            #-----------------------------------------------------------------
                            if 'DEACTIVATION' in current_type and self.mode == 'NORMAL' and activator_now[RBDLabNaming.ACT_RECORD_TYPE] == 'DEACTIVATION':
                                if hasattr(chunk.rigid_body, "use_deactivation"):
                                    if chunk.rigid_body.use_deactivation:

                                        # si ya fue acetonized en su categoria pasamos de el:
                                        for cp in custom_properties:
                                            cpl = cp.lower()
                                            if cpl == "rbdlab_acetonized_deactivation":
                                                to_ignore = True

                                        if not to_ignore:
                                            # print("actuando en deactivation con el helper", activator_now)
                                            chunk.keyframe_insert(
                                                data_path="rigid_body.use_deactivation",
                                                frame=current_frame
                                            )
                                            chunk.rigid_body.use_deactivation = False
                                            chunk.keyframe_insert(
                                                data_path="rigid_body.use_deactivation",
                                                frame=(current_frame + 1)
                                            )
                                            chunk["rbdlab_acetonized_deactivation"] = True
                                            deactivation_recorded = True


                            #-----------------------------------------------------------------
                            # KINEMATIC:
                            #-----------------------------------------------------------------
                            if self.mode == 'NORMAL':
                                
                                if 'KINEMATIC' in current_type and activator_now[RBDLabNaming.ACT_RECORD_TYPE] == 'KINEMATIC':
                                    
                                    if hasattr(chunk.rigid_body, "kinematic"):

                                        # print(scn.rigidbody_world.substeps_per_frame)

                                        if chunk.rigid_body.kinematic:
                                            # si ya fue acetonized en su categoria pasamos de el:
                                            for cp in custom_properties:
                                                cpl = cp.lower()
                                                if cpl == "rbdlab_acetonized_kineatic":
                                                    to_ignore = True

                                            if not to_ignore:
                                                # print("Animando Kinematic", current_frame, chunk.name)
                                                # print("actuando en kinematic con el helper", activator_now)
                                                chunk.keyframe_insert(
                                                    data_path="rigid_body.kinematic",
                                                    frame=(current_frame - 1)
                                                )
                                                chunk.rigid_body.kinematic = False
                                                chunk.keyframe_insert(
                                                    data_path="rigid_body.kinematic",
                                                    frame=current_frame
                                                )
                                                chunk["rbdlab_acetonized_kineatic"] = True

                                                # les cambio el color:
                                                self.animation_color(chunk=chunk, frame=current_frame, color=red_color)

                                                kinematic_recorded = True

                        #-----------------------------------------------------------------
                        # CONSTRAINTS:
                        #-----------------------------------------------------------------
                        if 'CONSTRAINTS' in current_type and self.mode == 'NORMAL' and activator_now[RBDLabNaming.ACT_RECORD_TYPE] == 'CONSTRAINTS':
                            
                            if RBDLabNaming.CONSTRAINTS in chunk:
                                constraints_processed = []
                                for const_name in chunk[RBDLabNaming.CONSTRAINTS].split():
                                    const_ob = scn_objects.get(const_name)

                                    if not const_ob:
                                        # print("const_name:", const_name, "Not Found!")
                                        continue

                                    if const_ob not in all_computable_constraints:
                                        # print("const_name:", const_name, "Not in computable constraints!")
                                        continue

                                    if const_ob.rigid_body_constraint.enabled:
                                        if const_name not in constraints_processed:

                                            # guardo su estado para luego en el clean restaurarlo:
                                            const_ob["rbdlab_const_status"] = const_ob.rigid_body_constraint.enabled

                                            for cp in custom_properties:
                                                cpl = cp.lower()
                                                if cpl == "rbdlab_acetonized_constraints":
                                                    to_ignore = True

                                            if not to_ignore:
                                                # print("actuando en constraints con el helper", activator_now)
                                                const_ob.keyframe_insert(
                                                    data_path="rigid_body_constraint.enabled",
                                                    frame=current_frame
                                                )
                                                const_ob.rigid_body_constraint.enabled = False
                                                const_ob.keyframe_insert(
                                                    data_path="rigid_body_constraint.enabled",
                                                    frame=(current_frame + 1)
                                                )
                                                const_ob["rbdlab_acetonized_constraints"] = True
                                                constraints_processed.append(const_name)
                                                constraints_recorded = True
                                                
                                                # coloreamos los chunks del constraint:
                                                self.animation_color(chunk=const_ob.rigid_body_constraint.object1, frame=current_frame, color=red_color)
                                                self.animation_color(chunk=const_ob.rigid_body_constraint.object2, frame=current_frame, color=red_color)

                        
                        #-----------------------------------------------------------------
                        # DYNAMICS:
                        #-----------------------------------------------------------------
                        if 'DYNAMIC' in current_type and self.mode == 'NORMAL' and activator_now[RBDLabNaming.ACT_RECORD_TYPE] == 'DYNAMIC':

                            dynamic_dpath = "rigid_body.enabled"
                            frames_between_actions = active_item.frames_between_actions
                            current_type_color = [active_item.r_c, active_item.g_c, active_item.b_c, active_item.a_c]
                            # print("afectando:", chunk.name)

                            # in_range = frame-1 <= frame <= frames_between_actions 
                            # if not in_range:

                            def set_rigidbody_enabled(chunk, enabled, frame):
                                # if chunk.rigid_body.enabled != enabled:
                                chunk.rigid_body.enabled = enabled
                                chunk.keyframe_insert(data_path=dynamic_dpath, frame=frame)
                                chunk["rbdlab_acetonized_dynamic"] = True

                            if active_item.actions in ['ON', 'ON_OFF']:
                                set_rigidbody_enabled(chunk, False, current_frame-1)
                                set_rigidbody_enabled(chunk, True, current_frame)
                                self.animation_color(chunk=chunk, frame=current_frame, color=red_color)

                            if active_item.actions in ['OFF', 'OFF_ON']:
                                set_rigidbody_enabled(chunk, True, current_frame-1)
                                set_rigidbody_enabled(chunk, False, current_frame)
                                self.animation_color(chunk=chunk, frame=current_frame, color=red_color)
                            
                            if active_item.actions in ['ON_OFF', 'OFF_ON']:
                                next_frame = current_frame + frames_between_actions
                                set_rigidbody_enabled(chunk, not chunk.rigid_body.enabled, next_frame)
                                
                                # Cambiar el color:
                                frame_color = [
                                                {"frame": current_frame-1,  "color": current_type_color},    
                                                {"frame": current_frame,    "color": red_color},
                                                {"frame": next_frame,       "color": current_type_color},  
                                            ]
                                for fc in frame_color:
                                    frame = fc["frame"]
                                    color = fc["color"]
                                    chunk.color = color
                                    if not check_if_have_previous_kf(chunk, frame, "color"):
                                        chunk.keyframe_insert(data_path="color", frame=frame)
                            
                            if "rbdlab_acetonized_dynamic" in chunk:
                                dynamic_recorded = True
                        
                        #-----------------------------------------------------------------
                    
                    wm.progress_update(frame)

                    # los eliminamos:
                    if previous_chunk_bvh:
                        del previous_chunk_bvh
                    if activator_now_bvh:
                        del activator_now_bvh

                    if skip_substeps:
                        break

        # si se hizo recording de alguno de los modos:
        if any([
                    deactivation_recorded, 
                    kinematic_recorded, 
                    constraints_recorded,
                    dynamic_recorded
                ]) or any([
                            loc_with_keyframes, 
                            rot_with_keyframes, 
                            explode_with_keyframes
                            ]) and self.mode == 'NORMAL':
            
            if "activators_recorded" not in tcoll:
                tcoll["activators_recorded"] = True

        if self.mode == 'FORCE_PREVIEW':
            if "activators_force_preview_recorded" not in tcoll:
                tcoll["activators_force_preview_recorded"] = True

        wm.progress_end()
        return objects
    

    def obtener_primer_y_ultimo_frame_de_keyframes(self, rbdlab, pc, ob, current_type, rbdlab_activators) -> List[float]:
        
        # chuleta: pc = point cache

        # sin no estamos usando auto range, usamos todos los frames:
        if rbdlab_activators.automatic_range_with_keyframes == False:
            return [pc.frame_start, rbdlab_activators.total_frames]
        
        else:

            def obtener_keyframes_del_objeto(ob):
                keyframes = []
                
                if not ob:
                    print("[obtener_keyframes_del_objeto], no input ob get!")
                    return
                
                if not hasattr(ob, "animation_data"):
                    self.report({'ERROR'}, "Activator " + ob.name + " has no animation information!")
                    return

                if not hasattr(ob.animation_data, "action"):
                    self.report({'ERROR'}, "Activator " + ob.name + " has no animation information!")
                    return
                
                if hasattr(ob.animation_data.action, "fcurves"):
                    for fc in ob.animation_data.action.fcurves:
                        for key in fc.keyframe_points:
                            keyframes.append(key.co.x)
                
                return keyframes

            # Obtener todos los keyframes del objeto actual o del objeto padre si no los tiene
            all_keyframes = obtener_keyframes_del_objeto(ob.parent) if ob.parent else obtener_keyframes_del_objeto(ob)
            # all_keyframes = obtener_keyframes_del_objeto(ob) or obtener_keyframes_del_objeto(ob.parent)

            # Si no hay keyframes y se usa rango automático, retornar -1 indicando que no hay keyframes
            if not all_keyframes:
                return -1 
            
            else:
                # Si hay keyframes, devolver el primer y último frame de la lista de keyframes
                # si usamos kinematic hay q computar hasta el final de la sim (porque no sabemos cuando dejan de moverse los rbd), sino usamos el automatic por keyframes:
                # return [min(all_keyframes), pc.frame_end] if 'KINEMATIC' in current_type else [min(all_keyframes), max(all_keyframes)]
                return [min(all_keyframes), max(all_keyframes)]


    def execute(self, context):
        ''' rbdlab.act_record '''

        start = datetime.now()

        scn, rbdlab, tcoll_list, ac_layers_list = get_common_vars(context, get_scn=True, get_rbdlab=True, get_tcoll_list=True, get_ac_layers_list=True)
        
        prev_substeps_per_frame = None

        tcoll = tcoll_list.active
        if not tcoll:
            self.report({'ERROR'}, "Not valid Targe Collection!")
            return {'CANCELLED'}

        if ac_layers_list.is_void:
            self.report({'ERROR'}, "First you must create some activator!")
            return {'CANCELLED'}        
        
        active_item = ac_layers_list.active
        if not active_item:
            self.report({'ERROR'}, "Not valid Activator!")
            return {'CANCELLED'}
        
        # los tipos del active item del listado:
        current_type = ac_layers_list.get_all_computable_types
        # current_type = list(set([t.type for t in active_item.types]))
        
        computes = next((item for item in ac_layers_list.list if item.compute), None)
        if not computes:
            self.report({'ERROR'}, "No activator was marked for processing!")
            return {'CANCELLED'}

        rbdw = scn.rigidbody_world

        if not rbdw:
            self.report({'WARNING'}, "No rigidbodies in the scene, first add rigidbodies!")
            return {'CANCELLED'}

        pc = rbdw.point_cache

        if scn.frame_current != scn.frame_start:
            context.scene.frame_set(context.scene.frame_start)
            # scn.frame_current = scn.frame_start

        rbdlab_activators = rbdlab.activators

        if 'KINEMATIC' in current_type and rbdlab.ui.activators_force_loc_mode == 'EXPLODE':
            rbdlab_activators.force_explode_amount = 0

        if not scn.rigidbody_world:
            self.report({'WARNING'}, "No rigidbodies detected at the scene!")
            return {'CANCELLED'}

        # self.report({'INFO'}, "OK, now it will start recording, please don't touch anything in this process!")
        all_min = []

        ACTIVATORS_OBJECTS = ac_layers_list.get_all_computable_activators
        
        # Ahora los activators solo trabajan con los activators de su Layer list activo:
        # ACTIVATORS_OBJECTS = ac_layers_list.get_all_computable_activators_from_active

        # ACTIVATORS_OBJECTS = [obj for obj in context.view_layer.objects if RBDLabNaming.ACTIVATORS_OBJECTS in obj]
        
        # print("ACTIVATORS_OBJECTS", ACTIVATORS_OBJECTS)

        if not ACTIVATORS_OBJECTS:
            self.report({'WARNING'}, "No activators objects detected!")
            return {'CANCELLED'}

        # Apply transforms Scale:
        # [apply_transfroms_low_level(ob, use_location=False, use_rotation=False, use_scale=True) for ob in ACTIVATORS_OBJECTS]

        # print('ACTIVATORS_OBJECTS', ACTIVATORS_OBJECTS)

        objects = self.get_valid_chunks(ac_layers_list)

        if not objects:
            self.report({'WARNING'}, "No chunks included!")
            deselect_all_objects(context)
            return {'CANCELLED'}
        
        if len(objects) <= 0:
            self.report({'WARNING'}, "No chunks included!")
            deselect_all_objects(context)
            return {'CANCELLED'}
        
        #------------------------------------------------------------------------------------------------------------------------------------------------------------
        # Guardamos las transformaciones originales y el color, para que al hacer el remove record, si no estan igual, deje a los chunks el el sitio correspondiente:
        #------------------------------------------------------------------------------------------------------------------------------------------------------------
        for ob in objects:
            ob[RBDLabNaming.ORG_DATA] = {"location": ob.location, "rotation_euler": ob.rotation_euler, "scale": ob.scale, "dimensions": ob.dimensions, "color": ob.color}
        #------------------------------------------------------------------------------------------------------------------------------------------------------------

        min_max = None
        for activator_ob in ACTIVATORS_OBJECTS:
            
            min_max = self.obtener_primer_y_ultimo_frame_de_keyframes(rbdlab, pc, activator_ob, current_type, rbdlab_activators)
            # print(min_max)

            if min_max == -1:
                
                self.report({'WARNING'}, "No keyframes detected in Activators Objects, neither in their parents!!")
                deselect_all_objects(context)
                return {'CANCELLED'}
            
            else:
                activator_ob["min_max_keyframnes"] = min_max

            all_min.append(activator_ob["min_max_keyframnes"][0])

            # print("Acetone ob:", activator_ob.name, "min_max", min_max)
        
        # # solo si hay keyframes en los activators, desactivamos el rbdworld:
        # # para que puedan funcionar de forma pasiva:
        # if not rbdlab_activators.passive_mode:
        #
        #     # si solo se usan constraints podemos apagar el rbw:
        #     if current_type == {'CONSTRAINTS'}:
        #         scn.rigidbody_world.enabled = False
        
        # Si se quiere usar un rango manual:
        if rbdlab_activators.automatic_range_with_keyframes:
            # en automatico se apaga el rbdw
            rbdw.enabled = False

        if not rbdlab_activators.automatic_range_with_keyframes:
            # guardo el substeps per frame del usuario:
            prev_substeps_per_frame = rbdw.substeps_per_frame
            # y seteamos los nuevos substeps del usuario:
            if prev_substeps_per_frame != rbdlab_activators.rbdw_substeps_per_frame:
                rbdw.substeps_per_frame = rbdlab_activators.rbdw_substeps_per_frame

        
        # Carece un poco de sentido desactivar el world usando el rando manual:
        # else:
        #
        #     # Si se quiere usar en ese rango manual el rbdw o no:
        #     if rbdlab_activators.with_rbdw == False:
        #        
        #         # NOTA IMPORTANTE, en el ejemplo de "pelotas emitidas desde particulas contra un muro", a partir de un frame x dejan de ser kinematics para ser simulación, si
        #         # ese ultimo frame están demasiado lejos del muro, y tenemos desactivado el world, es muy posible que 
        #         # nunca tengas colisión, porque no computará la simulación de donde estuviera la esfera despues de la animación, por lo tanto no se computará
        #
        #         scn.rigidbody_world.enabled = False


        # para agregar el auto kinematic es necesario estar en el start:
        if scn.frame_current != scn.frame_start:
            scn.frame_current = scn.frame_start

        # obtenemos todos los constraints que son computables para luego comparar:
        all_computable_constraints = rbdlab.constraints.get_all_computable_constraints

        # en 3 pasadas:
        activators_passe = int(active_item.passes)
        for i in range(activators_passe):

            dict_substeps = {
                1: {0: 1},
                2: {0: 1, 1: 6},
                3: {0: 1, 1: 5, 2: 10}
            }
            user_substeps = dict_substeps[activators_passe][i]

            # print("pasadas", activators_passe, "substeps", user_substeps)

            tcoll["kinematic_keyframes_text"] = ""

            # esto no se debe hacer aqui:
            # set chunks origin to geometry:
            # deselect_all_objects(context)
            # for obj in objects:
            #     select_object(context, obj)

            # if context.selected_objects:
            #     set_active_object(context, context.selected_objects[0])
            #     bpy.ops.object.origin_set(type='ORIGIN_CENTER_OF_VOLUME', center='MEDIAN')

            # deselect_all_objects(context)
            # LO GORDO en intersection_check:
            objects = self.intersection_check(
                                                context, 
                                                tcoll,
                                                active_item, 
                                                current_type, 
                                                min(all_min), 
                                                user_substeps, 
                                                ACTIVATORS_OBJECTS, 
                                                objects,
                                                all_computable_constraints
                                            )
            if not objects:
                continue

        # # solo si hay keyframes en los activators desactivamos el rbdworld:
        # # para que puedan funcionar de forma pasiva
        # if not rbdlab_activators.passive_mode:
        #     # si solo se usan constraints podemos apagar el rbw:
        #     if current_type == {'CONSTRAINTS'}:
        #         scn.rigidbody_world.enabled = True


        # Restauramos el rbdw:
        # si estuviera apagado lo volvemos a dejar encendido:
        if rbdw.enabled == False:
            rbdw.enabled = True

        # Restauramos el substeps per frame:
        if prev_substeps_per_frame:
            # y seteamos los nuevos substeps del usuario:
            if rbdw.substeps_per_frame != prev_substeps_per_frame:
                rbdw.substeps_per_frame = prev_substeps_per_frame
        
        # scn.frame_set(scn.frame_start)
        # scn.frame_current = scn.frame_start
        if scn.frame_current != scn.frame_start:
            scn.frame_current = scn.frame_start

        if RBDLabNaming.ACTIVATORS_EXPLODE_DONE in tcoll:
            rbdlab_activators.explode_centroid_visibility = False

        if self.mode == 'NORMAL':
            rbdlab_activators.activators_show_explode_amount_feedback = ""

        if "activators_recorded" in tcoll:
            self.report({'INFO'}, "Activators Finished in " + str(datetime.now() - start) + " seconds!")

        # Seteamos como que fuero grabados a todos los computables:
        ac_layers_list.set_all_computable_recorded(True)

        deselect_all_objects(context)
        return {'FINISHED'}
