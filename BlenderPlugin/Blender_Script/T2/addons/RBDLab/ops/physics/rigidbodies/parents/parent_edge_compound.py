import bpy
import ast
from bpy.types import Operator
from .....Global.functions import (
    move_objects_to_collection,
    unhide_collection_in_viewport,
    # append_attribute_to_obj
)
from .....Global.basics import select_object, set_active_object, deselect_all_objects
from .....addon.naming import RBDLabNaming


class RBDLAB_OT_edges_parent(Operator):
    bl_idname = "rbdlab.edges_pyshics_parent"
    bl_label = "Parent"
    bl_description = "Parent"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        ''' Physics Parent '''
        rbdlab = context.scene.rbdlab

        if rbdlab.filtered_target_collection:
            if rbdlab.filtered_target_collection.name:
                coll_name = rbdlab.filtered_target_collection.name
                if coll_name:

                    valid_objects = [obj for obj in context.selected_objects
                                     if obj.type == 'MESH' and obj.visible_get()]

                    if valid_objects:

                        # C.object.hide_set(True)
                        # C.object.hide_render = True

                        obj_froms = []
                        hides_in_viewport = []  # False estan ocultos
                        # hides_in_render = []  # True estan ocultos
                        for obj in valid_objects:

                            if not RBDLabNaming.FROM in obj:
                                continue

                            obj_f = bpy.data.objects[obj[RBDLabNaming.FROM]]
                            if obj_f not in obj_froms:
                                obj_froms.append(obj_f)
                                hides_in_viewport.append(obj_f.visible_get())
                                # hides_in_render.append(obj_f.hide_render)

                        all_previous_objects = [obj.name for obj in context.view_layer.objects]

                        # prevengo que este hide o no selectable la collection de los originales:
                        originals_coll = bpy.data.collections.get(RBDLabNaming.ORIGINALS)
                        if originals_coll:
                            originals_coll.hide_select = False
                            unhide_collection_in_viewport(context, originals_coll.name)

                        {(
                            obj.hide_set(False),
                            setattr(obj, "hide_select", False),
                            obj.select_set(True)
                        ) for obj in obj_froms}

                        deselect_all_objects(context)
                        for i in range(len(obj_froms)):
                            obj_v_h = hides_in_viewport[i]
                            obj = obj_froms[i]
                            if not obj_v_h:
                                obj.hide_set(False)
                                select_object(context, obj)
                                # guardo su matrix world original:
                                org_mw = obj.matrix_world
                                obj[RBDLabNaming.ORIGINAL_MW] = "[" + str(list(org_mw[0])) + ", " + str(
                                    list(org_mw[1])) + ", " + str(list(org_mw[2])) + ", " + str(list(org_mw[3])) + "]"
                                obj[RBDLabNaming.ORIGINAL_LOC] = obj.location

                        if context.selected_objects:
                            set_active_object(context, context.selected_objects[0])
                            bpy.ops.object.duplicate()
                        else:
                            self.report({'WARNING'}, "[Parent]: No objects for duplicate!")
                            return {'CANCELLED'}

                        for i in range(len(obj_froms)):
                            obj = obj_froms[i]
                            obj_v_h = hides_in_viewport[i]
                            if not obj_v_h:
                                obj.hide_set(True)
                            else:
                                obj.hide_set(False)

                        new_objects = [obj for obj in context.view_layer.objects
                                       if obj.name not in all_previous_objects]

                        for obj in new_objects:

                            if "." in obj.name:
                                obj.name = obj.name.split(".")[0] + "_copy"
                            else:
                                obj.name = obj.name + "_copy"

                            obj[RBDLabNaming.NO_SHAPE_OBJ] = True
                            obj.display_type = 'WIRE'

                        set_active_object(context, context.selected_objects[0])
                        bpy.ops.rigidbody.objects_add(type='ACTIVE')
                        material_type = rbdlab.physics.rigidbodies.avalidable_mass.title().replace("#", " ")
                        bpy.ops.rigidbody.mass_calculate(material=material_type)

                        for obj in new_objects:
                            obj.rigid_body.collision_shape = 'COMPOUND'

                        if new_objects:
                            move_objects_to_collection(context, new_objects, coll_name)

                        # fast parent:
                        for obj in valid_objects:

                            # emparento los chunks selected a los compound copy
                            father_name = obj[RBDLabNaming.FROM] + "_copy"  # <- compound

                            father = context.view_layer.objects.get(father_name)

                            if father:
                                # append_attribute_to_obj(father, RBDLabNaming.COMPOUND_CHILDS, obj.name)

                                mw = obj.matrix_world
                                obj.parent = father
                                obj.matrix_world = mw

                                # emparento los fragmentos originales a los compound copy:
                                original = context.view_layer.objects[obj[RBDLabNaming.FROM]]
                                original.parent = father
                                original.matrix_world = father.matrix_world

                        # if "rbdlab_fracture_helper_simple" in rbdlab.filtered_target_collection:
                        #     del rbdlab.filtered_target_collection["rbdlab_fracture_helper_simple"]

                        if RBDLabNaming.EDGE_COMPOUND_PARENTED not in rbdlab.filtered_target_collection:
                            rbdlab.filtered_target_collection[RBDLabNaming.EDGE_COMPOUND_PARENTED] = True

                        return {'FINISHED'}
                    else:
                        self.report({'WARNING'}, "Not valid Objects in this Target Collection!")
                        return {'CANCELLED'}
                else:
                    self.report({'WARNING'}, "Not valid Target Collection!")
                    return {'CANCELLED'}
            else:
                self.report({'WARNING'}, "Not valid Target Collection!")
                return {'CANCELLED'}
        else:
            self.report({'WARNING'}, "Not valid Target Collection!")
            return {'CANCELLED'}


