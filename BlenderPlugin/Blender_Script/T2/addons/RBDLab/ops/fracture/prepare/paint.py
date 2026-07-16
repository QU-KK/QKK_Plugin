import bpy
from bpy.types import Operator, Area
from ....Global.particles import create_particle_system
from ....addon.naming import RBDLabNaming
from ....Global.get_common_vars import get_common_vars
from ....Global.basics import context_override


class RBDLAB_weight_paint(Operator):
    bl_idname = "rbdlab.goto_weightpaint"
    bl_label = "Go to weight paint"
    bl_options = {'REGISTER', 'UNDO'}
    bl_description = "To paint where your object will have the most detail (only supports a single object at a time)"


    @classmethod
    def poll(cls, context):
        return context.active_object is not None and context.active_object.type == 'MESH'


    def execute(self, context):

        rbdlab = get_common_vars(context, get_rbdlab=True)

        # sobreescribir el contexto:
        def callback(context) -> None:
            area = context.area  # Accedemos al área desde el contexto
            for space in area.spaces:
                if space.type == 'VIEW_3D':
                    space.shading.type = 'SOLID'
            area.tag_redraw()
        context_override(context=context, area_type='VIEW_3D', callback=callback)

        bpy.ops.paint.weight_paint_toggle()
        obj = context.object

        obj.display_type = 'SOLID'

        if "paint" not in obj.vertex_groups:
            bpy.ops.object.vertex_group_add()
            if obj.vertex_groups.find("paint") == -1:
                obj.vertex_groups[-1].name = "paint"

        if "Detail_Scatter" not in obj.particle_systems and RBDLabNaming.SECOND_SCATTER in obj.particle_systems and context.mode != 'PAINT_WEIGHT':
            ps_name = "Detail_Scatter"
            vertex_group_density = "paint"

            create_particle_system(
                context,
                obj,
                ps_name,
                ps_type='VOLUME',
                ps_count=rbdlab.particle_count,
                display_size=0.018,
                frame_end=context.scene.frame_end,
                vertex_group_density=vertex_group_density,
            )

            # obj.particle_systems[ps_name].vertex_group_density = vertex_group_density
            obj.particle_systems[ps_name].settings.frame_end = 1
            obj.display_type = 'WIRE'

        return {'FINISHED'}


class CLEAR_weight_paint(Operator):
    bl_idname = "rbdlab.clear_weightpaint"
    bl_label = "Clear wight paint"
    bl_options = {'REGISTER', 'UNDO'}


    def execute(self, context):
        ob = context.object
        ob.display_type = 'SOLID'

        if "paint" in ob.vertex_groups:
            ob.vertex_groups.active_index = ob.vertex_groups.find("paint")
            bpy.ops.object.vertex_group_remove()

            bpy.ops.object.vertex_group_add()
            if ob.vertex_groups.find("paint") == -1:
                ob.vertex_groups[-1].name = "paint"

        return {'FINISHED'}