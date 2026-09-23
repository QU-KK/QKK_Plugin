"""ES Tools Hub - floating icon palettes you fill from Preferences.

You can create any number of palettes.  Each one has its own entries,
position, orientation, icon size and optional shortcut, so you can park a
modelling set top-left and an animation set bottom-right at the same time.

Two kinds of entries end up in a palette:

  * Providers - ES add-ons that register themselves into the shared
    `_es_tools_hub` namespace.  Clicking one makes it the active tool and
    shows its panels in the sidebar's "Tool" tab.
  * User entries - anything you add in this add-on's preferences.  An entry
    either switches the sidebar to a named tab (works with any add-on that
    has an N-panel category) or runs an operator by id.  A Sidebar Tab entry
    can also hide that tab until its icon is picked, with no changes to the
    other add-on's source.

Blender has no API for a persistent window of real UI buttons, so palettes
are drawn with the `gpu` module by a single modal operator.  That is the
only way to get something that is always visible and freely placeable.
"""

import os
import sys
import types

import bpy
import gpu
from bpy.app.handlers import persistent
from bpy.props import (
    BoolProperty,
    CollectionProperty,
    EnumProperty,
    FloatProperty,
    FloatVectorProperty,
    IntProperty,
    StringProperty,
)
from bpy.types import AddonPreferences, Menu, Operator, PropertyGroup, UIList
from gpu_extras.batch import batch_for_shader


# --------------------------------------------------------------------------- #
#  shared namespace
# --------------------------------------------------------------------------- #

HUB_OWNER = "__hub__"


def store():
    """Namespace shared with the ES provider add-ons, whatever the load order."""
    mod = sys.modules.get("_es_tools_hub")
    if mod is None:
        mod = types.ModuleType("_es_tools_hub")
        sys.modules["_es_tools_hub"] = mod
    for name, value in (("entries", {}), ("owner", None), ("host_stop", None),
                        ("hub", False), ("active", None), ("selected", None),
                        ("wanted", False), ("running", False),
                        ("pos_x", 40.0), ("pos_y", 40.0), ("vertical", False)):
        if not hasattr(mod, name):
            setattr(mod, name, value)
    return mod


def prefs():
    try:
        return bpy.context.preferences.addons[__package__].preferences
    except Exception:
        return None


def visible_palettes():
    """(index, palette) for every palette currently switched on."""
    p = prefs()
    if p is None:
        return []
    return [(i, pal) for i, pal in enumerate(p.palettes) if pal.visible]


def any_visible():
    return bool(visible_palettes())



# --------------------------------------------------------------------------- #
#  which editors a palette can live in
# --------------------------------------------------------------------------- #
#
#  Every editor's Space type takes a POST_PIXEL draw handler, so a palette can
#  be drawn in any of them.  Handlers are per Space class, so one is added for
#  each editor that some visible palette asks for, and they all share the same
#  callback - it works out which editor it is drawing in from context.area.

SPACE_ITEMS = (
    ('VIEW_3D', "3D Viewport", "", 1 << 0),
    ('IMAGE_EDITOR', "Image / UV", "", 1 << 1),
    ('NODE_EDITOR', "Node Editor", "", 1 << 2),
    ('TEXT_EDITOR', "Text Editor", "", 1 << 3),
    ('SEQUENCE_EDITOR', "Video Sequencer", "", 1 << 4),
    ('CLIP_EDITOR', "Movie Clip", "", 1 << 5),
    ('DOPESHEET_EDITOR', "Dope Sheet", "", 1 << 6),
    ('GRAPH_EDITOR', "Graph Editor", "", 1 << 7),
    ('NLA_EDITOR', "Nonlinear Animation", "", 1 << 8),
    ('SPREADSHEET', "Spreadsheet", "", 1 << 9),
)

SPACE_CLASSES = {
    'VIEW_3D': "SpaceView3D",
    'IMAGE_EDITOR': "SpaceImageEditor",
    'NODE_EDITOR': "SpaceNodeEditor",
    'TEXT_EDITOR': "SpaceTextEditor",
    'SEQUENCE_EDITOR': "SpaceSequenceEditor",
    'CLIP_EDITOR': "SpaceClipEditor",
    'DOPESHEET_EDITOR': "SpaceDopeSheetEditor",
    'GRAPH_EDITOR': "SpaceGraphEditor",
    'NLA_EDITOR': "SpaceNLA",
    'SPREADSHEET': "SpaceSpreadsheet",
}


def space_class(space_type):
    """The Space class for an editor, or None on a Blender that lacks it."""
    return getattr(bpy.types, SPACE_CLASSES.get(space_type, ""), None)


def palette_spaces(palette):
    spaces = set(palette.spaces)
    return spaces or {'VIEW_3D'}


def active_space_types():
    """Editors that some visible palette wants to be drawn in."""
    out = set()
    for _index, palette in visible_palettes():
        out |= palette_spaces(palette)
    return out


def area_key(screen, area):
    """A handle for one particular area.

    Areas carry no identifier of their own, so this is the screen's name plus
    the area's index in it.  That survives file loads and restarts; what it
    does not survive is the area being split or joined, which reshuffles the
    list.  The area type is stored alongside so an obviously wrong match after
    a reshuffle can be spotted rather than silently used.
    """
    if screen is None or area is None:
        return ""
    try:
        for i, other in enumerate(screen.areas):
            if other == area:
                return "%s|%d|%s" % (screen.name, i, area.type)
    except Exception:
        pass
    return ""


def current_area_key():
    return area_key(getattr(bpy.context, "screen", None),
                    getattr(bpy.context, "area", None))


def key_matches(pinned, key):
    if not pinned or not key:
        return False
    if pinned == key:
        return True
    # same screen and index, different type: the layout was rearranged
    return pinned.rsplit("|", 1)[0] == key.rsplit("|", 1)[0]


def palettes_for_area(area_type, key=""):
    """Visible palettes that belong in this area.

    A pinned palette is drawn only in the area it was pinned to; everything
    else follows its editor list.
    """
    out = []
    for i, pal in visible_palettes():
        if pal.pinned:
            if key_matches(pal.pinned, key):
                out.append((i, pal))
            continue
        if area_type in palette_spaces(pal):
            out.append((i, pal))
    return out


# --------------------------------------------------------------------------- #
#  palette contents
# --------------------------------------------------------------------------- #

def palette_entries(index, palette=None):
    """Providers first (if this palette wants them), then the user's entries."""
    p = prefs()
    if p is None:
        return []
    if palette is None:
        if not (0 <= index < len(p.palettes)):
            return []
        palette = p.palettes[index]

    out = []
    if palette.include_providers:
        providers = sorted(store().entries.values(),
                           key=lambda e: (e.get("order", 0), e.get("name", "")))
        for entry in providers:
            out.append({
                "id": "p:" + str(entry.get("key")),
                "name": entry.get("name", "?"),
                "path": entry.get("path"),
                "kind": "provider",
                "key": entry.get("key"),
            })

    for i, item in enumerate(palette.entries):
        path = entry_icon_path(item)
        out.append({
            "id": "u:%d:%d" % (index, i),
            "name": item.name or ("Entry %d" % (i + 1)),
            "path": path,
            "kind": "user",
            "mode": item.mode,
            "category": item.category,
            "operator": item.operator,
            "menu": item.menu_id,
            "modifier": item.modifier_type,
            "color": tuple(item.label_color),
        })
    return out


def find_area(types=None):
    """First (window, area, WINDOW region) matching `types`, or any palette's."""
    if types is None:
        types = active_space_types() or {'VIEW_3D'}
    for win in bpy.context.window_manager.windows:
        for area in win.screen.areas:
            if area.type not in types:
                continue
            for region in area.regions:
                if region.type == 'WINDOW':
                    return win, area, region
    return None, None, None


def find_view3d():
    return find_area({'VIEW_3D'})


def open_sidebar(category):
    """Open the sidebar in every 3D Viewport and switch it to `category`."""
    found = False
    for win in bpy.context.window_manager.windows:
        for area in win.screen.areas:
            if area.type != 'VIEW_3D':
                continue
            found = True
            try:
                area.spaces.active.show_region_ui = True
            except Exception:
                pass
            area.tag_redraw()
    if not found:
        return False

    # Panel categories only exist once the region has been drawn at least
    # once, so keep retrying for a few ticks instead of failing immediately.
    state = {"tries": 20}

    def tick():
        for win in bpy.context.window_manager.windows:
            for area in win.screen.areas:
                if area.type != 'VIEW_3D':
                    continue
                for region in area.regions:
                    if region.type != 'UI':
                        continue
                    try:
                        region.active_panel_category = category
                    except Exception:
                        continue
                    area.tag_redraw()
                    return None
        state["tries"] -= 1
        return 0.05 if state["tries"] > 0 else None

    bpy.app.timers.register(tick, first_interval=0.01)
    return True


def run_operator(idname, where=None):
    """Run `module.operator`, preferably in the editor the icon was clicked in.

    A palette in the Text Editor should run text.* operators against that
    editor, so the click's own area is used when one was supplied.
    """
    try:
        group, name = idname.split(".", 1)
        op = getattr(getattr(bpy.ops, group), name)
    except Exception:
        return False

    win, area, region = where if where else find_area()
    try:
        if win is not None:
            with bpy.context.temp_override(window=win, area=area, region=region):
                op('INVOKE_DEFAULT')
        else:
            op('INVOKE_DEFAULT')
    except Exception:
        return False
    return True


def activate(entry, where=None):
    st = store()
    st.selected = entry["id"]
    if entry["kind"] == "provider":
        st.active = entry["key"]
        open_sidebar("Tool")
        return
    # user entry: ES panels are hidden while a non-ES tool is picked
    st.active = None
    mode = entry.get("mode")
    if mode == 'OPERATOR':
        if entry.get("operator"):
            run_operator(entry["operator"], where)
    elif mode == 'MODIFIER':
        if not add_modifier(entry.get("modifier"), where):
            open_sidebar_report("Could not add that modifier here")
    elif mode == 'MENU':
        run_menu(entry.get("menu"), where)
    elif mode == 'MODIFIERS':
        run_modifier_popup(where)
    elif entry.get("category"):
        open_sidebar(entry["category"])


def open_sidebar_report(message):
    """A palette click has no operator to report through, so use the status bar."""
    try:
        for win in bpy.context.window_manager.windows:
            win.workspace.status_text_set(message)

        def clear():
            try:
                for w in bpy.context.window_manager.windows:
                    w.workspace.status_text_set(None)
            except Exception:
                pass
            return None

        bpy.app.timers.register(clear, first_interval=3.0)
    except Exception:
        pass


def sidebar_categories():
    """Every N-panel tab currently registered in the 3D Viewport."""
    found = set()
    for name in dir(bpy.types):
        cls = getattr(bpy.types, name, None)
        if not isinstance(cls, type):
            continue
        try:
            if not issubclass(cls, bpy.types.Panel):
                continue
        except Exception:
            continue
        if getattr(cls, "bl_space_type", "") != 'VIEW_3D':
            continue
        if getattr(cls, "bl_region_type", "") != 'UI':
            continue
        category = getattr(cls, "bl_category", "")
        if category:
            found.add(category)
    return sorted(found)



