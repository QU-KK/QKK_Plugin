from ..G import *
"""Section removal,layer locking/selection/add/delete/visibility,layer UI,and main sidebar panel.
Loaded into the add-on package shared namespace by __init__.py.
"""
class EDGEDECAL_OT_remove_decal_sections(Operator):
	bl_idname= "object.edge_decal_remove_sections";bl_label= g("Remove Decal Sections");bl_description=("进入交互式模式，每个断开的贴花有一红色目标\n 截面；单击目标以删除该节");bl_options={"REGISTER", "UNDO", "BLOCKING"}
	_draw_handle=None
	_components=None
	_hovered_index=-1
	_mouse_region=(0,0)
	_target_radius=18.0
	_undo_stack=None
	@classmethod
	def poll(cls,context):
		return (context.area is not None
			and context.area.type== "VIEW_3D"
			and context.mode== "OBJECT"
			and active_generated_decal(context) is not None)
	def _collect_components(self,obj):
		mesh=obj.data
		if not mesh.polygons:
			return []
		vertex_to_polygons={}
		for polygon in mesh.polygons:
			for vertex_index in polygon.vertices:
				vertex_to_polygons.setdefault(vertex_index,[]).append(polygon.index)
		adjacency={polygon.index: set() for polygon in mesh.polygons}
		for users in vertex_to_polygons.values():
			if len(users) < 2:
				continue
			for polygon_index in users:
				adjacency[polygon_index].update(other for other in users if other !=polygon_index)
		unvisited=set(adjacency)
		components=[]
		world_matrix=obj.matrix_world
		while unvisited:
			start=unvisited.pop()
			stack=[start]
			polygon_indices={start}
			while stack:
				polygon_index=stack.pop()
				for neighbor in adjacency[polygon_index]:
					if neighbor in unvisited:
						unvisited.remove(neighbor)
						polygon_indices.add(neighbor)
						stack.append(neighbor)
			vertex_indices=sorted({vertex_index for polygon_index in polygon_indices for vertex_index in mesh.polygons[polygon_index].vertices})
			if not vertex_indices:
				continue
			center=Vector((0.0,0.0,0.0))
			for vertex_index in vertex_indices:
				center +=world_matrix @ mesh.vertices[vertex_index].co
			center /=len(vertex_indices)
			components.append({"polygons": sorted(polygon_indices),"vertices": vertex_indices, "center": center,})
		return components
	def _projected_targets(self,context):
		region=context.region
		region_3d=context.space_data.region_3d
		targets=[]
		for component_index,component in enumerate(self._components or []):
			point_2d=view3d_utils.location_3d_to_region_2d(region,region_3d,component["center"],)
			if point_2d is not None:
				targets.append((component_index,point_2d))
		return targets
	def _update_hover(self,context):
		mouse=Vector(self._mouse_region)
		best_index=-1
		best_distance=self._target_radius + 7.0
		for component_index,point_2d in self._projected_targets(context):
			distance=(point_2d - mouse).length
			if distance < best_distance:
				best_distance=distance
				best_index=component_index
		self._hovered_index=best_index
	def _draw_target(self,shader,center,radius,color,width):
		segments=40
		vertices=[]
		for index in range(segments + 1):
			angle=2.0 * pi * index / segments
			vertices.append((center.x + cos(angle) * radius,center.y + sin(angle) * radius,))
		gpu.state.line_width_set(width)
		shader.uniform_float("color",color)
		batch_for_shader(shader, "LINE_STRIP",{"pos": vertices}).draw(shader)
		cross=((center.x - radius * 0.45,center.y),(center.x + radius * 0.45,center.y),(center.x,center.y - radius * 0.45),(center.x,center.y + radius * 0.45),)
		batch_for_shader(shader,"LINES",
			{"pos": cross},).draw(shader)
	def _draw_overlay(self,context):
		if context.area is None or context.area.type != "VIEW_3D":
			return
		shader=gpu.shader.from_builtin("UNIFORM_COLOR")
		gpu.state.blend_set("ALPHA")
		for component_index,point_2d in self._projected_targets(context):
			hovered=component_index==self._hovered_index
			self._draw_target(shader,point_2d,self._target_radius + (3.0 if hovered else 0.0),(1.0,0.75,0.05,1.0) if hovered else (1.0,0.02,0.02,0.95),5.0 if hovered else 4.0,)
		gpu.state.line_width_set(1.0)
		gpu.state.blend_set("NONE")
	def _make_mesh_backup(self,obj):
		return {"object_name": obj.name_full, "mesh": obj.data.copy(),}
	def _discard_mesh_backup(self,backup):
		if not backup:
			return
		mesh=backup.get("mesh")
		if mesh is not None and mesh.users==0:
			bpy.data.meshes.remove(mesh)
	def _restore_mesh_backup(self,backup):
		if not backup:
			return False
		obj=bpy.data.objects.get(backup.get("object_name", ""))
		mesh=backup.get("mesh")
		if obj is None or mesh is None:
			return False
		old_mesh=obj.data
		obj.data=mesh
		if old_mesh is not None and old_mesh.users==0:
			bpy.data.meshes.remove(old_mesh)
		return True
	def _remove_component(self,obj,component):
		mesh=obj.data
		backup=self._make_mesh_backup(obj)
		bm=bmesh.new()
		try:
			bm.from_mesh(mesh)
			bm.verts.ensure_lookup_table()
			vertices_to_delete=[bm.verts[index]
				for index in component["vertices"] if 0 <=index < len(bm.verts)]
			if not vertices_to_delete:
				self._discard_mesh_backup(backup)
				return False
			bmesh.ops.delete(bm,geom=vertices_to_delete,context="VERTS",)
			bm.to_mesh(mesh)
			mesh.update(calc_edges=True)
		finally:
			bm.free()
		self._undo_stack.append(backup)
		return True
	def _undo_last_remove(self,context,obj):
		if not self._undo_stack:
			GR(self,"INFO", "Nothing to undo in Remove Decal Sections")
			return False
		backup=self._undo_stack.pop()
		if not self._restore_mesh_backup(backup):
			GR(self,"WARNING", "Could not restore the removed decal section")
			return False
		self._components=self._collect_components(obj)
		self._hovered_index=-1
		if context.area:
			context.area.tag_redraw()
		GR(self,"INFO", "Restored last removed decal section")
		return True
	def _finish(self,context):
		draw_handle=self._draw_handle
		self._draw_handle=None
		if draw_handle is not None:
			try:
				bpy.types.SpaceView3D.draw_handler_remove(draw_handle,"WINDOW",)
			except (ReferenceError,RuntimeError,ValueError):
				pass
		try:
			if context.area is not None:
				context.area.tag_redraw()
		except ReferenceError:
			pass
	def invoke(self,context,event):
		obj=active_generated_decal(context)
		self._components=self._collect_components(obj)
		if not self._components:
			GR(self,"WARNING", "The selected decal has no removable sections.")
			return {"CANCELLED"}
		self._mouse_region=(event.mouse_region_x,event.mouse_region_y,)
		self._hovered_index=-1
		self._undo_stack=[]
		self._draw_handle=bpy.types.SpaceView3D.draw_handler_add(self._draw_overlay,(context,), "WINDOW","POST_PIXEL",)
		context.window_manager.modal_handler_add(self)
		context.area.tag_redraw()
		GR(self,"INFO","Click a red target to remove a decal section; Enter or Right Click finishes; Esc exits",)
		return {"RUNNING_MODAL"}
	def modal(self,context,event):
		obj=active_generated_decal(context)
		if obj is None or context.area is None or context.area.type != "VIEW_3D":
			self._finish(context)
			return {"CANCELLED"}
		if event.type== "MOUSEMOVE":
			self._mouse_region=(event.mouse_region_x,event.mouse_region_y,)
			self._update_hover(context)
			context.area.tag_redraw()
			return {"RUNNING_MODAL"}
		if (event.type== "Z"
			and event.value== "PRESS"
			and (event.ctrl or event.oskey)):
			self._undo_last_remove(context,obj)
			return {"RUNNING_MODAL"}
		if event.type== "LEFTMOUSE" and event.value== "PRESS":
			self._mouse_region=(event.mouse_region_x,event.mouse_region_y,)
			self._update_hover(context)
			if 0 <=self._hovered_index < len(self._components):
				component=self._components[self._hovered_index]
				if self._remove_component(obj,component):
					self._components=self._collect_components(obj)
					self._hovered_index=-1
					context.area.tag_redraw()
					if not self._components:
						self._finish(context)
						GR(self,"INFO", "All decal sections were removed.")
						return {"FINISHED"}
				return {"RUNNING_MODAL"}
			return {"PASS_THROUGH"}
		if event.type in {"RET", "NUMPAD_ENTER", "RIGHTMOUSE"} and event.value== "PRESS":
			self._finish(context)
			return {"FINISHED"}
		if event.type== "ESC" and event.value== "PRESS":
			self._finish(context)
			return {"CANCELLED"}
		return {"PASS_THROUGH"}
