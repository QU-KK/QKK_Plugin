import bpy
import ast
# import uuid
from bpy.types import Operator
from ....Global.particles import create_particle_system
from ....Global.functions import (
    create_modifier,
    move_objects_to_collection,
    hide_collection_in_viewport,
    remove_collection_if_is_empty,
    select_inner_faces_by_attribute
)
from ....Global.basics import enter_object_mode, enter_edit_mode, select_object, set_active_object, deselect_all_objects
from ....addon.naming import RBDLabNaming


class CommonMethods:

    def restore_previous_materials(self, context, rbdlab):
        objects_without_inner_mat = []
        # detecto los objectos que no tienen inner mat:
        for obj in rbdlab.filtered_target_collection.objects:
            have_inner_mat = [RBDLabNaming.INNER_MAT_TAG in mat.material for mat in obj.material_slots
                              if mat.material is not None]
            if len(have_inner_mat) > 0:
                if not any(have_inner_mat):
                    objects_without_inner_mat.append(obj)

        if len(objects_without_inner_mat) > 0:
            set_active_object(context, objects_without_inner_mat[0])
            select_inner_faces_by_attribute(context, objects_without_inner_mat)

            for obj in objects_without_inner_mat:
                obj.select_set(True)

            active_object = objects_without_inner_mat[0]
            set_active_object(context, active_object)

            bpy.ops.object.material_slot_add()
            if RBDLabNaming.TMP_PREVIOUS_MAT_NAME in active_object:
                mat_target_name = active_object[RBDLabNaming.TMP_PREVIOUS_MAT_NAME]
                if mat_target_name in bpy.data.materials:
                    target_material = bpy.data.materials[mat_target_name]
                    active_object.material_slots[-1].material = target_material

            # se los transfiero al resto:
            bpy.ops.object.make_links_data(type='MATERIAL')

            # seteo el ultimo como material activo:
            for obj in objects_without_inner_mat:
                obj.active_material_index = len(obj.material_slots)-1
                if RBDLabNaming.TMP_PREVIOUS_MAT_NAME in obj:
                    del obj[RBDLabNaming.TMP_PREVIOUS_MAT_NAME]

            bpy.ops.object.material_slot_assign()

            enter_object_mode(context)
            deselect_all_objects(context)


def remove_previous_materials(valid_objects):
    for obj in valid_objects:
        for mat in obj.data.materials:
            if mat:
                if mat.name.endswith(RBDLabNaming.SUFIX_INNER_MAT):
                    idx = obj.data.materials.find(mat.name)
                    if idx:
                        obj[RBDLabNaming.TMP_PREVIOUS_MAT_NAME] = mat.name
                        obj.data.materials.pop(index=idx)


def post_settings(rbdlab) -> None:
    rbdlab.rbdlab_cf_source_limit = 200
    rbdlab.scatter.edge_count = 15000


def auto_naming_single_output_collection(rbdlab) -> None:
    # auto name output single collection:
    if rbdlab.use_single_collection_name:
        if rbdlab.filtered_target_collection:
            current_coll_name = rbdlab.filtered_target_collection.name
            if current_coll_name:
                # rbdlab.rbdlab_cf_collection_name = current_coll_name.replace(RBDLabNaming.SUFIX_LOW, "") + \
                #     RBDLabNaming.SUFIX_EDGE_FRACTURE + "_" + rbdlab.ui.edge_methods.title() + "_" + str(uuid.uuid4())[:8]
                rbdlab.rbdlab_cf_collection_name = current_coll_name.replace(RBDLabNaming.SUFIX_LOW, "") + \
                    RBDLabNaming.SUFIX_EDGE_FRACTURE


