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

""" Zen UV Finishing System """

import bpy
import bmesh

from ...utils.uv_factory import UvIslandUtils, SelectionUtils
from ...utils.generic import (
    fit_uv_view,
    ResortObjects,
    bpy_select_by_context,
    verify_uv_layer
)
from ...ui.labels import ZuvLabels
from ...ui.pie import ZsPieFactory
from ...utils.generic import (
    ZUV_PANEL_CATEGORY, ZUV_REGION_TYPE,
    ZUV_SPACE_TYPE)

from mathutils import Vector

from ...utils.transform import UvTransformUtils
from ...utils.bounding_box import BoundingBox2d
from ...utils.iter_utils import IterUtils

from ...utils.generic import (
    set_face_int_tag,
    ensure_facemap)
from ...utils import vc_processor as vc
from ...utils.blender_zen_utils import ZenPolls, is_sync_off


FINISHED_FACEMAP_NAME = "ZenUV_Finished"


class FinishedFactory:

    @classmethod
    def pin_island(cls, island, uv_layer, _pin_action):
        for face in island:
            for loop in face.loops:
                loop[uv_layer].pin_uv = _pin_action

    @classmethod
    def island_in_range(cls, value, _min, _max):
        if _min <= value <= _max:  # and round(value,4)==value:
            return True
        return False

    @classmethod
    def select_finished(cls, context, bm, uv_layer, _finished_facemap, action: str = 'SELECT') -> bool:
        p_islands = [
            island for island in
            UvIslandUtils.yield_uv_islands(context, bm, uv_layer, b_selected_only=False, b_include_hidden=False)
            if any([f[_finished_facemap] for f in island])]

        if not len(p_islands):
            return False
        for island in p_islands:
            SelectionUtils.select_faces_any_context(context, island, state=action == 'SELECT', bm=bm, uv_layer=uv_layer)
        return True

    @classmethod
    def show_in_view_finished(cls, context, bm, _finished_facemap):
        finished_color = context.preferences.addons[ZenPolls.ADDON_PACKAGE].preferences.FinishedColor
        unfinished_color = context.preferences.addons[ZenPolls.ADDON_PACKAGE].preferences.UnFinishedColor
        finished_faces = [face for face in bm.faces if face[_finished_facemap]]
        unfinished_faces = [face for face in bm.faces if not face[_finished_facemap]]
        # for face in [face for face in bm.faces if face[_finished_facemap]]:
        #     face.select = True
        vc.set_v_color(
            unfinished_faces,
            vc.set_color_layer(bm, vc.Z_FINISHED_V_MAP_NAME),
            unfinished_color, randomize=False
        )
        vc.set_v_color(
            finished_faces,
            vc.set_color_layer(bm, vc.Z_FINISHED_V_MAP_NAME),
            finished_color, randomize=False
        )

    @classmethod
    def finished_sort_islands(cls, bm, islands, finished_facemap, is_sort_finished: bool = True, is_sort_unfinished: bool = True):
        ''' Sorting By Tag Finished '''

        uv_layer = verify_uv_layer(bm)
        sort_states = []
        for island in islands:
            x_base = BoundingBox2d(islands=[island, ], uv_layer=uv_layer).center.x % 1
            if finished_facemap is None:
                sort_states.append(x_base - 1)
            else:
                if any(face[finished_facemap] for face in island):
                    if is_sort_finished:
                        sort_states.append(x_base + 1)
                    else:
                        sort_states.append(False)
                else:
                    if is_sort_unfinished:
                        sort_states.append(x_base - 1)
                    else:
                        sort_states.append(False)

        for state, island in zip(sort_states, islands):
            if not state:
                continue

            UvTransformUtils.move_island_to_position(island, uv_layer, position=Vector((state, 0)), axis=Vector((1.0, 0.0)))

    @classmethod
    def get_finished_map_from(cls, _obj):
        """ Return finished VC Layer or None """
        return _obj.data.vertex_colors.get(vc.Z_FINISHED_V_MAP_NAME) or None

    @classmethod
    def disable_finished_vc(cls, _obj, _finished_vc_layer):
        """ Disable Finished VC and remove VC from object data """
        _finished_vc_layer = cls.get_finished_map_from(_obj)
        if _finished_vc_layer:
            _finished_vc_layer.active = False
            _obj.data.vertex_colors.remove(_finished_vc_layer)

    @classmethod
    def is_finished_activated(cls, context):
        for obj in context.objects_in_mode:
            finished_vc_map = None
            if obj.type == 'MESH':
                vc_map_in_object = obj.data.vertex_colors.get(vc.Z_FINISHED_V_MAP_NAME)
                if not finished_vc_map and vc_map_in_object:
                    finished_vc_map = vc_map_in_object
            return finished_vc_map

    @classmethod
    def tag_finished(cls, context, action):
        """
        Tag or untag Finished depend on action='TAG' / 'UNTAG'
        """
        addon_prefs = context.preferences.addons[ZenPolls.ADDON_PACKAGE].preferences

        objs = ResortObjects.resort_objects_by_selection(context, context.objects_in_mode)
        if not objs:
            return

        for obj, bm, uv_layer in IterUtils.iter_objs_with_bmesh_uv(objs, context, skip_obj_if_no_uv=True):

            finished_vc_layer = cls.get_finished_map_from(obj)
            if any(v.select for v in bm.verts):
                finished_facemap = ensure_facemap(bm, FINISHED_FACEMAP_NAME)
                islands_for_process = UvIslandUtils.get_selected_uv_islands(context, bm, uv_layer)
            else:
                continue

            if action == "TAG":
                tag = 1
            elif action == "UNTAG":
                tag = 0

            set_face_int_tag(islands_for_process, finished_facemap, int_tag=tag)
            # Set visible Finished faces if Finished VC Layer is apear in obj data.
            if finished_vc_layer:
                cls.disable_finished_vc(obj, finished_vc_layer)
                cls.show_in_view_finished(context, bm, finished_facemap)
                finished_vc_layer = cls.get_finished_map_from(obj)
                if finished_vc_layer:
                    finished_vc_layer.active = True

            if addon_prefs.autoFinishedToPinned:
                for island in islands_for_process:
                    cls.pin_island(island, uv_layer, tag)

            if addon_prefs.sortAutoSorting:
                FinishedFactory.finished_sort_islands(bm, islands_for_process, finished_facemap)

            bmesh.update_edit_mesh(obj.data, loop_triangles=False, destructive=False)


