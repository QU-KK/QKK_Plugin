import bpy
from bpy.types import Operator
from ...Global.basics import select_object, set_active_object, deselect_all_objects, enter_edit_mode
from ...Global.functions import select_inner_faces_by_attribute
from bpy.props import EnumProperty
from ...addon.naming import RBDLabNaming


class RBDLAB_OT_shade_smooth_inner(Operator):
    bl_idname = "rbdlab.shade_smooth_inner"
    bl_label = "Shade Smooth/Flat Inner/Outer"
    bl_description = "Shade Smooth/Flat Inner/Outer"
    bl_options = {'REGISTER', 'UNDO'}

    type: EnumProperty(name="Shade type",
                       items=(
                            ("smooth_inner", "Smooth", ""),
                            ("flat_inner", "Flat", ""),
                            ("smooth_outher", "Smooth", ""),
                            ("flat_outher", "Flat", ""),
                       ),
                       default="smooth_inner")

    @classmethod
    def poll(cls, context):
        return context.scene.rbdlab.filtered_target_collection is not None

    def execute(self, context):

        scn = context.scene
        rbdlab = scn.rbdlab

        tcoll_list = rbdlab.lists.target_coll_list
        tcoll = tcoll_list.active
        target_collection = None

        if tcoll:
            coll_name = tcoll.name
            if coll_name:

                if rbdlab.low_or_high_visibility_viewport == "High":
                    if RBDLabNaming.SUFIX_LOW in coll_name:
                        target_collection = coll_name.replace(RBDLabNaming.SUFIX_LOW, RBDLabNaming.SUFIX_HIGH)
                    elif RBDLabNaming.SUFIX_HIGH in coll_name:
                        target_collection = coll_name
                    else:
                        target_collection = coll_name
                
                elif rbdlab.low_or_high_visibility_viewport == "Low":
                    if RBDLabNaming.SUFIX_HIGH in coll_name:
                        target_collection = coll_name.replace(RBDLabNaming.SUFIX_HIGH, RBDLabNaming.SUFIX_LOW)
                    elif RBDLabNaming.SUFIX_LOW in coll_name:
                        target_collection = coll_name
                    else:
                        target_collection = coll_name

                deselect_all_objects(context)

                coll = bpy.data.collections.get(target_collection)
                if target_collection is None or not coll:
                    print("The Target Collection could not be found: " + target_collection + "!")
                    return {'CANCELLED'}

                [ob.select_set(True) for ob in coll.objects]

                if coll.objects:

                    active_object = coll.objects[0]
                    set_active_object(context, active_object)
                    
                    # store previous mode:
                    current_mode = context.object.mode

                    select_inner_faces_by_attribute(context, context.selected_objects)

                    if "smooth" in self.type:
                        if "inner" in self.type:
                            # print("inner smooth shade")
                            bpy.ops.mesh.faces_shade_smooth()
                        else:
                            # print("outer smooth shade")
                            bpy.ops.mesh.select_all(action='INVERT')
                            bpy.ops.mesh.faces_shade_smooth()
                    elif "flat" in self.type:
                        if "inner" in self.type:
                            # print("inner flat shade")
                            bpy.ops.mesh.faces_shade_flat()
                        else:
                            # print("outer flat shade")
                            bpy.ops.mesh.select_all(action='INVERT')
                            bpy.ops.mesh.faces_shade_flat()

                    # restore previous mode:
                    bpy.ops.object.mode_set(mode=current_mode)

                    deselect_all_objects(context)

        return {'FINISHED'}
