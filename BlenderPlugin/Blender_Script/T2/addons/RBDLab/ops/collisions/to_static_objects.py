import bpy
import bmesh
from bpy.types import Operator, Object
from ...Global.basics import enter_edit_mode, enter_object_mode, set_active_object
from ...Global.functions import move_objects_to_collection
from ...addon.naming import RBDLabNaming
# from ...addon.paths import RBDLabPreferences


class COLLISIONS_OT_to_static_objects(Operator):
    bl_idname = "rbdlab.collisions_to_static_objects"
    bl_label = "Collisions Static objects"
    bl_description = "To set collision to selected objects that are not moving in your scene"
    bl_options = {'REGISTER', 'UNDO'}

    def create_convex_hull_from_outer_vertex(self, context, valid_objects: list[Object]) -> None:
        scn = context.scene
        depsgraph = context.evaluated_depsgraph_get()

        outer_faces = []
        inner_faces = []
        outer_verts = []

        for ob in valid_objects:
            bm = bmesh.new()
            bm.from_object(ob.evaluated_get(depsgraph), depsgraph)
            fm = bm.faces.layers.face_map.verify()

            for face in bm.faces:
                map_idx = face[fm]
                if map_idx != -1:

                    if ob.face_maps[map_idx].name == "Interior":
                        if face not in inner_faces:
                            inner_faces.append(face)

                if face not in inner_faces:
                    if face not in outer_faces:
                        outer_faces.append(face)
                        for v in face.verts:
                            if v.co not in outer_verts:
                                outer_verts.append(ob.matrix_world @ v.co)

        # print(outer_verts)
        if outer_verts:

            me = bpy.data.meshes.new("mesh")  # add a new mesh
            ob = bpy.data.objects.new("MyObject", me)  # add a new object using the mesh

            scn.collection.objects.link(ob)  # put the object into the scene (link)
            set_active_object(context, ob)
            ob.select_set(True)  # select object

            mesh = ob.data
            bm = bmesh.new()

            for co in outer_verts:
                bm.verts.new(co)  # add a new vert

            bmesh.ops.convex_hull(bm, input=bm.verts, use_existing_faces=True)

            # make the bmesh the object's mesh
            bm.to_mesh(mesh)
            bm.free()  # always do this when finished

    def colors_acction(self, ob, col_p_collision):
        ob.color_stack.add_color(col_p_collision)
        ob.color = col_p_collision

    def execute(self, context):
        if context.selected_objects:

            if context.scene.frame_current != context.scene.frame_start:
                context.scene.frame_set(context.scene.frame_start)

            scn = context.scene
            rbdlab = scn.rbdlab
            depsgraph = context.evaluated_depsgraph_get()

            valid_objects = [
                ob.evaluated_get(depsgraph) for ob in context.selected_objects
                if ob.type == 'MESH'
                and ob.name in rbdlab.filtered_target_collection.objects
                and ob.name != RBDLabNaming.GROUND]

            if len(valid_objects) == 0:
                self.report({'WARNING'}, "Not Valid Ojects Selected!")
                return {'CANCELLED'}

            # self.create_convex_hull_from_outer_vertex(context, valid_objects)

            bpy.ops.object.duplicate_move(
                OBJECT_OT_duplicate={"linked": False, "mode": 'TRANSLATION'},
                TRANSFORM_OT_translate={"value": (0, 0, 0),
                                        "orient_type": 'GLOBAL',
                                        "orient_matrix": ((1, 0, 0),
                                                          (0, 1, 0),
                                                          (0, 0, 1)),
                                        "orient_matrix_type": 'GLOBAL', "constraint_axis": (False, False, False),
                                        "mirror": False, "use_proportional_edit": False,
                                        "proportional_edit_falloff": 'SMOOTH', "proportional_size": 1,
                                        "use_proportional_connected": False, "use_proportional_projected": False,
                                        "snap": False, "snap_elements": {'INCREMENT'},
                                        "use_snap_project": False, "snap_target": 'CLOSEST', "use_snap_self": True,
                                        "use_snap_edit": True, "use_snap_nonedit": True,
                                        "snap_point": (0, 0, 0),
                                        "snap_align": False, "snap_normal": (0, 0, 0),
                                        "gpencil_strokes": False, "cursor_transform": False, "texture_space": False,
                                        "remove_on_cancel": False, "view2d_edge_pan": False, "release_confirm": False,
                                        "use_accurate": False, "use_automerge_and_split": False})

            if len(context.selected_objects) > 0:
                set_active_object(context, context.selected_objects[-1])

                bpy.ops.object.join()  # el join requiere un activo

                new_objects = context.selected_objects
                active_ob = context.selected_objects[0]
                move_objects_to_collection(context, new_objects, RBDLabNaming.COLLISION_COLL)

                set_active_object(context, active_ob)
                bpy.ops.rigidbody.object_remove()
                bpy.ops.object.modifier_add(type='COLLISION')
                active_ob.hide_render = True
                if len(active_ob.modifiers):
                    mod = active_ob.modifiers[-1]
                    mod.name = RBDLabNaming.COLLISION_MOD

                active_ob.collision.damping_factor = 0.8
                active_ob.collision.friction_factor = 0.7

                enter_edit_mode(context)
                bpy.ops.mesh.select_all(action='SELECT')
                bpy.ops.mesh.remove_doubles()
                enter_object_mode(context)
                # hide ojito en viewport:
                # active_ob.hide_set(True)

                active_ob.name = RBDLabNaming.STATIC_COLLIDER

                # addon_preferences = RBDLabPreferences.get_prefs(context)
                # col_p_collision = list(addon_preferences.col_p_collision)
                # self.colors_acction(active_ob, col_p_collision)

                active_ob.display_type = 'TEXTURED'
                collision_so_list = rbdlab.lists.collision_so_list
                collision_so_list.add_item(active_ob)

                return {'FINISHED'}

            else:
                self.report({'WARNING'}, "Not Selected Objects!")
                return {'CANCELLED'}
        else:
            self.report({'WARNING'}, "Not Selected Objects!")
            return {'CANCELLED'}


class COLLISIONS_OT_to_static_objects_update(Operator):
    bl_idname = "rbdlab.collisions_to_static_objects_update"
    bl_label = "Update Collisions Static objects"
    bl_description = "To update collision to selected objects in list"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        scn = context.scene
        rbdlab = scn.rbdlab

        ob = rbdlab.lists.collision_so_list.get_active_item_list()
        ob.collision.stickiness = rbdlab.collision.so_stickiness
        ob.collision.use_particle_kill = rbdlab.collision.so_use_particle_kill
        ob.collision.damping_factor = rbdlab.collision.so_damping_factor
        ob.collision.damping_random = rbdlab.collision.so_damping_random
        ob.collision.friction_factor = rbdlab.collision.so_friction_factor
        ob.collision.friction_random = rbdlab.collision.so_friction_random

        return {'FINISHED'}
