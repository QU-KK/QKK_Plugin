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

from .spipeline.engine.types import GroupLayoutMode, TexelDensityGroupPolicy, GroupingMethod, PackOpType
from .spipeline.engine.labels import Labels
from .spipeline.engine.g_scheme import GroupingConfigBase
from .box import mark_boxes_dirty
from .box_utils import disable_box_rendering
from .grouping_scheme_access import GroupingSchemeAccess
from .pgroup import standalone_property_group
from .utils import PropertyWrapper
from .props import PropConstants
from .app_iface import *


@standalone_property_group
class UVPM4_GroupingOptionsBase:

    tiles_in_row : PropConstants.DEF__TILES_IN_ROW()
    
    tile_count_x : IntProperty(
        name=Labels.TILE_COUNT_X_NAME,
        description=Labels.TILE_COUNT_X_DESC,
        default=PropConstants.TILE_COUNT_XY_DEFAULT,
        min=PropConstants.TILE_COUNT_XY_MIN,
        max=PropConstants.TILE_COUNT_XY_MAX)

    tile_count_y : IntProperty(
        name=Labels.TILE_COUNT_Y_NAME,
        description=Labels.TILE_COUNT_Y_DESC,
        default=PropConstants.TILE_COUNT_XY_DEFAULT,
        min=PropConstants.TILE_COUNT_XY_MIN,
        max=PropConstants.TILE_COUNT_XY_MAX)
    
    atlas_size_x : IntProperty(
        name='Atlas Size (X)',
        default=PropConstants.TEXTURE_ATLAS_SIZE_DEFAULT,
        min=PropConstants.TEXTURE_ATLAS_SIZE_MIN,
        max=PropConstants.TEXTURE_ATLAS_SIZE_MAX
    )

    atlas_size_y : IntProperty(
        name='Atlas Size (Y)',
        default=PropConstants.TEXTURE_ATLAS_SIZE_DEFAULT,
        min=PropConstants.TEXTURE_ATLAS_SIZE_MIN,
        max=PropConstants.TEXTURE_ATLAS_SIZE_MAX
    )

    last_group_complementary : BoolProperty(
        name=Labels.LAST_GROUP_COMPLEMENTARY_NAME,
        description=Labels.LAST_GROUP_COMPLEMENTARY_DESC,
        default=False,
        update=mark_boxes_dirty)

    groups_together : PropConstants.DEF__GROUPS_TOGETHER
    grouping_compactness : PropConstants.DEF__GROUPING_COMPACTNESS
    
    pack_to_single_box : BoolProperty(
        name=Labels.PACK_TO_SINGLE_BOX_NAME,
        description=Labels.PACK_TO_SINGLE_BOX_DESC,
        default=PropConstants.PACK_TO_SINGLE_BOX_DEFAULT)
    
    dynamic_tiles_all : BoolProperty(
        name=Labels.DYNAMIC_TILES_ALL_NAME,
        description=Labels.DYNAMIC_TILES_ALL_DESC,
        default=False
    )


class GroupingOptionsMixin:

    @staticmethod
    def raise_grouping_error(msg):
        raise RuntimeError("Grouping: {}".format(msg))

    def supports_tile_count_per_group(self):
        return self.AUTOMATIC and GroupLayoutMode.supports_tile_count(self.group_layout_mode) and not self.base.dynamic_tiles_all
    
    def dynamic_tiles_all_validate_fail_msg(self):
        if self.base.dynamic_tiles_all and not GroupLayoutMode.supports_dynamic_tiles(self.group_layout_mode):
            return "'{}' is not supported with '{}' set to '{}'".format(
                PropertyWrapper(self.base, 'dynamic_tiles_all').get_name(),
                PropertyWrapper(self, 'group_layout_mode').get_name(),
                GroupLayoutMode.item_by_value(self.group_layout_mode).name)
        
        return None
    
    def validate_groups_to_tiles(self, pack_op_type):
        if pack_op_type == PackOpType.REPACK_WITH_OTHERS and self.group_layout_mode != GroupLayoutMode.MANUAL:
            self.raise_grouping_error("'{}' is only supported with '{}' set to '{}'".format(
                PackOpType.REPACK_WITH_OTHERS.name,
                PropertyWrapper(self, 'group_layout_mode').get_name(),
                GroupLayoutMode.MANUAL.name
            ))

        msg = self.dynamic_tiles_all_validate_fail_msg()
        if msg is not None:
            self.raise_grouping_error(msg)


