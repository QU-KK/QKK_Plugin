import bpy
from bpy.types import PropertyGroup
from bpy.props import *
from .icon import icon


class UNITY_PG_fbx(PropertyGroup):
    # Export Tab

    path_mode: EnumProperty(
        name="Path Mode",
        items=(
            ("AUTO", "Auto", ""),
            ("ABSOLUTE", "Absolute", ""),
            ("RELATIVE", "Relative", ""),
            ("MATCH", "Match", ""),
            ("STRIP", "Strip Path", ""),
            ("COPY", "Copy", ""),
        ),
        default="COPY",
    )

    embed_textures: BoolProperty(
        name="Embed Textures",
        description="Embed textures in FBX binary file (only for 'Copy' path mode!)",
        default=True,
    )

    batch_mode: EnumProperty(
        name="Batch Mode",
        items=(
            ("OFF", "Off", ""),
            ("SCENE", "Scene", ""),
            ("COLLECTION", "Collection", ""),
            ("SCENE_COLLECTION", "Scene Collection", ""),
            ("ACTIVE_SCENE_COLLECTION", "Active Scene Collection", ""),
        ),
        default="OFF",
    )

    use_batch_own_dir: BoolProperty(
        name="Batch Own Dir",
        description="Create a dir for exported file",
    )

    # Include

    use_selection: BoolProperty(
        name="Selected Objects",
        default=True,
    )

    use_visible: BoolProperty(
        name="Visible Objects",
        default=False,
    )

    use_active_collection: BoolProperty(
        name="Active Collection",
        description="Export only objects from the active collection (and its children)",
        default=False,
    )

    object_types: EnumProperty(
        name="Object Types",
        description="Which kind of object to export",
        items=(
            ("ARMATURE", "Armature", "WARNING: not supported in dupli/group instances"),
            ("CAMERA", "Camera", ""),
            ("EMPTY", "Empty", ""),
            ("LIGHT", "Lamp", ""),
            ("MESH", "Mesh", ""),
            (
                "OTHER",
                "Other",
                "Other geometry types, like curve, metaball, etc. (converted to meshes)",
            ),
        ),
        options={"ENUM_FLAG"},
        default={"ARMATURE", "EMPTY", "MESH", "OTHER"},
    )

    use_custom_props: BoolProperty(
        name="Custom Properties",
        description="Export custom properties",
        default=True,
    )

    # Transform

    global_scale: FloatProperty(
        name="Scale",
        description="Scale all data (Some importers do not support scaled armatures!)",
        min=0.001,
        max=1000.0,
        soft_min=0.01,
        soft_max=1000.0,
        default=1.0,
    )

    apply_scale_options: EnumProperty(
        name="Apply Scalings",
        description="How to apply custom and units scalings in generated FBX file "
        "(Blender uses FBX scale to detect units on import, "
        "but many other applications do not handle the same way)",
        items=(
            (
                "FBX_SCALE_NONE",
                "All Local",
                "Apply custom scaling and units scaling to each object transformation, FBX scale remains at 1.0",
            ),
            (
                "FBX_SCALE_UNITS",
                "FBX Units Scale",
                "Apply custom scaling to each object transformation, and units scaling to FBX scale",
            ),
            (
                "FBX_SCALE_CUSTOM",
                "FBX Custom Scale",
                "Apply custom scaling to FBX scale, and units scaling to each object transformation",
            ),
            (
                "FBX_SCALE_ALL",
                "FBX All",
                "Apply custom scaling and units scaling to FBX scale",
            ),
        ),
        default="FBX_SCALE_UNITS",
    )

    axis_forward: EnumProperty(
        name="Forward",
        items=(
            ("X", "X Forward", ""),
            ("Y", "Y Forward", ""),
            ("Z", "Z Forward", ""),
            ("-X", "-X Forward", ""),
            ("-Y", "-Y Forward", ""),
            ("-Z", "-Z Forward", ""),
        ),
        default="-Z",
    )

    axis_up: EnumProperty(
        name="Up",
        items=(
            ("X", "X Up", ""),
            ("Y", "Y Up", ""),
            ("Z", "Z Up", ""),
            ("-X", "-X Up", ""),
            ("-Y", "-Y Up", ""),
            ("-Z", "-Z Up", ""),
        ),
        default="Y",
    )

    apply_unit_scale: BoolProperty(
        name="Apply Unit",
        description="Take into account current Blender units settings (if unset, raw Blender Units values are used as-is)",
        default=True,
    )

    use_space_transform: BoolProperty(
        name="Use Space Transform",
        description="Apply global space transform to the object rotations. When disabled "
        "only the axis space is written to the file and all object transforms are left as-is",
        default=True,
    )

    bake_space_transform: BoolProperty(
        name="Apply Transform",
        description="Bake space transform into object data, avoids getting unwanted rotations to objects when "
        "target space is not aligned with Blender's space "
        "(WARNING! experimental option, use at own risks, known broken with armatures/animations)",
        default=False,
    )

    # Geomerty

    mesh_smooth_type: EnumProperty(
        name="Smoothing",
        description="Export smoothing information " "(prefer 'Normals Only' option if your target importer understand split normals)",
        items=(
            (
                "OFF",
                "Normals Only",
                "Export only normals instead of writing edge or face smoothing data",
            ),
            ("FACE", "Face", "Write face smoothing"),
            ("EDGE", "Edge", "Write edge smoothing"),
        ),
        default="FACE",
    )

    use_subsurf: BoolProperty(
        name="Export Subdivision Surface",
        description="Export the last Catmull-Rom subdivision modifier as FBX subdivision "
        "(does not apply the modifier even if 'Apply Modifiers' is enabled)",
        default=False,
    )

    use_mesh_modifiers: BoolProperty(
        name="Apply Modifiers",
        description="Apply modifiers to mesh objects (except Armature ones) - " "WARNING: prevents exporting shape keys",
        default=True,
    )

    use_mesh_edges: BoolProperty(
        name="Loose Edges",
        description="Export loose edges (as two-vertices polygons)",
        default=False,
    )

    use_triangles: BoolProperty(
        name="Triangulate Faces",
        default=False,
    )

    use_tspace: BoolProperty(
        name="Tangent Space",
        description="Add binormal and tangent vectors, together with normal they form the tangent space "
        "(will only work correctly with tris/quads only meshes!)",
        default=False,
    )

    colors_type: EnumProperty(
        name="Vertex Colors",
        items=(
            ("NONE", "None", ""),
            ("SRGB", "sRGB", ""),
            ("LINEAR", "Linear", ""),
        ),
        default="SRGB",
    )

    prioritize_active_color: BoolProperty(
        name="Prioritize Active Color",
    )

    # Armature

    primary_bone_axis: EnumProperty(
        name="Primary Bone Axis",
        items=(
            ("X", "X Axis", ""),
            ("Y", "Y Axis", ""),
            ("Z", "Z Axis", ""),
            ("-X", "-X Axis", ""),
            ("-Y", "-Y Axis", ""),
            ("-Z", "-Z Axis", ""),
        ),
        default="Y",
    )

    secondary_bone_axis: EnumProperty(
        name="Secondary Bone Axis",
        items=(
            ("X", "X Axis", ""),
            ("Y", "Y Axis", ""),
            ("Z", "Z Axis", ""),
            ("-X", "-X Axis", ""),
            ("-Y", "-Y Axis", ""),
            ("-Z", "-Z Axis", ""),
        ),
        default="X",
    )

    armature_nodetype: EnumProperty(
        name="Armature FBXNode Type",
        description="FBX type of node (object) used to represent Blender's armatures "
        "(use Null one unless you experience issues with other app, other choices may no import back "
        "perfectly in Blender...)",
        items=(
            ("NULL", "Null", "'Null' FBX node, similar to Blender's Empty (default)"),
            (
                "ROOT",
                "Root",
                "'Root' FBX node, supposed to be the root of chains of bones...",
            ),
            (
                "LIMBNODE",
                "LimbNode",
                "'LimbNode' FBX node, a regular joint between two bones...",
            ),
        ),
        default="NULL",
    )

    use_armature_deform_only: BoolProperty(
        name="Only Deform Bones",
        description="Only write deforming bones (and non-deforming ones when they have deforming children)",
        default=True,
    )

    add_leaf_bones: BoolProperty(
        name="Add Leaf Bones",
        description="Append a final bone to the end of each chain to specify last bone length "
        "(use this when you intend to edit the armature from exported data)",
        default=False,  # False for commit!
    )

    # Bake Animations

    bake_anim: BoolProperty(
        name="Baked Animation",
        description="Export baked keyframe animation",
        default=True,
    )

    bake_anim_use_all_bones: BoolProperty(
        name="Key All Bones",
        description="Force exporting at least one key of animation for all bones " "(needed with some target applications, like UE4)",
        default=True,
    )

    bake_anim_use_nla_strips: BoolProperty(
        name="NLA Strips",
        description="Export each non-muted NLA strip as a separated FBX's AnimStack, if any, " "instead of global scene animation",
        default=True,
    )

    bake_anim_use_all_actions: BoolProperty(
        name="All Actions",
        description="Export each action as a separated FBX's AnimStack, instead of global scene animation "
        "(note that animated objects will get all actions compatible with them, "
        "others will get no animation at all)",
        default=False,
    )

    bake_anim_force_startend_keying: BoolProperty(
        name="Force Start/End Keying",
        description="Always add a keyframe at start and end of actions for animated channels",
        default=True,
    )

    bake_anim_step: FloatProperty(
        name="Sampling Rate",
        description="How often to evaluate animated values (in frames)",
        min=0.01,
        max=100.0,
        soft_min=0.1,
        soft_max=10.0,
        default=1.0,
    )

    bake_anim_simplify_factor: FloatProperty(
        name="Simplify",
        description="How much to simplify baked values (0.0 to disable, the higher the more simplified)",
        min=0.0,
        max=100.0,
        soft_min=0.0,
        soft_max=10.0,
        default=1.0,  # default: min slope: 0.005, max frame step: 10.
    )

    def draw_settings(self, context, layout):
        col = layout.column()

        box = col.box()
        box.label(text=" Include")
        col = box.column()
        col.use_property_split = True
        row = col.row()
        col.prop(self, "object_types")
        col.prop(self, "use_custom_props")
        col.prop(self, "embed_textures")

        box = col.box()
        box.label(text=" Transform")
        col = box.column()
        col.use_property_split = True
        col.prop(self, "global_scale")
        col.prop(self, "apply_scale_options")
        col.prop(self, "axis_forward")
        col.prop(self, "axis_up")
        col.prop(self, "apply_unit_scale")
        col.prop(self, "use_space_transform")
        row = col.row()
        row.use_property_split = True
        row.prop(self, "bake_space_transform")
        row.label(text="", icon="ERROR")

        box = col.box()
        box.label(text=" Geometry")
        col = box.column()
        col.use_property_split = True
        col.prop(self, "mesh_smooth_type")
        col.prop(self, "use_subsurf")
        col.prop(self, "use_mesh_modifiers")
        col.prop(self, "use_mesh_edges")
        col.prop(self, "use_triangles")
        col.prop(self, "use_tspace")
        if bpy.app.version >= (3, 6, 0):
            col.prop(self, "colors_type")
            col.prop(self, "prioritize_active_color")

        box = col.box()
        box.label(text=" Armature")
        col = box.column()
        col.use_property_split = True
        col.prop(self, "primary_bone_axis")
        col.prop(self, "secondary_bone_axis")
        col.prop(self, "armature_nodetype")
        col.prop(self, "use_armature_deform_only")
        col.prop(self, "add_leaf_bones")

        box = col.box()
        box.prop(self, "bake_anim")
        if self.bake_anim:
            col = box.column()
            col.use_property_split = True
            col.prop(self, "bake_anim_use_all_bones")
            col.prop(self, "bake_anim_use_nla_strips")
            col.prop(self, "bake_anim_use_all_actions")
            col.prop(self, "bake_anim_force_startend_keying")
            col.prop(self, "bake_anim_step")
            col.prop(self, "bake_anim_simplify_factor")


