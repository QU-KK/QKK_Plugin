import bpy
import os

# 获取当前脚本所在目录
dir_path = os.path.dirname(os.path.abspath(__file__))
blend_path = os.path.join(dir_path, "调用", "资源", "地面.blend")

mat_name = ".地面"
mod_name = "地面"

# 1. 追加材质
if mat_name in bpy.data.materials:
    print(f"材质 '{mat_name}' 已存在，跳过追加")
else:
    with bpy.data.libraries.load(blend_path, link=False) as (data_from, data_to):
        data_to.materials = [mat_name]

# 2. 追加物体
with bpy.data.libraries.load(blend_path, link=False) as (data_from, data_to):
    data_to.objects = [mod_name]

# 3. 将追加的物体关联到当前场景集合（关键步骤）
obj = data_to.objects[0]
bpy.context.collection.objects.link(obj)
obj.material_slots[0].material = bpy.data.materials[mat_name]