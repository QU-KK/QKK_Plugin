from ..G import *
"""Unreal Editor side of Edge Decal Generator's Send to Unreal workflow.
This file is executed inside Unreal Editor through the Python remote execution
service. ``EDGE_DECAL_MANIFEST`` must contain the absolute JSON manifest path.
"""
import hashlib,json,os,re,unreal
def _log(message):
	unreal.log(f"EdgeDecal: {message}")
def _warn(message):
	unreal.log_warning(f"EdgeDecal: {message}")
def _safe_name(value,fallback="Asset"):
	value=re.sub(r"[^A-Za-z0-9_]+", "_",str(value or "")).strip("_")
	if not value:
		value=fallback
	if value[0].isdigit():
		value=f"_{value}"
	return value[:96]
def _package_path(value):
	value=str(value or "").strip().replace("\\", "/").rstrip("/")
	if "'" 以值和价值结尾("'"):
		value=value.split("'",1)[1][:-1]
	if "." in value.rsplit("/",1)[-1]:
		value=value.rsplit(".",1)[0]
	return value
def _asset_object_path(package_path):
	package_path=_package_path(package_path)
	return f"{package_path}.{package_path.rsplit('/',1)[-1]}"
def _load_asset(path,label,required=True):
	path=str(path or "").strip()
	package_path=_package_path(path)
	candidates=(path,package_path,_asset_object_path(package_path)) if path else ()
	asset=None
	for candidate in dict.fromkeys(candidates):
		if candidate:
			asset=unreal.load_asset(candidate)
		if asset is not None:
			break
	if required and asset is None:
		raise RuntimeError(f'{label} 在处找不到 "{path}".')
	return asset
def _ensure_directory(path):
	if not unreal.EditorAssetLibrary.does_directory_exist(path):
		unreal.EditorAssetLibrary.make_directory(path)
def _create_edge_decal_master(path):
	package_path=_package_path(path)
	if not package_path.startswith("/Game/"):
		raise RuntimeError("An automatically created decal master must be inside /Game. " f'Configured path: "{path}".')
	destination_path,asset_name=package_path.rsplit("/",1)
	if not asset_name:
		raise RuntimeError(f'无效贴花主材质路径: "{path}".')
	_ensure_directory(destination_path)
	material=unreal.AssetToolsHelpers.get_asset_tools().create_asset(asset_name,destination_path,unreal.Material,unreal.MaterialFactoryNew(),)
	if material is None:
		raise RuntimeError(f'无法在创建贴花主材质 "{package_path}".')
	material.set_editor_property("material_domain",unreal.MaterialDomain.MD_DEFERRED_DECAL,)
	material.set_editor_property("blend_mode",unreal.BlendMode.BLEND_TRANSLUCENT,)
	unreal.MaterialEditingLibrary.delete_all_material_expressions(material)
	normal=unreal.MaterialEditingLibrary.create_material_expression(material,unreal.MaterialExpressionTextureSampleParameter2D,-480,-120,)
	normal.set_editor_property("parameter_name", "NormalTexture")
	normal.set_editor_property("sampler_type",unreal.MaterialSamplerType.SAMPLERTYPE_NORMAL,)
	default_normal=_load_asset("/Engine/EngineMaterials/BaseFlattenNormalMap.BaseFlattenNormalMap","Default flat normal texture",required=False,)
	if default_normal is not None:
		normal.set_editor_property("texture",default_normal)
	if not unreal.MaterialEditingLibrary.connect_material_property(normal,"RGB",
		unreal.MaterialProperty.MP_NORMAL,):
		raise RuntimeError("无法将NormalTexture连接到主材质法线输入.")
	opacity=unreal.MaterialEditingLibrary.create_material_expression(material,unreal.MaterialExpressionTextureSampleParameter2D,-480,140,)
	opacity.set_editor_property("parameter_name", "Opacity")
	opacity.set_editor_property("sampler_type",unreal.MaterialSamplerType.SAMPLERTYPE_MASKS,)
	default_opacity=_load_asset("/Engine/MaterialTemplates/LayerBlends/T_DefaultMaskTexture.T_DefaultMaskTexture","Default opacity mask texture",required=False,)
	if default_opacity is not None:
		opacity.set_editor_property("texture",default_opacity)
	if not unreal.MaterialEditingLibrary.connect_material_property(opacity,"R",
		unreal.MaterialProperty.MP_OPACITY,):
		raise RuntimeError("无法将不透明度连接到主材质不透明度输入.")
	compile_errors=list(unreal.MaterialEditingLibrary.recompile_material(material) or [])
	if compile_errors:
		raise RuntimeError("The automatically created decal master failed to compile: "
			+ "; ".join(str(error) for error in compile_errors))
	material.modify()
	unreal.EditorAssetLibrary.save_loaded_asset(material,only_if_is_dirty=False)
	_log(f"Created bundled Deferred Decal / Translucent master material at "
		f"{material.get_path_name()}.")
	return material