class SCATTER_OT_extract_edges_all(Operator):
    bl_idname = "rbdlab.scatter_edges_all"
    bl_label = "Scatter by Edges"
    bl_description = "Add Scatter by Edges"
    bl_options = {'REGISTER', 'UNDO'}

    @staticmethod
    def extract(valid_objects: list, context, method="simple"):
        ''' All '''
        all_previous_objects = [obj.name for obj in context.view_layer.objects]
        deselect_all_objects(context)

        for obj in valid_objects:
            select_object(context, obj)

        if context.selected_objects:
            set_active_object(context, valid_objects[0])

        enter_edit_mode(context)
        bpy.ops.mesh.select_all(action='SELECT')

        context.scene.tool_settings.use_mesh_automerge = False
        # duplico por y separo por seleccion:
        bpy.ops.mesh.duplicate()
        bpy.ops.mesh.separate(type='SELECTED')

        # volvemos a object mode
        enter_object_mode(context)

        new_objects = [obj for obj in context.view_layer.objects if obj.name not in all_previous_objects]

        if new_objects:
            return new_objects
        else:
            return []

    def simple_method(self, context, rbdlab, coll_name, valid_objects):
        ''' All '''

        if "high" not in coll_name:

            new_objects = self.extract(valid_objects, context)

            if new_objects:

                deselect_all_objects(context)

                for obj in new_objects:
                    select_object(context, obj)

                set_active_object(context, new_objects[0])

                enter_edit_mode(context)
                bpy.ops.mesh.select_all(action='SELECT')
                bpy.ops.mesh.dissolve_limited()
                bpy.ops.mesh.select_all(action='SELECT')
                bpy.ops.mesh.delete(type='ONLY_FACE')
                enter_object_mode(context)

                org_chunk_loc = {}
                for obj in valid_objects:
                    org_chunk_loc[obj.name] = obj.matrix_world

                for obj in new_objects:

                    if "rbdlab_fracture_helper" not in obj:
                        obj["rbdlab_fracture_helper"] = True
                        obj["rbdlab_fracture_helper_simple"] = True

                    mw = obj.matrix_world
                    keys_list = list(org_chunk_loc.keys())
                    values_list = list(org_chunk_loc.values())
                    if mw not in values_list:
                        continue
                    father_name = keys_list[values_list.index(mw)]
                    father_obj = context.scene.objects[father_name]
                    # fast parent:
                    obj.parent = father_obj
                    obj.matrix_world = father_obj.matrix_world.copy()

                # damos grosor:
                bpy.ops.object.convert(target='CURVE')

                for obj in new_objects:
                    obj.data.bevel_depth = 0.18
                    obj.data.use_fill_caps = True
                    obj.display_type = 'WIRE'
                    obj.color = [1.000000, 1.000000, 1.000000, 1.000000]

        else:
            self.report({'WARNING'}, "No high collections are supported!")
            return {'CANCELLED'}

    def organic_method(self, context, rbdlab, coll_name, valid_objects):
        ''' All '''

        if "high" not in coll_name:

            new_objects = self.extract(valid_objects, context)

            if new_objects:

                deselect_all_objects(context)

                for obj in new_objects:
                    select_object(context, obj)

                set_active_object(context, new_objects[0])
                bpy.ops.object.join()
                helper = context.selected_objects[0]

                enter_edit_mode(context)
                bpy.ops.mesh.select_all(action='SELECT')
                bpy.ops.mesh.dissolve_limited()
                bpy.ops.mesh.select_all(action='SELECT')
                bpy.ops.mesh.delete(type='ONLY_FACE')
                enter_object_mode(context)

                org_chunk_loc = {}
                for obj in valid_objects:
                    org_chunk_loc[obj.name] = obj.matrix_world

                obj_original = context.view_layer.objects[valid_objects[0][RBDLabNaming.FROM]]
                obj_original.hide_set(False)
                deselect_all_objects(context)
                select_object(context, obj_original)
                bpy.ops.object.duplicate()
                obj_original.hide_set(True)
                obj_original = context.selected_objects[0]
                obj_original.color = valid_objects[0].color
                obj_original.display_type = 'TEXTURED'
                obj_original.hide_render = False
                set_active_object(context, obj_original)
                move_objects_to_collection(context, [obj_original], coll_name)

                if "rbdlab_fracture_helper" not in helper:
                    helper["rbdlab_fracture_helper"] = True
                    helper["rbdlab_fracture_helper_organic"] = True

                backup_coll_name = coll_name + "_pieces_backup"
                move_objects_to_collection(context, valid_objects, backup_coll_name)
                hide_collection_in_viewport(context, backup_coll_name)

                for mod in obj_original.modifiers:
                    if mod.type == 'PARTICLE_SYSTEM':
                        obj_original.modifiers.remove(mod)

                select_object(context, helper)
                set_active_object(context, obj_original)

                # fast parent:
                mw = helper.matrix_world
                helper.parent = obj_original
                # obj.matrix_world = obj_original.matrix_world.copy()
                helper.matrix_world = mw

                # damos grosor:
                bpy.ops.object.convert(target='CURVE')

                helper.data.bevel_depth = 0.18
                helper.data.use_fill_caps = True
                helper.display_type = 'WIRE'
                helper.color = [1.000000, 1.000000, 1.000000, 1.000000]

        else:
            self.report({'WARNING'}, "No high collections are supported!")
            return {'CANCELLED'}

    def execute(self, context):
        ''' All '''
        type = bpy.context.scene.rbdlab.ui.edge_methods_type

        rbdlab = context.scene.rbdlab

        if rbdlab.filtered_target_collection:
            coll_name = rbdlab.filtered_target_collection.name
            if coll_name:

                valid_objects = [obj for obj in rbdlab.filtered_target_collection.objects
                                 if obj.type == 'MESH' and obj.visible_get()]

                if valid_objects:

                    if type == 'SIMPLE':
                        self.simple_method(context, rbdlab, coll_name, valid_objects)
                    else:
                        self.organic_method(context, rbdlab, coll_name, valid_objects)

                    rbdlab.filtered_target_collection["edge_extracted_all"] = True
                    rbdlab.rbdlab_cf_source = {'PARTICLE_CHILD'}

                else:
                    self.report({'WARNING'}, "No valid objects in target collection!")
                    return {'CANCELLED'}

        deselect_all_objects(context)
        return {'FINISHED'}


