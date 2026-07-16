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
from ZenUV.ico import icon_get
from ZenUV.ops.transform_sys.tr_labels import TrLabels

from . tr_move import (
    ZUV_OT_TrMove,
    ZUV_OT_MoveToUvArea,
    ZUV_OT_MoveGrabIncrement,
    ZUV_OT_Move2dCursorTo,
    ZUV_OT_MoveToUvAreaMouseover,
    ZUV_OT_MoveToUvPositionMouseover
)
from . tr_fit import ZUV_OT_TrFit
from . tr_scale import ZUV_OT_TrScale, ZUV_OT_TrFlip

from .trim_depend_transform import (
    ZUV_OT_TrFitToTrim,
    ZUV_OT_TrFlipInTrim,
    ZUV_OT_TrAlignToTrim,
)

from . tr_rotate import (
    ZUV_OT_TrRotate,
    ZUV_OT_TrOrient
)
from . tr_align import ZUV_OT_TrAlign
from . transform_utils.tr_utils import BlPivotPoint

from ZenUV.ops.stitch import ZUV_OT_MatchAndStitch
from ZenUV.ops.mirror_uv import ZUV_OT_MirrorUV

from ZenUV.utils.generic import ZUV_PANEL_CATEGORY, ZUV_REGION_TYPE, ZUV_SPACE_TYPE


"""
    Transform sys operators properties order.

    influence_mode:
    order:
    operation mode - fit to, move to

    Settings operator

    Align to or island pivot
"""


class ZUV_PT_3DV_SubTransform(bpy.types.Panel):
    """  Zen Advanced Transform Subpanel """
    bl_label = "Advanced Transform"
    bl_space_type = ZUV_SPACE_TYPE
    bl_region_type = ZUV_REGION_TYPE
    bl_category = ZUV_PANEL_CATEGORY
    bl_options = {'DEFAULT_CLOSED'}
    bl_parent_id = "ZUV_PT_3DV_Transform"

    def draw(self, context):
        draw_extended_transform_panel(context, self.layout)


class ZUV_PT_UVL_SubTransform(bpy.types.Panel):
    """  Zen Advanced UV Transform Subpanel """
    bl_label = ZUV_PT_3DV_SubTransform.bl_label
    bl_space_type = 'IMAGE_EDITOR'
    bl_region_type = ZUV_REGION_TYPE
    bl_category = ZUV_PANEL_CATEGORY
    bl_options = {'DEFAULT_CLOSED'}
    bl_parent_id = "ZUV_PT_UVL_Transform"

    draw = ZUV_PT_3DV_SubTransform.draw


def draw_trim_transform_panel(self, is_uv: bool):
    ''' @Draw Trim Transform Panel '''
    layout = self.layout

    op_type = 'uv' if is_uv else 'view3d'

    col = layout.column(align=True)
    row = col.row(align=True)
    row.operator(f'{op_type}.zenuv_move_in_trim', icon_value=icon_get("transform-move"))
    row.operator(ZUV_OT_TrFitToTrim.bl_idname, icon_value=icon_get("transform-fit"))
    row = col.row(align=True)
    row.operator(f'{op_type}.zenuv_rotate_in_trim', icon_value=icon_get("transform-rotate"))
    row.operator(ZUV_OT_TrAlignToTrim.bl_idname, icon_value=icon_get("transform-orient"))
    row = col.row(align=True)
    row.operator(ZUV_OT_TrFlipInTrim.bl_idname, icon_value=icon_get("transform-flip"))
    row.operator(f'{op_type}.zenuv_scale_in_trim', icon_value=icon_get("transform-scale"))


def draw_transform_panel(self, context):
    ''' @Draw Transform Panel '''
    layout = self.layout
    prop = context.scene.zen_uv

    draw_trans_independent_operators(self, context, layout)

    box = layout.box()
    all_row = box.row(align=True)
    row = all_row.row(align=True)
    row.prop(prop, "tr_type", expand=False, text='')
    row.prop(prop, "tr_pivot_mode", expand=False, text='')

    if context.area.type == 'VIEW_3D':
        row = box.row(align=True)
        row.label(text='Transform space:')
        row.prop(prop, "tr_space_mode", expand=True, icon_only=True)

    if prop.tr_type in {'ISLAND', 'SELECTION'}:

        draw_tr_modes(prop, box)

        # col = box.column(align=True)
        row = box.row()

        UC_col = row.column(align=True)
        UnifiedControl.draw(context.scene.zen_uv, UC_col)

        # row = row.row(align=False)
        subcontrols_col = row.column()
        bottom_horizontal_row = box.row()

        if prop.tr_mode == "2DCURSOR":
            draw_2dcursor_subcontrols(context, prop, subcontrols_col)
        elif prop.tr_mode == "MOVE":
            draw_move_subcontrols(context, prop, subcontrols_col)
        elif prop.tr_mode == "SCALE":
            draw_scale_subcontrols(context, prop, subcontrols_col, bottom_horizontal_row)
        elif prop.tr_mode == "FIT":
            draw_fit_subcontrols(prop, subcontrols_col, bottom_horizontal_row)
            draw_fit_region_section(context, layout)
        elif prop.tr_mode == "FLIP":
            draw_flip_subcontrols(prop, subcontrols_col)
        elif prop.tr_mode == "ROTATE":
            draw_rotate_subcontrols(prop, subcontrols_col, bottom_horizontal_row)
        elif prop.tr_mode == "ALIGN":
            draw_align_subcontrols(context, prop, subcontrols_col, bottom_horizontal_row)
        elif prop.tr_mode == "DISTRIBUTE":
            draw_distribute_subcontrols(prop, subcontrols_col)
        else:
            print(f'Current tr_mode --> {prop.tr_mode} not matched to Transform Panel')
            pass


