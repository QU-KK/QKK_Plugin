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

""" Zen Stack Groups System """
# from typing import DefaultDict

import bpy
import bmesh
from bpy.props import StringProperty, FloatProperty, BoolProperty
from bpy.types import (
    UIList,
    Operator,
    Panel
)
from ZenUV.utils.generic import (
    ZUV_PANEL_CATEGORY,
    ZUV_REGION_TYPE,
    ZUV_CONTEXT
)
from ZenUV.utils import get_uv_islands as island_util
from ZenUV.ui.labels import ZuvLabels
from ZenUV.utils.generic import (
    select_all,
    enshure_text_block,
    update_indexes,
    verify_uv_layer)
from ZenUV.stacks.stacks import detect_masters, unstack
from ZenUV.stacks.utils import (
    get_area,
    get_geometry,
    get_perimeter,
    get_island_sim_index,
    StacksSystem,

)
from ZenUV.stacks.utils import (
    get_islands_from_stack,
    set_island_sim_index,
    enshure_stack_layer,
    M_STACK_LAYER_NAME
)
from ZenUV.prop.zuv_preferences import get_prefs

from ZenUV.utils.progress import ProgressBar, ProgressCancelException
from ZenUV.ui.ui_call import popup_areas
from ZenUV.utils.blender_zen_utils import ZenPolls
from ZenUV.utils.vlog import Log


def matching_indexes(sim_data, objs):
    for it_ob in objs:
        s_index, out_index = find_indexes_in_obj(sim_data, it_ob)
        if not s_index:
            continue
        it_ob.zms_list_index = out_index


def find_indexes_in_obj(sim_index, obj):
    """ Try to find given sim_index in manual stacks of given object """
    s_index = None
    out_index = None
    list_index = 0
    for list_item in obj.zen_stack_list:
        if not s_index and list_item.sim_index == sim_index:
            s_index = sim_index
            out_index = list_index
        list_index += 1

    return s_index, out_index


class ZMSListGroup(bpy.types.PropertyGroup):
    """
    Group of properties representing
    an item in the zen stack groups.
    """

    name: StringProperty(
        name="Name",
        description="",
        default="Stack"
    )
    layer_name: StringProperty(
        name="",
        description="",
        default=""
    )
    sim_index: FloatProperty(
        name=ZuvLabels.PROP_M_STACK_UI_LIST_SIM_INDEX_LABEL,
        description=ZuvLabels.PROP_M_STACK_UI_LIST_SIM_INDEX_DESC,
        default=0.0
    )
    move_only: BoolProperty(
        name=ZuvLabels.PROP_M_STACK_UI_LIST_MOVE_ONLY_LABEL,
        description=ZuvLabels.PROP_M_STACK_UI_LIST_MOVE_ONLY_DESC,
        default=False
    )
    area_match: BoolProperty(
        name=ZuvLabels.PREF_OT_AREA_MATCH_LABEL,
        description=ZuvLabels.PREF_OT_AREA_MATCH_DESC,
        default=True
    )


class ZMS_UL_List(UIList):
    ''' Zen Stacks Groups UIList '''
    def draw_item(self, context, layout, data, item,
                  icon, active_data, active_propname, index
                  ):
        ''' @Draw Stack Groups UI List '''
        custom_icon = 'OBJECT_DATAMODE'

        act_idx = getattr(active_data, active_propname)
        b_active = index == act_idx

        b_emboss = (context.area.as_pointer() in popup_areas) and b_active

        # Make sure code supports all 3 layout types
        if self.layout_type in {'DEFAULT', 'COMPACT'}:
            layout.prop(item, "name", text="", emboss=b_emboss, icon=custom_icon)
            layout.label(text=str(round(item.sim_index, 3)))
            layout.prop(item, "area_match", text="", icon_only=True, toggle=True, icon='EVENT_A')
            layout.prop(item, "move_only", text="", toggle=True, icon_only=True, icon='EVENT_M')

        elif self.layout_type in {'GRID'}:
            layout.alignment = 'CENTER'
            layout.prop(item, 'name', text="", emboss=b_emboss, icon=custom_icon)


