"""Fyr Material Capture and Custom Output Shader Editor nodes.

Transparent ShaderNodeCustomGroup nodes that do not change Blender rendering.
Discovery and map-stack sync live in material_capture_sync.py.
"""
from __future__ import annotations

import random

import bpy
from bpy.props import (
    BoolProperty,
    EnumProperty,
    StringProperty,
)

from . import constants
from .registration import safe_register_class, safe_unregister_class

_NODE_TREE_PREFIX = constants.FYR_NODE_TREE_PREFIX
_CAPTURE_TREE_TAG = "fyr_material_capture"
_CUSTOM_TREE_TAG = "fyr_custom_output"


def _unique_identifier(existing: set[str]) -> str:
    while True:
        value = f"{random.randint(1, 2**32):08x}"
        if value not in existing:
            return value


def _ensure_group_io(tree: bpy.types.NodeTree):
    nodes = tree.nodes
    group_in = next((n for n in nodes if n.bl_idname == "NodeGroupInput"), None)
    group_out = next((n for n in nodes if n.bl_idname == "NodeGroupOutput"), None)
    if group_in is None:
        group_in = nodes.new("NodeGroupInput")
        group_in.location = (-200, 0)
    if group_out is None:
        group_out = nodes.new("NodeGroupOutput")
        group_out.location = (200, 0)
    return group_in, group_out


def _clear_interface(tree: bpy.types.NodeTree):
    interface = getattr(tree, "interface", None)
    if interface is None:
        return
    for item in list(getattr(interface, "items_tree", []) or []):
        try:
            interface.remove(item)
        except Exception:
            pass


def _new_socket(tree: bpy.types.NodeTree, name: str, in_out: str, socket_type: str):
    interface = getattr(tree, "interface", None)
    if interface is None or not hasattr(interface, "new_socket"):
        return None
    try:
        return interface.new_socket(name=name, in_out=in_out, socket_type=socket_type)
    except Exception:
        return None


def _sync_interface(tree: bpy.types.NodeTree, desired) -> None:
    """Make *tree*'s interface exactly *desired* ``(name, in_out, socket_type)``, in order.

    Never clear-and-rebuild a live group: removing an interface socket deletes that
    socket on every node using the group, and Blender drops each link attached to it.
    Toggling one override used to disconnect the incoming shader, the Surface link to
    Material Output and every other override. Here only sockets that are no longer
    wanted are removed; kept ones are retyped and moved in place, which preserves
    their identifiers and so their links.
    """
    interface = getattr(tree, "interface", None)
    if interface is None:
        return
    wanted = list(desired)
    kept = [None] * len(wanted)
    for item in list(getattr(interface, "items_tree", []) or []):
        slot = None
        if getattr(item, "item_type", "SOCKET") == "SOCKET":
            key = (str(item.name), str(item.in_out))
            slot = next(
                (
                    index
                    for index, (name, in_out, _socket_type) in enumerate(wanted)
                    if kept[index] is None and (name, in_out) == key
                ),
                None,
            )
        if slot is None:
            try:
                interface.remove(item)
            except Exception:
                pass
            continue
        kept[slot] = item
        socket_type = wanted[slot][2]
        if str(getattr(item, "socket_type", "") or "") != socket_type:
            try:
                item.socket_type = socket_type
            except Exception:
                pass
    for index, (name, in_out, socket_type) in enumerate(wanted):
        if kept[index] is None:
            kept[index] = _new_socket(tree, name, in_out, socket_type)
    # Ascending, so every item is at or after its target and move() never overshoots.
    for position, item in enumerate(kept):
        if item is None or int(getattr(item, "position", position)) == position:
            continue
        try:
            interface.move(item, position)
        except Exception:
            pass


def _iter_shader_node_trees():
    """Every shader node tree a Fyr node can live in (its poll accepts SHADER trees)."""
    for collection_name in ("materials", "worlds", "lights", "linestyles"):
        for owner in getattr(bpy.data, collection_name, ()) or ():
            tree = getattr(owner, "node_tree", None)
            if tree is not None:
                yield tree
    for tree in bpy.data.node_groups:
        if getattr(tree, "bl_idname", "") == "ShaderNodeTree":
            yield tree


