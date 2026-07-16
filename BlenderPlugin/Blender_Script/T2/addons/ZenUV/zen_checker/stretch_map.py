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

""" Zen UV Stretch Map """

import bpy
import bmesh
import math
from mathutils import Vector, Color
from ZenUV.utils.register_util import RegisterUtils
from ZenUV.utils.generic import resort_by_type_mesh
from ZenUV.utils.generic import (
    get_mesh_data,
    select_islands,
    verify_uv_layer
)
from ZenUV.zen_checker.zen_checker_labels import ZCheckerLabels as label
from ZenUV.ui.labels import ZuvLabels
from ZenUV.ui.pie import ZsPieFactory
from ZenUV.utils.blender_zen_utils import ZenPolls
# from ZenUV.utils.vlog import Log


class StretchMap():
    uv_layer = None
    colors = []
    baseColor = Color((0.0, 0.0, 1.0))
    alpha = 0.6

    def __init__(self, context):
        self.context = context
        self.objs = resort_by_type_mesh(context)

    def get_stretched_faces_indices(self, bm: bmesh.types. BMesh, face_mask: list, factor_list: list, n_gons_only: bool):
        p_select = []
        if n_gons_only:
            for f in bm.faces:
                p_select.append(face_mask[f.index] and len(f.verts) > 4 and any(abs(1 - factor) > self.threshold for factor in factor_list[f.index]))
        else:
            for f in bm.faces:
                p_select.append(face_mask[f.index] and any(abs(1 - factor) > self.threshold for factor in factor_list[f.index]))
        return p_select

    def signed_angle_3d(self, v1: Vector, v2: Vector, normal):
        angle = v1.angle(v2, 0)
        if math.isclose(angle, math.pi, rel_tol=1e-6):
            return angle
        cross = v1.cross(v2)
        sign = 1 if cross.dot(normal) >= 0 else -1
        return angle * sign

    def signed_angle_2d(self, v1: Vector, v2: Vector):
        """ Return signed angle """
        angle = v1.angle(v2, 0)
        if math.isclose(angle, math.pi, rel_tol=1e-6):
            return angle
        cross = v1.x * v2.y - v1.y * v2.x
        sign = 1 if cross > 0 else -1
        return angle * sign

    def get_dir_vector(self, pos_0, pos_1):
        """ Return direction Vector from 2 Vectors """
        return Vector(pos_1 - pos_0)

    def fill_colors(self, bm):
        self.colors.clear()
        self.uv_layer = verify_uv_layer(bm)
        angles_map = [self.calc_distortion_factor_by_verts(vertex) for vertex in bm.verts]
        for angles in angles_map:
            self.colors.append((0.2, self.baseColor.g + angles, self.baseColor.b - angles, self.alpha))

    def calc_distortion_factor_by_verts(self, vertex):
        """ Returns the distortion factor for a given vertex"""
        distortion = 0
        loops = vertex.link_loops
        for loop in loops:
            mesh_angle = loop.calc_angle()
            vec_0 = self.get_dir_vector(loop[self.uv_layer].uv, loop.link_loop_next[self.uv_layer].uv)
            vec_1 = self.get_dir_vector(loop[self.uv_layer].uv, loop.link_loop_prev[self.uv_layer].uv)
            uv_angle = vec_0.angle(vec_1, 0)
            distortion += abs(mesh_angle - uv_angle)
        return distortion

    def get_stretched_verts(self):
        out = dict()
        for obj in self.objs:
            bm, obj = self.get_bmesh(obj.name)
            self.uv_layer = verify_uv_layer(bm)
            out.update({obj: [self.calc_distortion_factor_by_verts(vertex) for vertex in bm.verts]})
            bm.free()
        return out

    def calc_distortion_factor_by_faces(self, bm):
        """ Returns the distortion factor for a given vertex"""
        distortion = []
        for face in bm.faces:
            if face.hide:
                p_list = [None] * len(face.loops)
            else:
                p_list = []
                for loop in face.loops:
                    vm0 = self.get_dir_vector(loop.vert.co, loop.link_loop_next.vert.co)
                    vm1 = self.get_dir_vector(loop.vert.co, loop.link_loop_prev.vert.co)
                    mesh_angle = self.signed_angle_3d(vm0, vm1, face.normal)
                    vec_0 = self.get_dir_vector(loop[self.uv_layer].uv, loop.link_loop_next[self.uv_layer].uv)
                    vec_1 = self.get_dir_vector(loop[self.uv_layer].uv, loop.link_loop_prev[self.uv_layer].uv)
                    uv_angle = self.signed_angle_2d(vec_0, vec_1)

                    if mesh_angle * uv_angle < 0:
                        p_list.append(100)
                    else:
                        p_list.append(mesh_angle / uv_angle if uv_angle != 0 else 100)
            distortion.append(p_list)
        return distortion

    def collect_distortion_data_by_faces(self):
        out = dict()
        for obj in self.objs:
            bm, obj = self.get_bmesh(obj.name)
            self.uv_layer = verify_uv_layer(bm)
            out.update({obj: self.calc_distortion_factor_by_faces(bm)})
            bm.free()
        return out

    def create_osl_buffer(self):
        out_dict = dict()

        for obj in self.objs:
            bm, obj = self.get_bmesh(obj.name)
            self.fill_colors(bm)
            verts = [(obj.matrix_world @ v.co) for v in bm.verts]
            face_tri_indices = [[loop.vert.index for loop in looptris] for looptris in bm.calc_loop_triangles() if not looptris[0].face.hide]
            out_dict.update({obj.name: {"verts": verts}})
            out_dict[obj.name].update({"faces": face_tri_indices})
            out_dict[obj.name].update({"colors": self.colors.copy()})
            bm.free()
        return out_dict

    def get_bmesh(self, obj_name):
        obj = self.context.scene.objects[obj_name]
        bm = bmesh.from_edit_mesh(obj.data).copy()
        bm.faces.ensure_lookup_table()
        return bm, obj


