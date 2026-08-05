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

# Copyright 2023, Alex Zhornyak

import bpy

from dataclasses import dataclass, field

from ZenUV.utils.vlog import Log
from ZenUV.utils.blender_zen_utils import update_areas_in_view3d
from ZenUV.utils.register_util import RegisterUtils

# Tool Operators
from .tool_ops import (
    ZUV_OT_ToolTrimHandle,
    ZUV_OT_ToolAreaUpdate,
    ZUV_OT_ToolExitCreate,
    ZUV_OT_ToolScreenZoom,
    ZUV_OT_ToolScreenPan,
    ZUV_OT_ToolScreenReset,
    ZUV_OT_ToolScreenSelector,
    ZUV_OT_TrimScrollFit,
    ZUV_OT_TrimScrollFitInternal,
    ZUV_OT_TrimActivateTool,
    ZUV_OT_ToolSnapHandle,
    ZUV_OP_ToolTransform,
    ZUV_OP_ToolSnapTransformGizmo,
    ZUV_OT_ToolTransformHandle,
    ZUV_OT_ToolTransformHandleClick,
    ZUV_OP_ToolTransformMouseDraw,
    ZUV_OP_ToolTransformFitToSelection,
    ZUV_OP_ToolTransformSwapHandles,
    ZUV_OP_ToolTransformSetEnum,
    ZUV_OP_ToolTransformSetupModal,
    ZUV_OP_ToolTransformSetPerpendicular
)

# Custom Gizmos
from .view3d_texture_gizmo import ZuvTextureGizmo
from .view3d_trim import (
    ZuvTrimCageGizmo,
    ZuvTrimSelectGizmo,
    ZuvTrimAlignGizmo,
    ZuvTrimFitFlipGizmo,
    VIEW2D_GT_zenuv_trim_viewport_select)
from .view3d_transform_line import VIEW2D_GT_zenuv_transform_line
from .view3d_text import VIEW2D_GT_zenuv_tool_text

# NOTE: UV TRIM TOOL
from .uv.uv_trim import (
    UV_GT_zenuv_trim_select,
    UV_GT_zenuv_trim_box_select,
    UV_GT_zenuv_trim_select_background)
from .uv.uv_create import UV_GT_zenuv_trim_create
from .uv.uv_align import UV_GT_zenuv_trim_align
from .uv.uv_fit_flip import UV_GT_zenuv_trim_fitflip
from .uv.uv_arrow import UV_GT_zenuv_arrow
from .uv.uv_transform_line import UV_GT_zenuv_transform_line

# NOTE: UV TRANSFORM TOOL
from .uv.uv_transform_handle import UV_GT_zenuv_transform_handle
from .uv.uv_transform_gizmo import (
    UV_GT_zenuv_transform_pivot,
    UV_GT_zenuv_transform_a_handle,
    UV_GT_zenuv_draggable_line,
    UV_GT_zenuv_bbox_tool,
    UV_GT_zenuv_rotate_handle,
    UV_GT_zenuv_scale_handle,
    UV_GT_zenuv_transform_tool_tooltip)

# Gizmo Groups
from .view3d_move import ZUV_GGT_3DVTransformMove
from .view3d_scale import ZUV_GGT_3DVTransformScale, ZUV_GGT_2DVTransformScale, ZuvTrimScaleGizmo
from .view3d_rotate import ZUV_GGT_3DVTransformRot
from .view3d_text import ZUV_GGT_2DVToolText

from .uv.uv_move import ZUV_GGT_UVTransformMove
from .uv.uv_scale import ZUV_GGT_UVTransformScale
from .uv.uv_rotate import ZUV_GGT_UVTransformRot
from .uv.uv_create import ZUV_GGT_UVTrimCreate
from .uv.uv_generic import ZUV_GGT_UVTrimGeneric, ZUV_GGT_UVTrimDisplay

# Gizmo Transform
from .uv.uv_transform_gizmo import ZUV_GGT_UVTransformGizmo, ZUV_GGT_UVTransformButton

# Tools
from .view3d_tool import Zuv3DVWorkSpaceTool
from .uv.uv_tool import ZuvUVWorkSpaceTool
from .uv.uv_transform_tool import (
    ZuvUVTransformWorkSpaceTool,
    ZUV_PT_ToolTransformDrawSettings,
    ZUV_PT_ToolTransformDisplayState,
    ZUV_PT_ToolTransformEditingMode,
    ZUV_PT_ToolTransformFitToSelection)

