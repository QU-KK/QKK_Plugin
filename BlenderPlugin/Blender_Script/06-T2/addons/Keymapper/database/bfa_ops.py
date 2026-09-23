"""
bfa_ops.py
Tracks operators that are exclusive to BForArtists and should be hidden
when running in standard Blender.

Friendly names and raw IDs are now sourced directly from RNA at runtime.
"""

import bpy

# Operators that only exist in BForArtists builds.
# These are hidden in the operator browser when running standard Blender.
BFA_ONLY_OPS: set[str] = {
    "armature.delete",
    "bfa.reset_animation",
    "bfa.reset_edit",
    "bfa.reset_files",
    "bfa.reset_image",
    "bfa.reset_meshedit",
    "bfa.reset_misc",
    "bfa.reset_primitives",
    "bfa.reset_toolbar",
    "bfa.reset_toolbar_animation",
    "bfa.reset_toolbar_edit",
    "bfa.reset_toolbar_files",
    "bfa.reset_toolbar_image",
    "bfa.reset_toolbar_meshedit",
    "bfa.reset_toolbar_misc",
    "bfa.reset_toolbar_primitives",
    "bfa.reset_toolbar_tools",
    "bfa.reset_tools",
    "bfa.reset_topbar",
    "gpencil.annotation_active_frame_delete",
    "gpencil.annotation_add",
    "mesh.dissolve_contextual_bfa",
    "mesh.mark_seam",
    "nla.duplicate",
    "node.clear_viewer_border",
    "node.delete_copy_reconnect",
    "node.join",
    "node.viewer_border",
    "object.duplicate",
    "object.gpencil_modifier_apply",
    "object.gpencil_modifier_copy",
    "object.gpencil_modifier_remove",
    "object.link_to_collection",
    "object.move_to_collection",
    "outliner.collection_objects_select",
    "outliner.id_operation",
    "poselib.apply_pose_asset",
    "poselib.blend_pose_asset",
    "scene.cic_create_gameisocam",
    "scene.cic_create_groundplane",
    "scene.cic_create_trueisocam",
    "uv.clear_seam",
    "uv.unwrap",
    "wm.console_toggle",
    "wm.read_homefile",
}


def is_bfa_only(operator_id: str) -> bool:
    """Return True if this operator only exists in BForArtists."""
    return operator_id in BFA_ONLY_OPS


def get_friendly_name(operator_id: str) -> str | None:
    """Return the operator's friendly name from RNA (bl_label).
    Returns None if the operator is not found.
    """
    try:
        module, func = operator_id.split(".", 1)
        op_fn = getattr(getattr(bpy.ops, module), func)
        name = op_fn.get_rna_type().name
        if name == "(De)select All":
            name = "Select / Deselect All"
        from .friendly_ops import qualify_op_label
        return qualify_op_label(operator_id, name)
    except Exception:
        return None
