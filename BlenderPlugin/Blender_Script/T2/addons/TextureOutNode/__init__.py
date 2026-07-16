bl_info = {
    "name": "Texture Out Node",
    "blender": (2, 82, 0),
    "category": "Node",
    "description": "The node used to derive the texture.",
    "author": "uabol",
    "version": (1, 0),
}

import bpy
import os
import re
from bpy.types import Node, Operator, NodeTree
from bpy.props import StringProperty, EnumProperty, IntProperty


class TextureOutNode(Node):
    '''Custom Node for exporting texture'''
    bl_idname = 'texture_out'
    bl_label = "Texture Out"
    bl_icon = 'TEXTURE'

    filepath: bpy.props.StringProperty(
        name="File Path",
        description="Path to save exported texture",
        default="//Texture\out.png",
        subtype='FILE_PATH'
    )

    color_space: EnumProperty(
        name="Color Space",
        items=[
            ('sRGB', "sRGB", ""),
            ('Non-Color', "Non-Color", ""),
        ],
        default='sRGB',
        description="Select color space"
    )

    depth: EnumProperty(
        name="Depth",
        items=[
            ('8', "8-bit", ""),
            ('32', "32-bit Float", ""),
        ],
        default='8',
        description="Select texture depth"
    )

    size: EnumProperty(
        name="size",
        items=[
            ('512', "512x512", ""),
            ('1024', "1024x1024", ""),
            ('2048', "2048x2048", ""),
            ('4096', "4096x4096", ""),
        ],
        default='1024',
        description="Select baking texture size"
    )

    Samples: EnumProperty(
        name="Samples",
        items=[
            ('2', "2", ""),
            ('4', "4", ""),
            ('8', "8", ""),
            ('16', "16", ""),
            ('32', "32", ""),
            ('64', "64", ""),
            ('128', "128", ""),
            ('256', "256", ""),
            ('512', "512", ""),
            ('1024', "1024", ""),
        ],
        default='16',
        description="Select Sample Count"
    )

    Based: EnumProperty(
        name="Based",
        items=[
            ('UV', "UV", "Use object UV"),
            ('Tiled', "Tiled", "Use tetragonal continuous"),
        ],
        default='UV',
        description="Based on what type"
    )

    def init(self, context):
        self.inputs.new("NodeSocketColor", "Color")
        self.width = 300  # 设置节点宽度为300

    def draw_buttons(self, context, layout):
        layout.separator()  # 添加分隔线

        row_filepath = layout.row()
        row_filepath.prop(self, "filepath", text="")

        layout.separator()  # 添加分隔线

        # 这是参数设置面板 ##############################

        # 创建一个主面板
        box = layout.box()

        # 创建行
        row1 = box.row()

        row1.prop(self, "size", text="Size")

        # 创建行
        row2 = box.row()

        row2.prop(self, "color_space", text="Color Space")
        row2.prop(self, "Based", text="Based")

        # 创建行
        row3 = box.row()

        row3.prop(self, "Samples", text="Samples")
        row3.prop(self, "depth", text="Depth")

        #################################################

        layout.separator()  # 添加分隔线

        row = layout.row(align=False)
        save_button = row.operator("texture.save_to_disk", text="Save to Disk", icon='FILE_TICK')
        save_button.node_name = self.name  # 传递当前节点的名称

        get_texture_button = row.operator("texture.get_texture", text="Get Texture", icon='TEXTURE')
        get_texture_button.node_name = self.name  # 传递当前节点的名称

        layout.separator()  # 添加分隔线


