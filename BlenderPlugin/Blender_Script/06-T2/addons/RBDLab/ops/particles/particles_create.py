import bpy
import uuid
from datetime import datetime
from ...Global.functions import (
    append_collection,
    # calculate_motions,
    deselect_all_objects,
    set_active_collection_to_master_coll,
    select_object,
    set_active_object,
    # enter_edit_mode,
    enter_object_mode,
    # get_array_data_from_obj,
    select_inner_faces_by_attribute,
    remove_all_keyframes_in_action
)
from ...Global.get_common_vars import get_common_vars
# from ..constraints.detect import get_broken_chunks_at_frame, get_broken_chunks_at_frame_inv
from ...addon.paths import RBDLabPreferences
from ...addon.naming import RBDLabNaming
from .update_rbdlab_object import update_broken_neighbours_and_motions
from ...props.particles import RBDLab_PG_particles_add_props as PG_ParticlesCreate
from ...props.rbdlab_object import Motion  # , Velocity

from typing import List
from bpy.types import Operator, Menu, Object, ParticleSettings, Collection, Context
from bpy.props import EnumProperty

from bl_operators.presets import AddPresetBase
import os


class PARTICLE_MT_Presets(Menu):
    bl_label = "My Presets"
    preset_subdir = os.path.join("RBDLab", "Particles")
    preset_operator = "script.execute_preset"
    draw = Menu.draw_preset


class PARTICLE_OT_Add_Preset(AddPresetBase, Operator):
    bl_idname = "rbdlab.particles_add_preset"
    bl_label = "Add particles preset"
    preset_menu = "PARTICLE_MT_Presets"
    # Common variable used for all preset values:
    preset_defines = ["rbdlab = bpy.context.scene.rbdlab"]
    # Properties to store in the preset:
    preset_values = [
        "rbdlab.particles.debris.display_method",
        "rbdlab.particles.debris.display_size",
        "rbdlab.particles.debris.display_color",
        "rbdlab.particles.debris.show_instancer_for_viewport",
        "rbdlab.particles.debris.count",
        "rbdlab.particles.debris.offset",
        "rbdlab.particles.debris.enable_end_trails",
        "rbdlab.particles.debris.end_trails",
        "rbdlab.particles.debris.lifetime",
        "rbdlab.particles.debris.lifetime_random",
        "rbdlab.particles.debris.particle_size",
        "rbdlab.particles.debris.size_random",
        "rbdlab.particles.debris.use_dead",
        "rbdlab.particles.debris.show_instancer_for_render",
        "rbdlab.particles.debris.normal",
        "rbdlab.particles.debris.direction",
        "rbdlab.particles.debris.object_velocity",
        "rbdlab.particles.debris.velocity_randomize",
        "rbdlab.particles.debris.use_rotations",
        "rbdlab.particles.debris.use_rotations",
        "rbdlab.particles.debris.rotation_mode",
        "rbdlab.particles.debris.rotation_factor_random",
        "rbdlab.particles.debris.phase_factor",
        "rbdlab.particles.debris.phase_factor_random",
        "rbdlab.particles.debris.use_dynamic_rotation",
        "rbdlab.particles.debris.debris_coll",
        "rbdlab.particles.debris.all",
        "rbdlab.particles.debris.gravity",
        "rbdlab.particles.debris.force",
        "rbdlab.particles.debris.vortex",
        "rbdlab.particles.debris.magnetic",
        "rbdlab.particles.debris.harmonic",
        "rbdlab.particles.debris.charge",
        "rbdlab.particles.debris.lennardjones",
        "rbdlab.particles.debris.wind",
        "rbdlab.particles.debris.curve_guide",
        "rbdlab.particles.debris.texture",
        "rbdlab.particles.debris.smokeflow",
        "rbdlab.particles.debris.turbulence",
        "rbdlab.particles.debris.drag",
        "rbdlab.particles.debris.boid",
        "rbdlab.particles.debris.basic_subdivision_type",
        "rbdlab.particles.debris.basic_subdivision_level",
        "rbdlab.particles.debris.basic_decimate_collapse",
        "rbdlab.particles.debris.basic_disp_strength",
        "rbdlab.particles.debris.basic_clouds_size",
        "rbdlab.particles.debris.basic_clouds_depth",
        "rbdlab.particles.debris.basic_outher_material",
        "rbdlab.particles.debris.basic_inner_material",
    ]
    # Directory to store the presets
    preset_subdir = os.path.join("RBDLab", "Particles")