class ZUV_OT_SelectStretchedIslands(bpy.types.Operator):
    bl_idname = "uv.zenuv_select_stretched_islands"
    bl_label = label.OT_STRETCH_SELECT_LABEL
    bl_description = label.OT_STRETCH_SELECT_DESC
    bl_options = {'REGISTER', 'UNDO'}

    Filter: bpy.props.FloatProperty(
        name=label.PROP_STRETCHED_FILTER_LABEL,
        description=label.PROP_STRETCHED_FILTER_DESC,
        min=0.1,
        default=0.1,
        precision=2,
    )

    def draw(self, context):
        self.layout.prop(self, "Filter")

    def invoke(self, context, event):
        self.objs = resort_by_type_mesh(context)
        if not self.objs:
            return {"CANCELLED"}
        sm = StretchMap(context)
        self.data = sm.get_stretched_verts()
        return self.execute(context)

    def execute(self, context):
        context.tool_settings.mesh_select_mode = [True, False, False]
        for obj, fac in self.data.items():
            me, bm = get_mesh_data(obj)
            bm.verts.ensure_lookup_table()
            for i in range(len(fac)):
                bm.verts[i].select = fac[i] > self.Filter
            bmesh.update_edit_mesh(me, loop_triangles=False)
        select_islands(context, self.objs)
        context.tool_settings.mesh_select_mode = [False, False, True]

        return {'FINISHED'}


