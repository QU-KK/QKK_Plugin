import bpy

# 变量
Check_Item_Name = '图像'
Description = '检查图像名称是否含有 T_、+1、空格、.0、.tga，判断名称字段数'


Check_Data = [Check_Item_Name]
img_list =[]

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
                        img_list.append(image_name)
                        description = ''

                        # 判断图像名称中是否包含 '+1'
                        if 'T_' not in image_name:
                            description = description + '缺少T_    '

                        if "+1_" not in image_name:
                            description = description + '缺少+1    '
                            
                        if " " in image_name:    
                            description = description + '存在空格    '
                            
                        if ".0" in image_name:    
                            description = description + '存在 .0    '
                        
                        if ".tga" not in image_name:    
                            description = description + '格式不为.tga    '

                        if len(image_name.split('_')) != 7 and '+1_' in image_name and '_rgb_M' not in image_name:
                            description = description + '字段数错误'

                        if len(image_name.split('_')) != 8 and '+1_' in image_name and '_rgb_M' in image_name:
                            description = description + '字段数错误'
                        
                        X=node.image.size[0]
                        Y=node.image.size[1]
                        if X>2048 or Y>2048:
                            description = '尺寸大于2048    ' + str(X) +'*'+ str(Y)


                        if description != '':
                            data = [image_name,description]
                            Check_Data.append(data)

# 枚举
icon = 'NODE_SOCKET_SHADER'
if len(Check_Data) > 1:
    icon = 'NODE_SOCKET_MATRIX'
Check_Ui = [Check_Item_Name,Check_Item_Name, Description, icon]

# Merge Data
Check_Overall_Ui.append(Check_Ui)
Check_Overall_Data.append(Check_Data)