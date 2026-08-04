import bpy
from bpy.types import Operator, Area
from bpy.props import BoolProperty
from ...Global.basics import context_override
from ...addon.naming import RBDLabNaming


# "background_type" : 'VIEWPORT',
# "background_color" : (0.0, 0.0, 0.0),
# "single_color" : (1.0, 1.0, 1.0),
pretty_shading_props = {
    "light": 'MATCAP',
    "color_type": 'MATERIAL',
    "show_xray": False,
    "show_shadows": True,
    "show_cavity": True,
    "show_specular_highlight": False,
    "show_object_outline": False,
    "use_dof": False,
    "cavity_type": 'WORLD',
    "cavity_ridge_factor": 2.5,
    "cavity_valley_factor": 2.5,
}

pretty_display_props = {
    "matcap_ssao_samples": 32,
    "matcap_ssao_distance": 0.2,
    "matcap_ssao_attenuation": 1,
}

default_shading_props = {
    "light": 'STUDIO',
    "color_type": 'OBJECT',
    "show_xray": False,
    "show_shadows": False,
    "show_cavity": False,
    "show_specular_highlight": True,
    "show_object_outline": True,
    "use_dof": False,
    "cavity_type": 'SCREEN',
    "cavity_ridge_factor": 1.0,
    "cavity_valley_factor": 1.0,
}

default_display_props = {
    "matcap_ssao_samples": 16,
    "matcap_ssao_distance": 0.2,
    "matcap_ssao_attenuation": 1,
}

# TODO: cambiar este backup y que la info de aquí se guarde en una custom prop dentro de context.workspace.
backup_shading_props = {}
backup_display_props = {}


class RBLAB_OT_pretty_shading(Operator):
    bl_label = "Pretty Shading"
    bl_idname = "rbdlab.pretty_shading"
    bl_description = "To display the preview in viewport with shadows and more beautiful view mode"

    enable: BoolProperty(default=True)

    def execute(self, context):
        rbdlab = context.scene.rbdlab
        display = context.scene.display
        space_data = context.space_data
        shading = space_data.shading

        if "has_pretty_shading" not in context.workspace and not self.enable:
            return {'CANCELLED'}
        if "has_pretty_shading" in context.workspace and self.enable == context.workspace["has_pretty_shading"]:
            return {'CANCELLED'}

        if self.enable:
            # SHADING.
            for key, value in pretty_shading_props.items():
                if "exploding_mode" not in context.workspace:
                    backup_shading_props[key] = getattr(shading, key)
                setattr(shading, key, value)
            # DISPLAY.
            for key, value in pretty_display_props.items():
                if "exploding_mode" not in context.workspace:
                    backup_display_props[key] = getattr(display, key)
                setattr(display, key, value)

            space_data.overlay.show_relationship_lines = False
            context.workspace["has_pretty_shading"] = True

            # sobreescribir el contexto:
            def callback(context) -> None:
                area = context.area  # Accedemos al área desde el contexto
                for space in area.spaces:
                    if space.type == 'VIEW_3D':
                        space.shading.type = 'SOLID'
                area.tag_redraw()
            context_override(context=context, area_type='VIEW_3D', callback=callback)

        else:
            # DISPLAY.
            if backup_display_props != pretty_display_props:
                if backup_display_props:
                    # if have backup and if backup is diferent
                    # then restore the backup:
                    for key, value in backup_display_props.items():
                        setattr(display, key, value)
                else:
                    # else restore dafault settings
                    for key, value in default_display_props.items():
                        setattr(display, key, value)
            else:
                # else restore dafault settings
                for key, value in default_display_props.items():
                    setattr(display, key, value)

            # SHADING.
            if backup_shading_props != pretty_shading_props:
                if backup_shading_props:
                    # if have backup and if backup is diferent
                    # then restore the backup:
                    for key, value in backup_shading_props.items():
                        setattr(shading, key, value)
                else:
                    # else restore dafault settings
                    for key, value in default_shading_props.items():
                        setattr(shading, key, value)
            else:
                # else restore dafault settings
                for key, value in default_shading_props.items():
                    setattr(shading, key, value)

            if rbdlab.colorize and "exploding_mode" in context.workspace:
                rbdlab.colorize = True

            space_data.overlay.show_relationship_lines = True
            context.workspace["has_pretty_shading"] = False

            if rbdlab.ui.main_modules == 'MATERIALS':
                # sobreescribir el contexto:
                def callback(area:Area) -> None:
                    area = context.area  # Accedemos al área desde el contexto
                    for space in area.spaces:
                        if space.type == 'VIEW_3D':
                            space.shading.type = 'MATERIAL'
                    area.tag_redraw()
                context_override(context=context, area_type='VIEW_3D', callback=callback)

        return {'FINISHED'}


class RBLAB_OT_show_boundingbox(Operator):
    bl_label = "Show/Hide BoundingBox"
    bl_idname = "rbdlab.show_boundingbox"
    bl_description = "To improve performance and preview the current target collection in box mode"

    enable: BoolProperty(default=True)

    def execute(self, context):
        rbdlab = context.scene.rbdlab

        if rbdlab.filtered_target_collection:

            coll_name = rbdlab.filtered_target_collection.name
            if RBDLabNaming.SUFIX_LOW in coll_name:
                coll_name_high = coll_name.replace(RBDLabNaming.SUFIX_LOW, RBDLabNaming.SUFIX_HIGH)
            else:
                coll_name_high = coll_name + RBDLabNaming.SUFIX_HIGH

            if coll_name:

                if coll_name_high:
                    if rbdlab.low_or_high_visibility_viewport == "Low":
                        rbdlab.status_show_boundingbox_in_low = self.enable
                    else:
                        rbdlab.status_show_boundingbox_in_high = self.enable

                    for obj in bpy.data.collections[coll_name].objects:
                        if obj.type == 'MESH' and obj.visible_get():
                            if rbdlab.status_show_boundingbox_in_low:
                                obj.display_type = 'BOUNDS'
                                self.enable = True
                            else:
                                obj.display_type = 'TEXTURED'
                                self.enable = False
                else:
                    for obj in bpy.data.collections[coll_name].objects:
                        if obj.type == 'MESH' and obj.visible_get():
                            if obj.display_type == 'TEXTURED':
                                obj.display_type = 'BOUNDS'
                                self.enable = True
                            else:
                                obj.display_type = 'TEXTURED'
                                self.enable = False

                # si hay highs:
                if coll_name_high in bpy.data.collections:
                    for obj in bpy.data.collections[coll_name_high].objects:
                        if obj.type == 'MESH' and obj.visible_get():
                            if rbdlab.status_show_boundingbox_in_high:
                                obj.display_type = 'BOUNDS'
                                self.enable = True
                            else:
                                obj.display_type = 'TEXTURED'
                                self.enable = False

        return {'FINISHED'}


class RBLAB_OT_unhide_all_emitters_with_particles(Operator):
    bl_label = "UnHide all emitters with particles"
    bl_idname = "rbdlab.unhide_emitters_with_particles"
    bl_description = "Unhide emitters with particles"

    def execute(self, context):
        scn = context.scene
        rbdlab = scn.rbdlab

        if rbdlab.filtered_target_collection:
            coll_name = rbdlab.filtered_target_collection.name
            if coll_name:

                for obj in rbdlab.filtered_target_collection.objects:

                    if obj.type != 'MESH':
                        continue

                    if RBDLabNaming.INNER_EMISOR not in obj:
                        continue

                    if not obj.hide_get():
                        continue

                    obj.hide_set(False)

        return {'FINISHED'}
