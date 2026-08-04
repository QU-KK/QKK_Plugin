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


from .multi_panel import GroupingEditorMultiPanel
from .grouping_scheme_access import GroupingSchemeAccess
from .grouping_scheme_ui import UVPM4_MT_BrowseGroupingSchemes
from .panel import UVPM4_PT_Generic
from .operator_islands import UVPM4_OT_SetManualGroupIParam, UVPM4_OT_SelectManualGroupIParam, UVPM4_OT_ShowManualGroupIParam, UVPM4_OT_ApplyGroupingToScheme
from .app_iface import get_main_props
from .spipeline.modes.grouping_editor_mode import UVPM4_Mode_GroupingEditor
from .spipeline.operators.grouping_editor_operator import UVPM4_OT_EditGroupingSchemeInEditor


from .grouping_scheme import\
    (UVPM4_OT_NewGroupingScheme,
     UVPM4_OT_RemoveGroupingScheme,
     UVPM4_OT_NewGroupInfo,
     UVPM4_OT_RemoveGroupInfo,
     UVPM4_OT_NewTargetBox,
     UVPM4_OT_RemoveTargetBox,
     UVPM4_OT_MoveGroupInfo,
     UVPM4_OT_MoveTargetBox)

from .grouping_scheme_ui import UVPM4_UL_GroupInfo, UVPM4_UL_TargetBoxes

from .box_ui import GroupingSchemeBoxesEditUI