def draw_tr_modes(prop, box):
    row = box.row(align=False)
    row.alignment = "CENTER"
    row.scale_x = 1.2
    row.scale_y = 1.2

    row.prop(prop, "tr_mode", text="Mode", expand=True, icon_only=True)


def draw_distribute_subcontrols(prop, s_col):
    ''' @Draw Distribute Subcontrols '''
    if prop.tr_type == "ISLAND":
        s_col.operator("uv.zenuv_distribute_islands", text="Distribute & Sort")
        s_col.operator("uv.zenuv_arrange_transform")
    else:
        s_col.operator("uv.zenuv_distribute_verts")


def draw_align_subcontrols(context, prop, s_col, s_row):
    ''' @Draw Align Subcontrols '''
    props = context.scene.zen_uv
    row = s_col.row()
    row.enabled = not prop.tr_type == 'ISLAND'
    row.prop(props, 'tr_align_vertices')
    row = s_col.row(align=True)
    row.label(text='Center by Axis')

    if props.tr_type == 'SELECTION' and props.tr_align_vertices is True:
        p_influence = 'VERTICES'
    else:
        p_influence = props.tr_type
    ot = row.operator(
        ZUV_OT_TrAlign.bl_idname,
        icon_value=icon_get("tr_rotate_lc"), text='')
    ot.influence_mode = p_influence
    ot.align_direction = 'cen_h'

    ot = row.operator(
        ZUV_OT_TrAlign.bl_idname,
        icon_value=icon_get("tr_rotate_tc"), text='')
    ot.influence_mode = p_influence
    ot.align_direction = 'cen_v'

    bottom_col = s_row.column()
    bottom_col.prop(prop, "tr_align_to")

    if prop.tr_align_to == "TO_UV_AREA":
        pass

    elif prop.tr_align_to == "TO_POSITION":
        row = bottom_col.row()
        row.operator("uv.zenuv_align_grab_position")
        row.prop(prop, "tr_align_position")

    elif prop.tr_align_to == "TILE_NUMBER":
        row = bottom_col.row()
        row.prop(props, 'tr_tile_number')


def draw_rotate_subcontrols(prop, s_col, s_row):
    ''' @Draw Rotate Subcontrols '''
    from ZenUV.ops.select_sys.select_islands import ZUV_OP_SelectIslandByDirection
    s_col.prop(prop, "tr_rot_inc")
    row = s_col.row(align=True)
    row.operator(ZUV_OP_SelectIslandByDirection.bl_idname)
    if prop.tr_type == 'ISLAND':

        orient_row = s_row.row(align=True)
        orient_row.label(text="Orient by selected:")
        p_order = 'OVERALL' if prop.tr_pivot_mode == 'OVERALL' else 'ONE_BY_ONE'

        orient_auto = orient_row.operator(
                ZUV_OT_TrOrient.bl_idname,
                text="",
                icon_value=icon_get(UnifiedControl.STATE["ROTATE"]["cen"]["icon"])
            )
        orient_auto.mode = 'BY_SELECTION'
        orient_auto.orient_direction = 'AUTO'
        orient_auto.rotate_direction = 'CW'
        orient_auto.order = p_order

        orient_v = orient_row.operator(
                ZUV_OT_TrOrient.bl_idname,
                text="",
                icon_value=icon_get(UnifiedControl.STATE["ROTATE"]["tc"]["icon"])
            )
        orient_v.mode = 'BY_SELECTION'
        orient_v.orient_direction = 'VERTICAL'
        orient_v.rotate_direction = 'CW'
        orient_v.order = p_order

        orient_h = orient_row.operator(
                ZUV_OT_TrOrient.bl_idname,
                text="",
                icon_value=icon_get(UnifiedControl.STATE["ROTATE"]["lc"]["icon"])
            )
        orient_h.mode = 'BY_SELECTION'
        orient_h.orient_direction = 'HORIZONTAL'
        orient_h.rotate_direction = 'CW'
        orient_h.order = p_order