def _group_node_count(group: bpy.types.NodeTree, exclude=None) -> int:
    """How many nodes other than *exclude* use *group* as their node tree.

    Deliberately not ``group.users``. Blender 5.x ``node_init`` adds a user for any
    ID a node holds once the Python ``init()`` returns, on top of the one the
    ``node_tree`` assignment inside ``init()`` already took, so a group made in
    ``init()`` reads 2 with a single node on it (4.2 reads 1). Trusting that count
    made the first override toggle "un-share" an unshared group, orphaning the
    original with a stale user so it was saved into the .blend, and ``free()``
    never saw 0 so deleting the node leaked its group.
    """
    exclude_ptr = exclude.as_pointer() if exclude is not None else 0
    group_ptr = group.as_pointer()
    count = 0
    for tree in _iter_shader_node_trees():
        for node in tree.nodes:
            node_group = getattr(node, "node_tree", None)
            if node_group is None or node_group.as_pointer() != group_ptr:
                continue
            if node.as_pointer() != exclude_ptr:
                count += 1
    return count


def _remove_unused_group(group) -> None:
    """Delete *group* once no node uses it. Callers release their own reference first."""
    if group is None or getattr(group, "use_fake_user", False):
        return
    if group.get("fyr_kind") not in (_CAPTURE_TREE_TAG, _CUSTOM_TREE_TAG):
        return  # only ever delete Fyr's own passthrough groups
    if _group_node_count(group) == 0:
        try:
            bpy.data.node_groups.remove(group)
        except Exception:
            pass


def _unshare_tree(node) -> bool:
    """Give *node* its own copy of its group when it is sharing one. True if it split.

    `copy()` deliberately leaves the duplicated node pointing at the original's group,
    because allocating a node group inside Blender's ID copy is what wedged the bake
    (see the note on `ShaderNodeFyrCustomOutput.copy`). Sharing a passthrough group is
    harmless right up until something rewrites its interface, so the split happens
    here instead -- called from the rebuild paths, which only ever run from property
    update callbacks, well outside any ID copy.
    """
    tree = getattr(node, "node_tree", None)
    # Shared means another node is on this group; see _group_node_count for why
    # the ID user count cannot answer that.
    if tree is None or _group_node_count(tree, exclude=node) == 0:
        return False
    private = tree.copy()
    private.name = f"{_NODE_TREE_PREFIX}{str(getattr(node, 'identifier', '') or 'Copy')}"
    node.node_tree = private
    return True


def _create_passthrough_shader_tree(name: str, *, tag: str) -> bpy.types.NodeTree:
    tree = bpy.data.node_groups.new(name, "ShaderNodeTree")
    tree["fyr_kind"] = tag
    _clear_interface(tree)
    _new_socket(tree, "Shader", "INPUT", "NodeSocketShader")
    _new_socket(tree, "Shader", "OUTPUT", "NodeSocketShader")
    group_in, group_out = _ensure_group_io(tree)
    if group_in.outputs and group_out.inputs:
        tree.links.new(group_in.outputs[0], group_out.inputs[0])
    return tree


def _custom_output_socket(data_type: str) -> tuple[str, str]:
    """(label, socket_type) of a Custom Output group's single in/out pair."""
    return {
        constants.MATERIAL_DATA_COLOR: ("Color", "NodeSocketColor"),
        constants.MATERIAL_DATA_VALUE: ("Value", "NodeSocketFloat"),
        constants.MATERIAL_DATA_VECTOR: ("Vector", "NodeSocketVector"),
    }.get(data_type, ("Color", "NodeSocketColor"))


