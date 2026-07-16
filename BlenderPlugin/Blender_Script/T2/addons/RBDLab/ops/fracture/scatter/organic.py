import bpy
import random
from bpy.types import Operator
from ....Global.particles import create_particle_system
from ....Global.basics import select_object, set_active_object, deselect_all_objects
# from ....addon.naming import RBDLabNaming

class SCATTER_OT_add_organic(Operator):
    bl_idname = "rbdlab.scatter_organic"
    bl_label = "Organic Scatter"
    bl_description = "Add Scatter by Icospheres"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        rbdlab = context.scene.rbdlab
        scatter_props = rbdlab.scatter

        # obj = context.active_object
        original_active = context.active_object
        original_selection = context.selected_objects

        if len(original_selection) <= 0:
            self.report({'WARNING'}, "No Selected Objects!")
            return {'CANCELLED'}

        for obj in original_selection:

            obj["rbdlab_scatter_organic"] = True

            ps_name = "scatter_organic"
            if ps_name not in obj.particle_systems:

                create_particle_system(
                    context,
                    ob=obj,
                    ps_name=ps_name,
                    ps_type='VOLUME',
                    ps_count=scatter_props.scatter_geo_count,
                    display_size=0.025,
                    physics_type='NO',
                )

            # ps_name = RBDLabNaming.SECOND_SCATTER

            spawn = (0, 0, -50)
            geometry = None

            iconame = "RBDLab_Icosphere"
            if iconame in context.scene.objects:
                geometry = context.scene.objects.get(iconame)
            else:
                bpy.ops.mesh.primitive_ico_sphere_add(
                    radius=1, enter_editmode=False, align='WORLD', location=spawn, scale=(1, 1, 1))
                geometry = context.active_object
                geometry.name = iconame
                geometry.hide_set(True)

            deselect_all_objects(context)
            set_active_object(context, obj)
            select_object(context, obj)

            if len(obj.particle_systems) > 0:
                if ps_name in obj.particle_systems:
                    ps = obj.particle_systems[ps_name]
                    ps.settings.render_type = 'OBJECT'
                    ps.settings.instance_object = geometry
                    ps.settings.particle_size = scatter_props.scatter_geo_particle_size
                    ps.settings.use_rotations = True
                    ps.seed = random.randint(1, 1000)
                    ps.settings.size_random = scatter_props.scatter_geo_size_random

                    rbdlab.scatter_geo_count = 10

        # restore original selection
        for obj in original_selection:
            select_object(context, obj)

            if obj.type == 'MESH':
                obj.display_type = 'WIRE'

        set_active_object(context, original_active)

        rbdlab.scatter_working = True
        return {'FINISHED'}


class SCATTER_OT_organic_accept(Operator):
    bl_idname = "rbdlab.scatter_organic_accept"
    bl_label = "Scatter Organic Accept"
    bl_description = "Accept Scatter Organic"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        rbdlab = context.scene.rbdlab
        original_active = context.active_object
        original_selection = context.selected_objects
        # obj = context.active_object

        bpy.ops.object.duplicates_make_real(use_base_parent=True)
        new_objects = context.selected_objects

        for obj in original_selection:

            deselect_all_objects(context)
            select_object(context, obj)
            set_active_object(context, obj)

            ps_name = "child_particles"

            [(setattr(new_object, "display_type", 'WIRE'),
              create_particle_system(
                  context,
                  ob=new_object,
                  ps_name=ps_name,
                  ps_type='VOLUME',
                  ps_count=rbdlab.scatter.scatter_geo_child_count,
                  display_size=0.025,
                  physics_type='NO',
                  )
              ) for new_object in new_objects
             if ps_name not in new_object.particle_systems]

            new_set = rbdlab.rbdlab_cf_source
            new_set.add('PARTICLE_CHILD')
            rbdlab.rbdlab_cf_source = new_set
            # rbdlab.rbdlab_cf_source = {'PARTICLE_CHILD'}

            if "rbdlab_scatter_organic" in obj:
                del obj["rbdlab_scatter_organic"]

            primitives = ["RBDLab_Icosphere"]

            # elimino los objetos residuales:
            objs = bpy.data.objects
            [objs.remove(objs[obj.name], do_unlink=True) for obj in context.scene.objects if obj.name in primitives]

            obj["rbdlab_scatter_organic_accepted"] = True

            deselect_all_objects(context)

        # restore original selection
        for obj in original_selection:
            select_object(context, obj)

        set_active_object(context, original_active)
        rbdlab.scatter_working = False
        return {'FINISHED'}
