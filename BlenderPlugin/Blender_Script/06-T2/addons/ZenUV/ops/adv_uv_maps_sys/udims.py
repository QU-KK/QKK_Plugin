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

# Copyright 2023, Valeriy Yatsenko

import bpy

from .udim_utils import UdimFactory

from ZenUV.utils.generic import ZUV_PANEL_CATEGORY, ZUV_REGION_TYPE
from ZenUV.utils.generic import resort_by_type_mesh_in_edit_mode_and_sel
from ZenUV.ops.trimsheets.trimsheet import ZuvTrimsheetUtils
from ZenUV.utils.blender_zen_utils import ZenPolls
from ZenUV.utils.register_util import RegisterUtils
from ZenUV.utils.vlog import Log
from ZenUV.prop.zuv_preferences import get_prefs


class ZUV_OT_AddMissedUdimTile(bpy.types.Operator):
    bl_idname = 'uv.zenuv_add_missed_udim'
    bl_label = 'Add Missed UDIM'
    bl_description = 'Creates the missing UDIM Tile at the island location. The image source must already be "UDIM Tiles"'
    bl_options = {'REGISTER', 'UNDO'}

    by_selection: bpy.props.BoolProperty(
        name='By Selection',
        description='Use selection to determine where UDIM tile will be created',
        default=True)

    in_order: bpy.props.BoolProperty(
        name='In Order',
        description='Creates all the missing tiles in order until it reaches the last missed tile with the selection',
        default=False)

    fill: bpy.props.BoolProperty(
        name='Fill',
        description='Fill tile',
        default=False)

    color: bpy.props.FloatVectorProperty(
        name="Color",
        description="New tile color",
        subtype='COLOR',
        default=[0.0, 0.0, 0.0, 1.0],
        size=4,
        min=0,
        max=1)

    tile_width: bpy.props.IntProperty(
        name='Width',
        description='Tile width',
        default=1024,
        subtype='PIXEL')

    tile_height: bpy.props.IntProperty(
        name='Height',
        description='tile height',
        default=1024,
        subtype='PIXEL')

    alpha: bpy.props.BoolProperty(
        name='Alpha',
        description='Create an image with an alpha channel',
        default=True)

    generated_type: bpy.props.EnumProperty(
        name='Generated type',
        description='Fill the image with a grid for UV map testing',
        items=[
            ('BLANK', 'Blank', 'Generated grid to test UV mapping'),
            ('UV_GRID', 'UV Grid', 'Generate a blank image'),
            ('COLOR_GRID', 'Color grid', 'Generated improved grid to test UV mapping')
        ],
        default='BLANK')

    float_depth: bpy.props.BoolProperty(
        name='32-bit Float',
        description='Create image with 32-bit floating-point bit depth',
        default=True)

    @classmethod
    def poll(cls, context):
        sima = context.space_data
        return context.mode == 'EDIT_MESH' and context.area.type == "IMAGE_EDITOR" and sima is not None and sima.image and sima.image.source == 'TILED'

    def invoke(self, context: bpy.types.Context, event: bpy.types.Event):
        wm = context.window_manager
        return wm.invoke_props_dialog(self)

    def draw(self, context: bpy.types.Context):
        layout = self.layout
        layout.prop(self, 'by_selection')
        layout.prop(self, 'in_order')
        layout.prop(self, 'fill')
        box = layout.box()
        box.enabled = self.fill
        box.prop(self, 'color')

        row = box.row(align=True)
        row.prop(self, 'tile_width')
        row.prop(self, 'tile_height')

        box.prop(self, 'alpha')
        box.prop(self, 'generated_type')
        box.prop(self, 'float_depth')

    def execute(self, context):
        objs = resort_by_type_mesh_in_edit_mode_and_sel(context)
        if not objs:
            self.report({'WARNING'}, "Zen UV: There are no selected objects.")
            return {'CANCELLED'}
        UdimFactory.reset_report()

        image_udims = UdimFactory.get_active_image_udim_tiles(context)  # type: bpy.types.UDIMTiles

        p_first_tile = image_udims.get(1001)
        if p_first_tile is not None:
            b_is_fill_possible = p_first_tile.size[:] != (0, 0)

        if UdimFactory.result is False:
            self.report({'WARNING'}, UdimFactory.message)
            return {'CANCELLED'}

        if self.by_selection:
            p_udims = UdimFactory.get_udims_from_selected_loops(context, objs)
            if not len(p_udims):
                self.report({'WARNING'}, "Zen UV: There is no selection in UDIM area")
                return {'CANCELLED'}
            if UdimFactory.result is False:
                self.report({'WARNING'}, UdimFactory.message)
                return {'CANCELLED'}
            geo_udims = set(p_udims)

        else:
            geo_udims = set(UdimFactory.get_udims_from_loops(objs, groupped=False))
            if not geo_udims:
                self.report({'WARNING'}, "Zen UV: There are no islands")
                return {'FINISHED'}

            if UdimFactory.result is False:
                self.report({'WARNING'}, UdimFactory.message)
                return {'CANCELLED'}

        if self.in_order:
            geo_udims = set(range(1001, sorted(list(geo_udims))[-1] + 1))

        p_udims = list(geo_udims.difference({t.number for t in image_udims}))

        if not len(p_udims):
            self.report({'WARNING'}, "Zen UV: There is no missed UDIM tiles")
            return {'CANCELLED'}

        if self.fill:

            if b_is_fill_possible is False:
                self.report({'WARNING'}, "Zen UV: It is not possible to create filled tiles. It looks like tile 1001 is not filled")
                return {'FINISHED'}

            missed_udims = UdimFactory.split_udims_by_groups(p_udims)
            for group in missed_udims:
                if bpy.ops.image.tile_add.poll():
                    bpy.ops.image.tile_add(
                        number=group[0],
                        count=len(group),
                        label='',
                        fill=self.fill,
                        color=self.color,
                        generated_type=self.generated_type,
                        width=self.tile_width,
                        height=self.tile_height,
                        float=self.float_depth,
                        alpha=self.alpha)
                else:
                    self.report({'WARNING'}, "Zen UV: It is impossible to create filled UDIM tiles")
                    return {'FINISHED'}
        else:
            res = [UdimFactory.create_tile_by_number(context, n) for n in p_udims]
            if None in res or False in res:
                self.report({'WARNING'}, "Zen UV: Tiles were not created")
                return {'CANCELLED'}

        ZuvTrimsheetUtils.fix_undo()

        return {'FINISHED'}


