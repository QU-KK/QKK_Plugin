from __future__ import annotations

from dataclasses import dataclass
import traceback

import bpy

from . import cage_session, properties
from .overlay_keys import overlay_settings_state as _overlay_settings_state


@dataclass(slots=True)
class PreviewProxyState:
    source_signature: tuple
    preview_object: object
    last_offset: float | None = None
    last_opacity: float | None = None


class CageVisualizationController:
    def __init__(
        self,
        *,
        constants_module,
        data_collection_fn,
        is_valid_object_fn,
        is_valid_mesh_fn,
        object_signature_fn,
        iter_valid_meshes_fn,
        preview_collection_name: str = "_FYR_BAKER_PREVIEW",
        preview_material_name: str = "_FYR_BAKER_PREVIEW_MAT",
        preview_modifier_name: str = "_FYR_BAKER_PREVIEW_SOLIDIFY",
    ) -> None:
        self._constants = constants_module
        self._data_collection = data_collection_fn
        self._is_valid_object = is_valid_object_fn
        self._is_valid_mesh = is_valid_mesh_fn
        self._object_signature = object_signature_fn
        self._iter_valid_meshes = iter_valid_meshes_fn
        self.preview_collection_name = preview_collection_name
        self.preview_material_name = preview_material_name
        self.preview_modifier_name = preview_modifier_name
        self.preview_hidden_state: dict[int, tuple[object, bool]] = {}
        self.preview_proxy_state: dict[int, PreviewProxyState] = {}

    def ensure_preview_collection(self, scene):
        collections = self._data_collection("collections")
        if collections is None:
            return None
        collection = collections.get(self.preview_collection_name)
        if collection is None:
            collection = collections.new(self.preview_collection_name)
        if scene.collection.children.get(collection.name) is None:
            try:
                scene.collection.children.link(collection)
            except RuntimeError:
                pass
        collection.hide_render = True
        return collection

    def ensure_preview_material(self):
        materials = self._data_collection("materials")
        if materials is None:
            return None
        material = materials.get(self.preview_material_name)
        if material is None:
            material = materials.new(self.preview_material_name)
        material.diffuse_color = (0.18, 0.88, 0.46, 0.42)
        return material

    def make_preview_proxy_name(self, source_object) -> str:
        return f"_MBPreview_{source_object.name}_{source_object.as_pointer()}"

    def iter_preview_proxy_objects(self):
        objects = self._data_collection("objects")
        if objects is None:
            return
        for obj in objects:
            try:
                if bool(obj.get("_master_baker_preview_proxy")) or str(getattr(obj, "name", "") or "").startswith("_MBPreview_"):
                    yield obj
            except Exception:
                continue

    def remove_preview_proxy_object(self, preview_object) -> None:
        if preview_object is None:
            return
        preview_mesh = getattr(preview_object, "data", None)
        objects = self._data_collection("objects")
        meshes = self._data_collection("meshes")
        if self._is_valid_object(preview_object):
            if objects is not None:
                try:
                    objects.remove(preview_object, do_unlink=True)
                except Exception:
                    pass
        if self._is_valid_mesh(preview_mesh) and getattr(preview_mesh, "users", 0) == 0 and meshes is not None:
            try:
                meshes.remove(preview_mesh)
            except Exception:
                pass

    def remove_preview_proxy_state(self, source_pointer: int) -> None:
        state = self.preview_proxy_state.pop(source_pointer, None)
        if state is None:
            return
        self.remove_preview_proxy_object(state.preview_object)

    def clear_preview_proxy_states(self, *, keep_pointers: set[int] | None = None) -> None:
        keep = keep_pointers or set()
        for source_pointer in list(self.preview_proxy_state.keys()):
            if source_pointer in keep:
                continue
            self.remove_preview_proxy_state(source_pointer)
        tracked_object_pointers = {
            state.preview_object.as_pointer()
            for state in self.preview_proxy_state.values()
            if self._is_valid_object(state.preview_object)
        }
        for preview_object in list(self.iter_preview_proxy_objects()):
            if self._is_valid_object(preview_object) and preview_object.as_pointer() in tracked_object_pointers:
                continue
            self.remove_preview_proxy_object(preview_object)

    @staticmethod
    def high_reference_native_preview_supported() -> bool:
        return False

    def high_reference_uses_native_preview(self, settings, group) -> bool:
        del settings, group
        return False

    def hide_source_object_for_preview(self, source_object) -> int | None:
        if not self._is_valid_object(source_object):
            return None
        try:
            source_pointer = int(source_object.as_pointer())
        except Exception:
            return None
        if source_pointer not in self.preview_hidden_state:
            try:
                self.preview_hidden_state[source_pointer] = (source_object, bool(source_object.hide_get()))
            except Exception:
                self.preview_hidden_state[source_pointer] = (source_object, False)
        try:
            source_object.hide_set(True)
        except Exception:
            pass
        return source_pointer

    def show_source_object_for_high_reference(self, source_object) -> int | None:
        if not self._is_valid_object(source_object):
            return None
        try:
            source_pointer = int(source_object.as_pointer())
        except Exception:
            return None
        if source_pointer not in self.preview_hidden_state:
            try:
                self.preview_hidden_state[source_pointer] = (source_object, bool(source_object.hide_get()))
            except Exception:
                self.preview_hidden_state[source_pointer] = (source_object, False)
        try:
            source_object.hide_set(False)
        except Exception:
            pass
        return source_pointer

    def sync_high_reference_preview_objects(self, scene, settings, group) -> set[int]:
        del scene
        if not self.high_reference_uses_native_preview(settings, group):
            return set()

        visible_source_pointers: set[int] = set()
        for source_object in self._iter_valid_meshes(properties.effective_high_mesh_slots(group)):
            visible_pointer = self.show_source_object_for_high_reference(source_object)
            if visible_pointer is not None:
                visible_source_pointers.add(visible_pointer)

        return visible_source_pointers

    def build_preview_proxy_state(self, scene, source_object):
        objects = self._data_collection("objects")
        meshes = self._data_collection("meshes")
        if objects is None or meshes is None:
            raise RuntimeError("Preview cage data is not available in this Blender context yet")
        depsgraph = bpy.context.evaluated_depsgraph_get()
        evaluated_object = source_object.evaluated_get(depsgraph)
        try:
            preview_mesh = bpy.data.meshes.new_from_object(
                evaluated_object,
                preserve_all_data_layers=False,
                depsgraph=depsgraph,
            )
        except TypeError:
            preview_mesh = bpy.data.meshes.new_from_object(evaluated_object, depsgraph=depsgraph)
        if preview_mesh is None:
            raise RuntimeError(f"Unable to create preview cage mesh from '{source_object.name}'")
        preview_mesh.name = f"{self.make_preview_proxy_name(source_object)}_mesh"
        try:
            return self._finish_preview_proxy(scene, source_object, objects, preview_mesh)
        except BaseException:
            # Anything raising below (missing preview collection, objects.new, the
            # modifier) used to orphan a full mesh copy of the low poly per failed
            # sync; release what was created before re-raising.
            try:
                proxy = bpy.data.objects.get(self.make_preview_proxy_name(source_object))
                if proxy is not None and proxy.data == preview_mesh:
                    bpy.data.objects.remove(proxy, do_unlink=True)
            except Exception:
                pass
            try:
                if preview_mesh.users == 0:
                    bpy.data.meshes.remove(preview_mesh)
            except Exception:
                pass
            raise

    def _finish_preview_proxy(self, scene, source_object, objects, preview_mesh):
        preview_object = objects.new(self.make_preview_proxy_name(source_object), preview_mesh)
        preview_object.matrix_world = source_object.matrix_world.copy()
        preview_object.hide_render = True
        preview_object.display_type = "SOLID"
        preview_object.show_wire = False
        if hasattr(preview_object, "show_transparent"):
            preview_object.show_transparent = True
        if hasattr(preview_object, "show_in_front"):
            preview_object.show_in_front = False
        preview_object.hide_select = True
        preview_object.color = (0.18, 0.88, 0.46, 0.38)
        preview_object["_master_baker_preview_proxy"] = True
        preview_object["_master_baker_preview_source"] = source_object.name
        preview_material = self.ensure_preview_material()
        if preview_material is not None:
            if len(preview_mesh.materials) == 0:
                preview_mesh.materials.append(preview_material)
            else:
                for i in range(len(preview_mesh.materials)):
                    preview_mesh.materials[i] = preview_material
        modifier = preview_object.modifiers.new(name=self.preview_modifier_name, type="SOLIDIFY")
        modifier.thickness = 0.0
        if hasattr(modifier, "offset"):
            modifier.offset = 1.0
        if hasattr(modifier, "use_even_offset"):
            modifier.use_even_offset = True
        if hasattr(modifier, "use_quality_normals"):
            modifier.use_quality_normals = True
        if hasattr(modifier, "use_rim"):
            modifier.use_rim = False
        preview_collection = self.ensure_preview_collection(scene)
        if preview_collection is None:
            raise RuntimeError("Preview cage collection is not available in this Blender context yet")
        preview_collection.objects.link(preview_object)
        return PreviewProxyState(
            source_signature=self._object_signature(source_object),
            preview_object=preview_object,
        )

    def update_preview_proxy_state(self, state: PreviewProxyState, offset: float, opacity: float) -> None:
        preview_object = state.preview_object
        if not self._is_valid_object(preview_object):
            return
        preview_mesh = getattr(preview_object, "data", None)
        if not self._is_valid_mesh(preview_mesh):
            return

        if state.last_offset == float(offset) and state.last_opacity == float(opacity):
            return

        preview_object.hide_set(False)
        preview_object.display_type = "SOLID"
        preview_object.show_wire = False
        if hasattr(preview_object, "show_transparent"):
            preview_object.show_transparent = True
        if hasattr(preview_object, "show_in_front"):
            preview_object.show_in_front = False
        preview_object.color = (0.18, 0.88, 0.46, max(0.10, min(1.0, 0.42 * float(opacity))))
        preview_material = self.ensure_preview_material()
        if preview_material is not None:
            preview_material.diffuse_color = (0.18, 0.88, 0.46, max(0.10, min(1.0, 0.42 * float(opacity))))
        modifier = preview_object.modifiers.get(self.preview_modifier_name)
        if modifier is not None:
            modifier.thickness = float(offset)
        state.last_offset = float(offset)
        state.last_opacity = float(opacity)

    def _apply_generated_custom_cage_visibility(self, group, overlay_state, *, visible: bool) -> None:
        custom_cage = getattr(group, "custom_cage", None)
        if not self._is_valid_object(custom_cage):
            return
        if not bool(custom_cage.get("_master_baker_generated_cage")):
            return

        if visible and group.cage_mode == self._constants.CAGE_MODE_CUSTOM:
            show_surface = bool(getattr(overlay_state, "show_cage_surface", True))
            show_wireframe = bool(getattr(overlay_state, "show_cage_wireframe", True))
            surface_rgb = tuple(getattr(overlay_state, "cage_surface_color", (0.18, 0.88, 0.46)))
            wireframe_rgb = tuple(getattr(overlay_state, "cage_wireframe_color", (0.32, 1.0, 0.62)))
            surface_alpha = max(
                0.0,
                min(
                    1.0,
                    float(getattr(overlay_state, "cage_opacity", 1.0)) * float(getattr(overlay_state, "cage_surface_opacity", 0.42)),
                ),
            )
            wireframe_alpha = max(
                0.0,
                min(
                    1.0,
                    float(getattr(overlay_state, "cage_opacity", 1.0)) * float(getattr(overlay_state, "cage_wireframe_opacity", 0.38)),
                ),
            )
            if not ((show_surface and surface_alpha > 0.0) or (show_wireframe and wireframe_alpha > 0.0)):
                custom_cage.hide_set(True)
                return
            custom_cage.hide_set(False)
            custom_cage.display_type = "SOLID" if show_surface and surface_alpha > 0.0 else "WIRE"
            custom_cage.show_wire = bool(show_wireframe and wireframe_alpha > 0.0)
            if hasattr(custom_cage, "show_transparent"):
                custom_cage.show_transparent = bool(show_surface and surface_alpha > 0.0)
            if hasattr(custom_cage, "show_in_front"):
                custom_cage.show_in_front = False
            custom_cage.color = (
                float(surface_rgb[0] if show_surface and surface_alpha > 0.0 else wireframe_rgb[0]),
                float(surface_rgb[1] if show_surface and surface_alpha > 0.0 else wireframe_rgb[1]),
                float(surface_rgb[2] if show_surface and surface_alpha > 0.0 else wireframe_rgb[2]),
                max(0.10, min(1.0, surface_alpha if show_surface and surface_alpha > 0.0 else wireframe_alpha)),
            )
        else:
            custom_cage.hide_set(True)

    def sync_generated_custom_cage_visibility(self, group, settings) -> None:
        overlay_state = _overlay_settings_state(settings)
        context = getattr(bpy, "context", None)
        scene = getattr(context, "scene", None)
        preview_targets = []
        if scene is not None:
            preview_targets = cage_session.resolve_preview_targets(scene, context=context)[3]
        target_groups = [preview_target.group for preview_target in preview_targets]
        if not target_groups and group is not None and not bool(getattr(group, "cage_overlay_hidden", False)):
            target_groups = [group]

        candidate_groups = []
        # Compared through pointer sets: the pairwise any() scans this replaces were
        # O(G^2) wrapper-pointer reads (0.18 s a call at 300 groups, twice per bake).
        seen_pointers: set[int] = set()
        for project in getattr(settings, "projects", []):
            for candidate_group in getattr(project, "groups", []):
                # `is` on RNA wrappers is never true - Blender hands out a fresh wrapper
                # per access - so this comparison must go through the pointer. With `is`
                # the visible= below was always False: a cage the artist had just
                # generated was hidden on the next preview sync, un-hiding it by hand
                # was undone on the one after, and the whole colour/wireframe branch of
                # _apply_generated_custom_cage_visibility never ran at all.
                if candidate_group is not None:
                    pointer = cage_session._object_pointer(candidate_group)
                    if pointer in seen_pointers:
                        continue
                    seen_pointers.add(pointer)
                candidate_groups.append(candidate_group)
        if not candidate_groups and group is not None:
            candidate_groups = [group]

        target_pointers = {
            cage_session._object_pointer(target_group) for target_group in target_groups if target_group is not None
        }
        for candidate_group in candidate_groups:
            self._apply_generated_custom_cage_visibility(
                candidate_group,
                overlay_state,
                visible=candidate_group is not None
                and cage_session._object_pointer(candidate_group) in target_pointers,
            )

    def sync_preview_proxy_objects(self, scene, settings, group) -> None:
        overlay_state = _overlay_settings_state(settings)
        if group is None or not bool(getattr(overlay_state, "show_cage_overlay", False)) or group.cage_mode in (self._constants.CAGE_MODE_CUSTOM, self._constants.CAGE_MODE_AUTOMATIC, self._constants.CAGE_MODE_DISTANCE):
            self.clear_preview_proxy_states()
            return

        opacity = float(getattr(overlay_state, "cage_opacity", 1.0))
        keep_pointers: set[int] = set()
        for source_object in self._iter_valid_meshes(group.low_meshes):
            source_pointer = source_object.as_pointer()
            keep_pointers.add(source_pointer)
            source_signature = self._object_signature(source_object)
            state = self.preview_proxy_state.get(source_pointer)
            if state is None or not self._is_valid_object(state.preview_object) or state.source_signature != source_signature:
                self.remove_preview_proxy_state(source_pointer)
                state = self.build_preview_proxy_state(scene, source_object)
                self.preview_proxy_state[source_pointer] = state
            state.source_signature = source_signature
            state.preview_object.matrix_world = source_object.matrix_world.copy()
            self.update_preview_proxy_state(state, float(group.cage_offset), opacity)

        self.clear_preview_proxy_states(keep_pointers=keep_pointers)

    def restore_preview_hidden_objects(self, *, keep_keys: set[int] | None = None) -> None:
        keys_to_keep = keep_keys or set()
        for pointer, state in list(self.preview_hidden_state.items()):
            if pointer in keys_to_keep:
                continue
            obj, previous_hidden = state
            if self._is_valid_object(obj):
                try:
                    obj.hide_set(bool(previous_hidden))
                except Exception:
                    pass
            self.preview_hidden_state.pop(pointer, None)

    def sync_heatmap_preview(self, scene, settings, group) -> None:
        del scene, settings, group
        self.clear_heatmap_preview()

    def clear_heatmap_preview(self) -> None:
        try:
            from . import heatmap_preview

            heatmap_preview.clear_heatmap_preview()
        except Exception:
            traceback.print_exc()

    def cleanup_preview_runtime(self) -> None:
        self.restore_preview_hidden_objects()
        self.clear_preview_proxy_states()
        self.clear_heatmap_preview()

    def sync_preview_visibility_now(self, scene=None, *, high_reference_sync_fn=None) -> None:
        if scene is None:
            scene = getattr(bpy.context, "scene", None)
        settings = getattr(scene, "fyr_baker_settings", None) if scene is not None else None
        if settings is None:
            self.restore_preview_hidden_objects()
            self.clear_preview_proxy_states()
            self.clear_heatmap_preview()
            return
        if cage_session.preview_suppressed_for_context(getattr(bpy, "context", None)):
            self.restore_preview_hidden_objects()
            self.clear_preview_proxy_states()
            self.clear_heatmap_preview()
            return
        _settings, project, group = cage_session.resolve_project_group(scene)
        if group is None:
            self.restore_preview_hidden_objects()
            self.clear_preview_proxy_states()
            self.clear_heatmap_preview()
            return
        overlay_state = _overlay_settings_state(settings)
        if bool(getattr(overlay_state, "show_cage_overlay", False)):
            keep_hidden_keys: set[int] = set()
            self.sync_generated_custom_cage_visibility(group, settings)
            if high_reference_sync_fn is not None:
                high_reference_sync_fn()
            keep_hidden_keys.update(self.sync_high_reference_preview_objects(scene, settings, group))
            self.restore_preview_hidden_objects(keep_keys=keep_hidden_keys)
            self.clear_preview_proxy_states()
        else:
            self.restore_preview_hidden_objects()
            self.clear_preview_proxy_states()
        self.sync_heatmap_preview(scene, settings, group)


def register() -> None:
    return None


def unregister() -> None:
    return None