def _create_custom_output_tree(name: str, data_type: str) -> bpy.types.NodeTree:
    label, socket_type = _custom_output_socket(data_type)
    tree = bpy.data.node_groups.new(name, "ShaderNodeTree")
    tree["fyr_kind"] = _CUSTOM_TREE_TAG
    _clear_interface(tree)
    _new_socket(tree, label, "INPUT", socket_type)
    _new_socket(tree, label, "OUTPUT", socket_type)
    group_in, group_out = _ensure_group_io(tree)
    if group_in.outputs and group_out.inputs:
        tree.links.new(group_in.outputs[0], group_out.inputs[0])
    return tree


def _retype_custom_output_tree(tree: bpy.types.NodeTree, data_type: str) -> None:
    """Switch a Custom Output group's data type in place, keeping the node's links."""
    label, socket_type = _custom_output_socket(data_type)
    interface = getattr(tree, "interface", None)
    if interface is None:
        return
    # Rename first so _sync_interface matches the existing pair instead of
    # replacing it (Color -> Value would otherwise drop the incoming link).
    for in_out in ("OUTPUT", "INPUT"):
        item = next(
            (
                it
                for it in getattr(interface, "items_tree", []) or []
                if getattr(it, "item_type", "SOCKET") == "SOCKET" and it.in_out == in_out
            ),
            None,
        )
        if item is not None and item.name != label:
            item.name = label
    _sync_interface(
        tree,
        [(label, "OUTPUT", socket_type), (label, "INPUT", socket_type)],
    )
    group_in, group_out = _ensure_group_io(tree)
    if not tree.links and group_in.outputs and group_out.inputs:
        tree.links.new(group_in.outputs[0], group_out.inputs[0])


def _schedule_capture_sync(*_args):
    try:
        from . import material_capture_sync
        material_capture_sync.schedule_sync()
    except Exception:
        pass


def _prop_schedule_sync(self, context):
    _schedule_capture_sync()


def _capture_mode_update(self, _context):
    self._rebuild_override_sockets()
    _schedule_capture_sync()


def _capture_override_update(self, _context):
    self._rebuild_override_sockets()
    _schedule_capture_sync()


def _custom_output_update(self, _context):
    self._rebuild_tree_for_type()
    _schedule_capture_sync()