class ZUV_OT_Sorting_Islands(bpy.types.Operator):
    bl_idname = "uv.zenuv_islands_sorting"
    bl_label = ZuvLabels.SORTING_LABEL
    bl_description = ZuvLabels.SORTING_DESC
    bl_options = {'REGISTER', 'UNDO'}

    is_move_finished: bpy.props.BoolProperty(
        name='Move Finished',
        description='Determines whether to move islands marked as Finished',
        default=True)
    is_move_unfinished: bpy.props.BoolProperty(
        name='Move Unfinished',
        description='Determines whether to move islands marked as Finished',
        default=True)

    @classmethod
    def poll(cls, context):
        active_object = context.active_object
        return active_object is not None and active_object.type == 'MESH' and context.mode == 'EDIT_MESH'

    def execute(self, context):
        if self.is_move_finished is False and self.is_move_unfinished is False:
            self.report({'WARNING'}, "Nothing has been produced. All movement permissions are disabled.")
            return {'FINISHED'}
        objs = ResortObjects.resort_by_type_mesh_in_edit_mode_and_sel(context)
        if not objs:
            self.report({'WARNING'}, "No objects selected.")
            return {'CANCELLED'}

        for obj, bm, uv_layer in IterUtils.iter_objs_with_bmesh_uv(objs, context, skip_obj_if_no_uv=True):

            finished_facemap = bm.faces.layers.int.get(FINISHED_FACEMAP_NAME, None)
            islands_for_process = UvIslandUtils.get_all_uv_islands(context, bm, uv_layer)
            FinishedFactory.finished_sort_islands(
                bm,
                islands_for_process,
                finished_facemap,
                is_sort_finished=self.is_move_finished,
                is_sort_unfinished=self.is_move_unfinished)
            bmesh.update_edit_mesh(obj.data, loop_triangles=False, destructive=False)
        fit_uv_view(context, mode="checker")
        return {'FINISHED'}


