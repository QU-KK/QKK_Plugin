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
from ..id_collection import IdCollectionAccess, UVPM4_IdCollectionAccessDescriptor, id_collection_item, IdCollectionBase
from ..utils import redraw_ui, PanelUtilsMixin
from ..id_collection.main_props import MainPropSetAccess

from ..props import UVPM4_NamedHash


class RepackClusterAccess(IdCollectionAccess, PanelUtilsMixin):

    ITEM_LABEL = 'Repack cluster'
    DEFAULT_ITEM_NAME = 'RepackCluster'

    BROWSE_ONLY_NO_ITEM_HELP_MSG = 'Create a repack cluster in the main Auto Repack panel'

    ICON = 'GEOMETRY_SET' if AppInterface.APP_VERSION >= (4,3,0) else 'MOD_DATA_TRANSFER'
    DRAW_LABEL = True
    HELP_URL_SUFFIX = '/40-miscellaneous-functionalities/30-auto-repacking/#repack-clusters'

    PROP_SETS_HELP_MSG = 'If you want to define option configurations for repacking individually per repack cluster, enable option sets for the given scene in {}'.format(MainPropSetAccess.ENABLE_PROP_UI_LOCATION)

    def __init__(self, context, *args, **kwargs):
        super().__init__(context, *args, **kwargs)
        self.init_draw(context)

    def _get_collection(self):
        return get_scene_props(self.context).repack_props.repack_clusters
    
    def _get_access_desc(self):
        return get_scene_props(self.context).repack_props.repack_cluster_access_desc
    
    def draw_item(self, cluster, layout):
        self.draw_main_prop_sets_cond(layout, cluster.main_prop_access_desc, not_enabled_msg=self.PROP_SETS_HELP_MSG)
    
    def state_changed_handler(self):
        redraw_ui(self.context)


@id_collection_item
class UVPM4_RepackCluster:

    ACCESS_TYPE = RepackClusterAccess

    main_prop_access_desc : PointerProperty(type=UVPM4_IdCollectionAccessDescriptor)
    uv_hash : PointerProperty(type=UVPM4_NamedHash)


class UVPM4_RepackClusterIdCollection(IdCollectionBase):

    items : CollectionProperty(type=UVPM4_RepackCluster)