class SCATTER_OT_extract_edges_all_cancel(Operator, CommonMethods):
    bl_idname = "rbdlab.scatter_edges_all_cancel"
    bl_label = "Cancel Scatter by Edges"
    bl_description = "Cancel Scatter by Edges"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        ''' Cancel All Inners '''
        rbdlab = context.scene.rbdlab

        if rbdlab.filtered_target_collection:
            coll_name = rbdlab.filtered_target_collection.name
            if coll_name:

                valid_objects = [obj for obj in context.view_layer.objects if obj.visible_get()]

                deselect_all_objects(context)

                if rbdlab.ui.edge_methods_type == 'SIMPLE':
                    tag_to_check = "rbdlab_fracture_helper_simple"
                else:
                    tag_to_check = "rbdlab_fracture_helper_organic"

                if valid_objects:

                    self.restore_previous_materials(context, rbdlab)

                    for obj in valid_objects:
                        if "rbdlab_fracture_helper" not in obj:
                            continue
                        if tag_to_check not in obj:
                            continue
                        if obj.parent is None:
                            continue
                        if obj.parent.name not in rbdlab.filtered_target_collection.objects:
                            continue
                        if rbdlab.ui.edge_methods_type == 'ORGANIC':
                            obj.parent.select_set(True)

                        obj.select_set(True)

                if len(context.selected_objects) > 0:
                    bpy.ops.object.delete(use_global=False)

                if rbdlab.ui.edge_methods_type == 'ORGANIC':
                    destination_collection = coll_name + "_pieces_backup"
                    if destination_collection in bpy.data.collections:
                        move_objects_to_collection(
                            context, bpy.data.collections[destination_collection].objects, coll_name, False)
                        remove_collection_if_is_empty(context, destination_collection)

            if "edge_extracted_all" in rbdlab.filtered_target_collection:
                del rbdlab.filtered_target_collection["edge_extracted_all"]
            if "edge_extracted_all_accepted" in rbdlab.filtered_target_collection:
                del rbdlab.filtered_target_collection["edge_extracted_all_accepted"]

        deselect_all_objects(context)
        return {'FINISHED'}


