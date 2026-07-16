import bpy

# 直接遍历 Blender 里的所有图像文件
for img in bpy.data.images:
    # 统一将A通道设置为 “通道打包”
    img.alpha_mode = 'CHANNEL_PACKED'
    
    # 直接使用原始名称进行字符串包含判断
    if ("_N." in img.name) or ("_NRO." in img.name) or ("_M." in img.name):
        img.colorspace_settings.name = 'Non-Color'
        print(f"贴图 [{img.name}] 已直接设置为: Non-Color")
        
    elif ("_D." in img.name) or ("_E." in img.name):
        img.colorspace_settings.name = 'sRGB'
        print(f"贴图 [{img.name}] 已直接设置为: sRGB")