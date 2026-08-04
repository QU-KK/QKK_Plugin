# ##### BEGIN GPL LICENSE BLOCK #####
#
#  This program is free software; you can redistribute it and/or
#  modify it under the terms of the GNU General Public License
#  as published by the Free Software Foundation; either version 2
#  of the License, or (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program; if not, write to the Free Software Foundation,
#  Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301, USA.
#
# ##### END GPL LICENSE BLOCK #####

# <pep8 compliant>

# Original idea Oleg Stepanov (DotBow)
# Copyright 2023, Alex Zhornyak

import bpy
import rna_keymap_ui

from collections import defaultdict

from ZenUV.ui.keymap import _keymap

addon_keymap = []


class AddonKmiExt:
    LITERAL_KEYMAP_USER_ADDON = "__ZENUV__"

    @classmethod
    def get_kc(cls, wm: bpy.types.WindowManager):
        p_keyconfigs = wm.keyconfigs.get(cls.LITERAL_KEYMAP_USER_ADDON)
        if p_keyconfigs is None:
            p_keyconfigs = wm.keyconfigs.new(cls.LITERAL_KEYMAP_USER_ADDON)
        return p_keyconfigs

    @classmethod
    def get_kmi(cls, context: bpy.types.Context, identifier: str, is_new: bool = False):
        wm = context.window_manager
        p_keyconfigs = cls.get_kc(wm)
        p_keymap = p_keyconfigs.keymaps.get(identifier)
        if p_keymap is None:
            p_keymap = p_keyconfigs.keymaps.new(identifier)

        if is_new:
            while len(p_keymap.keymap_items) > 0:
                p_keymap.keymap_items.remove(p_keymap.keymap_items.values()[0])

            p_kmi = p_keymap.keymap_items.new('', 'NONE', 'NOTHING')
        else:
            if len(p_keymap.keymap_items) == 0:
                p_kmi = p_keymap.keymap_items.new('', 'NONE', 'NOTHING')
            else:
                p_kmi = p_keymap.keymap_items.values()[0]

        return p_kmi

    @classmethod
    def unregister(cls):
        wm = bpy.context.window_manager

        p_keyconfigs = wm.keyconfigs.get(cls.LITERAL_KEYMAP_USER_ADDON)
        if p_keyconfigs is not None:
            wm.keyconfigs.remove(p_keyconfigs)


def get_hotkey_entry_item(km: bpy.types.KeyMap, kmi_name, kmi_value, handled_kmi):
    for km_item in km.keymap_items:
        if km_item in handled_kmi:
            continue
        if km_item.idname == kmi_name:
            if kmi_value is None:
                return km_item
            elif ('name' in km_item.properties) and (km_item.properties.name == kmi_value):
                return km_item

    return None


def register():
    wm = bpy.context.window_manager
    kc = wm.keyconfigs.addon

    # NOTE: could be None in background
    if kc:
        addon_keymap.extend(_keymap())


def unregister():
    AddonKmiExt.unregister()

    for km, kmi in addon_keymap:
        km.keymap_items.remove(kmi)

    addon_keymap.clear()


def get_kmi_collision(kc: bpy.types.KeyConfig, km: bpy.types.KeyMap, kmi: bpy.types.KeyMapItem):
    if kmi.active:
        for it_kmi in km.keymap_items:
            if it_kmi.active and it_kmi != kmi:
                b_has_collision = it_kmi.compare(kmi)
                if b_has_collision:
                    return it_kmi
        # NOTE: Special cases: some areas like UV Editor have several keymaps: 'Image', 'UV Editor' etc.
        if km.name == 'Image':
            p_uv_editor_km = kc.keymaps.get("UV Editor")
            if p_uv_editor_km:
                return get_kmi_collision(kc, p_uv_editor_km, kmi)

    return False


def draw_keymap_button(layout: bpy.types.UILayout):
    from .keymap_operator import ZUV_OT_Keymaps
    from ZenUV.ico import icon_get
    from ZenUV.ui.labels import ZuvLabels

    layout.operator(
            ZUV_OT_Keymaps.bl_idname,
            icon_value=icon_get(ZuvLabels.ADDON_ICO),
            text="Zen UV Keymaps").tabs = "KEYMAP"


