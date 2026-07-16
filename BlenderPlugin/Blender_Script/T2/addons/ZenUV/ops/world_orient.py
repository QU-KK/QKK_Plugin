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
from mathutils import Vector
from ZenUV.utils.generic import (
    resort_by_type_mesh_in_edit_mode_and_sel,
    resort_objects_by_selection,
    get_mesh_data,
    verify_uv_layer
)
from ZenUV.utils import get_uv_islands as island_util
from ZenUV.utils.base_clusters.base_cluster import (
    _OrientClusterLegacy
)
from ZenUV.utils.base_clusters.zen_cluster import ZenCluster
from ZenUV.ui.labels import ZuvLabels
from ZenUV.ops.transform_sys.transform_utils.tr_utils import TransformSysOpsProps
from ZenUV.utils.blender_zen_utils import ZenPolls


class ZUV_OT_WorldOrient(bpy.types.Operator):
    bl_idname = "uv.zenuv_world_orient"
    bl_label = "World Orient"
    bl_description = """Rotate Islands the way they are oriented on the Models.
Each method (Organic/Hard Surface) uses a heuristic approach
and correctly orients most of the Islands in its area"""
    bl_options = {'REGISTER', 'UNDO'}

    further_orient: bpy.props.BoolProperty(
        name="Further Orient",
        description="Further rotation for horizontal or vertical alignment",
        default=ZenPolls.get_operator_defaults("UV_OT_zenuv_world_orient", "further_orient", True)
        )

    poll = TransformSysOpsProps.poll_edit_mesh_and_active_object

    poll_reason = TransformSysOpsProps.poll_reason_edit_mesh_and_active_object

    def execute(self, context):
        import numpy as np
        from ZenUV.utils.base_clusters.base_cluster import OrientCluster
        from ZenUV.ops.trimsheets.trimsheet_utils import ZuvTrimsheetUtils
        from ZenUV.utils.bounding_box import BoundingBox2dSimple, BoundingBoxUtils

        objs = resort_by_type_mesh_in_edit_mode_and_sel(context)
        objs = resort_objects_by_selection(context, objs)

        if not objs:
            self.report({'WARNING'}, "Zen UV: Select something.")
            return {'CANCELLED'}

        b_is_image_editor = context.space_data.type == 'IMAGE_EDITOR'

        def get_materials_from_island(facelist: list):
            materials = set()
            for face in facelist:
                if face.select:
                    material_index = face.material_index
                    if material_index < len(obj.material_slots):
                        material = obj.material_slots[material_index].material
                        if material:
                            materials.add(material)
            return list(materials)

        aspect_ratio = 1.0
        if b_is_image_editor:
            p_image = ZuvTrimsheetUtils.getSpaceDataImage(context)
            if p_image and p_image.size[0] > 0 and p_image.size[1] > 0:
                aspect_ratio = p_image.size[0] / p_image.size[1]
        else:
            aspect_ratio = None

        p_broken_objs_count = 0
        for obj in objs:
            bm = bmesh.from_edit_mesh(obj.data)
            uv_layer = bm.loops.layers.uv.active
            if not uv_layer:
                p_broken_objs_count += 1
                continue
            islands = island_util.get_island(context, bm, uv_layer)

            for island in islands:
                if not b_is_image_editor:
                    mats = get_materials_from_island(island)
                    if mats:
                        p_image = ZuvTrimsheetUtils.getMaterialImage(mats[0])
                        if p_image is not None:
                            if p_image and p_image.size[0] > 0 and p_image.size[1] > 0:
                                aspect_ratio = p_image.size[0] / p_image.size[1]
                        else:
                            aspect_ratio = 1
                    else:
                        aspect_ratio = 1
                if self.further_orient:
                    uv_coords = [lp[uv_layer].uv for f in island for lp in f.loops]
                    np_coords = np.array(uv_coords, dtype=np.double)
                    pivot = Vector(np.mean(np_coords, axis=0))

                    orient_angle = OrientCluster.get_orient_angle(island, uv_layer, image_aspect=aspect_ratio)
                    bbox = BoundingBox2dSimple(points=uv_coords)

                    bbox = BoundingBoxUtils.rotate_by_angle(bbox, orient_angle, aspect_ratio, pivot)
                    angle = BoundingBoxUtils.get_orient_angle(bbox, aspect_ratio)
                    res_angle = orient_angle + angle

                    OrientCluster._rotate_uv_island(island, uv_layer, res_angle, aspect_ratio, pivot)
                else:
                    OrientCluster.orient_uv_island(island, uv_layer, image_aspect=aspect_ratio)
            bmesh.update_edit_mesh(obj.data, loop_triangles=False)

        if p_broken_objs_count > 0:
            self.report({'WARNING'}, "One or more objects do not have a UV map and cannot be processed.")

        return {'FINISHED'}