def draw_flip_subcontrols(prop, s_col):
    ''' @Draw Flip Subcontrols '''
    UnifiedControl.STATE[prop.tr_mode]["cen"]["enable"] = False
    UnifiedControl.STATE[prop.tr_mode]["cen"]["icon"] = "tr_control_off"

    s_col.prop(prop, 'tr_flip_always_center')


def draw_fit_subcontrols(prop, s_col, s_row):
    ''' @Draw Fit Subcontrols '''
    row = s_col.row()
    row.enabled = not prop.tr_type == 'ISLAND'
    row.prop(prop, 'tr_fit_per_face')

    s_col.prop(prop, "tr_fit_padding")
    s_col.prop(prop, "tr_fit_bound")

    fill = s_row.operator("uv.zenuv_unified_transform", text=TrLabels.TR_FILL_NO_PROPORTION_LABEL)
    fill.desc = TrLabels.TR_FILL_NO_PROPORTION_DESC
    fill.fit_keep_proportion = False
    fill.pp_pos = "cen"


def draw_scale_subcontrols(context, props, s_col, s_row):
    ''' @Draw Scale Subcontrols '''
    s_col.prop(props, "tr_scale_mode")
    if props.tr_scale_mode == "AXIS":
        draw_scale_tuner(props, s_row)

    if props.tr_scale_mode == "UNITS":
        draw_scale_by_units(context, props, s_row)


def draw_scale_by_units(context, props, s_row):
    ''' @Draw Scale by Units '''
    col = s_row.column(align=False)
    col.prop(props, "unts_uv_area_size")
    row = col.row(align=True)

    if not context.area.ui_type == 'UV':
        row = row.split(factor=0.9, align=True)
        row.prop(props, "unts_desired_size")
        row.operator("uv.zenuv_scale_grab_size", text="G")
    else:
        row.prop(props, "unts_desired_size")

    row = col.row(align=True)
    row.prop(props, "unts_calculate_by", expand=True)


def draw_scale_tuner(props, s_row):
    ''' @Draw Scale Tuner '''
    row = s_row.split(factor=0.5, align=True)
    vector_col = row.column(align=True)
    vector_col.prop(props, "tr_scale")

    row = row.split(factor=0.8, align=True)
    tuner_col = row.column(align=True)

    locker_col = row.column(align=True)
    if props.tr_scale_keep_proportion:
        lock_icon = "LOCKED"
        draw_overall_v_tuner(tuner_col)
    else:
        lock_icon = "UNLOCKED"
        draw_splitted_v_tuner(tuner_col)
    locker_col.label(text="")
    s_col = locker_col.column(align=True)
    s_col.scale_y = 2
    s_col.prop(props, "tr_scale_keep_proportion", icon=lock_icon, icon_only=True)


def draw_2dcursor_subcontrols(context, prop, s_col):
    ''' @Draw 2D Cursor Subcontrols '''
    if 'IMAGE_EDITOR' in [area.type for area in context.screen.areas]:

        s_col.prop(prop, 'tr_set_cursor_to')

        row = s_col.row()
        row.enabled = prop.tr_set_cursor_to == 'TILE_NUMBER'
        row.prop(prop, 'tr_tile_number')

        row = s_col.row()
        row.enabled = prop.tr_set_cursor_to == 'TO_POSITION'
        row.prop(prop, 'tr_align_position')
    else:
        warn = """Cursor data is missing. To manipulate the 2D cursor, open the UV editor"""
        s_col.label(text=warn)


def draw_move_subcontrols(context, props, s_col):
    ''' @Draw Move Subcontrols '''
    if props.tr_pivot_mode == 'SYSTEM_PIVOT':
        if BlPivotPoint.get(context) == 'CURSOR':
            s_col.label(text="To 2D Cursor")
            UnifiedControl.STATE[props.tr_mode]["cen"]["enable"] = True
            UnifiedControl.STATE[props.tr_mode]["cen"]["icon"] = "tr_control_cen"
    else:
        s_col.prop(props, "tr_move_inc")
        if context.area.type == 'IMAGE_EDITOR':
            s_col.operator(ZUV_OT_MoveGrabIncrement.bl_idname)
        UnifiedControl.STATE[props.tr_mode]["cen"]["enable"] = False
        UnifiedControl.STATE[props.tr_mode]["cen"]["icon"] = "tr_control_off"


def draw_overall_v_tuner(col2):
    ''' @Draw Overall V Tuner '''
    col2.label(text="Tuner:")

    tuner_col = col2.column(align=True)
    tuner_col.scale_y = 2

    r2 = tuner_col.row(align=True)
    doub = r2.operator("uv.zenuv_tr_scale_tuner", text='D')
    doub.mode = "DOUBLE"
    doub.axis = 'XY'
    doub.desc = "Increases by two times"
    half = r2.operator("uv.zenuv_tr_scale_tuner", text='H')
    half.mode = "HALF"
    half.axis = 'XY'
    half.desc = "Decrease two times"
    res = r2.operator("uv.zenuv_tr_scale_tuner", text='R')
    res.mode = "RESET"
    res.desc = "Reset value to 1.0"
    res.axis = 'XY'


