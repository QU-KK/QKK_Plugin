import bpy
import math
import pyperclip
import os
os.system('cls')

# 获取场景中选中的所有物体
selected_objects = bpy.context.selected_objects
# 遍历选中的物体，并设置为四元数旋转
for obj in selected_objects:
    obj.rotation_mode = 'QUATERNION'
    obj.rotation_mode = 'XYZ'

pcg_list_variable = []
data = ''
for obj_mod in selected_objects:
    # 位置
    x1_in = obj_mod.location[0]*100
    y1_in = obj_mod.location[1]*100
    z1_in = obj_mod.location[2]*100
    # 旋转
    x2_in = math.degrees(obj_mod.rotation_euler.y)*-1
    y2_in = math.degrees(obj_mod.rotation_euler.z)*-1
    z2_in = math.degrees(obj_mod.rotation_euler.x)
    # 缩放
    x3_in = obj_mod.scale[0]
    y3_in = obj_mod.scale[1]
    z3_in = obj_mod.scale[2]

    x1_out = str(format(x1_in, '.6f'))
    y1_out = str(format(y1_in, '.6f'))
    z1_out = str(format(z1_in, '.6f'))
    location = x1_out + ',' + y1_out + ',' + z1_out


    x2_out = format(x2_in, '.6f')
    y2_out = format(y2_in, '.6f')
    z2_out = format(z2_in, '.6f')
    rotation = x2_out + ',' + y2_out + ',' + z2_out

    x3_out = format(x3_in, '.6f')
    y3_out = format(y3_in, '.6f')
    z3_out = format(z3_in, '.6f')
    scale = x3_out + ',' + y3_out + ',' + z3_out
    
    a = obj_mod.name + '~' + location + '~' + rotation + '~' + scale
    data = data + '\n' + a

data = data[1:]
path = r"C:\obj_data.txt"
os.makedirs(os.path.dirname(path), exist_ok=True)

with open(path, "w", encoding="utf-8") as f:
    f.write(data)
