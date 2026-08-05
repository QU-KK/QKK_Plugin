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

from ...app_iface import *
from ...panel import UVPM4_PT_Generic, UVPM4_PT_IParamEditMixin
from ...multi_panel import PackMultiPanel, GroupingPackMultiPanel
from ...utils import PropertyWrapper
from ...panel_islands import UVPM4_PT_NumberedGroups, UVPM4_PT_StackGroups, NumberedGroupsDrawer
from ...panel_grouping_editor import UVPM4_PT_GroupTargetBoxes, UVPM4_PT_Grouping, UVPM4_PT_SchemeGroups
from ..engine.labels import Labels
from ..engine.types import PackOpType
from ...operator import UVPM4_OT_AdjustIslandsToTexture, UVPM4_OT_UndoIslandsAdjustmentToTexture
from ...presets import UVPM4_PT_PresetsCustomTargetBox

from ...box_ui import CustomTargetBoxEditUI
from ...operator_misc import UVPM4_MT_SetRotStepScene
from ...operator_islands import IParamEditUI, NumberedGroupsAccess

from ...presets import UVPM4_PT_Presets
from ...mode import UVPM4_MT_BrowsePackModes


class UVPM4_PT_GenericPack(UVPM4_PT_Generic):

    PARENT_M_PANEL_ID = PackMultiPanel.M_PANEL_ID

    @classmethod
    def get_active_mode(cls, context):
        return get_prefs().get_active_pack_mode(context)
    

class UVPM4_PT_MainPack(UVPM4_PT_GenericPack):

    bl_idname = 'UVPM4_PT_MainPack'
    bl_label = 'Packing'
    bl_context = ''

    PANEL_PRIORITY = 100
    PRESET_PANEL = UVPM4_PT_Presets

    def draw_header_preset(self, _context):
        UVPM4_PT_Presets.draw_panel_header(self.layout)

    def draw_impl(self, context):

        layout = self.layout
        col = layout.column(align=True)

        self.draw_main_prop_sets(col)
        from ..operators.pack_operator import UVPM4_OT_Pack

        row = col.row(align=True)
        row.scale_y = 1.4
        op = row.operator(UVPM4_OT_Pack.bl_idname)
        op.mode_id = UVPM4_OT_Pack.ACTIVE_META_VALUE
        op.pack_op_type = PackOpType.PACK.value()

        row = col.row(align=True)
        op = row.operator(UVPM4_OT_Pack.bl_idname, text='Pack To Others')
        op.mode_id = UVPM4_OT_Pack.ACTIVE_META_VALUE
        op.pack_op_type = PackOpType.PACK_TO_OTHERS.value()

        row = col.row(align=True)
        op = row.operator(UVPM4_OT_Pack.bl_idname, text='Repack With Others')
        op.mode_id = UVPM4_OT_Pack.ACTIVE_META_VALUE
        op.pack_op_type = PackOpType.REPACK_WITH_OTHERS.value()

        col.separator()
        row = col.row(align=True)

        row.menu(UVPM4_MT_BrowsePackModes.bl_idname, text=type(self.active_mode).enum_name(), icon='MODIFIER')

        if self.active_mode.MODE_HELP_URL_SUFFIX:
            from ...help import UVPM4_OT_PackModeHelp
            help_op = row.operator(UVPM4_OT_PackModeHelp.bl_idname, icon=UVPM4_OT_PackModeHelp.ICON, text='')
            help_op.url_suffix = self.active_mode.MODE_HELP_URL_SUFFIX

        if self.active_mode.grouping_config.grouping_enabled:
            from ...prefs import GROUPING_PACK_DIS_MSG
            self.prefs.dis_msgs.handle(GROUPING_PACK_DIS_MSG, col, add_separator=False)


