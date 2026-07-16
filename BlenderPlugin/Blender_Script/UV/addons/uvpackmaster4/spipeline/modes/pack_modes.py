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

from ...mode import UVPM4_Mode_Generic, ModeType
from ..engine.island_params import NormalizeMultiplierIParamInfo, RotStepIParamInfo, TexelDensityPackingIParamInfo
from ...island_params import VColorIParamSerializer
from ...utils import in_debug_mode
from ...spipeline.engine.types import TexelDensityGroupPolicy, GroupLayoutMode, UvpmCoordSpace, PackOpType, UvpmScaleMode
from ...panel import PanelUtilsMixin
from ...operator_misc import UVPM4_MT_SetRotStepGroup, UVPM4_MT_SetPixelMarginTexSizeGroup
from ...operator_islands import NumberedGroupsAccess
from ..engine.g_scheme import GroupFeatures
from ...app_iface import *
from .align_mode import UVPM4_Mode_Align

from ..panels.pack_panels import (
        UVPM4_PT_TileSetup,
        UVPM4_PT_PackOptions,
        UVPM4_PT_NormalizeScale,
        UVPM4_PT_PixelMargin,
        UVPM4_PT_Heuristic,
        UVPM4_PT_NonSquarePacking,
        UVPM4_PT_TargetBox,
        UVPM4_PT_IslandRotStep,
        UVPM4_PT_LockOverlapping,
        UVPM4_PT_LockGroups,
        UVPM4_PT_StackGroupsPack,
        UVPM4_PT_TrackGroups,
        UVPM4_PT_ScriptingPack
    )


class UVPM4_Mode_Pack(UVPM4_Mode_Generic):
    
    MODE_TYPE = ModeType.PACK

    align_mode = None

    def __init__(self, context, interactive=False, pack_op_type=PackOpType.PACK.value(), auto_repack=False):
        super().__init__(context)

        self.interactive = interactive
        self.pack_op_type = pack_op_type
        self.auto_repack = auto_repack
        self.pinned_as_others = self.prefs.pinned_uvs_as_others

        self.lock_groups_access = NumberedGroupsAccess(self.context, desc_id='lock_group')
        self.track_groups_access = NumberedGroupsAccess(self.context, desc_id='track_group')
        self.norm_groups_access = NumberedGroupsAccess(self.context, desc_id='norm_group')

    def subpanels(self):
        output = []
        output.append(UVPM4_PT_TileSetup.bl_idname)
        output.append(UVPM4_PT_PackOptions.bl_idname)
        output.append(UVPM4_PT_NormalizeScale.bl_idname)
        output.append(UVPM4_PT_PixelMargin.bl_idname)
        output.append(UVPM4_PT_Heuristic.bl_idname)
        output.append(UVPM4_PT_LockOverlapping.bl_idname)
        output.append(UVPM4_PT_LockGroups.bl_idname)
        output.append(UVPM4_PT_StackGroupsPack.bl_idname)
        output.append(UVPM4_PT_TrackGroups.bl_idname)
        output.append(UVPM4_PT_NonSquarePacking.bl_idname)

        if self.supports_custom_target_box():
            output.append(UVPM4_PT_TargetBox.bl_idname)

        output.append(UVPM4_PT_IslandRotStep.bl_idname)
        output.append(UVPM4_PT_ScriptingPack.bl_idname)

        return output
    
    def get_grouping_config(self):
        config = super().get_grouping_config()
        config.g_scheme_access_desc_id = 'packing'

        from ...utils import PropertyWrapper
        config.group_method_prop = PropertyWrapper(get_main_props(self.context), 'group_method_pack')

        from ...presets_grouping_scheme import UVPM4_PT_PresetsGroupingSchemePack
        config.g_scheme_preset_panel_t = UVPM4_PT_PresetsGroupingSchemePack

        return config

    def pre_operation(self, op):
        super().pre_operation(op)
        self.main_props.set_pack_ratio(self.app_state)
        
        self.lock_groups_access.init_iparam_name()
        self.track_groups_access.init_iparam_name()
        self.norm_groups_access.init_iparam_name()

        if self.use_align_mode():
            self.align_mode = UVPM4_Mode_Align(self.context)
            self.align_mode.pre_operation(op)

    def validate_operation(self):
        if not self.interactive:
            if self.main_props.heuristic_enabled() and not self.main_props.heuristic_timeout_enabled():
                raise RuntimeError('Non-interactive operation cannot run heuristic search indefinitely')
            
        self.main_props.validate_packing(self)

    def supports_custom_target_box(self):
        return True
    
    def send_unselected_islands(self):
        return PackOpType.send_unselected_islands(self.pack_op_type) or self.track_groups_enabled()
    
    def get_script_container_id(self):
        return 'packing'
    
    def engine_box_renderer_enable(self):
        return True

    def validate_params(self):
        pass

    def use_align_mode(self):
        return self.main_props.align_before_pack_enabled()

    def send_verts_3d(self):
        ret = self.main_props.normalize_scale_enabled() and (self.main_props.normalize_space == UvpmCoordSpace.LOCAL)

        if self.use_align_mode():
            ret |= self.align_mode.send_verts_3d()

        return ret

    def send_verts_3d_global(self):
        ret = self.main_props.normalize_scale_enabled() and (self.main_props.normalize_space == UvpmCoordSpace.GLOBAL)
        ret |= self.tdensity_before_pack_enabled()

        if self.use_align_mode():
            ret |= self.align_mode.send_verts_3d_global()

        return ret

    def lock_groups_enabled(self):
        return self.lock_groups_access.groups_enabled()
    
    def track_groups_enabled(self):
        return self.track_groups_access.groups_enabled()
    
    def norm_groups_enabled(self):
        return self.main_props.normalize_scale_enabled() and self.norm_groups_access.groups_enabled()
    
    def tdensity_before_pack_enabled(self):
        return self.main_props.tdensity_before_pack_enabled()
    
    def island_tdensity_before_pack_enabled(self):
        return self.main_props.island_tdensity_before_pack_enabled()

    def get_iparam_serializers(self):
        output = super().get_iparam_serializers()

        if self.use_align_mode():
            output += self.align_mode.get_iparam_serializers()

        if self.main_props.island_normalize_multiplier_enabled():
            output.append(VColorIParamSerializer(NormalizeMultiplierIParamInfo()))

        if self.main_props.island_rot_step_enabled():
            output.append(VColorIParamSerializer(RotStepIParamInfo()))

        if self.lock_groups_enabled():
            output.append(self.lock_groups_access.get_iparam_serializer())

        if self.track_groups_enabled():
            output.append(self.track_groups_access.get_iparam_serializer())

        if self.norm_groups_enabled():
            output.append(self.norm_groups_access.get_iparam_serializer())

        if self.island_tdensity_before_pack_enabled():
            output.append(VColorIParamSerializer(TexelDensityPackingIParamInfo()))

        return output
    
    def supports_pack_to_tiles(self):
        return False
    
    def supports_tile_target(self):
        return False
    
    def supports_tile_filling_method(self):
        return False