classes = (
    # Operators
    ZUV_OT_ToolTrimHandle,
    ZUV_OT_ToolAreaUpdate,
    ZUV_OT_ToolExitCreate,
    ZUV_OT_ToolScreenZoom,
    ZUV_OT_ToolScreenPan,
    ZUV_OT_ToolScreenReset,
    ZUV_OT_ToolScreenSelector,
    ZUV_OT_TrimScrollFit,
    ZUV_OT_TrimScrollFitInternal,
    ZUV_OT_ToolSnapHandle,
    ZUV_OP_ToolTransform,
    ZUV_OP_ToolSnapTransformGizmo,
    ZUV_OT_ToolTransformHandle,
    ZUV_OT_ToolTransformHandleClick,
    ZUV_OP_ToolTransformSetPerpendicular,
    # Call from UI Operator
    ZUV_OT_TrimActivateTool,
    ZUV_OP_ToolTransformMouseDraw,
    ZUV_OP_ToolTransformFitToSelection,
    ZUV_OP_ToolTransformSwapHandles,
    ZUV_OP_ToolTransformSetEnum,
    ZUV_OP_ToolTransformSetupModal,

    # PANELS
    ZUV_PT_ToolTransformDrawSettings,
    ZUV_PT_ToolTransformDisplayState,
    ZUV_PT_ToolTransformEditingMode,
    ZUV_PT_ToolTransformFitToSelection,

    # 3D
    ZuvTextureGizmo,
    ZuvTrimAlignGizmo,
    ZuvTrimSelectGizmo,
    ZuvTrimFitFlipGizmo,
    ZuvTrimCageGizmo,
    ZuvTrimScaleGizmo,

    # 3D GizmoGroups
    ZUV_GGT_3DVTransformMove,
    ZUV_GGT_3DVTransformScale,
    ZUV_GGT_3DVTransformRot,

    # 2D View3D Gizmos
    VIEW2D_GT_zenuv_transform_line,
    ZUV_GGT_2DVTransformScale,

    VIEW2D_GT_zenuv_tool_text,
    ZUV_GGT_2DVToolText,

    VIEW2D_GT_zenuv_trim_viewport_select,

    # UV
    UV_GT_zenuv_trim_select,
    UV_GT_zenuv_trim_create,
    UV_GT_zenuv_trim_align,
    UV_GT_zenuv_transform_handle,
    UV_GT_zenuv_rotate_handle,
    UV_GT_zenuv_scale_handle,
    UV_GT_zenuv_transform_tool_tooltip,
    UV_GT_zenuv_trim_fitflip,
    UV_GT_zenuv_transform_line,
    UV_GT_zenuv_arrow,
    UV_GT_zenuv_trim_box_select,
    UV_GT_zenuv_trim_select_background,
    UV_GT_zenuv_transform_a_handle,
    UV_GT_zenuv_transform_pivot,
    UV_GT_zenuv_draggable_line,
    UV_GT_zenuv_bbox_tool,

    # UV GizmoGroups
    ZUV_GGT_UVTransformMove,
    ZUV_GGT_UVTrimCreate,
    ZUV_GGT_UVTrimGeneric,
    ZUV_GGT_UVTransformScale,
    ZUV_GGT_UVTransformRot,
    ZUV_GGT_UVTrimDisplay,
    ZUV_GGT_UVTransformGizmo,
    ZUV_GGT_UVTransformButton
)


@dataclass
class NotifyToolCache:
    UV: str = ''
    VIEW_3D: str = ''

    PREV_UV: str = ''
    PREV_VIEW_3D: str = ''


@dataclass
class NotifyToolCacheModes:
    OBJECT: NotifyToolCache = field(default_factory=NotifyToolCache)
    EDIT_MESH: NotifyToolCache = field(default_factory=NotifyToolCache)


_notify_tool_cache = NotifyToolCacheModes()


zenuv_handle_subcribe_to = None


