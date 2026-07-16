import bpy
import bmesh
from bpy.types import Operator
from ....Global.particles import create_particle_system
from ....Global.basics import enter_object_mode, enter_edit_mode, select_object, set_active_object, deselect_all_objects
from ....addon.naming import RBDLabNaming

class SCATTER_OT_object(Operator):
    bl_idname = "rbdlab.scatter_add"
    bl_label = "Add Scatter"
    bl_description = "Add Standar Scatter"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        rbdlab = context.scene.rbdlab

        enter_object_mode(context)
        ps_name = "Detail_Scatter"
        ps_secondary_name = RBDLabNaming.SECOND_SCATTER
        vg_name = "paint"

        rbdlab.scatter_working = True

        # multi scatter para los objetos seleccionados:
        for obj in bpy.context.selected_objects:
            if obj:
                
                set_active_object(context, obj)
                if obj.type == 'MESH' and obj.visible_get():
                    if vg_name in obj.vertex_groups:
                        # determino si pintaron:
                        enter_edit_mode(context)
                        obj.vertex_groups.active_index = obj.vertex_groups.find("paint")
                        bpy.ops.mesh.select_all(action='DESELECT')
                        bpy.ops.object.vertex_group_select()

                        bm = bmesh.from_edit_mesh(obj.data)
                        selected_vertex = []
                        for v in bm.verts:
                            if v.select:
                                selected_vertex.append(v.co)

                        enter_object_mode(context)

                        if ps_name not in obj.particle_systems:
                            if len(selected_vertex):

                                create_particle_system(
                                    context,
                                    obj,
                                    ps_name,
                                    ps_type='VOLUME',
                                    ps_count=rbdlab.particle_count,
                                    display_size=0.025,
                                    physics_type='NO',
                                    vertex_group_density=vg_name
                                )

                                # obj.particle_systems[ps_name].vertex_group_density = vg_name
                            else:
                                bpy.context.active_object.particle_systems.active_index = bpy.context.active_object.particle_systems.find(
                                    ps_name)
                                bpy.ops.object.particle_system_remove()
                        else:
                            if len(selected_vertex) < 1:
                                bpy.context.active_object.particle_systems.active_index = bpy.context.active_object.particle_systems.find(
                                    ps_name)
                                bpy.ops.object.particle_system_remove()

                    if ps_secondary_name not in obj.particle_systems:

                        create_particle_system(
                            context,
                            obj,
                            ps_name=ps_secondary_name,
                            ps_type='VOLUME',
                            ps_count=rbdlab.particle_secondary_count,
                            # display_size=0.018,
                            display_size=rbdlab.scatter_secondary_size_particles,
                            physics_type='NO',
                        )
                        # obj.particle_systems[ps_secondary_name].settings.display_size = rbdlab.scatter_secondary_size_particles

                    obj.display_type = 'WIRE'

                else:
                    self.report({'WARNING'}, "Is necesary select one object!")

        return {'FINISHED'}


class ACCEPT_OT_scatter(Operator):
    bl_idname = "rbdlab.scatter_end"
    bl_label = "Accept"
    bl_description = "Apply Scatter"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        rbdlab = context.scene.rbdlab

        # ps_name = "Detail_Scatter"
        # for obj in bpy.context.selected_objects:
        #     if obj.type == 'MESH' and obj.visible_get():
        #         obj.display_type = 'TEXTURED'
        # bpy.data.particles[ps_name].display_size = 0

        rbdlab.scatter_working = False
        rbdlab.ui.fracture_switch_subsections = 'FRACTURE'
        return {'FINISHED'}


class SELECT_OT_scatter(Operator):
    bl_idname = "rbdlab.scatter_select"
    bl_label = "Select Scatter"
    bl_description = "Select all objects with scatter"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        ps_name = "Detail_Scatter"
        ps_secondary_name = RBDLabNaming.SECOND_SCATTER
        deselect_all_objects(context)
        for obj in context.scene.objects:
            if obj.type == 'MESH' and obj.visible_get():
                if ps_name in obj.particle_systems or ps_secondary_name in obj.particle_systems:
                    # if obj.display_type == 'WIRE':
                    select_object(context, obj)

        return {'FINISHED'}


