import bpy

# 储存图像
tex_img_list = []
material = bpy.context.active_object.active_material

# get Principled BSDF 节点
principled_node = material.node_tree.nodes.get('Principled BSDF')
        
if principled_node:
    
    Base_Color = principled_node.inputs.get('Base Color')
    if Base_Color.is_linked:
        # 获取links第一个元素
        Color_Img = Base_Color.links[0].from_node.image
        if Color_Img:
            tex_img_list.append(['Color',Color_Img])
            Color_Img = None

        
    Normal = principled_node.inputs.get('Normal')
    if Normal.is_linked:
        # 获取迭代器里的元素
        node = Normal.links[0].from_node.inputs.get('Color')
        Normal_Img = node.links[0].from_node.image
        if Normal_Img:
            tex_img_list.append(['NRO',Normal_Img])
            Normal_Img = None

print(tex_img_list)


# 设置Shader材质
Shader_Name = 'ZMD_Lit_Two'
Blender_Path = 'C:\\Blender_Shader\\ZMD_Lit_Two.blend\\Material\\'

# 清理重名的旧材质，防止冲突
Old_Mat = bpy.data.materials.get(Shader_Name)
if Old_Mat:
    bpy.data.materials.remove(Old_Mat)

# 追加外部材质并修正节点组引用
bpy.ops.wm.append(directory=Blender_Path, filename=Shader_Name, link=False)
New_Mat = bpy.data.materials.get(Shader_Name)
Node_Name = New_Mat.node_tree.nodes['Shader'].node_tree.name
if Node_Name != Shader_Name:
    New_Mat.node_tree.nodes['Shader'].node_tree = bpy.data.node_groups[Shader_Name]
    bpy.data.node_groups.remove(bpy.data.node_groups[Node_Name])

# 记录当前物体材质，并临时替换为新材质
Active_Mat = bpy.context.active_object.active_material
bpy.context.active_object.active_material = New_Mat

# 切换至材质编辑器，复制新材质的节点
bpy.context.area.ui_type = 'ShaderNodeTree'
bpy.ops.node.select_all(action='SELECT')
bpy.ops.node.clipboard_copy()
# 删除临时材质
bpy.context.blend_data.materials.remove(material=New_Mat)

# 清空原材质节点   将复制的节点粘贴到原材质中，并切回3D视图
Active_Mat.node_tree.nodes.clear()
bpy.context.active_object.active_material = Active_Mat
bpy.context.area.ui_type = 'ShaderNodeTree'
bpy.ops.node.select_all(action='SELECT')
bpy.ops.node.clipboard_paste()
bpy.context.area.ui_type = 'VIEW_3D'

bpy.context.view_layer.objects.active.select_set(True)


# 应用贴图
for data in tex_img_list:
    Active_Mat.node_tree.nodes[data[0]].image = data[1]
tex_img_list = []