class ZUV_OT_Tag_Finished(bpy.types.Operator):
    """
    Operator to Tag Finished Islands
    """
    bl_idname = "uv.zenuv_tag_finished"
    bl_label = ZuvLabels.OT_TAG_FINISHED_LABEL
    bl_description = ZuvLabels.OT_TAG_FINISHED_DESC
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        """ Validate context """
        active_object = context.active_object
        return active_object is not None and active_object.type == 'MESH' and context.mode == 'EDIT_MESH'

    def execute(self, context):

        ZsPieFactory.mark_pie_cancelled()

        FinishedFactory.tag_finished(context, action="TAG")
        fit_uv_view(context, mode="checker")
        return {'FINISHED'}


class ZUV_OT_UnTag_Finished(bpy.types.Operator):
    """
    Operator to Untag Finished Islands
    """
    bl_idname = "uv.zenuv_untag_finished"
    bl_label = ZuvLabels.OT_UNTAG_FINISHED_LABEL
    bl_description = ZuvLabels.OT_UNTAG_FINISHED_DESC
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        """ Validate context """
        active_object = context.active_object
        return active_object is not None and active_object.type == 'MESH' and context.mode == 'EDIT_MESH'

    def execute(self, context):

        ZsPieFactory.mark_pie_cancelled()

        FinishedFactory.tag_finished(context, action="UNTAG")
        fit_uv_view(context, mode="checker")
        return {'FINISHED'}


class ZUV_OT_Display_Finished(bpy.types.Operator):
    bl_idname = "uv.zenuv_display_finished"
    bl_label = ZuvLabels.OT_FINISHED_DISPLAY_LABEL
    bl_description = ZuvLabels.OT_FINISHED_DISPLAY_DESC
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):

        ZsPieFactory.mark_pie_cancelled()

        p_scene = context.scene
        if context.space_data.type == 'IMAGE_EDITOR':
            p_scene.zen_uv.ui.draw_mode_UV = 'FINISHED' if p_scene.zen_uv.ui.draw_mode_UV != 'FINISHED' else 'NONE'
        else:
            p_scene.zen_uv.ui.draw_mode_3D = 'FINISHED' if p_scene.zen_uv.ui.draw_mode_3D != 'FINISHED' else 'NONE'

        return {"FINISHED"}


class ZUV_OT_Select_Finished(bpy.types.Operator):
    bl_idname = "uv.zenuv_select_finished"
    bl_label = ZuvLabels.OT_FINISHED_SELECT_LABEL
    bl_description = ZuvLabels.OT_FINISHED_SELECT_DESC
    bl_options = {'REGISTER', 'UNDO'}

    clear_selection: bpy.props.BoolProperty(
        name='Clear Selection',
        description='Clears the initial selection before applying the operation',
        default=True)

    action: bpy.props.EnumProperty(
        name='Action',
        description='Action',
        items=[
            ("SELECT", "Select", "Select islands tagged as finished"),
            ("DESELECT", "Deselect", "Deselect islands tagged as finished")
            ],
        default='SELECT')

    @classmethod
    def poll(cls, context):
        active_object = context.active_object
        return active_object is not None and active_object.type == 'MESH' and context.mode == 'EDIT_MESH'

    def execute(self, context):
        objs = ResortObjects.resort_by_type_mesh_in_edit_mode_and_sel(context)
        if not objs:
            self.report({'WARNING'}, "No objects selected.")
            return {'CANCELLED'}

        if self.action == 'SELECT' and self.clear_selection:
            bpy_select_by_context(context, action='DESELECT')

        result = []

        for obj, bm, uv_layer in IterUtils.iter_objs_with_bmesh_uv(objs, context, skip_obj_if_no_uv=True):

            finished_facemap = bm.faces.layers.int.get(FINISHED_FACEMAP_NAME, None)
            if finished_facemap is None:
                result.append(False)
                continue

            result.append(FinishedFactory.select_finished(context, bm, uv_layer, finished_facemap, action=self.action))
            bmesh.update_edit_mesh(obj.data, loop_triangles=False, destructive=False)

        if True not in result:
            self.report({'WARNING'}, "No islands found with 'finished' tag")
            return {'CANCELLED'}

        return {"FINISHED"}


