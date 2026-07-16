import bpy
import mathutils
import pyperclip
import os
os.system('cls')

# 获取场景中选中的所有物体
selected_objects = bpy.context.selected_objects
# 遍历选中的物体，并设置为四元数旋转
for obj in selected_objects:
    obj.rotation_mode = 'QUATERNION'
    obj.rotation_mode = 'YXZ'
pcg_list_variable = []
for i_F6FA0 in range(len(bpy.context.view_layer.objects.selected)):
    x1_in = float(bpy.context.view_layer.objects.selected[i_F6FA0].location[0] * -1.0)
    y1_in = bpy.context.view_layer.objects.selected[i_F6FA0].location[1]
    z1_in = bpy.context.view_layer.objects.selected[i_F6FA0].location[2]
    x2_in = float(bpy.context.view_layer.objects.selected[i_F6FA0].rotation_euler[0] * -1.0)
    y2_in = bpy.context.view_layer.objects.selected[i_F6FA0].rotation_euler[1]
    z2_in = bpy.context.view_layer.objects.selected[i_F6FA0].rotation_euler[2]
    x3_in = bpy.context.view_layer.objects.selected[i_F6FA0].scale[0]
    y3_in = bpy.context.view_layer.objects.selected[i_F6FA0].scale[1]
    z3_in = bpy.context.view_layer.objects.selected[i_F6FA0].scale[2]
    x1_out = None
    y1_out = None
    z1_out = None
    x2_out = None
    y2_out = None
    z2_out = None
    x3_out = None
    y3_out = None
    z3_out = None
    x1_out = format(x1_in, '.6f')
    y1_out = format(y1_in, '.6f')
    z1_out = format(z1_in, '.6f')
    x2_out = format(x2_in, '.6f')
    y2_out = format(y2_in, '.6f')
    z2_out = format(z2_in, '.6f')
    x3_out = format(x3_in, '.6f')
    y3_out = format(y3_in, '.6f')
    z3_out = format(z3_in, '.6f')
    pcg_list_variable.append('[' + "'" + bpy.context.view_layer.objects.selected[i_F6FA0]['Messiah_GUID'] + "'" + ',' + "'" + str(x1_out) + ',' + str(z1_out) + ',' + str(y1_out) + "'" + ',' + "'" + str(x2_out) + ',' + str(z2_out) + ',' + str(y2_out) + "'" + ',' + "'" + str(x3_out) + ',' + str(z3_out) + ',' + str(y3_out) + "'" + ']')
    text = pcg_list_variable
    output = '\n'.join(text)
    pyperclip.copy(output)