def draw_splitted_v_tuner(col2):
    ''' @Draw Splitted V Tuner '''
    col2.label(text="Tuner:")

    tuner_col = col2.column(align=True)

    r2 = tuner_col.row(align=True)
    doub = r2.operator("uv.zenuv_tr_scale_tuner", text='D')
    doub.mode = "DOUBLE"
    doub.axis = 'X'
    doub.desc = "Increases by two times"
    half = r2.operator("uv.zenuv_tr_scale_tuner", text='H')
    half.mode = "HALF"
    half.axis = 'X'
    half.desc = "Decrease two times"
    res = r2.operator("uv.zenuv_tr_scale_tuner", text='R')
    res.mode = "RESET"
    res.desc = "Reset value to 1.0"
    res.axis = 'X'

    r2 = tuner_col.row(align=True)
    doub = r2.operator("uv.zenuv_tr_scale_tuner", text='D')
    doub.mode = "DOUBLE"
    doub.axis = 'Y'
    doub.desc = "Increases by two times"
    half = r2.operator("uv.zenuv_tr_scale_tuner", text='H')
    half.mode = "HALF"
    half.axis = 'Y'
    half.desc = "Decrease two times"
    res = r2.operator("uv.zenuv_tr_scale_tuner", text='R')
    res.mode = "RESET"
    res.desc = "Reset value to 1.0"
    res.axis = 'Y'


def draw_trans_independent_operators(self, context, layout):
    ''' @Draw Trans Independent Operators '''
    from ZenUV.ops.stitch import ZUV_OT_MergeUvVerts, ZUV_OT_Split
    from ZenUV.ops.select_sys.select import (
        ZUV_OT_Select_UV_Borders, ZUV_OT_SelectLinkedLoops,
        ZUV_OT_SelectHalf)
    from ZenUV.ops.select_sys.select_islands import ZUV_OT_Select_QuadedIslands
    from ZenUV.ops.quadrify import ZUV_OT_Quadrify

    col = layout.column(align=True)
    row = col.row(align=True)
    row.operator("uv.zenuv_relax", icon_value=icon_get(TrLabels.ZEN_RELAX_ICO))
    row.popover(panel="RELAX_PT_Properties", text="", icon="PREFERENCES")
    col.operator("uv.zenuv_world_orient")
    col.operator("uv.zenuv_randomize_transform")

    # Quadrify section
    row = col.row(align=True)
    row.operator(ZUV_OT_Quadrify.bl_idname, icon_value=icon_get(TrLabels.ZEN_QUADRIFY_ICO))
    row.operator(ZUV_OT_Select_QuadedIslands.bl_idname, icon="RESTRICT_SELECT_OFF", text='')
    row.popover(panel="QUADRIFY_PT_Properties", text="", icon="PREFERENCES")

    if context.area.type == 'IMAGE_EDITOR':
        col.operator("uv.zenuv_reshape_island")

    row = col.row(align=True)
    row.operator(ZUV_OT_MatchAndStitch.bl_idname)
    if context.area.type == 'IMAGE_EDITOR':
        row.operator(ZUV_OT_SelectLinkedLoops.bl_idname, icon="RESTRICT_SELECT_OFF", text='')

    row = col.row(align=True)
    row.operator(ZUV_OT_Split.bl_idname, text='Split')
    row.operator(ZUV_OT_MergeUvVerts.bl_idname, text='Merge')
    row.operator(ZUV_OT_Select_UV_Borders.bl_idname, icon="RESTRICT_SELECT_OFF", text='')

    row = col.row(align=True)
    row.operator(ZUV_OT_MirrorUV.bl_idname, text='Mirror UV')
    row.operator(ZUV_OT_SelectHalf.bl_idname, icon="RESTRICT_SELECT_OFF", text='')


class UcOperator:

    def __init__(self, position_name) -> None:
        self.op = 'uv.zenuv_unified_transform'
        self.pp_pos = position_name
        self.rotate_direction = self.get_rotate_direction()
        self.orient_island = True if position_name in {'lc', 'rc', 'tc', 'bc', 'cen'} else False
        self.orient_direction = self.get_orient_direction()

    def get_rotate_direction(self):
        if self.pp_pos in {'tr', 'br', 'cen', 'tc', 'rc'}:
            return 'CW'
        elif self.pp_pos in {'tl', 'lc', 'bl', 'bc'}:
            return 'CCW'

    def get_orient_direction(self):
        if self.pp_pos in {'lc', 'rc'}:
            return 'HORIZONTAL'
        elif self.pp_pos in {'tc', 'bc'}:
            return 'VERTICAL'
        else:
            return 'AUTO'


