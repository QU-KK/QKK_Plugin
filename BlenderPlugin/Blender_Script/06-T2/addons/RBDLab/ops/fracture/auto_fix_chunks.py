import bpy
from bpy.types import Operator
from ...Global.basics import set_active_object
from ...addon.naming import RBDLabNaming

# boolean_mod_name = "Boolean"
boolean_mod_name = RBDLabNaming.BOOLEAN_MOD
boolean_mod_name_up = RBDLabNaming.BOOLEAN_MOD_UP


class AUTO_OT_fix_chunks(Operator):
    bl_idname = "rbdlab.auto_fix_chunks"
    bl_label = "RBDLab Automatic fix void chunks"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):

        objects = context.selected_objects

        valid_objects = [obj for obj in objects if obj.type == 'MESH' and obj.visible_get()]

        if len(valid_objects) > 0:
            first_chunk = valid_objects[0]
            bpy.ops.object.scale_clear(clear_delta=False)

            boolean_mod = first_chunk.modifiers[boolean_mod_name]
            boolean_mod.solver = 'EXACT'
            boolean_mod.use_self = True

            if boolean_mod_name_up in first_chunk.modifiers:
                boolean_up_mod = first_chunk.modifiers[boolean_mod_name_up]
                boolean_up_mod.solver = 'EXACT'
                boolean_up_mod.use_self = True

            set_active_object(context, first_chunk)
            bpy.ops.object.make_links_data(type='MODIFIERS')

            for obj in valid_objects:
                print(obj.name + " fixed")

            boolena_objects = [obj for obj in valid_objects
                               if boolean_mod_name in obj.modifiers and RBDLabNaming.FROM in obj]
            if boolena_objects:
                if boolean_mod_name_up in first_chunk.modifiers:
                    [(setattr(obj.modifiers[boolean_mod_name], "object", bpy.data.objects[obj[RBDLabNaming.FROM]]), setattr(
                        obj.modifiers[boolean_mod_name_up], "object", bpy.data.objects[obj[RBDLabNaming.FROM]])) for obj in boolena_objects]
                else:
                    [setattr(obj.modifiers[boolean_mod_name], "object", bpy.data.objects[obj[RBDLabNaming.FROM]])
                     for obj in boolena_objects]

            # OLD METHOD:
            # for obj in valid_objects:
            #     # reset weld to initial point for re-autofixes
            #     # obj.modifiers["RBDLab_Weld"].merge_threshold = 0.0
            #     # obj.modifiers["RBDLab_Dilate"].strength = 0.0
            #     bpy.ops.object.scale_clear(clear_delta=False)
            #
            #     enter_edit_mode(context)
            #     select_all_vertices(context)
            #     enter_object_mode(context)
            #
            #     stage = check_void_chunks(obj)
            #     # prevent = 0
            #
            #     if stage:
            #         print(obj.name, "detected to auto repair!")
            #
            #     # max_iterations = rbdlab.autofix_max_iterations
            #
            #     # while stage and prevent <= max_iterations:
            #     #     obj.modifiers["RBDLab_Weld"].merge_threshold += 0.01
            #     #     # obj.modifiers["RBDLab_Dilate"].strength += 0.001
            #     #     obj.scale[0] += 0.0005
            #     #     obj.scale[1] += 0.0005
            #     #     obj.scale[2] += 0.0005
            #     #
            #     #     stage = check_void_chunks(obj)
            #     #     print("repair " + obj.name + " iteration", prevent)
            #     #     # self.report({'INFO'}, "repair " + obj.name + " iteration" + str(prevent))
            #     #     prevent += 1
            #
            #     # if boolean_mod.show_render and boolean_mod.how_viewport:
            #     boolean_mod = obj.modifiers[boolean_mod_name]
            #     boolean_mod.solver = 'EXACT'
            #     boolean_mod.use_self = True
            #     boolean_up_mod = obj.modifiers[boolean_mod_name_up]
            #     boolean_up_mod.solver = 'EXACT'
            #     boolean_up_mod.use_self = True

        return {'FINISHED'}
