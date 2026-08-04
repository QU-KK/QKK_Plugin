import bpy
from bpy.types import Operator
from ...Global.functions import remove_collection_by_name, get_pack_islands, set_shading_color
from ...Global.basics import select_object, set_active_object, deselect_all_objects
from ...addon.naming import RBDLabNaming


class RBDLAB_OT_explode_start(Operator):
    bl_idname = "rbdlab.explode_start"
    bl_label = "Start Explode"
    bl_description = "To better appreciate the fractures, you can use this option that separates the pieces from each other"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return context.scene.rbdlab.filtered_target_collection is not None

    def execute(self, context):
        from ...props.when_updating_property import colorize_update

        rbdlab = context.scene.rbdlab

        if rbdlab.filtered_target_collection:
            coll_name = rbdlab.filtered_target_collection.name
            if coll_name:

                context.workspace["exploding_mode"] = True

                is_in_local_view = len(
                    [area for area in context.screen.areas if area.type == 'VIEW_3D' and area.spaces[0].local_view]) > 0

                if RBDLabNaming.SUFIX_LOW in coll_name:
                    coll_high_name = coll_name.replace(RBDLabNaming.SUFIX_LOW, RBDLabNaming.SUFIX_HIGH)

                # rbdlab.low_or_high_visibility_viewport = "Low"
                valid_objects = []
                [valid_objects.append(obj) for obj in bpy.data.collections[coll_name].objects]

                if len(valid_objects) > 0:
                    context.space_data.overlay.show_relationship_lines = False

                    rbdlab.rbdlab_shading_color_type = bpy.context.space_data.shading.color_type
                    colorize_update(self, context)

                    context.scene.frame_current = context.scene.frame_start
                    rbdlab.show_boundingbox = False

                    # isolate
                    original_stat_visualization = rbdlab.low_or_high_visibility_viewport
                    deselect_all_objects(context)

                    if is_in_local_view:
                        bpy.ops.view3d.localview(frame_selected=False)

                    # unhide_collection_in_viewport(context, coll_name)
                    # rbdlab.low_or_high_visibility_viewport = "Low"
                    # [selected_objects.append(obj) for obj in bpy.data.collections[coll_name].objects]
                    # [valid_objects.append(obj) for obj in bpy.data.collections[coll_name].objects]

                    # unhide_collection_in_viewport(context, coll_high_name)
                    # if coll_high_name in bpy.data.collections:
                    #     rbdlab.low_or_high_visibility_viewport = "High"
                    #     [valid_objects.append(obj) for obj in bpy.data.collections[coll_high_name].objects]

                    deselect_all_objects(context)
                    if valid_objects:
                        [(obj.hide_set(False), select_object(context, obj)) for obj in valid_objects]

                    bpy.ops.view3d.localview(frame_selected=False)
                    deselect_all_objects(context)
                    # end isolate

                    # restore visibility:
                    rbdlab.low_or_high_visibility_viewport = original_stat_visualization

                    rbdlab.exploding = True
                else:
                    self.report({'WARNING'}, "No valid objects in this collection!")
                    return {'CANCELLED'}

        return {'FINISHED'}


