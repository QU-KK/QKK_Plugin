# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTIBILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU
# General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program. If not, see <http://www.gnu.org/licenses/>.

bl_info = {
    "name" : "Operation_v3",
    "author" : "渠奎奎", 
    "description" : "操作方式4.2",
    "blender" : (4, 2, 0),
    "version" : (3, 0, 0),
    "location" : "",
    "warning" : "",
    "doc_url": "", 
    "tracker_url": "", 
    "category" : "A_工具插件" 
}


import bpy
import bpy.utils.previews
import blf
import os
import mathutils




def string_to_int(value):
    if value.isdigit():
        return int(value)
    return 0


def string_to_icon(value):
    if value in bpy.types.UILayout.bl_rna.functions["prop"].parameters["icon"].enum_items.keys():
        return bpy.types.UILayout.bl_rna.functions["prop"].parameters["icon"].enum_items[value].value
    return string_to_int(value)


addon_keymaps = {}
_icons = None
handler_6F16E = []


def region_by_type(area, region_type):
    for region in area.regions:
        if region.type == region_type:
            return region
    return area.regions[0]


class SNA_OT_My_Generic_Operator_41Ea1(bpy.types.Operator):
    bl_idname = "sna.my_generic_operator_41ea1"
    bl_label = "关闭顶点焊接"
    bl_description = "关闭顶点焊接"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        if bpy.app.version >= (3, 0, 0) and False:
            cls.poll_message_set()
        return not False

    def execute(self, context):
        bpy.context.scene.tool_settings.use_snap = False
        bpy.context.scene.tool_settings.use_mesh_automerge = False
        for i_B7A11 in range(2):
            if handler_6F16E:
                bpy.types.SpaceView3D.draw_handler_remove(handler_6F16E[0], 'WINDOW')
                handler_6F16E.pop(0)
                for a in bpy.context.screen.areas: a.tag_redraw()
        return {"FINISHED"}

    def invoke(self, context, event):
        return self.execute(context)


class SNA_OT_My_Generic_Operator_5B029(bpy.types.Operator):
    bl_idname = "sna.my_generic_operator_5b029"
    bl_label = "顶点焊接"
    bl_description = "顶点焊接"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        if bpy.app.version >= (3, 0, 0) and False:
            cls.poll_message_set()
        return not False

    def execute(self, context):
        bpy.context.scene.tool_settings.use_mesh_automerge = True
        bpy.context.scene.tool_settings.use_snap = True
        bpy.context.scene.tool_settings.snap_elements = {'VERTEX'}
        bpy.context.scene.tool_settings.snap_target = 'ACTIVE'
        bpy.context.scene.tool_settings.use_snap_translate = True
        handler_6F16E.append(bpy.types.SpaceView3D.draw_handler_add(sna_draw_vex_ex_51BA6, (), 'WINDOW', 'POST_PIXEL'))
        for a in bpy.context.screen.areas: a.tag_redraw()
        return {"FINISHED"}

    def invoke(self, context, event):
        return self.execute(context)


class SNA_OT_My_Generic_Operator_28Df2(bpy.types.Operator):
    bl_idname = "sna.my_generic_operator_28df2"
    bl_label = "软边"
    bl_description = ""
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        if bpy.app.version >= (3, 0, 0) and False:
            cls.poll_message_set()
        return not False

    def execute(self, context):
        bpy.ops.mesh.mark_sharp('INVOKE_DEFAULT', clear=True)
        bpy.ops.mesh.average_normals('INVOKE_DEFAULT', )
        return {"FINISHED"}

    def invoke(self, context, event):
        return self.execute(context)


