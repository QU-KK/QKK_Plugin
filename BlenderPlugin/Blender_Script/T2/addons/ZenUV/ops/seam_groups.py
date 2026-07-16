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

""" Zen Seam Groups System """
import bpy
import bmesh
from bpy.types import (
    UIList,
    Operator,
    Panel
)
from bpy.props import StringProperty
from ZenUV.utils.generic import (
    ZUV_PANEL_CATEGORY,
    ZUV_REGION_TYPE,
    ZUV_SPACE_TYPE,
    resort_by_type_mesh_in_edit_mode_and_sel
)
from ZenUV.ui.labels import ZuvLabels
from ZenUV.ico import icon_get
from ZenUV.prop.zuv_preferences import get_prefs
from ZenUV.prop.common import get_combo_panel_order
from ZenUV.ui.ui_call import popup_areas

from ZenUV.utils.mark_utils import ObjMarkState


class SeamGroupsProcessor:

    @classmethod
    def enshure_seam_layer(cls, bm, seam_layer_name):
        """ Return layer int type or create new """
        layer = bm.edges.layers.int.get(seam_layer_name)
        if not layer:
            layer = bm.edges.layers.int.new(seam_layer_name)
        return layer

    @classmethod
    def set_seams_to_group(cls, bm, _layer):
        for edge in bm.edges:
            edge[_layer] = edge.seam

    @classmethod
    def get_seams_from_group(cls, bm, _layer):
        for edge in bm.edges:
            edge.seam = edge[_layer]

    @classmethod
    def matching_groups(cls, name, objs):
        # print(f"Input data: {name}")
        for obj in objs:
            f_name, out_index = cls.find_indexes_in_obj(name, obj)
            # print(f"output: f_name: {f_name}, out_index: {out_index}")
            if not f_name:
                out_index = len(obj.zen_sg_list) + 1
            obj.zsg_list_index = out_index

    @classmethod
    def find_indexes_in_obj(cls, name, obj):
        f_name = None
        out_index = None
        list_index = 0
        for item in obj.zen_sg_list:
            if not f_name and item.layer_name == name:
                f_name = name
                out_index = list_index
            list_index += 1
        return f_name, out_index

    @classmethod
    def assign_all_seams_to_group(cls, context, objs):
        ob = context.active_object
        if not len(ob.zen_sg_list):
            bpy.ops.zen_sg_list.new_item()

        list_index = ob.zsg_list_index
        init_name = ob.zen_sg_list[list_index].name
        init_layer_name = ob.zen_sg_list[list_index].layer_name

        if list_index in range(len(ob.zen_sg_list)):
            cls.matching_groups(ob.zen_sg_list[list_index].layer_name, objs)

        for obj in objs:
            if list_index in range(len(obj.zen_sg_list)):
                layer_name = obj.zen_sg_list[list_index].layer_name
                cls.assign_to_group(layer_name, obj)
            else:
                obj.zen_sg_list.add()
                obj.zen_sg_list[-1].name = init_name
                obj.zen_sg_list[-1].layer_name = init_layer_name
                obj.zsg_list_index = len(ob.zen_sg_list) - 1
                cls.assign_to_group(init_layer_name, obj)

    @classmethod
    def assign_to_group(cls, layer_name, obj):
        me = obj.data
        bm = bmesh.from_edit_mesh(me)
        s_layer = cls.enshure_seam_layer(bm, seam_layer_name=layer_name)
        cls.set_seams_to_group(bm, s_layer)
        bmesh.update_edit_mesh(me, loop_triangles=False)

    @classmethod
    def assign_particular_seams_to_group(cls, context, mark_objs: list):
        if not len(mark_objs):
            return

        ob = context.active_object
        if not len(ob.zen_sg_list):
            bpy.ops.zen_sg_list.new_item()

        list_index = ob.zsg_list_index
        init_name = ob.zen_sg_list[list_index].name
        init_layer_name = ob.zen_sg_list[list_index].layer_name

        if list_index in range(len(ob.zen_sg_list)):
            cls.matching_groups_in_mark_objs(ob.zen_sg_list[list_index].layer_name, mark_objs)

        for mark_obj in mark_objs:
            obj = mark_obj.bl_object
            if list_index in range(len(obj.zen_sg_list)):
                layer_name = obj.zen_sg_list[list_index].layer_name
            else:
                obj.zen_sg_list.add()
                obj.zen_sg_list[-1].name = init_name
                obj.zen_sg_list[-1].layer_name = init_layer_name
                obj.zsg_list_index = len(ob.zen_sg_list) - 1
                layer_name = init_layer_name

            seam_layer = cls.enshure_seam_layer(mark_obj.bm, seam_layer_name=layer_name)
            cls.set_particular_seams_to_group(mark_obj, seam_layer)

    @classmethod
    def set_particular_seams_to_group(cls, mark_obj: ObjMarkState, _layer):
        for i in mark_obj.edges:
            p_edge = mark_obj.bm.edges[i]
            p_edge[_layer] = True

        if mark_obj.b_is_remove_inside:
            for i in mark_obj.edges_inside:
                p_edge = mark_obj.bm.edges[i]
                p_edge[_layer] = False

    @classmethod
    def matching_groups_in_mark_objs(cls, name: str, mark_objs: list):
        mark_obj: ObjMarkState = None
        for mark_obj in mark_objs:
            obj = mark_obj.bl_object
            f_name, out_index = cls.find_indexes_in_obj(name, obj)
            if not f_name:
                out_index = len(obj.zen_sg_list) + 1
            obj.zsg_list_index = out_index