class SaveToDiskOperator(Operator):
    bl_idname = "texture.save_to_disk"
    bl_label = "Save Texture to Disk"

    node_name: StringProperty()  # 用于获取节点名称

    def execute(self, context):
        # 设置为OBJECT模式
        bpy.ops.object.mode_set(mode='OBJECT')

        # 确保目标对象被选中并设置为活动对象
        bpy.ops.object.select_all(action='DESELECT') # 取消选择所有对象
        bpy.context.active_object.select_set(True)  # 选择当前活动对象

        # 记录原始渲染设置
        original_samples = context.scene.cycles.samples
        # 记录原始渲染采样
        original_Engine = context.scene.render.engine

        # 设置为Cy渲染器
        context.scene.render.engine = 'CYCLES'

        # 设置渲染设备为GPU
        import _cycles
        if bpy.context.preferences.addons['cycles'].preferences.compute_device_type != "NONE":
            bpy.context.scene.cycles.device = 'GPU'

        # 取消多精度物体烘焙选项
        bpy.context.scene.render.bake.use_multires = False

        # 设置观察方向为表面上方
        bpy.context.scene.render.bake.view_from = "ABOVE_SURFACE"
        # 取消使用高低模模式
        bpy.context.scene.render.bake.use_selected_to_active = False
        # 设置输出目标为图像纹理
        bpy.context.scene.render.bake.target = 'IMAGE_TEXTURES'
        # 设置烘焙UV边距类型
        bpy.context.scene.render.bake.margin_type = 'EXTEND'
        # 设置边距大小为2px
        bpy.context.scene.render.bake.margin = 2

        # 记录原始活动对象
        original_active_object = context.active_object

        # 判断选中的节点，或单独执行当前节点
        selected_nodes = [node for node in context.active_object.active_material.node_tree.nodes if
                          node.select and isinstance(node, TextureOutNode)]
        if not selected_nodes:
            # 如果没有选中节点，找到并执行当前按钮所属的节点
            current_node = context.active_object.active_material.node_tree.nodes.get(self.node_name)
            if current_node and isinstance(current_node, TextureOutNode):
                selected_nodes = [current_node]

        for node in selected_nodes:
            color_socket = node.inputs.get('Color')
            if not color_socket or not color_socket.is_linked:
                print(f"Error: Color input of node '{node.name}' is not connected!")
                continue

            linked_node_output = color_socket.links[0].from_socket
            if linked_node_output is None:
                print(f"Error: Linked node output of node '{node.name}' not found!")
                continue

            obj = context.active_object  # 记录活动对象

            current_material = obj.active_material  # 记录当前材质
            if node.Based == 'Tiled':
                bpy.ops.mesh.primitive_plane_add(size=2, enter_editmode=False, align='WORLD')
            else:
                # 复制当前物体并设为活动项并取消选择其他对象
                bpy.ops.object.duplicate()
                # 进入编辑模式
                bpy.ops.object.mode_set(mode='EDIT')
                # 取消选中全部面
                bpy.ops.mesh.select_all(action='DESELECT')
                # 选中当前材质指定的面
                bpy.ops.object.material_slot_select()
                # 反转选择
                bpy.ops.mesh.select_all(action='INVERT')
                # 删除选中的面
                bpy.ops.mesh.delete(type='FACE')
                # 退出编辑模式
                bpy.ops.object.mode_set(mode='OBJECT')
                # 删除全部材质插槽
                bpy.context.active_object.data.materials.clear()

            obj = context.active_object
            obj.select_set(True)
            obj.name = "BakeTempObject"
            # 将当前材质赋值给临时对象
            obj.data.materials.append(current_material)  # 赋值当前材质到临时对象

            # 获取用户选择的烘焙尺寸
            size = int(node.size)  # 将字符串转换为整数
            image = bpy.data.images.new("BakedImage", width=size, height=size, float_buffer=(node.depth == "32"))
            print(f"Info: Created new image for baking from node '{node.name}'.")

            # 创建图像纹理节点并设置为活动项
            texture_node = obj.active_material.node_tree.nodes.new('ShaderNodeTexImage')
            texture_node.image = image
            texture_node.location = (node.location.x + 350, node.location.y)  # 在 X 轴右侧且与 Texture Out 节点对齐
            texture_node.select = True  # 选中图像纹理节点
            context.view_layer.objects.active = obj  # 确保当前活动对象为目标对象
            obj.active_material.node_tree.nodes.active = texture_node  # 设置为活动节点
            texture_node.image.colorspace_settings.name = node.color_space# 设置图像的色彩空间

            mat = obj.active_material
            if not mat.use_nodes:
                mat.use_nodes = True

            tree = mat.node_tree
            output_node = next((n for n in tree.nodes if n.type == 'OUTPUT_MATERIAL'), None)
            if output_node is None:
                print(f"Error: Material Output node not found for node '{node.name}'!")
                continue

            # 记录现有链接的输入端
            existing_links = [link.from_socket for link in output_node.inputs['Surface'].links]
            # 断开现有链接
            for link in output_node.inputs['Surface'].links:
                tree.links.remove(link)
            print(f"Info: Disconnected existing links from Material Output for node '{node.name}'.")

            # 连接 Color 输入端的节点到 Material Output 的 Surface 输入
            tree.links.new(linked_node_output, output_node.inputs['Surface'])
            print(f"Info: Linked Color input to Material Output for node '{node.name}'.")

            # 检查路径格式是否有效，可以根据需要调整正则表达式
            def is_valid_filepath(filepath):
                return bool(
                    re.match(r'^[A-Za-z]:\\(?:[^<>:"/\\|?*\x00-\x1F]+\\)*[^<>:"/\\|?*\x00-\x1F]+\.[A-Za-z0-9]+$',
                             filepath)) or \
                    bool(
                        re.match(r'^(//|/)([^<>:"/\\|?*\x00-\x1F]+/)*[^<>:"/\\|?*\x00-\x1F]+\.[A-Za-z0-9]+$', filepath))

            filepath = bpy.path.abspath(node.filepath)

            if not is_valid_filepath(filepath):
                filepath = bpy.path.abspath("//Texture\out.png")
                self.report({'ERROR'}, "Path error, image will be saved in default path: //Texture\out.png")
            image.filepath_raw = filepath

            scene = context.scene
            scene.render.bake.use_clear = True
            scene.render.bake.use_selected_to_active = False
            scene.cycles.bake_type = 'EMIT'  # 保持为 Emit 类型以捕捉自发光

            # 设置采样数
            scene.cycles.samples = int(node.Samples)  # 获取节点中的采样数设置

            # 开始烘焙
            bpy.ops.object.bake(type='EMIT')  # 确保烘焙类型为 Emit

            # 保存烘焙图像
            image.save()

            # 提示成功保存图像
            self.report({'INFO'}, f"Texture saved to: {image.filepath_raw} for node '{self.name}'.")

            # 恢复原有链接
            for from_socket in existing_links:
                # 重新连接到 Material Output 的 Surface 输入
                tree.links.new(from_socket, output_node.inputs['Surface'])
            print(f"Info: Restored original links to Material Output for node '{node.name}'.")

            # 删除图像纹理节点
            obj.active_material.node_tree.nodes.remove(texture_node)

            # 删除烘焙图像
            bpy.data.images.remove(image)

            # 清理临时对象
            bpy.data.meshes.remove(obj.data)

        # 恢复原始渲染设置
        context.scene.cycles.samples = original_samples
        context.scene.render.engine = original_Engine
        # 恢复原始活动对象
        context.view_layer.objects.active = original_active_object
        original_active_object.select_set(True)

        return {'FINISHED'}

    def show_message(self, title, message):
        def draw_func(self, context):
            self.layout.label(text=message)

        bpy.context.window_manager.popup_menu(draw_func, title=title, icon='INFO')


