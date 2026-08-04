import bpy
from bpy.types import Operator

from ....Global.basics import set_active_object
from ....Global.particles import create_particle_system


class SCATTER_OT_add_by_texture(Operator):
    bl_idname = "rbdlab.scatter_by_texture"
    bl_label = "Scatter by Texture"
    bl_description = "Add Scatter by Texture"
    bl_options = {'REGISTER', 'UNDO'}

    def new_texture(self):
        bpy.ops.texture.new()
        texture_name = "RBDLab_Scatter_Texture"
        texture = bpy.data.textures[-1]
        texture.name = texture_name
        texture.type = 'CLOUDS'
        texture.use_color_ramp = True
        texture.color_ramp.elements[0].color = (0, 0, 0, 1)
        bpy.data.textures[texture.name].noise_scale = 0.4
        bpy.data.textures[texture.name].color_ramp.elements[0].position = 0.5
        return texture

    def execute(self, context):
        rbdlab = context.scene.rbdlab
        scatter_props = rbdlab.scatter

        # obj = context.active_object
        original_selection = context.selected_objects

        if len(original_selection) <= 0:
            self.report({'WARNING'}, "No Selected Objects!")
            return {'CANCELLED'}

        ps_name = "Scatter_by_Texture"

        for obj in original_selection:
            set_active_object(context, obj)
            if ps_name not in obj.particle_systems:

                create_particle_system(
                    context,
                    obj,
                    ps_name,
                    ps_type='VOLUME',
                    ps_count=scatter_props.texture_particle_count,
                    display_size=0.025,
                    physics_type='NO',
                )

            if len(obj.particle_systems) > 0:
                if ps_name in obj.particle_systems:
                    ps = obj.particle_systems[ps_name]
                    texture = self.new_texture()
                    ps.settings.active_texture = texture
                    ps.settings.texture_slots[0].use_map_time = False
                    ps.settings.texture_slots[0].use_map_density = True
                    ps.settings.texture_slots[0].texture_coords = scatter_props.texture_texture_coords

            obj["rbdlab_texture_created"] = True
            rbdlab.scatter_working = True
            obj.display_type = 'WIRE'

        return {'FINISHED'}


class SCATTER_OT_by_texture_accept(Operator):
    bl_idname = "rbdlab.scatter_by_texture_accept"
    bl_label = "Scatter texture Accept"
    bl_description = "Accept Scatter Organic"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        rbdlab = context.scene.rbdlab
        rbdlab.scatter_working = False
        rbdlab.ui.fracture_switch_subsections = 'FRACTURE'
        return {'FINISHED'}
