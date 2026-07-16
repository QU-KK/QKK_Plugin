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


from .spipeline.engine.types import (
    UvpmCoordSpace,
    UvpmSimilarityMode,
    UvpmPackStrategy,
    UvpmBoxCorner,
    UvpmAxis,
    UvpmScaleMode,
    UvpmOverlapDetectionMode
)
from .spipeline.engine.props import EngineScenePropsBase, SimilarityProps, TileTargetProps
from .utils import PanelUtilsMixin
from .spipeline.engine.labels import Labels
from .pgroup import standalone_property_group
from .app_iface import *


class PropConstants:

    TEXTURE_ATLAS_SIZE_MAX = 100
    TEXTURE_ATLAS_SIZE_MIN = 2
    TEXTURE_ATLAS_SIZE_DEFAULT = 2

    TILE_COUNT_XY_DEFAULT = 1
    TILE_COUNT_XY_MIN = 1
    TILE_COUNT_XY_MAX = 100

    TILES_IN_ROW_DEFAULT = 10
    TILE_COUNT_PER_GROUP_DEFAULT = 1
    PACK_TO_SINGLE_BOX_DEFAULT = False
    
    ORIENT_PRIM_3D_AXIS_DEFAULT = AppInterface.up_axis().value()
    ORIENT_PRIM_UV_AXIS_DEFAULT = UvpmAxis.Y.value()
    ORIENT_SEC_3D_AXIS_DEFAULT = UvpmAxis.X.value()
    ORIENT_SEC_UV_AXIS_DEFAULT = UvpmAxis.X.value()

    ORIENT_PRIM_SEC_BIAS_DEFAULT = 80

    DEF__ROTATION_ENABLE = BoolProperty(
        name=Labels.ROTATION_ENABLE_NAME,
        description=Labels.ROTATION_ENABLE_DESC,
        default=True)
    
    DEF__PRE_ROTATION_DISABLE = BoolProperty(
        name=Labels.PRE_ROTATION_DISABLE_NAME,
        description=Labels.PRE_ROTATION_DISABLE_DESC,
        default=False)
    
    DEF__ROTATION_STEP = IntProperty(
        name=Labels.ROTATION_STEP_NAME,
        description=Labels.ROTATION_STEP_DESC,
        default=90,
        min=1,
        max=180)

    DEF__SCALE_MODE = EnumProperty(
            name=Labels.SCALE_MODE_NAME,
            description=Labels.SCALE_MODE_DESC,
            items=UvpmScaleMode.to_blend_items())

    DEF__PIXEL_MARGIN = IntProperty(
        name=Labels.PIXEL_MARGIN_NAME,
        description=Labels.PIXEL_MARGIN_DESC,
        min=1,
        max=256,
        default=5)

    DEF__PIXEL_BORDER_MARGIN = IntProperty(
        name=Labels.PIXEL_BORDER_MARGIN_NAME,
        description=Labels.PIXEL_BORDER_MARGIN_DESC,
        min=0,
        max=256,
        default=1)

    DEF__EXTRA_PIXEL_MARGIN_TO_OTHERS = IntProperty(
        name=Labels.EXTRA_PIXEL_MARGIN_TO_OTHERS_NAME,
        description=Labels.EXTRA_PIXEL_MARGIN_TO_OTHERS_DESC,
        min=0,
        max=128,
        default=0)
    
    DEF__PIXEL_MARGIN_TEX_SIZE = IntProperty(
        name=Labels.PIXEL_MARGIN_TEX_SIZE_NAME,
        description=Labels.PIXEL_MARGIN_TEX_SIZE_DESC,
        min=16,
        max=32768,
        default=1024)

    DEF__GROUPS_TOGETHER = BoolProperty(
        name=Labels.GROUPS_TOGETHER_NAME,
        description=Labels.GROUPS_TOGETHER_DESC,
        default=False)

    DEF__GROUPING_COMPACTNESS = FloatProperty(
        name=Labels.GROUPING_COMPACTNESS_NAME,
        description=Labels.GROUPING_COMPACTNESS_DESC,
        default=0.0,
        min=0.0,
        max=1.0,
        precision=2,
        step=10.0)
    
    @classmethod
    def DEF__TILES_IN_ROW(cls, name=None, description=None, update=None):
        kwargs = {}
        if update is not None:
            kwargs['update'] = update

        return IntProperty(
            name=name if name is not None else Labels.TILES_IN_ROW_NAME,
            description=description if description is not None else Labels.TILES_IN_ROW_DESC,
            default=cls.TILES_IN_ROW_DEFAULT,
            min=PropConstants.TILE_COUNT_XY_MIN,
            max=PropConstants.TILE_COUNT_XY_MAX,
            **kwargs)
    

