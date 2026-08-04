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
    "name" : "Assets_Check_v4",
    "author" : "渠奎奎", 
    "description" : "全量分析检查4.2_v4",
    "blender" : (4, 2, 0),
    "version" : (4, 0, 0),
    "location" : "",
    "warning" : "",
    "doc_url": "", 
    "tracker_url": "", 
    "category" : "QKK_通用" 
}


import bpy
import bpy.utils.previews
import os
import sys
import bmesh




def string_to_int(value):
    if value.isdigit():
        return int(value)
    return 0


def string_to_icon(value):
    if value in bpy.types.UILayout.bl_rna.functions["prop"].parameters["icon"].enum_items.keys():
        return bpy.types.UILayout.bl_rna.functions["prop"].parameters["icon"].enum_items[value].value
    return string_to_int(value)


def string_to_type(value, to_type, default):
    try:
        value = to_type(value)
    except:
        value = default
    return value


addon_keymaps = {}
_icons = None
node_tree_004 = {'sna_check_distorted': [], }
node_tree_005 = {'sna_check_non_fluid': False, }
uv_001 = {'sna_check_overlap_uv': False, }
ui__003 = {'sna_check_sort_switching': False, 'sna_check_sort_orientation': 0, }
node_tree_013 = {'sna_check_extend_camber_face': [], }
node_tree_014 = {'sna_check_extend_intersect_face': [], }
node_tree_015 = {'sna_check_extend_zero_side': [], }
node_tree_017 = {'sna_image_missing_names': [], }
node_tree_002 = {'sna_check_obj_lis': [], 'sna_check_obj_data_lis': [], 'sna_check_add_obj_da_list': [], 'sna_check_class_list': [], }


def property_exists(prop_path, glob, loc):
    try:
        eval(prop_path, glob, loc)
        return True
    except:
        return False


def sna_func_3938F(obj):
    return [obj.name, len(list(obj.data.loop_triangles)), len(list(obj.material_slots)), len(list(obj.data.uv_layers)), len(list(obj.data.color_attributes)), obj]


def sna_func_CF58E(obj):
    obj = obj
    check_mat_slot = None
    # 判断是否存在空的材质槽
    check_mat_slot = False
    for slot in obj.material_slots:
        if slot.material is None:
            check_mat_slot = True
            break
    return [obj, check_mat_slot]


def sna_func_7D6B7(obj):
    obj = obj
    check_image_missing = None
    check_image_quantity = None
    image_missing_names = None
    #创建一个空列表来存储图像纹理名称
    image_texture_names = []
    material_slots = obj.material_slots
    for slot in material_slots:
        if slot.material and slot.material.use_nodes:
            #遍历节点，找到使用的图像纹理名称，并添加到列表中
            for node in slot.material.node_tree.nodes:
                if node.type == 'TEX_IMAGE' and node.image:
                    image_texture_names.append(node.image.name)
                    # print("检查贴图", (node.image.name))
    check_image_quantity = len(image_texture_names)
    check_image_missing = False
    missing_name = []
    for images in image_texture_names:
        #print(images)
        image = bpy.data.images.get(images)
        # 检查图像是否存在及本地路径
        filepath = bpy.path.abspath(image.filepath)
        if os.path.exists(filepath):
            check = False
        else:
            #print("图像", images, "不存在于本地路径")
            missing_name.append(images)
            check_image_missing = True
    image_missing_names = list(set(missing_name))
    return [check_image_missing, check_image_quantity, image_missing_names, obj]


def sna_func_80448(obj):
    obj = obj
    check_ngon_face = None
    check_ngon_face = False
    for i in obj.data.polygons:
        if i.loop_total > 4:
            check_ngon_face = True
            break
    return [obj, check_ngon_face]


def sna_check_distorted_function_4C1A4(obj):
    obj = obj
    faces_distort = None
    import array

    def bmesh_copy_from_object(obj, transform=True, triangulate=True, apply_modifiers=False):
        """Returns a transformed, triangulated copy of the mesh"""
        assert obj.type == "MESH"
        if apply_modifiers and obj.modifiers:
            depsgraph = bpy.context.evaluated_depsgraph_get()
            obj_eval = obj.evaluated_get(depsgraph)
            me = obj_eval.to_mesh()
            bm = bmesh.new()
            bm.from_mesh(me)
            obj_eval.to_mesh_clear()
        else:
            me = obj.data
            if obj.mode == "EDIT":
                bm_orig = bmesh.from_edit_mesh(me)
                bm = bm_orig.copy()
            else:
                bm = bmesh.new()
                bm.from_mesh(me)
        # TODO. remove all customdata layers.
        # would save ram
        if transform:
            matrix = obj.matrix_world.copy()
            if not matrix.is_identity:
                bm.transform(matrix)
                # Update normals if the matrix has no rotation.
                matrix.translation.zero()
                if not matrix.is_identity:
                    bm.normal_update()
        if triangulate:
            bmesh.ops.triangulate(bm, faces=bm.faces)
        return bm

    def bmesh_from_object(obj):
        """Object/Edit Mode get mesh, use bmesh_to_object() to write back."""
        me = obj.data
        if obj.mode == "EDIT":
            bm = bmesh.from_edit_mesh(me)
        else:
            bm = bmesh.new()
            bm.from_mesh(me)
        return bm

    def face_is_distorted(ele, angle_distort):
        no = ele.normal
        angle_fn = no.angle
        for loop in ele.loops:
            loopno = loop.calc_normal()
            if loopno.dot(no) < 0.0:
                loopno.negate()
            if angle_fn(loopno, 1000.0) > angle_distort:
                return True
        return False
    bm = bmesh_copy_from_object(obj, transform=True, triangulate=False)
    bm.normal_update()
    faces_distort = array.array("i",(i for i, ele in enumerate(bm.faces) if face_is_distorted(ele, 0)))
    bm.free()
    return [(len(str(faces_distort).replace("array('i')", '').replace("array('i', [", '').replace('])', '')) != 0), (str(faces_distort).replace("array('i')", '').replace("array('i', [", '').replace('])', '').split(',') if (len(str(faces_distort).replace("array('i')", '').replace("array('i', [", '').replace('])', '')) != 0) else []), obj]


def sna_func_FC9F2(obj):
    node_tree_005['sna_check_non_fluid'] = False
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.mode_set(mode='EDIT', toggle=False)
    bpy.ops.mesh.select_mode(type='VERT', action='ENABLE')
    bpy.ops.mesh.select_non_manifold(extend=False, use_wire=True, use_boundary=False, use_multi_face=True, use_non_contiguous=True, use_verts=False)
    bpy.ops.object.mode_set(mode='OBJECT', toggle=False)
    for i_DDA5F in range(len(obj.data.vertices)):
        if obj.data.vertices[i_DDA5F].select:
            node_tree_005['sna_check_non_fluid'] = True
            break
    return [node_tree_005['sna_check_non_fluid'], obj]


def sna_func_68F3E(obj):
    obj = obj
    faces_intersect = None
    import array

    def bmesh_copy_from_object(obj, transform=True, triangulate=True, apply_modifiers=False):
        """Returns a transformed, triangulated copy of the mesh"""
        assert obj.type == "MESH"
        if apply_modifiers and obj.modifiers:
            depsgraph = bpy.context.evaluated_depsgraph_get()
            obj_eval = obj.evaluated_get(depsgraph)
            me = obj_eval.to_mesh()
            bm = bmesh.new()
            bm.from_mesh(me)
            obj_eval.to_mesh_clear()
        else:
            me = obj.data
            if obj.mode == "EDIT":
                bm_orig = bmesh.from_edit_mesh(me)
                bm = bm_orig.copy()
            else:
                bm = bmesh.new()
                bm.from_mesh(me)
        # TODO. remove all customdata layers.
        # would save ram
        if transform:
            matrix = obj.matrix_world.copy()
            if not matrix.is_identity:
                bm.transform(matrix)
                # Update normals if the matrix has no rotation.
                matrix.translation.zero()
                if not matrix.is_identity:
                    bm.normal_update()
        if triangulate:
            bmesh.ops.triangulate(bm, faces=bm.faces)
        return bm

    def bmesh_check_self_intersect_object(obj):
        """Check if any faces self intersect returns an array of edge index values."""
        import array
        import mathutils
        if not obj.data.polygons:
            return array.array("i", ())
        bm = bmesh_copy_from_object(obj, transform=False, triangulate=False)
        tree = mathutils.bvhtree.BVHTree.FromBMesh(bm, epsilon=0.00001)
        overlap = tree.overlap(tree)
        faces_error = {i for i_pair in overlap for i in i_pair}
        return array.array("i", faces_error)
    faces_intersect = bmesh_check_self_intersect_object(obj)
    return [(len(str(faces_intersect).replace("array('i')", '').replace("array('i', [", '').replace('])', '')) != 0), (str(faces_intersect).replace("array('i')", '').replace("array('i', [", '').replace('])', '').split(',') if (len(str(faces_intersect).replace("array('i')", '').replace("array('i', [", '').replace('])', '')) != 0) else []), obj]


def sna_func_2BE0B(obj):
    obj = obj
    check_zero_edge_list_data = None
    import bmesh
    # 获取当前选择的对象
    obj = bpy.context.object
    # 获取对象的网格数据
    mesh = obj.data
    # 创建一个bmesh实例
    bm = bmesh.new()
    bm.from_mesh(mesh)
    check_zero_edge_list_data = []
    ## 遍历每个面并计算面积
    #for face in bm.faces:
    #    area = face.calc_area()
    #    if area < 0.0001:
    #        check_zero_face_list_data.append(face.index)
    # 遍历每条边并计算长度
    for edge in bm.edges:
        length = edge.calc_length()
        if length < 0.001:
            check_zero_edge_list_data.append(edge.index)
    # 释放bmesh
    bm.free()
    return [(len(check_zero_edge_list_data) != 0), check_zero_edge_list_data, obj]


def sna_uv_C5FDA(obj):
    obj = obj
    check_quadrant_1u = None
    check_quadrant_2u = None
    mesh = obj.data
    # 初始化变量，用于判断UV是否在第一象限
    check_quadrant_1u = False
    check_quadrant_2u = False
    # 检查是否存在1U数据
    if len(mesh.uv_layers) >= 1:
        # 获取UV层的数据
        uv_layer = mesh.uv_layers[0].data
        # 遍历UV层的所有顶点
        for loop in mesh.loops:
            uv = uv_layer[loop.index].uv
            # 判断UV是否在第一象限
            if uv.x < 0 or uv.y < 0 or uv.x > 1 or uv.y > 1:
                check_quadrant_1u = True
                break    
    # 检查是否存在2U数据
    if len(mesh.uv_layers) >= 2:
        # 获取UV层的数据
        uv_layer = mesh.uv_layers[1].data
        # 遍历UV层的所有顶点
        for loop in mesh.loops:
            uv = uv_layer[loop.index].uv
            # 判断UV是否在第一象限
            if uv.x < 0 or uv.y < 0 or uv.x > 1 or uv.y > 1:
                check_quadrant_2u = True
                break
    return [check_quadrant_1u, check_quadrant_2u, obj]


def sna_uv_8B0EC(obj, uv_id):
    uv_001['sna_check_overlap_uv'] = False
    bpy.context.view_layer.objects.active = obj
    if property_exists("bpy.context.view_layer.objects.active.data.uv_layers[uv_id].data", globals(), locals()):
        bpy.context.scene.tool_settings.use_uv_select_sync = True
        #bpy.context.scene.tool_settings.use_uv_select_sync = False
        bpy.ops.object.select_all(action='DESELECT')
        bpy.context.view_layer.objects.active.data.id_data.id_data.uv_layers.active_index = uv_id
        bpy.ops.object.mode_set(mode='EDIT', toggle=False)
        bpy.ops.mesh.select_all(action='SELECT')
        bpy.ops.uv.select_overlap(extend=False)
        bpy.ops.object.mode_set(mode='OBJECT', toggle=False)

        for vertice in bpy.context.active_object.data.vertices:
            if vertice.select:
                uv_001['sna_check_overlap_uv'] = True
                break

    bpy.context.view_layer.objects.active.data.id_data.id_data.uv_layers.active_index = 0
    return [uv_001['sna_check_overlap_uv'], obj]