class SNA_MT_3E602(bpy.types.Menu):
    bl_idname = "SNA_MT_3E602"
    bl_label = "(Qkk_3DMode)MeshShift右键_线"

    @classmethod
    def poll(cls, context):
        return not (((not 'EDIT_MESH'==bpy.context.mode) or  not bpy.context.tool_settings.mesh_select_mode[1]))

    def draw(self, context):
        layout = self.layout.menu_pie()
        op = layout.operator('mesh.fill_holes', text='填充洞', icon_value=string_to_icon('CLIPUV_DEHLT'), emboss=True, depress=False)
        op.sides = 0
        op = layout.operator('mesh.mark_sharp', text='软边', icon_value=string_to_icon('SPHERECURVE'), emboss=True, depress=False)
        op.clear = True
        box_BD852 = layout.box()
        box_BD852.alert = False
        box_BD852.enabled = True
        box_BD852.active = True
        box_BD852.use_property_split = False
        box_BD852.use_property_decorate = False
        box_BD852.alignment = 'Expand'.upper()
        box_BD852.scale_x = 1.0
        box_BD852.scale_y = 1.0
        if not True: box_BD852.operator_context = "EXEC_DEFAULT"
        col_B2AD6 = box_BD852.column(heading='', align=True)
        col_B2AD6.alert = False
        col_B2AD6.enabled = True
        col_B2AD6.active = True
        col_B2AD6.use_property_split = False
        col_B2AD6.use_property_decorate = False
        col_B2AD6.scale_x = 1.100000023841858
        col_B2AD6.scale_y = 1.5
        col_B2AD6.alignment = 'Expand'.upper()
        col_B2AD6.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
        layout_function = col_B2AD6
        sna_func_8F9A2(layout_function, )
        box_A63F4 = col_B2AD6.box()
        box_A63F4.alert = False
        box_A63F4.enabled = True
        box_A63F4.active = True
        box_A63F4.use_property_split = False
        box_A63F4.use_property_decorate = False
        box_A63F4.alignment = 'Expand'.upper()
        box_A63F4.scale_x = 1.0
        box_A63F4.scale_y = 1.0
        if not True: box_A63F4.operator_context = "EXEC_DEFAULT"
        col_7EA5C = box_A63F4.column(heading='', align=True)
        col_7EA5C.alert = False
        col_7EA5C.enabled = True
        col_7EA5C.active = True
        col_7EA5C.use_property_split = False
        col_7EA5C.use_property_decorate = False
        col_7EA5C.scale_x = 1.0
        col_7EA5C.scale_y = 1.0
        col_7EA5C.alignment = 'Expand'.upper()
        col_7EA5C.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
        op = col_7EA5C.operator('mesh.bevel', text='    倒角  ', icon_value=string_to_icon('MOD_BEVEL'), emboss=True, depress=False)
        op.segments = 0
        op.affect = 'EDGES'
        op = col_7EA5C.operator('mesh.subdivide', text='    细分', icon_value=string_to_icon('SPLIT_HORIZONTAL'), emboss=True, depress=False)
        op.number_cuts = 1
        op = col_7EA5C.operator('transform.edge_slide', text='    滑动', icon_value=string_to_icon('ARROW_LEFTRIGHT'), emboss=True, depress=False)
        op = col_7EA5C.operator('mesh.offset_edge_loops_slide', text='    拆段', icon_value=string_to_icon('COLLAPSEMENU'), emboss=True, depress=False)
        op = col_7EA5C.operator('mesh.set_edge_flow', text='    边流', icon_value=string_to_icon('MOD_SMOOTH'), emboss=True, depress=False)
        col_B2AD6.menu('SNA_MT_147F3', text='      元素', icon_value=132)
        op = layout.operator('view3d.edit_mesh_extrude_move_normal', text='挤出边', icon_value=string_to_icon('EMPTY_SINGLE_ARROW'), emboss=True, depress=False)
        op = layout.operator('mesh.merge', text='并排合并', icon_value=string_to_icon('COLLAPSEMENU'), emboss=True, depress=False)
        op.type = 'COLLAPSE'
        op = layout.operator('mesh.bridge_edge_loops', text='桥接', icon_value=string_to_icon('RIGID_BODY'), emboss=True, depress=False)
        op = layout.operator('mesh.dissolve_edges', text='删边', icon_value=string_to_icon('NOCURVE'), emboss=True, depress=False)
        op = layout.operator('mesh.mark_sharp', text='硬边', icon_value=string_to_icon('IPO_CONSTANT'), emboss=True, depress=False)
        op.clear = False