@standalone_property_group
class UVPM4_GroupingOptions(GroupingOptionsMixin):

    AUTOMATIC = False

    base : PointerProperty(type=UVPM4_GroupingOptionsBase)

    tile_count_per_group : IntProperty(
        default=0, min=0, max=0
    )

    tdensity_policy : EnumProperty(
        items=TexelDensityGroupPolicy.to_blend_items(),
        name=Labels.TEXEL_DENSITY_GROUP_POLICY_NAME,
        description=Labels.TEXEL_DENSITY_GROUP_POLICY_DESC,
        update=mark_boxes_dirty)

    group_layout_mode : EnumProperty(
        items=GroupLayoutMode.to_blend_items(),
        name=Labels.GROUP_LAYOUT_MODE_NAME,
        description=Labels.GROUP_LAYOUT_MODE_DESC,
        update=disable_box_rendering)


@standalone_property_group
class UVPM4_AutoGroupingOptions(GroupingOptionsMixin):

    AUTOMATIC = True

    base : PointerProperty(type=UVPM4_GroupingOptionsBase)

    tile_count_per_group : IntProperty(
        name=Labels.TILE_COUNT_PER_GROUP_NAME,
        description=Labels.TILE_COUNT_PER_GROUP_DESC,
        default=PropConstants.TILE_COUNT_PER_GROUP_DEFAULT,
        min=PropConstants.TILE_COUNT_XY_MIN,
        max=PropConstants.TILE_COUNT_XY_MAX)

    tdensity_policy : EnumProperty(
        items=TexelDensityGroupPolicy.to_blend_items_auto(),
        name=Labels.TEXEL_DENSITY_GROUP_POLICY_NAME,
        description=Labels.TEXEL_DENSITY_GROUP_POLICY_DESC)

    group_layout_mode : EnumProperty(
        items=GroupLayoutMode.to_blend_items_auto(),
        name=Labels.GROUP_LAYOUT_MODE_NAME,
        description=Labels.GROUP_LAYOUT_MODE_DESC)


class GroupingConfig(GroupingConfigBase):

    def __init__(self, context):
        self.context = context
        self.grouping_enabled = False
        self.g_scheme_access_desc_id = None
        self.target_box_editing = False
        self.group_method_prop = None
        self.group_features = 0
        self.g_scheme_preset_panel_t = None

    def auto_grouping_enabled(self):
        return GroupingMethod.auto_grouping_enabled(self.group_method_prop.get())
    
    def draw_group_method(self, layout):
        layout.label(text=self.group_method_prop.get_name() + ':')
        row = layout.row(align=True)
        self.group_method_prop.draw(row, text='')

    def get_scheme_access(self, ui_drawing=False):
        gs_access = GroupingSchemeAccess(self.context, desc_id=self.g_scheme_access_desc_id, ui_drawing=ui_drawing)
        return gs_access

    def get_active_g_scheme(self, auto_grouping_check=True, ui_drawing=False):
        if auto_grouping_check and self.auto_grouping_enabled():
            return None

        return self.get_scheme_access(ui_drawing=ui_drawing).active_g_scheme
    
    def active_g_scheme_target_box_editing(self):
        active_g_scheme = self.get_active_g_scheme(auto_grouping_check=True, ui_drawing=True)

        if not active_g_scheme:
            return False
        
        return active_g_scheme.target_box_editing()
    