class GroupingSchemeDrawer:

    def __init__(self,
                 context,
                 active_mode,
                 access_desc_id=None,
                 access_desc=None,
                 should_draw_grouping_options=False,
                 preset_panel_t=None,
                 draw_edit_g_scheme_button=False):
        
        self.context = context

        self.gs_access = GroupingSchemeAccess(context, desc_id=access_desc_id, desc=access_desc, ui_drawing=True)
        self.main_props = get_main_props(context)
        self.active_mode = active_mode
        self.should_draw_grouping_options = should_draw_grouping_options
        self.preset_panel_t = preset_panel_t
        self.draw_edit_g_scheme_button = draw_edit_g_scheme_button

    def draw_g_schemes_presets(self, layout):
        layout.emboss = 'NONE'
        layout.popover(panel=self.preset_panel_t.__name__, icon='PRESET', text="")

    def draw_g_schemes(self, layout):
        main_col = layout.column(align=True)
        self.gs_access.layout_init_desc(main_col)
        main_col.label(text='Select a grouping scheme:')

        row = main_col.row(align=True)
        row.menu(UVPM4_MT_BrowseGroupingSchemes.bl_idname, text="", icon='GROUP_UVS')

        g_scheme_available = len(self.gs_access.g_schemes) > 0

        if self.gs_access.active_g_scheme is not None:
            row.prop(self.gs_access.active_g_scheme, "name", text="")
        elif g_scheme_available:
            box = row.box()
            box.scale_y = 0.5
            box.enabled = False
            box.label(text='← Select a grouping scheme')

        op = row.operator(UVPM4_OT_NewGroupingScheme.bl_idname, icon='ADD', text='' if g_scheme_available else UVPM4_OT_NewGroupingScheme.bl_label)

        if self.gs_access.active_g_scheme is not None:
            op = row.operator(UVPM4_OT_RemoveGroupingScheme.bl_idname, icon='REMOVE', text='')

        if self.preset_panel_t is not None:
            box = row.box()
            box.scale_y = 0.5
            self.draw_g_schemes_presets(box)

        if self.draw_edit_g_scheme_button:
            main_col.separator()
            row = main_col.row(align=True)
            op = row.operator(UVPM4_OT_EditGroupingSchemeInEditor.bl_idname)
            if self.gs_access.active_g_scheme is None:
                row.enabled = False
            else:
                op.g_scheme_uuid = self.gs_access.get_active_g_scheme_uuid()

        if self.gs_access.active_g_scheme is None:
            return None

        if self.should_draw_grouping_options:
            main_col.separator()
            main_col.separator()
            main_col.label(text='Scheme options:')
            self.draw_grouping_options(self.gs_access.active_g_scheme.options, main_col, self.gs_access.active_g_scheme)


    def draw_grouping_options(self, g_options, layout, g_scheme=None):
        self.active_mode.draw_grouping_options(g_scheme, g_options, layout)

    def draw_groups(self, layout):
        if self.gs_access.active_g_scheme is None:
            return

        main_col = layout.column(align=True)
        self.gs_access.layout_init_desc(main_col)

        groups_layout = main_col # .box()

        show_more = self.gs_access.active_g_scheme is not None and len(self.gs_access.active_g_scheme.groups) > 1

        row = groups_layout.row()
        row.template_list(UVPM4_UL_GroupInfo.bl_idname, "", self.gs_access.active_g_scheme, "groups",
                            self.gs_access.active_g_scheme,
                            "active_group_idx", rows=4 if show_more else 2)

        col = row.column(align=True)
        op = col.operator(UVPM4_OT_NewGroupInfo.bl_idname, icon='ADD', text="")

        op = col.operator(UVPM4_OT_RemoveGroupInfo.bl_idname, icon='REMOVE', text="")

        if show_more:
            col.separator()
            op = col.operator(UVPM4_OT_MoveGroupInfo.bl_idname, icon='TRIA_UP', text="")
            op.direction = 'UP'

            op = col.operator(UVPM4_OT_MoveGroupInfo.bl_idname, icon='TRIA_DOWN', text="")
            op.direction = 'DOWN'

        if self.gs_access.active_group is None:
            return
            
        col = groups_layout.column(align=True)
        col.separator()

        if hasattr(self.active_mode, 'draw_group_options'):
            col.label(text='Group options:')
            col2 = col.column(align=True)

            props_count = self.active_mode.draw_group_options(self.gs_access.active_g_scheme, self.gs_access.active_group, col2)

            if props_count == 0:
                box = col2.box()
                box.label(text='No group options available the for currently selected modes')

        col.separator()
        col.separator()
        row = col.row(align=True)
        op = row.operator(UVPM4_OT_SetManualGroupIParam.bl_idname)
        col.separator()

        col.label(text="Select islands assigned to the group:")
        row = col.row(align=True)

        op = row.operator(UVPM4_OT_SelectManualGroupIParam.bl_idname, text="Select")
        op.select = True

        op = row.operator(UVPM4_OT_SelectManualGroupIParam.bl_idname, text="Deselect")
        op.select = False

        row = col.row(align=True)
        op = row.operator(UVPM4_OT_ShowManualGroupIParam.bl_idname)

    def draw_target_boxes(self, layout):
        if self.gs_access.active_g_scheme is None:
            return
        
        if self.gs_access.active_group is None:
            return

        boxes_not_editable_msg = self.active_mode.target_boxes_not_editable_msg(self.gs_access.active_group)

        target_boxes_col = layout.column(align=True)
        self.gs_access.layout_init_desc(target_boxes_col)
        target_boxes_col.enabled = boxes_not_editable_msg is None

        if boxes_not_editable_msg is not None:
            target_boxes_text='Boxes not editable: {}'.format(boxes_not_editable_msg)
            target_boxes_icon='ERROR'
            row = target_boxes_col.row()
            row.label(text=target_boxes_text, icon=target_boxes_icon)
            return

        show_more = self.gs_access.active_group is not None and len(self.gs_access.active_group.target_boxes) > 1

        row = target_boxes_col.row()
        row.template_list(UVPM4_UL_TargetBoxes.bl_idname, "", self.gs_access.active_group, "target_boxes",
                          self.gs_access.active_group,
                          "active_target_box_idx", rows=4 if show_more else 2)
        col = row.column(align=True)
        op = col.operator(UVPM4_OT_NewTargetBox.bl_idname, icon='ADD', text="")

        op = col.operator(UVPM4_OT_RemoveTargetBox.bl_idname, icon='REMOVE', text="")

        if show_more:
            col.separator()
            op = col.operator(UVPM4_OT_MoveTargetBox.bl_idname, icon='TRIA_UP', text="")
            op.direction = 'UP'

            op = col.operator(UVPM4_OT_MoveTargetBox.bl_idname, icon='TRIA_DOWN', text="")
            op.direction = 'DOWN'

        target_boxes_col.separator()
        box_edit_UI = GroupingSchemeBoxesEditUI(self.active_mode, self.main_props)
        box_edit_UI.draw(target_boxes_col)


