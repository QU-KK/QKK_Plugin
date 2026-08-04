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

from . import module_loader
module_loader.unload_uvpm4_modules(locals())

bl_info = {
    "name": "UVPackmaster4",
    "author": "glukoz",
    "version": (4, 0, 0),
    "blender": (5, 0, 0),
    "location": "UV Editor -> N panel -> UVPackmaster4",
    "description": "",
    "warning": "",
    "doc_url": "https://uvpackmaster.com/doc4/blender/latest/",
    "tracker_url": "",
    "category": "UV"}

from .app_iface import *

if INSIDE_APP:
    from .operator import *
    from .operator_islands import *
    from .operator_box import *
    from .operator_misc import *
    from .panel import *
    from .prefs import *
    from .register_utils import *
    from .presets import *
    from .presets_grouping_scheme import *
    from .mode import *
    from .grouping import *
    from .group import *
    from .grouping_scheme import *
    from .grouping_scheme_ui import *
    from .multi_panel import *
    from .multi_panel_manager import *
    from .help import *
    from .scripting import *
    from .debug import *
    from .multi_select import *
    from .spipeline.modes.pack_modes import UVPM4_PT_OverrideGlobalOptionsPopover

    from .id_collection.main_props import *
    from .id_collection.ui import *
    from .id_collection import *

    from .repack.panel import *
    from .repack.operator import *
    from .repack.props import *
    from .repack.cluster import *
    from .tdensity.operator import *
    from .tdensity.props import *
    from .tdensity.tier import *

    from .spipeline import operators
    
    scripted_operators_modules = module_loader.import_submodules(operators)
    scripted_operators_classes = module_loader.get_registrable_classes(scripted_operators_modules, sub_class=UVPM4_OT_Generic)

    from .spipeline import modes
    scripted_modes_modules = module_loader.import_submodules(modes)
    scripted_modes_classes = module_loader.get_registrable_classes(scripted_modes_modules,
                                                                   sub_class=UVPM4_Mode_Generic, required_vars=("MODE_ID",))
    scripted_modes_classes.sort(key=lambda x: x.MODE_PRIORITY)


    classes = (
        UVPM4_UL_GroupInfo,
        UVPM4_UL_TargetBoxes,
        UVPM4_MT_BrowseGroupingSchemes,
        UVPM4_OT_BrowseGroupingSchemes,

        UVPM4_IdCollectionAccessDescriptor,

        UVPM4_TileTargetProps,
        UVPM4_SimilarityProps,
        UVPM4_OrientTo3dProps,
        UVPM4_PackStrategyProps,
        UVPM4_TDensityValue,
        UVPM4_TDensityTierValue,
        UVPM4_TDensityValueToSet,
        UVPM4_TDensityValuePacking,

        UVPM4_Box,
        UVPM4_GroupOverrides,
        UVPM4_GroupInfo,
        UVPM4_GroupingOptionsBase,
        UVPM4_GroupingOptions,
        UVPM4_AutoGroupingOptions,
        UVPM4_GroupingScheme,

        UVPM4_GroupingSchemeAccessDescriptor,
        UVPM4_GroupingSchemeAccessDescriptorContainer,

        UVPM4_NumberedGroupsDescriptor,
        UVPM4_NumberedGroupsDescriptorContainer,

        UVPM4_TrackGroupsProps,

        UVPM4_MultiPanelAddonSettings,
        UVPM4_SavedMultiPanelAddonSettings,

        UVPM4_DeviceSettings,
        UVPM4_SavedDeviceSettings,
        UVPM4_DismissableMessages,
        UVPM4_Preferences,

        UVPM4_OT_Debug,
        UVPM4_OT_DismissMessage,

        UVPM4_MT_BrowsePackModes,
        UVPM4_OT_SelectPackMode,

        UVPM4_OT_ShowHideAdvancedOptions,
        UVPM4_OT_SetEnginePath,
        UVPM4_OT_AdjustIslandsToTexture,
        UVPM4_OT_UndoIslandsAdjustmentToTexture,

        UVPM4_OT_Help,
        UVPM4_OT_PackModeHelp,
        UVPM4_OT_SetupHelp,

        UVPM4_OT_HelpPopup,
        UVPM4_OT_WarningPopup,

        UVPM4_OT_StdShowIParam,
        UVPM4_OT_StdSetIParam,
        UVPM4_OT_StdResetIParam,
        UVPM4_OT_StdSelectIParam,

        UVPM4_OT_ShowManualGroupIParam,
        UVPM4_OT_SetManualGroupIParam,
        UVPM4_OT_ResetManualGroupIParam,
        UVPM4_OT_SelectManualGroupIParam,
        UVPM4_OT_ApplyGroupingToScheme,

        UVPM4_OT_NumberedGroupShowIParam,
        UVPM4_OT_NumberedGroupSetIParam,
        UVPM4_OT_NumberedGroupSetFreeIParam,
        UVPM4_OT_NumberedGroupResetIParam,
        UVPM4_OT_NumberedGroupSelectIParam,
        UVPM4_OT_NumberedGroupSelectNonDefaultIParam,

        UVPM4_OT_FinishBoxRendering,
        
        UVPM4_OT_RenderGroupingSchemeBoxes,
        UVPM4_OT_SetGroupingSchemeBoxToTile,
        UVPM4_OT_MoveGroupingSchemeBox,

        UVPM4_OT_SelectIslandsInGroupingSchemeBox,
        UVPM4_OT_SelectIslandsInCustomTargetBox,

        UVPM4_OT_RenderCustomTargetBox,
        UVPM4_OT_SetCustomTargetBoxToTile,
        UVPM4_OT_MoveCustomTargetBox,

        UVPM4_OT_RenderTargetTiles,

        UVPM4_PT_Presets,
        UVPM4_PT_PresetsCustomTargetBox,
        UVPM4_PT_PresetsGroupingSchemePack,
        UVPM4_PT_PresetsGroupingSchemeEditor,
        UVPM4_OT_SavePreset,
        UVPM4_OT_SaveGroupingSchemePreset,
        UVPM4_OT_RemovePreset,
        UVPM4_OT_LoadPreset,
        UVPM4_OT_LoadTargetBox,
        UVPM4_OT_LoadGroupingSchemePreset,
        UVPM4_OT_ResetToDefaults,

        UVPM4_PT_OverrideGlobalOptionsPopover,

        UVPM4_OT_NewGroupingScheme,
        UVPM4_OT_RemoveGroupingScheme,
        UVPM4_OT_NewGroupInfo,
        UVPM4_OT_RemoveGroupInfo,
        UVPM4_OT_MoveGroupInfo,
        UVPM4_OT_NewTargetBox,
        UVPM4_OT_RemoveTargetBox,
        UVPM4_OT_MoveTargetBox,

        UVPM4_OT_SetRotStepScene,
        UVPM4_MT_SetRotStepScene,
        UVPM4_OT_SetRotStepGroup,
        UVPM4_MT_SetRotStepGroup,

        UVPM4_OT_SetPixelMarginTexSizeScene,
        UVPM4_MT_SetPixelMarginTexSizeScene,
        UVPM4_OT_SetPixelMarginTexSizeGroup,
        UVPM4_MT_SetPixelMarginTexSizeGroup,

        UVPM4_ScriptEntry,
        UVPM4_ScriptCollection,
        UVPM4_ScriptContainer,
        UVPM4_Scripting,
        UVPM4_OT_ScriptSet,
        UVPM4_MT_ScriptSet,
        UVPM4_UL_ScriptCollection,

        UVPM4_OT_ScriptAddEntry,
        UVPM4_OT_ScriptRemoveEntry,
        UVPM4_OT_ScriptMoveActiveEntry,
        UVPM4_OT_ScriptAllowExecution,

        UVPM4_OT_ShowTexelDensity,
        UVPM4_OT_SetTexelDensity,
        UVPM4_OT_AdjustTexelDensityToUnselected,

        UVPM4_PT_MultiPanels,
        UVPM4_OT_SelectMultiPanel,
        UVPM4_OT_ExpandPanel,
        UVPM4_OT_EnablePanel,

        UVPM4_MultiPanelSettings,
        UVPM4_SavedMultiPanelSettings,

        UVPM4_PanelSettings,
        UVPM4_SavedPanelSettings,

        UVPM4_SplitOverlapProps,

        UVPM4_OT_IdCollectionNewItem,
        UVPM4_OT_IdCollectionRemoveItem,
        UVPM4_OT_IdCollectionBrowseItems,
        UVPM4_MT_IdCollectionBrowseItems,

        UVPM4_TDensityTier,
        UVPM4_TDensityTierIdCollection,
        UVPM4_SceneTDensityProps,

        UVPM4_MainProps,
        UVPM4_MainPropIdCollection,

        UVPM4_OT_MultiSelectAddEntry,
        UVPM4_OT_MultiSelectRemoveEntry,
        UVPM4_MT_MultiSelectAddEntry,

        UVPM4_NamedHash
    )

    if AppInterface.REGISTER_AUTO_REPACK:
        classes += (
            UVPM4_RepackCluster,
            UVPM4_RepackClusterIdCollection,

            UVPM4_SceneRepackProps,
            UVPM4_PT_ObjectOptions,
            UVPM4_OT_AutoRepack,

            UVPM4_UvMapRepackData,
            UVPM4_ObjectRepackProps,
            UVPM4_ObjectProps,

            UVPM4_MeshProps
        )

    classes += (
        UVPM4_SceneProps,
    )

    classes += MULTI_PANEL_SETTINGS_POPOVERS
    classes += MULTI_PANEL_ALL_PANELS
    classes += ENABLE_CHILD_PANEL_MENUS

    def register():
        AppInterface.register(classes, scripted_operators_classes)
        register_modes(scripted_modes_classes)
        register_specific(AppInterface.ISOLATED_ENGINE_PATH)

    def unregister():
        AppInterface.unregister()