class UcUnit:

    def __init__(self, prop, operator: UcOperator) -> None:
        self.prop = prop
        self.tr_m = UnifiedControl.STATE.get(prop.tr_mode, None)
        self.operator = operator
        self.position_name = self.operator.pp_pos
        self.fit_keep_proportion = True
        self.desc, self.icon_value, self.enabled = self.construct_desc_icon_enable(self.operator.pp_pos)

    @property
    def enabled(self):
        return self._enabled

    @enabled.setter
    def enabled(self, value):
        if self.tr_m is not None:
            self.tr_m[self.operator.pp_pos]['enable'] = value
        self._enabled = value

    @property
    def position_name(self):
        return self._position_name

    @position_name.setter
    def position_name(self, value):
        self._position_name = value
        self.desc, self.icon_value, _ = self.construct_desc_icon_enable(value)

    def draw(self, layout):
        btn = layout.row(align=True)
        btn.enabled = self.enabled
        op = btn.operator(
            self.operator.op,
            icon_value=self.icon_value,
            text=''
        )
        op.desc = self.desc
        op.pp_pos = self.operator.pp_pos
        op.rotate_direction = self.operator.rotate_direction
        op.orient_island = self.operator.orient_island
        op.orient_direction = self.operator.orient_direction
        op.fit_keep_proportion = self.fit_keep_proportion

    def construct_desc_icon_enable(self, position_name):
        desc = self.tr_m[position_name]['desc'] if self.tr_m is not None else ''
        ico = icon_get(self.tr_m[position_name]['icon']) if self.tr_m is not None else icon_get('tr_control_off')
        enbl = self.tr_m[position_name]['enable'] if self.tr_m is not None else False

        return desc, ico, enbl


