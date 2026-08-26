import bpy

# 移除材质
bpy.context.view_layer.material_override = None
Mat = bpy.data.materials.get('.UV像素密度可视化')
if Mat:
    bpy.context.blend_data.materials.remove(Mat)