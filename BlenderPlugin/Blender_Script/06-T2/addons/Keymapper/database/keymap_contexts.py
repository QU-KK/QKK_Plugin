"""
keymap_contexts.py — All valid keymap contexts from Blender/BFA.

Each entry: (keymap_name, space_type, region_type, group)
Groups: "common", "3d_view", "editors", "sequencer", "tools", "modal"
"""

KEYMAP_CONTEXTS = [
    # ── Common / Global ──────────────────────────────────────────────────────
    ("Window",              "EMPTY",           "WINDOW", "common"),
    ("Screen",              "EMPTY",           "WINDOW", "common"),
    ("User Interface",      "EMPTY",           "WINDOW", "common"),
    ("View2D",              "EMPTY",           "WINDOW", "common"),
    ("View2D Buttons List", "EMPTY",           "WINDOW", "common"),
    ("Time Scrub",          "EMPTY",           "WINDOW", "common"),

    # ── 3D View modes ────────────────────────────────────────────────────────
    ("3D View",             "VIEW_3D",         "WINDOW", "3d_view"),
    ("3D View Generic",     "VIEW_3D",         "WINDOW", "3d_view"),
    ("Object Mode",         "EMPTY",           "WINDOW", "3d_view"),
    ("Object Non-modal",    "EMPTY",           "WINDOW", "3d_view"),
    ("Mesh",                "EMPTY",           "WINDOW", "3d_view"),
    ("Curve",               "EMPTY",           "WINDOW", "3d_view"),
    ("Curves",              "EMPTY",           "WINDOW", "3d_view"),
    ("Armature",            "EMPTY",           "WINDOW", "3d_view"),
    ("Pose",                "EMPTY",           "WINDOW", "3d_view"),
    ("Sculpt",              "EMPTY",           "WINDOW", "3d_view"),
    ("Sculpt Curves",       "EMPTY",           "WINDOW", "3d_view"),
    ("Vertex Paint",        "EMPTY",           "WINDOW", "3d_view"),
    ("Weight Paint",        "EMPTY",           "WINDOW", "3d_view"),
    ("Image Paint",         "EMPTY",           "WINDOW", "3d_view"),
    ("Particle",            "EMPTY",           "WINDOW", "3d_view"),
    ("Lattice",             "EMPTY",           "WINDOW", "3d_view"),
    ("Font",                "EMPTY",           "WINDOW", "3d_view"),
    ("Metaball",            "EMPTY",           "WINDOW", "3d_view"),
    ("Point Cloud",         "EMPTY",           "WINDOW", "3d_view"),
    ("Grease Pencil",       "EMPTY",           "WINDOW", "3d_view"),
    ("Grease Pencil Draw Mode",    "EMPTY",    "WINDOW", "3d_view"),
    ("Grease Pencil Edit Mode",    "EMPTY",    "WINDOW", "3d_view"),
    ("Grease Pencil Sculpt Mode",  "EMPTY",    "WINDOW", "3d_view"),
    ("Grease Pencil Weight Paint", "EMPTY",    "WINDOW", "3d_view"),
    ("Grease Pencil Vertex Paint", "EMPTY",    "WINDOW", "3d_view"),
    ("Grease Pencil Selection",    "EMPTY",    "WINDOW", "3d_view"),
    ("Paint Face Mask (Weight, Vertex, Texture)", "EMPTY", "WINDOW", "3d_view"),
    ("Paint Vertex Selection (Weight, Vertex)",   "EMPTY", "WINDOW", "3d_view"),
    ("Paint Curve",         "EMPTY",           "WINDOW", "3d_view"),
    ("Paint Stroke Modal",  "EMPTY",           "WINDOW", "3d_view"),

    # ── 2D Editors ───────────────────────────────────────────────────────────
    ("Image",               "IMAGE_EDITOR",    "WINDOW", "editors"),
    ("Image Generic",       "IMAGE_EDITOR",    "WINDOW", "editors"),
    ("UV Editor",           "EMPTY",           "WINDOW", "editors"),
    ("Node Editor",         "NODE_EDITOR",     "WINDOW", "editors"),
    ("Node Generic",        "NODE_EDITOR",     "WINDOW", "editors"),
    ("Graph Editor",        "GRAPH_EDITOR",    "WINDOW", "editors"),
    ("Graph Editor Generic","GRAPH_EDITOR",    "WINDOW", "editors"),
    ("Dopesheet",           "DOPESHEET_EDITOR","WINDOW", "editors"),
    ("Dopesheet Generic",   "DOPESHEET_EDITOR","WINDOW", "editors"),
    ("NLA Editor",          "NLA_EDITOR",      "WINDOW", "editors"),
    ("NLA Generic",         "NLA_EDITOR",      "WINDOW", "editors"),
    ("NLA Tracks",          "NLA_EDITOR",      "WINDOW", "editors"),
    ("Outliner",            "OUTLINER",        "WINDOW", "editors"),
    ("Property Editor",     "PROPERTIES",      "WINDOW", "editors"),
    ("Info",                "INFO",            "WINDOW", "editors"),
    ("Text",                "TEXT_EDITOR",     "WINDOW", "editors"),
    ("Text Generic",        "TEXT_EDITOR",     "WINDOW", "editors"),
    ("Console",             "CONSOLE",         "WINDOW", "editors"),
    ("Spreadsheet Generic", "SPREADSHEET",     "WINDOW", "editors"),
    ("File Browser",        "FILE_BROWSER",    "WINDOW", "editors"),
    ("File Browser Main",   "FILE_BROWSER",    "WINDOW", "editors"),
    ("File Browser Buttons","FILE_BROWSER",    "WINDOW", "editors"),
    ("Preferences",         "PREFERENCES",     "WINDOW", "editors"),

    # ── Sequencer ────────────────────────────────────────────────────────────
    ("Sequencer",           "SEQUENCE_EDITOR", "WINDOW", "sequencer"),
    ("Video Sequence Editor","SEQUENCE_EDITOR","WINDOW", "sequencer"),
    ("Sequencer Channels",  "SEQUENCE_EDITOR", "WINDOW", "sequencer"),
    ("Preview",             "SEQUENCE_EDITOR", "WINDOW", "sequencer"),

    # ── Movie Clip / Mask ─────────────────────────────────────────────────────
    ("Clip",                "CLIP_EDITOR",     "WINDOW", "editors"),
    ("Clip Editor",         "CLIP_EDITOR",     "WINDOW", "editors"),
    ("Clip Graph Editor",   "CLIP_EDITOR",     "WINDOW", "editors"),
    ("Clip Dopesheet Editor","CLIP_EDITOR",    "WINDOW", "editors"),
    ("Clip Time Scrub",     "CLIP_EDITOR",     "PREVIEW", "editors"),
    ("Mask Editing",        "EMPTY",           "WINDOW", "editors"),

    # ── Animation / Markers ───────────────────────────────────────────────────
    ("Animation",           "EMPTY",           "WINDOW", "editors"),
    ("Animation Channels",  "EMPTY",           "WINDOW", "editors"),
    ("Markers",             "EMPTY",           "WINDOW", "editors"),
    ("Frames",              "EMPTY",           "WINDOW", "editors"),

    # ── Asset / Misc ──────────────────────────────────────────────────────────
    ("Region Context Menu", "EMPTY",           "WINDOW", "editors"),
    ("Screen Editing",      "EMPTY",           "WINDOW", "editors"),

    # ── 3D View Tool Keymaps ─────────────────────────────────────────────────
    ("3D View Tool: Move",              "VIEW_3D", "WINDOW", "tools"),
    ("3D View Tool: Rotate",            "VIEW_3D", "WINDOW", "tools"),
    ("3D View Tool: Scale",             "VIEW_3D", "WINDOW", "tools"),
    ("3D View Tool: Transform",         "VIEW_3D", "WINDOW", "tools"),
    ("3D View Tool: Measure",           "VIEW_3D", "WINDOW", "tools"),
    ("3D View Tool: Cursor",            "VIEW_3D", "WINDOW", "tools"),
    ("3D View Tool: Select Box",        "VIEW_3D", "WINDOW", "tools"),
    ("3D View Tool: Select Circle",     "VIEW_3D", "WINDOW", "tools"),
    ("3D View Tool: Select Lasso",      "VIEW_3D", "WINDOW", "tools"),
    ("3D View Tool: Tweak",             "VIEW_3D", "WINDOW", "tools"),
    ("3D View Tool: Edit Mesh, Bevel",  "VIEW_3D", "WINDOW", "tools"),
    ("3D View Tool: Edit Mesh, Loop Cut","VIEW_3D","WINDOW", "tools"),
    ("3D View Tool: Edit Mesh, Knife",  "VIEW_3D", "WINDOW", "tools"),
    ("3D View Tool: Edit Mesh, Extrude Region","VIEW_3D","WINDOW","tools"),
    ("3D View Tool: Sculpt, Box Mask",  "VIEW_3D", "WINDOW", "tools"),
    ("3D View Tool: Sculpt, Lasso Mask","VIEW_3D", "WINDOW", "tools"),
    ("3D View Tool: Sculpt, Mesh Filter","VIEW_3D","WINDOW", "tools"),

    # ── Modal Maps (advanced) ─────────────────────────────────────────────────
    ("Transform Modal Map",      "EMPTY", "WINDOW", "modal"),
    ("Standard Modal Map",       "EMPTY", "WINDOW", "modal"),
    ("View3D Rotate Modal",      "EMPTY", "WINDOW", "modal"),
    ("View3D Move Modal",        "EMPTY", "WINDOW", "modal"),
    ("View3D Zoom Modal",        "EMPTY", "WINDOW", "modal"),
    ("View3D Fly Modal",         "EMPTY", "WINDOW", "modal"),
    ("View3D Walk Modal",        "EMPTY", "WINDOW", "modal"),
    ("Knife Tool Modal Map",     "EMPTY", "WINDOW", "modal"),
    ("Bevel Modal Map",          "EMPTY", "WINDOW", "modal"),
]