class SCATTER_OT_extract_edges_all_accept(Operator):
    bl_idname = "rbdlab.scatter_edges_all_accept"
    bl_label = "Accept All Edges Method"
    bl_description = "Accept All Edges Method"
    bl_options = {'REGISTER', 'UNDO'}

    @staticmethod
    def simple_method(context, rbdlab, valid_objects, ps_name, ps_type, display_size, ps_count):
        deselect_all_objects(context)

        for obj in valid_objects:
            if obj.children:
                select_object(context, obj.children[0])

        if context.selected_objects:
            helpers = context.selected_objects
            set_active_object(context, helpers[0])

            bpy.ops.object.convert(target='MESH')

            for helper_object in helpers:
                if ps_name not in helper_object.particle_systems:

                    create_particle_system(
                        context,
                        helper_object,
                        ps_name,
                        ps_type=ps_type,
                        ps_count=ps_count,
                        display_size=display_size,
                        frame_end=1,
                        use_modifier_stack=True,
                        render_type='HALO',
                        physics_type='NO',
                        edge_method=True,
                    )

                    # ps = helper_object.particle_systems[ps_name].settings
                    # ps.use_modifier_stack = True
                    # ps.frame_end = 1

    @staticmethod
    def organic_method(context, rbdlab, valid_objects, ps_name, ps_type, display_size, ps_count):
        deselect_all_objects(context)

        children = None

        deselect_all_objects(context)

        obj = valid_objects[0]

        if obj.children:
            children = obj.children[0]
            select_object(context, children)

        if children:
            set_active_object(context, children)
            bpy.ops.object.convert(target='MESH')

            if ps_name not in children.particle_systems:
                create_particle_system(
                    context,
                    children,
                    ps_name,
                    ps_type=ps_type,
                    ps_count=ps_count,
                    display_size=display_size,
                    frame_end=1,
                    use_modifier_stack=True,
                    render_type='HALO',
                    physics_type='NO',
                    edge_method=True,
                )
                # ps = children.particle_systems[ps_name].settings
                # ps.use_modifier_stack = True
                # ps.frame_end = 1

    def execute(self, context):
        ''' Accept All '''
        rbdlab = context.scene.rbdlab
        type = rbdlab.ui.edge_methods_type

        ps_name = "Particle_Scatter"
        ps_type = 'VOLUME'
        dps_size = 0.018
        ps_count = 1000

        if rbdlab.filtered_target_collection:
            coll_name = rbdlab.filtered_target_collection.name
            if coll_name:

                if context.scene.frame_current != context.scene.frame_start:
                    context.scene.frame_current = context.scene.frame_start

                valid_objects = [obj for obj in rbdlab.filtered_target_collection.objects
                                 if obj.type == 'MESH' and obj.visible_get()]

                if valid_objects:
                    if type == 'SIMPLE':
                        self.simple_method(context, rbdlab, valid_objects, ps_name, ps_type, dps_size, ps_count)
                        rbdlab.use_single_collection_name = True
                    else:
                        self.organic_method(context, rbdlab, valid_objects, ps_name, ps_type, dps_size, ps_count)

                    if rbdlab.ui.edge_methods_type == 'SIMPLE':
                        rbdlab.use_single_collection_name = True

                    rbdlab.filtered_target_collection["edge_extracted_all_accepted"] = True
                    rbdlab.rbdlab_cf_source = {'PARTICLE_CHILD'}

                    remove_previous_materials(valid_objects)

                    deselect_all_objects(context)
                    for obj in rbdlab.filtered_target_collection.objects:
                        if obj.children:
                            select_object(context, obj)
                            if RBDLabNaming.FROM_EDGE_FRACTURE not in obj:
                                obj[RBDLabNaming.FROM_EDGE_FRACTURE] = True
                            # le quito los inner mats:
                            for mat in obj.material_slots:
                                if mat.material:
                                    if RBDLabNaming.INNER_MAT_TAG not in mat.material:
                                        continue
                                    obj[RBDLabNaming.TMP_PREVIOUS_MAT_NAME] = mat.name
                                    obj.data.materials.pop(index=obj.material_slots.find(mat.name))

                    post_settings(rbdlab)
                    auto_naming_single_output_collection(rbdlab)

                else:
                    self.report({'WARNING'}, "No valid objects detected!")
                    return {'CANCELLED'}

        # deselect_all_objects(context)
        return {'FINISHED'}