# --------------------------------------------------------------------------- #
#  Blender's own modifiers
# --------------------------------------------------------------------------- #
#
#  Modifier types come from Modifier.type's RNA enum, and every item already
#  carries the icon Blender itself uses (ICON_MOD_* in rna_modifier.cc), so
#  the grid below is always in step with the running version - nothing to
#  maintain when modifiers are added or renamed.
#
#  The enum also carries headings (items with an empty identifier), which give
#  the Modify / Generate / Deform / Physics grouping.  Which groups apply to
#  which object type is not in the enum, so the table below mirrors what
#  OBJECT_MT_modifier_add does in properties_data_modifier.py.

MODIFIER_GROUP_TYPES = {
    "Modify": {'MESH', 'CURVE', 'CURVES', 'FONT', 'SURFACE', 'LATTICE',
               'GREASEPENCIL', 'POINTCLOUD'},
    "Edit": {'MESH', 'CURVE', 'CURVES', 'FONT', 'SURFACE', 'LATTICE',
             'GREASEPENCIL', 'POINTCLOUD'},
    "Generate": {'MESH', 'CURVE', 'FONT', 'SURFACE', 'VOLUME', 'GREASEPENCIL'},
    "Deform": {'MESH', 'CURVE', 'FONT', 'SURFACE', 'LATTICE', 'VOLUME',
               'GREASEPENCIL'},
    "Normals": {'MESH'},
    "Physics": {'MESH', 'CURVE', 'FONT', 'SURFACE', 'LATTICE'},
    "Color": {'GREASEPENCIL'},
}


def modifier_groups(object_type=None):
    """[(heading, [enum item, ...]), ...] for `object_type`, or everything."""
    try:
        items = bpy.types.Modifier.bl_rna.properties["type"].enum_items_static
    except Exception:
        try:
            items = bpy.types.Modifier.bl_rna.properties["type"].enum_items
        except Exception:
            return []

    groups = []
    current = None
    for item in items:
        if not item.identifier:                 # a heading, not a modifier
            name = item.name or ""
            if current is None or current[0] != name:
                current = (name, [])
                groups.append(current)
            continue
        if current is None:
            current = ("", [])
            groups.append(current)

        if object_type is not None:
            allowed = MODIFIER_GROUP_TYPES.get(current[0])
            if allowed is not None and object_type not in allowed:
                continue
            # grease pencil modifiers share the same headings as the rest
            is_gp = item.identifier.startswith("GREASE_PENCIL_")
            if is_gp != (object_type == 'GREASEPENCIL'):
                continue
        current[1].append(item)

    merged = {}
    order = []
    for name, entries in groups:
        if not entries:
            continue
        if name not in merged:
            merged[name] = []
            order.append(name)
        merged[name].extend(entries)
    return [(name, merged[name]) for name in order]


def run_later(where, action):
    """Run `action` on the next tick, inside the given area's context.

    Popups cannot be opened from inside a modal operator's event handling,
    so the click only schedules them.
    """
    win, area, region = where if where else find_area()

    def call():
        try:
            if win is not None:
                with bpy.context.temp_override(window=win, area=area,
                                               region=region):
                    action()
            else:
                action()
        except Exception:
            pass
        return None

    bpy.app.timers.register(call, first_interval=0.0)
    return True


def modifier_items(object_type=None):
    """Flat list of modifier enum items, headings dropped."""
    out = []
    for _name, items in modifier_groups(object_type):
        out.extend(items)
    return out


def modifier_item(identifier):
    """The enum item for one modifier type, or None if it is unknown here."""
    if not identifier:
        return None
    for item in modifier_items():
        if item.identifier == identifier:
            return item
    return None


def add_modifier(mod_type, where=None):
    """Add one modifier to the active object, in the clicked editor."""
    if not mod_type:
        return False
    win, area, region = where if where else find_area()
    try:
        if win is not None:
            with bpy.context.temp_override(window=win, area=area, region=region):
                bpy.ops.object.modifier_add(type=mod_type)
        else:
            bpy.ops.object.modifier_add(type=mod_type)
    except Exception:
        return False
    return True


def run_menu(name, where=None):
    """Open a menu, with its items set to invoke rather than execute.

    A popup menu gets InvokeRegionWin only when it was spawned from a button;
    opened from a script it gets ExecRegionWin instead (see the opcontext
    choice in interface_region_menu_popup.cc).  Operators then run exec()
    straight away, so anything that would normally open a File Browser fails
    with "no filepath given".

    Drawing the wanted menu inside a proxy lets the operator context be set
    explicitly, so its items invoke properly and their file dialogs appear.
    """
    if not name:
        return False
    if not hasattr(bpy.types, name):
        open_sidebar_report("No menu named \"%s\" is registered" % name)
        return False
    ESHUB_MT_menu_proxy.target = name
    return run_later(where, lambda: bpy.ops.wm.call_menu(
        'INVOKE_DEFAULT', name="ESHUB_MT_menu_proxy"))


def run_modifier_popup(where=None):
    return run_later(where,
                     lambda: bpy.ops.es_hub.modifier_popup('INVOKE_DEFAULT'))


# --------------------------------------------------------------------------- #
#  hiding sidebar tabs until their icon is picked
# --------------------------------------------------------------------------- #
#
#  Blender only calls a panel's poll() if the class defined one at the moment
#  it was registered (see rna_Panel_register / panel_add_check), so assigning
#  a poll afterwards has no effect.  To gate a tab we therefore unregister its
#  panels and register them again with a poll injected.
#
#  Unregistering a parent panel sets `child->parent = nullptr`, which would
#  promote its sub-panels to top level, so the whole tree for a tab is taken
#  down children-first and rebuilt parents-first.  Only root panels get the
#  injected poll: Blender collects root panels only, and draws sub-panels from
#  their parent's layout, so hiding the root hides everything beneath it.
#
#  A tab disappears from the tab strip entirely when none of its root panels
#  poll True, which is what makes the tab vanish rather than just go empty.

# Blender's own tabs - gating these would hide built-in tools
PROTECTED_CATEGORIES = {"Item", "Tool", "View"}

# category -> [(cls, had_own_poll, original_poll), ...] in registration order
_gates = {}


def viewport_panels():
    """Every 3D Viewport sidebar panel class, keyed by its panel idname."""
    out = {}
    for name in dir(bpy.types):
        cls = getattr(bpy.types, name, None)
        if not isinstance(cls, type):
            continue
        try:
            if not issubclass(cls, bpy.types.Panel):
                continue
        except Exception:
            continue
        if getattr(cls, "bl_space_type", "") != 'VIEW_3D':
            continue
        if getattr(cls, "bl_region_type", "") != 'UI':
            continue
        if 'INSTANCED' in set(getattr(cls, "bl_options", None) or ()):
            continue
        out[getattr(cls, "bl_idname", None) or cls.__name__] = cls
    return out


def category_tree(category, panels):
    """Panels belonging to `category`, parents before children.

    Sub-panels do not inherit bl_category, so membership is decided by
    walking each panel's bl_parent_id chain up to its root.
    """
    def root_of(cls):
        seen = set()
        current = cls
        while True:
            parent_id = getattr(current, "bl_parent_id", "")
            if not parent_id or parent_id in seen:
                return current
            seen.add(parent_id)
            parent = panels.get(parent_id)
            if parent is None:
                return current
            current = parent

    members = [cls for cls in panels.values()
               if getattr(root_of(cls), "bl_category", "") == category]

    # Blender inserts panel types sorted by bl_order, so honour that here;
    # same-order panels fall back to name, which may not match the order the
    # other add-on registered them in.
    members.sort(key=lambda c: (getattr(c, "bl_order", 0) or 0,
                                getattr(c, "bl_idname", None) or c.__name__))

    ordered = []
    remaining = list(members)
    placed = set()
    guard = 0
    while remaining and guard < 100:
        guard += 1
        for cls in list(remaining):
            parent_id = getattr(cls, "bl_parent_id", "")
            if not parent_id or parent_id in placed or parent_id not in panels:
                ordered.append(cls)
                placed.add(getattr(cls, "bl_idname", None) or cls.__name__)
                remaining.remove(cls)
    ordered.extend(remaining)              # cycles, if anyone manages one
    return ordered


def make_gate_poll(category, original):
    def poll(cls, context):
        if not gate_open(category):
            return False
        if original is None:
            return True
        try:
            return original(context)
        except Exception:
            return True
    return classmethod(poll)


def gate_open(category):
    """A gated tab is visible only while one of its icons is the active pick."""
    p = prefs()
    if p is None:
        return True
    st = store()
    for i, palette in enumerate(p.palettes):
        for j, item in enumerate(palette.entries):
            if item.mode != 'CATEGORY' or item.category != category:
                continue
            if not palette.visible:
                # the palette holding this tab is hidden, so never lock it away
                return True
            if st.selected == "u:%d:%d" % (i, j):
                return True
    return False


def gate_category(category):
    if category in _gates or category in PROTECTED_CATEGORIES or not category:
        return False
    panels = viewport_panels()
    tree = category_tree(category, panels)
    if not tree:
        return False

    saved = [(cls, "poll" in cls.__dict__, cls.__dict__.get("poll"))
             for cls in tree]

    for cls in reversed(tree):             # children first
        try:
            bpy.utils.unregister_class(cls)
        except Exception:
            pass

    for cls in tree:                       # parents first
        if not getattr(cls, "bl_parent_id", ""):
            cls.poll = make_gate_poll(category, getattr(cls, "poll", None))
        try:
            bpy.utils.register_class(cls)
        except Exception:
            pass

    _gates[category] = saved
    return True


def ungate_category(category):
    saved = _gates.pop(category, None)
    if saved is None:
        return
    classes = [cls for cls, _own, _poll in saved]

    for cls in reversed(classes):
        try:
            bpy.utils.unregister_class(cls)
        except Exception:
            pass

    for cls, had_own, original in saved:
        if had_own:
            cls.poll = original
        else:
            try:
                del cls.poll                # reveals any inherited poll again
            except AttributeError:
                pass
        try:
            bpy.utils.register_class(cls)
        except Exception:
            pass


def wanted_gates():
    p = prefs()
    if p is None:
        return set()
    out = set()
    for palette in p.palettes:
        for item in palette.entries:
            if (item.mode == 'CATEGORY' and item.hide_tab and item.category
                    and item.category not in PROTECTED_CATEGORIES):
                out.add(item.category)
    return out


def sync_gates():
    """Bring the live gates in line with the preferences."""
    wanted = wanted_gates()
    for category in list(_gates):
        if category not in wanted:
            ungate_category(category)
    for category in wanted:
        if category not in _gates:
            gate_category(category)
    redraw_views()


def clear_gates():
    for category in list(_gates):
        ungate_category(category)


def sync_gates_soon():
    """Panels cannot be re-registered from a UI callback - defer a tick."""
    def run():
        sync_gates()
        return None
    bpy.app.timers.register(run, first_interval=0.0)


def on_entry_changed(self, context):
    clear_auto_icons()          # the entry points somewhere else now
    sync_gates_soon()


def on_icon_changed(self, context):
    clear_auto_icons()
    redraw_views()