# Groups in display order
GROUP_ORDER = ["common", "3d_view", "editors", "sequencer", "tools", "modal"]

GROUP_LABELS = {
    "common":    "Global",
    "3d_view":   "3D View",
    "editors":   "Editors",
    "sequencer": "Sequencer",
    "tools":     "Tool Keymaps",
    "modal":     "Modal Maps",
}

# Operators that REQUIRE a context to be specified
CONTEXT_REQUIRED_OPS = {
    "wm.call_menu",
    "wm.call_menu_pie",
    "wm.call_panel",
    "wm.tool_set_by_id",
    "wm.tool_set_by_name",
    # Context operators — need keymap context to register correctly
    "wm.context_toggle",
    "wm.context_toggle_enum",
    "wm.context_set_enum",
    "wm.context_set_value",
    "wm.context_set_int",
    "wm.context_set_float",
    "wm.context_set_boolean",
    "wm.context_set_string",
    "wm.context_set_id",
}

# Lookup by name
_BY_NAME = {entry[0]: entry for entry in KEYMAP_CONTEXTS}


def get_context(name: str):
    return _BY_NAME.get(name)


def context_requires_selection(op_id: str) -> bool:
    return op_id in CONTEXT_REQUIRED_OPS


def get_contexts_by_group() -> dict:
    groups = {}
    for entry in KEYMAP_CONTEXTS:
        g = entry[3]
        groups.setdefault(g, []).append(entry)
    return {g: groups[g] for g in GROUP_ORDER if g in groups}
