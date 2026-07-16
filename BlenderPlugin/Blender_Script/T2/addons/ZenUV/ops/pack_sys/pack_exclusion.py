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

""" Zen UV Pack Exclusion System """

import bpy
import bmesh

from ZenUV.utils.transform import move_island
from ZenUV.utils import get_uv_islands as island_util
from ZenUV.utils.generic import (
    fit_uv_view,
    select_by_context,
    set_face_int_tag,
    resort_by_type_mesh_in_edit_mode_and_sel,
    bpy_deselect_by_context,
    verify_uv_layer
)

from ZenUV.prop.zuv_preferences import get_prefs

from ZenUV.utils.generic import ZUV_PANEL_CATEGORY, ZUV_REGION_TYPE, ZUV_SPACE_TYPE
from ZenUV.utils.constants import PACK_EXCLUDED_FACEMAP_NAME, PACK_EXCLUDED_V_MAP_NAME
from ZenUV.utils.blender_zen_utils import prop_with_icon
from ZenUV.utils.register_util import RegisterUtils


class pLogger:
    """ Simple process logger.
        Main purpose is logging processes in the multi object selection mode
    """
    def __init__(self) -> None:
        self.storage = []

    def store(self, value: bool):
        self.storage.append(value)

    def get_result(self):
        return True in self.storage


class ZuvPackExcludedLabels:

    PT_EXCLUDED_LABEL = "Excluded"
    POPUP_PROPS_LABEL = "Pack Excluded Properties"

    OT_OFFSET_EXCLUDED_LABEL = "Offset Excluded"
    OT_OFFSET_EXCLUDED_DESC = "Move Islands tagged as Excluded from Packing out of UV Area"

    PROP_OFFSET_EXCLUDED_LABEL = "Offset"
    PROP_OFFSET_EXCLUDED_DESC = "Offset value"

    OT_TAG_EXCL_LABEL = "Tag Excluded"
    OT_TAG_EXCL_DESC = "Tag Islands as Excluded from Packing"

    OT_UNTAG_EXCL_LABEL = "Untag Excluded"
    OT_UNTAG_EXCL_DESC = "Untag Islands tagged as Excluded from Packing"

    OT_HIDE_EXCL_LABEL = "Hide"
    OT_HIDE_EXCL_DESC = "Hide Islands tagged as Excluded from Packing"

    OT_UNHIDE_EXCL_LABEL = "Unhide"
    OT_UNHIDE_EXCL_DESC = "Unhide Islands tagged as Excluded from Packing"

    OT_DISPLAY_EXCL_LABEL = "Display Excluded"
    OT_DISPLAY_EXCL_DESC = "Display Islands tagged as Excluded from Packing"

    OT_SELECT_EXCL_LABEL = "Select Excluded"
    OT_SELECT_EXCL_DESC = "Select Islands tagged as Excluded from Packing"

    OT_PROP_SELECT_EXCL_LABEL = "Clear"
    OT_PROP_SELECT_EXCL_DESC = 'Clears the initial selection before applying the operation'


class SYSTEM_PT_PackExcluded_UV(bpy.types.Panel):
    bl_space_type = "IMAGE_EDITOR"
    bl_label = ZuvPackExcludedLabels.PT_EXCLUDED_LABEL
    bl_parent_id = "ZUV_PT_UVL_Pack"
    bl_region_type = ZUV_REGION_TYPE
    bl_idname = "SYSTEM_PT_PackExcluded_UV"
    bl_category = ZUV_PANEL_CATEGORY
    bl_options = {'DEFAULT_CLOSED'}

    @classmethod
    def poll(cls, context: bpy.types.Context):
        return context.mode == 'EDIT_MESH'

    @classmethod
    def poll_reason(cls, context: bpy.types.Context):
        if context.mode != 'EDIT_MESH':
            return 'Available in Edit Mesh Mode'
        return ''

    def draw(self, context):
        draw_pack_excluded_section(self, context)