# --------------------------------------------------------------------------- #
#  finding an add-on's own icon
# --------------------------------------------------------------------------- #
#
#  An entry with no icon file set looks for one inside the add-on it points
#  at.  The add-on is located through the Python class that backs the entry:
#  a Sidebar Tab entry resolves through a panel with that bl_category, an
#  Operator entry through the operator class.  `cls.__module__` gives the
#  module, `sys.modules[...].__file__` gives its path, and the package root
#  is whatever is the highest folder still holding an __init__.py or a
#  blender_manifest.toml.  That works for legacy add-ons and 4.2+ extensions
#  alike, without needing to know the install location.

ICON_DIRS = ("icons", "icon")
ICON_NAMES = ("icon.png", "icon.PNG")

_auto_icons = {}                # cache key -> resolved path or None


def icon_in(folder):
    """icons/icon.png (or icon/icon.png, or the first PNG) inside `folder`."""
    for sub_name in ICON_DIRS:
        directory = os.path.join(folder, sub_name)
        if not os.path.isdir(directory):
            continue
        for name in ICON_NAMES:
            candidate = os.path.join(directory, name)
            if os.path.isfile(candidate):
                return candidate
        try:
            pngs = sorted(n for n in os.listdir(directory)
                          if n.lower().endswith(".png"))
        except OSError:
            pngs = []
        if pngs:
            return os.path.join(directory, pngs[0])
    return None


def package_folders(module_name):
    """The module's own folder plus every package folder above it."""
    module = sys.modules.get(module_name)
    path = getattr(module, "__file__", None)
    if not path:
        return []
    folder = os.path.dirname(os.path.abspath(path))
    out = []
    for _ in range(6):
        marker = (os.path.isfile(os.path.join(folder, "__init__.py")) or
                  os.path.isfile(os.path.join(folder, "blender_manifest.toml")))
        if not marker:
            break                       # left the add-on, do not scan further up
        out.append(folder)
        parent = os.path.dirname(folder)
        if parent == folder:
            break
        folder = parent
    return out


def icon_for_class(cls):
    if cls is None:
        return None
    for folder in package_folders(getattr(cls, "__module__", "")):
        found = icon_in(folder)
        if found:
            return found
    return None


def panel_for_category(category):
    """A root panel in `category`, preferred over a sub-panel."""
    panels = viewport_panels()
    roots = [cls for cls in panels.values()
             if getattr(cls, "bl_category", "") == category
             and not getattr(cls, "bl_parent_id", "")]
    if roots:
        roots.sort(key=lambda c: getattr(c, "bl_idname", None) or c.__name__)
        return roots[0]
    for cls in panels.values():
        if getattr(cls, "bl_category", "") == category:
            return cls
    return None


def operator_class(idname):
    for name in dir(bpy.types):
        cls = getattr(bpy.types, name, None)
        if not isinstance(cls, type):
            continue
        try:
            if not issubclass(cls, bpy.types.Operator):
                continue
        except Exception:
            continue
        if getattr(cls, "bl_idname", "") == idname:
            return cls
    return None


def auto_icon_path(item):
    """Icon shipped with the add-on this entry points at, if there is one."""
    if item.mode not in {'CATEGORY', 'OPERATOR'}:
        return None                     # menus have no add-on to look inside
    if item.mode == 'CATEGORY':
        if not item.category:
            return None
        key = ("c", item.category)
    else:
        if not item.operator:
            return None
        key = ("o", item.operator)

    if key in _auto_icons:
        return _auto_icons[key]

    if key[0] == "c":
        found = icon_for_class(panel_for_category(item.category))
    else:
        found = icon_for_class(operator_class(item.operator))
    _auto_icons[key] = found
    return found


def entry_icon_path(item):
    """An explicit icon always wins; otherwise fall back to the add-on's own."""
    if item.icon_path:
        try:
            return bpy.path.abspath(item.icon_path)
        except Exception:
            return item.icon_path
    if item.auto_icon:
        return auto_icon_path(item)
    return None


def clear_auto_icons():
    _auto_icons.clear()
    free_textures()


# --------------------------------------------------------------------------- #
#  palette drawing
# --------------------------------------------------------------------------- #

GAP = 4.0
PAD = 6.0
GRIP = 13.0

_handles = {}              # space type -> draw handler
_textures = {}
_images = {}
_hover = [-1, -1]          # [palette index, icon index]; -2 = the flip button
_live = {}                 # palette index -> (x, y) while dragging


def ui_scale():
    try:
        return bpy.context.preferences.system.ui_scale
    except Exception:
        return 1.0


def palette_pos(index, palette):
    live = _live.get(index)
    if live is not None:
        return live
    return palette.pos_x, palette.pos_y


def layout_for(region, index, palette, count):
    """Rects for a palette, its icons and its flip button, in region pixels."""
    scale = ui_scale()
    icon = float(palette.icon_size) * scale
    gap = GAP * scale
    pad = PAD * scale
    grip = GRIP * scale

    vertical = bool(palette.vertical)
    run = count * icon + max(0, count - 1) * gap

    if vertical:
        width = pad * 2 + icon
        height = pad * 2 + run + grip
    else:
        width = max(pad * 2 + run, pad * 2 + icon)
        height = pad * 2 + icon + grip

    px, py = palette_pos(index, palette)
    x = min(max(px, 0.0), max(0.0, region.width - width))
    y = min(max(py, 0.0), max(0.0, region.height - height))

    icons = []
    for i in range(count):
        if vertical:
            icons.append((x + pad,
                          y + height - grip - pad - icon - i * (icon + gap)))
        else:
            icons.append((x + pad + i * (icon + gap), y + pad))

    size = grip - 4.0 * scale
    btn = (x + width - size - 3.0 * scale,
           y + height - grip + 2.0 * scale, size, size)
    pin = (btn[0] - size - 3.0 * scale, btn[1], size, size)

    return {"x": x, "y": y, "w": width, "h": height, "icon": icon,
            "gap": gap, "pad": pad, "grip": grip, "scale": scale,
            "vertical": vertical, "icons": icons, "btn": btn, "pin": pin}


def icon_at(mx, my, lay):
    icon = lay["icon"]
    for i, (ix, iy) in enumerate(lay["icons"]):
        if ix <= mx <= ix + icon and iy <= my <= iy + icon:
            return i
    return -1


def hit_button(mx, my, lay):
    bx, by, bw, bh = lay["btn"]
    return bx <= mx <= bx + bw and by <= my <= by + bh


def hit_pin(mx, my, lay):
    bx, by, bw, bh = lay["pin"]
    if bx < lay["x"]:
        return False                    # too narrow to hold the pin button
    return bx <= mx <= bx + bw and by <= my <= by + bh


def texture_for(entry):
    key = entry["id"]
    path = entry.get("path")
    cached = _textures.get(key)
    if cached is not None and cached[0] == path:
        return cached[1]
    if not path or not os.path.exists(path):
        _textures[key] = (path, None)
        return None
    try:
        # check_existing would hand back a datablock the file already uses,
        # and the settings below would then be written into the user's scene
        img = bpy.data.images.load(path, check_existing=False)
        # Both must be set before the GPU texture is built.
        try:
            img.colorspace_settings.name = 'sRGB'
        except Exception:
            pass
        try:
            # STRAIGHT gives the same alpha association for 8-bit and 16-bit
            # files alike, so one blend mode covers both; 'NONE' would make
            # Blender ignore the alpha channel and draw an opaque box
            img.alpha_mode = 'STRAIGHT'
        except Exception:
            pass
        tex = gpu.texture.from_image(img)
    except Exception:
        _textures[key] = (path, None)
        return None
    _images[key] = img
    _textures[key] = (path, tex)
    return tex


def free_textures():
    _textures.clear()
    for img in list(_images.values()):
        try:
            bpy.data.images.remove(img)
        except Exception:
            pass
    _images.clear()


def fill(x, y, w, h, color):
    shader = gpu.shader.from_builtin('UNIFORM_COLOR')
    batch = batch_for_shader(
        shader, 'TRIS',
        {"pos": ((x, y), (x + w, y), (x + w, y + h), (x, y + h))},
        indices=((0, 1, 2), (0, 2, 3)))
    shader.bind()
    shader.uniform_float("color", color)
    batch.draw(shader)


def draw_text(text, x, y, size, color=(0.9, 0.9, 0.9, 1.0)):
    import blf
    try:
        blf.size(0, int(size))
    except TypeError:                       # Blender < 4.0
        blf.size(0, int(size), 72)
    blf.color(0, *color)
    blf.position(0, x, y, 0.0)
    blf.draw(0, text)


def text_size(text, size):
    import blf
    try:
        blf.size(0, int(size))
    except TypeError:
        blf.size(0, int(size), 72)
    return blf.dimensions(0, text)


def draw_icon_texture(tex, x, y, size):
    """Draw an icon from a bpy Image, with alpha and colour handled properly.

    Whether the GPU texture holds premultiplied alpha is decided by
    BKE_image_has_gpu_texture_premultiplied_alpha: a byte buffer is
    premultiplied only when alpha_mode is PREMUL, and a float buffer is
    premultiplied unless alpha_mode is STRAIGHT.  texture_for pins alpha_mode
    to STRAIGHT, so either kind of file ends up as straight alpha and plain
    ALPHA blending is the correct pairing.  ALPHA_PREMULT here would multiply
    by alpha twice and leave a dark box around the artwork.

    The texture is in scene linear while a POST_PIXEL handler draws into a
    Rec.709 sRGB buffer, so draw_texture_2d needs telling or the artwork comes
    out washed out.  That argument is newer than the function itself, hence
    the fallback.
    """
    from gpu_extras.presets import draw_texture_2d

    previous = 'ALPHA'
    try:
        previous = gpu.state.blend_get()
    except Exception:
        pass

    try:
        gpu.state.blend_set('ALPHA')
        try:
            draw_texture_2d(tex, (x, y), size, size,
                            is_scene_linear_with_rec709_srgb_target=True)
        except TypeError:
            draw_texture_2d(tex, (x, y), size, size)
        return True
    except Exception:
        return False
    finally:
        try:
            gpu.state.blend_set(previous)
        except Exception:
            gpu.state.blend_set('ALPHA')


def initials(name):
    """Short stand-in drawn when an entry has no icon file.

    Two words give their first letters; one word gives its first two, so
    "Array" reads as AR rather than a lone A.
    """
    words = name.split()
    if not words:
        return "?"
    if len(words) == 1:
        return words[0][:2].upper()
    return (words[0][0] + words[1][0]).upper()