def draw_manual_stacks(self, context):
    ''' @Draw Manual Stacks '''

    layout = self.layout
    ob = context.object

    row = layout.row()
    col = row.column()
    col.template_list(
        "ZMS_UL_List",
        "name",
        ob, "zen_stack_list",
        ob, "zms_list_index",
        rows=5
    )

    col_main = row.column()
    col = col_main.column(align=True)
    col.operator(ZMS_OT_NewItem.bl_idname, text="", icon='ADD')
    col.operator(ZMS_OT_DeleteItem.bl_idname, text="", icon='REMOVE')
    col_main.separator()
    col = col_main.column(align=True)
    col.operator(ZMS_OT_AssignToStack.bl_idname, text="", icon='IMPORT')
    col.operator(ZMS_OT_SelectStack.bl_idname, text="", icon='RESTRICT_SELECT_OFF')
    col.operator(ZMS_OT_AnalyzeStack.bl_idname, text="", icon='EXPERIMENTAL')
    col.operator(ZMS_OT_RemoveAllMstacks.bl_idname, text="", icon='TRASH')

    col = layout.column(align=True)
    col.operator(ZMS_OT_CollectManualStacks.bl_idname, text='Stack All').selected = False
    col.operator(ZMS_OT_CollectManualStacks.bl_idname, text='Selected').selected = True

    col.separator()

    col = layout.column(align=True)
    col.operator(ZMS_OT_Unstack_Manual_Stack.bl_idname, text='Unstack All').selected = False
    col.operator(ZMS_OT_Unstack_Manual_Stack.bl_idname, text='Selected').selected = True

    from ZenUV.zen_checker.check_utils import draw_checker_display_items, t_draw_stack_manual_modes

    draw_checker_display_items(layout, context, t_draw_stack_manual_modes)


class ZUV_PT_UVL_ZenManualStack(Panel):
    """  Zen Seam Groups Panel """
    bl_label = ZuvLabels.PT_STACK_GROUP_LABEL
    bl_context = ZUV_CONTEXT
    bl_space_type = "IMAGE_EDITOR"
    bl_region_type = ZUV_REGION_TYPE
    bl_category = ZUV_PANEL_CATEGORY
    bl_options = {'DEFAULT_CLOSED'}
    bl_parent_id = "ZUV_PT_UVL_Stack"

    def draw(self, context):
        draw_manual_stacks(self, context)


class ZUV_PT_ZenManualStack(Panel):
    """  Zen Seam Groups Panel """
    bl_label = ZuvLabels.PT_STACK_GROUP_LABEL
    bl_context = ZUV_CONTEXT
    bl_space_type = "VIEW_3D"
    bl_region_type = ZUV_REGION_TYPE
    bl_category = ZUV_PANEL_CATEGORY
    bl_options = {'DEFAULT_CLOSED'}
    bl_parent_id = "ZUV_PT_Stack"

    def draw(self, context):
        draw_manual_stacks(self, context)


class ZMS_OT_NewItem(Operator):
    """Add a new item to the list."""
    bl_description = ZuvLabels.OT_ZMS_NEW_ITEM_DESC
    bl_idname = "zen_stack_list.new_item"
    bl_label = ZuvLabels.OT_ZMS_NEW_ITEM_LABEL
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        """ Validate context """
        active_object = context.active_object
        return active_object is not None and active_object.type == 'MESH' and context.mode == 'EDIT_MESH'

    def execute(self, context):
        # Detect sim index
        sim_index = None
        for obj in context.objects_in_mode:
            if sim_index:
                continue
            me = obj.data
            bm = bmesh.from_edit_mesh(me)
            # enshure_stack_layer(bm, stack_layer_name=M_STACK_LAYER_NAME)
            uv_layer = verify_uv_layer(bm)
            islands = island_util.get_island(context, bm, uv_layer)
            for island in islands:
                sim_index, gd = get_island_sim_index(island, uv_layer)

            bmesh.update_edit_mesh(me, loop_triangles=False)

        # If there is no sim index it means that there are no selection
        if not sim_index:
            self.report({'INFO'}, "Select something.")
            return {'CANCELLED'}

        # Creating Layers
        for obj in context.objects_in_mode:
            obj.zen_stack_list.add()
            name = "Stack"
            i = 1

            while name in obj.zen_stack_list:
                name = "Stack_{0}".format(str(i))
                i = i + 1

            obj.zen_stack_list[-1].name = name
            obj.zen_stack_list[-1].layer_name = M_STACK_LAYER_NAME
            obj.zms_list_index = len(obj.zen_stack_list) - 1

            me = obj.data
            bm = bmesh.from_edit_mesh(me)
            enshure_stack_layer(bm, stack_layer_name=M_STACK_LAYER_NAME)
            uv_layer = verify_uv_layer(bm)
            islands = island_util.get_island(context, bm, uv_layer)
            for island in islands:
                set_island_sim_index(bm, island, M_STACK_LAYER_NAME, sim_index)
            obj.zen_stack_list[-1].sim_index = sim_index
            obj.zen_stack_list[-1].move_only = False

            bmesh.update_edit_mesh(me, loop_triangles=False)

        return {'FINISHED'}