class EngineSceneProps(EngineScenePropsBase):

    def __init__(self, context):
        scene_props = get_scene_props(context)
        self.arrange_non_packed = scene_props.arrange_non_packed

        from .tdensity.tier import TDensityTierAccess
        self.tdensity_tiers = TDensityTierAccess.get_collection_s(context)
        self.init_tier_access()


class UVPM4_NamedHash(PropertyGroup):

    name : StringProperty(
        default=''
    )

    hash : StringProperty(
        default=''
    )


@standalone_property_group
class UVPM4_TrackGroupsProps:

    require_match_for_all : BoolProperty(
        name=Labels.TRACK_GROUPS_REQUIRE_MATCH_FOR_ALL_NAME,
        description=Labels.TRACK_GROUPS_REQUIRE_MATCH_FOR_ALL_DESC,
        default=True
    )

    matching_mode : EnumProperty(
        items=UvpmSimilarityMode.to_blend_items(),
        name=Labels.TRACK_GROUPS_MATCHING_MODE_NAME,
        description=Labels.TRACK_GROUPS_MATCHING_MODE_DESC)


@standalone_property_group
class UVPM4_PackStrategyProps(PanelUtilsMixin):

    HELP_URL_SUFFIX = '20-packing-functionalities/45-advanced-packing-options/#pack-strategy'

    strategy : EnumProperty(
        items=UvpmPackStrategy.to_blend_items(),
        name=Labels.PACK_STRATEGY_NAME,
        description=Labels.PACK_STRATEGY_DESC)
    
    start_corner : EnumProperty(
        items=UvpmBoxCorner.to_blend_items(),
        name=Labels.PACK_STRATEGY_START_CORNER_NAME,
        description=Labels.PACK_STRATEGY_START_CORNER_DESC)

    def draw(self, layout):
        col = layout.column(align=True)
        inner_col = self.draw_enum_in_box(self, "strategy", col, help_url_suffix=self.HELP_URL_SUFFIX)

        if self.strategy != UvpmPackStrategy.AUTOMATIC:
            self.draw_enum_in_box(self, "start_corner", inner_col, expand=True)


@standalone_property_group
class UVPM4_SplitOverlapProps:

    detection_mode : EnumProperty(
        items=UvpmOverlapDetectionMode.to_blend_items(),
        name=Labels.SPLIT_OVERLAP_DETECTION_MODE_NAME,
        description=Labels.SPLIT_OVERLAP_DETECTION_MODE_DESC)
    
    max_tile_x : IntProperty(
        name=Labels.SPLIT_OVERLAP_MAX_TILE_X_NAME,
        description=Labels.SPLIT_OVERLAP_MAX_TILE_X_DESC,
        default = 0,
        min = 0)
    
    dont_split_priorities : BoolProperty(
        name=Labels.SPLIT_OVERLAP_DONT_SPLIT_PRIORITIES_NAME,
        description=Labels.SPLIT_OVERLAP_DONT_SPLIT_PRIORITIES_DESC,
        default=False
    )



