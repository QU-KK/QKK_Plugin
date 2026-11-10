# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Supra3D
"""Native Blender popups used by the panel (value popups, Add Modifier menu, pickers)."""

import bpy
from bpy.props import EnumProperty, StringProperty

from .state import _POPUP
from .utils import (
    _active_object, _data_collection_for, _get_modifier, _owner_attr, _rna_of,
    _supports_modifiers, _tag_all_view3d,
)


# =============================================================================
# Native popups used for typing values / pickers / menus
# =============================================================================

class VIEW3D_PT_modperf_lite_popup(bpy.types.Panel):
    bl_idname = "VIEW3D_PT_modperf_lite_popup"
    bl_label = "Modifier Value"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'WINDOW'
    bl_ui_units_x = 13

    def draw(self, context):
        layout = self.layout
        obj, mod = _get_modifier(context, _POPUP.get("mod"))
        if mod is None:
            layout.label(text="Modifier not found", icon='ERROR')
            return
        kind = _POPUP.get("kind")
        pid = _POPUP.get("prop", "")
        # Put the field straight into edit mode: one click, then just type.
        layout.activate_init = True
        if kind == 'rename':
            layout.prop(mod, "name", text="")
            return
        if kind == 'search':
            getter, coll = _POPUP.get("getter"), _POPUP.get("coll")
            try:
                data = getter(mod, obj) if getter else None
            except Exception:
                data = None
            if data is not None:
                layout.prop_search(mod, pid, data, coll, text="")
            else:
                layout.prop(mod, pid, text="")
            return
        if kind == 'tmpl':
            layout.activate_init = False
            tm = _POPUP.get("tmpl")
            col = layout.column()
            if tm == 'curve_mapping':
                col.template_curve_mapping(mod, pid)
            elif tm == 'curve_profile':
                col.template_curveprofile(mod, pid)
            elif tm == 'texture':
                col.template_ID(mod, pid, new="texture.new")
            elif tm == 'cache_file':
                col.template_cache_file(mod, pid)
            elif tm == 'cache_time' and mod.cache_file is not None:
                col.use_property_split = True
                col.template_cache_file_time_settings(mod, pid)
            elif tm == 'cache_velocity' and mod.cache_file is not None:
                col.use_property_split = True
                col.template_cache_file_velocity(mod, pid)
            elif tm == 'cache_layers' and mod.cache_file is not None:
                col.template_cache_file_layers(mod, pid)
            return
        try:
            owner, attr, p = _rna_of(mod, pid)
        except (AttributeError, KeyError):
            return
        text = _POPUP.get("label") or p.name
        col = layout.column()
        if p.type == 'ENUM' and p.is_enum_flag:
            col.prop(owner, attr, expand=True, text=text)
        else:
            col.prop(owner, attr, text=text)


# ---- Add Modifier menu --------------------------------------------------------
# Copies of Blender's own category menus, with two changes so no row looks
# blank: the icon-less "Array (Legacy)" entry is left out, and the "Smooth by
# Angle" asset is listed with an icon.

try:
    from bl_ui import properties_data_modifier as _bl_mod
except ImportError:          # pragma: no cover - Blender always ships it
    _bl_mod = None

# Essentials assets that Blender lists without an icon, per category menu.
_ASSET_ICONS = {
    "Normals": (("Smooth by Angle", 'NORMALS_VERTEX_FACE'),),
}


def _category_menu(name):
    """A ModPerf copy of one of Blender's Add Modifier category menus.

    It is a plain bpy.types.Menu that *calls* Blender's draw code, never a
    subclass of Blender's menu class: registering a subclass of a registered
    menu makes Blender drop its link to the original class, and Blender's own
    Add Modifier submenus (Properties editor, Ctrl+A, ...) then come up empty
    until Blender restarts.
    """
    base = getattr(_bl_mod, f"OBJECT_MT_modifier_add_{name}", None) if _bl_mod else None
    if base is None:
        return None
    assets = _ASSET_ICONS.get(base.bl_label)

    class _Menu(bpy.types.Menu):
        bl_idname = f"VIEW3D_MT_modperf_lite_add_{name}"
        bl_label = base.bl_label
        bl_options = {'SEARCH_ON_KEY_PRESS'}

        @classmethod
        def operator_modifier_add(cls, layout, mod_type, text=None, no_icon=False):
            if no_icon:
                # Blender's icon-less "Array (Legacy)" entry is left out; the
                # menu keeps Blender's node-based "Array".
                return
            base.operator_modifier_add(layout, mod_type, text=text)

        @classmethod
        def operator_modifier_add_asset(cls, layout, asset, icon='NONE'):
            base.operator_modifier_add_asset(layout, asset, icon=icon)

        def draw(self, context):
            layout = self.layout
            if not assets:
                base.draw(self, context)       # Blender's items, through the methods above
                return
            # Blender's items, then these essentials assets with an icon, then
            # any other assets in the catalog (the user's own).
            _draw_without_template(self, context, base, layout)
            if context.object is not None and context.object.type == 'MESH':
                for asset, icon in assets:
                    self.operator_modifier_add_asset(layout, asset, icon=icon)
            layout.template_modifier_asset_menu_items(catalog_path=self.bl_label,
                                                      skip_essentials=True)

    _Menu.__name__ = _Menu.__qualname__ = _Menu.bl_idname
    return _Menu