class SCATTER_OT_extract_edges_inners(Operator):
    bl_idname = "rbdlab.scatter_edges_inners"
    bl_label = "Scatter by Edges"
    bl_description = "Add Scatter by Edges"
    bl_options = {'REGISTER', 'UNDO'}

    @staticmethod
    def extract(valid_objects: list, context):
        ''' Inners '''
        deselect_all_objects(context)

        set_active_object(context, valid_objects[0])

        select_inner_faces_by_attribute(context, valid_objects)

        context.scene.tool_settings.use_mesh_automerge = False

        # duplico por y separo por seleccion:
        bpy.ops.mesh.duplicate()
        bpy.ops.mesh.separate(type='SELECTED')

        # volvemos a object mode
        enter_object_mode(context)

        return [obj for obj in context.selected_objects if obj not in valid_objects]

    def simple_method(self, context, rbdlab, coll_name, valid_objects):
        ''' Inners '''

        if "high" not in coll_name:

            new_objects = self.extract(valid_objects, context)

            if new_objects:

                deselect_all_objects(context)
                for obj in new_objects:
                    obj.select_set(True)

                set_active_object(context, new_objects[0])

                enter_edit_mode(context)
                bpy.ops.mesh.select_all(action='SELECT')
                bpy.ops.mesh.dissolve_limited()
                bpy.ops.mesh.select_all(action='SELECT')
                bpy.ops.mesh.delete(type='ONLY_FACE')
                enter_object_mode(context)

                org_chunk_loc = {}
                for obj in valid_objects:
                    org_chunk_loc[obj.name] = obj.matrix_world

                for obj in new_objects:
                    if "rbdlab_fracture_helper" not in obj:
                        obj["rbdlab_fracture_helper"] = True
                        obj["rbdlab_fracture_helper_simple"] = True

                    mw = obj.matrix_world
                    keys_list = list(org_chunk_loc.keys())
                    values_list = list(org_chunk_loc.values())
                    if mw not in values_list:
                        continue
                    father_name = keys_list[values_list.index(mw)]
                    father_obj = context.scene.objects[father_name]
                    # fast parent:
                    obj.parent = father_obj
                    obj.matrix_world = father_obj.matrix_world.copy()

                bpy.ops.object.convert(target='CURVE')

                for obj in new_objects:
                    obj.data.bevel_depth = 0.18
                    obj.data.use_fill_caps = True
                    obj.display_type = 'WIRE'
                    obj.color = [1.000000, 1.000000, 1.000000, 1.000000]

        else:
            self.report({'WARNING'}, "No high collections are supported!")
            return {'CANCELLED'}

    def organic_method(self, context, rbdlab, coll_name, valid_objects):
        ''' Inners '''

        if "high" not in coll_name:

            new_objects = self.extract(valid_objects, context)

            if new_objects:

                deselect_all_objects(context)
                for obj in new_objects:
                    obj.select_set(True)

                set_active_object(context, new_objects[0])
                bpy.ops.object.join()
                helper = context.selected_objects[0]

                enter_edit_mode(context)
                bpy.ops.mesh.select_all(action='SELECT')
                bpy.ops.mesh.dissolve_limited()
                bpy.ops.mesh.select_all(action='SELECT')
                bpy.ops.mesh.delete(type='ONLY_FACE')
                enter_object_mode(context)

                obj_original = context.view_layer.objects[valid_objects[0][RBDLabNaming.FROM]]
                obj_original.hide_set(False)
                deselect_all_objects(context)
                select_object(context, obj_original)
                bpy.ops.object.duplicate()
                obj_original.hide_set(True)
                obj_original = context.selected_objects[0]
                obj_original.color = valid_objects[0].color
                obj_original.display_type = 'TEXTURED'
                obj_original.hide_render = False
                set_active_object(context, obj_original)
                move_objects_to_collection(context, [obj_original], coll_name)

                if "rbdlab_fracture_helper" not in helper:
                    helper["rbdlab_fracture_helper"] = True
                    helper["rbdlab_fracture_helper_organic"] = True

                backup_coll_name = coll_name + "_pieces_backup"
                move_objects_to_collection(context, valid_objects, backup_coll_name)
                hide_collection_in_viewport(context, backup_coll_name)

                for mod in obj_original.modifiers:
                    if mod.type == 'PARTICLE_SYSTEM':
                        obj_original.modifiers.remove(mod)

                select_object(context, helper)
                set_active_object(context, obj_original)

                # fast parent:
                mw = helper.matrix_world
                helper.parent = obj_original
                # obj.matrix_world = obj_original.matrix_world.copy()
                helper.matrix_world = mw

                # damos grosor:
                bpy.ops.object.convert(target='CURVE')

                helper.data.bevel_depth = 0.18
                helper.data.use_fill_caps = True
                helper.display_type = 'WIRE'
                helper.color = [1.000000, 1.000000, 1.000000, 1.000000]

        else:
            self.report({'WARNING'}, "No high collections are supported!")
            return {'CANCELLED'}

    def execute(self, context):
        ''' Inners '''
        rbdlab = context.scene.rbdlab
        type = rbdlab.ui.edge_methods_type

        if rbdlab.filtered_target_collection:
            coll_name = rbdlab.filtered_target_collection.name
            if coll_name:

                valid_objects = [obj for obj in rbdlab.filtered_target_collection.objects
                                 if obj.type == 'MESH' and obj.visible_get()]

                if valid_objects:

                    if type == 'SIMPLE':
                        self.simple_method(context, rbdlab, coll_name, valid_objects)
                    else:
                        self.organic_method(context, rbdlab, coll_name, valid_objects)

                    rbdlab.filtered_target_collection["edge_extracted_inners"] = True
                    rbdlab.rbdlab_cf_source = {'PARTICLE_CHILD'}

                else:
                    self.report({'WARNING'}, "No valid objects in target collection!")
                    return {'CANCELLED'}

        deselect_all_objects(context)
        return {'FINISHED'}


class SCATTER_OT_extract_edges_inners_cancel(Operator, CommonMethods):
    bl_idname = "rbdlab.scatter_edges_inners_cancel"
    bl_label = "Cancel Scatter by Edges"
    bl_description = "Cancel Scatter by Edges"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        ''' Cancel Inners '''
        rbdlab = context.scene.rbdlab

        if rbdlab.filtered_target_collection:
            coll_name = rbdlab.filtered_target_collection.name
            if coll_name:

                valid_objects = [obj for obj in context.view_layer.objects if obj.visible_get()]

                deselect_all_objects(context)

                if rbdlab.ui.edge_methods_type == 'SIMPLE':
                    tag_to_check = "rbdlab_fracture_helper_simple"
                else:
                    tag_to_check = "rbdlab_fracture_helper_organic"

                if valid_objects:

                    self.restore_previous_materials(context, rbdlab)

                    for obj in valid_objects:
                        if "rbdlab_fracture_helper" not in obj:
                            continue
                        if tag_to_check not in obj:
                            continue
                        if obj.parent is None:
                            continue
                        if obj.parent.name not in rbdlab.filtered_target_collection.objects:
                            continue
                        if rbdlab.ui.edge_methods_type == 'ORGANIC':
                            obj.parent.select_set(True)

                        obj.select_set(True)

                if len(context.selected_objects) > 0:
                    bpy.ops.object.delete(use_global=False)

                if rbdlab.ui.edge_methods_type == 'ORGANIC':
                    destination_collection = coll_name + "_pieces_backup"
                    if destination_collection in bpy.data.collections:
                        move_objects_to_collection(
                            context, bpy.data.collections[destination_collection].objects, coll_name, False)
                        remove_collection_if_is_empty(context, destination_collection)

            if "edge_extracted_inners" in rbdlab.filtered_target_collection:
                del rbdlab.filtered_target_collection["edge_extracted_inners"]
            if "edge_extracted_inners_accepted" in rbdlab.filtered_target_collection:
                del rbdlab.filtered_target_collection["edge_extracted_inners_accepted"]

        deselect_all_objects(context)
        return {'FINISHED'}


