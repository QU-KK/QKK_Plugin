from ..G import *
"""UV pin data,overlay drawing,modal pin tools,pin application,and UV Pins panel.
Loaded into the add-on package shared namespace by __init__.py.
"""
def redraw_all_uv_editors():
	window_manager=bpy.context.window_manager
	if window_manager is None:
		return
	for window in window_manager.windows:
		screen=window.screen
		if screen is None:
			continue
		for area in screen.areas:
			if area.type== "IMAGE_EDITOR":
				area.tag_redraw()
def update_uv_pin_overlay_setting(self,context):
	redraw_all_uv_editors()
class EDGEDECAL_PG_uv_slice_pin(PropertyGroup):
	u: FloatProperty(name="Slice U",default=0.5,min=0.0,max=1.0,description="沿用作有效切割的贴花链的标准化位置",update=update_uv_pin_overlay_setting,)
class EDGEDECAL_PG_uv_pin(PropertyGroup):
	pin_name: StringProperty(name="Name",default="",description=("为该UV固定显示的可选名称；空物体名称使用其\n 数字"),update=update_uv_pin_overlay_setting,)
	material: PointerProperty(name="Material",type=bpy.types.Material,description="其贴花层使用此UV固定的材质",)
	u: FloatProperty(name="U",default=0.5)
	v: FloatProperty(name="V",default=0.5)
	width: FloatProperty(name="Width",default=0.25,min=0.0001,soft_max=1.0,description=("指定给该固定的贴花孤岛的目标垂直UV高度"),update=update_uv_pin_overlay_setting,)
	slice_pins: CollectionProperty(type=EDGEDECAL_PG_uv_slice_pin)
	active_slice_index: IntProperty(default=-1,min=-1)
def uv_pin_material_matches(pin,material):
	return getattr(pin, "material",None)==material
def uv_pin_display_name(pin,display_index):
	custom_name=str(getattr(pin, "pin_name", "")).strip()
	return custom_name or f"Pin {int(display_index) + 1}"
def uv_pin_entries_for_material(scene,material,fallback_to_default=False,):
	if scene is None or not hasattr(scene, "edge_decal_uv_pins"):
		return []
	entries=[(index,pin) for index,pin in enumerate(scene.edge_decal_uv_pins) if uv_pin_material_matches(pin,material)]
	if entries or material is None or not fallback_to_default:
		return entries
	return [(index,pin) for index,pin in enumerate(scene.edge_decal_uv_pins) if uv_pin_material_matches(pin,None)]
def active_uv_pin_entries(scene):
	material=getattr(scene, "edge_decal_uv_pin_material",None)
	return uv_pin_entries_for_material(scene,material)
def active_uv_pins(scene):
	return [pin for _index,pin in active_uv_pin_entries(scene)]
def decal_layer_material_for_uv_pins(decal_layer,fallback_material=None):
	if decal_layer is not None:
		data=getattr(decal_layer, "edge_decal_object_settings",None)
		material=(getattr(data, "decal_template_material",None) if data else None)
		if material is None:
			material=getattr(data, "decal_material",None) if data else None
			material=root_decal_template_material(material)
		if material is not None:
			return material
		mesh=getattr(decal_layer, "data",None)
		if mesh is not None and getattr(mesh, "materials",None):
			if len(mesh.materials) > 0 and mesh.materials[0] is not None:
				return mesh.materials[0]
	return fallback_material
def uv_pins_for_decal_layer_material(scene,decal_layer,fallback_material=None,):
	material=decal_layer_material_for_uv_pins(decal_layer,fallback_material=fallback_material,)
	return [pin for _index,pin in uv_pin_entries_for_material(scene,material,fallback_to_default=True,)]
def set_uv_pin_to_active_material(scene,pin):
	pin.material=getattr(scene, "edge_decal_uv_pin_material",None)
	return pin
def update_uv_pin_material_selection(self,context):
	scene=context.scene
	entries=active_uv_pin_entries(scene)
	scene.edge_decal_uv_pin_index=entries[0][0] if entries else -1
	redraw_all_uv_editors()
def select_nearest_active_uv_pin(scene,preferred_storage_index=-1):
	entries=active_uv_pin_entries(scene)
	if not entries:
		scene.edge_decal_uv_pin_index=-1
		return -1
	storage_indices=[index for index,_pin in entries]
	selected=min(storage_indices,
		key=lambda index: abs(index - int(preferred_storage_index)),)
	scene.edge_decal_uv_pin_index=selected
	return selected
def uv_grid_step_for_context(context,minimum_pixel_spacing=12.0):
	region=getattr(context, "region",None)
	if region is None or not hasattr(region, "view2d"):
		return 0.01
	try:
		u0,v0=region.view2d.region_to_view(0.0,0.0)
		u1,v1=region.view2d.region_to_view(1.0,1.0)
		uv_per_pixel=max(abs(u1 - u0),abs(v1 - v0),1.0e-12)
	except (AttributeError,RuntimeError,TypeError):
		return 0.01
	required_step=uv_per_pixel * max(1.0,float(minimum_pixel_spacing))
	grid_steps=(0.000001,0.000002,0.000005,0.00001,0.00002,0.00005,0.0001,0.0002,0.0005,0.001,0.002,0.005,0.01,0.02,0.05,0.1,0.2,0.25,0.5,1.0,2.0,5.0,10.0,)
	for step in grid_steps:
		if step + EPSILON >=required_step:
			return step
	return grid_steps[-1]
def snap_uv_value_to_grid(value,context):
	step=uv_grid_step_for_context(context)
	if step <=EPSILON:
		return value
	return round(float(value) / step) * step
def snap_uv_point_to_grid(u,v,context):
	return (snap_uv_value_to_grid(u,context),snap_uv_value_to_grid(v,context),)
def initialize_uv_pin_slices(pin):
	return
