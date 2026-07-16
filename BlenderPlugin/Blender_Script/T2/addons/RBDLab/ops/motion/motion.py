import bpy

from ...addon.naming import RBDLabNaming
from ...Global.functions import remove_collection_by_name, create_new_collection, rm_ob
from ...Global.basics import select_object, set_active_object, deselect_all_objects
from bpy.types import Operator
from bpy.props import StringProperty
from mathutils import Vector
from datetime import datetime
import uuid
from mathutils import Vector


class RBDLAB_OT_motion_set_kinematic(Operator):
    bl_idname = "rbdlab.motion_set_kinematic"
    bl_label = "Set Kinematic"

    @classmethod
    def description(cls, _context, properties):
        return "Set Kinematic to active object, and switch to rbd, from curren frame"

    def execute(self, context):
        if context.selected_objects:
            valid_objects = [ob for ob in context.selected_objects if ob.type == 'MESH']
            if valid_objects:

                deselect_all_objects(context)

                for ob in valid_objects:
                    if ob.rigid_body is None:
                        select_object(context, ob)
                    else:
                        ob.rigid_body.kinematic = True
                        if ob.rigid_body.type != 'ACTIVE':
                            ob.rigid_body.type = 'ACTIVE'

                if len(context.selected_objects):
                    set_active_object(context, context.selected_objects[0])
                    bpy.ops.rigidbody.objects_add(type='ACTIVE')

                for ob in valid_objects:
                    if ob.rigid_body is not None:
                        ob.rigid_body.kinematic = True
                        current_frame = context.scene.frame_current
                        ob.keyframe_insert(data_path="rigid_body.kinematic", frame=current_frame)
                        ob.rigid_body.kinematic = False
                        ob.keyframe_insert(data_path="rigid_body.kinematic", frame=current_frame+1)
                        if "rbdlab_motion_kinematic" not in ob:
                            ob["rbdlab_motion_kinematic"] = current_frame

            valid_objects = []
        else:
            self.report({'WARNING'}, "Select any object first!")
            return {'CANCELLED'}

        return {'FINISHED'}


class RBDLAB_OT_motion_set_rbd(Operator):
    bl_idname = "rbdlab.motion_set_rbd"
    bl_label = "Set RBD"

    @classmethod
    def description(cls, _context, properties):
        return "Set Passive to active object"

    def execute(self, context):
        if context.selected_objects:
            valid_objects = [ob for ob in context.selected_objects if ob.type == 'MESH']
            if valid_objects:

                deselect_all_objects(context)

                for ob in valid_objects:
                    if ob.rigid_body is None:
                        select_object(context, ob)
                    else:
                        ob.rigid_body.kinematic = False
                        if ob.rigid_body.type != 'ACTIVE':
                            ob.rigid_body.type = 'ACTIVE'

                if len(context.selected_objects):
                    set_active_object(context, context.selected_objects[0])
                    bpy.ops.rigidbody.objects_add(type='ACTIVE')

                for ob in valid_objects:
                    if ob.rigid_body is not None:
                        if "rbdlab_motion_rbd" not in ob:
                            ob["rbdlab_motion_rbd"] = True

            valid_objects = []
        else:
            self.report({'WARNING'}, "Select any object first!")
            return {'CANCELLED'}

        return {'FINISHED'}


class RBDLAB_OT_motion_rm_kinematic(Operator):
    bl_idname = "rbdlab.motion_rm_kinematic"
    bl_label = "Remove Kinematic"

    @classmethod
    def description(cls, _context, properties):
        return "Remove kinematic"

    def execute(self, context):
        ob = context.active_object
        rbo = ob.rigid_body

        if ob.type == 'MESH' and rbo is not None and len(context.selected_objects) > 0:
            bpy.ops.rigidbody.object_remove()
            if "rbdlab_motion_kinematic" in ob:
                del ob["rbdlab_motion_kinematic"]

                if ob.animation_data and ob.animation_data.action:
                    for fc in ob.animation_data.action.fcurves:
                        if fc.data_path == "rigid_body.kinematic":
                            ob.animation_data.action.fcurves.remove(fc)

        return {'FINISHED'}


class RBDLAB_OT_motion_rm_rbd(Operator):
    bl_idname = "rbdlab.motion_rm_rbd"
    bl_label = "Remove Passive"

    @classmethod
    def description(cls, _context, properties):
        return "Remove Passive"

    def execute(self, context):
        ob = context.active_object
        rbo = ob.rigid_body

        if ob.type == 'MESH' and rbo is not None and len(context.selected_objects) > 0:
            bpy.ops.rigidbody.object_remove()
            if "rbdlab_motion_rbd" in ob:
                del ob["rbdlab_motion_rbd"]

        return {'FINISHED'}