class SCATTER_OT_extract_edges_inners_accept(Operator):
    bl_idname = "rbdlab.scatter_edges_inners_accept"
    bl_label = "Accept Inners Edges Method"
    bl_description = "Accept Inners Edges Method"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        ''' Accept Inners '''
        rbdlab = context.scene.rbdlab

        ps_name = "Particle_Scatter"

        if rbdlab.filtered_target_collection:
            coll_name = rbdlab.filtered_target_collection.name
            if coll_name:

                if context.scene.frame_current != context.scene.frame_start:
                    context.scene.frame_current = context.scene.frame_start

                deselect_all_objects(context)
                valid_objects = [obj for obj in rbdlab.filtered_target_collection.objects
                                 if obj.type == 'MESH' and obj.visible_get()]

                if valid_objects:

                    for obj in valid_objects:
                        select_object(context, obj.children[0])

                    if context.selected_objects:
                        helpers = context.selected_objects
                        set_active_object(context, helpers[0])

                        bpy.ops.object.convert(target='MESH')

                        for helper_object in helpers:
                            if ps_name not in helper_object.particle_systems:
                                create_particle_system(
                                    context,
                                    helper_object,
                                    ps_name,
                                    ps_type='VOLUME',
                                    ps_count=1000,
                                    display_size=0.018,
                                    frame_end=1,
                                    use_modifier_stack=True,
                                    render_type='HALO',
                                    physics_type='NO',
                                    edge_method=True,
                                )
                                # ps = helper_object.particle_systems[ps_name].settings
                                # ps.use_modifier_stack = True
                                # ps.frame_end = 1

                    if rbdlab.ui.edge_methods_type == 'SIMPLE':
                        rbdlab.use_single_collection_name = True

                    rbdlab.filtered_target_collection["edge_extracted_inners_accepted"] = True
                    bpy.context.scene.rbdlab.rbdlab_cf_source = {'PARTICLE_CHILD'}

                    remove_previous_materials(valid_objects)

                    deselect_all_objects(context)
                    for obj in rbdlab.filtered_target_collection.objects:
                        if obj.children:
                            select_object(context, obj)
                            if RBDLabNaming.FROM_EDGE_FRACTURE not in obj:
                                obj[RBDLabNaming.FROM_EDGE_FRACTURE] = True
                            # le quito los inner mats:
                            for mat in obj.material_slots:
                                if mat.material:
                                    if RBDLabNaming.INNER_MAT_TAG not in mat.material:
                                        continue
                                    obj[RBDLabNaming.TMP_PREVIOUS_MAT_NAME] = mat.name
                                    obj.data.materials.pop(index=obj.material_slots.find(mat.name))

                    post_settings(rbdlab)
                    auto_naming_single_output_collection(rbdlab)

                else:
                    self.report({'WARNING'}, "No valid objects in target collection!")
                    return {'CANCELLED'}

        # deselect_all_objects(context)
        return {'FINISHED'}


