import bpy
# 按类型选择Mesh
bpy.ops.object.select_by_type(extend=False, type='MESH')
# 数据唯一化
bpy.ops.object.make_single_user(type='SELECTED_OBJECTS', object=True, obdata=True, material=False, animation=False, obdata_animation=False)