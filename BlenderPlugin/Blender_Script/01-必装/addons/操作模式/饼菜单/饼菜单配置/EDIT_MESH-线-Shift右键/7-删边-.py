import bpy
#删边
bpy.ops.mesh.dissolve_edges('INVOKE_DEFAULT', use_verts=True, angle_threshold=3.14159, use_face_split=False, use_preserve_quads=True)