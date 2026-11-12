import bpy
def join(window,source,target):
    with bpy.context.temp_override(window=window,area=source):
        bpy.ops.screen.area_join(source_xy=(source.x+source.width//2,source.y+source.height//2),target_xy=(target.x+target.width//2,target.y+target.height//2))