class RBDLAB_OT_edges_parent_remove(Operator):
    bl_idname = "rbdlab.edges_pyshics_parent_remove"
    bl_label = "Parent Remove"
    bl_description = "Parent"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        ''' Physics Parent '''
        rbdlab = context.scene.rbdlab

        if rbdlab.filtered_target_collection:
            if rbdlab.filtered_target_collection.name:

                compounds = [obj for obj in rbdlab.filtered_target_collection.objects
                             if obj.type == 'MESH' and RBDLabNaming.NO_SHAPE_OBJ in obj]
                # print(valid_objects)

                original_obj = [context.view_layer.objects[obj.name.replace("_copy", "")] for obj in compounds]

                if compounds:
                    context.scene.frame_current = context.scene.frame_start

                    deselect_all_objects(context)

                    childrens = [obj.children for obj in compounds if obj.children]

                    if childrens:
                        for tuple in childrens:
                            for child in tuple:
                                mw = child.matrix_world
                                child.parent = None
                                child.matrix_world = mw

                    for obj in compounds:
                        obj.hide_set(False)
                        select_object(context, obj)

                    set_active_object(context, compounds[0])
                    bpy.ops.object.delete(use_global=False)

                    if not rbdlab.physics.rigidbodies.edge_remove_keep_transforms:
                        for original in original_obj:
                            org_mw = ast.literal_eval(original[RBDLabNaming.ORIGINAL_MW])
                            original.matrix_world = org_mw
                            original.location = original[RBDLabNaming.ORIGINAL_LOC]

                    if RBDLabNaming.EDGE_COMPOUND_PARENTED in rbdlab.filtered_target_collection:
                        del rbdlab.filtered_target_collection[RBDLabNaming.EDGE_COMPOUND_PARENTED]

                    return {'FINISHED'}

                else:
                    self.report({'WARNING'}, "Not valid Objects in this Target Collection!")
                    return {'CANCELLED'}

            else:
                self.report({'WARNING'}, "Not valid Target Collection!")
                return {'CANCELLED'}
        else:
            self.report({'WARNING'}, "Not valid Target Collection!")
            return {'CANCELLED'}
