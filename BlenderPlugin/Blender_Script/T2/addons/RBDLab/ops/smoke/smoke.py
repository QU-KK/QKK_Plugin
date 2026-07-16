import bpy
from datetime import datetime
from bpy.types import Operator, Menu
from bpy.props import EnumProperty
import time
import tempfile

from .smoke_common import smoke_common
from ...Global.functions import (
    generate_bounding_box,
    add_fluid_modifier_to_active_object,
    create_modifier,
    remove_smoke_from_chunks,
    append_materials,
    set_active_collection_to_master_coll
)
from ...Global.basics import select_object, set_active_object, deselect_all_objects, rm_ob
from ...addon.paths import RBDLabPreferences
from ...addon.naming import RBDLabNaming

from bl_operators.presets import AddPresetBase
import os
from os.path import join

from ...addon.paths import RBDLabPreferences


class SMOKE_MT_Presets(Menu):
    bl_label = "My Presets"
    preset_subdir = os.path.join("RBDLab", "Smoke")
    preset_operator = "script.execute_preset"
    draw = Menu.draw_preset


class SMOKE_OT_Add_Preset(AddPresetBase, Operator):
    bl_idname = "rbdlab.smoke_add_preset"
    bl_label = "Add smoke preset"
    preset_menu = "SMOKE_MT_Presets"
    # Common variable used for all preset values:
    preset_defines = ["rbdlab = bpy.context.scene.rbdlab"]
    # Properties to store in the preset:
    preset_values = [
        "",
    ]
    # Directory to store the presets
    preset_subdir = os.path.join("RBDLab", "Smoke")