def parse_uv_pin_indices(text):
	if text is None:
		return []
	indices=[]
	for part in str(text).split(","):
		part=part.strip()
		if not part:
			continue
		try:
			indices.append(int(part))
		except ValueError:
			continue
	return sorted(set(indices))
def format_uv_pin_indices(indices):
	return ",".join(str(index) for index in sorted(set(indices)))
def layer_assigned_uv_pin_indices(layer_obj):
	if layer_obj is None:
		return []
	data=getattr(layer_obj, "edge_decal_object_settings",None)
	if data is None:
		return []
	indices=parse_uv_pin_indices(getattr(data, "uv_pin_indices", ""))
	if indices:
		return indices
	legacy_index=int(getattr(data, "uv_pin_index",-1))
	if legacy_index >=0:
		return [legacy_index]
	return []
def layer_uv_pin_is_enabled(layer_obj,pin_index):
	return pin_index in layer_assigned_uv_pin_indices(layer_obj)
def layer_uv_pin_summary_label(layer_obj,pins):
	indices=layer_assigned_uv_pin_indices(layer_obj)
	if not indices or not pins:
		return ""
	labels=[uv_pin_display_name(pins[index],index) for index in indices if 0 <=index < len(pins)]
	return "+".join(labels)
def uv_pin_indices_for_layer(pins,decal_layer):
	if not pins:
		return []
	if decal_layer is not None:
		assigned=[index for index in layer_assigned_uv_pin_indices(decal_layer) if 0 <=index < len(pins)]
		if assigned:
			return assigned
	return list(range(len(pins)))
def pins_for_decal_layer(pins,decal_layer):
	indices=uv_pin_indices_for_layer(pins,decal_layer)
	return [pins[index] for index in indices]
def seeded_uv_pin_cycle_slot(cycle_index,pin_count,seed=0):
	pin_count=int(pin_count)
	if pin_count <=0:
		return 0
	return (int(cycle_index) + int(seed)) % pin_count
def pin_index_for_layer_cycle(cycle_index,pins,decal_layer=None,seed=0,):
	indices=uv_pin_indices_for_layer(pins,decal_layer)
	if not indices:
		return 0
	return indices[seeded_uv_pin_cycle_slot(cycle_index,len(indices),seed)]
def uv_pin_to_region(region,pin):
	return region.view2d.view_to_region(pin.u,pin.v,clip=False,)
def find_uv_pin_width_handle_under_mouse(context,mouse_x,mouse_y,radius=11.0,):
	pin_entries=active_uv_pin_entries(context.scene)
	best_hit=None
	best_distance_sq=radius * radius
	tile_left_x,_=context.region.view2d.view_to_region(0.0,0.0,clip=False)
	tile_right_x,_=context.region.view2d.view_to_region(1.0,0.0,clip=False)
	min_x,max_x=sorted((tile_left_x,tile_right_x))
	for index,pin in pin_entries:
		_,top_y=context.region.view2d.view_to_region(pin.u,pin.v + pin.width * 0.5,clip=False,)
		_,bottom_y=context.region.view2d.view_to_region(pin.u,pin.v - pin.width * 0.5,clip=False,)
		if mouse_x < min_x - radius or mouse_x > max_x + radius:
			continue
		for side,handle_y in (("TOP",top_y),("BOTTOM",bottom_y)):
			dy=handle_y - mouse_y
			distance_sq=dy * dy
			if distance_sq <=best_distance_sq:
				best_distance_sq=distance_sq
				best_hit=(index,side)
	return best_hit
def find_uv_pin_under_mouse(context,mouse_x,mouse_y,radius=13.0):
	pin_entries=active_uv_pin_entries(context.scene)
	best_index=-1
	best_distance_sq=radius * radius
	for index,pin in pin_entries:
		region_x,region_y=uv_pin_to_region(context.region,pin)
		dx=region_x - mouse_x
		dy=region_y - mouse_y
		distance_sq=dx * dx + dy * dy
		if distance_sq <=best_distance_sq:
			best_distance_sq=distance_sq
			best_index=index
	return best_index