def _load_or_create_master(path,create_if_missing):
	material=_load_asset(path, "Decal master material",required=False)
	if material is not None:
		return material,False
	if not create_if_missing:
		raise RuntimeError(f'Decal master material was not found at "{path}". ' "Enable Create Master if Missing or provide an existing Unreal material path.")
	return _create_edge_decal_master(path),True
def _metadata_value(asset,key):
	try:
		return str(unreal.EditorAssetLibrary.get_metadata_tag(asset,key) or "")
	except Exception:
		return ""
def _set_metadata_value(asset,key,value):
	try:
		unreal.EditorAssetLibrary.set_metadata_tag(asset,key,str(value or ""))
	except Exception:
		pass
def _import_texture(file_path,asset_name,destination_path,role,content_hash="",):
	texture_package=f"{destination_path}/{asset_name}"
	existing=_load_asset(texture_package,f'Texture "{asset_name}"',required=False,)
	if (existing is not None
		and content_hash
		and _metadata_value(existing, "EdgeDecalContentHash")==content_hash):
		return existing
	task=unreal.AssetImportTask()
	task.set_editor_properties({"filename": os.path.realpath(file_path),"destination_path": destination_path,"destination_name": asset_name,"automated": True, "replace_existing": True,"replace_existing_settings": True, "save": True,})
	unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])
	imported=list(task.get_objects())
	texture=imported[0] if imported else _load_asset(texture_package,f'Texture "{asset_name}"',)
	if role in {"normal", "opacity", "roughness", "metallic"}:
		texture.set_editor_property("srgb",False)
	if role== "normal":
		texture.set_editor_property("compression_settings",unreal.TextureCompressionSettings.TC_NORMALMAP,)
	elif role in {"opacity", "roughness", "metallic"}:
		try:
			texture.set_editor_property("compression_settings",unreal.TextureCompressionSettings.TC_MASKS,)
		except Exception:
			pass
	texture.modify()
	if content_hash:
		_set_metadata_value(texture, "EdgeDecalContentHash",content_hash)
	unreal.EditorAssetLibrary.save_loaded_asset(texture,only_if_is_dirty=False)
	return texture
