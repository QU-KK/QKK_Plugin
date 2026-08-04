import bpy

import random
from typing import List
from datetime import datetime
from collections import defaultdict
from bpy.types import Operator, Object
from bpy.props import FloatProperty, EnumProperty
from ...addon.naming import RBDLabNaming
from ...addon.paths import RBDLabPreferences
from ...Global.functions import set_shading_color
from ..constraints.detect import calcute_chunks_neighbors


class RAND_OT_color(Operator):
    bl_idname = "rbdlab.randcolor"
    bl_label = "Random Color"
    bl_description = "Assign a random colour to your collection"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        scn = context.scene
        rbdlab = scn.rbdlab

        tcoll_list = rbdlab.lists.target_coll_list
        tcoll = tcoll_list.active

        def randColor(context):
            addon_preferences = RBDLabPreferences.get_prefs(context)
            rand_color_between_from = addon_preferences.rand_color_between_from
            rand_color_between_to = addon_preferences.rand_color_between_to

            rand_color = [
                random.uniform(
                    rand_color_between_from,
                    rand_color_between_to),
                random.uniform(
                    rand_color_between_from,
                    rand_color_between_to),
                random.uniform(
                    rand_color_between_from,
                    rand_color_between_to
                ), 1.0]
            
            return rand_color
        
        def add_color_per_chunks_froms(context, target_collections):

            ob_by_from: dict[str, List[Object]] = defaultdict(list)
            
            all_chunks = set([ob for target_coll in target_collections for ob in target_coll.objects])
            
            for ob in all_chunks:
                from_name = ob.get(RBDLabNaming.FROM)
                if from_name:
                    ob_by_from[from_name].append(ob)
            
            properties_to_skip = [
                RBDLabNaming.PASSIVE,
                RBDLabNaming.RBD_SEL_KINEMATIC,
                RBDLabNaming.INNER_EMISOR,
                RBDLabNaming.ACTIVATORS_OBJECTS,
                RBDLabNaming.ACETONABLE,
                RBDLabNaming.CHUNK_EXTRACTED
            ]
            
            for chunks in ob_by_from.values():
                # por cada from creo un color random:
                rand_color = randColor(context)
                
                # y se los aplicamos a sus chunks:
                for ob in chunks:
                    ob.color_stack.overwrite_first_color(rand_color)
                    
                    custom_properties = list(ob.keys())
                    intersection = set(custom_properties) & set(properties_to_skip)
                    if len(intersection) > 0:
                        continue
                    
                    ob.color = rand_color
        
        if tcoll:
            set_shading_color(context, color_type='OBJECT')

            all_colls = [tcoll]

            if RBDLabNaming.SUFIX_LOW in tcoll.name:
                coll_high_name = tcoll.name.replace(RBDLabNaming.SUFIX_LOW, RBDLabNaming.SUFIX_HIGH)
            else:
                coll_high_name = tcoll.name + RBDLabNaming.SUFIX_HIGH

            coll_high = bpy.data.collections.get(coll_high_name)
            if coll_high:
                all_colls.append(coll_high)

            add_color_per_chunks_froms(context, all_colls)

        return {'FINISHED'}


class CLEAR_ALL_OT_attributes(Operator):
    bl_idname = "rbdlab.clear_attr"
    bl_label = "Clear All Attributes"
    bl_description = "Clear All RBDLab attributes"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        rbdlab = context.scene.rbdlab

        if rbdlab.filtered_target_collection:
            coll_name = rbdlab.filtered_target_collection.name
            if coll_name:
                for ob in rbdlab.filtered_target_collection.objects:

                    if ob.type != 'MESH':
                        continue
                    if not ob.visible_get():
                        continue

                    custom_properties = list(ob.keys())
                    for cp in custom_properties:
                        cpl = cp.lower()

                        # borrando nuestras custom properties:
                        if cpl.startswith("rbdlab"):
                            del ob[cpl]

                        # borrando custom properties de jfran:
                        elif cpl.startswith("neighbour_") or cp == "temp__frame_start":
                            del ob[cp]

                if RBDLabNaming.CMPUTD_VELOCITIES in rbdlab.filtered_target_collection:
                    del rbdlab.filtered_target_collection[RBDLabNaming.CMPUTD_VELOCITIES]

        return {'FINISHED'}

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)

    def draw(self, context):
        layout = self.layout
        col = layout.column()
        col.label(text="I am aware and understand what this feature is used for.")
        col.label(text="Do you wish to continue?")


