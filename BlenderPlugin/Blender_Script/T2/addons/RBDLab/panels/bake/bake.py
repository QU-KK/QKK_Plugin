import bpy
from ..main.module_panel import ModulePanel
from bpy.types import Panel
from ..common_ui_elements import title_header, cheker_item_visibility
from ...Global.functions import have_rigidbodies_in_active_group


def custom_point_cache_ui(self, context, rbdlab, layout, cache, enabled):

    layout.use_property_split = True
    layout.context_pointer_set("point_cache", cache)

    # is_saved = bpy.data.is_saved
    is_liboverride = cache.id_data.override_library is not None

    # NOTE: TODO temporarily used until the animate properties are properly skipped.
    # No animation (remove this later on).
    layout.use_property_decorate = False

    if cache.use_external:
        col = layout.column()
        col.prop(cache, "index", text="Index")
        col.prop(cache, "filepath", text="Path")

        cache_info = cache.info
        if cache_info:
            col = layout.column()
            col.alignment = 'RIGHT'
            col.label(text=cache_info)

    if not cache.use_external:
        col = layout.column(align=True)

        col.enabled = enabled
        col.prop(cache, "frame_start", text="Simulation Start")
        row = col.row(align=True)
        # row.prop(cache, "frame_end")
        row.prop(rbdlab.bake, "frame_end")
        row.prop(rbdlab.bake, "sync_frame_end", text="", icon='UV_SYNC_SELECT')
        # row.operator("rbdlab.bake_transefer_to_frame_end", text="", icon='NLA_PUSHDOWN')
        # row.operator("rbdlab.bake_transefer_to_bk_to_keyframes", text="", icon='NLA_PUSHDOWN')

        cache_info = cache.info
        if cache_info:  # avoid empty space.
            col = layout.column(align=True)
            col.alignment = 'RIGHT'
            col.label(text=cache_info)

        # print("cache_info", cache_info)

        can_bake = True

        # layout.separator()

        flow = layout.grid_flow(row_major=True, columns=0,
                                even_columns=True, even_rows=False, align=False)
        col = flow.column(align=True)
        col.active = can_bake
        col.scale_y = 1.3

        if is_liboverride and not cache.use_disk_cache:
            col.operator("ptcache.bake", icon='ERROR',
                         text="Bake (Disk Cache mandatory)")
        elif cache.is_baked is True:
            col.operator("ptcache.free_bake", text="Delete Bake")
        else:
            col.operator("ptcache.bake", text="Bake").bake = True

        # sub = col.row()
        # sub.enabled = enabled
        # sub.operator("ptcache.bake", text="Calculate to Frame").bake = False

        sub = col.column(align=True)
        sub.enabled = enabled
        # my Current Cache to bake for seting end frame to cached frames:
        sub.operator("rbdlab.bake_current_to_cache", text="Current Cache to Bake")
        # original oeprator:
        # sub.operator("ptcache.bake_from_cache", text="Current Cache to Bake")

        # col = flow.column()
        col.operator("ptcache.bake_all", text="Bake All Dynamics").bake = True
        col.operator("ptcache.free_bake_all", text="Delete All Bakes")
        # col.operator("ptcache.bake_all", text="Update All to Frame").bake = False

        rbdlab = context.scene.rbdlab

        if rbdlab.low_or_high_visibility_viewport != "Low":
            col.enabled = False
        else:
            col.enabled = True