def sna_check_xfrom_20671(obj):
    return [(not (((obj.scale[0], obj.scale[1], obj.scale[2]) == (1.0, 1.0, 1.0)) and ((obj.rotation_euler[0], obj.rotation_euler[1], obj.rotation_euler[2]) == (0.0, 0.0, 0.0)))), obj]


def sna_func_84043(obj):
    return [property_exists("obj.animation_data.action.fcurves", globals(), locals()), (len(list(obj.modifiers)) != 0), obj]


class SNA_PT_assets_check_0FA06(bpy.types.Panel):
    bl_label = '资产检查'
    bl_idname = 'SNA_PT_assets_check_0FA06'
    bl_space_type = 'IMAGE_EDITOR'
    bl_region_type = 'UI'
    bl_context = ''
    bl_category = '资产检查'
    bl_order = 0
    bl_ui_units_x=0

    @classmethod
    def poll(cls, context):
        return not (False)

    def draw_header(self, context):
        layout = self.layout

    def draw(self, context):
        layout = self.layout
        layout_function = layout
        sna_ui__ECC98(layout_function, )


class SNA_OT_Check_D2E47(bpy.types.Operator):
    bl_idname = "sna.check_d2e47"
    bl_label = "Check"
    bl_description = "检查"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        if bpy.app.version >= (3, 0, 0) and True:
            cls.poll_message_set('')
        return not False

    def execute(self, context):
        return {"FINISHED"}

    def draw(self, context):
        layout = self.layout
        layout_function = layout
        sna_ui__ECC98(layout_function, )

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self, width=1200)


def sna_add_to_topbar_mt_editor_menus_B2CEF(self, context):
    if not (False):
        layout = self.layout
        op = layout.operator('sna.check_d2e47', text='检查', icon_value=string_to_icon('MENU_PANEL'), emboss=False, depress=False)


def sna_ui__ECC98(layout_function, ):
    col_8D06A = layout_function.column(heading='', align=False)
    col_8D06A.alert = False
    col_8D06A.enabled = 'OBJECT'==bpy.context.mode
    col_8D06A.active = True
    col_8D06A.use_property_split = False
    col_8D06A.use_property_decorate = False
    col_8D06A.scale_x = 1.0
    col_8D06A.scale_y = 1.0
    col_8D06A.alignment = 'Expand'.upper()
    col_8D06A.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
    layout_function = col_8D06A
    sna_check_class_switch_interface_14E74(layout_function, )
    col_54560 = col_8D06A.column(heading='', align=False)
    col_54560.alert = False
    col_54560.enabled = True
    col_54560.active = True
    col_54560.use_property_split = False
    col_54560.use_property_decorate = False
    col_54560.scale_x = 1.0
    col_54560.scale_y = 1.5
    col_54560.alignment = 'Expand'.upper()
    col_54560.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
    op = col_54560.operator('sna.check_start_1085a', text='检查', icon_value=string_to_icon('TEMP'), emboss=True, depress=False)
    layout_function = col_8D06A
    sna_func_40797(layout_function, )
    layout_function = col_8D06A
    sna_func_245C2(layout_function, )
    layout_function = col_8D06A
    sna_func_F18E7(layout_function, )


def sna_func_40797(layout_function, ):
    layout_function.separator(factor=1.0)
    split_D808D = layout_function.split(factor=0.30000001192092896, align=True)
    split_D808D.alert = False
    split_D808D.enabled = True
    split_D808D.active = True
    split_D808D.use_property_split = False
    split_D808D.use_property_decorate = False
    split_D808D.scale_x = 1.0
    split_D808D.scale_y = 1.0
    split_D808D.alignment = 'Expand'.upper()
    if not True: split_D808D.operator_context = "EXEC_DEFAULT"
    col_39082 = split_D808D.column(heading='', align=True)
    col_39082.alert = False
    col_39082.enabled = True
    col_39082.active = True
    col_39082.use_property_split = False
    col_39082.use_property_decorate = False
    col_39082.scale_x = 1.0
    col_39082.scale_y = 1.0
    col_39082.alignment = 'Expand'.upper()
    col_39082.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
    col_39082.label(text='选中物体数量：' + str(len(list(bpy.context.view_layer.objects.selected))), icon_value=string_to_icon('OUTLINER_OB_MESH'))
    split_F4EE1 = col_39082.split(factor=0.699999988079071, align=True)
    split_F4EE1.alert = False
    split_F4EE1.enabled = True
    split_F4EE1.active = True
    split_F4EE1.use_property_split = False
    split_F4EE1.use_property_decorate = False
    split_F4EE1.scale_x = 1.0
    split_F4EE1.scale_y = 1.0
    split_F4EE1.alignment = 'Expand'.upper()
    if not True: split_F4EE1.operator_context = "EXEC_DEFAULT"
    split_F4EE1.label(text='已检查物体数量：' + str(len(node_tree_002['sna_check_obj_data_lis'])), icon_value=string_to_icon('OUTLINER_OB_MESH'))
    op = split_F4EE1.operator('sna.select_all_97e08', text='全选', icon_value=0, emboss=True, depress=False)
    split_E8349 = split_D808D.split(factor=0.009999999776482582, align=True)
    split_E8349.alert = False
    split_E8349.enabled = True
    split_E8349.active = True
    split_E8349.use_property_split = False
    split_E8349.use_property_decorate = False
    split_E8349.scale_x = 1.0
    split_E8349.scale_y = 1.0
    split_E8349.alignment = 'Expand'.upper()
    if not True: split_E8349.operator_context = "EXEC_DEFAULT"
    split_E8349.separator(factor=1.0)
    col_DA2C1 = split_E8349.column(heading='', align=True)
    col_DA2C1.alert = False
    col_DA2C1.enabled = True
    col_DA2C1.active = True
    col_DA2C1.use_property_split = False
    col_DA2C1.use_property_decorate = False
    col_DA2C1.scale_x = 1.0
    col_DA2C1.scale_y = 1.0
    col_DA2C1.alignment = 'Expand'.upper()
    col_DA2C1.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
    col_DA2C1.separator(factor=4.0)
    col_DA2C1.prop(bpy.context.scene, 'sna_check_name_filtration', text='', icon_value=string_to_icon('VIEWZOOM'), emboss=True)
    layout_function.separator(factor=1.0)


class SNA_OT_Select_All_97E08(bpy.types.Operator):
    bl_idname = "sna.select_all_97e08"
    bl_label = "select_all"
    bl_description = "选中检查完毕物体"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        if bpy.app.version >= (3, 0, 0) and True:
            cls.poll_message_set('')
        return not False

    def execute(self, context):
        bpy.ops.object.select_all(action='DESELECT')
        for i_8C1CC in range(len(node_tree_002['sna_check_obj_data_lis'])):
            bpy.ops.object.select_pattern(pattern=node_tree_002['sna_check_obj_data_lis'][i_8C1CC][0], case_sensitive=False, extend=True)
            bpy.context.view_layer.objects.active = bpy.data.objects[node_tree_002['sna_check_obj_data_lis'][i_8C1CC][0]]
            self.report({'INFO'}, message='全选已检查物体成功！')
        return {"FINISHED"}

    def invoke(self, context, event):
        return self.execute(context)


def sna_func_F18E7(layout_function, ):
    col_55461 = layout_function.column(heading='', align=True)
    col_55461.alert = False
    col_55461.enabled = True
    col_55461.active = True
    col_55461.use_property_split = False
    col_55461.use_property_decorate = False
    col_55461.scale_x = 1.0
    col_55461.scale_y = 1.0
    col_55461.alignment = 'Expand'.upper()
    col_55461.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
    for i_3BFB1 in range(len(node_tree_002['sna_check_obj_data_lis'])):
        if bpy.context.scene.sna_check_name_filtration in node_tree_002['sna_check_obj_data_lis'][i_3BFB1][0]:
            split_C4A09 = col_55461.split(factor=0.3199999928474426, align=True)
            split_C4A09.alert = False
            split_C4A09.enabled = True
            split_C4A09.active = True
            split_C4A09.use_property_split = False
            split_C4A09.use_property_decorate = False
            split_C4A09.scale_x = 1.0
            split_C4A09.scale_y = 1.0
            split_C4A09.alignment = 'Expand'.upper()
            if not True: split_C4A09.operator_context = "EXEC_DEFAULT"
            split_47629 = split_C4A09.split(factor=0.800000011920929, align=True)
            split_47629.alert = False
            split_47629.enabled = True
            split_47629.active = True
            split_47629.use_property_split = False
            split_47629.use_property_decorate = False
            split_47629.scale_x = 1.0
            split_47629.scale_y = 1.0
            split_47629.alignment = 'Expand'.upper()
            if not True: split_47629.operator_context = "EXEC_DEFAULT"
            box_2A781 = split_47629.box()
            box_2A781.alert = False
            box_2A781.enabled = True
            box_2A781.active = True
            box_2A781.use_property_split = False
            box_2A781.use_property_decorate = False
            box_2A781.alignment = 'Expand'.upper()
            box_2A781.scale_x = 1.0
            box_2A781.scale_y = 1.0
            if not True: box_2A781.operator_context = "EXEC_DEFAULT"
            split_DD1E7 = box_2A781.split(factor=0.10000000149011612, align=True)
            split_DD1E7.alert = False
            split_DD1E7.enabled = True
            split_DD1E7.active = True
            split_DD1E7.use_property_split = False
            split_DD1E7.use_property_decorate = False
            split_DD1E7.scale_x = 1.0
            split_DD1E7.scale_y = 1.0
            split_DD1E7.alignment = 'Expand'.upper()
            if not True: split_DD1E7.operator_context = "EXEC_DEFAULT"
            col_757E0 = split_DD1E7.column(heading='', align=True)
            col_757E0.alert = (not property_exists("bpy.context.view_layer.objects.active.name", globals(), locals()))
            col_757E0.enabled = property_exists("bpy.context.view_layer.objects.active.name", globals(), locals())
            col_757E0.active = True
            col_757E0.use_property_split = False
            col_757E0.use_property_decorate = False
            col_757E0.scale_x = 1.0
            col_757E0.scale_y = 1.0
            col_757E0.alignment = 'Expand'.upper()
            col_757E0.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
            op = col_757E0.operator('sna.my_generic_operator_cc4a9', text='', icon_value=string_to_icon('OUTLINER_OB_MESH'), emboss=((bpy.context.view_layer.objects.active.name == node_tree_002['sna_check_obj_data_lis'][i_3BFB1][0]) if property_exists("bpy.context.view_layer.objects.active.name", globals(), locals()) else False), depress=False)
            op.sna_obj_name = node_tree_002['sna_check_obj_data_lis'][i_3BFB1][0]
            split_DD1E7.label(text=node_tree_002['sna_check_obj_data_lis'][i_3BFB1][0], icon_value=0)
            box_8E2E3 = split_47629.box()
            box_8E2E3.alert = False
            box_8E2E3.enabled = True
            box_8E2E3.active = True
            box_8E2E3.use_property_split = False
            box_8E2E3.use_property_decorate = False
            box_8E2E3.alignment = 'Expand'.upper()
            box_8E2E3.scale_x = 1.0
            box_8E2E3.scale_y = 1.0
            if not True: box_8E2E3.operator_context = "EXEC_DEFAULT"
            box_8E2E3.label(text=str(node_tree_002['sna_check_obj_data_lis'][i_3BFB1][1]), icon_value=0)
            row_BD963 = split_C4A09.row(heading='', align=True)
            row_BD963.alert = False
            row_BD963.enabled = True
            row_BD963.active = True
            row_BD963.use_property_split = False
            row_BD963.use_property_decorate = False
            row_BD963.scale_x = 1.0
            row_BD963.scale_y = 1.0
            row_BD963.alignment = 'Expand'.upper()
            row_BD963.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
            for i_808B7 in range(len(node_tree_002['sna_check_obj_data_lis'][i_3BFB1])):
                if (i_808B7 >= 2):
                    if ('False' in str(node_tree_002['sna_check_obj_data_lis'][i_3BFB1][i_808B7]) or 'True' in str(node_tree_002['sna_check_obj_data_lis'][i_3BFB1][i_808B7])):
                        box_620A4 = row_BD963.box()
                        box_620A4.alert = False
                        box_620A4.enabled = True
                        box_620A4.active = True
                        box_620A4.use_property_split = False
                        box_620A4.use_property_decorate = False
                        box_620A4.alignment = 'Expand'.upper()
                        box_620A4.scale_x = 1.0
                        box_620A4.scale_y = 1.0
                        if not True: box_620A4.operator_context = "EXEC_DEFAULT"
                        col_21FD5 = box_620A4.column(heading='', align=True)
                        col_21FD5.alert = False
                        col_21FD5.enabled = True
                        col_21FD5.active = True
                        col_21FD5.use_property_split = False
                        col_21FD5.use_property_decorate = False
                        col_21FD5.scale_x = 1.0
                        col_21FD5.scale_y = 1.0
                        col_21FD5.alignment = 'Expand'.upper()
                        col_21FD5.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
                        point_color = ((0.800000011920929, 0.20000000298023224, 0.20000000298023224, 1.0) if node_tree_002['sna_check_obj_data_lis'][i_3BFB1][i_808B7] else (0.30000001192092896, 0.699999988079071, 0.30000001192092896, 1.0))
                        col_21FD5.template_node_socket(color=point_color)
                        col_22436 = col_21FD5.column(heading='', align=True)
                        col_22436.alert = False
                        col_22436.enabled = True
                        col_22436.active = True
                        col_22436.use_property_split = False
                        col_22436.use_property_decorate = False
                        col_22436.scale_x = 1.0
                        col_22436.scale_y = 9.999999717180685e-10
                        col_22436.alignment = 'Expand'.upper()
                        col_22436.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
                        col_22436.label(text='', icon_value=0)
                    else:
                        box_5AEE0 = row_BD963.box()
                        box_5AEE0.alert = False
                        box_5AEE0.enabled = True
                        box_5AEE0.active = True
                        box_5AEE0.use_property_split = False
                        box_5AEE0.use_property_decorate = False
                        box_5AEE0.alignment = 'Expand'.upper()
                        box_5AEE0.scale_x = 1.0
                        box_5AEE0.scale_y = 1.0
                        if not True: box_5AEE0.operator_context = "EXEC_DEFAULT"
                        box_5AEE0.label(text=str(node_tree_002['sna_check_obj_data_lis'][i_3BFB1][i_808B7]), icon_value=0)