class ShaderNodeFyrMaterialCapture(bpy.types.ShaderNodeCustomGroup):
    """Transparent shader passthrough that marks a material for Fyr capture."""

    bl_idname = constants.FYR_CAPTURE_NODE_ID
    bl_label = "Fyr Material Capture"
    bl_description = "Capture PBR channels from this material into the Fyr Baker map stack"
    bl_width_default = 220

    identifier: StringProperty(
        name="Identifier",
        default="",
        options={"HIDDEN"},
    )
    capture_mode: EnumProperty(
        name="Mode",
        items=constants.CAPTURE_MODE_ITEMS,
        default=constants.CAPTURE_MODE_HYBRID,
        description="How channels are derived from the incoming shader",
        update=_capture_mode_update,
    )
    show_advanced: BoolProperty(
        name="Advanced",
        default=False,
        description="Show advanced Principled override toggles",
    )

    # Compact override toggles — sockets appear when enabled in Hybrid/Explicit.
    override_base_color: BoolProperty(name="Base Color", default=False, update=_capture_override_update)
    override_metalness: BoolProperty(name="Metalness", default=False, update=_capture_override_update)
    override_roughness: BoolProperty(name="Roughness", default=False, update=_capture_override_update)
    override_normal: BoolProperty(name="Normal", default=False, update=_capture_override_update)
    override_emission: BoolProperty(name="Emission", default=False, update=_capture_override_update)
    override_opacity: BoolProperty(name="Opacity", default=False, update=_capture_override_update)
    override_height: BoolProperty(name="Height", default=False, update=_capture_override_update)
    override_specular: BoolProperty(name="Specular", default=False, update=_capture_override_update)
    override_transmission: BoolProperty(name="Transmission", default=False, update=_capture_override_update)

    @classmethod
    def poll(cls, node_tree):
        return getattr(node_tree, "type", "") == "SHADER"

    def init(self, context):
        node_tree = self.id_data
        existing = {
            str(getattr(node, "identifier", "") or "")
            for node in (getattr(node_tree, "nodes", None) or [])
            if getattr(node, "bl_idname", "") == self.bl_idname
        }
        self.identifier = _unique_identifier(existing)
        self.width = 220
        if self.node_tree is None:
            self.node_tree = _create_passthrough_shader_tree(
                f"{_NODE_TREE_PREFIX}Capture {self.identifier}",
                tag=_CAPTURE_TREE_TAG,
            )
        self._rebuild_override_sockets()
        _schedule_capture_sync()

    def copy(self, node):
        node_tree = self.id_data
        existing = {
            str(getattr(n, "identifier", "") or "")
            for n in (getattr(node_tree, "nodes", None) or [])
            if getattr(n, "bl_idname", "") == self.bl_idname
        }
        self.identifier = _unique_identifier(existing)
        # No node group is built here. See ShaderNodeFyrCustomOutput.copy for why:
        # allocating one inside Blender's ID copy poisons the copied material. The
        # duplicate keeps pointing at the original's group, and `_unshare_tree`
        # splits it the first time the interface is rewritten.
        _schedule_capture_sync()

    def free(self):
        tree = self.node_tree
        # Release this node's reference first, then delete only a group no other node
        # uses. A group can still be shared with a duplicate (copy() deliberately
        # leaves the duplicate on the original's group); removing that one took the
        # *other* material's capture node's tree -- its sockets vanished, the Surface
        # link to Material Output went with them, and that material rendered and
        # baked black with nothing left to repair it.
        self.node_tree = None
        _remove_unused_group(tree)
        _schedule_capture_sync()

    def draw_buttons(self, _context, layout):
        layout.prop(self, "capture_mode", text="")
        mode = str(getattr(self, "capture_mode", "") or "")
        if mode == constants.CAPTURE_MODE_AUTO:
            layout.label(text="Derives channels automatically")
            return

        box = layout.box()
        box.label(text="Overrides")
        grid = box.grid_flow(columns=1, align=True)
        for prop_name, label in (
            ("override_base_color", "Base Color"),
            ("override_metalness", "Metalness"),
            ("override_roughness", "Roughness"),
            ("override_normal", "Normal"),
            ("override_emission", "Emission"),
            ("override_opacity", "Opacity"),
            ("override_height", "Height"),
            ("override_specular", "Specular"),
            ("override_transmission", "Transmission"),
        ):
            grid.prop(self, prop_name, text=label)

    def _override_enabled(self, channel_key: str) -> bool:
        return bool(getattr(self, f"override_{channel_key.lower()}", False))

    def enabled_overrides(self) -> list[str]:
        return [
            key
            for key, _label, _kind, _binding in constants.CAPTURE_COMPACT_CHANNELS
            if self._override_enabled(key)
        ]

    def _rebuild_override_sockets(self):
        if self.node_tree is None:
            # A duplicate whose copy() no longer allocates: build the group now, on a
            # path that is not inside an ID copy.
            self.node_tree = _create_passthrough_shader_tree(
                f"{_NODE_TREE_PREFIX}Capture {self.identifier}",
                tag=_CAPTURE_TREE_TAG,
            )
        # This rewrites the interface in place, so a group shared with the node this
        # one was duplicated from has to be split first or both nodes change.
        _unshare_tree(self)
        tree = self.node_tree
        if tree is None:
            return
        # Shader in/out plus the enabled override inputs (Hybrid/Explicit only),
        # synced in place so the node keeps its links.
        desired = [
            ("Shader", "OUTPUT", "NodeSocketShader"),
            ("Shader", "INPUT", "NodeSocketShader"),
        ]
        auto = str(getattr(self, "capture_mode", "") or "") == constants.CAPTURE_MODE_AUTO
        socket_types = {
            "RGBA": "NodeSocketColor",
            "VALUE": "NodeSocketFloat",
            "VECTOR": "NodeSocketVector",
        }
        for key, label, kind, _binding in constants.CAPTURE_COMPACT_CHANNELS:
            if not self._override_enabled(key):
                continue
            if auto:
                # Auto ignores overrides (material_graph gates on the mode), but a
                # wired one stays so switching back to Hybrid/Explicit keeps its link.
                socket = self.inputs.get(label)
                if socket is None or not socket.is_linked:
                    continue
            desired.append((label, "INPUT", socket_types[kind]))
        _sync_interface(tree, desired)
        group_in, group_out = _ensure_group_io(tree)
        # The only internal link is the shader passthrough.
        shader_out = next((s for s in group_in.outputs if s.name == "Shader"), None)
        shader_in = next((s for s in group_out.inputs if s.name == "Shader"), None)
        for link in list(tree.links):
            if link.from_socket == shader_out and link.to_socket == shader_in:
                continue
            try:
                tree.links.remove(link)
            except Exception:
                pass
        if shader_out is not None and shader_in is not None and not tree.links:
            tree.links.new(shader_out, shader_in)