class EDGEDECAL_OT_lock_current_decals(Operator):
	bl_idname= "object.edge_decal_lock_current";bl_label= g("Lock Current Decals");bl_description=("锁定从选定的源网格生成的全部当前贴花，以便下一代保持它们不变");bl_options={"REGISTER", "UNDO"}
	@classmethod
	def poll(cls,context):
		obj=context.active_object
		return (obj is not None
			and obj.type== "MESH"
			and not obj.get("edge_decal_generated")
			and any(iter_generated_decals(source_obj=obj)))
	def execute(self,context):
		source_obj=context.active_object
		locked_count=0
		for decal_obj in iter_generated_decals(source_obj=source_obj):
			if decal_obj.get("edge_decal_locked",False):
				continue
			decal_obj["edge_decal_locked"]=True
			locked_count +=1
		if locked_count==0:
			GR(self,"INFO", "All current decals are already locked")
			return {"FINISHED"}
		GR(self,"INFO",f"Locked {locked_count} decal object(s)")
		return {"FINISHED"}
def edge_decal_context_source(context):
	obj=getattr(context, "active_object",None)
	if obj is None:
		return None
	if obj.get("edge_decal_generated"):
		data=getattr(obj, "edge_decal_object_settings",None)
		source_obj=getattr(data, "source_object",None)
		if source_obj is not None:
			return source_obj
		return find_object_by_name_or_full(str(obj.get("edge_decal_source", "")))
	if obj.type== "MESH":
		return obj
	return None
def edge_decal_context_is_layer_object(context):
	obj=getattr(context, "active_object",None)
	return bool(obj is not None and obj.get("edge_decal_generated"))
EDGEDECAL_LAYER_UI_SYNCING=False
def decal_layer_workflow_label(layer_obj):
	data=getattr(layer_obj, "edge_decal_object_settings",None)
	has_generated_edges=bool(parsed_source_indices(data,layer_obj))
	has_interactive_edges=bool(parsed_interactive_stroke_edges(layer_obj))
	if has_generated_edges and has_interactive_edges:
		return "Mixed", "MODIFIER"
	if has_interactive_edges:
		return "Interactive", "GREASEPENCIL"
	if has_generated_edges:
		return "Generated", "MESH_DATA"
	return "Empty", "EMPTY_AXIS"
def decal_layer_is_interactive_only(layer_obj):
	label,_icon=decal_layer_workflow_label(layer_obj)
	return label== "Interactive"
class EDGEDECAL_PG_layer_item(PropertyGroup):
	layer_object: PointerProperty(name="Layer Object",type=bpy.types.Object,)
def _legacy_decal_layer_has_split_path_seams(layer_obj):
	mesh=getattr(layer_obj, "data",None)
	if mesh is None or len(mesh.vertices) < 2:
		return False
	coordinates=[vertex.co for vertex in mesh.vertices]
	minimum=Vector((min(coordinate.x for coordinate in coordinates),min(coordinate.y for coordinate in coordinates),min(coordinate.z for coordinate in coordinates),))
	maximum=Vector((max(coordinate.x for coordinate in coordinates),max(coordinate.y for coordinate in coordinates),max(coordinate.z for coordinate in coordinates),))
	tolerance=max(1.0e-7,(maximum - minimum).length * 1.0e-7)
	inverse_tolerance=1.0 / tolerance
	occupied=set()
	for coordinate in coordinates:
		key=tuple(int(round(float(component) * inverse_tolerance)) for component in coordinate)
		if key in occupied:
			return True
		occupied.add(key)
	return False
def sync_scene_settings_from_decal_layer(context,source_obj,layer_obj):
	if source_obj is None or layer_obj is None or context is None:
		return False
	data=getattr(layer_obj, "edge_decal_object_settings",None)
	settings=context.scene.edge_decal_settings
	initialize_decal_finish_settings_from_modifiers(layer_obj)
	global EDGEDECAL_SCENE_SETTINGS_COPYING
	EDGEDECAL_SCENE_SETTINGS_COPYING=True
	try:
		if data is not None and getattr(data, "initialized",False):
			if not data.is_property_set("use_edge_split"):
				data.use_edge_split=_legacy_decal_layer_has_split_path_seams(layer_obj)
				data.split_angle=float(getattr(settings, "split_angle",radians(45.0)))
			for property_name in SCENE_LIVE_EDIT_PROPERTIES:
				if hasattr(data,property_name) and hasattr(settings,property_name):
					try:
						setattr(settings,property_name,getattr(data,property_name),)
					except (TypeError,ValueError):
						pass
			if hasattr(data, "decal_material"):
				material=(getattr(data, "decal_template_material",None)
					or root_decal_template_material(data.decal_material))
				settings.decal_material=material
				settings.use_material=material is not None
				match_source_material=bool(getattr(data, "match_source_material",False)
					or (data.decal_material is not None
						and data.decal_material.get("edge_decal_source_matched")) 	)
				settings.match_source_material=match_source_material
				if match_source_material and not data.match_source_material:
					data.match_source_material=True
			enable_second_uv_for_material_matching(settings)
	finally:
		EDGEDECAL_SCENE_SETTINGS_COPYING=False
	EDGEDECAL_SCENE_LIVE_SYNC_CACHE[scene_live_sync_cache_key(source_obj,layer_obj)]=scene_live_edit_signature(settings)
	return True
def activate_decal_layer(context,source_obj,layer_obj,select_source=True,select_layer=False,):
	if source_obj is None or layer_obj is None:
		return False
	if (layer_obj.data is not None
		and len(layer_obj.data.vertices)==0
		and layer_obj.matrix_world !=Matrix.Identity(4)):
		layer_obj.matrix_world=Matrix.Identity(4)
		layer_obj.matrix_parent_inverse=source_obj.matrix_world.inverted_safe()
	set_active_decal_layer(source_obj,layer_obj)
	sync_scene_settings_from_decal_layer(context,source_obj,layer_obj)
	if select_layer:
		select_only_object(context,layer_obj)
	elif select_source:
		select_only_object(context,source_obj)
	return True
def layer_ui_props_available(source_obj):
	return (source_obj is not None
		and hasattr(source_obj, "edge_decal_layers_ui")
		and hasattr(source_obj, "edge_decal_layer_index"))
def repair_decal_layers_for_source(source_obj,context=None,activate=True):
	if (source_obj is None
		or source_obj.type != "MESH"
		or source_obj.get("edge_decal_generated")):
		return None
	layers=sorted_decal_layers_for_source(source_obj)
	valid_names={layer.name_full for layer in layers}
	active_name=str(source_obj.get("edge_decal_active_layer", ""))
	active_layer=stored_active_decal_layer_for_source(source_obj)
	if active_layer is None or active_layer.name_full not in valid_names:
		active_layer=layers[0] if layers else None
	if (active_name not in valid_names
		or (active_name and not object_name_exists(active_name))):
		set_active_decal_layer(source_obj,active_layer)
	elif not layers:
		set_active_decal_layer(source_obj,None)
	if layer_ui_props_available(source_obj):
		sync_source_layer_ui(source_obj,active_layer=active_layer)
	elif active_layer is not None:
		set_active_decal_layer(source_obj,active_layer)
	if activate and context is not None and active_layer is not None:
		activate_decal_layer(context,source_obj,active_layer)
	return active_layer
def source_mesh_for_removed_decal(decal_name,registry_source_name=""):
	source_obj=find_object_by_name_or_full(registry_source_name)
	if (source_obj is not None
		and source_obj.type== "MESH"
		and not source_obj.get("edge_decal_generated")):
		return source_obj
	for candidate in bpy.data.objects:
		if candidate.type != "MESH" or candidate.get("edge_decal_generated"):
			continue
		if str(candidate.get("edge_decal_active_layer", ""))==decal_name:
			return candidate
		if not layer_ui_props_available(candidate):
			continue
		for item in candidate.edge_decal_layers_ui:
			layer_obj=item.layer_object
			if layer_obj is None:
				continue
			try:
				if layer_obj.name_full==decal_name:
					return candidate
			except ReferenceError:
				return candidate
	return None
