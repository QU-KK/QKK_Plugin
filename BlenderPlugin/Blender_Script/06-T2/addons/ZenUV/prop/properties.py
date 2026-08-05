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

# Zen UV Scene Properties group

import bpy
from bpy.props import FloatProperty, BoolProperty, EnumProperty, FloatVectorProperty, IntProperty

import uuid

from ZenUV.ops.texel_density.td_props import ZUV_TdProperties, ZUV_TdDrawProperties
from ZenUV.ui.labels import ZuvLabels
from ZenUV.zen_checker.zen_checker_labels import ZCheckerLabels as ch_labels
from ZenUV.ico import icon_get
from ZenUV.zen_checker.checker import (
    ZEN_GLOBAL_OVERRIDER_NAME,
    ZEN_IMAGE_NODE_NAME,
    ZEN_TILER_NODE_NAME,
    ZEN_OFFSETTER_NODE_NAME
)
from ZenUV.utils.constants import UiConstants as uc
from ZenUV.ops.trimsheets.trimsheet import ZuvTrimsheetGroup
from ZenUV.ops.trimsheets.trimsheet_transform import ZuvTrimsheetTransformProps
from ZenUV.ops.trimsheets.trimsheet_props import ZuvTrimsheetOwnerProps
from ZenUV.prop.scene_ui_props import ZUV_SceneUIProps
from ZenUV.prop.adv_maps_props import ZUV_AdvMapsSceneProps
from ZenUV.ops.transform_sys.transform_utils.tr_utils import TransformSysOpsProps