class SNA_OT_My_Generic_Operator_Cc4A9(bpy.types.Operator):
    bl_idname = "sna.my_generic_operator_cc4a9"
    bl_label = "选中模型"
    bl_description = "选中模型"
    bl_options = {"REGISTER", "UNDO"}
    sna_obj_name: bpy.props.StringProperty(name='obj_name', description='', options={'HIDDEN'}, default='', subtype='NONE', maxlen=0)

    @classmethod
    def poll(cls, context):
        if bpy.app.version >= (3, 0, 0) and True:
            cls.poll_message_set('')
        return not False

    def execute(self, context):
        bpy.ops.object.select_all(action='DESELECT')
        bpy.ops.object.select_pattern(pattern=self.sna_obj_name, case_sensitive=True, extend=False)
        bpy.context.view_layer.objects.active = bpy.data.objects[self.sna_obj_name]
        return {"FINISHED"}

    def invoke(self, context, event):
        return self.execute(context)


def sna_func_245C2(layout_function, ):
    if (len(node_tree_002['sna_check_obj_data_lis']) > 0):
        col_0F66D = layout_function.column(heading='', align=True)
        col_0F66D.alert = False
        col_0F66D.enabled = True
        col_0F66D.active = True
        col_0F66D.use_property_split = False
        col_0F66D.use_property_decorate = False
        col_0F66D.scale_x = 1.0
        col_0F66D.scale_y = 1.0
        col_0F66D.alignment = 'Expand'.upper()
        col_0F66D.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
        split_98C76 = col_0F66D.split(factor=0.3199999928474426, align=True)
        split_98C76.alert = False
        split_98C76.enabled = True
        split_98C76.active = True
        split_98C76.use_property_split = False
        split_98C76.use_property_decorate = False
        split_98C76.scale_x = 1.0
        split_98C76.scale_y = 1.0
        split_98C76.alignment = 'Expand'.upper()
        if not True: split_98C76.operator_context = "EXEC_DEFAULT"
        split_0FABB = split_98C76.split(factor=0.800000011920929, align=True)
        split_0FABB.alert = False
        split_0FABB.enabled = True
        split_0FABB.active = True
        split_0FABB.use_property_split = False
        split_0FABB.use_property_decorate = False
        split_0FABB.scale_x = 1.0
        split_0FABB.scale_y = 1.0
        split_0FABB.alignment = 'Expand'.upper()
        if not True: split_0FABB.operator_context = "EXEC_DEFAULT"
        col_D2B6E = split_0FABB.column(heading='', align=True)
        col_D2B6E.alert = False
        col_D2B6E.enabled = True
        col_D2B6E.active = True
        col_D2B6E.use_property_split = False
        col_D2B6E.use_property_decorate = False
        col_D2B6E.scale_x = 1.0
        col_D2B6E.scale_y = 1.0
        col_D2B6E.alignment = 'Expand'.upper()
        col_D2B6E.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
        col_D2B6E.label(text='', icon_value=0)
        box_A3CF4 = col_D2B6E.box()
        box_A3CF4.alert = False
        box_A3CF4.enabled = True
        box_A3CF4.active = True
        box_A3CF4.use_property_split = False
        box_A3CF4.use_property_decorate = False
        box_A3CF4.alignment = 'Expand'.upper()
        box_A3CF4.scale_x = 1.0
        box_A3CF4.scale_y = 1.600000023841858
        if not True: box_A3CF4.operator_context = "EXEC_DEFAULT"
        op = box_A3CF4.operator('sna.placeholder_3baa5', text='名称', icon_value=0, emboss=False, depress=False)
        col_C4445 = split_0FABB.column(heading='', align=True)
        col_C4445.alert = False
        col_C4445.enabled = True
        col_C4445.active = True
        col_C4445.use_property_split = False
        col_C4445.use_property_decorate = False
        col_C4445.scale_x = 1.0
        col_C4445.scale_y = 1.0
        col_C4445.alignment = 'Expand'.upper()
        col_C4445.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
        col_C4445.label(text='', icon_value=0)
        box_C074F = col_C4445.box()
        box_C074F.alert = False
        box_C074F.enabled = True
        box_C074F.active = True
        box_C074F.use_property_split = False
        box_C074F.use_property_decorate = False
        box_C074F.alignment = 'Expand'.upper()
        box_C074F.scale_x = 1.0
        box_C074F.scale_y = 1.600000023841858
        if not True: box_C074F.operator_context = "EXEC_DEFAULT"
        op = box_C074F.operator('sna.placeholder_3baa5', text='面数', icon_value=0, emboss=False, depress=False)
        row_D5169 = split_98C76.row(heading='', align=True)
        row_D5169.alert = False
        row_D5169.enabled = True
        row_D5169.active = True
        row_D5169.use_property_split = False
        row_D5169.use_property_decorate = False
        row_D5169.scale_x = 1.0
        row_D5169.scale_y = 1.0
        row_D5169.alignment = 'Expand'.upper()
        row_D5169.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
        for i_39E07 in range(len(node_tree_002['sna_check_class_list'])):
            col_915D5 = row_D5169.column(heading='', align=True)
            col_915D5.alert = False
            col_915D5.enabled = True
            col_915D5.active = True
            col_915D5.use_property_split = False
            col_915D5.use_property_decorate = False
            col_915D5.scale_x = 1.0
            col_915D5.scale_y = 1.0
            col_915D5.alignment = 'Expand'.upper()
            col_915D5.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
            if '材质数量' in node_tree_002['sna_check_class_list'][i_39E07].split('-')[0] + node_tree_002['sna_check_class_list'][i_39E07].split('-')[1]:
                col_915D5.label(text=' ', icon_value=0)
            if 'U  V数量' in node_tree_002['sna_check_class_list'][i_39E07].split('-')[0] + node_tree_002['sna_check_class_list'][i_39E07].split('-')[1]:
                col_915D5.menu('SNA_MT_0EF39', text='', icon_value=0)
            if '顶点色数' in node_tree_002['sna_check_class_list'][i_39E07].split('-')[0] + node_tree_002['sna_check_class_list'][i_39E07].split('-')[1]:
                col_915D5.menu('SNA_MT_D1BE9', text='', icon_value=0)
            if '贴图数量' in node_tree_002['sna_check_class_list'][i_39E07].split('-')[0] + node_tree_002['sna_check_class_list'][i_39E07].split('-')[1]:
                col_915D5.label(text=' ', icon_value=0)
            if '空材质槽' in node_tree_002['sna_check_class_list'][i_39E07].split('-')[0] + node_tree_002['sna_check_class_list'][i_39E07].split('-')[1]:
                col_915D5.menu('SNA_MT_0854C', text='', icon_value=0)
            if '贴图丢失' in node_tree_002['sna_check_class_list'][i_39E07].split('-')[0] + node_tree_002['sna_check_class_list'][i_39E07].split('-')[1]:
                col_915D5.menu('SNA_MT_57AD1', text='', icon_value=0)
            if 'N 多边面' in node_tree_002['sna_check_class_list'][i_39E07].split('-')[0] + node_tree_002['sna_check_class_list'][i_39E07].split('-')[1]:
                col_915D5.menu('SNA_MT_B9C05', text='', icon_value=0)
            if '不平整面' in node_tree_002['sna_check_class_list'][i_39E07].split('-')[0] + node_tree_002['sna_check_class_list'][i_39E07].split('-')[1]:
                col_915D5.menu('SNA_MT_F45E8', text='', icon_value=0)
            if '非流体边' in node_tree_002['sna_check_class_list'][i_39E07].split('-')[0] + node_tree_002['sna_check_class_list'][i_39E07].split('-')[1]:
                col_915D5.menu('SNA_MT_F78BB', text='', icon_value=0)
            if '交叉边面' in node_tree_002['sna_check_class_list'][i_39E07].split('-')[0] + node_tree_002['sna_check_class_list'][i_39E07].split('-')[1]:
                col_915D5.menu('SNA_MT_7B81A', text='', icon_value=0)
            if '零边检查' in node_tree_002['sna_check_class_list'][i_39E07].split('-')[0] + node_tree_002['sna_check_class_list'][i_39E07].split('-')[1]:
                col_915D5.menu('SNA_MT_3C00A', text='', icon_value=0)
            if '1  U象限' in node_tree_002['sna_check_class_list'][i_39E07].split('-')[0] + node_tree_002['sna_check_class_list'][i_39E07].split('-')[1]:
                col_915D5.label(text=' ', icon_value=0)
            if '2  U象限' in node_tree_002['sna_check_class_list'][i_39E07].split('-')[0] + node_tree_002['sna_check_class_list'][i_39E07].split('-')[1]:
                col_915D5.label(text=' ', icon_value=0)
            if '1  U重叠' in node_tree_002['sna_check_class_list'][i_39E07].split('-')[0] + node_tree_002['sna_check_class_list'][i_39E07].split('-')[1]:
                col_915D5.label(text=' ', icon_value=0)
            if '2  U重叠' in node_tree_002['sna_check_class_list'][i_39E07].split('-')[0] + node_tree_002['sna_check_class_list'][i_39E07].split('-')[1]:
                col_915D5.label(text=' ', icon_value=0)
            if '变换归零' in node_tree_002['sna_check_class_list'][i_39E07].split('-')[0] + node_tree_002['sna_check_class_list'][i_39E07].split('-')[1]:
                col_915D5.menu('SNA_MT_4028E', text='', icon_value=0)
            if '动画检查' in node_tree_002['sna_check_class_list'][i_39E07].split('-')[0] + node_tree_002['sna_check_class_list'][i_39E07].split('-')[1]:
                col_915D5.menu('SNA_MT_F6D39', text='', icon_value=0)
            if '修改器' in node_tree_002['sna_check_class_list'][i_39E07].split('-')[0] + node_tree_002['sna_check_class_list'][i_39E07].split('-')[1]:
                col_915D5.label(text=' ', icon_value=0)
            box_3EFCC = col_915D5.box()
            box_3EFCC.alert = False
            box_3EFCC.enabled = True
            box_3EFCC.active = True
            box_3EFCC.use_property_split = False
            box_3EFCC.use_property_decorate = False
            box_3EFCC.alignment = 'Expand'.upper()
            box_3EFCC.scale_x = 1.0
            box_3EFCC.scale_y = 1.0
            if not True: box_3EFCC.operator_context = "EXEC_DEFAULT"
            col_3FF81 = box_3EFCC.column(heading='', align=True)
            col_3FF81.alert = False
            col_3FF81.enabled = True
            col_3FF81.active = True
            col_3FF81.use_property_split = False
            col_3FF81.use_property_decorate = False
            col_3FF81.scale_x = 1.0
            col_3FF81.scale_y = 0.800000011920929
            col_3FF81.alignment = 'Expand'.upper()
            col_3FF81.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
            op = col_3FF81.operator('sna.placeholder_3baa5', text=node_tree_002['sna_check_class_list'][i_39E07].split('-')[0], icon_value=0, emboss=False, depress=False)
            op = col_3FF81.operator('sna.placeholder_3baa5', text=node_tree_002['sna_check_class_list'][i_39E07].split('-')[1], icon_value=0, emboss=False, depress=False)
        split_1DECA = col_0F66D.split(factor=0.3199999928474426, align=True)
        split_1DECA.alert = False
        split_1DECA.enabled = True
        split_1DECA.active = True
        split_1DECA.use_property_split = False
        split_1DECA.use_property_decorate = False
        split_1DECA.scale_x = 1.0
        split_1DECA.scale_y = 1.0
        split_1DECA.alignment = 'Expand'.upper()
        if not True: split_1DECA.operator_context = "EXEC_DEFAULT"
        split_1C7B1 = split_1DECA.split(factor=0.800000011920929, align=True)
        split_1C7B1.alert = False
        split_1C7B1.enabled = True
        split_1C7B1.active = True
        split_1C7B1.use_property_split = False
        split_1C7B1.use_property_decorate = False
        split_1C7B1.scale_x = 1.0
        split_1C7B1.scale_y = 1.0
        split_1C7B1.alignment = 'Expand'.upper()
        if not True: split_1C7B1.operator_context = "EXEC_DEFAULT"
        box_7BC9E = split_1C7B1.box()
        box_7BC9E.alert = False
        box_7BC9E.enabled = True
        box_7BC9E.active = True
        box_7BC9E.use_property_split = False
        box_7BC9E.use_property_decorate = False
        box_7BC9E.alignment = 'Expand'.upper()
        box_7BC9E.scale_x = 1.0
        box_7BC9E.scale_y = 1.0
        if not True: box_7BC9E.operator_context = "EXEC_DEFAULT"
        op = box_7BC9E.operator('sna.list_sort_ee0c4', text='', icon_value=((string_to_icon('TRIA_DOWN') if (not ui__003['sna_check_sort_switching']) else string_to_icon('TRIA_UP')) if (0 == ui__003['sna_check_sort_orientation']) else 0), emboss=False, depress=False)
        op.sna_lis_column = 0
        op.sna_lis_reverse = (not ui__003['sna_check_sort_switching'])
        op.sna_lis_orientation = (0 == ui__003['sna_check_sort_orientation'])
        box_4A9F9 = split_1C7B1.box()
        box_4A9F9.alert = False
        box_4A9F9.enabled = True
        box_4A9F9.active = True
        box_4A9F9.use_property_split = False
        box_4A9F9.use_property_decorate = False
        box_4A9F9.alignment = 'Expand'.upper()
        box_4A9F9.scale_x = 1.0
        box_4A9F9.scale_y = 1.0
        if not True: box_4A9F9.operator_context = "EXEC_DEFAULT"
        op = box_4A9F9.operator('sna.list_sort_ee0c4', text='', icon_value=((string_to_icon('TRIA_DOWN') if (not ui__003['sna_check_sort_switching']) else string_to_icon('TRIA_UP')) if (ui__003['sna_check_sort_orientation'] == 1) else 0), emboss=False, depress=False)
        op.sna_lis_column = 1
        op.sna_lis_reverse = (not ui__003['sna_check_sort_switching'])
        op.sna_lis_orientation = (ui__003['sna_check_sort_orientation'] == 1)
        row_EBDB7 = split_1DECA.row(heading='', align=True)
        row_EBDB7.alert = False
        row_EBDB7.enabled = True
        row_EBDB7.active = True
        row_EBDB7.use_property_split = False
        row_EBDB7.use_property_decorate = False
        row_EBDB7.scale_x = 1.0
        row_EBDB7.scale_y = 1.0
        row_EBDB7.alignment = 'Expand'.upper()
        row_EBDB7.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
        for i_1CC2A in range(len(node_tree_002['sna_check_class_list'])):
            box_08919 = row_EBDB7.box()
            box_08919.alert = False
            box_08919.enabled = True
            box_08919.active = True
            box_08919.use_property_split = False
            box_08919.use_property_decorate = False
            box_08919.alignment = 'Expand'.upper()
            box_08919.scale_x = 1.0
            box_08919.scale_y = 1.0
            if not True: box_08919.operator_context = "EXEC_DEFAULT"
            op = box_08919.operator('sna.list_sort_ee0c4', text=' ', icon_value=((string_to_icon('TRIA_DOWN') if (not ui__003['sna_check_sort_switching']) else string_to_icon('TRIA_UP')) if (int(i_1CC2A + 2.0) == ui__003['sna_check_sort_orientation']) else 0), emboss=False, depress=False)
            op.sna_lis_column = int(i_1CC2A + 2.0)
            op.sna_lis_reverse = (not ui__003['sna_check_sort_switching'])
            op.sna_lis_orientation = (int(i_1CC2A + 2.0) == ui__003['sna_check_sort_orientation'])


