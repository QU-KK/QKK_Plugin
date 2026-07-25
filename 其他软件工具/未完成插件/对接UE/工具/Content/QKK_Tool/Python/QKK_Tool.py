import unreal
tool_menus = unreal.ToolMenus.get()
# 定义要加载的资产路径
assets = [
    #其他
    "/Game/QKK_Tool/提效工具/其他/开发辅助/小功能集_按钮_BP",
    #通用功能
    "/Game/QKK_Tool/提效工具/通用功能/定位视图/记录视图_按钮_BP",
    "/Game/QKK_Tool/提效工具/通用功能/快捷关卡/快捷关卡_按钮_BP",
    "/Game/QKK_Tool/提效工具/通用功能/PBR通道切换/PBR通道切换_按钮_BP",    
    "/Game/QKK_Tool/提效工具/通用功能/生成蓝图预制体/生成蓝图预制体_按钮_BP",
    "/Game/QKK_Tool/提效工具/通用功能/图像PS打开/图像PS打开_按钮_BP",
]

# 获取编辑器实用程序子系统
utility_subsystem = unreal.get_editor_subsystem(unreal.EditorUtilitySubsystem)

# 遍历资产路径并尝试加载和运行每个资产
for asset_path in assets:
    # 加载指定路径的资产
    asset = unreal.EditorAssetLibrary.load_asset(asset_path)
    
    # 检查资产是否成功加载
    if asset is not None:
        # 运行编辑器实用程序蓝图
        utility_subsystem.try_run(asset)
    else:
        unreal.log_warning(f"无法加载资产: {asset_path}")


tool_menus.refresh_all_widgets()  # 刷新所有小部件