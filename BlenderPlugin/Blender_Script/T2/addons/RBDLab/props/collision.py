import bpy
from typing import List
from bpy.types import PropertyGroup, Object
from bpy.props import BoolProperty, FloatProperty, EnumProperty, IntProperty, CollectionProperty, PointerProperty
from ..addon.naming import RBDLabNaming


class RBDLab_PG_collision(PropertyGroup):
    permeability: FloatProperty(
        name="Permeability",
        # default=1,
        default=0,
        min=0,
        max=1,
        precision=3
    )
    stickiness: FloatProperty(
        name="Stickiness",
        default=0.0,
        min=0,
        max=10,
        precision=3
    )
    use_particle_kill: BoolProperty(
        name="Kill Particles",
        default=False
    )
    damping_factor: FloatProperty(
        name="Damping",
        default=0.8,
        min=0,
        max=1,
        precision=3
    )
    damping_random: FloatProperty(
        name="Randomize",
        default=0,
        min=0,
        max=1,
        precision=3
    )
    friction_factor: FloatProperty(
        name="Friction",
        default=0.8,
        min=0,
        max=1,
        precision=3
    )
    friction_random: FloatProperty(
        name="Randomize",
        default=0,
        min=0,
        max=1,
        precision=3
    )
    through_offset_direction: EnumProperty(
        name="Direction",
        description="Forward: move with offset the end keyframes to RIGHT direction\nbackward: move with offset the end keyframes to LEFT direction",
        items=(
            ("forward", "Forward", ""),
            ("backward", "Backward", ""),
        ),
        default="forward"
    )

    def through_offset_update(self, context):
        scn = context.scene
        rbdlab = scn.rbdlab 

        tcoll_list = rbdlab.lists.target_coll_list
        tcoll = tcoll_list.active
        chunks = tcoll_list.get_current_active_tcoll_valild_objects(context)

        if chunks:

            through_offset = self.through_offset

            if RBDLabNaming.PART_COLLISION in tcoll:
                
                low_valid_objects = [ob for ob in chunks if RBDLabNaming.CHUNK_EXTRACTED in ob and ob.animation_data is not None and ob.animation_data.action is not None]
                ob_action = {ob: ob.animation_data.action for ob in low_valid_objects}

                if ob_action:

                    for ob, action in ob_action.items():

                        if RBDLabNaming.CHUNK_PART_CHILD not in ob:
                            continue
                        
                        childs = ob[RBDLabNaming.CHUNK_PART_CHILD]
                        for child in childs:

                            if child and child.particle_systems:
                                    
                                frame_end = max([ps.settings.frame_end for ps in child.particle_systems])

                                for fcu in action.fcurves:
                                    if "collision.use" in fcu.data_path:

                                        # los dos ultimos keyframes:
                                        two_last_keyframes = fcu.keyframe_points[-2:]

                                        for i, kp in enumerate(two_last_keyframes):
                                            if i == 0:
                                                value = frame_end + through_offset
                                            elif i == 1:
                                                value = frame_end + through_offset + 1

                                            kp.co.x = value
                                            kp.handle_left.x = value
                                            kp.handle_right.x = value

                                    # if "damping_factor" in fcu.data_path or "permeability" in fcu.data_path:

                                    #     # si tengo estos keyframes:
                                    #     # [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12]
                                    #     # y quiero mover solo los siguientes (saltandose 2):
                                    #     # [[3, 4], [7, 8], [11, 12]]
                                    #     # solucion:

                                    #     list1 = []
                                    #     list2 = []
                                    #     for i in range(len(fcu.keyframe_points)):
                                    #         list1.append(fcu.keyframe_points[i]) if i % 2 == 0 else list2.append(fcu.keyframe_points[i])

                                    #     for_through_offset_ends = []

                                    #     for i in range(len(list1)):
                                    #         if i % 2 != 0:
                                    #             if i < len(list1) and i < len(list2):
                                    #                 for_through_offset_ends.append([list1[i], list2[i]])

                                    #     if "damping_factor" in fcu.data_path:
                                    #         for kp in fcu.keyframe_points:
                                    #             # si el keyframe no esta en y 0 entonces le ponemos el nuevo valor:
                                    #             if kp.co.y != 0:
                                    #                 kp.co.y = self.damping_factor
                                    #                 kp.handle_left.y = self.damping_factor
                                    #                 kp.handle_right.y = self.damping_factor

                                    #     for grp_kp in for_through_offset_ends:

                                    #         for i, kp in enumerate(grp_kp):
                                    #             if i == 0:
                                    #                 value = frame_end + through_offset
                                    #             elif i == 1:
                                    #                 value = frame_end + through_offset + 1

                                    #             kp.co.x = value
                                    #             kp.handle_left.x = value
                                    #             kp.handle_right.x = value

        else:
            print("not valid objects!")

    through_offset: IntProperty(
        name="Through Offset",
        description="Apply an offset",
        default=0,
        soft_min=-15,
        soft_max=15,
        update=through_offset_update
    )

    # Static Objects
    so_stickiness: FloatProperty(
        name="Stickiness",
        default=0.0,
        min=0,
        max=10,
        precision=3
    )
    so_use_particle_kill: BoolProperty(
        name="Kill Particles",
        default=False
    )
    so_damping_factor: FloatProperty(
        name="Damping",
        default=0.8,
        min=0,
        max=1,
        precision=3
    )
    so_damping_random: FloatProperty(
        name="Randomize",
        default=0,
        min=0,
        max=1,
        precision=3
    )
    so_friction_factor: FloatProperty(
        name="Friction",
        default=0.8,
        min=0,
        max=1,
        precision=3
    )
    so_friction_random: FloatProperty(
        name="Randomize",
        default=0,
        min=0,
        max=1,
        precision=3
    )
    use_clear_parents: BoolProperty(
        default=False
    )

    def get_default_properties(self, target_prop):
        for prop in self.bl_rna.properties:
            if prop.identifier == target_prop:
                if hasattr(prop, "default"):
                    return prop.default

