import bpy
Mat_Name = 'PM_Glass'
Mat = bpy.data.materials.get(Mat_Name)
if Mat == None:
    # 创建材质
    Mat = bpy.context.blend_data.materials.new(Mat_Name)

# 激活的材质槽ID
Mat_ID = bpy.context.active_object.active_material_index
# 设置材质
bpy.context.active_object.material_slots[Mat_ID].material = Mat