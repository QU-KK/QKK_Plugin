# ##### BEGIN GPL LICENSE BLOCK #####
#
#  This program is free software; you can redistribute it and/or
#  modify it under the terms of the GNU General Public License
#  as published by the Free Software Foundation; either version 2
#  of the License, or (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program; if not, write to the Free Software Foundation,
#  Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301, USA.
#
# ##### END GPL LICENSE BLOCK #####

# Copyright 2025, Alex Zhornyak - alexander.zhornyak@gmail.com

import bpy
import bmesh
from bl_operators.presets import AddPresetOperator, AddPresetBase

import os
import subprocess
import urllib.error
import urllib.request
import ssl
import uuid
from zipfile import ZipFile
from io import BytesIO
from collections import defaultdict
import numpy as np

from ZenUV.ui.pie import ZsPieFactory
from ZenUV.utils.blender_zen_utils import ZuvPresets, ZenPolls
from ZenUV.utils.generic import (
    verify_uv_layer, has_overlapped_triangles_by_area,
    calc_uv_editor_image_aspect_ratio,
    correct_self_intersecting_face)
from ZenUV.utils.vlog import Log
from ZenUV.utils.selection_utils import SelectionProcessor, UniSelectedObject
from ZenUV.utils.get_uv_islands import get_uv_bound_edges_indexes
from ZenUV.ui.labels import ZuvLabels
from ZenUV.ops.texel_density.td_props import TdProps
from ZenUV.ops.context_utils import WM_MT_zenuv_operator_presets


class MinistryOfFlatData:
    URL_MINISTRY_OF_FLAT = 'https://www.quelsolaar.com/ministry_of_flat/'
    MINISTRY_OF_FLAT_TEXT = "www.ministryofflat.com"
    MINISTRY_OF_FLAT_AUTHOR = "Eskil Steenberg"