def draw_one(region, index, palette):
    entries = palette_entries(index, palette)
    if not entries:
        return

    lay = layout_for(region, index, palette, len(entries))
    x, y, width, height = lay["x"], lay["y"], lay["w"], lay["h"]
    icon, grip, scale = lay["icon"], lay["grip"], lay["scale"]
    selected = store().selected
    hover = _hover[1] if _hover[0] == index else -1

    fill(x, y, width, height, (0.10, 0.10, 0.10, 0.85))
    fill(x, y + height - grip, width, grip, (0.22, 0.22, 0.22, 0.90))

    # flip button, drawn as a hint of the layout it switches to
    bx, by, bw, bh = lay["btn"]
    fill(bx, by, bw, bh,
         (0.42, 0.42, 0.42, 0.95) if hover == -2 else (0.30, 0.30, 0.30, 0.95))
    bar = max(1.0, bw / 5.0)
    for i in range(3):
        if lay["vertical"]:
            fill(bx + i * bar * 2.0, by, bar, bh, (0.88, 0.88, 0.88, 0.95))
        else:
            fill(bx, by + i * bar * 2.0, bw, bar, (0.88, 0.88, 0.88, 0.95))

    # pin button: filled when the palette is tied to this area
    px, py, pw, ph = lay["pin"]
    if px >= lay["x"]:
        fill(px, py, pw, ph,
             (0.42, 0.42, 0.42, 0.95) if hover == -3 else (0.30, 0.30, 0.30, 0.95))
        dot = max(1.0, pw * 0.34)
        if palette.pinned:
            fill(px + (pw - dot * 2.0) * 0.5, py + (ph - dot * 2.0) * 0.5,
                 dot * 2.0, dot * 2.0, (0.30, 0.62, 0.95, 1.0))
        else:
            ring = max(1.0, scale)
            ix0 = px + (pw - dot * 2.0) * 0.5
            iy0 = py + (ph - dot * 2.0) * 0.5
            fill(ix0, iy0, dot * 2.0, ring, (0.80, 0.80, 0.80, 0.95))
            fill(ix0, iy0 + dot * 2.0 - ring, dot * 2.0, ring, (0.80, 0.80, 0.80, 0.95))
            fill(ix0, iy0, ring, dot * 2.0, (0.80, 0.80, 0.80, 0.95))
            fill(ix0 + dot * 2.0 - ring, iy0, ring, dot * 2.0, (0.80, 0.80, 0.80, 0.95))

    for i, entry in enumerate(entries):
        ix, iy = lay["icons"][i]
        if entry["id"] == selected:
            fill(ix - 2, iy - 2, icon + 4, icon + 4, (0.16, 0.42, 0.72, 0.95))
        elif i == hover:
            fill(ix - 2, iy - 2, icon + 4, icon + 4, (0.35, 0.35, 0.35, 0.90))

        tex = texture_for(entry)
        drawn = False
        if tex is not None:
            drawn = draw_icon_texture(tex, ix, iy, icon)
        if not drawn:
            # no icon file: initials on a plate, so the slot is still usable
            fill(ix, iy, icon, icon, (0.28, 0.28, 0.28, 0.95))
            label = initials(entry["name"])
            try:
                tw, th = text_size(label, icon * 0.42)
                draw_text(label, ix + (icon - tw) * 0.5,
                          iy + (icon - th) * 0.5, icon * 0.42,
                          entry.get("color") or (0.92, 0.92, 0.92, 1.0))
            except Exception:
                pass

    if 0 <= hover < len(entries):
        try:
            draw_tooltip(region, lay, entries[hover]["name"], hover)
        except Exception:
            pass


def theme_tooltip():
    """Colours, roundness and font size Blender uses for its own tooltips."""
    inner = (0.09, 0.09, 0.09, 0.95)
    outline = (0.25, 0.25, 0.25)
    text_col = (0.85, 0.85, 0.85)
    roundness = 0.4
    points = 11.0
    try:
        wcol = bpy.context.preferences.themes[0].user_interface.wcol_tooltip
        inner = tuple(wcol.inner)
        outline = tuple(wcol.outline)[:3]
        text_col = tuple(wcol.text)[:3]
        roundness = float(wcol.roundness)
    except Exception:
        pass
    try:
        points = float(bpy.context.preferences.ui_styles[0].widget.points)
    except Exception:
        pass
    return inner, outline, text_col, roundness, points


def rounded_contour(x, y, w, h, radius, segments=6):
    """Points around a round-cornered box, counter-clockwise from top right."""
    import math
    radius = max(0.0, min(radius, w * 0.5, h * 0.5))
    points = []
    corners = (
        (x + w - radius, y + h - radius, 0.0),          # top right
        (x + radius, y + h - radius, math.pi * 0.5),    # top left
        (x + radius, y + radius, math.pi),              # bottom left
        (x + w - radius, y + radius, math.pi * 1.5),    # bottom right
    )
    for cx, cy, base in corners:
        for i in range(segments + 1):
            angle = base + (math.pi * 0.5) * (i / segments)
            points.append((cx + math.cos(angle) * radius,
                           cy + math.sin(angle) * radius))
    return points


def draw_tris(points, indices, color):
    shader = gpu.shader.from_builtin('UNIFORM_COLOR')
    batch = batch_for_shader(shader, 'TRIS', {"pos": points}, indices=indices)
    shader.bind()
    shader.uniform_float("color", color)
    batch.draw(shader)


def rounded_rect(x, y, w, h, radius, color, segments=6):
    """Filled round-cornered box, matching Blender's widget corners."""
    if radius <= 0.5 or w <= 0.0 or h <= 0.0:
        if w > 0.0 and h > 0.0:
            fill(x, y, w, h, color)
        return
    points = rounded_contour(x, y, w, h, radius, segments)
    indices = [(0, i, i + 1) for i in range(1, len(points) - 1)]
    draw_tris(points, indices, color)


def rounded_outline(x, y, w, h, radius, thickness, color, segments=6):
    """Ring following a round-cornered box.

    Drawn as a band between two contours rather than as a larger filled plate
    behind the box: the tooltip body is translucent, so a plate underneath
    would show through it and darken the whole thing.
    """
    if w <= 0.0 or h <= 0.0 or thickness <= 0.0:
        return
    outer = rounded_contour(x, y, w, h, radius, segments)
    inner = rounded_contour(x + thickness, y + thickness,
                            w - thickness * 2.0, h - thickness * 2.0,
                            max(0.0, radius - thickness), segments)
    if len(outer) != len(inner):
        return

    points = []
    indices = []
    count = len(outer)
    for i in range(count):
        j = (i + 1) % count
        base = len(points)
        points.extend((outer[i], outer[j], inner[j], inner[i]))
        indices.extend(((base, base + 1, base + 2),
                        (base, base + 2, base + 3)))
    draw_tris(points, indices, color)


def draw_tooltip(region, lay, text, hover):
    """Hover label styled like a Blender tooltip.

    Blender's real tooltips float above everything because the UI code spawns
    a temporary screen-level region for them (region_temp_add, RGN_TYPE_
    TEMPORARY in interface_region_tooltip.cc).  Python cannot create those, and
    a draw handler is scissored to its own region, so this label is placed on
    whichever side has room and clamped inside the region instead.  Colours,
    corner radius, padding and font size are read from the active theme so it
    still matches whatever Blender itself would draw.
    """
    x, y, width, height = lay["x"], lay["y"], lay["w"], lay["h"]
    icon, scale = lay["icon"], lay["scale"]

    inner, outline, text_col, roundness, points = theme_tooltip()
    size = points * scale

    tw, th = text_size(text, size)
    line_h = max(th, size)
    # TIP_PADDING_X / TIP_PADDING_Y from interface_region_tooltip.cc, halved
    # the same way the text bounding box is inset there
    pad_x = line_h * 1.95 * 0.5
    pad_y = line_h * 1.28 * 0.5

    box_w = tw + pad_x * 2.0
    box_h = line_h + pad_y * 2.0
    # widget_radius_from_zoom: roundness * widget_unit (20 px before UI scale)
    radius = roundness * 20.0 * scale

    offset = 8.0 * scale
    margin = 2.0 * scale
    hx, hy = lay["icons"][hover]

    if lay["vertical"]:
        bx = x + width + offset
        if bx + box_w > region.width - margin:
            bx = x - offset - box_w
        by = hy + (icon - box_h) * 0.5
    else:
        bx = hx + (icon - box_w) * 0.5
        by = y - offset - box_h
        if by < margin:
            by = y + height + offset

    # never let the plate leave the region, or it would be cut in half
    bx = min(max(bx, margin), max(margin, region.width - box_w - margin))
    by = min(max(by, margin), max(margin, region.height - box_h - margin))

    if len(inner) < 4:
        inner = tuple(inner) + (0.95,)

    # soft shadow, as widget_softshadow does behind menus and tooltips.  Rings
    # rather than plates, so nothing is stacked under the translucent body.
    for i in range(3):
        spread = (i + 1) * 1.4 * scale
        rounded_outline(bx - spread, by - spread - 1.0 * scale,
                        box_w + spread * 2.0, box_h + spread * 2.0,
                        radius + spread, 1.4 * scale, (0.0, 0.0, 0.0, 0.07))

    rounded_rect(bx, by, box_w, box_h, radius, inner)
    rounded_outline(bx, by, box_w, box_h, radius, max(1.0, scale),
                    (outline[0], outline[1], outline[2], 1.0))

    baseline = by + pad_y + (line_h - th) * 0.5
    draw_text(text, bx + pad_x, baseline, size,
              (text_col[0], text_col[1], text_col[2], 1.0))


def draw_palettes():
    """Shared callback: works out which editor it is drawing in."""
    region = getattr(bpy.context, "region", None)
    area = getattr(bpy.context, "area", None)
    if region is None or area is None or region.type != 'WINDOW':
        return
    palettes = palettes_for_area(area.type, current_area_key())
    if not palettes:
        return
    gpu.state.blend_set('ALPHA')
    try:
        for index, palette in palettes:
            draw_one(region, index, palette)
    finally:
        gpu.state.blend_set('NONE')


def redraw_views():
    wanted = active_space_types() | set(_handles)
    try:
        for win in bpy.context.window_manager.windows:
            for area in win.screen.areas:
                if area.type in wanted:
                    area.tag_redraw()
    except Exception:
        pass


def enable_draw():
    """Add or drop handlers so they match the editors currently asked for."""
    wanted = active_space_types()

    for space_type in list(_handles):
        if space_type in wanted:
            continue
        cls = space_class(space_type)
        if cls is not None:
            try:
                cls.draw_handler_remove(_handles[space_type], 'WINDOW')
            except Exception:
                pass
        del _handles[space_type]

    for space_type in wanted:
        if space_type in _handles:
            continue
        cls = space_class(space_type)
        if cls is None:
            continue                # editor missing on this Blender version
        try:
            _handles[space_type] = cls.draw_handler_add(
                draw_palettes, (), 'WINDOW', 'POST_PIXEL')
        except Exception:
            pass


def disable_draw():
    for space_type, handle in list(_handles.items()):
        cls = space_class(space_type)
        if cls is not None:
            try:
                cls.draw_handler_remove(handle, 'WINDOW')
            except Exception:
                pass
        del _handles[space_type]
    _hover[0] = -1
    _hover[1] = -1
    _live.clear()
    free_textures()
    redraw_views()


def region_under_mouse(event):
    """(window, area, region) under the cursor, in an editor a palette uses."""
    wanted = active_space_types()
    for win in bpy.context.window_manager.windows:
        for area in win.screen.areas:
            if area.type not in wanted:
                continue
            for region in area.regions:
                if region.type != 'WINDOW':
                    continue
                if (region.x <= event.mouse_x < region.x + region.width and
                        region.y <= event.mouse_y < region.y + region.height):
                    return win, area, region
    return None, None, None


