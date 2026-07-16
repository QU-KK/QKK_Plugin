import bpy
# from ...addon.paths import RBDLabPreferences
from bpy.types import Operator
from bpy.props import EnumProperty
from ...addon.naming import RBDLabNaming
from ...Global.functions import remove_all_keyframes_in_action
from ...Global.get_common_vars import get_common_vars


class RBDLAB_OT_mute_particles(Operator):
    bl_idname = "rbdlab.mute_particles"
    bl_label = "Mute Particles"

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

    @classmethod
    def description(cls, _context, properties):
        return "Mute %s particles" % properties.type

    def colors_acction(self, context, ob, col_p_mute):
        ob.color_stack.add_color(col_p_mute)
        ob.color = col_p_mute
        remove_all_keyframes_in_action(context, ob, "color")
        if ob.parent and ob.parent.type == 'MESH':
            remove_all_keyframes_in_action(context, ob.parent, "color")
            ob.parent.color_stack.add_color(col_p_mute)
            ob.parent.color = col_p_mute

        # if RBDLabNaming.CHUNK_PART_CHILD in ob:
        #     childs = ob[RBDLabNaming.CHUNK_PART_CHILD]
        #     if childs:
        #         for child in childs:
        #             remove_all_keyframes_in_action(context, child, "color")
        #             child.color_stack.add_color(col_p_mute)
        #             child.color = col_p_mute

    @staticmethod
    def mute_acction(rbdlab, ob, ps_name):

        for ps_modifier in ob.modifiers:
            if not ps_modifier.name.startswith(ps_name):
                continue

            # para que mute solo al ps con el q se este trabajando:
            if rbdlab.ui.selected_particle_type not in ps_modifier.name:
                continue

            ps_modifier.show_viewport = False
            ps_modifier.show_render = False

    def execute(self, context):

        rbdlab, tcoll_list = get_common_vars(context, get_rbdlab=True, get_tcoll_list=True)
        
        tcoll = tcoll_list.active
        # addon_preferences = RBDLabPreferences.get_prefs(context)

        if not rbdlab.has_particles(self.type):
            self.report({'WARNING'}, "Current collection does not have %s particles!" % self.type)
            return {'CANCELLED'}

        coll_name = tcoll.name
        if not coll_name:
            return {'CANCELLED'}

        ps_names = (coll_name + "_debris_", coll_name + "_dust_", coll_name + "_smoke_")
        # col_p_mute = list(addon_preferences.col_p_mute)

        muted_count = []
        for ob in tcoll.objects:

            if ob.type != 'MESH' or not ob.visible_get() or not ob.select_get():
                continue

            """ 
                
                En una escena no está encontrando los childs CHUNK_PART_CHILD objects en la escena.
                Una hipotesis es que al borrar las particulas no se actualice el property guardado o algo :S ni idea.
                Queda apuntado para revisarlo más adelante.

            """

            childs = None    
            if RBDLabNaming.CHUNK_PART_CHILD in ob:
                childs = ob[RBDLabNaming.CHUNK_PART_CHILD]
                # print(ob.name, ob[RBDLabNaming.CHUNK_PART_CHILD])

            if childs is None:
                # print("skip")
                continue

            for child in childs:

                # self.colors_acction(context, child, col_p_mute)

                for ps_name in ps_names:
                    self.mute_acction(rbdlab, child, ps_name)

                if len(child.particle_systems) > 0:
                    child["rbdlab_mute_particles_" + self.type] = True
                    muted_count.append(child)

        # este o no lo reseteo siempre:
        rbdlab.filtered_target_collection["feedback_mute_particles"] = "Muted:"
        rbdlab.filtered_target_collection["feedback_mute_particles"] += " ##### " + str(len(muted_count))

        if len(muted_count) == 0:
            rbdlab.filtered_target_collection["feedback_mute_particles"] = ""

        return {'FINISHED'}