class SNA_MT_C2C6C(bpy.types.Menu):
    bl_idname = "SNA_MT_C2C6C"
    bl_label = "(Qkk_3DMode)MeshShift右键_面"

    @classmethod
    def poll(cls, context):
        return not (((not 'EDIT_MESH'==bpy.context.mode) or  not bpy.context.tool_settings.mesh_select_mode[2]))

    def draw(self, context):
        layout = self.layout.menu_pie()
        op = layout.operator('mesh.flip_normals', text='翻转法线', icon_value=string_to_icon('CON_ROTLIMIT'), emboss=True, depress=False)
        op.only_clnors = False
        op = layout.operator('view3d.edit_mesh_extrude_move_normal', text='挤出面', icon_value=string_to_icon('LIGHT_AREA'), emboss=True, depress=False)
        box_9E5EF = layout.box()
        box_9E5EF.alert = False
        box_9E5EF.enabled = True
        box_9E5EF.active = True
        box_9E5EF.use_property_split = False
        box_9E5EF.use_property_decorate = False
        box_9E5EF.alignment = 'Expand'.upper()
        box_9E5EF.scale_x = 1.0
        box_9E5EF.scale_y = 1.0
        if not True: box_9E5EF.operator_context = "EXEC_DEFAULT"
        col_1F782 = box_9E5EF.column(heading='', align=True)
        col_1F782.alert = False
        col_1F782.enabled = True
        col_1F782.active = True
        col_1F782.use_property_split = False
        col_1F782.use_property_decorate = False
        col_1F782.scale_x = 1.100000023841858
        col_1F782.scale_y = 1.5
        col_1F782.alignment = 'Expand'.upper()
        col_1F782.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
        layout_function = col_1F782
        sna_func_8F9A2(layout_function, )
        box_3AE55 = col_1F782.box()
        box_3AE55.alert = False
        box_3AE55.enabled = True
        box_3AE55.active = True
        box_3AE55.use_property_split = False
        box_3AE55.use_property_decorate = False
        box_3AE55.alignment = 'Expand'.upper()
        box_3AE55.scale_x = 1.0
        box_3AE55.scale_y = 1.0
        if not True: box_3AE55.operator_context = "EXEC_DEFAULT"
        col_D6B36 = box_3AE55.column(heading='', align=True)
        col_D6B36.alert = False
        col_D6B36.enabled = True
        col_D6B36.active = True
        col_D6B36.use_property_split = False
        col_D6B36.use_property_decorate = False
        col_D6B36.scale_x = 1.0
        col_D6B36.scale_y = 1.0
        col_D6B36.alignment = 'Expand'.upper()
        col_D6B36.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
        row_0D5B6 = col_D6B36.row(heading='', align=True)
        row_0D5B6.alert = False
        row_0D5B6.enabled = True
        row_0D5B6.active = True
        row_0D5B6.use_property_split = False
        row_0D5B6.use_property_decorate = False
        row_0D5B6.scale_x = 0.6000000238418579
        row_0D5B6.scale_y = 1.0
        row_0D5B6.alignment = 'Expand'.upper()
        row_0D5B6.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
        op = row_0D5B6.operator('mesh.bevel', text=' ', icon_value=string_to_icon('MOD_BEVEL'), emboss=True, depress=False)
        op.segments = 0
        op.affect = 'EDGES'
        op = row_0D5B6.operator('view3d.edit_mesh_extrude_move_shrink_fatten', text=' ', icon_value=string_to_icon('NORMALS_FACE'), emboss=True, depress=False)
        op = row_0D5B6.operator('mesh.extrude_faces_move', text=' ', icon_value=string_to_icon('MOD_EDGESPLIT'), emboss=True, depress=False)
        op = col_D6B36.operator('mesh.looptools_circle', text='    圆环    ', icon_value=string_to_icon('SEQ_CHROMA_SCOPE'), emboss=True, depress=False)
        if False:
            box_72921 = col_1F782.box()
            box_72921.alert = False
            box_72921.enabled = True
            box_72921.active = True
            box_72921.use_property_split = False
            box_72921.use_property_decorate = False
            box_72921.alignment = 'Expand'.upper()
            box_72921.scale_x = 1.0
            box_72921.scale_y = 1.0
            if not True: box_72921.operator_context = "EXEC_DEFAULT"
            col_B89B3 = box_72921.column(heading='', align=True)
            col_B89B3.alert = False
            col_B89B3.enabled = True
            col_B89B3.active = True
            col_B89B3.use_property_split = False
            col_B89B3.use_property_decorate = False
            col_B89B3.scale_x = 1.0
            col_B89B3.scale_y = 1.0
            col_B89B3.alignment = 'Expand'.upper()
            col_B89B3.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
            split_16A1F = col_B89B3.split(factor=0.5, align=True)
            split_16A1F.alert = False
            split_16A1F.enabled = True
            split_16A1F.active = True
            split_16A1F.use_property_split = False
            split_16A1F.use_property_decorate = False
            split_16A1F.scale_x = 0.5
            split_16A1F.scale_y = 1.0
            split_16A1F.alignment = 'Expand'.upper()
            if not True: split_16A1F.operator_context = "EXEC_DEFAULT"
            op = split_16A1F.operator('machin3.change_width', text='宽度', icon_value=0, emboss=True, depress=False)
            op = split_16A1F.operator('machin3.unchamfer', text='反平', icon_value=0, emboss=True, depress=False)
            split_FD985 = col_B89B3.split(factor=0.5, align=True)
            split_FD985.alert = False
            split_FD985.enabled = True
            split_FD985.active = True
            split_FD985.use_property_split = False
            split_FD985.use_property_decorate = False
            split_FD985.scale_x = 0.5
            split_FD985.scale_y = 1.0
            split_FD985.alignment = 'Expand'.upper()
            if not True: split_FD985.operator_context = "EXEC_DEFAULT"
            op = split_FD985.operator('machin3.fuse', text='融接', icon_value=0, emboss=True, depress=False)
            op.segments = 2
            op = split_FD985.operator('machin3.unbevel', text='取消', icon_value=0, emboss=True, depress=False)
        box_6FB2F = col_1F782.box()
        box_6FB2F.alert = False
        box_6FB2F.enabled = True
        box_6FB2F.active = True
        box_6FB2F.use_property_split = False
        box_6FB2F.use_property_decorate = False
        box_6FB2F.alignment = 'Expand'.upper()
        box_6FB2F.scale_x = 1.0
        box_6FB2F.scale_y = 1.0
        if not True: box_6FB2F.operator_context = "EXEC_DEFAULT"
        split_FC9B6 = box_6FB2F.split(factor=0.5, align=True)
        split_FC9B6.alert = False
        split_FC9B6.enabled = True
        split_FC9B6.active = True
        split_FC9B6.use_property_split = False
        split_FC9B6.use_property_decorate = False
        split_FC9B6.scale_x = 0.5
        split_FC9B6.scale_y = 1.0
        split_FC9B6.alignment = 'Expand'.upper()
        if not True: split_FC9B6.operator_context = "EXEC_DEFAULT"
        op = split_FC9B6.operator('mesh.quads_convert_to_tris', text='三角', icon_value=0, emboss=True, depress=False)
        op = split_FC9B6.operator('mesh.tris_convert_to_quads', text='四边', icon_value=0, emboss=True, depress=False)
        op.face_threshold = 180.0
        op.shape_threshold = 180.0
        op.uvs = True
        op.materials = True
        col_1F782.menu('SNA_MT_C190F', text='    元素', icon_value=string_to_icon('UV_DATA'))
        op = layout.operator('mesh.merge', text='中心合并', icon_value=string_to_icon('LIGHTPROBE_PLANE'), emboss=True, depress=False)
        op.type = 'CENTER'
        op = layout.operator('mesh.normals_make_consistent', text='重算外法线', icon_value=string_to_icon('CON_LOCLIMIT'), emboss=True, depress=False)
        op.inside = False
        op = layout.operator('transform.push_pull', text='推拉', icon_value=string_to_icon('ARROW_LEFTRIGHT'), emboss=False, depress=False)
        op = layout.operator('mesh.delete', text='删面', icon_value=string_to_icon('MESH_PLANE'), emboss=True, depress=False)
        op.type = 'FACE'
        op = layout.operator('mesh.inset', text='内插', icon_value=string_to_icon('FULLSCREEN_EXIT'), emboss=True, depress=False)