class SNA_OT_List_Sort_Ee0C4(bpy.types.Operator):
    bl_idname = "sna.list_sort_ee0c4"
    bl_label = "list_sort"
    bl_description = "列表排序"
    bl_options = {"REGISTER", "UNDO"}
    sna_lis_column: bpy.props.IntProperty(name='lis_column', description='', options={'HIDDEN'}, default=0, subtype='NONE')
    sna_lis_reverse: bpy.props.BoolProperty(name='lis_reverse', description='', options={'HIDDEN'}, default=False)
    sna_lis_orientation: bpy.props.BoolProperty(name='lis_orientation', description='', default=False)

    @classmethod
    def poll(cls, context):
        if bpy.app.version >= (3, 0, 0) and True:
            cls.poll_message_set('')
        return not False

    def execute(self, context):
        ui__003['sna_check_sort_orientation'] = self.sna_lis_column
        if self.sna_lis_orientation:
            ui__003['sna_check_sort_switching'] = self.sna_lis_reverse
        data_lis = node_tree_002['sna_check_obj_data_lis']
        column = self.sna_lis_column
        lis_reverse = ((not self.sna_lis_reverse) if (self.sna_lis_column == 0) else ((not self.sna_lis_reverse) if self.sna_lis_orientation else self.sna_lis_reverse))
        sorted_data = None
        sorted_data = sorted(data_lis, key=lambda x: (x[column]), reverse=lis_reverse)
        node_tree_002['sna_check_obj_data_lis'] = sorted_data
        self.report({'INFO'}, message='排序完毕!')
        return {"FINISHED"}

    def invoke(self, context, event):
        return self.execute(context)


class SNA_OT_Placeholder_3Baa5(bpy.types.Operator):
    bl_idname = "sna.placeholder_3baa5"
    bl_label = "placeholder"
    bl_description = ""
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        if bpy.app.version >= (3, 0, 0) and True:
            cls.poll_message_set('')
        return not False

    def execute(self, context):
        return {"FINISHED"}

    def invoke(self, context, event):
        return self.execute(context)


def sna_check_class_switch_interface_14E74(layout_function, ):
    col_CC2FB = layout_function.column(heading='', align=False)
    col_CC2FB.alert = False
    col_CC2FB.enabled = True
    col_CC2FB.active = True
    col_CC2FB.use_property_split = False
    col_CC2FB.use_property_decorate = False
    col_CC2FB.scale_x = 1.0
    col_CC2FB.scale_y = 1.0
    col_CC2FB.alignment = 'Expand'.upper()
    col_CC2FB.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
    split_F4528 = col_CC2FB.split(factor=0.10000000149011612, align=True)
    split_F4528.alert = False
    split_F4528.enabled = True
    split_F4528.active = True
    split_F4528.use_property_split = False
    split_F4528.use_property_decorate = False
    split_F4528.scale_x = 1.0
    split_F4528.scale_y = 1.0
    split_F4528.alignment = 'Expand'.upper()
    if not True: split_F4528.operator_context = "EXEC_DEFAULT"
    split_F4528.prop(bpy.context.scene, 'sna_check_class_switch', text='检查类别', icon_value=0, emboss=True, toggle=True)
    split_F4528.separator(factor=1.0)
    if bpy.context.scene.sna_check_class_switch:
        box_36EF2 = col_CC2FB.box()
        box_36EF2.alert = False
        box_36EF2.enabled = True
        box_36EF2.active = True
        box_36EF2.use_property_split = False
        box_36EF2.use_property_decorate = False
        box_36EF2.alignment = 'Expand'.upper()
        box_36EF2.scale_x = 1.0
        box_36EF2.scale_y = 1.0
        if not True: box_36EF2.operator_context = "EXEC_DEFAULT"
        col_52CE0 = box_36EF2.column(heading='', align=False)
        col_52CE0.alert = False
        col_52CE0.enabled = True
        col_52CE0.active = True
        col_52CE0.use_property_split = False
        col_52CE0.use_property_decorate = False
        col_52CE0.scale_x = 1.0
        col_52CE0.scale_y = 1.0
        col_52CE0.alignment = 'Expand'.upper()
        col_52CE0.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
        split_759F5 = col_52CE0.split(factor=0.10000000149011612, align=False)
        split_759F5.alert = False
        split_759F5.enabled = True
        split_759F5.active = True
        split_759F5.use_property_split = False
        split_759F5.use_property_decorate = False
        split_759F5.scale_x = 1.0
        split_759F5.scale_y = 1.5
        split_759F5.alignment = 'Expand'.upper()
        if not True: split_759F5.operator_context = "EXEC_DEFAULT"
        op = split_759F5.operator('wm.save_userpref', text='保存配置', icon_value=string_to_icon('CHECKMARK'), emboss=True, depress=False)
        split_759F5.label(text='按住  Shift   增加/减少  检查项', icon_value=string_to_icon('EVENT_SHIFT'))
        grid_B6F44 = col_52CE0.grid_flow(columns=10, row_major=True, even_columns=False, even_rows=False, align=True)
        grid_B6F44.enabled = True
        grid_B6F44.active = True
        grid_B6F44.use_property_split = False
        grid_B6F44.use_property_decorate = False
        grid_B6F44.alignment = 'Expand'.upper()
        grid_B6F44.scale_x = 1.0
        grid_B6F44.scale_y = 1.2000000476837158
        if not True: grid_B6F44.operator_context = "EXEC_DEFAULT"
        grid_B6F44.prop(bpy.context.preferences.addons[__package__].preferences, 'sna_check_class_switch_01', text=str(list(bpy.context.preferences.addons[__package__].preferences.sna_check_class_switch_01)), icon_value=0, emboss=True)