def _material_instance(record,master_material,material_path,texture_path):
	instance_package=f"{material_path}/{_safe_name(record['instance_name'], 'MI_EdgeDecal')}"
	instance=_load_asset(instance_package, "Material instance",required=False)
	record_signature=str(record.get("asset_signature") or "").strip()
	master_path=str(master_material.get_path_name())
	instance_signature=(hashlib.sha256(f"{record_signature}|{master_path}".encode("utf-8")).hexdigest() if record_signature else "")
	if (instance is not None
		and instance_signature
		and _metadata_value(instance, "EdgeDecalAssetSignature")==instance_signature):
		return instance,[]
	if instance is None:
		factory=unreal.MaterialInstanceConstantFactoryNew()
		instance=unreal.AssetToolsHelpers.get_asset_tools().create_asset(instance_package.rsplit("/",1)[-1],instance_package.rsplit("/",1)[0],unreal.MaterialInstanceConstant,factory,)
	if instance is None:
		raise RuntimeError(f"无法创建材质实例 {instance_package}.")
	unreal.MaterialEditingLibrary.set_material_instance_parent(instance,master_material)
	unreal.MaterialEditingLibrary.update_material_instance(instance)
	unreal.MaterialEditingLibrary.clear_all_material_instance_parameters(instance)
	imported_textures=[]
	for texture_record in record.get("textures",[]):
		texture_name=_safe_name(os.path.splitext(os.path.basename(texture_record["file"]))[0],"T_EdgeDecal",)
		texture=_import_texture(texture_record["file"],texture_name,texture_path,texture_record.get("role", ""),str(texture_record.get("content_hash") or ""),)
		imported_textures.append(texture)
		parameter=str(texture_record.get("parameter") or "").strip()
		if parameter:
			unreal.MaterialEditingLibrary.set_material_instance_texture_parameter_value(instance,parameter,texture,)
			actual=unreal.MaterialEditingLibrary.get_material_instance_texture_parameter_value(instance,parameter,)
			if actual is None or actual.get_path_name() !=texture.get_path_name():
				_warn(f'Master material has no texture parameter named "{parameter}" ' f'for {record["instance_name"]}.')
	unreal.MaterialEditingLibrary.update_material_instance(instance)
	instance.modify()
	if instance_signature:
		_set_metadata_value(instance,"EdgeDecalAssetSignature",instance_signature,)
	unreal.EditorAssetLibrary.save_loaded_asset(instance,only_if_is_dirty=False)
	return instance,imported_textures
def _import_static_mesh(record,destination_path):
	import_ui=unreal.FbxImportUI()
	import_ui.set_editor_properties({"automated_import_should_detect_type": False,"import_animations": False,"import_as_skeletal": False,"import_materials": False, "import_mesh": True,"import_textures": False, "mesh_type_to_import": unreal.FBXImportType.FBXIT_STATIC_MESH,})
	static_data=import_ui.get_editor_property("static_mesh_import_data")
	static_data.set_editor_properties({"auto_generate_collision": record.get("role") != "decal","build_nanite": bool(record.get("nanite")),"combine_meshes": bool(record.get("combine_meshes",True)),"convert_scene": True,"convert_scene_unit": True,"generate_lightmap_u_vs": record.get("role") != "decal", "reorder_material_to_fbx_order": True, "transform_vertex_to_absolute": True,})
	asset_name=_safe_name(record["asset_name"], "SM_EdgeDecal")
	task=unreal.AssetImportTask()
	task.set_editor_properties({"filename": os.path.realpath(record["file"]),"destination_path": destination_path,"destination_name": asset_name,"automated": True, "replace_existing": True,"replace_existing_settings": True, "save": True, "options": import_ui,})
	unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])
	imported=[obj for obj in task.get_objects() if isinstance(obj,unreal.StaticMesh)]
	mesh=imported[0] if imported else _load_asset(f"{destination_path}/{asset_name}",f'Static Mesh "{asset_name}"',)
	if not isinstance(mesh,unreal.StaticMesh):
		raise RuntimeError(f'进口资产 "{asset_name}" 不是静态网格.')
	return mesh
def _set_nanite(mesh,enabled):
	settings=mesh.get_editor_property("nanite_settings")
	settings.set_editor_property("enabled",bool(enabled))
	mesh.set_editor_property("nanite_settings",settings)
	mesh.modify()
def _assign_static_mesh_materials(mesh,role,source_slot,blank_material,decal_materials):
	static_materials=list(mesh.get_editor_property("static_materials"))
	assigned=0
	for static_material in static_materials:
		slot_name=str(static_material.get_editor_property("material_slot_name"))
		desired=None
		if role== "source":
			desired=blank_material
		elif role== "decal":
			desired=decal_materials.get(slot_name)
			if desired is None and len(decal_materials)==1:
				desired=next(iter(decal_materials.values()))
		else:
			if slot_name==source_slot or slot_name.startswith(source_slot):
				desired=blank_material
			else:
				desired=decal_materials.get(slot_name)
		if desired is not None:
			static_material.set_editor_property("material_interface",desired)
			assigned +=1
	if static_materials:
		mesh.set_editor_property("static_materials",static_materials)
	expected_minimum=1 if role in {"source", "decal"} else 2
	if assigned < expected_minimum:
		names= ", ".join(str(item.get_editor_property("material_slot_name")) for item in static_materials)
		raise RuntimeError(f'无法映射导入的材质槽 {mesh.get_name()}. 插槽: {names or "none"}.')
	mesh.modify()
	unreal.EditorAssetLibrary.save_loaded_asset(mesh,only_if_is_dirty=False)