class ZUV_OT_AutoUVUnwrap(bpy.types.Operator):
    bl_idname = "uv.zenuv_auto_uv_unwrap"
    bl_label = "Auto Unwrap"
    bl_options = {'REGISTER', 'UNDO', 'PRESET'}
    bl_description = F"Automated UV unwrapper based on utility, written by {MinistryOfFlatData.MINISTRY_OF_FLAT_AUTHOR} {MinistryOfFlatData.MINISTRY_OF_FLAT_TEXT}"
    bl_ui_units_x = 16

    force_hard_surface: bpy.props.BoolProperty(
        name="Force Hard Surface",
        description="Makes the algorithm treat the surface as Hard Surface, ensuring precise handling of sharp edges and rigid structures",
        default=False
    )

    separate_by_material: bpy.props.BoolProperty(
        name="Separate By Material",
        description="Mesh is splitted by materials before unwrapping",
        default=False
    )

    separate_sharp_edges: bpy.props.BoolProperty(
        name="Separate By Sharp Edges",
        description="Mesh is splitted by sharp edges before unwrapping",
        default=False
    )

    triangulate_mesh: bpy.props.BoolProperty(
        name="Triangulate Mesh",
        description="All ngons with four or more vertices will be triangulated",
        default=False
    )

    triangulate_ngon_method: bpy.props.EnumProperty(
        name=bpy.types.TriangulateModifier.bl_rna.properties["ngon_method"].name,
        description=bpy.types.TriangulateModifier.bl_rna.properties["ngon_method"].description,
        items=[
            (item.identifier, item.name, item.description)
            for item in bpy.types.TriangulateModifier.bl_rna.properties["ngon_method"].enum_items_static],
        default="CLIP"
    )

    triangulate_quad_method: bpy.props.EnumProperty(
        name=bpy.types.TriangulateModifier.bl_rna.properties["quad_method"].name,
        description=bpy.types.TriangulateModifier.bl_rna.properties["quad_method"].description,
        items=[
            (item.identifier, item.name, item.description)
            for item in bpy.types.TriangulateModifier.bl_rna.properties["quad_method"].enum_items_static],
        default="BEAUTY"
    )

    auto_detect_hard_edges: bpy.props.BoolProperty(
        name="Auto Detect Hard Edges",
        description="UV unwrapper will try to separate all hard edges. Useful for lightmapping and Normalmapping",
        default=False
    )

    use_normal: bpy.props.BoolProperty(
        name="Use Normal",
        description="Use the models normals to help classify polygons",
        default=False
    )

    overlap_identical_parts: bpy.props.BoolProperty(
        name="Overlap Identical Parts",
        description="Overlap identtical parts to take up the same texture space",
        default=False
    )

    overlap_mirrored_parts: bpy.props.BoolProperty(
        name="Overlap Mirrored parts",
        description="Overlap mirrored parts to take up the same texture space",
        default=False
    )

    world_scale: bpy.props.BoolProperty(
        name="Scale UV to Worldspace",
        description="Scales the UVs to match their real world scale going beyound the zero to one range",
        default=True
    )

    use_texel_density: bpy.props.BoolProperty(
        name="Use Texel Density",
        description="Scales the UVs to match the texel density value",
        default=False
    )

    texel_density: bpy.props.FloatProperty(
        name=ZuvLabels.PREF_TEXEL_DENSITY_LABEL,
        description=ZuvLabels.PREF_TEXEL_DENSITY_DESC,
        min=0.001,
        default=1024.0,
        precision=2
    )

    TD_TextureSizeX: TdProps.TD_TextureSizeX
    TD_TextureSizeY: TdProps.TD_TextureSizeY
    td_im_size_presets: TdProps.td_im_size_presets

    mark_seam_edges: bpy.props.BoolProperty(
        name="Mark Seams",
        description="Automatically assign seams",
        default=True
    )

    correct_self_intersecting: bpy.props.BoolProperty(
        name="Correct Self-Intersecting",
        description="Correct uv faces that have self-intersecting uv edges",
        default=True
    )

    stretch: bpy.props.BoolProperty(
        name="Stretch",
        description="Stretch any island that is too wide to fit in the image",
        default=False
    )

    packing: bpy.props.BoolProperty(
        name="Packing",
        description="Pack islands in to a rectangle",
        default=True
    )

    cut: bpy.props.BoolProperty(
        name="Cut",
        description="Cut down awkward shapes in order to optimize layout coverage",
        default=False
    )

    squares: bpy.props.BoolProperty(
        name="Squares",
        description="Finds various individual polygons that hare right angles",
        default=False
    )

    quads: bpy.props.BoolProperty(
        name="Quads",
        description="Searches the model for triangle pairs that make good quads. Improves the use of patches",
        default=True
    )

    weld: bpy.props.BoolProperty(
        name="Vertex Weld",
        description="Merges duplicate vertices, Does not efect the out put polygon or vertext data",
        default=False
    )

    extra_cmd: bpy.props.StringProperty(
        name="Extra Arguments",
        description="Extended command line arguments that can be passed to the uv unwrapping application",
        default=""
    )

    LITERAL_PRESET_AUTO_UV_UNWRAP = "auto_uv_unwrap"
    LITERAL_UNWRAPPER_APPLICATION = "MinistryOfFlat_Release/UnWrapConsole3.exe"
    LITERAL_ATTR_LOOP_INDICES = "LOOPS_INDICES"

    @classmethod
    def get_unwrapper_file_path(cls):
        s_target_dir = ZuvPresets.get_full_preset_path(ZUV_OT_AutoUVUnwrap.LITERAL_PRESET_AUTO_UV_UNWRAP)
        s_unwrapper_app = os.path.join(s_target_dir, ZUV_OT_AutoUVUnwrap.LITERAL_UNWRAPPER_APPLICATION)
        return s_unwrapper_app

    @classmethod
    def poll(cls, context):
        """ Validate context """
        active_object = context.active_object
        if active_object is not None and active_object.type == 'MESH' and context.mode == 'EDIT_MESH':
            return True
        return False

    def invoke(self, context: bpy.types.Context, event: bpy.types.Event):
        s_target_dir = ZuvPresets.force_full_preset_path(
            ZUV_OT_AutoUVUnwrap.LITERAL_PRESET_AUTO_UV_UNWRAP)
        if not s_target_dir:
            self.report({'ERROR'}, f"Can not create: {ZUV_OT_AutoUVUnwrap.LITERAL_PRESET_AUTO_UV_UNWRAP} - directory!")
            return {'CANCELLED'}

        s_unwrapper_app = os.path.join(s_target_dir, ZUV_OT_AutoUVUnwrap.LITERAL_UNWRAPPER_APPLICATION)
        if not os.path.exists(s_unwrapper_app):
            if not bpy.ops.wm.zenuv_auto_uv_unwrap_install.poll():
                self.report({'WARNING'}, 'OFFLINE - Allow Online Access in Blender Preferences to continue!')
                return {'CANCELLED'}
            return bpy.ops.wm.zenuv_auto_uv_unwrap_install('INVOKE_DEFAULT')

        return self.execute(context)

    @classmethod
    def do_draw(cls, op, layout: bpy.types.UILayout, context: bpy.types.Context):
        b_is_last_props = isinstance(op, bpy.types.OperatorProperties)

        from ZenUV.prop.zuv_preferences import get_prefs
        addon_prefs = get_prefs()

        layout.use_property_decorate = False  # No animation

        def draw_td(p_box: bpy.types.UILayout):
            p_scene = context.scene
            td_props = p_scene.zen_uv.td_props

            row = p_box.row(align=True)
            row.use_property_split = True
            row.prop(op, "use_texel_density")

            col = p_box.column(align=False)
            col.active = op.use_texel_density

            from ZenUV.ops.operators import ZUV_OT_SetTextureSizePreset
            s_last_props_td = 'window_manager.operator_properties_last("uv.zenuv_auto_uv_unwrap").td_im_size_presets'

            s_data_path = (
                s_last_props_td
                if b_is_last_props else
                'active_operator.td_im_size_presets'
            )

            ZUV_OT_SetTextureSizePreset.draw_image_size_preset(
                s_data_path, context, col,
                s_import_data_path=s_last_props_td,
                b_alert_accent=False,
                use_property_split=True)

            b_is_same = td_props.prp_current_td == op.texel_density

            row = col.row(align=True)
            r_split = row.split(factor=0.4)
            r_label = r_split.row(align=True)
            r_label.alignment = 'RIGHT'
            r_label.label(text="Texel Density")
            row = r_split.row(align=True)
            r1 = row.row(align=True)
            r1.ui_units_x = 4
            r1.prop(op, 'texel_density', text="")
            r_units = row.row(align=True)
            r_units.ui_units_x = 3
            r_units.enabled = False
            r_units.prop(td_props, "td_unit", text="")

            r2 = row.row(align=True)
            r2.active = not b_is_same
            r2.context_pointer_set("unwrap_operator", op)
            op_set = r2.operator("wm.zenuv_script_exec", text='', icon='IMPORT')
            op_set.script = "C.unwrap_operator.texel_density = C.scene.zen_uv.td_props.prp_current_td"
            op_set.desc = f"Set current Texel Density value: {td_props.prp_current_td:.2f}"

        box: bpy.types.UILayout = addon_prefs.op_addon_props.prepare_layout_panel(layout, "expand_auto_unwrap_preprocess")
        if box:
            col = box.column(align=True)
            col.use_property_split = True
            col.prop(op, "force_hard_surface")
            col.prop(op, "separate_by_material")
            col.prop(op, "separate_sharp_edges")
            col.prop(op, "triangulate_mesh")
            if op.triangulate_mesh:
                col.prop(op, "triangulate_ngon_method")
                col.prop(op, "triangulate_quad_method")

        box: bpy.types.UILayout = addon_prefs.op_addon_props.prepare_layout_panel(layout, "expand_auto_unwrap_postprocess")
        if box:
            col = box.column(align=True)
            col.use_property_split = True
            col.prop(op, "mark_seam_edges")
            col.prop(op, "correct_self_intersecting")

        # NOTE: Texel density block
        box: bpy.types.UILayout = addon_prefs.op_addon_props.prepare_layout_panel(layout, "expand_auto_unwrap_texel_density")
        if box:
            draw_td(box)

        box: bpy.types.UILayout = addon_prefs.op_addon_props.prepare_layout_panel(layout, "expand_auto_unwrap_unwrap_settings")
        if box:
            col = box.column(align=True)
            col.use_property_split = True
            col.prop(op, "auto_detect_hard_edges")
            col.prop(op, "use_normal")
            col.prop(op, "overlap_identical_parts")
            col.prop(op, "overlap_mirrored_parts")
            col.prop(op, "world_scale")

        box: bpy.types.UILayout = addon_prefs.op_addon_props.prepare_layout_panel(layout, "expand_auto_unwrap_advanced_settings")
        if box:
            col = box.column(align=True)
            col.use_property_split = True
            col.prop(op, "stretch")
            col.prop(op, "packing")
            col.prop(op, "cut")
            col.prop(op, "squares")
            col.prop(op, "weld")
            col.prop(op, "quads")
            col.prop(op, "extra_cmd")

    def draw(self, context: bpy.types.Context):
        ZUV_OT_AutoUVUnwrap.do_draw(self, self.layout, context)

    def update_unwrapper_arguments(self, t_args: list):
        d_image_aspect = 1.0
        if self.use_texel_density:
            if self.td_im_size_presets == 'Custom':
                d_image_aspect = self.TD_TextureSizeX / self.TD_TextureSizeY

        if self.auto_detect_hard_edges:
            t_args.append("-SEPARATE")
            t_args.append("TRUE")

        if self.use_normal:
            t_args.append("-NORMALS")
            t_args.append("TRUE")

        if self.overlap_identical_parts:
            t_args.append("-OVERLAP")
            t_args.append("TRUE")

        if self.overlap_mirrored_parts:
            t_args.append("-MIRROR")
            t_args.append("TRUE")

        if self.world_scale:
            t_args.append("-WORLDSCALE")
            t_args.append("TRUE")

        if self.use_texel_density:
            t_args.append("-DENSITY")
            t_args.append(f"{round(self.texel_density)}")

            t_args.append("-RESOLUTION")
            t_args.append(str(self.TD_TextureSizeX))

            if self.td_im_size_presets == 'Custom':
                t_args.append("-ASPECT")
                t_args.append(f'{d_image_aspect:.4f}')

        t_args.append("-STRETCH")
        t_args.append(str(self.stretch).upper())

        t_args.append("-PACKING")
        t_args.append(str(self.packing).upper())

        t_args.append("-CUTDEBUG")
        t_args.append(str(self.cut).upper())

        t_args.append("-SQUARE")
        t_args.append(str(self.squares).upper())

        t_args.append("-WELD")
        t_args.append(str(self.weld).upper())

        t_args.append("-QUAD")
        t_args.append(str(self.quads).upper())

        t_args.append("-SILENT")
        t_args.append("TRUE")

        s_extra_args: str = self.extra_cmd.strip()
        if s_extra_args:
            t_args.extend(s_extra_args.split(" "))

    def execute(self, context):

        ZsPieFactory.mark_pie_cancelled()

        if not context.scene.tool_settings.use_uv_select_sync:
            context.scene.tool_settings.use_uv_select_sync = True

        bpy.ops.mesh.select_mode(type="FACE", action="ENABLE")

        stored_selection = SelectionProcessor.collect_selected_objects(
            context, False,
            b_skip_uv_layer_fail=True,
            b_is_skip_objs_without_selection=True, b_in_indices=True)
        if not stored_selection:
            self.report({'WARNING'}, "Zen UV: Select something.")
            return {'CANCELLED'}

        s_target_dir = ZuvPresets.force_full_preset_path(ZUV_OT_AutoUVUnwrap.LITERAL_PRESET_AUTO_UV_UNWRAP)
        if not s_target_dir:
            self.report({'ERROR'}, f"Can not create: {ZUV_OT_AutoUVUnwrap.LITERAL_PRESET_AUTO_UV_UNWRAP} - directory!")
            return {'CANCELLED'}

        s_unwrapper_app = os.path.join(s_target_dir, ZUV_OT_AutoUVUnwrap.LITERAL_UNWRAPPER_APPLICATION)
        if not os.path.exists(s_unwrapper_app):
            self.report({'ERROR'}, f"Install {ZUV_OT_AutoUVUnwrap.LITERAL_UNWRAPPER_APPLICATION}!")
            return {'CANCELLED'}

        p_all_object_names = {obj.name for obj in context.objects_in_mode}
        s_act_obj_name = context.active_object.name

        t_new_objects = defaultdict(list)

        b_is_groupping = self.separate_by_material

        t_hidden_data = {}

        if b_is_groupping:

            for u_obj in stored_selection:
                t_hidden_faces = {}
                bm = bmesh.from_edit_mesh(u_obj.obj.data)
                bm.faces.ensure_lookup_table()
                t_hidden_faces = {face.index for face in bm.faces if face.hide}
                if t_hidden_faces:
                    t_hidden_data[u_obj.obj_name] = t_hidden_faces

        def process_selection(bm: bmesh.types.BMesh, s_obj_name: str, indices: list):
            s_temp_obj_name = str(uuid.uuid4())
            bm.faces.ensure_lookup_table()

            mesh_new = bpy.data.meshes.new(name=s_temp_obj_name)
            p_obj = bpy.data.objects.new(s_temp_obj_name, mesh_new)
            bpy.context.collection.objects.link(p_obj)

            bm_new = bmesh.new()
            bm_new.from_mesh(mesh_new)
            vert_map = {}  # Mapping from old vertices to new vertices

            # Copy the faces and their related vertices/edges
            for idx in indices:
                face: bmesh.types.BMFace = bm.faces[idx]
                new_verts = []
                for vert in face.verts:
                    if vert not in vert_map:
                        new_vert = bm_new.verts.new(vert.co)
                        vert_map[vert] = new_vert
                        new_vert.normal = vert.normal[:]
                    new_verts.append(vert_map[vert])
                new_face: bmesh.types.BMFace = bm_new.faces.new(new_verts)
                new_face.normal = face.normal[:]
                new_face.smooth = face.smooth

            bm_new.verts.ensure_lookup_table()
            bm_new.edges.ensure_lookup_table()
            bm_new.faces.ensure_lookup_table()

            for idx_out, idx_in in enumerate(indices):
                f_in: bmesh.types.BMesh = bm.faces[idx_in]
                f_out: bmesh.types.BMesh = bm_new.faces[idx_out]
                t_in_edges = [e for e in f_in.edges]
                t_out_edges = [e for e in f_out.edges]
                if len(t_in_edges) == len(t_out_edges):
                    for idx in range(len(t_in_edges)):
                        t_out_edges[idx].seam = t_in_edges[idx].seam
                        t_out_edges[idx].smooth = t_in_edges[idx].smooth
                else:
                    raise RuntimeError(f"Edge count mismatch: {len(t_in_edges)} != {len(t_out_edges)} !")

            bm_new.normal_update()

            bm_new.verts.ensure_lookup_table()
            bm_new.edges.ensure_lookup_table()
            bm_new.faces.ensure_lookup_table()

            edges = (
                [e for e in bm_new.edges if e.seam or not e.smooth]
                if self.separate_sharp_edges else
                [e for e in bm_new.edges if e.seam])
            bmesh.ops.split_edges(bm_new, edges=edges)

            if self.force_hard_surface:

                bm_new.verts.ensure_lookup_table()
                bm_new.edges.ensure_lookup_table()
                bm_new.faces.ensure_lookup_table()

                d_cube_side = (sum(p_obj.dimensions) / 3) * 0.001

                verts = [
                    bm_new.verts.new((d_cube_side, d_cube_side, d_cube_side)),
                    bm_new.verts.new((d_cube_side, d_cube_side, -d_cube_side)),
                    bm_new.verts.new((d_cube_side, -d_cube_side, d_cube_side)),
                    bm_new.verts.new((d_cube_side, -d_cube_side, -d_cube_side)),
                    bm_new.verts.new((-d_cube_side, d_cube_side, d_cube_side)),
                    bm_new.verts.new((-d_cube_side, d_cube_side, -d_cube_side)),
                    bm_new.verts.new((-d_cube_side, -d_cube_side, d_cube_side)),
                    bm_new.verts.new((-d_cube_side, -d_cube_side, -d_cube_side))
                ]
                bm_new.verts.ensure_lookup_table()

                bm_new.faces.new((verts[0], verts[1], verts[3], verts[2])),
                bm_new.faces.new((verts[4], verts[5], verts[7], verts[6])),
                bm_new.faces.new((verts[0], verts[1], verts[5], verts[4])),
                bm_new.faces.new((verts[2], verts[3], verts[7], verts[6])),
                bm_new.faces.new((verts[0], verts[2], verts[6], verts[4])),
                bm_new.faces.new((verts[1], verts[3], verts[7], verts[5]))

            bm_new.to_mesh(mesh_new)
            mesh_new.update()

            bm_new.free()

            t_new_objects[s_obj_name].append(
                (s_temp_obj_name, indices.copy()))

        u_obj: UniSelectedObject
        for u_obj in stored_selection:
            bpy.ops.mesh.select_all(action='DESELECT')

            if b_is_groupping:
                bpy.ops.mesh.reveal(select=False)

            SelectionProcessor.restore_items_selection(u_obj)

            si = u_obj.selected_items

            p_obj = bpy.data.objects.get(u_obj.obj_name)
            me: bpy.types.Mesh = p_obj.data
            bm = bmesh.from_edit_mesh(me)

            if b_is_groupping:
                bpy.ops.mesh.hide(unselected=True)
                bpy.ops.mesh.select_all(action='DESELECT')

                t_groups = []

                b_have_unprocessed = False

                for i in si.selected_faces:
                    bm.faces.ensure_lookup_table()
                    p_face: bmesh.types.BMFace = bm.faces[i]
                    if p_face.hide:
                        continue
                    p_face.select_set(True)

                    was_sel = me.total_face_sel
                    res = bpy.ops.mesh.select_linked(delimit={'MATERIAL'})

                    if 'FINISHED' in res:
                        p_new_sel_count = me.total_face_sel
                        sel_dif = p_new_sel_count - was_sel
                        min_group_size = 1
                        if p_new_sel_count > 0 and sel_dif >= min_group_size - 1:
                            bm.faces.ensure_lookup_table()
                            t_groups.append([idx for idx in si.selected_faces if bm.faces[idx].select])
                        elif p_new_sel_count == 0:
                            p_face.select_set(True)
                            b_have_unprocessed = True
                    else:
                        p_face.select_set(True)
                        b_have_unprocessed = True

                    bpy.ops.mesh.hide(unselected=False)

                if b_have_unprocessed:
                    t_all_indices = set(si.selected_faces)
                    for group in t_groups:
                        t_all_indices.difference_update(group)

                    if t_all_indices:
                        t_all_indices = sorted(t_all_indices)
                        t_groups.append(t_all_indices)

                bpy.ops.mesh.reveal(select=False)
                bpy.ops.mesh.select_all(action='DESELECT')

                # NOTE: nothing was splitted, this is the all mesh
                if len(t_groups) == len(si.selected_faces):
                    process_selection(bm, u_obj.obj_name, si.selected_faces)
                else:
                    for group in t_groups:
                        process_selection(bm, u_obj.obj_name, group)
            else:
                process_selection(bm, u_obj.obj_name, si.selected_faces)

        bpy.ops.object.mode_set(mode='OBJECT')

        bpy.ops.object.select_all(action='DESELECT')

        b_triangulate = self.triangulate_mesh

        t_triangulate_map = {}

        for obj_list in t_new_objects.values():
            for s_obj_name, _ in obj_list:
                p_obj: bpy.types.Object = bpy.data.objects.get(s_obj_name)
                p_obj.select_set(True)

                if b_triangulate:
                    me: bpy.types.Mesh = p_obj.data
                    p_attr: bpy.types.IntAttribute = me.attributes.new(
                        ZUV_OT_AutoUVUnwrap.LITERAL_ATTR_LOOP_INDICES, type='INT', domain='CORNER')
                    n_loop_count = len(me.loops)
                    p_arr = list(range(n_loop_count))
                    p_attr.data.foreach_set("value", p_arr)

        if b_triangulate:
            bpy.ops.object.duplicate(linked=False, mode='TRANSLATION')

            for p_obj in context.selected_objects[:]:
                triangulate_modifier: bpy.types.TriangulateModifier = p_obj.modifiers.new(name="Triangulate", type='TRIANGULATE')
                triangulate_modifier.ngon_method = self.triangulate_ngon_method
                triangulate_modifier.quad_method = self.triangulate_quad_method
                triangulate_modifier.min_vertices = 4
                override_context = {'object': p_obj, 'view_layer': bpy.context.view_layer}
                with bpy.context.temp_override(**override_context):
                    bpy.ops.object.modifier_apply(modifier=triangulate_modifier.name)
                me: bpy.types.Mesh = p_obj.data
                p_attr = me.attributes.get(ZUV_OT_AutoUVUnwrap.LITERAL_ATTR_LOOP_INDICES)
                p_arr = [0] * len(me.loops)
                p_attr.data.foreach_get("value", p_arr)
                t_triangulate_map[p_obj.name] = p_arr

        s_filename = '_TEMP.obj'
        s_filename_unwrapped = '_TEMP_UNWRAPPED.obj'

        s_out_file = os.path.join(s_target_dir, s_filename)

        res = bpy.ops.wm.obj_export(
            filepath=s_out_file,
            export_selected_objects=True,
            export_materials=False,
            export_uv=False,
            export_normals=True,
            export_smooth_groups=True
        )

        for obj_list in t_new_objects.values():
            for s_obj_name, _ in obj_list:
                s_it_obj = f"{s_obj_name}.001" if b_triangulate else s_obj_name
                p_obj: bpy.types.Object = bpy.data.objects.get(s_it_obj)
                bpy.data.objects.remove(p_obj)
                temp_me = bpy.data.meshes.get(s_it_obj)
                if temp_me:
                    bpy.data.meshes.remove(temp_me)

        if 'FINISHED' in res:
            t_args = [s_unwrapper_app, s_filename, s_filename_unwrapped]

            self.update_unwrapper_arguments(t_args)

            subprocess.call(
                t_args,
                cwd=s_target_dir)

            s_in_file = os.path.join(s_target_dir, s_filename_unwrapped)

            try:
                # NOTE: we do not analyze the result of call, we just understand that it is failed by missing target file
                if os.path.exists(s_in_file):
                    all_objs = set(bpy.data.objects)
                    if 'FINISHED' in bpy.ops.wm.obj_import(filepath=s_in_file):
                        new_objs = set(bpy.data.objects) - all_objs
                        if len(new_objs) == 0:
                            self.report({'WARNING'}, "No objects were processed during unwrap!")
                    else:
                        self.report({'WARNING'}, "Import failed!")
                else:
                    self.report({'WARNING'}, "Unwrap failed!")

            finally:
                try:
                    os.remove(s_out_file)
                    os.remove(s_in_file)
                except OSError as e:
                    Log.error("AUTO UNWRAP:", e)
                    pass
        else:
            self.report({'WARNING'}, "Export failed!")

        bpy.ops.object.select_all(action='DESELECT')

        t_uv_ratio_max = []

        for s_obj in p_all_object_names:
            p_obj: bpy.types.Object = bpy.data.objects.get(s_obj)
            p_obj.select_set(True)

            obj_list = t_new_objects.get(s_obj, None)
            if obj_list:

                for s_obj_name, _ in obj_list:

                    p_import_obj: bpy.types.Object = bpy.data.objects.get(s_obj_name)
                    p_import_obj.select_set(True)

                    if b_triangulate:
                        me: bpy.types.Mesh = p_import_obj.data
                        uv_layer = me.uv_layers.active
                        if not uv_layer:
                            uv_layer = me.uv_layers.new()

                        p_data = uv_layer.uv if ZenPolls.version_since_4_2_0 else uv_layer.data

                        t_tag = [False] * len(me.loops)

                        s_obj_tri_name = f"{s_obj_name}.001"
                        p_import_triangulated_obj = bpy.data.objects.get(s_obj_tri_name)
                        me_tri: bpy.types.Mesh = p_import_triangulated_obj.data
                        uv_layer_tri = me_tri.uv_layers.active
                        if uv_layer_tri:
                            t_indices_map = t_triangulate_map[s_obj_tri_name]
                            p_data_tri = uv_layer_tri.uv if ZenPolls.version_since_4_2_0 else uv_layer_tri.data

                            for idx, uv in enumerate(p_data_tri):
                                was_loop_idx = t_indices_map[idx]
                                if not t_tag[was_loop_idx]:
                                    t_tag[was_loop_idx] = True
                                    if ZenPolls.version_since_4_2_0:
                                        p_data[was_loop_idx].vector = uv.vector
                                    else:
                                        p_data[was_loop_idx].uv = uv.uv

                        bpy.data.objects.remove(p_import_triangulated_obj)
                        bpy.data.meshes.remove(me_tri)

                    if not self.use_texel_density:
                        me: bpy.types.Mesh = p_import_obj.data
                        uv_layer = me.uv_layers.active
                        if uv_layer:
                            if ZenPolls.version_since_4_2_0:
                                n_uv_data_count = len(uv_layer.uv)
                                if n_uv_data_count:
                                    uv_data = np.empty(n_uv_data_count * 2, dtype=np.double)
                                    uv_layer.uv.foreach_get("vector", uv_data)
                            else:
                                n_uv_data_count = len(uv_layer.data)
                                if n_uv_data_count:
                                    uv_data = np.empty(n_uv_data_count * 2, dtype=np.double)
                                    uv_layer.data.foreach_get("uv", uv_data)

                            if n_uv_data_count:
                                uv_coords = uv_data.reshape(n_uv_data_count, 2)
                                t_uv_ratio_max.append(uv_coords.max())

        d_uv_ratio = 0
        if t_uv_ratio_max:
            d_uv_ratio = max(t_uv_ratio_max)
            if d_uv_ratio:
                d_uv_ratio = 1 / d_uv_ratio

        p_act_obj = bpy.data.objects.get(s_act_obj_name)
        if context.view_layer.objects.active != p_act_obj:
            context.view_layer.objects.active = p_act_obj

        bpy.ops.object.mode_set(mode='EDIT')

        i_corrected_uvs = 0

        b_is_island_mode = True

        image_aspect_ratio = calc_uv_editor_image_aspect_ratio(context)

        for u_obj in stored_selection:
            p_obj = bpy.data.objects.get(u_obj.obj_name)

            bm_out = bmesh.from_edit_mesh(p_obj.data)
            bm_out.faces.ensure_lookup_table()
            uv_layer_out = verify_uv_layer(bm_out)

            used_faces = [False] * len(bm_out.faces)

            obj_list = t_new_objects.get(u_obj.obj_name, None)
            if obj_list:
                b_correct_self_intersecting = self.correct_self_intersecting
                if b_correct_self_intersecting:
                    loops = bm_out.calc_loop_triangles()

                for s_import_obj, indices in obj_list:
                    b_need_to_update = True

                    p_import_obj = bpy.data.objects.get(s_import_obj)

                    bm_in = bmesh.from_edit_mesh(p_import_obj.data)
                    bm_in.faces.ensure_lookup_table()

                    uv_layer_in = bm_in.loops.layers.uv.active
                    if uv_layer_in:
                        for in_idx, out_idx in enumerate(indices):
                            t_in_loops = {idx: loop for idx, loop in enumerate(bm_in.faces[in_idx].loops)}
                            t_out_loops = {idx: loop for idx, loop in enumerate(bm_out.faces[out_idx].loops)}

                            if len(t_in_loops) == len(t_out_loops):
                                for k, v in t_in_loops.items():
                                    if d_uv_ratio:
                                        t_out_loops[k][uv_layer_out].uv = v[uv_layer_in].uv * d_uv_ratio
                                    else:
                                        t_out_loops[k][uv_layer_out].uv = v[uv_layer_in].uv

                        if b_correct_self_intersecting:
                            triangles = defaultdict(list)

                            indices_set = set(indices)

                            for looptris in loops:
                                idx = looptris[0].face.index
                                if idx in indices_set:
                                    triangles[idx].append([loop[uv_layer_out].uv.to_tuple(5) for loop in looptris])

                            for i in indices:
                                p_face: bmesh.types.BMFace = bm_out.faces[i]

                                if used_faces[p_face.index]:
                                    continue

                                if has_overlapped_triangles_by_area(p_face, triangles[i], uv_layer_out):
                                    i_corrected_uvs += 1

                                    correct_self_intersecting_face(
                                        context, p_face, uv_layer_out, used_faces, image_aspect_ratio,
                                        b_is_island_mode, False)

                        if self.mark_seam_edges:
                            bm_out.edges.ensure_lookup_table()
                            p_edges = {e for i in indices for e in bm_out.faces[i].edges}

                            for e in p_edges:
                                e.seam = False

                            for i in get_uv_bound_edges_indexes((bm_out.faces[i] for i in indices), uv_layer_out):
                                bm_out.edges[i].seam = True

                    bpy.data.objects.remove(p_import_obj)
                    temp_me = bpy.data.meshes.get(s_import_obj)
                    if temp_me:
                        bpy.data.meshes.remove(temp_me)

            if b_need_to_update:
                bmesh.update_edit_mesh(p_obj.data, loop_triangles=False, destructive=False)

        if i_corrected_uvs:
            self.report({'INFO'}, f"Corrected UV Faces: {i_corrected_uvs}")

        if b_is_groupping:
            bpy.ops.mesh.reveal(select=False)
            if t_hidden_data:
                for s_obj_name, indices in t_hidden_data.items():
                    p_obj = bpy.data.objects.get(s_obj_name)
                    if p_obj:
                        bm = bmesh.from_edit_mesh(p_obj.data)
                        bm.faces.ensure_lookup_table()
                        for idx in indices:
                            bm.faces[idx].hide_set(True)
        SelectionProcessor.restore_selection_in_objects(context, stored_selection, False)

        return {'FINISHED'}


