import bpy

selected_objs = bpy.context.selected_objects

lod_processed = 0
col_shadow_processed = 0

for obj in selected_objs:
    if obj.type == 'MESH':
        name = obj.name
        uv_layers = obj.data.uv_layers

        # 条件 1：模型名称包含 '_lod' (使用 lower() 兼容大小写如 _LOD)
        if '_lod' in name.lower():
            if len(uv_layers) > 2:
                while len(uv_layers) > 2:
                    uv_layers.remove(uv_layers[-1])
                lod_processed += 1
                print(f"[LOD处理] {name}: UV 已裁剪至 2 个")

        # 条件 2：模型名称包含 '_COL' 或 '_shadowProxy'
        elif "_COL" in name or "_shadowProxy" in name:
            if len(uv_layers) > 0:
                while len(uv_layers) > 0:
                    uv_layers.remove(uv_layers[-1])
                col_shadow_processed += 1
                print(f"[清空UV] {name}: 所有 UV 已清空")

print(f"处理完成！LOD 模型处理: {lod_processed} 个，碰撞/阴影代理模型处理: {col_shadow_processed} 个。")