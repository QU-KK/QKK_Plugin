import bpy
#四边化
bpy.ops.mesh.tris_convert_to_quads('INVOKE_DEFAULT', uvs=True, materials=True)