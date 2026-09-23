import bpy
from bpy.props import (
    StringProperty,
    BoolProperty,
    IntProperty,
    EnumProperty,
    CollectionProperty,
)
from bpy.types import PropertyGroup


# ---------------------------------------------------------------------------
# Conflict Item
# ---------------------------------------------------------------------------

class KEYMAPPER_ConflictItem(PropertyGroup):
    """Stores a single conflict (shortcut or keybind)."""

    name: StringProperty(
        name="Name",
        description="Human-readable name of the conflicting action",
        default="",
    )
    key_display: StringProperty(
        name="Key Display",
        description="Shortcut string, e.g. 'Shift+D'",
        default="",
    )
    disabled: BoolProperty(
        name="Disabled",
        description="Whether this conflict has been disabled by Keymapper",
        default=False,
    )
    conflict_type: StringProperty(
        name="Conflict Type",
        description="'shortcut' or 'keybind'",
        default="shortcut",
    )
    # Path used to locate the kmi for restore
    keymap_name: StringProperty(
        name="Keymap Name",
        description="Name of the keymap that owns this item",
        default="",
    )
    operator_id: StringProperty(
        name="Operator ID",
        description="Raw operator ID of the conflicting item",
        default="",
    )
    kmi_id: IntProperty(
        name="KMI ID",
        description="Blender internal ID of the KeyMapItem",
        default=-1,
    )


# ---------------------------------------------------------------------------
# Main Entry
# ---------------------------------------------------------------------------

class KEYMAPPER_Entry(PropertyGroup):
    """One user-defined shortcut entry."""

    # --- Identity ---
    entry_id: StringProperty(
        name="Entry ID",
        description="Unique identifier for this entry",
        default="",
    )

    # --- Display ---
    display_name: StringProperty(
        name="Display Name",
        description="The label shown in the panel (friendly name or raw operator ID)",
        default="",
    )
    is_friendly: BoolProperty(
        name="Is Friendly Name",
        description="True = was added via friendly name, False = raw operator ID",
        default=True,
    )

    # --- State ---
    enabled: BoolProperty(
        name="Enabled",
        description="Whether this shortcut is currently active",
        default=True,
        update=lambda self, ctx: _on_enabled_changed(self, ctx),
    )
    selected: BoolProperty(
        name="Selected",
        description="Whether this entry is selected in the list",
        default=False,
    )

    # --- Expand/Collapse ---
    expanded_entry: BoolProperty(
        name="Expanded",
        description="Show conflict submenus",
        default=False,
    )
    expanded_shortcuts: BoolProperty(
        name="Shortcuts Expanded",
        description="Show shortcut conflicts list",
        default=False,
    )
    expanded_keybinds: BoolProperty(
        name="Keybinds Expanded",
        description="Show keybind conflicts list",
        default=False,
    )

    # --- Operator ---
    # Comma-separated list of raw operator IDs (e.g. "mesh.duplicate_move,object.duplicate_move")
    operator_ids: StringProperty(
        name="Operator IDs",
        description="Comma-separated raw operator IDs this entry maps to",
        default="",
    )

    # --- Shortcut ---
    key: StringProperty(
        name="Key",
        description="The key for this shortcut (e.g. 'D', 'F2', 'SPACE')",
        default="",
    )
    shift: BoolProperty(name="Shift", default=False)
    ctrl: BoolProperty(name="Ctrl", default=False)
    alt: BoolProperty(name="Alt", default=False)
    oskey: BoolProperty(name="OSKey", default=False)
    event_type: EnumProperty(
        name="Event Type",
        items=[
            ("PRESS", "Press", "Trigger on key press"),
            ("CLICK", "Click", "Trigger on click"),
            ("RELEASE", "Release", "Trigger on key release"),
            ("DOUBLE_CLICK", "Double Click", "Trigger on double click"),
        ],
        default="PRESS",
    )

    # --- Context ---
    # Comma-separated keymap names (e.g. "Object Mode,Mesh")
    keymap_contexts: StringProperty(
        name="Keymap Contexts",
        description="Comma-separated keymap context names",
        default="",
    )

    # --- Conflicts ---
    shortcut_conflicts: CollectionProperty(
        name="Shortcut Conflicts",
        type=KEYMAPPER_ConflictItem,
    )
    keybind_conflicts: CollectionProperty(
        name="Keybind Conflicts",
        type=KEYMAPPER_ConflictItem,
    )

    # --- Sort ---
    sort_index: IntProperty(
        name="Sort Index",
        description="Position in the list",
        default=0,
    )

    # --- Metadata ---
    source_app: StringProperty(
        name="Source App",
        description="'blender' or 'bforartists'",
        default="blender",
    )

    def get_operator_ids_list(self):
        """Returns operator_ids as a clean Python list."""
        return [op.strip() for op in self.operator_ids.split(",") if op.strip()]

    def get_keymap_contexts_list(self):
        """Returns keymap_contexts as a clean Python list."""
        return [k.strip() for k in self.keymap_contexts.split(",") if k.strip()]

    def get_shortcut_display(self):
        """Returns human-readable shortcut string, e.g. 'Ctrl + Alt + D'."""
        parts = []
        if self.shift:
            parts.append("Shift")
        if self.ctrl:
            parts.append("Ctrl")
        if self.alt:
            parts.append("Alt")
        if self.oskey:
            parts.append("OS")
        if self.key:
            parts.append(self.key)
        return " + ".join(parts) if parts else "—"


def _on_enabled_changed(entry, context):
    """Called when an entry's enabled state changes."""
    try:
        from . import keymap_manager
        if entry.enabled:
            keymap_manager.activate_entry(entry)
        else:
            keymap_manager.deactivate_entry(entry)
    except Exception as e:
        print(f"[Keymapper] Error toggling entry '{entry.display_name}': {e}")


# ---------------------------------------------------------------------------
# Window Manager properties (runtime selection index)
# ---------------------------------------------------------------------------

class KEYMAPPER_WindowManagerProps(PropertyGroup):
    selected_index: IntProperty(
        name="Selected Entry Index",
        description="Currently selected entry index",
        default=-1,
        min=-1,
    )


# ---------------------------------------------------------------------------
# Register
# ---------------------------------------------------------------------------

_classes = (
    KEYMAPPER_ConflictItem,
    KEYMAPPER_Entry,
    KEYMAPPER_WindowManagerProps,
)


def register():
    for cls in _classes:
        bpy.utils.register_class(cls)

    bpy.types.WindowManager.keymapper = bpy.props.PointerProperty(
        type=KEYMAPPER_WindowManagerProps
    )

    print("[Keymapper] Properties registered.")


def unregister():
    try:
        del bpy.types.WindowManager.keymapper
    except Exception:
        pass

    for cls in reversed(_classes):
        try:
            bpy.utils.unregister_class(cls)
        except Exception:
            pass

    print("[Keymapper] Properties unregistered.")