class SYSTEM_PT_PackExcluded(bpy.types.Panel):
    bl_space_type = ZUV_SPACE_TYPE
    bl_label = ZuvPackExcludedLabels.PT_EXCLUDED_LABEL
    bl_parent_id = "ZUV_PT_Pack"
    bl_region_type = ZUV_REGION_TYPE
    bl_idname = "SYSTEM_PT_PackExcluded"
    bl_category = ZUV_PANEL_CATEGORY
    bl_options = {'DEFAULT_CLOSED'}

    @classmethod
    def poll(cls, context: bpy.types.Context):
        return context.mode == 'EDIT_MESH' and get_prefs().packEngine != "UVPACKER"

    @classmethod
    def poll_reason(cls, context: bpy.types.Context):
        if context.mode != 'EDIT_MESH':
            return 'Available in Edit Mesh Mode'
        if get_prefs().packEngine == "UVPACKER":
            return 'Not available for UV-Packer'
        return ''

    def draw(self, context):
        draw_pack_excluded_section(self, context)


class ZUV_PT_pExclude_Properties(bpy.types.Panel):
    """ Internal Popover Zen UV Pack Excluded Section Properties"""
    bl_idname = "ZUV_PT_pExclude_Properties"
    bl_label = ZuvPackExcludedLabels.POPUP_PROPS_LABEL
    bl_context = "__POPUP__"
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_ui_units_x = 14

    def draw(self, context):
        layout = self.layout
        wm = context.window_manager
        prop_with_icon(layout, wm.zen_uv.draw_props, 'draw_auto_update', 'FILE_REFRESH', s_icon_operator_id='wm.zuv_draw_update')
        col = layout.column(align=True)
        col.use_property_split = True
        col.prop(get_prefs(), 'ExcludedColor')


def draw_pack_excluded_section(self, context: bpy.types.Context):
    ''' @Draw Pack Excluded '''
    layout: bpy.types.UILayout = self.layout
    col = layout.column(align=True)

    row = col.row(align=True)
    row.operator(ZUV_OT_OffsetPackExcluded.bl_idname)
    row.popover(panel="ZUV_PT_pExclude_Properties", text="", icon="PREFERENCES")

    row = col.row(align=True)
    row.operator(ZUV_OT_Tag_PackExcluded.bl_idname)
    row.operator(ZUV_OT_UnTag_PackExcluded.bl_idname)

    row = col.row(align=True)
    row.operator(ZUV_OT_Select_PackExcluded.bl_idname, text='Select').action = 'SELECT'
    row.operator(ZUV_OT_Select_PackExcluded.bl_idname, text='Deselect').action = 'DESELECT'

    row = col.row(align=True)
    row.operator(ZUV_OT_Hide_PackExcluded.bl_idname, text='Hide').action = 'HIDE'
    row.operator(ZUV_OT_Hide_PackExcluded.bl_idname, text='Unhide').action = 'UNHIDE'

    from ZenUV.zen_checker.check_utils import draw_checker_display_items, DisplayItem
    draw_checker_display_items(col, context, {'EXCLUDED': DisplayItem({'EDIT_MESH'}, {'UV', '3D'}, '', 'Display Excluded')})


class ExclusionObj:

    def __init__(self, object_name, excluded_faces, sel_faces) -> None:
        self.obj_name = object_name
        self.faces = excluded_faces
        self.selection = sel_faces


