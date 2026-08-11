import bpy
#清理
bpy.context.view_layer.material_override = None
Mat = bpy.data.materials.get('.UV棋盘格')
if Mat:
    bpy.context.blend_data.materials.remove(Mat)