def schedule_source_layer_ui_sync(source_obj):
	if source_obj is None or regenerating_active():
		return
	source_name=source_obj.name_full
	def _sync_once():
		obj=find_object_by_name_or_full(source_name)
		if obj is not None and layer_ui_props_available(obj):
			sync_source_layer_ui(obj)
		for area in bpy.context.screen.areas:
			if area.type== "VIEW_3D":
				area.tag_redraw()
		return None
	bpy.app.timers.register(_sync_once,first_interval=0.0)
def sync_source_layer_ui(source_obj,active_layer=None):
	global EDGEDECAL_LAYER_UI_SYNCING
	if source_obj is None or source_obj.type != "MESH":
		return []
	if not layer_ui_props_available(source_obj):
		return sorted_decal_layers_for_source(source_obj)
	layers=sorted_decal_layers_for_source(source_obj)
	if active_layer is None:
		active_layer=stored_active_decal_layer_for_source(source_obj)
	ui=source_obj.edge_decal_layers_ui
	needs_rebuild=len(ui) !=len(layers)
	if not needs_rebuild:
		for item in ui:
			if not decal_layer_is_valid(item.layer_object,source_obj):
				needs_rebuild=True
				break
	if not needs_rebuild:
		for item,layer_obj in zip(ui,layers):
			if item.layer_object !=layer_obj:
				needs_rebuild=True
				break
	EDGEDECAL_LAYER_UI_SYNCING=True
	try:
		if needs_rebuild:
			ui.clear()
			for layer_obj in layers:
				item=ui.add()
				item.layer_object=layer_obj
		active_index=0
		if active_layer is not None:
			for index,item in enumerate(ui):
				if item.layer_object==active_layer:
					active_index=index
					break
		if ui:
			active_index=max(0,min(active_index,len(ui) - 1))
			if int(source_obj.edge_decal_layer_index) !=active_index:
				source_obj.edge_decal_layer_index=active_index
		elif int(source_obj.edge_decal_layer_index) !=0:
			source_obj.edge_decal_layer_index=0
	finally:
		EDGEDECAL_LAYER_UI_SYNCING=False
	return layers
def update_edge_decal_layer_index(self,context):
	global EDGEDECAL_LAYER_UI_SYNCING
	if EDGEDECAL_LAYER_UI_SYNCING or context is None:
		return
	if self.type != "MESH" or self.get("edge_decal_generated"):
		return
	if not layer_ui_props_available(self):
		return
	ui=self.edge_decal_layers_ui
	index=int(self.edge_decal_layer_index)
	if index < 0 or index >=len(ui):
		return
	layer_obj=ui[index].layer_object
	if not decal_layer_is_valid(layer_obj,self):
		repair_decal_layers_for_source(self,context)
		return
	activate_decal_layer(context,self,layer_obj,select_source=False,select_layer=True,)
class EDGEDECAL_UL_layers(UIList):
	bl_idname= "EDGEDECAL_UL_layers"
	def draw_item(self,context,layout,data,item,icon,active_data,active_property,index,):
		layer_obj=item.layer_object
		if layer_obj is None:
			GL(layout,"<missing layer>",icon="ERROR")
			return
		row=layout.row(align=True)
		is_active=index==getattr(active_data,active_property)
		vis=row.operator(EDGEDECAL_OT_layer_toggle_visibility.bl_idname,text="",icon="HIDE_ON" if layer_obj.hide_viewport else "HIDE_OFF",emboss=False,)
		vis.layer_name=layer_obj.name_full
		locked=bool(layer_obj.get("edge_decal_locked",False))
		lock=row.operator(EDGEDECAL_OT_layer_toggle_lock.bl_idname,text="",icon="LOCKED" if locked else "UNLOCKED",emboss=False,)
		lock.layer_name=layer_obj.name_full
		display_name=str(layer_obj.get( "edge_decal_layer_name",layer_obj.name,))
		edge_count=decal_layer_source_count(layer_obj)
		name_row=row.row(align=True)
		name_row.enabled=not locked
		GL(name_row,f"{display_name}  ({edge_count})",icon="RENDERLAYERS",)
		workflow_label,workflow_icon=decal_layer_workflow_label(layer_obj)
		GL(row,workflow_label,icon=workflow_icon)
		pin_summary=layer_uv_pin_summary_label(layer_obj,uv_pins_for_decal_layer_material(context.scene,layer_obj,),)
		if pin_summary:
			GL(row,pin_summary,icon="PIVOT_CURSOR")
class EDGEDECAL_OT_layer_toggle_uv_pin(Operator):
	bl_idname= "object.edge_decal_layer_toggle_uv_pin";bl_label= g("Toggle Layer UV Pin");bl_options={"REGISTER", "UNDO"}
	def draw(S,_):L=S.layout;[GP(L,S,n) for n in S.__annotations__]
	layer_name: StringProperty(default="")
	pin_index: IntProperty(default=-1)
	def execute(self,context):
		layer_obj=find_object_by_name_or_full(self.layer_name)
		if layer_obj is None:
			return {"CANCELLED"}
		data=getattr(layer_obj, "edge_decal_object_settings",None)
		if data is None:
			return {"CANCELLED"}
		pins=uv_pins_for_decal_layer_material(context.scene,layer_obj,)
		if not (0 <=self.pin_index < len(pins)):
			return {"CANCELLED"}
		indices=set(layer_assigned_uv_pin_indices(layer_obj))
		if self.pin_index in indices:
			indices.remove(self.pin_index)
		else:
			indices.add(self.pin_index)
		data.uv_pin_indices=format_uv_pin_indices(indices)
		for area in getattr(context.screen, "areas",()):
			area.tag_redraw()
		return {"FINISHED"}
class EDGEDECAL_OT_layer_select(Operator):
	bl_idname= "object.edge_decal_layer_select";bl_label= g("Select Decal Layer");bl_options={"INTERNAL"}
	def draw(S,_):L=S.layout;[GP(L,S,n) for n in S.__annotations__]
	layer_name: StringProperty(options={"HIDDEN"})
	def execute(self,context):
		source_obj=edge_decal_context_source(context)
		layer_obj=find_object_by_name_or_full(self.layer_name)
		if source_obj is None or layer_obj is None:
			return {"CANCELLED"}
		if not activate_decal_layer(context,source_obj,layer_obj,select_source=False,
			select_layer=True,):
			return {"CANCELLED"}
		sync_source_layer_ui(source_obj,active_layer=layer_obj)
		return {"FINISHED"}
def create_empty_decal_layer(context,source_obj,layer_index=None):
	if source_obj is None or source_obj.type != "MESH":
		return None
	if layer_index is None:
		layer_index=next_decal_index(source_obj)
	base_name=f"{source_obj.name}_DecalLayer_{layer_index:02d}"
	mesh=bpy.data.meshes.new(f"{base_name}_Mesh")
	layer_obj=bpy.data.objects.new(base_name,mesh)
	configure_decal_object(layer_obj,source_obj=source_obj,scene=context.scene,)
	layer_obj.matrix_world=Matrix.Identity(4)
	decal_world_matrix=layer_obj.matrix_world.copy()
	layer_obj.parent=source_obj
	layer_obj.matrix_parent_inverse=source_obj.matrix_world.inverted_safe()
	layer_obj.matrix_world=decal_world_matrix
	layer_obj["edge_decal_generated"]=True
	layer_obj["edge_decal_source"]=source_obj.name_full
	layer_obj["edge_decal_index"]=layer_index
	layer_obj["edge_decal_mode"]= "SHARP_EDGES"
	layer_obj["edge_decal_layer_name"]=f"Decal Layer {layer_index}"
	data=layer_obj.edge_decal_object_settings
	data.initialized=False
	data.live_update=False
	data.source_object=source_obj
	data.selection_mode= "SELECTED_EDGES"
	data.source_indices= ""
	data.uv_pin_indices= ""
	scene_settings=context.scene.edge_decal_settings
	global EDGEDECAL_SETTINGS_SYNCING
	previous_syncing=EDGEDECAL_SETTINGS_SYNCING
	EDGEDECAL_SETTINGS_SYNCING=True
	try:
		data.use_edge_split=True
		scene_settings.use_edge_split=True
		data.match_source_material=bool(getattr(scene_settings, "match_source_material",False))
		if scene_settings.decal_material is not None:
			data.decal_template_material=root_decal_template_material(scene_settings.decal_material)
	finally:
		EDGEDECAL_SETTINGS_SYNCING=previous_syncing
	register_fn=globals().get("register_decal_in_registry")
	if register_fn is not None:
		register_fn(layer_obj,source_obj)
	set_active_decal_layer(source_obj,layer_obj)
	return layer_obj
