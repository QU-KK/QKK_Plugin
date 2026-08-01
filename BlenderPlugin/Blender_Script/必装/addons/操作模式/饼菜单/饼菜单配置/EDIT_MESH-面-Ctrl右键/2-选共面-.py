import bpy
#选共面
bpy.ops.mesh.select_similar('INVOKE_DEFAULT', type='FACE_COPLANAR', compare='EQUAL', threshold=0.001)