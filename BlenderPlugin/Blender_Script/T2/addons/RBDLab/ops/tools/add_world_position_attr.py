import bpy
from bpy.types import Operator
from datetime import datetime
from ...addon.naming import RBDLabNaming


class RBLAB_OT_add_world_position(Operator):
    bl_label = "Add World Position Attribute"
    bl_idname = "rbdlab.add_world_position_attr"
    bl_description = "Add World Position Attribute for use in materials"

    wpos_name = RBDLabNaming.WORLD_POSITION

    def execute(self, context):
        start = datetime.now()

        rbdlab = context.scene.rbdlab

        if rbdlab.filtered_target_collection:
            coll_name = rbdlab.filtered_target_collection.name
            if coll_name:

                context.scene.frame_current = context.scene.frame_start

                target_high_coll_name = None
                target_objects = None

                if rbdlab.world_position_to == 'HIGH':

                    if RBDLabNaming.SUFIX_LOW in coll_name:
                        target_high_coll_name = coll_name.replace(RBDLabNaming.SUFIX_LOW, RBDLabNaming.SUFIX_HIGH)
                    else:
                        target_high_coll_name = coll_name + RBDLabNaming.SUFIX_HIGH

                    if target_high_coll_name is not None:
                        if target_high_coll_name in bpy.data.collections:
                            target_high_coll = bpy.data.collections[target_high_coll_name]
                            target_objects = target_high_coll.objects
                            target_coll_name = target_high_coll_name
                        else:
                            self.report({'WARNING'}, target_high_coll_name + " collection not found!")
                            return {'CANCELLED'}
                    else:
                        self.report({'WARNING'}, target_high_coll_name + " collection not found!")
                        return {'CANCELLED'}
                else:
                    target_coll_name = coll_name
                    target_objects = rbdlab.filtered_target_collection.objects

                valid_objects = [obj for obj in target_objects
                                 if obj.type == 'MESH' and "ground"
                                 not in obj.name.lower() and "BBox" not in obj.name]

                for chunk in valid_objects:

                    me = chunk.data
                    vert_list = me.vertices
                    attributes = me.attributes

                    if self.wpos_name not in chunk.data.attributes:
                        chunk.data.attributes.new(name=self.wpos_name,
                                                  type='FLOAT_VECTOR', domain='POINT')

                    attribute = attributes[self.wpos_name]

                    print("Store World Position Attribute in: %s" % chunk.name)

                    for v in me.vertices:
                        v_co_world = chunk.matrix_world @ vert_list[v.index].co

                        # le contraresto las coordenadas del objetos original:
                        if "rbdlab_from" in chunk:
                            if chunk["rbdlab_from"] in context.view_layer.objects:
                                v_co_world -= context.view_layer.objects[chunk["rbdlab_from"]].location

                        attribute.data[v.index].vector = v_co_world

                self.report(
                    {'INFO'},
                    "Attribute " + self.wpos_name + " added in " + target_coll_name + " to " +
                    str(len(valid_objects)) + " collection chunks!")

        else:
            self.report({'INFO'}, "No target collection!")
            return {'CANCELLED'}

        print("World Position End: " + str(datetime.now() - start))
        return {'FINISHED'}