class ZUV_Properties(bpy.types.PropertyGroup):

    trimsheet_transform: bpy.props.PointerProperty(type=ZuvTrimsheetTransformProps)
    ui: bpy.props.PointerProperty(name='UI Properties', type=ZUV_SceneUIProps)
    td_props: bpy.props.PointerProperty(name='Texel Density Propertyes', type=ZUV_TdProperties)
    td_draw_props: bpy.props.PointerProperty(name='Texel Density Draw Properties', type=ZUV_TdDrawProperties)
    adv_maps: bpy.props.PointerProperty(name='Adv UV Maps', type=ZUV_AdvMapsSceneProps)

    def update_tr_fit_bounds_single(self, context):
        self.tr_fit_bound[0] = self.tr_fit_bound[1] = self.tr_fit_bounds_single

    def tr_mode_items(self, context):
        return [
            ('MOVE', 'Move', 'MOVE', icon_get("transform-move"), 0),
            ('SCALE', 'Scale', 'SCALE', icon_get("transform-scale"), 1),
            ('ROTATE', 'Rotate', 'ROTATE', icon_get("transform-rotate"), 2),
            ('FLIP', 'Flip', 'FLIP', icon_get("transform-flip"), 3),
            ('FIT', 'Fit', 'FIT', icon_get("transform-fit"), 4),
            ('ALIGN', 'Align', 'ALIGN', icon_get("transform-orient"), 5),
            ('DISTRIBUTE', 'Distribute', 'DISTRIBUTE', icon_get("transform-distribute"), 6),
            ('2DCURSOR', '2D Cursor', 'CURSOR', icon_get("transform-cursor"), 7)
        ]

    def update_interpolation(self, context):
        interpolation = {True: 'Linear', False: 'Closest'}
        _overrider = None
        if bpy.data.node_groups.items():
            _overrider = bpy.data.node_groups.get(ZEN_GLOBAL_OVERRIDER_NAME, None)
        if _overrider:
            if hasattr(_overrider, "nodes"):
                image_node = _overrider.nodes.get(ZEN_IMAGE_NODE_NAME)
                if image_node:
                    # image_node.image = _image
                    image_node.interpolation = interpolation[context.scene.zen_uv.tex_checker_interpolation]

    def update_checker_tiling(self, context):
        _overrider = None
        if bpy.data.node_groups.items():
            _overrider = bpy.data.node_groups.get(ZEN_GLOBAL_OVERRIDER_NAME, None)
        if _overrider:
            if hasattr(_overrider, "nodes"):
                tiler_node = _overrider.nodes.get(ZEN_TILER_NODE_NAME)
                if tiler_node:

                    tiler_node.inputs['Scale'].default_value = context.scene.zen_uv.tex_checker_tiling.to_3d()

    def update_checker_offset(self, context):
        _overrider = None
        if bpy.data.node_groups.items():
            _overrider = bpy.data.node_groups.get(ZEN_GLOBAL_OVERRIDER_NAME, None)
        if _overrider:
            if hasattr(_overrider, "nodes"):
                offsetter_node = _overrider.nodes.get(ZEN_OFFSETTER_NODE_NAME)
                if offsetter_node:
                    offsetter_node.outputs[0].default_value = context.scene.zen_uv.tex_checker_offset

    # def update_area_value_for_sel(self, context):
    #     self.range_value_start = self.area_value_for_sel - 2
    #     self.range_value_end = self.area_value_for_sel + 2

    tr_scale: FloatVectorProperty(
        name="Scale",
        description="Scaling size",
        size=2,
        default=(2.0, 2.0),
        subtype='XYZ'
    )

    tr_scale_mode: EnumProperty(
        name="Mode",
        description="Scaling Mode",
        items=[
            ("AXIS", "Axis", ""),
            ("UNITS", "Units", "")
        ],
        default="AXIS"
    )

    tr_flip_always_center: BoolProperty(
        name="Always Center",
        description='Always use the center of the island as a pivot',
        default=True
    )

    tr_scale_keep_proportion: BoolProperty(
        name="Keep Proportion",
        default=True
    )

    tr_move_inc: FloatProperty(
        name="Move Increment",
        description="The value on which the island will be shifted",
        default=1.0,
        min=0,
        step=0.1,
    )

    tr_fit_keep_proportion: BoolProperty(
        name="Keep Proportion",
        default=True
    )
    tr_fit_padding: FloatProperty(
        name="Padding",
        default=0.0
    )
    tr_fit_bound: FloatVectorProperty(
        name="Bounds",
        size=2,
        default=(1.0, 1.0),
        subtype='XYZ'
    )
    tr_fit_bounds_single: FloatProperty(
        name="Bounds",
        min=0.01,
        default=1.0,
        precision=2,
        update=update_tr_fit_bounds_single
    )
    tr_fit_region_bl: FloatVectorProperty(
        name="Bottom Left",
        size=2,
        default=(0.0, 0.0),
        subtype='XYZ'
    )
    tr_fit_region_tr: FloatVectorProperty(
        name="Top Right",
        size=2,
        default=(1.0, 1.0),
        subtype='XYZ'
    )
    tr_fit_per_face: BoolProperty(
        name="Face by Face",
        description='Fits Face by Face. Transform selection mode only',
        default=False
    )

    tr_rot_inc: IntProperty(
        name=ZuvLabels.PROP_ROTATE_INCREMENT_LABEL,
        description=ZuvLabels.PROP_ROTATE_INCREMENT_DESC,
        min=0,
        max=360,
        default=90
    )

    tr_rot_orient: BoolProperty(
        name="Orient to selection",
        default=False
    )

    tr_align_center: BoolProperty(
        name="Always center",
        default=False
    )

    tr_align_to: EnumProperty(
        name="Align To",
        description="",
        items=[
            ("TO_SEL_BBOX", "Selection Bounding Box", "Selection Bounding Box"),
            ("TO_UV_AREA", "UV Area Bounds", "Align To UV Area bounds"),
            ("TO_POSITION", "Position", "Align to given Position"),
            ("TO_CURSOR", "2D Cursor", ""),
            ("TO_ACTIVE_COMPONENT", "To Active Component", "Align to Active Component. Works only in UV Sync Selection - On"),
            ("ACTIVE_UDIM", "Active UDIM tile", "To active UDIM Tile"),
            ("TILE_NUMBER", "Tile Number", "To UDIM tile with the specified number")
        ],
        default="TO_SEL_BBOX"
    )
    tr_tile_number: bpy.props.IntProperty(
        name='Tile Number',
        description='Number of UDIM tile',
        default=1001,
        min=1001,
        max=2000)

    tr_set_cursor_to: bpy.props.EnumProperty(
        name='Influence',
        description="How to set the 2D Cursor",
        items=[
            ("ISLAND", "Islands", "To islands", 'UV_ISLANDSEL', 0),
            ("SELECTION", "Selection", "To selection", 'UV_FACESEL', 1),
            ("UV_AREA", "UV Area", "To UV Area", 'VIEW_ORTHO', 2),
            ("TO_POSITION", "To Position", "To the defined position", 3),
            ("ACTIVE_UDIM", "Active UDIM tile", "To active UDIM Tile", 4),
            ("TILE_NUMBER", "Tile Number", "To UDIM tile with the specified number", 5)
        ],
        default="ISLAND"
    )

    tr_align_vertices: BoolProperty(
        name="Vertex by Vertex",
        description='Mode for vertex alignment. Aligns vertex by vertex. Transform selection mode only',
        default=False
    )

    tr_align_position: FloatVectorProperty(
        name="Position",
        size=2,
        default=(0.0, 0.0),
        subtype='XYZ'
    )

    tr_mode: EnumProperty(
        name=ZuvLabels.PANEL_TRANSFORM_LABEL,
        description=ZuvLabels.PROP_ENUM_TRANSFORM_DESC,
        items=tr_mode_items
    )

    tr_pivot_mode: EnumProperty(
        name="Order",
        description="Processing order",
        items=[
                ('ONE_BY_ONE', "One by one", "Processing islands one by one", 'STICKY_UVS_DISABLE', 0),
                ('OVERALL', "Overall", "Processing all selections as one", 'STICKY_UVS_LOC', 1),
                ('SYSTEM_PIVOT', "System Pivot", "The processing order is determined by the system pivot settings", 'PIVOT_BOUNDBOX', 2),
            ],
        default='ONE_BY_ONE'
    )

    tr_space_mode: EnumProperty(
        name=ZuvLabels.PROP_TRANSFORM_SPACE_LABEL,
        description=ZuvLabels.PROP_TRANSFORM_SPACE_DESC,
        items=[
            ("ISLAND", "Island", "", 'MESH_GRID', 1),
            ("TEXTURE", "Texture", "", 'NODE_TEXTURE', 0)
        ],
        default="TEXTURE"
    )

    tr_type: EnumProperty(
        name=ZuvLabels.PROP_TRANSFORM_TYPE_LABEL,
        description=ZuvLabels.PROP_TRANSFORM_TYPE_DESC,
        items=[
            ("ISLAND", "Islands", "Transform islands mode", 'UV_ISLANDSEL', 0),
            ("SELECTION", "Selection", "Transform selection (uv, mesh) mode", 'UV_FACESEL', 1),
        ],
        default="ISLAND"
    )

    sl_convert: EnumProperty(
        name='Convert',
        description='Convert different edge types',
        items=uc.unified_mark_enum,
        default="SEAM_BY_OPEN_EDGES",
    )
    pack_uv_packer_margin: FloatProperty(
        name="Padding",
        description="Margin in conventional units. Not percentages or pixels.",
        default=2.0
    )

    uvp3_packing_method: EnumProperty(
        name='Packing Mode',
        items=[
            ('pack.single_tile', 'Single Tile', 'Single Tile'),
            ('pack.tiles', 'Tiles', 'Tiles'),
            ('pack.groups_to_tiles', 'Groups To Tiles', 'Groups To Tiles'),
            ('pack.groups_together', 'Groups Together', 'Groups Together')
        ],
        default='pack.single_tile'
    )

    world_size_units: TransformSysOpsProps.get_units_enum(name='Units', description='World size units', default=1)

    tex_checker_interpolation: BoolProperty(
        name=ch_labels.PROP_INTERPOLATION_LABEL,
        default=True,
        description=ch_labels.PROP_INTERPOLATION_DESC,
        update=update_interpolation,
        options=set()
    )
    tex_checker_tiling: FloatVectorProperty(
        name="Tiling",
        size=2,
        default=(1.0, 1.0),
        subtype='XYZ',
        update=update_checker_tiling,
        options=set()
    )
    tex_checker_offset: FloatProperty(
        name="Offset",
        default=0.0,
        step=1,
        update=update_checker_offset,
        options=set()
    )

    # Rescale by units block
    unts_uv_area_size: FloatProperty(
        name="UV size",
        description="The estimated width of the UV area",
        min=0.0,
        default=1000.0,
        precision=2,
        options=set()
    )
    unts_desired_size: FloatProperty(
        name="Desired size",
        description="The size of which should be set for selected elements relative to UV area",
        min=0.0,
        default=250.0,
        precision=4,
        options=set()
    )
    unts_calculate_by: EnumProperty(
        name="Calcutate",
        description="What mean the Desired Size",
        items=[
            ("HORIZONTAL", "Horizontal", "Horizontal"),
            ("VERTICAL", "Vertical", "Vertical")
        ],
        default="HORIZONTAL",
        options=set()
    )
    trans_betw_uv_name: bpy.props.StringProperty(name="Source UV Map", default='None')

    # ZUV_OT_SelectByUvArea properties START
    area_value_for_sel: FloatProperty(
        name="Area",
        description="Area value for select.",
        default=2.0,
        min=0.0,
        options=set()
    )
    range_value_start: FloatProperty(
        name=ZuvLabels.PROP_SEL_BY_UV_AREA_FROM_LABEL,
        description=ZuvLabels.PROP_SEL_BY_UV_AREA_FROM_DESC,
        default=2.0,
        min=0.0,
        options=set()
    )
    range_value_end: FloatProperty(
        name=ZuvLabels.PROP_SEL_BY_UV_AREA_TO_LABEL,
        description=ZuvLabels.PROP_SEL_BY_UV_AREA_TO_DESC,
        default=3.0,
        min=0.0,
        options=set()
    )
    # ZUV_OT_SelectByUvArea properties END

    trimsheet: bpy.props.CollectionProperty(name='Trimsheet', type=ZuvTrimsheetGroup)
    trimsheet_index: ZuvTrimsheetOwnerProps.trimsheet_index
    trimsheet_index_ui: ZuvTrimsheetOwnerProps.trimsheet_index_ui
    trimsheet_geometry_uuid: ZuvTrimsheetOwnerProps.trimsheet_geometry_uuid

    def trimsheet_mark_geometry_update(self):
        self.trimsheet_geometry_uuid = str(uuid.uuid4())

    st_uv_area_only: BoolProperty(
        name=ZuvLabels.PROP_ST_UV_AREA_ONLY_LABEL,
        default=False,
        options=set(),
        description=ZuvLabels.PROP_ST_UV_AREA_ONLY_DESC
    )

    get_uv_coverage_mode: bpy.props.EnumProperty(
        name="Mode",
        description='Coverage calculation mode',
        items=[
                ("GENERIC", 'Generic', 'The size of each island is calculated and added to the total value.', 0),
                ("SELECTED", 'Selected', 'Shows area for selected islands only', 1),
                ("ALREADY_STACKED", 'Exclude stacked', 'Excludes similar islands that stacked from the calculation', 2)
            ],
        default='GENERIC'
    )

    is_show_ops_annotations: BoolProperty(
        name='Show Annotations',
        default=False,
        description='Show operator data using Blender annotations'
    )