class EDGEDECAL_OT_layer_add(Operator):
	bl_idname= "object.edge_decal_layer_add";bl_label= g("Add Decal Layer");bl_description= "为此源网格创建新建空物体活动贴花层";bl_options={"REGISTER", "UNDO"}
	def execute(self,context):
		source_obj=edge_decal_context_source(context)
		if source_obj is None or source_obj.type != "MESH":
			GR(self,"ERROR", "Select a source mesh")
			return {"CANCELLED"}
		layer_obj=create_empty_decal_layer(context,source_obj)
		if layer_obj is None:
			return {"CANCELLED"}
		activate_decal_layer(context,source_obj,layer_obj,select_source=False,select_layer=False,)
		sync_source_layer_ui(source_obj,active_layer=layer_obj)
		return {"FINISHED"}
class EDGEDECAL_OT_layer_delete(Operator):
	bl_idname= "object.edge_decal_layer_delete";bl_label= g("Delete Decal Layer");bl_options={"REGISTER", "UNDO"}
	def draw(S,_):L=S.layout;[GP(L,S,n) for n in S.__annotations__]
	layer_name: StringProperty(options={"HIDDEN"})
	def execute(self,context):
		source_obj=edge_decal_context_source(context)
		layer_obj=find_object_by_name_or_full(self.layer_name)
		if source_obj is None or layer_obj is None:
			return {"CANCELLED"}
		mesh=layer_obj.data
		bpy.data.objects.remove(layer_obj,do_unlink=True)
		if mesh is not None and mesh.users==0:
			bpy.data.meshes.remove(mesh)
		remaining=sorted_decal_layers_for_source(source_obj)
		active_layer=remaining[0] if remaining else None
		set_active_decal_layer(source_obj,active_layer)
		sync_source_layer_ui(source_obj,active_layer=active_layer)
		if active_layer is not None:
			activate_decal_layer(context,source_obj,active_layer,select_source=False,select_layer=True,)
		elif not edge_decal_context_is_layer_object(context):
			select_only_object(context,source_obj)
		return {"FINISHED"}
class EDGEDECAL_OT_layer_delete_active(Operator):
	bl_idname= "object.edge_decal_layer_delete_active";bl_label= g("Delete Active Decal Layer");bl_description= "删除选定的贴花层";bl_options={"REGISTER", "UNDO"}
	def execute(self,context):
		source_obj=edge_decal_context_source(context)
		if source_obj is None:
			return {"CANCELLED"}
		sync_source_layer_ui(source_obj)
		ui=source_obj.edge_decal_layers_ui
		index=int(source_obj.edge_decal_layer_index)
		if index < 0 or index >=len(ui):
			return {"CANCELLED"}
		layer_obj=ui[index].layer_object
		if layer_obj is None:
			return {"CANCELLED"}
		bpy.ops.object.edge_decal_layer_delete("EXEC_DEFAULT",layer_name=layer_obj.name_full,)
		return {"FINISHED"}
class EDGEDECAL_OT_layer_move(Operator):
	bl_idname= "object.edge_decal_layer_move";bl_label= g("Move Decal Layer");bl_description= "更改贴花层的堆栈排序";bl_options={"REGISTER", "UNDO"}
	def draw(S,_):L=S.layout;[GP(L,S,n) for n in S.__annotations__]
	direction: EnumProperty(name="Direction",items=(("UP", "Up", "在堆栈中上移动层"),("DOWN", "Down", "在堆栈中向下移动层"),),options={"HIDDEN"},)
	def execute(self,context):
		source_obj=edge_decal_context_source(context)
		if source_obj is None:
			return {"CANCELLED"}
		layers=sync_source_layer_ui(source_obj)
		if len(layers) < 2:
			return {"CANCELLED"}
		index=int(source_obj.edge_decal_layer_index)
		if self.direction== "UP":
			target_index=index - 1
		else:
			target_index=index + 1
		if target_index < 0 or target_index >=len(layers):
			return {"CANCELLED"}
		layer_a=layers[index]
		layer_b=layers[target_index]
		order_a=int(layer_a.get("edge_decal_index",0))
		order_b=int(layer_b.get("edge_decal_index",0))
		layer_a["edge_decal_index"]=order_b
		layer_b["edge_decal_index"]=order_a
		sync_source_layer_ui(source_obj,active_layer=layer_a)
		source_obj.edge_decal_layer_index=target_index
		activate_decal_layer(context,source_obj,layer_a)
		return {"FINISHED"}
def _decal_layer_mask_is_above(source_obj,target_layer,mask_layer):
	layers=sorted_decal_layers_for_source(source_obj)
	try:
		return layers.index(mask_layer) < layers.index(target_layer)
	except ValueError:
		return False
def _decal_layer_mask_cutter_thickness(source_obj,target_layer,mask_layer):
	source_extent=max((abs(float(value)) for value in source_obj.dimensions),default=1.0,)
	target_data=getattr(target_layer, "edge_decal_object_settings",None)
	mask_data=getattr(mask_layer, "edge_decal_object_settings",None)
	target_offset=float(getattr(target_data, "surface_offset",0.0))
	mask_offset=float(getattr(mask_data, "surface_offset",0.0))
	surface_gap=abs(target_offset - mask_offset)
	numeric_margin=max(1.0e-5,source_extent * 1.0e-5)
	return max(numeric_margin * 2.0,surface_gap * 2.0 + numeric_margin)
def _remove_temporary_decal_mask_object(obj):
	if obj is None:
		return
	mesh=getattr(obj, "data",None)
	try:
		bpy.data.objects.remove(obj,do_unlink=True)
	except (ReferenceError,RuntimeError):
		return
	if mesh is not None and mesh.users==0:
		bpy.data.meshes.remove(mesh)
def _evaluated_decal_mask_volume(context,mask_layer,thickness):
	depsgraph=context.evaluated_depsgraph_get()
	bevel_visibility=[]
	for modifier in mask_layer.modifiers:
		if modifier.type != "BEVEL":
			continue
		bevel_visibility.append((modifier,bool(modifier.show_viewport)))
		modifier.show_viewport=False
	surface_mesh=None
	try:
		depsgraph.update()
		evaluated=mask_layer.evaluated_get(depsgraph)
		surface_mesh=bpy.data.meshes.new_from_object(evaluated,preserve_all_data_layers=True,depsgraph=depsgraph,)
	finally:
		for modifier,was_visible in bevel_visibility:
			try:
				modifier.show_viewport=was_visible
			except ReferenceError:
				pass
		depsgraph.update()
	if surface_mesh is None or not surface_mesh.polygons:
		if surface_mesh is not None and surface_mesh.users==0:
			bpy.data.meshes.remove(surface_mesh)
		return None
	surface_obj=bpy.data.objects.new("__EdgeDecalLayerMaskSurface",surface_mesh)
	context.scene.collection.objects.link(surface_obj)
	surface_obj.matrix_world=mask_layer.matrix_world.copy()
	try:
		solidify=surface_obj.modifiers.new("__EdgeDecalLayerMaskThickness","SOLIDIFY",)
		solidify.thickness=thickness
		solidify.offset=0.0
		solidify.use_rim=True
		solidify.use_even_offset=True
		if hasattr(solidify, "use_quality_normals"):
			solidify.use_quality_normals=True
		depsgraph.update()
		evaluated_volume=surface_obj.evaluated_get(depsgraph)
		volume_mesh=bpy.data.meshes.new_from_object(evaluated_volume,preserve_all_data_layers=False,depsgraph=depsgraph,)
		if volume_mesh is None or not volume_mesh.polygons:
			if volume_mesh is not None and volume_mesh.users==0:
				bpy.data.meshes.remove(volume_mesh)
			return None
		volume_obj=bpy.data.objects.new("__EdgeDecalLayerMaskVolume",volume_mesh,)
		context.scene.collection.objects.link(volume_obj)
		volume_obj.matrix_world=mask_layer.matrix_world.copy()
		return volume_obj
	finally:
		_remove_temporary_decal_mask_object(surface_obj)
def _extract_original_decal_surface(result_mesh,original_mesh,tolerance):
	if result_mesh is None or original_mesh is None:
		return False
	original_bvh=BVHTree.FromPolygons([vertex.co.copy() for vertex in original_mesh.vertices],[tuple(polygon.vertices) for polygon in original_mesh.polygons],all_triangles=False,)
	keep_indices=[]
	for polygon in result_mesh.polygons:
		on_original_surface=True
		for vertex_index in polygon.vertices:
			nearest=original_bvh.find_nearest(result_mesh.vertices[vertex_index].co)
			if nearest is None or nearest[3] > tolerance:
				on_original_surface=False
				break
		if on_original_surface:
			keep_indices.append(polygon.index)
	if not keep_indices:
		return False
	keep=set(keep_indices)
	bm=bmesh.new()
	try:
		bm.from_mesh(result_mesh)
		bm.faces.ensure_lookup_table()
		remove_faces=[face for face in bm.faces if face.index not in keep]
		if remove_faces:
			bmesh.ops.delete(bm,geom=remove_faces,context="FACES",)
		bm.to_mesh(result_mesh)
		result_mesh.update(calc_edges=True)
	finally:
		bm.free()
	return bool(result_mesh.polygons)
