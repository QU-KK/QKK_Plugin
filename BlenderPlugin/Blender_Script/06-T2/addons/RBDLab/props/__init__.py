# PROPERTY GROUP CLASSES REGISTRATION.
from bpy.utils import register_class, unregister_class
from bpy.types import Scene as scene, Object, Collection
from bpy.props import PointerProperty, CollectionProperty


from .main import rbdlab
from .ui import RBDLab_PG_UI

# SCATTER:
from .scatter import RBDLab_PG_scatter

# RIGID BODIES:
from .lists.animations.rbd.rbd_anim_dynamic_list import StoredChunk, StoredKeyFrames, RBDLAB_UL_draw_rbd_anim_dynamic, RBDAnimDynamicListItem, RBDAnimDynamicList
from .physics.rbd_props.animations import RBDLAB_PG_rbd_animations
from .physics.rbd_props.rigidbodies import RBDLAB_PG_rigidbodies

# DYNAMIC SWITCH:
from .physics.dswitch.dparent.dynamic_parent_props import RBDLAB_PG_dynamic_parent
from .physics.dswitch.visual_switching_props import RBDLab_PG_visual_switching_props
from .physics.dswitch.dswitch_pointers import RBDLAB_PG_DSwitch

# PHYSICS:
from .physics.physics import RBDLAB_PG_Physics

from .activators import RBDLab_PG_activators
from .smoke import RBDLab_PG_Smoke, RBDLab_PG_Smoke_Emiter
from .particles import RBDLab_PG_particles_add_props, RBDLab_PG_particles, RBDLab_PG_particles_debris, RBDLab_PG_particles_dust, RBDLab_PG_particles_smoke
from .bake import RBDLab_PG_Bake
from .motion import RBDLab_PG_motion
from .collision import RBDLab_PG_collision, COLLISION_SO_PG_list_item, RBDLab_PG_collision_so_list

# CONSTRAINTS:
from .lists.animations.constraints.constswitch_list import CS_StoredChunk, CS_StoredConstraint, CS_StoredKeyFrames, ConstSwitchListItem, ConstSwitchList, RBDLAB_UL_draw_constswitch
from .lists.animations.constraints.glue_strength_anim_list import GS_StoredChunk, GS_StoredConstraint, GS_StoredKeyFrames, GlueStrengthListItem, GlueStrengthList, RBDLAB_UL_draw_glue_strength_anim
from .lists.animations.constraints.springs import CSprings_StoredChunk, CSprings_StoredConstraint, CSprings_StoredKeyFrames, CSprings_StoredDpath, ConstraintSpringsListItem, SpringsList, RBDLAB_UL_draw_const_springs_anim

from .constraints.animations import RBDLab_PG_ConstraintsAnimation
from .constraints.constraints import RBDLab_PG_Constraints, ConstraintCollListItem, Cluster, Chunk, ConstraintGroup, NeighborChunks

from .materials import RBDLab_PG_thumbnails, MaterialCollListItem, RBDLab_PG_Materials
from .rbdlab_object import Velocity, Motion, RBDLabObjectData
from .metal.metal import RBDLabMetalData
from .rbdlab_collection import RBDLabCollectionData

# Activators Layers Lists:
from .lists.ac_layers_list import Ac_layers_lst_StoredObjects, Ac_layers_lst_StoredTypes, Ac_layers_lst_item, Ac_layers_list, RBDLAB_UL_draw_ac_layers
# Activators Lists:
from .lists.activators_list import Activators_lst_StoredObjects, Activators_lst_StoredTypes, Activators_lst_item, Activators_list, RBDLAB_UL_draw_activators, RBDLAB_MT_activators_dropdow


# Target collection Lists:
from .lists.merge_collections_list import MCListItem, MergeCollectionsList, RBDLAB_UL_draw_merge_collections
from .lists.bf_gn_list import BF_GN_StoredObjects, BFractureGNListItem, BFractureGNList, RBDLAB_UL_draw_bf_gn
from .lists.metal_modifiers_list import MetalModifiersList, MetalModifiers_StoredObjects, MetalModifiersListItem, RBDLAB_UL_draw_metal_modifiers
from .lists.metal_list import Metal_StoredObjects, Metal_StoredCollections, MetalListItem, MetalList, RBDLAB_UL_draw_metal
from .lists.target_collection_list import ListItem, RBDLab_PG_TargetCollectionList, RBDLAB_UL_draw_target_coll_list, RBDLAB_OT_target_collection_list_item_move, RBDLAB_MT_target_collection_submenu
from .lists.all_lists_pointers import AllLists