class ZSGListGroup(bpy.types.PropertyGroup):
    """
    Group of properties representing
    an item in the zen seam groups.
    """

    name: StringProperty(
        name="Name",
        description="A name for this item",
        default="Seams"
    )

    layer_name: StringProperty(
        name="",
        description="",
        default=""
    )


class ZSG_UL_List(UIList):
    ''' Zen Seam Groups UIList '''
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        ''' @Draw Seam Groups UIList '''
        custom_icon = 'OBJECT_DATAMODE'

        act_idx = getattr(active_data, active_propname)
        b_active = index == act_idx

        b_emboss = (context.area.as_pointer() in popup_areas) and b_active

        # Make sure code supports all 3 layout types
        if self.layout_type in {'DEFAULT', 'COMPACT'}:
            layout.prop(item, "name", text="", emboss=b_emboss, icon=custom_icon)

        elif self.layout_type in {'GRID'}:
            layout.alignment = 'CENTER'
            layout.prop(text="", emboss=b_emboss, icon=custom_icon)


class ZUV_PT_ZenSeamsGroups(Panel):
    """  Zen Seam Groups Panel """
    bl_label = ZuvLabels.PT_SEAMS_GROUP_LABEL
    bl_space_type = ZUV_SPACE_TYPE
    bl_region_type = ZUV_REGION_TYPE
    bl_category = ZUV_PANEL_CATEGORY
    bl_order = get_combo_panel_order('VIEW_3D', 'ZUV_PT_ZenSeamsGroups')
    bl_options = {'DEFAULT_CLOSED'}

    zen_icon_value = 'pn_SeamsGroups'

    @classmethod
    def get_icon(cls):
        return icon_get(cls.zen_icon_value)

    @classmethod
    def poll(cls, context):
        addon_prefs = get_prefs()
        return addon_prefs.float_VIEW_3D_panels.enable_pt_seam_group and cls.combo_poll(context)

    @classmethod
    def combo_poll(cls, context: bpy.types.Context):
        return context.mode == 'EDIT_MESH'

    @classmethod
    def poll_reason(cls, context: bpy.types.Context):
        return 'Available in Edit Mode'

    def draw(self, context):
        layout = self.layout
        ob = context.object

        row = layout.row()
        col = row.column()
        col.template_list(
            "ZSG_UL_List",
            "name",
            ob,
            "zen_sg_list",
            ob,
            "zsg_list_index",
            rows=5
        )

        col = row.column(align=True)
        col.operator(ZSG_OT_NewItem.bl_idname, text="", icon='ADD')
        col.operator(ZSG_OT_DeleteItem.bl_idname, text="", icon='REMOVE')
        col.separator()

        row = layout.row(align=True)
        row.operator(ZUV_OT_AssignSelectionToGroup.bl_idname, text='Assign Selection', icon='IMPORT').action = 'ASSIGN'
        row.operator(ZUV_OT_AssignSelectionToGroup.bl_idname, text='Remove Selection', icon='EXPORT').action = 'REMOVE'

        # col.operator(ZSG_OT_MoveItem.bl_idname, text="", icon='TRIA_UP').direction = 'UP'
        # col.operator(ZSG_OT_MoveItem.bl_idname, text="", icon='TRIA_DOWN').direction = 'DOWN'

        row = layout.row()
        row.operator(ZSG_OT_AssignToGroup.bl_idname)
        row.operator(ZSG_OT_ActivateGroup.bl_idname)


