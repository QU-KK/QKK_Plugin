from bpy.types import PropertyGroup
from bpy.props import PointerProperty
from .target_collection_list import RBDLab_PG_TargetCollectionList
from .merge_collections_list import MergeCollectionsList
from ..collision import RBDLab_PG_collision_so_list
from .bf_gn_list import BFractureGNList
from .ac_layers_list import Ac_layers_list


class AllLists(PropertyGroup):

    """ context.scene.rbdlab.lists """
    # listados que no estan guardados en los "data"(Collection).x, ni en rutas con sentido.

    # Target Collection lists
    target_coll_list: PointerProperty(type=RBDLab_PG_TargetCollectionList)
    merge_collections_list: PointerProperty(type=MergeCollectionsList)

    # Collision Static Objects list
    collision_so_list: PointerProperty(type=RBDLab_PG_collision_so_list)

    # BFracture GN list
    bfracture_gn_list: PointerProperty(type=BFractureGNList)

    # Activators Layers List:
    ac_layers_list: PointerProperty(type=Ac_layers_list)