class GetTextureOperator(Operator):
    bl_idname = "texture.get_texture"
    bl_label = "Get Texture"

    node_name: StringProperty()  # 用于获取节点名称

    def execute(self, context):
        selected_nodes = [node for node in context.active_object.active_material.node_tree.nodes if
                          node.select and isinstance(node, TextureOutNode)]
        if not selected_nodes:
            current_node = context.active_object.active_material.node_tree.nodes.get(self.node_name)
            if current_node and isinstance(current_node, TextureOutNode):
                selected_nodes = [current_node]

        for node in selected_nodes:
            image_path = bpy.path.abspath(node.filepath)

            try:
                # 检查是否已有图像纹理节点指向该路径
                existing_texture_node = next(
                    (n for n in context.active_object.active_material.node_tree.nodes if
                     n.type == 'TEX_IMAGE' and n.image.filepath == image_path),
                    None
                )
                if existing_texture_node:
                    existing_texture_node.image.reload()  # 重新加载图像
                    existing_texture_node.image.colorspace_settings.name = node.color_space  # 更新色彩空间
                    print(f"Info: Updated existing Image Texture Node for node '{node.name}'.")
                else:
                    # 创建新的图像纹理节点
                    texture_node = context.active_object.active_material.node_tree.nodes.new('ShaderNodeTexImage')
                    texture_node.location = (node.location.x + 350, node.location.y)  # 在 X 轴右侧且与 Texture Out 节点对齐
                    context.active_object.active_material.node_tree.nodes.active = texture_node  # 设置为活动节点

                    # 尝试加载图像
                    texture_node.image = bpy.data.images.load(image_path)
                    texture_node.image.colorspace_settings.name = node.color_space  # 设置色彩空间
                    print(f"Info: Created new Image Texture Node with path: {node.filepath} for node '{node.name}'.")

            except Exception:
                # 删除新建的空节点并打印错误提示
                print("Error: Texture not found, please export first.")
                if 'texture_node' in locals() and texture_node:
                    context.active_object.active_material.node_tree.nodes.remove(texture_node)  # 删除空图像纹理节点
                return {'CANCELLED'}

        return {'FINISHED'}


def add_texture_out_node_menu(self, context):
    if context.space_data.type == 'NODE_EDITOR' and context.space_data.tree_type == 'ShaderNodeTree':
        self.layout.operator("node.add_node", text="Texture Out").type = "texture_out"


def register():
    # bpy.utils.register_class(TextureOutNodeTree)
    bpy.utils.register_class(TextureOutNode)
    bpy.utils.register_class(SaveToDiskOperator)
    bpy.utils.register_class(GetTextureOperator)
    bpy.types.NODE_MT_add.append(add_texture_out_node_menu)

    # 注册回调以在场景依赖图更新后执行操作
    #def post_depsgraph_update(dummy):
        # 在执行之前检查是否已经存在此材质
        #if "ConvertToTangentSpaceNormal" not in bpy.data.materials:
            #from . import ConvertToTangentSpaceNormal
    #bpy.app.handlers.depsgraph_update_post.append(post_depsgraph_update)


def unregister():
    # bpy.utils.unregister_class(TextureOutNodeTree)
    bpy.utils.unregister_class(TextureOutNode)
    bpy.utils.unregister_class(SaveToDiskOperator)
    bpy.utils.unregister_class(GetTextureOperator)
    bpy.types.NODE_MT_add.remove(add_texture_out_node_menu)


if __name__ == "__main__":
    register()
