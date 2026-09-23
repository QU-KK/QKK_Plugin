from .G import *
VERSION=(2,0,5)
VERSION_TEXT= ".".join(str(n) for n in (VERSION[:2] if VERSION[2]==0 else VERSION))
bl_info={"name": "🌐 智能重构 (Smart Remesh)","author":"Milad Kambari - 3DRedbox Studio 汉化：GJJ","version": (2,0,5),"blender": (4,2,0),"location": "3D视图>边栏(N)>智能重构","description": "硬表面和有机模型的四边重构。将平直面板重建为n个多边形，并丢弃无形状的循环边，无移动表面","doc_url": "https://discord.gg/EC8d7nPsYj", "tracker_url": "https://discord.gg/EC8d7nPsYj", "category": "Mesh",}
QUADREMESH_SOURCE= "quadremesh_source"
QUADREMESH_ORIG= "quadremesh_orig_mesh"
QUADREMESH_KIND= "quadremesh_kind"
ARTSTATION_URL= "https://www.artstation.com/milad_kambari"
SUPERHIVE_URL= "https://superhivemarket.com/seller/milad_kambari"
DISCORD_URL= "https://discord.gg/EC8d7nPsYj"
import importlib,os,sys,traceback,bpy,bmesh,numpy as np
from bpy.props import (BoolProperty,EnumProperty,FloatProperty,IntProperty,PointerProperty,StringProperty)
from bpy.types import Operator,Panel,PropertyGroup
from .core import instantmeshes
from . import lines_preview
from .core.auto import auto_remesh
from .core import remesh as run_remesh
from .core.instantmeshes import find_exe
for _name in list(sys.modules):
	if _name.startswith(__name__ + ".core"):
		importlib.reload(sys.modules[_name])
class SmartRemeshPrefs(bpy.types.AddonPreferences):
	bl_idname=AD
	exe_path: StringProperty(name="Instant Meshes",subtype="FILE_PATH",default=JP(FP,"bin","Instant Meshes.exe"),description="即时网格可执行的路径。将空物体保留为\n 使用与加载项捆绑的副本。仅需要" "苹果系统和Linux，其中没有绑定副本",)
	V:bpy.props.BoolProperty(default=1,name='Confirm version compatibility',description="不再显示版本提示")
	C:bpy.props.StringProperty(name="Category",description="N面板类别的名称",default=TB,update=UPG)
	def draw(self,context):
		layout=self.layout.column_flow(columns=2,align=1);DH(self,context,layout);layout.template_icon(icon_value=I("1"),scale=12);GP(layout,self,"C",text="Category");X(self,context,layout);layout=self.layout
		GP(layout,self, "exe_path",text="Instant Meshes")
		if engine_exe() is None:
			box=layout.box()
			GL(box,"Organic engine not found",icon="ERROR")
			col=box.column(align=True)
			GL(col,"Download the build for your platform from the")
			GL(col,"Instant Meshes project page,unzip it,and point")
			GL(col,"the field above at the executable.")
			GL(col,"On macOS that is inside the .app bundle,at")
			GL(col,"Instant Meshes.app/Contents/MacOS/Instant Meshes")
			col.separator()
			GL(col,"Smart Remesh (Hardsurface) needs none of this")
			GL(col,"and works on every platform as shipped.")
		else:
			GL(layout,"Organic engine found",icon="CHECKMARK")
def engine_path() -> str:
	try:
		prefs=P()
		return bpy.path.abspath(prefs.exe_path or "")
	except Exception:
		return ""
def engine_exe():
	return find_exe(engine_path())
def engine_blocked() -> str:
	exe=engine_exe()
	if exe and instantmeshes.is_quarantined(exe):
		return exe
	return ""
class QUADREMESH_OT_unquarantine(Operator):
	"""清理捆绑有机引擎的苹果系统隔离标志。
	引擎从其作者处重新发布，未经从，并且不携带
	苹果签名，因此苹果系统将其标记为与到达的任何否则一样
	下载。从从打开，这将是通常的"无论如何打开"
	prompt; run in the background the way this add-on runs it,there is no
	prompt - it is killed and the remesh fails with nothing to click.
	Doing this silently at install time would have been easy and is exactly
	why it is not done: undoing a Gatekeeper flag is the user's decision,so
	it asks first and names the command it will run.
	"""
	bl_idname= "mesh.quadremesh_unquarantine";bl_label=g("Allow Organic Engine");bl_description=("让苹果系统运行捆绑的有机引擎。清除\n 加载项自己的bin文件夹上的隔离标志");bl_options={"REGISTER"}
	def invoke(self,context,event):
		return context.window_manager.invoke_props_dialog(self,width=460)
	def draw(self,context):
		col=self.layout.column(align=True)
		exe=engine_exe() or ""
		GL(col,"This runs,on the add-on's own folder only:")
		col.separator()
		box=self.layout.box().column(align=True)
		GL(box,"xattr -dr com.apple.quarantine")
		GL(box,os.path.dirname(exe) if exe else "")
		col=self.layout.column(align=True)
		col.separator()
		GL(col,"The engine is Instant Meshes,redistributed")
		GL(col,"unmodified from its authors. macOS flags it")
		GL(col,"because it has no Apple signature,not because")
		GL(col,"anything is wrong with it.")
		col.separator()
		GL(col,"Prefer to do it yourself? Run that command in")
		GL(col,"Terminal instead. Nothing else changes.")
	def execute(self,context):
		exe=engine_exe()
		if not exe:
			GR(self,"ERROR", "Organic engine not found")
			return {"CANCELLED"}
		ok,why=instantmeshes.clear_quarantine(exe)
		if not ok:
			GR(self,"ERROR",f"Could not clear the flag: {why}")
			return {"CANCELLED"}
		GR(self,"INFO", "Organic engine enabled")
		return {"FINISHED"}
