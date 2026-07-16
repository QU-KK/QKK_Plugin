import bpy
from bpy.types import Operator
from bpy.props import EnumProperty
from ...Global.basics import deselect_all_objects
from ...addon.paths import RBDLabPreferences
from ...addon.naming import RBDLabNaming
from ...Global.functions import remove_all_keyframes_in_action


class RBDLAB_OT_mute_smoke(Operator):
    bl_idname = "rbdlab.mute_smoke"
    bl_label = "Mute Smoke"

    type: EnumProperty(name="Particle type",
                       items=(
                            ("debris", "Debris", ""),
                            ("dust", "Dust", ""),
                            ("smoke", "Smoke", "")
                       ),
                       default="debris")

    @classmethod
    def poll(cls, context):
        return context.scene.rbdlab.filtered_target_collection is not None

    def colors_acction(self, context, ob, col_p_mute):

        remove_all_keyframes_in_action(context, ob, "color")
        ob.color_stack.add_color(col_p_mute)
        ob.color = col_p_mute

        if ob.parent:
            if ob.parent.type == 'MESH':
                remove_all_keyframes_in_action(context, ob.parent, "color")
                ob.parent.color_stack.add_color(col_p_mute)
                ob.parent.color = col_p_mute

    def execute(self, context):
        rbdlab = context.scene.rbdlab
        # addon_preferences = RBDLabPreferences.get_prefs(context)

        coll_name = rbdlab.filtered_target_collection.name

        if not coll_name:
            return {'CANCELLED'}

        mod_name = RBDLabNaming.SMOKE_MOD

        # col_p_mute = list(addon_preferences.col_p_mute)

        valid_objects = [obj for obj in rbdlab.filtered_target_collection.objects
                         if obj.type == 'MESH' and obj.visible_get() and obj.select_get()]

        if not valid_objects:
            rbdlab.filtered_target_collection["feedback_mute_smoke"] = ""
            self.report({'WARNING'}, "Not Selected Chunks!")
            return {'CANCELLED'}

        muted_count = []
        for ob in valid_objects:

            childs = None    
            if RBDLabNaming.CHUNK_PART_CHILD in ob:
                childs = ob[RBDLabNaming.CHUNK_PART_CHILD]
                # print(ob.name, ob[RBDLabNaming.CHUNK_PART_CHILD])

            if childs is None:
                # print("skip")
                continue

            for child in childs:

                # self.colors_acction(context, ob, col_p_mute)

                for mod in child.modifiers:

                    if not mod.name.startswith(mod_name):
                        continue

                    if RBDLabNaming.SMOKE_MOD not in mod.name:
                        continue

                    mod.show_viewport = False
                    mod.show_render = False
                    mod.fluid_type = 'NONE'
                    muted_count.append(child)
                    child["rbdlab_mute_smoke"] = True

        deselect_all_objects(context)

        # fuerzo a que recompute la cache:
        domain = [obj for obj in bpy.data.objects if obj.name.endswith(RBDLabNaming.SUFIX_DOMAIN)][0]
        if domain:
            domain.modifiers[RBDLabNaming.SMOKE_MOD].domain_settings.resolution_max = domain.modifiers[RBDLabNaming.SMOKE_MOD].domain_settings.resolution_max

        # este o no lo reseteo siempre:
        rbdlab.filtered_target_collection["feedback_mute_smoke"] = "Muted:"
        rbdlab.filtered_target_collection["feedback_mute_smoke"] += " ##### " + str(len(muted_count))

        if len(muted_count) == 0:
            rbdlab.filtered_target_collection["feedback_mute_smoke"] = ""

        return {'FINISHED'}