def draw_uv_pin_overlay():
	context=bpy.context
	scene=context.scene
	if (context.area is None
		or context.area.type != "IMAGE_EDITOR"
		or not getattr(context.scene, "edge_decal_show_uv_pins",True)):
		return
	region=context.region
	pin_entries=active_uv_pin_entries(context.scene)
	selected_index=context.scene.edge_decal_uv_pin_index
	shader=gpu.shader.from_builtin("UNIFORM_COLOR")
	gpu.state.blend_set("ALPHA")
	gpu.state.line_width_set(2.0)
	for display_index,(index,pin) in enumerate(pin_entries):
		center_x,center_y=uv_pin_to_region(region,pin)
		_,top_y=region.view2d.view_to_region(pin.u,pin.v + pin.width * 0.5,clip=False,)
		_,bottom_y=region.view2d.view_to_region(pin.u,pin.v - pin.width * 0.5,clip=False,)
		if index==selected_index:
			radius=scene.edge_decal_selected_pin_size
			rgb=scene.edge_decal_selected_pin_color
		else:
			radius=scene.edge_decal_unselected_pin_size
			rgb=scene.edge_decal_unselected_pin_color
		tile_left_x,_=region.view2d.view_to_region(0.0,pin.v,clip=False)
		tile_right_x,_=region.view2d.view_to_region(1.0,pin.v,clip=False)
		boundary_batch=batch_for_shader(shader,"LINES",
			{"pos": [(tile_left_x,top_y),(tile_right_x,top_y),(tile_left_x,bottom_y),(tile_right_x,bottom_y),]},)
		shader.bind()
		shader.uniform_float("color",(rgb[0],rgb[1],rgb[2],0.75))
		boundary_batch.draw(shader)
		centerline_batch=batch_for_shader(shader,"LINES",
			{"pos": [(tile_left_x,center_y),(tile_right_x,center_y)]},)
		shader.bind()
		shader.uniform_float("color",(rgb[0],rgb[1],rgb[2],0.95))
		centerline_batch.draw(shader)
		handle_dot_radius=max(radius * 0.28,3.0)
		for handle_y in (top_y,bottom_y):
			handle_dot_vertices=[]
			for segment in range(24):
				angle=(segment / 24) * pi * 2.0
				handle_dot_vertices.append((center_x + cos(angle) * handle_dot_radius,handle_y + sin(angle) * handle_dot_radius,))
			handle_dot_batch=batch_for_shader(shader,"TRI_FAN",
				{"pos": [ (center_x,handle_y),*handle_dot_vertices,] },)
			shader.bind()
			shader.uniform_float("color",(rgb[0],rgb[1],rgb[2],1.0),)
			handle_dot_batch.draw(shader)
			handle_dot_outline=(handle_dot_vertices + [handle_dot_vertices[0]])
			handle_dot_outline_batch=batch_for_shader(shader,"LINE_STRIP",{"pos": handle_dot_outline},)
			shader.bind()
			shader.uniform_float("color",(0.0,0.0,0.0,0.85),)
			handle_dot_outline_batch.draw(shader)
		segments=32
		circle_vertices=[]
		for segment in range(segments):
			angle=(segment / segments) * pi * 2.0
			circle_vertices.append((center_x + cos(angle) * radius,center_y + sin(angle) * radius,))
		circle_vertices.append(circle_vertices[0])
		color=(rgb[0],rgb[1],rgb[2],1.0)
		outline_batch=batch_for_shader(shader,"LINE_STRIP",{"pos": circle_vertices},)
		shader.bind()
		shader.uniform_float("color",color)
		outline_batch.draw(shader)
		inner_radius=2.5
		inner_vertices=[]
		for segment in range(20):
			angle=(segment / 20) * pi * 2.0
			inner_vertices.append((center_x + cos(angle) * inner_radius,center_y + sin(angle) * inner_radius,))
		inner_vertices.append(inner_vertices[0])
		inner_batch=batch_for_shader(shader,"LINE_STRIP",{"pos": inner_vertices},)
		shader.bind()
		shader.uniform_float("color",color)
		inner_batch.draw(shader)
		cross=[(center_x - radius - 4.0,center_y),(center_x - radius + 1.0,center_y),(center_x + radius - 1.0,center_y),(center_x + radius + 4.0,center_y),(center_x,center_y - radius - 4.0),(center_x,center_y - radius + 1.0),(center_x,center_y + radius - 1.0),(center_x,center_y + radius + 4.0),]
		cross_batch=batch_for_shader(shader,"LINES",{"pos": cross},)
		shader.bind()
		shader.uniform_float("color",color)
		cross_batch.draw(shader)
		blf.position(0,center_x + radius + 6.0,center_y + radius + 3.0,0)
		blf.size(0,12)
		blf.color(0,color[0],color[1],color[2],1.0)
		blf.draw(0,g(uv_pin_display_name(pin,display_index)))
	gpu.state.line_width_set(1.0)
	gpu.state.blend_set("NONE")
class EDGEDECAL_OT_uv_pin_toggle_edit_mode(Operator):
	bl_idname= "uv.edge_decal_pin_toggle_edit_mode";bl_label= g("Toggle UV Pin Edit Mode");bl_description=("启用或禁用UV固定编辑模式，以便贴花固定快捷方式\n 不干扰法线Blender UV编辑")
	def draw(S,_):L=S.layout;[GP(L,S,n) for n in S.__annotations__]
	exit_only: BoolProperty(default=False,options={"SKIP_SAVE"})
	def execute(self,context):
		scene=context.scene
		if self.exit_only:
			if not scene.edge_decal_pin_edit_active:
				return {"CANCELLED"}
			scene.edge_decal_pin_edit_active=False
		else:
			scene.edge_decal_pin_edit_active=not scene.edge_decal_pin_edit_active
		redraw_all_uv_editors()
		if scene.edge_decal_pin_edit_active:
			GR(self,"INFO", "UV Pin Edit Mode enabled: LMB drag adjusts,Shift+LMB adds,Shift+RMB removes",)
		else:
			GR(self,"INFO", "UV Pin Edit Mode disabled")
		return {"FINISHED"}
class EDGEDECAL_OT_uv_slice_pin_set_shortcut(Operator):
	bl_idname= "uv.edge_decal_slice_pin_set_shortcut";bl_label= g("Add Slice Pin");bl_description= "将切片位置添加到选定的UV固定";bl_options={"REGISTER", "UNDO"}
	@classmethod
	def poll(cls,context):
		return (context.area is not None
			and context.area.type== "IMAGE_EDITOR"
			and bool(active_uv_pin_entries(context.scene)))
	def invoke(self,context,event):
		scene=context.scene
		pins=scene.edge_decal_uv_pins
		pin_index=scene.edge_decal_uv_pin_index
		if not (0 <=pin_index < len(pins)):
			pin_index=find_uv_pin_under_mouse(context,event.mouse_region_x,event.mouse_region_y,radius=32.0,)
		if not (0 <=pin_index < len(pins)):
			GR(self,"WARNING", "Select a UV pin before adding slice pins.")
			return {"CANCELLED"}
		u,_v=context.region.view2d.region_to_view(event.mouse_region_x,event.mouse_region_y,)
		pin=pins[pin_index]
		slice_pin=pin.slice_pins.add()
		slice_pin.u=max(0.0,min(1.0,u))
		pin.active_slice_index=len(pin.slice_pins) - 1
		scene.edge_decal_uv_pin_index=pin_index
		redraw_all_uv_editors()
		return {"FINISHED"}