class UNITY_PG_lod(PropertyGroup):
    ratio: FloatProperty(
        name="Ratio",
        description="Reduction ratio",
        min=0,
        max=1,
        default=0.5,
    )


class UNITY_PG_folder(PropertyGroup):
    path: StringProperty(subtype="DIR_PATH")

    use_subfolder: BoolProperty(default=False)


class UNITY_PG_export(PropertyGroup):
    progress: IntProperty(
        name="Progress",
        subtype="PERCENTAGE",
        min=-1,
        soft_min=0,
        soft_max=100,
        max=100,
        default=-1,
    )

    type: EnumProperty(
        name="Path",
        description="Select which type of paths you want to export to",
        items=(
            ("UNITY", "Export to Unity", ""),
            ("DISK", "Export to Disk", ""),
            ("BOTH", "Both", ""),
        ),
        default="UNITY",
    )

    unity_folders: CollectionProperty(type=UNITY_PG_folder)
    unity_folder_index: IntProperty(name="Active Unity Folder Index")

    disk_folders: CollectionProperty(type=UNITY_PG_folder)
    disk_folder_index: IntProperty(name="Active Disk Folder Index")

    selection_type: EnumProperty(
        name="Selected",
        description="Export selected",
        items=(
            ("OBJECT", "Objects", "Export selected objects only"),
            (
                "COLLECTION",
                "Collections",
                "Export objects from selected collections (and its children)",
            ),
        ),
    )

    use_include: BoolProperty(
        name="Include Children",
        description="Export objects and its children",
        default=True,
    )

    use_sub_collection: BoolProperty(
        name="Include Sub Collections",
        description="Export objects from sub collections",
        default=True,
    )

    use_materials: BoolProperty(
        name="Include Materials",
        description="Export materials",
        default=True,
    )

    use_baked_material: BoolProperty(
        name="Assign BAKED Material",
        description="Replace materials with baked one (if available).\nBAKED material from Quick Baker",
        default=True,
    )

    shader_type: EnumProperty(
        name="Shader Type",
        description="Type of material shader to create in Unity",
        items=(
            ("STANDARD", "Standard", "Shader: Standard"),
            (
                "SPECULAR",
                "Standard (Specular setup)",
                "Shader: Standard (Specular setup)",
            ),
            ("AUTODESK", "Autodesk Interactive", "Shader: Autodesk Interactive"),
            ("HDRP_LIT", "HDRP/Lit", "Shader: HDRP/Lit"),
        ),
        default="STANDARD",
    )


class SCENE_PG_unity(PropertyGroup):
    lods: CollectionProperty(type=UNITY_PG_lod)
    lod_index: IntProperty()

    fbx: PointerProperty(type=UNITY_PG_fbx)
    export: PointerProperty(type=UNITY_PG_export)


classes = (
    UNITY_PG_fbx,
    UNITY_PG_lod,
    UNITY_PG_folder,
    UNITY_PG_export,
    SCENE_PG_unity,
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)

    bpy.types.Scene.unity = bpy.props.PointerProperty(type=SCENE_PG_unity)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)

    del bpy.types.Scene.unity
