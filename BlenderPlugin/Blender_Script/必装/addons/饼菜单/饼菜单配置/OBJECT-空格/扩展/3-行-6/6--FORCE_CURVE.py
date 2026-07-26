import bpy
# 新建曲线
bpy.ops.curve.primitive_bezier_curve_add()
bpy.ops.object.mode_set(mode='EDIT')
bpy.ops.curve.select_all(action='SELECT')
bpy.ops.curve.delete(type='VERT')
bpy.ops.wm.tool_set_by_id(name="builtin.draw")