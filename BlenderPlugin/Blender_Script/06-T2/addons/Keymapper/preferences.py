import bpy
from bpy.props import BoolProperty, StringProperty, EnumProperty
from bpy.types import AddonPreferences

# Internal build version — bump on each delivered zip.
KEYMAPPER_VERSION = "1.3.3"

# Action-value override matrix: which default action values an entry's action
# value may override, when they differ. One BoolProperty per (winner, loser)
# pair, gated by keybind_conflicts_cross_value.
KBCV_VALUES = ("PRESS", "RELEASE", "CLICK", "DOUBLE_CLICK", "CLICK_DRAG")
KBCV_LABELS = {
    "PRESS": "Press", "RELEASE": "Release", "CLICK": "Click",
    "DOUBLE_CLICK": "Double Click", "CLICK_DRAG": "Click Drag",
}
# Checked by default: pairs where the default value would also fire while
# performing the entry value's gesture (native double-fire), per Blender's
# event semantics. Click/Click Drag/Double Click are gesture-disambiguated
# by Blender and coexist natively.
KBCV_DEFAULTS = {
    ("PRESS", "RELEASE"), ("PRESS", "CLICK"),
    ("PRESS", "DOUBLE_CLICK"), ("PRESS", "CLICK_DRAG"),
    ("RELEASE", "PRESS"), ("RELEASE", "CLICK"),
    ("CLICK", "PRESS"), ("CLICK", "RELEASE"),
    ("DOUBLE_CLICK", "PRESS"), ("DOUBLE_CLICK", "RELEASE"),
    ("DOUBLE_CLICK", "CLICK"),
    ("CLICK_DRAG", "PRESS"), ("CLICK_DRAG", "RELEASE"),
}


def kbcv_prop_name(winner: str, loser: str) -> str:
    return f"kbcv_{winner.lower()}_over_{loser.lower()}"
def _wrap_lines(text: str, width_px: int) -> list:
    """Split text into label-sized lines (Blender labels do not wrap)."""
    import textwrap
    chars = max(30, int(width_px / 7.2)) if width_px else 100
    return textwrap.wrap(text, width=chars) or [""]


def _panel_vis_update(self, context):
    """If the panel that is the right-click target gets disabled, move the
    target back to Preferences->Keymap (which is permanently enabled)."""
    try:
        if self.open_editor_target == "NPANEL" and not self.enable_npanel:
            self.open_editor_target = "KEYMAP"
        elif (self.open_editor_target == "ADDON_PREFS"
                and not self.enable_prefs_panel):
            self.open_editor_target = "KEYMAP"
    except Exception:
        pass
    try:
        _redraw_all(context)
    except Exception:
        pass