class SNA_MT_396C5(bpy.types.Menu):
    bl_idname = "SNA_MT_396C5"
    bl_label = "(Qkk_3DMode)MeshShift右键_点"

    @classmethod
    def poll(cls, context):
        return not (((not 'EDIT_MESH'==bpy.context.mode) or  not bpy.context.tool_settings.mesh_select_mode[0]))

    def draw(self, context):
        layout = self.layout.menu_pie()
        op = layout.operator('mesh.extrude_vertices_move', text='挤出点', icon_value=string_to_icon('PARTICLE_TIP'), emboss=True, depress=False)
        op = layout.operator('transform.vert_slide', text='滑动', icon_value=string_to_icon('MOD_SIMPLIFY'), emboss=True, depress=False)
        box_E71F5 = layout.box()
        box_E71F5.alert = False
        box_E71F5.enabled = True
        box_E71F5.active = True
        box_E71F5.use_property_split = False
        box_E71F5.use_property_decorate = False
        box_E71F5.alignment = 'Expand'.upper()
        box_E71F5.scale_x = 1.0
        box_E71F5.scale_y = 1.0
        if not True: box_E71F5.operator_context = "EXEC_DEFAULT"
        col_B2B15 = box_E71F5.column(heading='', align=True)
        col_B2B15.alert = False
        col_B2B15.enabled = True
        col_B2B15.active = True
        col_B2B15.use_property_split = False
        col_B2B15.use_property_decorate = False
        col_B2B15.scale_x = 1.100000023841858
        col_B2B15.scale_y = 1.5
        col_B2B15.alignment = 'Expand'.upper()
        col_B2B15.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
        layout_function = col_B2B15
        sna_func_8F9A2(layout_function, )
        box_4D9C7 = col_B2B15.box()
        box_4D9C7.alert = False
        box_4D9C7.enabled = True
        box_4D9C7.active = True
        box_4D9C7.use_property_split = False
        box_4D9C7.use_property_decorate = False
        box_4D9C7.alignment = 'Expand'.upper()
        box_4D9C7.scale_x = 1.0
        box_4D9C7.scale_y = 1.0
        if not True: box_4D9C7.operator_context = "EXEC_DEFAULT"
        col_19916 = box_4D9C7.column(heading='', align=True)
        col_19916.alert = False
        col_19916.enabled = True
        col_19916.active = True
        col_19916.use_property_split = False
        col_19916.use_property_decorate = False
        col_19916.scale_x = 1.0
        col_19916.scale_y = 1.0
        col_19916.alignment = 'Expand'.upper()
        col_19916.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
        col_85157 = col_19916.column(heading='', align=True)
        col_85157.alert = False
        col_85157.enabled = True
        col_85157.active = True
        col_85157.use_property_split = False
        col_85157.use_property_decorate = False
        col_85157.scale_x = 1.0
        col_85157.scale_y = 1.0
        col_85157.alignment = 'Expand'.upper()
        col_85157.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
        if (bpy.context.scene.tool_settings.use_mesh_automerge and bpy.context.scene.tool_settings.use_snap and bpy.context.scene.tool_settings.use_snap_translate):
            op = col_85157.operator('sna.my_generic_operator_41ea1', text='吸附焊接', icon_value=string_to_icon('TRANSFORM_ORIGINS'), emboss=True, depress=True)
        else:
            op = col_85157.operator('sna.my_generic_operator_5b029', text='吸附焊接', icon_value=string_to_icon('TRANSFORM_ORIGINS'), emboss=True, depress=False)
        op = layout.operator('mesh.bevel', text='倒角', icon_value=string_to_icon('NORMALS_VERTEX'), emboss=True, depress=False)
        op.segments = 0
        op.affect = 'VERTICES'
        op = layout.operator('mesh.remove_doubles', text='阀值焊接', icon_value=string_to_icon('SNAP_INCREMENT'), emboss=True, depress=False)
        op = layout.operator('mesh.merge', text='中心焊接', icon_value=string_to_icon('SNAP_MIDPOINT'), emboss=True, depress=False)
        op.type = 'CENTER'
        op = layout.operator('mesh.dissolve_verts', text='删点', icon_value=string_to_icon('LAYER_ACTIVE'), emboss=True, depress=False)
        op = layout.operator('mesh.vert_connect_path', text='连接', icon_value=string_to_icon('IPO_LINEAR'), emboss=True, depress=False)


