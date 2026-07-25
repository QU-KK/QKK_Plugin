import unreal

with open('C://obj_data.txt', 'r', encoding='utf-8') as f:
    for line in f:
        data = line.strip().split('~')

        obj_name = data[0]
        location = data[1]
        rotation = data[2]
        scale = data[3]

        # 修正路径格式
        path = '//Game/mod//' + obj_name
        mod = unreal.EditorAssetLibrary.load_asset(path)
        
        if mod is None:
            print(f"无法加载资产: {path}")
            continue

        # 解析位置、旋转和缩放
        loc = [float(x) for x in location.split(',')]
        rot = [float(x) for x in rotation.split(',')]
        print(rot)
        scl = [float(x) for x in scale.split(',')]

        # 创建 Actor
        actor_subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
        new_actor = actor_subsystem.spawn_actor_from_class(
            actor_class=unreal.StaticMeshActor.static_class(),
            location=loc,
            rotation=rot,
            transient=False
        )
        
        # 设置 StaticMesh
        if new_actor:
            new_actor.set_actor_label(obj_name)
            new_actor.set_actor_scale3d(scl)
            static_mesh_component = new_actor.get_component_by_class(unreal.StaticMeshComponent)
            if static_mesh_component:
                static_mesh_component.set_static_mesh(mod)
