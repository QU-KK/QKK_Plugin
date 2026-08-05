import bpy
from bpy.types import Operator
from bpy.props import EnumProperty
from ...addon.naming import RBDLabNaming


class HIGH_DETAILS_OT_toggle_decimate(Operator):
    bl_idname = "rbdlab.high_details_toggle_decimate"
    bl_label = "Toggle Decimate"
    bl_description = "Try Fix Fissures in selected chunks"
    bl_options = {'REGISTER', 'UNDO'}

    type: EnumProperty(name="Toggle Decimate",
                       items=(
                           ('ENABLE_PLANAR', "Enable", "Enable Decimate Planar"),
                           ('DISABLE_PLANAR', "Disable", "Disable Decimate Planar"),
                           ('ENABLE_COLLAPSE', "Enable", "Enable Decimate Collapse"),
                           ('DISABLE_COLLAPSE', "Disable", "Disable Decimate Collapse"),
                       ),
                       default='ENABLE_PLANAR')

    def acction(self, valid_objects: list[object]) -> None:
        if valid_objects:
            for obj in valid_objects:
                # print(obj.name)

                if RBDLabNaming.DECIMATE in obj.modifiers:
                    if self.type == 'DISABLE_PLANAR':
                        obj.modifiers[RBDLabNaming.DECIMATE].show_viewport = True
                        obj.modifiers[RBDLabNaming.DECIMATE].show_render = True
                    elif self.type == 'ENABLE_PLANAR':
                        obj.modifiers[RBDLabNaming.DECIMATE].show_viewport = False
                        obj.modifiers[RBDLabNaming.DECIMATE].show_render = False

                # if "RBDLab_Decimate_collapse" in obj.modifiers:
                #     if self.type == 'ENABLE_COLLAPSE':
                #         obj.modifiers["RBDLab_Decimate_collapse"].show_viewport = True
                #         obj.modifiers["RBDLab_Decimate_collapse"].show_render = True
                #     elif self.type == 'DISABLE_COLLAPSE':
                #         obj.modifiers["RBDLab_Decimate_collapse"].show_viewport = False
                #         obj.modifiers["RBDLab_Decimate_collapse"].show_render = False

    def execute(self, context):
        rbdlab = context.scene.rbdlab

        if 'PLANAR' in self.type:
            valid_objects = [obj for obj in context.selected_objects if obj.type == 'MESH']
            self.acction(valid_objects)

        elif 'COLLAPSE' in self.type:
            target_collections = rbdlab.filtered_target_collection[RBDLabNaming.LAST_CREATED_COLLS]
            if target_collections:
                for target_coll in target_collections:
                    coll_name = target_coll.name

                    print("coll_name", coll_name)

                    if RBDLabNaming.SUFIX_LOW in coll_name:
                        coll_high_name = coll_name.replace(RBDLabNaming.SUFIX_LOW, RBDLabNaming.SUFIX_HIGH)
                    else:
                        coll_high_name = coll_name + RBDLabNaming.SUFIX_HIGH

                    valid_objects = [obj for obj in bpy.data.collections[coll_high_name].objects if obj.type == 'MESH']

                    self.acction(valid_objects)

        return {'FINISHED'}
