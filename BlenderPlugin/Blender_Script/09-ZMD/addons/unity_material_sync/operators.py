import bpy

from . import material_sync, template_material, unity_client, uv_utils


class MATERIAL_OT_sync_from_unity(bpy.types.Operator):
    bl_idname = "material.sync_from_unity"
    bl_label = "从 Unity 同步材质"
    bl_description = "同步选中 Mesh 或其子层级中的 Unity 材质"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        obj = context.object
        return bool(_find_syncable_meshes(obj))

    def execute(self, context):
        _progress_begin(context, 1)
        _progress_update(context, 0)
        _status_update(context, 0, 1, "准备校验")

        obj = context.object
        if obj is None:
            self.report({"ERROR"}, "请先选择一个 Mesh 模型或包含 Mesh 的父级对象")
            _progress_end(context)
            _status_clear(context)
            return {"CANCELLED"}

        try:
            targets = _build_sync_targets(obj)
        except Exception as exc:
            self.report({"ERROR"}, str(exc))
            _progress_end(context)
            _status_clear(context)
            return {"CANCELLED"}

        if not targets:
            self.report({"ERROR"}, "选中对象及其子层级没有可同步的 Mesh")
            _progress_end(context)
            _status_clear(context)
            return {"CANCELLED"}

        prefs = _addon_preferences(context)
        progress_total = sum(len(target.material_slots) + 1 for target in targets)
        first_prefab_name = targets[0].prefab_name
        _progress_end(context)
        _progress_begin(context, progress_total)
        _progress_update(context, 0)
        _status_update(context, 0, progress_total, f"准备查询 Unity prefab：{first_prefab_name}")
        nats_url = (
            prefs.endpoint
            if prefs and prefs.endpoint
            else unity_client.DEFAULT_NATS_URL
        )
        timeout = prefs.timeout if prefs else unity_client.DEFAULT_TIMEOUT
        self._sync_session = _SyncSession(
            targets=targets,
            nats_url=nats_url,
            timeout=timeout,
            timer=_add_modal_timer(context, self),
        )
        return {"RUNNING_MODAL"}

    def modal(self, context, event):
        if getattr(event, "type", None) != "TIMER":
            return {"PASS_THROUGH"}

        session = getattr(self, "_sync_session", None)
        if session is None:
            return {"CANCELLED"}

        if session.phase == "query":
            return self._query_material_infos_step(context, session)
        if session.phase == "materials":
            return self._sync_next_material_step(context, session)

        return {"CANCELLED"}

    def _query_material_infos_step(self, context, session):
        target = session.current_target
        prefab_candidates = _prefab_query_candidates_for_names(target.prefab_names)
        _status_update(
            context,
            session.completed_steps,
            session.progress_total,
            f"查询 Unity prefab：{target.prefab_name}",
        )
        cached_material_infos = _cached_material_infos(session, prefab_candidates)
        if cached_material_infos is not None:
            session.material_infos = cached_material_infos
            session.completed_steps += 1
            _progress_update(context, session.completed_steps)
            _status_update(context, session.completed_steps, session.progress_total, "已获取 Unity 材质数据")
            session.phase = "materials"
            return {"RUNNING_MODAL"}

        if prefab_candidates and all(candidate in session.failed_prefabs for candidate in prefab_candidates):
            session.completed_steps += 1
            _progress_update(context, session.completed_steps)
            if session.advance_target():
                return {"RUNNING_MODAL"}
            return self._finish_sync(context, session)

        try:
            session.material_infos = _fetch_material_infos_with_prefab_candidates(
                prefab_candidates,
                nats_url=session.nats_url,
                timeout=session.timeout,
            )
        except Exception as exc:
            failure_message = f"查询 prefab“{target.prefab_name}”材质失败：{exc}"
            for candidate in prefab_candidates:
                session.failed_prefabs[candidate] = failure_message
            session.failure_messages.append(failure_message)
            self.report({"WARNING"}, failure_message)
            session.warning_count += 1
            session.completed_steps += 1
            _progress_update(context, session.completed_steps)
            if session.advance_target():
                return {"RUNNING_MODAL"}
            return self._finish_sync(context, session)

        for candidate in prefab_candidates:
            session.prefab_info_cache[candidate] = session.material_infos
        session.completed_steps += 1
        _progress_update(context, session.completed_steps)
        _status_update(context, session.completed_steps, session.progress_total, "已获取 Unity 材质数据")
        session.phase = "materials"
        return {"RUNNING_MODAL"}

    def _sync_next_material_step(self, context, session):
        material_index = session.material_index
        target = session.current_target
        slot_target = target.material_slots[material_index]
        slot = slot_target.slot
        source_material_name = slot_target.source_material_name
        if session.is_material_datablock_synced(slot_target.original_material):
            session.skipped_shared_material_count += 1
            return self._advance_material_step(context, session)

        _status_update(
            context,
            session.completed_steps,
            session.progress_total,
            f"同步材质 {source_material_name}",
        )
        try:
            material_data = unity_client.fetch_material(
                source_material_name,
                material_infos=session.material_infos,
                material_index=material_index,
            )
            target_material_name = _target_material_name_for_material_data(
                slot_target,
                material_data,
            )
            material = template_material.ensure_template_material_for_slot(
                slot,
                target_material_name,
            )
            result = material_sync.apply_material_data(material, material_data)
        except Exception as exc:
            failure_message = f"同步材质“{source_material_name}”失败：{exc}"
            session.failure_messages.append(failure_message)
            self.report({"WARNING"}, failure_message)
            session.warning_count += 1
        else:
            session.mark_material_datablock_synced(slot_target.original_material or material)
            session.synced_count += 1
            session.warning_count += len(result.warnings)
            for warning in result.warnings:
                self.report({"WARNING"}, warning)
        return self._advance_material_step(context, session)

    def _advance_material_step(self, context, session):
        target = session.current_target
        session.material_index += 1
        session.completed_steps += 1
        _progress_update(context, session.completed_steps)
        if session.material_index < len(target.material_slots):
            return {"RUNNING_MODAL"}

        if session.advance_target():
            return {"RUNNING_MODAL"}
        return self._finish_sync(context, session)

    def _finish_sync(self, context, session):
        self._clear_sync_session(context, session)

        if session.synced_count == 0:
            message = _format_no_material_synced_message(session)
            self.report({"ERROR"}, message)
            _show_message_popup(
                context,
                "Unity 材质同步失败",
                _format_failure_popup_lines(session, message),
                icon="ERROR",
            )
            return {"CANCELLED"}

        uv_message = ""
        if session.renamed_uv_count:
            uv_message = f"，已规范 {session.renamed_uv_count} 个 UV 通道"

        if session.warning_count:
            message = f"已同步 {session.synced_count} 个材质{uv_message}，包含 {session.warning_count} 条警告"
        else:
            message = f"已同步 {session.synced_count} 个材质{uv_message}"
        self.report({"INFO"}, message)
        _show_message_popup(context, "Unity 材质同步完成", [message], icon="INFO")

        return {"FINISHED"}

    def _clear_sync_session(self, context, session):
        _progress_end(context)
        _remove_modal_timer(context, session.timer)
        _status_clear(context)
        self._sync_session = None


