import bpy
import os

deleted_count = 0

for img in list(bpy.data.images):
    # 仅处理来源为外部文件的图像（排除渲染结果、查看器图像等）
    if img.source == 'FILE':
        # 如果图像已经打包到 .blend 文件中，说明它没有丢失
        if img.packed_file:
            continue
            
        # 将 Blender 的相对路径转换为操作系统的绝对路径
        abs_path = bpy.path.abspath(img.filepath)
        
        # 如果路径为空，或者文件在硬盘上不存在，则删除该图像数据
        if not img.filepath or not os.path.exists(abs_path):
            print(f"清理丢失图像: {img.name} (原路径: {img.filepath})")
            bpy.data.images.remove(img)
            deleted_count += 1
            
print(f"清理完成！共删除了 {deleted_count} 个丢失路径的图像。")

