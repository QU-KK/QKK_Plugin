import bpy

import os

from .. utils.registration import get_prefs, get_path, get_pretty_version, set_new_decal_index, is_library_in_assetspath
from .. utils.ui import get_icon, draw_pil_warning, get_panel_fold
from .. utils.atlas import get_lower_and_upper_atlas_resolution, get_textypes_from_atlasmats
from .. utils.material import get_pbrnode_from_mat, get_override_sockets
from .. utils.assets import get_ambiguous_libs
from .. utils.library import get_atlas, poll_trimsheetlibs
from .. utils.system import get_safe_filename

from .. import bl_info
from .. import DECALmachineManager as DM

class PanelDECALmachine(bpy.types.Panel):
    bl_idname = "MACHIN3_PT_decal_machine"
    bl_label = ''
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "MACHIN3"
    bl_order = 0

    @classmethod
    def poll(cls, context):
        return get_prefs().show_sidebar_panel

    def draw_header(self, context):
        layout = self.layout
        dm = context.scene.DM

        row = layout.row(align=True)

        assets_dict = DM.get_assets_dict()
        legacy_mats = DM.get_legacy_materials(force=False)

        legacy = assets_dict['LEGACY']
        ambiguous = get_ambiguous_libs()

        decal = legacy_mats['DECAL']
        sheet = legacy_mats['TRIM']

        is_updateable = (legacy or ambiguous) or (decal or sheet)

        if get_prefs().update_available:
            layout.label(text="", icon_value=get_icon("refresh_green"))

        row.label(text=f'DECALmachine {get_pretty_version(bl_info["version"])}')

        row.prop(dm, "sidebar_show_creation", text="", icon="SHADERFX")
        row.prop(dm, "sidebar_show_export", text="", icon="EXPORT")

        if is_updateable and not dm.sidebar_show_update:
            r = row.row(align=True)
            r.alert = True
            r.prop(dm, "sidebar_show_update", text="", icon="FILE_REFRESH")
        else:
            row.prop(dm, "sidebar_show_update", text="", icon="FILE_REFRESH")

        row.prop(dm, 'sidebar_show_resources', text='', icon='BLENDER')
        row.prop(dm, "sidebar_show_help", text="", icon="QUESTION")

    def draw(self, context):
        layout = self.layout
        column = layout.column()

        dm = context.scene.DM
        wm = context.window_manager

        if get_prefs().update_available:
            column.separator()

            row = column.row()
            row.scale_y = 1.2
            row.label(text="An Update is Available", icon_value=get_icon("refresh_green"))
            row.operator("wm.url_open", text="What's new?").url = 'https://machin3.io/DECALmachine/docs/whatsnew'

            column.separator()

        can_sweep = bool([obj for obj in context.scene.objects if obj.DM.isbackup])

        if can_sweep:
            row = column.row(align=True)
            row.alignment = 'CENTER'
            row.label(text="Decal Backups have been linked to the Scene.")

            row = column.row()
            row.scale_y = 1.2
            row.alert = True
            row.operator('machin3.sweep_decal_backups', text='Sweep Decal Backups', icon='BRUSH_DATA')

        if panel := get_panel_fold(column, "defaults", "Defaults", icon="SETTINGS", default_closed=True):
            self.draw_defaults(panel, dm, wm)

        if panel := get_panel_fold(column, "tools_utils", "Tools + Utils", icon="TOOL_SETTINGS", default_closed=True):
            if sub_panel := get_panel_fold(panel, "tools", "Tools", icon="TOOL_SETTINGS", default_closed=True):
                self.draw_tools(sub_panel, dm)

            if sub_panel := get_panel_fold(panel, "utils", "Utils", icon="SETTINGS", default_closed=True):
                self.draw_utils(sub_panel)

        if dm.sidebar_show_creation:
            if panel := get_panel_fold(column, "create", "Create", icon="SHADERFX", default_closed=True):
                if sub_panel := get_panel_fold(panel, "decal_creation", "Create Decals", default_closed=True):
                    self.draw_decal_creation(context, sub_panel, dm)

                if sub_panel := get_panel_fold(panel, "trim_creation", "Create Trim Sheet", default_closed=True):
                    self.draw_trim_creation(context, sub_panel, dm)

                if sub_panel := get_panel_fold(panel, "atlas_creation", "Create Atlas", default_closed=True):
                    self.draw_atlas_creation(context, sub_panel, dm)

        if dm.sidebar_show_export:
            if panel := get_panel_fold(column, "export", "Export", icon="EXPORT", default_closed=True):
                if sub_panel := get_panel_fold(panel, "bake_decal_textures", "Bake Decal Textures", default_closed=True):
                    self.draw_decal_texture_baking(context, sub_panel, dm)

                if sub_panel := get_panel_fold(panel, "export_atlas", "Export Decal Atlas", default_closed=True):
                    self.draw_atlas_export(context, sub_panel, dm)

        if dm.sidebar_show_update:
            assets_dict = DM.get_assets_dict()
            legacy_mats = DM.get_legacy_materials(force=False)

            legacy = assets_dict['LEGACY']
            ambiguous = get_ambiguous_libs()

            decal = legacy_mats['DECAL']
            sheet = legacy_mats['TRIM']

            title = "Update Legacy Decals"

            if (legacy or ambiguous) or (decal or sheet):
                title += " ⚠"

            if panel := get_panel_fold(column, "update", title, icon="FILE_REFRESH", default_closed=True):
                if legacy or ambiguous:
                    if sub_panel := get_panel_fold(panel, "update_assetspath", "Update Assets path ⚠", default_closed=True):
                        draw_pil_warning(sub_panel, needed="for assets path update")

                        self.draw_assetspath_update(sub_panel, legacy, ambiguous)

                if sub_panel := get_panel_fold(panel, "update_library", "Update Specific Library", default_closed=True):
                    draw_pil_warning(sub_panel, needed="for library update")

                    self.draw_library_update(context, sub_panel, dm)

                if decal or sheet:
                    if sub_panel := get_panel_fold(panel, "update_blend_file", "Update current .blend File ⚠", default_closed=True):
                        self.draw_update_blend_file(sub_panel, decal, sheet)

        if dm.sidebar_show_resources:
            if panel := get_panel_fold(column, "resources", "Resources", icon="BLENDER", default_closed=False):
                self.draw_resources(panel)

        if dm.sidebar_show_help:
            col = column.column(align=True)
            col.alert = True

            if panel := get_panel_fold(col, 'get_support', "Get Support", icon='GREASEPENCIL', default_closed=True):
                self.draw_support(panel)

            if panel := get_panel_fold(column, 'documentation', "Documentation", icon='INFO', default_closed=False):
                self.draw_documentation(panel)

        if dm.debug or bpy.ops.machin3.decalmachine_debug.poll():
            if panel := get_panel_fold(column, "dev", "Dev", icon="MONKEY", default_closed=True):
                self.draw_debug(context, panel, dm)

    def draw_defaults(self, layout, dm, wm):

        b = layout.box()
        column = b.column()

        row = column.split(factor=0.33)
        row.label(text="Collections")
        r = row.row(align=True)
        r.prop(dm, "collection_decaltype", text="Type", toggle=True)
        r.prop(dm, "collection_decalparent", text="Parent", toggle=True)
        r.prop(dm, "collection_active", text="Active", toggle=True)

        b = layout.box()
        column = b.column(align=True)

        row = column.split(factor=0.33, align=True)
        row.label(text="Hide")
        r = row.row(align=True)
        r.prop(dm, "hide_materials", text="Materials", toggle=True)
        r.prop(dm, "hide_textures", text="Textures", toggle=True)
        r.prop(dm, "hide_nodetrees", text="Node Trees", toggle=True)

        if DM.get_addon("Batch Operations™"):
            row = column.split(factor=0.33, align=True)
            row.label()
            r = row.row(align=True)
            r.prop(dm, "hide_decaltype_collections", text="Type Col", toggle=True)
            r.prop(dm, "hide_decalparent_collections", text="Parent Col", toggle=True)

        row = column.split(factor=0.33, align=True)
        row.label(text="Texture Storage")
        r = row.row(align=True)
        r.prop(dm, "pack_images", expand=True)

        b = layout.box()
        column = b.column(align=True)

        row = column.row(align=True)
        row.label(text="Quality")
        row.prop(dm, "parallax", toggle=True)
        row.prop(dm, "glossyrays", toggle=True)

        row = column.row(align=True)
        row.label(text="Normal Transfer")
        row.prop(dm, "normaltransfer_viewport", text="Viewport", toggle=True)
        row.prop(dm, "normaltransfer_render", text="Render", toggle=True)

        b = layout.box()
        column = b.column(align=True)

        row = column.split(factor=0.33, align=True)
        row.label(text="Color Interpolation")
        r = row.row(align=True)
        r.prop(dm, "color_interpolation", expand=True)

        row = column.split(factor=0.33, align=True)
        row.label(text="AO & Invert")
        r = row.row(align=True)
        r.prop(dm, "ao_strength", slider=True)
        r.prop(dm, "invert_infodecals", text="Invert", toggle=True)

        row = column.split(factor=0.33, align=True)
        row.label(text="Edge Highlights")
        r = row.row(align=True)
        r.prop(dm, "edge_highlights", expand=True)

        row = column.split(factor=0.33, align=True)

        r = row.row()
        r.label(text="Coat")
        r.operator("machin3.coat_info", text='', icon='INFO', emboss=False)
        r = row.row(align=True)
        r.prop(dm, "coat", expand=True)

        b = layout.box()
        column = b.column()

        col = column.column(align=True)

        row = col.split(factor=0.33, align=True)
        row.label(text="Auto-Match")
        r = row.row(align=True)
        r.prop(dm, "auto_match", expand=True)

        if dm.auto_match == "MATERIAL":
            row = col.split(factor=0.33, align=True)
            row.label(text="Material")

            r = row.row(align=True)
            r.prop(wm, "matchmaterial", text="")

            mat = bpy.data.materials.get(wm.matchmaterial)
            icon = "refresh" if wm.matchmaterial in ["None", "Default"] or (mat and get_pbrnode_from_mat(mat)) else "refresh_red"

            r.operator("machin3.update_match_materials", text="", icon_value=get_icon(icon))

        split = column.split(factor=0.33, align=True)
        split.label(text="Override")
        split.operator("machin3.override_decal_materials", text="Override Materials")

        if dm.material_override:
            box = column.box()
            box.label(text="Material Override")

            c = box.column(align=True)

            row = c.row(align=True)
            row.prop(dm, 'material_override', text='')

            if dm.material_override.name == 'DECALmachine Override':
                split = c.split(factor=0.2, align=True)
                split.label(text="Presets")
                row = split.row(align=True)
                row.prop(dm, 'material_override_preset', expand=True)

            split = c.split(factor=0.2, align=True)
            split.label(text="Override")
            row = split.row(align=True)
            row.prop(dm, 'material_override_decal_subsets', text="Decal Subsets", toggle=True)
            row.prop(dm, 'material_override_decal_emission', text="Decal Emission", toggle=True)

            sockets = get_override_sockets(dm.material_override)

            c.separator()

            for name, socket in sockets:
                row = c.row(align=True)
                row.prop(socket, 'default_value', text='')
                row.label(text=" " + name)

        b = layout.box()
        column = b.column()

        row = column.split(factor=0.33)
        row.label(text="Snapping")
        r = row.row()
        r.prop(dm, "enable_surface_snapping", text='Surface Snapping', toggle=True)

        row = column.split(factor=0.33)
        row.label(text="Decal Align")
        r = row.row()
        r.prop(dm, "align_mode", expand=True)

    def draw_tools(self, layout, dm):
        col = layout.column(align=True)
        row = col.row(align=True)
        row.scale_y = 1.2
        row.operator("machin3.join_decal", text="Join")
        row.operator("machin3.split_decal", text="Split")

        row = col.row(align=True)
        row.scale_y = 1.2
        row.operator("machin3.remove_mesh_cuts", text="Remove Mesh Cuts")

        row = col.row(align=True)
        row.scale_y = 1.2
        row.operator("machin3.init_generated_coordinates", text="Init Generated Coords")
        row.operator("machin3.uv_transfer", text="Transfer UVs")

    def draw_utils(self, layout):
        col = layout.column(align=True)
        row = col.row(align=True)
        row.scale_y = 1.2
        row.operator("machin3.remove_decal_orphans", text="Remove Decal Orphans")
        row.operator("machin3.fix_decal_texture_paths", text="Fix Texture Paths")

        row = col.row(align=True)
        row.scale_y = 1.2
        row.operator("machin3.validate_decal", text="Validate Decal")
        row.operator("machin3.clear_decal_props", text="Clear Decal Props")

    def draw_decal_creation(self, context, layout, dm):
        box = layout.box()

        wm = context.window_manager
        sel = context.selected_objects
        active = context.active_object

        decals = sorted([obj for obj in sel if obj.DM.isdecal and not obj.DM.isprojected and not obj.DM.issliced], key=lambda x: x.name)

        row = box.row()
        row.scale_y = 1.2
        row.prop(dm, "create_decaltype", expand=True)

        if dm.create_decaltype in ['SIMPLESUBSET', 'PANEL']:
            b = box.box()
            b.label(text="Bake Settings")

            row = b.split(factor=0.33)
            row.label(text="Device")
            row.prop(context.scene.cycles, "device", text='')

            self.draw_simple_subset_panel_creation(context, active, dm, wm, sel, b)

        elif dm.create_decaltype == "INFO":
            b = box.box()
            b.label(text="Texture Settings")

            row = b.split(factor=0.33)
            row.label(text="Source")
            r = row.row()
            r.prop(dm, "create_infotype", expand=True)

            if dm.create_infotype == 'IMAGE':
                self.draw_info_from_image_creation(context, dm, b)

            elif dm.create_infotype == 'FONT':
                self.draw_info_from_text_creation(context, dm, b)

            elif dm.create_infotype == 'GEOMETRY':
                self.draw_info_from_geometry_creation(context, active, dm, b)

        draw_pil_warning(box, needed="for decals creation")
        self.draw_create_button(dm, sel, box)

        if bpy.types.WindowManager.instantdecallib.keywords['items']:
            box = box.box()
            action = "Remove " if get_prefs().decalremovemode else ""
            row = box.row()
            row.scale_y = 1.2
            row.label(text="%sInstant Decals" % (action))
            row.operator("machin3.open_instant_location", text="Open Folder").type = 'DECAL'

            self.draw_instant_decals(context, box)

        elif get_prefs().decalremovemode:
            box = box.box()
            box.label(text="Toggle Remove")

            row = box.row()
            row.prop(get_prefs(), "decalremovemode", text="Remove Decals")

        if decals:
            box = box.box()
            box.label(text="Add to Library")

            self.draw_add_to_library(context, dm, decals, box)

    def draw_simple_subset_panel_creation(self, context, active, dm, wm, sel, layout):
        if active and not active.DM.isdecal:
            column = layout.column(align=True)

            row = column.split(factor=0.33, align=True)
            row.label(text="Anti Aliasing")
            r = row.row(align=True)
            r.prop(dm, "create_bake_supersample", expand=True)

            r = row.row(align=True)
            r.active = context.scene.DM.create_bake_supersample != "0"
            r.prop(dm, "create_bake_supersamplealpha", text="Alpha", toggle=True)

            row = column.split(factor=0.32, align=True)
            row.label(text="Resolution")
            r = row.row(align=True)
            r.prop(dm, "create_bake_resolution", expand=True)

            column = layout.column(align=True)

            row = column.split(factor=0.33, align=True)
            row.label(text="AO")
            r = row.row(align=True)
            r.prop(dm, "create_bake_aosamples", expand=True)
            row.prop(dm, "create_bake_aocontrast")

            row = column.split(factor=0.33, align=True)
            row.label(text="Curvature")
            row.prop(dm, "create_bake_curvaturewidth")
            row.prop(dm, "create_bake_curvaturecontrast")

            row = column.split(factor=0.32, align=True)
            row.label(text="Height")
            row.prop(dm, "create_bake_heightdistance")

            column = layout.column(align=True)

            row = column.split(factor=0.33, align=True)
            row.label(text="Emission")
            r = row.row(align=True)
            r.prop(dm, "create_bake_emissive", text="Bake Emission", toggle=True)

            if dm.create_bake_emissive:
                r.prop(dm, "create_bake_emissive_bounce", text="Bounce", toggle=True)

                if dm.create_bake_emissive_bounce:
                    row = column.split(factor=0.33, align=True)
                    row.separator()
                    r = row.row(align=True)
                    r.prop(dm, "create_bake_emissionsamples", text="Bounce Light", expand=True)

            column = layout.column(align=True)

            row = column.split(factor=0.33, align=True)
            row.label(text="Alpha")
            col = row.column(align=True)
            col.prop(dm, "create_bake_limit_alpha_to_active", text="Limit to Active", toggle=True)
            col.prop(dm, "create_bake_limit_alpha_to_boundary", text="Limit to Boundary", toggle=True)
            col.prop(dm, "create_bake_flatten_alpha_normals", text="Flatten Normals", toggle=True)

            if dm.create_decaltype == "PANEL":
                row = layout.split(factor=0.33, align=True)
                row.label(text="Mask")
                row.prop(dm, "create_bake_maskmat2", toggle=True)

            if len(sel) > 1:
                row = layout.split(factor=0.33, align=True)
                row.label(text="Subset")

                col = row.column(align=True)
                col.prop(dm, "create_bake_store_subset", text="Store Subset Material on Decal Asset", toggle=True)

                if dm.create_bake_store_subset:
                    row = col.row(align=True)
                    row.prop(wm, "matchmaterial", text="")

                    mat = bpy.data.materials.get(wm.matchmaterial)
                    icon = "refresh" if wm.matchmaterial in ["None", "Default"] or (mat and get_pbrnode_from_mat(mat)) else "refresh_red"

                    row.operator("machin3.update_match_materials", text="", icon_value=get_icon(icon))

            column = layout.column(align=True)

            row = layout.split(factor=0.33, align=True)

            row.label(text="Advanced")
            col = row.column(align=True)
            col.prop(dm, "create_bake_inspect", toggle=True)
            col.prop(dm, "create_force_uuid", toggle=True)

            if dm.create_force_uuid and active:
                if active.DM.forced_uuid:
                    col.prop(active.DM, "forced_uuid", text='')

                else:
                    col.label(text='No UUID set yet')

        else:
            layout.label(text="Select Decal Source Geometry", icon='INFO')

    def draw_info_from_image_creation(self, context, dm, layout):
        wm = context.window_manager
        WM = bpy.types.WindowManager

        column = layout.column(align=True)
        row = column.row(align=True)

        row.scale_y = 1.2

        row.operator("machin3.load_images", text="Load Image(s)")
        row.operator("machin3.open_instant_location", text="Open Folder").type = 'INFOTEXTURES'
        row.operator("machin3.clear_images", text="Clear Images")

        if WM.infotextures.keywords['items']:
            layout.template_icon_view(wm, "infotextures", show_labels=True, scale=4, scale_popup=8)

        row = layout.split(factor=0.33, align=True)
        row.label(text="Crop, Padding")
        row.prop(dm, "create_infoimg_crop", toggle=True)
        r = row.row(align=True)
        r.active = dm.create_infoimg_crop
        r.prop(dm, "create_infoimg_padding", text="")

        if len(WM.infotextures.keywords['items']) > 1:
            row = layout.split(factor=0.33)
            row.label(text="Batch Creation")
            row.prop(dm, "create_infoimg_batch", text="All source images at once")

    def draw_info_from_text_creation(self, context, dm, layout):
        wm = context.window_manager
        WM = bpy.types.WindowManager

        column = layout.column(align=True)
        row = column.row(align=True)

        row.scale_y = 1.2

        row.operator("machin3.load_fonts", text="Load Font")
        row.operator("machin3.open_instant_location", text="Open Folder").type = 'INFOFONTS'
        row.operator("machin3.clear_fonts", text="Clear Fonts")

        if WM.infofonts.keywords['items']:
            layout.template_icon_view(wm, "infofonts", show_labels=True, scale=4, scale_popup=8)

            row = column.split(factor=0.33, align=True)
            row.label(text="Font")
            row.label(text=wm.infofonts)
            row.prop(dm, "create_infotext_size", text="Size")

            row = column.split(factor=0.33, align=True)
            row.scale_y = 1.5
            row.label(text="Text")
            row.prop(dm, "create_infotext", text="")

            row = column.split(factor=0.34, align=True)
            row.label(text="Colors")
            row.prop(dm, "create_infotext_color", text="")

            row.prop(dm, "create_infotext_bgcolor", text="")

            if "\\n" in dm.create_infotext:
                row = column.split(factor=0.33, align=True)
                row.label(text="Align Text")
                r = row.row(align=True)
                r.prop(dm, "create_infotext_align", expand=True)

            row = column.split(factor=0.33, align=True)
            row.label(text="Padding, Offset")
            r = row.row(align=True)

            rs = r.row(align=True)
            rs.prop(dm, "create_infotext_padding", text="")
            rs.operator("machin3.reset_default_property", text="", icon="LOOP_BACK").mode = "PADDING"
            rs = r.row(align=True)
            rs.prop(dm, "create_infotext_offset", text="")
            rs.operator("machin3.reset_default_property", text="", icon="LOOP_BACK").mode = "OFFSET"
    def draw_info_from_geometry_creation(self, context, active, dm, layout):
        if active and not active.DM.isdecal:
            column = layout.column(align=True)

            row = column.split(factor=0.33, align=True)
            row.label(text="Anti Aliasing, Padding")
            r = row.row(align=True)
            r.prop(dm, "create_bake_supersample", expand=True)

            rr = r.row(align=True)
            rr.prop(dm, "create_infotext_padding", text="")
            rr.operator("machin3.reset_default_property", text="", icon="LOOP_BACK").mode = "PADDING"
            row = column.split(factor=0.33, align=True)
            row.label(text="Resolution")
            r = row.row(align=True)
            r.prop(dm, "create_bake_resolution", expand=True)

            column = layout.column(align=True)

            row = column.split(factor=0.33, align=True)
            row.label(text="Emission")
            col = row.column(align=True)
            col.prop(dm, "create_bake_emissive", text="Bake Emission", toggle=True)

            column = layout.column(align=True)

            row = column.split(factor=0.33, align=True)
            row.label(text="Advanced")
            col = row.column(align=True)
            col.prop(dm, "create_bake_inspect", toggle=True)
            col.prop(dm, "create_force_uuid", toggle=True)

            if dm.create_force_uuid and active:
                if active.DM.forced_uuid:
                    col.prop(active.DM, "forced_uuid", text='', toggle=True)

                else:
                    col.label(text='No UUID set yet')

        else:
            layout.label(text="Select Decal Source Geometry", icon='INFO')

    def draw_create_button(self, dm, sel, layout):
        row = layout.row()
        row.scale_y = 1.5

        if dm.create_decaltype == "SIMPLESUBSET":
            decaltype = "SIMPLE" if len(sel) == 1 else "SUBSET" if len(sel) > 1 else ""

        else:
            decaltype = dm.create_decaltype

        if dm.create_decaltype == 'INFO' and dm.create_infoimg_batch:
            row.operator("machin3.batch_create_decals", text="Batch Create %s Decals" % (decaltype))

        else:
            row.operator("machin3.create_decal", text="Create %s Decal" % (decaltype))

    def draw_instant_decals(self, context, layout):
        wm = context.window_manager

        libraryscale = get_prefs().libraryscale
        decalsinlibraryscale = get_prefs().decalsinlibraryscale

        column = layout.column()
        column.template_icon_view(wm, "instantdecallib", show_labels=False, scale=libraryscale, scale_popup=decalsinlibraryscale)

        decalmode = get_prefs().decalmode

        if decalmode == "INSERT":
            text, icon = "", get_icon("plus")
            idname = "machin3.insert_decal"

        elif decalmode == "REMOVE":
            text, icon = ("", get_icon("cancel"))
            idname = "machin3.remove_decal"

        op = column.operator(idname, text=text, icon_value=icon)
        op.library = "INSTANT"
        op.decal = getattr(wm, "instantdecallib")
        op.instant = True

        if decalmode == "INSERT":
            op.force_cursor_align = True

        row = column.row()
        row.prop(get_prefs(), "decalremovemode", text="Remove Decals")

        if get_prefs().decalremovemode and len(bpy.types.WindowManager.instantdecallib.keywords['items']) > 1:
            row = column.row()
            row.scale_y = 1.5
            row.operator("machin3.remove_all_instant_decals", text="Remove All Instant Decals at once", icon_value=get_icon("cancel"))

    def draw_add_to_library(self, context, dm, decals, layout):
        column = layout.column()

        if not context.scene.userdecallibs:
            text = "Create a new empty Decal Library"

            if [lib for lib in get_prefs().decallibsCOL if not lib.istrimsheet and lib.islocked]:
                text += " or unlock an existing one"

            text += "!"

            column.label(text=text, icon_value=get_icon('error'))

        else:
            decals_with_names = [obj for obj in decals if obj.DM.decaltype == 'INFO' and obj.active_material.DM.decalnamefromfile]

            wm = context.window_manager
            skip_index = dm.addlibrary_skip_index

            if not wm.newdecalidx:
                set_new_decal_index(self, context)

            basename = dm.addlibrary_decalname.strip().replace(" ", "_") if dm.addlibrary_decalname else ''
            startidx = wm.newdecalidx

            assetspath = get_prefs().assetspath
            library = context.scene.userdecallibs
            librarypath = os.path.join(assetspath, 'Decals', library)

            existingnames = [f for f in os.listdir(librarypath) if os.path.isdir(os.path.join(librarypath, f))]

            names = [decal.active_material.DM.decalnamefromfile if (decal.active_material.DM.decalnamefromfile and dm.addlibrary_use_filename) else basename for decal in decals]

            row = column.split(factor=0.33)
            row.label(text="User Decal Library")

            r = row.row(align=True)
            r.prop(context.scene, "userdecallibs", text="")
            r.operator("machin3.open_user_decal_lib", text="", icon="FILE_FOLDER")

            row = column.split(factor=0.33)
            row.label(text="Decal Name")
            col = row.column()

            row = col.row()

            if decals_with_names:
                row.prop(dm, "addlibrary_use_filename", text=f"Use File Name{'s' if len(decals_with_names) > 1 else ''}")

            if (decals_with_names and dm.addlibrary_use_filename) or dm.addlibrary_decalname:
                row.prop(dm, "addlibrary_skip_index", text=f"Skip {'Indices' if len(decals) > 1 else 'Index'}")

            if decals != decals_with_names or not dm.addlibrary_use_filename:
                col.prop(dm, "addlibrary_decalname", text="")

            decalnames = []

            for i, name in enumerate(names):
                if name:
                    decalname = f"{str(int(startidx) + i).zfill(3) + '_' if not skip_index else ''}{name}"

                else:
                    decalname = str(int(startidx) + i).zfill(3)

                decalnames.append(decalname)

            duplicate_names = len(decalnames) > len(set(decalnames))
            unavailable_names = sum([decalname in existingnames for decalname in decalnames])

            if duplicate_names or unavailable_names:
                col.separator()

                if unavailable_names:
                    col.label(text=f"Existing Folder Name{'s' if unavailable_names > 1 else ''}!", icon_value=get_icon('error'))

                if duplicate_names:
                    col.label(text="Duplicate Decal Names!", icon_value=get_icon('error'))

                col.separator()

            pathstr = []

            for decalname in decalnames:
                pathstr.append(f"{library} / {get_safe_filename(decalname)}")

            row = column.split(factor=0.33)
            row.label(text="Path Preview")
            col = row.column()

            for ps in pathstr:
                col.label(text=ps, icon="FILE_FOLDER")

            column = layout.column()

            subset_decals = [obj for obj in decals if obj.DM.decaltype == 'SUBSET']

            if subset_decals:
                column.separator()

                row = column.split(factor=0.33)
                row.label(text="Subset")

                col = row.column()
                col.prop(dm, "create_bake_store_subset", text=f"Store Subset Material{'s' if len(subset_decals) > 1 else ''} on Decal Asset{'s' if len(subset_decals) > 1 else ''}")
                column.separator()

            forced = [obj.DM.is_forced_uuid for obj in decals]

            if any(forced):
                row = column.split(factor=0.33)
                row.label(text="Advanced")
                row.label(text=f"Forced UUID{'s are' if sum(forced) > 1 else ' is'} being used", icon='INFO')

            row = column.row()
            row.scale_y = 1.5
            row.operator("machin3.add_decal_to_library", text="Add %s to Library" % ("Decal" if len(decals) <= 1 else "Decals"))

    def draw_trim_creation(self, context, layout, dm):
        box = layout.box()

        wm = context.window_manager
        sel = context.selected_objects
        active = context.active_object

        row = box.row()
        row.scale_y = 1.2
        row.prop(dm, "create_trim_type", expand=True)

        self.draw_trimsheet_creation(context, dm, active, box)
        self.draw_trimsheet_properties(context, dm, active, box)

        draw_pil_warning(box, needed="for trim sheet creation")
        self.draw_trimsheet_create_buttons(dm, active, sel, box)

        if wm.instanttrimsheetcount > 0:
            b = box.box()
            self.draw_instant_trimsheets(context, wm, b)

    def draw_instant_trimsheets(self, context, wm, layout):
        row = layout.split(factor=0.7)
        row.label(text="Instant Trim Sheets")
        row.label(text=str(wm.instanttrimsheetcount))

        row = layout.row(align=True)
        row.scale_y = 1.2
        row.operator("machin3.open_instant_location", text="Open Folder").type = 'TRIMSHEET'
        row.operator("machin3.clear_instant", text="Clear Out Folder").type = 'TRIMSHEET'

    def draw_trimsheet_create_buttons(self, dm, active, sel, layout):
        if active and active.DM.istrimsheet:
            row = layout.split(factor=0.35, align=True)
            row.label(text="Keep Sheet UUID")
            row.prop(dm, "create_trim_import_keep_sheet_uuid", text='True' if dm.create_trim_import_keep_sheet_uuid else 'False', toggle=True)

            row = layout.split(factor=0.35, align=True)
            row.scale_y = 1.5
            row.operator("machin3.trimsheet", text="Trim it")
            row.operator("machin3.create_trimsheet_library", text="Create Trim Sheet Library")

    def draw_trimsheet_properties(self, context, dm, active, layout):
        if active and active.DM.istrimsheet:
            box = layout.box()
            dm = active.DM

            self.draw_trimsheet_available_textures(self, box)

            row = box.row()
            row.label(text="Trim Sheet Properties")
            row.operator("machin3.remove_instant_trim_sheet", text="", icon_value=get_icon('cancel'), emboss=True)

            row = box.split(factor=0.3)
            row.label(text="Name")
            row.prop(dm, "trimsheetname", text='')

            width, height = dm.trimsheetresolution
            trimmaps = dm.trimmapsCOL

            row = box.split(factor=0.3)
            row.label(text="Resolution")
            row.label(text=f"{width} x {height}")

            if any([trim_map.texture and tuple(trim_map.resolution) != (width, height) for trim_map in trimmaps]):
                row.label(text="Mismatch", icon='ERROR')

            box.prop(dm, "show_trim_maps", text="Texture Maps (%d)" % len([True for trim_map in trimmaps if trim_map.texture]), icon='TRIA_DOWN' if dm.show_trim_maps else 'TRIA_RIGHT', emboss=False)

            if dm.show_trim_maps:
                column = box.column()
                column.active = len(bpy.types.WindowManager.trimtextures.keywords['items']) > 1
                column.template_list("MACHIN3_UL_trim_maps", "", dm, "trimmapsCOL", dm, "trimmapsIDX", rows=len(dm.trimmapsCOL))

            if active and (any([trim_map.texture for trim_map in trimmaps]) or dm.trimsCOL):

                box.prop(dm, "show_trims", text="Trim Setup (%d)" % len(dm.trimsCOL), icon='TRIA_DOWN' if dm.show_trims else 'TRIA_RIGHT', emboss=False)

                if dm.show_trims:
                    column = box.column(align=True)

                    row = column.split(factor=0.3, align=True)
                    row.label(text="Snapping")

                    r = row.row(align=True)
                    r.prop(dm, "trimsnapping", text=str(dm.trimsnapping), toggle=True)

                    if dm.trimsnapping:
                        r.prop(dm, "trimsnappingdraw", text='', icon='MESH_GRID')

                        if dm.trimsnappingobject:
                            r.prop(dm, "trimsnappingobjectedgesdraw", text='', icon='MOD_MULTIRES')

                        if not dm.trimsnappingobject:
                            row = column.split(factor=0.3, align=True)
                            row.label(text="Pixel")
                            row.prop(dm, "trimsnappingpixel", text=str(dm.trimsnappingpixel), toggle=True)

                        if not dm.trimsnappingpixel:
                            row = column.split(factor=0.3, align=True)
                            row.label(text="Object")
                            row.prop(dm, "trimsnappingobject", text='')

                        if not (dm.trimsnappingpixel or dm.trimsnappingobject):
                            row = column.split(factor=0.3, align=True)
                            row.label(text="Resolution")
                            row.prop(dm, "trimsnappingresolution", text='')

                    column = box.column()
                    row = column.row()

                    offset = 12

                    col = row.column(align=True)
                    col.template_list("MACHIN3_UL_trims", "", dm, "trimsCOL", dm, "trimsIDX", rows=max(len(dm.trimsCOL), offset))

                    col = row.column(align=True)

                    c = col.column()
                    scale = (max(len(dm.trimsCOL), offset) - offset) * 3.3 if dm.trimopspinned else 0

                    c.scale_y = scale
                    c.separator()

                    c = col.column(align=True)
                    c.prop(dm, "trimopspinned", text="", icon="PINNED" if dm.trimopspinned else "UNPINNED")
                    c.separator()
                    c.operator("machin3.add_trim", text="", icon="ADD")
                    c.operator("machin3.duplicate_trim", text="", icon="DUPLICATE")
                    c.operator("machin3.draw_trim", text="", icon="GREASEPENCIL")
                    c.separator()
                    c.operator("machin3.align_trim", text="", icon="TRIA_LEFT").side = 'LEFT'
                    c.operator("machin3.align_trim", text="", icon="TRIA_RIGHT").side = 'RIGHT'
                    c.operator("machin3.align_trim", text="", icon="TRIA_UP").side = 'TOP'
                    c.operator("machin3.align_trim", text="", icon="TRIA_DOWN").side = 'BOTTOM'
                    c.separator()
                    c.operator("machin3.hide_all_trims", text="", icon="HIDE_OFF").hide_select = False
                    c.operator("machin3.hide_all_trims", text="", icon="RESTRICT_SELECT_OFF").hide_select = True
                    c.separator()
                    icon = "cancel" if dm.trimsCOL else "cancel_grey"
                    c.operator("machin3.remove_trim", text="", icon_value=get_icon(icon))

    def draw_trimsheet_creation(self, context, dm, active, layout):
        if dm.create_trim_type == 'NEW':
            row = layout.row(align=True)
            row.scale_y = 1.2
            row.operator("machin3.init_trimsheet", text="Initialze")
            row.operator("machin3.duplicate_trimsheet", text="Duplicate")

        elif dm.create_trim_type == 'IMPORT':
            row = layout.split(factor=0.3, align=True)
            row.label(text='Location')
            row.prop(dm, "create_trim_import_path", text='')

            row = layout.split(factor=0.3, align=True)
            row.label(text='Keep Trim UUIDs')
            row.prop(dm, "create_trim_import_keep_trim_uuids", text='True' if dm.create_trim_import_keep_trim_uuids else 'False', toggle=True)

            row = layout.row(align=True)
            row.scale_y = 1.5
            row.operator("machin3.import_trimsheet", text="Import Trim Sheet")

    def draw_trimsheet_available_textures(self, context, layout):
        box = layout.box()

        row = box.split(factor=0.7)
        row.label(text="Available PNG Textures:")
        row.label(text=f"{len(bpy.types.WindowManager.trimtextures.keywords['items']) - 1}")

        row = box.row(align=True)
        row.scale_y = 1.2

        row.operator("machin3.load_trimsheet_textures", text="Load Texture(s)")
        row.operator("machin3.open_instant_location", text="Open Folder").type = 'TRIMTEXTURES'
        row.operator("machin3.clear_trimsheet_textures", text="Clear Textures")

    def draw_atlas_creation(self, context, layout, dm):
        box = layout.box()

        wm = context.window_manager
        sel = context.selected_objects
        active = context.active_object

        row = box.row()
        row.scale_y = 1.2
        row.prop(dm, "create_atlas_creation_type", expand=True)

        atlas = active if active and active.DM.isatlas else None
        only_atlas_is_selected = [atlas] == sel
        decals = [obj for obj in sel if obj.DM.isdecal]

        if dm.create_atlas_creation_type == 'IMPORT':
            self.draw_import_atlas(dm, box)

        if only_atlas_is_selected:
            self.draw_atlas_properties(context, dm, atlas, box)

            self.draw_atlas_storage(atlas, box)

        elif atlas and decals:
            self.draw_add_decals_to_atlas(atlas, decals, box)

        elif dm.create_atlas_creation_type == 'NEW':
            self.draw_packing_settings(context, dm, atlas, only_atlas_is_selected, box)

        if wm.instantatlascount > 0:
            b = box.box()
            self.draw_instant_atlases(context, wm, b)

    def draw_import_atlas(self, dm, layout):
        box = layout.box()

        row = box.row(align=True)
        row.prop(dm, "create_atlas_import_path", text="Location")

        row = box.row(align=True)
        row.scale_y = 1.5
        row.operator("machin3.import_atlas", text="Import Atlas")

    def draw_instant_atlases(self, context, wm, layout):
        row = layout.split(factor=0.7)
        row.label(text="Instant Atlases")
        row.label(text=str(wm.instantatlascount))

        row = layout.row(align=True)
        row.scale_y = 1.2
        row.operator("machin3.open_instant_location", text="Open Folder").type = 'ATLAS'
        row.operator("machin3.clear_instant", text="Clear Out Folder").type = 'ATLAS'

    def draw_packing_settings(self, context, dm, atlas, only_atlas_is_selected, layout):
        box = layout.box()
        box.label(text=f"{'Tweak' if only_atlas_is_selected and atlas.DM.atlasrefinement == 'TWEAK' else 'Pack'} Settings")

        column = box.column(align=True)

        if only_atlas_is_selected:
            row = column.split(factor=0.33, align=True)
            row.label(text="Refinement")
            r = row.row(align=True)
            r.scale_y = 1.2
            r.prop(atlas.DM, "atlasrefinement", expand=True)

            column = box.column(align=True)

        if not only_atlas_is_selected:
            row = column.split(factor=0.33, align=True)
            row.label(text="Type")
            r = row.row(align=True)
            r.scale_y = 1.2
            r.prop(dm, "create_atlas_type", expand=True)

            column = box.column(align=True)

        if not only_atlas_is_selected or atlas.DM.atlasrefinement == 'REPACK':
            row = column.split(factor=0.33, align=True)
            row.label(text="File Format")
            r = row.row(align=True)
            r.prop(dm, "create_atlas_file_format", expand=True)

            row = column.split(factor=0.33, align=True)
            row.label(text="Size")
            r = row.row(align=True)
            r.prop(dm, "create_atlas_size_mode", expand=True)

            if dm.create_atlas_size_mode == 'SPECIFIC':
                row = column.split(factor=0.33, align=True)
                row.label(text="Resolution")
                r = row.row(align=True)
                r.prop(dm, "create_atlas_resolution", text="")

            row = column.split(factor=0.33, align=True)
            row.label(text="Padding")
            row.prop(dm, "create_atlas_padding", text="")

        if only_atlas_is_selected and atlas.DM.atlasrefinement == 'TWEAK':
            row = column.split(factor=0.33, align=True)
            row.label(text="File Format")
            r = row.row(align=True)
            r.prop(dm, "create_atlas_file_format", expand=True)

            row = column.split(factor=0.33, align=True)
            row.label(text="Resolution")
            r = row.row(align=True)

            if dm.create_atlas_resolution < atlas.DM.atlasresolution[0]:
                r.label(text="", icon="ERROR")

            r.prop(dm, "create_atlas_resolution", text="")

        if not only_atlas_is_selected:
            column = box.column(align=True)

            row = column.split(factor=0.33, align=True)
            row.label(text="Pre-Pack Panels")
            r = row.row(align=True)
            r.prop(dm, "create_atlas_prepack", expand=True)

        if (only_atlas_is_selected and atlas.DM.get('solution') and atlas.DM.get('solution')['type'] in ['NORMAL', 'COMBINED']) or (not only_atlas_is_selected and dm.create_atlas_type in ['NORMAL', 'COMBINED']):
            column = box.column(align=True)

            row = column.split(factor=0.34, align=True)
            row.label(text="Height")
            row.prop(dm, "create_atlas_compensate_height", text="Compensate", toggle=True)
            row.prop(dm, "create_atlas_normalize_height", text="Normalize", toggle=True)

        if not only_atlas_is_selected:
            draw_pil_warning(column, "for atlas creation")

            column = box.column()

            row = column.row()
            row.scale_y = 1.5
            row.operator("machin3.create_atlas", text=f"Create new Decal Atlas from {('Selection' if context.selected_objects else 'Scene')}").mode='INITIATE'

    def draw_atlas_properties(self, context, dm, atlas, layout):
        box = layout.box()

        row = box.row()
        row.prop(atlas.DM, "show_atlas_props", text="Atlas Properties", icon='TRIA_DOWN' if atlas.DM.show_atlas_props else 'TRIA_RIGHT', emboss=False)
        row.operator("machin3.remove_instant_atlas", text="", icon_value=get_icon('cancel'), emboss=True)

        row = box.split(factor=0.3)
        row.label(text="Name")
        row.prop(atlas.DM, "atlasname", text='')

        solution = atlas.DM.get('solution')

        if solution:
            resolution = atlas.DM.atlasresolution
            padding = solution.get('padding', None)
            efficiency = solution.get('efficiency', None)

            if not any(prop is None for prop in [resolution, padding, efficiency]):
                row = box.split(factor=0.3)

                if atlas.DM.show_atlas_props:
                    row.label(text="Stats")
                    row.label(text=f"{resolution[0]} x {resolution[1]}, {padding} padding, {efficiency:.1f}% efficient")
                else:
                    row.label(text="Resolution")
                    row.label(text=f"{resolution[0]} x {resolution[1]}")

                if solution['type'] in ['NORMAL', 'COMBINED']:
                    row = box.split(factor=0.3)

                    row.label(text="Parallax")
                    row.prop(atlas.DM, "atlasdummyparallax", text='', slider=True)

        if atlas.DM.show_atlas_props:
            column = box.column()
            column.label(text=f"Packed Decals (sorted by {('Name' if atlas.DM.atlastrimsort == 'NAME' else 'Packing Order')})")

            offset = 7 if atlas.DM.atlasrefinement == 'REPACK' else 11

            row = column.row()
            col = row.column()
            col.template_list("MACHIN3_UL_atlas_trims", "", atlas.DM, "trimsCOL", atlas.DM, "trimsIDX", rows=max(len(atlas.DM.trimsCOL), offset))

            col = row.column(align=True)

            c = col.column()
            scale = (max(len(atlas.DM.trimsCOL), offset) - offset) * 3.3 if atlas.DM.trimopspinned else 0

            c.scale_y = scale
            c.separator()

            c = col.column(align=True)
            c.prop(atlas.DM, "trimopspinned", text="", icon="PINNED" if atlas.DM.trimopspinned else "UNPINNED")
            c.separator()
            c.separator()
            c.operator("machin3.toggle_atlas_trim_sort", text="", icon_value=get_icon('refresh'))
            c.separator()
            c.prop(dm, "create_atlas_non_uniform_scale", text="", icon="CON_SAMEVOL")
            c.operator("machin3.scale_atlas_trim", text="", icon="FULLSCREEN_EXIT").mode = 'DOWN'
            c.operator("machin3.scale_atlas_trim", text="", icon="FULLSCREEN_ENTER").mode = 'UP'

            if atlas.DM.atlasrefinement == 'TWEAK':
                c.separator()
                c.operator("machin3.align_atlas_trim", text="", icon="TRIA_LEFT").side = 'LEFT'
                c.operator("machin3.align_atlas_trim", text="", icon="TRIA_RIGHT").side = 'RIGHT'
                c.operator("machin3.align_atlas_trim", text="", icon="TRIA_UP").side = 'TOP'
                c.operator("machin3.align_atlas_trim", text="", icon="TRIA_DOWN").side = 'BOTTOM'

            c.separator()
            c.operator("machin3.reset_atlas_trim", text="", icon="LOOP_BACK").idx = "ALL"
            c.operator("machin3.remove_decal_from_atlas", text="", icon_value=get_icon('cancel'))

            self.draw_packing_settings(context, dm, atlas, True, box)

            draw_pil_warning(box, "for atlas creation")

            row = box.row()
            row.scale_y = 1.5

            mode = atlas.DM.atlasrefinement
            row.operator("machin3.create_atlas", text=f"{('Re-Pack' if mode == 'REPACK' else 'Tweak')} selected Atlas").mode = mode

    def draw_add_decals_to_atlas(self, atlas, decals, layout):
        sourceuuids = [uuid for uuid in atlas.DM.get('sources').to_dict()] if atlas.DM.get('sources') else []
        new_decals = [obj for obj in decals if obj.DM.uuid not in sourceuuids] if sourceuuids else []

        box = layout.box()

        box.label(text="Add to Atlas")

        column = box.column()

        row = column.split(factor=0.3)
        row.label(text="Name")
        row.label(text=atlas.DM.atlasname)

        row = column.split(factor=0.3)
        row.label(text="Resolution")
        row.label(text=f"{atlas.DM.atlasresolution[0]} x {atlas.DM.atlasresolution[1]}")

        row = box.row()
        row.scale_y = 1.5
        row.operator("machin3.add_decals_to_atlas", text=f"Add {('Decal' if len(new_decals) < 2 else 'Decals')}")

    def draw_atlas_storage(self, atlas, layout):
        box = layout.box()
        box.label(text="Store Atlas")

        lower, _ = get_lower_and_upper_atlas_resolution(atlas.DM.atlasresolution[0])

        if lower != atlas.DM.atlasresolution[0]:
            row = box.split(factor=0.3, align=True)
            row.label(text="Resize")
            row.prop(atlas.DM, "atlasresizedown", text="True" if atlas.DM.atlasresizedown else "False", toggle=True)
            r = row.row()
            r.active = atlas.DM.atlasresizedown
            r.label(text=f"{lower} x {lower}")

        draw_pil_warning(box, "for atlas storage")

        row = box.row()
        row.scale_y = 1.5

        row.operator("machin3.store_atlas", text="Store selected Atlas")

    def draw_decal_texture_baking(self, context, layout, dm):
        box = layout.box()

        targets = [obj for obj in context.selected_objects if not obj.DM.isdecal]
        restore = bool([obj for obj in targets if obj.DM.prebakepreviewmats]) or dm.export_bake_preview

        self.draw_bake_settings(context, dm, box, len(targets))

        draw_pil_warning(layout, "for decal export")

        self.draw_bake_button(box, restore=restore)

    def draw_bake_settings(self, context, dm, layout, targetcount):
        box = layout.box()
        box.label(text="Bake Settings")

        row = box.split(factor=0.33)
        row.label(text="Device")
        row.prop(context.scene.cycles, "device", text='')

        row = box.split(factor=0.33)
        row.label(text="Anti Aliasing")
        col = row.column()
        r = col.row()
        r.prop(dm, "export_bake_supersample", expand=True)

        if int(dm.export_bake_supersample):
            row = box.split(factor=0.33)
            row.label(text="Attention", icon_value=get_icon('error'))
            col = row.column()

            if int(dm.export_bake_supersample) == 2:
                col.label(text="This significantly increases the render time!")
            elif int(dm.export_bake_supersample) == 4:
                col.label(text="This dramatically increases the render time!")

        row = box.split(factor=0.33)
        row.label(text="Resolution")
        split = row.split(factor=0.42, align=True)
        split.prop(dm, "export_bake_x", text='')
        s = split.split(factor=0.2, align=True)
        icon = 'LINKED' if dm.export_bake_linked_res else 'UNLINKED'
        s.prop(dm, "export_bake_linked_res", text='', icon=icon)
        r = s.row(align=True)
        r.active = not dm.export_bake_linked_res
        r.prop(dm, "export_bake_y", text='')

        row = box.split(factor=0.33)
        row.label(text="Properties")
        col = row.column(align=True)
        row = col.row(align=True)
        row.prop(dm, 'export_bake_samples')
        row.prop(dm, 'export_bake_margin')
        col.prop(dm, 'export_bake_extrusion_distance', slider=True)
        col.prop(dm, 'export_bake_ray_distance', slider=True)
        col.prop(dm, 'export_bake_triangulate', toggle=True)

        row = box.split(factor=0.33)
        row.label(text="Maps")
        col = row.column(align=True)
        col.prop(dm, 'export_bake_color', toggle=True)
        col.prop(dm, 'export_bake_normal', toggle=True)
        col.prop(dm, 'export_bake_emission', toggle=True)
        col.prop(dm, 'export_bake_aocurvheight', toggle=True)
        col.prop(dm, 'export_bake_masks', toggle=True)

        row = box.split(factor=0.33)
        row.label(text="Post-Baking")
        col = row.column()

        if targetcount > 1:
            col.prop(dm, 'export_bake_combine_bakes')

        col.prop(dm, 'export_bake_preview')
        col.prop(dm, 'export_bake_open_folder')
        col.prop(dm, 'export_bake_substance_naming')

        row = box.split(factor=0.33)
        row.label(text="Folder")
        row.prop(dm, 'use_custom_export_path', toggle=True)

        if dm.use_custom_export_path:
            if dm.custom_export_path:
                row = box.split(factor=0.2, align=True)
                row.operator("machin3.open_folder", text="Open", icon='FILE_FOLDER').path = dm.custom_export_path
            else:
                row = box.row()

            row.prop(dm, 'custom_export_path', text='')

        else:
            assetspath = get_prefs().assetspath
            exportpath = os.path.join(assetspath, "Export")
            bakespath = os.path.join(exportpath, "bakes")

            if os.path.join(bakespath):
                row = box.row()
                row.operator("machin3.open_folder", text="Open Export Folder", icon='FILE_FOLDER').path = bakespath

    def draw_bake_button(self, layout, restore=False):
        col = layout.column(align=True)

        row = col.row(align=True)
        row.scale_y = 1.5
        row.operator("machin3.bake_decals", text="Bake Decals")

        if restore:
            row = col.row(align=True)
            row.scale_y = 1.2
            row.operator("machin3.restore_pre_bakepreview_materials", text="Restore Materials + Decals")

    def draw_atlas_export(self, context, layout, dm):
        box = layout.box()
        box.label(text="Atlas Settings")

        self.draw_atlas_settings(dm, box)

        self.draw_decal_atlases(box)

        self.draw_use_atlas_button(box)

        if [obj for obj in context.visible_objects if obj.DM.preatlasmats]:
            self.draw_join_button(context, dm, box)

            self.draw_export_atlas(context, dm, box)

    def draw_export_atlas(self, context, dm, layout):
        def draw_machin3tools_unity_export(context, layout):
            m3 = context.scene.M3

            row = layout.split(factor=0.25)
            row.label(text="Triangulate")
            row.prop(m3, 'unity_triangulate', text='True' if m3.unity_triangulate else 'False', toggle=True)

            layout.separator()

            row = layout.row(align=True)
            row.scale_y = 1.5
            row.operator("machin3.prepare_unity_export", text=f"Prepare {('Selected' if context.selected_objects else 'Visible')}" if m3.unity_export else f"Prepare {('Selected' if context.selected_objects else 'Visible')}").prepare_only = True

            row = layout.row(align=True)
            row.scale_y = 1.2
            row.operator("machin3.restore_unity_export", text="Restore Transformations")

        box = layout.box()
        box.label(text="Export Atlas Textures & Models")

        column = box.column()

        row = column.split(factor=0.25)
        row.label(text="Type")

        r = row.row(align=True)
        row.scale_y = 1.2
        r.prop(dm, "export_atlas_textures", text="Textures", toggle=True)
        r.prop(dm, "export_atlas_models", text="Models", toggle=True)

        column.separator()

        row = column.split(factor=0.25)
        row.label(text="Export Location")
        row.prop(dm, "export_atlas_path", text="")

        if dm.export_atlas_textures:
            row = column.split(factor=0.25)
            row.label(text="Textures Folder")
            r = row.row()
            r.prop(dm, "export_atlas_use_textures_folder", text="")
            rr = r.row()
            rr.active = dm.export_atlas_use_textures_folder
            rr.prop(dm, "export_atlas_textures_folder", text="")

        if dm.export_atlas_models:
            row = column.split(factor=0.25)
            row.label(text="Models Folder")
            r = row.row()
            r.prop(dm, "export_atlas_use_models_folder", text="")
            rr = r.row()
            rr.active = dm.export_atlas_use_models_folder
            rr.prop(dm, "export_atlas_models_folder", text="")

        decals = [obj for obj in (context.selected_objects if context.selected_objects else context.visible_objects) if obj.DM.isdecal and obj.DM.preatlasmats]
        atlasmats = {mat for decal in decals for mat in decal.data.materials if mat and mat.DM.isatlasmat}

        if dm.export_atlas_textures:
            b = column.box()
            b.label(text='Textures')

            if atlasmats:
                textypes = get_textypes_from_atlasmats(atlasmats)

                row = b.split(factor=0.25)
                row.label(text="Individual")

                r = row.row(align=True)

                col = r.column(align=True)
                rr = col.row(align=True)
                rr.active = 'ALPHA' in textypes
                rr.prop(dm, "export_atlas_texture_alpha", text="Alpha", toggle=True)
                rr = col.row(align=True)
                rr.active = 'COLOR' in textypes
                rr.prop(dm, "export_atlas_texture_color", text="Color", toggle=True)
                rr = col.row(align=True)
                rr.active = 'EMISSION' in textypes
                rr.prop(dm, "export_atlas_texture_emission", text="Emission", toggle=True)
                rr = col.row(align=True)
                rr.active = 'NORMAL' in textypes
                rr.prop(dm, "export_atlas_texture_normal", text="Normal", toggle=True)
                rr = col.row(align=True)
                rr.active = 'METALLIC' in textypes
                rr.prop(dm, "export_atlas_texture_metallic", text="Metallic", toggle=True)
                rr = col.row(align=True)
                rr.active = 'ROUGHNESS' in textypes
                rr.prop(dm, "export_atlas_texture_smoothness", text="Smoothness", toggle=True)
                rr = col.row(align=True)
                rr.active = all(textype in textypes for textype in ['SUBSET', 'AO'])
                rr.prop(dm, "export_atlas_texture_subset_occlusion", text="Subset Occlusion", toggle=True)

                col = r.column(align=True)
                rr = col.row(align=True)
                rr.active = 'AO' in textypes
                rr.prop(dm, "export_atlas_texture_ao", text="Ambient Occlusion", toggle=True)
                rr = col.row(align=True)
                rr.active = 'CURVATURE' in textypes
                rr.prop(dm, "export_atlas_texture_curvature", text="Curvature", toggle=True)
                rr = col.row(align=True)
                rr.active = 'HEIGHT' in textypes
                rr.prop(dm, "export_atlas_texture_height", text="Height", toggle=True)
                rr = col.row(align=True)
                rr.active = 'MATERIAL2' in textypes
                rr.prop(dm, "export_atlas_texture_material2", text="Material 2", toggle=True)
                rr = col.row(align=True)
                rr.active = 'ROUGHNESS' in textypes
                rr.prop(dm, "export_atlas_texture_roughness", text="Roughness", toggle=True)
                rr = col.row(align=True)
                rr.active = 'SUBSET' in textypes
                rr.prop(dm, "export_atlas_texture_subset", text="Subset", toggle=True)
                rr = col.row(align=True)
                rr.active = 'HEIGHT' in textypes
                rr.prop(dm, "export_atlas_texture_white_height", text="White Height", toggle=True)

                row = b.split(factor=0.25)
                row.label(text="Channel Packed")

                r = row.row()

                col = r.column()
                col.template_list("MACHIN3_UL_atlas_channel_pack", "", dm, "export_atlas_texture_channel_packCOL", dm, "export_atlas_texture_channel_packIDX", rows=max(len(dm.export_atlas_texture_channel_packCOL), 2))

                col = r.column()
                col.operator("machin3.add_atlas_channel_pack", text="", icon_value=get_icon('plus'))
                col.operator("machin3.remove_atlas_channel_pack", text="", icon_value=get_icon('cancel'))

            else:

                col = b.column()
                row = col.split(factor=0.1)
                row.separator()
                row.label(text="No atlased Decals %s!" % ('selected' if context.selected_objects else 'visible'), icon='INFO')

        if dm.export_atlas_models:
            b = column.box()
            b.label(text="Models")

            row = b.split(factor=0.25)
            row.label(text="Format")
            r = row.row()
            r.prop(dm, 'export_atlas_model_format', expand=True)

            if dm.export_atlas_model_format == 'FBX':
                m3prefs = DM.addons['machin3tools']['prefs'] if DM.get_addon('MACHIN3tools') else None
                activate_unity = getattr(m3prefs, 'activate_unity', None)

                if activate_unity:
                    col = b.column(align=True)

                    row = col.split(factor=0.25)
                    row.label(text="Unity")
                    row.prop(dm, 'export_atlas_model_unity', text='True' if dm.export_atlas_model_unity else 'False', toggle=True)

                    if dm.export_atlas_model_unity:#
                        draw_machin3tools_unity_export(context, col)

        row = column.row()
        row.scale_y = 1.5
        row.operator("machin3.export_atlas_decals", text="Export")

    def draw_join_button(self, context, dm, layout):
        box = layout.box()
        box.label(text="Join & Split")

        column = box.column(align=True)
        column.scale_y = 1.2
        row = column.split(factor=0.7, align=True)
        row.operator("machin3.join_atlased_decals", text="Join Atlased Decals")

        r = row.row(align=True)
        r.active = True if [obj for obj in context.visible_objects if obj.DM.isdecal and obj.DM.preatlasmats] else False
        r.prop(dm, "export_atlas_join_atlased_per_parent", text="per Parent", toggle=True)
        column.operator("machin3.split_atlased_decals", text="Split Atlased Decals")

    def draw_use_atlas_button(self, layout):
        column = layout.column(align=True)

        row = column.row(align=True)
        row.scale_y = 1.5
        row.operator("machin3.use_atlas", text="Use %s" % ("Atlases" if sum(atlas.isenabled for atlas in get_atlas()[1]) > 1 else "Atlas"))
        row = column.row(align=True)
        row.scale_y = 1.2
        row.operator("machin3.restore_preatlas_decal_materials", text="Restore Pre-Atlas Decal UVs + Materials")

    def draw_decal_atlases(self, layout):
        layout.label(text="Decal Atlases")

        column = layout.column()

        row = column.row()

        col = row.column()
        prefs = get_prefs()
        col.template_list("MACHIN3_UL_export_atlases", "", prefs, "atlasesCOL", prefs, "atlasesIDX", rows=max(len(prefs.atlasesCOL), 6))

        col = row.column(align=True)
        col.operator("machin3.move_atlas", text="", icon="TRIA_UP").direction = "UP"
        col.operator("machin3.move_atlas", text="", icon="TRIA_DOWN").direction = "DOWN"
        col.separator()
        col.operator_context = "EXEC_DEFAULT"
        col.operator("wm.save_userpref", text="", icon_value=get_icon('save'))

    def draw_atlas_settings(self, dm, layout):
        row = layout.split(factor=0.5)
        row.label(text="Create Collections")
        row.prop(dm, "export_atlas_create_collections", text="True" if dm.export_atlas_create_collections else "False", toggle=True)

    def draw_assetspath_update(self, layout, legacy, ambiguous):
        box = layout.box()
        column = box.column()

        has_both_types = legacy and ambiguous
        has_multiple = (len(legacy) + len(ambiguous) > 1) or has_both_types

        updateable_type = 'Legacy and Ambiguous' if has_both_types else 'Legacy' if legacy else 'Ambiguous'

        updateable_action_button = 'Update and Fix' if has_both_types else 'Update' if legacy else 'Fix'
        updateable_object_button = 'Them All' if has_multiple else 'It'

        decalspath = os.path.join(get_prefs().assetspath, 'Decals')
        trimspath = os.path.join(get_prefs().assetspath, 'Trims')

        asset_type = 'Decal and Trim Sheet' if all(any(path.startswith(type_path) for path in legacy + ambiguous) for type_path in [decalspath, trimspath]) else 'Decal' if all(path.startswith(decalspath) for path in legacy + ambiguous) else 'Trim Sheet'

        text = f"{updateable_type} {asset_type} {'libraries' if has_multiple else 'library'} detected!"
        optext = f"{updateable_action_button} {updateable_object_button}!"

        column.label(text=text, icon='INFO')

        row = column.row()
        row.scale_y = 1.5
        row.operator("machin3.batch_update_decal_libraries", text=optext)

    def draw_library_update(self, context, layout, dm):
        box = layout.box()
        column = box.column()

        is_trimsheet = dm.updatelibraryistrimsheet

        row = column.split(factor=0.33)
        row.label(text="Library Path")
        row.prop(context.scene.DM, "updatelibrarypath", text="")

        if not dm.update_library_inplace and not is_trimsheet:
            if context.scene.userdecallibs:
                row = column.split(factor=0.33)
                row.label(text="User Decal Library")
                row.prop(context.scene, "userdecallibs", text="")

            else:
                column.separator()
                column.label(text="Create a new Library or Unlock an existing one.", icon_value=get_icon('error'))
                column.separator()

        row = column.split(factor=0.33)
        row.label(text="Settings")

        col = row.column()
        row = col.row()

        row.active = not is_library_in_assetspath(dm.updatelibrarypath)
        row.prop(dm, "update_library_inplace")

        col.prop(dm, "update_keep_old_thumbnails")

        if is_trimsheet and not dm.update_library_inplace:
            sheetname = os.path.basename(context.scene.DM.updatelibrarypath)
            sheetlib = get_prefs().decallibsCOL.get(sheetname)

            if sheetlib and sheetlib.istrimsheet:
                column = box.column()
                column.label(text="A Trim Sheet of that name is already registered!", icon_value=get_icon('error'))

        column = box.column()

        row = column.row()
        row.scale_y = 1.5
        row.active = bool(dm.updatelibrarypath)
        op = row.operator("machin3.update_decal_library", text=f"Update {'Trim Decal' if is_trimsheet else 'Decal'} Library")
        op.path = dm.updatelibrarypath
        op.batch = False
        op.auto_fix = False

    def draw_update_blend_file(self, layout, decal, sheet):
        box = layout.box()

        column = box.column()
        column.label(text="Legacy Assets in Current File")

        row = column.row()
        row.scale_y = 1.5
        row.operator("machin3.update_blend_file", text=f"Update {'Decals & Trimsheets' if decal and sheet else 'Decals' if decal else 'Trimsheets'} in current .blend")

        if decal:
            for version, decals in sorted(decal.items()):
                b = box.box()
                b.label(text=f"Decal Version {get_pretty_version(version)}")

                col = b.column(align=True)

                for name in sorted(decals['names']):
                    is_registered = decals['registered'][name]
                    mat_count = decals['count'][name]

                    row = col.row(align=True)
                    row.active = is_registered
                    row.label(text=f" {'✔' if is_registered else '❌'} {mat_count} x {name} {'' if is_registered else ' - not registered!'}")

        if sheet:
            for version, sheets in sorted(sheet.items()):
                b = box.box()
                b.label(text=f"Trimsheet Version {get_pretty_version(version)}")

                col = b.column(align=True)

                for name in sorted(sheets['names']):
                    is_registered = sheets['registered'][name]
                    mat_count = sheets['count'][name]

                    row = col.row(align=True)
                    row.active = is_registered
                    row.label(text=f" {'✔' if is_registered else '❌'} {mat_count} x {name} {'' if is_registered else ' - not registered!'}")

    def draw_resources(self, layout):
        current_path = os.path.dirname(bpy.data.filepath)

        resources_path = os.path.join(get_path(), "resources")
        example_decal_basics_path = os.path.join(resources_path, "Example_Decal_Basics.blend")
        example_decal_creation_path = os.path.join(resources_path, "Example_Decal_Creation.blend")
        example_decal_bake_path = os.path.join(resources_path, "Example_Decal_Bake.blend")
        example_decal_asset_path = os.path.join(resources_path, "Example_Decal_Asset.blend")

        example_trimsheet_geometry_path = os.path.join(resources_path, "Example_Trim_Sheet_Geometry.blend")
        example_trimsheet_setup_path = os.path.join(resources_path, "Example_Trim_Sheet_Setup.blend")
        example_trimsheet_asset_path = os.path.join(resources_path, "Example_Trim_Sheet_Asset.blend")

        if sub_panel := get_panel_fold(layout, "examples", "Examples", icon="FILE_BLEND", default_closed=True):
            if bpy.data.is_dirty and resources_path != current_path:
                col = sub_panel.column(align=True)
                col.alert = True
                row = col.row(align=True)
                row.alignment = 'CENTER'
                row.label(text="Your current file is not saved!", icon="ERROR")
                row = col.row(align=True)
                row.alignment = 'CENTER'
                row.label(text="Unsaved changes will be lost,")
                row = col.row(align=True)
                row.alignment = 'CENTER'
                row.label(text="if you load the following examples.")

            row = sub_panel.row(align=True)
            row.scale_y = 1.5
            row.operator_context = 'EXEC_DEFAULT'
            op = row.operator("wm.open_mainfile", text="Decal Basics", icon="FILE_BLEND")
            op.filepath = example_decal_basics_path
            op.load_ui = True

            row = sub_panel.row(align=True)
            row.scale_y = 1.2
            row.operator_context = 'EXEC_DEFAULT'
            op = row.operator("wm.open_mainfile", text="Create Decals", icon="FILE_BLEND")
            op.filepath=example_decal_creation_path
            op.load_ui = True
            op = row.operator("wm.open_mainfile", text="Bake Decals", icon="FILE_BLEND")
            op.filepath = example_decal_bake_path
            op.load_ui = True

            row = sub_panel.row(align=True)
            row.scale_y = 1.5
            row.operator_context = 'EXEC_DEFAULT'
            op = row.operator("wm.open_mainfile", text="Decal Demo Asset", icon="FILE_BLEND")
            op.filepath = example_decal_asset_path
            op.load_ui = True

            sub_panel.separator()

            row = sub_panel.row(align=True)
            row.scale_y = 1.2
            row.operator_context = 'EXEC_DEFAULT'
            op = row.operator("wm.open_mainfile", text="Trim Sheet Geometry", icon="FILE_BLEND")
            op.filepath = example_trimsheet_geometry_path

            op.load_ui = True
            op = row.operator("wm.open_mainfile", text="Trim Sheet Setup", icon="FILE_BLEND")
            op.filepath = example_trimsheet_setup_path
            op.load_ui = True

            row = sub_panel.row(align=True)
            row.scale_y = 1.5
            row.operator_context = 'EXEC_DEFAULT'
            op = row.operator("wm.open_mainfile", text="Trim Sheet Demo Asset", icon="FILE_BLEND")
            op.filepath = example_trimsheet_asset_path
            op.load_ui = True

            sub_panel.separator()
            column = sub_panel.column(align=True)
            row = column.row(align=True)
            row.alignment = 'CENTER'
            row.label(text="Please refer to the documentation", icon='INFO')
            row = column.row(align=True)
            row.alignment = 'CENTER'
            row.label(text="for details on Trim Sheet and Atlas Creation")

        if sub_panel := get_panel_fold(layout, "decal_packs", "3rd Party Decal Packs", icon="PLUGIN", default_closed=True):
            row = sub_panel.row()
            row.scale_y = 1.2
            row.operator("wm.url_open", text="Decal Packs", icon='RENDER_RESULT').url = "https://machin3.io/DECALmachine/docs/decal_resources"

    def draw_support(self, layout):
        layout.scale_y = 1.5
        layout.operator('machin3.get_decalmachine_support', text='Get Support', icon='GREASEPENCIL')

    def draw_documentation(self, layout):
        row = layout.row(align=True)
        row.scale_y = 1.25
        row.operator("wm.url_open", text="Local", icon='FILE_BACKUP').url = "file://" + os.path.join(get_path(), "docs", "index.html")
        row.operator("wm.url_open", text="Online", icon='FILE_BLEND').url = "https://machin3.io/DECALmachine/docs"

        row = layout.row(align=True)
        row.scale_y = 1.2
        row.operator("wm.url_open", text="FAQ", icon='QUESTION').url = "https://machin3.io/DECALmachine/docs/faq"
        row.operator("wm.url_open", text="Youtube", icon='FILE_MOVIE').url = "https://www.youtube.com/playlist?list=PLcEiZ9GDvSdWiU2BPQp99HglGGg1OGiHs"

        layout.separator()

        row = layout.row(align=True)
        row.operator("wm.url_open", text="Blender Artists", icon="COMMUNITY").url = "https://blenderartists.org/t/decalmachine/688181"

    def draw_debug(self, context, layout, dm):
        if bpy.ops.machin3.decalmachine_debug.poll():
            row = layout.row(align=True)
            row.scale_y = 1.5
            row.operator("machin3.decalmachine_debug", text="Button")

        if dm.debug:
            if context.scene.userdecallibs:
                row = layout.split(factor=0.33, align=True)
                row.label(text="User Decal Library")
                row.prop(context.scene, "userdecallibs", text="")

                if getattr(bpy.types, "MACHIN3_OT_rerender_decal_thumbnails", False):
                    row = layout.row(align=True)
                    row.scale_y = 1.2
                    row.operator("machin3.rerender_decal_thumbnails", text="Re-Render Decal Thumbnails")

                if getattr(bpy.types, "MACHIN3_OT_update_interpolation", False):
                    row = layout.row(align=True)
                    row.scale_y = 1.2
                    row.operator("machin3.update_interpolation", text="Update Interpolation")

            else:
                layout.separator()
                layout.label(text="Create a new Library or Unlock an existing one.", icon_value=get_icon('error'))
                layout.separator()

            if getattr(bpy.types, "MACHIN3_OT_update_decal_node_tree", False):
                row = layout.row(align=True)
                row.scale_y = 1.2
                row.operator("machin3.update_decal_node_tree", text="Update Decal NodeTrees")

            if getattr(bpy.types, "MACHIN3_OT_replace_material", False):
                row = layout.row(align=True)
                row.scale_y = 1.2
                row.operator("machin3.replace_material", text="Replace Material")

            if getattr(bpy.types, "MACHIN3_OT_set_props_and_name_from_material", False):
                row = layout.row(align=True)
                row.scale_y = 1.2
                row.operator("machin3.set_props_and_name_from_material", text="Set Props and Name from Material")

            if getattr(bpy.types, "MACHIN3_OT_update_decal_backup", False):
                row = layout.row(align=True)
                row.scale_y = 1.2
                row.operator("machin3.update_decal_backup", text="Update Decal Backup")

            if getattr(bpy.types, "MACHIN3_OT_update_add_nodes_clamping", False):
                layout.separator()

                row = layout.row(align=True)
                row.scale_y = 1.5
                row.operator("machin3.update_add_nodes_clamping", text="Fix AO Clamping")

class PanelMaterial(bpy.types.Panel):
    bl_idname = "MACHIN3_PT_material_decal_machine"
    bl_label = "Trim Sheet"
    bl_space_type = "PROPERTIES"
    bl_region_type = "WINDOW"
    bl_context = 'material'

    @classmethod
    def poll(cls, context):
        return poll_trimsheetlibs()

    def draw(self, context):
        layout = self.layout

        column = layout.column()

        col = column.column(align=True)
        col.scale_y = 1.2
        col.prop(context.scene, "trimsheetlibs", text='')
        col.operator('machin3.init_trimsheet_mat', text='Init Trim Sheet Material')

        column.separator()
        row = column.row()
        row.scale_y = 1.2

        row.operator('machin3.setup_trimsheet_subsets', text='Setup Subsets')
