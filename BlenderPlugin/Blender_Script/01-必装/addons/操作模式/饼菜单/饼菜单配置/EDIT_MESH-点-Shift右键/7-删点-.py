import bpy
#删点
bpy.ops.mesh.dissolve_verts('INVOKE_DEFAULT', use_face_split=False, use_boundary_tear=False)