class ZSG_OT_NewItem(Operator):
    """Add a new item to the list."""
    bl_description = ZuvLabels.OT_SGL_NEW_ITEM_DESC
    bl_idname = "zen_sg_list.new_item"
    bl_label = ZuvLabels.OT_SGL_NEW_ITEM_LABEL
    bl_options = {'INTERNAL'}

    @classmethod
    def poll(cls, context):
        """ Validate context """
        active_object = context.active_object
        return active_object is not None and active_object.type == 'MESH' and context.mode == 'EDIT_MESH'

    def execute(self, context):
        objs = resort_by_type_mesh_in_edit_mode_and_sel(context)
        if not objs:
            self.report({'WARNING'}, "There are no selected objects")
            return {'CANCELLED'}
        for obj in objs:
            obj.zen_sg_list.add()
            name = "Seams"
            _layer_name = "zen_seam_grp"
            i = 1
            while _layer_name in [obj.zen_sg_list[i].layer_name for i in range(len(obj.zen_sg_list))]:
                name = "Seams_{0}".format(str(i))
                _layer_name = "zen_seam_grp_{0}".format(str(i))
                i = i + 1

            obj.zen_sg_list[-1].name = name
            obj.zen_sg_list[-1].layer_name = _layer_name
            obj.zsg_list_index = len(obj.zen_sg_list) - 1

            me = obj.data
            bm = bmesh.from_edit_mesh(me)
            s_layer = bm.edges.layers.int.new(_layer_name)
            SeamGroupsProcessor.set_seams_to_group(bm, s_layer)
            bmesh.update_edit_mesh(me, loop_triangles=False)
        return {'FINISHED'}


class ZSG_OT_DeleteItem(Operator):
    """Delete the selected item from the list."""
    bl_description = ZuvLabels.OT_SGL_DEL_ITEM_DESC
    bl_idname = "zen_sg_list.delete_item"
    bl_label = ZuvLabels.OT_SGL_DEL_ITEM_LABEL
    bl_options = {'INTERNAL'}

    @classmethod
    def poll(cls, context):
        """ Validate context """
        active_object = context.active_object
        return active_object is not None and active_object.type == 'MESH' and context.mode == 'EDIT_MESH' and active_object.zen_sg_list

    def execute(self, context):
        objs = resort_by_type_mesh_in_edit_mode_and_sel(context)
        if not objs:
            self.report({'WARNING'}, "There are no selected objects")
            return {'CANCELLED'}
        ob = context.active_object
        list_index = ob.zsg_list_index
        init_layer_name = ob.zen_sg_list[list_index].layer_name
        if list_index in range(len(ob.zen_sg_list)):
            SeamGroupsProcessor.matching_groups(ob.zen_sg_list[list_index].layer_name, objs)
        for obj in objs:
            me = obj.data
            bm = bmesh.from_edit_mesh(me)
            layer = bm.edges.layers.int.get(init_layer_name)
            if layer:
                bm.edges.layers.int.remove(layer)

            zen_sg_list = obj.zen_sg_list
            index = obj.zsg_list_index
            if index in range(len(ob.zen_sg_list)):
                zen_sg_list.remove(index)
                obj.zsg_list_index = min(max(0, index - 1), len(zen_sg_list) - 1)

        return {'FINISHED'}