class SNA_MT_C190F(bpy.types.Menu):
    bl_idname = "SNA_MT_C190F"
    bl_label = ""

    @classmethod
    def poll(cls, context):
        return not (False)

    def draw(self, context):
        layout = self.layout.column_flow(columns=1)
        layout.operator_context = "INVOKE_DEFAULT"
        col_7C3A6 = layout.column(heading='元素处理', align=False)
        col_7C3A6.alert = False
        col_7C3A6.enabled = True
        col_7C3A6.active = True
        col_7C3A6.use_property_split = False
        col_7C3A6.use_property_decorate = False
        col_7C3A6.scale_x = 1.0
        col_7C3A6.scale_y = 1.2999999523162842
        col_7C3A6.alignment = 'Expand'.upper()
        col_7C3A6.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
        op = col_7C3A6.operator('sna.my_generic_operator_6e1b4', text='复制出元素', icon_value=string_to_icon('MOD_DECIM'), emboss=True, depress=False)
        op = col_7C3A6.operator('sna.my_generic_operator_5ee82', text='拆分出元素', icon_value=string_to_icon('MOD_BUILD'), emboss=True, depress=False)
        op = col_7C3A6.operator('mesh.duplicate_move', text='复制元素', icon_value=string_to_icon('MOD_TRIANGULATE'), emboss=True, depress=False)
        op = col_7C3A6.operator('mesh.split', text='拆分元素', icon_value=string_to_icon('SEQ_STRIP_META'), emboss=True, depress=False)


