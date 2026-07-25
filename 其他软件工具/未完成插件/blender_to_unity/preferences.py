import bpy
from bpy.types import AddonPreferences, PropertyGroup
from bpy.props import *
from .qbpy.icon import icon
import os


class UNITY_AP_collider(PropertyGroup):
    def update_material_color(self, context, property_name, material_name):
        """Update collison material color.

        property_name (str) - Name of the property.
        material_name (str) - Name of the material.
        """
        if material := bpy.data.materials.get(material_name, None):
            material.diffuse_color = self.get(property_name, (1, 1, 1, 1))

    convex: FloatVectorProperty(
        name="Convex Color",
        description="Color of the convex object",
        size=4,
        min=0,
        max=1,
        subtype="COLOR_GAMMA",
        default=(0.0, 1, 0, 0.15),
        update=lambda self, context: self.update_material_color(context, property_name="convex", material_name="Convex_Collider"),
    )

    box: FloatVectorProperty(
        name="Box Color",
        description="Color of the box object",
        size=4,
        min=0,
        max=1,
        subtype="COLOR_GAMMA",
        default=(0.0, 1, 1, 0.15),
        update=lambda self, context: self.update_material_color(context, property_name="box", material_name="Box_Collider"),
    )

    sphere: FloatVectorProperty(
        name="Sphere Color",
        description="Color of the sphere object",
        size=4,
        min=0,
        max=1,
        subtype="COLOR_GAMMA",
        default=(1, 0, 1, 0.15),
        update=lambda self, context: self.update_material_color(context, property_name="sphere", material_name="Sphere_Collider"),
    )

    capsule: FloatVectorProperty(
        name="Capsule Color",
        description="Color of the capsule object",
        size=4,
        min=0,
        max=1,
        subtype="COLOR_GAMMA",
        default=(1, 1, 0, 0.15),
        update=lambda self, context: self.update_material_color(context, property_name="capsule", material_name="Capsule_Collider"),
    )

    def draw(self, context, layout):
        col = layout.column()
        col.use_property_split = True
        col.prop(self, "box")
        col.prop(self, "capsule")
        col.prop(self, "convex")
        col.prop(self, "sphere")


class UNITY_AP_lod(PropertyGroup):
    offset: FloatProperty(
        name="LODs Offset",
        description="Offset LODs location for better comparison",
        min=1,
        soft_max=5,
        default=3,
    )

    def draw(self, context, layout):
        layout.use_property_split = True
        col = layout.column()
        col.prop(self, "offset")