class KEYMAPPER_AddonPreferences(AddonPreferences):
    bl_idname = __package__

    keymapper_json_store: StringProperty(default="")
    keymapper_folders_store: StringProperty(default="")
    # Registry of the KMIs Keymapper itself created, persisted across restarts.
    # Blender saves the user keyconfig, so on the next launch our own KMIs are
    # already present and are otherwise indistinguishable from KMIs the user
    # made by hand (both get negative ids in factory keymaps). Without this
    # record every entry would "adopt" its own leftover and wrongly report
    # being identical to a pre-existing default.
    keymapper_owned_kmis_store: StringProperty(default="")
    # These are only written on explicit Save — used as the authoritative source on load
    keymapper_saved_json_store: StringProperty(default="")
    keymapper_saved_folders_store: StringProperty(default="")
    # Keyconfig snapshot — written on user-initiated scan
    keymapper_keyconfig_store: StringProperty(default="")
    # Environment snapshot (v0.9.92+) — Blender version + enabled addons
    # at last Re-scan. Used to detect when the environment changed and
    # warn the user that their conflict cache may be stale.
    keymapper_environment_snapshot: StringProperty(default="")

    naming_mode: EnumProperty(
        name="Naming Mode",
        description="Toggle between friendly and pure naming for operators, contexts, menus and panels",
        items=[
            ("FRIENDLY", "Friendly", "Display operators with friendly naming scheme", "FONT_DATA",  0),
            ("PURE",     "Pure",     "Display operators with their raw IDs",          "SYNTAX_OFF", 1),
        ],
        default="FRIENDLY",
    )

    enable_npanel: BoolProperty(
        name="Show in N-Panel",
        description="Show the main Keymapper panel in the 3D Viewport sidebar",
        default=False,
        update=_panel_vis_update,
    )
    open_editor_target: EnumProperty(
        name="Open Full Editor In",
        description=(
            "Which Keymapper panel the right-click 'Add Shortcut Entry' popup "
            "opens when you choose Open Full Editor"
        ),
        items=[
            ("KEYMAP", "Keymap",
             "Open the Keymapper panel on the Preferences Keymap page"),
            ("NPANEL", "N-Panel",
             "Open the Keymapper tab in the 3D Viewport sidebar (N-panel)"),
            ("ADDON_PREFS", "Addon Preferences",
             "Open the Keymapper panel in this addon's preferences"),
        ],
        default="KEYMAP",
    )
    enable_keymap_panel: BoolProperty(
        name="Show in Keymap",
        description="Show the main Keymapper panel in Preferences > Keymap",
        default=True,
    )
    enable_prefs_panel: BoolProperty(
        name="Show in Addon Preferences",
        description="Show the main Keymapper panel in the Addon Preferences",
        default=False,
        update=_panel_vis_update,
    )
    show_factory_browse: BoolProperty(
        name="Include all Factory bindings as separate \"Browse Operator\" category",
        description=(
            "Show the Factory browse mode: every binding the factory "
            "keyconfig actually uses, listed as its own category next to "
            "All and Simple"
        ),
        default=False,
    )
    find_shortcut_conflicts: BoolProperty(
        name="Override Shortcut Conflicts",
        description="Detect and disable default KMIs using the same operator in the same context",
        default=True,
    )
    shortcut_conflicts_cross_props: BoolProperty(
        name="Override Shortcut Conflicts with different property values",
        description=(
            "Also override defaults using the same operator with different "
            "property values. When off, only defaults whose properties exactly "
            "match this entry's are overridden"
        ),
        default=True,
    )
    find_keybind_conflicts: BoolProperty(
        name="Override Keybind Conflicts",
        description="Detect and disable default KMIs using the same keybinding in the same context",
        default=True,
    )
    keybind_conflicts_cross_value: BoolProperty(
        name="Override Keybind Conflicts with different action values",
        description=(
            "Master switch for the action-value override matrix below. When "
            "off, only defaults with the exact same action value as the entry "
            "are overridden"
        ),
        default=True,
    )
    # Display-only: the locked always-on checkbox for a value over itself.
    kbcv_self: BoolProperty(
        name="Self",
        description="An action value always overrides defaults with the same action value",
        default=True,
    )
    kbcv_mode: EnumProperty(
        name="Action Value Mode",
        items=[
            ("ALL", "All", "Override keybind conflicts regardless of action value"),
            ("NATIVE", "Blender Native",
             "Only override action values that would natively double-fire"),
            ("CUSTOM", "Custom", "Choose exactly which action values are detected"),
        ],
        default="NATIVE",
    )

    scan_default_keyconfig: BoolProperty(
        name="Factory (keyconfig.default)",
        description=(
            "Detect shortcut and keybind conflicts from the keyconfig.default "
            "layer. These are all KMIs that originate from the active keyconfig "
            "file, like \"Blender\", \"Blender 27x\", \"Industry Compatible\" or "
            "any other keyconfig file"
        ),
        default=True,
    )
    scan_user_keyconfig: BoolProperty(
        name="User (keyconfig.user)",
        description=(
            "Detect shortcut and keybind conflicts from the keyconfig.user "
            "layer. These are KMIs that have been either manually added in "
            "blenders native Keymap system by the user, or in some cases "
            "add-ons that write directly to it instead of the addon layer"
        ),
        default=True,
    )
    scan_addon_keyconfig: BoolProperty(
        name="Addon (keyconfig.addon)",
        description=(
            "Detect shortcut and keybind conflicts from the keyconfig.addon "
            "layer. This allows Keymapper to find and disable KMIs created by "
            "addons"
        ),
        default=True,
    )

    global_enabled: BoolProperty(
        name="Enable Keymapper Shortcuts",
        description=(
            "Master switch for all Keymapper shortcuts. When off, every shortcut "
            "entry is disabled and all conflicting Blender defaults are restored"
        ),
        default=True,
        update=lambda self, context: _on_global_enabled_update(self, context),
    )

    def draw(self, context):
        from . import panel as panel_mod

        def _bool_row(parent, prop, enabled=True, indent=False):
            row = parent.row()
            row.enabled = enabled
            sub = row.row()
            if indent:
                sub.separator(factor=2.0)
            sub.prop(self, prop)
            r = row.row()
            r.alignment = "RIGHT"
            try:
                _default = self.bl_rna.properties[prop].default
            except Exception:
                _default = True
            if getattr(self, prop) != _default:
                r.operator(
                    "keymapper.reset_pref", text="", icon="LOOP_BACK"
                ).prop = prop

        def _collapsible_box(parent, wm_key, text, icon):
            """Bordered box with a collapse header; returns (box, is_open).
            Collapsed by default (default_open=False on the shared toggle)."""
            import bpy as _bpy
            from .operators import subcat_wm_key
            _wm = _bpy.context.window_manager
            _open = bool(_wm.get(subcat_wm_key(wm_key), False))
            _b = parent.box()
            _hdr = _b.row(align=True)
            _hdr.alignment = "LEFT"
            _t = _hdr.operator(
                "keymapper.form_toggle_browse_subcat",
                text=text,
                icon="DOWNARROW_HLT" if _open else "RIGHTARROW",
                emboss=False,
            )
            _t.key = wm_key
            _t.default_open = False
            _hdr.label(text="", icon=icon)
            return _b, _open

        def _collapsible_line(parent, wm_key, text):
            """Arrow-toggle row (no border); returns whether it is open."""
            import bpy as _bpy
            from .operators import subcat_wm_key
            _wm = _bpy.context.window_manager
            _open = bool(_wm.get(subcat_wm_key(wm_key), False))
            _row = parent.row(align=True)
            _row.alignment = "LEFT"
            _t = _row.operator(
                "keymapper.form_toggle_browse_subcat",
                text=text,
                icon="DOWNARROW_HLT" if _open else "RIGHTARROW",
                emboss=False,
            )
            _t.key = wm_key
            _t.default_open = False
            return _open

        # General settings
        box = self.layout.box()
        box.label(text="General", icon="PREFERENCES")
        col = box.column()
        # ── Panel visibility ─────────────────────────────────────────────
        # ── Documentation link ────────────────────────────────────────────
        doc_row = col.row(align=True)
        doc_row.operator(
            "wm.url_open", text="Documentation & Changelog", icon="URL"
        ).url = "https://jarandfolkestadwicklund.github.io/keymapper.html"

        vis_box, _vis_open = _collapsible_box(
            col, "prefs_panel_visibility", "Panel Visibility", "WINDOW")
        if _vis_open:
            vc = vis_box.column()
            # Show in Keymap is LOCKED ON: it guarantees at least one panel
            # location always exists (and so is always a valid right-click
            # target). Drawn checked but non-interactive.
            _lock = vc.row()
            _lock.enabled = False
            _lock.prop(self, "enable_keymap_panel")
            _bool_row(vc, "enable_npanel")
            _bool_row(vc, "enable_prefs_panel")

            # Which panel the right-click popup's "Open Full Editor" opens.
            # Each choice is greyed out unless its panel is enabled above;
            # drawn as rows (not a dropdown) because a dropdown cannot grey
            # out individual items.
            vc.separator(factor=0.5)
            # Header names the current target, so the choice is visible while
            # the section is collapsed (which it is by default).
            try:
                _cur = self.bl_rna.properties["open_editor_target"].enum_items[
                    self.open_editor_target].name
            except Exception:
                _cur = self.open_editor_target
            if _collapsible_line(vc, "prefs_open_editor_in",
                                 f"Open Full Editor In ({_cur})"):
                _desc = vc.column(align=True)
                _desc.scale_y = 0.8
                _desc.label(
                    text="Which panel the right-click \"Add Keymapper Shortcut")
                _desc.label(
                    text="Entry\" popup opens when you press Open Full Editor.")
                _desc.label(
                    text="Only enabled panels above can be chosen.")
                _targets = (
                    ("KEYMAP", True),
                    ("NPANEL", bool(self.enable_npanel)),
                    ("ADDON_PREFS", bool(self.enable_prefs_panel)),
                )
                _tcol = vc.column(align=True)
                for _val, _avail in _targets:
                    _r = _tcol.row(align=True)
                    _r.enabled = _avail
                    _r.prop_enum(self, "open_editor_target", _val)

        # ── Conflict Detection (contains Keyconfig Layers + Overrides) ────
        cd_box = col.box()
        cd_box.label(text="Conflict Detection", icon="MOD_PHYSICS")
        cd_col = cd_box.column()

        # ── Keyconfig layers to scan (collapsible, collapsed) ─────────────
        layers_box, _layers_open = _collapsible_box(
            cd_col, "prefs_keyconfig_layers", "Keyconfig Layers", "KEYINGSET")
        if _layers_open:
            layers_box.label(
                text="Keyconfig layers to include for conflict detection.")
            lc = layers_box.column(align=True)
            _bool_row(lc, "scan_default_keyconfig")
            _bool_row(lc, "scan_user_keyconfig")
            _bool_row(lc, "scan_addon_keyconfig")

        # ── Conflict overrides (collapsible, collapsed) ───────────────────
        ov_box, _ov_open = _collapsible_box(
            cd_col, "prefs_conflict_overrides", "Conflict Overrides",
            "OPTIONS")
        if _ov_open:
            oc = ov_box.column()
            _bool_row(oc, "find_shortcut_conflicts")
            _bool_row(oc, "shortcut_conflicts_cross_props",
                      enabled=self.find_shortcut_conflicts, indent=True)
            _bool_row(oc, "find_keybind_conflicts")
            _bool_row(oc, "keybind_conflicts_cross_value",
                      enabled=self.find_keybind_conflicts, indent=True)

        # Action-value override matrix: one column per action value, all five
        # values listed under each in the same order; the self-pair is always
        # on and locked. Collapsed entirely while the master toggle is off.
        if _ov_open and self.find_keybind_conflicts \
                and self.keybind_conflicts_cross_value:
            mrow = oc.row()
            mrow.separator(factor=2.0)
            mbox = mrow.box()
            hdr = mbox.row(align=True)
            for mode_id, mode_label in (("ALL", "All"),
                                        ("NATIVE", "Blender Native"),
                                        ("CUSTOM", "Custom")):
                op = hdr.operator("keymapper.kbcv_set_mode", text=mode_label,
                                  depress=(self.kbcv_mode == mode_id))
                op.mode = mode_id
            grid = mbox.row(align=False)
            for winner in KBCV_VALUES:
                c = grid.column(align=True)
                c.label(text=KBCV_LABELS[winner] + " detects:")
                for loser in KBCV_VALUES:
                    r = c.row()
                    if loser == winner:
                        r.enabled = False
                        r.prop(self, "kbcv_self", text=KBCV_LABELS[loser])
                    else:
                        r.enabled = (self.kbcv_mode == "CUSTOM")
                        r.prop(self, kbcv_prop_name(winner, loser))

        # ── Other (collapsible, collapsed) ────────────────────────────────
        other_box, _other_open = _collapsible_box(
            col, "prefs_other", "Other", "NONE")
        if _other_open:
            othc = other_box.column()
            _bool_row(othc, "show_factory_browse")

        if getattr(self, "enable_prefs_panel", True):
            self.layout.separator()
            panel_mod.draw_collapsible_main_panel(
                self.layout, context, "keymapper_addon_prefs")