_ENGINE_ITEMS: list=[]
def _engine_items(self,context):
	global _ENGINE_ITEMS
	if engine_exe() is not None:
		items=[("AUTO", "Auto","分析模型，从中导出折痕角度，校准\n 面数量，然后尝试几个设置并保持最佳"),("STABLE", "Manual", "一通过，设置如下，无分析"),]
	else:
		items=[("OURS", "In-house","纯净Python，没有二进制。平台上使用的引擎\n 即时网格构建不涵盖。较慢，其输出为" "更粗糙-期望非流形边和较低的四边比"),]
	_ENGINE_ITEMS=items
	return _ENGINE_ITEMS
class QuadRemeshSettings(PropertyGroup):
	backend: EnumProperty(name="Engine",items=_engine_items,description="哪个解算器重建表面")
	auto_crease: BoolProperty(name="Detect Crease Angle",default=True,description="读取模型自身二面体的折痕角度关\n 直方图，而不是使用下面的值",)
	auto_calibrate: BoolProperty(name="Calibrate Face Count",default=True,description="即时网格将面目标视为提示，并\n 通常会超过它几次次数。这个探测器" "一次，并为其更正",)
	auto_search: BoolProperty(name="Search Settings",default=True,description="尝试几个折痕角度，并保持最好的分数。  \n 需要几次额外跑步",)
	pure_quad: BoolProperty(name="Pure Quads",default=True,description="仅限即时网格。关提供四边形主导网格\n 更近地击中目标面数量",)
	mode: EnumProperty(name="Target",items=[("FACES", "Face Count", "目标为数字的输出面"),("EDGE", "Edge Length", "目标是绝对四边尺寸"),],default="FACES",)
	target_faces: IntProperty(name="Faces",default=2000,min=8,soft_max=200000,description="要生成的四边形的近似数字",)
	target_edge: FloatProperty(name="Edge Length",default=0.1,min=1e-5,soft_max=10.0,subtype="DISTANCE",description="近似四边侧长度，以对象单位表示",)
	feature_angle: FloatProperty(name="Sharp Angle",default=30.0,min=0.0,max=180.0,description="处理边的二面角角度，以度为单位\n 作为折痕保存",)
	orient_iterations: IntProperty(name="Orientation Steps",default=40,min=1,max=500,description="平滑为方向域通过。如果出现以下情况，请提出此问题\n 水流看起来很吵",)
	position_iterations: IntProperty(name="Position Steps",default=40,min=1,max=500,description="晶格位置的平滑过程",)
	smooth_iterations: IntProperty(name="Relax",default=0,min=0,max=20,description="放松输出。我们的引擎没有\n 重投影，因此它仅将顶点关表面-\n 在0离开。对于即时网格，它是重投影" "步骤数量和2是一个好的值",)
	thin_density: FloatProperty(name="Thin Parts",default=1.0,min=0.0,max=1.0,description="将较小的四边形放在模型较薄的位置，以便板材\n 布料或指甲永远不会被四边跨越" "比它的厚度还宽。0转向它关")
	spread_over: FloatProperty(name="Build Over",default=3.0,min=1.5,max=6.0,description="在捆绑引擎上安装适配密度\n 许多次数你要的面数量然后掉下来\n 没有形状的环。越高越容易下降" "更多可供选择，并且需要更长的时间")
	adaptive: BoolProperty(name="Adaptive Density",default=False,description="在褶皱附近和弯曲区域放置较小的四边形。  \n 我们的引擎仅仅-即时网格没有等效的",)
	feature_density: FloatProperty(name="Near Creases",default=1.0,min=0.0,max=1.0,description="围绕锐边边进行细化的强度",)
	curvature_density: FloatProperty(name="By Curvature",default=0.6,min=0.0,max=1.0,description="细化表面弯曲处的强度",)
	inner_density: FloatProperty(name="Inner Edges",default=1.0,min=0.0,max=1.0,description="细化凹形边-内部夹角、凹槽、\n 放置AO烘焙变为暗",)
	outer_density: FloatProperty(name="Outer Edges",default=0.5,min=0.0,max=1.0,description="细化凸包边-外部夹角、脊、边",)
	min_size_ratio: FloatProperty(name="Min Size",default=0.5,min=0.15,max=1.0,description="最小的四边是基本尺寸的一小部分。0.35以下\n 四边质量急剧下降",)
	gradient_limit: FloatProperty(name="Transition",default=0.1,min=0.02,max=0.6,description="四边尺寸的快速可能会随着距离的变化而变化。Low是\n 更流畅和可测量的更好-0.1对75分" "55 用于测试中的0.4",)
	use_curvature: BoolProperty(name="Follow Curvature",default=True,description="种子方向域从主曲率。转弯\n 关，用于纯粹的折痕驱动流",)
	replace: BoolProperty(name="Replace Original",default=False,description="替换源对象，而不是添加新建一\n 在它旁边",)