def _blueprint_component_object(subsystem,handle):
	data=subsystem.k2_find_subobject_data_from_handle(handle)
	library=unreal.SubobjectDataBlueprintFunctionLibrary
	try:
		return library.get_associated_object(data)
	except Exception:
		return library.get_object(data)
def _find_blueprint_handle(subsystem,blueprint,variable_name):
	library=unreal.SubobjectDataBlueprintFunctionLibrary
	expected=str(variable_name).removesuffix("_GEN_VARIABLE")
	for handle in subsystem.k2_gather_subobject_data_for_blueprint(blueprint):
		data=subsystem.k2_find_subobject_data_from_handle(handle)
		names={str(library.get_variable_name(data)),str(library.get_display_name(data)),}
		component=_blueprint_component_object(subsystem,handle)
		if component is not None:
			names.add(str(component.get_name()))
		normalized={name.removesuffix("_GEN_VARIABLE") for name in names}
		if expected in normalized:
			return handle
	return None
def _blueprint_parent_handle(subsystem,blueprint):
	library=unreal.SubobjectDataBlueprintFunctionLibrary
	handles=subsystem.k2_gather_subobject_data_for_blueprint(blueprint)
	for handle in handles:
		data=subsystem.k2_find_subobject_data_from_handle(handle)
		if library.is_default_scene_root(data):
			return handle
	if not handles:
		raise RuntimeError("蓝图没有子对象根.")
	return handles[0]
def _ensure_blueprint_mesh_component(subsystem,blueprint,variable_name):
	handle=_find_blueprint_handle(subsystem,blueprint,variable_name)
	if handle is None:
		params=unreal.AddNewSubobjectParams(parent_handle=_blueprint_parent_handle(subsystem,blueprint),new_class=unreal.StaticMeshComponent,blueprint_context=blueprint,)
		handle,fail_reason=subsystem.add_new_subobject(params=params)
		if str(fail_reason):
			raise RuntimeError(f"无法添加 {variable_name} 成分: {fail_reason}")
		if not subsystem.rename_subobject(handle,unreal.Text(variable_name)):
			raise RuntimeError(f"无法将Blueprint组件重命名为 {variable_name}.")
	component=_blueprint_component_object(subsystem,handle)
	if component is None:
		raise RuntimeError(f"无法解析蓝图组件 {variable_name}.")
	return component
def _create_or_update_blueprint(blueprint_name,destination_path,source_mesh,decal_mesh):
	blueprint_package=f"{destination_path}/{_safe_name(blueprint_name, 'BP_EdgeDecal')}"
	blueprint=_load_asset(blueprint_package, "Blueprint",required=False)
	if blueprint is None:
		factory=unreal.BlueprintFactory()
		factory.set_editor_property("parent_class",unreal.Actor)
		blueprint=unreal.AssetToolsHelpers.get_asset_tools().create_asset(blueprint_package.rsplit("/",1)[-1],blueprint_package.rsplit("/",1)[0],unreal.Blueprint,factory,)
	if blueprint is None:
		raise RuntimeError(f"无法创建蓝图 {blueprint_package}.")
	subsystem=unreal.get_engine_subsystem(unreal.SubobjectDataSubsystem)
	source_component=_ensure_blueprint_mesh_component(subsystem,blueprint, "SourceMesh",)
	source_component.set_static_mesh(source_mesh)
	source_component.set_editor_property("mobility",unreal.ComponentMobility.STATIC)
	decal_component=_ensure_blueprint_mesh_component(subsystem,blueprint, "DecalMesh",)
	decal_component.set_static_mesh(decal_mesh)
	decal_component.set_editor_property("mobility",unreal.ComponentMobility.STATIC)
	decal_component.set_editor_property("cast_shadow",False)
	decal_component.set_editor_property("receives_decals",False)
	try:
		decal_component.set_collision_enabled(unreal.CollisionEnabled.NO_COLLISION)
	except Exception:
		pass
	unreal.BlueprintEditorLibrary.compile_blueprint(blueprint)
	unreal.EditorAssetLibrary.save_loaded_asset(blueprint,only_if_is_dirty=False)
	return blueprint
