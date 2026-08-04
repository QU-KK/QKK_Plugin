import bpy
from ..main.module_panel import ModulePanel
from bpy.types import Panel


def custom_point_cache_ui(self, cache, enabled, cachetype):
    layout = self.layout
    layout.use_property_split = True

    layout.context_pointer_set("point_cache", cache)

    is_saved = bpy.data.is_saved
    is_liboverride = cache.id_data.override_library is not None

    # NOTE: TODO temporarily used until the animate properties are properly skipped.
    layout.use_property_decorate = False  # No animation (remove this later on).

    # if not cachetype == 'RIGID_BODY':
    #     row = layout.row()
    #     row.template_list(
    #         "UI_UL_list", "point_caches", cache, "point_caches",
    #         cache.point_caches, "active_index", rows=1,
    #     )
    #     col = row.column(align=True)
    #     col.operator("ptcache.add", icon='ADD', text="")
    #     col.operator("ptcache.remove", icon='REMOVE', text="")

    #####################################
    # en nuestro caso cachetype = 'PSYS'
    #####################################

    # if cachetype in {'PSYS', 'HAIR', 'FLUID'}:
    #     col = layout.column()
    #
    #     if cachetype == 'FLUID':
    #         col.prop(cache, "use_library_path", text="Use Library Path")
    #
    #     col.prop(cache, "use_external")

    # if cache.use_external:
    #     col = layout.column()
    #     col.prop(cache, "index", text="Index")
    #     col.prop(cache, "filepath", text="Path")
    #
    #     cache_info = cache.info
    #     if cache_info:
    #         col = layout.column()
    #         col.alignment = 'RIGHT'
    #         col.label(text=cache_info)
    # else:
    # if cachetype in {'FLUID', 'DYNAMIC_PAINT'}:
    #     if not is_saved:
    #         col = layout.column(align=True)
    #         col.alignment = 'RIGHT'
    #         col.label(text="Cache is disabled until the file is saved")
    #         layout.enabled = False

    if not cache.use_external or cachetype == 'FLUID':
        col = layout.column(align=True)

        if cachetype not in {'PSYS', 'DYNAMIC_PAINT'}:
            col.enabled = enabled
            col.prop(cache, "frame_start", text="Simulation Start")
            col.prop(cache, "frame_end")

        if cachetype not in {'FLUID', 'CLOTH', 'DYNAMIC_PAINT', 'RIGID_BODY'}:
            col.prop(cache, "frame_step")

        cache_info = cache.info
        if cachetype != 'FLUID' and cache_info:  # avoid empty space.
            col = layout.column(align=True)
            col.alignment = 'RIGHT'
            col.label(text=cache_info)

        can_bake = True

        if cachetype not in {'FLUID', 'DYNAMIC_PAINT', 'RIGID_BODY'}:
            if not is_saved:
                col = layout.column(align=True)
                col.alignment = 'RIGHT'
                col.label(text="Options are disabled until the file is saved")

            flow = layout.grid_flow(row_major=True, columns=0, even_columns=True, even_rows=False, align=True)
            flow.enabled = enabled and is_saved

            # col = flow.column(align=True)
            # col.prop(cache, "use_disk_cache")

            # subcol = col.column()
            # subcol.active = cache.use_disk_cache
            # subcol.prop(cache, "use_library_path", text="Use Library Path")

            # col = flow.column()
            # col.active = cache.use_disk_cache
            # col.prop(cache, "compression", text="Compression")

            if cache.id_data.library and not cache.use_disk_cache:
                can_bake = False

                col = layout.column(align=True)
                col.alignment = 'RIGHT'

                col.separator()

                col.label(text="Linked object baking requires Disk Cache to be enabled")
        else:
            layout.separator()

        flow = layout.grid_flow(row_major=True, columns=0, even_columns=True, even_rows=False, align=False)
        col = flow.column()
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

        # sub = col.column()
        # sub.enabled = enabled
        # sub.operator("ptcache.bake_from_cache", text="Current Cache to Bake")

        col = flow.column()
        col.operator("ptcache.bake_all", text="Bake All Dynamics").bake = True
        col.operator("ptcache.free_bake_all", text="Delete All Bakes")
        col.operator("ptcache.bake_all", text="Update All to Frame").bake = False


class BAKE_PT_cache(Panel, ModulePanel):
    rbdlab_section = 'PARTICLES'
    bl_label = "Cache Bake"
    bl_idname = "BAKE_PT_cache"
    bl_parent_id = "PARTICLES_PT_ui"
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        layout = self.layout
        layout.use_property_split = True
        layout.use_property_decorate = False

        rbdlab = context.scene.rbdlab
        col = layout.column()

        obj = None
        if rbdlab.filtered_target_collection:
            coll_name = rbdlab.filtered_target_collection.name
            if coll_name:
                match = 0
                i = 0
                while not match and i < len(bpy.data.collections[coll_name].objects):
                    obj = bpy.data.collections[coll_name].objects[i]
                    if obj.type == 'MESH' and obj.visible_get() and len(obj.particle_systems) > 0:
                        match = obj
                    i += 1

        if obj and len(obj.particle_systems) > 0:
            # psys = context.particle_system
            psys = obj.particle_systems[0]
            custom_point_cache_ui(self, psys.point_cache, True, 'HAIR' if (psys.settings.type == 'HAIR') else 'PSYS')
            col.alert = False
        else:
            col.alert = True
            col.label(text="No particle systems detected", icon='ERROR')