class ZMS_OT_DeleteItem(Operator):
    """Delete the selected item from the list."""
    bl_description = ZuvLabels.OT_ZMS_DEL_ITEM_DESC
    bl_idname = "zen_stack_list.delete_item"
    bl_label = ZuvLabels.OT_ZMS_DEL_ITEM_LABEL
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        """ Validate context """
        active_object = context.active_object
        return active_object is not None and active_object.type == 'MESH' and context.mode == 'EDIT_MESH' and active_object.zen_stack_list

    def execute(self, context):
        obj = context.active_object
        if obj.zms_list_index in range(len(obj.zen_stack_list)):
            sim_index = obj.zen_stack_list[obj.zms_list_index].sim_index

            for obj in context.objects_in_mode:
                if obj.zms_list_index in range(len(obj.zen_stack_list)) and obj.zen_stack_list[obj.zms_list_index].sim_index == sim_index:
                    me = obj.data
                    bm = bmesh.from_edit_mesh(me)
                    faces = get_islands_from_stack(bm, M_STACK_LAYER_NAME, sim_index)
                    set_island_sim_index(bm, faces, M_STACK_LAYER_NAME, 0.0)
                    bmesh.update_edit_mesh(me, loop_triangles=False)

                    zen_stack_list = obj.zen_stack_list
                    index = obj.zms_list_index
                    zen_stack_list.remove(index)
                    obj.zms_list_index = min(max(0, index - 1), len(zen_stack_list) - 1)
        else:
            self.report({'INFO'}, ZuvLabels.OT_ZMS_COLLECT_STACK_MSG)
        return {'FINISHED'}


class ZMS_OT_RemoveAllMstacks(Operator):
    """Full Clear List"""
    bl_description = ZuvLabels.OT_ZMS_CLEAR_LIST_DESC
    bl_idname = "zen_stack_list.remove_all_m_stacks"
    bl_label = ZuvLabels.OT_ZMS_CLEAR_LIST_LABEL
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        """ Validate context """
        active_object = context.active_object
        return active_object is not None and active_object.type == 'MESH' and context.mode == 'EDIT_MESH' and active_object.zen_stack_list

    def execute(self, context):
        for obj in context.objects_in_mode:
            me = obj.data
            bm = bmesh.from_edit_mesh(me)
            set_island_sim_index(bm, bm.faces, M_STACK_LAYER_NAME, 0.0)
            bmesh.update_edit_mesh(me, loop_triangles=False)
            obj.zen_stack_list.clear()

        return {'FINISHED'}


class ZMS_OT_MoveItem(Operator):
    """Move an item in the list."""
    bl_description = ZuvLabels.OT_SGL_MOVE_ITEM_DESC
    bl_idname = "zen_stack_list.move_item"
    bl_label = ZuvLabels.OT_SGL_MOVE_ITEM_LABEL
    bl_options = {'REGISTER', 'UNDO'}

    direction: bpy.props.EnumProperty(
        items=(
            ('UP', 'Up', ""),
            ('DOWN', 'Down', ""),
        )
    )

    @classmethod
    def poll(cls, context):
        return context.object.zen_stack_list

    def move_index(self, context):
        """ Move index of an item stack while clamping it. """
        index = context.object.zms_list_index
        list_length = len(context.object.zen_stack_list) - 1
        # (index starts at 0)
        new_index = index + (-1 if self.direction == 'UP' else 1)
        context.object.zms_list_index = max(0, min(new_index, list_length))

    def execute(self, context):
        zen_stack_list = context.object.zen_stack_list
        index = context.object.zms_list_index
        neighbor = index + (-1 if self.direction == 'UP' else 1)
        zen_stack_list.move(neighbor, index)
        self.move_index()
        return {'FINISHED'}


