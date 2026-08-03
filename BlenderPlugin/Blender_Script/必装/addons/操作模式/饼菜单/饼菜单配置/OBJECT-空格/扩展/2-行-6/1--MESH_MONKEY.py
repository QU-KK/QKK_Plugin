import bpy
# 新建猴头
bpy.ops.mesh.primitive_monkey_add()

# 平滑着色
bpy.ops.object.modifier_add(type='SUBSURF', use_selected_objects=True)
bpy.ops.object.shade_auto_smooth(use_auto_smooth=True, angle=3)
bpy.ops.object.convert(target='MESH')
bpy.context.object.data.uv_layers[0].name = "1U"