class RBDLAB_OT_motion_offset(Operator):
    bl_idname = "rbdlab.motion_offset"
    bl_label = "Offset"

    direction: StringProperty(
        default="forward"
    )

    @classmethod
    def description(cls, _context, properties):
        return "Offset direction"

    def execute(self, context):
        rbdlab = context.scene.rbdlab
        ob = context.active_object
        rbo = ob.rigid_body

        if ob.type == 'MESH' and rbo is not None and len(context.selected_objects) > 0:

            if ob.animation_data is not None and ob.animation_data.action is not None:
                action = ob.animation_data.action

                for fcu in action.fcurves:
                    if "rigid_body.kinematic" in fcu.data_path:
                        for kp in fcu.keyframe_points:
                            if self.direction == "forward":
                                kp.co.x += rbdlab.motion.offset_amount
                                kp.handle_left.x += rbdlab.motion.offset_amount
                                kp.handle_right.x += rbdlab.motion.offset_amount
                            elif self.direction == "backward":
                                kp.co.x -= rbdlab.motion.offset_amount
                                kp.handle_left.x -= rbdlab.motion.offset_amount
                                kp.handle_right.x -= rbdlab.motion.offset_amount

            if self.direction == "forward":
                ob["rbdlab_motion_kinematic"] += rbdlab.motion.offset_amount
            elif self.direction == "backward":
                ob["rbdlab_motion_kinematic"] -= rbdlab.motion.offset_amount

        return {'FINISHED'}


class RBDLAB_OT_motion_add_emitter(Operator):
    bl_idname = "rbdlab.motion_add_emitter"
    bl_label = "Add Emitter"

    @classmethod
    def description(cls, _context, properties):
        return "Add Emitter"

    def execute(self, context):
        rbdlab = context.scene.rbdlab
        ob_active = context.active_object

        if ob_active.type != 'MESH':
            self.report({'WARNING'}, ob_active.name + " is not a valid object!")
            return {'CANCELLED'}

        if len(ob_active.particle_systems) > 0:
            self.report({'WARNING'}, ob_active.name + " has already particle systems!")
            return {'CANCELLED'}

        # bpy.ops.object.particle_system_add()
        ps_name = RBDLabNaming.PS_MOD_P_TO_RBD
        ob_active.modifiers.new(ps_name, 'PARTICLE_SYSTEM')
        rbdlab.motion_emitter_target_object = ob_active
        ob_active[RBDLabNaming.MOTION_OBJECT_EMITTER] = True

        ps = ob_active.particle_systems.get(ps_name)
        if ps:
            ps.settings.use_rotation_instance = True
            ps.settings.frame_end = context.scene.frame_end
            ps.settings.lifetime = context.scene.frame_end
            ps.settings.particle_size = 1

            if rbdlab.motion_object_for_emit:
                ps.settings.render_type = 'OBJECT'
                ps.settings.instance_object = rbdlab.motion_object_for_emit

        return {'FINISHED'}


