struct MenuHandler (
	fn getMenuOrCreate menuName =(
		main = menuMan.getMainMenuBar()
		menu = menuMan.findMenu menuName
		if(menu==undefined)then(
			menu = menuMan.createMenu menuName
			item = menuMan.createSubMenuItem menuName menu
			main.addItem item (main.numItems()+1)
			menuMan.updateMenuBar()
		)
		menu
	),
	fn deleteMenu menuName =(
		menu = menuMan.findMenu menuName
		if(menu!=undefined)then(
			menuMan.unregisterMenu menu
		)
		menuMan.updateMenuBar()
	),
	fn AddMenuItem _menu _macroName _categoryName = (
		_menu.addItem (menuMan.createActionItem _macroName _categoryName) (_menu.numItems()+1)
		menuMan.updateMenuBar()
	),
	fn deleteMenuItem _menu _itemName =(
		for i=_menu.numItems() to 1 by -1 do(
			if((_menu.getItem i).getTitle()==_itemName)then(
				_menu.removeItembyPosition i
			)
		)
		menuMan.updateMenuBar()
	),
	fn ClearAllMenuItems _menu=(
		for i=1 to _menu.numItems() do(
			_menu.removeItemByPosition 1
		)
		menuMan.updateMenuBar()
	)
)

macroScript pluginGenMacro buttonText:"启动插件" category:"Blender_To_Max" tooltip:""(
	
        rollout ro_pluginRoll  "Blender-Max互导" width:220 height:110
        (
	        button 'btn1' "导入至Max" pos:[10,30] width:100 height:35 align:#left
	        button 'btn2' "导出至Blender" pos:[110,30] width:100 height:70 align:#left
	        button 'btn3' "导入带有平滑组" pos:[10,65] width:100 height:35 align:#left
                label 'lbl1' "显示: 米       系统: 1单位 = 1米" pos:[15,10] width:220 height:12 enabled:true align:#left

	        on btn1 pressed  do
        (
                        FBXImporterSetParam "Mode" #create
		        FBXImporterSetParam"ConvertUnit" "m"  
		        FBXImporterSetParam"ScaleFactor" 1
                        FBXImporterSetParam "SmoothingGroups"  false

		        FBXImporterSetParam "Animation"  false
		        FBXImporterSetParam "Cameras"  false
                        FBXImporterSetParam "Lights"  false
                        FBXImporterSetParam "GenerateLog"  True
                        FBXImporterSetParam "ShowWarnings"  True

		        ImportFile"C:\Blender_Cache\BlenderToMax\Qkk_BlenderToMax.FBX"#noPrompt using:FBXIMP
	        )

	        on btn2 pressed  do
        (

                        FBXImporterSetParam"ConvertUnit" "m"   
                        FBXImporterSetParam"ScaleFactor" 1  
                        FBXExporterSetParam "UpAxis" "z"

                        FBXExporterSetParam "SmoothingGroups" false
                        FBXExporterSetParam "NormalsPerPoly" false
                        FBXExporterSetParam "TangentSpaceExport" false
                        FBXExporterSetParam "SmoothMeshExport" false
                        FBXExporterSetParam "Preserveinstances" false
                        FBXExporterSetParam "SelectionSetExport" false
                        FBXExporterSetParam "GeomAsBone" false
                        FBXExporterSetParam "Triangulate" false

                        FBXExporterSetParam "Animation"  false  
                        FBXExporterSetParam "Cameras" false
                        FBXImporterSetParam "Lights"  false
                        FBXImporterSetParam "EmbedTextures"  false
                        FBXImporterSetParam "GenerateLog"  True
                        FBXImporterSetParam "ShowWarnings"  True

                        FBXImporterSetParam "ASCII"  false
                        FBXImporterSetParam "FileVersion"  FBX201400

                        ExportFile "C:\Blender_Cache\BlenderToMax\Qkk_MaxToBlender"#noPrompt  selectedOnly:true using:FBXEXP
                )

	        on btn3 pressed  do
        (
                        FBXImporterSetParam "Mode" #create
		        FBXImporterSetParam"ConvertUnit" "m"  
		        FBXImporterSetParam"ScaleFactor" 1
                        FBXImporterSetParam "SmoothingGroups"  True

		        FBXImporterSetParam "Animation"  false
		        FBXImporterSetParam "Cameras"  false
                        FBXImporterSetParam "Lights"  false
                        FBXImporterSetParam "GenerateLog"  True
                        FBXImporterSetParam "ShowWarnings"  True

		        ImportFile"C:\Blender_Cache\BlenderToMax\Qkk_BlenderToMax.FBX"#noPrompt using:FBXIMP
	        )

        )
	createdialog ro_pluginRoll

)
MH = MenuHandler()
menu =MH.getMenuOrCreate "Blender_To_Max"
MH.deleteMenuItem menu "Blender_Max互导插件"
MH.AddMenuItem menu "pluginGenMacro" "Blender_To_Max"
--MH.ClearAllMenuItems menu
-- MH.deleteMenu "Blender_To_Max"