class RBDLAB_OT_unmute_smoke(Operator):
    bl_idname = "rbdlab.unmute_smoke"
    bl_label = "Unmute Smoke"

    type: EnumProperty(name="Particle type",
                       items=(
                            ("debris", "Debris", ""),
                            ("dust", "Dust", ""),
                            ("smoke", "Smoke", "")
                       ),
                       default="debris")

    unmuted_count = []

    @classmethod
    def poll(cls, context):
        return context.scene.rbdlab.filtered_target_collection is not None

    def colors_acction(self, context, ob, col_p_mute):
        ob.color_stack.rm_color(col_p_mute)
        color = ob.color_stack.get_last_color()
        if color:
            ob.color = color

        if ob.parent:
            if ob.parent.type == 'MESH':
                ob.parent.color_stack.rm_color(col_p_mute)
                color = ob.parent.color_stack.get_last_color()
                if color:
                    ob.parent.color = color

    def unmute_action(self, rbdlab, ob, mod_name, show_status):
        for mod in ob.modifiers:

            if not mod.name.startswith(mod_name):
                continue

            if RBDLabNaming.SMOKE_MOD not in mod.name:
                continue

            if show_status:
                mod.show_viewport = show_status[0]
                mod.show_render = show_status[1]
                mod.fluid_type = 'FLOW'
            else:
                mod.show_viewport = True
                mod.show_render = True
                mod.fluid_type = 'FLOW'

            self.unmuted_count.append(ob)

            # restauramos las particulas y el resto de settings q hacen falta para el unmute
            if rbdlab.smoke.emiter.flow_source == 'PARTICLES':
                mod.flow_settings.flow_source = 'PARTICLES'

                if mod.flow_settings.particle_system is None:
                    ps_smoke_name = [ps.name for ps in ob.particle_systems if "_smoke_motion_" in ps.name]

                    if len(ps_smoke_name) > 0:
                        mod.flow_settings.particle_system = ob.particle_systems[ps_smoke_name[0]]
                        mod.flow_settings.flow_behavior = 'INFLOW'
            else:
                mod.flow_settings.surface_distance = rbdlab.smoke.emiter.surface_distance
                mod.flow_settings.volume_density = rbdlab.smoke.emiter.volume_density

    def execute(self, context):
        rbdlab = context.scene.rbdlab
        # addon_preferences = RBDLabPreferences.get_prefs(context)

        coll_name = rbdlab.filtered_target_collection.name
        if not coll_name:
            return {'CANCELLED'}

        mod_name = RBDLabNaming.SMOKE_MOD

        # col_smoke = list(addon_preferences.col_smoke)
        # col_p_mute = list(addon_preferences.col_p_mute)

        muted_chunks = [ob for ob in rbdlab.filtered_target_collection.objects if ob.type ==
                        'MESH' and "rbdlab_mute_smoke" in ob]

        if not muted_chunks:
            rbdlab.filtered_target_collection["feedback_mute_smoke"] = ""
            self.report({'WARNING'}, "Not Selected Chunks!")
            return {'CANCELLED'}

        unmuted_chunks = [ob for ob in rbdlab.filtered_target_collection.objects if ob.type ==
                          'MESH' and ob.visible_get() and "rbdlab_mute_smoke" not in ob]

        show_status = []
        if len(unmuted_chunks) > 0:
            first_unmuted_chunk = unmuted_chunks[0]

            for modifier in first_unmuted_chunk.modifiers:
                if modifier.name.startswith(mod_name):
                    show_status.append(modifier.show_viewport)
                    show_status.append(modifier.show_render)

        self.unmuted_count = []
        childs = None
        for ob in muted_chunks:

            if not ob.select_get():
                if ob.parent:
                    if ob.parent.type == 'MESH':
                        if not ob.parent.select_get():
                            continue

            if RBDLabNaming.CHUNK_PART_CHILD in ob:
                childs = ob[RBDLabNaming.CHUNK_PART_CHILD]

            # print(ob.name)
            if "rbdlab_mute_smoke" in ob:
                del ob["rbdlab_mute_smoke"]

            self.unmute_action(rbdlab, ob, mod_name, show_status)
            
            if childs is None:
                continue

            for child in childs:
                self.unmute_action(rbdlab, child, mod_name, show_status)
                if "rbdlab_mute_smoke" in child:
                    del child["rbdlab_mute_smoke"]

            # self.colors_acction(context, ob, col_p_mute)

        deselect_all_objects(context)

        # fuerzo a que recompute la cache:
        domain = [obj for obj in bpy.data.objects if obj.name.endswith(RBDLabNaming.SUFIX_DOMAIN)][0]
        if domain:
            domain.modifiers[RBDLabNaming.SMOKE_MOD].domain_settings.resolution_max = domain.modifiers[RBDLabNaming.SMOKE_MOD].domain_settings.resolution_max

        if len(self.unmuted_count) == 0:
            rbdlab.filtered_target_collection["feedback_mute_smoke"] = ""
        else:
            rbdlab.filtered_target_collection["feedback_mute_smoke"] = "Unmuted:"
            rbdlab.filtered_target_collection["feedback_mute_smoke"] += " ##### " + str(len(self.unmuted_count))

        return {'FINISHED'}


class RBDLAB_OT_select_muted_smoke(Operator):
    bl_idname = "rbdlab.select_muted_smoke"
    bl_label = "Select Muted Smoke"

    def execute(self, context):
        scn = context.scene
        rbdlab = scn.rbdlab

        bpy.ops.object.select_all(action='DESELECT')

        for ob in rbdlab.filtered_target_collection.objects:

            if ob.type != 'MESH' or not ob.visible_get():
                continue

            if "rbdlab_mute_smoke" in ob:
                ob.select_set(True)

        if context.selected_objects:
            self.report({'INFO'}, "Selected " + str(len(context.selected_objects)) + " objects!")
        else:
            if "feedback_mute_smoke" in rbdlab.filtered_target_collection:
                del rbdlab.filtered_target_collection["feedback_mute_smoke"]
            self.report({'INFO'}, "Not Muted objects!")

        return {'FINISHED'}