class UVPM4_PT_AdvancedPackOptions(UVPM4_PT_GenericPack):

    bl_idname = 'UVPM4_PT_AdvancedPackOptions'
    bl_label = 'Advanced Packing Options'
    bl_context = ''

    bl_options = {'DEFAULT_CLOSED'}

    PANEL_PRIORITY = 300
    ENABLE_MENU_LABEL = 'Adv. Packing Features'

    def draw_impl(self, context):
        col = self.layout.column(align=True)
        self.main_props.pack_strategy_props.draw(col)


class UVPM4_PT_SubPanelPack(UVPM4_PT_GenericPack):
    
    bl_parent_id = UVPM4_PT_MainPack.bl_idname

    @classmethod
    def poll_impl(cls, context):
        return cls.bl_idname in cls.active_mode.subpanels_base()
    

class UVPM4_PT_TileSetup(UVPM4_PT_SubPanelPack):

    bl_idname = 'UVPM4_PT_TileSetup'
    bl_label = 'Tile Setup'

    PANEL_PRIORITY = 500

    @classmethod
    def poll_impl(cls, context):
        return super().poll_impl(context) and cls.active_mode.supports_pack_to_tiles()
    
    def warning_msg(self, context):
        return self.main_props.tile_target_props.validate_fail_msg()
    
    def not_supported_msg(self, context):
        if self.active_mode.supports_custom_target_box() and self.main_props.custom_target_box_enable:
            return 'These settings are ignored when custom target box is enabled'
        
        return None

    def draw_impl(self, context):
        layout = self.layout
        col = layout.column(align=True)

        if self.active_mode.supports_tile_target():
            self.main_props.tile_target_props.draw(col)

        if self.active_mode.supports_tile_filling_method():
            filling_method_warning_msg = "The '{}' method is always used for islands packed with fixed scale".format(Labels.TILE_FILLING_METHOD_ONE_BY_ONE_NAME)\
                if self.main_props.fixed_scale_enabled() else None
    
            self.draw_enum_in_box(
                self.main_props,
                "tile_filling_method",
                col,
                warning_msg=filling_method_warning_msg)


class UVPM4_PT_PackOptions(UVPM4_PT_GenericPack):

    bl_idname = 'UVPM4_PT_PackOptions'
    bl_label = 'Packing Options'

    ENABLE_MENU_LABEL = 'Packing Features'
    PANEL_PRIORITY = 200
    HELP_URL_SUFFIX = '20-packing-functionalities/15-basic-packing-and-options'

    def draw_impl(self, context):
        layout = self.layout
        col = layout.column(align=True)

        self.prop_with_help(self.main_props, "precision", col, self.HELP_URL_SUFFIX if self.props_with_help else None)

        row = col.row(align=True)
        margin_supported = not self.main_props.pixel_margin_enabled()
        margin_not_supported_msg = 'The Margin option is ignored when Pixel Margin is enabled'
        self.handle_prop(self.main_props, "margin", row, not_supported_msg=None if margin_supported else margin_not_supported_msg)

        # Rotation Resolution
        box = col.box()

        row = box.row()
        # TODO: missing feature check
        row.prop(self.main_props, "rotation_enable")

        box = col.box()
        row = box.row()
        row.enabled = self.main_props.rotation_enable
        row.prop(self.main_props, "pre_rotation_disable")

        row = col.row(align=True)
        row.enabled = self.main_props.rotation_enable
        self.draw_prop_with_set_menu(self.main_props, "rotation_step", row, UVPM4_MT_SetRotStepScene)

        # Flipping enable
        box = col.box()
        row = box.row()
        row.prop(self.main_props, "flipping_enable")

        # Scale mode
        self.draw_enum_in_box(self.main_props, "scale_mode", col)


class UVPM4_PT_SubPanelPackOptions(UVPM4_PT_SubPanelPack):
    
    bl_parent_id = UVPM4_PT_PackOptions.bl_idname


class UVPM4_PT_SubPanelAdvancedPackOptions(UVPM4_PT_SubPanelPack):
    
    bl_parent_id = UVPM4_PT_AdvancedPackOptions.bl_idname


