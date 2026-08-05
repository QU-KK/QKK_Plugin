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


from .box_utils import CustomTargetBoxAccess

from .operator_box import (UVPM4_OT_MoveCustomTargetBox,
                           UVPM4_OT_MoveGroupingSchemeBox,
                           UVPM4_OT_RenderCustomTargetBox,
                           UVPM4_OT_RenderGroupingSchemeBoxes,
                           UVPM4_OT_SelectIslandsInCustomTargetBox,
                           UVPM4_OT_SelectIslandsInGroupingSchemeBox,
                           UVPM4_OT_SetCustomTargetBoxToTile,
                           UVPM4_OT_SetGroupingSchemeBoxToTile,
                           UVPM4_OT_FinishBoxRendering)

from .utils import get_prefs, PanelUtilsMixin


class BoxEditUI(PanelUtilsMixin):

    def __init__(self, context, main_props):
        self.prefs = get_prefs()
        self.box_access = self.get_box_access(context)
        self.context = context
        self.main_props = main_props

    def force_show_coords_impl(self):
        return False
    
    def init_operator_impl(self, op):
        pass

    def draw(self, layout):
        col = layout.column(align=True)
        edit_enable = self.edit_enable_impl()
        active_box = self.box_access.active_box_impl()
        draw_box_coords = active_box is not None and (edit_enable or self.force_show_coords_impl())

        if edit_enable or draw_box_coords:
            edit_box = col.box()
            edit_col = edit_box.column(align=True)
            # edit_col.enabled = edit_enable

        if draw_box_coords:
            edit_col.label(text='Box coordinates:')

            coord_c = edit_col.column(align=True)

            row = coord_c.row(align=True)
            row.prop(active_box, "p1_x")

            row = coord_c.row(align=True)
            row.prop(active_box, "p1_y")

            row = coord_c.row(align=True)
            row.prop(active_box, "p2_x")

            row = coord_c.row(align=True)
            row.prop(active_box, "p2_y")

            edit_col.separator()

        if edit_enable:
            edit_box = col.box()
            edit_col = edit_box.column(align=True)
            
            row = edit_col.row(align=True)
            op = row.operator(self.set_to_tile_operator_impl().bl_idname)
            self.init_operator_impl(op)

            edit_col.separator()
            edit_col.label(text='Islands inside the box:')

            select_op = self.select_islands_in_box_operator_impl()
            row = edit_col.row(align=True)
            op = row.operator(select_op.bl_idname, text="Select")
            self.init_operator_impl(op)
            op.select = True

            op = row.operator(select_op.bl_idname, text="Deselect")
            self.init_operator_impl(op)
            op.select = False

            box = edit_col.box()
            box.prop(self.main_props, "fully_inside")

            edit_col.separator()
            edit_col.label(text='Move the box to an adjacent tile:')

            move_op = self.move_box_operator_impl()

            move_cols = self.create_split_columns(edit_col, (0.33, 0.33))

            op = move_cols[0].operator(move_op.bl_idname, text="↖")
            self.init_operator_impl(op)
            op.dir_x = -1
            op.dir_y = 1
            op = move_cols[0].operator(move_op.bl_idname, text="←")
            self.init_operator_impl(op)
            op.dir_x = -1
            op.dir_y = 0
            op = move_cols[0].operator(move_op.bl_idname, text="↙")
            self.init_operator_impl(op)
            op.dir_x = -1
            op.dir_y = -1

            op = move_cols[1].operator(move_op.bl_idname, text="↑")
            self.init_operator_impl(op)
            op.dir_x = 0
            op.dir_y = 1
            move_cols[1].label(text=" ")
            op = move_cols[1].operator(move_op.bl_idname, text="↓")
            self.init_operator_impl(op)
            op.dir_x = 0
            op.dir_y = -1

            op = move_cols[2].operator(move_op.bl_idname, text="↗")
            self.init_operator_impl(op)
            op.dir_x = 1
            op.dir_y = 1
            op = move_cols[2].operator(move_op.bl_idname, text="→")
            self.init_operator_impl(op)
            op.dir_x = 1
            op.dir_y = 0
            op = move_cols[2].operator(move_op.bl_idname, text="↘")
            self.init_operator_impl(op)
            op.dir_x = 1
            op.dir_y = -1

            box = edit_col.box()
            box.label(text='TIP: press with Shift to move the box')
            box.label(text='together with selected islands inside')

            edit_col.separator()

        if edit_enable:
            col.operator(UVPM4_OT_FinishBoxRendering.bl_idname)
        else:
            op = col.operator(self.render_boxes_operator_impl().bl_idname)
            self.init_operator_impl(op)


class GroupingSchemeBoxesEditUI(BoxEditUI):

    def __init__(self, active_mode, main_props):
        from .mode import UVPM4_Mode_Generic
        self.active_mode : UVPM4_Mode_Generic = active_mode

        super().__init__(active_mode.context, main_props)

    def get_box_access(self, context):
        from .operator_box import ActiveModeGroupingSchemeRenderAccess
        return ActiveModeGroupingSchemeRenderAccess(self.active_mode, ui_drawing=True)

    def active_box_impl(self):
        return self.gs_access.active_target_box

    def edit_enable_impl(self):
        return self.prefs.group_scheme_boxes_editing

    def set_to_tile_operator_impl(self):
        return UVPM4_OT_SetGroupingSchemeBoxToTile

    def render_boxes_operator_impl(self):
        return UVPM4_OT_RenderGroupingSchemeBoxes

    def move_box_operator_impl(self):
        return UVPM4_OT_MoveGroupingSchemeBox

    def select_islands_in_box_operator_impl(self):
        return UVPM4_OT_SelectIslandsInGroupingSchemeBox
    
    def init_operator_impl(self, op):
        if hasattr(op, 'mode_id'):
            op.mode_id = self.active_mode.MODE_ID

        op.gs_access_desc_id = self.active_mode.grouping_config.g_scheme_access_desc_id
    

class CustomTargetBoxEditUI(BoxEditUI):

    def get_box_access(self, context):
        return CustomTargetBoxAccess(context, ui_drawing=True)

    def force_show_coords_impl(self):
        return True

    def edit_enable_impl(self):
        return self.prefs.custom_target_box_editing

    def set_to_tile_operator_impl(self):
        return UVPM4_OT_SetCustomTargetBoxToTile

    def render_boxes_operator_impl(self):
        return UVPM4_OT_RenderCustomTargetBox

    def move_box_operator_impl(self):
        return UVPM4_OT_MoveCustomTargetBox

    def select_islands_in_box_operator_impl(self):
        return UVPM4_OT_SelectIslandsInCustomTargetBox
