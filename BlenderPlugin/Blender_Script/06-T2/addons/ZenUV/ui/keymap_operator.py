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

import bpy
import addon_utils
import rna_keymap_ui

from ZenUV.prop.zuv_preferences import get_prefs
from ZenUV.utils.vlog import Log


class ZUV_OT_Keymaps(bpy.types.Operator):
    bl_idname = "ops.zenuv_show_prefs"
    bl_label = "Zen UV Show Prefs"
    bl_options = {'INTERNAL'}
    bl_description = "Set shortcuts for Zen UV menus"

    tabs: bpy.props.EnumProperty(
        items=[
            ("KEYMAP", "Keymap", ""),
            ("PANELS", "Panels", ""),
            ("MODULES", "Modules", ""),
            ("STK_UV_EDITOR", "Sticky UV Editor", ""),
            ("HELP", "Help", ""),
            ("KEYMAP_COLLISIONS", "Keymap Collisions", ""),
        ],
        default="KEYMAP",
        options={'HIDDEN', 'SKIP_SAVE'}
    )

    filter_text: bpy.props.StringProperty(
        name="Filter Text",
        description="Used to filter SpacePreferences.filter_text",
        default=""
    )

    @classmethod
    def description(cls, context: bpy.types.Context, properties: bpy.types.OperatorProperties) -> str:
        if properties:
            if properties.tabs == 'KEYMAP':
                return "Set Shortcuts for Zen UV Menus"
            elif properties.tabs == 'KEYMAP_COLLISIONS':
                return "Show keymap collisions"
            else:
                s_prop_name = bpy.types.UILayout.enum_item_name(properties, 'tabs', properties.tabs)
                return f'Change Zen UV preferences category: {s_prop_name}'
        else:
            return cls.bl_description

    def execute(self, context):
        if self.tabs == 'KEYMAP_COLLISIONS':
            bpy.ops.screen.userpref_show("INVOKE_DEFAULT", section='KEYMAP')

            for window in bpy.context.window_manager.windows:
                for area in window.screen.areas:
                    if area.type == 'PREFERENCES':
                        area.spaces.active.filter_type = 'KEY'
                        area.spaces.active.filter_text = self.filter_text
                        break
        else:
            addon_utils.modules_refresh()

            try:
                mod = addon_utils.addons_fake_modules.get("ZenUV")
                info = addon_utils.module_bl_info(mod)
                info["show_expanded"] = True  # or False to Collapse
            except Exception as e:
                Log.error("SHOW ADDON:", e)

            addon_prefs = get_prefs()
            addon_prefs.tabs = self.tabs

            context.preferences.active_section = "ADDONS"
            bpy.ops.screen.userpref_show("INVOKE_DEFAULT")
            bpy.data.window_managers['WinMan'].addon_search = "Zen UV"

        return {'FINISHED'}


class ZenKmiWrapper(bpy.types.PropertyGroup):
    kmi_id: bpy.props.IntProperty(
        name="Id",
        default=-1,
        min=-1
    )