@bpy.app.handlers.persistent
def zenuv_notify_tool_changed(handle):
    try:
        ctx = bpy.context
        s_mode = ctx.mode

        if s_mode in {'EDIT_MESH', 'OBJECT'}:

            from ZenUV.prop.zuv_preferences import get_prefs

            global _notify_tool_cache

            p_mode_cache: NotifyToolCache = getattr(_notify_tool_cache, s_mode)

            _id_UV = getattr(ctx.workspace.tools.from_space_image_mode('UV', create=False), 'idname', None)
            _id_3D = getattr(ctx.workspace.tools.from_space_view3d_mode(s_mode, create=False), 'idname', None)

            b_UV_tool = None
            b_3D_tool = None

            if _id_UV and isinstance(_id_UV, str):
                if p_mode_cache.UV != _id_UV:
                    p_mode_cache.PREV_UV = p_mode_cache.UV
                    p_mode_cache.UV = _id_UV
                    b_UV_tool = p_mode_cache.UV == ZuvUVWorkSpaceTool.bl_idname

            if _id_3D and isinstance(_id_3D, str):
                if p_mode_cache.VIEW_3D != _id_3D:
                    p_mode_cache.PREV_VIEW_3D = p_mode_cache.VIEW_3D
                    p_mode_cache.VIEW_3D = _id_3D
                    b_3D_tool = p_mode_cache.VIEW_3D == Zuv3DVWorkSpaceTool.bl_idname

            addon_prefs = get_prefs()
            if addon_prefs.trimsheet.auto_highlight == 'DEFAULT':
                p_scene = ctx.scene

                if b_UV_tool is not None and p_scene.zen_uv.ui.uv_tool.display_trims != b_UV_tool:
                    p_scene.zen_uv.ui.uv_tool.display_trims = b_UV_tool
                if b_3D_tool is not None and p_scene.zen_uv.ui.view3d_tool.display_trims != b_3D_tool:
                    p_scene.zen_uv.ui.view3d_tool.display_trims = b_3D_tool
    except Exception as e:
        Log.error('TOOL CHANGED:', e)


@bpy.app.handlers.persistent
def zenuv_notify_object_mode_changed(handle):
    from ZenUV.prop.zuv_preferences import get_prefs
    addon_prefs = get_prefs()
    if addon_prefs.draw_auto_disable:
        p_scene = bpy.context.scene
        if p_scene:
            if p_scene.zen_uv.ui.draw_mode_UV != 'NONE':
                p_scene.zen_uv.ui.draw_mode_UV = 'NONE'
            if p_scene.zen_uv.ui.draw_mode_3D != 'NONE':
                p_scene.zen_uv.ui.draw_mode_3D = 'NONE'


@bpy.app.handlers.persistent
def zenuv_notify_tool_settings_uv_sync_changed(handle):
    # NOTE: Blender does not inform about UV Sync Select is changed,
    # but there may be possible draw operations in View3D that requires update
    update_areas_in_view3d(bpy.context)


def _process_tool_scene_undo_redo(p_scene: bpy.types.Scene):
    from .uv.uv_transform_tool import ZuvUVTransformWorkSpaceTool

    # NOTE: we restrict to react for undo-redo only in our tool mode
    if ZuvUVTransformWorkSpaceTool.is_workspace_tool_active(bpy.context):
        from ZenUV.prop.scene_ui_props import ZUV_UVToolProps
        p_tool_props: ZUV_UVToolProps = p_scene.zen_uv.ui.uv_tool
        p_tool_props.tr_gizmo_redo_last()


@bpy.app.handlers.persistent
def zenuv_tool_undo_scene(p_scene: bpy.types.Scene):
    _process_tool_scene_undo_redo(p_scene)


@bpy.app.handlers.persistent
def zenuv_tool_redo_scene(p_scene: bpy.types.Scene):
    _process_tool_scene_undo_redo(p_scene)


@bpy.app.handlers.persistent
def zenuv_tool_load_scene_handler(_):

    p_scene = bpy.context.scene
    if p_scene:
        from ZenUV.prop.scene_ui_props import ZUV_SceneUIProps, ZUV_UVToolProps

        p_ui_props: ZUV_SceneUIProps = p_scene.zen_uv.ui
        if p_ui_props.draw_mode_UV != 'NONE':
            p_ui_props.draw_mode_UV = 'NONE'
        if p_ui_props.draw_mode_3D != 'NONE':
            p_ui_props.draw_mode_3D = 'NONE'

        p_uv_tool_props: ZUV_UVToolProps = p_ui_props.uv_tool
        if p_uv_tool_props.tr_gizmo_mode != 'SETUP':
            p_uv_tool_props.tr_gizmo_mode = 'SETUP'

    global _notify_tool_cache
    _notify_tool_cache = NotifyToolCacheModes()

    _subscribe_rna_common_types()