def _relink_blender_menus():
    """Repair Blender's category menus if an older ModPerf (1.0.0) unlinked them
    earlier in this session: re-registering Blender's class restores the link."""
    if _bl_mod is None:
        return
    for name in _CATEGORIES:
        cls = getattr(_bl_mod, f"OBJECT_MT_modifier_add_{name}", None)
        if cls is None or getattr(bpy.types, cls.__name__, None) is cls:
            continue
        try:
            bpy.utils.unregister_class(cls)
            bpy.utils.register_class(cls)
        except Exception:
            pass


class _NoTemplateLayout:
    """Proxy for a UILayout that drops template_modifier_asset_menu_items."""
    def __init__(self, layout):
        self._layout = layout

    def template_modifier_asset_menu_items(self, **_kw):
        return None

    def __getattr__(self, attr):
        return getattr(self._layout, attr)


def _draw_without_template(menu, context, base, layout):
    class _Self:
        pass
    me = _Self()
    me.layout = _NoTemplateLayout(layout)
    me.bl_label = menu.bl_label
    me.operator_modifier_add = menu.operator_modifier_add
    me.operator_modifier_add_asset = menu.operator_modifier_add_asset
    base.draw(me, context)


_CATEGORIES = ("edit", "generate", "deform", "normals", "physics", "color")
ADD_CATEGORY_MENUS = tuple(m for m in (_category_menu(n) for n in _CATEGORIES) if m is not None)
_CAT_IDS = {m.bl_idname.rsplit("_", 1)[1]: m.bl_idname for m in ADD_CATEGORY_MENUS}


class VIEW3D_MT_modperf_lite_add(bpy.types.Menu):
    """Blender's Add Modifier menu with search built into the same prompt.

    OBJECT_MT_modifier_add adds a "Search..." item that opens a *second*
    search popup when its layout runs in an EXEC context (which is what
    scripted wm.call_menu gives). Drawing from an INVOKE layout avoids that,
    and SEARCH_ON_KEY_PRESS turns this very menu into a search box as soon as
    you type, so searching happens inside the one prompt. The categories are
    the same as Blender's, drawn through the menus above so every item has an
    icon.
    """
    bl_idname = "VIEW3D_MT_modperf_lite_add"
    bl_label = "Add Modifier"
    bl_options = {'SEARCH_ON_KEY_PRESS'}

    def draw(self, context):
        layout = self.layout
        layout.operator_context = 'INVOKE_REGION_WIN'
        layout.label(text="Type to search…", icon='VIEWZOOM')
        layout.separator()
        ob = context.object
        if ob is None or len(_CAT_IDS) != len(_CATEGORIES):
            layout.menu_contents("OBJECT_MT_modifier_add")
            return
        t = ob.type
        if t in {'MESH', 'CURVE', 'CURVES', 'FONT', 'SURFACE', 'LATTICE', 'GREASEPENCIL', 'POINTCLOUD'}:
            layout.menu(_CAT_IDS["edit"])
        if t in {'MESH', 'CURVE', 'FONT', 'SURFACE', 'VOLUME', 'GREASEPENCIL'}:
            layout.menu(_CAT_IDS["generate"])
        if t in {'MESH', 'CURVE', 'FONT', 'SURFACE', 'LATTICE', 'VOLUME', 'GREASEPENCIL'}:
            layout.menu(_CAT_IDS["deform"])
        if t in {'MESH'}:
            layout.menu(_CAT_IDS["normals"])
        if t in {'MESH', 'CURVE', 'FONT', 'SURFACE', 'LATTICE'}:
            layout.menu(_CAT_IDS["physics"])
        if t in {'GREASEPENCIL'}:
            layout.menu(_CAT_IDS["color"])
        if t in {'EMPTY', 'MESH', 'CURVE', 'CURVES', 'FONT', 'VOLUME', 'POINTCLOUD', 'GREASEPENCIL'}:
            layout.menu_contents("OBJECT_MT_modifier_add_root_catalogs")
            layout.separator()
            _bl_mod.ModifierAddMenu.operator_modifier_add(layout, 'NODES')