@standalone_property_group
class UVPM4_TileTargetProps(TileTargetProps):

    from .box import mark_boxes_dirty

    mode : EnumProperty(
        items=TileTargetProps.TileTargetMode.to_blend_items(),
        name='Mode',
        description='',
        update=mark_boxes_dirty)

    use_editor_grid : BoolProperty(
        name=Labels.USE_EDITOR_GRID_NAME,
        description=Labels.USE_EDITOR_GRID_DESC,
        default=False,
        update=mark_boxes_dirty)
    
    tile_count_x : IntProperty(
        name=Labels.TILE_COUNT_X_NAME,
        description=Labels.TILE_COUNT_X_DESC,
        default=PropConstants.TILE_COUNT_XY_DEFAULT,
        min=PropConstants.TILE_COUNT_XY_MIN,
        max=PropConstants.TILE_COUNT_XY_MAX,
        update=mark_boxes_dirty)

    tile_count_y : IntProperty(
        name=Labels.TILE_COUNT_Y_NAME,
        description=Labels.TILE_COUNT_Y_DESC,
        default=PropConstants.TILE_COUNT_XY_DEFAULT,
        min=PropConstants.TILE_COUNT_XY_MIN,
        max=PropConstants.TILE_COUNT_XY_MAX,
        update=mark_boxes_dirty)
    
    start_tile_x : IntProperty(
        name=Labels.START_TILE_X_NAME,
        description='',
        default=0,
        min=0,
        max=100,
        update=mark_boxes_dirty)

    start_tile_y : IntProperty(
        name=Labels.START_TILE_Y_NAME,
        description='',
        default=0,
        min=0,
        max=10,
        update=mark_boxes_dirty)
    
    tile_count : IntProperty(
        name='Tile Count',
        description='',
        default=1,
        min=1,
        max=100,
        update=mark_boxes_dirty)
    
    tiles_in_row : PropConstants.DEF__TILES_IN_ROW(description='', update=mark_boxes_dirty)
    

    def draw(self, layout):
        col = layout.column(align=True)

        row = col.box().row(align=True)
        row.prop(self, 'mode')

        from .operator_box import UVPM4_OT_RenderTargetTiles
        row.operator(UVPM4_OT_RenderTargetTiles.bl_idname, text='', icon='RESTRICT_RENDER_OFF')

        if self.mode == self.TileTargetMode.TILE_GRID:
            box = col.box()
            box.prop(self, "use_editor_grid")

            row = col.row(align=True)
            row.enabled = not self.use_editor_grid
            box = row.box()
            box.scale_y = PanelUtilsMixin.BOX_ALIGN_SCALE_Y
            box.label(text='Tile Count:')
            row.prop(self, "tile_count_x", text='X:')
            row.prop(self, "tile_count_y", text='Y:')

        elif self.mode == self.TileTargetMode.TILE_RANGE:
            row = col.row(align=True)
            box = row.box()
            box.scale_y = PanelUtilsMixin.BOX_ALIGN_SCALE_Y
            box.label(text='Start Tile:')
            row.prop(self, "start_tile_x", text='X:')
            row.prop(self, "start_tile_y", text='Y:')

            col.prop(self, "tile_count")
            col.prop(self, "tiles_in_row")

        else:
            assert False


@standalone_property_group
class UVPM4_SimilarityProps(SimilarityProps):

    simi_mode : EnumProperty(
        items=UvpmSimilarityMode.to_blend_items(),
        name=Labels.SIMI_MODE_NAME,
        description=Labels.SIMI_MODE_DESC)

    threshold : FloatProperty(
        name=Labels.SIMI_THRESHOLD_NAME,
        description=Labels.SIMI_THRESHOLD_DESC,
        default=0.1,
        min=0.0,
        precision=2,
        step=5.0)
    
    check_holes : BoolProperty(
        name=Labels.SIMI_CHECK_HOLES_NAME,
        description=Labels.SIMI_CHECK_HOLES_DESC,
        default=True)

    adjust_scale : BoolProperty(
        name=Labels.SIMI_ADJUST_SCALE_NAME,
        description=Labels.SIMI_ADJUST_SCALE_DESC,
        default=False)
    
    non_uniform_scaling_tolerance : FloatProperty(
        name=Labels.SIMI_NON_UNIFORM_SCALING_TOLERANCE_NAME,
        description=Labels.SIMI_NON_UNIFORM_SCALING_TOLERANCE_DESC,
        default=0.0,
        min=0.0,
        max=1.0,
        precision=2,
        step=2.0)

    match_3d_axis : EnumProperty(
        items=UvpmAxis.to_blend_items(include_none=True, only_positive=True),
        name=Labels.SIMI_MATCH_3D_AXIS_NAME,
        description=Labels.SIMI_MATCH_3D_AXIS_DESC)

    match_3d_axis_space : EnumProperty(
        items=UvpmCoordSpace.to_blend_items(),
        name=Labels.SIMI_MATCH_3D_AXIS_SPACE_NAME,
        description=Labels.SIMI_MATCH_3D_AXIS_SPACE_DESC)

    correct_vertices : BoolProperty(
        name=Labels.SIMI_CORRECT_VERTICES_NAME,
        description=Labels.SIMI_CORRECT_VERTICES_DESC,
        default=False)

    vertex_threshold : FloatProperty(
        name=Labels.SIMI_VERTEX_THRESHOLD_NAME,
        description=Labels.SIMI_VERTEX_THRESHOLD_DESC,
        default=0.01,
        min=0.0,
        max=0.05,
        precision=4,
        step=1.0e-1)
    