class RBDLAB_OT_unmute_particles(Operator):
    bl_idname = "rbdlab.unmute_particles"
    bl_label = "Unmute Particles"

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

    @classmethod
    def description(cls, _context, properties):
        return "Unmute %s particles" % properties.type

    def colors_acction(self, ob, col_p_mute):
        ob.color_stack.rm_color(col_p_mute)
        color = ob.color_stack.get_last_color()
        if color:
            ob.color = color
        if ob.parent and ob.parent.type == 'MESH':
            ob.parent.color_stack.rm_color(col_p_mute)
            color = ob.parent.color_stack.get_last_color()
            if color:
                ob.parent.color = color

        # if RBDLabNaming.CHUNK_PART_CHILD in ob:
        #     child = bpy.data.objects.get(ob[RBDLabNaming.CHUNK_PART_CHILD])
        #     if child:
        #         child.color_stack.rm_color(col_p_mute)
        #         color = child.color_stack.get_last_color()
        #         if color:
        #             child.color = color

    @staticmethod
    def unmute_acction(rbdlab, ob, ps_name):
        for ps_modifier in ob.modifiers:

            if not ps_modifier.name.startswith(ps_name):
                continue

            # para que mute solo al ps con el q se este trabajando:
            if rbdlab.ui.selected_particle_type not in ps_modifier.name:
                continue

            ps_modifier.show_viewport = True
            ps_modifier.show_render = True

    def execute(self, context):
        rbdlab = context.scene.rbdlab
        # addon_preferences = RBDLabPreferences.get_prefs(context)

        if not rbdlab.has_particles(self.type):
            self.report({'WARNING'}, "Current collection does not have %s particles!" % self.type)
            return {'CANCELLED'}

        coll_name = rbdlab.filtered_target_collection.name
        if not coll_name:
            return {'CANCELLED'}

        ps_names = (coll_name + "_debris_", coll_name + "_dust_", coll_name + "_smoke_")
        # col_p_mute = list(addon_preferences.col_p_mute)

        muted_chunks = [
            ob for ob in rbdlab.filtered_target_collection.objects
            if ob.type == 'MESH' and ob.visible_get() and "rbdlab_mute_particles_" + self.type in ob and
            len(ob.particle_systems) > 0]

        # unmuted_chunks = [
        #     ob for ob in rbdlab.filtered_target_collection.objects
        #     if ob.type == 'MESH' and "rbdlab_mute_particles_" + self.type
        #     not in ob and len(ob.particle_systems) > 0]

        unmuted_count = []
        for ob in muted_chunks:
            # print(ob.name, ob.select_get())

            if not ob.select_get():
                if "rbdlab_father_obj" in ob:
                    father = bpy.data.objects.get(ob["rbdlab_father_obj"])

                    if father is None:
                        continue

                    if not father.select_get():
                        continue

            if "rbdlab_mute_particles_" + self.type in ob:
                del ob["rbdlab_mute_particles_" + self.type]

            # self.colors_acction(ob, col_p_mute)

            for ps_name in ps_names:
                self.unmute_acction(rbdlab, ob, ps_name)

            unmuted_count.append(ob)

        if len(unmuted_count) == 0:
            rbdlab.filtered_target_collection["feedback_mute_particles"] = ""
        else:
            rbdlab.filtered_target_collection["feedback_mute_particles"] = "Unmuted:"
            rbdlab.filtered_target_collection["feedback_mute_particles"] += " ##### " + str(len(unmuted_count))

        return {'FINISHED'}


class RBDLAB_OT_select_muted_particles(Operator):
    bl_idname = "rbdlab.select_muted_particles"
    bl_label = "Select Muted Particles"

    def execute(self, context):

        rbdlab = get_common_vars(context, get_rbdlab=True)

        bpy.ops.object.select_all(action='DESELECT')

        for ob in rbdlab.filtered_target_collection.objects:

            if ob.type != 'MESH' or not ob.visible_get():
                continue

            if "rbdlab_mute_particles_" + rbdlab.ui.selected_particle_type in ob:
                ob.select_set(True)

        if context.selected_objects:
            self.report({'INFO'}, "Selected " + str(len(context.selected_objects)) + " objects!")
        else:
            if "feedback_mute_particles" in rbdlab.filtered_target_collection:
                del rbdlab.filtered_target_collection["feedback_mute_particles"]
            self.report({'INFO'}, "Not Muted objects!")

        return {'FINISHED'}
