import unreal

# 获取资产
if covering:
    material_path = "/Game/QKK_Tool/提效工具/通用功能/场景白膜覆盖/白膜材质"
    new_mat = unreal.EditorAssetLibrary.load_asset(material_path)
else:
    new_mat = None

# 获取选中的实例
editor_actor_subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
selected_actors = editor_actor_subsystem.get_selected_level_actors()

for actor in selected_actors:
    
    # 获取Actor的所有组件
    all_items = actor.get_components_by_class(unreal.ActorComponent)

    for item in all_items:
        # 判断组件类型是否为StaticMeshComponent
        if item.get_class().get_name() == "StaticMeshComponent":
            # 材质数量
            mat_len = len(item.get_materials())
            for mat_id in range(mat_len):
                # 材质id设置材质
                item.set_material(mat_id, new_mat)

#def Update_Seams():

# 调用函数
#functions = {
    #"VERT": VERT,
#}

#functions[func_name]()
