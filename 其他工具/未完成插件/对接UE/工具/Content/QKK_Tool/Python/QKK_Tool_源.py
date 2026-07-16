import unreal
#ToolMenus.Edit

# 菜单拥有者名称
menu_owner = "editorUtilities"
tool_menus = unreal.ToolMenus.get()
owning_menu_name = "LevelEditor.LevelEditorToolBar.User"  # 工具栏菜单名称



# 按钮1
@unreal.uclass()
class CreateEntryExample001(unreal.ToolMenuEntryScript):
    print("a01")
    @unreal.ufunction(override=True)
    def execute(self, context):
        print("a02")
        asset = unreal.EditorAssetLibrary.load_asset("/Game/QKK_Tool/界面操作") # 加载指定路径的资产
        unreal.get_editor_subsystem(unreal.EditorUtilitySubsystem).spawn_and_register_tab(asset) # 创建并注册一个新的标签

entry = CreateEntryExample001() # 创建菜单项实例
entry.data.menu = owning_menu_name # 初始化工具栏按钮
entry.data.advanced.entry_type = unreal.MultiBlockType.TOOL_BAR_BUTTON
entry.data.icon = unreal.ScriptSlateIcon("EditorStyle", "EditorViewport.ViewportConfig_FourPanesRight")  # 设置图标
entry.init_entry(menu_owner, "editorUtilitiesExampleEntry", "分栏名称", "按钮名称", "标签名称", "按钮提示")  # 配置菜单
toolbar = tool_menus.extend_menu(owning_menu_name)  # 扩展工具栏菜单
toolbar.add_menu_entry_object(entry)  # 添加菜单项到工具栏



import unreal

# 定义要加载的资产路径
assets = [
    "/Game/QKK_Tool/功能/定位视图/记录视图_按钮_BP",
    "/Game/QKK_Tool/功能/快捷关卡/快捷关卡_按钮_BP",
    "/Game/QKK_Tool/功能/PBR通道切换/PBR通道切换_按钮_BP",
    "/Game/QKK_Tool/功能/小功能集/小功能集_按钮_BP",
    "/Game/QKK_Tool/功能/生成蓝图预制体/生成蓝图预制体_按钮_BP"
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