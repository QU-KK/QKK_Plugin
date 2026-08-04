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
from dataclasses import dataclass
from math import pi
from mathutils import Vector, Matrix
from random import choice

from ZenUV.utils.register_util import RegisterUtils
from ZenUV.utils import get_uv_islands as island_util
from ZenUV.utils.get_uv_islands import FacesFactory
from ZenUV.utils.bounding_box import BoundingBox2d
from ZenUV.ops.trimsheets.trimsheet_utils import ZuvTrimsheetUtils

from ZenUV.utils.generic import resort_by_type_mesh_in_edit_mode_and_sel, verify_uv_layer
from ZenUV.ops.transform_sys.transform_utils.transform_loops import TransformLoops

from .hotspot import HspPropertiesBase

from ZenUV.ops.world_orient import oCluster
from ZenUV.ops.transform_sys.transform_utils.tr_rotate_utils import TrOrientProcessor
from ZenUV.ops.transform_sys.transform_utils.tr_utils import ActiveUvImage

from ZenUV.utils.generic import ZUV_PANEL_CATEGORY, ZUV_REGION_TYPE, ZUV_SPACE_TYPE


CAT = 'DIR_HOTSPOT'


class ZUV_PT_3DV_DirectionalHotspot(bpy.types.Panel):
    bl_space_type = ZUV_SPACE_TYPE
    bl_label = "Directional Hotspot"
    bl_region_type = ZUV_REGION_TYPE
    bl_category = ZUV_PANEL_CATEGORY
    bl_options = {'DEFAULT_CLOSED'}
    bl_parent_id = "ZUV_PT_3DV_Trimsheet"

    def draw(self, context: bpy.types.Context):
        layout = self.layout
        layout.operator(ZUV_OT_DirectionalHotspot.bl_idname)
        layout.operator(ZUV_OT_SetFaceNormalToTrimProps.bl_idname)


class ZUV_PT_UV_DirectionalHotspot(bpy.types.Panel):
    bl_space_type = "IMAGE_EDITOR"
    bl_label = "Directional Hotspot"
    bl_region_type = ZUV_REGION_TYPE
    bl_category = ZUV_PANEL_CATEGORY
    bl_options = {'DEFAULT_CLOSED'}
    bl_parent_id = "ZUV_PT_UVL_Trimsheet"

    draw = ZUV_PT_3DV_DirectionalHotspot.draw


@dataclass
class HspProperties(HspPropertiesBase):
    """ HotspotFactory Properties """
    trims_preselection: str = 'ALL'  # in {"ALL", "SELECTED"}
    orient: str = 'AS_IS'  # in {"NONE", "WORLD", "ORIENT"}
    allow_location_variation: bool = False
    keep_proportion: bool = True
    allow_scaling: bool = True
    selection_mode: str = 'ALL'
    threshold: float = 0
    select_processed_islands: bool = False

    def __post_init__(self, PROPS) -> None:
        super().__post_init__(PROPS)