class SCATTER_OT_extract_edges_innerfaces(Operator):
    bl_idname = "rbdlab.scatter_edges_innerfaces"
    bl_label = "Scatter by Edges"
    bl_description = "Add Scatter by Edges"
    bl_options = {'REGISTER', 'UNDO'}

    @staticmethod
    def extract(valid_objects: list, context):
        ''' Inner Faces '''
        deselect_all_objects(context)

        set_active_object(context, valid_objects[0])

        select_inner_faces_by_attribute(context, valid_objects)

        context.scene.tool_settings.use_mesh_automerge = False
        # duplico por y separo por seleccion:
        bpy.ops.mesh.duplicate()
        bpy.ops.mesh.separate(type='SELECTED')

        # volvemos a object mode
        enter_object_mode(context)

        return [obj for obj in context.selected_objects if obj not in valid_objects]

    def simple_method(self, context, rbdlab, coll_name, valid_objects, ps_name, ps_type, display_size, ps_count):
        ''' Inner Faces '''

        if "high" not in coll_name:

            new_objects = self.extract(valid_objects, context)

            if new_objects:

                deselect_all_objects(context)
                for obj in new_objects:
                    select_object(context, obj)

                set_active_object(context, new_objects[0])

                org_chunk_loc = {}
                for obj in valid_objects:
                    org_chunk_loc[obj.name] = obj.matrix_world

                for obj in new_objects:

                    if "rbdlab_fracture_helper" not in obj:
                        obj["rbdlab_fracture_helper"] = True

                    mw = obj.matrix_world
                    keys_list = list(org_chunk_loc.keys())
                    values_list = list(org_chunk_loc.values())
                    if mw not in values_list:
                        continue
                    father_name = keys_list[values_list.index(mw)]
                    father_obj = context.scene.objects[father_name]
                    # fast parent:
                    obj.parent = father_obj
                    obj.matrix_world = father_obj.matrix_world.copy()

                for helper_object in new_objects:

                    mod_decimate = create_modifier(helper_object, RBDLabNaming.DECIMATE, 'DECIMATE', 0)
                    mod_solidify = create_modifier(helper_object, RBDLabNaming.SOLIDIFY_MOD, 'SOLIDIFY', 1)
                    mod_remesh = create_modifier(helper_object, RBDLabNaming.REMESH, 'REMESH', 2)
                    mod_displace = create_modifier(helper_object, RBDLabNaming.DISPLACE, 'DISPLACE', 3)
                    mod_decimate.decimate_type = 'DISSOLVE'
                    mod_solidify.offset = 0.07
                    mod_solidify.thickness = 0.1
                    mod_remesh.voxel_size = 0.07
                    mod_displace.strength = 0.2
                    helper_object.display_type = 'WIRE'
                    helper_object.color = [1.000000, 1.000000, 1.000000, 1.000000]

                    if ps_name not in helper_object.particle_systems:
                        create_particle_system(
                            context,
                            helper_object,
                            ps_name,
                            ps_type=ps_type,
                            ps_count=ps_count,
                            display_size=display_size,
                            frame_end=1,
                            use_modifier_stack=True,
                            render_type='HALO',
                            physics_type='NO',
                            edge_method=True,
                        )
                        # ps = helper_object.particle_systems[ps_name].settings
                        # ps.use_modifier_stack = True
                        # ps.frame_end = 1
        else:
            self.report({'WARNING'}, "No high collections are supported!")
            return {'CANCELLED'}

    def organic_method(self, context, rbdlab, coll_name, valid_objects, ps_name, ps_type, display_size, ps_count):
        ''' Inner Faces '''

        if "high" not in coll_name:

            new_objects = self.extract(valid_objects, context)

            if new_objects:

                deselect_all_objects(context)

                for obj in new_objects:
                    select_object(context, obj)

                set_active_object(context, new_objects[0])
                bpy.ops.object.join()
                helper = context.selected_objects[0]

                obj_original = context.view_layer.objects[valid_objects[0][RBDLabNaming.FROM]]
                obj_original.hide_set(False)
                deselect_all_objects(context)
                select_object(context, obj_original)
                bpy.ops.object.duplicate()
                obj_original.hide_set(True)
                obj_original = context.selected_objects[0]
                obj_original.color = valid_objects[0].color
                obj_original.display_type = 'TEXTURED'
                obj_original.hide_render = False
                set_active_object(context, obj_original)
                move_objects_to_collection(context, [obj_original], coll_name)

                if "rbdlab_fracture_helper" not in helper:
                    helper["rbdlab_fracture_helper"] = True

                backup_coll_name = coll_name + "_pieces_backup"
                move_objects_to_collection(context, valid_objects, backup_coll_name)
                hide_collection_in_viewport(context, backup_coll_name)

                for mod in obj_original.modifiers:
                    if mod.type == 'PARTICLE_SYSTEM':
                        obj_original.modifiers.remove(mod)

                select_object(context, helper)
                set_active_object(context, obj_original)

                # fast parent:
                mw = helper.matrix_world
                helper.parent = obj_original
                # obj.matrix_world = obj_original.matrix_world.copy()
                helper.matrix_world = mw

                mod_decimate = create_modifier(helper, RBDLabNaming.DECIMATE, 'DECIMATE', 0)
                mod_solidify = create_modifier(helper, RBDLabNaming.SOLIDIFY_MOD, 'SOLIDIFY', 1)
                mod_remesh = create_modifier(helper, RBDLabNaming.REMESH, 'REMESH', 2)
                mod_displace = create_modifier(helper, RBDLabNaming.DISPLACE, 'DISPLACE', 3)
                mod_decimate.decimate_type = 'DISSOLVE'
                mod_solidify.offset = 0.07
                mod_solidify.thickness = 0.1
                mod_remesh.voxel_size = 0.07
                mod_displace.strength = 0.2
                helper.display_type = 'WIRE'
                helper.color = [1.000000, 1.000000, 1.000000, 1.000000]

                if ps_name not in helper.particle_systems:
                    create_particle_system(
                        context,
                        helper,
                        ps_name,
                        ps_type=ps_type,
                        ps_count=ps_count,
                        display_size=display_size,
                        frame_end=1,
                        use_modifier_stack=True,
                        render_type='HALO',
                        physics_type='NO',
                        edge_method=True,
                    )
                    # ps = helper.particle_systems[ps_name].settings
                    # ps.use_modifier_stack = True
                    # ps.frame_end = 1

    def execute(self, context):
        ''' Inner Faces '''
        rbdlab = context.scene.rbdlab
        type = rbdlab.ui.edge_methods_type

        if rbdlab.filtered_target_collection:
            coll_name = rbdlab.filtered_target_collection.name
            if coll_name:

                if context.scene.frame_current != context.scene.frame_start:
                    context.scene.frame_current = context.scene.frame_start

                ps_name = "Particle_Scatter"
                ps_type = 'VOLUME'
                dps_size = 0.018
                ps_count = 1000

                valid_objects = [obj for obj in rbdlab.filtered_target_collection.objects
                                 if obj.type == 'MESH' and obj.visible_get()]

                if valid_objects:

                    if type == 'SIMPLE':
                        self.simple_method(context, rbdlab, coll_name, valid_objects,
                                           ps_name, ps_type, dps_size, ps_count)
                    else:
                        self.organic_method(context, rbdlab, coll_name, valid_objects,
                                            ps_name, ps_type, dps_size, ps_count)

                    if rbdlab.ui.edge_methods_type == 'SIMPLE':
                        rbdlab.use_single_collection_name = True

                    rbdlab.filtered_target_collection["edge_extracted_innerfaces"] = True
                    bpy.context.scene.rbdlab.rbdlab_cf_source = {'PARTICLE_CHILD'}

                    deselect_all_objects(context)
                    for obj in rbdlab.filtered_target_collection.objects:
                        if obj.children:
                            select_object(context, obj)
                            if RBDLabNaming.FROM_EDGE_FRACTURE not in obj:
                                obj[RBDLabNaming.FROM_EDGE_FRACTURE] = True
                            # le quito los inner mats:
                            for mat in obj.material_slots:
                                if RBDLabNaming.INNER_MAT_TAG not in mat.material:
                                    continue
                                obj[RBDLabNaming.TMP_PREVIOUS_MAT_NAME] = mat.name
                                obj.data.materials.pop(index=obj.material_slots.find(mat.name))

                    post_settings(rbdlab)
                    auto_naming_single_output_collection(rbdlab)

                else:
                    self.report({'WARNING'}, "No valid objects in target collection!")
                    return {'CANCELLED'}

        # deselect_all_objects(context)
        return {'FINISHED'}