class SNA_OT_My_Generic_Operator_5Ee82(bpy.types.Operator):
    bl_idname = "sna.my_generic_operator_5ee82"
    bl_label = "拆分出元素"
    bl_description = ""
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        if bpy.app.version >= (3, 0, 0) and False:
            cls.poll_message_set()
        return not False

    def execute(self, context):
        bpy.ops.mesh.separate(type='SELECTED')
        bpy.ops.object.mode_set(mode='OBJECT')
        return {"FINISHED"}

    def invoke(self, context, event):
        return self.execute(context)


class SNA_OT_My_Generic_Operator_6E1B4(bpy.types.Operator):
    bl_idname = "sna.my_generic_operator_6e1b4"
    bl_label = "复制出元素"
    bl_description = ""
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        if bpy.app.version >= (3, 0, 0) and False:
            cls.poll_message_set()
        return not False

    def execute(self, context):
        bpy.ops.mesh.duplicate_move()
        bpy.ops.mesh.separate(type='SELECTED')
        bpy.ops.object.mode_set(mode='OBJECT')
        return {"FINISHED"}

    def invoke(self, context, event):
        return self.execute(context)


class SNA_OT_My_Generic_Operator_30A9F(bpy.types.Operator):
    bl_idname = "sna.my_generic_operator_30a9f"
    bl_label = "复制出元素线"
    bl_description = ""
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        if bpy.app.version >= (3, 0, 0) and False:
            cls.poll_message_set()
        return not False

    def execute(self, context):
        bpy.ops.mesh.duplicate_move()
        bpy.ops.mesh.separate(type='SELECTED')
        bpy.ops.object.mode_set(mode='OBJECT')
        return {"FINISHED"}

    def invoke(self, context, event):
        return self.execute(context)


class SNA_MT_147F3(bpy.types.Menu):
    bl_idname = "SNA_MT_147F3"
    bl_label = ""

    @classmethod
    def poll(cls, context):
        return not (False)

    def draw(self, context):
        layout = self.layout.column_flow(columns=1)
        layout.operator_context = "INVOKE_DEFAULT"
        col_3AD34 = layout.column(heading='', align=False)
        col_3AD34.alert = False
        col_3AD34.enabled = True
        col_3AD34.active = True
        col_3AD34.use_property_split = False
        col_3AD34.use_property_decorate = False
        col_3AD34.scale_x = 1.0
        col_3AD34.scale_y = 1.2999999523162842
        col_3AD34.alignment = 'Expand'.upper()
        col_3AD34.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
        op = col_3AD34.operator('sna.my_generic_operator_30a9f', text='复制出元素', icon_value=string_to_icon('MOD_DECIM'), emboss=True, depress=False)
        op = col_3AD34.operator('mesh.duplicate_move', text='复制元素', icon_value=string_to_icon('MOD_TRIANGULATE'), emboss=True, depress=False)
        op = col_3AD34.operator('mesh.edge_split', text='断开边', icon_value=string_to_icon('REMOVE'), emboss=True, depress=False)
        op.type = 'EDGE'


