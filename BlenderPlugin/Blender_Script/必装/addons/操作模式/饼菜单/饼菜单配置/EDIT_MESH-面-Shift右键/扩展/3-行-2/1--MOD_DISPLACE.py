import bpy
#三角化
bpy.ops.mesh.quads_convert_to_tris('INVOKE_DEFAULT', quad_method='BEAUTY', ngon_method='BEAUTY')