class DirHotspotFactory(HspProperties):

    def __init__(self, PROPS: bpy.types.OperatorProperties) -> None:
        super().__post_init__(PROPS)

    def get_normal_suitable_trims(self, trimsheet, poly_island: list, object_matrix: Matrix, is_selected_only: bool, selection_mode: str, threshold_radians):
        for trim in trimsheet:
            if is_selected_only and not trim.selected:
                continue
            if trim.normal.magnitude == 0.0:
                continue
            island_normal = FacesFactory.get_poly_island_normal(poly_island).normalized()
            if island_normal.magnitude == 0.0:
                continue
            angle = trim.normal.angle(object_matrix.to_3x3() @ island_normal)
            if angle > threshold_radians:
                continue

            if selection_mode == 'ALL':
                yield trim
            else:
                direction = (object_matrix @ FacesFactory.get_poly_island_center(poly_island) - trim.world_position).normalized()
                dot_product = direction.dot(trim.normal)
                if selection_mode == 'FRONT' and dot_product <= 0:
                    continue
                elif selection_mode == 'BACK' and dot_product >= 0:
                    continue
                yield trim

    def do_directional_hotspotting(self, context: bpy.types.Context, objs: list, trimsheet: list):
        from ZenUV.ops.transform_sys.transform_utils.tr_utils import ActiveUvImage
        from collections import defaultdict

        if self.trims_preselection == 'SELECTED':
            trimsheet = [trim for trim in trimsheet if trim.selected]

        i_counter = 0
        t_counter = 0
        p_processed_data = defaultdict(list)
        for obj in objs:
            bm = bmesh.from_edit_mesh(obj.data)
            bm.faces.ensure_lookup_table()
            uv_layer = verify_uv_layer(bm)

            for island in island_util.get_island(context, bm, uv_layer):
                i_counter += 1
                suitable_trims = list(
                    self.get_normal_suitable_trims(
                        trimsheet=trimsheet,
                        poly_island=island,
                        object_matrix=obj.matrix_world,
                        is_selected_only=self.trims_preselection == 'SELECTED',
                        selection_mode=self.selection_mode,
                        threshold_radians=self.threshold))

                if not suitable_trims:
                    continue

                t_counter += len(suitable_trims)

                if self.allow_location_variation:
                    suitable_trim = choice(suitable_trims)
                else:
                    suitable_trim = suitable_trims[0]

                if self.orient == 'WORLD':
                    self.orient_island_to_world(context, obj, bm, island)
                elif self.orient == 'ORIENT':
                    self.orient_island_to_near_axis(context, island, uv_layer)

                TransformLoops.fit_loops(
                        [lp for f in island for lp in f.loops],
                        uv_layer,
                        BoundingBox2d(points=(suitable_trim.left_bottom, suitable_trim.top_right)),
                        'AUTO',
                        keep_proportion=self.keep_proportion,
                        angle=0.0,
                        image_aspect=ActiveUvImage(context).aspect,
                        rotate=False,
                        scale=self.allow_scaling
                    )
                if self.select_processed_islands:
                    p_processed_data[obj.name].extend([f.index for f in island])

            bmesh.update_edit_mesh(obj.data)

        if self.select_processed_islands:
            self.select_processed(context, p_processed_data)
        return i_counter, t_counter

    def select_processed(self, context: bpy.types.Context, data: dict):
        from ZenUV.utils.generic import bpy_deselect_by_context

        bpy_deselect_by_context(context)

        for obj_name, f_idxs in data.items():
            p_obj = bpy.data.objects.get(obj_name, None)
            if not p_obj:
                continue
            bm = bmesh.from_edit_mesh(p_obj.data)
            bm.faces.ensure_lookup_table()
            for i in f_idxs:
                bm.faces[i].select = True

    def orient_island_to_world(self, context: bpy.types.Context, obj: bpy.types.Object, bm: bmesh.types.BMesh, island: list):
        cluster = oCluster(context, obj, island, bm)
        cluster.f_orient = True
        cluster.type = "HARD"
        cluster.do_orient_to_world()

    def orient_island_to_near_axis(self, context: bpy.types.Context, island: list, uv_layer):
        TrOrientProcessor._orient_loops(
                cluster=[lp for f in island for lp in f.loops],
                uv_layer=uv_layer,
                bbox=BoundingBox2d(islands=[island, ], uv_layer=uv_layer),
                image_aspect=ActiveUvImage(context).aspect,
                orient_direction='AUTO',
                rotate_direction='CW'
            )