PROPERTY_GROUPS = (


    RBDLab_PG_thumbnails,
    MaterialCollListItem,
    RBDLab_PG_Materials,

    RBDLab_PG_UI,

    RBDLab_PG_scatter,

    # physics module:
    StoredChunk, StoredKeyFrames, RBDLAB_UL_draw_rbd_anim_dynamic, RBDAnimDynamicListItem, RBDAnimDynamicList,
    RBDLAB_PG_rbd_animations,
    RBDLAB_PG_rigidbodies,
    RBDLAB_PG_dynamic_parent,
    RBDLab_PG_visual_switching_props,
    RBDLAB_PG_DSwitch,
    RBDLAB_PG_Physics,

    RBDLab_PG_activators,
    RBDLab_PG_motion,

    RBDLab_PG_Smoke_Emiter,
    RBDLab_PG_Smoke,

    RBDLab_PG_particles_add_props,
    RBDLab_PG_particles_debris,
    RBDLab_PG_particles_dust,
    RBDLab_PG_particles_smoke,

    # Metal modifiers tiene q ir antes de MetalList porque esta guardado dentro de el:
    MetalModifiers_StoredObjects, MetalModifiersListItem, MetalModifiersList, RBDLAB_UL_draw_metal_modifiers,
    # Metal list, tiene q ir antes de RBDLabCollectionData porque se guarda dentro del collection:
    Metal_StoredObjects, Metal_StoredCollections, MetalListItem, MetalList, RBDLAB_UL_draw_metal,

    # (Activators List) tiene q ir antes de (Activators Layers List) porque se guarda dentro de (Activators Layers List)
    # (Activators Layers List) tiene q ir antes de (RBDLabCollectionData) porque se guarda dentro del collection
    Activators_lst_StoredObjects, Activators_lst_StoredTypes, Activators_lst_item, Activators_list, RBDLAB_UL_draw_activators, RBDLAB_MT_activators_dropdow,
    Ac_layers_lst_StoredObjects, Ac_layers_lst_StoredTypes, Ac_layers_lst_item, Ac_layers_list, RBDLAB_UL_draw_ac_layers,

    # constraint switch list:
    CS_StoredChunk, 
    CS_StoredConstraint,
    CS_StoredKeyFrames,
    ConstSwitchListItem,
    ConstSwitchList,
    RBDLAB_UL_draw_constswitch,

    # Glue Strength list:
    GS_StoredChunk, 
    GS_StoredConstraint, 
    GS_StoredKeyFrames, 
    GlueStrengthListItem, 
    GlueStrengthList, 
    RBDLAB_UL_draw_glue_strength_anim,

    # Springs list:
    CSprings_StoredChunk, 
    CSprings_StoredConstraint, 
    CSprings_StoredKeyFrames, 
    CSprings_StoredDpath,
    ConstraintSpringsListItem, 
    SpringsList, 
    RBDLAB_UL_draw_const_springs_anim,
    
    RBDLab_PG_ConstraintsAnimation,
    
    Chunk,
    NeighborChunks,
    Cluster,
    ConstraintCollListItem,
    ConstraintGroup,
    RBDLab_PG_Constraints,

    RBDLab_PG_particles,
    RBDLab_PG_Bake,
    COLLISION_SO_PG_list_item,
    RBDLab_PG_collision_so_list,
    RBDLab_PG_collision,

    # RBDLab Object
    Velocity, Motion, RBDLabObjectData,

    # Propiedades -> collection.rbdlab.metal.x :
    RBDLabMetalData,
        
    RBDLabCollectionData,
    
    ListItem, RBDLab_PG_TargetCollectionList, RBDLAB_UL_draw_target_coll_list, RBDLAB_OT_target_collection_list_item_move, RBDLAB_MT_target_collection_submenu,
    MCListItem, MergeCollectionsList, RBDLAB_UL_draw_merge_collections,
    BF_GN_StoredObjects, BFractureGNListItem, BFractureGNList, RBDLAB_UL_draw_bf_gn,
    AllLists,

    rbdlab,  # Main PG.
)


def register():
    for cls in PROPERTY_GROUPS:
        register_class(cls)

    scene.rbdlab = PointerProperty(type=rbdlab)
    Object.neighbor_chunks = PointerProperty(type=NeighborChunks)
    Object.coll_neighbor_chunks = CollectionProperty(type=NeighborChunks)
    Object.rbdlab = PointerProperty(type=RBDLabObjectData)
    Collection.rbdlab = PointerProperty(type=RBDLabCollectionData)


def unregister():
    from bpy.types import Scene as scene

    # from bpy.utils import previews
    # for pcoll in scene.rbdlab.thumbnails.img_preview_collection.values():
    #     previews.remove(pcoll)
    # scene.rbdlab.thumbnails.img_preview_collection.clear()

    del scene.rbdlab
    del Object.neighbor_chunks
    del Object.coll_neighbor_chunks
    del Object.rbdlab
    del Collection.rbdlab

    for cls in reversed(PROPERTY_GROUPS):
        unregister_class(cls)