class oCluster(ZenCluster, _OrientClusterLegacy):
    def __init__(self, context, obj, island, bm=None, index=-1) -> None:
        super().__init__(context, obj, island, bm, index=index)
        # ZenCluster.__init__(self)
        _OrientClusterLegacy.__init__(self)


class ZUV_OT_WorldOrient_legacy(bpy.types.Operator):
    bl_idname = "uv.zenuv_world_orient"
    bl_label = ZuvLabels.OT_WORLD_ORIENT_LABEL
    bl_description = ZuvLabels.OT_WORLD_ORIENT_DESC
    bl_options = {'REGISTER', 'UNDO'}

    method: bpy.props.EnumProperty(
        name=ZuvLabels.PROP_WO_METHOD_LABEL,
        description=ZuvLabels.PROP_WO_METHOD_DESC,
        items=[
            ("HARD", "Hard Surface", ""),
            ("ORGANIC", "Organic", "")
        ],
        default="HARD"
    )
    rev_x: bpy.props.BoolProperty(name="X", default=False, description="Reverse Axis X")
    rev_y: bpy.props.BoolProperty(name="Y", default=False, description="Reverse Axis Y")
    rev_z: bpy.props.BoolProperty(name="Z", default=False, description="Reverse Axis Z")
    rev_neg_x: bpy.props.BoolProperty(name="-X", default=False, description="Reverse Axis -X")
    rev_neg_y: bpy.props.BoolProperty(name="-Y", default=False, description="Reverse Axis -Y")
    rev_neg_z: bpy.props.BoolProperty(name="-Z", default=False, description="Reverse Axis -Z")

    further_orient: bpy.props.BoolProperty(
        name=ZuvLabels.PROP_WO_FURTHER_LABEL,
        default=True,
        description=ZuvLabels.PROP_WO_FURTHER_DESC
        )
    flip_by_axis: bpy.props.BoolProperty(
        name="Flip By Axis",
        default=False,
        description="Allow flip islands by axis"
        )

    def draw(self, context):
        layout = self.layout
        layout.prop(self, "method")
        layout.prop(self, "further_orient")
        layout.prop(self, "flip_by_axis")
        if self.flip_by_axis:
            layout.label(text="Reverse Axis:")
            box = layout.box()
            row = box.row(align=True)
            row.prop(self, "rev_x")
            row.prop(self, "rev_y")
            row.prop(self, "rev_z")
            row = box.row(align=True)
            row.prop(self, "rev_neg_x")
            row.prop(self, "rev_neg_y")
            row.prop(self, "rev_neg_z")

    poll = TransformSysOpsProps.poll_edit_mesh_and_active_object

    poll_reason = TransformSysOpsProps.poll_reason_edit_mesh_and_active_object

    def execute(self, context):
        objs = resort_by_type_mesh_in_edit_mode_and_sel(context)
        objs = resort_objects_by_selection(context, objs)
        # print(f"\n{'-' * 50}\nObjs in WO Operator:", objs)
        if not objs:
            self.report({'WARNING'}, "Zen UV: Select something.")
            return {'CANCELLED'}

        for obj in objs:
            # print("\nProcessed Object --->  ", obj.name)
            me, bm = get_mesh_data(obj)
            uv_layer = verify_uv_layer(bm)
            islands = island_util.get_island(context, bm, uv_layer)
            # clusters = []
            # print("Islands count: ", len(islands))
            for ids, island in enumerate(islands):
                # print(f"Island No {ids} processing")
                cluster = oCluster(context, obj, island, bm, index=ids)
                if cluster.analyser.is_warning:
                    CA = cluster.analyser
                    print(f'\n{CA.message_type}, {CA.message}\n\t{CA.data}')
                    continue
                cluster.f_orient = self.further_orient
                cluster.set_direction(
                    {
                        "x": self.rev_x,
                        "-x": self.rev_neg_x,
                        "y": self.rev_y,
                        "-y": self.rev_neg_y,
                        "z": self.rev_z,
                        "-z": self.rev_neg_z,
                    }
                )
                cluster.type = self.method
                cluster.do_orient_to_world()

            bmesh.update_edit_mesh(me, loop_triangles=False)

        return {'FINISHED'}


w_orient_classes = (
    ZUV_OT_WorldOrient,
)