def _update_orient_3d_axes(self, context):
    if self.prim_3d_axis == self.sec_3d_axis:
        enum_values = AppInterface.object_property_data(self)["sec_3d_axis"].enum_items_static.keys()
        value_index = enum_values.index(self.sec_3d_axis)
        self.sec_3d_axis = enum_values[(value_index+1) % len(enum_values)]


@standalone_property_group
class UVPM4_OrientTo3dProps(PanelUtilsMixin):

    prim_3d_axis : EnumProperty(
        items=UvpmAxis.to_blend_items(include_none=False, only_positive=True),
        default=PropConstants.ORIENT_PRIM_3D_AXIS_DEFAULT,
        update=_update_orient_3d_axes,
        name=Labels.ORIENT_PRIM_3D_AXIS_NAME,
        description=Labels.ORIENT_PRIM_3D_AXIS_DESC)

    prim_uv_axis : EnumProperty(
        items=UvpmAxis.to_blend_items(include_none=False, only_2d=True),
        default=PropConstants.ORIENT_PRIM_UV_AXIS_DEFAULT,
        name=Labels.ORIENT_PRIM_UV_AXIS_NAME,
        description=Labels.ORIENT_PRIM_UV_AXIS_DESC)

    sec_3d_axis : EnumProperty(
        items=UvpmAxis.to_blend_items(include_none=False, only_positive=True),
        default=PropConstants.ORIENT_SEC_3D_AXIS_DEFAULT,
        update=_update_orient_3d_axes,
        name=Labels.ORIENT_SEC_3D_AXIS_NAME,
        description=Labels.ORIENT_SEC_3D_AXIS_DESC)

    sec_uv_axis : EnumProperty(
        items=UvpmAxis.to_blend_items(include_none=False, only_2d=True),
        default=PropConstants.ORIENT_SEC_UV_AXIS_DEFAULT,
        name=Labels.ORIENT_SEC_UV_AXIS_NAME,
        description=Labels.ORIENT_SEC_UV_AXIS_DESC)

    axes_space : EnumProperty(
        items=UvpmCoordSpace.to_blend_items(),
        name=Labels.ORIENT_TO_3D_AXES_SPACE_NAME,
        description=Labels.ORIENT_TO_3D_AXES_SPACE_DESC)

    prim_sec_bias : IntProperty(
        name=Labels.ORIENT_PRIM_SEC_BIAS_NAME,
        description=Labels.ORIENT_PRIM_SEC_BIAS_DESC,
        default=PropConstants.ORIENT_PRIM_SEC_BIAS_DEFAULT,
        min=0,
        max=90)
    

    def draw_axes_to_match(self, prop_name_3d, prop_name_uv, header, layout, *, prop_checker_3d=None):
        col = layout.column(align=True)
        col.label(text=header)

        col2 = col
        box2 = col2.box()
        split = box2.split(factor=0.15, align=True)

        s_col = split.column(align=True)
        row = s_col.row(align=True)
        row.label(text='3D:')

        s_col = split.column(align=True)
        col_flow = s_col.column_flow(columns=3, align=True)
        self.draw_expanded_enum(self, prop_name_3d, col_flow, prop_checker_3d)

        box2 = col2.box()
        split = box2.split(factor=0.15, align=True)

        s_col = split.column(align=True)
        row = s_col.row(align=True)
        row.label(text='UV:')

        s_col = split.column(align=True)
        col_flow = s_col.column_flow(columns=4, align=True)
        self.draw_expanded_enum(self, prop_name_uv, col_flow)

    def draw(self, layout):
        col = layout.column(align=True)
        box = col.box()
        self.draw_axes_to_match("prim_3d_axis", "prim_uv_axis", 'Primary Axes To Match:', box)
        self.draw_axes_to_match("sec_3d_axis", "sec_uv_axis", 'Secondary Axes To Match:', box,
                                prop_checker_3d=self.exclude_enum_item_checker(self, "prim_3d_axis"))

        self.draw_enum_in_box(self, "axes_space", col, expand=True)

        row = col.row(align=True)
        row.prop(self, 'prim_sec_bias')