class UnifiedControl:

    STATE = {
        "MOVE": {
            "tl": {"desc": "Move Islands Up Left", "enable": True, "icon": "tr_control_tl"},
            "tc": {"desc": "Move Islands Up", "enable": True, "icon": "tr_control_tc"},
            "tr": {"desc": "Move Islands Up Right", "enable": True, "icon": "tr_control_tr"},
            "lc": {"desc": "Move Islands Left", "enable": True, "icon": "tr_control_lc"},
            "cen": {"desc": "Disabled", "enable": False, "icon": "tr_control_cen"},
            "rc": {"desc": "Move Islands Right", "enable": True, "icon": "tr_control_rc"},
            "bl": {"desc": "Move Islands Down Left", "enable": True, "icon": "tr_control_bl"},
            "bc": {"desc": "Move Islands Down", "enable": True, "icon": "tr_control_bc"},
            "br": {"desc": "Move Islands Down Right", "enable": True, "icon": "tr_control_br"}
        },
        "SCALE": {
            "tl": {"desc": "Scale Islands from Up Left", "enable": True, "icon": "tr_control_tl"},
            "tc": {"desc": "Scale Islands from Up", "enable": True, "icon": "tr_control_tc"},
            "tr": {"desc": "Scale Islands from Up Right", "enable": True, "icon": "tr_control_tr"},
            "lc": {"desc": "Scale Islands from Left", "enable": True, "icon": "tr_control_lc"},
            "cen": {"desc": "Scale from Center", "enable": True, "icon": "tr_control_cen"},
            "rc": {"desc": "Scale Islands from Right", "enable": True, "icon": "tr_control_rc"},
            "bl": {"desc": "Scale Islands from Down Left", "enable": True, "icon": "tr_control_bl"},
            "bc": {"desc": "Scale Islands from Down", "enable": True, "icon": "tr_control_bc"},
            "br": {"desc": "Scale Islands from Down Right", "enable": True, "icon": "tr_control_br"}
        },
        "ROTATE": {
            "tl": {"desc": "Rotate Islands counterclockwise", "enable": True, "icon": "tr_rotate_tl"},
            "tc": {"desc": "Orient Islands vertically", "enable": True, "icon": "tr_rotate_tc"},
            "tr": {"desc": "Rotate Islands clockwise", "enable": True, "icon": "tr_rotate_tr"},
            "lc": {"desc": "Orient Islands horizontally", "enable": True, "icon": "tr_rotate_lc"},
            "cen": {"desc": "Orient Islands automatically", "enable": True, "icon": "tr_rotate_cen"},
            "rc": {"desc": "Orient Islands horizontally", "enable": True, "icon": "tr_rotate_rc"},
            "bl": {"desc": "Rotate Islands counterclockwise", "enable": True, "icon": "tr_rotate_bl"},
            "bc": {"desc": "Orient Islands vertically", "enable": True, "icon": "tr_rotate_bc"},
            "br": {"desc": "Rotate Islands clockwise", "enable": True, "icon": "tr_rotate_br"}
        },
        "FLIP": {
            "tl": {"desc": "Flip Islands Up Left in X and Y", "enable": True, "icon": "tr_control_tl"},
            "tc": {"desc": "Flip Islands Up in Y", "enable": True, "icon": "tr_control_tc"},
            "tr": {"desc": "Flip Islands Up Right in X and Y", "enable": True, "icon": "tr_control_tr"},
            "lc": {"desc": "Flip Islands Left in X", "enable": True, "icon": "tr_control_lc"},
            "cen": {"desc": "Disabled", "enable": False, "icon": "tr_control_cen"},
            "rc": {"desc": "Flip Islands Right in X", "enable": True, "icon": "tr_control_rc"},
            "bl": {"desc": "Flip Islands Down Left in X and Y", "enable": True, "icon": "tr_control_bl"},
            "bc": {"desc": "Flip Islands Down in Y", "enable": True, "icon": "tr_control_bc"},
            "br": {"desc": "Flip Islands Down Right in X and Y", "enable": True, "icon": "tr_control_br"}
        },
        "FIT": {
            "tl": {"desc": "Fit Islands from Up Left", "enable": True, "icon": "tr_control_tl"},
            "tc": {"desc": "Fit Islands from Up with width X. The length will change proportionally", "enable": True, "icon": "tr_control_tc"},
            "tr": {"desc": "Fit Islands from Up Right", "enable": True, "icon": "tr_control_tr"},
            "lc": {"desc": "Fit Islands from Left with width Y. The length will change proportionally", "enable": True, "icon": "tr_control_lc"},
            "cen": {"desc": "Fit Islands from Center", "enable": True, "icon": "tr_control_cen"},
            "rc": {"desc": "Fit Islands from Right with width Y. The length will change proportionally", "enable": True, "icon": "tr_control_rc"},
            "bl": {"desc": "Fit Islands from Down Left", "enable": True, "icon": "tr_control_bl"},
            "bc": {"desc": "Fit Islands from Down with width X. The length will change proportionally", "enable": True, "icon": "tr_control_bc"},
            "br": {"desc": "Fit Islands from Down Right", "enable": True, "icon": "tr_control_br"}
        },
        "ALIGN": {
            "tl": {"desc": "Align Islands from Up Left in X and Y", "enable": True, "icon": "tr_control_tl"},
            "tc": {"desc": "Align Islands from Up in Y only", "enable": True, "icon": "tr_control_tc"},
            "tr": {"desc": "Align Islands from Up Right in X and Y", "enable": True, "icon": "tr_control_tr"},
            "lc": {"desc": "Align Islands from Left in X only", "enable": True, "icon": "tr_control_lc"},
            "cen": {"desc": "Align Islands to Center in X and Y", "enable": True, "icon": "tr_control_cen"},
            "rc": {"desc": "Align Islands from Right in X only", "enable": True, "icon": "tr_control_rc"},
            "bl": {"desc": "Align Islands from Down Left in X and Y", "enable": True, "icon": "tr_control_bl"},
            "bc": {"desc": "Align Islands from Down in Y only", "enable": True, "icon": "tr_control_bc"},
            "br": {"desc": "Align Islands from Down Right in X and Y", "enable": True, "icon": "tr_control_br"}
        },
        "2DCURSOR": {
            "tl": {"desc": "Set 2D Cursor Up Left", "enable": True, "icon": "tr_control_tl"},
            "tc": {"desc": "Set 2D Cursor Up", "enable": True, "icon": "tr_control_tc"},
            "tr": {"desc": "Set 2D Cursor Up Right", "enable": True, "icon": "tr_control_tr"},
            "lc": {"desc": "Set 2D Cursor Left", "enable": True, "icon": "tr_control_lc"},
            "cen": {"desc": "Set 2D Cursor to Center", "enable": True, "icon": "tr_control_cen"},
            "rc": {"desc": "Set 2D Cursor Right", "enable": True, "icon": "tr_control_rc"},
            "bl": {"desc": "Set 2D Cursor Down Left", "enable": True, "icon": "tr_control_bl"},
            "bc": {"desc": "Set 2D Cursor Down", "enable": True, "icon": "tr_control_bc"},
            "br": {"desc": "Set 2D Cursor Down Right", "enable": True, "icon": "tr_control_br"}
        }
    }

    @classmethod
    def poll(cls, props):
        return props.tr_mode in cls.STATE

    @classmethod
    def draw(cls, props, layout):
        if cls.poll(props):
            uc_col = layout.column(align=True)
            top_row = uc_col.row(align=True)
            mid_row = uc_col.row(align=True)
            bot_row = uc_col.row(align=True)

            cls.draw_top_row(props, top_row)

            cls.draw_middle_row(props, mid_row)

            cls.draw_bottom_row(props, bot_row)

    @classmethod
    def draw_bottom_row(cls, props, bot_row):

        tl = UcUnit(props, UcOperator('bl'))
        tl.draw(bot_row)

        tc = UcUnit(props, UcOperator('bc'))
        tc.draw(bot_row)

        tr = UcUnit(props, UcOperator('br'))
        tr.draw(bot_row)

    @classmethod
    def draw_middle_row(cls, props, mid_row):

        tl = UcUnit(props, UcOperator('lc'))
        tl.draw(mid_row)

        tc = UcUnit(props, UcOperator('cen'))
        tc.draw(mid_row)

        tr = UcUnit(props, UcOperator('rc'))
        tr.draw(mid_row)

    @classmethod
    def draw_top_row(cls, props, top_row):

        tl = UcUnit(props, UcOperator('tl'))
        tl.draw(top_row)

        tc = UcUnit(props, UcOperator('tc'))
        tc.draw(top_row)

        tr = UcUnit(props, UcOperator('tr'))
        tr.draw(top_row)