class _SyncSession:
    def __init__(self, targets, nats_url, timeout, timer):
        self.targets = targets
        self.nats_url = nats_url
        self.timeout = timeout
        self.timer = timer
        self.progress_total = sum(len(target.material_slots) + 1 for target in targets)
        self.phase = "query"
        self.material_infos = None
        self.target_index = 0
        self.material_index = 0
        self.completed_steps = 0
        self.synced_count = 0
        self.warning_count = 0
        self.failure_messages = []
        self.renamed_uv_count = sum(len(target.renamed_uvs) for target in targets)
        self.prefab_info_cache = {}
        self.failed_prefabs = {}
        self.synced_material_datablock_ids = set()
        self.skipped_shared_material_count = 0

    @property
    def current_target(self):
        return self.targets[self.target_index]

    def advance_target(self):
        self.target_index += 1
        if self.target_index >= len(self.targets):
            return False
        self.material_infos = None
        self.material_index = 0
        self.phase = "query"
        return True

    def is_material_datablock_synced(self, material):
        if material is None:
            return False
        return id(material) in self.synced_material_datablock_ids

    def mark_material_datablock_synced(self, material):
        if material is None:
            return
        self.synced_material_datablock_ids.add(id(material))


class _SyncTarget:
    def __init__(self, obj, material_slots, renamed_uvs, prefab_names):
        self.obj = obj
        self.material_slots = material_slots
        self.renamed_uvs = renamed_uvs
        self.prefab_names = prefab_names
        self.prefab_name = prefab_names[0]


class _MaterialSlotTarget:
    def __init__(self, slot, source_material_name):
        self.slot = slot
        self.original_material = getattr(slot, "material", None)
        self.source_material_name = source_material_name
        self.target_material_name = _material_base_name(source_material_name)