def palette_under_mouse(area_type, region, mx, my, key=""):
    """Topmost palette under the cursor: (index, palette, layout, entries)."""
    for index, palette in reversed(palettes_for_area(area_type, key)):
        entries = palette_entries(index, palette)
        if not entries:
            continue
        lay = layout_for(region, index, palette, len(entries))
        if (lay["x"] <= mx <= lay["x"] + lay["w"] and
                lay["y"] <= my <= lay["y"] + lay["h"]):
            return index, palette, lay, entries
    return None, None, None, None


# --------------------------------------------------------------------------- #
#  palette operators
# --------------------------------------------------------------------------- #

class ES_OT_tools_hud(Operator):
    """Modal operator that keeps the palettes alive and handles their clicks."""
    bl_idname = "es_tools.hud"
    bl_label = "ES Tools Palette (internal)"
    bl_options = {'INTERNAL'}

    def invoke(self, context, event):
        st = store()
        if st.running:
            return {'CANCELLED'}
        st.running = True
        self._drag = -1
        self._armed = (-1, -1)
        self._grab = (0.0, 0.0)
        self._region = None
        enable_draw()
        context.window_manager.modal_handler_add(self)
        redraw_views()
        return {'RUNNING_MODAL'}

    def _finish(self):
        st = store()
        st.running = False
        st.wanted = False
        disable_draw()
        return {'FINISHED'}

    def modal(self, context, event):
        st = store()
        if not any_visible():
            return self._finish()
        st.wanted = True

        p = prefs()
        if p is None:
            return self._finish()

        # --- dragging: keep using the region the drag started in ------------
        if self._drag >= 0:
            if event.type == 'LEFTMOUSE' and event.value == 'RELEASE':
                self._commit_drag(p)
                return {'RUNNING_MODAL'}
            if event.type in {'RIGHTMOUSE', 'ESC'}:
                self._commit_drag(p)
                return {'RUNNING_MODAL'}
            if event.type == 'MOUSEMOVE':
                try:
                    rx, ry = self._region.x, self._region.y
                except Exception:
                    self._drag = -1
                    return {'RUNNING_MODAL'}
                _live[self._drag] = ((event.mouse_x - rx) - self._grab[0],
                                     (event.mouse_y - ry) - self._grab[1])
                redraw_views()
            return {'RUNNING_MODAL'}

        win, area, region = region_under_mouse(event)
        if region is None:
            if _hover[0] != -1:
                _hover[0] = -1
                _hover[1] = -1
                redraw_views()
            return {'PASS_THROUGH'}

        mx = event.mouse_x - region.x
        my = event.mouse_y - region.y
        index, palette, lay, entries = palette_under_mouse(
            area.type, region, mx, my, area_key(win.screen, area))

        if event.type == 'MOUSEMOVE':
            if index is None:
                hover = (-1, -1)
            elif hit_button(mx, my, lay):
                hover = (index, -2)
            elif hit_pin(mx, my, lay):
                hover = (index, -3)
            else:
                hover = (index, icon_at(mx, my, lay))
            if [hover[0], hover[1]] != _hover:
                _hover[0], _hover[1] = hover
                redraw_views()
            return {'PASS_THROUGH'}

        if event.type == 'LEFTMOUSE' and event.value == 'PRESS' and index is not None:
            if hit_button(mx, my, lay):
                palette.vertical = not palette.vertical
                redraw_views()
                return {'RUNNING_MODAL'}
            if hit_pin(mx, my, lay):
                toggle_pin(palette, win, area)
                return {'RUNNING_MODAL'}
            hit = icon_at(mx, my, lay)
            if hit >= 0:
                # Arm on press, fire on release, the way a normal button
                # behaves.  It also matters for entries that open a menu: a
                # popup created while the button is still down treats the
                # ongoing press as a drag-select, so it closes the moment the
                # button comes up and has to be held open instead.
                self._armed = (index, hit)
                return {'RUNNING_MODAL'}
            self._drag = index
            self._region = region
            self._grab = (mx - lay["x"], my - lay["y"])
            _live[index] = (lay["x"], lay["y"])
            return {'RUNNING_MODAL'}

        if event.type == 'LEFTMOUSE' and event.value == 'RELEASE':
            armed = self._armed
            self._armed = (-1, -1)
            if armed[0] < 0:
                return {'RUNNING_MODAL'} if index is not None else {'PASS_THROUGH'}
            # only counts if the release lands on the icon the press started on
            if index == armed[0] and icon_at(mx, my, lay) == armed[1]:
                activate(entries[armed[1]], (win, area, region))
                redraw_views()
            return {'RUNNING_MODAL'}

        if event.type in {'RIGHTMOUSE', 'ESC'} and self._armed[0] >= 0:
            self._armed = (-1, -1)
            return {'RUNNING_MODAL'}

        return {'PASS_THROUGH'}

    def _commit_drag(self, p):
        """Positions live in a volatile dict while dragging; persist on release."""
        index = self._drag
        self._drag = -1
        pos = _live.pop(index, None)
        if pos is None or not (0 <= index < len(p.palettes)):
            return
        palette = p.palettes[index]
        palette.pos_x, palette.pos_y = pos
        redraw_views()


def toggle_pin(palette, win, area):
    """Tie a palette to this one area, or let it follow its editor list again."""
    if palette.pinned:
        palette.pinned = ""
        open_sidebar_report("Palette \"%s\" unpinned" % palette.name)
    else:
        key = area_key(win.screen if win else None, area)
        if not key:
            open_sidebar_report("Could not identify this area")
            return
        palette.pinned = key
        # keep the editor list in step, so the draw handler stays registered
        try:
            palette.spaces = {area.type}
        except Exception:
            pass
        open_sidebar_report("Palette \"%s\" pinned to this area" % palette.name)
    refresh_palettes_soon()


def start_palettes():
    st = store()
    if st.running:
        return True
    win, area, region = find_area()
    if win is None:
        return False
    try:
        with bpy.context.temp_override(window=win, area=area, region=region):
            bpy.ops.es_tools.hud('INVOKE_DEFAULT')
    except Exception:
        return False
    return True


def refresh_palettes():
    """Start or stop the modal so it matches the palettes' visible flags."""
    st = store()
    if any_visible():
        st.wanted = True
        enable_draw()               # editors may have been added or removed
        if not st.running:
            start_palettes()
        clear_auto_icons()          # an add-on may have been installed since
        clear_gates()               # pick up panels registered since last time
        sync_gates()
    else:
        st.wanted = False           # the live modal notices and cleans up
        sync_gates_soon()           # gated tabs come back while hidden
    redraw_views()


def refresh_palettes_soon():
    def run():
        refresh_palettes()
        return None
    bpy.app.timers.register(run, first_interval=0.0)


def on_visible_changed(self, context):
    refresh_palettes_soon()


def on_spaces_changed(self, context):
    refresh_palettes_soon()


class ES_OT_tools_palette(Operator):
    """Toggle a floating ES Tools palette"""
    bl_idname = "es_tools.palette"
    bl_label = "ES Tools Palette"
    bl_description = "Toggle a floating ES Tools palette (drag it anywhere)"

    index: IntProperty(
        name="Palette",
        description="Palette to toggle; -1 toggles all of them at once",
        default=-1,
    )

    def execute(self, context):
        p = prefs()
        if p is None:
            return {'CANCELLED'}
        if not len(p.palettes):
            self.report({'WARNING'},
                        "No palettes yet - add one in the ES Tools Hub preferences")
            return {'CANCELLED'}

        if self.index < 0:
            show = not any_visible()
            for palette in p.palettes:
                palette.visible = show
        elif self.index < len(p.palettes):
            palette = p.palettes[self.index]
            palette.visible = not palette.visible
        else:
            self.report({'WARNING'}, "Palette %d does not exist" % (self.index + 1))
            return {'CANCELLED'}

        if any_visible() and find_area()[0] is None:
            for palette in p.palettes:
                palette.visible = False
            self.report({'WARNING'},
                        "None of the editors these palettes use are open")
            return {'CANCELLED'}

        refresh_palettes()
        return {'FINISHED'}


@persistent
def on_load(_dummy):
    """Modal operators die on file load - bring the palettes back."""
    st = store()
    st.running = False
    _textures.clear()
    _images.clear()

    def restart():
        refresh_palettes()
        return None

    bpy.app.timers.register(restart, first_interval=0.2)


# --------------------------------------------------------------------------- #
#  preferences
# --------------------------------------------------------------------------- #

KEY_ITEMS = ([('NONE', "None", "No shortcut")] +
             [(c, c, "") for c in "ABCDEFGHIJKLMNOPQRSTUVWXYZ"] +
             [("F%d" % i, "F%d" % i, "") for i in range(1, 13)])


SPACE_ICONS = {
    'VIEW_3D': 'VIEW3D',
    'IMAGE_EDITOR': 'IMAGE',
    'NODE_EDITOR': 'NODETREE',
    'TEXT_EDITOR': 'TEXT',
    'SEQUENCE_EDITOR': 'SEQUENCE',
    'CLIP_EDITOR': 'TRACKER',
    'DOPESHEET_EDITOR': 'ACTION',
    'GRAPH_EDITOR': 'GRAPH',
    'NLA_EDITOR': 'NLA',
    'SPREADSHEET': 'SPREADSHEET',
}


def on_keymap_changed(self, context):
    keymap_unregister()
    keymap_register()


class ESHUB_Entry(PropertyGroup):
    name: StringProperty(
        name="Name",
        description="Shown when hovering the icon in the palette",
        default="New Entry",
    )
    mode: EnumProperty(
        name="Action",
        description="What clicking this icon does",
        items=[
            ('CATEGORY', "Sidebar Tab",
             "Open the 3D Viewport sidebar on a named tab"),
            ('OPERATOR', "Operator",
             "Run an operator, e.g. wm.call_menu or object.shade_smooth"),
            ('MENU', "Menu",
             "Open a menu by its identifier, e.g. OBJECT_MT_modifier_add"),
            ('MODIFIER', "Modifier",
             "Add one specific modifier to the active object"),
            ('MODIFIERS', "Modifier Menu",
             "Open a grid of every Blender modifier, with its own icons"),
        ],
        default='CATEGORY',
        update=on_entry_changed,
    )
    category: StringProperty(
        name="Tab",
        description="Sidebar tab name, exactly as it appears in the N-panel",
        default="",
        update=on_entry_changed,
    )
    hide_tab: BoolProperty(
        name="Hide Tab Until Picked",
        description="Hide this add-on's sidebar tab until its palette icon is "
                    "clicked. No changes to the other add-on are needed. The "
                    "tab reappears whenever this palette is hidden",
        default=True,
        update=on_entry_changed,
    )
    operator: StringProperty(
        name="Operator",
        description="Operator id, e.g. object.shade_smooth",
        default="",
    )
    modifier_type: StringProperty(
        name="Modifier",
        description="Modifier type identifier, e.g. SUBSURF or BEVEL",
        default="",
    )
    menu_id: StringProperty(
        name="Menu",
        description="Menu identifier, e.g. OBJECT_MT_modifier_add or "
                    "VIEW3D_MT_add",
        default="",
    )
    auto_icon: BoolProperty(
        name="Use Add-on's Own Icon",
        description="Look for icons/icon.png (or icon/icon.png) inside the "
                    "add-on this entry points at, and use it automatically",
        default=True,
        update=on_icon_changed,
    )
    label_color: FloatVectorProperty(
        name="Text Color",
        description="Colour of the initials drawn when this entry has no icon",
        subtype='COLOR',
        size=4, min=0.0, max=1.0,
        default=(0.92, 0.92, 0.92, 1.0),
    )
    icon_path: StringProperty(
        name="Icon Override",
        description="Square PNG, 128-256 px, transparent background. Leave "
                    "empty to use the add-on's own icon, or the entry's "
                    "initials when it has none",
        subtype='FILE_PATH',
        default="",
        update=on_icon_changed,
    )