class ShaderNodeFyrCustomOutput(bpy.types.ShaderNodeCustomGroup):
    """Named intermediate capture independent of Material Output."""

    bl_idname = constants.FYR_CUSTOM_OUTPUT_NODE_ID
    bl_label = "Fyr Custom Output"
    bl_description = "Capture a named color, value, or vector into the Fyr Baker map stack"
    bl_width_default = 200

    identifier: StringProperty(name="Identifier", default="", options={"HIDDEN"})
    output_name: StringProperty(
        name="Name",
        default="Custom",
        description="Map stack name for this output. Matching names across materials share one row",
        update=_custom_output_update,
    )
    data_type: EnumProperty(
        name="Type",
        items=constants.MATERIAL_DATA_TYPE_ITEMS,
        default=constants.MATERIAL_DATA_COLOR,
        update=_custom_output_update,
    )
    vector_encoding: EnumProperty(
        name="Encoding",
        items=constants.MATERIAL_VECTOR_ENCODE_ITEMS,
        default=constants.MATERIAL_VECTOR_ENCODE_UNIT,
        description="How vector outputs are stored in the baked image",
        update=_prop_schedule_sync,
    )

    @classmethod
    def poll(cls, node_tree):
        return getattr(node_tree, "type", "") == "SHADER"

    def init(self, context):
        node_tree = self.id_data
        existing = {
            str(getattr(node, "identifier", "") or "")
            for node in (getattr(node_tree, "nodes", None) or [])
            if getattr(node, "bl_idname", "") == self.bl_idname
        }
        self.identifier = _unique_identifier(existing)
        if not str(getattr(self, "output_name", "") or "").strip():
            self.output_name = "Custom"
        self.width = 200
        self._rebuild_tree_for_type()
        _schedule_capture_sync()

    def copy(self, node):
        node_tree = self.id_data
        existing = {
            str(getattr(n, "identifier", "") or "")
            for n in (getattr(node_tree, "nodes", None) or [])
            if getattr(n, "bl_idname", "") == self.bl_idname
        }
        self.identifier = _unique_identifier(existing)
        # Do NOT build a node group here. Creating a `bpy.data.node_groups` datablock
        # from inside this callback runs while Blender is part-way through
        # `material.copy()`, and it leaves the copied material in a state where the
        # next Cycles bake never returns -- `bpy.ops.object.bake` hangs and Blender
        # has to be killed. That was the long-standing G12 freeze; it reproduced on a
        # two-node material and disappeared the moment this line stopped allocating.
        # The duplicate keeps the original's group, which is safe for a passthrough,
        # and `_unshare_tree` gives it a private one before anything rewrites it.
        _schedule_capture_sync()

    def free(self):
        tree = self.node_tree
        # Release our reference, then remove the group only if no other node uses
        # it -- see the note on ShaderNodeFyrMaterialCapture.free.
        self.node_tree = None
        _remove_unused_group(tree)
        _schedule_capture_sync()

    def draw_buttons(self, _context, layout):
        layout.prop(self, "output_name", text="")
        layout.prop(self, "data_type", text="")
        if str(getattr(self, "data_type", "") or "") == constants.MATERIAL_DATA_VECTOR:
            layout.prop(self, "vector_encoding", text="")

    def _rebuild_tree_for_type(self):
        data_type = str(getattr(self, "data_type", "") or constants.MATERIAL_DATA_COLOR)
        old = self.node_tree
        if old is not None and old.get("fyr_kind") == _CUSTOM_TREE_TAG:
            # Rename / type change on a live node: edit its own group in place so the
            # incoming link survives (a fresh group has new socket identifiers and
            # Blender drops the link). Split a group shared with a duplicate first.
            _unshare_tree(self)
            _retype_custom_output_tree(self.node_tree, data_type)
            return
        # No group yet, or not one of ours: build a fresh one. The old group is removed
        # only if no other node still uses it (a duplicate may be pointing at it).
        self.node_tree = _create_custom_output_tree(
            f"{_NODE_TREE_PREFIX}Custom {self.identifier}",
            data_type,
        )
        if old is not None and old != self.node_tree:
            _remove_unused_group(old)