class SNA_AddonPreferences_810BC(bpy.types.AddonPreferences):
    bl_idname = __package__

    def sna_check_class_switch_01_enum_items(self, context):
        return [("No Items", "No Items", "No generate enum items node found to create items!", "ERROR", 0)]
    sna_check_class_switch_01: bpy.props.EnumProperty(name='check_class_switch_01', description='', items=[('材质数量', '材质数量', '', 0, 1), ('U  V数量', 'U  V数量', '', 0, 2), ('顶点色数', '顶点色数', '', 0, 4), ('贴图数量', '贴图数量', '', 0, 8), ('空材质槽', '空材质槽', '', 0, 16), ('贴图丢失', '贴图丢失', '', 0, 32), ('N 多边面', 'N 多边面', '', 0, 64), ('不平整面', '不平整面', '', 0, 128), ('非流体边', '非流体边', '', 0, 256), ('交叉边面', '交叉边面', '', 0, 512), ('零边检查', '零边检查', '', 0, 1024), ('1  U象限', '1  U象限', '', 0, 2048), ('2  U象限', '2  U象限', '', 0, 4096), ('1  U重叠', '1  U重叠', '', 0, 8192), ('2  U重叠', '2  U重叠', '', 0, 16384), ('变换归零', '变换归零', '', 0, 32768), ('动画检查', '动画检查', '', 0, 65536), ('修改器', '修改器', '', 0, 131072)], options={'ENUM_FLAG'})

    def draw(self, context):
        if not (False):
            layout = self.layout 


class SNA_OT_U_Dbcc0(bpy.types.Operator):
    bl_idname = "sna.u_dbcc0"
    bl_label = "清除大于2U"
    bl_description = "清除大于2U"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        if bpy.app.version >= (3, 0, 0) and False:
            cls.poll_message_set()
        return not False

    def execute(self, context):
        for i_17B88 in range(len(bpy.context.view_layer.objects.selected)):
            for i_DF436 in range(len(bpy.context.view_layer.objects.selected[i_17B88].data.uv_layers)):
                for i_0264C in range(len(bpy.context.view_layer.objects.selected[i_17B88].data.uv_layers)-1,-1,-1):
                    if (i_DF436 > 1):
                        print('物体：' + bpy.context.view_layer.objects.selected[i_17B88].name + '  清理UV数据：' + bpy.context.view_layer.objects.selected[i_17B88].data.uv_layers[i_0264C].name)
                        bpy.context.view_layer.objects.selected[i_17B88].data.uv_layers.remove(layer=bpy.context.view_layer.objects.selected[i_17B88].data.uv_layers[i_0264C], )
                        break
        self.report({'INFO'}, message='UV清理成功！')
        return {"FINISHED"}

    def invoke(self, context, event):
        return self.execute(context)


class SNA_MT_0EF39(bpy.types.Menu):
    bl_idname = "SNA_MT_0EF39"
    bl_label = ""

    @classmethod
    def poll(cls, context):
        return not (False)

    def draw(self, context):
        layout = self.layout.column_flow(columns=1)
        layout.operator_context = "INVOKE_DEFAULT"
        op = layout.operator('sna.uv_2f460', text='清除全部UV', icon_value=string_to_icon('PANEL_CLOSE'), emboss=True, depress=False)
        op = layout.operator('sna.uv_053a5', text='清除1U', icon_value=string_to_icon('PANEL_CLOSE'), emboss=True, depress=False)
        op.sna_uv_layer = 0
        op = layout.operator('sna.uv_053a5', text='清除2U', icon_value=string_to_icon('PANEL_CLOSE'), emboss=True, depress=False)
        op.sna_uv_layer = 1
        op = layout.operator('sna.u_dbcc0', text='清除大于2U', icon_value=string_to_icon('PANEL_CLOSE'), emboss=True, depress=False)
        op = layout.operator('sna.uv_478d7', text='UV序号命名', icon_value=string_to_icon('MODIFIER_DATA'), emboss=True, depress=False)


class SNA_OT_Uv_053A5(bpy.types.Operator):
    bl_idname = "sna.uv_053a5"
    bl_label = "清除UV"
    bl_description = "清除UV"
    bl_options = {"REGISTER", "UNDO"}
    sna_uv_layer: bpy.props.IntProperty(name='UV_layer', description='', options={'HIDDEN'}, default=0, subtype='NONE')

    @classmethod
    def poll(cls, context):
        if bpy.app.version >= (3, 0, 0) and True:
            cls.poll_message_set('')
        return not False

    def execute(self, context):
        for i_E65CC in range(len(bpy.context.view_layer.objects.selected)):
            if property_exists("bpy.context.view_layer.objects.selected[i_E65CC].data.uv_layers[self.sna_uv_layer]", globals(), locals()):
                print('物体：' + bpy.context.view_layer.objects.selected[i_E65CC].name + '  清理UV数据：' + bpy.context.view_layer.objects.selected[i_E65CC].data.uv_layers[self.sna_uv_layer].name)
                bpy.context.view_layer.objects.selected[i_E65CC].data.uv_layers.remove(layer=bpy.context.view_layer.objects.selected[i_E65CC].data.uv_layers[self.sna_uv_layer], )
        self.report({'INFO'}, message='UV清理成功！')
        return {"FINISHED"}

    def invoke(self, context, event):
        return self.execute(context)


class SNA_OT_Uv_2F460(bpy.types.Operator):
    bl_idname = "sna.uv_2f460"
    bl_label = "清除全部UV"
    bl_description = "清除全部UV"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        if bpy.app.version >= (3, 0, 0) and True:
            cls.poll_message_set('')
        return not False

    def execute(self, context):
        bpy.ops.sna.u_dbcc0()
        bpy.ops.sna.uv_053a5(sna_uv_layer=1)
        bpy.ops.sna.uv_053a5(sna_uv_layer=0)
        self.report({'INFO'}, message='UV清理成功！')
        return {"FINISHED"}

    def invoke(self, context, event):
        return self.execute(context)


class SNA_OT_Uv_478D7(bpy.types.Operator):
    bl_idname = "sna.uv_478d7"
    bl_label = "UV序号命名"
    bl_description = "UV序号命名"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        if bpy.app.version >= (3, 0, 0) and True:
            cls.poll_message_set('')
        return not False

    def execute(self, context):
        for i_1840C in range(len(bpy.context.view_layer.objects.selected)):
            for i_94583 in range(len(bpy.context.view_layer.objects.selected[i_1840C].data.uv_layers)):
                bpy.context.view_layer.objects.selected[i_1840C].data.uv_layers[i_94583].name = str(int(i_94583 + 1.0)) + 'U'
                self.report({'INFO'}, message='UV命名成功！')
        return {"FINISHED"}

    def invoke(self, context, event):
        return self.execute(context)


class SNA_OT_My_Generic_Operator_F1453(bpy.types.Operator):
    bl_idname = "sna.my_generic_operator_f1453"
    bl_label = "清除顶点色"
    bl_description = "清除顶点色"
    bl_options = {"REGISTER", "UNDO"}
    sna_vertex_number: bpy.props.IntProperty(name='vertex_number', description='', options={'HIDDEN'}, default=0, subtype='NONE')

    @classmethod
    def poll(cls, context):
        if bpy.app.version >= (3, 0, 0) and False:
            cls.poll_message_set()
        return not False

    def execute(self, context):
        for i_1E23A in range(len(bpy.context.view_layer.objects.selected)):
            for i_E8172 in range(len(bpy.context.view_layer.objects.selected[i_1E23A].data.color_attributes)):
                for i_1FEB4 in range(len(bpy.context.view_layer.objects.selected[i_1E23A].data.color_attributes)-1,-1,-1):
                    if (i_E8172 > self.sna_vertex_number):
                        print('物体：' + bpy.context.view_layer.objects.selected[i_1E23A].name + '  清理顶点色数据：' + bpy.context.view_layer.objects.selected[i_1E23A].data.color_attributes[i_1FEB4].name)
                        bpy.context.view_layer.objects.selected[i_1E23A].data.color_attributes.remove(attribute=bpy.context.view_layer.objects.selected[i_1E23A].data.color_attributes[i_1FEB4], )
                        break
        self.report({'INFO'}, message='顶点色清理成功！')
        return {"FINISHED"}

    def invoke(self, context, event):
        return self.execute(context)


class SNA_MT_D1BE9(bpy.types.Menu):
    bl_idname = "SNA_MT_D1BE9"
    bl_label = ""

    @classmethod
    def poll(cls, context):
        return not (False)

    def draw(self, context):
        layout = self.layout.column_flow(columns=1)
        layout.operator_context = "INVOKE_DEFAULT"
        op = layout.operator('sna.my_generic_operator_f1453', text='清除全部顶点色', icon_value=string_to_icon('PANEL_CLOSE'), emboss=True, depress=False)
        op.sna_vertex_number = -1
        op = layout.operator('sna.my_generic_operator_f1453', text='清除除1外的顶点色', icon_value=string_to_icon('PANEL_CLOSE'), emboss=True, depress=False)
        op.sna_vertex_number = 0
        op = layout.operator('sna.my_generic_operator_9b866', text='顶点色统一命名', icon_value=string_to_icon('MODIFIER_DATA'), emboss=True, depress=False)


class SNA_OT_My_Generic_Operator_9B866(bpy.types.Operator):
    bl_idname = "sna.my_generic_operator_9b866"
    bl_label = "顶点色统一名称"
    bl_description = "顶点色统一名称"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        if bpy.app.version >= (3, 0, 0) and True:
            cls.poll_message_set('')
        return not False

    def execute(self, context):
        for i_26722 in range(len(bpy.context.view_layer.objects.selected)):
            for i_E806C in range(len(bpy.context.view_layer.objects.selected[i_26722].data.vertex_colors)):
                bpy.context.view_layer.objects.selected[i_26722].data.vertex_colors[i_E806C].name = 'RGB'
        self.report({'INFO'}, message='顶点色统一名称成功！')
        return {"FINISHED"}

    def invoke(self, context, event):
        return self.execute(context)


class SNA_OT_My_Generic_Operator_Ca84F(bpy.types.Operator):
    bl_idname = "sna.my_generic_operator_ca84f"
    bl_label = "定位非流体"
    bl_description = "定位非流体"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        if bpy.app.version >= (3, 0, 0) and True:
            cls.poll_message_set('')
        return not False

    def execute(self, context):
        bpy.ops.object.mode_set(mode='EDIT', toggle=False)
        bpy.ops.mesh.select_mode(type='VERT', action='ENABLE')
        bpy.ops.mesh.select_non_manifold(extend=False, use_wire=True, use_boundary=False, use_multi_face=True, use_non_contiguous=True, use_verts=False)
        self.report({'INFO'}, message='定位非流体成功！')
        return {"FINISHED"}

    def invoke(self, context, event):
        return self.execute(context)


class SNA_MT_F78BB(bpy.types.Menu):
    bl_idname = "SNA_MT_F78BB"
    bl_label = ""

    @classmethod
    def poll(cls, context):
        return not (False)

    def draw(self, context):
        layout = self.layout.column_flow(columns=1)
        layout.operator_context = "INVOKE_DEFAULT"
        op = layout.operator('sna.my_generic_operator_ca84f', text='定位非流体', icon_value=string_to_icon('RESTRICT_SELECT_OFF'), emboss=True, depress=False)


class SNA_MT_0854C(bpy.types.Menu):
    bl_idname = "SNA_MT_0854C"
    bl_label = ""

    @classmethod
    def poll(cls, context):
        return not (False)

    def draw(self, context):
        layout = self.layout.column_flow(columns=1)
        layout.operator_context = "INVOKE_DEFAULT"
        op = layout.operator('sna.my_generic_operator_23016', text='清除空材质槽', icon_value=string_to_icon('PANEL_CLOSE'), emboss=True, depress=False)


