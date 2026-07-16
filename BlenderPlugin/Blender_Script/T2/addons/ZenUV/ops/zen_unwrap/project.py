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

""" Zen UV The batch transformation is dependent on the Trim module """

# Copyright 2023, Valeriy Yatsenko


import bpy
import bmesh

from mathutils import Vector, Matrix
from ZenUV.utils.register_util import RegisterUtils
from ZenUV.ui.tool.view3d_base import gizmo_texture
from ZenUV.utils.generic import (
    get_mesh_data,
    resort_by_type_mesh_in_edit_mode_and_sel,
    verify_uv_layer
)
from ZenUV.utils import get_uv_islands as island_util
from ZenUV.utils.base_clusters.base_cluster import BaseCluster, ProjectCluster


class projCluster(BaseCluster, ProjectCluster):

    def __init__(self, context, obj, island, bm=None) -> None:
        super().__init__(context, obj, island, bm)


class ZUV_OT_ProjectByScreenCage(bpy.types.Operator):
    bl_idname = "uv.zenuv_project_by_cage"
    bl_label = "Project by Cage"
    bl_options = {'REGISTER', 'UNDO'}
    bl_description = "Project texture from current Screen Cage"

    influence_mode: bpy.props.EnumProperty(
        name='Mode',
        description="Project Mode",
        items=[
            ("ISLAND", "Islands", ""),
            ("SELECTION", "Selection", "")
        ],
        default="ISLAND"
    )

    @classmethod
    def poll(cls, context):
        """ Validate context """
        active_object = context.active_object
        return active_object is not None and active_object.type == 'MESH' and context.mode == 'EDIT_MESH'

    def draw(self, context):
        self.layout.prop(self, 'influence_mode')

    def execute(self, context):
        objs = resort_by_type_mesh_in_edit_mode_and_sel(context)
        if not objs:
            self.report({'INFO'}, "There are no selected objects.")
            return {'CANCELLED'}
        p_scene = context.scene
        b_is_screen = p_scene.zen_uv.ui.view3d_tool.get_select_mode() == 'SCREEN'
        try:
            # p_gizmo_trim_items = gizmo_trims.get(context.area.as_pointer(), {})
            # p_gizmo_cage = gizmo_cage.get(context.area.as_pointer(), None)
            p_gizmo_texture = gizmo_texture.get(context.area.as_pointer(), None)
            # print(context.area.as_pointer())
            # print(f'{p_gizmo_texture = }')
        except Exception:
            pass
        if p_gizmo_texture is None:
            self.report({'WARNING'}, "Zen UV: Zen Tool Cage is not found")
            return {'CANCELLED'}
        if b_is_screen is False:
            self.report({'WARNING'}, "Zen UV: Zen Tool Cage not in Screen mode")
            return {'CANCELLED'}

        base_verts = (Vector(), Vector((1.0, 0.0, 0.0)), Vector((0.0, 1.0, 0.0)))
        for obj in objs:
            me, bm = get_mesh_data(obj)
            uv_layer = verify_uv_layer(bm)
            if self.influence_mode == "ISLAND":
                islands = island_util.get_island(context, bm, uv_layer)
            else:
                islands = [[f for f in bm.faces if f.select], ]
            for island in islands:
                cluster = projCluster(context, obj, island, bm)
                cluster.set_fit_to_uv(False)
                cluster.set_transform(obj.matrix_world)
                pplane_verts = [p_gizmo_texture.matrix_basis @ Matrix.Translation(Vector((-0.5, -0.5, 0.0))) @ v for v in base_verts]
                cluster.project(input_plane=pplane_verts)
            bmesh.update_edit_mesh(me)
        return {"FINISHED"}


classes = (
    ZUV_OT_ProjectByScreenCage,
)


def register():
    RegisterUtils.register(classes)


def unregister():
    RegisterUtils.unregister(classes)