class RBDLAB_OT_motion_convert_ps_to_rbd(Operator):
    bl_idname = "rbdlab.motion_convert_ps_to_rbd"
    bl_label = "Conver to rigidbodies"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def description(cls, _context, properties):
        return "Convert particles in to rigidbodies"

    cp_coll_name = "_particles_copied"

    def execute(self, context):
        start = datetime.now()

        rbdlab = context.scene.rbdlab

        bpy.ops.screen.frame_jump(end=False)
        # if context.scene.frame_current != context.scene.frame_start:
        #     context.scene.frame_set(context.scene.frame_start)
        # context.scene.frame_current = context.scene.frame_start

        # Evaluate the Dependency graph in order to get data from animation, modifiers, etc
        depsgraph = context.evaluated_depsgraph_get()

        # objects:
        obj_emitter = rbdlab.motion_emitter_target_object
        # print('OP', rbdlab.motion_emitter_target_object)

        obj_to_copy = rbdlab.motion_object_for_emit

        if not obj_emitter:
            self.report({'WARNING'}, "No valid Object emitter!")
            return {'CANCELLED'}

        if RBDLabNaming.MOTION_OBJECT_EMITTER not in obj_emitter:
            self.report({'WARNING'}, "No valid Object emitter!")
            return {'CANCELLED'}

        if not obj_to_copy:
            self.report({'WARNING'}, "Object to emit is mandatory!")
            return {'CANCELLED'}

        if obj_to_copy.scale != Vector((1.0, 1.0, 1.0)):
            self.report({'WARNING'}, "First Apply the scale to " + obj_to_copy.name + "!")
            return {'CANCELLED'}

        if obj_emitter is None:
            self.report({'WARNING'}, "Invalid Object!")
            return {'CANCELLED'}

        if len(obj_emitter.particle_systems) < 1:
            self.report({'WARNING'}, obj_emitter.name + " dont have particles!")
            return {'CANCELLED'}

        if len(obj_emitter.particle_systems) > 1:
            self.report({'WARNING'}, obj_emitter.name + " has too many particle systems!")
            return {'CANCELLED'}

        # reseteo los settings:
        rbdlab.motion.avalidable_mass = rbdlab.motion.get_default_properties("avalidable_mass")
        rbdlab.motion.mass = rbdlab.motion.get_default_properties("mass")
        rbdlab.motion.collision_shape = rbdlab.motion.get_default_properties("collision_shape")
        rbdlab.motion.friction = rbdlab.motion.get_default_properties("friction")
        rbdlab.motion.restitution = rbdlab.motion.get_default_properties("restitution")
        rbdlab.motion.use_margin = rbdlab.motion.get_default_properties("use_margin")
        rbdlab.motion.collision_margin = rbdlab.motion.get_default_properties("collision_margin")

        # obj_evaluated = depsgraph.objects[obj_emitter.name]
        # context.scene.frame_set(rbdlab.motion_ps_to_rbd_kinematics_end)
        obj_evaluated = obj_emitter.evaluated_get(depsgraph)

        if len(obj_evaluated.particle_systems) > 0:
            ps = obj_evaluated.particle_systems[0]  # Assume only 1 particle system is present.

            new_coll_name = obj_emitter.name + self.cp_coll_name
            if new_coll_name not in bpy.data.collections:
                create_new_collection(context, new_coll_name)
                hash = str(uuid.uuid3(uuid.NAMESPACE_DNS, new_coll_name))
                obj_emitter["rbdlab_motion_collection_id"] = hash
                bpy.data.collections[new_coll_name]["rbdlab_motion_collection_id"] = hash

            particles_coll = bpy.data.collections[new_coll_name]

            bpy.ops.object.select_all(action='DESELECT')
            # create_objects_for_particles

            obj_list = []

            for i in range(len(ps.particles)):
                obj_copy = bpy.data.objects[obj_to_copy.name].copy()
                obj_list.append(obj_copy)
                particles_coll.objects.link(obj_copy)
                obj_copy.select_set(True)
                # bpy.ops.object.make_single_user(obdata=True)

            # end create_objects_for_particles
            # print("*******************  obj_list", obj_list)

            if len(obj_list) > 0:
                first_copy = obj_list[0]
                set_active_object(context, first_copy)
                bpy.ops.rigidbody.objects_add(type='ACTIVE')
                # bpy.context.object.rigid_body.kinematic = True
                context.scene.rigidbody_world.enabled = False  # optimizando tiempos

            # match_and_keyframe_objects
            kine_end = rbdlab.motion_ps_to_rbd_kinematics_end

            for frame in range(context.scene.frame_start, context.scene.frame_end):
                context.scene.frame_set(frame)

                for p, ob in zip(ps.particles, obj_list):

                    if ob is None:
                        continue

                    start_particle_motion = int(p.birth_time)
                    end_particle_motion = int(p.birth_time + kine_end + 1)

                    if any([abs(p.velocity.x) > 0.0, abs(p.velocity.y) > 0.0, abs(p.velocity.z) > 0.0]):

                        if p.alive_state != 'ALIVE':

                            ###
                            # NOTA IMPORTANTE motion_convert_ps_to_rbd_with_hide es un bool property oculto en la ui
                            # esto es porque primero era opcional esto, pero debido a que el bake to keyframes de blender
                            # requiere de no tener animada la visibilidad, hice la property motion_p_to_rbd_show_hide_toggle con
                            # el motion_p_to_rbd_show_hide_toggle_update a modo de toggle para poder ocultaro/desocultar en modo post creacion
                            # la información la guardamos en las copias de el frame on y el frame of.
                            ###

                            if start_particle_motion - 1 == frame and rbdlab.ui.motion_convert_ps_to_rbd_with_hide:

                                # se descarto el metodo de escala porque si usas colliders tipo mesh requiere tener la escala aplicada
                                # por lo tanto para respetar la escala no la tocamos y usamos ocultacion por settings

                                # ocultacion por escala:
                                # if ob.scale != Vector((0, 0, 0)):
                                #     ob.scale = (0,) * 3
                                #     ob.keyframe_insert(data_path="scale", frame=frame + 1)

                                first_frame = frame + 1
                                second_frame = frame + 2

                                # ocultacion por setting:
                                # ob.hide_viewport = True
                                # ob.keyframe_insert(data_path="hide_viewport", frame=first_frame)

                                # ob.hide_viewport = False
                                # ob.keyframe_insert(data_path="hide_viewport", frame=second_frame)

                                # ob.hide_render = True
                                # ob.keyframe_insert(data_path="hide_render", frame=first_frame)

                                # ob.hide_render = False
                                # ob.keyframe_insert(data_path="hide_render", frame=second_frame)

                                ob["rbdlab_hide_first_frame_True"] = first_frame
                                ob["rbdlab_hide_second_frame_False"] = second_frame
                        else:
                            if start_particle_motion < frame < (end_particle_motion + 3):

                                # match_object_to_particle
                                M = p.rotation.to_matrix().to_4x4()
                                M.translation = p.location
                                ob.matrix_world = M
                                ob.scale = (p.size,) * 3
                                ob.rotation_euler = p.rotation.to_euler()
                                # end match_object_to_particle

                                ob.keyframe_insert(data_path="location", frame=frame)
                                ob.keyframe_insert(data_path="rotation_euler", frame=frame)
                                # esto es necesario si se usa la ocultacion por escala:
                                # ob.keyframe_insert(data_path="scale", frame=frame)

                                # if ob.rigid_body:
                                ob.rigid_body.kinematic = True
                                ob.keyframe_insert(data_path="rigid_body.kinematic", frame=end_particle_motion - 2)
                                ob.rigid_body.kinematic = False
                                ob.keyframe_insert(data_path="rigid_body.kinematic", frame=end_particle_motion - 1)
                                ob["rbdlab_motion_kinematic_converted"] = end_particle_motion - 1
                                # le ponemos la masa:
                                ob.rigid_body.mass = ps.settings.mass

            # end match_and_keyframe_objects
        else:
            print("no particles in object!")

        bpy.ops.object.select_all(action='DESELECT')
        [(
            setattr(ob, "hide_viewport", False),
            setattr(ob, "hide_render", False),
            ob.select_set(True)
        ) for ob in obj_list]

        if context.selected_objects:
            # los hago objetos reales y les aplico la escala:
            first_selected = context.selected_objects[0]
            set_active_object(context, first_selected)
            bpy.ops.object.make_single_user(obdata=True)
            bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
            # este me estaba machacando la masa:
            # bpy.ops.rigidbody.mass_calculate(material="Concrete")

        # eliminamos las copias que no tengan animacion:
        [rm_ob(ob) for ob in obj_list if not ob.animation_data]

        ps_mod = obj_emitter.modifiers.get(RBDLabNaming.PS_MOD_P_TO_RBD)
        if ps_mod:
            ps_mod.show_viewport = False
            ps_mod.show_render = False

        context.scene.frame_current = context.scene.frame_start
        bpy.ops.object.select_all(action='DESELECT')
        context.scene.rigidbody_world.enabled = True  # optimizando tiempos
        obj_emitter.select_set(True)
        set_active_object(context, obj_emitter)
        rbdlab.ui.show_motion_p_settings = False
        rbdlab.ui.show_motion_rb_settings = True

        print("Convert particles in to rigidbodies End: " + str(datetime.now() - start))
        return {'FINISHED'}