def _subscribe_rna_common_types():
    bpy.msgbus.subscribe_rna(
        key=(bpy.types.WorkSpace, 'tools'),
        owner=zenuv_handle_subcribe_to,
        args=(zenuv_handle_subcribe_to,),
        notify=zenuv_notify_tool_changed,
        options={"PERSISTENT", }
    )

    bpy.msgbus.subscribe_rna(
        key=(bpy.types.Object, 'mode'),
        owner=zenuv_handle_subcribe_to,
        args=(zenuv_handle_subcribe_to,),
        notify=zenuv_notify_object_mode_changed,
        options={"PERSISTENT", }
    )

    bpy.msgbus.subscribe_rna(
        key=(bpy.types.ToolSettings, 'use_uv_select_sync'),
        owner=zenuv_handle_subcribe_to,
        args=(zenuv_handle_subcribe_to,),
        notify=zenuv_notify_tool_settings_uv_sync_changed,
        options={"PERSISTENT", }
    )


def zenuv_image_pt_snapping_draw(self, context: bpy.types.Context):
    from ZenUV.prop.scene_ui_props import ZUV_UVToolProps

    if ZuvUVTransformWorkSpaceTool.is_workspace_tool_active(context):
        p_scene = context.scene
        tool_props: ZUV_UVToolProps = p_scene.zen_uv.ui.uv_tool
        layout: bpy.types.UILayout = self.layout

        if tool_props.tr_gizmo_mode == 'TRANSFORM':
            col = layout.column(align=True)
            col.active = p_scene.tool_settings.use_snap_uv
            col.label(text="Snap Transform Target")
            col.prop(tool_props, "tr_gizmo_snap_to_gizmo_flip_point")
            col.prop(tool_props, "tr_gizmo_snap_to_gizmo_origin_points")


def zenuv_image_ht_tool_header_draw(self, context: bpy.types.Context):
    if ZuvUVTransformWorkSpaceTool.is_workspace_tool_active(context):
        wm = context.window_manager

        layout: bpy.types.UILayout = self.layout

        wm.zen_uv.uv_transform_tool.draw_header(layout, context)


def register():
    RegisterUtils.register(classes)

    try:
        bpy.utils.register_tool(Zuv3DVWorkSpaceTool)
        bpy.utils.register_tool(ZuvUVWorkSpaceTool, group=False)
        bpy.utils.register_tool(ZuvUVTransformWorkSpaceTool, after=ZuvUVWorkSpaceTool.bl_idname)
    except Exception as e:
        Log.error('Register tool:', e)

    global zenuv_handle_subcribe_to
    if zenuv_handle_subcribe_to is None:
        zenuv_handle_subcribe_to = object()
        _subscribe_rna_common_types()

    if zenuv_tool_load_scene_handler not in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.append(zenuv_tool_load_scene_handler)

    if zenuv_tool_undo_scene not in bpy.app.handlers.undo_post:
        bpy.app.handlers.undo_post.append(zenuv_tool_undo_scene)

    if zenuv_tool_redo_scene not in bpy.app.handlers.redo_post:
        bpy.app.handlers.redo_post.append(zenuv_tool_redo_scene)

    try:
        bpy.types.IMAGE_PT_snapping.prepend(zenuv_image_pt_snapping_draw)
    except Exception as e:
        Log.error("REGISTER TOOL SNAP:", e)

    try:
        bpy.types.IMAGE_HT_tool_header.append(zenuv_image_ht_tool_header_draw)
    except Exception as e:
        Log.error("REGISTER TOOL HEADER:", e)


def unregister():

    try:
        bpy.types.IMAGE_PT_snapping.remove(zenuv_image_pt_snapping_draw)
    except Exception as e:
        Log.error("UNREGISTER TOOL SNAP:", e)

    try:
        bpy.types.IMAGE_HT_tool_header.remove(zenuv_image_ht_tool_header_draw)
    except Exception as e:
        Log.error("UNREGISTER TOOL HEADER:", e)

    if zenuv_tool_load_scene_handler in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.remove(zenuv_tool_load_scene_handler)

    if zenuv_tool_undo_scene in bpy.app.handlers.undo_post:
        bpy.app.handlers.undo_post.remove(zenuv_tool_undo_scene)

    if zenuv_tool_redo_scene in bpy.app.handlers.redo_post:
        bpy.app.handlers.redo_post.remove(zenuv_tool_redo_scene)

    global zenuv_handle_subcribe_to
    if zenuv_handle_subcribe_to is not None:
        bpy.msgbus.clear_by_owner(zenuv_handle_subcribe_to)
        zenuv_handle_subcribe_to = None

    try:
        bpy.utils.unregister_tool(ZuvUVTransformWorkSpaceTool)
        bpy.utils.unregister_tool(ZuvUVWorkSpaceTool)
        bpy.utils.unregister_tool(Zuv3DVWorkSpaceTool)
    except Exception as e:
        Log.error('Unregister tool:', e)

    RegisterUtils.unregister(classes)