class SNA_OT_My_Generic_Operator_23016(bpy.types.Operator):
    bl_idname = "sna.my_generic_operator_23016"
    bl_label = "清除空材质槽"
    bl_description = "清除空材质槽"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        if bpy.app.version >= (3, 0, 0) and True:
            cls.poll_message_set('')
        return not False

    def execute(self, context):
        bpy.ops.object.material_slot_remove_unused()
        self.report({'INFO'}, message='清除空材质槽成功！')
        return {"FINISHED"}

    def invoke(self, context, event):
        return self.execute(context)


class SNA_OT_My_Generic_Operator_Bce76(bpy.types.Operator):
    bl_idname = "sna.my_generic_operator_bce76"
    bl_label = "多边面定位"
    bl_description = ""
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        if bpy.app.version >= (3, 0, 0) and False:
            cls.poll_message_set()
        return not False

    def execute(self, context):
        bpy.ops.object.mode_set(mode='EDIT', toggle=False)
        bpy.ops.mesh.select_all(action='DESELECT')
        bpy.ops.mesh.select_face_by_sides(number=4, type='GREATER', extend=False)
        self.report({'INFO'}, message='多边面定位成功！')
        return {"FINISHED"}

    def invoke(self, context, event):
        return self.execute(context)


class SNA_OT_My_Generic_Operator_44Fae(bpy.types.Operator):
    bl_idname = "sna.my_generic_operator_44fae"
    bl_label = "修复多边面"
    bl_description = ""
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        if bpy.app.version >= (3, 0, 0) and False:
            cls.poll_message_set()
        return not False

    def execute(self, context):
        bpy.ops.object.mode_set(mode='EDIT', toggle=False)
        bpy.ops.mesh.select_all(action='DESELECT')
        bpy.ops.mesh.select_face_by_sides(number=4, type='GREATER', extend=False)
        bpy.ops.mesh.quads_convert_to_tris()
        bpy.ops.mesh.tris_convert_to_quads()
        bpy.ops.object.mode_set(mode='OBJECT', toggle=False)
        self.report({'INFO'}, message='多边面修复成功！')
        return {"FINISHED"}

    def invoke(self, context, event):
        return self.execute(context)


class SNA_MT_B9C05(bpy.types.Menu):
    bl_idname = "SNA_MT_B9C05"
    bl_label = ""

    @classmethod
    def poll(cls, context):
        return not (False)

    def draw(self, context):
        layout = self.layout.column_flow(columns=1)
        layout.operator_context = "INVOKE_DEFAULT"
        op = layout.operator('sna.my_generic_operator_bce76', text='定位多边面', icon_value=string_to_icon('RESTRICT_SELECT_OFF'), emboss=True, depress=False)
        op = layout.operator('sna.my_generic_operator_44fae', text='修复多边面', icon_value=string_to_icon('MODIFIER_DATA'), emboss=True, depress=False)


class SNA_MT_F45E8(bpy.types.Menu):
    bl_idname = "SNA_MT_F45E8"
    bl_label = ""

    @classmethod
    def poll(cls, context):
        return not (False)

    def draw(self, context):
        layout = self.layout.column_flow(columns=1)
        layout.operator_context = "INVOKE_DEFAULT"
        op = layout.operator('sna.my_generic_operator_d73f1', text='定位不平整面', icon_value=string_to_icon('RESTRICT_SELECT_OFF'), emboss=True, depress=False)


class SNA_OT_My_Generic_Operator_D73F1(bpy.types.Operator):
    bl_idname = "sna.my_generic_operator_d73f1"
    bl_label = "定位不平整面"
    bl_description = "定位不平整面"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        if bpy.app.version >= (3, 0, 0) and True:
            cls.poll_message_set('')
        return not False

    def execute(self, context):
        node_tree_013['sna_check_extend_camber_face'] = []
        for i_68806 in range(len(bpy.context.view_layer.objects.selected)):
            node_tree_013['sna_check_extend_camber_face'].append(bpy.context.view_layer.objects.selected[i_68806])
        for i_3C488 in range(len(node_tree_013['sna_check_extend_camber_face'])):
            bpy.context.view_layer.objects.active = node_tree_013['sna_check_extend_camber_face'][i_3C488]
            bpy.ops.object.select_all(action='DESELECT')
            check_distorted_boole_0_30e11, check_distorted_list_data_1_30e11, obj_2_30e11 = sna_check_distorted_function_4C1A4(bpy.context.view_layer.objects.active)
            bpy.ops.object.mode_set(mode='EDIT', toggle=False)
            bpy.ops.mesh.select_mode(use_extend=False, use_expand=False, type='FACE', action='ENABLE')
            bpy.ops.mesh.select_all(action='DESELECT')
            bpy.ops.object.mode_set(mode='OBJECT', toggle=False)
            for i_F587A in range(len(check_distorted_list_data_1_30e11)):
                obj_2_30e11.data.polygons[string_to_type(check_distorted_list_data_1_30e11[i_F587A], int, 0)].select = True
        for i_EF566 in range(len(node_tree_013['sna_check_extend_camber_face'])):
            bpy.ops.object.select_pattern(pattern=node_tree_013['sna_check_extend_camber_face'][i_EF566].name, case_sensitive=False, extend=True)
        bpy.ops.object.mode_set(mode='EDIT', toggle=False)
        self.report({'INFO'}, message='不平整面定位成功！')
        return {"FINISHED"}

    def invoke(self, context, event):
        return self.execute(context)


class SNA_OT_My_Generic_Operator_83745(bpy.types.Operator):
    bl_idname = "sna.my_generic_operator_83745"
    bl_label = "定位交叉面"
    bl_description = "定位交叉面"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        if bpy.app.version >= (3, 0, 0) and True:
            cls.poll_message_set('')
        return not False

    def execute(self, context):
        node_tree_014['sna_check_extend_intersect_face'] = []
        for i_588C5 in range(len(bpy.context.view_layer.objects.selected)):
            node_tree_014['sna_check_extend_intersect_face'].append(bpy.context.view_layer.objects.selected[i_588C5])
        for i_33915 in range(len(node_tree_014['sna_check_extend_intersect_face'])):
            bpy.context.view_layer.objects.active = node_tree_014['sna_check_extend_intersect_face'][i_33915]
            bpy.ops.object.select_all(action='DESELECT')
            check_intersection_0_7aa93, check_intersection_list_data_1_7aa93, obj_2_7aa93 = sna_func_68F3E(bpy.context.view_layer.objects.active)
            bpy.ops.object.mode_set(mode='EDIT', toggle=False)
            bpy.ops.mesh.select_mode(use_extend=False, use_expand=False, type='FACE', action='ENABLE')
            bpy.ops.mesh.select_all(action='DESELECT')
            bpy.ops.object.mode_set(mode='OBJECT', toggle=False)
            for i_EECBE in range(len(check_intersection_list_data_1_7aa93)):
                obj_2_7aa93.data.polygons[string_to_type(check_intersection_list_data_1_7aa93[i_EECBE], int, 0)].select = True
        for i_816C5 in range(len(node_tree_014['sna_check_extend_intersect_face'])):
            bpy.ops.object.select_pattern(pattern=node_tree_014['sna_check_extend_intersect_face'][i_816C5].name, case_sensitive=False, extend=True)
        bpy.ops.object.mode_set(mode='EDIT', toggle=False)
        self.report({'INFO'}, message='交叉面定位成功！')
        return {"FINISHED"}

    def invoke(self, context, event):
        return self.execute(context)


class SNA_MT_7B81A(bpy.types.Menu):
    bl_idname = "SNA_MT_7B81A"
    bl_label = ""

    @classmethod
    def poll(cls, context):
        return not (False)

    def draw(self, context):
        layout = self.layout.column_flow(columns=1)
        layout.operator_context = "INVOKE_DEFAULT"
        op = layout.operator('sna.my_generic_operator_83745', text='定位交叉面', icon_value=string_to_icon('RESTRICT_SELECT_OFF'), emboss=True, depress=False)


class SNA_MT_3C00A(bpy.types.Menu):
    bl_idname = "SNA_MT_3C00A"
    bl_label = ""

    @classmethod
    def poll(cls, context):
        return not (False)

    def draw(self, context):
        layout = self.layout.column_flow(columns=1)
        layout.operator_context = "INVOKE_DEFAULT"
        op = layout.operator('sna.my_generic_operator_b023b', text='零边定位', icon_value=string_to_icon('RESTRICT_SELECT_OFF'), emboss=True, depress=False)


class SNA_OT_My_Generic_Operator_B023B(bpy.types.Operator):
    bl_idname = "sna.my_generic_operator_b023b"
    bl_label = "零边定位"
    bl_description = "零边定位"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        if bpy.app.version >= (3, 0, 0) and True:
            cls.poll_message_set('')
        return not False

    def execute(self, context):
        node_tree_015['sna_check_extend_zero_side'] = []
        for i_2ED63 in range(len(bpy.context.view_layer.objects.selected)):
            node_tree_015['sna_check_extend_zero_side'].append(bpy.context.view_layer.objects.selected[i_2ED63])
        for i_AC184 in range(len(node_tree_015['sna_check_extend_zero_side'])):
            bpy.context.view_layer.objects.active = node_tree_015['sna_check_extend_zero_side'][i_AC184]
            bpy.ops.object.select_all(action='DESELECT')
            check_zero_0_e65e4, check_zero_edge_list_data_1_e65e4, obj_2_e65e4 = sna_func_2BE0B(bpy.context.view_layer.objects.active)
            print(str(check_zero_edge_list_data_1_e65e4))
            bpy.ops.object.mode_set(mode='EDIT', toggle=False)
            bpy.ops.mesh.select_mode(use_extend=False, use_expand=False, type='EDGE', action='ENABLE')
            bpy.ops.mesh.select_all(action='DESELECT')
            bpy.ops.object.mode_set(mode='OBJECT', toggle=False)
            for i_FBBE9 in range(len(check_zero_edge_list_data_1_e65e4)):
                obj_2_e65e4.data.edges[string_to_type(check_zero_edge_list_data_1_e65e4[i_FBBE9], int, 0)].select = True
        for i_A0776 in range(len(node_tree_015['sna_check_extend_zero_side'])):
            bpy.ops.object.select_pattern(pattern=node_tree_015['sna_check_extend_zero_side'][i_A0776].name, case_sensitive=False, extend=True)
        bpy.ops.object.mode_set(mode='EDIT', toggle=False)
        self.report({'INFO'}, message='零边定位成功！')
        return {"FINISHED"}

    def invoke(self, context, event):
        return self.execute(context)


class SNA_OT_Xfrom_C0163(bpy.types.Operator):
    bl_idname = "sna.xfrom_c0163"
    bl_label = "一键Xfrom"
    bl_description = "一键Xfrom"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        if bpy.app.version >= (3, 0, 0) and False:
            cls.poll_message_set()
        return not False

    def execute(self, context):
        bpy.ops.object.transform_apply(location=False, rotation=True, scale=True, properties=True)
        self.report({'INFO'}, message='一键Xfrom成功！')
        return {"FINISHED"}

    def invoke(self, context, event):
        return self.execute(context)


class SNA_MT_4028E(bpy.types.Menu):
    bl_idname = "SNA_MT_4028E"
    bl_label = ""

    @classmethod
    def poll(cls, context):
        return not (False)

    def draw(self, context):
        layout = self.layout.column_flow(columns=1)
        layout.operator_context = "INVOKE_DEFAULT"
        op = layout.operator('sna.xfrom_c0163', text='重置Xfrom', icon_value=string_to_icon('MODIFIER_DATA'), emboss=True, depress=False)