def _decal_mesh_polygon_components(mesh):
	vertex_faces={}
	for polygon in mesh.polygons:
		for vertex_index in polygon.vertices:
			vertex_faces.setdefault(vertex_index,set()).add(polygon.index)
	adjacency={polygon.index: set() for polygon in mesh.polygons}
	for polygon_indices in vertex_faces.values():
		for polygon_index in polygon_indices:
			adjacency[polygon_index].update(polygon_indices - {polygon_index})
	component_by_polygon={}
	remaining=set(adjacency)
	component_index=0
	while remaining:
		seed=remaining.pop()
		pending=[seed]
		component_by_polygon[seed]=component_index
		while pending:
			polygon_index=pending.pop()
			neighbors=adjacency[polygon_index] & remaining
			remaining.difference_update(neighbors)
			for neighbor in neighbors:
				component_by_polygon[neighbor]=component_index
			pending.extend(neighbors)
		component_index +=1
	return component_by_polygon,component_index
def _copy_decal_component_mesh(original_mesh,polygon_indices,name):
	component_mesh=original_mesh.copy()
	keep=set(polygon_indices)
	bm=bmesh.new()
	try:
		bm.from_mesh(component_mesh)
		bm.faces.ensure_lookup_table()
		remove_faces=[face for face in bm.faces if face.index not in keep]
		if remove_faces:
			bmesh.ops.delete(bm,geom=remove_faces,context="FACES",)
		bm.to_mesh(component_mesh)
		component_mesh.name=name
		component_mesh.update(calc_edges=True)
	finally:
		bm.free()
	return component_mesh
def _combine_decal_component_meshes(component_meshes,original_mesh):
	combined_vertices=[]
	combined_faces=[]
	combined_material_indices=[]
	combined_smooth_flags=[]
	uv_layer_count=max((len(mesh.uv_layers) for mesh in component_meshes),default=0,)
	uv_layer_names=[]
	combined_uvs=[[] for _index in range(uv_layer_count)]
	for layer_index in range(uv_layer_count):
		uv_layer_names.append(next((mesh.uv_layers[layer_index].name
				for mesh in component_meshes
				if layer_index < len(mesh.uv_layers)), "UVMap" if layer_index==0 else f"UVMap.{layer_index:03d}",))
	for component_mesh in component_meshes:
		vertex_offset=len(combined_vertices)
		combined_vertices.extend(tuple(vertex.co) for vertex in component_mesh.vertices)
		for polygon in component_mesh.polygons:
			combined_faces.append(tuple(vertex_offset + vertex_index for vertex_index in polygon.vertices))
			combined_material_indices.append(int(polygon.material_index))
			combined_smooth_flags.append(bool(polygon.use_smooth))
			for layer_index in range(uv_layer_count):
				uv_layer=(component_mesh.uv_layers[layer_index]
					if layer_index < len(component_mesh.uv_layers) else None)
				combined_uvs[layer_index].append([(uv_layer.data[loop_index].uv.copy()
						if uv_layer is not None
						else Vector((0.0,0.0))) for loop_index in polygon.loop_indices])
	combined_mesh=bpy.data.meshes.new(f"{original_mesh.name}_LayerMaskCombined")
	combined_mesh.from_pydata(combined_vertices,[],combined_faces)
	combined_mesh.update(calc_edges=True)
	for material in original_mesh.materials:
		combined_mesh.materials.append(material)
	for polygon,material_index,use_smooth in zip(combined_mesh.polygons,combined_material_indices,
		combined_smooth_flags,):
		polygon.material_index=material_index
		polygon.use_smooth=use_smooth
	for layer_index,layer_name in enumerate(uv_layer_names):
		uv_layer=combined_mesh.uv_layers.new(name=layer_name)
		for polygon,polygon_uvs in zip(combined_mesh.polygons,combined_uvs[layer_index],):
			for loop_index,uv in zip(polygon.loop_indices,polygon_uvs):
				uv_layer.data[loop_index].uv=uv
	if combined_mesh.uv_layers:
		combined_mesh.uv_layers.active=combined_mesh.uv_layers[0]
		if hasattr(combined_mesh.uv_layers, "active_render"):
			combined_mesh.uv_layers.active_render=combined_mesh.uv_layers[0]
	return combined_mesh
def _decal_component_vertex_group_weights(component_meshes):
	weights_by_group={}
	vertex_offset=0
	for component_mesh in component_meshes:
		for vertex in component_mesh.vertices:
			for assignment in vertex.groups:
				weights_by_group.setdefault(assignment.group,[]).append((vertex_offset + vertex.index,float(assignment.weight),))
		vertex_offset +=len(component_mesh.vertices)
	return weights_by_group
def _restore_decal_vertex_group_weights(target_layer,group_names,weights_by_group,):
	for group in list(target_layer.vertex_groups):
		target_layer.vertex_groups.remove(group)
	for group_name in group_names:
		target_layer.vertex_groups.new(name=group_name)
	groups_by_index={group.index: group for group in target_layer.vertex_groups}
	for group_index,assignments in weights_by_group.items():
		group=groups_by_index.get(group_index)
		if group is None:
			continue
		indices_by_weight={}
		for vertex_index,weight in assignments:
			indices_by_weight.setdefault(round(weight,6),[]).append(vertex_index)
		for weight,vertex_indices in indices_by_weight.items():
			group.add(vertex_indices,weight, "REPLACE")
def _boolean_mask_decal_component(context,target_layer,component_mesh,cutter_obj,thickness,):
	target_obj=bpy.data.objects.new("__EdgeDecalLayerMaskTarget",component_mesh,)
	context.scene.collection.objects.link(target_obj)
	target_obj.matrix_world=target_layer.matrix_world.copy()
	for _group_index,group_name in sorted(((group.index,group.name)
			for group in target_layer.vertex_groups),
		key=lambda item: item[0],):
		target_obj.vertex_groups.new(name=group_name)
	result_mesh=None
	try:
		target_shell=target_obj.modifiers.new("__EdgeDecalLayerMaskTargetShell","SOLIDIFY",)
		target_shell.thickness=thickness
		target_shell.offset=-1.0
		target_shell.use_rim=True
		target_shell.use_even_offset=True
		if hasattr(target_shell, "use_quality_normals"):
			target_shell.use_quality_normals=True
		boolean=target_obj.modifiers.new("__EdgeDecalLayerMaskDifference","BOOLEAN",)
		boolean.operation= "DIFFERENCE"
		boolean.solver= "EXACT"
		boolean.object=cutter_obj
		if hasattr(boolean, "use_hole_tolerant"):
			boolean.use_hole_tolerant=True
		if hasattr(boolean, "double_threshold"):
			boolean.double_threshold=max(1.0e-8,thickness * 1.0e-4)
		depsgraph=context.evaluated_depsgraph_get()
		depsgraph.update()
		evaluated_target=target_obj.evaluated_get(depsgraph)
		result_mesh=bpy.data.meshes.new_from_object(evaluated_target,preserve_all_data_layers=True,depsgraph=depsgraph,)
		if result_mesh is None:
			return None, "The layer mask Boolean did not produce a mesh"
		surface_tolerance=max(1.0e-7,thickness * 0.05)
		if result_mesh.polygons and not _extract_original_decal_surface(result_mesh,component_mesh,
			surface_tolerance,):
			return None, "The layer mask could not recover a split decal island"
		completed_mesh=result_mesh
		result_mesh=None
		return completed_mesh, ""
	finally:
		target_obj.data=None
		_remove_temporary_decal_mask_object(target_obj)
		if result_mesh is not None and result_mesh.users==0:
			bpy.data.meshes.remove(result_mesh)
