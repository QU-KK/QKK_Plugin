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

# Copyright 2023, Valeriy Yatsenko


import bpy
import numpy as np

from ZenUV.utils.register_util import RegisterUtils

from ZenUV.utils.generic import (
    resort_objects_by_selection,
    resort_by_type_mesh_in_edit_mode_and_sel,
)


def get_image_size(context):
    if context.scene.zen_uv.td_props.td_im_size_presets == 'Custom':
        return [context.scene.zen_uv.td_props.TD_TextureSizeX, context.scene.zen_uv.td_props.TD_TextureSizeY]
    else:
        return [context.scene.zen_uv.td_props.TD_TextureSizeX, context.scene.zen_uv.td_props.TD_TextureSizeX]


def get_face_areas(mesh):
    face_areas = np.empty(len(mesh.polygons), dtype=np.double)  # Slower but more accurate
    mesh.polygons.foreach_get("area", face_areas)
    return face_areas


def calculate_uv_areas(mesh):
    uv_layer = mesh.uv_layers.active.data

    if uv_layer is None:
        return 0  # no UV layer, so area is zero

    num_loops = len(mesh.loops)
    uv_data = np.empty(num_loops * 2, dtype=np.double)
    uv_layer.foreach_get("uv", uv_data)
    uv_coords = uv_data.reshape(num_loops, 2)
    num_faces = len(mesh.polygons)
    loop_totals = np.empty(num_faces, dtype=np.int32)
    loop_starts = np.empty(num_faces, dtype=np.int32)
    mesh.polygons.foreach_get("loop_total", loop_totals)
    mesh.polygons.foreach_get("loop_start", loop_starts)
    indices = np.arange(num_loops)
    next_indices = indices + 1
    boundaries = loop_starts + loop_totals - 1
    next_indices[boundaries] = loop_starts
    diffs = uv_coords[:, 0] * uv_coords[next_indices, 1] - uv_coords[:, 1] * uv_coords[next_indices, 0]
    areas = np.add.reduceat(diffs, loop_starts, axis=0)
    return 0.5 * np.abs(areas)


def calculate_texel_density(context, obj, td_units):
    mesh = obj.data
    image_size = get_image_size(context)
    bl_unit_scale = context.scene.unit_settings.scale_length

    face_areas_mult = (bl_unit_scale / float(td_units)) ** 2
    mult_table = np.array([int(image_size[0]) * int(image_size[1])], dtype=np.int32)

    # NOTE: It's impossible to use user materials because it can be messy.
    # num_slots = len(obj.material_slots)
    # if num_slots == 0:
    #     mult_table = np.array([int(context.scene.rtd.global_x) * int(context.scene.rtd.global_y)], dtype=np.int32)
    # else:
    #     mult_table = np.ones(num_slots, dtype=np.int32)
    #     for idx in range(num_slots):
    #         material = obj.material_slots[idx].material
    #         if material and not material.rtd.use_global:
    #             texture_width = material.rtd.tex_x
    #             texture_height = material.rtd.tex_y
    #         else:
    #             texture_width = context.scene.rtd.global_x
    #             texture_height = context.scene.rtd.global_y
    #         mult_table[idx] = int(texture_width) * int(texture_height)

    uv_areas = calculate_uv_areas(mesh)
    face_areas = get_face_areas(mesh)
    material_indices = np.empty(len(mesh.polygons), dtype=np.int32)
    mesh.polygons.foreach_get("material_index", material_indices)
    uv_mult_array = mult_table[material_indices.clip(0, len(mult_table) - 1)]
    texel_densities = np.sqrt((uv_areas * uv_mult_array) / (face_areas * face_areas_mult))
    return texel_densities, face_areas


class ZUV_OT_GetTexelDensityWeighted(bpy.types.Operator):
    bl_idname = "uv.zenuv_get_weighted_texel_density"
    bl_label = "Get TD Weighted"
    bl_description = ""
    bl_options = {'REGISTER', 'UNDO'}

    units: bpy.props.EnumProperty(
        name="Global Unit",
        description="Global Unit",
        items=[
            ('.001', 'px/mm', ''),
            ('.01', 'px/cm', ''),
            ('1', 'px/m', ''),
            ('.0254', 'px/in', ''),
            ('.3048', 'px/ft', ''),
            ('.9144', 'px/yd', ''),
        ],
        default=".01"
    )

    @classmethod
    def poll(cls, context):
        """ Validate context """
        active_object = context.active_object
        return active_object is not None and active_object.type == 'MESH'

    def execute(self, context):
        objs = resort_by_type_mesh_in_edit_mode_and_sel(context)
        if not objs:
            self.report({'INFO'}, "There are no selected objects.")
            return {'CANCELLED'}

        if context.mode == 'EDIT_MESH':
            objs = resort_objects_by_selection(context, objs)
            if not objs:
                self.report({'WARNING'}, "Zen UV: Select something.")
                return {'CANCELLED'}

        for obj in objs:
            if not obj.data.uv_layers:
                self.report({'WARNING'}, f"Object {obj.name} has no UV data. Calculation cancelled")
                return {'CANCELLED'}

        min_vals = []
        max_vals = []
        weighted_sum: float = 0
        total_area_sum: float = 0
        face_count: int = 0
        is_selected_only = True

        for obj in objs:
            td_array, face_areas = calculate_texel_density(context, obj, self.units)
            if td_array.size == 0 or face_areas.size == 0:
                continue

            if is_selected_only:
                mask = np.array([poly.select for poly in obj.data.polygons])
                face_count += mask.sum()
                if mask.sum() == 0:
                    continue
                td_sel = td_array[mask]
                areas_sel = face_areas[mask]
            else:
                td_sel = td_array
                areas_sel = face_areas

            local_min = float(np.min(td_sel))
            local_max = float(np.max(td_sel))
            local_weighted = float(np.sum(td_sel * areas_sel) / np.sum(areas_sel))
            local_area = float(np.sum(areas_sel))

            min_vals.append(local_min)
            max_vals.append(local_max)
            weighted_sum += local_weighted * local_area
            total_area_sum += local_area

        overall_min = min(min_vals) if min_vals else 0.0
        overall_max = max(max_vals) if max_vals else 0.0
        overall_weighted = weighted_sum / total_area_sum if total_area_sum else 0.0
        object_count = len(objs)
        # face_count = face_count
        print(overall_min, overall_max, overall_weighted, object_count, face_count)

        return {'FINISHED'}


classes = (
    ZUV_OT_GetTexelDensityWeighted,
)


def register():
    RegisterUtils.register(classes)


def unregister():
    RegisterUtils.unregister(classes)