class SCATTER_OT_cancel(Operator):
    bl_idname = "rbdlab.scatter_cancel"
    bl_label = "Cancel Scatter"
    bl_description = "Cancel Scatter"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return context.scene.rbdlab.scatter_working

    def execute(self, context):
        rbdlab = context.scene.rbdlab
        self.original_active = context.active_object
        self.original_selection = context.selected_objects

        cancel_scatter = getattr(self, "cancel_scatter_%s" % rbdlab.ui.scatter_mode.lower())
        cancel_scatter(context)

        # restore original selection
        for obj in self.original_selection:
            select_object(context, obj)
            obj.display_type = 'TEXTURED'

        set_active_object(context, self.original_active)

        rbdlab.scatter_working = False
        return {'FINISHED'}

    def remove_from_selected_objects(
            self, modifier_names: set = set(),
            key_names: set = set(),
            callback: callable = None):
        for obj in self.original_selection:
            if callback:
                callback(obj)

            for key in key_names:
                if key in obj:
                    del obj[key]

            for mod_name in modifier_names:
                mod = obj.modifiers.get(mod_name, None)
                if mod:
                    obj.modifiers.remove(mod)

    def cancel_scatter_standard(self, context):
        modifiers = {RBDLabNaming.SECOND_SCATTER, "Detail_Scatter"}
        self.remove_from_selected_objects(modifiers)

    def cancel_scatter_boolean(self, context):
        context.space_data.overlay.show_wireframes = False

        def remove_objects(obj):
            if "scatter_plane_accepted" not in obj:
                return

            for mod in obj.modifiers:
                if not mod.name.startswith(RBDLabNaming.BOOLEAN_MOD):
                    continue
                if mod.collection:
                    bpy.data.collections.remove(mod.collection, do_unlink=True, do_id_user=True, do_ui_user=True)
                obj.modifiers.remove(mod)

        modifiers = {RBDLabNaming.SECOND_SCATTER, "scatter_organic"}
        keys = {"scatter_by_planes", "scatter_plane_accepted"}
        self.remove_from_selected_objects(modifiers, keys, callback=remove_objects)

        objs = bpy.data.objects
        [objs.remove(ob, do_unlink=True) for ob in context.scene.objects if ob.name.startswith("RBDLab_Plane_")]

    def cancel_scatter_texture(self, context):
        # TO DO: probablemente a futuro se quede con sólo un sistema de particulas y haya que quitarlo de aquí.
        modifiers = {RBDLabNaming.SECOND_SCATTER, "Scatter_by_Texture"}
        keys = {"rbdlab_texture_created"}
        self.remove_from_selected_objects(modifiers, keys)

        tex = bpy.data.textures.get("RBDLab_Scatter_Texture", None)
        if tex:
            bpy.data.textures.remove(tex, do_unlink=True, do_id_user=True, do_ui_user=True)

    def cancel_scatter_organic(self, context):
        # eliminamos todas las posibles icospheres
        def remove_objects(obj):
            objs = bpy.data.objects
            [objs.remove(ob, do_unlink=True, do_id_user=True, do_ui_user=True)
             for ob in context.scene.objects if ob.parent == obj]

            # BUG: Al borrar las icoesferas, sucede que de alguna forma
            # el padre recibe las particulas de las icoesferas (las hijas).
            if "rbdlab_scatter_organic_accepted" not in obj:
                return

            mod = obj.modifiers.get("child_particles", None)
            if mod:
                obj.modifiers.remove(mod)

        modifiers = {"scatter_organic"}
        keys = {"rbdlab_scatter_organic_accepted", "scatter_organic"}
        self.remove_from_selected_objects(modifiers, keys, callback=remove_objects)

        ob = context.scene.objects.get("RBDLab_Icosphere", None)
        if ob:
            bpy.data.objects.remove(ob, do_unlink=True, do_id_user=True, do_ui_user=True)

        for obj in self.original_selection:
            if "rbdlab_scatter_organic" in obj:
                del obj["rbdlab_scatter_organic"]