class RBDLAB_OT_explode_finish(Operator):
    bl_idname = "rbdlab.explode_finish"
    bl_label = "Finish Explode"
    bl_description = "End explode mode"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        rbdlab = context.scene.rbdlab

        if rbdlab.filtered_target_collection:
            coll_name = rbdlab.filtered_target_collection.name
            if coll_name:

                if RBDLabNaming.SUFIX_LOW in coll_name:
                    coll_high_name = coll_name.replace(RBDLabNaming.SUFIX_LOW, RBDLabNaming.SUFIX_HIGH)
                else:
                    coll_high_name = coll_name + RBDLabNaming.SUFIX_HIGH

                context.space_data.overlay.show_relationship_lines = True
                rbdlab.explode_slider = 0
                color_type = rbdlab.rbdlab_shading_color_type
                if context.space_data.shading.type == 'SOLID':
                    if context.space_data.shading.color_type != color_type:
                        set_shading_color(context, color_type)
                elif context.space_data.shading.type == 'WIREFRAME':
                    if context.space_data.shading.color_type != 'OBJECT':
                        set_shading_color(context, color_type='OBJECT')

                        # bpy.context.space_data.shading.color_type = 'OBJECT'

                if "has_pretty_shading" in context.workspace:
                    if context.workspace["has_pretty_shading"]:
                        if context.space_data.shading.color_type != 'MATERIAL':
                            set_shading_color(context, color_type='MATERIAL')

                explodeds = [obj for obj in rbdlab.filtered_target_collection.objects
                             if obj.type == 'MESH' and obj.visible_get() and "exploded" in obj]

                if coll_high_name in bpy.data.collections:
                    [explodeds.append(obj) for obj in bpy.data.collections[coll_high_name].objects
                     if obj.type == 'MESH' and obj.visible_get() and "exploded" in obj]

                for obj in explodeds:
                    del obj["exploded"]

                # isolate
                deselect_all_objects(context)
                bpy.ops.view3d.localview(frame_selected=False)
                deselect_all_objects(context)
                # end isolate

                # restore visibility:
                rbdlab.low_or_high_visibility_viewport = rbdlab.low_or_high_visibility_viewport

                rbdlab.exploding = False

                if "exploding_mode" in context.workspace:
                    del context.workspace["exploding_mode"]

        return {'FINISHED'}


class RBDLAB_OT_explode_restart(Operator):
    bl_idname = "rbdlab.explode_restart"
    bl_label = "Restart Process"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        rbdlab = context.scene.rbdlab
        tcoll = rbdlab.filtered_target_collection
        coll_name = tcoll.name
        if coll_name:

            coll_high_name = coll_name.replace(RBDLabNaming.SUFIX_LOW, RBDLabNaming.SUFIX_HIGH)
            constraints_collection_name = coll_name + "_GlueConstraints"

            # para luego quitarlos de los rigidbodies y no exploten
            # por estar repetidos en la coleccion de rigidbodies de blender
            removed_chunks = []
            for obj in bpy.data.collections[coll_name].objects:
                removed_chunks.append(obj)

            pack_islands = get_pack_islands(tcoll)

            deselect_all_objects(context)
            bpy.ops.rbdlab.explode_finish()
            for k, v in pack_islands.items():
                obj = bpy.data.objects.get(k)
                if obj:

                    remove_collection_by_name(context, coll_name, True)

                    if coll_high_name in bpy.data.collections:
                        remove_collection_by_name(context, coll_high_name, True)

                    if constraints_collection_name in bpy.data.collections:
                        remove_collection_by_name(context, constraints_collection_name, True)

                    rbdlab.filtered_target_collection = None
                    obj.hide_set(False)
                    obj.hide_render = False
                    select_object(context, obj)
                    set_active_object(context, obj)
                    # si tiene particulas se las quito:
                    if len(obj.particle_systems) > 0:
                        for ps in obj.particle_systems:
                            obj.particle_systems.active_index = obj.particle_systems.find(ps.name)
                            bpy.ops.object.particle_system_remove()
                    obj.display_type = 'TEXTURED'
                else:
                    self.report({'WARNING'}, "The original object: " + k + " not are avalidable!")
                    # return {'CANCELLED'}

            # para que no exploten quitamos de la ecuacion los
            # rigidbody de los chunks eliminados
            if "RigidBodyWorld" in bpy.data.collections:
                for obj in removed_chunks:
                    bpy.data.collections["RigidBodyWorld"].objects.unlink(obj)
        else:
            self.report({'WARNING'}, "Not target colection!")
            return {'CANCELLED'}

        return {'FINISHED'}