class PackExcludedFactory:

    exclusion = []

    @classmethod
    def ensure_facemap(cls, bm, facemap_name):
        """ Return facemap int type or create new """
        facemap = bm.faces.layers.int.get(facemap_name)
        if not facemap:
            facemap = bm.faces.layers.int.new(facemap_name)
        return facemap

    @classmethod
    def _get_excluded_facemap(cls, bm):
        return bm.faces.layers.int.get(PACK_EXCLUDED_FACEMAP_NAME, None)

    @classmethod
    def get_pack_excluded_map_from(cls, _obj):
        """ Return excluded VC Layer or None """
        return _obj.data.vertex_colors.get(PACK_EXCLUDED_V_MAP_NAME) or None

    @classmethod
    def tag_pack_excluded(cls, context, objs, action):
        """
        Tag or untag Pack Excluded depend on action='TAG' / 'UNTAG'
        """
        log = pLogger()
        for obj in objs:
            me, bm, uv_layer = cls._get_obj_bm_data(obj)
            if True in (v.select for v in bm.verts):
                pack_excluded_facemap = cls.ensure_facemap(bm, PACK_EXCLUDED_FACEMAP_NAME)
                islands_for_process = island_util.get_island(context, bm, uv_layer)
            else:
                continue
            log.store(len(islands_for_process) != 0)

            if action == "TAG":
                tag = 1
            elif action == "UNTAG":
                tag = 0

            set_face_int_tag(islands_for_process, pack_excluded_facemap, int_tag=tag)
            bmesh.update_edit_mesh(me)

        return log.get_result()

    @classmethod
    def _get_obj_bm_data(cls, obj):
        me = obj.data
        bm = bmesh.from_edit_mesh(me)
        bm.faces.ensure_lookup_table()
        bm.verts.ensure_lookup_table()
        uv_layer = verify_uv_layer(bm)
        return me, bm, uv_layer

    @classmethod
    def offset_tagged_islands(cls, context, objs, direction):
        log = pLogger()
        for obj in objs:
            me, bm, uv_layer = cls._get_obj_bm_data(obj)
            pack_excluded_facemap = cls._get_excluded_facemap(bm)
            if pack_excluded_facemap is None:
                continue

            for island in island_util.get_islands(context, bm):
                if True in [face[pack_excluded_facemap] for face in island]:
                    log.store(True)
                    move_island(island, uv_layer, direction)
                log.store(False)
            bmesh.update_edit_mesh(me)
        return log.get_result()

    @classmethod
    def select_excluded(cls, context: bpy.types.Context, objs: list, clear: bool, action: str = 'SELECT'):
        log = pLogger()
        for obj in objs:
            me, bm, uv_layer = cls._get_obj_bm_data(obj)
            pack_excluded_facemap = cls._get_excluded_facemap(bm)
            if pack_excluded_facemap is None:
                continue
            islands_for_select = [island for island in island_util.get_islands(context, bm) if True in [f[pack_excluded_facemap] for f in island]]
            log.store(len(islands_for_select) != 0)

            select_by_context(context, bm, islands_for_select, state=action == 'SELECT')
            bmesh.update_edit_mesh(me)
        return log.get_result()

    @classmethod
    def hide_by_facemap(cls, context, objs):
        cls.exclusion.clear()
        log = pLogger()
        for obj in objs:
            me, bm, uv_layer = cls._get_obj_bm_data(obj)
            _facemap = bm.faces.layers.int.get(PACK_EXCLUDED_FACEMAP_NAME, None)
            if _facemap is None:
                continue
            islands = [island for island in island_util.get_islands(context, bm) if True in [f[_facemap] for f in island]]
            log.store(len(islands) != 0)

            ex_faces = [f.index for island in islands for f in island]
            sel_faces = [f.index for island in islands for f in island if f.select]
            cls.exclusion.append(ExclusionObj(obj.name, ex_faces, sel_faces))

            for i in ex_faces:
                bm.faces[i].hide_set(True)

            bmesh.update_edit_mesh(me)
        return log.get_result()

    @classmethod
    def unhide_by_facemap(cls, objs):
        log = pLogger()
        for obj in objs:
            me, bm, uv_layer = cls._get_obj_bm_data(obj)
            _facemap = cls._get_excluded_facemap(bm)
            if _facemap is None:
                continue
            hidden_faces = [f.index for f in bm.faces if f.hide and f[_facemap]]
            log.store(len(hidden_faces) != 0)

            for i in hidden_faces:
                bm.faces[i].hide_set(False)

            bmesh.update_edit_mesh(me)
        return log.get_result()

    @classmethod
    def unhide_by_stored(cls, context):
        if cls.exclusion:
            for st in cls.exclusion:
                me, bm, uv_layer = cls._get_obj_bm_data(context.scene.objects[st.obj_name])
                if st.faces:
                    for i in st.faces:
                        bm.faces[i].hide_set(False)
                bmesh.update_edit_mesh(me)
            return True
        return False

    @classmethod
    def restore_selection(cls, context):
        if cls.exclusion:
            for st in cls.exclusion:
                me, bm, uv_layer = cls._get_obj_bm_data(context.scene.objects[st.obj_name])
                if st.selection:
                    for i in st.selection:
                        bm.faces[i].select = True
                bmesh.update_edit_mesh(me)
            return True
        return False