def draw_fit_region_section(context, layout):
    ''' @Draw Fit Region Section '''
    from ZenUV.ops.transform_sys.tr_fit import (
        ZUV_OT_FitGrabRegion, ZUV_OT_FitShowRegion,
        ZUV_OT_FitHideRegion, ZUV_OT_FitRegion)

    prop = context.scene.zen_uv

    box = layout.box()
    grab_row = box.row(align=True)
    grab_row.label(text="Grab Region:")

    grb_sel = grab_row.operator(ZUV_OT_FitGrabRegion.bl_idname, text="Selection")
    grb_sel.selected_only = True
    grb_sel.desc = "Grab Region coordinates form Selection"

    grb_island = grab_row.operator(ZUV_OT_FitGrabRegion.bl_idname, text="Island")
    grb_island.selected_only = False
    grb_island.desc = "Grab Region coordinates from Island"

    region_row = box.row(align=True)
    reg_col01 = region_row.column(align=True)
    reg_col01.prop(prop, "tr_fit_region_bl")
    reg_col02 = region_row.column(align=True)
    reg_col02.prop(prop, "tr_fit_region_tr")

    if context.area.type == 'IMAGE_EDITOR':
        row = box.row(align=True)
        row.operator(ZUV_OT_FitShowRegion.bl_idname, icon='HIDE_OFF')
        row.operator(ZUV_OT_FitHideRegion.bl_idname, icon='HIDE_ON')

    box.operator(ZUV_OT_FitRegion.bl_idname)