class ZUV_OT_SetActiveUdimTileMouseover(bpy.types.Operator):
    bl_idname = 'uv.zenuv_set_active_udim_mouseover'
    bl_label = 'Set Active UDIM Tile'
    bl_description = 'Sets the active UDIM tile over which the mouse cursor is positioned. '
    bl_options = {'REGISTER', 'UNDO'}

    def __del__(self):
        self.cancel(bpy.context)

    x: bpy.props.IntProperty(
        name='X',
        description='X position',
        default=0
    )
    y: bpy.props.IntProperty(
        name='Y',
        description='Y position',
        default=0
    )

    @classmethod
    def poll(cls, context):
        sima = context.space_data
        return context.mode == 'EDIT_MESH' and context.area.type == "IMAGE_EDITOR" and sima is not None and sima.image and sima.image.source == 'TILED'

    def invoke(self, context: bpy.types.Context, event: bpy.types.Event):
        # NOTE: is already running
        if self.bl_idname in bpy.app.driver_namespace:
            return {'CANCELLED'}

        bpy.app.driver_namespace[self.bl_idname] = ZenPolls.SESSION_UUID
        context.window_manager.modal_handler_add(self)
        context.workspace.status_text_set(f"{self.bl_label} - Enter/LMB: Confirm, Esc/RMB: Cancel")
        return {'RUNNING_MODAL'}

    def modal(self, context, event):
        if event.type in {'RIGHTMOUSE', 'ESC'} or bpy.app.driver_namespace.get(self.bl_idname, Ellipsis) != ZenPolls.SESSION_UUID:
            self.cancel(context)
            return {'CANCELLED'}

        elif event.type in {'LEFTMOUSE', 'RET'}:
            return self.execute(context)

        context.window.cursor_modal_set('EYEDROPPER')

        return {'PASS_THROUGH'}

    def execute(self, context):
        self.cancel(context)

        from ZenUV.ops.event_service import get_blender_event

        UdimFactory.reset_report()
        UdimFactory.report_style = 'SHORT'

        p_event = get_blender_event(force=True)
        self.x, self.y = p_event.get('mouse_region_x', 0), p_event.get('mouse_region_y', 0)
        l_uv_co = context.region.view2d.region_to_view(self.x, self.y)
        l_uvs = UdimFactory.filtering_uvs((l_uv_co, ))
        l_numbers = UdimFactory.convert_uv_coords_to_udim_number(l_uvs)
        if not len(l_numbers):
            return {'CANCELLED'}

        UdimFactory.set_active_udim_by_number(context, l_numbers[0], False)

        if UdimFactory.result is False:
            self.report({'WARNING'}, UdimFactory.message)
            return {'CANCELLED'}

        for window in context.window_manager.windows:
            for area in window.screen.areas:
                if area.type == 'IMAGE_EDITOR':
                    area.tag_redraw()

        ZuvTrimsheetUtils.fix_undo()

        return {'FINISHED'}

    def cancel(self, context: bpy.types.Context):
        # NOTE: check is operator is running
        if self.bl_idname in bpy.app.driver_namespace:
            del bpy.app.driver_namespace[self.bl_idname]

            if context.window:
                context.window.cursor_modal_restore()
            if context.workspace:
                context.workspace.status_text_set(None)