class UNITY_AP_vhacd(PropertyGroup):
    version: EnumProperty(
        name="Version",
        description="Select the V-HACD version",
        items=(
            ("VHACD4.1", "VHACD 4.1", ""),
            ("VHACD4", "VHACD 4", ""),
            ("VHACD2", "VHACD 2", ""),
        ),
    )

    def get_abs_vhacd_path(self):
        directory = os.path.join(os.path.dirname(__file__), "resource", "V-HACD")

        if self.version == "VHACD4.1":
            return os.path.join(directory, "VHACD_v4.1.exe")
        elif self.version == "VHACD4":
            return os.path.join(directory, "VHACD_v4.exe")
        else:
            return os.path.join(directory, "VHACD_v2.exe")

    def set_abs_vhacd_path(self, value):
        self.path = bpy.path.abspath(value)

    path: StringProperty(
        name="Path",
        description="Path to the V-HACD executable",
        subtype="FILE_PATH",
        get=get_abs_vhacd_path,
        set=set_abs_vhacd_path,
    )

    resolution: IntProperty(
        name="Voxel Resolution",
        description="Maximum number of voxels generated during the voxelization stage",
        min=10000,
        max=64000000,
        default=100000,
    )

    depth: IntProperty(
        name="Clipping Depth",
        description='Maximum number of clipping stages. During each split stage, all the model parts (with a concavity higher than the user defined threshold) are clipped according the "best" clipping plane',
        min=1,
        max=32,
        default=20,
    )

    concavity: FloatProperty(
        name="Concavity",
        description="Maximum allowed concavity",
        min=0.0,
        max=1.0,
        precision=4,
        default=0.0025,
    )

    plane_downsample: IntProperty(
        name="Plane Downsample",
        description='Controls the granularity for the "best" clipping plane',
        min=1,
        max=16,
        default=4,
    )

    hull_downsample: IntProperty(
        name="Hull Downsample",
        description="Precision of the convex-hull generation process during the clipping plane selection stage",
        min=1,
        max=16,
        default=4,
    )

    alpha: FloatProperty(
        name="Alpha",
        description="Bias toward clipping along symmetry planes",
        min=0.0,
        max=1.0,
        default=0.05,
    )

    beta: FloatProperty(
        name="Beta",
        description="Bias toward clipping along revolution axes",
        min=0.0,
        max=1.0,
        default=0.05,
    )

    gamma: FloatProperty(
        name="Gamma",
        description="Maximum allowed concavity during the merge stage",
        min=0.0,
        max=1.0,
        precision=5,
        default=0.00125,
    )

    normalize: BoolProperty(
        name="Normalize",
        description="Normalize the mesh before applying the convex decomposition",
        default=False,
    )

    shrinkwrap: BoolProperty(name="Shrinkwrap", description="Shrinkwrap hull to source mesh.", default=False)

    mode: EnumProperty(
        name="Mode",
        description="Approximate convex decomposition mode",
        items=(
            ("VOXEL", "Voxel", "Voxel ACD Mode"),
            ("TETRAHEDRON", "Tetrahedron", "Tetrahedron ACD Mode"),
        ),
        default="VOXEL",
    )

    hull_vertices: IntProperty(
        name="Hull Vertices",
        description="Maximum number of vertices per convex-hull",
        min=4,
        max=1024,
        default=32,
    )

    hull_volume: FloatProperty(
        name="Hull Volume",
        description="Minimum volume to add vertices to convex-hulls",
        min=0.0,
        max=0.01,
        precision=4,
        default=0.0001,
    )

    # VHACD v4

    output_hull: IntProperty(
        name="Output Hull",
        description="Maximum number of output hulls.",
        min=1,
        default=16,
    )

    voxel_resolution: IntProperty(
        name="Voxel Resolution",
        description="Total number of voxels to use.",
        min=1,
        default=100000,
    )

    volume_error: FloatProperty(
        name="Volume Error",
        description="Volume error allowed as a percentage.",
        subtype="PERCENTAGE",
        min=0,
        default=1,
    )

    recursion_depth: IntProperty(
        name="Recursion Depth",
        description="Maximum recursion depth.",
        min=0,
        default=12,
    )

    shrinkwrap: BoolProperty(name="Shrinkwrap", description="Shrinkwrap output to source mesh.", default=True)

    fill_mode: EnumProperty(
        name="Fill Mode",
        items=(
            ("FLOOD", "Flood", ""),
            ("SURFACE", "Surface", ""),
            ("RAYCAST", "Raycast", ""),
        ),
        default="SURFACE",
    )

    vertex_count: IntProperty(
        name="Vertex Count",
        description="Maximum number of vertices in the output hulls.",
        min=1,
        default=64,
    )

    asynchronous: BoolProperty(name="Asynchronous", description="Run V-HACD asynchronously.", default=True)

    edge_length: IntProperty(
        name="Edge Length",
        description="Minimum size of a voxel edge.",
        min=1,
        default=2,
    )

    split_hull: BoolProperty(
        name="Split Hull",
        description="Tries to find optimal split plane location.",
        default=True,
    )

    def draw(self, context, layout):
        col = layout.column()
        if self.version in {"VHACD4.1", "VHACD4"}:
            col.prop(self, "voxel_resolution")
            col.prop(self, "recursion_depth")
            col.prop(self, "output_hull")
            col.prop(self, "vertex_count")
            col.prop(self, "fill_mode")

            col = layout.column()
            col.prop(self, "shrinkwrap")
            col.prop(self, "asynchronous")
            col.prop(self, "split_hull")

            col = layout.column()
            col.prop(self, "edge_length")
            col.prop(self, "volume_error")
        else:
            col.prop(self, "resolution")
            col.prop(self, "depth")
            col.prop(self, "concavity")
            col.prop(self, "plane_downsample")
            col.prop(self, "hull_downsample")

            col = layout.column()
            col.prop(self, "alpha")
            col.prop(self, "beta")
            col.prop(self, "gamma")

            col = layout.column()
            col.prop(self, "normalize")
            col.prop(self, "shrinkwrap")

            col = layout.column()
            col.prop(self, "mode")
            col.prop(self, "hull_vertices")
            col.prop(self, "hull_volume")


