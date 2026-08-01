import bpy
#复制出
bpy.ops.mesh.duplicate_move()
bpy.ops.mesh.separate(type='SELECTED')
bpy.ops.object.mode_set(mode='OBJECT')