class UVPM4_Mode_SingleTile(UVPM4_Mode_Pack):

    MODE_ID = 'pack.single_tile'
    MODE_NAME = 'Single Tile'
    MODE_PRIORITY = 1000
    MODE_HELP_URL_SUFFIX = "30-packing-modes/10-single-tile"

    SCENARIO_ID = 'pack_single_tile'

class UVPM4_Mode_Tiles(UVPM4_Mode_Pack):

    MODE_ID = 'pack.tiles'
    MODE_NAME = 'Tiles'
    MODE_PRIORITY = 2000
    MODE_HELP_URL_SUFFIX = "30-packing-modes/20-tiles"

    SCENARIO_ID = 'pack_tiles'

    def supports_pack_to_tiles(self):
        return True
    
    def supports_tile_target(self):
        return True
    
    def supports_tile_filling_method(self):
        return True
    

class UVPM4_PT_OverrideGlobalOptionsPopover(Panel, PanelUtilsMixin, PresetPanel):

    bl_label = 'Override Global Options'

    @classmethod
    def get_active_mode(cls, context):
        return get_prefs().get_active_pack_mode(context)

    def draw(self, context):
        self.init_draw(context)

        if not self.active_mode:
            return

        gs_access = self.active_mode.grouping_config.get_scheme_access(ui_drawing=True)
        active_group = gs_access.active_group

        if not active_group:
            return
        
        g_features = self.active_mode.grouping_config.group_features
        overrides = active_group.overrides

        ow_layout = self.layout
        ow_col = ow_layout.column(align=True)

        ow_col.label(text='Group - Override Global Options')
        ow_col.separator()
        ow_col.label(text='Packing Options:')

        def draw_prop_override(prop_name, layout_creator=None, prop_drawer=None):
            if layout_creator is None:
                if type(getattr(overrides, prop_name)) == bool:
                    layout_creator = lambda l: l.box()
                else:
                    layout_creator = lambda l: l.column(align=True)

            if prop_drawer is None:
                prop_drawer = lambda l, o, p: l.prop(o, p)

            row = ow_col.row(align=True)
            override_prop_name = 'override_' + prop_name
            row.prop(overrides, override_prop_name, text='')

            prop_layout = layout_creator(row)
            prop_layout2 = prop_drawer(prop_layout, overrides, prop_name)
            prop_layout.enabled = getattr(overrides, override_prop_name)
            return prop_layout, prop_layout2

        draw_prop_override('rotation_enable')
        draw_prop_override('pre_rotation_disable')
        draw_prop_override('rotation_step',
                           layout_creator=lambda l: l.box(),
                           prop_drawer=lambda l, o, p: self.draw_prop_with_set_menu(o, p, l, UVPM4_MT_SetRotStepGroup))

        draw_prop_override('scale_mode', prop_drawer=lambda l, o, p: self.draw_enum_in_box(o, p, l))

        ow_col.separator()
        ow_col.label(text='Pixel Margin:')
        pixel_margin_override_enabled = hasattr(self.active_mode, 'group_pixel_margin_override_enabled') and self.active_mode.group_pixel_margin_override_enabled()
        if pixel_margin_override_enabled:
            draw_prop_override('pixel_margin')
            draw_prop_override('pixel_border_margin')
            draw_prop_override('extra_pixel_margin_to_others')

            draw_prop_override('pixel_margin_tex_size',
                               prop_drawer=lambda l, o, p: self.draw_prop_with_set_menu(o, p, l, UVPM4_MT_SetPixelMarginTexSizeGroup))
            
        else:
            row = ow_col.box()
            row.label(text='Enable Pixel Margin globally')
            row.label(text='to enable overriding')

        ow_col.separator()
        ow_col.label(text='Texel Density:')
        tdensity_override_enabled = hasattr(self.active_mode, 'group_texel_density_override_enabled') and self.active_mode.group_texel_density_override_enabled()
        if tdensity_override_enabled:
            draw_prop_override('tdensity_packing', prop_drawer=lambda l, o, p: getattr(o, p).draw(l))
            
        else:
            from ...spipeline.engine.labels import Labels
            row = ow_col.box()
            row.label(text="Enable '{}'".format(Labels.TEXEL_DENSITY_SET_BEFORE_PACK_NAME))
            row.label(text='to enable overriding')

        ow_col.separator()
        ow_col.label(text='Other Options:')

        if g_features & GroupFeatures.GROUPS_TOGETHER:
            draw_prop_override('groups_together')
            draw_prop_override('grouping_compactness', layout_creator=lambda l: l.box())

        if g_features & GroupFeatures.PACK_TO_SINGLE_BOX:
            draw_prop_override('pack_to_single_box')

        draw_prop_override('pack_strategy', prop_drawer=lambda l, o, p: getattr(o, p).draw(l))


