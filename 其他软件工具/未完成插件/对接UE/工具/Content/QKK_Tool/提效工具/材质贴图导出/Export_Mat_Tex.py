import unreal
import json

# 获取材质数据
def Get_Mat_Data(input_mat_name,Merge_Json,Repeat_Tex_List):
    print('获取材质:',input_mat_name)
    # 搜索位置：所有资产
    all= unreal.MaterialSearchLocation.ALL_ASSETS
    # 查找材质
    data = unreal.MaterialImportHelpers.find_existing_material_from_search_location(
    material_full_name = input_mat_name, 
    base_package_path = '/Game/', 
    search_location = all
    )
    # 从元组中提取材质对象（第一个元素）
    mat = data[0]
    if mat:
        print('    材质对象:',mat)
        Mat_Name = mat.get_name()
        Shader_Name = unreal.MaterialInterface.get_base_material(mat).get_name()

        # 获取所有参数名称,调用材质编辑库
        scalar_parameter_names_list = unreal.MaterialEditingLibrary.get_scalar_parameter_names(mat)
        vector_parameter_names_list = unreal.MaterialEditingLibrary.get_vector_parameter_names(mat)
        texture_parameter_names_list = unreal.MaterialEditingLibrary.get_texture_parameter_names(mat)

        print('    开始获取材质参数')
        Value_list = []
        Image_list = []
        # 获取标量参数值
        for parameter_name in scalar_parameter_names_list:
            scalar = unreal.MaterialEditingLibrary.get_material_instance_scalar_parameter_value (mat, parameter_name, association=unreal.MaterialParameterAssociation.GLOBAL_PARAMETER)
            # 格式化输出，保留小数点后4为
            data = f"{parameter_name}={scalar:.4f}"
            Value_list.append(data)

        # 获取向量参数值
        for parameter_name in vector_parameter_names_list:
            vector = unreal.MaterialEditingLibrary.get_material_instance_vector_parameter_value (mat, parameter_name, association=unreal.MaterialParameterAssociation.GLOBAL_PARAMETER)
            # 拆分颜色向量为字符串
            r = vector.r
            g = vector.g
            b = vector.b
            a = vector.a
            # 格式化输出，保留小数点后4为
            data = f"{parameter_name}={r:.4f}, {g:.4f}, {b:.4f}, {a:.4f}"
            Value_list.append(data)

        # 获取纹理参数值
        for parameter_name in texture_parameter_names_list:
            texture = unreal.MaterialEditingLibrary.get_material_instance_texture_parameter_value (mat, parameter_name, association=unreal.MaterialParameterAssociation.GLOBAL_PARAMETER)
            # 获取贴图名称，判断贴图是否存在
            if texture:
                # 直接获取贴图名称
                tex_name = texture.get_name()
                Export_path = "C:\\Blender_UE\\Ue_Mat_Export\\Tex\\"  # 可自定义
                data = f"{parameter_name}={Export_path}{tex_name}{'.tga'}"
                Image_list.append(data)
                input_mat_name
                print('    获取纹理:',tex_name)
                if tex_name not in Repeat_Tex_List:
                    Repeat_Tex_List.append(tex_name)
                    export_path = f"{Export_path}{tex_name}{'.tga'}"
                    Export_Texture(texture,export_path)
        
        # 导出材质数据json
        json_data = {  # 创建一个字典用于存储材质信息
            'Mat_Name': Mat_Name,  # 材质名称
            'Shader_Name': Shader_Name,  # Shader名称
            'Parameters': Value_list,  # 参数列表
            'Images': Image_list    # 图像列表
        }    
        Merge_Json.append(json_data)  # 将字典添加到合并的JSON列表中
    
    else:
        print('    材质不存在')

# 导出资产贴图
def Export_Texture(texture,export_path):
    task = unreal.AssetExportTask()
    task.set_editor_property('object', texture) #物体
    task.set_editor_property('filename', export_path) #路径+名称
    task.set_editor_property('replace_identical', True)  # 替换已存在的文件
    task.set_editor_property('prompt', False) #对话框
    task.set_editor_property('automated', False) #自动处理，不显示UI
    # 执行导出任务
    unreal.Exporter.run_asset_export_task(task)

mat_names_list = ['01_mat','02_mat']
Merge_Json = [] 
Repeat_Tex_List = []  # 重复贴图列表初始化

for input_mat_name in mat_names_list:
    Get_Mat_Data(input_mat_name,Merge_Json,Repeat_Tex_List)


if Merge_Json:
    # 导出为json
    file_path = 'C:\\Blender_UE\\Ue_Mat_Export\\Mat.json'  # JSON文件路径
    # 将数据写入 JSON 文件
    with open(file_path, 'w', encoding='utf-8') as json_file:  # 打开文件进行写入
        json.dump(Merge_Json, json_file, indent=4, ensure_ascii=False)  # 将合并的JSON数据写入文件
    print('获取完成已经导出')
else:
    print('没有指定的材质')