def draw_extended_transform_panel(context: bpy.types.Context, layout: bpy.types.UILayout):
    ''' @Draw Extended Transform Panel '''
    main_col = layout.column(align=True)

    # Move Section
    box = main_col.box()
    box.label(text='Move:', icon_value=icon_get("transform-move"))
    m_col = box.column(align=True)
    grid = m_col.grid_flow(row_major=True, align=True, columns=2)

    ot = grid.operator(ZUV_OT_TrMove.bl_idname, text='By Increment')
    ot.move_mode = "INCREMENT"
    ot.direction = 'rc'
    ot.increment = 1.0

    ot = grid.operator(ZUV_OT_TrMove.bl_idname, text='To the Active Trim')
    ot.move_mode = "TO_ACTIVE_TRIM"

    ot = grid.operator(ZUV_OT_TrMove.bl_idname, text='To Position')
    ot.move_mode = "TO_POSITION"
    ot.destination_pos = (0.5, 0.5)

    ot = grid.operator(ZUV_OT_TrMove.bl_idname, text='To 2d Cursor')
    ot.move_mode = "TO_CURSOR"

    ot = grid.operator(ZUV_OT_TrMove.bl_idname, text='To Mouse Cursor')
    ot.move_mode = "TO_M_CURSOR"

    grid.operator(ZUV_OT_MoveToUvArea.bl_idname, text='To UV Area')
    m_col.operator(ZUV_OT_Move2dCursorTo.bl_idname)

    if context.area.type == "IMAGE_EDITOR":
        m_col.operator(ZUV_OT_MoveToUvAreaMouseover.bl_idname, icon='EYEDROPPER')
        m_col.operator(ZUV_OT_MoveToUvPositionMouseover.bl_idname, icon='EYEDROPPER')

    # Scale Section
    box = main_col.box()
    box.label(text='Scale:', icon_value=icon_get("transform-scale"))
    grid = box.grid_flow(row_major=True, align=True, columns=2)
    ot = grid.operator(ZUV_OT_TrScale.bl_idname, text='By Axis')
    ot.scale_mode = 'AXIS'
    ot.op_tr_scale = (0.5, 0.5)

    ot = grid.operator(ZUV_OT_TrScale.bl_idname, text='By Units')
    ot.scale_mode = 'UNITS'
    ot.op_unts_uv_area_size = 1000
    ot.op_unts_desired_size = 250
    ot.op_unts_calculate_by = 'HORIZONTAL'

    # Rotate Section
    box = main_col.box()
    box.label(text='Rotate:', icon_value=icon_get("transform-rotate"))
    grid = box.grid_flow(row_major=True, align=True, columns=2)
    ot = grid.operator(ZUV_OT_TrRotate.bl_idname, text='By Angle')
    ot.rotation_mode = 'ANGLE'
    ot.tr_rot_inc_full_range = -90

    ot = grid.operator(ZUV_OT_TrRotate.bl_idname, text='By Increment')
    ot.rotation_mode = 'DIRECTION'
    ot.direction = 'CW'
    ot.tr_rot_inc = 90

    ot = grid.operator(ZUV_OT_TrOrient.bl_idname, text='Orient by Bounding Box')
    ot.mode = 'BBOX'

    ot = grid.operator(ZUV_OT_TrOrient.bl_idname, text='Orient by Selection')
    ot.mode = 'BY_SELECTION'

    # Flip Section
    box = main_col.box()
    box.label(text='Flip:', icon_value=icon_get("transform-flip"))
    grid = box.grid_flow(row_major=True, align=True, columns=2)

    ot = grid.operator(ZUV_OT_TrFlip.bl_idname, text='Horizontal')
    ot.flip_direction = "HORIZONTAL"

    ot = grid.operator(ZUV_OT_TrFlip.bl_idname, text='Vertical')
    ot.flip_direction = "VERTICAL"

    # Fit Section
    box = main_col.box()
    box.label(text='Fit:', icon_value=icon_get("transform-fit"))
    grid = box.grid_flow(row_major=True, align=True, columns=2)

    ot = grid.operator(ZUV_OT_TrFit.bl_idname, text='To UV Area')
    ot.fit_mode = "UV_AREA"
    ot.op_fit_axis = 'AUTO'
    ot.op_padding = 0.0
    ot.op_keep_proportion = True
    ot.match_rotation = False

    ot = grid.operator(ZUV_OT_TrFit.bl_idname, text='To Region')
    ot.fit_mode = "REGION"
    ot.op_region_bl = (0.25, 0.25)
    ot.op_region_tr = (0.75, 0.75)
    ot.op_fit_axis = 'AUTO'
    ot.op_padding = 0.0
    ot.op_keep_proportion = True
    ot.match_rotation = False

    ot = grid.operator(ZUV_OT_TrFit.bl_idname, text='To Active UDIM')
    ot.fit_mode = "ACTIVE_UDIM"
    ot.op_fit_axis = 'AUTO'
    ot.op_padding = 0.0
    ot.op_keep_proportion = True
    ot.match_rotation = False

    ot = grid.operator(ZUV_OT_TrFit.bl_idname, text='To Tile')
    ot.fit_mode = "TILE_NUMBER"
    ot.op_fit_axis = 'AUTO'
    ot.op_padding = 0.0
    ot.op_keep_proportion = True
    ot.match_rotation = False

    # Align Section
    box = main_col.box()
    box.label(text='Align:', icon_value=icon_get("transform-orient"))
    col = box.column(align=True)
    grid = col.grid_flow(row_major=True, align=True, columns=2)

    ot = grid.operator(ZUV_OT_TrAlign.bl_idname, text='To Sel. BBox')
    ot.align_to = "TO_SEL_BBOX"
    ot.align_direction = "cen_v"

    ot = grid.operator(ZUV_OT_TrAlign.bl_idname, text='To Position')
    ot.align_to = "TO_POSITION"
    ot.destination = (0.75, 0.75)
    ot.align_direction = "cen_v"

    ot = grid.operator(ZUV_OT_TrAlign.bl_idname, text='To 2d Cursor')
    ot.align_to = "TO_CURSOR"
    ot.align_direction = "cen_v"

    ot = grid.operator(ZUV_OT_TrAlign.bl_idname, text='To UV Area')
    ot.align_to = "TO_UV_AREA"
    ot.align_direction = "cen_v"

    ot = grid.operator(ZUV_OT_TrAlign.bl_idname, text='To Active UDIM')
    ot.align_to = "ACTIVE_UDIM"
    ot.align_direction = "cen"

    ot = grid.operator(ZUV_OT_TrAlign.bl_idname, text='To Tile Number')
    ot.align_to = "TILE_NUMBER"
    ot.align_direction = "cen"

    ot = col.operator(ZUV_OT_TrAlign.bl_idname, text='To Active Component')
    ot.align_to = "TO_ACTIVE_COMPONENT"
    ot.align_direction = "cen_v"

    # Distribute Section
    box = main_col.box()
    box.label(text='Distribute:', icon_value=icon_get("transform-orient"))
    col = box.column(align=True)

    col.operator("uv.zenuv_distribute_islands", text="Distribute & Sort")
    col.operator("uv.zenuv_arrange_transform")
    col.operator("uv.zenuv_distribute_verts", text='Distribute Verts')


transform_parented_panels = (
    ZUV_PT_UVL_SubTransform,
    ZUV_PT_3DV_SubTransform,
)