class ESHUB_Palette(PropertyGroup):
    name: StringProperty(name="Name", default="Palette")
    visible: BoolProperty(
        name="Show",
        description="Show this palette in the 3D Viewport",
        default=False,
        update=on_visible_changed,
    )
    entries: CollectionProperty(type=ESHUB_Entry)
    active_index: IntProperty(default=0)

    include_providers: BoolProperty(
        name="Include ES add-ons",
        description="Show every installed ES add-on in this palette",
        default=False,
    )
    icon_size: IntProperty(
        name="Icon Size",
        description="Icon size in pixels, before UI scale",
        default=32, min=16, max=64,
    )
    spaces: EnumProperty(
        name="Editors",
        description="Editors this palette is drawn in",
        items=SPACE_ITEMS,
        options={'ENUM_FLAG'},
        default={'VIEW_3D'},
        update=on_spaces_changed,
    )
    pinned: StringProperty(
        name="Pinned Area",
        description="When set, this palette is drawn only in that one area",
        default="",
    )
    vertical: BoolProperty(name="Vertical", default=False)
    pos_x: FloatProperty(default=40.0)
    pos_y: FloatProperty(default=40.0)

    key: EnumProperty(
        name="Key", description="Shortcut key for this palette",
        items=KEY_ITEMS, default='NONE', update=on_keymap_changed,
    )
    use_shift: BoolProperty(name="Shift", default=True, update=on_keymap_changed)
    use_ctrl: BoolProperty(name="Ctrl", default=False, update=on_keymap_changed)
    use_alt: BoolProperty(name="Alt", default=True, update=on_keymap_changed)

    def shortcut_text(self):
        if self.key == 'NONE':
            return ""
        parts = []
        if self.use_ctrl:
            parts.append("Ctrl")
        if self.use_alt:
            parts.append("Alt")
        if self.use_shift:
            parts.append("Shift")
        parts.append(self.key)
        return "+".join(parts)


class ESHUB_UL_palettes(UIList):
    def draw_item(self, context, layout, data, item, icon, active_data,
                  active_propname, index):
        row = layout.row(align=True)
        row.prop(item, "visible", text="",
                 icon='HIDE_OFF' if item.visible else 'HIDE_ON', emboss=False)
        row.prop(item, "name", text="", emboss=False)
        sub = row.row()
        sub.alignment = 'RIGHT'
        sub.label(text="%d  %s" % (len(item.entries), item.shortcut_text()))
        if item.pinned:
            sub.label(text="", icon='PINNED')
        sub.label(text="", icon=SPACE_ICONS.get(
            sorted(item.spaces)[0] if item.spaces else 'VIEW_3D', 'BLANK1'))


class ESHUB_UL_entries(UIList):
    def draw_item(self, context, layout, data, item, icon, active_data,
                  active_propname, index):
        row = layout.row(align=True)
        row.prop(item, "name", text="", emboss=False,
                 icon='FILE_IMAGE' if item.icon_path else 'DOT')
        sub = row.row()
        sub.alignment = 'RIGHT'
        if item.mode == 'CATEGORY':
            detail = item.category
        elif item.mode == 'OPERATOR':
            detail = item.operator
        elif item.mode == 'MENU':
            detail = item.menu_id
        elif item.mode == 'MODIFIER':
            detail = item.modifier_type
        else:
            detail = "all modifiers"
        sub.label(text=detail)


class ESHUB_MT_modifier_types(Menu):
    """Every modifier, drawn with the icon Blender uses for it."""
    bl_idname = "ESHUB_MT_modifier_types"
    bl_label = "Modifiers"

    # set by whichever button opened this menu
    mode = 'SET'

    def draw(self, context):
        layout = self.layout
        groups = modifier_groups()
        if not groups:
            layout.label(text="No modifiers found", icon='INFO')
            return
        row = layout.row()
        for name, items in groups:
            column = row.column(align=True)
            if name:
                column.label(text=name)
            for item in items:
                op = column.operator("es_hub.set_modifier", text=item.name,
                                     icon=item.icon or 'MODIFIER')
                op.modifier_type = item.identifier
                op.as_new_entry = (ESHUB_MT_modifier_types.mode == 'NEW')


class ESHUB_OT_open_modifier_types(Operator):
    """Choose a modifier"""
    bl_idname = "es_hub.open_modifier_types"
    bl_label = "Choose Modifier"
    bl_options = {'INTERNAL'}

    as_new_entry: BoolProperty(default=False)

    def execute(self, context):
        ESHUB_MT_modifier_types.mode = 'NEW' if self.as_new_entry else 'SET'
        bpy.ops.wm.call_menu('INVOKE_DEFAULT', name="ESHUB_MT_modifier_types")
        return {'FINISHED'}


class ESHUB_OT_set_modifier(Operator):
    """Use this modifier"""
    bl_idname = "es_hub.set_modifier"
    bl_label = "Set Modifier"
    bl_options = {'INTERNAL'}

    modifier_type: StringProperty()
    as_new_entry: BoolProperty(default=False)

    def execute(self, context):
        _index, palette = active_palette()
        if palette is None:
            return {'CANCELLED'}
        item = modifier_item(self.modifier_type)

        if self.as_new_entry:
            entry = palette.entries.add()
            entry.name = item.name if item else self.modifier_type.title()
            entry.mode = 'MODIFIER'
            entry.modifier_type = self.modifier_type
            palette.active_index = len(palette.entries) - 1
        else:
            if not (0 <= palette.active_index < len(palette.entries)):
                return {'CANCELLED'}
            entry = palette.entries[palette.active_index]
            entry.modifier_type = self.modifier_type
            if entry.name in ("", "New Entry") and item:
                entry.name = item.name

        redraw_views()
        return {'FINISHED'}


class ESHUB_MT_menu_proxy(Menu):
    """Draws another menu's contents with the operator context fixed up."""
    bl_idname = "ESHUB_MT_menu_proxy"
    bl_label = ""

    # set by run_menu just before the popup is opened
    target = ""

    def draw(self, context):
        layout = self.layout
        # the whole point of the proxy: items invoke instead of executing
        layout.operator_context = 'INVOKE_DEFAULT'
        target = ESHUB_MT_menu_proxy.target
        if not target or not hasattr(bpy.types, target):
            layout.label(text="No menu named \"%s\"" % target, icon='ERROR')
            return
        layout.menu_contents(target)


class ESHUB_MT_menu_presets(Menu):
    bl_idname = "ESHUB_MT_menu_presets"
    bl_label = "Common Menus"

    PRESETS = (
        ("TOPBAR_MT_file_import", "Import"),
        ("TOPBAR_MT_file_export", "Export"),
        ("TOPBAR_MT_file", "File"),
        ("TOPBAR_MT_file_new", "New File"),
        ("TOPBAR_MT_window", "Window"),
        ("OBJECT_MT_modifier_add", "Add Modifier"),
        ("VIEW3D_MT_add", "Add Object"),
        ("VIEW3D_MT_object", "Object"),
        ("VIEW3D_MT_object_apply", "Apply"),
        ("VIEW3D_MT_snap", "Snap"),
        ("VIEW3D_MT_mesh_add", "Add Mesh"),
        ("VIEW3D_MT_edit_mesh", "Mesh (Edit Mode)"),
        ("VIEW3D_MT_uv_map", "UV Mapping"),
        ("VIEW3D_MT_object_parent", "Parent"),
        ("VIEW3D_MT_make_links", "Link/Transfer Data"),
    )

    def draw(self, context):
        layout = self.layout
        column = layout.column(align=True)
        for idname, label in self.PRESETS:
            if not hasattr(bpy.types, idname):
                continue
            column.operator("es_hub.set_menu", text=label).menu_id = idname


class ESHUB_OT_set_menu(Operator):
    """Use this menu for the selected entry"""
    bl_idname = "es_hub.set_menu"
    bl_label = "Set Menu"
    bl_options = {'INTERNAL'}

    menu_id: StringProperty()

    def execute(self, context):
        _index, palette = active_palette()
        if palette is None or not (0 <= palette.active_index < len(palette.entries)):
            return {'CANCELLED'}
        palette.entries[palette.active_index].menu_id = self.menu_id
        redraw_views()
        return {'FINISHED'}


class ESHUB_MT_categories(Menu):
    bl_idname = "ESHUB_MT_categories"
    bl_label = "Sidebar Tabs"

    def draw(self, context):
        layout = self.layout
        categories = sidebar_categories()
        if not categories:
            layout.label(text="No sidebar tabs found", icon='INFO')
            return
        column = layout.column(align=True)
        for i, category in enumerate(categories):
            if i and i % 20 == 0:
                column = layout.column(align=True)
            column.operator("es_hub.set_category", text=category).category = category


def active_palette():
    p = prefs()
    if p is None or not (0 <= p.active_palette < len(p.palettes)):
        return None, None
    return p.active_palette, p.palettes[p.active_palette]


class ESHUB_OT_set_category(Operator):
    """Use this sidebar tab for the selected entry"""
    bl_idname = "es_hub.set_category"
    bl_label = "Set Tab"
    bl_options = {'INTERNAL'}

    category: StringProperty()

    def execute(self, context):
        _index, palette = active_palette()
        if palette is None or not (0 <= palette.active_index < len(palette.entries)):
            return {'CANCELLED'}
        palette.entries[palette.active_index].category = self.category
        clear_auto_icons()
        redraw_views()
        return {'FINISHED'}


class ESHUB_OT_palette_add(Operator):
    """Add a palette"""
    bl_idname = "es_hub.palette_add"
    bl_label = "Add Palette"
    bl_options = {'INTERNAL'}

    def execute(self, context):
        p = prefs()
        if p is None:
            return {'CANCELLED'}
        palette = p.palettes.add()
        palette.name = "Palette %d" % len(p.palettes)
        # stack new palettes upwards so they do not land on top of each other
        palette.pos_x = 40.0
        palette.pos_y = 40.0 + 70.0 * (len(p.palettes) - 1)
        p.active_palette = len(p.palettes) - 1
        redraw_views()
        return {'FINISHED'}


class ESHUB_OT_palette_remove(Operator):
    """Remove the selected palette"""
    bl_idname = "es_hub.palette_remove"
    bl_label = "Remove Palette"
    bl_options = {'INTERNAL'}

    def execute(self, context):
        p = prefs()
        if p is None or not (0 <= p.active_palette < len(p.palettes)):
            return {'CANCELLED'}
        p.palettes.remove(p.active_palette)
        p.active_palette = min(p.active_palette, len(p.palettes) - 1)
        free_textures()
        _live.clear()
        keymap_unregister()
        keymap_register()
        sync_gates_soon()
        refresh_palettes_soon()
        return {'FINISHED'}