class ZUV_OT_SelectStretchedFaces(bpy.types.Operator):
    bl_idname = "uv.zenuv_select_stretched_faces"
    bl_label = "Select Stretched Faces"
    bl_zen_short_name = "Stretched Faces"
    bl_description = "Selects faces with stretched UV coordinates"
    bl_options = {'REGISTER', 'UNDO'}

    influence: bpy.props.EnumProperty(
        name="Influence",
        description="Defines the selection target",
        items=[
            ("FACE", "Face", "Selects individual stretched faces"),
            ("ISLAND", "Island", "Selects entire islands containing stretched faces"),
            ],
        default='FACE')

    clear_selection: bpy.props.BoolProperty(
        name='Clear Selection',
        description='Clears the initial selection before applying the operation',
        default=True)

    threshold: bpy.props.FloatProperty(
        name="Threshold",
        description="Defines the minimum stretch factor required for a face to be selected",
        min=0.0,
        max=1.0,
        default=0.05)

    n_gons_only: bpy.props.BoolProperty(
        name="N-gons Only",
        description="Selects only n-gons (faces with more than four edges)",
        default=False)

    def invoke(self, context, event):
        self.objs = resort_by_type_mesh(context)
        if not self.objs:
            self.report({'WARNING'}, "Zen UV: Select something.")
            return {"CANCELLED"}
        sm = StretchMap(context)
        self.data = sm.collect_distortion_data_by_faces()
        return self.execute(context)

    def execute(self, context):
        b_is_image_editor = context.space_data.type == 'IMAGE_EDITOR'
        b_is_not_sync = b_is_image_editor and not context.scene.tool_settings.use_uv_select_sync
        if b_is_not_sync:
            bpy.ops.uv.select_mode(type='FACE')
        else:
            bpy.ops.mesh.select_mode(type='FACE')

        masks = dict()
        for obj in self.data.keys():
            bm = bmesh.from_edit_mesh(obj.data)
            uv_layer = verify_uv_layer(bm)
            bm.faces.ensure_lookup_table()
            if b_is_not_sync:
                masks.update({obj.name: [f.select and not f.hide for f in bm.faces]})
            else:
                masks.update({obj.name: [not f.hide for f in bm.faces]})

            if not any(any(value) for value in masks.values()):
                self.report({'WARNING'}, "Zen UV: There is no faces for calculation")
                return {'CANCELLED'}

        if self.clear_selection:
            from ZenUV.utils.generic import bpy_deselect_by_context
            bpy_deselect_by_context(context)

        for obj, factor_list in self.data.items():
            bm = bmesh.from_edit_mesh(obj.data)
            uv_layer = verify_uv_layer(bm)
            bm.faces.ensure_lookup_table()
            mask = masks[obj.name]

            p_select = []
            if self.n_gons_only:
                for f in bm.faces:
                    p_select.append(mask[f.index] and len(f.verts) > 4 and any(abs(1 - factor) > self.threshold for factor in factor_list[f.index]))
            else:
                for f in bm.faces:
                    p_select.append(mask[f.index] and any(abs(1 - factor) > self.threshold for factor in factor_list[f.index]))

            if b_is_not_sync:
                if ZenPolls.version_since_3_2_0:
                    for f in bm.faces:
                        if p_select[f.index]:
                            for loop in f.loops:
                                loop[uv_layer].select = True
                                loop[uv_layer].select_edge = True
                else:
                    for f in bm.faces:
                        if p_select[f.index]:
                            for loop in f.loops:
                                loop[uv_layer].select = True
            else:
                for f in bm.faces:
                    f.select = p_select[f.index]

            bm.select_flush_mode()
            bmesh.update_edit_mesh(obj.data, loop_triangles=False, destructive=False)

            if self.influence == 'ISLAND':
                select_islands(context, self.objs)

        return {'FINISHED'}


class ZUV_OT_StretchMapSwitch(bpy.types.Operator):
    bl_idname = "uv.switch_stretch_map"
    bl_label = ZuvLabels.OT_STRETCH_DISPLAY_LABEL
    bl_description = ZuvLabels.OT_STRETCH_DISPLAY_DESC
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(self, context):
        return context.area.type in {'VIEW_3D', 'IMAGE_EDITOR'}

    def execute(self, context):

        ZsPieFactory.mark_pie_cancelled()

        if context.area.type == 'VIEW_3D':
            p_scene = context.scene
            p_scene.zen_uv.ui.draw_mode_3D = 'STRETCHED' if p_scene.zen_uv.ui.draw_mode_3D != 'STRETCHED' else 'NONE'
        elif context.area.type == 'IMAGE_EDITOR':
            context.space_data.uv_editor.show_stretch = not context.space_data.uv_editor.show_stretch
        else:
            return {'CANCELLED'}

        return {'FINISHED'}


classes = [
    ZUV_OT_StretchMapSwitch,
    ZUV_OT_SelectStretchedIslands,
    ZUV_OT_SelectStretchedFaces
]


def register():
    RegisterUtils.register(classes)


def unregister():
    RegisterUtils.unregister(classes)


if __name__ == "__main__":
    pass