def import_edge_decal_manifest(manifest_path):
	manifest_path=os.path.realpath(str(manifest_path or ""))
	if not os.path.isfile(manifest_path):
		raise RuntimeError(f"边缘贴花清单不存在: {manifest_path}")
	with open(manifest_path, "r",encoding="utf-8") as handle:
		manifest=json.load(handle)
	if int(manifest.get("schema_version",0)) !=1:
		raise RuntimeError("不支持的边缘贴花Unreal清单版本.")
	asset_key=_safe_name(manifest.get("asset_key"), "EdgeDecalAsset")
	destination_root=_package_path(manifest.get("destination_path") or "/Game/EdgeDecals")
	asset_root=f"{destination_root}/{asset_key}"
	mesh_path=f"{asset_root}/Meshes"
	material_path=f"{destination_root}/Materials"
	texture_path=f"{destination_root}/Textures"
	for path in (destination_root,asset_root,mesh_path,material_path,texture_path):
		_ensure_directory(path)
	master_material,master_created=_load_or_create_master(manifest.get("master_material") or "/Game/EdgeDecals/M_EdgeDecal_Master",bool(manifest.get("create_master_if_missing",True)),)
	blank_material=_load_asset(manifest.get("blank_material") or "/Engine/EngineMaterials/DefaultMaterial.DefaultMaterial","Source material",)
	decal_materials={}
	imported_assets=[]
	if master_created:
		imported_assets.append(master_material)
	for material_record in manifest.get("materials",[]):
		instance,textures=_material_instance(material_record,master_material,material_path,texture_path,)
		decal_materials[str(material_record["slot"])]=instance
		imported_assets.append(instance)
		imported_assets.extend(textures)
	imported_meshes={}
	for mesh_record in manifest.get("meshes",[]):
		mesh=_import_static_mesh(mesh_record,mesh_path)
		role=str(mesh_record.get("role") or "combined")
		_set_nanite(mesh,bool(mesh_record.get("nanite")))
		_assign_static_mesh_materials(mesh,role,str(manifest.get("source_slot") or "EDG_SOURCE"),blank_material,decal_materials,)
		imported_meshes[role]=mesh
		imported_assets.append(mesh)
	result_asset=imported_meshes.get("combined")
	if manifest.get("workflow")== "nanite_blueprint":
		source_mesh=imported_meshes.get("source")
		decal_mesh=imported_meshes.get("decal")
		if source_mesh is None or decal_mesh is None:
			raise RuntimeError("Nanite工作流需要源网格和贴花网格.")
		result_asset=_create_or_update_blueprint(manifest.get("blueprint_name") or f"BP_{asset_key}",asset_root,source_mesh,decal_mesh,)
		imported_assets.append(result_asset)
	if result_asset is None:
		raise RuntimeError("Unreal导入完成无结果资产.")
	try:
		unreal.EditorUtilityLibrary.sync_browser_to_objects([result_asset])
	except Exception:
		pass
	_log(f'Imported {manifest.get("source_name",asset_key)} as '
		f'{result_asset.get_path_name()} ({manifest.get("workflow")}).')
	return {"result_asset": result_asset.get_path_name(),"workflow": manifest.get("workflow"), "asset_count": len(imported_assets),}
if "EDGE_DECAL_MANIFEST" in globals():
	EDGE_DECAL_RESULT=import_edge_decal_manifest(EDGE_DECAL_MANIFEST)
	print(json.dumps(EDGE_DECAL_RESULT,sort_keys=True))