class UNITY_AP_fbx(PropertyGroup):
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

    use_triangles: BoolProperty(name="Triangulate Faces", default=False)

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

    def draw(self, context, layout):
        col = layout.column()

        box = col.box()
        box.label(text=" Include")
        subcol = box.column()
        subcol.use_property_split = True
        row = subcol.row()
        subcol.prop(self, "object_types")
        subcol.prop(self, "use_custom_props")
        subcol.prop(self, "embed_textures")

        box = col.box()
        box.label(text=" Transform")
        subcol = box.column()
        subcol.use_property_split = True
        subcol.prop(self, "global_scale")
        subcol.prop(self, "apply_scale_options")
        subcol.prop(self, "axis_forward")
        subcol.prop(self, "axis_up")
        subcol.prop(self, "apply_unit_scale")
        subcol.prop(self, "use_space_transform")
        row = subcol.row()
        row.use_property_split = True
        row.prop(self, "bake_space_transform")
        row.label(text="", icon="ERROR")

        box = col.box()
        box.label(text=" Geometry")
        subcol = box.column()
        subcol.use_property_split = True
        subcol.prop(self, "mesh_smooth_type")
        subcol.prop(self, "use_subsurf")
        subcol.prop(self, "use_mesh_modifiers")
        subcol.prop(self, "use_mesh_edges")
        subcol.prop(self, "use_triangles")
        subcol.prop(self, "use_tspace")
        if bpy.app.version >= (3, 6, 0):
            subcol.prop(self, "colors_type")
            subcol.prop(self, "prioritize_active_color")

        box = col.box()
        box.label(text=" Armature")
        subcol = box.column()
        subcol.use_property_split = True
        subcol.prop(self, "primary_bone_axis")
        subcol.prop(self, "secondary_bone_axis")
        subcol.prop(self, "armature_nodetype")
        subcol.prop(self, "use_armature_deform_only")
        subcol.prop(self, "add_leaf_bones")

        box = col.box()
        box.prop(self, "bake_anim")
        if self.bake_anim:
            subcol = box.column()
            subcol.use_property_split = True
            subcol.prop(self, "bake_anim_use_all_bones")
            subcol.prop(self, "bake_anim_use_nla_strips")
            subcol.prop(self, "bake_anim_use_all_actions")
            subcol.prop(self, "bake_anim_force_startend_keying")
            subcol.prop(self, "bake_anim_step")
            subcol.prop(self, "bake_anim_simplify_factor")


class UNITY_AP_unity(PropertyGroup):
    object_collection: BoolProperty(
        name="Collection",
        description="Create collection for object's colliders and LODs",
        default=True,
    )

    collider: PointerProperty(type=UNITY_AP_collider)
    lod: PointerProperty(type=UNITY_AP_lod)
    vhacd: PointerProperty(type=UNITY_AP_vhacd)
    fbx: PointerProperty(type=UNITY_AP_fbx)


class UNITY_AP_preference(AddonPreferences):
    bl_idname = __package__

    prefs_tabs: EnumProperty(
        items=(
            ("GENERAL", "General", "General"),
            ("EXPORT", "Export", "Export"),
        ),
        default="GENERAL",
    )

    object_settings: BoolProperty(
        name="Object",
        default=False,
    )

    collider_settings: BoolProperty(
        name="Collider",
        default=False,
    )

    lod_settings: BoolProperty(
        name="LODs",
        default=False,
    )

    vhacd_settings: BoolProperty(
        name="V-HACD",
        default=False,
    )

    fbx_settings: BoolProperty(
        name="FBX Settings",
        default=False,
    )

    unity: PointerProperty(type=UNITY_AP_unity)

    def draw(self, context):
        layout = self.layout
        layout.use_property_decorate = False

        row = layout.row()
        row.prop(self, "prefs_tabs", expand=True)

        # General
        if self.prefs_tabs == "GENERAL":
            col = layout.column()

            box = col.box()
            row = box.row()
            row.alignment = "LEFT"
            row.prop(
                self,
                "object_settings",
                icon="DOWNARROW_HLT" if self.object_settings else "RIGHTARROW_THIN",
                emboss=False,
            )
            if self.object_settings:
                subcol = box.column()
                subcol.use_property_split = True
                subcol.prop(self.unity, "object_collection")

            box = col.box()
            row = box.row()
            row.alignment = "LEFT"
            row.prop(
                self,
                "collider_settings",
                icon="DOWNARROW_HLT" if self.collider_settings else "RIGHTARROW_THIN",
                emboss=False,
            )
            if self.collider_settings:
                self.unity.collider.draw(context, box)

            box = col.box()
            row = box.row()
            row.alignment = "LEFT"
            row.prop(
                self,
                "lod_settings",
                icon="DOWNARROW_HLT" if self.lod_settings else "RIGHTARROW_THIN",
                emboss=False,
            )
            if self.lod_settings:
                self.unity.lod.draw(context, box)

            if bpy.app.build_platform == b"Windows":
                box = col.box()
                row = box.row()
                row.alignment = "LEFT"
                row.prop(
                    self,
                    "vhacd_settings",
                    icon="DOWNARROW_HLT" if self.vhacd_settings else "RIGHTARROW_THIN",
                    emboss=False,
                )
                if self.vhacd_settings:
                    box.use_property_split = True
                    box.prop(self.unity.vhacd, "version")
                    self.unity.vhacd.draw(context, box)

        # Export
        elif self.prefs_tabs == "EXPORT":
            col = layout.column()
            box = col.box()
            row = box.row()
            row.alignment = "LEFT"
            row.prop(
                self,
                "fbx_settings",
                icon="DOWNARROW_HLT" if self.fbx_settings else "RIGHTARROW_THIN",
                emboss=False,
            )
            if self.fbx_settings:
                self.unity.fbx.draw(context, box)


classes = (
    UNITY_AP_collider,
    UNITY_AP_lod,
    UNITY_AP_vhacd,
    UNITY_AP_fbx,
    UNITY_AP_unity,
    UNITY_AP_preference,
)


register, unregister = bpy.utils.register_classes_factory(classes)