def thin_shell_limit(me,samples=600):
	import bmesh
	from mathutils.bvhtree import BVHTree
	if len(me.polygons) < 8:
		return 0,0.0
	if len(me.polygons) > 200000:
		return 0,0.0
	tree=BVHTree.FromPolygons([v.co[:] for v in me.vertices],[f.vertices[:] for f in me.polygons])
	ext=[max(v.co[i] for v in me.vertices) - min(v.co[i] for v in me.vertices) for i in range(3)]
	diag=max(ext) or 1.0
	step=max(1,len(me.polygons) // samples)
	thick=[]
	for i in range(0,len(me.polygons),step):
		f=me.polygons[i]
		o=f.center - f.normal * (diag * 1e-4)
		hit=tree.ray_cast(o,-f.normal,diag)
		if hit and hit[0] is not None and hit[3] > diag * 1e-5:
			thick.append(hit[3])
	if len(thick) < 8:
		return 0,0.0
	thick.sort()
	thin=thick[int(len(thick) * 0.05)]
	area=sum(f.area for f in me.polygons)
	if thin <=0 or area <=0:
		return 0,0.0
	return int(area / (thin * thin)),thin
def spread_by_shape(new_mesh,target_faces,keep_marked=False,progress=None):
	import bmesh
	from .core import panelize as PZ
	bm=bmesh.new()
	bm.from_mesh(new_mesh)
	bm.edges.ensure_lookup_table()
	PZ.tag_marked(bm)
	start=len(bm.faces)
	if start <=target_faces:
		bm.free()
		return start,0
	total=PZ.drop_to_budget(bm,target_faces,keep_marked=keep_marked,progress=progress)
	PZ.heal_stubs(bm)
	PZ.polish_verts(bm)
	bm.to_mesh(new_mesh)
	bm.free()
	new_mesh.update()
	return start,total
def close_engine_holes(new_mesh,src_mesh):
	import bmesh
	from mathutils import Vector
	from mathutils.bvhtree import BVHTree
	bm=bmesh.new()
	bm.from_mesh(new_mesh)
	open_edges=[e for e in bm.edges if len(e.link_faces)==1]
	if not open_edges:
		bm.free()
		return 0
	src_open=None
	if len(src_mesh.polygons):
		import numpy as _np
		nl=len(src_mesh.loops)
		le=_np.empty(nl,dtype=_np.int32)
		src_mesh.loops.foreach_get("edge_index",le)
		cnt=_np.bincount(le,minlength=len(src_mesh.edges))
		open_idx=_np.flatnonzero(cnt==1)
		ev=_np.empty(len(src_mesh.edges) * 2,dtype=_np.int32)
		src_mesh.edges.foreach_get("vertices",ev)
		ev=ev.reshape(-1,2)[open_idx]
		pts=[src_mesh.vertices[int(i)].co.copy() for pair in ev for i in pair]
		if pts:
			from mathutils.kdtree import KDTree
			src_open=KDTree(len(pts))
			for i,q in enumerate(pts):
				src_open.insert(q,i)
			src_open.balance()
	ext=[max(v.co[i] for v in bm.verts) - min(v.co[i] for v in bm.verts) for i in range(3)]
	near=(max(ext) or 1.0) * 0.01
	seen=set()
	doomed=[]
	for e0 in open_edges:
		if e0.index in seen:
			continue
		stack=[e0]
		ring=[]
		while stack:
			e=stack.pop()
			if e.index in seen:
				continue
			seen.add(e.index)
			ring.append(e)
			for v in e.verts:
				for o in v.link_edges:
					if len(o.link_faces)==1 and o.index not in seen:
						stack.append(o)
		if src_open is not None:
			mid=Vector()
			for e in ring:
				mid +=(e.verts[0].co + e.verts[1].co) / 2
			mid /=len(ring)
			if src_open.find_range(mid,near):
				continue
		doomed.extend(ring)
	if not doomed:
		bm.free()
		return 0
	filled=bmesh.ops.holes_fill(bm,edges=doomed,sides=0)
	made=filled.get("faces",[])
	if made:
		tri=bmesh.ops.triangulate(bm,faces=made)["faces"]
		bmesh.ops.join_triangles(bm,faces=tri,angle_face_threshold=3.14,angle_shape_threshold=3.14,cmp_seam=False,cmp_sharp=False,cmp_uvs=False,cmp_vcols=False,cmp_materials=False)
	bm.to_mesh(new_mesh)
	bm.free()
	new_mesh.update()
	return len(made)
class QUADREMESH_OT_spread(Operator):
	"""将新构建的网格细化到其面预算，每勾选一轮."""
	bl_idname= "mesh.quadremesh_spread";bl_label=g("Spreading faces by shape");bl_options={"REGISTER", "UNDO", "INTERNAL"}
	def draw(S,_):L=S.layout;[GP(L,S,n) for n in S.__annotations__]
	mesh_name: bpy.props.StringProperty()
	target: bpy.props.IntProperty(default=0)
	_timer=None
	_thinner=None
	_bm=None
	_mesh=None
	def execute(self,context):
		return self.invoke(context,None)
	def invoke(self,context,event):
		import bmesh
		from .core import panelize as PZ
		self._mesh=bpy.data.meshes.get(self.mesh_name)
		if self._mesh is None or not self.target:
			return {"CANCELLED"}
		self._bm=bmesh.new()
		self._bm.from_mesh(self._mesh)
		self._bm.edges.ensure_lookup_table()
		PZ.tag_marked(self._bm)
		if len(self._bm.faces) <=self.target:
			self._bm.free()
			return {"CANCELLED"}
		self._thinner=PZ.BudgetThinner(self._bm,self.target,keep_marked=False)
		wm=context.window_manager
		self._timer=wm.event_timer_add(0.01,window=context.window)
		wm.modal_handler_add(self)
		context.window_manager.progress_begin(0.0,1.0)
		return {"RUNNING_MODAL"}
	def _shut(self,context,write):
		wm=context.window_manager
		if self._timer is not None:
			wm.event_timer_remove(self._timer)
			self._timer=None
		wm.progress_end()
		try:
			context.workspace.status_text_set(None)
		except Exception:
			pass
		n=0
		if self._thinner is not None:
			n=self._thinner.finish()
		if write and self._bm is not None and self._mesh is not None:
			self._bm.to_mesh(self._mesh)
			self._mesh.update()
		if self._bm is not None:
			self._bm.free()
			self._bm=None
		return n
	def modal(self,context,event):
		if event.type in {"ESC", "RIGHTMOUSE"}:
			n=self._shut(context,True)
			GR(self,"INFO",f"stopped early,{n} loops removed")
			return {"CANCELLED"}
		if event.type != "TIMER":
			return {"PASS_THROUGH"}
		going=True
		try:
			going=self._thinner.round()
		except Exception as exc:
			self._shut(context,True)
			GR(self,"WARNING",f"thinning stopped: {exc}")
			return {"CANCELLED"}
		wm=context.window_manager
		wm.progress_update(self._thinner.fraction)
		try:
			context.workspace.status_text_set(f"Smart Remesh - spreading "
				f"{len(self._bm.faces):,} of {self.target:,} faces  "
				f"{self._thinner.fraction * 100:.0f}%   (Esc to stop)")
		except Exception:
			pass
		for area in context.screen.areas:
			area.tag_redraw()
		if not going:
			n=self._shut(context,True)
			GR(self,{"INFO"},
						f"spread by shape: down to "
						f"{len(self._mesh.polygons):,} faces,{n} loops removed")
			return {"FINISHED"}
		return {"RUNNING_MODAL"}
class QUADREMESH_OT_run(Operator):
	bl_idname= "mesh.quadremesh_run";bl_label= g("Remesh (Organic)");bl_description=("使用我们自己的四边形重构活动网格\n 交叉场解算器");bl_options={"REGISTER", "UNDO"}
	@classmethod
	def poll(cls,context):
		obj=context.active_object
		return obj is not None and obj.type== "MESH" and len(obj.data.polygons)
	SOURCE_KEY=QUADREMESH_SOURCE
	def execute(self,context):
		obj=context.active_object
		st=context.scene.quadremesh
		src_name=obj.get(self.SOURCE_KEY)
		if src_name:
			src=bpy.data.objects.get(src_name)
			if src is not None and src.type== "MESH":
				GR(self,"INFO",f"rebuilding from the original '{src_name}'")
				obj=src
			else:
				GR(self,"WARNING",f"source '{src_name}' is gone; using this mesh")
		me=obj.data
		nv=len(me.vertices)
		co=np.empty(nv * 3,dtype=np.float64)
		me.vertices.foreach_get("co",co)
		co=co.reshape(nv,3)
		npoly=len(me.polygons)
		sizes=np.empty(npoly,dtype=np.int64)
		me.polygons.foreach_get("loop_total",sizes)
		loops=np.empty(int(sizes.sum()),dtype=np.int64)
		me.loops.foreach_get("vertex_index",loops)
		wm=context.window_manager
		wm.progress_begin(0.0,1.0)
		def report_progress(name,frac):
			wm.progress_update(frac)
			try:
				context.workspace.status_text_set(f"Smart Remesh - {name}  {frac * 100:.0f}%")
			except Exception:
				pass
		faces_arg=st.target_faces if st.mode== "FACES" else None
		spread=(st.adaptive and st.backend== "OURS" and st.mode== "FACES" and faces_arg)
		if spread:
			faces_arg=int(faces_arg * st.spread_over * st.spread_over)
		edge_arg=st.target_edge if st.mode== "EDGE" else None
		try:
			if st.backend== "OURS":
				result=run_remesh(co,loops,sizes,target_faces=faces_arg,target_edge=edge_arg,feature_angle=st.feature_angle,orient_iterations=st.orient_iterations,position_iterations=st.position_iterations,smooth_iterations=st.smooth_iterations,use_curvature=st.use_curvature,adaptive=st.adaptive,feature_density=st.feature_density,curvature_density=st.curvature_density,inner_density=st.inner_density,outer_density=st.outer_density,thin_strength=st.thin_density,min_size_ratio=st.min_size_ratio,gradient_limit=st.gradient_limit,progress=report_progress,)
			elif st.backend== "AUTO":
				result=auto_remesh(co,loops,sizes,target_faces=faces_arg or 4000,crease_override=None if st.auto_crease else st.feature_angle,calibrate=st.auto_calibrate,search=st.auto_search,smooth_iterations=max(st.smooth_iterations,1),exe=engine_path(),progress=report_progress,)
			elif st.backend== "STABLE":
				result=instantmeshes.remesh(co,loops,sizes,target_faces=faces_arg,target_edge=edge_arg,feature_angle=st.feature_angle,smooth_iterations=max(st.smooth_iterations,1),dominant=not st.pure_quad,exe=engine_path(),progress=report_progress,)
			else:
				raise RuntimeError(f"未知引擎 {st.backend!r}")
		except Exception as exc:
			traceback.print_exc()
			GR(self,"ERROR",f"QuadRemesh failed: {exc}")
			return {"CANCELLED"}
		finally:
			pass
		Vo=result["V"]
		faces=result["faces"]
		log=result["log"]
		new_mesh=bpy.data.meshes.new(me.name + "_S-Remesh")
		new_mesh.from_pydata([tuple(v) for v in Vo],[],faces)
		new_mesh.update()
		new_mesh.validate(verbose=False)
		patched=close_engine_holes(new_mesh,me)
		wm.progress_end()
		try:
			context.workspace.status_text_set(None)
		except Exception:
			pass
		if spread:
			spread_pending=(new_mesh,st.target_faces)
		else:
			spread_pending=None
		thin_min,thin_d=thin_shell_limit(me)
		if thin_min and len(new_mesh.polygons) < thin_min * 0.9:
			GR(self,"WARNING",f"thin parts of this model need about {thin_min:,} faces to " f"stay separate - below that the cloth and other thin sheets " f"fuse to themselves")
		try:
			from .lines_preview import keep_materials,keep_uvs
		except ImportError:
			keep_materials=keep_uvs=None
		if keep_materials is not None:
			keep_materials(me,new_mesh)
		if st.replace:
			old=obj.data
			obj.data=new_mesh
			old.use_fake_user=True
			obj[QUADREMESH_ORIG]=old.name
			target=obj
			try:
				from .lines_preview import mute_topology_mods
				off=mute_topology_mods(obj)
				if off:
					GR(self,"INFO","switched off " + ", ".join(off) + " so they do not undo the remesh")
			except ImportError:
				pass
			if keep_uvs is not None:
				keep_uvs(target,old)
		else:
			target=next((o for o in bpy.data.objects
						   if o.get(self.SOURCE_KEY)==obj.name
						   and o.get(QUADREMESH_KIND)== "organic" and o.type== "MESH"),None)
			if target is not None:
				old=target.data
				target.data=new_mesh
				if old.users==0 and not old.use_fake_user:
					bpy.data.meshes.remove(old)
			else:
				target=bpy.data.objects.new(obj.name + "_S-Remesh",new_mesh)
				for coll in obj.users_collection:
					coll.objects.link(target)
			target[self.SOURCE_KEY]=obj.name
			if keep_uvs is not None:
				keep_uvs(target,me)
			target[QUADREMESH_KIND]= "organic"
			target.matrix_world=obj.matrix_world.copy()
			for o in list(context.selected_objects):
				o.select_set(False)
			target.select_set(True)
			context.view_layer.objects.active=target
		o=log["output"]
		msg=(f"{o['faces']} faces ({o['quads']} quad / {o['tris']} tri / " f"{o['ngons']} ngon,{o['quad_ratio']:.0%} quads) in " f"{log['seconds']:.1f}s")
		if st.backend== "AUTO":
			msg +=(f" | crease {log['crease_used']:.0f}deg"
					f" ({log['analysis']['kind']})" f",score {log['final_score']}")
			for line in log["attempts"]:
				print("QuadRemesh attempt:",line)
		GR(self,"INFO",msg)
		if spread_pending is not None:
			bpy.ops.mesh.quadremesh_spread("INVOKE_DEFAULT",mesh_name=spread_pending[0].name,target=spread_pending[1])
		return {"FINISHED"}
def _drop_clean_snapshots(obj):
	for key in ("quadremesh_clean_orig", "quadremesh_clean_base","四边形_拖放_装配"):
		name=obj.get(key)
		if not name:
			continue
		del obj[key]
		mesh=bpy.data.meshes.get(name)
		if mesh is not None:
			mesh.use_fake_user=False
			if mesh.users==0:
				bpy.data.meshes.remove(mesh)
class QUADREMESH_OT_reset_all(Operator):
	"""把整个文件放回原处：每次重构和每次清理。
	每一步按钮都会撤消一事情，这在工作时是右的，但
	当答案是"重新开始，重新开始". This walks every object the
	add-on has marked and undoes all of it in one go.
	"""
	bl_idname= "mesh.quadremesh_reset_all";bl_label=g("Reset Everything");bl_description=("撤消此文件中的每个重构和每个清理，在\n 全部对象，并删除结果对象");bl_options={"REGISTER", "UNDO"}
	@classmethod
	def poll(cls,context):
		return any(o.type== "MESH" and (QUADREMESH_ORIG in o or QUADREMESH_SOURCE in o
					   or o.get("quadremesh_clean_base")) for o in bpy.data.objects)
	def invoke(self,context,event):
		return context.window_manager.invoke_confirm(self,event)
	def execute(self,context):
		if context.active_object is not None and context.active_object.mode== "EDIT":
			bpy.ops.object.mode_set(mode="OBJECT")
		restored=deleted=cleaned=0
		for obj in list(bpy.data.objects):
			if obj.type != "MESH":
				continue
			base=(bpy.data.meshes.get(obj.get("quadremesh_drop_orig") or "")
					or bpy.data.meshes.get(obj.get("quadremesh_clean_base") or ""))
			if base is not None and QUADREMESH_ORIG not in obj:
				bm=bmesh.new()
				bm.from_mesh(base)
				bm.to_mesh(obj.data)
				bm.free()
				obj.data.update()
				cleaned +=1
			_drop_clean_snapshots(obj)
		for obj in list(bpy.data.objects):
			if obj.type != "MESH":
				continue
			orig_name=obj.get(QUADREMESH_ORIG)
			if orig_name:
				mesh=bpy.data.meshes.get(orig_name)
				if mesh is not None:
					spent=obj.data
					obj.data=mesh
					mesh.use_fake_user=False
					del obj[QUADREMESH_ORIG]
					if spent.users==0 and not spent.use_fake_user:
						bpy.data.meshes.remove(spent)
					restored +=1
					obj.pop(QUADREMESH_SOURCE,None)
					obj.pop(QUADREMESH_KIND,None)
				continue
			src_name=obj.get(QUADREMESH_SOURCE)
			if src_name:
				src=bpy.data.objects.get(src_name)
				if src is not None:
					src.hide_set(False)
					src.hide_viewport=False
				data=obj.data
				bpy.data.objects.remove(obj,do_unlink=True)
				if data.users==0 and not data.use_fake_user:
					bpy.data.meshes.remove(data)
				deleted +=1
		st=context.scene.quadremesh_lines
		st.source= ""
		st.result= ""
		st.build_info=(f"reset everything  |  {restored} restored, " f"{deleted} results removed,{cleaned} uncleaned")
		GR(self,"INFO",st.build_info)
		return {"FINISHED"}
class QUADREMESH_OT_restore(Operator):
	bl_idname= "mesh.quadremesh_restore";bl_label= g("Restore Original");bl_description=("将所选结果放回原样。工程\n 在这个附加组件所做的任何事情上：结果对象是\n 删除并取消隐藏其源，以及 " "replaced in place gets its original geometry back");bl_options={"REGISTER", "UNDO"}
	@classmethod
	def _targets(cls,o):
		if o.type != "MESH":
			return []
		if QUADREMESH_ORIG in o or QUADREMESH_SOURCE in o:
			return [o]
		return [x for x in bpy.data.objects if x.type== "MESH" and x.get(QUADREMESH_SOURCE)==o.name]
	@classmethod
	def poll(cls,context):
		return any(cls._targets(o) for o in context.selected_objects)
	def execute(self,context):
		restored,deleted,missing=0,0,[]
		work,seen=[],set()
		for picked in list(context.selected_objects):
			for t in self._targets(picked):
				if t.name not in seen:
					seen.add(t.name)
					work.append(t)
		for obj in work:
			_drop_clean_snapshots(obj)
			orig_name=obj.get(QUADREMESH_ORIG)
			if orig_name:
				mesh=bpy.data.meshes.get(orig_name)
				if mesh is None:
					missing.append(obj.name)
					continue
				spent=obj.data
				obj.data=mesh
				mesh.use_fake_user=False
				del obj[QUADREMESH_ORIG]
				if spent.users==0 and not spent.use_fake_user:
					bpy.data.meshes.remove(spent)
				restored +=1
				continue
			src=bpy.data.objects.get(obj.get(QUADREMESH_SOURCE, ""))
			if src is None:
				missing.append(obj.name)
				continue
			src_name=src.name
			obj_name=obj.name
			for extra in (src_name + "_FEATURELINES",src_name + "_PANELS"):
				e=bpy.data.objects.get(extra)
				if e is not None:
					d=e.data
					bpy.data.objects.remove(e)
					if d and d.users==0:
						try:
							bpy.data.meshes.remove(d)
						except Exception:
							pass
			obj=bpy.data.objects.get(obj_name)
			if obj is not None:
				d=obj.data
				bpy.data.objects.remove(obj)
				if d and d.users==0 and not d.use_fake_user:
					bpy.data.meshes.remove(d)
			src=bpy.data.objects.get(src_name)
			if src is not None:
				if src_name in context.view_layer.objects:
					src.hide_set(False)
				src.select_set(True)
				context.view_layer.objects.active=src
			deleted +=1
		if missing:
			GR(self,{"WARNING"},
						f"no original recorded for: {', '.join(missing[:3])}")
		if not (restored or deleted):
			return {"CANCELLED"}
		GR(self,"INFO",f"restored {restored} in place,removed {deleted} result"
					+ ("s" if deleted !=1 else ""))
		return {"FINISHED"}
class QUADREMESH_PT_panel(Panel):
	bl_idname="QUADREMESH_PT_panel";bl_label= "";bl_space_type= "VIEW_3D";bl_region_type="UI";bl_category=TB;bl_parent_id="SMART_REMESH_PT_M";bl_order=10
	def draw_header(S,_):GL(S.layout,"Smart Remesh (Organic)")
	def draw(self,context):
		layout=self.layout
		st=context.scene.quadremesh
		obj=context.active_object
		engine=True
		blocked=engine_blocked()
		if blocked:
			box=layout.box()
			GL(box,"Organic engine is blocked by macOS",icon="ERROR")
			col=box.column(align=True)
			GL(col,"The engine is here but macOS will not let it")
			GL(col,"start,because it carries no Apple signature.")
			GL(col,"One click clears that; it will show you the")
			GL(col,"command first.")
			col.separator()
			GO(col,"mesh.quadremesh_unquarantine",text="Allow Organic Engine",icon="UNLOCKED")
			engine=False
		elif engine_exe() is None:
			box=layout.box()
			GL(box,"Running the in-house engine",icon="INFO")
			col=box.column(align=True)
			GL(col,"The faster engine ships with the Windows,")
			GL(col,"macOS and Linux downloads. This copy does")
			GL(col,"not have it - either the wrong package was")
			GL(col,"installed for this machine,or bin/ is")
			GL(col,"missing. Get the build for your platform")
			GL(col,"from the Instant Meshes project page and")
			GL(col,"set its path in")
			GL(col,"Preferences ▸ Add-ons ▸ Smart Remesh.")
			col.separator()
			GL(col,"Until then output is rougher: fewer quads,")
			GL(col,"and some non-manifold edges.")
			GL(col,"Smart Remesh (Hardsurface) below is")
			GL(col,"unaffected and works everywhere.")
			col.separator()
			GO(col,"preferences.addon_show",text="Open Add-on Preferences",icon="PREFERENCES").module=__package__
		row=layout.row(align=True)
		row.scale_y=1.5
		row.enabled=engine
		GO(row,"mesh.quadremesh_run",text="Remesh (Organic)",icon="MOD_REMESH")
		row.operator("mesh.quadremesh_restore",text="",icon="LOOP_BACK")
		layout.prop(st, "backend",text="")
		col=layout.column(align=True)
		GE(col,st,"mode")
		if st.mode== "FACES":
			GP(col,st, "target_faces",text="Faces")
		else:
			GP(col,st, "target_edge",text="Edge Length")
		layout.separator()
		col=layout.column(align=True)
		if st.backend== "AUTO":
			box=layout.box()
			GP(box,st, "auto_crease",text="Detect Crease Angle")
			if not st.auto_crease:
				GP(box,st, "feature_angle",text="Sharp Angle")
			GP(box,st, "auto_calibrate",text="Calibrate Face Count")
			GP(box,st, "auto_search",text="Search Settings")
			GP(box,st, "smooth_iterations",text="Reprojection Steps")
			n_runs=(1 if st.auto_calibrate else 0) + (4 if st.auto_search else 1)
			GL(box,f"{n_runs} engine runs",icon="TIME")
		else:
			GP(col,st, "feature_angle",text="Sharp Angle")
		if st.backend== "STABLE":
			GP(col,st, "pure_quad",text="Pure Quads")
			box=layout.box()
			GP(box,st, "smooth_iterations",text="Reprojection Steps")
		if st.backend== "OURS":
			GP(col,st, "use_curvature",text="Follow Curvature")
			box=layout.box()
			GP(box,st, "adaptive",text="Adaptive Density")
			if st.adaptive:
				sub=box.column(align=True)
				GP(sub,st, "inner_density",text="Inner Edges")
				GP(sub,st, "outer_density",text="Outer Edges")
				sub.separator()
				GP(sub,st, "feature_density",text="Near Creases")
				GP(sub,st, "curvature_density",text="By Curvature")
				sub.separator()
				GP(sub,st, "spread_over",text="Build Over")
				GP(sub,st, "thin_density",text="Thin Parts")
				GP(sub,st, "min_size_ratio",text="Min Size")
				GP(sub,st, "gradient_limit",text="Transition")
				GL(box,"Costs ~10 pts of quad quality",icon="INFO")
			box=layout.box()
			GL(box,"Solver",icon="SETTINGS")
			GP(box,st, "orient_iterations",text="Orientation Steps")
			GP(box,st, "position_iterations",text="Position Steps")
			GP(box,st, "smooth_iterations",text="Relax")
			GL(box,"Expect non-manifold edges",icon="ERROR")
		layout.separator()
		GP(layout,st, "replace",text="Replace Original")
		lines=getattr(context.scene, "quadremesh_lines",None)
		if lines is not None:
			box=layout.box()
			GL(box,"UV",icon="UV")
			GP(box,lines, "uv_keep_islands",text="Bake Into Existing UV")
			GP(box,lines, "uv_show_seams",text="Show UV Seams")
			GP(box,lines, "uv_seams_sharp",text="Seams As Sharp")
			box.separator()
			rbk=box.row(align=True)
			GO(rbk,"mesh.quadremesh_bake_from_original",text="Bake From Original",icon="RENDER_STILL")
			rbk.operator("mesh.quadremesh_unbake",text="",icon="LOOP_BACK")
			rb=box.row(align=True)
			rb.prop(lines, "bake_size",text="")
			GP(rb,lines, "bake_pbr",toggle=True)
			GL(box,"If the UV is stretched after a remesh,bake it.",icon="INFO")
		if obj and obj.type== "MESH":
			n=len(obj.data.polygons)
			info=layout.column(align=True)
			GL(info,f"Input: {n:,} faces")
class QUADREMESH_PT_tips(Panel):
	bl_idname="QUADREMESH_PT_tips";bl_label= "";bl_space_type= "VIEW_3D";bl_region_type="UI";bl_category=TB;bl_parent_id="SMART_REMESH_PT_M";bl_options={"DEFAULT_CLOSED"};bl_order=30;bl_options={"DEFAULT_CLOSED"}
	def draw_header(S,_):GL(S.layout,"Tips")
	def draw(self,context):
		layout=self.layout
		col=layout.column(align=True)
		GL(col,"Hover to read a setting.Rest the mouse on any button,checkbox or number for a moment and its full description appears. Every setting carries one,including the numbers it was measured at on real models - so the tooltip tells you what the value does,not just its name.",icon="INFO")
class QUADREMESH_PT_about(Panel):
	bl_idname="QUADREMESH_PT_about";bl_label= "";bl_space_type= "VIEW_3D";bl_region_type="UI";bl_category=TB;bl_parent_id="SMART_REMESH_PT_M";bl_order=40;bl_options={"DEFAULT_CLOSED"}
	def draw_header(S,_):GL(S.layout,"About")
	def draw(self,context):
		layout=self.layout
		col=layout.column(align=True)
		GL(col,"Smart Remesh  v" + VERSION_TEXT)
		GL(col,"Milad Kambari - 3DRedbox Studio")
		layout.separator()
		links=layout.column(align=True)
		links.scale_y=1.2
		GO(links,"wm.url_open",text="ArtStation",icon="URL").url=ARTSTATION_URL
		GO(links,"wm.url_open",text="Superhive",icon="URL").url=SUPERHIVE_URL
		GO(links,"wm.url_open",text="Discord - Support",icon="URL").url=DISCORD_URL
class SMART_REMESH_PT_M(bpy.types.Panel):
	bl_idname="SMART_REMESH_PT_M";bl_label=BT;bl_category=TB;bl_space_type='VIEW_3D';bl_region_type='UI';bl_options={"DEFAULT_CLOSED"}
	def draw_header_preset(S,_):L=S.layout;DHP(S,_,L)
	def draw_header(S,_):DIC(S,_)
	def draw(S,_):L=S.layout;DH(S,_,L)

CLASSES=(SmartRemeshPrefs,SMART_REMESH_PT_M,QuadRemeshSettings,QUADREMESH_OT_run,QUADREMESH_OT_spread,QUADREMESH_OT_unquarantine,QUADREMESH_OT_restore,QUADREMESH_OT_reset_all,QUADREMESH_PT_panel,QUADREMESH_PT_tips,QUADREMESH_PT_about)
def register():
	RCL(CLASSES)
	SAF(setattr,bpy.types.Scene,'quadremesh',bpy.props.PointerProperty(type=QuadRemeshSettings))
	lines_preview.register()
def unregister():
	try:
		lines_preview.unregister()
	except Exception:
		pass
	if hasattr(bpy.types.Scene, "quadremesh"):
		DAS("quadremesh","Scene")
	for cls in reversed(CLASSES):
		try:
			UCL(cls)
		except Exception:
			pass
if __name__== "__main__":
	register()