class EDGEDECAL_OT_uv_pin_add_shortcut(Operator):
	bl_idname= "uv.edge_decal_pin_add_shortcut";bl_label= g("Add Decal Pin");bl_description= "在鼠标位置添加UV放置固定";bl_options={"REGISTER", "UNDO"}
	@classmethod
	def poll(cls,context):
		return (context.area is not None and context.area.type== "IMAGE_EDITOR" and context.scene is not None and context.scene.edge_decal_pin_edit_active)
	def invoke(self,context,event):
		u,v=context.region.view2d.region_to_view(event.mouse_region_x,event.mouse_region_y,)
		pin=context.scene.edge_decal_uv_pins.add()
		set_uv_pin_to_active_material(context.scene,pin)
		pin.u=u
		pin.v=v
		initialize_uv_pin_slices(pin)
		context.scene.edge_decal_uv_pin_index=(len(context.scene.edge_decal_uv_pins) - 1)
		redraw_all_uv_editors()
		return {"FINISHED"}
class EDGEDECAL_OT_uv_pin_remove_shortcut(Operator):
	bl_idname= "uv.edge_decal_pin_remove_shortcut";bl_label= g("Remove Decal Pin");bl_description= "移除鼠标游标下的贴花固定";bl_options={"REGISTER", "UNDO"}
	@classmethod
	def poll(cls,context):
		return (context.area is not None and context.area.type== "IMAGE_EDITOR" and context.scene is not None and context.scene.edge_decal_pin_edit_active)
	def invoke(self,context,event):
		pins=context.scene.edge_decal_uv_pins
		index=find_uv_pin_under_mouse(context,event.mouse_region_x,event.mouse_region_y,)
		if 0 <=index < len(pins):
			pins.remove(index)
			select_nearest_active_uv_pin(context.scene,index)
			redraw_all_uv_editors()
		return {"FINISHED"}
class EDGEDECAL_OT_uv_pin_move_shortcut(Operator):
	bl_idname= "uv.edge_decal_pin_move_shortcut";bl_label= g("Move or Resize Decal Pin");bl_description=("左键单击并拖动固定中心以移动它，或顶部/底部\n 手柄来更改其垂直UV宽度。保持Ctrl捕捉到UV栅格");bl_options={"REGISTER", "UNDO", "BLOCKING"}
	def draw(S,_):L=S.layout;[GP(L,S,n) for n in S.__annotations__]
	pin_index: IntProperty(default=-1)
	interaction_mode: StringProperty(default=g("MOVE"))
	original_u: FloatProperty(default=0.0)
	original_v: FloatProperty(default=0.0)
	original_width: FloatProperty(default=0.25)
	@classmethod
	def poll(cls,context):
		return (context.area is not None and context.area.type== "IMAGE_EDITOR" and context.scene is not None and context.scene.edge_decal_pin_edit_active)
	def invoke(self,context,event):
		handle_hit=find_uv_pin_width_handle_under_mouse(context,event.mouse_region_x,event.mouse_region_y,)
		if handle_hit is not None:
			self.pin_index=handle_hit[0]
			self.interaction_mode= "RESIZE"
		else:
			self.pin_index=find_uv_pin_under_mouse(context,event.mouse_region_x,event.mouse_region_y,)
			self.interaction_mode= "MOVE"
		if self.pin_index < 0:
			return {"PASS_THROUGH"}
		pin=context.scene.edge_decal_uv_pins[self.pin_index]
		self.original_u=pin.u
		self.original_v=pin.v
		self.original_width=pin.width
		context.scene.edge_decal_uv_pin_index=self.pin_index
		context.window_manager.modal_handler_add(self)
		redraw_all_uv_editors()
		return {"RUNNING_MODAL"}
	def modal(self,context,event):
		pins=context.scene.edge_decal_uv_pins
		if not (0 <=self.pin_index < len(pins)):
			return {"CANCELLED"}
		pin=pins[self.pin_index]
		if event.type== "MOUSEMOVE":
			mouse_u,mouse_v=context.region.view2d.region_to_view(event.mouse_region_x,event.mouse_region_y,)
			if self.interaction_mode== "RESIZE":
				handle_v=(snap_uv_value_to_grid(mouse_v,context) if event.ctrl else mouse_v)
				pin.width=max(abs(handle_v - pin.v) * 2.0,0.0001,)
			else:
				if event.ctrl:
					mouse_u,mouse_v=snap_uv_point_to_grid(mouse_u,mouse_v,context,)
				pin.u=mouse_u
				pin.v=mouse_v
			redraw_all_uv_editors()
			return {"RUNNING_MODAL"}
		if event.type== "LEFTMOUSE" and event.value== "RELEASE":
			redraw_all_uv_editors()
			return {"FINISHED"}
		if event.type in {"ESC", "RIGHTMOUSE"}:
			pin.u=self.original_u
			pin.v=self.original_v
			pin.width=self.original_width
			redraw_all_uv_editors()
			return {"CANCELLED"}
		return {"RUNNING_MODAL"}