def draw_keymap_controls(context: bpy.types.Context, layout: bpy.types.UILayout):
    wm = context.window_manager
    kc = wm.keyconfigs.user

    km_tree = defaultdict(list)
    for _km, _kmi in addon_keymap:
        km_tree[_km.name].append((_kmi.idname, _kmi.properties.name if 'name' in _kmi.properties else None))

    """ Special case for Tool keymap """
    for _km in kc.keymaps:
        if 'Zen UV' in _km.name:
            for _kmi in _km.keymap_items:
                km_tree[_km.name].append(_kmi)

    t_collisions = defaultdict(list)

    handled_kmi = set()
    for km_name, kmi_items in km_tree.items():
        km = kc.keymaps.get(km_name)
        if km:
            for kmi_node in kmi_items:
                kmi = get_hotkey_entry_item(km, kmi_node[0], kmi_node[1], handled_kmi) if isinstance(kmi_node, tuple) else kmi_node

                if kmi:
                    handled_kmi.add(kmi)
                    p_collision_kmi = get_kmi_collision(kc, km, kmi)
                    if p_collision_kmi:
                        t_collisions[km_name].append(
                            (kmi.to_string(), f" - {p_collision_kmi.name}({p_collision_kmi.idname})", kmi))

    if t_collisions:
        box = layout.box()

        draw_keymap_button(box)

        row = box.row(align=True)
        row.separator()
        row.label(text="Keymap Collisions:", icon='ERROR')

        col_box = box.column(align=True)
        for km_name, collision_items in t_collisions.items():
            subbox = col_box.box()
            col = subbox.column(align=True)
            col.label(text=f"{km_name}:")
            for col_item in collision_items:
                s_keymap, s_label, p_kmi = col_item
                row = col.row(align=True)
                r1 = row.row(align=True)
                r1.alignment = 'LEFT'

                op = r1.operator(
                    "preferences.zenuv_keymaps_resolve_collisions",
                    text=s_keymap,
                )
                op.category = km_name
                op.kmi_keymap = p_kmi.to_string()
                op.kmi_id = p_kmi.id

                r2 = row.row(align=True)
                r2.label(text=s_label)
    else:
        draw_keymap_button(layout)


def draw_keymaps(context: bpy.types.Context, layout: bpy.types.UILayout):
    ''' @Draw Prefs Keymaps Manager '''
    wm = context.window_manager
    kc = wm.keyconfigs.user
    box = layout.box()
    split = box.split()
    col = split.column()
    col.label(text='Setup Keymap')

    km_tree = defaultdict(list)
    for _km, _kmi in addon_keymap:
        km_tree[_km.name].append((_kmi.idname, _kmi.properties.name if 'name' in _kmi.properties else None))

    """ Special case for Tool keymap """
    for _km in kc.keymaps:
        if 'Zen UV' in _km.name:
            for _kmi in _km.keymap_items:
                km_tree[_km.name].append(_kmi)

    handled_kmi = set()

    t_keymap_data = dict()

    for km_name, kmi_items in km_tree.items():
        km = kc.keymaps.get(km_name)
        if km:

            p_kmi_list = []

            b_modified = False
            b_has_deleted = False

            for kmi_node in kmi_items:
                kmi = get_hotkey_entry_item(km, kmi_node[0], kmi_node[1], handled_kmi) if isinstance(kmi_node, tuple) else kmi_node
                if kmi:
                    handled_kmi.add(kmi)

                    if kmi.is_user_modified:
                        b_modified = True
                else:
                    b_has_deleted = True

                p_kmi_list.append((kmi, kmi_node))

            if not b_modified:
                b_modified = km.is_user_modified
                if b_modified:
                    # NOTE: in this case something internal is deleted (like tool, so only full category should be restored)
                    b_has_deleted = True

            t_keymap_data[km] = {
                "modified": b_modified,
                "has_deleted": b_has_deleted,
                "items": p_kmi_list
            }

    kmi: bpy.types.KeyMapItem

    for km, kmi_data in t_keymap_data.items():
        km_name = km.name

        col.context_pointer_set("keymap", km)
        col.separator()
        row = col.row(align=True)
        row.label(text=km_name)

        if kmi_data["modified"] or kmi_data["has_deleted"]:
            subrow = row.row()
            subrow.alignment = 'RIGHT'

            s_restore_mode = "BLENDER" if kmi_data["has_deleted"] else "ADDON"
            s_restore_caption = "Restore Keymap" if kmi_data["has_deleted"] else "Restore"
            s_icon = "FILE_REFRESH" if kmi_data["has_deleted"] else "BACK"
            op = subrow.operator(
                "preferences.zenuv_keymaps_restore_category",
                text=s_restore_caption,
                icon=s_icon)
            op.mode = s_restore_mode
            op.category = km_name
            op.kmi_items.clear()

            for kmi, kmi_node in kmi_data["items"]:
                op.kmi_items.add()
                op.kmi_items[-1].kmi_id = kmi.id if kmi else -1
                op.kmi_items[-1].name = kmi.name if kmi else kmi_node[0]

        for kmi, kmi_node in kmi_data["items"]:
            col.separator()
            if kmi:
                p_collision_kmi = get_kmi_collision(kc, km, kmi)
                subcol = col
                if p_collision_kmi:
                    row = subcol.row(align=True)
                    row.separator(factor=2)
                    r1 = row.row(align=True)
                    r1.alignment = 'LEFT'
                    r1.label(text="Collision:", icon="ERROR")

                    r2 = row.row(align=True)
                    r2.alignment = 'RIGHT'
                    op = r2.operator(
                        "preferences.zenuv_keymaps_resolve_collisions",
                        text=f"Resolve:     {p_collision_kmi.name}({p_collision_kmi.idname})",
                        icon="VIEWZOOM"
                    )
                    op.category = km_name
                    op.kmi_keymap = kmi.to_string()
                    op.kmi_id = kmi.id

                    subcol = col.column(align=True)
                    subcol.active = False
                rna_keymap_ui.draw_kmi([], kc, km, kmi, subcol, 0)
            else:
                row = col.row(align=True)
                row.separator(factor=2.0)
                row.label(
                    text=f"Keymap item for '{kmi_node[0]} ' in '{km_name}' not found",
                    icon='ERROR')
