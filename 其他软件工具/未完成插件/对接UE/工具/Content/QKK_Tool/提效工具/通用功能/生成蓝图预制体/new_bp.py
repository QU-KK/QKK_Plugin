import unreal
# 获取选中的资产
asset_data_list  = unreal.EditorUtilityLibrary.get_selected_asset_data()
print(asset_data_list)
for asset_data in asset_data_list:
    asset_name = asset_data.asset_name
    asset_path = asset_data.package_name
    asset_class_name = asset_data.asset_class_path.asset_name
    
    if asset_class_name == "StaticMesh":
        static_mesh = unreal.EditorAssetLibrary.load_asset(str(asset_path))
        
        bp_name = str(asset_name) + '_BP'
        package = '/Game/Blueprints/'
        package_path = package + bp_name
    
        if unreal.EditorAssetLibrary.does_asset_exist(package + bp_name):
            print('存在有')
        else:
            print('没有')

            # 创建蓝图资产
            blueprint_factory = unreal.BlueprintFactory()
            blueprint_factory.set_editor_property("ParentClass", unreal.Actor)
            
            # 创建蓝图
            blueprint = unreal.AssetToolsHelpers.get_asset_tools().create_asset(
                asset_name=bp_name,
                package_path=package,
                asset_class=unreal.Blueprint,
                factory=blueprint_factory
            )