class ZUV_OT_AutoUVUnwrapInstall(bpy.types.Operator):
    bl_idname = "wm.zenuv_auto_uv_unwrap_install"
    bl_label = "Download Auto UV Unwrapper"
    bl_description = f"Download and install auto uv unwrapper from {MinistryOfFlatData.URL_MINISTRY_OF_FLAT}"

    @classmethod
    def description(cls, context: bpy.types.Context, properties: bpy.types.OperatorProperties):
        s_desc = cls.bl_description
        if not ZenPolls.internet_enabled():
            s_desc += "\n* Offline - Allow Online Access in System->Network Preferences"
        return s_desc

    @classmethod
    def poll(cls, context: bpy.types.Context):
        return ZenPolls.internet_enabled()

    def draw(self, context: bpy.types.Context):
        layout = self.layout

        box = layout.box()

        col = box.column(align=True)

        t_lines = [
            'You are about to download "UV Automated Unwrapper" from the Ministry of Flat.',
            'Please note that by pressing the "OK" button, you acknowledge that you have read and agree',
            'to the terms and conditions of the free license associated with this tool.',
            'We recommend reviewing these terms carefully to understand your rights and responsibilities.'
        ]

        for line in t_lines:
            row = col.row(align=True)
            row.separator(factor=2)
            row.label(text=line)

        col.separator()

        row = col.row(align=True)
        r_split = row.split(factor=0.5)
        r_split.separator()
        r_1 = r_split.row(align=True)
        r_1.alignment = 'CENTER'
        r_1.label(text=f"Author: {MinistryOfFlatData.MINISTRY_OF_FLAT_AUTHOR}")

        row = layout.row(align=True)
        row.label(text="To access the terms and conditions, please visit:")
        op = row.operator("wm.url_open", text=MinistryOfFlatData.MINISTRY_OF_FLAT_TEXT)
        op.url = MinistryOfFlatData.URL_MINISTRY_OF_FLAT

    def invoke(self, context: bpy.types.Context, event: bpy.types.Event):
        wm = context.window_manager
        if ZenPolls.version_since_4_2_0:
            return wm.invoke_props_dialog(self, width=540, cancel_default=True)
        else:
            return wm.invoke_props_dialog(self, width=540)

    def execute(self, context: bpy.types.Context):

        s_target_dir = ZuvPresets.force_full_preset_path(ZUV_OT_AutoUVUnwrap.LITERAL_PRESET_AUTO_UV_UNWRAP)
        if not s_target_dir:
            self.report({'ERROR'}, f"Can not create: {ZUV_OT_AutoUVUnwrap.LITERAL_PRESET_AUTO_UV_UNWRAP} - directory!")
            return {'CANCELLED'}

        ssl_context = ssl._create_unverified_context()
        with urllib.request.urlopen("https://www.quelsolaar.com/MinistryOfFlat_Release.zip", context=ssl_context) as zipresp:
            with ZipFile(BytesIO(zipresp.read())) as zfile:
                zfile.extractall(s_target_dir)

        return {'FINISHED'}