class ESHUB_OT_palette_move(Operator):
    """Move the selected palette in the list"""
    bl_idname = "es_hub.palette_move"
    bl_label = "Move Palette"
    bl_options = {'INTERNAL'}

    direction: EnumProperty(items=[('UP', "Up", ""), ('DOWN', "Down", "")])

    def execute(self, context):
        p = prefs()
        if p is None:
            return {'CANCELLED'}
        index = p.active_palette
        target = index - 1 if self.direction == 'UP' else index + 1
        if not (0 <= index < len(p.palettes)) or not (0 <= target < len(p.palettes)):
            return {'CANCELLED'}
        p.palettes.move(index, target)
        p.active_palette = target
        free_textures()
        _live.clear()
        keymap_unregister()
        keymap_register()
        redraw_views()
        return {'FINISHED'}


class ESHUB_OT_entry_add(Operator):
    """Add an entry to the selected palette"""
    bl_idname = "es_hub.entry_add"
    bl_label = "Add Entry"
    bl_options = {'INTERNAL'}

    def execute(self, context):
        _index, palette = active_palette()
        if palette is None:
            return {'CANCELLED'}
        item = palette.entries.add()
        item.name = "New Entry"
        palette.active_index = len(palette.entries) - 1
        redraw_views()
        return {'FINISHED'}


class ESHUB_OT_entry_remove(Operator):
    """Remove the selected entry"""
    bl_idname = "es_hub.entry_remove"
    bl_label = "Remove Entry"
    bl_options = {'INTERNAL'}

    def execute(self, context):
        _index, palette = active_palette()
        if palette is None or not (0 <= palette.active_index < len(palette.entries)):
            return {'CANCELLED'}
        palette.entries.remove(palette.active_index)
        palette.active_index = min(palette.active_index, len(palette.entries) - 1)
        free_textures()
        sync_gates_soon()
        redraw_views()
        return {'FINISHED'}


class ESHUB_OT_entry_move(Operator):
    """Move the selected entry in the palette order"""
    bl_idname = "es_hub.entry_move"
    bl_label = "Move Entry"
    bl_options = {'INTERNAL'}

    direction: EnumProperty(items=[('UP', "Up", ""), ('DOWN', "Down", "")])

    def execute(self, context):
        _index, palette = active_palette()
        if palette is None:
            return {'CANCELLED'}
        index = palette.active_index
        target = index - 1 if self.direction == 'UP' else index + 1
        if not (0 <= index < len(palette.entries)) or not (0 <= target < len(palette.entries)):
            return {'CANCELLED'}
        palette.entries.move(index, target)
        palette.active_index = target
        free_textures()
        redraw_views()
        return {'FINISHED'}


class ESHUB_OT_reset_placement(Operator):
    """Move the selected palette back to the bottom left of the viewport"""
    bl_idname = "es_hub.reset_placement"
    bl_label = "Reset Position"
    bl_options = {'INTERNAL'}

    def execute(self, context):
        index, palette = active_palette()
        if palette is None:
            return {'CANCELLED'}
        _live.pop(index, None)
        palette.pos_x = 40.0
        palette.pos_y = 40.0
        redraw_views()
        return {'FINISHED'}


ENTRY_FIELDS = ("name", "mode", "category", "hide_tab", "operator",
                "menu_id", "modifier_type", "auto_icon", "icon_path")
PALETTE_FIELDS = ("name", "visible", "include_providers", "icon_size",
                  "vertical", "pos_x", "pos_y", "key", "use_shift",
                  "use_ctrl", "use_alt", "pinned")


def palettes_to_data(only_active=False):
    p = prefs()
    if p is None:
        return {"version": 1, "palettes": []}

    if only_active:
        _index, palette = active_palette()
        palettes = [palette] if palette is not None else []
    else:
        palettes = list(p.palettes)

    out = []
    for palette in palettes:
        record = {field: getattr(palette, field) for field in PALETTE_FIELDS}
        record["spaces"] = sorted(palette.spaces)
        record["entries"] = []
        for item in palette.entries:
            entry = {field: getattr(item, field) for field in ENTRY_FIELDS}
            entry["label_color"] = list(item.label_color)
            record["entries"].append(entry)
        out.append(record)
    return {"version": 1, "palettes": out}


def data_to_palettes(data, replace=False):
    """Returns how many palettes were read, or -1 if the file made no sense."""
    p = prefs()
    if p is None:
        return -1
    records = data.get("palettes") if isinstance(data, dict) else None
    if not isinstance(records, list):
        return -1

    if replace:
        p.palettes.clear()

    added = 0
    for record in records:
        if not isinstance(record, dict):
            continue
        palette = p.palettes.add()
        for field in PALETTE_FIELDS:
            if field in record:
                try:
                    setattr(palette, field, record[field])
                except Exception:
                    pass
        spaces = record.get("spaces")
        if spaces:
            try:
                palette.spaces = set(spaces)
            except Exception:
                pass
        for entry_data in record.get("entries", []):
            if not isinstance(entry_data, dict):
                continue
            item = palette.entries.add()
            for field in ENTRY_FIELDS:
                if field in entry_data:
                    try:
                        setattr(item, field, entry_data[field])
                    except Exception:
                        pass
            color = entry_data.get("label_color")
            if color:
                try:
                    item.label_color = color
                except Exception:
                    pass
        added += 1

    p.active_palette = max(0, len(p.palettes) - 1)
    return added


class ESHUB_OT_export_palettes(Operator):
    """Save palettes to a .json file"""
    bl_idname = "es_hub.export_palettes"
    bl_label = "Save Palettes"

    filepath: StringProperty(subtype='FILE_PATH')
    filter_glob: StringProperty(default="*.json", options={'HIDDEN'})
    only_active: BoolProperty(
        name="Selected Palette Only",
        description="Save just the highlighted palette instead of all of them",
        default=False,
    )

    def invoke(self, context, event):
        if not self.filepath:
            self.filepath = "es_palettes.json"
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}

    def execute(self, context):
        import json
        path = self.filepath
        if not path.lower().endswith(".json"):
            path += ".json"
        data = palettes_to_data(self.only_active)
        try:
            with open(path, "w", encoding="utf-8") as handle:
                json.dump(data, handle, indent=2)
        except Exception as error:
            self.report({'ERROR'}, "Could not write that file: %s" % error)
            return {'CANCELLED'}
        self.report({'INFO'}, "Saved %d palette(s)" % len(data["palettes"]))
        return {'FINISHED'}


class ESHUB_OT_import_palettes(Operator):
    """Load palettes from a .json file"""
    bl_idname = "es_hub.import_palettes"
    bl_label = "Load Palettes"

    filepath: StringProperty(subtype='FILE_PATH')
    filter_glob: StringProperty(default="*.json", options={'HIDDEN'})
    replace: BoolProperty(
        name="Replace Existing",
        description="Remove the current palettes instead of adding to them",
        default=False,
    )

    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}

    def execute(self, context):
        import json
        try:
            with open(self.filepath, "r", encoding="utf-8") as handle:
                data = json.load(handle)
        except Exception as error:
            self.report({'ERROR'}, "Could not read that file: %s" % error)
            return {'CANCELLED'}

        added = data_to_palettes(data, self.replace)
        if added < 0:
            self.report({'ERROR'}, "That file holds no palettes")
            return {'CANCELLED'}

        free_textures()
        clear_auto_icons()
        keymap_unregister()
        keymap_register()
        sync_gates_soon()
        refresh_palettes_soon()
        self.report({'INFO'}, "Loaded %d palette(s)" % added)
        return {'FINISHED'}


class ESHUB_OT_refresh_tabs(Operator):
    """Re-apply tab hiding

    Run this after enabling another add-on, so its panels are picked up
    """
    bl_idname = "es_hub.refresh_tabs"
    bl_label = "Refresh Tabs"
    bl_options = {'INTERNAL'}

    def execute(self, context):
        clear_gates()
        sync_gates()
        return {'FINISHED'}


def pinned_label(pinned):
    """Human-readable form of an area key."""
    parts = pinned.split("|")
    if len(parts) == 3:
        return "%s, area %s (%s)" % (parts[0], int(parts[1]) + 1,
                                     parts[2].replace("_", " ").title())
    return pinned


class ESHUB_OT_unpin(Operator):
    """Let this palette appear in every editor it is set to again"""
    bl_idname = "es_hub.unpin"
    bl_label = "Unpin"
    bl_options = {'INTERNAL'}

    def execute(self, context):
        _index, palette = active_palette()
        if palette is None:
            return {'CANCELLED'}
        palette.pinned = ""
        refresh_palettes_soon()
        return {'FINISHED'}


class ESHUB_OT_refresh_icons(Operator):
    """Look for add-on icons again

    Run this after installing another add-on, or after replacing an icon file
    """
    bl_idname = "es_hub.refresh_icons"
    bl_label = "Refresh Icons"
    bl_options = {'INTERNAL'}

    def execute(self, context):
        clear_auto_icons()
        redraw_views()
        return {'FINISHED'}


class ESHUB_OT_modifier_popup(Operator):
    """Add a modifier to the active object"""
    bl_idname = "es_hub.modifier_popup"
    bl_label = "Add Modifier"

    def invoke(self, context, event):
        return context.window_manager.invoke_popup(self, width=560)

    def draw(self, context):
        layout = self.layout
        obj = context.object

        row = layout.row()
        row.label(text="Add Modifier", icon='MODIFIER')
        sub = row.row()
        sub.alignment = 'RIGHT'
        sub.operator("wm.call_menu", text="Blender's Menu",
                     icon='DOWNARROW_HLT').name = "OBJECT_MT_modifier_add"

        if obj is None:
            layout.label(text="No active object", icon='INFO')
            return

        groups = modifier_groups(obj.type)
        if not groups:
            layout.label(text="No modifiers for a %s object"
                              % obj.type.title(), icon='INFO')
            return

        layout.separator()
        layout.operator_context = 'INVOKE_DEFAULT'
        grid = layout.grid_flow(row_major=False, columns=len(groups),
                                even_columns=True, align=False)
        for name, items in groups:
            column = grid.column(align=True)
            if name:
                column.label(text=name)
            for item in items:
                op = column.operator("object.modifier_add", text=item.name,
                                     icon=item.icon or 'MODIFIER')
                op.type = item.identifier

    def execute(self, context):
        return {'FINISHED'}