class SMOKE_OT_add(Operator):
    bl_idname = "rbdlab.smoke_add"
    bl_label = "Add Smoke"
    bl_description = "Add Smoke"
    bl_options = {'PRESET'}
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        # Si "filtered_target_collection" es nulo no se ejecutará el Operator y el botón saldrá desactivado.
        return context.scene.rbdlab.filtered_target_collection is not None and context.scene.rbdlab.filtered_target_collection.name

    @classmethod
    def description(cls, context, _properties):
        if not context.scene.rbdlab.filtered_target_collection:
            return "You need to select a target collection (viewport's header)"
        return cls.bl_description

    def execute(self, context):
        start = datetime.now()

        scn = context.scene
        rbdlab = scn.rbdlab

        tcoll_list = rbdlab.lists.target_coll_list
        tcoll = tcoll_list.active

        addon_preferences = RBDLabPreferences.get_prefs(context)

        domain_name = RBDLabNaming.DOMAIN_NAME
        chunks = tcoll_list.get_current_active_tcoll_valild_objects(context)

        if not chunks or tcoll is None:
            # print("Not chunks detected!")
            return {'CANCELLED'}

        ''' SMOKE COMMON FUNCTION '''
        check = smoke_common(self, context, tcoll, rbdlab.smoke.source)
        if not check:
            # print("Not check detected!")
            return {'CANCELLED'}

        domains = [ob for ob in context.scene.objects if ob.name.endswith(RBDLabNaming.SUFIX_DOMAIN)]

        if addon_preferences.auto_add_sun_on_smoke_creation:
            sun_name = "Sun_Domain_system"
            sun_exist = len([ob for ob in context.scene.objects if ob.name == sun_name]) > 0
            if not sun_exist:
                set_active_collection_to_master_coll(context)
                bpy.ops.object.light_add(type='SUN', align='WORLD', location=(0, 0, 19), scale=(1, 1, 1))
                sun = context.active_object
                sun.name = sun_name
                sun.rotation_euler[0] = -0.610865
                sun.rotation_euler[2] = -2.61799
                context.object.data.color = (1, 0.947217, 0.798777)

        if len(domains) == 0:
            # create domain
            offset_x = 0.5
            offset_y = 0.5
            offset_z = 0.5
            clamp = 12
            domain = generate_bounding_box(self, context, chunks, "Mesh", False, offset_x,
                                           offset_y, offset_z, domain_name, "StartEnd", clamp)
            if domain:
                domain_mod = add_fluid_modifier_to_active_object(context, 'DOMAIN')
            # end create domain
        else:
            domain = domains[-1]

        if domain:

            # Si existe domain, por rendimiento primero se desactiva:
            if RBDLabNaming.SMOKE_MOD in domain.modifiers:
                domain.modifiers[RBDLabNaming.SMOKE_MOD].show_viewport = False

            # marco al domain como RBDLab_Domain para poder verlo/filtrarlo en VDBLab:
            domain[RBDLabNaming.DOMAIN_NAME] = RBDLabNaming.DOMAIN_NAME

            # seteamos las propiedades del domain
            domain_mod = domain.modifiers[RBDLabNaming.SMOKE_MOD]
            if domain_mod:
                domain_settings = domain_mod.domain_settings

                # domain.location.z = (domain.dimensions.z / 2) - (domain_mod.domain_settings.resolution_max / 50)
                domain_settings.use_dissolve_smoke = True
                domain_settings.use_adaptive_domain = True
                domain_settings.dissolve_speed = 10
                domain_settings.resolution_max = domain_mod.domain_settings.resolution_max
                domain_settings.use_adaptive_timesteps = False
                domain_settings.adapt_threshold = 0.001

                current_name = domain.name
                root_path = tempfile.gettempdir()

                if bpy.data.is_saved:
                    blend_file_name = bpy.path.basename(context.blend_data.filepath).replace(".blend", "")
                else:
                    blend_file_name = "Unsaved_Scene" + "_" + time.strftime("%dd_%Hh_%Mm_%Ss")

                addon_preferences = RBDLabPreferences.get_prefs(context)
                smoke_cache_path = addon_preferences.cache_path

                if smoke_cache_path == "":
                    new_cache_path = join(root_path, blend_file_name, current_name)
                else:
                    new_cache_path = join(smoke_cache_path, blend_file_name)

                domain_settings.cache_directory = new_cache_path

                if rbdlab.bake.sync_frame_end:
                    domain_settings.cache_frame_end = rbdlab.bake.frame_end

            # append material smoke
            mat_name = RBDLabNaming.SMOKE_SHADER
            append_materials(context, domain.name, mat_name)

            # si hay suelo le pongo como effector:
            if RBDLabNaming.GROUND in context.scene.objects:
                ground = context.scene.objects.get(RBDLabNaming.GROUND)
                name = "RBDLab_GSmoke"
                set_active_object(context, ground)
                if name not in ground.modifiers:
                    gound_mod = create_modifier(ground, name, 'FLUID')
                    gound_mod.fluid_type = 'EFFECTOR'

            deselect_all_objects(context)

            if rbdlab.smoke.source == 'PARTICLES':
                rbdlab.smoke.emiter.flow_source = 'PARTICLES'
            else:
                rbdlab.smoke.emiter.flow_source = 'MESH'

            rbdlab.set_flag("has_smoke")

            context.scene.frame_set(context.scene.frame_start)
            print("smoke end: " + str(datetime.now() - start))

            # Si existe domain, por rendimiento primero se desactiva pero ahora lo vuelvo a restablecer:
            if RBDLabNaming.SMOKE_MOD in domain.modifiers:
                domain.modifiers[RBDLabNaming.SMOKE_MOD].show_viewport = True

            # al agregar un domain lo dejamos la seleccion en modo Faces para facilitar su edicion:
            context.tool_settings.mesh_select_mode = (False, False, True)

        if RBDLabNaming.COLL_WITH_SMOKE not in rbdlab.filtered_target_collection:
            rbdlab.filtered_target_collection[RBDLabNaming.COLL_WITH_SMOKE] = RBDLabNaming.COLL_WITH_SMOKE

        return {'FINISHED'}


class SMOKE_OT_flow_source(Operator):
    bl_idname = "rbdlab.smoke_flow_source"
    bl_label = "Smoke Flow Source"
    bl_description = "Flow Source"
    bl_options = {'REGISTER', 'UNDO'}

    type: EnumProperty(name="Slow Source type",
                       items=(
                           ('MESH', "Mesh", ""),
                           ('PARTICLES', "Particles", ""),
                       ),
                       default='MESH')

    @classmethod
    def poll(cls, context):
        rbdlab = context.scene.rbdlab

        # Si "filtered_target_collection" es nulo no se ejecutará el
        # Operator y el botón saldrá desactivado.
        if not rbdlab.filtered_target_collection:
            return False
        try:
            return rbdlab.filtered_target_collection["has_smoke"]
        except KeyError:
            return False

    def execute(self, context):
        rbdlab = context.scene.rbdlab

        if rbdlab.filtered_target_collection:
            coll_name = rbdlab.filtered_target_collection.name
            if coll_name:
                for ob in rbdlab.filtered_target_collection.objects:
                    if ob.type == 'MESH' and ob.visible_get():
                        if RBDLabNaming.SMOKE_MOD in ob.modifiers:
                            smoke_mod = ob.modifiers[RBDLabNaming.SMOKE_MOD]
                            smoke_mod.flow_settings.flow_source = self.type

                            # if hasattr(ob, "vertex_groups"):
                            #     if "Interior" in ob.vertex_groups:
                            #         smoke_mod.flow_settings.density_vertex_group = "Interior"

        context.scene.frame_set(context.scene.frame_start)
        return {'FINISHED'}