def is_capture_node(node) -> bool:
    return getattr(node, "bl_idname", "") == constants.FYR_CAPTURE_NODE_ID


def is_custom_output_node(node) -> bool:
    return getattr(node, "bl_idname", "") == constants.FYR_CUSTOM_OUTPUT_NODE_ID


def find_active_capture(material):
    """Return the capture node closest to the active Material Output Surface, if any."""
    from . import material_channel_graph

    tree = getattr(material, "node_tree", None)
    if tree is None:
        return None
    output = material_channel_graph.active_material_output(tree)
    if output is None:
        return None
    surface = output.inputs.get("Surface")
    if surface is None or not surface.links:
        return None
    node = surface.links[0].from_node
    visited = set()
    while node is not None:
        key = node.as_pointer()
        if key in visited:
            break
        visited.add(key)
        if is_capture_node(node):
            return node
        # Walk through transparent group/reroute chains toward the surface source.
        if getattr(node, "type", "") == "REROUTE" and node.inputs and node.inputs[0].links:
            node = node.inputs[0].links[0].from_node
            continue
        break
    return None


def iter_custom_outputs(material):
    tree = getattr(material, "node_tree", None)
    if tree is None:
        return
    for node in tree.nodes:
        if is_custom_output_node(node):
            yield node


def insert_capture_before_output(material) -> bool:
    """Insert a Fyr Material Capture before the active Material Output. Returns True if inserted."""
    from . import material_channel_graph

    if material is None:
        return False
    if not getattr(material, "use_nodes", False):
        material.use_nodes = True
    tree = material.node_tree
    if tree is None:
        return False
    if find_active_capture(material) is not None:
        return False
    output = material_channel_graph.active_material_output(tree)
    if output is None:
        output = tree.nodes.new("ShaderNodeOutputMaterial")
        output.is_active_output = True
    surface = output.inputs.get("Surface")
    if surface is None:
        return False
    capture = tree.nodes.new(constants.FYR_CAPTURE_NODE_ID)
    capture.location = (output.location[0] - 220, output.location[1])
    if surface.links:
        from_socket = surface.links[0].from_socket
        tree.links.remove(surface.links[0])
        tree.links.new(from_socket, capture.inputs.get("Shader") or capture.inputs[0])
    tree.links.new(capture.outputs.get("Shader") or capture.outputs[0], surface)
    return True


