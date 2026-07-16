import bpy
from bpy.types import Panel
from ..main.module_panel import ModulePanel
# import os
# from bl_ui.utils import PresetPanel
from .smoke_emiter import draw_smoke_flow_ui
from .smoke_domain import draw_smoke_domain_ui
from ...addon.naming import RBDLabNaming
from ..common_ui_elements import title_header, collapsable, cheker_item_visibility

# class SMOKE_PT_presets(PresetPanel, Panel):
#     bl_label = "My Presets"
#     preset_subdir = os.path.join("RBDLab", "Smoke")
#     preset_operator = "script.execute_preset"
#     preset_add_operator = "rbdlab.particles_add_preset"


class SMOKE_PT_ui(Panel, ModulePanel):
    rbdlab_section = 'SMOKE'
    bl_label = "Module"
    bl_idname = "SMOKE_PT_ui"
    # bl_options = {'DEFAULT_CLOSED'}

    # def draw_header_preset(self, _context):
    #     SMOKE_PT_presets.draw_panel_header(self.layout)

    def draw(self, context):
        scene = context.scene
        rbdlab = scene.rbdlab
        ui = rbdlab.ui

        layout = self.layout

        layout.enabled = cheker_item_visibility(context)

        smoke_props = rbdlab.smoke

        rbw = scene.rigidbody_world

        col = layout.column(align=True)
        title_header(col, "Smoke")
        main_col = col.box().column(align=True)

        if rbdlab.low_or_high_visibility_viewport != "Low":
            main_col.box().label(text="Please Continue Working in Low mode", icon='ERROR')
            # main_col.separator()

        layout.use_property_split = True
        layout.use_property_decorate = False

        '''
        # comento los msg de outdated 
        if rbw and "has_smoke" not in rbdlab.filtered_target_collection:
            col_cache_msg = layout.grid_flow(align=True).box()
        '''

        # col = layout.grid_flow(align=True)

        main_col = col.box().column(align=True)
        main_col.enabled = rbdlab.low_or_high_visibility_viewport == "Low"

        tc = rbdlab.filtered_target_collection
        if not tc:
            main_col.box().label(text="Target Collection is Empty!", icon='ERROR')
            return

        has_smoke = rbdlab.has_smoke()
        has_smoke_ps = rbdlab.has_smoke_ps()

        if has_smoke:

            domain_fluid = rbdlab.get_smoke_domain_mod(context, False)
            flow = main_col.grid_flow(row_major=True, columns=2, even_columns=True, even_rows=False, align=True)
            flow.use_property_split = False
            flow.scale_y = 1.3
            if domain_fluid:
                flow.prop(
                    domain_fluid, "show_viewport",
                    text="Enable / Disable")

            bt_remove = flow.row(align=True)
            bt_remove.alert = True
            bt_remove.operator("rbdlab.smoke_remove", text="Remove Smoke", icon='TRASH')

            # col = main_col.column(align=True)
            main_col.separator()
            header = main_col.row(align=True)
            header.scale_y = 1.3
            header.use_property_split = False
            header.prop(rbdlab.ui, "selected_smoke_entity",
                        expand=True, text=" ")

            if not rbdlab.smoke.toggle_play:
                icon_play = 'PLAY'
            else:
                icon_play = 'SNAP_FACE'

            header.operator("rbdlab.smoke_play", icon=icon_play, text="")

            main_col.separator()
            if rbdlab.ui.selected_smoke_entity == 'FLOW':
                draw_smoke_flow_ui(self, context, main_col)
            else:
                draw_smoke_domain_ui(self, context, main_col)

        else:
            if rbw:
                '''
                # comento los msg de outdated 
                msg_cache_status = rbw.point_cache.info
                '''
                valid_objects = []

                if not rbw.point_cache.is_baked:
                    # si se detectan keyframes se da por hecho q tiene bake a keyframes y no se muestra el label:
                    if rbdlab.filtered_target_collection:
                        coll_name = rbdlab.filtered_target_collection.name
                        if coll_name:
                            valid_objects = [
                                obj for obj in bpy.data.collections[coll_name].objects
                                if obj.type == 'MESH' and obj.visible_get() and obj.name != RBDLabNaming.GROUND and
                                RBDLabNaming.SUFIX_BBOX
                                not in obj.name and RBDLabNaming.PASSIVE
                                not in obj and obj.animation_data is
                                not None and obj.animation_data.action is
                                not None and len(obj.animation_data.action.fcurves) > 0]

                            if not valid_objects:
                                if "has_smoke" not in rbdlab.filtered_target_collection:
                                    col_cache_msg = layout.grid_flow(align=True).box()
                                    row_1_ch_msg = col_cache_msg.column()
                                    # row_1_ch_msg.alert = True
                                    row_1_ch_msg.label(text="It is important to bake first!", icon='INFO')
            '''
            # comento los msg de outdated 
            if rbw:
                if rbw.point_cache.info:
                    row_2_ch_msg = col_cache_msg.column()
                    if "outdated" in msg_cache_status:
                        row_2_ch_msg.alert = True

                    if "outdated" in msg_cache_status:
                        icon_cache_msg = 'ERROR'
                    else:
                        icon_cache_msg = 'INFO'

                    row_2_ch_msg.label(text=msg_cache_status, icon=icon_cache_msg)

                    if icon_cache_msg == 'ERROR':
                        row_2_ch_msg.label(text="Your cache is out of date, you should redo bake.")
            '''

            no_particles = smoke_props.source == 'PARTICLES' and not has_smoke_ps

            col_add = col.column(align=True)
            col_add.scale_y = 1.3

            # recalculate:
            # op_add = col_add.column()
            # op_add.operator("rbdlab.compute_velocities", text="Compute velocities")

            section = main_col.column(align=True)
            header = section.row(align=True)
            header.label(text="Emission Settings", icon='MOD_FLUID')
            section.separator()
            actions_col = section.column(align=True)
            actions_col.scale_y = 1.3

            ppt_source = actions_col.row(align=True)  # heading="Emit from :")
            ppt_source.use_property_split = False
            ppt_source.row(align=True).prop(smoke_props, "source", text="Source", expand=True)

            # row = col_add.row(align=True)
            # row.use_property_split = False
            # # row.label(icon='OUTLINER_OB_VOLUME')
            # row.prop(smoke_props, "density_multiplier", text="Density Multiplier", icon='OUTLINER_OB_VOLUME', expand=True)
            # # row.scale_y = 0.8

            op_add = actions_col.column(align=True)
            op_add.enabled = not no_particles and rbdlab.low_or_high_visibility_viewport == "Low"
            op_add.operator("rbdlab.smoke_add", text="Add Smoke", icon='ADD')

            if no_particles:
                alert = col.box().row(align=True)
                # alert.alert = True
                alert.label(text="Please, create Smoke Particles to continue!", icon='INFO')

        main_col.separator()
        filter_smoke = collapsable(
            col,
            ui,
            "show_hide_filter_smoke",
            "Filter Smoke",
            'FILTER',
            align=True,
        )
        if filter_smoke:

            filter_smoke.prop(rbdlab, "smoke_mute_size_delimiter", text="Select Small")
            row = filter_smoke.row(align=True)
            row.scale_y = 1.3
            row.operator("rbdlab.mute_smoke", text="Mute", icon='HIDE_ON')
            row.operator("rbdlab.unmute_smoke", text="UnMute", icon='HIDE_OFF')
            row.operator("rbdlab.select_muted_smoke", text="", icon='RESTRICT_SELECT_OFF')

            # texto de feedback de smoke muted
            if rbdlab.filtered_target_collection:
                coll_name = rbdlab.filtered_target_collection.name
                if coll_name:
                    if "feedback_mute_smoke" in bpy.data.collections[coll_name]:
                        if rbdlab.filtered_target_collection["feedback_mute_smoke"]:
                            box = col.box().box().column(align=True)
                            n = 0
                            for text in rbdlab.filtered_target_collection["feedback_mute_smoke"].split("#####"):
                                if text:
                                    if n == 0:
                                        box.label(text=text, icon='INFO')
                                    else:
                                        if text.replace(" ", "") == '1':
                                            box.label(text=text + " Chunk")
                                        else:
                                            box.label(text=text + " Chunks")
                                    n += 1

            if rbdlab.filtered_target_collection:
                if rbdlab.filtered_target_collection.name:
                    filter_smoke.enabled = "has_smoke" in rbdlab.filtered_target_collection
                else:
                    filter_smoke.enabled = False
            else:
                filter_smoke.enabled = False

            '''
            # comento los msg de outdated 
            rbw = scene.rigidbody_world
            if rbw:
                msg_cache_status = rbw.point_cache.info
                if "outdated" in msg_cache_status:
                    op_add.enabled = False
            '''


'''
        if rbdlab.low_or_high_visibility_viewport == "Low":

            if not has_smoke:
                col.prop(smoke_props, "source", text="Emit From")

            col.prop(smoke_props, "density_multiplier", text="Density multiplier")
            col.prop(smoke_props, "fuel_multiplier", text="Fuel multiplier")

            if not has_smoke:
                col_add = col.column()
                col_add.operator("rbdlab.smoke_add", text="Add Smoke")

                if rbdlab.smoke.source == 'CHUNKS':
                    control_add = True
                else:
                    if "particles_smoke" in rbdlab.filtered_target_collection:
                        control_add = True
                    else:
                        control_add = False

                col_add.enabled = control_add

            if rbdlab.smoke.source == 'PARTICLES':
                if has_smoke:
                    row = col.row(align=True)
                    row.label(text="Flow Source")
                    row.operator("rbdlab.smoke_flow_source", text="Mesh").type = 'MESH'
                    row.operator("rbdlab.smoke_flow_source", text="Particles").type = 'PARTICLES'

            if has_smoke:
                op_delete = col.row()
                op_delete.scale_y = 1.2
                op_delete.alert = True
                op_delete.operator("rbdlab.smoke_remove", text="Remove Smoke", icon='TRASH')
'''
