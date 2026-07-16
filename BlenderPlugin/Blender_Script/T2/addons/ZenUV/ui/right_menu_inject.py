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

# Copyright 2024, Alex Zhornyak

""" Zen UV Right menu inject """
import bpy


from ZenUV.ico import icon_get
from ZenUV.utils.vlog import Log
from ZenUV.prop.zuv_preferences import get_prefs
from ZenUV.prop.favourites_props import ZUV_FavItem
from ZenUV.utils.blender_zen_utils import update_areas_in_all_screens, get_command_props, ZenPolls


def _dump_object(obj, text):
    print('-' * 40, text, '-' * 40)
    s_type = type(obj)
    print('Type ====>', s_type)
    for attr in dir(obj):
        if hasattr(obj, attr):
            print(f".{attr} = {getattr(obj, attr, 'None')}")


def _dump_context(context):
    if hasattr(context, 'button_pointer'):
        btn = context.button_pointer
        _dump_object(btn, 'button_pointer')

    if hasattr(context, 'button_prop'):
        prop = context.button_prop
        _dump_object(prop, 'button_prop')

    if hasattr(context, 'button_operator'):
        op = context.button_operator
        _dump_object(op, 'button_operator')


class ZUV_OT_InternalRmbTest(bpy.types.Operator):
    """Right click entry test"""
    bl_idname = "wm.zenuv_internal_rmb_test"
    bl_label = "Execute custom action"

    @classmethod
    def poll(cls, context):
        return context.active_object is not None

    def execute(self, context):

        _dump_context(context)

        return {'FINISHED'}


class ZUV_OT_RmbAddToFavourites(bpy.types.Operator):
    bl_idname = "wm.zenuv_rmb_add_to_favs"
    bl_label = "Add to ZenUV Favourites"
    bl_description = "Add to user defined ZenUV quick favourites menu bar"
    bl_options = {'REGISTER', 'UNDO'}

    item_name: bpy.props.StringProperty(
        name='Name',
        default='',
        options={'SKIP_SAVE'}
    )

    category: bpy.props.StringProperty(
        name='Category',
        default=''
    )

    mode: bpy.props.StringProperty(
        name='Mode',
        default=''
    )

    python_command: bpy.props.StringProperty(
        name='Python Command',
        default=''
    )

    @classmethod
    def poll(cls, context: bpy.types.Context):
        return context.mode in {'EDIT_MESH', 'OBJECT'}

    def invoke(self, context: bpy.types.Context, event: bpy.types.Event):
        wm = context.window_manager
        return wm.invoke_props_dialog(self, width=500)

    def execute(self, context: bpy.types.Context):
        try:
            if self.python_command in ZUV_FavItem.t_skip_values:
                raise RuntimeError(f"Can not add item - {self.python_command}")

            addon_prefs = get_prefs()

            b_is_uv = (
                True
                if hasattr(context, 'space_data') and context.space_data and context.space_data.type == 'IMAGE_EDITOR'
                else False)

            def add_to_favs(p_fav_props):
                p_fav_props.favourites.add()
                p_item: ZUV_FavItem = p_fav_props.favourites[-1]

                b_is_panel = self.mode == 'PANEL'

                if self.item_name:
                    p_item.name = self.item_name
                else:
                    if self.mode == 'OPERATOR':
                        op_props = get_command_props(self.python_command, context)
                        p_item.name = op_props.bl_label
                    elif b_is_panel:
                        p_item.name = self.python_command
                p_item.command = self.python_command

                p_item.mode = self.mode
                p_item.category = self.category

                p_item.icon, p_item.is_icon_value = p_item.get_auto_icon(p_item.mode, p_item.command, context)

                p_fav_props.favourite_index = len(p_fav_props.favourites) - 1

            s_panel_mode = 'UV' if b_is_uv else 'VIEW_3D'
            p_fav_props = getattr(addon_prefs, f'favourite_props_{s_panel_mode}')
            add_to_favs(p_fav_props)

            update_areas_in_all_screens(context)
            return {'FINISHED'}

        except Exception as e:
            self.report({'ERROR'}, str(e))
        return {'CANCELLED'}


# This class has to be exactly named like that to insert an entry in the right click menu
class WM_MT_button_context(bpy.types.Menu):
    bl_label = "Zen UV Injector Menu"

    def draw(self, context):
        pass