def apply_decal_layer_mask(context,source_obj,target_layer,mask_layer,):
	if source_obj is None or target_layer is None or mask_layer is None:
		return False, "Choose a selected layer and a mask layer"
	if not decal_layer_is_valid(target_layer,source_obj):
		return False, "The selected decal layer is no longer valid"
	if not decal_layer_is_valid(mask_layer,source_obj):
		return False, "The chosen mask layer is no longer valid"
	if target_layer.get("edge_decal_locked",False):
		return False, "Unlock the selected decal layer before masking it"
	if not _decal_layer_mask_is_above(source_obj,target_layer,mask_layer):
		return False, "The mask layer must be above the selected layer"
	if target_layer.data is None or not target_layer.data.polygons:
		return False, "The selected decal layer has no geometry"
	if mask_layer.data is None or not mask_layer.data.polygons:
		return False, "The chosen mask layer has no geometry"
	original_mesh=target_layer.data
	original_area=sum(polygon.area for polygon in original_mesh.polygons)
	vertex_group_names=[group.name for group in sorted(target_layer.vertex_groups,key=lambda group: group.index,)]
	component_by_polygon,component_count=_decal_mesh_polygon_components(original_mesh)
	polygons_by_component={component_index: [] for component_index in range(component_count)}
	for polygon_index,component_index in component_by_polygon.items():
		polygons_by_component[component_index].append(polygon_index)
	cutter_obj=None
	component_meshes=[]
	component_results=[]
	final_result_mesh=None
	vertex_group_weights={}
	try:
		thickness=_decal_layer_mask_cutter_thickness(source_obj,target_layer,mask_layer,)
		cutter_obj=_evaluated_decal_mask_volume(context,mask_layer,thickness * 4.0,)
		if cutter_obj is None:
			return False, "The chosen mask layer could not form a cutter"
		for component_index in range(component_count):
			component_mesh=_copy_decal_component_mesh(original_mesh,polygons_by_component[component_index],f"{original_mesh.name}_MaskIsland_{component_index:04d}",)
			component_meshes.append(component_mesh)
			result_mesh,error=_boolean_mask_decal_component(context,target_layer,component_mesh,cutter_obj,thickness,)
			if result_mesh is None:
				return False,error
			component_results.append(result_mesh)
		vertex_group_weights=_decal_component_vertex_group_weights(component_results)
		if len(component_results)==1:
			final_result_mesh=component_results.pop()
		else:
			final_result_mesh=_combine_decal_component_meshes(component_results,original_mesh,)
		result_area=sum(polygon.area for polygon in final_result_mesh.polygons)
		area_epsilon=max(1.0e-10,original_area * 1.0e-8)
		if original_area - result_area <=area_epsilon:
			return True,f"{mask_layer.name} does not overlap the selected layer"
		old_name=original_mesh.name
		target_layer.data=final_result_mesh
		final_result_mesh=None
		if original_mesh.users==0:
			bpy.data.meshes.remove(original_mesh)
		target_layer.data.name=old_name
		_restore_decal_vertex_group_weights(target_layer,vertex_group_names,vertex_group_weights,)
		ensure_decal_mesh_uv_layers(target_layer.data)
		target_layer.data.update(calc_edges=True)
		target_layer.update_tag(refresh={"DATA"})
		return True,f"Regenerated and masked with {mask_layer.name}"
	except (AttributeError,ReferenceError,RuntimeError,TypeError,
		ValueError,) as error:
		return False,f"Layer masking failed: {error}"
	finally:
		_remove_temporary_decal_mask_object(cutter_obj)
		for temporary_mesh in (component_meshes
			+ component_results
			+ ([final_result_mesh] if final_result_mesh is not None else [])):
			if temporary_mesh is None:
				continue
			try:
				if temporary_mesh.users==0:
					bpy.data.meshes.remove(temporary_mesh)
			except ReferenceError:
				pass
class EDGEDECAL_OT_layer_apply_mask(Operator):
	bl_idname= "object.edge_decal_layer_apply_mask";bl_label= g("Regenerate with Layer Mask");bl_description=("重新生成仅选定的层，然后移除其足迹\n 选定的上遮罩层");bl_options={"REGISTER", "UNDO"}
	@classmethod
	def poll(cls,context):
		return context.mode== "OBJECT" and edge_decal_context_source(context) is not None
	def execute(self,context):
		source_obj=edge_decal_context_source(context)
		target_layer=active_decal_layer_for_source(source_obj,context=context)
		data=getattr(target_layer, "edge_decal_object_settings",None)
		mask_layer=getattr(data, "layer_mask",None) if data is not None else None
		if target_layer is None or mask_layer is None:
			GR(self,"WARNING", "Choose a mask layer first")
			return {"CANCELLED"}
		if target_layer.get("edge_decal_locked",False):
			GR(self,"WARNING", "Unlock the selected decal layer first")
			return {"CANCELLED"}
		if not _decal_layer_mask_is_above(source_obj,target_layer,mask_layer):
			GR(self,"WARNING", "The mask layer must be above the selected layer")
			return {"CANCELLED"}
		if decal_has_regeneratable_source_data(target_layer):
			result=bpy.ops.object.edge_decal_regenerate("EXEC_DEFAULT",preview=False,)
			if "FINISHED" not in result:
				return {"CANCELLED"}
			return {"FINISHED"}
		success,message=apply_decal_layer_mask(context,source_obj,target_layer,mask_layer,)
		GR(self,"INFO" if success else "WARNING",message)
		return {"FINISHED"} if success else {"CANCELLED"}
class EDGEDECAL_OT_layer_clear_mask(Operator):
	bl_idname= "object.edge_decal_layer_clear_mask";bl_label= g("Clear Layer Mask");bl_description= "移除遮罩分配，重新生成整个选定的层";bl_options={"REGISTER", "UNDO"}
	@classmethod
	def poll(cls,context):
		source_obj=edge_decal_context_source(context)
		target_layer=(active_decal_layer_for_source(source_obj,context=context) if source_obj is not None else None)
		data=getattr(target_layer, "edge_decal_object_settings",None)
		return (context.mode== "OBJECT"
			and data is not None
			and getattr(data, "layer_mask",None) is not None)
	def execute(self,context):
		source_obj=edge_decal_context_source(context)
		target_layer=active_decal_layer_for_source(source_obj,context=context)
		data=getattr(target_layer, "edge_decal_object_settings",None)
		if data is None or data.layer_mask is None:
			return {"CANCELLED"}
		if target_layer.get("edge_decal_locked",False):
			GR(self,"WARNING", "Unlock the selected decal layer first")
			return {"CANCELLED"}
		if not decal_has_regeneratable_source_data(target_layer):
			GR(self,"WARNING","This layer has no stored source data to restore from",)
			return {"CANCELLED"}
		previous_mask=data.layer_mask
		data.layer_mask=None
		result=bpy.ops.object.edge_decal_regenerate("EXEC_DEFAULT",preview=False,)
		if "FINISHED" not in result:
			data.layer_mask=previous_mask
			return {"CANCELLED"}
		GR(self,"INFO", "Cleared the layer mask and restored the full layer")
		return {"FINISHED"}
class EDGEDECAL_OT_layer_toggle_lock(Operator):
	bl_idname= "object.edge_decal_layer_toggle_lock";bl_label= g("Toggle Layer Lock");bl_options={"INTERNAL"}
	def draw(S,_):L=S.layout;[GP(L,S,n) for n in S.__annotations__]
	layer_name: StringProperty(options={"HIDDEN"})
	def execute(self,context):
		layer_obj=find_object_by_name_or_full(self.layer_name)
		if layer_obj is None:
			return {"CANCELLED"}
		layer_obj["edge_decal_locked"]=not bool(layer_obj.get("edge_decal_locked",False))
		return {"FINISHED"}
class EDGEDECAL_OT_layer_toggle_visibility(Operator):
	bl_idname= "object.edge_decal_layer_toggle_visibility";bl_label= g("Toggle Layer Visibility");bl_options={"INTERNAL"}
	def draw(S,_):L=S.layout;[GP(L,S,n) for n in S.__annotations__]
	layer_name: StringProperty(options={"HIDDEN"})
	def execute(self,context):
		layer_obj=find_object_by_name_or_full(self.layer_name)
		if layer_obj is None:
			return {"CANCELLED"}
		data=getattr(layer_obj, "edge_decal_object_settings",None)
		source_obj=getattr(data, "source_object",None) if data else None
		if source_obj is None:
			source_obj=find_object_by_name_or_full(str(layer_obj.get("edge_decal_source", "")))
		layer_obj.hide_viewport=not layer_obj.hide_viewport
		layer_obj.hide_render=layer_obj.hide_viewport
		if layer_obj.hide_viewport and source_obj is not None:
			select_only_object(context,source_obj)
		return {"FINISHED"}
