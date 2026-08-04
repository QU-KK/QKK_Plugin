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

""" Zen Unwrap Operator """

import bpy

from ZenUV.utils.generic import fit_uv_view

from ZenUV.ui.labels import ZuvLabels
from ZenUV.utils.hops_integration import show_uv_in_3dview
from .ui import ZENUNWRAP_PT_Properties
from .utils import (
    uObject,
    UIslandsManager
)
from .props import ZenUnwrapState, LiveUnwrapPropManager, ZenUnwrapProps
from ZenUV.utils.vlog import Log
from ZenUV.utils.global_report import ZuvReporter
from ZenUV.utils.generic import resort_by_type_mesh_in_edit_mode_and_sel
from ZenUV.utils.blender_zen_utils import ZenPolls


CAT = "ZenUnwrap"


class ZUV_OT_ZenUnwrap(bpy.types.Operator, ZuvReporter):
    """ Zen Unwrap Operator """
    bl_idname = "uv.zenuv_unwrap"
    bl_label = ZuvLabels.ZEN_UNWRAP_LABEL
    bl_description = ZuvLabels.ZEN_UNWRAP_DESC
    bl_options = {'REGISTER', 'UNDO'}

    action: bpy.props.EnumProperty(
        items=[
            ("DEFAULT", "Zen Unwrap", "Default Zen Unwrap Mode."),
            ("AUTO", "Auto Seams Mode", "Perform Auto Seams Before Zen Unwrap."),
            ("CONTINUE", "Continue Mode", "Perform Unwrap with no respect to warnings."),
            ("LIVE_UWRP", "Live Unwrap Mode", "Perform Unwrap in No Selection Mode")
            ],
        default="DEFAULT",
        options={'HIDDEN'}
    )

    UnwrapMethod: bpy.props.EnumProperty(
        name="Unwrap Method",
        items=ZenUnwrapProps.UNWRAP_METHOD_ITEMS,
        default=ZenPolls.get_operator_defaults("UV_OT_zenuv_unwrap", "UnwrapMethod", "CONFORMAL")
        )

    MarkUnwrapped: bpy.props.BoolProperty(
        name=ZuvLabels.PREF_AUTO_SEAMS_WITH_UNWRAP_LABEL,
        description=ZuvLabels.PREF_AUTO_SEAMS_WITH_UNWRAP_DESC,
        default=ZenPolls.get_operator_defaults("UV_OT_zenuv_unwrap", "MarkUnwrapped", True))

    ProcessingMode: bpy.props.EnumProperty(
        name='Processing Mode',
        items=[
            ("SEL_ONLY", "Selected Only", "Processing selection only."),
            ("WHOLE_MESH", "Whole Mesh", "Processing whole mesh."),
            ("SEAM_SWITCH", "Seam Switch", "Switch Seam Mode"),
            ("URP_VERTICES", "Unfold Vertices", "Processing Selected vertices only")],
        default=ZenPolls.get_operator_defaults("UV_OT_zenuv_unwrap", "ProcessingMode", "WHOLE_MESH"),
    )

    packAfUnwrap: bpy.props.BoolProperty(
        name=ZuvLabels.PREF_PACK_AF_UNWRAP_LABEL,
        description=ZuvLabels.PREF_PACK_AF_UNWRAP_DESC,
        default=ZenPolls.get_operator_defaults("UV_OT_zenuv_unwrap", "packAfUnwrap", True))

    post_td_mode: bpy.props.EnumProperty(
        name="Texel Density",
        description="Set texel density. Not available in the Seam Switch mode or if Pack Unwrapped is On",
        items=[
            ("AVERAGED", "Averaged", "Set averaged Texel Density"),
            ("GLOBAL_PRESET", "Global Preset", "Set value described in the Texel Density panel as Global TD Preset"),
            ("SKIP", "Skip", "Do not make any texel density corrections")],
        default=ZenPolls.get_operator_defaults("UV_OT_zenuv_unwrap", "post_td_mode", "AVERAGED"),
    )

    fill_holes: bpy.props.BoolProperty(
        name=ZuvLabels.PREF_ZEN_UNWRAP_FILL_HOLES_LABEL,
        description=ZuvLabels.PREF_ZEN_UNWRAP_FILL_HOLES_DESC,
        default=ZenPolls.get_operator_defaults("UV_OT_zenuv_unwrap", "fill_holes", True))

    correct_aspect: bpy.props.BoolProperty(
        name=ZuvLabels.PREF_ZEN_UNWRAP_CORR_ASPECT_LABEL,
        description=ZuvLabels.PREF_ZEN_UNWRAP_CORR_ASPECT_DESC,
        default=ZenPolls.get_operator_defaults("UV_OT_zenuv_unwrap", "correct_aspect", True))

    def get_markSeamEdges(self):
        from ZenUV.prop.zuv_preferences import get_prefs
        addon_prefs = get_prefs()
        b_default = ZenPolls.get_operator_defaults("UV_OT_zenuv_unwrap", "markSeamEdges", True)
        return addon_prefs.markSeamEdges if addon_prefs.useGlobalMarkSettings else self.get('markSeamEdges', b_default)

    def set_markSeamEdges(self, value):
        from ZenUV.prop.zuv_preferences import get_prefs
        addon_prefs = get_prefs()
        if addon_prefs.useGlobalMarkSettings:
            addon_prefs.markSeamEdges = value
        else:
            self['markSeamEdges'] = value

    markSeamEdges: bpy.props.BoolProperty(
        name="Mark Seams",
        description="Automatically assign Seams",
        get=get_markSeamEdges,
        set=set_markSeamEdges)

    def get_markSharpEdges(self):
        from ZenUV.prop.zuv_preferences import get_prefs
        addon_prefs = get_prefs()
        b_default = ZenPolls.get_operator_defaults("UV_OT_zenuv_unwrap", "markSharpEdges", False)
        return addon_prefs.markSharpEdges if addon_prefs.useGlobalMarkSettings else self.get('markSharpEdges', b_default)

    def set_markSharpEdges(self, value):
        from ZenUV.prop.zuv_preferences import get_prefs
        addon_prefs = get_prefs()
        if addon_prefs.useGlobalMarkSettings:
            addon_prefs.markSharpEdges = value
        else:
            self['markSharpEdges'] = value

    markSharpEdges: bpy.props.BoolProperty(
        name="Mark Sharp Edges",
        description="Automatically assign Sharp edges",
        get=get_markSharpEdges,
        set=set_markSharpEdges)

    def get_unwrapAutoSorting(self):
        from ZenUV.prop.zuv_preferences import get_prefs
        addon_prefs = get_prefs()
        return addon_prefs.op_zen_unwrap_props.unwrapAutoSorting

    def set_unwrapAutoSorting(self, value):
        from ZenUV.prop.zuv_preferences import get_prefs
        addon_prefs = get_prefs()
        addon_prefs.op_zen_unwrap_props.unwrapAutoSorting = value

    unwrapAutoSorting: bpy.props.BoolProperty(
        name=ZuvLabels.PREF_ZEN_UNWRAP_SORT_ISLANDS_LABEL,
        description=ZuvLabels.PREF_ZEN_UNWRAP_SORT_ISLANDS_DESC,
        get=get_unwrapAutoSorting,
        set=set_unwrapAutoSorting,
        options={'SKIP_SAVE'})

    def _is_avg_td_allowed(self):
        if self.ProcessingMode == "SEL_ONLY":
            return True
        return not self.ProcessingMode == "SEAM_SWITCH" and not self.packAfUnwrap

    def draw(self, context: bpy.types.Context):
        layout = self.layout
        from ZenUV.prop.zuv_preferences import get_prefs
        addon_prefs = get_prefs()
        # switch_seam_mode = self.ProcessingMode == "SEAM_SWITCH"
        if context.tool_settings.mesh_select_mode[:] == (False, True, False):
            s_mode = "Edge"
            ico = 'EDGESEL'
        elif context.tool_settings.mesh_select_mode[:] == (False, False, True):
            s_mode = "Face"
            ico = 'FACESEL'
        else:
            s_mode = "Vertex"
            ico = 'VERTEXSEL'

        box = layout.box()
        row = box.row()
        row.split(factor=0.7, align=False)
        row.label(text="Select Mode: ")
        row.label(text=s_mode, icon=ico)

        row = box.row()
        # row.enabled = not switch_seam_mode
        row.split(factor=0.7, align=False)
        row.label(text="Processing Mode: ")
        row.prop(self, "ProcessingMode", text="")

        row = box.row()
        row.split(factor=0.7, align=False)
        row.label(text=ZuvLabels.PANEL_UNWRAP_METHOD_LABEL)
        row.prop(self, 'UnwrapMethod', text='')

        box = layout.box()
        box.enabled = not self.ProcessingMode == "URP_VERTICES"

        mark_box = box.box()
        self.draw_mark_section(mark_box, addon_prefs)

        box.prop(self, "fill_holes")

        row = box.row(align=True)
        row.enabled = self._is_avg_td_allowed()
        row.prop(self, "post_td_mode")

        row = box.row()
        from ZenUV.utils.blender_zen_utils import ZenPolls
        row.enabled = not ZenPolls.version_equal_3_6_0 and not self.ProcessingMode == 'SEL_ONLY'
        row.prop(self, "packAfUnwrap")
        if ZenPolls.version_equal_3_6_0:
            row.label(text='Disabled in 3.6.0')

        box.prop(self, 'unwrapAutoSorting')

    def draw_mark_section(self, layout, addon_prefs):
        s_mark_settings = 'Mark Settings'
        s_mark_settings += ' (Global Mode)' if addon_prefs.useGlobalMarkSettings else ' (Local Mode)'
        layout.label(text=s_mark_settings)

        row = layout.row(align=True)
        row.prop(self, "MarkUnwrapped", text='Mark')
        sub_row = row.row(align=True)
        sub_row.enabled = self.MarkUnwrapped
        if not addon_prefs.useGlobalMarkSettings:
            sub_row.prop(self, "mark_seams")
            sub_row.prop(self, "mark_sharp")
        else:
            sub_row.enabled = False
            sub_row.prop(addon_prefs, "markSeamEdges")
            sub_row.prop(addon_prefs, "markSharpEdges")

    @classmethod
    def poll(cls, context):
        """ Validate context """
        is_active_object = context.active_object is not None and context.active_object.type == 'MESH'
        is_sync_mode = context.area.type == "VIEW_3D" or context.area.type == "IMAGE_EDITOR" and context.scene.tool_settings.use_uv_select_sync
        return is_active_object and context.mode == 'EDIT_MESH' and is_sync_mode and context.active_object.visible_get()

    def execute(self, context):
        from .props import ZenUnwrapProps
        self.report_clear()
        Log.debug_header(" Zen Unwrap Processing ")
        objs = resort_by_type_mesh_in_edit_mode_and_sel(context)
        objs = [uObject(context, obj) for obj in objs]
        objs = [o for o in objs if o.l_all_faces]

        if not objs:
            self.report({'WARNING'}, "Zen UV: There are no selected objects.")
            return {'CANCELLED'}

        STATE = ZenUnwrapState(context, objs, self)
        STATE.set_operator_mode(self.action)
        STATE.mSeam = self.markSeamEdges
        STATE.mSharp = self.markSharpEdges
        PROPS: ZenUnwrapProps = STATE.PROPS

        # PROPS.Mark = self.MarkUnwrapped
        # PROPS.ProcessingMode = self.ProcessingMode
        # PROPS.Pack = self.packAfUnwrap
        # PROPS.TdMode = self.post_td_mode
        # PROPS.fill_holes = self.fill_holes
        # PROPS.correct_aspect = self.correct_aspect

        # STATE.objs_count = len(objs)

        if PROPS.ActivateSyncUV:
            context.scene.tool_settings.use_uv_select_sync = True
            STATE.update_sync_mode(context)

        # # In the EDGE Selection mode Mark will do anyway.
        # if STATE.bl_selection_mode == "EDGE":
        #     # context.scene.zen_uv.op_zen_unwrap_sc_props.MarkUnwrapped = True
        #     # PROPS.Mark = True
        #     pass
        # STATE.bl_selection_mode == "VERTEX" and
        if PROPS.ProcessingMode == 'URP_VERTICES':
            self.unwrap_selected_vertices(context, objs, STATE)
            return {'FINISHED'}

        if self.action == "LIVE_UWRP":
            # LiveUnwrapPropManager.show_args()
            LiveUnwrapPropManager.store_props(STATE)
            LiveUnwrapPropManager.set_live_unwrap_preset(STATE)
        else:
            context.scene.tool_settings.use_edge_path_live_unwrap = False

        # Detect Operator Processing Mode
        if STATE.OPM == "ALL" and PROPS.ProcessingMode == 'SEL_ONLY' and not STATE.b_is_selection_exist:
            # NOTE: we do not change to 'WHOLE_MESH' on this stage,
            # it will be decided later in called popup operator
            bpy.ops.wm.call_menu(name="ZUV_MT_ZenUnwrap_ConfirmPopup")
            return {'CANCELLED'}

        # Filtering objects without selection
        if STATE.OPM == 'SELECTION' and PROPS.ProcessingMode == 'SEL_ONLY':  # not STATE.is_pack_allowed():
            objs = [obj for obj in objs if obj.b_is_selection_exist]
            STATE.objs_count = len(objs)
        else:
            pass

        # Full Automatic Unwrap Mode. First Perform Auto Seams
        if STATE.operator_mode == "AUTO":
            bpy.ops.uv.zenuv_auto_mark("INVOKE_DEFAULT")
            STATE.update_seams_exist(objs)
            STATE.skip_warning = True

        if STATE.operator_mode == "CONTINUE":
            STATE.skip_warning = True

        if STATE.is_all_ready_to_unwrap(objs) is False and STATE.skip_warning is False:
            bpy.ops.wm.call_menu(name="ZUV_MT_ZenUnwrap_Popup")
            STATE.skip_warning = True
            return {'CANCELLED'}

        # Unwrapping Phase
        result = self._unwrap(context, objs, STATE)
        if result == {'CANCELLED'}:
            return result

        # Pack Phase
        if STATE.is_pack_allowed():
            kp_st = PROPS.KeepStacks
            PROPS.KeepStacks = '0'
            bpy.ops.uv.zenuv_pack('INVOKE_DEFAULT', display_uv=False, disable_overlay=True, fast_mode=True)
            PROPS.KeepStacks = kp_st

        # Sortig Phase
        if STATE.is_sorting_allowed():
            for uobj in objs:
                uobj.sorting_finished(context)

        # Restore Initial Selection if works in Selection Mode
        self.restore_init_selection(objs, STATE, PROPS)

        fit_uv_view(context, mode=STATE.fit_view)

        # Display UV Widget from HOPS addon
        if PROPS.ProcessingMode == 'SEL_ONLY':
            show_uv_in_3dview(context, use_selected_meshes=True, use_selected_faces=False, use_tagged_faces=True)
        else:
            show_uv_in_3dview(context, use_selected_meshes=True, use_selected_faces=False, use_tagged_faces=False)

        # Reset self values to default
        self.reset_values(context, STATE)

        if STATE.finished_came_across:
            s_message = "Zen UV: Finised Islands is came across. They were not unwrapped."
            self.report_ex({'WARNING'}, s_message)

        return {'FINISHED'}

    def restore_init_selection(self, objs, STATE: ZenUnwrapState, PROPS):
        if STATE.b_is_selection_exist:
            for uobj in objs:
                uobj.restore_selection(STATE.bl_selection_mode)

            if len(objs) == 1:
                STATE.fit_view = "selected"
            else:
                STATE.fit_view = "all"

        else:
            bpy.ops.mesh.select_all(action='DESELECT')
            if PROPS.SortFinished:
                STATE.fit_view = "checker"
            else:
                STATE.fit_view = "all"

    def unwrap_selected_vertices(self, context, objs, STATE: ZenUnwrapState):
        from .props import ZenUnwrapProps
        PROPS: ZenUnwrapProps = STATE.PROPS

        uobj: uObject = None

        for uobj in objs:
            obj = uobj.obj
            Log.debug_header_short(f" Processed Object --> {obj.name} ")

            uobj.bm.edges.ensure_lookup_table()

            IM = UIslandsManager(uobj, STATE)

            uobj.l_seam_state = [e.seam for e in uobj.bm.edges]
            result = IM.set_seams_in_vertex_processing_mode(context, uobj)
            if not result:
                pass
            uobj.collect_init_pins()
            uobj.pin_all_but_not_sel()

        bpy.ops.mesh.select_all(action='SELECT')
        IM._unwrap(context)

        for uobj in objs:
            uobj.restore_pins()
            uobj.restore_seams()

        bpy.ops.mesh.select_all(action='DESELECT')

        self.restore_init_selection(objs, STATE, PROPS)

    def reset_values(self, context, STATE: ZenUnwrapState):
        from .props import ZenUnwrapProps
        if self.action == "LIVE_UWRP":
            LiveUnwrapPropManager.restore_props(STATE)

        STATE.set_operator_mode("DEFAULT")
        STATE.one_by_one = False

        PROPS: ZenUnwrapProps = STATE.PROPS
        PROPS.Mark = True
        context.scene.tool_settings.use_edge_path_live_unwrap = STATE.bl_live_unwrap
        self.action = 'DEFAULT'

    def _unwrap(self, context, objs, STATE: ZenUnwrapState):
        from .props import ZenUnwrapProps
        from ZenUV.utils.mark_utils import MarkFactory
        PROPS: ZenUnwrapProps = STATE.PROPS

        uobj: uObject = None

        for uobj in objs:
            obj = uobj.obj
            Log.debug_header_short(f" Processed Object --> {obj.name} ")

            bm = uobj.bm

            if uobj.b_is_pack_excluded:
                uobj.hide_pack_excluded()

            # Clear Finished and Vcolor
            uobj.clear_finished_and_vcolor(bm)
            uobj.collect_loops()
            uobj.collect_init_pins()

            if PROPS.ProcessingMode == "SEAM_SWITCH" or STATE.OPM == "SELECTION" and PROPS.Mark and not STATE.bl_selection_mode == 'VERTEX':
                if STATE.is_mark_allowed():

                    mark_seam = True if PROPS.ProcessingMode == "SEAM_SWITCH" else STATE.mSeam

                    MarkFactory.initialize()

                    uobj.restore_face_selection()
                    p_mark_obj = MarkFactory.create_mark_state_object_from_bm(obj, bm)

                    if p_mark_obj is not None:
                        MarkFactory.mark_edges(
                            mark_objects=[p_mark_obj, ],
                            b_set_seam=mark_seam,
                            b_set_sharp=STATE.mSharp,
                            is_silent_mode=False,
                            is_switch=PROPS.ProcessingMode == "SEAM_SWITCH")
                    else:
                        Log.error(CAT, "Selection is not marked.")

                    if MarkFactory.message != '':
                        uobj.b_is_closed_mesh = True
                        if STATE.objs_init_count == 1:
                            bpy.ops.wm.call_menu(name="ZUV_MT_ZenMark_Popup")
                            return {'CANCELLED'}

            IM = UIslandsManager(uobj, STATE)

            bm.faces.ensure_lookup_table()

            if STATE.bl_selection_mode == 'EDGE' and not PROPS.ProcessingMode == "SEAM_SWITCH" and not STATE.operator_mode == "LIVE_UWRP":
                bpy.ops.mesh.mark_seam(clear=False)

            IM.create_islands(context)

            IM.z_unuwrap(context)

            uobj.restore_pins()

            if STATE.bl_selection_mode == 'EDGE' and not STATE.is_mark_allowed():
                if not PROPS.ProcessingMode == "SEAM_SWITCH":
                    if not STATE.operator_mode == "LIVE_UWRP":
                        uobj.clear_temp_seams()

            bpy.ops.mesh.select_all(action='DESELECT')

            IM.set_averaged_td(context, uobj)
            IM.set_islands_positions(offset=True)

            if uobj.b_is_pack_excluded:
                uobj.unhide_pack_excluded()

            # bpy.ops.object.mode_set(mode='OBJECT')
            # obj.select_set(state=False)

        # self.finish_objs_processing(objs, view_layer, active_obj)

        return {'FINISHED'}

    def finish_objs_processing(self, objs, view_layer, active_obj):
        for obj in objs:
            obj.select_set(state=True)

        view_layer.objects.active = active_obj
        bpy.ops.object.mode_set(mode='EDIT')