def project_materials(project) -> list:
    """Materials used by the project's high sources, or lows when no highs exist."""
    from . import project_structure

    materials = []
    seen = set()
    for group in getattr(project, "groups", []) or []:
        highs = list(project_structure.group_role_targets(group, constants.OBJECT_ROLE_HIGH) or [])
        lows = list(project_structure.group_role_targets(group, constants.OBJECT_ROLE_LOW) or [])
        objects = highs or lows
        for obj in objects:
            for slot in getattr(obj, "material_slots", []) or []:
                material = getattr(slot, "material", None)
                if material is None:
                    continue
                key = material.as_pointer()
                if key in seen:
                    continue
                seen.add(key)
                materials.append(material)
    return materials


class MASTER_BAKER_OT_insert_material_capture(bpy.types.Operator):
    bl_idname = "master_baker.insert_material_capture"
    bl_label = "Insert Capture Nodes"
    bl_description = "Insert Fyr Material Capture before Material Output on materials used by this project"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        from . import properties
        return properties.get_active_project(context.scene) is not None

    def execute(self, context):
        from . import material_capture_sync
        from . import properties

        project = properties.get_active_project(context.scene)
        if project is None:
            return {"CANCELLED"}
        inserted = 0
        for material in project_materials(project):
            if insert_capture_before_output(material):
                inserted += 1
        material_capture_sync.sync_project(project)
        if inserted:
            self.report({"INFO"}, f"Inserted capture on {inserted} material(s)")
        else:
            self.report({"INFO"}, "All project materials already have an active capture")
        return {"FINISHED"}


class MASTER_BAKER_OT_restore_detected_outputs(bpy.types.Operator):
    bl_idname = "master_baker.restore_detected_outputs"
    bl_label = "Restore Detected Outputs"
    bl_description = "Clear suppressed auto-detected material outputs and re-sync the map stack"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        from . import properties
        return properties.get_active_project(context.scene) is not None

    def execute(self, context):
        from . import material_capture_sync
        from . import properties

        project = properties.get_active_project(context.scene)
        if project is None:
            return {"CANCELLED"}
        cleared = 0
        for item in list(getattr(project, "material_binding_suppressions", []) or []):
            try:
                project.material_binding_suppressions.remove(0)
                cleared += 1
            except Exception:
                break
        material_capture_sync.sync_project(project, clear_suppressions=False)
        self.report({"INFO"}, f"Restored detections ({cleared} suppression(s) cleared)")
        return {"FINISHED"}


def _draw_fyr_shader_menu(self, context):
    if getattr(getattr(context, "space_data", None), "tree_type", "") != "ShaderNodeTree":
        return
    layout = self.layout
    layout.separator()
    layout.label(text="Fyr Baker")
    op = layout.operator("node.add_node", text="Material Capture")
    op.type = constants.FYR_CAPTURE_NODE_ID
    op.use_transform = True
    op = layout.operator("node.add_node", text="Custom Output")
    op.type = constants.FYR_CUSTOM_OUTPUT_NODE_ID
    op.use_transform = True


_CLASSES = (
    ShaderNodeFyrMaterialCapture,
    ShaderNodeFyrCustomOutput,
    MASTER_BAKER_OT_insert_material_capture,
    MASTER_BAKER_OT_restore_detected_outputs,
)


def register():
    for cls in _CLASSES:
        safe_register_class(cls)
    if hasattr(bpy.types, "NODE_MT_category_shader_output"):
        bpy.types.NODE_MT_category_shader_output.append(_draw_fyr_shader_menu)
    elif hasattr(bpy.types, "NODE_MT_shader_node_add_all"):
        bpy.types.NODE_MT_shader_node_add_all.append(_draw_fyr_shader_menu)


def unregister():
    if hasattr(bpy.types, "NODE_MT_category_shader_output"):
        try:
            bpy.types.NODE_MT_category_shader_output.remove(_draw_fyr_shader_menu)
        except Exception:
            pass
    if hasattr(bpy.types, "NODE_MT_shader_node_add_all"):
        try:
            bpy.types.NODE_MT_shader_node_add_all.remove(_draw_fyr_shader_menu)
        except Exception:
            pass
    for cls in reversed(_CLASSES):
        safe_unregister_class(cls)