def _draw_layer_uv_pin_toggles(box,context,layer_obj):
	pins=uv_pins_for_decal_layer_material(context.scene,layer_obj,)
	pin_box=box.box()
	header=pin_box.row(align=True)
	GL(header,"UV Pins",icon="PIVOT_CURSOR")
	if not pins:
		GL(pin_box,"No UV pins defined yet",icon="INFO")
		GL(pin_box,"Add pins in the UV Editor panel")
		return
	assigned=layer_assigned_uv_pin_indices(layer_obj)
	if assigned:
		GL(header,f"{len(assigned)} selected",icon="CHECKMARK",)
	else:
		GL(header,"Auto (all pins)",icon="LOOP_BACK")
	for index,pin in enumerate(pins):
		row=pin_box.row(align=True)
		enabled=layer_uv_pin_is_enabled(layer_obj,index)
		toggle=row.operator(EDGEDECAL_OT_layer_toggle_uv_pin.bl_idname,text="",icon="CHECKBOX_HLT" if enabled else "CHECKBOX_DEHLT",emboss=False,)
		toggle.layer_name=layer_obj.name_full
		toggle.pin_index=index
		GL(row,(f"{uv_pin_display_name(pin,index)}   " f"U {pin.u:.3f}   V {pin.v:.3f}   W {pin.width:.3f}"))
def _draw_decal_layer_details(box,context,active_layer):
	if active_layer is None:
		return
	settings=context.scene.edge_decal_settings
	if not draw_edge_decal_foldout(box,settings,"show_layer_details","Active UV Pins",
		icon="RENDERLAYERS",prominent=True,):
		return
	details=box.column(align=True)
	GP(details,active_layer,'["edge_decal_layer_name"]',text="Layer Name",)
	GP(details,active_layer.edge_decal_object_settings,"decal_template_material",text="Material",)
	if decal_layer_is_interactive_only(active_layer):
		GL(details,"Interactive-only layer: use Interactive Mode or add a new layer.",icon="INFO",)
	_draw_layer_uv_pin_toggles(details,context,active_layer)
def _draw_decal_layer_mask_controls(box,active_layer):
	mask_box=box.box()
	header=mask_box.row(align=True)
	GL(header,"Mask by Layer (Experimental)",icon="MOD_MASK")
	if active_layer is None:
		GL(mask_box,"Select the layer to regenerate",icon="INFO")
		return
	data=active_layer.edge_decal_object_settings
	GP(mask_box,data, "layer_mask",text="Mask Layer")
	actions=mask_box.row(align=True)
	actions.scale_y=1.2
	apply_row=actions.row(align=True)
	apply_row.enabled=(data.layer_mask is not None
		and not active_layer.get("edge_decal_locked",False))
	GO(apply_row,EDGEDECAL_OT_layer_apply_mask.bl_idname,text="Regenerate with Mask",icon="MOD_BOOLEAN",)
	if data.layer_mask is not None:
		actions.operator(EDGEDECAL_OT_layer_clear_mask.bl_idname,text="",icon="LOOP_BACK",)
def draw_masking_category(layout,context,settings,active_layer):
	card=layout.box()
	if not draw_edge_decal_foldout(card,settings,"show_masking_category","Masking",
		icon="MOD_MASK",):
		return
	body=card.column(align=True)
	_draw_decal_layer_mask_controls(body,active_layer)
	texture_box=body.box()
	texture_header=texture_box.row(align=True)
	GL(texture_header,"Layer Texture Mask",icon="IMAGE_DATA")
	if active_layer is None:
		GL(texture_box,"Select a decal layer",icon="INFO")
	else:
		mask_data=active_layer.edge_decal_object_settings
		mask_image=getattr(mask_data, "texture_mask",None)
		if mask_image is None:
			GL(texture_box,"Black blocks; white generates",icon="INFO")
			add_mask=texture_box.column()
			add_mask.scale_y=1.25
			GO(add_mask,EDGEDECAL_OT_texture_mask_add.bl_idname,text="Add Black Mask",icon="ADD",)
		else:
			texture_header.prop(mask_data,"use_texture_mask",text="",icon=("CHECKBOX_HLT" if mask_data.use_texture_mask else "CHECKBOX_DEHLT"),)
			texture_box.template_ID(mask_data,"texture_mask",open="image.open",)
			controls=texture_box.column(align=True)
			controls.enabled=mask_data.use_texture_mask
			GP(controls,mask_data, "texture_mask_threshold",slider=True)
			paint=controls.row(align=True)
			paint.scale_y=1.25
			painting_mask=texture_mask_paint_is_active(context,active_layer,)
			GO(paint,EDGEDECAL_OT_texture_mask_paint.bl_idname,text="Exit Paint Mask" if painting_mask else "Paint Mask",icon="OBJECT_DATA" if painting_mask else "BRUSH_DATA",depress=painting_mask,)
			GO(paint,EDGEDECAL_OT_texture_mask_reset.bl_idname,text="Reset Black",icon="LOOP_BACK",)
			GO(texture_box,EDGEDECAL_OT_texture_mask_remove.bl_idname,text="Remove Mask",icon="UNLINKED",)
	crevice_box=body.box()
	GL(crevice_box,"Crevices Masking",icon="MOD_MASK")
	GP(crevice_box,settings, "crevice_removal",text="Amount",slider=True)
	crevice=crevice_box.column(align=True)
	crevice.enabled=settings.crevice_removal > 0.0
	GP(crevice,settings, "crevice_detection_mode",text="Detection")
	ao=crevice.column(align=True)
	ao.enabled=settings.crevice_detection_mode== "AO"
	GP(ao,settings, "crevice_ao_distance")
	GP(ao,settings, "crevice_ao_samples")
def _draw_decal_layers_legacy(box,context,layers,active_layer):
	if not layers:
		empty=box.column(align=True)
		GL(empty,"No decal layers",icon="INFO")
		GO(empty,EDGEDECAL_OT_layer_add.bl_idname,text="Create First Layer",icon="ADD",)
		return
	for layer_obj in layers:
		is_active=layer_obj==active_layer
		row_box=box.box() if is_active else box
		row=row_box.row(align=True)
		vis=row.operator(EDGEDECAL_OT_layer_toggle_visibility.bl_idname,text="",icon="HIDE_ON" if layer_obj.hide_viewport else "HIDE_OFF",emboss=False,)
		vis.layer_name=layer_obj.name_full
		lock=row.operator(EDGEDECAL_OT_layer_toggle_lock.bl_idname,text="",icon=("LOCKED"
				if layer_obj.get("edge_decal_locked",False) else "UNLOCKED"),emboss=False,)
		lock.layer_name=layer_obj.name_full
		select=GO(row,EDGEDECAL_OT_layer_select.bl_idname,text=str(layer_obj.get( "edge_decal_layer_name",layer_obj.name,)),icon="RADIOBUT_ON" if is_active else "RADIOBUT_OFF",depress=is_active,)
		select.layer_name=layer_obj.name_full
		data=getattr(layer_obj, "edge_decal_object_settings",None)
		count=decal_layer_source_count(layer_obj)
		GL(row,str(count))
		workflow_label,workflow_icon=decal_layer_workflow_label(layer_obj)
		GL(row,workflow_label,icon=workflow_icon)
		delete=row.operator(EDGEDECAL_OT_layer_delete.bl_idname,text="",icon="X",emboss=False,)
		delete.layer_name=layer_obj.name_full
	_draw_decal_layer_details(box,context,active_layer)
def draw_decal_layers(layout,context,source_obj,layers=None,active_layer=None):
	box=layout.box()
	header=box.row(align=True)
	GL(header,"Decal Layers",icon="RENDERLAYERS")
	header.operator(EDGEDECAL_OT_layer_add.bl_idname,text="",icon="ADD",)
	if layers is None:
		layers=sorted_decal_layers_for_source(source_obj)
	if active_layer is None:
		active_layer=active_decal_layer_for_source(source_obj,context=context)
	if not layer_ui_props_available(source_obj):
		_draw_decal_layers_legacy(box,context,layers,active_layer)
		return
	ui=source_obj.edge_decal_layers_ui
	ui_is_current=(len(ui)==len(layers)
		and all(item.layer_object==layer_obj
			for item,layer_obj in zip(ui,layers)))
	if not ui_is_current:
		schedule_source_layer_ui_sync(source_obj)
		_draw_decal_layers_legacy(box,context,layers,active_layer)
		return
	if not ui:
		if layers:
			schedule_source_layer_ui_sync(source_obj)
			_draw_decal_layers_legacy(box,context,layers,active_layer)
			return
		empty=box.column(align=True)
		GL(empty,"No decal layers",icon="INFO")
		GO(empty,EDGEDECAL_OT_layer_add.bl_idname,text="Create First Layer",icon="ADD",)
		return
	list_row=box.row()
	list_col=list_row.column()
	list_col.template_list(EDGEDECAL_UL_layers.bl_idname,"edgedecal_decal_layers",source_obj,"edge_decal_layers_ui",source_obj,"edge_decal_layer_index",rows=min(8,max(3,len(ui))),)
	controls=list_row.column(align=True)
	move_up=controls.operator(EDGEDECAL_OT_layer_move.bl_idname,text="",icon="TRIA_UP",)
	move_up.direction= "UP"
	move_down=controls.operator(EDGEDECAL_OT_layer_move.bl_idname,text="",icon="TRIA_DOWN",)
	move_down.direction= "DOWN"
	controls.separator()
	controls.operator(EDGEDECAL_OT_layer_add.bl_idname,text="",icon="ADD",)
	controls.operator(EDGEDECAL_OT_layer_delete_active.bl_idname,text="",icon="REMOVE",)
	_draw_decal_layer_details(box,context,active_layer)