class ZSG_OT_MoveItem(Operator):
    """Move an item in the list."""
    bl_description = ZuvLabels.OT_SGL_MOVE_ITEM_DESC
    bl_idname = "zen_sg_list.move_item"
    bl_label = ZuvLabels.OT_SGL_MOVE_ITEM_LABEL
    bl_options = {'INTERNAL'}

    @classmethod
    def poll(cls, context):
        """ Validate context """
        active_object = context.active_object
        return active_object is not None and active_object.type == 'MESH' and context.mode == 'EDIT_MESH' and active_object.zen_sg_list

    direction: bpy.props.EnumProperty(
        items=(
            ('UP', 'Up', ""),
            ('DOWN', 'Down', ""),
        )
    )

    def move_index(self, context):
        """ Move index of an item render queue while clamping it. """
        index = context.object.zsg_list_index
        list_length = len(context.object.zen_sg_list) - 1
        # (index starts at 0)
        new_index = index + (-1 if self.direction == 'UP' else 1)
        context.object.zsg_list_index = max(0, min(new_index, list_length))

    def execute(self, context):
        zen_sg_list = context.object.zen_sg_list
        index = context.object.zsg_list_index
        neighbor = index + (-1 if self.direction == 'UP' else 1)
        zen_sg_list.move(neighbor, index)
        self.move_index()
        return {'FINISHED'}


class ZSG_OT_AssignToGroup(bpy.types.Operator):
    """ Assign current seams to selected seam group """
    bl_description = ZuvLabels.OT_SGL_ASSIGN_ITEM_DESC
    bl_idname = "uv.zenuv_assign_seam_to_group"
    bl_label = ZuvLabels.OT_SGL_ASSIGN_ITEM_LABEL
    bl_options = {'INTERNAL'}

    @classmethod
    def poll(cls, context):
        """ Validate context """
        active_object = context.active_object
        return active_object is not None and active_object.type == 'MESH' and context.mode == 'EDIT_MESH'

    def execute(self, context):
        objs = resort_by_type_mesh_in_edit_mode_and_sel(context)
        if not objs:
            self.report({'WARNING'}, "There are no selected objects")
            return {'CANCELLED'}
        SeamGroupsProcessor.assign_all_seams_to_group(context, objs)
        return {'FINISHED'}


class ZSG_OT_ActivateGroup(bpy.types.Operator):
    """ Set Seams from active group to current object seams. """
    bl_description = ZuvLabels.OT_SGL_ACTIVATE_ITEM_DESC
    bl_idname = "uv.zenuv_activate_seam_group"
    bl_label = ZuvLabels.OT_SGL_ACTIVATE_ITEM_LABEL
    bl_options = {'INTERNAL'}

    @classmethod
    def poll(cls, context):
        """ Validate context """
        active_object = context.active_object
        return active_object is not None and active_object.type == 'MESH' and context.mode == 'EDIT_MESH'

    def execute(self, context):
        objs = resort_by_type_mesh_in_edit_mode_and_sel(context)
        if not objs:
            self.report({'WARNING'}, "There are no selected objects")
            return {'CANCELLED'}

        ob = context.active_object
        list_index = ob.zsg_list_index
        if list_index in range(len(ob.zen_sg_list)):
            SeamGroupsProcessor.matching_groups(ob.zen_sg_list[list_index].layer_name, objs)

        for obj in objs:
            if obj.zsg_list_index in range(len(obj.zen_sg_list)):
                p_seams_layer_name = obj.zen_sg_list[obj.zsg_list_index].layer_name
                me = obj.data
                bm = bmesh.from_edit_mesh(me)
                s_layer = SeamGroupsProcessor.enshure_seam_layer(bm, seam_layer_name=p_seams_layer_name)
                SeamGroupsProcessor.get_seams_from_group(bm, s_layer)
                bmesh.update_edit_mesh(me, loop_triangles=False, destructive=False)

        return {'FINISHED'}