class ZMS_OT_AssignToStack(bpy.types.Operator):
    """ Assign current stack to selected stack group """
    bl_description = ZuvLabels.OT_ZMS_ASSIGN_TO_STACK_DESC
    bl_idname = "uv.zenuv_assign_manual_stack"
    bl_label = ZuvLabels.OT_ZMS_ASSIGN_TO_STACK_LABEL
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        """ Validate context """
        active_object = context.active_object
        return active_object is not None and active_object.type == 'MESH' and context.mode == 'EDIT_MESH' and active_object.zen_stack_list

    def execute(self, context):
        ob = context.active_object
        if ob.zms_list_index not in range(len(ob.zen_stack_list)):
            self.report({'INFO'}, ZuvLabels.OT_ZMS_COLLECT_STACK_MSG)
            return {'CANCELLED'}
        active_index = ob.zms_list_index
        active_data = ob.zen_stack_list[active_index]
        sim_data = active_data.sim_index
        name = active_data.name
        layer_name = active_data.layer_name

        for obj in context.objects_in_mode:
            s_index, out_index = find_indexes_in_obj(sim_data, obj)
            if not s_index:
                obj.zen_stack_list.add()

                obj.zen_stack_list[-1].name = name
                obj.zen_stack_list[-1].layer_name = layer_name
                obj.zms_list_index = len(obj.zen_stack_list) - 1
                obj.zen_stack_list[-1].sim_index = sim_data

                me = obj.data
                bm = bmesh.from_edit_mesh(me)
                enshure_stack_layer(bm, stack_layer_name=layer_name)
                uv_layer = verify_uv_layer(bm)
                islands = island_util.get_island(context, bm, uv_layer)
                for island in islands:
                    set_island_sim_index(bm, island, layer_name, sim_data)
                    obj.zen_stack_list[-1].sim_index = sim_data

                bmesh.update_edit_mesh(me, loop_triangles=False)
            else:
                obj.zms_list_index = out_index

        for obj in context.objects_in_mode:
            if obj.zms_list_index in range(len(obj.zen_stack_list)):
                M_STACK_LAYER_NAME = obj. \
                    zen_stack_list[obj.zms_list_index].layer_name
                me = obj.data
                bm = bmesh.from_edit_mesh(me)
                uv_layer = verify_uv_layer(bm)
                islands = island_util.get_island(context, bm, uv_layer)
                for island in islands:
                    set_island_sim_index(bm, island, M_STACK_LAYER_NAME, sim_data)
                bmesh.update_edit_mesh(me, loop_triangles=False)
            else:
                self.report({'INFO'}, ZuvLabels.OT_ZMS_COLLECT_STACK_MSG)
        return {'FINISHED'}


class ZMS_OT_SelectStack(bpy.types.Operator):
    """ Set Stack from active group to current object stack. """
    bl_description = ZuvLabels.OT_ZMS_SELECT_STACK_DESC
    bl_idname = "uv.zenuv_select_m_stack"
    bl_label = ZuvLabels.OT_ZMS_SELECT_STACK_LABEL
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        """ Validate context """
        active_object = context.active_object
        return active_object is not None and active_object.type == 'MESH' and context.mode == 'EDIT_MESH' and active_object.zen_stack_list

    def execute(self, context):
        obj = context.active_object
        if obj.zms_list_index in range(len(obj.zen_stack_list)):
            sim_index = None
            me = obj.data
            bm = bmesh.from_edit_mesh(me)
            sim_index = obj.zen_stack_list[obj.zms_list_index].sim_index
            for obj in context.objects_in_mode:
                me = obj.data
                bm = bmesh.from_edit_mesh(me)
                select_all(bm, action=False)
                faces = get_islands_from_stack(bm, M_STACK_LAYER_NAME, sim_index)
                for face in faces:
                    face.select = True
                bmesh.update_edit_mesh(me, loop_triangles=False)
        else:
            self.report({'INFO'}, ZuvLabels.OT_ZMS_COLLECT_STACK_MSG)
        return {'FINISHED'}