class SNA_OT_My_Generic_Operator_997D5(bpy.types.Operator):
    bl_idname = "sna.my_generic_operator_997d5"
    bl_label = "清除全部动画"
    bl_description = "清除全部动画"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        if bpy.app.version >= (3, 0, 0) and False:
            cls.poll_message_set()
        return not False

    def execute(self, context):
        for i_09442 in range(len(bpy.context.blend_data.actions)):
            for i_BD756 in range(len(bpy.context.blend_data.actions)):
                print('删除动画数据：' + bpy.context.blend_data.actions[i_BD756].name)
                bpy.context.blend_data.actions.remove(action=bpy.context.blend_data.actions[i_BD756], )
                break
        self.report({'INFO'}, message='动画清理成功！')
        return {"FINISHED"}

    def invoke(self, context, event):
        return self.execute(context)


class SNA_OT_My_Generic_Operator_25625(bpy.types.Operator):
    bl_idname = "sna.my_generic_operator_25625"
    bl_label = "清除选中物体动画"
    bl_description = "清除选中物体动画"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        if bpy.app.version >= (3, 0, 0) and True:
            cls.poll_message_set('')
        return not False

    def execute(self, context):
        for i_C9709 in range(len(bpy.context.view_layer.objects.selected)):
            if (bpy.context.view_layer.objects.selected[i_C9709].animation_data.action != None):
                print('物体：' + bpy.context.view_layer.objects.selected[i_C9709].name + '  动画数据：' + bpy.context.view_layer.objects.selected[i_C9709].animation_data.action.name)
                bpy.context.blend_data.actions.remove(action=bpy.context.view_layer.objects.selected[i_C9709].animation_data.action, )
        self.report({'INFO'}, message='动画清理成功！')
        return {"FINISHED"}

    def invoke(self, context, event):
        return self.execute(context)


class SNA_MT_F6D39(bpy.types.Menu):
    bl_idname = "SNA_MT_F6D39"
    bl_label = ""

    @classmethod
    def poll(cls, context):
        return not (False)

    def draw(self, context):
        layout = self.layout.column_flow(columns=1)
        layout.operator_context = "INVOKE_DEFAULT"
        op = layout.operator('sna.my_generic_operator_997d5', text='清理全部动画数据', icon_value=string_to_icon('PANEL_CLOSE'), emboss=True, depress=False)
        op = layout.operator('sna.my_generic_operator_25625', text='清理选中物体动画', icon_value=string_to_icon('PANEL_CLOSE'), emboss=True, depress=False)


class SNA_OT_My_Generic_Operator_E5783(bpy.types.Operator):
    bl_idname = "sna.my_generic_operator_e5783"
    bl_label = "贴图丢失处理"
    bl_description = "检查选中检查模型引用贴图丢失"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        if bpy.app.version >= (3, 0, 0) and True:
            cls.poll_message_set('')
        return not False

    def execute(self, context):
        return {"FINISHED"}

    def draw(self, context):
        layout = self.layout
        col_62882 = layout.column(heading='', align=True)
        col_62882.alert = False
        col_62882.enabled = True
        col_62882.active = True
        col_62882.use_property_split = False
        col_62882.use_property_decorate = False
        col_62882.scale_x = 1.0
        col_62882.scale_y = 1.0
        col_62882.alignment = 'Expand'.upper()
        col_62882.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
        col_378B6 = col_62882.column(heading='', align=True)
        col_378B6.alert = True
        col_378B6.enabled = True
        col_378B6.active = True
        col_378B6.use_property_split = False
        col_378B6.use_property_decorate = False
        col_378B6.scale_x = 1.0
        col_378B6.scale_y = 1.0
        col_378B6.alignment = 'Expand'.upper()
        col_378B6.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
        col_378B6.label(text='贴图丢失数量 = ' + str(len(node_tree_017['sna_image_missing_names'])), icon_value=249)
        for i_DFB02 in range(len(node_tree_017['sna_image_missing_names'])):
            box_47CD5 = col_62882.box()
            box_47CD5.alert = False
            box_47CD5.enabled = True
            box_47CD5.active = True
            box_47CD5.use_property_split = False
            box_47CD5.use_property_decorate = False
            box_47CD5.alignment = 'Expand'.upper()
            box_47CD5.scale_x = 1.0
            box_47CD5.scale_y = 1.0
            if not True: box_47CD5.operator_context = "EXEC_DEFAULT"
            col_6B22D = box_47CD5.column(heading='', align=True)
            col_6B22D.alert = False
            col_6B22D.enabled = True
            col_6B22D.active = True
            col_6B22D.use_property_split = False
            col_6B22D.use_property_decorate = False
            col_6B22D.scale_x = 1.0
            col_6B22D.scale_y = 1.0
            col_6B22D.alignment = 'Expand'.upper()
            col_6B22D.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
            col_6B22D.prop(bpy.context.blend_data.images[node_tree_017['sna_image_missing_names'][i_DFB02]], 'name', text='', icon_value=0, emboss=True)
            col_6B22D.prop(bpy.context.blend_data.images[node_tree_017['sna_image_missing_names'][i_DFB02]], 'filepath', text='', icon_value=0, emboss=True)

    def invoke(self, context, event):
        node_tree_017['sna_image_missing_names'] = []
        for i_69D89 in range(len(bpy.context.view_layer.objects.selected)):
            check_image_missing_0_08422, check_image_quantity_1_08422, image_missing_names_2_08422, obj_3_08422 = sna_func_7D6B7(bpy.context.view_layer.objects.selected[i_69D89])
            if check_image_missing_0_08422:
                for i_B55F2 in range(len(image_missing_names_2_08422)):
                    node_tree_017['sna_image_missing_names'].append(image_missing_names_2_08422[i_B55F2])
        input = node_tree_017['sna_image_missing_names']
        exportation = None
        exportation = list(set(input))
        node_tree_017['sna_image_missing_names'] = exportation
        self.report({'INFO'}, message='丢失贴图检查完毕！' + '    选中模型贴图丢失贴图数量 = ' + str(len(exportation)))
        return context.window_manager.invoke_props_dialog(self, width=300)


class SNA_MT_57AD1(bpy.types.Menu):
    bl_idname = "SNA_MT_57AD1"
    bl_label = ""

    @classmethod
    def poll(cls, context):
        return not (False)

    def draw(self, context):
        layout = self.layout.column_flow(columns=1)
        layout.operator_context = "INVOKE_DEFAULT"
        op = layout.operator('sna.my_generic_operator_e5783', text='贴图丢失检查', icon_value=string_to_icon('OUTLINER_OB_IMAGE'), emboss=True, depress=False)


class SNA_OT_Check_Start_1085A(bpy.types.Operator):
    bl_idname = "sna.check_start_1085a"
    bl_label = "check_start"
    bl_description = "点击开始全量检查"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        if bpy.app.version >= (3, 0, 0) and False:
            cls.poll_message_set()
        return not False

    def execute(self, context):
        node_tree_002['sna_check_obj_lis'] = []
        node_tree_002['sna_check_obj_data_lis'] = []
        for i_6B9BD in range(len(bpy.context.view_layer.objects.selected)):
            if (bpy.context.view_layer.objects.selected[i_6B9BD].data.id_data.id_type == 'MESH'):
                node_tree_002['sna_check_obj_lis'].append(bpy.context.view_layer.objects.selected[i_6B9BD])
        print('开始检查！')
        for i_F4E3B in range(len(node_tree_002['sna_check_obj_lis'])):
            print(str(int(float(int(i_F4E3B + 1.0) / len(node_tree_002['sna_check_obj_lis'])) * 100.0)) + '%', ' —— ', node_tree_002['sna_check_obj_lis'][i_F4E3B].name)
            add_list_0_c0553 = sna_func_16E51(node_tree_002['sna_check_obj_lis'][i_F4E3B], True, True, '材质数量' in str(list(bpy.context.preferences.addons[__package__].preferences.sna_check_class_switch_01)), 'U  V数量' in str(list(bpy.context.preferences.addons[__package__].preferences.sna_check_class_switch_01)), '顶点色数' in str(list(bpy.context.preferences.addons[__package__].preferences.sna_check_class_switch_01)), '贴图数量' in str(list(bpy.context.preferences.addons[__package__].preferences.sna_check_class_switch_01)), '空材质槽' in str(list(bpy.context.preferences.addons[__package__].preferences.sna_check_class_switch_01)), '贴图丢失' in str(list(bpy.context.preferences.addons[__package__].preferences.sna_check_class_switch_01)), 'N 多边面' in str(list(bpy.context.preferences.addons[__package__].preferences.sna_check_class_switch_01)), '不平整面' in str(list(bpy.context.preferences.addons[__package__].preferences.sna_check_class_switch_01)), '非流体边' in str(list(bpy.context.preferences.addons[__package__].preferences.sna_check_class_switch_01)), '交叉边面' in str(list(bpy.context.preferences.addons[__package__].preferences.sna_check_class_switch_01)), '零边检查' in str(list(bpy.context.preferences.addons[__package__].preferences.sna_check_class_switch_01)), '1  U象限' in str(list(bpy.context.preferences.addons[__package__].preferences.sna_check_class_switch_01)), '2  U象限' in str(list(bpy.context.preferences.addons[__package__].preferences.sna_check_class_switch_01)), '1  U重叠' in str(list(bpy.context.preferences.addons[__package__].preferences.sna_check_class_switch_01)), '2  U重叠' in str(list(bpy.context.preferences.addons[__package__].preferences.sna_check_class_switch_01)), '变换归零' in str(list(bpy.context.preferences.addons[__package__].preferences.sna_check_class_switch_01)), '动画检查' in str(list(bpy.context.preferences.addons[__package__].preferences.sna_check_class_switch_01)), '修改器' in str(list(bpy.context.preferences.addons[__package__].preferences.sna_check_class_switch_01)))
            node_tree_002['sna_check_obj_data_lis'].append(add_list_0_c0553)
            node_tree_002['sna_check_class_list'] = []
            for i_8F6E5 in range(len(['材质-数量', 'U  V-数量', '顶点-色数', '贴图-数量', '空材-质槽', '贴图-丢失', 'N 多-边面', '不平-整面', '非流-体边', '交叉-边面', '零边-检查', '1  U-象限', '2  U-象限', '1  U-重叠', '2  U-重叠', '变换-归零', '动画-检查', '修改-器'])):
                if ['材质-数量', 'U  V-数量', '顶点-色数', '贴图-数量', '空材-质槽', '贴图-丢失', 'N 多-边面', '不平-整面', '非流-体边', '交叉-边面', '零边-检查', '1  U-象限', '2  U-象限', '1  U-重叠', '2  U-重叠', '变换-归零', '动画-检查', '修改-器'][i_8F6E5].replace('-', '') in str(list(bpy.context.preferences.addons[__package__].preferences.sna_check_class_switch_01)):
                    node_tree_002['sna_check_class_list'].append(['材质-数量', 'U  V-数量', '顶点-色数', '贴图-数量', '空材-质槽', '贴图-丢失', 'N 多-边面', '不平-整面', '非流-体边', '交叉-边面', '零边-检查', '1  U-象限', '2  U-象限', '1  U-重叠', '2  U-重叠', '变换-归零', '动画-检查', '修改-器'][i_8F6E5])
        for i_F9328 in range(len(node_tree_002['sna_check_obj_lis'])):
            bpy.ops.object.select_pattern(pattern=node_tree_002['sna_check_obj_lis'][i_F9328].name, case_sensitive=True, extend=True)
        print('检查结束！')
        bpy.ops.wm.console_toggle()
        return {"FINISHED"}

    def invoke(self, context, event):
        bpy.ops.wm.console_toggle()
        return self.execute(context)