class WM_OT_zenuv_auto_unwrap_preset_add(AddPresetBase, bpy.types.Operator):
    """Add or remove an Operator Preset"""
    bl_idname = "wm.zenuv_auto_unwrap_operator_preset_add"
    bl_label = "Operator Preset"
    preset_menu = "WM_MT_zenuv_auto_unwrap_presets"

    operator: bpy.props.StringProperty(
        name="Operator",
        maxlen=64,
        options={'HIDDEN', 'SKIP_SAVE'},
    )

    preset_defines = [
        f"op = bpy.context.window_manager.operator_properties_last('{ZUV_OT_AutoUVUnwrap.bl_idname}')",
    ]

    preset_subdir = AddPresetOperator.preset_subdir

    preset_values = AddPresetOperator.preset_values

    operator_path = AddPresetOperator.operator_path


# NOTE: we need to override to have individual 'bl_label'
class WM_MT_zenuv_auto_unwrap_presets(WM_MT_zenuv_operator_presets):
    pass


class ZUV_PT_AutoUVUnwrapProperties(bpy.types.Panel):
    bl_label = "Auto UV Unwrap Properties"
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = "__POPUP__"
    bl_ui_units_x = 16

    def draw(self, context: bpy.types.Context):
        layout = self.layout

        wm = context.window_manager
        op_last = wm.operator_properties_last(ZUV_OT_AutoUVUnwrap.bl_idname)
        if op_last:
            row = layout.row(align=True)
            row.context_pointer_set("active_operator_properties", op_last)
            row.menu("WM_MT_zenuv_auto_unwrap_presets", text=WM_MT_zenuv_auto_unwrap_presets.bl_label)

            op = row.operator(WM_OT_zenuv_auto_unwrap_preset_add.bl_idname, text="", icon="ADD")
            op.operator = ZUV_OT_AutoUVUnwrap.bl_rna.identifier
            op.remove_active = False

            op = row.operator(WM_OT_zenuv_auto_unwrap_preset_add.bl_idname, text="", icon="REMOVE")
            op.operator = ZUV_OT_AutoUVUnwrap.bl_rna.identifier
            op.remove_active = True

            ZUV_OT_AutoUVUnwrap.do_draw(op_last, layout, context)


def draw_auto_unwrap(layout: bpy.types.UILayout, context: bpy.types.Context):
    row = layout.row(align=True)
    row.operator(ZUV_OT_AutoUVUnwrap.bl_idname)
    row.popover(panel="ZUV_PT_AutoUVUnwrapProperties", text="", icon="PREFERENCES")


classes = (
    ZUV_OT_AutoUVUnwrap,
    ZUV_OT_AutoUVUnwrapInstall,

    WM_OT_zenuv_auto_unwrap_preset_add,
    WM_MT_zenuv_auto_unwrap_presets,

    ZUV_PT_AutoUVUnwrapProperties
)