class EDGEDECAL_PT_panel(Panel):
	bl_idname="EDGEDECAL_PT_panel";bl_label=BT;bl_space_type= "VIEW_3D";bl_region_type="UI";bl_category=TB
	def draw_header_preset(S,_):L=S.layout;DHP(S,_,L)
	def draw_header(S,_):DIC(S,_)
	def draw(self,context):
		layout=self.layout;DH(self,context,layout)
		settings=context.scene.edge_decal_settings
		active_obj=context.active_object
		source_obj=edge_decal_context_source(context)
		header=layout.box()
		title=header.row(align=True)
		title.scale_y=1.15
		GL(title,"Edge Decal Generator",icon="MOD_BEVEL")
		draw_edge_decal_presets(layout,context)
		if source_obj is None:
			GL(header,"Select a mesh to begin",icon="INFO")
			return
		if source_mesh_needs_layer_repair(source_obj):
			schedule_decal_layer_repair(source_obj)
		layers=sorted_decal_layers_for_source(source_obj)
		active_layer=active_decal_layer_for_source(source_obj,context=context)
		if (active_obj is not None
			and active_obj.get("edge_decal_generated")
			and active_obj in layers
			and active_layer !=active_obj):
			set_active_decal_layer(source_obj,active_obj)
			sync_scene_settings_from_decal_layer(context,source_obj,active_obj)
			active_layer=active_obj
		status=header.row(align=True)
		GL(status,f"Source: {source_obj.name}",icon="OBJECT_DATA")
		if active_layer is not None:
			GL(status,str(active_layer.get("edge_decal_layer_name",active_layer.name,) ),icon="RENDERLAYERS",)
		if not layers:
			starter=layout.box()
			GL(starter,"Create a decal layer before generating",icon="INFO",)
			add_row=starter.row(align=True)
			add_row.scale_y=1.5
			GO(add_row,EDGEDECAL_OT_layer_add.bl_idname,text="Add Layer",icon="ADD",)
			return
		draw_decal_layers(layout,context,source_obj,layers=layers,active_layer=active_layer,)
		actions=layout.box()
		row=actions.row(align=True)
		row.scale_y=1.35
		GO(row,EDGEDECAL_OT_generate_contextual.bl_idname,text="Generate",icon="PLAY",)
		GO(row,EDGEDECAL_OT_interactive_generate.bl_idname,text="Interactive",icon="RESTRICT_SELECT_OFF",depress=EDGEDECAL_INTERACTIVE_RUNNING,)
		if context.mode== "OBJECT":
			intersection_action=actions.row(align=True)
			intersection_action.scale_y=1.15
			GO(intersection_action,EDGEDECAL_OT_generate_intersections.bl_idname,text="Generate Intersections",icon="MOD_BOOLEAN",)
			GO(intersection_action,EDGEDECAL_OT_generate_boolean.bl_idname,text="Generate From Booleans",icon="SELECT_INTERSECT",)
		if (active_layer is not None
			and active_layer.data is not None
			and active_layer.data.polygons):
			row=actions.row(align=True)
			update=GO(row,EDGEDECAL_OT_regenerate.bl_idname,text="Update Layer",icon="FILE_REFRESH",)
			update.preview=False
			apply_uvs=row.row(align=True)
			apply_uvs.enabled=not active_layer.get("edge_decal_locked",False,)
			GO(apply_uvs,EDGEDECAL_OT_apply_uvs.bl_idname,text="Apply UVs",icon="UV",)
		quick=layout.box()
		quick_header=quick.row(align=True)
		GL(quick_header,"Quick Controls",icon="PREFERENCES")
		if active_layer is not None:
			GP(quick_header,active_layer.edge_decal_object_settings,"live_update",text="Live Update",toggle=True,)
		body=quick.column(align=True)
		width=body.row(align=True)
		width.scale_y=1.15
		width.enabled=not settings.randomize_face_width
		GP(width,settings, "face_width")
		GP(body,settings,"randomize_face_width",text="Random Width",toggle=True,icon="RNDCURVE",)
		random_width_bounds=body.column(align=True)
		random_width_bounds.enabled=settings.randomize_face_width
		GP(random_width_bounds,settings, "minimum_face_width")
		GP(random_width_bounds,settings, "maximum_face_width")
		GP(body,settings, "surface_offset")
		GP(body,settings, "decal_amount",slider=True)
		GP(body,settings, "seed")
		if context.mode== "OBJECT":
			auto_angle=body.row(align=True)
			auto_angle.scale_y=1.1
			GP(auto_angle,settings, "auto_edge_angle")
			GP(body,settings, "auto_follow_edge_loops")
		GP(body,settings, "use_edge_split")
		quick_split_angle=body.row(align=True)
		quick_split_angle.enabled=settings.use_edge_split
		GP(quick_split_angle,settings, "split_angle")
		performance=body.row(align=True)
		performance.scale_y=1.1
		GP(performance,settings,"fast_geometry_only",text="Fast Geometry",toggle=True,icon="MOD_SIMPLIFY",)
		draw_shape_settings(layout,settings)
		draw_masking_category(layout,context,settings,active_layer,)
		material=layout.box()
		if draw_edge_decal_foldout(material,settings,"show_material_category","Material",
			icon="MATERIAL",):
			material_body=material.column(align=True)
			GP(material_body,settings,"use_material",text="Assign Material",toggle=True,)
			if settings.use_material:
				material_body.prop(settings, "decal_material",text="")
				pending_fn=globals().get("edge_decal_pending_preset_material_name")
				pending_name=(pending_fn(context.scene,settings) if pending_fn is not None else "")
				if pending_name:
					GL(material_body,f"Loads on first generation: {pending_name}",icon="INFO",)
				GP(material_body,settings,"match_source_material",text="Match Material",toggle=True,)
				if settings.match_source_material:
					projection=material_body.row(align=True)
					projection.enabled=False
					GP(projection,settings,"generate_second_uv",text="Material UV Projection",toggle=True,)
					update_material=material_body.row(align=True)
					update_material.enabled=active_layer is not None
					GO(update_material,EDGEDECAL_OT_update_material.bl_idname,text="Update Material",icon="FILE_REFRESH",)
					if active_layer is not None:
						source_material=getattr(active_layer.edge_decal_object_settings,"source_material",None,)
						if source_material is not None:
							GL(material_body,f"Source: {source_material.name}",icon="LINKED",)
		uv_card=layout.box()
		if draw_edge_decal_foldout(uv_card,settings,"show_uv_category","UV Placement",
			icon="UV",):
			uv_body=uv_card.column(align=True)
			auto_pins=uv_body.row(align=True)
			auto_pins.enabled=not settings.fast_geometry_only
			GP(auto_pins,settings, "auto_use_uv_pins",text="Auto Pins")
			uv_actions=uv_body.row(align=True)
			GO(uv_actions,EDGEDECAL_OT_uv_pin_toggle_edit_mode.bl_idname,text="Edit UV Pins",icon="UV_SYNC_SELECT",)
			GP(uv_actions,settings, "uv_scale",text="Scale",slider=True)
			draw_uv_settings(uv_card,settings)
		draw_finish_settings(layout,settings)
		draw_normals_settings(layout,settings)
		draw_edge_decal_unreal_export(layout,context,source_obj,layers,)
		help_box=layout.box()
		if draw_edge_decal_foldout(help_box,settings,"show_interactive_help","Interactive Shortcuts",
			icon="QUESTION",):
			GL(help_box,"Click add/edit | Hold R + click remove")
			GL(help_box,"Hold R + double-click connected | Alt chain | Shift path")
			GL(help_box,"Ctrl slice | T trim")