class EDGEDECAL_OT_uv_pin_tool(Operator):
	bl_idname= "uv.edge_decal_pin_tool";bl_label= g("Place / Drag Decal Pins");bl_description=("Shift+左键单击创建固定；拖动现有固定以移动它们。  \n 保持Ctrl键，同时拖动以捕捉到UV栅格. " "Shift + Right Click removes a pin; Enter finishes");bl_options={"REGISTER", "UNDO", "BLOCKING"}
	_dragging=False
	_drag_pin_index=-1
	_drag_original_u=0.0
	_drag_original_v=0.0
	_drag_created_pin=False
	_drag_previous_selected_index=-1
	@classmethod
	def poll(cls,context):
		return (context.area is not None and context.area.type== "IMAGE_EDITOR")
	def invoke(self,context,event):
		context.scene.edge_decal_pin_edit_active=True
		self._dragging=False
		self._drag_pin_index=-1
		self._drag_created_pin=False
		self._drag_previous_selected_index=context.scene.edge_decal_uv_pin_index
		context.window_manager.modal_handler_add(self)
		context.area.tag_redraw()
		GR(self,"INFO", "v27.226.1: Shift+Click adds,drag moves,Esc exits,Right Click cancels drag",)
		return {"RUNNING_MODAL"}
	def finish(self,context):
		self._dragging=False
		context.scene.edge_decal_pin_edit_active=False
		redraw_all_uv_editors()
	def begin_drag(self,context,pin_index,created_pin=False):
		pin=context.scene.edge_decal_uv_pins[pin_index]
		self._dragging=True
		self._drag_pin_index=pin_index
		self._drag_original_u=pin.u
		self._drag_original_v=pin.v
		self._drag_created_pin=created_pin
		self._drag_previous_selected_index=context.scene.edge_decal_uv_pin_index
	def cancel_drag(self,context):
		pins=context.scene.edge_decal_uv_pins
		if not self._dragging:
			return
		if self._drag_created_pin and 0 <=self._drag_pin_index < len(pins):
			pins.remove(self._drag_pin_index)
			select_nearest_active_uv_pin(context.scene,self._drag_previous_selected_index,)
		elif 0 <=self._drag_pin_index < len(pins):
			pin=pins[self._drag_pin_index]
			pin.u=self._drag_original_u
			pin.v=self._drag_original_v
		self._dragging=False
		self._drag_pin_index=-1
		self._drag_created_pin=False
		redraw_all_uv_editors()
	def modal(self,context,event):
		if context.area is None or context.area.type != "IMAGE_EDITOR":
			context.scene.edge_decal_pin_edit_active=False
			redraw_all_uv_editors()
			return {"CANCELLED"}
		pins=context.scene.edge_decal_uv_pins
		if event.type== "ESC":
			self.finish(context)
			return {"FINISHED"}
		if event.type in {"RET", "NUMPAD_ENTER"} and event.value== "PRESS":
			self.finish(context)
			return {"FINISHED"}
		if (event.type== "RIGHTMOUSE"
			and event.value== "PRESS"
			and self._dragging):
			self.cancel_drag(context)
			return {"RUNNING_MODAL"}
		if (event.type== "RIGHTMOUSE"
			and event.value== "PRESS"
			and event.shift):
			index=find_uv_pin_under_mouse(context,event.mouse_region_x,event.mouse_region_y,)
			if 0 <=index < len(pins):
				pins.remove(index)
				select_nearest_active_uv_pin(context.scene,index)
				context.area.tag_redraw()
			return {"RUNNING_MODAL"}
		if event.type== "RIGHTMOUSE" and event.value== "PRESS":
			self.cancel_drag(context)
			return {"RUNNING_MODAL"}
		if event.type in {"DEL", "X"} and event.value== "PRESS":
			index=context.scene.edge_decal_uv_pin_index
			if 0 <=index < len(pins):
				pins.remove(index)
				select_nearest_active_uv_pin(context.scene,index)
				context.area.tag_redraw()
			return {"RUNNING_MODAL"}
		if (event.type== "LEFTMOUSE"
			and event.value== "PRESS"
			and event.shift):
			u,v=context.region.view2d.region_to_view(event.mouse_region_x,event.mouse_region_y,)
			if event.ctrl:
				u,v=snap_uv_point_to_grid(u,v,context)
			pin=pins.add()
			set_uv_pin_to_active_material(context.scene,pin)
			pin.u=u
			pin.v=v
			initialize_uv_pin_slices(pin)
			self.begin_drag(context,len(pins) - 1,created_pin=True)
			context.scene.edge_decal_uv_pin_index=len(pins) - 1
			context.area.tag_redraw()
			return {"RUNNING_MODAL"}
		if (event.type== "LEFTMOUSE"
			and event.value== "PRESS"
			and not event.shift):
			index=find_uv_pin_under_mouse(context,event.mouse_region_x,event.mouse_region_y,)
			if index >=0:
				self.begin_drag(context,index)
				context.scene.edge_decal_uv_pin_index=index
			context.area.tag_redraw()
			return {"RUNNING_MODAL"}
		if event.type== "MOUSEMOVE" and self._dragging:
			index=context.scene.edge_decal_uv_pin_index
			if 0 <=index < len(pins):
				u,v=context.region.view2d.region_to_view(event.mouse_region_x,event.mouse_region_y,)
				if event.ctrl:
					u,v=snap_uv_point_to_grid(u,v,context)
				pins[index].u=u
				pins[index].v=v
				context.area.tag_redraw()
			return {"RUNNING_MODAL"}
		if event.type== "LEFTMOUSE" and event.value== "RELEASE":
			self._dragging=False
			return {"RUNNING_MODAL"}
		if event.type in {"MIDDLEMOUSE","WHEELUPMOUSE","WHEELDOWNMOUSE","WHEELINMOUSE","WHEELOUTMOUSE",}:
			return {"PASS_THROUGH"}
		return {"RUNNING_MODAL"}
class EDGEDECAL_OT_uv_pin_add(Operator):
	bl_idname= "uv.edge_decal_pin_add";bl_label= g("Add UV Pin");bl_description= "在UV平铺的中心添加UV放置固定";bl_options={"REGISTER", "UNDO"}
	@classmethod
	def poll(cls,context):
		return context.scene is not None
	def execute(self,context):
		pins=context.scene.edge_decal_uv_pins
		pin=pins.add()
		set_uv_pin_to_active_material(context.scene,pin)
		pin.u=0.5
		material_slot=len(active_uv_pin_entries(context.scene)) - 1
		storage_index=len(pins) - 1
		pin.v=0.125 + (material_slot % 4) * 0.25
		initialize_uv_pin_slices(pin)
		context.scene.edge_decal_uv_pin_index=storage_index
		redraw_all_uv_editors()
		return {"FINISHED"}
class EDGEDECAL_OT_uv_pin_delete(Operator):
	bl_idname= "uv.edge_decal_pin_delete";bl_label= g("Delete Selected Pin");bl_options={"REGISTER", "UNDO"}
	def execute(self,context):
		pins=context.scene.edge_decal_uv_pins
		index=context.scene.edge_decal_uv_pin_index
		if 0 <=index < len(pins):
			pins.remove(index)
			select_nearest_active_uv_pin(context.scene,index)
		if context.area:
			context.area.tag_redraw()
		return {"FINISHED"}