def _build_sync_targets(obj):
    if getattr(obj, "type", None) == "MESH":
        if _is_shadow_proxy_mesh(obj):
            _hide_object(obj)
            return []
        return [_build_sync_target(obj)]

    targets = []
    for candidate, ancestors in _iter_descendants_with_ancestors(obj):
        if _is_shadow_proxy_mesh(candidate):
            _hide_object(candidate)
            continue
        if _is_syncable_mesh(candidate):
            targets.append(_build_sync_target(candidate, ancestors=ancestors))
    return targets


def _fetch_material_infos_with_prefab_candidates(prefab_names, nats_url, timeout):
    errors = []
    candidates = _prefab_query_candidates_for_names(prefab_names)
    for candidate in candidates:
        try:
            return unity_client.fetch_material_infos_for_prefab(
                candidate,
                nats_url=nats_url,
                timeout=timeout,
            )
        except Exception as exc:
            errors.append((candidate, exc))
    if not errors:
        raise unity_client.UnityClientError(f"没有可查询的 prefab 名：{prefab_names}")
    tried = "、".join(candidate for candidate, _exc in errors)
    last_error = errors[-1][1]
    raise unity_client.UnityClientError(f"已尝试 {tried}，均失败；最后错误：{last_error}") from last_error


def _prefab_query_candidates_for_names(prefab_names):
    candidates = []
    for prefab_name in _as_list(prefab_names):
        for candidate in unity_client.prefab_name_query_candidates(prefab_name):
            _append_unique(candidates, candidate)
    return candidates


def _cached_material_infos(session, candidates):
    for candidate in candidates:
        if candidate in session.prefab_info_cache:
            return session.prefab_info_cache[candidate]
    return None


def _build_sync_target(obj, ancestors=()):
    material_slots = _material_slot_targets_with_material(obj)
    if not material_slots:
        raise unity_client.UnityClientError("选中模型没有可同步的材质槽")

    unity_client.validate_lod_model_name(obj.name)
    prefab_names = _prefab_names_for_mesh(obj, ancestors)
    renamed_uvs = uv_utils.ensure_unity_uv_names(obj)
    return _SyncTarget(obj, material_slots, renamed_uvs, prefab_names)


def _find_syncable_meshes(obj):
    if obj is None:
        return []

    if getattr(obj, "type", None) == "MESH":
        if _is_shadow_proxy_mesh(obj):
            return []
        return [obj] if _is_syncable_mesh(obj) else []

    return [
        candidate for candidate in _iter_descendants(obj)
        if not _is_shadow_proxy_mesh(candidate) and _is_syncable_mesh(candidate)
    ]


def _is_syncable_mesh(obj):
    if getattr(obj, "type", None) != "MESH":
        return False
    if not _material_slots_with_material(obj):
        return False
    try:
        unity_client.validate_lod_model_name(obj.name)
    except Exception:
        return False
    return True


def _material_slot_targets_with_material(obj):
    return [
        _MaterialSlotTarget(slot, getattr(slot.material, "name", ""))
        for slot in _material_slots_with_material(obj)
    ]


def _target_material_name_for_material_data(slot_target, material_data):
    unity_material_name = ""
    if isinstance(material_data, dict):
        unity_material_name = material_data.get("name") or material_data.get("material_name") or ""
    if not unity_material_name:
        return slot_target.target_material_name

    source_match_name = unity_client.material_match_name(slot_target.source_material_name)
    unity_match_name = unity_client.material_match_name(unity_material_name)
    if unity_match_name and unity_match_name != source_match_name:
        return _material_base_name(unity_material_name)
    return slot_target.target_material_name


def _reassign_scene_slots_from_old_material(context, target, old_material, new_material):
    if old_material is None or new_material is None or old_material is new_material:
        return

    for obj in _iter_scene_mesh_objects(context):
        if obj is target.obj:
            continue
        for slot in getattr(obj, "material_slots", []):
            if getattr(slot, "material", None) is old_material:
                slot.material = new_material


def _iter_scene_mesh_objects(context):
    scene = getattr(context, "scene", None)
    objects = getattr(scene, "objects", None)
    if objects is None:
        return []
    return [
        obj for obj in objects
        if getattr(obj, "type", None) == "MESH"
    ]


def _is_shadow_proxy_mesh(obj):
    if getattr(obj, "type", None) != "MESH":
        return False
    return str(getattr(obj, "name", "")).lower().endswith("_shadowproxy")


def _hide_object(obj):
    if hasattr(obj, "hide_viewport"):
        obj.hide_viewport = True
    if hasattr(obj, "hide_render"):
        obj.hide_render = True
    hide_set = getattr(obj, "hide_set", None)
    if callable(hide_set):
        hide_set(True)


def _material_slots_with_material(obj):
    return [
        slot for slot in getattr(obj, "material_slots", [])
        if getattr(slot, "material", None) is not None
    ]