def sna_func_16E51(obj, name, face_number, mat_number, uv_number, vc_number, img_number, empty_mat, img_deficiency, n_face, bend_face, non_fluid, intersect_face, zero_edges, u1_quadrant, u2_quadrant, u1_overlap, u2_overlap, x_from, ani, modifie):
    node_tree_002['sna_check_add_obj_da_list'] = []
    if name:
        check_name_0_154e8, check_face_number_1_154e8, check_mat_number_2_154e8, check_uv_number_3_154e8, check_vertexcolor_number_4_154e8, obj_5_154e8 = sna_func_3938F(obj)
        node_tree_002['sna_check_add_obj_da_list'].append(check_name_0_154e8)
    if face_number:
        check_name_0_ada7d, check_face_number_1_ada7d, check_mat_number_2_ada7d, check_uv_number_3_ada7d, check_vertexcolor_number_4_ada7d, obj_5_ada7d = sna_func_3938F(obj)
        node_tree_002['sna_check_add_obj_da_list'].append(check_face_number_1_ada7d)
    if mat_number:
        check_name_0_99e6f, check_face_number_1_99e6f, check_mat_number_2_99e6f, check_uv_number_3_99e6f, check_vertexcolor_number_4_99e6f, obj_5_99e6f = sna_func_3938F(obj)
        node_tree_002['sna_check_add_obj_da_list'].append(check_mat_number_2_99e6f)
    if uv_number:
        check_name_0_8c2f1, check_face_number_1_8c2f1, check_mat_number_2_8c2f1, check_uv_number_3_8c2f1, check_vertexcolor_number_4_8c2f1, obj_5_8c2f1 = sna_func_3938F(obj)
        node_tree_002['sna_check_add_obj_da_list'].append(check_uv_number_3_8c2f1)
    if vc_number:
        check_name_0_2a857, check_face_number_1_2a857, check_mat_number_2_2a857, check_uv_number_3_2a857, check_vertexcolor_number_4_2a857, obj_5_2a857 = sna_func_3938F(obj)
        node_tree_002['sna_check_add_obj_da_list'].append(check_vertexcolor_number_4_2a857)
    if img_number:
        check_image_missing_0_7a551, check_image_quantity_1_7a551, image_missing_names_2_7a551, obj_3_7a551 = sna_func_7D6B7(obj)
        node_tree_002['sna_check_add_obj_da_list'].append(check_image_quantity_1_7a551)
    if empty_mat:
        obj_0_1e7ca, check_mat_slot_1_1e7ca = sna_func_CF58E(obj)
        node_tree_002['sna_check_add_obj_da_list'].append(check_mat_slot_1_1e7ca)
    if img_deficiency:
        check_image_missing_0_1211e, check_image_quantity_1_1211e, image_missing_names_2_1211e, obj_3_1211e = sna_func_7D6B7(obj)
        node_tree_002['sna_check_add_obj_da_list'].append(check_image_missing_0_1211e)
    if n_face:
        obj_0_4df1b, check_ngon_face_1_4df1b = sna_func_80448(obj)
        node_tree_002['sna_check_add_obj_da_list'].append(check_ngon_face_1_4df1b)
    if bend_face:
        check_distorted_boole_0_c1693, check_distorted_list_data_1_c1693, obj_2_c1693 = sna_check_distorted_function_4C1A4(obj)
        node_tree_002['sna_check_add_obj_da_list'].append(check_distorted_boole_0_c1693)
    if non_fluid:
        check_non_fluid_0_f2dee, obj_1_f2dee = sna_func_FC9F2(obj)
        node_tree_002['sna_check_add_obj_da_list'].append(check_non_fluid_0_f2dee)
    if intersect_face:
        check_intersection_0_1c770, check_intersection_list_data_1_1c770, obj_2_1c770 = sna_func_68F3E(obj)
        node_tree_002['sna_check_add_obj_da_list'].append(check_intersection_0_1c770)
    if zero_edges:
        check_zero_0_14f95, check_zero_edge_list_data_1_14f95, obj_2_14f95 = sna_func_2BE0B(obj)
        node_tree_002['sna_check_add_obj_da_list'].append(check_zero_0_14f95)
    if u1_quadrant:
        check_quadrant_1u_0_f1d33, check_quadrant_2u_1_f1d33, obj_2_f1d33 = sna_uv_C5FDA(obj)
        node_tree_002['sna_check_add_obj_da_list'].append(check_quadrant_1u_0_f1d33)
    if u2_quadrant:
        check_quadrant_1u_0_df6c8, check_quadrant_2u_1_df6c8, obj_2_df6c8 = sna_uv_C5FDA(obj)
        node_tree_002['sna_check_add_obj_da_list'].append(check_quadrant_2u_1_df6c8)
    if u1_overlap:
        check_overlap_0_ec384, obj_1_ec384 = sna_uv_8B0EC(obj, 0)
        node_tree_002['sna_check_add_obj_da_list'].append(check_overlap_0_ec384)
    if u2_overlap:
        check_overlap_0_bb064, obj_1_bb064 = sna_uv_8B0EC(obj, 1)
        node_tree_002['sna_check_add_obj_da_list'].append(check_overlap_0_bb064)
    if x_from:
        check_xfrom_boole_0_08651, obj_1_08651 = sna_check_xfrom_20671(obj)
        node_tree_002['sna_check_add_obj_da_list'].append(check_xfrom_boole_0_08651)
    if ani:
        check_animation_0_99c0c, check_modifier_1_99c0c, obj_2_99c0c = sna_func_84043(obj)
        node_tree_002['sna_check_add_obj_da_list'].append(check_animation_0_99c0c)
    if modifie:
        check_animation_0_7553b, check_modifier_1_7553b, obj_2_7553b = sna_func_84043(obj)
        node_tree_002['sna_check_add_obj_da_list'].append(check_modifier_1_7553b)
    return node_tree_002['sna_check_add_obj_da_list']


def register():
    global _icons
    _icons = bpy.utils.previews.new()
    bpy.types.Scene.sna_check_name_filtration = bpy.props.StringProperty(name='check_name_filtration', description='', default='', subtype='NONE', maxlen=0)
    bpy.types.Scene.sna_check_class_switch = bpy.props.BoolProperty(name='check_class_switch', description='', default=False)
    #bpy.utils.register_class(SNA_PT_assets_check_0FA06)
    bpy.utils.register_class(SNA_OT_Check_D2E47)
    bpy.types.TOPBAR_MT_editor_menus.append(sna_add_to_topbar_mt_editor_menus_B2CEF)
    bpy.utils.register_class(SNA_OT_Select_All_97E08)
    bpy.utils.register_class(SNA_OT_My_Generic_Operator_Cc4A9)
    bpy.utils.register_class(SNA_OT_List_Sort_Ee0C4)
    bpy.utils.register_class(SNA_OT_Placeholder_3Baa5)
    bpy.utils.register_class(SNA_AddonPreferences_810BC)
    bpy.utils.register_class(SNA_OT_U_Dbcc0)
    bpy.utils.register_class(SNA_MT_0EF39)
    bpy.utils.register_class(SNA_OT_Uv_053A5)
    bpy.utils.register_class(SNA_OT_Uv_2F460)
    bpy.utils.register_class(SNA_OT_Uv_478D7)
    bpy.utils.register_class(SNA_OT_My_Generic_Operator_F1453)
    bpy.utils.register_class(SNA_MT_D1BE9)
    bpy.utils.register_class(SNA_OT_My_Generic_Operator_9B866)
    bpy.utils.register_class(SNA_OT_My_Generic_Operator_Ca84F)
    bpy.utils.register_class(SNA_MT_F78BB)
    bpy.utils.register_class(SNA_MT_0854C)
    bpy.utils.register_class(SNA_OT_My_Generic_Operator_23016)
    bpy.utils.register_class(SNA_OT_My_Generic_Operator_Bce76)
    bpy.utils.register_class(SNA_OT_My_Generic_Operator_44Fae)
    bpy.utils.register_class(SNA_MT_B9C05)
    bpy.utils.register_class(SNA_MT_F45E8)
    bpy.utils.register_class(SNA_OT_My_Generic_Operator_D73F1)
    bpy.utils.register_class(SNA_OT_My_Generic_Operator_83745)
    bpy.utils.register_class(SNA_MT_7B81A)
    bpy.utils.register_class(SNA_MT_3C00A)
    bpy.utils.register_class(SNA_OT_My_Generic_Operator_B023B)
    bpy.utils.register_class(SNA_OT_Xfrom_C0163)
    bpy.utils.register_class(SNA_MT_4028E)
    bpy.utils.register_class(SNA_OT_My_Generic_Operator_997D5)
    bpy.utils.register_class(SNA_OT_My_Generic_Operator_25625)
    bpy.utils.register_class(SNA_MT_F6D39)
    bpy.utils.register_class(SNA_OT_My_Generic_Operator_E5783)
    bpy.utils.register_class(SNA_MT_57AD1)
    bpy.utils.register_class(SNA_OT_Check_Start_1085A)


def unregister():
    global _icons
    bpy.utils.previews.remove(_icons)
    wm = bpy.context.window_manager
    kc = wm.keyconfigs.addon
    for km, kmi in addon_keymaps.values():
        km.keymap_items.remove(kmi)
    addon_keymaps.clear()
    del bpy.types.Scene.sna_check_class_switch
    del bpy.types.Scene.sna_check_name_filtration
    #bpy.utils.unregister_class(SNA_PT_assets_check_0FA06)
    bpy.utils.unregister_class(SNA_OT_Check_D2E47)
    bpy.types.TOPBAR_MT_editor_menus.remove(sna_add_to_topbar_mt_editor_menus_B2CEF)
    bpy.utils.unregister_class(SNA_OT_Select_All_97E08)
    bpy.utils.unregister_class(SNA_OT_My_Generic_Operator_Cc4A9)
    bpy.utils.unregister_class(SNA_OT_List_Sort_Ee0C4)
    bpy.utils.unregister_class(SNA_OT_Placeholder_3Baa5)
    bpy.utils.unregister_class(SNA_AddonPreferences_810BC)
    bpy.utils.unregister_class(SNA_OT_U_Dbcc0)
    bpy.utils.unregister_class(SNA_MT_0EF39)
    bpy.utils.unregister_class(SNA_OT_Uv_053A5)
    bpy.utils.unregister_class(SNA_OT_Uv_2F460)
    bpy.utils.unregister_class(SNA_OT_Uv_478D7)
    bpy.utils.unregister_class(SNA_OT_My_Generic_Operator_F1453)
    bpy.utils.unregister_class(SNA_MT_D1BE9)
    bpy.utils.unregister_class(SNA_OT_My_Generic_Operator_9B866)
    bpy.utils.unregister_class(SNA_OT_My_Generic_Operator_Ca84F)
    bpy.utils.unregister_class(SNA_MT_F78BB)
    bpy.utils.unregister_class(SNA_MT_0854C)
    bpy.utils.unregister_class(SNA_OT_My_Generic_Operator_23016)
    bpy.utils.unregister_class(SNA_OT_My_Generic_Operator_Bce76)
    bpy.utils.unregister_class(SNA_OT_My_Generic_Operator_44Fae)
    bpy.utils.unregister_class(SNA_MT_B9C05)
    bpy.utils.unregister_class(SNA_MT_F45E8)
    bpy.utils.unregister_class(SNA_OT_My_Generic_Operator_D73F1)
    bpy.utils.unregister_class(SNA_OT_My_Generic_Operator_83745)
    bpy.utils.unregister_class(SNA_MT_7B81A)
    bpy.utils.unregister_class(SNA_MT_3C00A)
    bpy.utils.unregister_class(SNA_OT_My_Generic_Operator_B023B)
    bpy.utils.unregister_class(SNA_OT_Xfrom_C0163)
    bpy.utils.unregister_class(SNA_MT_4028E)
    bpy.utils.unregister_class(SNA_OT_My_Generic_Operator_997D5)
    bpy.utils.unregister_class(SNA_OT_My_Generic_Operator_25625)
    bpy.utils.unregister_class(SNA_MT_F6D39)
    bpy.utils.unregister_class(SNA_OT_My_Generic_Operator_E5783)
    bpy.utils.unregister_class(SNA_MT_57AD1)
    bpy.utils.unregister_class(SNA_OT_Check_Start_1085A)