class ZUV_OT_OffsetPackExcluded(bpy.types.Operator):
    bl_idname = "uv.zenuv_offset_pack_excluded"
    bl_label = ZuvPackExcludedLabels.OT_OFFSET_EXCLUDED_LABEL
    bl_description = ZuvPackExcludedLabels.OT_OFFSET_EXCLUDED_DESC
    bl_options = {'REGISTER', 'UNDO'}

    offset: bpy.props.FloatVectorProperty(
        name=ZuvPackExcludedLabels.PROP_OFFSET_EXCLUDED_LABEL,
        description=ZuvPackExcludedLabels.PROP_OFFSET_EXCLUDED_DESC,
        size=2,
        default=(1.0, 0.0),
        subtype='XYZ'
    )

    @classmethod
    def poll(cls, context):
        active_object = context.active_object
        return active_object is not None and active_object.type == 'MESH' and context.mode == 'EDIT_MESH'

    def execute(self, context):
        PEF = PackExcludedFactory()
        objs = resort_by_type_mesh_in_edit_mode_and_sel(context)
        if not objs:
            self.report({'WARNING'}, "Zen UV: There are no selected objects.")
            return {'CANCELLED'}

        res = PEF.offset_tagged_islands(context, objs, self.offset)
        if not res:
            self.report({'WARNING'}, "Zen UV: There are no Excluded Islands.")
            return {'CANCELLED'}
        fit_uv_view(context, mode="checker")
        return {'FINISHED'}


class ZUV_OT_Tag_PackExcluded(bpy.types.Operator):
    """
    Operator to Tag PackExcluded Islands
    """
    bl_idname = "uv.zenuv_tag_pack_excluded"
    bl_label = ZuvPackExcludedLabels.OT_TAG_EXCL_LABEL
    bl_description = ZuvPackExcludedLabels.OT_TAG_EXCL_DESC
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        """ Validate context """
        active_object = context.active_object
        return active_object is not None and active_object.type == 'MESH' and context.mode == 'EDIT_MESH'

    def execute(self, context):
        objs = resort_by_type_mesh_in_edit_mode_and_sel(context)
        if not objs:
            self.report({'WARNING'}, "Zen UV: There are no selected objects.")
            return {'CANCELLED'}

        res = PackExcludedFactory.tag_pack_excluded(context, objs, action="TAG")
        if not res:
            self.report({'WARNING'}, "Zen UV: There is no Selection.")
            return {'CANCELLED'}

        fit_uv_view(context, mode="checker")
        return {'FINISHED'}


class ZUV_OT_UnTag_PackExcluded(bpy.types.Operator):
    """
    Operator to Untag Pack Excluded Islands
    """
    bl_idname = "uv.zenuv_untag_pack_excluded"
    bl_label = ZuvPackExcludedLabels.OT_UNTAG_EXCL_LABEL
    bl_description = ZuvPackExcludedLabels.OT_UNTAG_EXCL_DESC
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        """ Validate context """
        active_object = context.active_object
        return active_object is not None and active_object.type == 'MESH' and context.mode == 'EDIT_MESH'

    def execute(self, context):
        objs = resort_by_type_mesh_in_edit_mode_and_sel(context)
        if not objs:
            self.report({'WARNING'}, "Zen UV: There are no selected objects.")
            return {'CANCELLED'}

        res = PackExcludedFactory.tag_pack_excluded(context, objs, action="UNTAG")
        if not res:
            self.report({'WARNING'}, "Zen UV: There is no Selection.")
            return {'CANCELLED'}

        fit_uv_view(context, mode="checker")
        return {'FINISHED'}


