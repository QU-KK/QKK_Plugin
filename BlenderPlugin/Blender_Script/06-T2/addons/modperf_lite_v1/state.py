# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Supra3D
"""Runtime state shared by the whole add-on (the panel, popups, remembered UI state)."""


# UI state that survives closing / reopening the panel
_PERSIST = {}


# =============================================================================
# Runtime state
# =============================================================================

class _HUDState:
    def __init__(self):
        self.reset()

    def reset(self):
        self.running = False
        self.draw_handle = None
        self.window_ptr = 0
        self.area_ptr = 0
        self.region_ptr = 0
        # Panel geometry in region pixel coordinates (x = left, y = TOP edge).
        self.x = 0.0
        self.y = 0.0
        self.w = 0
        self.h = 0
        self.max_h = 0
        self.size_scale = 0.0       # UI scale the panel size (w / max_h) was set at
        # Built layout reused between redraws while nothing changed (e.g. while
        # orbiting the viewport); any event or depsgraph update marks it dirty.
        self.layout_cache = None
        self.layout_dirty = True
        self.place_pending = False  # first build after opening places the panel
        self.scroll = 0.0
        self.content_h = 0.0
        self.view_h = 0.0
        # Built every redraw, used for hit testing.
        self.widgets = []
        self.headers = []          # (modifier name, top, header_bottom, block_bottom)
        self.hover = None          # widget key under the mouse
        self.hover_tip = ""
        self.drag = None           # dict describing an active drag
        self.status = ""
        self.status_time = 0.0
        self.draw_error = False
        self.edit = None           # inline number editing state
        self.multi = []            # number fields selected with Shift+click
        self.sel_keys = set()      # fields drawn as selected (multi-value editing)
        self.pending = None        # widget key pressed; acts on mouse release
        # tooltip
        self.timer = None
        self.mouse = (0.0, 0.0)
        self.tip_since = 0.0
        self.tip_visible = False
        self.tip_lines = []
        self.tip_block = None      # widget whose tooltip was dismissed by a click
        self.known_mods = {}       # object -> modifier ids (collapse newly added ones)
        self.search_getters = {}   # (modifier, prop) -> (data getter, collection) for prop_search
        self.no_collapse = False   # duplicating: keep the copy's expanded state


HUD = _HUDState()

# Target of the native popup panel / "more" menu (names, never references,
# because undo invalidates Python references to Blender data).
_POPUP = {}