class UVPM4_PT_NormalizeScale(UVPM4_PT_SubPanelPackOptions):

    bl_idname = 'UVPM4_PT_NormalizeScale'
    bl_label = 'Normalize Scale'
    bl_options = {'DEFAULT_CLOSED'}

    PANEL_PRIORITY = 1500
    HELP_URL_SUFFIX = '20-packing-functionalities/25-normalize-scale'

    def get_main_property(self):
        return PropertyWrapper(get_main_props(self.context), 'normalize_scale')
    
    def warning_msg(self, context):
        if get_main_props(context).fixed_scale_enabled():
            return "Islands packed with fixed scale will not be normalized"
        
        return None

    def draw_impl(self, context):
        layout = self.layout
        col = layout.column(align=True)

        self.draw_enum_in_box(self.main_props, "normalize_space", col, expand=True)

        box = col.box()
        box.row().prop(self.main_props, "island_normalize_multiplier_enable")

        if self.main_props.island_normalize_multiplier_enable:
            IParamEditUI(self.context, self.main_props, 'NormalizeMultiplierIParamInfo').draw(box.column(align=True))

        box = col.box()
        norm_group_access = NumberedGroupsAccess(self.context, desc_id='norm_group')
        norm_group_enable_prop = norm_group_access.get_enable_property()
        norm_group_enable_prop.draw(box.row(), text='Normalize Groups', help_url_suffix=self.HELP_URL_SUFFIX + '#normalize-groups')

        if norm_group_enable_prop.get():
            NumberedGroupsDrawer(self, desc_id='norm_group').draw(box.column(align=True))


class UVPM4_PT_PixelMargin(UVPM4_PT_SubPanelPackOptions):

    bl_idname = 'UVPM4_PT_PixelMargin'
    bl_label = 'Pixel Margin'
    bl_options = {'DEFAULT_CLOSED'}

    PANEL_PRIORITY = 3000
    HELP_URL_SUFFIX = '20-packing-functionalities/30-pixel-margin'
    PIXEL_PERFECT_ALIGN_URL_SUFFIX = HELP_URL_SUFFIX + '#pixel-perfect-alignment'

    BORDER_MARGIN_ZERO_WARNING_MSG = "When packing to multiple tiles with 'Border Margin' set to 0, the packer may report islands packed into neighbor tiles as overlapping (islands may touch at a tile boundary)"

    def get_main_property(self):
        return PropertyWrapper(get_main_props(self.context), 'pixel_margin_enable')

    def draw_impl(self, context):
        layout = self.layout
        col = layout.column(align=True)

        from ...prefs import PIXEL_MARGIN_DIS_MSG
        self.prefs.dis_msgs.handle(PIXEL_MARGIN_DIS_MSG, col)

        # Pixel margin
        self.prop_with_help(self.main_props, "pixel_margin", col, self.HELP_URL_SUFFIX if self.props_with_help else None)

        # Pixel padding
        row = col.row(align=True)
        row.prop(self.main_props, "pixel_border_margin_enable", text='')

        row2 = row.row(align=True)
        row2.enabled = self.main_props.pixel_border_margin_enabled()

        border_margin_warning_msg = self.BORDER_MARGIN_ZERO_WARNING_MSG if self.main_props.pixel_border_margin == 0 else None

        self.handle_prop(self.main_props, "pixel_border_margin", row2, warning_msg=border_margin_warning_msg)

        # Pixel margin to others
        row = col.row(align=True)
        row.prop(self.main_props, "extra_pixel_margin_to_others")

        # Pixel Margin Tex Size
        self.draw_pixel_margin_tex_size(col)

        box = col.box()
        self.prop_with_help(self.main_props, 'pixel_perfect_align', box, self.PIXEL_PERFECT_ALIGN_URL_SUFFIX)

        if self.main_props.pixel_perfect_align:
            col2 = box.column(align=True)
            self.draw_enum_in_box(self.main_props, 'pixel_perfect_align_target', col2)
            self.draw_enum_in_box(self.main_props, 'pixel_perfect_vert_align_mode', col2)