class RBDLAB_OT_particles_create(Operator):
    bl_idname = "rbdlab.particles_create"
    bl_label = "Create Particles"
    bl_options = {'PRESET'}
    bl_options = {'REGISTER', 'UNDO'}

    type: EnumProperty(name="Particle type",
                       items=(
                           ("debris", "Debris", ""),
                           ("dust", "Dust", ""),
                           ("smoke", "Smoke", "")
                       ),
                       default="debris")

    exist_particles: False
    particles_systems_names = ("particles_debris", "particles_dust", "particles_smoke")
    magic_bias = 0.002  # for fix particles apear in blender collision
    chunk_objects = []
    info_islands = []
    recolection_info = {}

    CHUNK_P_EMITTER_BROKEN_COLOR = []
    CHUNK_P_EMITTER_COLOR = []

    @classmethod
    def poll(cls, context) -> bool:
        return context.scene.rbdlab.filtered_target_collection is not None

    @classmethod
    def description(cls, _context, properties) -> str:
        return "Create %s particles" % properties.type

    @staticmethod
    def check_if_is_ectracted(chunk: object) -> bool:
        return RBDLabNaming.CHUNK_EXTRACTED in chunk

    def check_if_exist_domain(self, context:Context, tcoll:Collection) -> bool:
        
        if tcoll:
            coll_name = tcoll.name
            domain_name = RBDLabNaming.DOMAIN_NAME

            have_fluids = []
            for obj in bpy.data.collections[coll_name].objects:
                if RBDLabNaming.SMOKE_MOD in obj.modifiers:
                    have_fluids.append(obj)

            if domain_name in context.scene.objects or len(have_fluids) > 0:
                domain = bpy.data.objects.get(RBDLabNaming.DOMAIN_NAME)

                if domain:
                    return domain
                else:
                    print("I did not find the domain!")
                    return True
        else:
            return False

    def add_material(self, context, obj: Object, mat_name: str, color4: List):
        if mat_name:
            if mat_name not in bpy.data.materials:
                mat = bpy.data.materials.new(name=mat_name)
                mat.use_nodes = True
            else:
                mat = bpy.data.materials.get(mat_name)

            if mat and mat_name not in obj.data.materials:
                obj.data.materials.append(mat)
                obj.active_material_index = obj.data.materials.find(mat.name)
                principled_node = obj.active_material.node_tree.nodes.get(RBDLabNaming.PRINCIPLED)
                if principled_node is not None:
                    principled_node.inputs["Base Color"].default_value = color4
                else:
                    if context.preferences.view.use_translate_new_dataname:
                        lang = context.preferences.view.language
                        print("[ WARNING ] Principled BSDF is not found because the " + lang.upper() +
                              " language is being used for Data translations. ")
                        obj.active_material.diffuse_color = color4

                return mat

    def particle_materials(self, context, dummy: str, ob: Object, settings: ParticleSettings):

        # print("********", context.active_object.name, ob.name)
        set_active_object(context, ob)

        # print("particle materials para", ob.name)

        # creamos los materiales para poder cambiar de color las particulas en modo point:
        common_name = RBDLabNaming.PARTICLES_MAT
        mat_name = common_name + "_" + dummy

        # Elimino todos los materiales excepto los de particulas:
        for i, mt_slot in enumerate(ob.material_slots):
            if not mt_slot.material.name.startswith(common_name):
                # print("eliminamos", mt_slot.material.name)
                ob.data.materials.pop(index=i-1)

        mat1 = None
        if mat_name not in bpy.data.materials:
            # print("creando material:", mat_name)
            # aun no existe!, se crea y asigna:
            mat1 = self.add_material(context, ob, mat_name, [0.0, 0.3, 1.0, 1.0])
        else:
            # ya existe!, se recupera y se asigna si no lo tuviera:
            # print("recuperando material:", mat_name)
            mat1 = bpy.data.materials.get(mat_name)

        if mat1:
            if mat_name not in ob.data.materials:
                # print("incluyendo material " + mat_name + " a", ob.name)
                ob.data.materials.append(mat1)  # este ya crea el slot

            # print(ob.name, settings.name, ob.data.materials[:])

            ob.active_material_index = len(ob.material_slots)-1
            settings.material_slot = mat_name

    def recolect_inners(self, context, non_extracted_chunks: list[object]) -> list[object]:

        # print("Recolect inners")
        if len(context.selected_objects) == 0:
            # inner_objects = [obj for obj in self.chunk_objects if RBDLabNaming.INNER_CHUNK in obj]
            inner_objects = [ob for ob in non_extracted_chunks if RBDLabNaming.INNER_CHUNK in ob]
        else:
            inner_objects = [ob for ob in context.selected_objects if ob not in non_extracted_chunks]

        # print(context.selected_objects)
        # print("inner_objects", inner_objects)

        self.recolection_info = {}
        deselect_all_objects(context)

        for ob in inner_objects:

            # set_active_object(context, ob)

            # Eliminamos todos las animaciones excepto las de color:
            if ob.animation_data:
                animation_data = ob.animation_data
                if animation_data.action:
                    fcurves = animation_data.action.fcurves
                    if len(fcurves) > 0:
                        for fc in fcurves:
                            if not fc.data_path.startswith("color"):
                                fcurves.remove(fc)

            if hasattr(ob, "rigid_body"):
                if ob.rigid_body is not None:
                    ob.select_set(True)

        if len(context.selected_objects) > 0:
            set_active_object(context, context.selected_objects[0])
            bpy.ops.rigidbody.objects_remove()

        # los depsgraph y los eval los tuve que usar porque
        # cuando se usaban los bake to keyframes no lo hacia bien.

        dg = context.evaluated_depsgraph_get()
        # print("***************** inner_objects", inner_objects)
        for inner_ob in inner_objects:
            # print("inner_ob", inner_ob)
            inner_eval = inner_ob.evaluated_get(dg)

            # print("inner_ob not in chunks", inner_ob not in chunks)
            if inner_ob not in non_extracted_chunks:

                for father_obj in non_extracted_chunks:
                    father_eval = father_obj.evaluated_get(dg)

                    if RBDLabNaming.EXTRACTION_ID in father_eval:

                        if inner_eval[RBDLabNaming.EXTRACTION_ID] == father_eval[RBDLabNaming.EXTRACTION_ID]:

                            if father_obj not in self.recolection_info:
                                self.recolection_info[father_obj] = inner_ob

                            # father_obj[RBDLabNaming.CHUNK_EXTRACTED] = True # esto ya no tiene sentido aqui
                            # inner_ob[RBDLabNaming.INNER_CHUNK] = True

                            # fast parent:
                            father_mw = father_obj.matrix_world.copy()
                            if inner_ob.parent != father_obj:

                                inner_ob["rbdlab_father_obj"] = father_obj.name
                                father_obj[RBDLabNaming.CHUNK_PART_CHILD] = [inner_ob]
                                inner_ob.parent = father_obj
                                inner_ob.matrix_world = father_mw

            else:
                if inner_ob.parent not in self.recolection_info:
                    self.recolection_info[inner_ob.parent] = inner_ob

        # print("*** self.recolection_info", self.recolection_info)
        # print("*** self.info_islands", self.info_islands)

        if self.recolection_info not in self.info_islands:
            self.info_islands.append(self.recolection_info)

        # print("*** self.recolection_info", self.recolection_info)
        # print("*** self.info_islands", self.info_islands)

        if inner_objects:
            return inner_objects

    def extraction(self, context, chunks_to_extract: list[object]) -> None:

        # NOTA: chunks_to_extract son los self.chunk_objects que no fueron extraidos

        # print("Extraction...")
        # print("*** chunks_to_extract", chunks_to_extract)

        # chunks no extraidos pero que sean inners:
        chunks_non_extracted = [chunk for chunk in chunks_to_extract if RBDLabNaming.INNER_CHUNK not in chunk]
        
        bpy.ops.object.select_all(action='DESELECT')

        for chunk in chunks_non_extracted:

            # si no tiene id se la agregamos:
            if RBDLabNaming.EXTRACTION_ID not in chunk:
                chunk[RBDLabNaming.EXTRACTION_ID] = uuid.uuid4().hex

            chunk.select_set(True)

        # si no hay damos por hecho que ya estan extraidos todos:
        if len(context.selected_objects) == 0:
            print("Already extracteds, dont extract more.")
            # pasamos a recolectarlos:
            self.recolect_inners(context, chunks_to_extract)
        else:

            # si hay alguno seleccionado, quiere decir q no estaba extraido y ya se le puso id
            active_object = chunks_non_extracted[0]
            set_active_object(context, active_object)

            selected_any = select_inner_faces_by_attribute(context, chunks_non_extracted, debug=False)

            if not selected_any:
                self.report({'WARNING'}, "Your objects do not have the attribute Inner_faces!")
                return {'CANCELLED'}

            # Duplicate
            bpy.ops.mesh.duplicate()

            # Extract
            bpy.ops.mesh.separate(type='SELECTED')

            enter_object_mode(context)

            # pasamos a recolectarlos:
            self.recolect_inners(context, chunks_non_extracted)

            # inner_to_recolect = [obj for obj in context.selected_objects if obj not in chunks]
            # return inner_objects

    @staticmethod
    def get_particles_ui_defaults(self, rbdlab) -> None:

        dummy = self.type

        # viewport display
        ps_props = rbdlab.get_particles_properties(dummy)
        ps_props.display_method = ps_props.get_default_properties("display_method")
        ps_props.display_size = ps_props.get_default_properties("display_size")
        ps_props.display_color = ps_props.get_default_properties("display_color")

        if dummy != "smoke":
            ps_props.show_instancer_for_viewport = ps_props.get_default_properties("show_instancer_for_viewport")

        # emission
        if dummy == "smoke":
            ps_props.count = 500
        else:
            ps_props.count = ps_props.get_default_properties("count")

        ''' New neighbor system
        ps_props.offset = ps_props.get_default_properties("offset")
        '''
        ps_props.enable_end_trails = ps_props.get_default_properties("enable_end_trails")
        ps_props.end_trails = ps_props.get_default_properties("end_trails")
        ps_props.lifetime = ps_props.get_default_properties("lifetime")
        ps_props.lifetime_random = ps_props.get_default_properties("lifetime_random")

        # render
        if dummy != "smoke":
            ps_props.particle_size = ps_props.get_default_properties("particle_size")
            ps_props.size_random = ps_props.get_default_properties("size_random")
            ps_props.use_dead = ps_props.get_default_properties("use_dead")
            ps_props.show_instancer_for_render = ps_props.get_default_properties("show_instancer_for_render")

        # velocity
        if dummy == "smoke":
            ps_props.normal = 0
        else:
            ps_props.normal = ps_props.get_default_properties("normal")

        ps_props.direction = (0.0, 0.0, 0.0)
        ps_props.object_velocity = ps_props.get_default_properties("object_velocity")
        ps_props.subframes = ps_props.get_default_properties("subframes")
        
        if dummy == "smoke":
            ps_props.velocity_randomize = 1
        else:
            ps_props.velocity_randomize = ps_props.get_default_properties("velocity_randomize")

        # rotation
        if dummy != "smoke":
            ps_props.use_rotations = ps_props.get_default_properties("use_rotations")
            ps_props.rotation_mode = ps_props.get_default_properties("rotation_mode")
            ps_props.rotation_factor_random = ps_props.get_default_properties("rotation_factor_random")
            ps_props.phase_factor = ps_props.get_default_properties("phase_factor")
            ps_props.phase_factor_random = ps_props.get_default_properties("phase_factor_random")
            ps_props.use_dynamic_rotation = ps_props.get_default_properties("use_dynamic_rotation")

        # field weights
        ps_props.all = ps_props.get_default_properties("all")
        ps_props.gravity = ps_props.get_default_properties("gravity")
        ps_props.force = ps_props.get_default_properties("force")
        ps_props.vortex = ps_props.get_default_properties("vortex")
        ps_props.magnetic = ps_props.get_default_properties("magnetic")
        ps_props.harmonic = ps_props.get_default_properties("harmonic")
        ps_props.charge = ps_props.get_default_properties("charge")
        ps_props.lennardjones = ps_props.get_default_properties("lennardjones")
        ps_props.wind = ps_props.get_default_properties("wind")
        ps_props.curve_guide = ps_props.get_default_properties("curve_guide")
        ps_props.texture = ps_props.get_default_properties("texture")
        ps_props.smokeflow = ps_props.get_default_properties("smokeflow")
        ps_props.turbulence = ps_props.get_default_properties("turbulence")
        ps_props.drag = ps_props.get_default_properties("drag")
        ps_props.boid = ps_props.get_default_properties("boid")

        # Basic Debris Settings
        if dummy != "smoke":
            ps_props.basic_subdivision_type = ps_props.get_default_properties("basic_subdivision_type")
            ps_props.basic_subdivision_level = ps_props.get_default_properties("basic_subdivision_level")
            ps_props.basic_decimate_collapse = ps_props.get_default_properties("basic_decimate_collapse")
            ps_props.basic_disp_strength = ps_props.get_default_properties("basic_disp_strength")
            ps_props.basic_clouds_size = ps_props.get_default_properties("basic_clouds_size")
            ps_props.basic_clouds_depth = ps_props.get_default_properties("basic_clouds_depth")

    def setup_particle_system(
                                self, context, 
                                rbdlab, ps_props, 
                                p_create: PG_ParticlesCreate, chunk_ob: Object, inner_ob: Object,
                                use_distance_threshold: bool, motion: Motion = None) -> None:
        
        dummy = self.type

        if p_create.use_motions:
            # print("**** Motions:", len(chunk_ob.rbdlab.motions), "chunk_ob.rbdlab.motions[:]", chunk_ob.rbdlab.motions[:])
            first_motion: Motion = chunk_ob.rbdlab.motions[0]
            motion_start, motion_end = motion.range
            motion_frame_count: int = motion_end - motion_start
            motion_idx: int = motion.index

            if motion_frame_count <= 3:
                # print(f"SKIP PS in Chunk '{chunk_ob.name}'. Not enough movement !")
                return

        if p_create.use_broken:
            # Checkear si la condición del distance_threshold se ha cumplido.
            if use_distance_threshold and not chunk_ob.rbdlab.ok_distance_threshold:
                # print(f"SKIP PS in Chunk '{chunk_ob.name}'. Distance Threshold not fullfilled! (tho probably it is broken and in motion)")
                return

            broken_at_frame = self.broken_chunks.get(chunk_ob, None)
            if not broken_at_frame:
                # print(f"SKIP PS in Chunk '{chunk_ob.name}'. Not broken !")
                return

            if p_create.use_motions:
                # 2 is a safe threshold to avoid very fast particle emission.
                if (broken_at_frame + 2) >= first_motion.range[1]:
                    # print(f"SKIP PS in Chunk '{chunk_ob.name}'. Broken after first motion end...")
                    return
                # elif broken_at_frame < motion_start:
                #     # Broken before motion started...
                #     # print(f"INFO PS in Chunk '{chunk_ob.name}'. Broken before motion start...")
                #     motion_start = motion_start
                elif broken_at_frame > motion_start and broken_at_frame < motion_end:
                    motion_start = broken_at_frame
            else:
                # ONLY BROKEN.
                motion_frame_count = 8
                motion_start, motion_end = broken_at_frame, broken_at_frame + motion_frame_count
                motion_idx = 1

        # print(frame_start, self.magic_bias)
        # if motion_idx == 1 or len(inner_ob.particle_systems) == 0:
        frame_start = motion_start
        if p_create.use_broken and not p_create.use_motions:
            frame_end = motion_end
        else:
            frame_end = motion_end - max(3, int(motion_frame_count * .125))  # To stop emitting before motion stops.

        frame_start += self.magic_bias
        frame_end += self.magic_bias

        ps_name = rbdlab.set_particles(dummy) + "_motion_" + str(motion_idx)

        # print("add particles to:", obj.name)
        if ps_name not in inner_ob.particle_systems:
            # print("PS to be created", ps_name, inner_ob.name)
            inner_ob.modifiers.new(ps_name, type='PARTICLE_SYSTEM')
        else:
            print(f"WARN! PS already in Chunk '{chunk_ob.name}'!")

        ps = inner_ob.particle_systems[-1]

        ps.seed = ps_props.seed
        settings = ps.settings
        settings.name = ps_name

        settings.count = ps_props.count

        # settings.frame_start = frame_start + p_create.frame_offset
        # settings.frame_end = frame_end + p_create.frame_offset

        settings.frame_start = frame_start
        settings.frame_end = frame_end

        # print(inner_ob.name, inner_ob.parent.name)
        chunk_ob[RBDLabNaming.CHUNK_EXTRACTED] = True
        inner_ob[RBDLabNaming.INNER_CHUNK] = True

        child_of = inner_ob.constraints.get(RBDLabNaming.CHILD_OF)
        if child_of:
            inner_ob.constraints.remove(child_of)

        # Clear any color animation data.
        remove_all_keyframes_in_action(context, chunk_ob, "color")
        remove_all_keyframes_in_action(context, inner_ob, "color")

        # Set chunk color change animation.
        chunk_ob.color = self.CHUNK_P_EMITTER_BROKEN_COLOR

        chunk_ob.keyframe_insert(data_path="color", frame=(settings.frame_start-1))
        chunk_ob.color = self.CHUNK_P_EMITTER_COLOR  # CHUNK PARTICLES COLOR.

        # propiedad para solo guardar una vez el color en el stack:
        if RBDLabNaming.PART_COLOR_ADDED not in chunk_ob:
            # print("All colors:", ob.color_stack.get_all_colors())
            # print("Guardando color:", self.CHUNK_P_EMITTER_COLOR)
            chunk_ob.color_stack.add_color(self.CHUNK_P_EMITTER_COLOR)
            chunk_ob[RBDLabNaming.PART_COLOR_ADDED] = True

        chunk_ob.keyframe_insert(data_path="color", frame=settings.frame_start)

        inner_ob.color = self.CHUNK_P_EMITTER_BROKEN_COLOR
        inner_ob.keyframe_insert(data_path="color", frame=(settings.frame_start-1))

        inner_ob.color = self.CHUNK_P_EMITTER_COLOR
        # para poder restaurar el color del inner también necesito guardarlo:
        if RBDLabNaming.PART_COLOR_ADDED not in inner_ob:
            inner_ob.color_stack.add_color(self.CHUNK_P_EMITTER_COLOR)
            inner_ob[RBDLabNaming.PART_COLOR_ADDED] = True

        inner_ob.keyframe_insert(data_path="color", frame=settings.frame_start)
        # Blender BUG. visualation of color is not updated correctly when returning to frame 0.
        chunk_ob.color = self.CHUNK_P_EMITTER_BROKEN_COLOR
        inner_ob.color = self.CHUNK_P_EMITTER_BROKEN_COLOR

        # almacenamos el fstart y el fend "del current type" para el end trails:
        # inner_ob[RBDLabNaming.PART_FSTART + "_" + settings.name + "_" + dummy] = frame_start
        # inner_ob[RBDLabNaming.PART_FEND + "_" + settings.name + "_" + dummy] = frame_end

        inner_ob[ps.name] = {
            "frame_start": frame_start,
            "frame_end": frame_end
        }

        # settings.frame_end = (
        #     settings.frame_start + ps_props.end_trails) if ps_props.enable_end_trails else frame_end

        # if dummy == "debris":
        #     settings.frame_end = frame_start + rbdlab.particles.debris.end_trails
        # if dummy == "dust":
        #     settings.frame_end = frame_start + rbdlab.particles.dust.end_trails
        # elif dummy == "smoke":
        #     settings.frame_end = frame_start + rbdlab.particles.smoke.end_trails

        if ps_props.dynamic:
            if hasattr(settings, "use_dynamic_rotation"):
                settings.use_dynamic_rotation = ps_props.use_dynamic_rotation

        if ps_props.debris_coll:
            settings.instance_collection = ps_props.debris_coll

        if dummy == "smoke":
            settings.count = 500
            ps_props.lifetime = 8
            ps_props.display_method = 'DOT'
            ps_props.display_size = 0.01
            ps_props.gravity = 0.3
            ps_props.normal = 0
            ps_props.velocity_randomize = 1
            # el smoke va disinto el object velocity:
            ps_props.object_velocity = 0
            settings.effector_weights.gravity = ps_props.gravity

        if dummy != "smoke":
            ps_props.lifetime = context.scene.frame_end
            ps_props.normal = 0
            ps_props.velocity_randomize = 1

        if dummy == "debris":
            ps_props.count = 20
            ps_props.display_size = 0.2
            ps_props.particle_size = 0.2
            ps_props.lifetime = context.scene.frame_end

        elif dummy == "dust":
            ps_props.count = 60
            ps_props.display_size = 0.1
            ps_props.particle_size = 0.1

        settings.lifetime = ps_props.lifetime
        settings.display_method = ps_props.display_method
        settings.normal_factor = ps_props.normal
        settings.particle_size = ps_props.particle_size
        settings.display_size = ps_props.display_size
        settings.factor_random = ps_props.velocity_randomize

        settings.object_align_factor = ps_props.direction
        settings.object_factor = ps_props.object_velocity
        settings.subframes = ps_props.subframes
        settings.display_color = ps_props.display_color
        settings.lifetime_random = ps_props.lifetime_random
        settings.distribution = 'RAND'
        settings.render_type = 'COLLECTION'
        settings.size_random = ps_props.size_random
        settings.use_rotations = ps_props.use_rotation
        settings.phase_factor_random = ps_props.random_phase

        ps_props.seed += 1

        # por defecto el show_instancer_for_viewport:
        inner_ob.show_instancer_for_render = ps_props.show_instancer_for_render
        inner_ob.show_instancer_for_viewport = ps_props.show_instancer_for_viewport

        self.particle_materials(context, dummy, inner_ob, settings)

    def checkeo_si_hay_particulas_y_sino_hago_limpieza(self, tcoll):
        particles_names = ("debris", "dust", "smoke")

        have_particles = []

        for ob in tcoll.objects:
            if len(ob.particle_systems) > 0:
                for ps in ob.particle_systems:
                    for pn in particles_names:
                        if pn in ps.name:
                            if pn not in have_particles:
                                have_particles.append(pn)

        # si no tiene particulas hago una limpieza:
        if len(have_particles) == 0:

            if RBDLabNaming.COLL_WITH_PARTICLES in tcoll:
                del tcoll[RBDLabNaming.COLL_WITH_PARTICLES]

            for ob in tcoll.objects:
                if RBDLabNaming.EXTRACTION_ID in ob:
                    del ob[RBDLabNaming.EXTRACTION_ID]
                if RBDLabNaming.CHUNK_EXTRACTED in ob:
                    del ob[RBDLabNaming.CHUNK_EXTRACTED]

            if RBDLabNaming.HAS_BROKEN in tcoll:
                del tcoll[RBDLabNaming.HAS_BROKEN]
            if RBDLabNaming.HAS_MOTIONS in tcoll:
                del tcoll[RBDLabNaming.HAS_MOTIONS]
            if RBDLabNaming.VELOCITIES in tcoll:
                del tcoll[RBDLabNaming.VELOCITIES]

        return have_particles
    
    
    def set_cache_names(self, tcoll: Collection) -> None:

        # Les tengo q setear el nombre de las caches, despues de crear todas las particulas 
        # por culpa de los .x que pone de sufijo blender en los nombres:
        
        white_list_names = ("_debris_", "_dust_", "_smoke_")
        for ob in tcoll.objects: 
            
            if ob.type != 'MESH' or not ob.visible_get() or RBDLabNaming.INNER_EMISOR not in ob or len(ob.particle_systems) < 1:
                continue

            for ps in ob.particle_systems:

                can_continue = next((True for wln in white_list_names if wln in ps.name), False)
                if not can_continue:
                    continue

                # Les pongo el nombre a las caches:
                for cache in ps.point_cache.point_caches:
                    cache.name = ps.settings.name


    def execute(self, context):
        ''' EXECUTE rbdlab.particles_create '''

        start0 = datetime.now()

        rbdlab, tcoll_list = get_common_vars(context, get_rbdlab=True, get_tcoll_list=True)
        tcoll = tcoll_list.active
        
        if tcoll is None:
            return {'CANCELLED'}
        
        coll_name = tcoll.name
        if not coll_name:
            return {'CANCELLED'}
        
        # si estamos visualizando metal, lo cambio a chunks para poder trabajar:
        tcoll_item = tcoll_list.active_item
        metal_list = tcoll_item.metal_list
        current_metal = metal_list.active

        if current_metal:
            metal_previous_state = current_metal.metal_or_fractures
            if 'FRACTURES' not in metal_previous_state:
                current_metal.metal_or_fractures = {'FRACTURES'}

        # QUIZAS LO QUITE ESTE TROZO -------------------------------------------------------
        self.checkeo_si_hay_particulas_y_sino_hago_limpieza(tcoll)
        # END QUIZAS LO QUITE ESTE TROZO ------------------------------------------------------

        addon_preferences = RBDLabPreferences.get_prefs(context)
        # rbdlab_particles = rbdlab.particles

        # ps_props = rbdlab.particles.debris or rbdlab.particles.dust or rbdlab.particles.smoke:
        dummy = self.type
        ps_props = rbdlab.get_particles_properties(dummy)
        p_create: PG_ParticlesCreate = ps_props.create  # rbdlab.particles.dymmy.create

        use_distance_threshold = p_create.distance_threshold != 0.01  # Different from default one.

        # print("create particles: " + str(datetime.now() - start0))

        # for ob in rbdlab.get_chunks():
        #     ob_rbdlab = ob.rbdlab
        #     print(f"{ob.name} broken at frame {ob_rbdlab.broken_at_frame}')
        #     print(f"{ob.name} with {len(ob_rbdlab.motions)} motions")
        #     for idx, motion in enumerate(ob_rbdlab.motions):
        #         print(f"\t- Motion {idx}. Frame-range: {motion.range[0]}-{motion.range[1]}')

        # Por ahora fuerzo siempre que se recompute:
        # p_create.force_update_broken_motion = True

        # Si existe domain, por rendimiento primero se desactiva:
        domain = self.check_if_exist_domain(context, tcoll)
        if domain:
            if RBDLabNaming.SMOKE_MOD in domain.modifiers:
                domain.modifiers[RBDLabNaming.SMOKE_MOD].show_viewport = False

        self.CHUNK_P_EMITTER_BROKEN_COLOR = list(addon_preferences.color_p_emiter_broken)
        self.CHUNK_P_EMITTER_COLOR = list(addon_preferences.color_p_emiter)

        self.get_particles_ui_defaults(self, rbdlab=rbdlab)

        self.chunk_objects = [ob for ob in tcoll.objects if ob.type == 'MESH' and ob.visible_get() and ob.name != RBDLabNaming.GROUND and RBDLabNaming.SUFIX_BBOX not in ob.name and RBDLabNaming.PASSIVE not in ob]

        # print("[PARTICLES_DEBUG] Chunk count in target collection: ", len(tcoll.objects))
        # print("[PARTICLES_DEBUG] Chunk count to process in particle creation: ", len(self.chunk_objects))

        if not self.chunk_objects:
            self.report({'WARNING'}, "Not valid objects!")
            return {'CANCELLED'}

        if p_create.by_selection:
            self.chunk_objects = [obj for obj in self.chunk_objects if obj.select_get()]
            if len(self.chunk_objects) < 1:
                self.report({'WARNING'}, "Not valid objects selected!")
                return {'CANCELLED'}

        if rbdlab.low_or_high_visibility_viewport != "Low":
            rbdlab.low_or_high_visibility_viewport = "Low"

        # print("self.chunk_objects:", self.chunk_objects)

        # +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
        # Update Broken / Motions.
        # +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++

        if (RBDLabNaming.HAS_MOTIONS not in tcoll and p_create.use_motions) or\
           (RBDLabNaming.HAS_BROKEN not in tcoll and p_create.use_broken) or\
           p_create.force_update_broken_motion:
            start_update = datetime.now()
            update_broken_neighbours_and_motions(
                context,
                list(self.chunk_objects),  # rbdlab.get_chunks(),
                step=p_create.frame_step,
                distance_threshold=p_create.distance_threshold,
                # condition=p_create.condition,
                velocity_threshold=p_create.velocity_threshold,
                max_motions=p_create.ps_count,
                flag=p_create.options)
            if p_create.use_broken:
                tcoll[RBDLabNaming.HAS_BROKEN] = 1
            if p_create.use_motions:
                tcoll[RBDLabNaming.HAS_MOTIONS] = 1
            if p_create.use_motions:
                tcoll[RBDLabNaming.VELOCITIES] = 1  # TODO: DEPRECATE!
            p_create.force_update_broken_motion = False
            print("Update broken/motions: " + str(datetime.now() - start_update))

        # +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
        # Setup Creation
        # +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++

        if p_create.use_broken:
            self.broken_chunks: dict[Object, int] = {chunk: chunk.rbdlab.broken_at_frame for chunk in self.chunk_objects if chunk.rbdlab.broken_at_frame != -1}
            self.chunk_objects = [chunk for chunk in self.chunk_objects if chunk in self.broken_chunks]
        
        if p_create.use_motions:
            self.motion_chunks: dict[Object, list[Motion]] = {chunk: chunk.rbdlab.motions for chunk in self.chunk_objects if chunk.rbdlab.has_motions}
            self.chunk_objects = [chunk for chunk in self.chunk_objects if chunk in self.motion_chunks]

        chunks_to_extract = [ob for ob in self.chunk_objects if not self.check_if_is_ectracted(ob)]
        
        # print("chunks_to_extract:", chunks_to_extract)
        self.extraction(context, chunks_to_extract)

        # +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
        # Particles Creation
        # +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++

        # LIB Collection: Debris Basics.
        if dummy in ("debris", "dust"):
            instance_collection = RBDLabNaming.BASIC_DEBRIS_COLL_NAME
            if instance_collection not in bpy.data.collections:
                set_active_collection_to_master_coll(context)
                append_collection(context, instance_collection)

            ps_props.debris_coll = bpy.data.collections[instance_collection]

        start1 = datetime.now()

        use_motions = p_create.use_motions
        use_broken = p_create.use_broken

        inner_objects: dict[Object, Object] = {}
        chunks_set = set(self.chunk_objects)
        chunk_names_set = {chunk.name for chunk in self.chunk_objects}
        for ob in context.view_layer.objects:
            if ob.type != 'MESH':
                continue
            if not ob.visible_get():
                continue
            if ob.parent is None:
                # Not inner.
                continue
            # if ob not in chunks_set:
            #    # Not inner but parent.
            #    ### print("Not inner but parent.", ob.name, ob.parent.name)
            #    continue
            if "rbdlab_father_obj" not in ob:
                # No father.
                continue
            if ob["rbdlab_father_obj"] not in chunk_names_set:
                # Father mismatch.
                continue
            if ob.parent not in chunks_set:
                # Father not in our chunks set.
                # print("Father not in our chunks set.", ob.name, ob.parent.name)
                continue
            # OK.
            inner_objects[ob.parent] = ob

        del chunks_set

        for parent_ob, inner_ob in inner_objects.items():
            if RBDLabNaming.SUFIX_BBOX in parent_ob.name:
                continue

            if RBDLabNaming.INNER_EMISOR not in inner_ob:
                inner_ob[RBDLabNaming.INNER_EMISOR] = True

            if use_motions:
                
                if dummy == "smoke":
                    inners_duplieds = set()
                
                else: # Si no es smoke no lo duplicaremos:
                    target_inner_ob = inner_ob

                for i, motion in enumerate(parent_ob.rbdlab.motions):

                    # Por cada motion duplicamo el objeto inner_ob (en low level):
                    if dummy == "smoke":
                        
                        target_inner_ob = inner_ob.copy()
                        target_inner_ob.data = inner_ob.data.copy()

                        # Les seteo ciertas propiedades necesarias:

                        # nombres:
                        if "." in parent_ob.name:
                            new_name = parent_ob.name.replace(".", "_smoke_duplied.")
                        else:
                            new_name = parent_ob.name + "_smoke__duplied"

                        target_inner_ob.name = new_name
                        target_inner_ob[RBDLabNaming.INNER_EMISOR] = True

                        # Les tengo que transferir el ob.rbdlab.modions también:
                        for tmp_motion in  parent_ob.rbdlab.motions:
                            target_inner_ob.rbdlab.add_motion(tmp_motion.range[0], tmp_motion.range[1])
                        
                        # Lo linkamos a las colecciones donde estuviera el original 
                        [user_coll.objects.link(target_inner_ob) for user_coll in inner_ob.users_collection]
                        
                        # los agregamos al conjunto de duplicados:
                        inners_duplieds.add(target_inner_ob)
                        
                    
                    self.setup_particle_system(
                        context=context,
                        rbdlab=rbdlab,
                        ps_props=ps_props,
                        p_create=p_create,
                        chunk_ob=parent_ob,
                        inner_ob=target_inner_ob,
                        use_distance_threshold=use_distance_threshold,
                        motion=motion
                    )

                    if dummy == "smoke":

                        # Guardamos sus hijos pero esta vez es un listado en lugar de un nombre de objeto (al ser smoke):
                        parent_ob[RBDLabNaming.CHUNK_PART_CHILD] = list(inners_duplieds)
                        
                        # si estoy en la ultima vuelta del bucle de motions:
                        if i == len(parent_ob.rbdlab.motions)-1:
                            # lo deslinko que le costará menos q borrarlos:
                            [user_coll.objects.unlink(inner_ob) for user_coll in inner_ob.users_collection]
                            # rm_ob(inner_ob)

            elif use_broken:
                self.setup_particle_system(
                    context=context,
                    rbdlab=rbdlab,
                    ps_props=ps_props,
                    p_create=p_create,
                    chunk_ob=parent_ob,
                    inner_ob=inner_ob,
                    use_distance_threshold=use_distance_threshold,
                    motion=None
                )

        del inner_objects

        if RBDLabNaming.SUFIX_LOW in coll_name:
            coll_high_name = coll_name.replace(RBDLabNaming.SUFIX_LOW, RBDLabNaming.SUFIX_HIGH)
        else:
            coll_high_name = coll_name + RBDLabNaming.SUFIX_HIGH

        if coll_high_name in bpy.data.collections:

            # seteo para q lo haga solo al target collection:
            show_low_high_to_all_or_tc = rbdlab.ui.show_low_high_to_all_or_tc
            rbdlab.ui.show_low_high_to_all_or_tc = False

            if rbdlab.low_or_high_visibility_render == "Low":
                rbdlab.low_or_high_visibility_render = "High"
                rbdlab.low_or_high_visibility_render = "Low"
            else:
                rbdlab.low_or_high_visibility_render = "Low"
                rbdlab.low_or_high_visibility_render = "High"

            rbdlab.ui.show_low_high_to_all_or_tc = show_low_high_to_all_or_tc

        print("Particles setting up End: " + str(datetime.now() - start1))

        # por rendimiento primero se desactiva el domain.
        # vuelvo a activar el domain:
        if domain:
            if RBDLabNaming.SMOKE_MOD in domain.modifiers:
                domain.modifiers[RBDLabNaming.SMOKE_MOD].show_viewport = True

        deselect_all_objects(context)

        # limpieza de inners sin particulas
        [ob.select_set(True) for ob in tcoll.objects if ob.type == 'MESH' and ob.visible_get() and RBDLabNaming.INNER_EMISOR in ob and len(ob.particle_systems) == 0]

        if context.selected_objects:
            set_active_object(context, context.selected_objects[0])
            bpy.ops.object.delete(use_global=False)

        deselect_all_objects(context)

        # Seteamos el nombre de las caches:
        self.set_cache_names(tcoll)

        # QUIZAS LO QUITE ESTE TROZO ----------------------------------------------------
        have_particles = self.checkeo_si_hay_particulas_y_sino_hago_limpieza(tcoll)
        # END QUIZAS LO QUITE ------------------------------------------------------

        if len(have_particles) > 0:
            tcoll[RBDLabNaming.COLL_WITH_PARTICLES] = RBDLabNaming.COLL_WITH_PARTICLES
        

        # restauro la visibilidad del metal:
        if current_metal and metal_previous_state:
            current_metal.metal_or_fractures = metal_previous_state

        print("create particles: " + str(datetime.now() - start0))
        return {'FINISHED'}
