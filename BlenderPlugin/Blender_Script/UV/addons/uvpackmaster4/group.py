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


from .box import UVPM4_Box, mark_boxes_dirty
from .island_params import GroupIParamInfoGeneric
from .spipeline.engine.labels import Labels

from .props import UVPM4_PackStrategyProps, PropConstants
from .pgroup import standalone_property_group
from .app_iface import *
from .tdensity.tier import UVPM4_TDensityValuePacking


def _update_group_info_name(self, context):
    orig_name = self.name

    from .utils import format_name
    name = format_name(self.name)

    if name == '':
        name = UVPM4_GroupInfo.get_default_group_name(self.num)
        
    if orig_name != name:
        self.name = name
            
    mark_boxes_dirty(self, context)


_OVERRIDE_PROPERTY_DEFAULT = False


def _def_prop_override(orig_prop_name):
    return BoolProperty(
        name='Override {}'.format(orig_prop_name),
        description=Labels.OVERRIDE_GLOBAL_OPTION_DESC,
        default=_OVERRIDE_PROPERTY_DEFAULT)


@standalone_property_group
class UVPM4_GroupOverrides:

    override_global_options : BoolProperty(
        name=Labels.OVERRIDE_GLOBAL_OPTIONS_NAME,
        description=Labels.OVERRIDE_GLOBAL_OPTIONS_DESC,
        default=_OVERRIDE_PROPERTY_DEFAULT)

    override_rotation_enable : _def_prop_override(Labels.ROTATION_ENABLE_NAME)
    rotation_enable : PropConstants.DEF__ROTATION_ENABLE

    override_pre_rotation_disable : _def_prop_override(Labels.PRE_ROTATION_DISABLE_NAME)
    pre_rotation_disable : PropConstants.DEF__PRE_ROTATION_DISABLE

    override_rotation_step : _def_prop_override(Labels.ROTATION_STEP_NAME)
    rotation_step : PropConstants.DEF__ROTATION_STEP
    
    override_scale_mode : _def_prop_override(Labels.SCALE_MODE_NAME)
    scale_mode : PropConstants.DEF__SCALE_MODE

    override_pixel_margin : _def_prop_override(Labels.PIXEL_MARGIN_NAME)
    pixel_margin : PropConstants.DEF__PIXEL_MARGIN

    override_pixel_border_margin : _def_prop_override(Labels.PIXEL_BORDER_MARGIN_NAME)
    pixel_border_margin : PropConstants.DEF__PIXEL_BORDER_MARGIN

    override_extra_pixel_margin_to_others : _def_prop_override(Labels.EXTRA_PIXEL_MARGIN_TO_OTHERS_NAME)
    extra_pixel_margin_to_others : PropConstants.DEF__EXTRA_PIXEL_MARGIN_TO_OTHERS

    override_pixel_margin_tex_size : _def_prop_override(Labels.PIXEL_MARGIN_TEX_SIZE_NAME)
    pixel_margin_tex_size : PropConstants.DEF__PIXEL_MARGIN_TEX_SIZE

    override_tdensity_packing : _def_prop_override(UVPM4_TDensityValuePacking.PROP_NAME)
    tdensity_packing : PointerProperty(type=UVPM4_TDensityValuePacking)
    
    override_groups_together : _def_prop_override(Labels.GROUPS_TOGETHER_NAME)
    groups_together : PropConstants.DEF__GROUPS_TOGETHER
    
    override_grouping_compactness : _def_prop_override(Labels.GROUPING_COMPACTNESS_NAME)
    grouping_compactness : PropConstants.DEF__GROUPING_COMPACTNESS
    
    override_pack_to_single_box : _def_prop_override(Labels.PACK_TO_SINGLE_BOX_NAME)
    pack_to_single_box : BoolProperty(
        name=Labels.PACK_TO_SINGLE_BOX_NAME,
        description=Labels.PACK_TO_SINGLE_BOX_DESC,
        default=PropConstants.PACK_TO_SINGLE_BOX_DEFAULT)
    
    override_pack_strategy : _def_prop_override(Labels.PACK_STRATEGY_NAME)
    pack_strategy : PointerProperty(type=UVPM4_PackStrategyProps)


@standalone_property_group
class UVPM4_GroupInfo:

    MIN_GROUP_NUM = 0
    MAX_GROUP_NUM = 1000
    DEFAULT_GROUP_NUM = MIN_GROUP_NUM
    DEFAULT_GROUP_NAME = 'G'
    TDENSITY_CLUSTER_DEFAULT = 0
    TILE_COUNT_DEFAULT = 1

    name : StringProperty(name="Name", default="", update=_update_group_info_name)
    num : IntProperty(name="Group Number", default=0)
    color : FloatVectorProperty(name="", default=(1.0, 1.0, 0.0), min=0.0, max=1.0, subtype="COLOR", update=mark_boxes_dirty)
    target_boxes : CollectionProperty(type=UVPM4_Box)
    active_target_box_idx : IntProperty(name="", default=0, update=mark_boxes_dirty)

    
    tdensity_cluster : IntProperty(
        name=Labels.TEXEL_DENSITY_CLUSTER_NAME,
        description=Labels.TEXEL_DENSITY_CLUSTER_DESC ,
        default=TDENSITY_CLUSTER_DEFAULT,
        min=0,
        max=100 * 1000)

    tile_count : IntProperty(
        name=Labels.TILE_COUNT_NAME,
        description=Labels.TILE_COUNT_DESC,
        default=TILE_COUNT_DEFAULT,
        min=1,
        max=100)
    
    dynamic_tiles : BoolProperty(
        name=Labels.DYNAMIC_TILES_GROUP_NAME,
        description=Labels.DYNAMIC_TILES_GROUP_DESC,
        default=False,
        update=mark_boxes_dirty
    )

    overrides : PointerProperty(type=UVPM4_GroupOverrides)

    def __init__(self, name='', num=0):
        super(type(self), self).__init__(name=name, num=num)
        self.color = GroupIParamInfoGeneric.GROUP_COLORS[self.num % len(GroupIParamInfoGeneric.GROUP_COLORS)] if self.num is not None else None

    @classmethod
    def get_default_group_name(cls, g_num):
        return "{}{}".format(cls.DEFAULT_GROUP_NAME, g_num)

    def is_default(self):
        return self.num == self.DEFAULT_GROUP_NUM

    def add_target_box(self, new_box):
        added_box = self.target_boxes.add()
        added_box.copy_from(new_box)
        self.active_target_box_idx = len(self.target_boxes)-1

    def remove_target_box(self, box_idx):
        if len(self.target_boxes) <= 1:
            raise RuntimeError('Group has to have at least one target box')

        self.target_boxes.remove(box_idx)
        self.active_target_box_idx = min(self.active_target_box_idx, len(self.target_boxes)-1)

    def get_active_target_box(self):
        try:
            return self.target_boxes[self.active_target_box_idx]

        except IndexError:
            return None
        