class ZUV_OT_SetActiveUdimTile(bpy.types.Operator):
    bl_idname = 'uv.zenuv_set_active_udim'
    bl_label = 'Set Active UDIM'
    bl_description = 'Sets the active UDIM tile based on the selection'
    bl_options = {'REGISTER', 'UNDO'}

    create_if_absent: bpy.props.BoolProperty(
        name='Create if Absent',
        description='Create a new tile if the selection does not belong to any tile',
        default=True)

    @classmethod
    def poll(cls, context):
        sima = context.space_data
        return context.mode == 'EDIT_MESH' and context.area.type == "IMAGE_EDITOR" and sima is not None and sima.image and sima.image.source == 'TILED'

    def execute(self, context):
        UdimFactory.reset_report()

        objs = resort_by_type_mesh_in_edit_mode_and_sel(context)
        if not objs:
            self.report({'WARNING'}, "There are no selected objects")
            return {'CANCELLED'}

        p_image_udims = UdimFactory.get_active_image_udim_tiles_numbers(context)
        if not len(p_image_udims):
            self.report({'WARNING'}, "Zen UV: Active Image has no UDIM tiles")
            self.redraw_viewports(context)
            return {'CANCELLED'}

        if UdimFactory.result is False:
            self.report({'WARNING'}, UdimFactory.message)
            self.redraw_viewports(context)
            return {'CANCELLED'}

        udims = UdimFactory.get_udims_from_selected_loops(context, objs)

        if not len(udims):
            self.report({'WARNING'}, "Zen UV: There is no selection in UDIM area")
            self.redraw_viewports(context)
            return {'CANCELLED'}

        if len(udims) > 1:
            p_current_active = UdimFactory.get_active_udim_tile(context)
            if p_current_active is None:
                p_a_udim = udims[0]
            else:
                if p_current_active.number not in udims:
                    p_a_udim = udims[0]
                else:
                    p_index = udims.index(p_current_active.number)
                    next_index = (p_index + 1) % len(udims)
                    p_a_udim = udims[next_index]
        else:
            p_a_udim = udims[0]

        UdimFactory.reset_report()

        UdimFactory.set_active_udim_by_number(context, p_a_udim, self.create_if_absent)

        if UdimFactory.result is False:
            self.report({'WARNING'}, UdimFactory.message)
            self.redraw_viewports(context)
            return {'CANCELLED'}

        self.redraw_viewports(context)

        ZuvTrimsheetUtils.fix_undo()

        return {'FINISHED'}

    def redraw_viewports(self, context):
        for window in context.window_manager.windows:
            for area in window.screen.areas:
                if area.type == 'IMAGE_EDITOR':
                    area.tag_redraw()


class ZUV_OT_RemoveActiveUdimTile(bpy.types.Operator):
    bl_idname = 'uv.zenuv_remove_active_udim_tile'
    bl_label = 'Remove Active UDIM Tile'
    bl_description = 'Remove the active UDIM tile'
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        sima = context.space_data
        return context.mode == 'EDIT_MESH' and context.area.type == "IMAGE_EDITOR" and sima is not None and sima.image and sima.image.source == 'TILED'

    def invoke(self, context: bpy.types.Context, event: bpy.types.Event):
        wm = context.window_manager
        return wm.invoke_confirm(self, event)

    def execute(self, context):
        UdimFactory.reset_report()

        objs = resort_by_type_mesh_in_edit_mode_and_sel(context)
        if not objs:
            self.report({'WARNING'}, "There are no selected objects")
            return {'CANCELLED'}

        UdimFactory.remove_active_tile(context)

        UdimFactory.set_active_udim_by_number(context, 1001)

        if UdimFactory.result is False:
            self.report({'WARNING'}, UdimFactory.message)
            return {'CANCELLED'}

        for window in context.window_manager.windows:
            for area in window.screen.areas:
                if area.type == 'IMAGE_EDITOR':
                    area.tag_redraw()

        ZuvTrimsheetUtils.fix_undo()

        return {'FINISHED'}


def draw_udims(context: bpy.types.Context, layout):

    draw_blender_udims(context, layout)
    draw_zen_udims(context, layout)