def _iter_descendants(obj):
    for child in getattr(obj, "children", []):
        yield child
        yield from _iter_descendants(child)


def _iter_descendants_with_ancestors(obj, ancestors=()):
    for child in getattr(obj, "children", []):
        child_ancestors = ancestors + (obj,)
        yield child, child_ancestors
        yield from _iter_descendants_with_ancestors(child, child_ancestors)


def _prefab_names_for_mesh(obj, ancestors=()):
    names = []
    parent_prefab = _nearest_prefab_ancestor_name(ancestors)
    if parent_prefab:
        _append_unique(names, parent_prefab)
    mesh_prefab = unity_client.prefab_name_from_model_name(obj.name)
    _append_unique(names, mesh_prefab)
    return names


def _nearest_prefab_ancestor_name(ancestors):
    search_ancestors = ancestors[1:] if ancestors else ancestors
    for ancestor in reversed(search_ancestors):
        name = _object_name_without_blender_duplicate_suffix(getattr(ancestor, "name", ""))
        if name.startswith("P_"):
            return name
    return ""


def _object_name_without_blender_duplicate_suffix(name):
    return unity_client.BLENDER_DUPLICATE_SUFFIX_RE.sub("", name)


def _material_base_name(name):
    return unity_client.BLENDER_DUPLICATE_SUFFIX_RE.sub("", str(name))


def _as_list(value):
    if isinstance(value, (list, tuple)):
        return value
    return [value]


def _append_unique(values, value):
    if value and value not in values:
        values.append(value)


def _format_no_material_synced_message(session):
    target_count = len(session.targets)
    failed_prefab_count = len(session.failed_prefabs)
    failed_material_count = len(session.failure_messages) - failed_prefab_count
    parts = [
        "没有材质被同步",
        f"已尝试 {target_count} 个对象",
    ]
    if failed_prefab_count:
        parts.append(f"{failed_prefab_count} 个 prefab 查询失败")
    if failed_material_count > 0:
        parts.append(f"{failed_material_count} 个材质同步失败")
    if not session.failure_messages:
        parts.append("没有可用的失败详情")
    return "，".join(parts)


def _format_failure_popup_lines(session, summary):
    lines = [summary]
    if session.failure_messages:
        lines.append("失败详情：")
        lines.extend(session.failure_messages[:5])
        remaining = len(session.failure_messages) - 5
        if remaining > 0:
            lines.append(f"还有 {remaining} 条失败详情，请在 Info 面板查看。")
    return lines


def _addon_preferences(context):
    addon = context.preferences.addons.get(__package__)
    if addon is None:
        return None
    return addon.preferences


def _progress_begin(context, total):
    window_manager = getattr(context, "window_manager", None)
    if window_manager and hasattr(window_manager, "progress_begin"):
        window_manager.progress_begin(0, total)


def _progress_update(context, value):
    window_manager = getattr(context, "window_manager", None)
    if window_manager and hasattr(window_manager, "progress_update"):
        window_manager.progress_update(value)


def _progress_end(context):
    window_manager = getattr(context, "window_manager", None)
    if window_manager and hasattr(window_manager, "progress_end"):
        window_manager.progress_end()


def _status_update(context, current, total, description):
    workspace = getattr(context, "workspace", None)
    if workspace and hasattr(workspace, "status_text_set"):
        workspace.status_text_set(f"Unity 材质同步 {current}/{total}：{description}")


def _status_clear(context):
    workspace = getattr(context, "workspace", None)
    if workspace and hasattr(workspace, "status_text_set"):
        workspace.status_text_set(None)


def _add_modal_timer(context, operator):
    window_manager = getattr(context, "window_manager", None)
    if window_manager is None:
        return None

    timer = None
    if hasattr(window_manager, "event_timer_add"):
        timer = window_manager.event_timer_add(0.1, window=getattr(context, "window", None))
    if hasattr(window_manager, "modal_handler_add"):
        window_manager.modal_handler_add(operator)
    return timer


def _remove_modal_timer(context, timer):
    if timer is None:
        return

    window_manager = getattr(context, "window_manager", None)
    if window_manager and hasattr(window_manager, "event_timer_remove"):
        window_manager.event_timer_remove(timer)


def _show_message_popup(context, title, lines, icon="INFO"):
    window_manager = getattr(context, "window_manager", None)
    if not window_manager or not hasattr(window_manager, "popup_menu"):
        return

    def draw(self, _context):
        for line in lines:
            self.layout.label(text=line)

    window_manager.popup_menu(draw, title=title, icon=icon)


classes = (
    MATERIAL_OT_sync_from_unity,
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
