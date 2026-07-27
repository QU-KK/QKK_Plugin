import bpy
# 冻结旋转 缩放
bpy.ops.object.transform_apply(location=False, rotation=True, scale=True)