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

# Copyright 2023-2025, Valeriy Yatsenko lightbio@gmail.com


import bpy
import bmesh
import math

from .select_utils import MeshAnalyse

from ...utils.generic import ResortObjects, bpy_select_by_context
from ...utils.iter_utils import IterUtils, IterUtils2
from ...utils.blender_zen_utils import is_sync_off


class ZUV_OT_SelectCylinderCap(bpy.types.Operator):
    bl_idname = "mesh.zenuv_select_cylinder_cap"
    bl_label = "Select Cylinder Cap"
    bl_zen_short_name = "Cylinder Cap"
    bl_description = (
        "Select the caps of cylinder meshes.\n"
        "Selects faces or boundary edges depending on mesh selection mode"
    )
    bl_options = {'REGISTER', 'UNDO'}

    clear_selection: bpy.props.BoolProperty(
        name='Clear Selection',
        description='Clears the initial selection before applying the operation',
        default=True)

    cap_type: bpy.props.EnumProperty(
        name="Cap Type",
        description="Select the type of cylinder cap to detect",
        items=[
            ('FLAT', "Flat", "A flat cap consisting of different types of polygons (n-gons, triangles, quads)"),
            ('STAR', "Star", "Cover has a central vertex with edges radiating outwards"),
            ('DONUT', "Donut", "Cover has a hole in the center, like a donut")
        ],
        default={'FLAT'},
        options={'ENUM_FLAG'}
    )

    edges_tolerance: bpy.props.FloatProperty(
        name="Edges Tolerance",
        description="Allowed difference between face opposite edges length",
        default=3.0,
        min=0.01,
        max=100,
        subtype='PERCENTAGE')

    donut_angle_tolerance: bpy.props.FloatProperty(
        name="Donut Angle Tolerance",
        description="Allowed angle between adjacent faces",
        default=0.052,
        min=0,
        max=math.pi,
        subtype='ANGLE')  # RADIANS

    use_area_check: bpy.props.BoolProperty(
        name="Check Area",
        description="Also compare face areas",
        default=True)

    area_tolerance: bpy.props.FloatProperty(
        name="Area Tolerance",
        description="Allowed difference between face areas",
        default=5.0,
        min=0.01,
        max=100,
        subtype='PERCENTAGE')

    flat_angle_tolerance: bpy.props.FloatProperty(
        name="Flat Angle Tolerance",
        description="Allowed angle between adjacent faces",
        default=0.268,
        min=0,
        max=math.pi,
        subtype='ANGLE')  # RADIANS

    star_angle_tolerance: bpy.props.FloatProperty(
        name="Star Angle Tolerance",
        description="Allowed angle between adjacent faces",
        default=0.268,
        min=0,
        max=math.pi,
        subtype='ANGLE')  # RADIANS

    @classmethod
    def description(cls, context: bpy.types.Context, properties: bpy.types.OperatorProperties):
        s_desc = cls.bl_description
        if is_sync_off(context):
            s_desc += ".\nRequires UV Sync Selection - On"
        return s_desc

    @classmethod
    def poll(cls, context):
        """ Validate context """
        if is_sync_off(context):
            return False
        active_object = context.active_object
        return active_object is not None \
            and active_object.type == 'MESH' \
            and context.mode == 'EDIT_MESH'

    def draw(self, context):
        layout = self.layout

        # Selection
        box = layout.box()
        box.use_property_split = True
        box.prop(self, "clear_selection")

        # Cap Type
        row = layout.row()
        row.prop(self, "cap_type")

        box = layout.box()
        box.use_property_split = True
        if "FLAT" in self.cap_type:
            box.prop(self, "flat_angle_tolerance")
        if "STAR" in self.cap_type:
            box.prop(self, "star_angle_tolerance")
        if "DONUT" in self.cap_type:
            box.prop(self, "edges_tolerance")
            box.prop(self, "donut_angle_tolerance")
            box.prop(self, "use_area_check")
            row = box.row()
            row.enabled = self.use_area_check
            row.prop(self, "area_tolerance")

    def execute(self, context):
        objs = ResortObjects.resort_by_type_mesh_in_edit_mode_and_sel(context)
        if not objs:
            self.report({'WARNING'}, "No objects selected.")
            return {'CANCELLED'}

        if self.clear_selection:
            bpy_select_by_context(context, action='DESELECT')

        for obj, bm, _ in IterUtils.iter_objs_with_bmesh_uv(objs, context):
            if 'FLAT' in self.cap_type:
                p_groups = MeshAnalyse.collect_cylindrical_faces(bm, bm.faces)

                if not p_groups:
                    continue
                p_groups = MeshAnalyse.merge_groups_by_edges(bm, p_groups, angle_tolerance=0.611)

                groups = []
                for p_group in p_groups:
                    if len(p_group) <= 4:
                        continue

                    border_edges = [e.index for i in p_group for e in bm.faces[i].edges if any(lf.index not in p_group for lf in e.link_faces)]

                    faces = {f.index for e in border_edges for f in bm.edges[e].link_faces if f.index not in p_group and bm.edges[e].calc_face_angle_signed(0) > 0}

                    if not faces:
                        continue

                    p_full_group = MeshAnalyse.collect_adjacent_faces_simple(bm, list(faces), self.flat_angle_tolerance, min_group_size=0)

                    if not p_full_group:
                        continue

                    if MeshAnalyse.get_faceloop_type(bm, p_full_group[0]) in {'INVALID'}:
                        groups.extend(p_full_group)

                MeshAnalyse.select_groups(bm, groups)

            if 'STAR' in self.cap_type:
                verts = [v for v in bm.verts if not v.hide and len(v.link_faces) >= 5]
                if not verts:
                    continue

                p_groups = []
                for v in verts:
                    group = [f.index for f in v.link_faces if MeshAnalyse.faces_same_area(v.link_faces)]
                    if group:
                        p_groups.append(group)

                groups = []
                for g in p_groups:
                    groups.extend(MeshAnalyse.collect_adjacent_faces_simple(bm, g, self.star_angle_tolerance))

                MeshAnalyse.select_groups(bm, groups)

            if 'DONUT' in self.cap_type:
                groups = MeshAnalyse.collect_adjacent_faces(
                    bm, bm.faces,
                    self.use_area_check,
                    self.edges_tolerance,
                    self.area_tolerance,
                    self.donut_angle_tolerance)

                groups = MeshAnalyse.merge_groups_by_normals(bm, groups)

                MeshAnalyse.select_groups(bm, groups)

            bm.select_flush_mode()

            bmesh.update_edit_mesh(obj.data, loop_triangles=False, destructive=False)

        return {'FINISHED'}