def custom_particles_point_cache_ui(self, ui, layout, cache, enabled, cachetype):

    main_col = layout.box().column(align=True)

    main_col.use_property_split = True
    main_col.context_pointer_set("point_cache", cache)

    # is_saved = bpy.data.is_saved
    # is_liboverride = cache.id_data.override_library is not None

    # NOTE: TODO temporarily used until the animate properties are properly skipped.
    main_col.use_property_decorate = False  # No animation (remove this later on).

    # if not cachetype == 'RIGID_BODY':
    #     row = main_col.row()
    #     row.template_list(
    #         "UI_UL_list", "point_caches", cache, "point_caches",
    #         cache.point_caches, "active_index", rows=1,
    #     )
    #     col = row.column(align=True)
    #     col.operator("ptcache.add", icon='ADD', text="")
    #     col.operator("ptcache.remove", icon='REMOVE', text="")

    # if cachetype in {'PSYS', 'HAIR', 'FLUID'}:
    #     col = main_col.column()

    #     if cachetype == 'FLUID':
    #         col.prop(cache, "use_library_path", text="Use Library Path")

    #     col.prop(cache, "use_external")

    # if cache.use_external:
    #     col = main_col.column()
    #     col.prop(cache, "index", text="Index")
    #     col.prop(cache, "filepath", text="Path")

    #     cache_info = cache.info
    #     if cache_info:
    #         col = main_col.column()
    #         col.alignment = 'RIGHT'
    #         col.label(text=cache_info)
    # else:
    #     if cachetype in {'FLUID', 'DYNAMIC_PAINT'}:
    #         if not is_saved:
    #             col = layomain_colut.column(align=True)
    #             col.alignment = 'RIGHT'
    #             col.label(text="Cache is disabled until the file is saved")
    #             main_col.enabled = False

    # if not cache.use_external or cachetype == 'FLUID':
    #     col = main_col.column(align=True)

    #     if cachetype not in {'PSYS', 'DYNAMIC_PAINT'}:
    #         col.enabled = enabled
    #         col.prop(cache, "frame_start", text="Simulation Start")
    #         col.prop(cache, "frame_end")

    #     if cachetype not in {'FLUID', 'CLOTH', 'DYNAMIC_PAINT', 'RIGID_BODY'}:
    #         col.prop(cache, "frame_step")

    #     cache_info = cache.info
    #     if cachetype != 'FLUID' and cache_info:  # avoid empty space.
    #         col = main_col.column(align=True)
    #         col.alignment = 'RIGHT'
    #         col.label(text=cache_info)

    #     can_bake = True

    #     if cachetype not in {'FLUID', 'DYNAMIC_PAINT', 'RIGID_BODY'}:
    #         if not is_saved:
    #             col = main_col.column(align=True)
    #             col.alignment = 'RIGHT'
    #             col.label(text="Options are disabled until the file is saved")

    #         flow = main_col.grid_flow(row_major=True, columns=0, even_columns=True, even_rows=False, align=True)
    #         flow.enabled = enabled and is_saved

    #         col = flow.column(align=True)
    #         col.prop(cache, "use_disk_cache")

    #         subcol = col.column()
    #         subcol.active = cache.use_disk_cache
    #         subcol.prop(cache, "use_library_path", text="Use Library Path")

    #         col = flow.column()
    #         col.active = cache.use_disk_cache
    #         col.prop(cache, "compression", text="Compression")

    #         if cache.id_data.library and not cache.use_disk_cache:
    #             can_bake = False

    #             col = main_col.column(align=True)
    #             col.alignment = 'RIGHT'

    #             col.separator()

    #             col.label(text="Linked object baking requires Disk Cache to be enabled")
    #     else:
    #         main_col.separator()

    
    main_col.separator()
    cache_options = main_col.column(align=True)
    saved_file = bpy.data.is_saved
    cache_options.prop(ui, "bake_particles_point_cache_use_disk_cache", text="Disk Cache")
    c_compression = cache_options.row(align=True)
    c_compression.enabled = ui.bake_particles_point_cache_use_disk_cache
    c_compression.prop(ui, "bake_particles_point_cache_compression", text="Compression")
    cache_options.enabled = saved_file

    if not saved_file:
        main_col.separator()
        main_col.box().label(text="if you want to use disk cache, you need to save first", icon='INFO')
    
    main_col.separator()

    can_bake = True

    flow = main_col.grid_flow(row_major=True, columns=0, even_columns=True, even_rows=False, align=True)
    col = flow.column(align=True)
    col.active = can_bake

    # if is_liboverride and not cache.use_disk_cache:
    #     col.operator("ptcache.bake", icon='ERROR', text="Bake (Disk Cache mandatory)")
    # elif cache.is_baked is True:
    #     col.operator("ptcache.free_bake", text="Delete Bake")
    # else:
    #     col.operator("ptcache.bake", text="Bake").bake = True

    # sub = col.row()
    # sub.enabled = enabled
    # sub.operator("ptcache.bake", text="Calculate to Frame").bake = False

    # col = flow.column()


    col.scale_y = 1.3
    col.operator("ptcache.bake_all", text="Bake All Particles").bake = True

    # esto no me vale porque solo lo hace al sitema de particulas actual:
    # if cache.is_baked is True:
    #     col.operator("ptcache.free_bake", text="Delete Bake")
    # esto lo hace a todos pero tambien pierdes el bake de rbd:
    # col.operator("ptcache.free_bake_all", text="Delete All Bakes")

    # con mi metodo ya funciona:
    col.operator("rbdlab.bake_free_all_particles_cache", text="Delete All Particles Bakes").by_type = False

    # sub = col.column()
    # sub.enabled = enabled
    # sub.operator("ptcache.bake_from_cache", text="Current Cache to Bake")

    # col.operator("ptcache.bake_all", text="Update All to Frame").bake = False


