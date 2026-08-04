import bpy
#解包文件并且路径绝对化
bpy.ops.file.unpack_all('INVOKE_DEFAULT', method='USE_LOCAL')
bpy.ops.file.make_paths_absolute('INVOKE_DEFAULT', )