class ZUV_OT_Hide_Finished(bpy.types.Operator):
    bl_idname = "uv.zenuv_hide_finished"
    bl_label = 'Hide Finished'
    bl_description = 'Hide/Unhide islands tagged as finished'
    bl_options = {'REGISTER', 'UNDO'}

    action: bpy.props.EnumProperty(
        name='Action',
        description='Action',
        items=[
            ("HIDE", "Hide", "Hide islands tagged as finished"),
            ("UNHIDE", "Unhide", "Unhide islands tagged as finished")
            ],
        default='HIDE')

    select: bpy.props.BoolProperty(
        name='Select',
        description='Select unhided islands',
        default=True)

    reveal_anyway: bpy.props.BoolProperty(
        name='Reveal Anyway',
        description='Anyway reveal finished islands if UV Sync Selection is off',
        default=True)

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
        row.enabled = is_sync_off(context)
        row.prop(self, 'reveal_anyway')

    def execute(self, context):
        from ...utils.generic import HideUnhideProcessor
        objs = ResortObjects.resort_by_type_mesh_in_edit_mode_and_sel(context)
        if not objs:
            self.report({'WARNING'}, "No objects selected.")
            return {'CANCELLED'}

        result = []

        for obj, bm, uv_layer in IterUtils.iter_objs_with_bmesh_uv(objs, context, skip_obj_if_no_uv=True):

            finished_facemap = bm.faces.layers.int.get(FINISHED_FACEMAP_NAME, None)
            if finished_facemap is None:
                result.append(False)
                continue

            result.append(True)

            HideUnhideProcessor.hide_by_context(
                context,
                bm,
                uv_layer,
                [[face for face in bm.faces if face[finished_facemap]], ],
                self.action,
                self.select,
                self.reveal_anyway)

            bmesh.update_edit_mesh(obj.data, loop_triangles=False, destructive=False)

        if True not in result:
            self.report({'WARNING'}, "There are no finished islands")
            return {'CANCELLED'}

        return {"FINISHED"}


def draw_finished_section(self, context: bpy.types.Context):
    ''' @Draw Finished '''
    layout = self.layout
    col = layout.column(align=True)
    row = col.row(align=True)
    row.operator(ZUV_OT_Sorting_Islands.bl_idname, text='Sort Islands by Tags')
    row.popover(panel="FINISHED_PT_Properties", text="", icon="PREFERENCES")

    row = col.row(align=True)
    row.operator(ZUV_OT_Tag_Finished.bl_idname)
    row.operator(ZUV_OT_UnTag_Finished.bl_idname)

    row = col.row(align=True)
    row.operator(ZUV_OT_Select_Finished.bl_idname, text='Select').action = 'SELECT'
    row.operator(ZUV_OT_Select_Finished.bl_idname, text='Deselect').action = 'DESELECT'

    row = col.row(align=True)
    row.operator(ZUV_OT_Hide_Finished.bl_idname, text='Hide').action = 'HIDE'
    row.operator(ZUV_OT_Hide_Finished.bl_idname, text='Unhide').action = 'UNHIDE'

    from ...zen_checker.check_utils import draw_checker_display_items, DisplayItem
    draw_checker_display_items(col, context, {'FINISHED': DisplayItem({'EDIT_MESH'}, {'UV', '3D'}, '', 'Display Finished')})


class SYSTEM_PT_Finished(bpy.types.Panel):
    bl_space_type = ZUV_SPACE_TYPE
    bl_label = "Finished"
    bl_parent_id = "ZUV_PT_Unwrap"
    bl_region_type = ZUV_REGION_TYPE
    bl_idname = "SYSTEM_PT_Finished"
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        draw_finished_section(self, context)


class SYSTEM_PT_Finished_UV(bpy.types.Panel):
    bl_space_type = "IMAGE_EDITOR"
    bl_label = "Finished"
    bl_parent_id = "ZUV_PT_UVL_Unwrap"
    bl_region_type = ZUV_REGION_TYPE
    bl_idname = "SYSTEM_PT_Finished_UV"
    bl_category = ZUV_PANEL_CATEGORY
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        draw_finished_section(self, context)


finishing_parented_panels = [
    SYSTEM_PT_Finished_UV,
    SYSTEM_PT_Finished,
]

finishing_classes = (
    ZUV_OT_UnTag_Finished,
    ZUV_OT_Tag_Finished,
    ZUV_OT_Sorting_Islands,
    ZUV_OT_Select_Finished,
    ZUV_OT_Display_Finished,
    ZUV_OT_Hide_Finished
)


if __name__ == '__main__':
    pass