class ZUV_OT_SelectCylinderFaces(bpy.types.Operator):
    bl_idname = "mesh.zenuv_select_cylinder_faces"
    bl_label = "Select Cylinder Faces"
    bl_zen_short_name = "Cylinder Faces"
    bl_description = (
        "Select connected quad faces that form a cylindrical surface.\n"
        "Useful for detecting cylindrical geometry in meshes.\n"
        "Selects faces or boundary edges depending on mesh selection mode"
    )
    bl_options = {'REGISTER', 'UNDO'}

    clear_selection: bpy.props.BoolProperty(
        name='Clear Selection',
        description='Clears the initial selection before applying the operation',
        default=True)

    edges_tolerance: bpy.props.FloatProperty(
        name="Edges Tolerance",
        description="Allowed difference between face opposite edges length",
        default=3.0,
        min=0.01,
        max=100,
        subtype='PERCENTAGE')

    angle_tolerance: bpy.props.FloatProperty(
        name="Angle Tolerance",
        description="Allowed angle between adjacent faces",
        default=0.877,
        min=0.0,
        max=math.pi,
        subtype='ANGLE')  # RADIANS

    use_area_check: bpy.props.BoolProperty(
        name="Check Area",
        description="Also compare face areas",
        default=True)

    area_tolerance: bpy.props.FloatProperty(
        name="Area Tolerance",
        description="Allowed difference between face areas",
        default=15.0,
        min=0.01,
        max=100,
        subtype='PERCENTAGE')

    @classmethod
    def description(cls, context: bpy.types.Context, properties: bpy.types.OperatorProperties):
        s_desc = cls.bl_description
        if is_sync_off(context):
            s_desc += ".\nRequires UV Sync Selection - On"
        return s_desc

    def draw(self, context):
        layout = self.layout
        box = layout.box()
        box.use_property_split = True
        box.prop(self, 'clear_selection')

        box = layout.box()
        box.use_property_split = True
        box.prop(self, 'edges_tolerance')
        box.prop(self, 'angle_tolerance')
        box.prop(self, 'use_area_check')
        row = box.row()
        row.enabled = self.use_area_check
        row.prop(self, 'area_tolerance')

    @classmethod
    def poll(cls, context):
        """ Validate context """
        if is_sync_off(context):
            return False
        active_object = context.active_object
        return active_object is not None \
            and active_object.type == 'MESH' \
            and context.mode == 'EDIT_MESH'

    def execute(self, context):
        objs = ResortObjects.resort_by_type_mesh_in_edit_mode_and_sel(context)
        if not objs:
            self.report({'WARNING'}, "No objects selected.")
            return {'CANCELLED'}

        if self.clear_selection:
            bpy_select_by_context(context, action='DESELECT')

        for obj, bm in IterUtils2.iter_objs_with_bmesh(objs):

            groups = MeshAnalyse.collect_cylindrical_faces(
                bm,
                bm.faces,
                self.use_area_check,
                self.edges_tolerance,
                self.area_tolerance,
                self.angle_tolerance)

            if not groups:
                continue

            groups = MeshAnalyse.merge_groups_by_edges(bm, groups, angle_tolerance=0.611)

            for group in groups:
                if len(group) <= 4:
                    continue
                for f_idx in group:
                    bm.faces[f_idx].select = True

        bmesh.update_edit_mesh(obj.data, loop_triangles=False, destructive=False)

        return {'FINISHED'}


classes = (
    ZUV_OT_SelectCylinderFaces,
    ZUV_OT_SelectCylinderCap
    )


def register():
    for cl in classes:
        bpy.utils.register_class(cl)


def unregister():
    for cl in classes:
        bpy.utils.unregister_class(cl)


if __name__ == "__main__":
    pass