class ZUV_OT_AssignSelectionToGroup(bpy.types.Operator):

    bl_idname = "uv.zenuv_assign_selection_to_group"
    bl_label = 'Assign Selection To Group'
    bl_description = 'Creates seams from the selection and assigns them to the active group'
    bl_options = {'REGISTER', 'UNDO'}

    action: bpy.props.EnumProperty(
        name='Action',
        description='Action to be performed',
        items=[
            ("ASSIGN", "Assign", "Assign a selection to the active group"),
            ("REMOVE", "Remove", "Remove a selection from an active group")
            ],
        default='ASSIGN')

    markSeamEdges: bpy.props.BoolProperty(
        name="Mark Seams",
        description="Automatically assign Seams",
        default=True)

    markSharpEdges: bpy.props.BoolProperty(
        name="Mark Sharp Edges",
        description="Automatically assign Sharp edges",
        default=False)

    clear_inside: bpy.props.BoolProperty(
        name="Clear Inside",
        description="Clear marking inside of selected faces",
        default=True)

    def draw(self, context):
        layout = self.layout
        self.layout.prop(self, 'action')

        state = 'MARK'
        if state == 'UNMARK':
            seam_label = 'Unmark Seams'
            sharp_label = 'Unmark Sharp Edges'
        else:
            seam_label = 'Mark Seams'
            sharp_label = 'Mark Sharp Edges'

        addon_prefs = context.preferences.addons[ZuvLabels.ADDON_NAME].preferences
        layout.prop(self, 'clear_inside')
        mark_box = layout.box()
        s_mark_settings = 'Mark Settings'
        s_mark_settings += ' (Global Mode)' if addon_prefs.useGlobalMarkSettings else ' (Local Mode)'
        mark_box.label(text=s_mark_settings)

        row = mark_box.row(align=True)
        if not addon_prefs.useGlobalMarkSettings:
            row.prop(self, 'markSeamEdges', text=seam_label)
            row.prop(self, 'markSharpEdges', text=sharp_label)
        else:
            row.enabled = False
            row.prop(addon_prefs, "markSeamEdges")
            row.prop(addon_prefs, "markSharpEdges")

    @classmethod
    def description(cls, context, properties):
        if properties:
            if properties.action == 'REMOVE':
                return 'Removes seams based on selection from the active group'
        else:
            return cls.bl_description

    @classmethod
    def poll(cls, context):
        """ Validate context """
        active_object = context.active_object
        return active_object is not None and active_object.type == 'MESH' and context.mode == 'EDIT_MESH'

    def execute(self, context):
        from ZenUV.utils.mark_utils import (
            MarkStateManager,
            MarkFactory)

        objs = resort_by_type_mesh_in_edit_mode_and_sel(context)
        if not objs:
            self.report({'WARNING'}, "There are no selected objects")
            return {'CANCELLED'}

        MarkFactory.initialize()

        b_set_seam, b_set_sharp = MarkStateManager(context).get_state_from_generic_operator(self.markSeamEdges, self.markSharpEdges)

        if not b_set_seam and not b_set_sharp:
            return {'FINISHED'}

        p_objs = MarkFactory.collect_mark_objects(objs)

        MarkFactory.mark_edges(
            p_objs,
            b_set_seam,
            b_set_sharp,
            is_switch=False,
            is_assign=self.action == 'ASSIGN',
            is_remove_inside=self.clear_inside,
            is_silent_mode=False
        )
        if MarkFactory.message != '':
            self.report({'WARNING'}, message=MarkFactory.message)

        if MarkFactory.raise_popup:
            bpy.ops.wm.call_menu(name=MarkFactory.popup_name)

        SeamGroupsProcessor.assign_particular_seams_to_group(context, p_objs)

        return {'FINISHED'}


seam_groups_classes = (
    ZSG_UL_List,
    ZSGListGroup,
    ZSG_OT_NewItem,
    ZSG_OT_DeleteItem,
    # ZSG_OT_MoveItem,
    ZSG_OT_AssignToGroup,
    ZSG_OT_ActivateGroup,
    ZUV_OT_AssignSelectionToGroup

)

if __name__ == "__main__":
    pass