class BAKE_PT_ui(Panel, ModulePanel):
    rbdlab_section = 'BAKE'
    bl_label = "Module"
    bl_idname = "BAKE_PT_ui"


    def draw(self, context):
        scn = context.scene
        rbdlab = scn.rbdlab
        ui = rbdlab.ui

        layout = self.layout

        layout.enabled = cheker_item_visibility(context)

        rbw = scn.rigidbody_world

        col = layout.column(align=True)
        title_header(col, "Bake")
        main_col = col.box().column(align=True)
        main_col.use_property_split = True
        main_col.use_property_decorate = False

        if rbdlab.low_or_high_visibility_viewport != "Low":
            main_col.box().label(text="Please Continue Working in Low mode", icon='ERROR')
            main_col.separator()

        switcher_subsections = main_col.row(align=True)
        switcher_subsections.use_property_split = False
        switcher_subsections.scale_y = 1.3
        switcher_subsections.prop(ui, "bake_sub_sections", expand=True)
        main_col = col.box().column(align=True)
        # main_col.separator()

        if ui.bake_sub_sections == 'RIGIDBODIES':

            # bake rigid bodies
            main_col.box().label(text="Bake RigidBodies", icon='FILE_BACKUP')
            # rbd_bake = collapsable(
            #     main_col,
            #     ui,
            #     "show_hide_rbd_bake",
            #     "RigidBodies",
            #     'ONIONSKIN_ON',
            #     align=True,
            # )
            # if rbd_bake:

            rbd_bake = main_col
            flow = rbd_bake.grid_flow(align=True)
            col = flow.box().column()

            if rbw:
                # cachetype = 'RIGIDBODY'
                custom_point_cache_ui(self, context, rbdlab, col, rbw.point_cache,
                                      rbw.point_cache.is_baked is False and rbw.enabled)
            else:
                col.alert = True
                col.label(text="No rigid bodies at the moment in the scene", icon='INFO')

        elif ui.bake_sub_sections == 'BK_TO_KEYFRAMES':

            # to keyframes:
            main_col.box().label(text="Bake To Keyframes", icon='KEYFRAME_HLT')

            # rbd_bake_to_keyframes = collapsable(
            #     main_col,
            #     ui,
            #     "show_hide_rbd_bake_to_keyframes",
            #     "To Keyframes",
            #     'ONIONSKIN_ON',
            #     align=True,
            # )
            # if rbd_bake_to_keyframes:

            rbd_bake_to_keyframes = main_col
            flow = rbd_bake_to_keyframes.grid_flow(align=True)

            col = flow.box().column(align=True)
            col.prop(rbdlab.bake, "bk_to_kf_by_selection", text="By Selection")
            col.prop(rbdlab.bake, "bk_to_kf_start", text="start")
            col.prop(rbdlab.bake, "bk_to_kf_end", text="end")
            col.prop(rbdlab.bake, "bk_to_kf_steps", text="Frame Step")

            col.operator_context = 'INVOKE_DEFAULT'
            col.separator()
            bt_bk_to_kf = col.row(align=True)
            bt_bk_to_kf.scale_y = 1.3
            bt_bk_to_kf.operator("rbdlab.bake_tokeyframes", text="Bake to Keyframes")

            if rbdlab.low_or_high_visibility_viewport == "Low":
                if have_rigidbodies_in_active_group(context):
                    col.enabled = True
                else:
                    col.enabled = False
            else:
                col.enabled = False

        elif ui.bake_sub_sections == 'PARTICCLES':

            # bake particles
            main_col.box().label(text="Bake Particles", icon='MOD_PARTICLE_INSTANCE')

            # bake_particles = collapsable(
            #     main_col,
            #     ui,
            #     "show_hide_rbd_bake_particles",
            #     "Bake Particles",
            #     'ONIONSKIN_ON',
            #     align=True,
            # )
            # if bake_particles:

            bake_particles = main_col
            flow = bake_particles.grid_flow(align=True)
            col = flow.column(align=True)

            psys = None

            for obj in rbdlab.filtered_target_collection.objects:

                if obj.type != 'MESH':
                    continue

                if len(obj.particle_systems) > 0:
                    psys = obj.particle_systems[0]
                    break

            if psys:
                custom_particles_point_cache_ui(self, ui, bake_particles, psys.point_cache, True, 'HAIR' if (psys.settings.type == 'HAIR') else 'PSYS')
            else:
                col.box().label(text="No Particles at the moment in the target collection", icon='INFO')
