import bpy

# 1. 删除所有场景物体（清理大纲视图中的实例）
for obj in list(bpy.data.objects):
    bpy.data.objects.remove(obj, do_unlink=True)

# 2. 删除所有网格 (Meshes)
for mesh in list(bpy.data.meshes):
    bpy.data.meshes.remove(mesh, do_unlink=True)

# 3. 删除所有材质 (Materials)
for mat in list(bpy.data.materials):
    bpy.data.materials.remove(mat, do_unlink=True)

# 4. 删除所有导入/生成的图像 (Images - 包含外部纹理、HDRI贴图等)
for img in list(bpy.data.images):
    bpy.data.images.remove(img, do_unlink=True)

# 5. 删除所有世界环境 (Worlds - 包含环境天空节点、背景设置)
for world in list(bpy.data.worlds):
    bpy.data.worlds.remove(world, do_unlink=True)

# 6. 删除所有节点组 (Node Groups - 外部导入或自定义的着色器/几何节点)
for ng in list(bpy.data.node_groups):
    bpy.data.node_groups.remove(ng, do_unlink=True)

# 7. 删除灯光、摄像机、曲线、体积等基础数据块
for light in list(bpy.data.lights):
    bpy.data.lights.remove(light, do_unlink=True)
for cam in list(bpy.data.cameras):
    bpy.data.cameras.remove(cam, do_unlink=True)
for curve in list(bpy.data.curves):
    bpy.data.curves.remove(curve, do_unlink=True)
for volume in list(bpy.data.volumes):
    bpy.data.volumes.remove(volume, do_unlink=True)

# 8. 删除所有动画动作/关键帧 (Actions)
for action in list(bpy.data.actions):
    bpy.data.actions.remove(action, do_unlink=True)

# 9. 删除所有集合 (Collections)
for col in list(bpy.data.collections):
    bpy.data.collections.remove(col, do_unlink=True)

# 10. 删除所有链接的外部库文件 (Libraries - 清理关联的外部 .blend 数据)
for lib in list(bpy.data.libraries):
    bpy.data.libraries.remove(lib, do_unlink=True)

# 11. 彻底清理孤立残留缓存 (Purge Orphan Data)
# 循环执行多次，确保相互关联的数据（如节点组依赖图像）被层层剥离并完全清理
for _ in range(4):
    bpy.data.orphans_purge(do_local_ids=True, do_linked_ids=True, do_recursive=True)

print("当前 Blender 文件已彻底清空所有环境、外部数据以及关联的库文件！")