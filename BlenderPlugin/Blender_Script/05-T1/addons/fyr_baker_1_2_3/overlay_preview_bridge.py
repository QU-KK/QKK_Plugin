from __future__ import annotations

from . import cage_visualization, properties
from .overlay_preview_visibility import PreviewVisibilityDeps


def create_cage_visualization_controller(
    *,
    constants_module,
    data_collection_fn,
    is_valid_object_fn,
    is_valid_mesh_fn,
    object_signature_fn,
    iter_valid_meshes_fn,
    preview_collection_name: str,
    preview_material_name: str,
    preview_modifier_name: str,
):
    return cage_visualization.CageVisualizationController(
        constants_module=constants_module,
        data_collection_fn=data_collection_fn,
        is_valid_object_fn=is_valid_object_fn,
        is_valid_mesh_fn=is_valid_mesh_fn,
        object_signature_fn=object_signature_fn,
        iter_valid_meshes_fn=iter_valid_meshes_fn,
        preview_collection_name=preview_collection_name,
        preview_material_name=preview_material_name,
        preview_modifier_name=preview_modifier_name,
    )


def high_reference_uses_native_preview(high_reference_native_preview_supported_fn, settings, group) -> bool:
    del high_reference_native_preview_supported_fn, settings, group
    return False


def build_preview_visibility_deps(
    *,
    preview_suppressed_for_context_fn,
    resolve_project_group_fn,
    restore_preview_hidden_objects_fn,
    clear_preview_proxy_states_fn,
    clear_heatmap_preview_fn,
    sync_generated_custom_cage_visibility_fn,
    reset_high_reference_runtime_fn,
    sync_high_reference_preview_objects_fn,
    sync_preview_proxy_objects_fn,
    sync_heatmap_preview_fn,
) -> PreviewVisibilityDeps:
    return PreviewVisibilityDeps(
        preview_suppressed_for_context=preview_suppressed_for_context_fn,
        resolve_project_group=resolve_project_group_fn,
        restore_preview_hidden_objects=restore_preview_hidden_objects_fn,
        clear_preview_proxy_states=clear_preview_proxy_states_fn,
        clear_heatmap_preview=clear_heatmap_preview_fn,
        sync_generated_custom_cage_visibility=sync_generated_custom_cage_visibility_fn,
        reset_high_reference_runtime=reset_high_reference_runtime_fn,
        sync_high_reference_preview_objects=sync_high_reference_preview_objects_fn,
        sync_preview_proxy_objects=sync_preview_proxy_objects_fn,
        sync_heatmap_preview=sync_heatmap_preview_fn,
    )


def apply_object_override_material(obj, material) -> bool:
    if obj is None or material is None:
        return False
    applied = False
    for slot in list(getattr(obj, "material_slots", []) or []):
        try:
            slot.link = "OBJECT"
        except Exception:
            pass
        try:
            slot.material = material
            applied = True
        except Exception:
            pass
    if applied:
        return True
    try:
        obj.active_material = material
        return True
    except Exception:
        return False