class EDGEDECAL_OT_uv_pin_remove_index(Operator):
	bl_idname= "uv.edge_decal_pin_remove_index";bl_label= g("Remove Pin");bl_options={"REGISTER", "UNDO"}
	def draw(S,_):L=S.layout;[GP(L,S,n) for n in S.__annotations__]
	index: IntProperty(default=-1)
	def execute(self,context):
		pins=context.scene.edge_decal_uv_pins
		if 0 <=self.index < len(pins):
			pins.remove(self.index)
			select_nearest_active_uv_pin(context.scene,self.index)
		if context.area:
			context.area.tag_redraw()
		return {"FINISHED"}
class EDGEDECAL_OT_uv_slice_pin_add(Operator):
	bl_idname= "uv.edge_decal_slice_pin_add";bl_label= g("Add Slice");bl_options={"REGISTER", "UNDO"}
	def execute(self,context):
		pins=context.scene.edge_decal_uv_pins
		pin_index=context.scene.edge_decal_uv_pin_index
		if not (0 <=pin_index < len(pins)):
			return {"CANCELLED"}
		pin=pins[pin_index]
		existing=sorted(slice_pin.u for slice_pin in pin.slice_pins)
		position=0.5
		if existing:
			boundaries=[0.0] + existing + [1.0]
			largest=max(zip(boundaries[:-1],boundaries[1:]),key=lambda pair: pair[1] - pair[0],)
			position=(largest[0] + largest[1]) * 0.5
		item=pin.slice_pins.add()
		item.u=position
		pin.active_slice_index=len(pin.slice_pins) - 1
		redraw_all_uv_editors()
		return {"FINISHED"}
class EDGEDECAL_OT_uv_slice_pin_remove(Operator):
	bl_idname= "uv.edge_decal_slice_pin_remove";bl_label= g("Remove Slice");bl_options={"REGISTER", "UNDO"}
	def draw(S,_):L=S.layout;[GP(L,S,n) for n in S.__annotations__]
	index: IntProperty(default=-1)
	def execute(self,context):
		pins=context.scene.edge_decal_uv_pins
		pin_index=context.scene.edge_decal_uv_pin_index
		if not (0 <=pin_index < len(pins)):
			return {"CANCELLED"}
		pin=pins[pin_index]
		index=self.index if self.index >=0 else pin.active_slice_index
		if 0 <=index < len(pin.slice_pins):
			pin.slice_pins.remove(index)
			pin.active_slice_index=min(index,len(pin.slice_pins) - 1)
		redraw_all_uv_editors()
		return {"FINISHED"}
class EDGEDECAL_UL_uv_pins(UIList):
	bl_idname= "EDGEDECAL_UL_uv_pins"
	def filter_items(self,context,data,property_name):
		pins=getattr(data,property_name)
		material=getattr(context.scene,"edge_decal_uv_pin_material",None,)
		flags=[self.bitflag_filter_item if uv_pin_material_matches(pin,material) else 0 for pin in pins]
		return flags,[]
	def draw_item(self,context,layout,data,item,icon,active_data,active_property,index,):
		pin=item
		row=layout.row(align=True)
		icon_name=("RADIOBUT_ON" if index==context.scene.edge_decal_uv_pin_index else "RADIOBUT_OFF")
		row.label(text="",icon=icon_name)
		visible_indices=[storage_index for storage_index,_pin in active_uv_pin_entries(context.scene)]
		display_index=(visible_indices.index(index) if index in visible_indices else index)
		GL(row,uv_pin_display_name(pin,display_index))
		coords=row.row(align=True)
		coords.scale_x=0.8
		GL(coords,f"U {pin.u:.3f}")
		GL(coords,f"V {pin.v:.3f}")
		GL(coords,f"W {pin.width:.3f}")
		GL(coords,f"S {len(pin.slice_pins)}")
		remove=row.operator(EDGEDECAL_OT_uv_pin_remove_index.bl_idname,text="",icon="X",emboss=False,)
		remove.index=index
class EDGEDECAL_OT_uv_pin_clear(Operator):
	bl_idname= "uv.edge_decal_pin_clear";bl_label= g("Clear All Pins");bl_options={"REGISTER", "UNDO"}
	def execute(self,context):
		pins=context.scene.edge_decal_uv_pins
		for index,_pin in reversed(active_uv_pin_entries(context.scene)):
			pins.remove(index)
		context.scene.edge_decal_uv_pin_index=-1
		if context.area:
			context.area.tag_redraw()
		return {"FINISHED"}
class EDGEDECAL_OT_uv_pin_create_equal(Operator):
	bl_idname= "uv.edge_decal_pin_create_equal";bl_label= g("Create Equal UV Pins");bl_description=("替换当前固定");bl_options={"REGISTER", "UNDO"}
	def draw(S,_):L=S.layout;[GP(L,S,n) for n in S.__annotations__]
	pin_count: IntProperty(name="Pin Count",description="要创建的等大小UV固定行的数字",default=4,min=1,max=128,)
	def invoke(self,context,_event):
		return context.window_manager.invoke_props_dialog(self,width=320)
	def draw(self,context):
		layout=self.layout
		GP(layout,self, "pin_count")
		if active_uv_pin_entries(context.scene):
			GL(layout,"This replaces the selected material's UV pins.",icon="ERROR",)
	def execute(self,context):
		scene=context.scene
		pins=scene.edge_decal_uv_pins
		for storage_index,_pin in reversed(active_uv_pin_entries(scene)):
			pins.remove(storage_index)
		width=1.0 / self.pin_count
		first_storage_index=-1
		for index in range(self.pin_count):
			pin=pins.add()
			set_uv_pin_to_active_material(scene,pin)
			if first_storage_index < 0:
				first_storage_index=len(pins) - 1
			pin.u=0.5
			pin.v=(index + 0.5) * width
			pin.width=width
			initialize_uv_pin_slices(pin)
		scene.edge_decal_uv_pin_index=first_storage_index
		redraw_all_uv_editors()
		GR(self,"INFO",f"Created {self.pin_count} equal UV pin(s)",)
		return {"FINISHED"}