class SCATTER_OT_extract_edges_innerfaces_cancel(Operator, CommonMethods):
    bl_idname = "rbdlab.scatter_edges_innerfaces_cancel"
    bl_label = "Cancel Scatter by Edges"
    bl_description = "Cancel Scatter by Edges"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        ''' Cancel Inners Faces '''
        rbdlab = context.scene.rbdlab

        if rbdlab.filtered_target_collection:
            coll_name = rbdlab.filtered_target_collection.name
            if coll_name:

                valid_objects = [obj for obj in context.view_layer.objects if obj.visible_get()]

                deselect_all_objects(context)

                if valid_objects:

                    self.restore_previous_materials(context, rbdlab)

                    for obj in valid_objects:
                        if "rbdlab_fracture_helper" not in obj:
                            continue
                        if obj.parent is None:
                            continue
                        if obj.parent.name not in rbdlab.filtered_target_collection.objects:
                            continue
                        if rbdlab.ui.edge_methods_type == 'ORGANIC':
                            obj.parent.select_set(True)

                        obj.select_set(True)

                if len(context.selected_objects) > 0:
                    bpy.ops.object.delete(use_global=False)

                if rbdlab.ui.edge_methods_type == 'ORGANIC':
                    destination_collection = coll_name + "_pieces_backup"
                    if destination_collection in bpy.data.collections:
                        move_objects_to_collection(
                            context, bpy.data.collections[destination_collection].objects, coll_name, False)
                        remove_collection_if_is_empty(context, destination_collection)

            if "edge_extracted_innerfaces" in rbdlab.filtered_target_collection:
                del rbdlab.filtered_target_collection["edge_extracted_innerfaces"]

        deselect_all_objects(context)
        return {'FINISHED'}