def draw_zen_udims(context: bpy.types.Context, layout):
    from ZenUV.ops.select_sys.select_islands import ZUV_OT_SelectInTile
    from ZenUV.ops.transform_sys.tr_move import ZUV_OT_MoveToUvArea
    from ZenUV.ops.transform_sys.tr_move import ZUV_OT_MoveToUvAreaMouseover
    col = layout.column()
    col.enabled = context.space_data.image.source == 'TILED'

    col.operator(ZUV_OT_AddMissedUdimTile.bl_idname, text='Add Missed')
    row = col.row(align=True)
    row.operator(ZUV_OT_SetActiveUdimTile.bl_idname, text='Set Active')
    row.operator(ZUV_OT_RemoveActiveUdimTile.bl_idname, text='Remove Active')
    row = col.row(align=True)
    op = row.operator(ZUV_OT_SelectInTile.bl_idname, text='Select In Active')
    op.clear_selection = True
    op.base = 'ACTIVE_UDIM'
    op.location = 'INSIDE'

    op = row.operator(ZUV_OT_MoveToUvArea.bl_idname, text='Move To Active')
    op.move_mode = 'ACTIVE_UDIM'

    col.operator(ZUV_OT_SetActiveUdimTileMouseover.bl_idname, text='Set Active', icon='EYEDROPPER')
    col.operator(ZUV_OT_MoveToUvAreaMouseover.bl_idname, icon='EYEDROPPER')


def draw_blender_udims(context: bpy.types.Context, layout):
    p_image = context.space_data.image
    if p_image:
        box = layout.box()
        box.prop(p_image, 'source')

    layout.operator("image.tile_fill")


class SYSTEM_PT_Udims_UV(bpy.types.Panel):
    bl_idname = "SYSTEM_PT_Udims_UV"
    bl_space_type = "IMAGE_EDITOR"
    bl_label = "UDIM Tools"
    bl_parent_id = "DATA_PT_UVL_uv_texture_advanced"
    bl_region_type = ZUV_REGION_TYPE
    bl_category = ZUV_PANEL_CATEGORY
    bl_options = {'DEFAULT_CLOSED'}

    @classmethod
    def poll(cls, context: bpy.types.Context):
        return context.mode == 'EDIT_MESH' and context.space_data.image is not None

    @classmethod
    def poll_reason(cls, context: bpy.types.Context):
        if context.mode != 'EDIT_MESH':
            return 'Available in Edit Mesh Mode'
        if context.space_data.image is None:
            return 'No active image'

    def draw(self, context: bpy.types.Context):
        draw_udims(context, self.layout)


class SYSTEM_PT_Udims_BLENDER(bpy.types.Panel):
    bl_space_type = "IMAGE_EDITOR"
    bl_label = "UDIM Tools"
    bl_parent_id = "IMAGE_PT_udim_tiles"
    bl_region_type = "UI"
    bl_category = "Image"
    bl_options = {'DEFAULT_CLOSED'}

    @classmethod
    def poll(cls, context: bpy.types.Context):
        return context.mode == 'EDIT_MESH'

    @classmethod
    def poll_reason(cls, context: bpy.types.Context):
        if context.mode != 'EDIT_MESH':
            return 'Available in Edit Mesh Mode'

    def draw(self, context: bpy.types.Context):
        draw_zen_udims(context, self.layout)


class IMAGE_MT_uvs_context_menu(bpy.types.Menu):
    bl_label = ""

    def draw(self, context):
        pass


def zuv_uv_draw_uvs_context_menu(self, context: bpy.types.Context):
    addon_prefs = get_prefs()
    if not addon_prefs.right_menu_assist:
        return

    from ZenUV.ops.transform_sys.tr_move import ZUV_OT_Move2dCursorTo
    layout: bpy.types.UILayout = self.layout

    layout.separator()
    layout.operator(ZUV_OT_SetActiveUdimTileMouseover.bl_idname)
    ot = layout.operator(ZUV_OT_Move2dCursorTo.bl_idname)
    ot.influence = 'SELECTION'
    ot.island_pivot = 'cen'


reg_classes = (
    ZUV_OT_AddMissedUdimTile,
    ZUV_OT_SetActiveUdimTile,
    ZUV_OT_RemoveActiveUdimTile,
    ZUV_OT_SetActiveUdimTileMouseover,
    SYSTEM_PT_Udims_BLENDER
)

udims_parented_panels = (
    SYSTEM_PT_Udims_UV,
)


def register():
    RegisterUtils.register(reg_classes)

    try:
        bpy.types.IMAGE_MT_uvs_context_menu.append(zuv_uv_draw_uvs_context_menu)
    except Exception as e:
        Log.error("REGISTER_IMAGE_MT_UVS", e)


def unregister():
    try:
        bpy.types.IMAGE_MT_uvs_context_menu.remove(zuv_uv_draw_uvs_context_menu)
    except Exception as e:
        Log.error("UNREGISTER_IMAGE_MT_UVS", e)

    RegisterUtils.unregister(reg_classes)


if __name__ == "__main__":
    pass
