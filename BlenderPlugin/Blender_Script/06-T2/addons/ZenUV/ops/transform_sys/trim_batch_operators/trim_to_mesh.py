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
import bmesh
from math import pi, cos, sin
from mathutils import Matrix, Vector

from ZenUV.utils.register_util import RegisterUtils
from ZenUV.ui.tool.view3d_base import ZuvGizmoBase
from ZenUV.utils.blender_zen_utils import ZenPolls
from ZenUV.utils.transform import ZenLocRotScale
from ZenUV.utils.generic import view3d_find
from ZenUV.utils.vlog import Log
from ZenUV.ops.trimsheets.trimsheet_utils import ZuvTrimsheetUtils
from ZenUV.utils.bounding_box import BoundingBox2d
from ZenUV.utils.constants import UV_AREA_BBOX
from ZenUV.ops.transform_sys.transform_utils.tr_utils import TransformSysOpsProps


class ZUV_OT_TrimToMesh(bpy.types.Operator):
    bl_idname = "uv.zenuv_trim_to_mesh"
    bl_label = 'Trim To Mesh'
    bl_description = 'Create Trim representation in Mesh as single face'
    bl_options = {'REGISTER', 'UNDO'}

    orientation: bpy.props.EnumProperty(
        name="Orientation",
        description="Orientation of the Face",
        items=[
            ("TEXTURE", "Texture", ""),
            ("FACE", "Active Selection", ""),
            ("VIEW", "View", ""),
            ("NORMAL_VEC", "Active Selection Normal", ""),
            ],
        default="NORMAL_VEC"
    )
    offset: bpy.props.FloatProperty(
        name='Trim Offset',
        description='Offset along the Z-axis',
        min=-1.0,
        max=1.0,
        default=0.0,
        precision=3
    )
    numverts: bpy.props.IntProperty(
        name='Verts Count',
        description='The number of vertices of the Trim representation',
        min=4,
        max=24,
        default=4
    )
    track_normal: bpy.props.EnumProperty(
        name="Orientation",
        description="Orientation of the Face",
        items=[
            ("X", "Along", ""),
            ("Z", "Across", ""),
            ],
        default="X"
    )
    trim_pivot: TransformSysOpsProps.get_island_pivot_prop(default=7)
    turn: bpy.props.BoolProperty(name='Turn', description='Rotate Trim representation by 180 along a Z axis', default=False)

    @classmethod
    def poll(cls, context):
        """ Validate context """
        active_object = context.active_object
        return active_object is not None and active_object.type == 'MESH' and context.mode == 'EDIT_MESH'

    def draw(self, context: bpy.types.Context):
        layout = self.layout
        layout.prop(self, 'orientation')
        box = layout.box()
        box.prop(self, 'numverts')
        box.prop(self, 'offset')
        if self.orientation == 'NORMAL_VEC':
            row = layout.row()
            row.prop(self, 'track_normal', expand=True)
            row.prop(self, 'turn', expand=True)

        box = layout.box()
        row = box.row(align=True)
        row.prop(self, "trim_pivot")

    def execute(self, context):
        obj = context.active_object
        if not obj:
            self.report({'INFO'}, "There are no active object")
            return {'CANCELLED'}

        trim = ZuvTrimsheetUtils.getActiveTrim(context)
        if trim is not None:
            tr_bbox = BoundingBox2d(points=(trim.left_bottom, trim.top_right))
        else:
            tr_bbox = UV_AREA_BBOX()

        meshMtx = ZuvGizmoBase.getActiveMeshMtx(context, obj)

        bm = bmesh.from_edit_mesh(obj.data)
        bm.faces.ensure_lookup_table()
        bm.verts.ensure_lookup_table()
        p_face = bm.faces.active

        uv_layer = bm.loops.layers.uv.active
        if p_face is not None and uv_layer is not None:
            bpy.ops.uv.select_all(action='DESELECT')
            if context.scene.tool_settings.use_uv_select_sync:
                bpy.ops.mesh.select_all(action='DESELECT')
            p_face_cen = p_face.calc_center_median()

            if self.orientation == 'TEXTURE':
                R = meshMtx.rotation
            elif self.orientation == 'FACE':
                q = p_face.normal.to_track_quat('Z', 'Y')
                R = ZenLocRotScale(None, q, None)
            elif self.orientation == 'VIEW':
                r3d, rv3d, v3d = view3d_find(context)
                if rv3d is None:
                    self.report({'WARNING'}, "It only works in 3D Viewport")
                    return {'FINISHED'}
                view_quat = rv3d.view_rotation
                R = ZenLocRotScale(None, view_quat, None)
            elif self.orientation == 'NORMAL_VEC':
                q = p_face.normal.to_track_quat('Y', self.track_normal)
                R = ZenLocRotScale(None, q, None)

            if self.turn:
                R @= Matrix.Rotation(pi, 4, (0.0, 1.0, 0.0))

            direct_offset = Matrix.Translation((p_face_cen.x, p_face_cen.y, p_face_cen.z + self.offset)) @ R

            if self.numverts == 4:
                trim_pivot = tr_bbox.get_as_dict()[self.trim_pivot].to_3d()
                reset_matrix = Matrix.Translation((Vector() - trim_pivot))
                uv_co = [c for c in reversed(tr_bbox.corners[:4])]
                coo = [direct_offset @ (meshMtx.scale @ (reset_matrix @ c.to_3d())) for c in uv_co]
            else:
                diameter = tr_bbox.get_shortest_axis_len()
                template_co = self.get_circle_3d_co(num_verts=self.numverts, diameter=diameter)
                circle_bbox = BoundingBox2d(points=[c.to_2d() for c in template_co])
                trim_pivot = circle_bbox.get_as_dict()[self.trim_pivot].to_3d()
                reset_matrix = Matrix.Translation((Vector() - trim_pivot))
                uv_offset_m = Matrix.Translation(tr_bbox.get_as_dict()['cen'].to_3d())
                uv_co = [(uv_offset_m @ co).to_2d() for co in template_co]
                coo = [direct_offset @ (meshMtx.scale @ (reset_matrix @ c)) for c in template_co]

            try:
                face = bm.faces.new((bm.verts.new(c, p_face.verts[0]) for c in coo), p_face)

                for loop, uv in zip(face.loops, uv_co):
                    loop[uv_layer].uv = uv
                    loop[uv_layer].select = True
                    if ZenPolls.version_since_3_2_0:
                        loop[uv_layer].select_edge = True
                face.normal_update()
                face.hide_set(False)
                face.select_set(True)

                bm.faces.active = face

            except Exception as e:
                Log.error("TRIM TO MESH:", e)

        bmesh.update_edit_mesh(obj.data, loop_triangles=True, destructive=True)

        return {'FINISHED'}

    def get_circle_3d_co(self, num_verts: int = 8, diameter: float = 1) -> list:
        rad = diameter / 2
        phi = 2 * pi / num_verts
        return [Vector((cos(i * phi), sin(i * phi), 0)) * rad for i in range(num_verts)]


classes = (
    ZUV_OT_TrimToMesh,
)


def register():
    RegisterUtils.register(classes)


def unregister():
    RegisterUtils.unregister(classes)
