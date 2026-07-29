import bpy
from mathutils import Vector
# 选择物体对齐最低端

selected = list(bpy.context.selected_objects)

if not selected:
    print("没有选中任何物体")
else:
    min_z_dict = {}

    for obj in selected:
        corners = [obj.matrix_world @ Vector(corner) for corner in obj.bound_box]
        min_z_dict[obj] = min(c.z for c in corners)

    target_z = min(min_z_dict.values())

    for obj in selected:
        delta_z = target_z - min_z_dict[obj]
        obj.matrix_world.translation.z += delta_z

    print(f"对齐完成，基准 Z = {target_z:.4f}")