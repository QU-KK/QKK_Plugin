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

from ..id_collection.main_props import MainPropSetAccess
from ..id_collection.ui import IdCollectionDrawer

from ..app_iface import *
from ..multi_select import MultiSelectCollectionAccess
from ..id_collection import UVPM4_IdCollectionAccessDescriptor
from ..utils import PanelUtilsMixin
from ..props import UVPM4_NamedHash

from .cluster import UVPM4_RepackClusterIdCollection, RepackClusterAccess


def is_valid_obj(obj, accept_hidden=False):
    return (obj.type == 'MESH') and (accept_hidden or obj.visible_get())


def get_uvpm4_props(data):
    return data.uvpm4_props


class UVPM4_SceneRepackProps(PropertyGroup):

    force_repack : BoolProperty(
        name='Force Repacking',
        description='Repack all configured UV maps, even if they are up to date',
        default=False
    )

    show_results : BoolProperty(
        name='Show Results',
        description='After processing of an object / UV map is done, pause the operation showing the resulting UVs in the Edit mode. The user then needs to press Space to proceed to processing the next object / UV map',
        default=False
    )

    repack_cluster_access_desc : PointerProperty(type=UVPM4_IdCollectionAccessDescriptor)
    repack_clusters : PointerProperty(type=UVPM4_RepackClusterIdCollection)



class UVPM4_UvMapRepackData(PropertyGroup):
    
    name : StringProperty(name='Name', default='')
    main_prop_access_desc : PointerProperty(type=UVPM4_IdCollectionAccessDescriptor)

    add_to_cluster : BoolProperty(
        name='Add To Repack Cluster',
        description='',
        default=False
    )

    repack_cluster_access_desc : PointerProperty(type=UVPM4_IdCollectionAccessDescriptor)


class UVPM4_ObjectRepackProps(PropertyGroup):

    repack_enable : BoolProperty(
        name='Enable Auto Repacking',
        description='Enable auto repacking for the given object',
        default=False
    )

    force_repack : BoolProperty(
        name='Force Repacking',
        description='Repack UV maps for the given object, even if they are up to date',
        default=False
    )

    uv_map_array : CollectionProperty(type=UVPM4_UvMapRepackData)


class UVPM4_ObjectProps(PropertyGroup):

    repack_props : PointerProperty(type=UVPM4_ObjectRepackProps)


class UVPM4_MeshProps(PropertyGroup):

    uv_hash_array : CollectionProperty(type=UVPM4_NamedHash)


class UvMapRepackCollectionAccess(MultiSelectCollectionAccess, PanelUtilsMixin):

    ADD_ENTRY_MENU_LABEL = 'Add UV Map To Repack'
    ENTRY_NAME = 'Map'

    PROP_SETS_HELP_MSG = 'If you want to define option configurations for repacking individually per object / UV map, enable option sets for the given scene in {}'.format(MainPropSetAccess.ENABLE_PROP_UI_LOCATION)

    def __init__(self, context, init_str):
        self.init_draw(context)

        self.obj = bpy.data.objects[init_str]
        self.repack_props = get_uvpm4_props(self.obj).repack_props

        super().__init__(context, init_str)

    def _get_key_collection(self):
        return self.obj.data.uv_layers

    def _get_sel_collection(self):
        return self.repack_props.uv_map_array
    
    def _draw_entry(self, uv_data, layout):
        col = layout.column(align=True)
        col.box().prop(uv_data, 'add_to_cluster')

        col2 = col.box().column(align=True)

        if not uv_data.add_to_cluster:
            self.draw_main_prop_sets_cond(col2, uv_data.main_prop_access_desc, not_enabled_msg=self.PROP_SETS_HELP_MSG)

        else:
            IdCollectionDrawer(access=RepackClusterAccess(self.context, desc=uv_data.repack_cluster_access_desc, ui_drawing=True), browse_only=True).draw(col2)