class ESHUB_Prefs(AddonPreferences):
    bl_idname = __package__

    palettes: CollectionProperty(type=ESHUB_Palette)
    active_palette: IntProperty(default=0)

    # kept so a v1 setup is carried over on first run of v2
    entries: CollectionProperty(type=ESHUB_Entry)
    include_providers: BoolProperty(default=True)
    icon_size: IntProperty(default=32)
    pos_x: FloatProperty(default=40.0)
    pos_y: FloatProperty(default=40.0)
    vertical: BoolProperty(default=False)
    migrated: BoolProperty(default=False)

    def draw(self, context):
        layout = self.layout

        row = layout.row()
        row.scale_y = 1.3
        op = row.operator("es_tools.palette",
                          text="Hide All" if any_visible() else "Show All",
                          icon='HIDE_ON' if any_visible() else 'HIDE_OFF',
                          depress=any_visible())
        op.index = -1
        row.operator("es_hub.refresh_tabs", icon='FILE_REFRESH')
        row.operator("es_hub.refresh_icons", icon='IMAGE_DATA')

        row = layout.row(align=True)
        row.operator("es_hub.export_palettes", icon='EXPORT')
        row.operator("es_hub.import_palettes", icon='IMPORT')

        # --- palettes ---
        box = layout.box()
        box.label(text="Palettes", icon='PRESET')
        row = box.row()
        row.template_list("ESHUB_UL_palettes", "", self, "palettes",
                          self, "active_palette", rows=3)
        column = row.column(align=True)
        column.operator("es_hub.palette_add", text="", icon='ADD')
        column.operator("es_hub.palette_remove", text="", icon='REMOVE')
        column.separator()
        column.operator("es_hub.palette_move", text="", icon='TRIA_UP').direction = 'UP'
        column.operator("es_hub.palette_move", text="", icon='TRIA_DOWN').direction = 'DOWN'

        if not len(self.palettes):
            box.label(text="Add a palette to get started", icon='INFO')
            return

        index, palette = active_palette()
        if palette is None:
            return

        settings = box.column()
        settings.use_property_split = True
        settings.use_property_decorate = False
        settings.prop(palette, "include_providers")
        settings.prop(palette, "icon_size")
        settings.prop(palette, "vertical")

        if palette.pinned:
            box_row = settings.row(align=True)
            box_row.label(text="Pinned to %s" % pinned_label(palette.pinned),
                          icon='PINNED')
            box_row.operator("es_hub.unpin", text="", icon='X')
        else:
            settings.label(text="Shown in every editor ticked below",
                           icon='UNPINNED')

        column = settings.column(align=True)
        column.enabled = not palette.pinned
        column.label(text="Editors:")
        grid = column.grid_flow(row_major=True, columns=3, even_columns=True,
                                align=True)
        grid.prop(palette, "spaces", expand=True)
        if not palette.spaces:
            column.label(text="Pick at least one editor - defaulting to the "
                              "3D Viewport", icon='INFO')
        settings.prop(palette, "key")
        row = settings.row(align=True)
        row.prop(palette, "use_ctrl", toggle=True)
        row.prop(palette, "use_alt", toggle=True)
        row.prop(palette, "use_shift", toggle=True)
        settings.operator("es_hub.reset_placement", icon='LOOP_BACK')

        # --- entries of the selected palette ---
        box = layout.box()
        box.label(text="Entries in \"%s\"" % palette.name, icon='OUTLINER')
        row = box.row()
        row.template_list("ESHUB_UL_entries", "", palette, "entries",
                          palette, "active_index", rows=4)
        column = row.column(align=True)
        column.operator("es_hub.entry_add", text="", icon='ADD')
        column.operator("es_hub.entry_remove", text="", icon='REMOVE')
        column.separator()
        column.operator("es_hub.entry_move", text="", icon='TRIA_UP').direction = 'UP'
        column.operator("es_hub.entry_move", text="", icon='TRIA_DOWN').direction = 'DOWN'
        column.separator()
        column.operator("es_hub.open_modifier_types", text="",
                        icon='MODIFIER').as_new_entry = True

        if 0 <= palette.active_index < len(palette.entries):
            item = palette.entries[palette.active_index]
            detail = box.column()
            detail.use_property_split = True
            detail.use_property_decorate = False
            detail.prop(item, "name")
            detail.prop(item, "mode")
            if item.mode == 'CATEGORY':
                row = detail.row(align=True)
                row.prop(item, "category")
                row.menu("ESHUB_MT_categories", text="", icon='DOWNARROW_HLT')
                if item.category and item.category not in sidebar_categories():
                    detail.label(
                        text="No sidebar tab named \"%s\" is registered yet"
                             % item.category, icon='ERROR')
                sub = detail.row()
                sub.enabled = item.category not in PROTECTED_CATEGORIES
                sub.prop(item, "hide_tab")
                if item.category in PROTECTED_CATEGORIES:
                    detail.label(text="\"%s\" is a built-in tab and is never hidden"
                                      % item.category, icon='INFO')
            elif item.mode == 'OPERATOR':
                detail.prop(item, "operator")
            elif item.mode == 'MODIFIER':
                found = modifier_item(item.modifier_type)
                row = detail.row(align=True)
                row.prop(item, "modifier_type")
                row.operator("es_hub.open_modifier_types", text="",
                             icon='DOWNARROW_HLT').as_new_entry = False
                if found:
                    detail.label(text=found.name, icon=found.icon or 'MODIFIER')
                elif item.modifier_type:
                    detail.label(text="No modifier type named \"%s\""
                                      % item.modifier_type, icon='ERROR')
                else:
                    detail.label(text="Pick a modifier from the list",
                                 icon='INFO')
            elif item.mode == 'MENU':
                row = detail.row(align=True)
                row.prop(item, "menu_id")
                row.menu("ESHUB_MT_menu_presets", text="", icon='DOWNARROW_HLT')
                if item.menu_id and not hasattr(bpy.types, item.menu_id):
                    detail.label(text="No menu named \"%s\" is registered"
                                      % item.menu_id, icon='ERROR')
            else:
                detail.label(
                    text="Opens every modifier for the active object, "
                         "using Blender's own icons", icon='MODIFIER')

            detail.prop(item, "label_color")
            detail.prop(item, "auto_icon")
            row = detail.row()
            row.enabled = not item.auto_icon or bool(item.icon_path)
            row.prop(item, "icon_path")
            if item.auto_icon and not item.icon_path:
                found = auto_icon_path(item)
                if found:
                    shown = os.path.join(os.path.basename(os.path.dirname(found)),
                                         os.path.basename(found))
                    detail.label(text="Found: %s" % shown, icon='CHECKMARK')
                else:
                    detail.label(
                        text="No icon shipped with that add-on - showing initials",
                        icon='INFO')
        else:
            box.label(text="Add an entry to put an add-on in this palette",
                      icon='INFO')

        if _gates:
            layout.label(text="Hidden until picked: %s" % ", ".join(sorted(_gates)),
                         icon='HIDE_ON')


# --------------------------------------------------------------------------- #
#  registration
# --------------------------------------------------------------------------- #

classes = (
    ESHUB_Entry,
    ESHUB_Palette,
    ESHUB_UL_palettes,
    ESHUB_UL_entries,
    ESHUB_MT_categories,
    ESHUB_MT_menu_presets,
    ESHUB_MT_menu_proxy,
    ESHUB_MT_modifier_types,
    ESHUB_OT_open_modifier_types,
    ESHUB_OT_set_modifier,
    ESHUB_OT_set_menu,
    ESHUB_OT_set_category,
    ESHUB_OT_palette_add,
    ESHUB_OT_palette_remove,
    ESHUB_OT_palette_move,
    ESHUB_OT_entry_add,
    ESHUB_OT_entry_remove,
    ESHUB_OT_entry_move,
    ESHUB_OT_reset_placement,
    ESHUB_OT_export_palettes,
    ESHUB_OT_import_palettes,
    ESHUB_OT_refresh_tabs,
    ESHUB_OT_refresh_icons,
    ESHUB_OT_unpin,
    ESHUB_OT_modifier_popup,
    ESHUB_Prefs,
    ES_OT_tools_hud,
    ES_OT_tools_palette,
)

_keymaps = []


def keymap_register():
    kc = bpy.context.window_manager.keyconfigs.addon
    if kc is None:
        return
    # the Window keymap so a palette can be toggled from whichever editor it
    # lives in, rather than only from the 3D Viewport
    km = kc.keymaps.new(name="Window", space_type='EMPTY')
    p = prefs()

    if p is None or not len(p.palettes):
        # nothing configured yet: keep the familiar shortcut alive
        kmi = km.keymap_items.new("es_tools.palette", 'T', 'PRESS',
                                  shift=True, alt=True)
        kmi.properties.index = -1
        _keymaps.append((km, kmi))
        return

    for i, palette in enumerate(p.palettes):
        if palette.key == 'NONE':
            continue
        kmi = km.keymap_items.new("es_tools.palette", palette.key, 'PRESS',
                                  shift=palette.use_shift,
                                  ctrl=palette.use_ctrl,
                                  alt=palette.use_alt)
        kmi.properties.index = i
        _keymaps.append((km, kmi))


def keymap_unregister():
    for km, kmi in _keymaps:
        try:
            km.keymap_items.remove(kmi)
        except Exception:
            pass
    _keymaps.clear()


def migrate():
    """Carry a v1 single-palette setup into the first palette."""
    p = prefs()
    if p is None or p.migrated:
        return
    p.migrated = True
    if len(p.palettes) or not len(p.entries):
        return

    palette = p.palettes.add()
    palette.name = "Palette 1"
    palette.include_providers = p.include_providers
    palette.icon_size = p.icon_size
    palette.vertical = p.vertical
    palette.pos_x = p.pos_x
    palette.pos_y = p.pos_y
    palette.key = 'T'
    palette.use_shift = True
    palette.use_alt = True
    palette.use_ctrl = False

    for old in p.entries:
        new = palette.entries.add()
        new.name = old.name
        new.mode = old.mode
        new.category = old.category
        new.hide_tab = old.hide_tab
        new.operator = old.operator
        new.icon_path = old.icon_path

    p.entries.clear()


def host_unregister():
    """Give up hosting the palettes (called by us, or by a provider taking over)."""
    keymap_unregister()
    st = store()
    st.wanted = False
    st.running = False
    disable_draw()
    if on_load in bpy.app.handlers.load_post:
        try:
            bpy.app.handlers.load_post.remove(on_load)
        except Exception:
            pass
    if st.owner == HUB_OWNER:
        st.owner = None
        st.host_stop = None


def register():
    st = store()

    # a provider add-on may already be hosting a palette - evict it, the hub
    # draws the same icons plus the user's own entries
    stop = getattr(st, "host_stop", None)
    if stop is not None:
        try:
            stop()
        except Exception:
            pass

    for cls in classes:
        bpy.utils.register_class(cls)

    st.hub = True
    st.owner = HUB_OWNER
    st.host_stop = host_unregister

    if on_load not in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.append(on_load)

    def setup():
        # preferences are only readable once registration has settled
        migrate()
        keymap_unregister()
        keymap_register()
        sync_gates()
        refresh_palettes()
        return None

    bpy.app.timers.register(setup, first_interval=0.0)


def unregister():
    st = store()
    host_unregister()
    clear_gates()                       # always give the tabs back
    st.hub = False

    for cls in reversed(classes):
        try:
            bpy.utils.unregister_class(cls)
        except Exception:
            pass

    # hand the palette back to any ES provider that is still enabled
    for entry in st.entries.values():
        rehost = entry.get("rehost")
        if rehost is None:
            continue
        try:
            rehost()
        except Exception:
            continue
        break


if __name__ == "__main__":
    register()