class UVPM4_PT_Heuristic(UVPM4_PT_SubPanelPackOptions):

    bl_idname = 'UVPM4_PT_Heuristic'
    bl_label = 'Heuristic Search'
    bl_options = {'DEFAULT_CLOSED'}

    PANEL_PRIORITY = 4000
    HELP_URL_SUFFIX = '20-packing-functionalities/40-heuristic-search'

    def get_main_property(self):
        return PropertyWrapper(get_main_props(self.context), 'heuristic_enable')

    def draw_impl(self, context):
        layout = self.layout

        col = layout.column(align=True)

        self.prop_with_help(self.main_props, "heuristic_search_time", col, self.HELP_URL_SUFFIX if self.props_with_help else None)
        row = col.row(align=True)
        row.prop(self.main_props, "heuristic_max_wait_time")

        box = col.box()
        row = box.row()

        self.handle_prop(self.main_props, "heuristic_allow_mixed_scales", row, warning_msg=self.main_props.allow_mixed_scales_warning_msg())

        # Advanced Heuristic
        box = col.box()
        box.enabled = self.main_props.advanced_heuristic_available()
        row = box.row()
        self.handle_prop(self.main_props, "advanced_heuristic", row)
        

class UVPM4_PT_LockOverlapping(UVPM4_PT_SubPanelAdvancedPackOptions):

    bl_idname = 'UVPM4_PT_LockOverlapping'
    bl_label = 'Lock Overlapping'
    bl_options = {'DEFAULT_CLOSED'}

    PANEL_PRIORITY = 4400
    HELP_URL_SUFFIX = '20-packing-functionalities/50-lock-overlapping'

    def get_main_property(self):
        return PropertyWrapper(get_main_props(self.context), 'lock_overlapping_enable')

    def draw_impl(self, context):
        layout = self.layout
        col = layout.column(align=True)

        # Lock overlapping
        self.draw_enum_in_box(self.main_props, "lock_overlapping_mode", col, self.HELP_URL_SUFFIX)
        


class UVPM4_PT_LockGroups(UVPM4_PT_NumberedGroups, UVPM4_PT_SubPanelAdvancedPackOptions):

    bl_idname = 'UVPM4_PT_LockGroups'
    bl_label = 'Lock Groups'
    bl_options = {'DEFAULT_CLOSED'}

    PANEL_PRIORITY = 4500

    DESC_ID = 'lock_group'
    HELP_URL_SUFFIX = '20-packing-functionalities/50-lock-overlapping#lock-groups'


class UVPM4_PT_StackGroupsPack(UVPM4_PT_StackGroups, UVPM4_PT_SubPanelAdvancedPackOptions):

    bl_idname = 'UVPM4_PT_StackGroupsPack'
    PANEL_PRIORITY = 4700


class UVPM4_PT_TrackGroups(UVPM4_PT_NumberedGroups, UVPM4_PT_SubPanelAdvancedPackOptions):

    bl_idname = 'UVPM4_PT_TrackGroups'
    bl_label = 'Track Groups'
    bl_options = {'DEFAULT_CLOSED'}

    PANEL_PRIORITY = 4800

    DESC_ID = 'track_group'
    HELP_URL_SUFFIX = '20-packing-functionalities/57-track-groups'

    def post_draw(self, layout):
        track_groups_props = self.main_props.track_groups_props

        self.draw_enum_in_box(track_groups_props, 'matching_mode', layout)

        box = layout.box()
        box.prop(track_groups_props, 'require_match_for_all')


