from .paths import RBDLabPaths


class RBDLabNaming:
    # Base RBDLab names:
    _RBDLAB_name = RBDLabPaths.ROOT_BASENAME  # <- RBDLAB
    _rbdlab_name = _RBDLAB_name.lower()  # <- rbdlab
    _RBDLab_name = _RBDLAB_name[:-2] + _rbdlab_name[-2:]  # <- RBDLab

    # ADD HIGHS MODS:
    SUFIX_LOW = "_Low"
    SUFIX_HIGH = "_High"
    USE_HIGHS = "use_highs"

    SECOND_SCATTER = "Secondary_Scatter"

    # Working with:
    WORKING_WITH = "Working with: "

    # Annotations:
    ANNOTATION_LAYER = _RBDLab_name + "_Annotation"

    # COLLECTIONS:
    COLLISION_COLL = _RBDLab_name + "_Collision"
    SUFIX_EDGE_FRACTURE = "_Edge_Fracture"
    ORIGINALS = _RBDLab_name + "_Originals"
    METAL_SOFT_PROXYS = "MetalSoft_Proxys"
    CUSTOM_COLL = _RBDLab_name + "_Custom_Collection"
    COLLECTION__COLL_ID = _rbdlab_name + "_id"
    OBJECT__COLL_ID = _rbdlab_name + "_collection_id"
    RBD_WORLD = "RigidBodyWorld"
    RBD_CONSTRAINTS = "RigidBodyConstraints"
    COMPUTED_NEIGHBORS = "ComputedNeighbors"
    LAST_CREATED_COLLS = "last_created_collections"
    ACTVTRS_RAY_CAST_DB = "Debug_Ray_Curves"
    PROXYS_COLL = "Proxys"
    
    # Metal Collections:
    METAL_MESHES = _RBDLab_name + "_Metal_Meshes"
    METAL_LINKS_COLL = "Metal_Links"
    CREATED_METAL_MESH = _RBDLab_name + "_Created_Metal_Mesh"
    
    # Metal Objects:
    SUFIX_DUMMY_METAL_OB = "_Metal_Mesh" 
    METAL_BASIC_MAT = _RBDLab_name + "_Basic_Metal_Mat"

    OB_PROXY = _RBDLab_name + "_Proxy"

    # MODIFIERS NAMES:
    SMOKE_MOD = _RBDLAB_name + "_Smoke"
    BOOLEAN_MOD = _RBDLAB_name + "_Boolean"
    BOOLEAN_MOD_UP = BOOLEAN_MOD + "_up"
    BOOLEAN_MOD_LOOP = BOOLEAN_MOD + "_Loop"
    BOOLEAN_MOD_FE = BOOLEAN_MOD + "_Fast_Exact"
    SOLIDIFY_MOD = _RBDLAB_name + "_Solidify"
    ACT_CANVAS_MOD = _RBDLAB_name + "_Canvas"
    ACT_BRUSH_MOD = _RBDLAB_name + "_Brush"


    # MODIFIERS:
    COLLISION_MOD = COLLISION_COLL
    DP_MOD = _RBDLab_name + "_DynamicPaint"
    SUBSURF_MOD = _RBDLab_name + "_Subsurf"
    VERTEX_WEIGHT_EDIT_MOD = _RBDLab_name + "_VertexWeightEdit"
    MASK_MOD = _RBDLab_name + "_Mask"
    GN_METAL_MESH = _RBDLab_name + "_GN_Metal_Mesh"
    TRIANGULATE = _RBDLab_name + "_Triangulate"
    DECIMATE_PLANAR = _RBDLab_name + "_DecimatePlanar"

    DISPLACE = _RBDLab_name + "_Displace"
    REMESH = _RBDLab_name + "_Remesh"
    DECIMATE = _RBDLab_name + "_Decimate"

    REMESH_ORIGNAL = _RBDLab_name + "_Remesh_Original"
    DECIMATE_ORIGINAL = _RBDLab_name + "_Decimate_Original"
    DISPLACE_FOR_DDFORM = _RBDLab_name + "_Displace_For_SurfaceDeform"
    SURFACE_DEFORM = _RBDLab_name + "_SurfaceDeform"

    SECONDARY_DISPLACE = _RBDLab_name + "_Secondary_Displace"
    SMOOTH_MOD = _RBDLab_name + "_Smooth"
    LAPLACIAN_MOD = _RBDLab_name + "_LaplacianSmooth"

    # MATERIALS:
    SUFIX_OUTER_MAT = "_Outer_mat"
    SUFIX_INNER_MAT = "_Inner_mat"
    INNER_MAT_TAG = _RBDLAB_name + SUFIX_INNER_MAT
    SMOKE_SHADER = SMOKE_MOD + "_Shader"
    TMP_MAT_NAME = "tmp_rbdlab_mat"
    TMP_PREVIOUS_MAT_NAME = _rbdlab_name + "_previous_" + SUFIX_INNER_MAT
    PARTICLES_MAT = _rbdlab_name + "_particles_mat"

    PRINCIPLED = "Principled BSDF"

    # DEBRIS:
    BASIC_DEBRIS_COLL_NAME = "Debris_Basics"
    BASIC_DEBRIS_OUTER_MAT = "Basicdust" + SUFIX_OUTER_MAT
    BASIC_DEBRIS_INNER_MAT = "BasicDebris" + SUFIX_INNER_MAT

    # PARTICLES:
    CHUNK_PART_CHILD = _rbdlab_name + "_child_obj"
    INNER_CHUNK = _rbdlab_name + "_inner"
    INNER_EMISOR = _rbdlab_name + "_inner_particle_emisor"
    EXTRACTION_ID = _rbdlab_name + "_exctraction_id"
    CHUNK_EXTRACTED = _rbdlab_name + "_chunk_extracted"
    PART_COLLISION = _rbdlab_name + "_particle_collision"
    PART_FSTART = _rbdlab_name + "_particle_fstart"
    PART_FEND = _rbdlab_name + "_particle_fend"
    PART_COLOR_ADDED = _rbdlab_name + "_ps_color_added"
    SMOKE_FRAME_OFFSET = _rbdlab_name + "_smoke_frame_offset"
    END_TRAILS = _rbdlab_name + "_ps_end_tails"
    PS_MOD_P_TO_RBD = _RBDLab_name + "_Emitter_motion_module"

    # ACTIVATORS/ACETONE:
    ACTIVATORS_COLL = "Activators" 
    CHUNK_ACTIVATORS = _rbdlab_name + "_Chunk_Activators" 
    ACETONABLE = _rbdlab_name + "_acetonable"
    ACTIVATORS_OBJECTS = "activators_objects"
    ACTIVATORS_EXPLODE_DONE = "activators_force_explode_done"
    ACTIVATORS_INITIAL_EXPLODE = _rbdlab_name + "_activators_initial_explode"
    ACTIVATORS_EXPLODED_DEST = _rbdlab_name + "_activators_exploded_dest"
    ACTIVATOR_OB_TO_PARENT = _rbdlab_name + "_activators_ob_to_parent"
    ACT_RECORD_TYPE = _rbdlab_name + "_act_record_type"
    ACT_RM_MESH = _rbdlab_name + "_act_mesh_mthd_org_ob"
    ORG_DATA = _rbdlab_name + "org_transforms_and_color"
    ACT_VG_DP_WEIGHT = _rbdlab_name + "_dp_weight"
    ACT_OB_COMPUTE = _rbdlab_name + "_act_compute"

    # CONSTRAINTS:
    PREFIX_CONST = ".ConstraintGroup_"
    
    # ahora usamos constraitns empty:
    # CONST_TYPE = 'GPENCIL'
    CONST_TYPE = 'EMPTY'

    CONSTRAINTS = _rbdlab_name + "_constraints"
    CONST_COLL = _RBDLab_name + "_Constraints"
    CONST_DIST = _rbdlab_name + "_const_dist"
    CONST_MAX_CONNECTIONS = _rbdlab_name + "_max_connections"
    CONST_IS_ADJACENT = _rbdlab_name + "_is_adjacent"
    CONST_PROCESSED = "constraints_processed"
    CLUSTER_ID = "cluster_id"
    GROUP_ID = "group_id"
    INTER_CLUSTER_CHUNKS = "inter_cluster_chunks"

    # DOMAINS:
    SUFIX_DOMAIN = "_Domain"
    DOMAIN_NAME = _RBDLAB_name + SUFIX_DOMAIN

    # GROUND:
    GROUND = _RBDLAB_name + "_Ground"

    # BOUNDING BOX:
    SUFIX_BBOX = "_BBox"
    HANDLER = _rbdlab_name + "_handler"

    # FACE MAPS:
    FACE_MAP_NAME = "Interior"

    # VELOCITIES:
    CMPUTD_VELOCITIES = "computed_velocities"
    VELOCITIES = _rbdlab_name + "_velocities"

    HAS_MOTIONS = _rbdlab_name + "_has_motions"
    HAS_BROKEN = _rbdlab_name + "_has_broken"

    # Boolean Fracture:
    BFRACTURE_DATA = "BooleanFractureData"
    BOOL_OBS = "BF_Bool_Objects"
    BF_BASE_PLANES_COLL_TMP = "BF_Base_Planes_Tmp"
    BOOLFRACTURE_GN_OB = "BooleanFracture"
    BF_INNER_MAT_NAME = "BoolPlane" + SUFIX_INNER_MAT
    BF_GN_COLL = _RBDLab_name + "_GN"
    BF_COLL_ID = _RBDLab_name + "_BF_GN_ID"

    # EDGE FRACTURES:
    FROM_EDGE_FRACTURE = _rbdlab_name + "_from_edge_fracture"
    EDGE_COMPOUND_PARENTED = "edges_pyshics_parented"
    NO_SHAPE_OBJ = _rbdlab_name + "_physics_no_shape"
    # COMPOUND_CHILDS = _rbdlab_name + "_compound_childrens"
    ACTIVE_ACTION = _rbdlab_name + "_active_action"

    # OBJECTS:
    FROM = _rbdlab_name + "_from"
    ORIGINAL_MW = _rbdlab_name + "_original_mw"
    ORIGINAL_LOC = _rbdlab_name + "_original_loc"
    BAKED_TO_KFRAMES = _rbdlab_name + "_baked_to_keyframes"

    BAKED_ACTION = _rbdlab_name + "_baked_action"
    RBD_TYPE = _rbdlab_name + "_rbd_type"

    RBD_KINEMATIC = _rbdlab_name + "_rbd_kinematic"
    RBD_SEL_KINEMATIC = _rbdlab_name + "_sel_kinematic"

    RBD_MASS = _rbdlab_name + "_rbd_mass"
    RBD_ENABLED = _rbdlab_name + "_rbd_enabled"
    RBD_DISABLED = _rbdlab_name + "_rbd_disabled"
    RBD_SHAPE = _rbdlab_name + "_rbd_shape"
    STATIC_COLLIDER = _RBDLab_name + "_Static_Collider"

    STORED_LOW_CHUNK_RELATION = "rbdlab_hich_chunk_to_parent"

    # MOTION:
    MOTION_OBJECT_EMITTER = _rbdlab_name + "_motion_emitter_object"


    # COLLECTION WITH:
    COLL_WITH_RBD = _rbdlab_name + "_collection_with_rbd"
    COLL_WITH_CONST = _rbdlab_name + "_collection_with_constraints"
    COLL_WITH_PARTICLES = _rbdlab_name + "_collection_with_particles"
    COLL_WITH_SMOKE = _rbdlab_name + "_collection_with_smoke"

    # PHYSICS:
    ACTIVE = _rbdlab_name + "_active"
    PASSIVE = _rbdlab_name + "_passive"
    CHILD_OF = _rbdlab_name + "_child_of"

    CURRENT_MASS = _rbdlab_name + "_current_mass"
    CUSTOM_MASS = _rbdlab_name + "_custom_mass"
    METAL_MASS = _rbdlab_name + "_metal_mass"

    # BAKE UVS
    WORLD_POSITION = "wpos"

    # Dynamic Switch ############################## 
    # Dynamic parent:
    # DSWITCH_DPARENT_ACTION = _rbdlab_name + "_dswitch_dparent_action"
    DSWITCH_DPARENT_BAKED_TO_KFRAMES = _rbdlab_name + "_dswitch_dparent_baked_to_keyframes"
    DSWITCH_DPARENT_STORE_RBD_SETTINGS = _rbdlab_name + "_dswitch_dparent_rbd_settings"
    # Visual Switching
    DSWITCH_VSWITCHING_PREV_EYE_VISIBILITY = _rbdlab_name + "_visual_switching_prev_eye_visibility"
    DSWITCH_VSWITCHING_PREV_VIEWPORT_VISIBILITY = _rbdlab_name + "_visual_switching_prev_viewport_visibility"
    DSWITCH_VSWITCHING_PREV_RENDER_VISIBILITY = _rbdlab_name + "_visual_switching_prev_render_visibility"
    DSWITCH_VSWITCHING_COMPUTED = _rbdlab_name + "_visual_switching_computed"
    ################################################

    # Physics Join:
    JOIN_SEPARATE_DATA = "join_separate_data"
    JOINED = _rbdlab_name + "_joined"


    # Adjacents comprobations:
    WM_RECOMP_ADJACENT = "recomputed_adjacents_neighbors"