# Collision Static Object list:


class COLLISION_SO_PG_list_item(PropertyGroup):

    def update_data(self, context):
        scn = context.scene
        rbdlab = scn.rbdlab
        obj = self.data

        if not obj:
            rbdlab.lists.collision_so_list.remove_obj_list(self)

        if obj:
            obj.hide_set(self.visible)
            obj.select_set(self.select_obj)

    def do_remove(self, context):
        if not self.remove:
            return
        scn = context.scene
        rbdlab = scn.rbdlab
        self.remove = False
        obj = self.data
        if obj:
            bpy.data.objects.remove(obj, do_unlink=True)
        rbdlab.lists.collision_so_list.remove_obj_list(self)

    remove: BoolProperty(default=False, update=do_remove)
    data: PointerProperty(type=Object, update=update_data)
    visible: BoolProperty(default=True, update=update_data)
    select_obj: BoolProperty(default=False, update=update_data)


class RBDLab_PG_collision_so_list(PropertyGroup):
    ''' Collision Static Object Groups
        ++++++++++++++++++++++++++++++++++++++++ '''

    def obj_list_index_update(self, context):
        # when change item active in list:
        # get the ui data
        scn = context.scene
        rbdlab = scn.rbdlab
        obj = self.get_active_item_list()

        if obj:
            rbdlab.collision.so_stickiness = obj.collision.stickiness
            rbdlab.collision.so_use_particle_kill = obj.collision.use_particle_kill
            rbdlab.collision.so_damping_factor = obj.collision.damping_factor
            rbdlab.collision.so_damping_random = obj.collision.damping_random
            rbdlab.collision.so_friction_factor = obj.collision.friction_factor
            rbdlab.collision.so_friction_random = obj.collision.friction_random
        else:
            rbdlab.collision.so_stickiness = rbdlab.collision.get_default_properties("so_stickiness")
            rbdlab.collision.so_use_particle_kill = rbdlab.collision.get_default_properties("so_use_particle_kill")
            rbdlab.collision.so_damping_factor = rbdlab.collision.get_default_properties("so_damping_factor")
            rbdlab.collision.so_damping_random = rbdlab.collision.get_default_properties("so_damping_random")
            rbdlab.collision.so_friction_factor = rbdlab.collision.get_default_properties("so_friction_factor")
            rbdlab.collision.so_friction_random = rbdlab.collision.get_default_properties("so_friction_random")

    obj_list_index: IntProperty(
        default=0,
        update=obj_list_index_update
    )
    obj_list: CollectionProperty(type=COLLISION_SO_PG_list_item)

    def add_item(self, obj):
        obj_list_item = self.obj_list.add()
        obj_list_item.data = obj
        obj_list_item.selected = True

    def remove_obj_list(self, target_obj_list_item: COLLISION_SO_PG_list_item):
        obj_index = -1
        for i, obj_list_item in enumerate(self.obj_list):
            if target_obj_list_item == obj_list_item:
                obj_index = i
                break
        if obj_index != -1:
            self.obj_list.remove(obj_index)

    def get_active_item_list(self) -> List[Object]:
        return self.obj_list[self.obj_list_index].data

    def get_all_objects(self) -> List[Object]:
        return [obj_list_item.data for obj_list_item in self.obj_list]