def uv_island_centerline_center(decal_obj,uv_layer,island):
	mesh=decal_obj.data
	center_vertices=get_center_vertex_indices(decal_obj)
	center_loops=[loop_index
		for loop_index in island["loops"]
		if mesh.loops[loop_index].vertex_index in center_vertices]
	loops=center_loops if center_loops else island["loops"]
	if not loops:
		return Vector((0.0,0.0))
	min_u=min(uv_layer.data[index].uv.x for index in loops)
	max_u=max(uv_layer.data[index].uv.x for index in loops)
	min_v=min(uv_layer.data[index].uv.y for index in loops)
	max_v=max(uv_layer.data[index].uv.y for index in loops)
	return Vector(((min_u + max_u) * 0.5,(min_v + max_v) * 0.5,))
def average_uv_island_record_scales(island_records):
	measurements=[]
	total_mesh_area=0.0
	total_uv_area=0.0
	for obj,uv_layer,island in island_records:
		mesh=obj.data
		mesh_area=sum(mesh.polygons[polygon_index].area for polygon_index in island["polygons"])
		uv_area=sum(uv_polygon_area( uv_layer,mesh.polygons[polygon_index],) for polygon_index in island["polygons"])
		if mesh_area <=EPSILON or uv_area <=EPSILON:
			measurements.append(None)
			continue
		measurements.append((mesh_area,uv_area))
		total_mesh_area +=mesh_area
		total_uv_area +=uv_area
	if total_mesh_area <=EPSILON or total_uv_area <=EPSILON:
		return
	target_density=(total_uv_area / total_mesh_area) ** 0.5
	for record,measurement in zip(island_records,measurements,):
		if measurement is None:
			continue
		_obj,uv_layer,island=record
		mesh_area,uv_area=measurement
		current_density=(uv_area / mesh_area) ** 0.5
		if current_density <=EPSILON:
			continue
		scale_uv_island_about_center(uv_layer,island["loops"],target_density / current_density,)
def uv_island_cross_width(decal_obj,uv_layer,island,):
	axis_angle=centerline_uv_axis_angle(decal_obj,uv_layer,island["loops"],)
	if axis_angle is None:
		axis_angle=principal_uv_axis_angle(uv_layer,island["loops"],)
	perpendicular=Vector((-sin(axis_angle),cos(axis_angle),))
	projections=[uv_layer.data[loop_index].uv.dot(perpendicular)
		for loop_index in island["loops"]]
	if not projections:
		return EPSILON
	return max(max(projections) - min(projections),EPSILON,)
def apply_uv_pins_to_decal_objects(decal_objects,pins,seed=None):
	if not pins:
		return 0
	island_records=[]
	for obj in sorted(decal_objects,
		key=lambda item: item.name_full,):
		if (obj.type != "MESH"
			or not obj.get("edge_decal_generated")
			or obj.data.uv_layers.active is None):
			continue
		mesh=obj.data
		uv_layer=mesh.uv_layers.active
		islands=collect_selected_uv_islands(mesh,selected_only=False,)
		for island in islands:
			if island["loops"]:
				island_records.append((obj,uv_layer,island))
	if not island_records:
		return 0
	touched_objects=set()
	island_counters={}
	for obj,uv_layer,island in island_records:
		layer_pins=pins_for_decal_layer(pins,obj)
		if not layer_pins:
			continue
		counter=island_counters.get(obj.name_full,0)
		object_seed=seed
		if object_seed is None:
			object_settings=getattr(obj,"edge_decal_object_settings",None,)
			object_seed=int(getattr(object_settings, "seed",0))
		pin=layer_pins[seeded_uv_pin_cycle_slot(counter,len(layer_pins),object_seed,)]
		island_counters[obj.name_full]=counter + 1
		loops=island["loops"]
		centerline_angle=centerline_uv_axis_angle(obj,uv_layer,loops,)
		if centerline_angle is not None:
			rotate_uv_island(uv_layer,loops,-centerline_angle,)
		current_center=uv_island_centerline_center(obj,uv_layer,island,)
		min_v=min(uv_layer.data[index].uv.y for index in loops)
		max_v=max(uv_layer.data[index].uv.y for index in loops)
		current_width=max(max_v - min_v,EPSILON)
		uniform_scale=(pin.width / current_width) * 0.999999
		for loop_index in loops:
			uv=uv_layer.data[loop_index].uv
			uv.x=current_center.x + (uv.x - current_center.x) * uniform_scale
			uv.y=current_center.y + (uv.y - current_center.y) * uniform_scale
		scaled_center=uv_island_centerline_center(obj,uv_layer,island,)
		offset=Vector((pin.u,pin.v)) - scaled_center
		for loop_index in loops:
			uv_layer.data[loop_index].uv +=offset
		touched_objects.add(obj)
	for obj in touched_objects:
		obj.data.update()
	return len(island_records)
def apply_uv_pins_to_decal_objects_by_material(scene,decal_objects):
	processed_count=0
	for decal_obj in decal_objects:
		pins=uv_pins_for_decal_layer_material(scene,decal_obj)
		if not pins:
			continue
		processed_count +=apply_uv_pins_to_decal_objects([decal_obj],pins,)
	return processed_count
def decal_objects_have_material_uv_pins(scene,decal_objects):
	return any(decal_obj is not None
		and getattr(decal_obj, "type",None)== "MESH"
		and decal_obj.get("edge_decal_generated")
		and uv_pins_for_decal_layer_material(scene,decal_obj) for decal_obj in decal_objects)