class RBDLAB_OT_motion_remove_emitter(Operator):
    bl_idname = "rbdlab.motion_remove_emitter"
    bl_label = "Remove Emitter"

    cp_coll_name = "_particles_copied"

    @ classmethod
    def description(cls, _context, properties):
        return "Add Emitter"

    def execute(self, context):
        rbdlab = context.scene.rbdlab
        obj_active = context.active_object

        if obj_active.type != 'MESH':
            self.report({'WARNING'}, obj_active.name + " is not a valid object!")
            return {'CANCELLED'}

        if len(obj_active.particle_systems) == 0:
            self.report({'WARNING'}, obj_active.name + " has no particle systems!")
            return {'CANCELLED'}

        bpy.ops.object.particle_system_remove()

        coll_name = obj_active.name + self.cp_coll_name
        if coll_name in bpy.data.collections:

            # los quito primero de los rbd para no tener luego problemas:
            rbw_coll = bpy.data.collections.get(RBDLabNaming.RBD_WORLD)
            if rbw_coll:
                for ob in rbw_coll.objects:
                    rbw_coll.objects.unlink(ob)

            remove_collection_by_name(context, coll_name, True)

        if "rbdlab_motion_collection_id" in obj_active:
            del obj_active["rbdlab_motion_collection_id"]

        if RBDLabNaming.MOTION_OBJECT_EMITTER in obj_active:
            del obj_active[RBDLabNaming.MOTION_OBJECT_EMITTER]

        select_object(context, rbdlab.motion_object_for_emit)
        set_active_object(context, rbdlab.motion_object_for_emit)
        bpy.ops.object.make_single_user(obdata=True)
        set_active_object(context, obj_active)
        deselect_all_objects(context)
        set_active_object(context, obj_active)
        select_object(context, obj_active)

        return {'FINISHED'}
