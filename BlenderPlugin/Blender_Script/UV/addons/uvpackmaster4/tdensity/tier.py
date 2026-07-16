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

from ..app_iface import *
from ..id_collection import id_collection_item, IdCollectionAccess, IdCollectionMixin
from ..pgroup import standalone_property_group
from ..id_collection import UVPM4_IdCollectionAccessDescriptor
from ..id_collection.ui import IdCollectionDrawer
from ..spipeline.engine.tdensity import TDensityTierValue, TDensityTier, TDensityTierValueMode
from ..spipeline.engine.labels import Labels
from ..spipeline.engine.utils import UTIL_COLOR_ARRAY
from .props import UVPM4_TDensityValue
from ..utils import redraw_ui, get_scene_props


class TDensityTierAccess(IdCollectionAccess):

    ITEM_LABEL = 'TDensity Tier'
    DEFAULT_ITEM_NAME = 'TDensityTier'

    @classmethod
    @property
    def BROWSE_ONLY_NO_ITEM_HELP_MSG(cls):
        from .panel import UVPM4_PT_TexelDensityTiers
        return "Create a texel density tier in the {} panel".format(UVPM4_PT_TexelDensityTiers.bl_label)

    ICON = 'TEXTURE_DATA'
    DRAW_LABEL = False
    HELP_URL_SUFFIX = ''

    @staticmethod
    def get_collection_s(context):
        return get_scene_props(context).tdensity_props.tdensity_tiers

    def _get_collection(self):
        return self.get_collection_s(self.context)
    
    def _get_access_desc(self):
        return get_scene_props(self.context).tdensity_props.tdensity_tier_access_desc
    
    def state_changed_handler(self):
        redraw_ui(self.context)

    def init_item(self, item):
        super().init_item(item)

        if len(self) > 1:
            item.num = self.get_items()[-2].num + 1

        item.color = UTIL_COLOR_ARRAY[item.num % len(UTIL_COLOR_ARRAY)]


@id_collection_item
@standalone_property_group
class UVPM4_TDensityTier(TDensityTier):

    ACCESS_TYPE = TDensityTierAccess

    val : PointerProperty(type=UVPM4_TDensityValue)
    num : IntProperty(name="Number", default=0)
    color : FloatVectorProperty(
        name="Color",
        description="Color for visual representation of UV overlays",
        default=(0.0, 0.0, 0.0),
        min=0.0,
        max=1.0,
        subtype="COLOR")

    def draw(self, layout):
        col = layout.column(align=True)
        self.val.draw(col, text=Labels.TEXEL_DENSITY_VALUE_NAME(add_prefix=True))
        col.box().prop(self, 'color')


@standalone_property_group
class UVPM4_TDensityTierIdCollection(IdCollectionMixin):

    items : CollectionProperty(type=UVPM4_TDensityTier)


@standalone_property_group
class UVPM4_SceneTDensityProps:

    tdensity_tiers : PointerProperty(type=UVPM4_TDensityTierIdCollection)
    tdensity_tier_access_desc : PointerProperty(type=UVPM4_IdCollectionAccessDescriptor)


class UVPM4_TDensityTierValueBase(TDensityTierValue):

    PROP_NAME = 'Texel Density'

    def draw(self, layout, text=None):
        if text is None:
            text = self.PROP_NAME

        col = layout.box().column(align=True)
        s = col.split(factor=0.4)
        s.row(align=True).label(text=text + ':')
        s.row(align=True).prop(self, 'mode', text='')

        if self.use_tier:
            IdCollectionDrawer(access=TDensityTierAccess(bpy.context, desc=self.tier_access_desc, ui_drawing=True), browse_only=True).draw(col)

        else:
            self.val.draw(col)


def tdensity_tier_value_decorator(new_cls) -> UVPM4_TDensityTierValueBase:
    annotations = new_cls.__dict__.get('__annotations__', dict())

    annotations['tier_access_desc'] = PointerProperty(type=UVPM4_IdCollectionAccessDescriptor)
    annotations['val'] = PointerProperty(type=UVPM4_TDensityValue)
    annotations['mode'] = EnumProperty(
        name='TD Value Mode',
        description='Defines how the texel density value will be determined',
        items=TDensityTierValueMode.to_blend_items()
    )

    return type(new_cls.__name__, (UVPM4_TDensityTierValueBase,) + new_cls.__bases__, dict(new_cls.__dict__, __annotations__=annotations))


@standalone_property_group
@tdensity_tier_value_decorator
class UVPM4_TDensityTierValue:
    pass


@standalone_property_group
@tdensity_tier_value_decorator
class UVPM4_TDensityValueToSet:
    
    PROP_NAME = Labels.TDENSITY_TO_SET_NAME


@standalone_property_group
@tdensity_tier_value_decorator
class UVPM4_TDensityValuePacking:
    
    PROP_NAME = Labels.TDENSITY_PACKING_NAME
