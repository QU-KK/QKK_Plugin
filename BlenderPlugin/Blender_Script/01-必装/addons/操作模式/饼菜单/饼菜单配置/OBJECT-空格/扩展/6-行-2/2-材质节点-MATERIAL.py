import bpy

bpy.ops.screen.area_split(direction='HORIZONTAL', factor=0.4)   # VERTICAL
areas = bpy.context.screen.areas
area = areas[int(len(areas) - 1.0)]
area.ui_type = 'ShaderNodeTree'