class GroupOverridesModeMixin:

    def draw_group_options(self, g_scheme, group, layout):
        props_count = 0

        overrides = group.overrides
        box = layout.box()
        row = box.row(align=True)
        row.prop(overrides, "override_global_options")
        props_count += 1
        
        if overrides.override_global_options:
            row.popover(panel=UVPM4_PT_OverrideGlobalOptionsPopover.__name__, text='', icon='SETTINGS')

        return props_count

    def group_pixel_margin_override_enabled(self):
        return self.main_props.pixel_margin_enabled()
    
    def group_texel_density_override_enabled(self):
        return self.tdensity_before_pack_enabled()


class UVPM4_Mode_GroupsToTiles(UVPM4_Mode_Pack, GroupOverridesModeMixin):

    MODE_ID = 'pack.groups_to_tiles'
    MODE_NAME = 'Groups To Tiles'
    MODE_PRIORITY = 3000
    MODE_HELP_URL_SUFFIX = "30-packing-modes/30-groups-to-tiles"
    TEXEL_DENSITY_POLICY_URL_SUFFIX = MODE_HELP_URL_SUFFIX + '#texel-density-policy'
    GROUP_LAYOUT_MODE_URL_SUFFIX = MODE_HELP_URL_SUFFIX + '#group-layout-mode'

    SCENARIO_ID = 'pack_groups_to_tiles'

    def get_grouping_config(self):
        config = super().get_grouping_config()
        config.grouping_enabled = True
        config.target_box_editing = config.active_g_scheme_target_box_editing()

        config.group_features |= GroupFeatures.PACK_TO_SINGLE_BOX
        config.group_features |= GroupFeatures.GROUPS_TOGETHER

        return config
    
    def target_boxes_not_editable_msg(self, group):
        return self.grouping_config.get_scheme_access(ui_drawing=True).get_active_g_scheme_safe().groups_to_tiles_target_boxes_not_editable_msg(group)
    
    def validate_operation(self):
        super().validate_operation()

        self.g_scheme.validate_groups_to_tiles(self.pack_op_type)

    def draw_grouping_options(self, g_scheme, g_options, layout):
        col = layout
        PanelUtilsMixin.draw_enum_in_box(g_options, 'tdensity_policy', col, self.TEXEL_DENSITY_POLICY_URL_SUFFIX)

        if not g_options.AUTOMATIC:
            box = col.box()
            PanelUtilsMixin.handle_prop(g_options.base,
                                         'last_group_complementary',
                                         box,
                                         warning_msg=g_scheme.complementary_group_validate_fail_msg())

        mode_layout = PanelUtilsMixin.draw_enum_in_box(g_options, 'group_layout_mode', col, self.GROUP_LAYOUT_MODE_URL_SUFFIX)

        if g_options.group_layout_mode == GroupLayoutMode.TEXTURE_ATLAS:
            row = mode_layout.row(align=True)
            row.prop(g_options.base, "atlas_size_x")

            row = mode_layout.row(align=True)
            row.prop(g_options.base, "atlas_size_y")

        if g_options.supports_tile_count_per_group():
            row = mode_layout.row(align=True)
            row.prop(g_options, "tile_count_per_group")

        if GroupLayoutMode.supports_tiles_in_row(g_options.group_layout_mode):
            row = mode_layout.row(align=True)
            row.prop(g_options.base, "tiles_in_row")

        if GroupLayoutMode.supports_tile_count_xy(g_options.group_layout_mode):
            row = mode_layout.row(align=True)
            row.prop(g_options.base, "tile_count_x")

            row = mode_layout.row(align=True)
            row.prop(g_options.base, "tile_count_y")

        PanelUtilsMixin.handle_prop(g_options.base, "dynamic_tiles_all", col.box(), warning_msg=g_options.dynamic_tiles_all_validate_fail_msg())

        box = col.box()
        row = box.row(align=True)
        row.prop(g_options.base, "groups_together")

        if g_options.base.groups_together:
            row = box.row(align=True)
            row.prop(g_options.base, "grouping_compactness")

        box = col.box()
        row = box.row(align=True)
        row.prop(g_options.base, "pack_to_single_box")

    def draw_group_options(self, g_scheme, group, layout):
        props_count = 0

        if in_debug_mode():
            row = layout.row(align=True)
            row.enabled = False
            row.prop(group, "num")
            props_count += 1

        if g_scheme.options.tdensity_policy == TexelDensityGroupPolicy.CUSTOM:
            row = layout.row(align=True)
            row.enabled = g_scheme.options.tdensity_policy == TexelDensityGroupPolicy.CUSTOM
            row.prop(group, "tdensity_cluster")
            props_count += 1

        if g_scheme.supports_dynamic_tiles_prop(group):
            PanelUtilsMixin.handle_prop(group, 'dynamic_tiles', layout.box(), warning_msg=g_scheme.dynamic_tiles_validate_fail_msg(group))

        if g_scheme.supports_tile_count_prop(group):
            row = layout.row(align=True)
            row.prop(group, "tile_count")
            props_count += 1

        props_count += super().draw_group_options(g_scheme, group, layout)
        return props_count

    def supports_custom_target_box(self):
        return False
    
    def supports_pack_to_tiles(self):
        return True
    
    def supports_tile_filling_method(self):
        return True


class UVPM4_Mode_GroupsTogether(UVPM4_Mode_Tiles):

    MODE_ID = 'pack.groups_together'
    MODE_NAME = 'Groups Together'
    MODE_PRIORITY = 4000
    MODE_HELP_URL_SUFFIX = "30-packing-modes/40-groups-together"

    SCENARIO_ID = 'pack_groups_together'

    def get_grouping_config(self):
        config = super().get_grouping_config()
        config.grouping_enabled = True
        return config

    def draw_grouping_options(self, g_scheme, g_options, layout):

        col = layout
        row = col.row(align=True)
        row.prop(g_options.base, "grouping_compactness")

    def supports_tile_filling_method(self):
        return False


class UVPM4_Mode_GroupsIndependently(UVPM4_Mode_Tiles, GroupOverridesModeMixin):

    MODE_ID = 'pack.groups_independently'
    MODE_NAME = 'Groups Independently'
    MODE_PRIORITY = 5000
    MODE_HELP_URL_SUFFIX = "30-packing-modes/50-groups-independently"

    SCENARIO_ID = 'pack_groups_independently'

    def get_grouping_config(self):
        config = super().get_grouping_config()
        config.grouping_enabled = True
        return config