class ZUV_OT_ProxyUnwrapAllSelected(bpy.types.Operator):
    bl_idname = "uv.zenuv_proxy_zenunwrap_all_selected"
    bl_label = 'Proxy Zen Unwrap'
    bl_description = 'Used for Unwrap in case all faces selected in close object'
    bl_options = {'REGISTER', 'UNDO'}

    action: bpy.props.EnumProperty(
        items=[
            ("DEFAULT", "Zen Unwrap", "Default Zen Unwrap Mode."),
            ("AUTO", "Auto Seams Mode", "Perform Auto Seams Before Zen Unwrap."),
            ("CONTINUE", "Continue Mode", "Perform Unwrap with no respect to warnings."),
            ("LIVE_UWRP", "Live Unwrap Mode", "Perform Unwrap in No Selection Mode")
            ],
        default="DEFAULT",
        options={'HIDDEN'}
    )

    @classmethod
    def poll(cls, context):
        """ Validate context """
        active_object = context.active_object
        return active_object is not None and active_object.type == 'MESH' and context.mode == 'EDIT_MESH'

    def execute(self, context):

        from ZenUV.utils.selection_utils import SelectionProcessor
        from ZenUV.utils.generic import bpy_deselect_by_context

        b_is_not_sync = context.space_data.type == 'IMAGE_EDITOR' and not context.scene.tool_settings.use_uv_select_sync

        p_act_objs = SelectionProcessor.collect_selected_objects(context, b_is_not_sync)
        if not p_act_objs:
            print('No selected objects')
            return {'CANCELLED'}

        bpy_deselect_by_context(context)

        if bpy.ops.uv.zenuv_unwrap.poll():
            if self.action == 'DEFAULT':
                # NOTE: if we came here, user pressed 'OK' when nothing was selected
                wm = context.window_manager
                op_props = wm.operator_properties_last("uv.zenuv_unwrap")
                if op_props:
                    op_props.ProcessingMode = 'WHOLE_MESH'

            bpy.ops.uv.zenuv_unwrap(action=self.action, ProcessingMode='WHOLE_MESH')

        SelectionProcessor.restore_selection_in_objects(context, p_act_objs, b_is_not_sync)

        return {'FINISHED'}


ZenUnwrapClasses = [
    ZUV_OT_ZenUnwrap,
    ZENUNWRAP_PT_Properties,
    ZUV_OT_ProxyUnwrapAllSelected
]

if __name__ == '__main__':
    pass