class CLEAR_ALL_OT_motions(Operator):
    bl_idname = "rbdlab.clear_motions"
    bl_label = "Clear Motions"
    bl_description = "Clear Motions"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        scn = context.scene
        rbdlab = scn.rbdlab

        tcoll = rbdlab.filtered_target_collection
        if tcoll:
            if tcoll.name:
                for ob in rbdlab.filtered_target_collection.objects:
                    if ob.type == 'MESH' and ob.visible_get():
                        ob.rbdlab.clear_motions()

                # # OLD:
                # for ob in bpy.data.collections[coll_name].objects:
                #         custom_properties = list(ob.keys())
                #         for cp in custom_properties:
                #             cpl = cp.lower()
                #             if cpl == "rbdlab_motions":
                #                 del ob[cpl]

        return {'FINISHED'}

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)

    def draw(self, context):
        layout = self.layout
        col = layout.column()
        col.label(text="I am aware and understand what this feature is used for.")
        col.label(text="Do you wish to continue?")


# class REMOVE_ALL_OT_less_than_tree_verts(Operator):
#     bl_idname = "rbdlab.rm_obs_with_less_than_3_verts"
#     bl_label = "Remove les than 3 verts obs"
#     bl_description = "Remove les than 3 verts obs"
#     bl_options = {'REGISTER', 'UNDO'}

#     def execute(self, context):
#         start = datetime.now()
#         scn = context.scene
#         rbdlab = scn.rbdlab

#         tcoll = rbdlab.filtered_target_collection
#         if tcoll:
#             tcoll_name = tcoll.name
#             if tcoll_name:
#                 data = bpy.data

#                 previous_mode = rbdlab.low_or_high_visibility_viewport

#                 rbdlab.low_or_high_visibility_viewport = 'Low'

#                 print("Clean objects with less than 3 vertices in Low collection")
#                 low_chunks = [ob for ob in rbdlab.filtered_target_collection.objects
#                               if ob.type == 'MESH' and ob.visible_get()]

#                 to_rm_lows = [ob for ob in low_chunks if len(ob.data.vertices) <= 3]
#                 [data.objects.remove(obj) for obj in to_rm_lows]

#                 if RBDLabNaming.SUFIX_LOW in tcoll.name:
#                     coll_high_name = tcoll_name.replace(RBDLabNaming.SUFIX_LOW, RBDLabNaming.SUFIX_HIGH)
#                 else:
#                     coll_high_name = tcoll_name + RBDLabNaming.SUFIX_HIGH

#                 if coll_high_name:

#                     rbdlab.low_or_high_visibility_viewport = 'High'
#                     print("Clean objects with less than 3 vertices in High collection")

#                     high_chunks = [ob for ob in bpy.data.collections[coll_high_name].objects
#                                    if ob.type == 'MESH' and ob.visible_get()]

#                     if high_chunks:
#                         to_rm_highs = [ob for ob in high_chunks if len(ob.data.vertices) <= 3]
#                         [data.objects.remove(ob) for ob in to_rm_highs]

#                 rbdlab.low_or_high_visibility_viewport = previous_mode

#         self.report(
#             {'INFO'},
#             "rm_obs_with_less_than_3_verts Removed: " + str(len(to_rm_lows) + len(to_rm_highs)) + " objects in " +
#             str(datetime.now() - start))

#         return {'FINISHED'}


class CLEAR_ALL_OT_velocities(Operator):
    bl_idname = "rbdlab.clear_velocities"
    bl_label = "Clear Velocities"
    bl_description = "Clear Velocities"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        rbdlab = context.scene.rbdlab

        if rbdlab.filtered_target_collection:
            coll_name = rbdlab.filtered_target_collection.name
            if coll_name:

                for obj in bpy.data.collections[coll_name].objects:
                    if obj.type == 'MESH' and obj.visible_get():
                        custom_properties = list(obj.keys())
                        for cp in custom_properties:
                            cpl = cp.lower()
                            if cpl == RBDLabNaming.VELOCITIES:
                                del obj[cpl]

                if RBDLabNaming.CMPUTD_VELOCITIES in rbdlab.filtered_target_collection:
                    del rbdlab.filtered_target_collection[RBDLabNaming.CMPUTD_VELOCITIES]

        return {'FINISHED'}

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)

    def draw(self, context):
        layout = self.layout
        col = layout.column()
        col.label(text="I am aware and understand what this feature is used for.")
        col.label(text="Do you wish to continue?")