def zen_uv_menu_func(self, context: bpy.types.Context):
    addon_prefs = get_prefs()
    if not addon_prefs.right_menu_assist:
        return

    layout: bpy.types.UILayout = self.layout

    # DEBUG
    # _dump_context(context)

    def to_clipboard(bl_rna):
        layout.separator()

        if hasattr(bl_rna, "name"):
            op = layout.operator("wm.zenuv_copy_to_clipboard", text="Copy Name To Clipboard")
            op.text = bl_rna.name

        if hasattr(bl_rna, "identifier"):
            op = layout.operator("wm.zenuv_copy_to_clipboard", text="Copy Identifier To Clipboard")
            try:
                prefix, suffix = bl_rna.identifier.split("_OT_", 1)
                op.text = f"{prefix.lower()}.{suffix.lower()}"
            except Exception as e:
                op.text = bl_rna.identifier

        if hasattr(bl_rna, "description"):
            op = layout.operator("wm.zenuv_copy_to_clipboard", text="Copy Description To Clipboard")
            op.text = bl_rna.description

        if hasattr(bl_rna, "name") and hasattr(bl_rna, "description"):
            op = layout.operator("wm.zenuv_copy_to_clipboard", text="Copy Name and Description for Doc")
            op.text = f'- **{bl_rna.name}** - {bl_rna.description}'

    if hasattr(context, 'button_prop'):
        if hasattr(context, 'button_pointer') and context.button_pointer:

            op_idname = context.button_pointer.bl_rna.identifier
            if op_idname in ZenPolls.map_operator_defaults:
                if context.button_prop.identifier in ZenPolls.map_operator_defaults[op_idname]:
                    layout.separator()

                    op = layout.operator("wm.zenuv_presets_save_operator_default")
                    op.mode = "PROPERTY"
                    op.op_id = op_idname
                    op.op_property = context.button_prop.identifier

                    layout.separator()


    if hasattr(context, 'button_operator'):
        p_instance = context.button_operator

        bl_rna = getattr(p_instance, 'bl_rna', None)
        if bl_rna is not None:

            id = getattr(bl_rna, "identifier", None)
            if id is not None and context.mode in {'EDIT_MESH', 'OBJECT'}:

                s_name = getattr(bl_rna, "name", '')
                if not s_name:
                    s_name = id

                s_low_id = id.lower()
                if s_low_id in {'wm_ot_zuv_expand_combo_panel', 'wm_ot_zuv_pin_combo_panel'}:
                    id = p_instance.panel_name
                elif s_low_id == 'wm_ot_zuv_set_combo_panel':
                    id = p_instance.data_value

                if "_PT_" in id:
                    p_panel_class = getattr(bpy.types, id)
                    if p_panel_class.bl_label:
                        s_name = p_panel_class.bl_label

                    layout.separator()
                    op = layout.operator(
                        ZUV_OT_RmbAddToFavourites.bl_idname,
                        icon_value=icon_get("zen-uv_32")
                    )
                    op.item_name = s_name
                    op.mode = 'PANEL'
                    op.python_command = id
                elif "_OT_" in id:
                    op_module, op_name = id.split("_OT_", 1)

                    props = p_instance.bl_rna.properties
                    keys = set(props.keys()) - {'rna_type'}
                    kwargs = [
                        k + '=' + repr(getattr(p_instance, k))
                        for k in dir(p_instance)
                        if k in keys and not props[k].is_readonly and not props[k].is_skip_save]
                    kwargs = ','.join(kwargs)

                    op_module = op_module.lower()
                    op_name = op_name.lower()

                    layout.separator()
                    op = layout.operator(
                        ZUV_OT_RmbAddToFavourites.bl_idname,
                        icon_value=icon_get("zen-uv_32")
                    )

                    if op_module == 'wm' and op_name.startswith('context_set_'):
                        try:
                            p_class = getattr(bpy.types, id)
                            s_description = p_class.description(context, p_instance)
                            s_description = s_description.replace('\n', ' ')
                            s_description = s_description.replace('Assign:', '')
                            s_description = s_description.replace('Value:', ':')
                            op.item_name = s_description.strip()
                        except Exception:
                            op.item_name = s_name
                    else:
                        op.item_name = s_name
                    op.mode = 'OPERATOR'
                    op.python_command = f'{op_module}.{op_name}({kwargs})'


def zen_uv_draw_uvs_snap(self, context: bpy.types.Context):
    layout: bpy.types.UILayout = self.layout

    addon_prefs = get_prefs()
    if not addon_prefs.right_menu_assist:
        return

    from ZenUV.ui.tool.uv.uv_transform_tool import ZuvUVTransformWorkSpaceTool
    if ZuvUVTransformWorkSpaceTool.is_workspace_tool_active(context):
        layout.separator()
        op = layout.operator("uv.zenuv_tool_snap_transform_gizmo", text='Gizmo Pivot To Selected')
        op.gizmo_type = 'PIVOT_HANDLE'

        op = layout.operator("uv.zenuv_tool_snap_transform_gizmo", text='Gizmo Handle To Selected')
        op.gizmo_type = 'ANGLE_HANDLE'


classes = (
    # DEBUG
    # ZUV_OT_InternalRmbTest,
    ZUV_OT_RmbAddToFavourites,
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)

    if not hasattr(bpy.types, 'WM_MT_button_context'):
        bpy.utils.register_class(WM_MT_button_context)

    try:
        bpy.types.WM_MT_button_context.append(zen_uv_menu_func)
        bpy.types.IMAGE_MT_uvs_snap.append(zen_uv_draw_uvs_snap)
    except Exception as e:
        Log.error('REGISTER -> RIGHT MENU:', str(e))


def unregister():
    try:
        bpy.types.IMAGE_MT_uvs_snap.remove(zen_uv_draw_uvs_snap)
        bpy.types.WM_MT_button_context.remove(zen_uv_menu_func)
    except Exception as e:
        Log.error('UNREGISTER -> RIGHT MENU:', str(e))

    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