class SMOKE_OT_remove(Operator):
    bl_idname = "rbdlab.smoke_remove"
    bl_label = "Remove Smoke"
    bl_description = "Remove Smoke"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        # Si "filtered_target_collection" es nulo no se ejecutará el Operator y el botón saldrá desactivado.
        if not context.scene.rbdlab.filtered_target_collection:
            return False
        try:
            return context.scene.rbdlab.filtered_target_collection["has_smoke"]
        except KeyError:
            return False

    @classmethod
    def description(cls, context, _properties):
        if not context.scene.rbdlab.filtered_target_collection:
            return "You need to select a target collection (viewport's header)"
        return cls.bl_description

    def colors_acction(self, ob, col_smoke):
        ob.color_stack.rm_color(col_smoke)
        color = ob.color_stack.get_last_color()
        if color:
            ob.color = color
        if ob.parent:
            ob.parent.color_stack.rm_color(col_smoke)
            color = None
            color = ob.color_stack.get_last_color()
            if color:
                ob.parent.color = color

    def execute(self, context):
        rbdlab = context.scene.rbdlab
        # addon_preferences = RBDLabPreferences.get_prefs(context)
        coll_name = rbdlab.filtered_target_collection.name
        domain_name = RBDLabNaming.DOMAIN_NAME

        # guardamos la seleccion del usuario para luego restarurarla:
        selected_objects = []
        for ob in context.selected_objects:
            if ob.name != domain_name:
                selected_objects.append(ob)

        coll_name = rbdlab.filtered_target_collection.name
        if coll_name:
            deselect_all_objects(context)

            sun_name = "Sun_Domain_system"
            sun_exist = [sun_exist for sun_exist in context.scene.objects if sun_exist.name == sun_name]
            if sun_exist:
                bpy.data.objects.remove(sun_exist[0])

            valid_objects = []
            # col_smoke = list(addon_preferences.col_smoke)

            for ob in rbdlab.filtered_target_collection.objects:

                if "rbdlab_mute_smoke" in ob:
                    del ob["rbdlab_mute_smoke"]

                # self.colors_acction(ob, col_smoke)

                if ob.type == 'MESH' and RBDLabNaming.RBD_SEL_KINEMATIC not in ob and RBDLabNaming.PASSIVE not in ob:
                    select_object(context, ob)
                    valid_objects.append(ob)

                    # remove keyframes de density:
                    remove_types = ["density"]
                    if hasattr(ob.animation_data, "action"):
                        action = ob.animation_data.action
                        if action:
                            fcurves = [
                                fc for fc in action.fcurves for type in remove_types if fc.data_path.endswith(type)]

                            while (fcurves):
                                fc = fcurves.pop()
                                action.fcurves.remove(fc)
                    # fin borrar keyframes de density

                    # remove keyframes de fuel:
                    remove_types = ["fuel_amount"]
                    if hasattr(ob.animation_data, "action"):
                        action = ob.animation_data.action
                        if action:
                            fcurves = [
                                fc for fc in action.fcurves for type in remove_types if fc.data_path.endswith(type)]

                            while (fcurves):
                                fc = fcurves.pop()
                                action.fcurves.remove(fc)
                    # fin borrar keyframes de density

        # Borramos los Fluid modifiers de los objetos...
        remove_smoke_from_chunks(context)

        # Borramos el Domain...
        rm_ob(domain_name)

        # Borramos el fluid modifier del suelo...
        # remove_modifier_from_object(RBDLabNaming.GROUND, 'FLUID', True)

        # Recuperamos la selección del usuario.
        deselect_all_objects(context)

        for ob in selected_objects:
            select_object(context, ob)

        rbdlab.remove_flag("has_smoke")

        context.scene.frame_set(context.scene.frame_start)

        #################################################################################
        # reseteo los valores a por default:
        #################################################################################
        rbdlab.smoke.emiter.flow_type = rbdlab.smoke.emiter.get_default_properties(
            "flow_type")
        rbdlab.smoke.emiter.subframes = rbdlab.smoke.emiter.get_default_properties(
            "subframes")
        # rbdlab.smoke.emiter.smoke_color = rbdlab.smoke.emiter.get_default_properties("Smoke Color")
        rbdlab.smoke.emiter.smoke_color = (.7, .7, .7)
        rbdlab.smoke.emiter.temperature = rbdlab.smoke.emiter.get_default_properties(
            "temperature")
        # rbdlab.smoke.emiter.flow_source = rbdlab.smoke.emiter.get_default_properties("Flow Source")
        rbdlab.smoke.emiter.flow_source = 'MESH'
        rbdlab.smoke.emiter.particle_size = rbdlab.smoke.emiter.get_default_properties(
            "particle_size")
        rbdlab.smoke.emiter.surface_distance = rbdlab.smoke.emiter.get_default_properties(
            "surface_distance")
        rbdlab.smoke.emiter.volume_density = rbdlab.smoke.emiter.get_default_properties(
            "volume_density")
        rbdlab.smoke.emiter.use_initial_velocity = rbdlab.smoke.emiter.get_default_properties(
            "use_initial_velocity")
        rbdlab.smoke.emiter.velocity_factor = rbdlab.smoke.emiter.get_default_properties(
            "velocity_factor")
        rbdlab.smoke.emiter.velocity_normal = rbdlab.smoke.emiter.get_default_properties(
            "velocity_normal")
        # rbdlab.smoke.emiter.velocity_coord = rbdlab.smoke.emiter.get_default_properties("Initial")
        rbdlab.smoke.emiter.velocity_coord = (0, 0, 0)

        if RBDLabNaming.CMPUTD_VELOCITIES in rbdlab.filtered_target_collection:
            del rbdlab.filtered_target_collection[RBDLabNaming.CMPUTD_VELOCITIES]

        if RBDLabNaming.COLL_WITH_SMOKE in rbdlab.filtered_target_collection:
            del rbdlab.filtered_target_collection[RBDLabNaming.COLL_WITH_SMOKE]

        return {'FINISHED'}


