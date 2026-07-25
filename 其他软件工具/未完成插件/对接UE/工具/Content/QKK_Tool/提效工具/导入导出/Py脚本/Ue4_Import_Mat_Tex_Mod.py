import unreal
import json
import os

# 获取Json数据
def Get_Json():
    # 设置要读取的 JSON 文件路径
    file_path = 'C:\\Blender_UE\\Blender-Ue\\Mat.json'  # 确保使用双反斜杠
    with open(file_path, 'r', encoding='utf-8') as json_file:
        # 解析 JSON 数据
        json_data = json.load(json_file)
        # 删除首个元素
        if json_data:  # 确保列表不为空
            json_data.pop(0)
        for data in json_data:
            print('    开始导入')
            Mat_Path = data['Mat_Path']  # 材质路径
            Mat_Name = data['Mat_Name']  # 材质名称
            Shader_Name = data['Shader_Name']  # 着色器名称
            Parameters = data['Parameters']  # 参数
            Tex_Path = data['Tex_Path']  # 图像路径
            Images = data['Images']  # 图像

            # 检查材质实例是否存在
            Mat_Ins_Path = Mat_Path + '/' + Mat_Name
            if not unreal.EditorAssetLibrary.does_asset_exist(Mat_Ins_Path):
                print('    新建材质:',Mat_Name)
                # 新建材质实例
                Material_Instance = New_Mat_Ins(Mat_Name,Mat_Path)

                if Shader_Name != 'None':
                    print('    Shader:',Shader_Name)
                    Set_Shader(Material_Instance,Shader_Name,Shader_Directory_Path)  # 设置着色器
                    print('    参数:',Parameters)
                    Set_Parameters(Material_Instance, Parameters)  # 设置参数
                    print('    图像:',Images)
                    Set_Images(Material_Instance, Images,Tex_Path)  # 设置图像
                else:
                    print('    无Shader,使用空材质')

# 新建材质实例
def New_Mat_Ins(Mat_Name,Mat_Path):
    # 准备创建工具
    asset_tools = unreal.AssetToolsHelpers.get_asset_tools()
    material_instance_factory = unreal.MaterialInstanceConstantFactoryNew()
    # 创建材质实例
    Material_Instance = asset_tools.create_asset(
        asset_name=Mat_Name,  # 只需提供实例的名称
        package_path=Mat_Path,  # 包路径
        asset_class=unreal.MaterialInstanceConstant,  # 资产类型
        factory=material_instance_factory
    )
    return Material_Instance


# 设置Shader
def Set_Shader(Material_Instance,Shader_Name,Shader_Directory_Path):
    Shader_Path = Shader_Directory_Path + '/' + Shader_Name
    Shader = unreal.load_asset(Shader_Path)
    Material_Instance.set_editor_property('parent', Shader)


# 设置参数
def Set_Parameters(Material_Instance,Parameters):
    # 参数属于 Shader 逻辑，必须使用 MaterialEditingLibrary
    set_shader_param = unreal.MaterialEditingLibrary

    for Param in Parameters:
        param_name = Param.split('=')[0]  # 获取参数名称
        param_value = Param.split('=')[1]  # 获取参数值

        # 根据参数值的格式设置值
        if len(param_value.split(',')) == 1:
            value = float(param_value)
            set_shader_param.set_material_instance_scalar_parameter_value(Material_Instance, param_name, value)

        if len(param_value.split(',')) == 4:
            value = [float(v.strip()) for v in param_value.split(',')]
            set_shader_param.set_material_instance_vector_parameter_value(Material_Instance, param_name, value)

        if len(param_value.split(',')) == 3:
            value = [float(v.strip()) for v in param_value.split(',')]
            value.append(1)
            set_shader_param.set_material_instance_vector_parameter_value(Material_Instance, param_name, value)

# 设置图像
def Set_Images(Material_Instance, Images,Tex_Path):
    for image_node in Images:
        node_name = image_node.split('=')[0]  # 获取节点名称
        image_path = image_node.split('=')[1]  # 获取图像路径
        image_name = os.path.basename(image_path).replace(os.path.splitext(image_path)[1],'')# 获取图像文件名无扩展名
        asset_path = Tex_Path + '/' + image_name

        if not unreal.EditorAssetLibrary.does_asset_exist(asset_path):
            # 检查图像是否已存在且路径有效
            if os.path.exists(image_path):
                import_image(image_path,Tex_Path)

        texture = unreal.load_asset(asset_path)
        # 参数属于 Shader 逻辑，必须使用 MaterialEditingLibrary
        set_shader_param = unreal.MaterialEditingLibrary
        set_shader_param.set_material_instance_texture_parameter_value(Material_Instance, node_name, texture)


# 导入图像
def import_image(image_path,Tex_Path):
    print('    导入图像')
    # 因为import_asset_tasks需要的参数是数组Array，所以我们先把import_tasks设成list
    import_tasks = []

    file = unreal.AssetImportTask()
    # 按照属性描述，设置属性
    file.set_editor_property("automated",True)# 是否避免弹框对话
    file.set_editor_property("destination_name","")# 资产重命名，若空字符串则为文件原名
    file.set_editor_property("destination_path",Tex_Path)# 资产存放路径
    file.set_editor_property("filename",image_path)# 从哪里导入文件
    file.set_editor_property("replace_existing",True)# 是否覆盖现在资产
    file.set_editor_property("replace_existing_settings",False)# 覆盖时是否替换现在设置
    file.set_editor_property("save",False)# 导入后是否保存

    # 最后把对象添加到我们的列表里面
    import_tasks.append(file)
    unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks(import_tasks)