class SNA_MT_BA1C6(bpy.types.Menu):
    bl_idname = "SNA_MT_BA1C6"
    bl_label = "(Qkk_3DMode)CurveShift右键"

    @classmethod
    def poll(cls, context):
        return not ((not 'EDIT_CURVE'==bpy.context.mode))

    def draw(self, context):
        layout = self.layout.menu_pie()
        op = layout.operator('curve.spline_type_set', text='曲线类型', icon_value=string_to_icon('MOD_INSTANCE'), emboss=True, depress=False)
        op = layout.operator('curve.normals_make_consistent', text='重置手柄', icon_value=string_to_icon('IPO_BEZIER'), emboss=True, depress=False)
        op = layout.operator('curve.smooth', text='光滑', icon_value=string_to_icon('SPHERECURVE'), emboss=True, depress=False)
        op = layout.operator('wm.tool_set_by_id', text='挤出', icon_value=string_to_icon('TRANSFORM_ORIGINS'), emboss=True, depress=False)
        op.name = 'builtin.extrude'


class SNA_OT_My_Generic_Operator_A4Edb(bpy.types.Operator):
    bl_idname = "sna.my_generic_operator_a4edb"
    bl_label = "建模工具"
    bl_description = "建模工具"
    bl_options = {"REGISTER", "UNDO"}
    sna_tool_name: bpy.props.StringProperty(name='tool_name', description='', options={'HIDDEN'}, default='', subtype='NONE', maxlen=0)

    @classmethod
    def poll(cls, context):
        if bpy.app.version >= (3, 0, 0) and True:
            cls.poll_message_set('')
        return not False

    def execute(self, context):
        bpy.ops.wm.tool_set_by_id(name=self.sna_tool_name)
        return {"FINISHED"}

    def invoke(self, context, event):
        return self.execute(context)


def sna_func_8F9A2(layout_function, ):
    box_167C4 = layout_function.box()
    box_167C4.alert = False
    box_167C4.enabled = True
    box_167C4.active = True
    box_167C4.use_property_split = False
    box_167C4.use_property_decorate = False
    box_167C4.alignment = 'Expand'.upper()
    box_167C4.scale_x = 1.0
    box_167C4.scale_y = 1.0
    if not True: box_167C4.operator_context = "EXEC_DEFAULT"
    row_980DE = box_167C4.row(heading='', align=True)
    row_980DE.alert = False
    row_980DE.enabled = True
    row_980DE.active = True
    row_980DE.use_property_split = False
    row_980DE.use_property_decorate = False
    row_980DE.scale_x = 0.8299999833106995
    row_980DE.scale_y = 1.0
    row_980DE.alignment = 'Expand'.upper()
    row_980DE.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
    op = row_980DE.operator('mesh.knife_tool', text=' ', icon_value=string_to_icon('RESTRICT_SELECT_ON'), emboss=True, depress=False)
    op.use_occlude_geometry = True
    op.only_selected = False
    op.wait_for_input = True
    op = row_980DE.operator('sna.my_generic_operator_a4edb', text=' ', icon_value=string_to_icon('MATSPHERE'), emboss=True, depress=False)
    op.sna_tool_name = 'builtin.loop_cut'


def sna_draw_vex_ex_51BA6():
    font_id = 0
    if r'' and os.path.exists(r''):
        font_id = blf.load(r'')
    if font_id == -1:
        print("Couldn't load font!")
    else:
        x_B491B, y_B491B = tuple(mathutils.Vector((-60.0, -60.0)) + mathutils.Vector((region_by_type(bpy.context.area, 'WINDOW').width/2, region_by_type(bpy.context.area, 'WINDOW').height)))
        blf.position(font_id, x_B491B, y_B491B, 0)
        if bpy.app.version >= (3, 4, 0):
            blf.size(font_id, 20.0)
        else:
            blf.size(font_id, 20.0, 72)
        clr = (1.0, 0.9759753942489624, 0.34133413434028625, 1.0)
        blf.color(font_id, clr[0], clr[1], clr[2], clr[3])
        if 0:
            blf.enable(font_id, blf.WORD_WRAP)
            blf.word_wrap(font_id, 0)
        if 0.0:
            blf.enable(font_id, blf.ROTATION)
            blf.rotation(font_id, 0.0)
        blf.enable(font_id, blf.WORD_WRAP)
        blf.draw(font_id, '顶点吸附中')
        blf.disable(font_id, blf.ROTATION)
        blf.disable(font_id, blf.WORD_WRAP)