class ZUV_OT_Select_PackExcluded(bpy.types.Operator):
    bl_idname = "uv.zenuv_select_pack_excluded"
    bl_label = ZuvPackExcludedLabels.OT_SELECT_EXCL_LABEL
    bl_description = ZuvPackExcludedLabels.OT_SELECT_EXCL_DESC
    bl_options = {'REGISTER', 'UNDO'}

    clear_selection: bpy.props.BoolProperty(
        name=ZuvPackExcludedLabels.OT_PROP_SELECT_EXCL_LABEL,
        description=ZuvPackExcludedLabels.OT_PROP_SELECT_EXCL_DESC,
        default=True)

    action: bpy.props.EnumProperty(
        name='Action',
        description='Action',
        items=[
            ("SELECT", "Select", "Select islands tagged as excluded"),
            ("DESELECT", "Deselect", "Deselect islands tagged as excluded")
            ],
        default='SELECT')

    @classmethod
    def poll(cls, context):
        active_object = context.active_object
        return active_object is not None and active_object.type == 'MESH' and context.mode == 'EDIT_MESH'

    def execute(self, context):
        objs = resort_by_type_mesh_in_edit_mode_and_sel(context)
        if not objs:
            self.report({'WARNING'}, "There are no selected objects")
            return {'CANCELLED'}

        if self.action == 'SELECT' and self.clear_selection:
            bpy_deselect_by_context(context)

        result = PackExcludedFactory.select_excluded(context, objs, self.clear_selection, self.action)

        if not result:
            self.report({'WARNING'}, "Zen UV: There are no Excluded Islands.")
            return {'CANCELLED'}

        return {"FINISHED"}


class ZUV_OT_Hide_PackExcluded(bpy.types.Operator):
    bl_idname = "uv.zenuv_hide_pack_excluded"
    bl_label = 'Hide Excluded'
    bl_description = 'Hide islands tagged as excluded from packing'
    bl_options = {'REGISTER', 'UNDO'}

    action: bpy.props.EnumProperty(
        name='Action',
        description='Action',
        items=[
            ("HIDE", "Hide", "Hide islands tagged as excluded"),
            ("UNHIDE", "Unhide", "Unhide islands tagged as excluded")
            ],
        default='HIDE')

    select: bpy.props.BoolProperty(
        name='Select',
        description='Select unhided islands',
        default=True)

    reveal_anyway: bpy.props.BoolProperty(
        name='Reveal Anyway',
        description='Anyway reveal excluded islands if UV Sync Selection is off',
        default=False)

    @classmethod
    def poll(cls, context):
        active_object = context.active_object
        return active_object is not None and active_object.type == 'MESH' and context.mode == 'EDIT_MESH'

    def draw(self, context):
        layout = self.layout
        layout.prop(self, 'action')
        row = layout.row()
        row.enabled = self.action == 'UNHIDE'
        row.prop(self, 'select')
        row = layout.row()
        row.enabled = not context.scene.tool_settings.use_uv_select_sync
        row.prop(self, 'reveal_anyway')

    def execute(self, context):
        from ZenUV.utils.generic import HideUnhideProcessor
        objs = resort_by_type_mesh_in_edit_mode_and_sel(context)
        if not objs:
            self.report({'WARNING'}, "There are no selected objects")
            return {'CANCELLED'}

        result = []

        for obj in objs:
            bm = bmesh.from_edit_mesh(obj.data)
            uv_layer = verify_uv_layer(bm)
            bm.faces.ensure_lookup_table()

            p_fmap = PackExcludedFactory._get_excluded_facemap(bm)
            if p_fmap is None:
                result.append(False)
                continue

            result.append(True)

            HideUnhideProcessor.hide_by_context(
                context,
                uv_layer,
                [[face for face in bm.faces if face[p_fmap]], ],
                self.action,
                self.select,
                self.reveal_anyway)

            bmesh.update_edit_mesh(obj.data, loop_triangles=False, destructive=False)

        if True not in result:
            self.report({'WARNING'}, "There are no excluded islands")
            return {'CANCELLED'}

        return {"FINISHED"}


pack_exlusion_classes = [
    ZUV_OT_Tag_PackExcluded,
    ZUV_OT_UnTag_PackExcluded,
    ZUV_OT_Select_PackExcluded,
    ZUV_OT_OffsetPackExcluded,
    ZUV_OT_Hide_PackExcluded
]

pack_exclusion_panels = [
    ZUV_PT_pExclude_Properties,
]

pack_exclusion_parented_panels = [
    SYSTEM_PT_PackExcluded_UV,
    SYSTEM_PT_PackExcluded,
]


def register_pack_exclusion():
    RegisterUtils.register(pack_exlusion_classes + pack_exclusion_panels)


def unregister_pack_exclusion():
    RegisterUtils.unregister(pack_exlusion_classes + pack_exclusion_panels)


if __name__ == '__main__':
    pass