class EDGEDECAL_OT_apply_uv_pins(Operator):
	bl_idname= "uv.edge_decal_apply_pins";bl_label= g("Center Decals on Pins");bl_description=("均匀缩放UV孤岛，以匹配固定宽度无拉伸，然后\n 将他们的跟踪贴花中心线中心在固定上");bl_options={"REGISTER", "UNDO"}
	@classmethod
	def poll(cls,context):
		return bool(context.selected_objects
			and decal_objects_have_material_uv_pins(context.scene,context.selected_objects,) 	)
	def execute(self,context):
		decal_objects=[obj for obj in context.selected_objects if (obj.type== "MESH" and obj.get("edge_decal_generated") and obj.data.uv_layers.active is not None) 	]
		if not decal_objects:
			GR(self,"ERROR","Select at least one generated edge-decal object.",)
			return {"CANCELLED"}
		processed_count=apply_uv_pins_to_decal_objects_by_material(context.scene,decal_objects,)
		if processed_count==0:
			GR(self,"ERROR", "No UV islands were found.")
			return {"CANCELLED"}
		GR(self,"INFO",f"Centered {processed_count} UV island(s) using material pin sets.",)
		return {"FINISHED"}
class EDGEDECAL_PT_uv_pins(Panel):
	bl_idname="EDGEDECAL_PT_uv_pins";bl_label= "";bl_space_type= "IMAGE_EDITOR";bl_region_type="UI";bl_category=TB
	def draw_header(S,_):GL(S.layout,"Edge Decal UV Pins")
	def draw(self,context):
		layout=self.layout
		scene=context.scene
		pin_entries=active_uv_pin_entries(scene)
		pins=[pin for _index,pin in pin_entries]
		selected_index=scene.edge_decal_uv_pin_index
		selected_display_index=next((display_index
				for display_index,(storage_index,_pin) in enumerate(pin_entries) if storage_index==selected_index),-1,)
		valid_selection=selected_display_index >=0
		material_box=layout.box()
		GL(material_box,"Material Pin Set",icon="MATERIAL")
		GP(material_box,scene,"edge_decal_uv_pin_material",text="Material",)
		if (scene.edge_decal_uv_pin_material is not None
			and not pins
			and uv_pin_entries_for_material(scene,None)):
			GL(material_box,"No dedicated pins; layers currently use Default pins",icon="INFO",)
		header=layout.row(align=True)
		GL(header,f"UV Pins  {len(pins)}",icon="PIVOT_CURSOR")
		header.prop(scene,"edge_decal_show_uv_pins",text="",icon=("HIDE_OFF" if scene.edge_decal_show_uv_pins else "HIDE_ON"),emboss=False,)
		mode_row=layout.row(align=True)
		mode_row.scale_y=1.15
		GO(mode_row,EDGEDECAL_OT_uv_pin_toggle_edit_mode.bl_idname,text=("Exit Pin Edit Mode"
				if scene.edge_decal_pin_edit_active
				else "Enter Pin Edit Mode"),icon=("CHECKMARK" if scene.edge_decal_pin_edit_active else "GREASEPENCIL"),)
		toolbar=layout.row(align=True)
		GO(toolbar,EDGEDECAL_OT_uv_pin_add.bl_idname,text="Add Pin",icon="ADD",)
		GO(toolbar,EDGEDECAL_OT_uv_pin_delete.bl_idname,text="Remove",icon="REMOVE",)
		toolbar.operator(EDGEDECAL_OT_uv_pin_clear.bl_idname,text="",icon="TRASH",)
		equal_row=layout.row()
		equal_row.scale_y=1.1
		GO(equal_row,EDGEDECAL_OT_uv_pin_create_equal.bl_idname,text="Create Equal Pins",icon="UV",)
		list_box=layout.box()
		list_box.template_list(EDGEDECAL_UL_uv_pins.bl_idname,"",scene,"edge_decal_uv_pins",scene,"edge_decal_uv_pin_index",rows=4,)
		if valid_selection:
			pin=scene.edge_decal_uv_pins[selected_index]
			selected_box=layout.box()
			GL(selected_box,("Selected: "
					f"{uv_pin_display_name(pin,selected_display_index)}"),icon="RADIOBUT_ON",)
			GP(selected_box,pin, "pin_name",text="Name")
			position_row=selected_box.row(align=True)
			GP(position_row,pin, "u",text="U")
			GP(position_row,pin, "v",text="V")
			GP(selected_box,pin, "width",slider=True)
		apply_column=layout.column()
		apply_column.enabled=decal_objects_have_material_uv_pins(scene,context.selected_objects,)
		apply_column.scale_y=1.25
		GO(apply_column,EDGEDECAL_OT_apply_uv_pins.bl_idname,text="Apply Pins to Selected Decals",icon="UV_SYNC_SELECT",)
		help_box=layout.box()
		GL(help_box,"Viewport Controls",icon="MOUSE_LMB")
		GL(help_box,("Pin Edit Mode is ON"
				if scene.edge_decal_pin_edit_active
				else "Pin Edit Mode is OFF"),icon=("CHECKMARK" if scene.edge_decal_pin_edit_active else "PAUSE"),)
		GL(help_box,"Shift + LMB: add pin")
		GL(help_box,"Shift + RMB: remove pin")
		GL(help_box,"LMB + drag: move or resize pin")
		GL(help_box,"When OFF,Blender UV shortcuts work normally.")
		GL(help_box,"Assign UV pins per layer in the 3D View Decal Layers panel",icon="RENDERLAYERS",)
		appearance=layout.box()
		GL(appearance,"Display",icon="COLOR")
		selected_style=appearance.column(align=True)
		GP(selected_style,scene,"edge_decal_selected_pin_color",text="Selected Color",)
		GP(selected_style,scene,"edge_decal_selected_pin_size",text="Selected Size",)
		unselected_style=appearance.column(align=True)
		GP(unselected_style,scene,"edge_decal_unselected_pin_color",text="Other Pin Color",)
		GP(unselected_style,scene,"edge_decal_unselected_pin_size",text="Other Pin Size",)