def get_prefs(context=None):
    ctx = context or bpy.context
    return ctx.preferences.addons[__package__].preferences


def _redraw_all(context):
    """Tag every area for redraw so a preference change repaints immediately."""
    try:
        for win in context.window_manager.windows:
            for area in win.screen.areas:
                area.tag_redraw()
    except Exception:
        pass


def get_naming_mode() -> str:
    try:
        return get_prefs().naming_mode
    except Exception:
        return "FRIENDLY"


def is_friendly() -> bool:
    return get_naming_mode() == "FRIENDLY"


def _on_global_enabled_update(self, context):
    """Master switch toggle: activate or deactivate all entries' KMIs.

    Does NOT touch each entry's individual `enabled` flag — those are preserved
    so the per-entry on/off state survives a global off→on cycle.
    """
    from . import keymap_manager
    keymap_manager.set_global_enabled(bool(self.global_enabled))


# Inject the 20 matrix properties (each value vs the other four).
for _w in KBCV_VALUES:
    for _l in KBCV_VALUES:
        if _w == _l:
            continue
        KEYMAPPER_AddonPreferences.__annotations__[kbcv_prop_name(_w, _l)] = BoolProperty(
            name=KBCV_LABELS[_l],
            description=(
                f"Let a {KBCV_LABELS[_w]} entry override defaults bound to "
                f"the same key with the {KBCV_LABELS[_l]} action value"
            ),
            default=(_w, _l) in KBCV_DEFAULTS,
        )

_classes = (KEYMAPPER_AddonPreferences,)


def register():
    for cls in _classes:
        bpy.utils.register_class(cls)
    print("[Keymapper] Preferences registered.")

    # "Show in Keymap" is locked on — repair any saved prefs that have it off.
    try:
        import bpy as _b
        _p = _b.context.preferences.addons[__package__].preferences
        if not _p.enable_keymap_panel:
            _p.enable_keymap_panel = True
    except Exception:
        pass



def unregister():
    for cls in reversed(_classes):
        try:
            bpy.utils.unregister_class(cls)
        except Exception:
            pass
    print("[Keymapper] Preferences unregistered.")
