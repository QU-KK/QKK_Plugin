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

from ZenUV.utils.register_util import RegisterUtils
from ZenUV.utils.selection_utils import SelectionProcessor, UniSelectedObject
from ZenUV.utils import get_uv_islands as island_util
from ZenUV.utils.get_uv_islands import LoopsFactory
from mathutils import Vector
from ZenUV.ops.transform_sys.transform_utils.tr_utils import Cursor2D


class ZUV_OT_MirrorUV(bpy.types.Operator):
    bl_idname = "uv.zenuv_mirror_uv"
    bl_label = "Mirror UV"
    bl_description = "Mirroring UV coordinates in a mirrored mesh"
    bl_options = {'REGISTER', 'UNDO'}

    mesh_mirror_axis: bpy.props.EnumProperty(
        name='Mesh Mirror Axis',
        description='How the mirroring is represented in the object',
        items=[
            ("X", "X", "Mirorring along the X axis"),
            ("Y", "Y", "Mirorring along the Y axis"),
            ("Z", "Z", "Mirorring along the Z axis")
        ],
        default="X")
    uv_symmetry_axis: bpy.props.EnumProperty(
        name='UV Symmetry Axis',
        description='UV Symmetry axis',
        items=[
            ("X", "X", "Create symmetry from left to right or vice versa"),
            ("Y", "Y", "Create symmetry from top to bottom or vice versa")
        ],
        default="X")
    axis_position: bpy.props.EnumProperty(
        name="Axis Position",
        description="Base position of the symmetry axis",
        items=(
            ('MANUAL', "Manual", "Fully manual mode. The position of the symmetry axis depends only on the specified value"),
            ('CURSOR', "2D Cursor", "2D Cursor position"),
            ('UV_AREA', "UV Area Center", "UV Area center"),
            ('ACTIVE_UDIM', "Active UDIM Center", "Active UDIM Tile center"),
            ('BBOX', "Bounding Box", "One side of the selection bounding box"),
            ('ACTIVE_TRIM', "Active Trim Center", "Active trim center"),
        ),
        default='CURSOR')
    axis_offset: bpy.props.FloatProperty(
        name='Axis Offset',
        description='Offset of the symmetry axis. This value is added to any "Axis Position" type',
        default=0.0,
        precision=3)

    def get_direction_items(self, context):
        if self.uv_symmetry_axis == 'X':
            return (
                ('LEFT', "Left", "", "", 0),
                ('RIGHT', "Right", "", "", 1))
        else:
            return (
                ('TOP', "Top", "", "", 0),
                ('BOTTOM', "Bottom", "", "", 1))

    manual_axis_position: bpy.props.FloatProperty(
        name='Manual Axis Position',
        description='Position of the symmetry axis in manual mode. Active only if "Axis Position" is "Manual"',
        default=0.0,
        precision=3)
    mirroring_direction: bpy.props.EnumProperty(
        name="Mirroring Direction",
        description='Bounding box mirroring direction. Active only if "Axis Position" is "Bounding Box"',
        items=get_direction_items,
        default=1)
    folded: bpy.props.BoolProperty(
        name='Folded',
        description='Creates a folded symmetry where the coordinates of one part are equal to the coordinates of the other',
        default=False)

    @classmethod
    def poll(cls, context):
        """ Validate context """
        active_object = context.active_object
        return active_object is not None and active_object.type == 'MESH' and context.mode == 'EDIT_MESH'

    def draw(self, context):
        p_split = 0.5
        layout = self.layout

        row = layout.row()
        s = row.split(factor=p_split)
        r1 = s.row(align=True)
        r1.label(text='Mesh Mirror Axis: ')
        r2 = s.row(align=True)
        r2.prop(self, 'mesh_mirror_axis', expand=True)

        row = layout.row()
        s = row.split(factor=p_split)
        r1 = s.row(align=True)
        r1.label(text='UV Symmetry Axis: ')
        r2 = s.row(align=True)
        r2.prop(self, 'uv_symmetry_axis', expand=True)

        row = layout.row()
        s = row.split(factor=p_split)
        r1 = s.row(align=True)
        r1.label(text='Mode: ')
        r2 = s.row(align=True)
        r2.prop(self, 'folded', toggle=True)

        row = layout.row(align=True)
        s = row.split(factor=p_split)
        r1 = s.row(align=True)
        r1.label(text='Axis Position:')
        r2 = s.row(align=True)
        r2.prop(self, 'axis_position', text='')

        layout.label(text='Axis Properties:')
        a_box = layout.box()

        a_box.prop(self, 'axis_offset')
        row = a_box.row()
        row.enabled = self.axis_position == 'MANUAL'
        row.prop(self, 'manual_axis_position')

        row = a_box.row(align=True)
        s = row.split(factor=p_split)
        r1 = s.row(align=True)
        r1.label(text='Mirroring Direction:')
        row.enabled = self.axis_position == 'BBOX'
        r2 = s.row(align=True)
        r2.prop(self, 'mirroring_direction', text='')

    def execute(self, context):

        SelectionProcessor.reset_state()
        Storage = SelectionProcessor.collect_selected_objects(
            context,
            b_is_not_sync=False,
            b_in_indices=True,
            b_is_skip_objs_without_selection=True,
            b_skip_uv_layer_fail=False,
            b_skip_store_selected_items=True)

        if SelectionProcessor.result is False:
            self.report({'WARNING'}, SelectionProcessor.message)
            return {'CANCELLED'}

        precision = 5
        s_obj: UniSelectedObject = None

        for s_obj in Storage:
            s_obj.attribute_storage['islands'] = [
                [f.index for f in island]
                for island in island_util.get_island(context, s_obj.bm, s_obj.uv_layer)]

        for s_obj in Storage:
            bm = s_obj.bm
            uv_layer = s_obj.uv_layer
            bm.verts.ensure_lookup_table()

            # if self.influence == 'ISLAND':
            #     p_loops = LoopsFactory.loops_by_islands(context, bm, uv_layer, groupped=False)
            # else:
            #     p_loops = LoopsFactory.loops_by_sel_mode(context, bm, uv_layer)

            p_loops = LoopsFactory.loops_by_sel_mode(context, bm, uv_layer)

            # Get selection bound loops
            # p_faces = (lp.face for lp in p_loops)
            # p_sel_bound_edges = island_util.get_uv_bound_edges_indexes(p_faces, uv_layer)
            # bm.edges.ensure_lookup_table()
            # p_sel_bound_verts = (v for i in p_sel_bound_edges for v in bm.edges[i].verts)
            # bound_loops = [lp for v in p_sel_bound_verts for lp in v.link_loops if lp in p_loops]

            if self.axis_position == 'MANUAL':
                p_axis = Vector.Fill(2, self.manual_axis_position)

            elif self.axis_position == 'CURSOR':
                p_axis = Cursor2D(context).uv_cursor_pos
                if p_axis is None:
                    self.report({'WARNING'}, '2D Cursor is not found. Open UV Editor.')
                    return {'FINISHED'}

            elif self.axis_position == 'UV_AREA':
                p_axis = Vector.Fill(2, 0.5)

            elif self.axis_position == 'ACTIVE_UDIM':
                from ZenUV.ops.adv_uv_maps_sys.udim_utils import UdimFactory
                UdimFactory.reset_report()
                a_tile = UdimFactory.get_active_udim_tile(context)
                if a_tile is None:
                    self.report({'WARNING'}, UdimFactory.message)
                    return {'FINISHED'}
                p_axis = UdimFactory.get_bbox_of_udim(a_tile.number).center

            elif self.axis_position == 'BBOX':
                from ZenUV.utils.bounding_box import BoundingBox2d
                p_loops_co = [lp[uv_layer].uv for lp in p_loops]
                if not len(p_loops_co):
                    self.report({'WARNING'}, 'There is no selection')
                    return {'FINISHED'}
                p_bbox = BoundingBox2d(points=p_loops_co)
                if self.mirroring_direction == 'RIGHT':
                    p_axis = p_bbox.right_center
                elif self.mirroring_direction == 'LEFT':
                    p_axis = p_bbox.left_center
                elif self.mirroring_direction == 'TOP':
                    p_axis = p_bbox.top_center
                elif self.mirroring_direction == 'BOTTOM':
                    p_axis = p_bbox.bot_center

            elif self.axis_position == 'ACTIVE_TRIM':
                from ZenUV.ops.trimsheets.trimsheet_utils import ZuvTrimsheetUtils
                trim = ZuvTrimsheetUtils.getActiveTrim(context)
                if trim is None:
                    self.report({'WARNING'}, "There are no Active Trim.")
                    return {'FINISHED'}
                else:
                    p_axis = Vector(trim.get_center())
            else:
                raise RuntimeError('axis_position not in ("MANUAL", "CURSOR", "UV_AREA", "BBOX", "ACTIVE_TRIM")')

            p_axis += Vector.Fill(2, self.axis_offset)

            if self.uv_symmetry_axis == 'X':
                p_axis *= Vector((2, 0))
                p_side = Vector((-1, 1))
            else:
                p_axis *= Vector((0, 2))
                p_side = Vector((1, -1))

            if self.folded:
                p_side = Vector((1, 1))

            m_x, m_y, m_z = {'X': (-1, 1, 1), 'Y': (1, -1, 1), 'Z': (1, 1, -1)}[self.mesh_mirror_axis]

            selection = self.collect_loops_using_zen_scope(precision, p_loops)
            mesh_loops_cache = self.collect_mesh_cache(precision, bm, p_loops)

            for co, selection_loops in selection.items():
                adj_mesh_loops = mesh_loops_cache.get((co[0] * m_x, co[1] * m_y, co[2] * m_z))
                if adj_mesh_loops is None or not len(adj_mesh_loops):
                    continue

                adj_verts = {v.co.to_tuple(precision): v.index for v in [lp.vert for lp in adj_mesh_loops]}

                selection_verts = {}
                for v in ((v.co.to_tuple(precision), v.index) for v in [lp.vert for lp in selection_loops]):
                    selection_verts[v[0]] = v[1]

                for co, i in selection_verts.items():
                    adj_mesh_index = adj_verts.get((co[0] * m_x, co[1] * m_y, co[2] * m_z))
                    if adj_mesh_index is not None:
                        for lt, rt in zip([lp for lp in bm.verts[i].link_loops if lp in selection_loops],
                                          [lp for lp in bm.verts[adj_mesh_index].link_loops if lp in adj_mesh_loops]):
                            rt[uv_layer].uv = lt[uv_layer].uv * p_side + p_axis

            bmesh.update_edit_mesh(s_obj.obj.data)

        return {'FINISHED'}

    def collect_mesh_cache(self, precision: int, bm: bmesh.types.BMesh, p_loops: list) -> dict[list, list]:
        return {f.calc_center_bounds().to_tuple(precision): [lp for lp in f.loops if lp not in p_loops] for f in bm.faces}

    def collect_loops_using_zen_scope(self, precision: int, p_loops: list) -> dict[list, list]:
        from ZenUV.utils.generic import Scope
        scp = Scope()
        for lp in p_loops:
            scp.append(lp.face.calc_center_bounds().to_tuple(precision), lp)

        return scp.data


classes = (
    ZUV_OT_MirrorUV,
)


def register():
    RegisterUtils.register(classes)


def unregister():
    RegisterUtils.unregister(classes)


if __name__ == "__main__":
    pass
