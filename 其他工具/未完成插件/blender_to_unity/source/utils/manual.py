import bpy


manual = (
    # tool
    ("bpy.ops.unity.rename", "tool.html#rename"),
    # collider
    ("bpy.ops.unity.collider_box", "collider.html#box"),
    ("bpy.ops.unity.collider_capsule", "collider.html#capsule"),
    ("bpy.ops.unity.collider_sphere", "collider.html#sphere"),
    ("bpy.ops.unity.collider_cylinder", "collider.html#cylinder"),
    ("bpy.ops.unity.collider_convex", "collider.html#convex"),
    ("bpy.ops.unity.collider_convex_vhacd", "collider.html#convex"),
    # lod
    ("bpy.ops.unity.lod_add", "lod.html#create"),
    ("bpy.ops.unity.lod_create", "lod.html#update"),
    ("bpy.ops.unity.lod_preset", "lod.html#preset"),
    # export
    ("bpy.ops.unity.unity_path_add", "export.html#path-add"),
    ("bpy.ops.unity.unity_path_remove", "export.html#path-remove"),
    ("bpy.ops.unity.disk_path_add", "export.html#path-add"),
    ("bpy.ops.unity.disk_path_remove", "export.html#path-remove"),
    ("bpy.ops.unity.path_load", "export.html#path-add"),
    ("bpy.ops.unity.export_fbx", "export.html"),
)


def manual_hook():
    return ("https://b3dhub.github.io/blender-to-unity-docs/", manual)


def register():
    bpy.utils.register_manual_map(manual_hook)


def unregister():
    bpy.utils.unregister_manual_map(manual_hook)
