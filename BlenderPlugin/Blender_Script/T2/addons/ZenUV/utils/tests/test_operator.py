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


import bpy
import bmesh
import time
from math import pi, radians
from mathutils import Vector, Matrix

from ZenUV.utils import get_uv_islands as island_util
from ZenUV.utils.generic import verify_uv_layer, resort_by_type_mesh_in_edit_mode_and_sel, resort_objects_by_selection
from ZenUV.utils.bounding_box import BoundingBox2d
from ZenUV.ui.pie import ZsPieFactory
from ZenUV.ops.transform_sys.transform_utils.tr_utils import ActiveUvImage
from ZenUV.ops.transform_sys.transform_utils.transform_loops import TransformLoops
from ZenUV.ops.transform_sys.transform_utils.tr_utils import Cursor2D
from ZenUV.utils.transform import matrix_by_image_aspect
from ZenUV.ops.transform_sys.transform_utils.tr_object_data import transform_object_data
from ZenUV.ops.transform_sys.transform_utils.tr_utils import TransformSysOpsProps
from ZenUV.prop.scene_ui_props import ZUV_UVToolProps
from ZenUV.utils.base_clusters.zen_cluster import ZenCluster
from ZenUV.utils.base_clusters.base_cluster import _OrientClusterLegacy

# NOTE: TD Section
from ZenUV.ops.texel_density.td_alternative import register as register_weighted_td
from ZenUV.ops.texel_density.td_alternative import unregister as unregister_weighted_td
from ZenUV.ops.texel_density.td_alternative import ZUV_OT_GetTexelDensityWeighted


class ZUV_OP_TestOperator(bpy.types.Operator):
    bl_idname = 'zenuv_test.test_operator'
    bl_label = 'Test Operator'
    bl_description = 'Isolate Islands (Toggle) by selected edge/face of the Islands'
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        """ Validate context """
        active_object = context.active_object
        return active_object is not None and active_object.type == 'MESH' and context.mode == 'EDIT_MESH'

    def execute(self, context):
        from ZenUV.ops.trimsheets.trimsheet_utils import ZuvTrimsheetUtils
        from ZenUV.utils.transform import UvTransformUtils
        objs = resort_by_type_mesh_in_edit_mode_and_sel(context)
        if not objs:
            self.info_message = "There are no selected objects"
            self.report({'INFO'}, self.info_message)
            return {'CANCELLED'}

        return {'FINISHED'}


class OBJECT_OT_ComparePerformanceComprehension(bpy.types.Operator):
    """Compare performance of three methods for filtering faces in BMesh"""
    bl_idname = "object.compare_performance"
    bl_label = "Compare Performance"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        print('-----------------------------------------------')
        obj = context.object
        if obj is None or obj.type != 'MESH':
            self.report({'ERROR'}, "Active object must be a mesh")
            return {'CANCELLED'}

        bm = bmesh.from_edit_mesh(obj.data)

        uv_layer = bm.loops.layers.uv.verify()

        # Variant 1
        start_time = time.time()
        p_selected_faces_v1 = set()
        for f in bm.faces:
            if f.select and not f.hide:
                for loop in f.loops:
                    if loop[uv_layer].select:
                        p_selected_faces_v1.add(f)
                        break
        time_v1 = time.time() - start_time

        # Variant 2
        start_time = time.time()
        p_selected_faces_v2 = {f for f in bm.faces if f.select and not f.hide and any(loop[uv_layer].select for loop in f.loops)}
        time_v2 = time.time() - start_time

        # Variant 3
        start_time = time.time()
        p_selected_faces_v3 = {
            f for f in bm.faces if f.select and not f.hide for loop in f.loops
            if loop[uv_layer].select}
        time_v3 = time.time() - start_time

        # Variant 4
        start_time = time.time()
        p_selected_faces_v4 = {
                f for f in bm.faces for loop in f.loops
                if not f.hide and f.select and loop[uv_layer].select and loop[uv_layer].select_edge
            }
        time_v4 = time.time() - start_time

        # Variant 5
        start_time = time.time()
        p_selected_faces_v5 = set()
        for f in bm.faces:
            if f.select and not f.hide:
                if all(loop[uv_layer].select for loop in f.loops):
                    p_selected_faces_v5.add(f)

        time_v5 = time.time() - start_time

        # Вывод результатов в консоль
        print(f"Variant 1: {time_v1:.6f} seconds, {len(p_selected_faces_v1)} faces")
        print(f"Variant 2: {time_v2:.6f} seconds, {len(p_selected_faces_v2)} faces")
        print(f"Variant 3: {time_v3:.6f} seconds, {len(p_selected_faces_v3)} faces")
        print(f"Variant 4: {time_v4:.6f} seconds, {len(p_selected_faces_v4)} faces")
        print(f"Variant 5: {time_v5:.6f} seconds, {len(p_selected_faces_v4)} faces")

        return {'FINISHED'}


class ZUV_OP_TestIslandUtils(bpy.types.Operator):
    bl_description = 'Test Islands utils'
    bl_idname = "uv.test_island_utils"
    bl_label = 'Test Island Utils'
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        """ Validate context """
        active_object = context.active_object
        return active_object is not None and active_object.type == 'MESH' and context.mode == 'EDIT_MESH'

    def execute(self, context):
        from ZenUV.utils.uv_islands_utils import get_uv_islands_sketch, get_selected_uv_islands_in_indices
        from timeit import default_timer as timer

        for obj in context.objects_in_mode:
            bm = bmesh.from_edit_mesh(obj.data)
            uv_layer = verify_uv_layer(bm)
            interval = timer()
            islands = get_uv_islands_sketch(context, bm, uv_layer, b_selected_only=True, b_include_hidden=True)
            print(f'Time: {timer()-interval}')
            print(f'{len(islands) = }')
            print(get_selected_uv_islands_in_indices(context, bm, uv_layer))
        return {'FINISHED'}


def draw_test_operators(context, layout):
    layout.operator(ZUV_OP_TestOperator.bl_idname)

    layout.operator(OBJECT_OT_ComparePerformanceComprehension.bl_idname)

    layout.operator(ZUV_OP_TestIslandUtils.bl_idname)

    layout.operator(ZUV_OT_GetTexelDensityWeighted.bl_idname)


test_classes = (
    ZUV_OP_TestOperator,
    OBJECT_OT_ComparePerformanceComprehension,
    ZUV_OP_TestIslandUtils)


def register_test_operator():
    for cl in test_classes:
        bpy.utils.register_class(cl)

    register_weighted_td()


def unregister_test_operator():
    for cl in test_classes:
        bpy.utils.unregister_class(cl)

    unregister_weighted_td()


if __name__ == "__main__":
    pass