class UVPM4_PT_GroupingBase():

    @classmethod
    def poll_impl(cls, context):
        return cls.active_mode.grouping_config.grouping_enabled

    def draw_impl(self, context):
        self.g_scheme_drawer = GroupingSchemeDrawer(context,
                                                    self.active_mode,
                                                    self.active_mode.grouping_config.g_scheme_access_desc_id,
                                                    should_draw_grouping_options=hasattr(self.active_mode, 'draw_grouping_options'),
                                                    preset_panel_t=self.active_mode.grouping_config.g_scheme_preset_panel_t)
        
        self.draw_impl2(context)


class UVPM4_PT_Grouping(UVPM4_PT_GroupingBase):

    PANEL_PRIORITY = 800
    APPLY_GROUPING_TO_SCHEME_HELP_URL_SUFFIX = '30-packing-modes/30-groups-to-tiles/#apply-automatic-grouping-to-a-grouping-scheme'
            
    def draw_impl2(self, context):
        layout = self.layout

        col = layout.column(align=True)
        box = col.box()
        col2 = box.column(align=True)
        self.active_mode.grouping_config.draw_group_method(col2)

        if self.active_mode.grouping_config.auto_grouping_enabled():
            if self.g_scheme_drawer.should_draw_grouping_options:
                options_box = col.box()
                options_col = options_box.column(align=True)
                options_col.label(text='Grouping options:')
                # options_box = options_col.box()

                self.g_scheme_drawer.draw_grouping_options(self.main_props.auto_group_options, options_col)
            
            box = col.box()
            self.operator_attach_mode(UVPM4_OT_ApplyGroupingToScheme.bl_idname, self.active_mode.MODE_ID, box, help_url_suffix=self.APPLY_GROUPING_TO_SCHEME_HELP_URL_SUFFIX)

        else:
            # col.separator()
            box = col.box()
            self.g_scheme_drawer.draw_g_schemes(box)


class UVPM4_PT_RequireGroupingScheme(UVPM4_PT_GroupingBase):

    @classmethod
    def poll_impl(cls, context):
        return super().poll_impl(context) and cls.active_mode.grouping_config.get_active_g_scheme(ui_drawing=True) is not None
    

class UVPM4_PT_SchemeGroups(UVPM4_PT_RequireGroupingScheme):

    bl_label = 'Scheme Groups'

    PANEL_PRIORITY = 810

    def draw_impl2(self, context):
        self.g_scheme_drawer.draw_groups(self.layout)


class UVPM4_PT_GroupTargetBoxes(UVPM4_PT_RequireGroupingScheme):

    bl_label = 'Group Target Boxes'

    PANEL_PRIORITY = 820

    @classmethod
    def poll_impl(cls, context):
        return super().poll_impl(context) and cls.active_mode.grouping_config.target_box_editing

    def draw_impl2(self, context):
        self.g_scheme_drawer.draw_target_boxes(self.layout)


class UVPM4_PT_GenericGroupingEditor(UVPM4_PT_Generic):

    PARENT_M_PANEL_ID = GroupingEditorMultiPanel.M_PANEL_ID

    @classmethod
    def get_active_mode(cls, context):
        return UVPM4_Mode_GroupingEditor(context)