# ---- one-step search picker for object / collection / vertex group fields ----

# Enum items must stay referenced from Python while Blender uses them.
_PICK_ITEMS = []

_ICON_FOR_COLLECTION = {
    "objects": 'OBJECT_DATA', "collections": 'OUTLINER_COLLECTION',
    "materials": 'MATERIAL', "images": 'IMAGE_DATA', "textures": 'TEXTURE',
    "node_groups": 'NODETREE',
}


def _pick_source(obj, mod, prop):
    """Return (kind, collection) describing where a picker gets its choices."""
    try:
        _owner, attr, p = _rna_of(mod, prop)
    except (AttributeError, KeyError):
        return None, None
    if p.type == 'POINTER':
        coll = _data_collection_for(p.fixed_type)
        return ('ID', coll) if coll else (None, None)
    if (p.type == 'STRING' and "vertex_group" in attr and not attr.startswith("invert")
            and obj.type in {'MESH', 'LATTICE'}):
        return 'VGROUP', None
    if p.type == 'STRING' and "uv" in attr and obj.type == 'MESH':
        return 'UV', None
    return None, None


def _pickable(obj, mod, prop):
    return _pick_source(obj, mod, prop)[0] is not None


def _pick_candidates(obj, mod, prop):
    kind, coll = _pick_source(obj, mod, prop)
    items = [("__NONE__", "None", "Clear", 'X', 0)]
    if kind == 'ID' and coll:
        icon = _ICON_FOR_COLLECTION.get(coll, 'DOT')
        names = [i.name for i in getattr(bpy.data, coll)
                 if not (coll == "objects" and i == obj)]
    elif kind == 'VGROUP':
        icon, names = 'GROUP_VERTEX', [vg.name for vg in obj.vertex_groups]
    elif kind == 'UV':
        icon, names = 'GROUP_UVS', [uv.name for uv in obj.data.uv_layers]
    else:
        icon, names = 'DOT', []
    items += [(n, n, "", icon, i + 1) for i, n in enumerate(sorted(names))]
    return items


def _pick_items(self, context):
    return _PICK_ITEMS


class OBJECT_OT_modperf_lite_pick(bpy.types.Operator):
    """Pick a value for a modifier field from a search list"""
    bl_idname = "object.modperf_lite_pick"
    bl_label = "Choose"
    bl_options = {'REGISTER', 'UNDO', 'INTERNAL'}
    bl_property = "choice"

    modifier: StringProperty(options={'HIDDEN'})
    prop: StringProperty(options={'HIDDEN'})
    choice: EnumProperty(name="Choice", items=_pick_items)

    @classmethod
    def poll(cls, context):
        return _supports_modifiers(_active_object(context))

    def invoke(self, context, event):
        obj, mod = _get_modifier(context, self.modifier)
        if mod is None:
            return {'CANCELLED'}
        _PICK_ITEMS[:] = _pick_candidates(obj, mod, self.prop)
        context.window_manager.invoke_search_popup(self)
        return {'RUNNING_MODAL'}

    def execute(self, context):
        obj, mod = _get_modifier(context, self.modifier)
        if mod is None:
            return {'CANCELLED'}
        kind, coll = _pick_source(obj, mod, self.prop)
        name = "" if self.choice == "__NONE__" else self.choice
        try:
            owner, attr = _owner_attr(mod, self.prop)
            if kind == 'ID':
                value = getattr(bpy.data, coll).get(name) if name else None
                setattr(owner, attr, value)
            else:
                setattr(owner, attr, name)
        except (TypeError, ValueError, AttributeError) as ex:
            self.report({'ERROR'}, str(ex))
            return {'CANCELLED'}
        _tag_all_view3d(context)
        return {'FINISHED'}