class ZUV_OT_KeymapsRestoreCategory(bpy.types.Operator):
    bl_idname = "preferences.zenuv_keymaps_restore_category"
    bl_label = "Restore"
    bl_description = "Restore Zen UV keymap category"
    bl_options = {'INTERNAL'}

    mode: bpy.props.EnumProperty(
        name="Mode",
        items=[
            ("ADDON", "Addon", "Restore only addon category"),
            ("BLENDER", "Blender", "Restore all blender category"),
        ],
        default="ADDON"
    )

    category: bpy.props.StringProperty(
        name="Category",
        default=""
    )

    kmi_items: bpy.props.CollectionProperty(
        name="Keymap Items",
        type=ZenKmiWrapper
    )

    @classmethod
    def description(cls, context: bpy.types.Context, properties: bpy.types.OperatorProperties):
        s_desc = cls.description
        if properties:
            if properties.mode == "ADDON":
                s_desc = f'Restore {len(properties.kmi_items)} Zen UV keymap item(s) in "{properties.category}" to default'
            else:
                wm = context.window_manager
                kc = wm.keyconfigs.user
                km: bpy.types.KeyMap = kc.keymaps.get(properties.category)
                if km:
                    s_desc = f'Restore all {len(km.keymap_items)} keymap item(s) in "{properties.category}" to default'
        return s_desc

    def draw(self, context: bpy.types.Context):
        layout = self.layout

        wm = context.window_manager
        kc = wm.keyconfigs.user
        km: bpy.types.KeyMap = kc.keymaps.get(self.category)
        if km:
            layout.label(
                text='WARNING!',
                icon="ERROR")

            row = layout.row(align=True)
            row.separator(factor=4)
            col = row.column(align=True)

            col.label(
                text=f'All {len(km.keymap_items)} keymap item(s) in "{self.category}"')
            col.label(text="will be restored to default!")

    def invoke(self, context: bpy.types.Context, event: bpy.types.Event):
        if self.mode == "BLENDER":
            wm = context.window_manager
            return wm.invoke_props_dialog(self)
        return self.execute(context)

    def execute(self, context: bpy.types.Context):
        if self.category:
            wm = context.window_manager
            kc = wm.keyconfigs.user
            km: bpy.types.KeyMap = kc.keymaps.get(self.category)
            if km:
                if self.mode == "BLENDER":
                    km.restore_to_default()
                else:
                    for item in self.kmi_items:
                        if item.kmi_id != -1:
                            if kmi := km.keymap_items.from_id(item.kmi_id):
                                km.restore_item_to_default(kmi)

                context.preferences.is_dirty = True

        return {'FINISHED'}


class ZUV_OT_KeymapsResolveCollisions(bpy.types.Operator):
    bl_idname = "preferences.zenuv_keymaps_resolve_collisions"
    bl_label = "Resolve"
    bl_description = "Disable all other keymap items with the same key sequence"
    bl_options = {'INTERNAL'}

    category: bpy.props.StringProperty(
        name="Category"
    )

    kmi_keymap: bpy.props.StringProperty(
        name="Keymap"
    )

    kmi_id: bpy.props.IntProperty(
        name="Identifier"
    )

    def draw(self, context: bpy.types.Context):
        layout = self.layout
        wm = context.window_manager
        kc = wm.keyconfigs.user
        km: bpy.types.KeyMap = kc.keymaps.get(self.category)
        if km:
            kmi = km.keymap_items.from_id(self.kmi_id)
            if kmi and kmi.active:
                t_kmi_items = [
                    it_kmi
                    for it_kmi in km.keymap_items
                    if it_kmi != kmi and it_kmi.active and it_kmi.compare(kmi)]

                if len(t_kmi_items):
                    layout.label(text="Keymap conflict(s) will be disabled:", icon="ERROR")

                    box = layout.box()
                    subcol = box.column(align=True)
                    subcol.context_pointer_set("keymap", km)

                    for it_kmi in t_kmi_items:
                        rna_keymap_ui.draw_kmi([], kc, km, it_kmi, subcol, 0)
                else:
                    layout.label(text="No more conflicts!")
            else:
                box.label(text=f"Keymap item {self.kmi_id} is not found in {self.category}!", icon="ERROR")

    def invoke(self, context: bpy.types.Context, event: bpy.types.Event):
        wm = context.window_manager

        return wm.invoke_props_dialog(self, width=500)

    def execute(self, context: bpy.types.Context):
        wm = context.window_manager
        kc = wm.keyconfigs.user
        km: bpy.types.KeyMap = kc.keymaps.get(self.category)
        if km:
            kmi = km.keymap_items.from_id(self.kmi_id)
            if kmi:
                for it_kmi in km.keymap_items:
                    if it_kmi != kmi:
                        if it_kmi.active and it_kmi.compare(kmi):
                            it_kmi.active = False

                context.preferences.is_dirty = True

                for window in context.window_manager.windows:
                    for area in window.screen.areas:
                        area.tag_redraw()

        return {'FINISHED'}