def register():
    global _icons
    _icons = bpy.utils.previews.new()
    bpy.utils.register_class(SNA_OT_My_Generic_Operator_41Ea1)
    bpy.utils.register_class(SNA_OT_My_Generic_Operator_5B029)
    bpy.utils.register_class(SNA_OT_My_Generic_Operator_28Df2)
    bpy.utils.register_class(SNA_MT_3E602)
    bpy.utils.register_class(SNA_MT_C2C6C)
    bpy.utils.register_class(SNA_MT_396C5)
    bpy.utils.register_class(SNA_MT_C190F)
    bpy.utils.register_class(SNA_OT_My_Generic_Operator_5Ee82)
    bpy.utils.register_class(SNA_OT_My_Generic_Operator_6E1B4)
    bpy.utils.register_class(SNA_OT_My_Generic_Operator_30A9F)
    bpy.utils.register_class(SNA_MT_147F3)
    bpy.utils.register_class(SNA_MT_BA1C6)
    bpy.utils.register_class(SNA_OT_My_Generic_Operator_A4Edb)
    kc = bpy.context.window_manager.keyconfigs.addon
    km = kc.keymaps.new(name='3D View', space_type='VIEW_3D')
    kmi = km.keymap_items.new('wm.call_menu_pie', 'RIGHTMOUSE', 'ANY',
        ctrl=False, alt=False, shift=True, repeat=False)
    kmi.properties.name = 'SNA_MT_C2C6C'
    addon_keymaps['82E1F'] = (km, kmi)
    kc = bpy.context.window_manager.keyconfigs.addon
    km = kc.keymaps.new(name='3D View', space_type='VIEW_3D')
    kmi = km.keymap_items.new('wm.call_menu_pie', 'RIGHTMOUSE', 'ANY',
        ctrl=False, alt=False, shift=True, repeat=False)
    kmi.properties.name = 'SNA_MT_3E602'
    addon_keymaps['4B52C'] = (km, kmi)
    kc = bpy.context.window_manager.keyconfigs.addon
    km = kc.keymaps.new(name='3D View', space_type='VIEW_3D')
    kmi = km.keymap_items.new('wm.call_menu_pie', 'RIGHTMOUSE', 'ANY',
        ctrl=False, alt=False, shift=True, repeat=False)
    kmi.properties.name = 'SNA_MT_396C5'
    addon_keymaps['B9DA3'] = (km, kmi)
    kc = bpy.context.window_manager.keyconfigs.addon
    km = kc.keymaps.new(name='3D View', space_type='VIEW_3D')
    kmi = km.keymap_items.new('wm.call_menu_pie', 'RIGHTMOUSE', 'ANY',
        ctrl=False, alt=False, shift=True, repeat=False)
    kmi.properties.name = 'SNA_MT_BA1C6'
    addon_keymaps['ECC95'] = (km, kmi)


def unregister():
    global _icons
    bpy.utils.previews.remove(_icons)
    wm = bpy.context.window_manager
    kc = wm.keyconfigs.addon
    for km, kmi in addon_keymaps.values():
        km.keymap_items.remove(kmi)
    addon_keymaps.clear()
    bpy.utils.unregister_class(SNA_OT_My_Generic_Operator_41Ea1)
    bpy.utils.unregister_class(SNA_OT_My_Generic_Operator_5B029)
    if handler_6F16E:
        bpy.types.SpaceView3D.draw_handler_remove(handler_6F16E[0], 'WINDOW')
        handler_6F16E.pop(0)
    bpy.utils.unregister_class(SNA_OT_My_Generic_Operator_28Df2)
    bpy.utils.unregister_class(SNA_MT_3E602)
    bpy.utils.unregister_class(SNA_MT_C2C6C)
    bpy.utils.unregister_class(SNA_MT_396C5)
    bpy.utils.unregister_class(SNA_MT_C190F)
    bpy.utils.unregister_class(SNA_OT_My_Generic_Operator_5Ee82)
    bpy.utils.unregister_class(SNA_OT_My_Generic_Operator_6E1B4)
    bpy.utils.unregister_class(SNA_OT_My_Generic_Operator_30A9F)
    bpy.utils.unregister_class(SNA_MT_147F3)
    bpy.utils.unregister_class(SNA_MT_BA1C6)
    bpy.utils.unregister_class(SNA_OT_My_Generic_Operator_A4Edb)