class CLEAR_OT_rbo_in_limbo(Operator):
    bl_idname = "rbdlab.clear_rigidbody_objects_in_limbo"
    bl_label = "Clear RigidBody Objects in Limbo"
    bl_description = "Clear RigidBody Objects in Limbo"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        rb_coll = bpy.data.collections.get(RBDLabNaming.RBD_CONSTRAINTS)
        if rb_coll:
            for ob in rb_coll.objects:
                if ob.name not in context.view_layer.objects:
                    print("We remove the object " + ob.name + " from the "+ RBDLabNaming.RBD_WORLD +" collection.")
                    rb_coll.objects.unlink(ob)
        
        return {'FINISHED'}


class CLEAR_OT_const_in_limbo(Operator):
    bl_idname = "rbdlab.clear_constraints_objects_in_limbo"
    bl_label = "Clear Constraints Objects in Limbo"
    bl_description = "Clear Constraints Objects in Limbo"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        rb_const_coll = bpy.data.collections.get(RBDLabNaming.RBD_CONSTRAINTS)
        if rb_const_coll:
            for ob in rb_const_coll.objects:
                if ob.name not in context.view_layer.objects:
                    print("We remove the object " + ob.name + " from the "+ RBDLabNaming.RBD_CONSTRAINTS +" collection.")
                    rb_const_coll.objects.unlink(ob)
        
        return {'FINISHED'}


class RECALCULATE_OT_neighbors(Operator):
    bl_idname = "rbdlab.recalculate_neighbors"
    bl_label = "Recompute Neighbors (Chunks Search)"
    bl_description = "Recompute Neighbors"
    bl_options = {'REGISTER', 'UNDO'}

    search_method: EnumProperty(
        name="Neighbor Search Method",
        items=(
            # ('VERT', 'Vertices', "Use nearest vertices. (PRECISE in organic patterns, don't use for brick walls)"),
            ('CYTHON', 'Automatic', "Use automatic method powered by Cython"),
            ('VERT_KDTREE', 'Vertices', "Use nearest vertices. (PRECISE in organic patterns, don't use for brick walls)"),
            # ('EDGE', 'Edges', "Use nearest edges. (SLOWER BUT PRECISE IN ALMOST EVERY CASE)"), # este es muy lento por eso lo desactivo
            ('BBOX', 'Bounding Box', "Use bounding box intersection between the chunks. (FASTEST, really nice for brick walls or similar)")
        ),
        default='CYTHON'
    )
    virtual_cube_threshold: FloatProperty(
        min=0.0001, 
        max=0.1, 
        default=0.001, 
        precision=4, 
        step=1 / 1000, 
        name="Neighbors Threshold",
        description="Distance threshold to consider a chunk is neighbor of another chunk"
    )

    def execute(self, context):
        scn = context.scene
        rbdlab = scn.rbdlab
        tcoll_list = rbdlab.lists.target_coll_list
        tcoll = tcoll_list.active

        if not tcoll:
            self.report({'ERROR'}, "Invalid target collection!")
            return {'CANCELLED'}
        
        # vertex_distance_threshold: float = 0.001
        chunks = tcoll_list.get_current_active_tcoll_valild_objects(context)

        if not chunks:
            self.report({'ERROR'}, "Chunks could not be obtained from target collection!")
            return {'CANCELLED'}

        # Cleanup old neighbors data.
        for chunk in chunks:
            for coll_neighbor in chunk.coll_neighbor_chunks:
                coll_neighbor.clear()
            chunk.coll_neighbor_chunks.clear()

        calcute_chunks_neighbors(
            context,
            chunk_list=chunks,
            search_method=self.search_method,
            virtual_cube_threshold=self.virtual_cube_threshold,
            # vertex_distance_threshold=vertex_distance_threshold
        )

        return {'FINISHED'}
    
    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self, width=235)

    def draw(self, context):

        layout = self.layout
        layout.scale_y = 1.3
        
        scn = context.scene
        rbdlab = scn.rbdlab
        rbdlab_const = rbdlab.constraints

        col = layout.column(align=True)
        col.row(align=True).prop(self, "search_method", expand=True, text='Method')


        if self.search_method != 'BBOX':
            col.prop(self, "virtual_cube_threshold", slider=True, text="Threshold")
        else:
            col.prop(rbdlab_const, "bbox_offset_unified")  