def Import_FBX():
    print('    导入FBX')

    file_path = 'C:\\Blender_UE\\Blender-Ue\\Mat.json'  # 确保使用双反斜杠
    with open(file_path, 'r', encoding='utf-8') as json_file:
        # 解析 JSON 数据
        json_data = json.load(json_file)
        # 获取第一个元素
        first_element = json_data[0]
        Mesh_Path = first_element['Mesh_Path']  # 材质路径



    # 获取FBX导入任务
    import_task = unreal.AssetImportTask()
    import_task.filename = "C:\\Blender_UE\\Blender-Ue\\.fbx" # 使用变量设置文件路径
    #import_task.destination_name = ""  # 设置导入后的静态模型名称
    import_task.destination_path = Mesh_Path #project_path  # Unreal Engine 中的导入路径
    import_task.replace_existing = True
    import_task.automated = True #自动化 导入面板控制
    import_task.save = False #保存资产

    # 设置导入的选项
    fbx_import_options = unreal.FbxImportUI()
    static_mesh_import_data = fbx_import_options.static_mesh_import_data
    #fbx_import_options.import_mesh = False  #是否导入网格
    #fbx_import_options.import_as_skeletal = False  # 是否作为骨骼网格导入

    # 材质,纹理选项
    if Mat_Import:
        fbx_import_options.texture_import_data.material_search_location = unreal.MaterialSearchLocation.UNDER_PARENT
    else:
        fbx_import_options.texture_import_data.material_search_location = unreal.MaterialSearchLocation.DO_NOT_SEARCH  # 材质搜索位置DO_NOT_SEARCH 不搜索 ALL_ASSETS 所有 LOCAL 本地 UNDER_ROOT 根目录  UNDER_PARENT 父目录下
    fbx_import_options.import_materials = Mat_Import  # 是否导入材质
    fbx_import_options.import_textures = False  # 是否导入纹理


    # 网格选项
    static_mesh_import_data.auto_generate_collision = False  # 自动生成碰撞

    #网格高级配置
    #static_mesh_import_data.static_mesh_lod_group = None  # LOD组
    static_mesh_import_data.vertex_color_import_option = unreal.VertexColorImportOption.REPLACE  # 顶点颜色导入选项: REPLACE替换, IGNORE忽略, OVERRIDE覆盖
    static_mesh_import_data.vertex_override_color = unreal.Color(255,255,255,255)  # 覆盖颜色, 仅在 OVERRIDE 选项时有效
    static_mesh_import_data.remove_degenerates = True  # 移除退化
    static_mesh_import_data.build_adjacency_buffer = True  # 构建邻接缓冲
    static_mesh_import_data.build_reversed_index_buffer = True  # 构建反向索引缓冲
    static_mesh_import_data.generate_lightmap_u_vs = False  # 生成光照贴图 UV
    static_mesh_import_data.one_convex_hull_per_ucx = False  # 每UCX一个顶点   (ue 4 5不同)
    static_mesh_import_data.combine_meshes = False  # 合并网格
    static_mesh_import_data.bake_pivot_in_vertex = False  # 烘焙顶点中的枢轴
    static_mesh_import_data.transform_vertex_to_absolute = True  # 将顶点转换为绝对坐标
    static_mesh_import_data.import_mesh_lo_ds = False  # 导入 LOD
    static_mesh_import_data.normal_import_method = unreal.FBXNormalImportMethod.FBXNIM_IMPORT_NORMALS  # 法线导入
    static_mesh_import_data.normal_generation_method = unreal.FBXNormalGenerationMethod.MIKK_T_SPACE  # 法线生成方式
    static_mesh_import_data.compute_weighted_normals = True  # 计算加权法线

    # 变换
    static_mesh_import_data.import_translation = unreal.Vector(0.0, 0.0, 0.0)  # 导入平移
    static_mesh_import_data.import_rotation = unreal.Rotator(0.0, 0.0, 0.0)  # 导入旋转
    static_mesh_import_data.import_uniform_scale = 1  # 导入统一缩放比例

    # 应用导入选项
    static_mesh_import_data.convert_scene = True  # 是否转换场景
    static_mesh_import_data.force_front_x_axis = False  # 是否强制使用 X 轴
    static_mesh_import_data.convert_scene_unit = False  # 是否转换场景单位

    #关闭按文件名称命名
    fbx_import_options.override_full_name = False # 覆盖全名

    import_task.options = fbx_import_options
    # 执行导入任务
    unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks([import_task])
    print('    导入完成')


# Shader仓库
Shader_Directory_Path = '/Game/QKK_Tool/提效工具/导入导出/Shader'
# 是否导入材质贴图
Mat_Import = True



# 导入材质+贴图
if Mat_Import:
    Get_Json()

# FBX
Import_FBX()