class UVPM4_PT_NonSquarePacking(UVPM4_PT_SubPanelAdvancedPackOptions):

    bl_idname = 'UVPM4_PT_NonSquarePacking'
    bl_label = 'Non-Square Packing'
    bl_options = {'DEFAULT_CLOSED'}

    PANEL_PRIORITY = 5000
    HELP_URL_SUFFIX = '20-packing-functionalities/60-non-square-packing'

    def get_main_property(self):
        return PropertyWrapper(get_main_props(self.context), 'non_square_packing')

    def draw_impl(self, context):
        layout = self.layout
        col = layout.column(align=True)

        self.operator_with_help(UVPM4_OT_AdjustIslandsToTexture.bl_idname, col, help_url_suffix=self.HELP_URL_SUFFIX if self.props_with_help else None)

        row = col.row(align=True)
        row.operator(UVPM4_OT_UndoIslandsAdjustmentToTexture.bl_idname)


class UVPM4_PT_TargetBox(UVPM4_PT_SubPanelAdvancedPackOptions):

    bl_idname = 'UVPM4_PT_TargetBox'
    bl_label = 'Custom Target Box'
    bl_options = {'DEFAULT_CLOSED'}

    PRESET_PANEL = UVPM4_PT_PresetsCustomTargetBox
    PANEL_PRIORITY = 6000
    HELP_URL_SUFFIX = '20-packing-functionalities/70-custom-target-box/'

    def get_main_property(self):
        return PropertyWrapper(get_main_props(self.context), 'custom_target_box_enable')

    def draw_header_preset(self, _context):
        UVPM4_PT_PresetsCustomTargetBox.draw_panel_header(self.layout)

    def draw_impl(self, context):
        layout = self.layout

        col = layout.column(align=True)

        box_edit_UI = CustomTargetBoxEditUI(context, self.main_props)
        box_edit_UI.draw(col)


class UVPM4_PT_IslandRotStep(UVPM4_PT_IParamEditMixin, UVPM4_PT_SubPanelAdvancedPackOptions):

    bl_idname = 'UVPM4_PT_IslandRotStep'
    bl_label = 'Island Rotation Step'
    bl_options = {'DEFAULT_CLOSED'}

    HELP_URL_SUFFIX = '20-packing-functionalities/80-island-rotation-step'

    PANEL_PRIORITY = 7000
    IPARAM_INFO_TYPE = 'RotStepIParamInfo'


from ...scripting import UVPM4_PT_ScriptingBase

class UVPM4_PT_ScriptingPack(UVPM4_PT_ScriptingBase, UVPM4_PT_SubPanelAdvancedPackOptions):

    bl_idname = 'UVPM4_PT_ScriptingPack'
    bl_label = 'Scripting'
    bl_options = {'DEFAULT_CLOSED'}

    HELP_URL_SUFFIX = '20-packing-functionalities/95-scripting'
    PANEL_PRIORITY = 9000
    SCRIPT_CONTAINER_ID = 'packing'



class UVPM4_PT_GenericGroupingPack(UVPM4_PT_GenericPack):

    PARENT_M_PANEL_ID = GroupingPackMultiPanel.M_PANEL_ID


class UVPM4_PT_GroupingPack(UVPM4_PT_Grouping, UVPM4_PT_GenericGroupingPack):

    bl_idname = 'UVPM4_PT_GroupingPack'
    bl_label = 'Grouping (Packing)'


class UVPM4_PT_SchemeGroupsPack(UVPM4_PT_SchemeGroups, UVPM4_PT_GenericGroupingPack):

    bl_idname = 'UVPM4_PT_SchemeGroupsPack'
    bl_parent_id = UVPM4_PT_GroupingPack.bl_idname


class UVPM4_PT_GroupTargetBoxesPack(UVPM4_PT_GroupTargetBoxes, UVPM4_PT_GenericGroupingPack):

    bl_idname = 'UVPM4_PT_GroupTargetBoxesPack'
    bl_parent_id = UVPM4_PT_GroupingPack.bl_idname