class ZUV_OT_DirectionalHotspot(bpy.types.Operator):
    bl_idname = "uv.zenuv_directional_hotspot"
    bl_label = "Directional Hotspot"
    bl_zen_short_name = 'Dir. Hotspot'
    bl_options = {'REGISTER', 'UNDO'}
    bl_description = "Hotspot mapping using island normal vector"

    trims_preselection: bpy.props.EnumProperty(
        name='Mode',
        description='Use all Trims or selected Trims to map Islands',
        items=[
            ("ALL", "All Trims", "Use all available Trims"),
            ("SELECTED", "Selected Trims", "Use only the selected Trims")],
        default='ALL')

    orient: bpy.props.EnumProperty(
        name='Orient',
        description='Perform some Island rotation before Hotspotting',
        items=[
            ("AS_IS", "As is", "No rotation at all"),
            ("WORLD", "Orient to World", "Orient to World"),
            ("ORIENT", "Orient to axis", "Auto orient island to nearest axis")],
        default='AS_IS')

    threshold: bpy.props.FloatProperty(
        name="Threshold",
        description="Normal alignment accuracy",
        default=0.0872664600610733,
        min=0.0,
        max=pi / 2,
        subtype='ANGLE')

    # selection_mode: bpy.props.EnumProperty(
    #     name="Selection Mode",
    #     description="Polygon selection mode",
    #     items=[
    #         ('FRONT', "Front", "Select polygons ahead of the reference"),
    #         ('BACK', "Back", "Select polygons behind the reference"),
    #         ('ALL', "All", "Select all polygons that match the normal")],
    #     default='ALL')

    keep_proportion: bpy.props.BoolProperty(
        name="Keep proportion",
        description="",
        default=True)

    allow_location_variation: bpy.props.BoolProperty(
        name='Allow Location Variation',
        description='Allow islands to be placed in other trims with similar parameters',
        default=False)

    allow_scaling: bpy.props.BoolProperty(
        name='Allow Scaling',
        description='Allow islands to be scaled to fit the trim',
        default=True)

    select_processed_islands: bpy.props.BoolProperty(
        name='Select Processed',
        description='Select processed islands',
        default=False)

    seed: bpy.props.IntProperty(
        name='Seed',
        description='Seed of variable island distribution in similar trims',
        default=132)

    @classmethod
    def poll(cls, context):
        """ Validate context """
        active_object = context.active_object
        return active_object is not None and active_object.type == 'MESH' and context.mode == 'EDIT_MESH'

    def draw(self, context):
        layout = self.layout

        # Preprocess
        layout.label(text='Preprocess:')
        box = layout.box()
        box.prop(self, 'trims_preselection')
        box.prop(self, 'orient')
        box.prop(self, 'threshold')

        # Settings
        layout.label(text='Settings:')
        box = layout.box()
        box.prop(self, 'allow_scaling')

        row = box.row()
        row.enabled = self.allow_scaling
        row.prop(self, 'keep_proportion')

        box.prop(self, 'select_processed_islands')

        # Variability
        layout.label(text='Variability:')
        box = layout.box()
        # box.prop(self, 'selection_mode')
        box.prop(self, 'allow_location_variation')
        box.prop(self, 'seed')

    def execute(self, context):
        objs = resort_by_type_mesh_in_edit_mode_and_sel(context)
        if not objs:
            self.report({'WARNING'}, "There are no selected objects.")
            return {'CANCELLED'}

        p_trimsheet = ZuvTrimsheetUtils.getTrimsheet(context)
        if not len(p_trimsheet):
            self.report({'WARNING'}, "There are no trims.")
            return {'CANCELLED'}

        if sum(trim.normal.magnitude for trim in p_trimsheet) == 0.0:
            self.report({'WARNING'}, 'No trims with directional data found. Set a non-zero value for the trim property "Normal".')
            return {'CANCELLED'}

        HSP = DirHotspotFactory(self.properties)
        i_counter, t_counter = HSP.do_directional_hotspotting(context, objs, p_trimsheet)

        if not i_counter:
            self.report({'WARNING'}, "Zen UV: Select something.")

        if not t_counter:
            self.report({'WARNING'}, "No suitable trims found.")

        return {"FINISHED"}


class ZUV_OT_SetFaceNormalToTrimProps(bpy.types.Operator):
    bl_idname = "mesh.zenuv_set_face_normal_to_trim_props"
    bl_label = "Normals To Trim"
    bl_options = {'REGISTER', 'UNDO'}
    bl_description = "Retrieve the normal vector from the selected face and apply it to the active trim"

    average_normal: bpy.props.BoolProperty(
        name='Average Normal Value',
        description='Calculate the averaged value if more than one face is selected.',
        default=False
    )

    def execute(self, context):
        objs = resort_by_type_mesh_in_edit_mode_and_sel(context)
        if not objs:
            self.report({'INFO'}, "There are no selected objects.")
            return {'CANCELLED'}

        a_trim = ZuvTrimsheetUtils.getActiveTrim(context)
        if a_trim is None:
            self.report({'INFO'}, "There are no active trim.")
            return {'CANCELLED'}

        reference_data = []
        for obj in objs:
            bm = bmesh.from_edit_mesh(obj.data)
            bm.faces.ensure_lookup_table()
            M = obj.matrix_world

            for face in (f for f in bm.faces if f.select):
                reference_data.append((M.to_3x3() @ face.normal, M @ face.calc_center_median()))

        if not reference_data:
            self.report({'WARNING'}, "Select at least one face.")
            return {'CANCELLED'}

        if len(reference_data) > 1:
            if self.average_normal:
                reference_data = [
                        (sum((i[0] for i in reference_data), Vector()).normalized(),
                         sum((i[1] for i in reference_data), Vector())), ]
            else:
                self.report({'WARNING'}, 'Select only one face or activate "Average Normal Value".')
                return {'FINISHED'}

        a_trim.normal = reference_data[0][0]
        a_trim.world_position = reference_data[0][1]

        self.report({'INFO'}, f'The normal value has been set for the trim "{a_trim.name}"')

        return {"FINISHED"}


classes = (
    ZUV_OT_DirectionalHotspot,
    ZUV_OT_SetFaceNormalToTrimProps,
)


def register():
    RegisterUtils.register(classes)


def unregister():
    RegisterUtils.unregister(classes)
