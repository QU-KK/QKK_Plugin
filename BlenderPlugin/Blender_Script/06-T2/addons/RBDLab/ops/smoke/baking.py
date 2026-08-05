import bpy
from bpy.types import Operator
from ...Global.functions import set_active_object, deselect_all_objects
from ...addon.naming import RBDLabNaming


def bake_function(self, target: str, domain):

    # El unico motivo para hacer estos ops de bypass es porque
    # para poder hacer los bake tiene q sel el activo y estar seleccionado el
    # domain al que se le va a hacer el bake.

    if domain:

        if target == "modular_baking_data":
            result = bpy.ops.fluid.bake_data('INVOKE_DEFAULT')

        elif target == "modular_free_data":
            result = bpy.ops.fluid.free_data()

        elif target == "modular_baking_noise":
            result = bpy.ops.fluid.bake_noise('INVOKE_DEFAULT')

        elif target == "modular_free_noise":
            result = bpy.ops.fluid.free_noise()

        elif target == "bake_all":
            result = bpy.ops.fluid.bake_all('INVOKE_DEFAULT')

        elif target == "bake_free_all":
            result = bpy.ops.fluid.free_all()

        if result != {'RUNNING_MODAL'}:
            self.report({'WARNING'}, "Failed to start baking")
            return {'FINISHED'}


''' MODULAR DATA BAKE/FREE '''


def common_code(self, context, bake_function, type_bake: str):
    domains = [obj for obj in bpy.data.objects if obj.name.startswith(RBDLabNaming.DOMAIN_NAME)]
    if domains:
        domain = domains[0]

    if domain:
        # previous_selection = context.selected_objects
        # previous_active = context.active_object

        deselect_all_objects(context)

        domain.select_set(True)
        set_active_object(context, domain)

        # bake
        bake_function(self, type_bake, domain)

        # si restauto la seleccion en linux no me hace el bake porque no se
        # esperar a que se ejecute cuando termine el bakeo.
        # deselect_all_objects(context)

        # if previous_selection:
        #     for obj in previous_selection:
        #         obj.select_set(True)

        # if previous_active:
        #     set_active_object(context, previous_active)


class RBDLab_OT_domain_modular_baking_data(Operator):
    bl_idname = "rbdlab.domain_modular_baking_data"
    bl_label = "Modular Baking Data"
    bl_description = "Modular Baking Data"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):

        common_code(self, context, bake_function, "modular_baking_data")

        return {'FINISHED'}


class RBDLab_OT_domain_modular_free_data(Operator):
    bl_idname = "rbdlab.domain_modular_free_data"
    bl_label = "Modular Free Data"
    bl_description = "Modular Free Data"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):

        common_code(self, context, bake_function, "modular_free_data")

        return {'FINISHED'}


''' MODULAR NOISE/FREE '''


class RBDLab_OT_domain_modular_baking_noise(Operator):
    bl_idname = "rbdlab.domain_modular_baking_noise"
    bl_label = "Modular Baking Noise"
    bl_description = "Modular Baking Noise"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):

        common_code(self, context, bake_function, "modular_baking_noise")

        return {'FINISHED'}


class RBDLab_OT_domain_modular_free_noise(Operator):
    bl_idname = "rbdlab.domain_modular_free_noise"
    bl_label = "Modular Free Noise"
    bl_description = "Modular Free Noise"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):

        common_code(self, context, bake_function, "modular_free_noise")

        return {'FINISHED'}


''' ALL DATA BAKE/RESUME/FREE_ALL '''


class RBDLab_OT_domain_bake_all(Operator):
    bl_idname = "rbdlab.domain_bake_all"
    bl_label = "Bake All"
    bl_description = "Bake All"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):

        common_code(self, context, bake_function, "bake_all")

        return {'FINISHED'}


class RBDLab_OT_domain_bake_free_all(Operator):
    bl_idname = "rbdlab.domain_bake_free_all"
    bl_label = "Bake Free All"
    bl_description = "Bake Free All"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):

        common_code(self, context, bake_function, "bake_free_all")

        return {'FINISHED'}