class SMOKE_OT_update_emiter(Operator):
    bl_idname = "rbdlab.smoke_update_emiter"
    bl_label = "Update Smoke Emiter"
    bl_description = "Update Smoke Emiter"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        if not context.scene.rbdlab.filtered_target_collection:
            return False
        return context.scene.rbdlab.smoke.emiter.dirt is not None

    @classmethod
    def description(cls, context, _properties):
        if not context.scene.rbdlab.filtered_target_collection:
            return "No target collection detected"
        if not context.scene.rbdlab.smoke.emiter.dirt:
            return "There is no changes to update particles"
        return cls.bl_description

    def execute(self, context):
        rbdlab = context.scene.rbdlab
        smoke_emiter = rbdlab.smoke.emiter
        dirties = smoke_emiter.dirt.split(" ")

        for chunk in rbdlab.get_chunks():
            flow = rbdlab.get_smoke_emiter(chunk)
            if not flow:
                continue
            for ppt in dirties:
                if ppt:
                    setattr(flow, ppt, getattr(smoke_emiter, ppt))
                # else:
                #     print(ppt, "property not found! (in smoke.update_emiter)")

            # restauramos las particulas y el resto de settings q hacen falta para el unmute
            if RBDLabNaming.SMOKE_MOD in chunk.modifiers:
                mod = chunk.modifiers[RBDLabNaming.SMOKE_MOD]
                if rbdlab.smoke.emiter.flow_source == 'PARTICLES':
                    mod.flow_settings.flow_source = 'PARTICLES'
                    if mod.flow_settings.particle_system is None:
                        ps_smoke_name = [ps.name for ps in chunk.particle_systems if "_smoke_motion_" in ps.name]
                        if len(ps_smoke_name) > 0:
                            mod.flow_settings.particle_system = chunk.particle_systems[ps_smoke_name[0]]
                            mod.flow_settings.flow_behavior = 'INFLOW'
                else:
                    mod.flow_settings.surface_distance = rbdlab.smoke.emiter.surface_distance
                    mod.flow_settings.volume_density = rbdlab.smoke.emiter.volume_density

        smoke_emiter.dirt = ""
        return {'FINISHED'}
