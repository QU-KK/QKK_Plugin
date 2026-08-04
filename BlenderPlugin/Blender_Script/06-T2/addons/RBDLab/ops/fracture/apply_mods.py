import bpy
import bmesh
from datetime import datetime

from bpy.types import Operator
from ...Global.utilities import finding_home_for_orphaned_chunks
from ...Global.functions import (
    set_active_collection_to_master_coll,
    hide_collection_in_viewport,
    unhide_collection_in_viewport,
    collapse_collections,
    remove_collection_if_is_empty
)
from ...Global.basics import enter_edit_mode, set_active_object, enter_object_mode, rm_ob
from ...addon.paths import RBDLabPreferences
from ...addon.naming import RBDLabNaming
from ..constraints.detect import calcute_chunks_neighbors
from ...Global.get_common_vars import get_common_vars


# boolean_mod_name = "Boolean"
boolean_mod_name = RBDLabNaming.BOOLEAN_MOD
boolean_mod_name_up = RBDLabNaming.BOOLEAN_MOD_UP


class APPLY_OT_mods(Operator):
    bl_idname = "rbdlab.apply_mods"
    bl_label = "RBDLab Apply All Modifiers"
    bl_description = "Apply Fracture"
    bl_options = {'REGISTER', 'UNDO'}

    coll_low_name = None
    coll_low_objects = []
    coll_high_name = None
    coll_high_objects = []
    coll_high_in_collectons = False

    @classmethod
    def poll(cls, context):
        return context.scene.rbdlab.filtered_target_collection is not None and context.scene.rbdlab.filtered_target_collection.name

    @classmethod
    def description(cls, context, _properties):
        if not context.scene.rbdlab.filtered_target_collection:
            return "You need to select a target collection"
        return cls.bl_description

    def get_low_collection_name(self, coll_name) -> None:
        # start = datetime.now()
        if RBDLabNaming.SUFIX_LOW not in coll_name:
            self.coll_low_name = coll_name + RBDLabNaming.SUFIX_LOW
        else:
            self.coll_low_name = coll_name

        if self.coll_low_name not in bpy.data.collections:
            self.coll_low_name = coll_name
        # print("get_low_collection_name End: " + str(datetime.now() - start))

    def get_low_objects(self):
        start = datetime.now()
        print("---------------------------------------------")
        self.coll_low_objects = [ob for ob in bpy.data.collections[self.coll_low_name].objects if ob.type == 'MESH' and ob.visible_get()]
        print("get_low_objects End: " + str(datetime.now() - start))

    def get_high_collection_name(self, coll_name) -> None:
        start = datetime.now()
        if RBDLabNaming.SUFIX_LOW in coll_name:
            self.coll_high_name = coll_name.replace(RBDLabNaming.SUFIX_LOW, RBDLabNaming.SUFIX_HIGH)
        else:
            self.coll_high_name = coll_name + RBDLabNaming.SUFIX_HIGH
        print("get_high_collection_name End: " + str(datetime.now() - start))

    def check_high_coll_in_collections(self):
        start = datetime.now()
        if self.coll_high_name in bpy.data.collections:
            self.coll_high_in_collectons = True
        print("check_high_coll_in_collections End: " + str(datetime.now() - start))

    def get_high_objects(self):
        start = datetime.now()
        if self.coll_high_in_collectons:
            self.coll_high_objects = [
                ob for ob in bpy.data.collections[self.coll_high_name].objects
                if ob.type == 'MESH' and ob.visible_get()]
        print("get_high_objects End: " + str(datetime.now() - start))

    def asign_inner_material_for_remesheds(self, context, rbdlab):
        start = datetime.now()
        '''
            asignamos inner material a las caras internas de high chunks remesheds
            usamos un truco poniendole shade smooth para poder luego hacer select similar
        '''

        if self.coll_high_in_collectons:
            # deselect_all_objects(context)
            bpy.ops.object.select_all(action='DESELECT')

            bpy.ops.object.mode_set(mode='OBJECT', toggle=False)

            active_object = self.coll_high_objects[0]
            context.view_layer.objects.active = active_object

            for obj in self.coll_high_objects:
                obj.select_set(True)

            # if context.selected_objects:
                active_object = obj

                # set_active_object(context, active_object)
                context.view_layer.objects.active = active_object

                bpy.ops.object.mode_set(mode='EDIT', toggle=False)

                # firs material for all:
                # bpy.ops.mesh.select_all(action='SELECT')
                # active_object.active_material_index = 0
                # bpy.ops.object.material_slot_assign()

                bpy.ops.mesh.select_all(action='DESELECT')
                me = active_object.data
                bm = bmesh.from_edit_mesh(me)

                if "rbdlab_use_smooth_shade" not in obj:
                    continue

                for face in bm.faces:
                    f_selected = False
                    if obj["rbdlab_use_smooth_shade"]:
                        # with smooth shade
                        if len(face.verts) > 3 and not face.smooth:
                            face.select = True
                            f_selected = True
                            break
                    else:
                        # without smooth shade
                        if len(face.verts) == 3 and face.smooth:
                            face.select = True
                            f_selected = True
                            break

                if not f_selected:
                    continue

                bmesh.update_edit_mesh(me, loop_triangles=False, destructive=False)
                context.tool_settings.mesh_select_mode = (False, False, True)
    
                faces_selected = next((True for face in bm.faces if face.select), False)
                if faces_selected:
                    # en blender 4.1.1 ahora se llama 'FACE_SMOOTH' en lugar de 'SMOOTH': 
                    bpy.ops.mesh.select_similar(type='FACE_SMOOTH', threshold=0.01)

                i = 0
                for mat in active_object.material_slots:
                    if mat.name.endswith(RBDLabNaming.SUFIX_INNER_MAT):
                        active_object.active_material_index = i
                    i += 1

                bpy.ops.object.material_slot_assign()
                bpy.ops.uv.cube_project(correct_aspect=True, clip_to_bounds=True, scale_to_bounds=True)
                bpy.ops.object.mode_set(mode='OBJECT', toggle=False)

                # asignamos los vertex group:
                # for obj in self.coll_high_objects:
                # set_active_object(context, obj)

                group = None
                if "Interior" not in obj.vertex_groups:
                    group = obj.vertex_groups.new(name="Interior")

                if not group:
                    group = obj.vertex_groups["Interior"]

                vertex_indices = [v.index for v in obj.data.vertices if v.select]
                wanted_weight = 1
                group.add(vertex_indices, wanted_weight, 'REPLACE')

                bpy.ops.object.mode_set(mode='EDIT', toggle=False)
                bpy.ops.mesh.select_all(action='DESELECT')
                bpy.ops.object.mode_set(mode='OBJECT', toggle=False)

                bpy.ops.object.select_all(action='DESELECT')

        bpy.ops.object.mode_set(mode='OBJECT', toggle=False)
        print("asign_inner_material_for_remesheds End: " + str(datetime.now() - start))

    @staticmethod
    def set_origin_to_center(context, objects: list[object], type: str) -> None:
        start = datetime.now()

        # print("Center Origins to: " + collection)
        bpy.ops.object.select_all(action='DESELECT')
        [ob.select_set(True) for ob in objects]
        # context.view_layer.objects.active = objects[0]
        context.view_layer.objects.active = objects[0]

        # Center to Geometry
        # bpy.ops.object.origin_set(type='ORIGIN_GEOMETRY', center='MEDIAN')
        
        # Center of Mass (Surface)
        bpy.ops.object.origin_set(type='ORIGIN_CENTER_OF_MASS', center='MEDIAN')
        
        # Center of Mass (Volume)
        # bpy.ops.object.origin_set(type='ORIGIN_CENTER_OF_VOLUME', center='MEDIAN')


        print("set_origin_to_center " + type + " End: " + str(datetime.now() - start))

    def apply_modifiers_to(self, context, objects: list[object], type: str) -> None:
        start = datetime.now()
        print("---------------------------------------------")
        # deselect_all_objects(context)
        bpy.ops.object.select_all(action='DESELECT')

        [(ob.select_set(True), property(ob, "rbdlab_modifiers_applied", True)) for ob in objects]

        if context.selected_objects:
            # set_active_object(context, objects[0])
            context.view_layer.objects.active = objects[0]
            bpy.ops.object.convert(target='MESH')

        print("apply_modifiers_to " + type + " End: " + str(datetime.now() - start))

    def apply_rules_visibility_collections(self, context, coll_low) -> None:
        start = datetime.now()
        if "use_highs" in coll_low:
            if not coll_low["used_single_output"]:
                # print('1')
                hide_collection_in_viewport(context, self.coll_high_name)
            else:
                # print('2')
                hide_collection_in_viewport(context, self.coll_high_name)
        else:
            # print('3')
            unhide_collection_in_viewport(context, self.coll_low_name)
        print("apply_rules_visibility_collections End: " + str(datetime.now() - start))

    def remove_chunks_with_less_than_three_vertices(self, context, objects: list[object], in_type: str = ""):
        start = datetime.now()

        # depsgraph = context.evaluated_depsgraph_get()
        if in_type == "Low Objects":
            local_objects = self.coll_low_objects
            # [(self.coll_low_objects.remove(ob), rm_ob(ob)) for ob in objects if len(ob.data.vertices) <= 3]
        elif in_type == "High Objects":
            local_objects = self.coll_high_objects
            # [(self.coll_high_objects.remove(ob), rm_ob(ob)) for ob in objects if len(ob.data.vertices) <= 3]

        total_rmoved = 0
        for ob in objects:
            # ob_eval = ob.evaluated_get(depsgraph)
            # if len(ob_eval.data.vertices) <= 3:
            if len(ob.data.vertices) <= 3:
                local_objects.remove(ob)
                bpy.data.objects.remove(ob)
                total_rmoved += 1

        print(
            "remove_chunks_with_less_than_three_vertices " + in_type + " Total removed: " + str(total_rmoved) +
            " Time: " + str(datetime.now() - start))

    def remove_ob_without_faces(self, objects: list[object]) -> None:
        start = datetime.now()
        [(objects.remove(ob), rm_ob(ob)) for ob in objects if len(ob.data.polygons) == 0]

        print("remove_ob_without_faces End: " + str(datetime.now() - start))

        return objects

    def remove_loose_verts(self, context, objects: list[object], in_type: str = ""):
        start = datetime.now()

        bpy.ops.object.select_all(action='DESELECT')
        [ob.select_set(True) for ob in objects]

        if context.selected_objects:
            context.view_layer.objects.active = objects[0]
            bpy.ops.object.mode_set(mode='EDIT', toggle=False)
            bpy.ops.mesh.select_all(action='DESELECT')
            bpy.ops.mesh.select_mode(type='VERT')
            bpy.ops.mesh.select_loose()
            bpy.ops.mesh.delete(type='VERT')
            bpy.ops.object.mode_set(mode='OBJECT', toggle=False)

        print("remove_loose_verts " + in_type + " End: " + str(datetime.now() - start))

    def separate_loose_parts(self, context, objects: list[object]) -> None:

        previous_mode = objects[0].mode

        bpy.ops.object.select_all(action='DESELECT')

        for ob in objects:
            ob.select_set(True)

        set_active_object(context, objects[0])
        enter_edit_mode(context)

        bpy.ops.mesh.select_all(action='SELECT')
        bpy.ops.mesh.separate(type='LOOSE')

        if previous_mode == 'OBJECT':
            enter_object_mode(context)

        if previous_mode == 'EDIT':
            enter_edit_mode(context)

        # Al hacer separate se crean objetos nuevos que no estan en self.coll_low_objects ni self.coll_high_objects
        # por eso los agregamos pero primeo una limpieza y luego los incluyo
        objects = self.remove_ob_without_faces(context.selected_objects)

        for ob in context.selected_objects:
            if ob not in objects:
                objects.append(ob)

        return objects

    def execute(self, context):
        # print("\n\n# REFACTORED APPLY MODS \n###############################")
        start0 = datetime.now()

        rbdlab, ui, tcoll_list = get_common_vars(context, get_rbdlab=True, get_ui=True, get_tcoll_list=True)
        tcoll = tcoll_list.active

        target_collections = tcoll[RBDLabNaming.LAST_CREATED_COLLS]
        if target_collections:

            for target_coll in target_collections:
                coll_name = target_coll.name

                context.space_data.overlay.show_relationship_lines = True

                # init
                self.get_low_collection_name(coll_name)
                unhide_collection_in_viewport(context, self.coll_low_name)
                self.get_low_objects()

                if not self.coll_low_objects:
                    print("[FRACTURE] Apply Mods: No chunks were found!")
                    return {'CANCELLED'}

                self.get_high_collection_name(coll_name)
                unhide_collection_in_viewport(context, self.coll_high_name)
                self.check_high_coll_in_collections()
                self.get_high_objects()


                # Aplico los modifiers de los low:
                # POR RENDIMIENTO: desactivamos el subsurf de los high para aplicar los low mas rapido:
                if self.coll_high_in_collectons:
                    for ob in self.coll_high_objects:

                        # RBDLab_Remesh:
                        ob["rbdlab_remesh_viewport_status"] = ob.modifiers[RBDLabNaming.REMESH].show_viewport
                        ob.modifiers[RBDLabNaming.REMESH].show_viewport = False

                        # RBDLab_Subsurf:
                        ob["rbdlab_subsurf_viewport_status"] = ob.modifiers[RBDLabNaming.SUBSURF_MOD].show_viewport
                        ob.modifiers[RBDLabNaming.SUBSURF_MOD].show_viewport = False

                self.apply_modifiers_to(context, self.coll_low_objects, 'LOWS')

                # hago un separate
                if self.coll_low_objects:
                    self.coll_low_objects = self.separate_loose_parts(context, self.coll_low_objects)

                # limpieza de vertices flotantes pertenecientes a un chunk:
                self.remove_loose_verts(context, self.coll_low_objects, in_type="Low Objects")

                # limpieza de chunks con menos o igual a 3 vertices:
                self.remove_chunks_with_less_than_three_vertices(context, self.coll_low_objects, in_type="Low Objects")

                self.set_origin_to_center(context, self.coll_low_objects, 'LOWS')


                coll_low = bpy.data.collections.get(self.coll_low_name)

                if self.coll_high_in_collectons:

                    # POR RENDIMIENTO: habiamos apagado los subsurfs pero una vez hechos los low los vuevlo a encender:
                    for ob in self.coll_high_objects:

                        # fast parent:
                        if RBDLabNaming.STORED_LOW_CHUNK_RELATION in ob:
                            chunk_low = context.view_layer.objects.get(ob[RBDLabNaming.STORED_LOW_CHUNK_RELATION])
                            if chunk_low:
                                ob.parent = chunk_low
                                ob.matrix_parent_inverse = chunk_low.matrix_world.inverted()
                                del ob[RBDLabNaming.STORED_LOW_CHUNK_RELATION]

                        # RBDLab_Remesh:
                        if "rbdlab_remesh_viewport_status" in ob:
                            ob.modifiers[RBDLabNaming.REMESH].show_viewport = ob["rbdlab_remesh_viewport_status"]
                            del ob["rbdlab_remesh_viewport_status"]

                        # RBDLab_Subsurf:
                        if "rbdlab_subsurf_viewport_status" in ob:
                            ob.modifiers[RBDLabNaming.SUBSURF_MOD].show_viewport = ob["rbdlab_subsurf_viewport_status"]
                            del ob["rbdlab_subsurf_viewport_status"]

                    # -------------------------------------------------------------

                    if self.coll_high_in_collectons and rbdlab.remesh_or_subdivision == "Remesh" and rbdlab.external_roughness == False:

                        for obj in self.coll_high_objects:
                            use_smooth = obj.data.polygons[0].use_smooth
                            obj["rbdlab_use_smooth_shade"] = use_smooth

                        # en blender 4.1.1 ya no existe obj.data.use_auto_smooth:
                        # [(setattr(obj.data, "use_auto_smooth", True), setattr( obj.modifiers[RBDLabNaming.REMESH], "use_smooth_shade", not obj["rbdlab_use_smooth_shade"])) for obj in self.coll_high_objects if "rbdlab_use_smooth_shade" in obj]
                        [(bpy.ops.object.shade_smooth_by_angle(angle=int(rbdlab.auto_smooth)), setattr( obj.modifiers[RBDLabNaming.REMESH], "use_smooth_shade", not obj["rbdlab_use_smooth_shade"])) for obj in self.coll_high_objects if "rbdlab_use_smooth_shade" in obj]
                        
                        # for obj in self.coll_high_objects:
                        #     obj.data.use_auto_smooth = True
                        #     obj.modifiers[RBDLabNaming.REMESH].use_smooth_shade = not rbdlab.use_auto_smooth

                    self.apply_modifiers_to(context, self.coll_high_objects, 'HIGHS')

                    if self.coll_high_in_collectons:
                        self.coll_high_objects = self.separate_loose_parts(context, self.coll_high_objects)

                    if rbdlab.remove_loose_verts:
                        self.remove_loose_verts(context, self.coll_high_objects, in_type="High Objects")

                    self.remove_chunks_with_less_than_three_vertices(
                        context, self.coll_high_objects, in_type="High Objects")

                    self.set_origin_to_center(context, self.coll_high_objects, 'HIGHS')

                    coll_high = bpy.data.collections.get(self.coll_high_name)

                    if coll_low and coll_high:
                        print("---------------------------------------------")
                        finding_home_for_orphaned_chunks(context, coll_low, coll_high)

                    if self.coll_high_in_collectons and rbdlab.remesh_or_subdivision == "Remesh" and rbdlab.external_roughness == False:
                        self.asign_inner_material_for_remesheds(context, rbdlab)

                bpy.ops.object.select_all(action='DESELECT')
                self.apply_rules_visibility_collections(context, coll_low)
                print("---------------------------------------------")

                if ui.compute_neighbors:
                    # computamos los vecinos:
                    calcute_chunks_neighbors(
                                            context, 
                                            self.coll_low_objects, 
                                            search_method='CYTHON', # agrego el metodo automatico
                                            virtual_cube_threshold=0.001 # agrego el thresold por defecto
                                            )
                    # 1 Marco la tcoll para que aparezcan los constraitns, y saber si las particles son solo motion o broken y motion:
                    target_coll[RBDLabNaming.COMPUTED_NEIGHBORS] = 1
                    # 2 Actualizo el listado de target collection, para que actualice los
                    # rbdlab.particles.XTYPE.create.options = {'MOTION'} or {'BROKEN', 'MOTION'}:
                    tcoll_list.list_index_update(context)

                # marcamos todas las collections como que fueron aplicadas las fracturas:
                target_coll["fracture_applied"] = 1

            # end loop per islands -------------------------------------------

            start1 = datetime.now()
            rbdlab.working_in_inner_details = False
            # rbdlab.filtered_target_collection["fracture_applied"] = 1
            ui.show_fracture_details_extras = False
            rbdlab.scatter_working = False
            rbdlab.current_using_cell_fracture = False

            if self.coll_high_in_collectons:
                # refresco:
                if rbdlab.low_or_high_visibility_render == "Low":
                    rbdlab.low_or_high_visibility_render = "High"
                    rbdlab.low_or_high_visibility_render = "Low"
                elif rbdlab.low_or_high_visibility_render == "High":
                    rbdlab.low_or_high_visibility_render = "Low"
                    rbdlab.low_or_high_visibility_render = "High"

            print("Setting up low/high visibility End: " + str(datetime.now() - start1))

            if tcoll:
                if "starting_fracture" in tcoll:
                    del tcoll["starting_fracture"]

            if context.selected_objects:
                # deselect_all_objects(context)
                bpy.ops.object.select_all(action='DESELECT')

            addon_preferences = RBDLabPreferences.get_prefs(context)
            rbdlab_cf_fast_exact_prefs = addon_preferences.rbdlab_cf_fast_exact_prefs
            rbdlab.rbdlab_cf_fast_exact = rbdlab_cf_fast_exact_prefs

            # volvemos a scatter:
            ui.fracture_switch_subsections = 'SCATTER'

            set_active_collection_to_master_coll(context)

            # tras fracturar dejo apagado el boton de kinematics (pudiera estar encendido) y tras fracturar de nuevo lo reseteo:
            rbdlab.physics.rigidbodies.kinematic = False

            # eliminamos nuestros annotations si hubiera:
            if "Annotations" in bpy.data.grease_pencils and not rbdlab.in_annotation_mode:
                layers = bpy.data.grease_pencils["Annotations"].layers
                annotation_layer = layers.get(RBDLabNaming.ANNOTATION_LAYER) 
                if annotation_layer:
                    my_index = layers.find(RBDLabNaming.ANNOTATION_LAYER)
                    if my_index != -1:
                        layers.active_index = my_index
                        print(layers, my_index, annotation_layer)
                        layers.remove(annotation_layer)
                    # bpy.ops.gpencil.layer_annotation_remove()

            # cierro/collapso las collections
            collapse_collections(context, 2)

            # Si se quedó la collection por default de blender Collection vacia, la borramos:
            remove_collection_if_is_empty(context, "Collection")

            # bpy.ops.rbdlab.rm_obs_with_less_than_3_verts()
            print("---------------------------------------------")
            print("Apply mods End: " + str(datetime.now() - start0))

            # rbdlab.low_or_high_visibility_viewport = "High"
            # context.space_data.shading.type = 'MATERIAL'
            return {'FINISHED'}
