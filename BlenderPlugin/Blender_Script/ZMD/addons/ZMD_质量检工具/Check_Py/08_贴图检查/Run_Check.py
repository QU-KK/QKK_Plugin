import bpy

# 变量
Check_Item_Name = '图像名称'
Description = '检查图像名称是否含有 T_、+1、空格、.0、.tga'


Check_Data = [Check_Item_Name]
img_list =[]

def img_name_check(image_name,description):
    data = [image_name,description]
    Check_Data.append(data)
    img_list.append(image_name)

for obj in selected_objects:
    # 遍历物体上的所有材质槽
    for slot in obj.material_slots:
        if slot.material:
            mat = slot.material
            # 遍历材质节点树中的所有节点
            for node in mat.node_tree.nodes:            
                if node.type == 'TEX_IMAGE' and node.image:
                    image_name = node.image.name
                    if image_name not in img_list:

                        # 判断图像名称中是否包含 '+1'
                        if 'T_' not in image_name:
                            description = '图像名称不存在 T_'
                            img_name_check(image_name,description)

                        if "+1_" not in image_name:    
                            description = '图像名称不存在 +1'
                            img_name_check(image_name,description)
                            
                        if " " in image_name:    
                            description = '图像名称存在空格'
                            img_name_check(image_name,description)
                            
                        if ".0" in image_name:    
                            description = '图像名称存在 .0 '
                            img_name_check(image_name,description)
                        
                        if ".tga" not in image_name:    
                            description = '图像格式不为.tga'
                            img_name_check(image_name,description)

# 枚举
icon = 'NODE_SOCKET_SHADER'
if len(Check_Data) > 1:
    icon = 'NODE_SOCKET_MATRIX'
Check_Ui = [Check_Item_Name,Check_Item_Name, Description, icon]

# Merge Data
Check_Overall_Ui.append(Check_Ui)
Check_Overall_Data.append(Check_Data)