class ZMS_OT_AnalyzeStack(bpy.types.Operator):
    """ Set Stack from active group to current object stack. """
    bl_description = ZuvLabels.OT_ZMS_ANALYZE_STACK_DESC
    bl_idname = "uv.zenuv_analyze_stack"
    bl_label = ZuvLabels.OT_ZMS_ANALYZE_STACK_LABEL
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        """ Validate context """
        active_object = context.active_object
        return active_object is not None and active_object.type == 'MESH' and context.mode == 'EDIT_MESH' and active_object.zen_stack_list

    def execute(self, context):
        obj = context.active_object
        if obj.zms_list_index in range(len(obj.zen_stack_list)):
            sim_index = None
            me = obj.data
            bm = bmesh.from_edit_mesh(me)
            sim_index = obj.zen_stack_list[obj.zms_list_index].sim_index
            analyze_data = "\n\tStack name: {}, Index: {}\n".format(obj.zen_stack_list[obj.zms_list_index].name, sim_index)
            for obj in context.objects_in_mode:
                me = obj.data
                bm = bmesh.from_edit_mesh(me)
                uv_layer = verify_uv_layer(bm)
                faces = get_islands_from_stack(bm, M_STACK_LAYER_NAME, sim_index)
                islands = island_util.get_islands_by_face_list(context, bm, faces, uv_layer)
                island_counter = 0
                if islands:
                    analyze_data += "\n\t\tObject: {}\n".format(obj.name)
                    for island in islands:
                        gd = get_geometry(island)
                        verts_count, edges_count, faces_count = len(gd["verts_ids"]), len(gd["edges_ids"]), len(gd["faces_ids"])
                        area = get_area(island)
                        perimeter = get_perimeter(island, uv_layer)
                        analyze_data += "\t\t\tIsland_{} -  Vertices: {}, Edges: {}, Faces: {}, Island Area: {}, Perimeter: {}\n".format(island_counter, verts_count, edges_count, faces_count, area, perimeter)
                        island_counter += 1
                bmesh.update_edit_mesh(me, loop_triangles=False)
            an_data_text = enshure_text_block("Zen UV Manual Stack Analyze")
            an_data_text.from_string("\nZen UV Manual Stacks analyze rezults:\n{}".format(analyze_data))
            self.raise_text(context, an_data_text)
            self.report({'INFO'}, "See 'Zen UV Analyze' in the text editor")
        else:
            self.report({'INFO'}, ZuvLabels.OT_ZMS_COLLECT_STACK_MSG)
        return {'FINISHED'}

    def raise_text(self, context: bpy.types.Context, an_data_text):

        try:
            bpy.ops.screen.userpref_show("INVOKE_DEFAULT")
            area = context.window_manager.windows[-1].screen.areas[0]
            area.type = 'TEXT_EDITOR'
            area.spaces[0].text = an_data_text

            ctx_override = context.copy()
            ctx_override['screen'] = context.window_manager.windows[-1].screen
            ctx_override['window'] = context.window_manager.windows[-1]
            ctx_override['area'] = area
            ctx_override['space_data'] = area.spaces[0]

            if ZenPolls.version_since_3_2_0:
                with bpy.context.temp_override(**ctx_override):
                    bpy.ops.text.jump(line=1)
            else:
                bpy.ops.text.jump(line=1)
        except Exception as e:
            Log.error('MANUAL STACKS: Open editor:', e)


class ZMS_OT_CollectManualStacks(bpy.types.Operator):
    """ Set Stack from active group to current object stack. """
    bl_description = ZuvLabels.OT_ZMS_COLLECT_STACK_DESC
    bl_idname = "uv.zenuv_collect_manual_stacks"
    bl_label = ZuvLabels.OT_ZMS_COLLECT_STACK_LABEL
    bl_options = {'REGISTER', 'UNDO'}

    selected: BoolProperty(
        name=ZuvLabels.PREF_OT_M_UNSTACK_SELECTED_LABEL,
        default=False,
        description=ZuvLabels.PREF_OT_M_UNSTACK_SELECTED_DESC,
        options={'HIDDEN'}
    )

    @classmethod
    def poll(cls, context):
        """ Validate context """
        active_object = context.active_object
        return active_object is not None and active_object.type == 'MESH' and context.mode == 'EDIT_MESH' and active_object.zen_stack_list

    def execute(self, context):
        ob = context.object
        # sim_index = ob.zen_stack_list[ob.zms_list_index].sim_index
        objs = context.objects_in_mode
        if not objs:
            return {'CANCELLED'}
        if self.selected:
            stacks = [ob.zen_stack_list[ob.zms_list_index], ]
        else:
            stacks = ob.zen_stack_list

        progress = ProgressBar(context, 100, text_only=False)
        progress.set_text(prefix="Stacking:", preposition=" of")
        progress.current_step = 0

        try:
            for m_stack in stacks:
                sim_index = m_stack.sim_index
                matching_indexes(sim_index, objs)
                move_only = m_stack.move_only
                stacks = StacksSystem(context)
                for master, replicas in stacks.clustered_full_forecast_with_masters(progress, m_stack=True, sim_index=sim_index, s_layer_name=M_STACK_LAYER_NAME, area_match=m_stack.area_match):
                    if not m_stack.area_match:
                        master.sim_index = int(master.sim_index)
                    for cl in replicas:
                        if not progress.update():
                            raise ProgressCancelException()
                        if not m_stack.area_match:
                            cl.sim_index = int(cl.sim_index)
                        cl.remap(
                            master,
                            transfer_params=False,
                            match_position=True,
                            move_only=move_only
                        )
                        cl.update_mesh()
        except ProgressCancelException:
            pass
        finally:
            progress.finish()
        return {'FINISHED'}


class ZMS_OT_Unstack_Manual_Stack(bpy.types.Operator):
    """ Set Stack from active group to current object stack. """
    bl_description = ZuvLabels.OT_ZMS_MANUAL_UNSTACK_DESC
    bl_idname = "uv.zenuv_unstack_manual_stack"
    bl_label = ZuvLabels.OT_ZMS_MANUAL_UNSTACK_LABEL
    bl_options = {'REGISTER', 'UNDO'}

    def update_break(self, context):
        if self.breakStack:
            self.increment = 1.0

    breakStack: BoolProperty(
        name=ZuvLabels.PREF_OT_M_UNSTACK_BREAK_LABEL,
        default=False,
        description=ZuvLabels.PREF_OT_M_UNSTACK_BREAK_DESC,
        update=update_break
    )
    increment: FloatProperty(
        name=ZuvLabels.PREF_OT_M_UNSTACK_INCREMENT_LABEL,
        description=ZuvLabels.PREF_OT_M_UNSTACK_INCREMENT_DESC,
        min=0.0,
        max=1.0,
        step=1,
        default=1.0,
        precision=3
    )
    selected: BoolProperty(
        name=ZuvLabels.PREF_OT_M_UNSTACK_SELECTED_LABEL,
        default=False,
        description=ZuvLabels.PREF_OT_M_UNSTACK_SELECTED_DESC,
        options={'HIDDEN'}
    )
    direction = None

    def invoke(self, context, event):
        self.direction = get_prefs().unstack_direction
        if not self.breakStack:
            self.increment = 0.0
        return self.execute(context)

    def draw(self, context):
        layout = self.layout
        layout.prop(self, "breakStack")
        if self.breakStack:
            layout.prop(self, "increment")

    @classmethod
    def poll(cls, context):
        """ Validate context """
        active_object = context.active_object
        return active_object is not None and active_object.type == 'MESH' and context.mode == 'EDIT_MESH' and active_object.zen_stack_list

    def execute(self, context):
        ob = context.object
        sim_index = ob.zen_stack_list[ob.zms_list_index].sim_index
        objs = context.objects_in_mode
        if not objs:
            return {'CANCELLED'}
        update_indexes(objs)
        if not self.breakStack:
            self.increment = 0.0
        if self.selected:
            stacks = [ob.zen_stack_list[ob.zms_list_index], ]
        else:
            stacks = ob.zen_stack_list

        progress = ProgressBar(context, 100, text_only=False)
        progress.set_text(prefix="Unstacking:", preposition=" of")
        progress.iterations = len(stacks)

        for m_stack in stacks:
            sim_index = m_stack.sim_index
            matching_indexes(sim_index, objs)
            stacks = StacksSystem(context)
            sim_data = stacks.forecast(m_stack=True, sim_index=sim_index, s_layer_name=M_STACK_LAYER_NAME)
            sim_data = detect_masters(context, sim_data, False)
            unstack(context, sim_data[sim_index], self.direction, self.increment, progress)
            if not progress.update():
                break

        if progress.pb is not None:
            progress.finish()

            if self.selected:
                self.report({'INFO'}, "Manual Stacks: Unstacked")

        # else:
        #     self.report({'INFO'}, ZuvLabels.OT_ZMS_COLLECT_STACK_MSG)
        return {'FINISHED'}


if __name__ == "__main__":
    pass
