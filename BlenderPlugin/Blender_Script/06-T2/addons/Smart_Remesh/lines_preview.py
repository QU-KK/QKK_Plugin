from __future__ import annotations
from .G import *
"""Live feature-line preview with hand-adjustable thresholds.
The expensive part of detection is cached per mesh,so dragging a slider only
re-applies the thresholds and rebuilds the line object - fast enough to watch
the lines move while you drag.
"""
import json,math
from mathutils.geometry import intersect_point_line
import os
from collections import defaultdict
import numpy as np,bpy,bmesh
from mathutils import Vector
from mathutils.bvhtree import BVHTree
from bpy.props import (BoolProperty,EnumProperty,FloatProperty,StringProperty,IntProperty)
from bpy.types import Operator,Panel,PropertyGroup
from .core import hardsurface as HS,prune as PR,panelize as PZ
_CACHE: dict={}
SUFFIX= "_FEATURELINES"
_suspend=0
class suspend_live:
	"""批将多个属性写入一重构."""
	def __enter__(self):
		global _suspend
		_suspend +=1
		return self
	def __exit__(self,*exc):
		global _suspend
		_suspend=max(0,_suspend - 1)
		return False
def _straight_loops(bm,tol_world,protect=None):
	def step(e,v):
		if len(v.link_edges) !=4:
			return None,None
		ef=set(e.link_faces)
		cand=[x for x in v.link_edges if x is not e and not (set(x.link_faces) & ef)]
		if len(cand) !=1:
			return None,None
		return cand[0],cand[0].other_vert(v)
	def cost(v,loop_edges):
		side=[e for e in v.link_edges if e not in loop_edges]
		if len(side) !=2:
			return None
		a=side[0].other_vert(v)
		b=side[1].other_vert(v)
		ab=b.co - a.co
		L=ab.length
		if L < 1e-12:
			return None
		t=max(0.0,min(1.0,(v.co - a.co).dot(ab) / (L * L)))
		return (v.co - (a.co + ab * t)).length
	seen,out,blocked=set(),[],set()
	for e0 in bm.edges:
		if e0.index in seen or len(e0.link_faces) !=2:
			continue
		chain,verts=[e0],set(e0.verts)
		seen.add(e0.index)
		closed=False
		for start in (e0.verts[0],e0.verts[1]):
			e,v=e0,start
			while True:
				e,v=step(e,v)
				if e is None:
					break
				if e is e0:
					closed=True
					break
				if e.index in seen:
					break
				seen.add(e.index)
				chain.append(e)
				verts.update(e.verts)
			if closed:
				break
		eset=set(chain)
		ok=all(v.index not in blocked for v in verts)
		if ok and protect is not None:
			if any(e[protect] for e in chain):
				ok=False
			else:
				for v in verts:
					ue=[x for x in v.link_edges if x[protect]]
					if not ue:
						continue
					if len(ue)==2:
						a=ue[0].other_vert(v).co - v.co
						b=ue[1].other_vert(v).co - v.co
						if a.length > 1e-12 and b.length > 1e-12                                 and a.angle(b) >=math.radians(179.0):
							continue
					ok=False
					break
		if ok:
			for v in verts:
				c=cost(v,eset)
				if c is None or c >=tol_world:
					ok=False
					break
		if ok:
			out.extend(chain)
			for v in verts:
				blocked.add(v.index)
				for e in v.link_edges:
					if e not in eset:
						blocked.add(e.other_vert(v).index)
	return out
def _refit_circles(bm,src_obj):
	from mathutils.bvhtree import BVHTree
	me=source_mesh(src_obj)
	verts=[Vector(v.co) for v in me.vertices]
	tris=[]
	for p in me.polygons:
		idx=list(p.vertices)
		for j in range(1,len(idx) - 1):
			tris.append((idx[0],idx[j],idx[j + 1]))
	bvh=BVHTree.FromPolygons(verts,tris,all_triangles=True)
	acc={}
	for f in bm.faces:
		if len(f.verts) > 4:
			continue
		c=f.calc_center_median()
		loc,nor,_i,dist=bvh.find_nearest(c)
		if loc is None or dist is None or dist <=0.0:
			continue
		span=f.calc_perimeter() / max(len(f.verts),1)
		if span <=0.0 or dist > 0.25 * span:
			continue          # too far to be this face's own chord error
		off=(loc - c) * 0.5
		for v in f.verts:
			a=acc.get(v.index)
			acc[v.index]=(off.copy(),1) if a is None else (a[0] + off,a[1] + 1)
	moved=0
	for v in bm.verts:
		a=acc.get(v.index)
		if a is None:
			continue
		d=a[0] / a[1]
		if d.length > 1e-9:
			v.co=v.co + d
			moved +=1
	return moved
PZ_DROP_KEY= "quadremesh_drop_orig"
PZ_FIRST_KEY= "quadremesh_drop_first"
PZ_ORIG_KEY= "quadremesh_clean_orig"
PZ_BASE_KEY= "quadremesh_clean_base"
def _remember_base(obj,mesh):
	if obj.get(PZ_BASE_KEY) and bpy.data.meshes.get(obj[PZ_BASE_KEY]):
		return
	base=mesh.copy()
	base.name=mesh.name + "_cleanbase"
	base.use_fake_user=True
	obj[PZ_BASE_KEY]=base.name
def _clean_apply(obj,st):
	stash=bpy.data.meshes.get(obj.get(PZ_ORIG_KEY) or "")
	if stash is None:
		return None
	editing=obj.mode== "EDIT"
	if editing:
		bm=bmesh.from_edit_mesh(obj.data)
		bm.clear()
		bm.from_mesh(stash)
	else:
		bm=bmesh.new()
		bm.from_mesh(stash)
	bm.edges.ensure_lookup_table()
	bm.faces.ensure_lookup_table()
	PZ.tag_marked(bm)
	region_edges=PZ.enclosed_interior(bm,require_selected=True)
	doomed=PZ.thin_out(region_edges,st.pz_amount)
	limit=set(region_edges) if st.pz_confine else None
	before=len(bm.faces)
	if doomed:
		PZ.dissolve_keeping_rims(bm,doomed,region=PZ.region_faces(bm),polish=True)
	bm.normal_update()
	PZ.heal_stubs(bm,confine=limit)
	PZ.polish_verts(bm)
	if editing:
		after=len(bm.faces)
		bmesh.update_edit_mesh(obj.data,loop_triangles=True,destructive=True)
	else:
		bm.to_mesh(obj.data)
		after=len(obj.data.polygons)
		bm.free()
		obj.data.update()
	return before,after
def _pz_live(self,context):
	if _suspend:
		return
	obj=context.active_object
	if obj is None or obj.type != "MESH":
		return
	if not obj.get(PZ_ORIG_KEY):
		if obj.mode== "EDIT":
			live=bmesh.from_edit_mesh(obj.data)
			if not any(e.select for e in live.edges):
				return
			stash=bpy.data.meshes.new(obj.data.name + "_preclean")
			live.to_mesh(stash)
			_remember_base(obj,stash)
		else:
			if not any(e.select for e in obj.data.edges):
				return
			stash=obj.data.copy()
			stash.name=obj.data.name + "_preclean"
			_remember_base(obj,stash)
		stash.use_fake_user=True
		obj[PZ_ORIG_KEY]=stash.name
	res=_clean_apply(obj,self)
	if res:
		self.build_info=f"{res[0]} -> {res[1]} faces  |  {self.pz_amount:.0f}%"
def _shade_from(obj,base):
	if base is None or len(base.polygons)==0:
		return
	src=bpy.data.objects.new("qr_shade_src",base)
	bpy.context.scene.collection.objects.link(src)
	src.matrix_world=obj.matrix_world.copy()
	try:
		with bpy.context.temp_override(object=src,active_object=src,
				selected_editable_objects=[src,obj]):
			bpy.ops.object.data_transfer(data_type="CUSTOM_NORMAL",loop_mapping="NEAREST_POLYNOR",use_create=True)
	finally:
		bpy.data.objects.remove(src,do_unlink=True)
	me=obj.data
	sharp_verts=set()
	for e in me.edges:
		if e.use_edge_sharp:
			sharp_verts.update(e.vertices)
	acc={}
	for l in me.loops:
		acc.setdefault(l.vertex_index,[]).append(l.normal.copy())
	avg={v: sum(ns,Vector()).normalized() for v,ns in acc.items()}
	me.normals_split_custom_set([l.normal if l.vertex_index in sharp_verts else avg[l.vertex_index] for l in me.loops])
def _drop_apply(obj,st):
	base=bpy.data.meshes.get(obj.get(PZ_DROP_KEY) or "")
	if base is None:
		return None
	editing=obj.mode== "EDIT"
	if editing:
		bm=bmesh.from_edit_mesh(obj.data)
		bm.clear()
		bm.from_mesh(base)
	else:
		bm=bmesh.new()
		bm.from_mesh(base)
	bm.edges.ensure_lookup_table()
	bm.faces.ensure_lookup_table()
	PZ.tag_marked(bm)
	before=len(bm.faces)
	dropped=partial=0
	if st.pz_every >=1:
		doomed,n2=PZ.thin_every(bm,st.pz_every,keep_marked=st.pz_keep_marked,axes=(st.pz_axis_x,st.pz_axis_y,st.pz_axis_z))
		if doomed:
			PZ.dissolve_keeping_rims(bm,doomed,polish=True)
			PZ.heal_stubs(bm)
			PZ.polish_verts(bm)
			dropped +=n2
	if st.pz_useless > 0.0:
		n1,partial=PZ.drop_loops(bm,tol_deg=st.pz_useless,keep_marked=st.pz_keep_marked,sag_pct=0.0,axes=(st.pz_axis_x,st.pz_axis_y,st.pz_axis_z))
		dropped +=n1
	PZ.polish_verts(bm)
	if editing:
		after=len(bm.faces)
		bmesh.update_edit_mesh(obj.data,loop_triangles=True,destructive=True)
	else:
		bm.to_mesh(obj.data)
		after=len(obj.data.polygons)
		bm.free()
		obj.data.update()
		_shade_from(obj,base)
	return before,after,dropped
def _drop_live(self,context):
	if _suspend:
		return
	obj=context.active_object
	if obj is None or obj.type != "MESH":
		return
	if not obj.get(PZ_DROP_KEY):
		if obj.mode== "EDIT":
			live=bmesh.from_edit_mesh(obj.data)
			base=bpy.data.meshes.new(obj.data.name + "_predrop")
			live.to_mesh(base)
		else:
			base=obj.data.copy()
			base.name=obj.data.name + "_predrop"
		base.use_fake_user=True
		obj[PZ_DROP_KEY]=base.name
		if not obj.get(PZ_FIRST_KEY):
			first=base.copy()
			first.name=obj.data.name + "_dropstart"
			first.use_fake_user=True
			obj[PZ_FIRST_KEY]=first.name
	res=_drop_apply(obj,self)
	if res:
		self.build_info=(f"{res[2]} loops dropped  |  " f"{res[0]} -> {res[1]} faces")
def marked_mask(obj,cache):
	src=source_mesh(obj)
	E=cache["edges"]
	lookup={}
	for i,(a,b) in enumerate(E.tolist()):
		lookup[(a,b) if a < b else (b,a)]=i
	out=np.zeros(len(E),dtype=bool)
	n=0
	for e in src.edges:
		if not (e.use_edge_sharp or e.select):
			continue
		a,b=e.vertices
		i=lookup.get((a,b) if a < b else (b,a))
		if i is not None:
			out[i]=True
			n +=1
	return out,n
def uv_seam_mask(obj,cache):
	src=source_mesh(obj)
	if not src.uv_layers or not len(src.polygons):
		return None
	layer=next((l for l in src.uv_layers if l.active_render),src.uv_layers[0])
	nl=len(src.loops)
	uv=np.empty(nl * 2,dtype=np.float32)
	layer.data.foreach_get("uv",uv)
	uv=uv.reshape(nl,2)
	lvert=np.empty(nl,dtype=np.int32)
	src.loops.foreach_get("vertex_index",lvert)
	nf=len(src.polygons)
	lstart=np.empty(nf,dtype=np.int32)
	src.polygons.foreach_get("loop_start",lstart)
	ltotal=np.empty(nf,dtype=np.int32)
	src.polygons.foreach_get("loop_total",ltotal)
	nxt=np.arange(nl,dtype=np.int32) + 1
	nxt[lstart + ltotal - 1]=lstart
	va=lvert
	vb=lvert[nxt]
	lo=np.minimum(va,vb)
	hi=np.maximum(va,vb)
	order=np.lexsort((hi,lo))
	lo_s,hi_s=lo[order],hi[order]
	pair=np.zeros(len(order),dtype=bool)
	same=(lo_s[1:]==lo_s[:-1]) & (hi_s[1:]==hi_s[:-1])
	pair[:-1] |=same
	pair[1:] |=same
	ia=order[:-1][same]
	ib=order[1:][same]
	ua0,ub0=uv[ia],uv[ib]
	na=uv[nxt[ia]]
	nb=uv[nxt[ib]]
	d1=np.abs(ua0 - nb).max(axis=1)
	d2=np.abs(na - ub0).max(axis=1)
	cut=(d1 > 1e-5) | (d2 > 1e-5)
	pairs_lo=np.concatenate([lo[ia][cut],lo[~pair[np.argsort(order)]]])
	pairs_hi=np.concatenate([hi[ia][cut],hi[~pair[np.argsort(order)]]])
	if not len(pairs_lo):
		return None
	seam_pairs=set(zip(pairs_lo.tolist(),pairs_hi.tolist()))
	E=cache["edges"]
	ea=np.minimum(E[:,0],E[:,1])
	eb=np.maximum(E[:,0],E[:,1])
	out=np.zeros(len(E),dtype=bool)
	for i in range(len(E)):
		if (int(ea[i]),int(eb[i])) in seam_pairs:
			out[i]=True
	return out
def detect(context,cache,st):
	auto_c,auto_f=HS.auto_thresholds(cache)
	crease=auto_c if st.auto_thresholds else st.crease_deg
	flat=auto_f if st.auto_thresholds else st.flat_deg
	mask,info=HS.classify(cache,crease,flat,min_chain=st.min_chain,use_type=st.use_type,close_gaps=st.close_gaps,gap_span=st.gap_span)
	mask=mask | ~cache["man"]
	obj=bpy.data.objects.get(st.source)
	seam_mask=None
	n_marked=0
	marked=None
	if obj is not None and (st.hs_use_marked or st.hs_only_marked):
		marked,n_marked=marked_mask(obj,cache)
		if n_marked:
			if st.hs_only_marked:
				mask=marked | ~cache["man"]
				if seam_mask is not None:
					mask=mask | seam_mask
			else:
				mask=mask | marked
	info=dict(info)
	info["n_marked"]=n_marked
	info["final"]=int(mask.sum())
	plog=None
	if st.auto_prune:
		mask,plog=PR.prune(cache,mask,planar_tol=st.planar_tol,merge=True)
		if n_marked:
			mask=mask | marked
		if seam_mask is not None:
			mask=mask | seam_mask
		info=dict(info)
		info["final"]=int(mask.sum())
	return mask,info,plog,crease,flat,auto_c,auto_f
def _info_line(info,plog,crease,flat,auto_c,auto_f):
	txt=(f"{info['final']} edges  |  {info['n_crease']} crease + "
		   f"{info['n_type']} type  |  {info['open_ends']} open ends  |  "
		   f"{100 * info['panel_pct']:.0f}% of area is flat panel  |  "
		   f"using {crease:.1f} / {flat:.2f}  (auto {auto_c:.1f} / {auto_f:.1f})")
	if info.get("n_marked"):
		txt +=f"  |  {info['n_marked']} of your own lines"
	if plog:
		txt +=(f"  |  pruned {plog['removed']} lines that change nothing "
				f"({plog['regions_before']}->{plog['regions_after']} regions)")
		if plog.get("sliver_merges"):
			txt +=f"  |  welded {plog['sliver_merges']} strips too thin to keep"
	return txt
ORIG_KEY= "quadremesh_orig_mesh"
def source_mesh(obj):
	orig=obj.get(ORIG_KEY)
	if orig:
		me=bpy.data.meshes.get(orig)
		if me is not None:
			return me
	return obj.data
def _mesh_arrays(obj):
	me=source_mesh(obj)
	nv=len(me.vertices)
	V=np.empty(nv * 3)
	me.vertices.foreach_get("co",V)
	V=V.reshape(nv,3)
	fs=np.empty(len(me.polygons),dtype=np.int64)
	me.polygons.foreach_get("loop_total",fs)
	fv=np.empty(int(fs.sum()),dtype=np.int64)
	me.loops.foreach_get("vertex_index",fv)
	return V,fv,fs
def get_cache(obj):
	key=obj.name
	src=source_mesh(obj)
	stamp=(len(src.vertices),len(src.polygons),src.name)
	hit=_CACHE.get(key)
	if hit is not None and hit[0]==stamp:
		return hit[1]
	V,fv,fs=_mesh_arrays(obj)
	starts,edges,pair=HS._topology(V,fv,fs)
	fn,fa=HS._face_normals_areas(V,fv,fs,starts)
	cache=HS.analyse(V,fv,fs,starts,edges,pair,fn,fa)
	_CACHE[key]=(stamp,cache)
	return cache
def rebuild_preview(context,source=None):
	st=context.scene.quadremesh_lines
	obj=source or bpy.data.objects.get(st.source)
	if obj is None or obj.type != "MESH" or not len(obj.data.polygons):
		return None
	cache=get_cache(obj)
	mask,info,plog,crease,flat,auto_c,auto_f=detect(context,cache,st)
	st.info=_info_line(info,plog,crease,flat,auto_c,auto_f)
	V=cache["V"]
	E=cache["edges"][mask]
	name=obj.name + SUFFIX
	old=bpy.data.objects.get(name)
	if old is not None:
		data=old.data
		bpy.data.objects.remove(old)
		if data.users==0:
			bpy.data.meshes.remove(data)
	if not len(E):
		return None
	used=np.unique(E)
	remap=np.full(len(V),-1,dtype=np.int64)
	remap[used]=np.arange(len(used))
	me=bpy.data.meshes.new(name + "_mesh")
	me.from_pydata([tuple(v) for v in V[used].tolist()],[tuple(e) for e in remap[E].tolist()],[])
	me.update()
	out=bpy.data.objects.new(name,me)
	out.matrix_world=obj.matrix_world.copy()
	for coll in obj.users_collection:
		coll.objects.link(out)
	out.show_in_front=True
	out.color=(1.0,0.45,0.05,1.0)
	return out
PANEL_SUFFIX= "_PANELS"
BUILD_SUFFIX= "_S-Remesh"
def rebuild_panels(context,source=None):
	st=context.scene.quadremesh_lines
	obj=source or bpy.data.objects.get(st.source)
	if obj is None or obj.type != "MESH" or not len(obj.data.polygons):
		return None
	cache=get_cache(obj)
	mask,_info,_plog,crease,flat,auto_c,auto_f=detect(context,cache,st)
	A,B,idx=cache["A"],cache["B"],cache["idx"]
	nf,fa=cache["nf"],cache["fa"]
	ds=HS.DisjointSet(nf)
	for e,x,y in zip(idx.tolist(),A.tolist(),B.tolist()):
		if not mask[e]:
			ds.union(x,y)
	root=np.fromiter((ds.find(i) for i in range(nf)),dtype=np.int64,count=nf)
	_,lab=np.unique(root,return_inverse=True)
	nreg=int(lab.max()) + 1
	area=np.bincount(lab,weights=fa)
	total=max(area.sum(),1e-20)
	rng=np.random.default_rng(11)
	pal=rng.random((nreg,3)) * 0.65 + 0.35
	tiny=area < 0.002 * total
	pal[tiny]=(0.16,0.16,0.18)
	me=obj.data
	sizes=np.empty(len(me.polygons),dtype=np.int64)
	me.polygons.foreach_get("loop_total",sizes)
	poly_lab=lab
	name=obj.name + PANEL_SUFFIX
	old=bpy.data.objects.get(name)
	if old is not None:
		d=old.data
		bpy.data.objects.remove(old)
		if d.users==0:
			bpy.data.meshes.remove(d)
	nm=me.copy()
	nm.name=name + "_mesh"
	for a in list(nm.color_attributes):
		nm.color_attributes.remove(a)
	at=nm.color_attributes.new(name="panels",type="FLOAT_COLOR",domain="CORNER")
	cols=np.ones((int(sizes.sum()),4),dtype=np.float32)
	cols[:,:3]=np.repeat(pal[poly_lab],sizes,axis=0)
	at.data.foreach_set("color",cols.ravel())
	nm.attributes.active_color_name= "panels"
	nm.attributes.default_color_name= "panels"
	nm.update()
	out=bpy.data.objects.new(name,nm)
	out.matrix_world=obj.matrix_world.copy()
	for coll in obj.users_collection:
		coll.objects.link(out)
	st.panel_info=(f"{nreg} panels  |  {int(tiny.sum())} tiny  |  "
					 f"largest {100 * float(area.max() / total):.1f}% of area")
	return out
def keep_materials(src_me,dst_me):
	if src_me is None or not src_me.materials:
		return
	dst_me.materials.clear()
	for m in src_me.materials:
		dst_me.materials.append(m)
	if len(src_me.materials) < 2 or not len(src_me.polygons):
		return
	from mathutils.bvhtree import BVHTree
	tree=BVHTree.FromPolygons([v.co[:] for v in src_me.vertices],[p.vertices[:] for p in src_me.polygons])
	for p in dst_me.polygons:
		hit=tree.find_nearest(p.center)
		if hit and hit[2] is not None:
			p.material_index=src_me.polygons[hit[2]].material_index
def _split_on_seams(dst_me,src_me):
	if len(src_me.polygons) > 5000:
		return 0
	uv=src_me.uv_layers[0].data
	cuv={}
	ef={}
	for poly in src_me.polygons:
		for k in range(poly.loop_start,poly.loop_start + poly.loop_total):
			cuv[(poly.index,src_me.loops[k].vertex_index)]=uv[k].uv
		for ek in poly.edge_keys:
			ef.setdefault(ek,[]).append(poly.index)
	segs=[]
	for ek,fs in ef.items():
		seam=len(fs)==1 or (len(fs)==2 and any((cuv[(fs[0],v)] - cuv[(fs[1],v)]).length > 1e-5 for v in ek))
		if seam:
			segs.append((src_me.vertices[ek[0]].co.copy(),src_me.vertices[ek[1]].co.copy()))
	if not segs:
		return 0
	from mathutils.bvhtree import BVHTree
	ext=[max(v.co[i] for v in src_me.vertices) -
		   min(v.co[i] for v in src_me.vertices) for i in range(3)]
	diag=max(ext) or 1.0
	bm=bmesh.new()
	bm.from_mesh(dst_me)
	bm.faces.ensure_lookup_table()
	cuts=0
	if len(segs) > 1200:
		bm.free()
		return 0
	CUT_CAP=300
	tree=BVHTree.FromBMesh(bm)
	for a,b in segs:
		d=b - a
		if d.length < 1e-12:
			continue
		mid=(a + b) / 2
		hit=tree.find_nearest(mid)
		if hit is None or hit[2] is None or hit[3] > diag * 0.005:
			continue
		face=bm.faces[hit[2]]
		if len(face.verts) < 4:
			continue
		on_edge=False
		for e in face.edges:
			_q,t=intersect_point_line(mid,e.verts[0].co,e.verts[1].co)
			t=min(max(t,0.0),1.0)
			if (mid - e.verts[0].co.lerp(e.verts[1].co,t)).length                     < diag * 2e-3:
				on_edge=True
				break
		if on_edge:
			continue
		if abs(d.normalized().dot(face.normal)) > 0.3:
			continue
		no=face.normal.cross(d.normalized())
		if no.length < 1e-9:
			continue
		no.normalize()
		side=[(v.co - mid).dot(no) for v in face.verts]
		thin=diag * 0.01
		if max(side) < thin or min(side) > -thin:
			continue
		geom=[face] + list(face.edges) + list(face.verts)
		res=bmesh.ops.bisect_plane(bm,geom=geom,plane_co=mid,plane_no=no)
		if res["geom_cut"]:
			cuts +=1
			if cuts >=CUT_CAP:
				break
			bm.faces.ensure_lookup_table()
			tree=BVHTree.FromBMesh(bm)
	if cuts:
		bm.to_mesh(dst_me)
		dst_me.update()
	bm.free()
	return cuts
def _fast_uv_transfer(dst_obj,src_me):
	src=bpy.data.objects.new("qr_uv_src",src_me)
	bpy.context.scene.collection.objects.link(src)
	src.matrix_world=dst_obj.matrix_world.copy()
	was=[(m,m.show_viewport) for m in dst_obj.modifiers]
	for m,_ in was:
		m.show_viewport=False
	try:
		with bpy.context.temp_override(object=src,active_object=src,
				selected_editable_objects=[src,dst_obj]):
			bpy.ops.object.data_transfer(data_type="UV",loop_mapping="POLYINTERP_NEAREST",layers_select_src="ALL",layers_select_dst="NAME",use_create=True)
	except Exception:
		pass
	finally:
		for m,on in was:
			m.show_viewport=on
		bpy.data.objects.remove(src,do_unlink=True)
	dst_me=dst_obj.data
	for want in src_me.uv_layers:
		got=dst_me.uv_layers.get(want.name)
		if got is None or len(got.data) !=len(dst_me.loops):
			return False
		if not any(got.data[i].uv.length > 1e-9
				   for i in range(0,len(got.data),29)):
			return False
	for want in src_me.uv_layers:
		got=dst_me.uv_layers.get(want.name)
		if got is not None and want.active_render:
			got.active_render=True
			dst_me.uv_layers.active=got
	return bool(len(src_me.uv_layers))
def _fix_uv_slivers(dst_obj,src_me=None,layer_name=None):
	dst_me=dst_obj.data
	if not dst_me.uv_layers:
		return 0
	fixed=0
	for layer in dst_me.uv_layers:
		if layer_name is not None and layer.name !=layer_name:
			continue
		nl=len(dst_me.loops)
		arr=np.empty(nl * 2,dtype=np.float32)
		layer.data.foreach_get("uv",arr)
		uv=arr.reshape(nl,2)
		changed=False
		for face in dst_me.polygons:
			a=face.loop_start
			b=a + face.loop_total
			block=uv[a:b]
			d=np.linalg.norm(block[:,None,:] - block[None,:,:],axis=2)
			if d.max() <=0.2:
				continue
			counts=(d <=0.2).sum(axis=1)
			home=int(counts.argmax())
			stray=np.flatnonzero(d[home] > 0.2)
			if not len(stray):
				continue
			for k in stray:
				good=np.flatnonzero(d[home] <=0.2)
				near=good[np.argmin(np.linalg.norm(block[good] - block[k],axis=1))]
				uv[a + k]=block[near]
			changed=True
			fixed +=1
		if changed:
			layer.data.foreach_set("uv",uv.reshape(-1))
	if fixed:
		dst_me.update()
	return fixed
def _mend_seam_faces(dst_obj,src_me):
	dst_me=dst_obj.data
	if not (src_me.uv_layers and dst_me.uv_layers):
		return 0
	if len(src_me.uv_layers[0].data) !=len(src_me.loops):
		return 0
	from mathutils.kdtree import KDTree
	nv=len(src_me.vertices)
	sco=np.empty(nv * 3,dtype=np.float32)
	src_me.vertices.foreach_get("co",sco)
	sco=sco.reshape(nv,3)
	kd=KDTree(nv)
	for i in range(nv):
		kd.insert(Vector(sco[i]),i)
	kd.balance()
	reach=float(max(sco.max(axis=0) - sco.min(axis=0))) * 1e-2
	nl=len(src_me.loops)
	slv=np.empty(nl,dtype=np.int32)
	src_me.loops.foreach_get("vertex_index",slv)
	kd_find_range=kd.find_range
	kd_find_n=kd.find_n
	dn=len(dst_me.loops)
	dvi=np.empty(dn,dtype=np.int32)
	dst_me.loops.foreach_get("vertex_index",dvi)
	dnv=len(dst_me.vertices)
	dco=np.empty(dnv * 3,dtype=np.float32)
	dst_me.vertices.foreach_get("co",dco)
	dco=dco.reshape(dnv,3)
	ls=np.empty(len(dst_me.polygons),dtype=np.int32)
	dst_me.polygons.foreach_get("loop_start",ls)
	lt=np.empty(len(dst_me.polygons),dtype=np.int32)
	dst_me.polygons.foreach_get("loop_total",lt)
	fixed=0
	for layer in dst_me.uv_layers:
		src_layer=src_me.uv_layers.get(layer.name) or src_me.uv_layers[0]
		sn=len(src_layer.data)
		sarr=np.empty(sn * 2,dtype=np.float32)
		src_layer.data.foreach_get("uv",sarr)
		sarr=sarr.reshape(sn,2)
		out=np.empty(dn * 2,dtype=np.float32)
		layer.data.foreach_get("uv",out)
		out=out.reshape(dn,2)
		want=set()
		for f in range(len(dst_me.polygons)):
			a0,k0=int(ls[f]),int(lt[f])
			b0=out[a0:a0 + k0]
			if float(np.linalg.norm(b0[:,None,:] - b0[None,:,:],axis=2).max()) <=0.03:
				continue
			for j in range(k0):
				for _c,vi,_d in kd_find_n(Vector(dco[dvi[a0 + j]]),64):
					want.add(vi)
		if not want:
			continue
		choices={}
		for i in range(nl):
			vi=int(slv[i])
			if vi in want:
				choices.setdefault(vi,[]).append(sarr[i])
		torn=[]
		for f in range(len(dst_me.polygons)):
			a,k=int(ls[f]),int(lt[f])
			blk=out[a:a + k]
			if float(np.abs(blk - blk[0]).max()) > 0.03 or                     float(np.linalg.norm(blk[:,None,:] - blk[None,:,:],axis=2).max()) > 0.03:
				torn.append(f)
		changed=False
		pools={}
		for _round in range(6):
			round_fixed=0
			for f in torn:
				a,k=int(ls[f]),int(lt[f])
				blk=out[a:a + k]
				d=np.linalg.norm(blk[:,None,:] - blk[None,:,:],axis=2)
				if d.max() <=0.03:
					continue
				home=int((d <=0.03).sum(axis=1).argmax())
				anchor=blk[home].copy()
				moved=False
				for j in range(k):
					if np.linalg.norm(blk[j] - anchor) <=0.03:
						continue
					li=a + j
					pool=pools.get(li)
					if pool is None:
						co=Vector(dco[dvi[li]])
						pool=[]
						for _c,vi,_d in kd_find_n(co,64):
							pool.extend(choices.get(vi,()))
						pools[li]=pool
					if not pool:
						continue
					best=min(pool,
							   key=lambda u: float(np.linalg.norm(u - anchor)))
					if not np.allclose(best,out[a + j]):
						out[a + j]=best
						moved=True
				if moved:
					round_fixed +=1
			if not round_fixed:
				break
			changed=True
			fixed +=round_fixed
		if changed:
			layer.data.foreach_set("uv",out.reshape(-1))
	if fixed:
		dst_me.update()
	return fixed
def keep_uvs(dst_obj,src_me):
	if src_me is None or not src_me.uv_layers or not len(src_me.polygons):
		return
	if len(src_me.uv_layers[0].data) !=len(src_me.loops):
		return
	dst_me=dst_obj.data
	if not len(dst_me.polygons):
		return
	if len(dst_me.polygons) > 20000 or len(src_me.polygons) > 40000:
		if _fast_uv_transfer(dst_obj,src_me):
			_mend_seam_faces(dst_obj,src_me)
			return
	from mathutils.bvhtree import BVHTree
	if len(dst_me.polygons) <=20000 and len(src_me.polygons) <=20000:
		_split_on_seams(dst_me,src_me)
	verts=[v.co.copy() for v in src_me.vertices]
	polys=[p.vertices[:] for p in src_me.polygons]
	vtuples=[v[:] for v in verts]
	tree=BVHTree.FromPolygons(vtuples,polys)
	layer0=src_me.uv_layers[0].data
	parent=list(range(len(src_me.polygons)))
	def find(x):
		while parent[x] !=x:
			parent[x]=parent[parent[x]]
			x=parent[x]
		return x
	nl=len(src_me.loops)
	uvs=np.empty(nl * 2,dtype=np.float32)
	layer0.foreach_get("uv",uvs)
	uvs=uvs.reshape(nl,2)
	lvert=np.empty(nl,dtype=np.int32)
	src_me.loops.foreach_get("vertex_index",lvert)
	nf=len(src_me.polygons)
	lstart=np.empty(nf,dtype=np.int32)
	src_me.polygons.foreach_get("loop_start",lstart)
	ltotal=np.empty(nf,dtype=np.int32)
	src_me.polygons.foreach_get("loop_total",ltotal)
	face_of_loop=np.repeat(np.arange(nf,dtype=np.int32),ltotal)
	corner_uv={}
	for i in range(nl):
		corner_uv[(int(face_of_loop[i]),int(lvert[i]))]=uvs[i]
	nxt=np.arange(nl,dtype=np.int32) + 1
	ends=lstart + ltotal - 1
	nxt[ends]=lstart
	va=lvert
	vb=lvert[nxt]
	lo=np.minimum(va,vb)
	hi=np.maximum(va,vb)
	order=np.lexsort((hi,lo))
	lo_s=lo[order]
	hi_s=hi[order]
	f_s=face_of_loop[order]
	same=(lo_s[1:]==lo_s[:-1]) & (hi_s[1:]==hi_s[:-1])
	for i in np.flatnonzero(same):
		a=int(f_s[i])
		b=int(f_s[i + 1])
		v0=int(lo_s[i])
		v1=int(hi_s[i])
		ua0=corner_uv.get((a,v0))
		ub0=corner_uv.get((b,v0))
		ua1=corner_uv.get((a,v1))
		ub1=corner_uv.get((b,v1))
		if ua0 is None or ub0 is None or ua1 is None or ub1 is None:
			continue
		if (abs(ua0[0] - ub0[0]) < 1e-5 and abs(ua0[1] - ub0[1]) < 1e-5
				and abs(ua1[0] - ub1[0]) < 1e-5
				and abs(ua1[1] - ub1[1]) < 1e-5):
			parent[find(a)]=find(b)
	island_of=[find(i) for i in range(len(src_me.polygons))]
	members={}
	for i,isl in enumerate(island_of):
		members.setdefault(isl,[]).append(i)
	from mathutils.kdtree import KDTree
	fkd=KDTree(nf)
	centres=np.empty(nf * 3,dtype=np.float32)
	src_me.polygons.foreach_get("center",centres)
	centres=centres.reshape(nf,3)
	areas=np.empty(nf,dtype=np.float32)
	src_me.polygons.foreach_get("area",areas)
	for i in range(nf):
		fkd.insert(centres[i],i)
	fkd.balance()
	edge_hint=math.sqrt(float(areas.mean())) or 1e-6
	def nearest_on(isl,co):
		r=edge_hint * 4.0
		for _try in range(5):
			best=None
			best_d=None
			for _c,fi,d in fkd.find_range(co,r):
				if island_of[fi] !=isl:
					continue
				if best_d is None or d < best_d:
					best_d=d
					best=fi
			if best is not None:
				return best,best_d
			r *=3.0
		return None,None
	def frame(poly):
		idx=list(range(poly.loop_start,poly.loop_start + poly.loop_total))
		cos=[verts[src_me.loops[k].vertex_index] for k in idx]
		best=None
		area=0.0
		for b in range(1,len(idx)):
			for c in range(b + 1,len(idx)):
				ar=(cos[b] - cos[0]).cross(cos[c] - cos[0]).length
				if ar > area:
					area=ar
					best=(idx[0],idx[b],idx[c])
		return best
	frames={}
	from mathutils.kdtree import KDTree
	vkd=KDTree(len(verts))
	for i,v in enumerate(verts):
		vkd.insert(v,i)
	vkd.balance()
	vert_islands={}
	vert_uv_by_island={}
	for i in range(nl):
		vi=int(lvert[i])
		isl=island_of[int(face_of_loop[i])]
		vert_islands.setdefault(vi,set()).add(isl)
		vert_uv_by_island.setdefault((vi,isl),uvs[i])
	dst_me.calc_loop_triangles()
	tris_of={}
	for tri in dst_me.loop_triangles:
		tris_of.setdefault(tri.polygon_index,[]).append(tri)
	ext=[max(v[i] for v in verts) - min(v[i] for v in verts) for i in range(3)]
	vtol=max(ext) * 1e-5 if verts else 0.0
	dn=len(dst_me.loops)
	dvi=np.empty(dn,dtype=np.int32)
	dst_me.loops.foreach_get("vertex_index",dvi)
	dnv=len(dst_me.vertices)
	dco=np.empty(dnv * 3,dtype=np.float32)
	dst_me.vertices.foreach_get("co",dco)
	dco=dco.reshape(dnv,3)
	for layer in src_me.uv_layers:
		dst_layer=(dst_me.uv_layers.get(layer.name)
					 or dst_me.uv_layers.new(name=layer.name))
		sn=len(layer.data)
		sarr=np.empty(sn * 2,dtype=np.float32)
		layer.data.foreach_get("uv",sarr)
		sarr=sarr.reshape(sn,2)
		if len(dst_layer.data) !=dn:
			out=np.zeros(dn * 2,dtype=np.float32)
		else:
			out=np.empty(dn * 2,dtype=np.float32)
			dst_layer.data.foreach_get("uv",out)
		out=out.reshape(dn,2)
		for face in dst_me.polygons:
			cvotes={}
			votes={}
			dist={}
			for tri in tris_of.get(face.index,()):
				pts=[dst_me.vertices[i].co for i in tri.vertices]
				cen=(pts[0] + pts[1] + pts[2]) / 3
				h=tree.find_nearest(cen)
				if not h or h[2] is None:
					continue
				isl=island_of[h[2]]
				votes[isl]=votes.get(isl,0.0) + tri.area
				dist[isl]=min(dist.get(isl,1e30),h[3])
			for k2 in range(face.loop_start,
							face.loop_start + face.loop_total):
				co2=Vector(dco[dvi[k2]])
				for _c,vi,_d in vkd.find_range(co2,vtol):
					for isl in vert_islands.get(vi,()):
						cvotes[isl]=cvotes.get(isl,0) + 1
			if not votes and not cvotes:
				continue
			pool=set(votes) | set(cvotes)
			best=max(pool,key=lambda i: (cvotes.get(i,0),votes.get(i,0.0),-dist.get(i,1e30)))
			for k in range(face.loop_start,
						   face.loop_start + face.loop_total):
				co=Vector(dco[dvi[k]])
				exact=None
				for _c,svi,_d in vkd.find_range(co,vtol):
					exact=vert_uv_by_island.get((svi,best))
					if exact is not None:
						break
				if exact is not None:
					out[k]=exact
					continue
				pi,pd=nearest_on(best,co)
				if pi is None:
					h3=tree.find_nearest(co)
					if not h3 or h3[2] is None:
						continue
					pi=h3[2]
				fr=frames.get(pi)
				if fr is None:
					fr=frames[pi]=frame(src_me.polygons[pi])
				if fr is None:
					continue
				l0,l1,l2=fr
				p0=verts[src_me.loops[l0].vertex_index]
				e1=verts[src_me.loops[l1].vertex_index] - p0
				e2=verts[src_me.loops[l2].vertex_index] - p0
				a11=e1.dot(e1); a12=e1.dot(e2); a22=e2.dot(e2)
				det=a11 * a22 - a12 * a12
				if abs(det) < 1e-18:
					continue
				q=co - p0
				b1=q.dot(e1); b2=q.dot(e2)
				sgm=(b1 * a22 - b2 * a12) / det
				tau=(a11 * b2 - a12 * b1) / det
				u0=sarr[l0]
				out[k]=u0 + (sarr[l1] - u0) * sgm + (sarr[l2] - u0) * tau
		dst_layer.data.foreach_set("uv",out.reshape(-1))
	dst_me.update()
TOPO_MODS={"TRIANGULATE", "DECIMATE", "REMESH", "SUBSURF", "MULTIRES"}
def mute_topology_mods(obj):
	off=[]
	for m in obj.modifiers:
		if m.type in TOPO_MODS and (m.show_viewport or m.show_render):
			m.show_viewport=False
			m.show_render=False
			off.append(m.name)
	return off
def at_same_place(a,b):
	return max((abs(x - y) for ra,rb in zip(a.matrix_world,b.matrix_world)
				for x,y in zip(ra,rb)),default=0.0) <=1e-6
def _cut_faces_across_seams(dst_obj,src_me,rounds=3,tol=0.05):
	total=0
	for _round in range(rounds):
		me=dst_obj.data
		nl=len(me.loops)
		if not me.uv_layers or not nl:
			return total
		uv=np.empty(nl * 2,dtype=np.float32)
		me.uv_layers[0].data.foreach_get("uv",uv)
		uv=uv.reshape(nl,2)
		ls=np.empty(len(me.polygons),dtype=np.int32)
		me.polygons.foreach_get("loop_start",ls)
		lt=np.empty(len(me.polygons),dtype=np.int32)
		me.polygons.foreach_get("loop_total",lt)
		jobs=[]
		for i in range(len(me.polygons)):
			a,k=int(ls[i]),int(lt[i])
			blk=uv[a:a + k]
			d=np.linalg.norm(blk[:,None,:] - blk[None,:,:],axis=2)
			if d.max() <=tol:
				continue
			home=int((d <=tol).sum(axis=1).argmax())
			near=d[home] <=tol
			if near.all():
				continue
			jobs.append((i,near))
		if not jobs:
			return total
		bm=bmesh.new()
		bm.from_mesh(me)
		bm.faces.ensure_lookup_table()
		picked=[]
		for i,near in jobs:
			picked.append((bm.faces[i],near))
		cut=0
		for face,near in picked:
			if not face.is_valid or len(face.verts) < 3:
				continue
			vs=list(face.verts)
			if len(vs) !=len(near):
				continue
			a_pts=[v.co for v,n in zip(vs,near) if n]
			b_pts=[v.co for v,n in zip(vs,near) if not n]
			if not a_pts or not b_pts:
				continue
			ca=sum(a_pts,Vector()) / len(a_pts)
			cb=sum(b_pts,Vector()) / len(b_pts)
			no=cb - ca
			no -=face.normal * no.dot(face.normal)
			if no.length < 1e-12:
				continue
			geom=[face] + list(face.edges) + list(face.verts)
			try:
				bmesh.ops.bisect_plane(bm,geom=geom,plane_co=(ca + cb) / 2,plane_no=no.normalized())
				cut +=1
			except Exception:
				pass
		if not cut:
			bm.free()
			return total
		bm.to_mesh(me)
		bm.free()
		me.update()
		total +=cut
		keep_uvs(dst_obj,src_me)
	return total
MIRROR_AXIS={"X": 0, "Y": 1, "Z": 2}
def detect_symmetry(obj,tol_ratio=0.01):
	from mathutils.kdtree import KDTree
	me=obj.data
	n=len(me.vertices)
	if n < 8:
		return None
	co=np.empty(n * 3,dtype=np.float64)
	me.vertices.foreach_get("co",co)
	co=co.reshape(-1,3)
	size=float(max(co.max(axis=0) - co.min(axis=0)))
	if size <=0:
		return None
	tol=size * tol_ratio
	tree=KDTree(n)
	for i,p in enumerate(co):
		tree.insert(p,i)
	tree.balance()
	step=max(1,n // 2000)
	sample=co[::step]
	best=None
	for name,axis in MIRROR_AXIS.items():
		spread=float(sample[:,axis].max() - sample[:,axis].min())
		if spread < size * 0.05:
			continue
		worst=0.0
		for p in sample:
			q=p.copy()
			q[axis]=-q[axis]
			hit=tree.find(Vector(q))
			if hit is None or hit[0] is None:
				worst=float("inf")
				break
			d=(Vector(q) - hit[0]).length
			if d > worst:
				worst=d
			if worst > tol:
				break
		if worst <=tol and (best is None or worst < best[1]):
			best=(name,worst)
	return best[0] if best else None
def cut_half(obj,axis_name,gap=1e-6):
	import bmesh
	from mathutils import Vector as V3
	axis=MIRROR_AXIS[axis_name]
	me=obj.data.copy()
	me.name=obj.data.name + "_half"
	bm=bmesh.new()
	bm.from_mesh(me)
	no=V3((0.0,0.0,0.0))
	no[axis]=1.0
	bmesh.ops.bisect_plane(bm,geom=list(bm.verts) + list(bm.edges) +
						   list(bm.faces),plane_co=V3((0.0,0.0,0.0)),plane_no=no,clear_inner=True,clear_outer=False)
	size=max(obj.dimensions) or 1.0
	for v in bm.verts:
		if abs(v.co[axis]) < size * 1e-4:
			v.co[axis]=0.0
	bm.to_mesh(me)
	bm.free()
	me.update()
	half=bpy.data.objects.new(obj.name + "_SR_half",me)
	for coll in obj.users_collection:
		coll.objects.link(half)
	half.matrix_world=obj.matrix_world.copy()
	return half
def weld_mirror(obj,axis_name):
	import bmesh
	axis=MIRROR_AXIS[axis_name]
	me=obj.data
	bm=bmesh.new()
	bm.from_mesh(me)
	size=max(obj.dimensions) or 1.0
	for v in bm.verts:
		if abs(v.co[axis]) < size * 1e-4:
			v.co[axis]=0.0
	src=list(bm.verts) + list(bm.edges) + list(bm.faces)
	dup=bmesh.ops.duplicate(bm,geom=src)["geom"]
	verts=[g for g in dup if isinstance(g,bmesh.types.BMVert)]
	faces=[g for g in dup if isinstance(g,bmesh.types.BMFace)]
	for v in verts:
		v.co[axis]=-v.co[axis]
	bmesh.ops.reverse_faces(bm,faces=faces)
	bmesh.ops.remove_doubles(bm,verts=list(bm.verts),dist=size * 1e-4)
	bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces))
	bm.to_mesh(me)
	bm.free()
	me.update()
	return len(me.polygons)
def fold_result(obj,axis_name):
	import bmesh
	axis=MIRROR_AXIS[axis_name]
	me=obj.data
	bm=bmesh.new()
	bm.from_mesh(me)
	if not bm.faces:
		bm.free()
		return len(me.polygons)
	span=0.0
	for e in bm.edges:
		span +=(e.verts[0].co - e.verts[1].co).length
	span /=max(len(bm.edges),1)
	snap=span * 0.35
	for v in bm.verts:
		if abs(v.co[axis]) < snap:
			v.co[axis]=0.0
	no=Vector((0.0,0.0,0.0))
	no[axis]=1.0
	bmesh.ops.bisect_plane(bm,geom=list(bm.verts) + list(bm.edges) +
						   list(bm.faces),plane_co=Vector((0.0,0.0,0.0)),plane_no=no,clear_inner=True,clear_outer=False)
	bm.verts.ensure_lookup_table()
	for v in bm.verts:
		if abs(v.co[axis]) < snap * 0.5:
			v.co[axis]=0.0
	src=list(bm.verts) + list(bm.edges) + list(bm.faces)
	dup=bmesh.ops.duplicate(bm,geom=src)["geom"]
	verts=[g for g in dup if isinstance(g,bmesh.types.BMVert)]
	faces=[g for g in dup if isinstance(g,bmesh.types.BMFace)]
	for v in verts:
		v.co[axis]=-v.co[axis]
	bmesh.ops.reverse_faces(bm,faces=faces)
	bmesh.ops.remove_doubles(bm,verts=list(bm.verts),dist=span * 1e-3)
	bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces))
	bm.to_mesh(me)
	bm.free()
	me.update()
	return len(me.polygons)
def build_panel_mesh(context,source=None,reuse=None):
	import bmesh
	st=context.scene.quadremesh_lines
	obj=source or bpy.data.objects.get(st.source)
	if obj is None or obj.type != "MESH" or not len(obj.data.polygons):
		return None
	cache=get_cache(obj)
	mask,info,plog,crease,flat,auto_c,auto_f=detect(context,cache,st)
	st.info=_info_line(info,plog,crease,flat,auto_c,auto_f)
	pinned=None
	keep_edges=None
	if st.hs_use_marked or st.hs_only_marked:
		marked,n_marked=marked_mask(obj,cache)
		if n_marked:
			keep_edges=marked
	if keep_edges is not None and keep_edges.any():
		pinned=np.zeros(len(cache["V"]),dtype=bool)
		pinned[cache["edges"][keep_edges].ravel()]=True
		marked=keep_edges
	V,faces,rep,lines=HS.panels_to_mesh(cache,mask,straighten=st.straighten,planar_tol=st.planar_tol,pinned=pinned)
	if not len(faces):
		st.build_info= "no closed panel found"
		return None
	diag=float(np.linalg.norm(V.max(0) - V.min(0))) or 1.0
	muted=[]
	name=obj.name + BUILD_SUFFIX
	target=bpy.data.objects.get(reuse) if reuse else None
	if target is None:
		existing=bpy.data.objects.get(name)
		if existing is not None:
			if not at_same_place(existing,obj):
				n=1
				while bpy.data.objects.get(f"{name}.{n:03d}") is not None:
					n +=1
				name=f"{name}.{n:03d}"
			else:
				target=existing
	me=bpy.data.meshes.new(name + "_mesh")
	me.from_pydata([tuple(p) for p in V],[],[list(f) for f in faces])
	me.validate(verbose=False)
	keep_materials(obj.data,me)
	bm=bmesh.new()
	bm.from_mesh(me)
	bmesh.ops.recalc_face_normals(bm,faces=bm.faces)
	bm.faces.ensure_lookup_table()
	kind=bm.faces.layers.int.new("qr_kind")
	group=bm.faces.layers.int.new("qr_panel")
	for f,g in zip(bm.faces,rep["face_panel"]):
		f[group]=g
	for i in rep["bore_faces"]:
		bm.faces[i][kind]=1
	is_line=bm.edges.layers.int.new("qr_line")
	is_user=bm.edges.layers.int.new("qr_user")
	bm.edges.ensure_lookup_table()
	for e in bm.edges:
		a,b=e.verts[0].index,e.verts[1].index
		if (min(a,b),max(a,b)) in lines:
			e[is_line]=1
	segs=[]
	if pinned is not None:
		from mathutils.kdtree import KDTree
		src_V=cache["V"]
		mids=[((src_V[a] + src_V[b]) / 2.0) for a,b in
				cache["edges"][marked].tolist()]
		if mids:
			from mathutils import Vector
			segs=[(Vector(src_V[a].tolist()),Vector(src_V[b].tolist()))
					for a,b in cache["edges"][marked].tolist()]
			kd=KDTree(len(mids))
			for i,m in enumerate(mids):
				kd.insert(m.tolist(),i)
			kd.balance()
			tol=diag * 1e-4
			for e in bm.edges:
				m=(e.verts[0].co + e.verts[1].co) / 2
				for _co,i,_d in kd.find_n(m,6):
					a,b=segs[i]
					_q,t=intersect_point_line(m,a,b)
					t=min(max(t,0.0),1.0)
					if (m - a.lerp(b,t)).length < tol:
						e[is_user]=1
						break
	bmesh.ops.remove_doubles(bm,verts=bm.verts,dist=diag * 1e-5)
	bm.verts.ensure_lookup_table()
	bm.edges.ensure_lookup_table()
	bm.faces.ensure_lookup_table()
	HEAVY=20000
	heavy=len(bm.faces) > HEAVY or len(segs) > 4000
	cut_in=0
	if pinned is not None and segs and not heavy:
		from mathutils.bvhtree import BVHTree
		tree=BVHTree.FromBMesh(bm)
		for a,b in segs:
			mid=(a + b) / 2
			hit=tree.find_nearest(mid)
			if hit is None or hit[2] is None or hit[3] > diag * 0.02:
				continue
			face=bm.faces[hit[2]]
			on_edge=False
			for e in face.edges:
				_q,t=intersect_point_line(mid,e.verts[0].co,e.verts[1].co)
				t=min(max(t,0.0),1.0)
				if (mid - e.verts[0].co.lerp(e.verts[1].co,t)).length                         < diag * 1e-4:
					on_edge=True
					break
			if on_edge:
				continue
			d=(b - a)
			if d.length < 1e-12:
				continue
			no=face.normal.cross(d.normalized())
			if no.length < 1e-9:
				continue
			no.normalize()
			side=[(v.co - mid).dot(no) for v in face.verts]
			thin=diag * 0.01
			if max(side) < thin or min(side) > -thin:
				continue
			geom=[face] + list(face.edges) + list(face.verts)
			res=bmesh.ops.bisect_plane(bm,geom=geom,plane_co=mid,plane_no=no)
			for g in res["geom_cut"]:
				if isinstance(g,bmesh.types.BMEdge):
					g[is_user]=1
					g[is_line]=1
			cut_in +=1
			bm.faces.ensure_lookup_table()
			bm.edges.ensure_lookup_table()
			bm.verts.ensure_lookup_table()
			tree=BVHTree.FromBMesh(bm)
	tri=[f for f in bm.faces if len(f.verts)==3]
	if tri:
		lent=[e for e in bm.edges if (e[is_line] or e[is_user]) and e.smooth]
		for e in lent:
			e.smooth=False
		bmesh.ops.join_triangles(bm,faces=tri,angle_face_threshold=0.9,angle_shape_threshold=1.4,cmp_seam=False,cmp_sharp=True,cmp_uvs=False,cmp_vcols=False,cmp_materials=False)
		for e in lent:
			if e.is_valid:
				e.smooth=True
		bm.faces.ensure_lookup_table()
	dissolved=0
	if st.dissolve_straight > 0.0:
		before_f=len(bm.faces)
		for _pass in range(40):
			sel=_straight_loops(bm,st.dissolve_straight * diag,protect=is_user)
			if not sel:
				break
			bmesh.ops.dissolve_edges(bm,edges=sel,use_verts=True,use_face_split=False)
			bm.faces.ensure_lookup_table()
			bm.edges.ensure_lookup_table()
			bm.verts.ensure_lookup_table()
		dissolved=before_f - len(bm.faces)
	circles=0
	if st.refit_circles and dissolved:
		circles=_refit_circles(bm,obj)
		bm.normal_update()
	cham=0
	got_width=0.0
	beveled=set()
	if st.chamfer > 0.0:
		bm.edges.ensure_lookup_table()
		sel=[e for e in bm.edges if e[is_line]]
		if sel:
			line_len=sum(e.calc_length() for e in sel)
			res=bmesh.ops.bevel(bm,geom=sel,offset=st.chamfer * diag,offset_type="OFFSET",segments=st.chamfer_segments,profile=st.chamfer_profile,affect="EDGES",clamp_overlap=st.chamfer_clamp,miter_outer="ARC",miter_inner="SHARP",loop_slide=True,material=-1)
			beveled=set(res["faces"])
			cham=len(sel)
			band_area=sum(f.calc_area() for f in res["faces"] if f.is_valid)
			if line_len > 0.0:
				got_width=band_area / line_len
			bmesh.ops.recalc_face_normals(bm,faces=bm.faces)
	sup,clamped=0,0
	if st.support > 0.0 and st.support_loops > 0:
		live=defaultdict(list)
		for f in bm.faces:
			if f not in beveled and f[kind]==0:
				live[f[group]].append(f)
		live=list(live.values())
		for _ in range(st.support_loops):
			nxt=[]
			for grp in live:
				grp=[f for f in grp if f.is_valid]
				if not grp:
					continue
				inner_e={e for f in grp for e in f.edges if sum(1 for g in e.link_faces if g in grp) > 1}
				per=sum(e.calc_length() for f in grp for e in f.edges
						  if e not in inner_e) or 1e-12
				area=sum(f.calc_area() for f in grp)
				w=st.support * diag
				cap=0.4 * (2.0 * area / per)
				if w > cap:
					w=cap
					clamped +=1
				if w <=1e-9:
					continue
				res=bmesh.ops.inset_region(bm,faces=grp,use_boundary=True,use_even_offset=True,thickness=w,depth=0.0,use_interpolate=True)
				sup +=1
				band=set(res["faces"])
				keep=[f for f in bm.faces
						if f.is_valid and f not in band and f[group]==grp[0][group]
						and f[kind]==0 and f not in beveled]
				if keep:
					nxt.append(keep)
			live=nxt
		bmesh.ops.recalc_face_normals(bm,faces=bm.faces)
	bmesh.ops.remove_doubles(bm,verts=bm.verts,dist=diag * 1e-5)
	bm.verts.ensure_lookup_table()
	bm.edges.ensure_lookup_table()
	welded=0
	if st.weld_close > 0.0:
		before_v=len(bm.verts)
		limit=st.weld_close * diag
		if got_width > 0.0:
			limit=min(limit,got_width * 0.25)
		bmesh.ops.dissolve_degenerate(bm,dist=limit,edges=bm.edges[:])
		bm.verts.ensure_lookup_table()
		bm.edges.ensure_lookup_table()
		bm.faces.ensure_lookup_table()
		welded=before_v - len(bm.verts)
	bnd=sum(1 for e in bm.edges if len(e.link_faces)==1)
	tris=sum(1 for f in bm.faces if len(f.verts)==3)
	bm.to_mesh(me)
	bm.free()
	me.update()
	if st.hs_replace:
		if ORIG_KEY not in obj:
			obj.data.use_fake_user=True
			obj[ORIG_KEY]=obj.data.name
		obj.data=me
		out=obj
		muted=mute_topology_mods(obj)
	else:
		if ORIG_KEY in obj:
			back=bpy.data.meshes.get(obj[ORIG_KEY])
			if back is not None:
				spent=obj.data
				obj.data=back
				back.use_fake_user=False
				del obj[ORIG_KEY]
				if spent.users==0 and not spent.use_fake_user:
					try:
						bpy.data.meshes.remove(spent)
					except Exception:
						pass
		if target is not None:
			spent=target.data
			target.data=me
			if spent.users==0 and not spent.use_fake_user:
				try:
					bpy.data.meshes.remove(spent)
				except Exception:
					pass
			out=target
		else:
			out=bpy.data.objects.new(name,me)
			out.matrix_world=obj.matrix_world.copy()
			for coll in obj.users_collection:
				coll.objects.link(out)
		out["quadremesh_source"]=obj.name
		out["quadremesh_kind"]= "hardsurface"
	src_data=(bpy.data.meshes.get(obj[ORIG_KEY]) if ORIG_KEY in obj
				else obj.data) if out is obj else obj.data
	keep_uvs(out,src_data)
	st.result=out.name
	st.build_info=(f"{len(me.polygons)} faces  |  {len(me.vertices)} verts  |  "
		f"{rep['holes']} holes cut,{rep['bores']} bores walled  |  "
		f"{rep['kept_curved']} curved regions kept as-is "
		f"({100 * rep['curved_area_pct']:.0f}% of area)  |  "
		f"{rep['dropped']} straight-run verts dropped  |  "
		f"chamfer on {cham} lines"
		+ (f" - asked {st.chamfer:.4f},got {got_width / diag:.4f}"
		   + (" (Clamp Overlap)" if st.chamfer_clamp and got_width / diag < st.chamfer * 0.9 else "")
		   if cham and st.chamfer > 0.0 else "") + "  |  "
		f"{sup} support rings ({clamped} narrowed to fit)  |  "
		f"{bnd} boundary edges  |  {tris} tris"
		+ (f"  |  welded {welded} verts off collapsed chamfer" if welded else "")
		+ (f"  |  switched off {', '.join(muted)}" if muted else ""))
	return out
def build_maybe_mirrored(context,source=None,reuse=None,report=None):
	st=context.scene.quadremesh_lines
	obj=source or bpy.data.objects.get(st.source)
	if obj is None:
		return None
	axis=None
	if st.hs_mirror:
		axis=(st.hs_mirror_axis if st.hs_mirror_axis != "AUTO"
				else detect_symmetry(obj))
		if axis is None and report:
			report({"WARNING"},"Mirror Retopology: this model is not symmetric across any " "axis - built whole instead")
	out=build_panel_mesh(context,obj,reuse=reuse)
	if out is None:
		return None
	st.result=out.name
	if axis is not None:
		n=fold_result(out,axis)
		st.build_info=(f"{st.build_info}  |  mirrored across {axis}, " f"{n:,} faces")
	return out
def _rebuild(self,context):
	st=context.scene.quadremesh_lines
	if _suspend or not st.source or not session_owns(context,st):
		return
	src=bpy.data.objects.get(st.source)
	built=(bpy.data.objects.get(st.result) is not None
			 or (src is not None and ORIG_KEY in src))
	if not built:
		return
	prev=context.view_layer.objects.active
	was_result=prev is not None and prev.name.endswith(BUILD_SUFFIX)
	out=build_maybe_mirrored(context,reuse=st.result)
	if out is not None and was_result:
		for o in list(context.selected_objects):
			o.select_set(False)
		out.select_set(True)
		context.view_layer.objects.active=out
def session_owns(context,st):
	act=context.view_layer.objects.active
	if act is None or not st.source:
		return False
	return act.name in (st.source,st.result,st.source + SUFFIX,st.source + PANEL_SUFFIX)
def _live(self,context):
	st=context.scene.quadremesh_lines
	if _suspend or not st.source or not session_owns(context,st):
		return
	if bpy.data.objects.get(st.source + SUFFIX) is not None:
		rebuild_preview(context)
	if bpy.data.objects.get(st.source + PANEL_SUFFIX) is not None:
		rebuild_panels(context)
	src=bpy.data.objects.get(st.source)
	if (bpy.data.objects.get(st.result) is not None
			or (src is not None and ORIG_KEY in src)):
		_rebuild(self,context)
PRESET_COMMON={"planar_tol": 0.01,"straighten": 0.0002,"chamfer": 0.0,"support": 0.0, "use_type": True,"close_gaps": True,"gap_span": 0.0,"refit_circles": True, "auto_thresholds": False, "weld_close": 0.0002,}
PRESETS={"DETAIL": {"crease_deg": 0.0, "flat_deg": 4.90,"min_chain": 0.0, "dissolve_straight": 0.0015,"auto_prune": True,},"BALANCED": {"crease_deg": 23.0, "flat_deg": 2.00,"min_chain": 1.0, "dissolve_straight": 0.0020,"auto_prune": True,},"FLAT": {"crease_deg": 40.0, "flat_deg": 2.00,"min_chain": 0.1, "dissolve_straight": 0.0010, "auto_prune": False,},}
PRESET_FIELDS=sorted(set(PRESET_COMMON) | set(PRESETS["BALANCED"]))
_USER: dict={}
_ENUM_ITEMS: list=[]
def _user_path():
	d=bpy.utils.user_resource("CONFIG",path="smart_remesh",create=True)
	return os.path.join(d, "presets.json")
def load_user_presets():
	global _USER
	try:
		with open(_user_path(), "r",encoding="utf-8") as fh:
			data=json.load(fh)
		_USER={k: v for k,v in data.items() if isinstance(v,dict)}
	except Exception:
		_USER={}
def save_user_presets():
	try:
		with open(_user_path(), "w",encoding="utf-8") as fh:
			json.dump(_USER,fh,indent=1,sort_keys=True)
		return True
	except Exception as exc:
		print("Smart Remesh: could not write presets:",exc)
		return False
def _preset_items(self,context):
	global _ENUM_ITEMS
	items=[("BALANCED", "Balanced","折痕23，共面2.00，最小长度1.0，回路0.0020。设置\n 八个原型中的四个收敛于"),("DETAIL", "Detail","折痕0，共面4.90，最小长度0，回路0.0015。采取每个" "线段，让共面测试和修剪将它们外面"),("FLAT", "Flat Panels","折痕40，共面2.00，最小长度0.1，循环0.0010，修剪关。" "对于几乎是全部平直面板的模型"),]
	if _USER:
		items.append(None)
		for name in sorted(_USER):
			items.append(("USER:" + name,name, "Saved preset"))
	items.append(None)
	items.append(("CUSTOM", "Custom", "手动设置的值"))
	_ENUM_ITEMS=items
	return _ENUM_ITEMS
def _apply_preset(self,context):
	st=context.scene.quadremesh_lines
	key=st.preset
	if key== "CUSTOM":
		return
	if key.startswith("USER:"):
		values=_USER.get(key[5:])
		if not values:
			return
	else:
		values=dict(PRESET_COMMON)
		values.update(PRESETS[key])
	with suspend_live():
		for k,v in values.items():
			try:
				setattr(st,k,v)
			except Exception:
				pass
	_live(self,context)
class QUADREMESH_OT_preset_save(Operator):
	bl_idname= "mesh.quadremesh_preset_save";bl_label= g("Save Preset");bl_description=("存储当前设置。保存的预设\n 实时在Blender的配置文件夹，所以他们跟踪你 " "between files");bl_options={"REGISTER"}
	def draw(S,_):L=S.layout;[GP(L,S,n) for n in S.__annotations__]
	name: StringProperty(name="Name",default=g("My Preset"))
	def invoke(self,context,event):
		return context.window_manager.invoke_props_dialog(self,width=260)
	def draw(self,context):
		GP(self.layout,self, "name",text="Name")
	def execute(self,context):
		st=context.scene.quadremesh_lines
		nm=self.name.strip()
		if not nm:
			GR(self,"WARNING", "give it a name")
			return {"CANCELLED"}
		_USER[nm]={k: getattr(st,k) for k in PRESET_FIELDS if k in st.bl_rna.properties}
		if not save_user_presets():
			GR(self,"ERROR", "could not write the preset file")
			return {"CANCELLED"}
		st.preset= "USER:" + nm
		GR(self,"INFO",f"saved '{nm}'")
		return {"FINISHED"}
class QUADREMESH_OT_preset_delete(Operator):
	bl_idname= "mesh.quadremesh_preset_delete";bl_label= g("Delete Preset");bl_description= "移除当前选定的已保存预设";bl_options={"REGISTER"}
	@classmethod
	def poll(cls,context):
		return context.scene.quadremesh_lines.preset.startswith("USER:")
	def execute(self,context):
		st=context.scene.quadremesh_lines
		nm=st.preset[5:]
		if nm not in _USER:
			return {"CANCELLED"}
		del _USER[nm]
		save_user_presets()
		st.preset= "CUSTOM"
		GR(self,"INFO",f"deleted '{nm}'")
		return {"FINISHED"}
class QuadRemeshLines(PropertyGroup):
	preset: EnumProperty(name="Preset",items=_preset_items,update=_apply_preset,description="内置预设，然后保存任何内容")
	source: StringProperty(name="Source")
	result: StringProperty(name="Result")
	info: StringProperty(name="Info")
	panel_info: StringProperty(name="Panel Info")
	build_info: StringProperty(name="Build Info")
	panelize_info: StringProperty(name="Panelize Info")
	hs_use_marked: BoolProperty(name="Include My Lines",default=True,update=_live,description="将标记为锐边的边添加到检测器的线条中\n 找到。然后他们会像以前一样进行相同的重构" "其它线段")
	pz_amount: FloatProperty(name="Remove",default=100.0,min=0.0,max=100.0,subtype="PERCENTAGE",update=_pz_live,description="要移除的线内部几何的多少。  \n 100 每个子区域留一面；较低的保留了一些" "栅格，保持最小形状的回路首先")
	pz_merge: FloatProperty(name="Second Pass",default=0.0,min=0.0,max=100.0,subtype="PERCENTAGE",update=_pz_live,description="把剩下的东西再检查一遍，隔其它线段走。  \n 简单而可预测，不像基于角度的合并\n 被替换了，它在栅格上徘徊并折断" "表单。0为关，每个备用线段100个")
	pz_confine: BoolProperty(name="Stay Inside Lines",default=True,update=_pz_live,description="把每一个变化都放在你标记的区域内。关让\n 循环无论在哪里运行，都会跟随它，它整理了端点\n 但可以进入模型的另一部分，即" "相同循环正在成形，并将其拆开")
	pz_useless: FloatProperty(name="Flat Below",default=1.0,min=0.0,max=20.0,update=_drop_live,description="当表面转向较少时，循环没有形状\n 比这许多度还高。总是做循环\n 完整或根本不完整-一将停止中间曲面是" "独自留下来")
	pz_every: IntProperty(name="Remove Per Kept",default=0,min=0,max=10,update=_drop_live,description="对于保持的每个循环，移除这个许多：1取每个\n 其它循环，三分之二离开一，四分之三离开一。0是\n 关。尊重轴勾选，从不接触标记" "lines")
	uv_keep_islands: BoolProperty(name="Bake Into Existing UV",default=False,description="烘焙到模型已有的UV布局上，UDIM\n 瓷砖和全部，而不是重新解包它。仅\n 影响烘焙从原点-重构本身是" "未被触及的")
	uv_show_seams: BoolProperty(name="Show UV Seams",default=False,update=_uv_show_update,description="显示UV映射切割为红色接缝线的边")
	uv_seams_sharp: BoolProperty(name="Seams As Sharp",default=False,update=_uv_sharp_update,description="标记UV缝线锐边-重构保持的蓝线\n - 所以纹理落在重建的面上，没有断裂")
	bake_size: EnumProperty(name="Size",default="2048",items=[("1024", "1024", ""),("2048", "2048", ""),("4096", "4096", "")],description="纹理尺寸用于烘焙从原点")
	bake_pbr: BoolProperty(name="All Maps",default=True,description="烘焙原点的材质驱动器的每个通道\n 纹理-粗糙度，金属度，高度，阿尔法，自发光，\n 那里有什么-所以没有旧材质" "落在后面")
	pz_loop_axis: EnumProperty(name="Cut Along",default="AUTO",items=[("AUTO", "Auto", "从单击的边跟随表面"),("X", "X", "世界上的一条直线切割YZ平面"),("Y", "Y", "世界上的直线切割XZ平面"),("Z", "Z", "世界上的直线切割XY平面")],description="力度边循环方向：自动从\n 点击边缘；X、Y或Z直接穿过" "单击点处的整个模型")
	pz_axis_x: BoolProperty(name="X",default=True,update=_drop_live,description="允许删除沿世界X运行的运行")
	pz_axis_y: BoolProperty(name="Y",default=True,update=_drop_live,description="允许删除沿世界Y运行的运行")
	pz_axis_z: BoolProperty(name="Z",default=True,update=_drop_live,description="允许删除沿世界Z运行的运行")
	pz_keep_marked: BoolProperty(name="Spare My Lines",default=True,update=_drop_live,description="切勿丢弃标记为锐边或已选择的循环")
	hs_only_marked: BoolProperty(name="Only My Lines",default=False,update=_live,description="完全忽略检测器，从你的标记从\n 只有边。仍然保留网格边界，或者" "重构将没有从工作的轮廓")
	pz_use_sharp: BoolProperty(name="Marked Sharp",default=True,description="将标有锐边的边视为面板边界。标记他们进来了\n 带边编辑模式▸ 标记·锐边；他们显示上青色" "并与网格一起保存")
	pz_use_selection: BoolProperty(name="Selected Edges",default=True,description="还将当前边选择视为面板边界。  \n 适用于一次性无标记")
	pz_keep_boundary: BoolProperty(name="Keep Outline",default=True,description="永远不要溶解网格自己的边界。关这个\n 让轮廓折叠")
	pz_keep_creased: BoolProperty(name="Keep Creased",default=True,description="还保持边具有细分折痕")
	pz_keep_seams: BoolProperty(name="Keep UV Seams",default=False,description="同时保持边标记为UV缝线")
	pz_protect: FloatProperty(name="Protect Above",default=0.0,min=0.0,max=180.0,description="保持未标记的边当其两个面弯曲更多时\n 比这个许多度，所以曲率不会被\n 事故。0删除行之间的所有内容，这" "是字面上的行为")
	pz_dissolve_verts: BoolProperty(name="Clean Stray Vertices",default=True,description="还可以在没有附加的情况下放置中间管路左侧的顶点。  \n 无，面板保持顶点的边缘" "什么都不做")
	auto_thresholds: BoolProperty(name="Automatic",default=True,update=_live,description="拾取两个阈值从与大通的模型。关闭关\n 用手放好，看着线移动")
	crease_deg: FloatProperty(name="Crease",default=20.0,min=0.0,max=90.0,soft_min=0.0,soft_max=90.0,step=100,precision=1,update=_live,description="一个弯曲要比它的邻居锋利多少\n 数量为折痕。低值开始标记的面\n 曲面。度量是相对的，因此可以\n 原则上是负向-但0已经占用74k的" "浓缩咖啡机的187k边和-5需要157k，因此" "地板保持在0以停止滑块拖动着陆")
	flat_deg: FloatProperty(name="Coplanar",default=2.0,min=0.1,max=15.0,step=10,precision=2,update=_live,description="两张面可能不一致的程度，但仍然数量\n 相同平直面板。平直面板与\n 通过询问哪一侧是平直的，而不是曲面壳，可以找到曲面壳" "通过线段本身的任何角度-线段通常具有" "几乎完全没有二面角角度")
	planar_tol: FloatProperty(name="Flatten Below",default=0.01,min=0.0,max=0.1,step=1,precision=4,update=_rebuild,description="一个比这更平坦的子区域成为一n-gon；什么都可以\n curved保留自己的面。展平曲线\n 子区域不是一个简化，它是一个凹痕-测量" "手榴弹引信模型的5.5%")
	min_chain: FloatProperty(name="Min Length",default=0.02,min=0.0,max=1.0,soft_max=1.0,step=1,precision=4,update=_live,description="丢弃比模型这一部分短的线段链")
	dissolve_straight: FloatProperty(name="Remove Straight Loops",default=0.0005,min=0.0,max=5.0,soft_min=0.0,soft_max=0.02,step=1,precision=5,update=_rebuild,description="丢弃循环时，表面可以移动多远当，作为\n 模型的分数。循环仅在以下情况下被删除：\n 它上面的顶点在它的邻居线段的这个范围内\n 制作没有它，所以形式不能折叠无论多远\n 这是提高-圆角简单停止资格。 " "0 转向。天花板是5，远远超过" "模型本身的尺寸；滑块仍然步长在" "有用的范围和任何超过0.02的东西很少被发现" "另一个要执行的循环")
	refit_circles: BoolProperty(name="Keep Circles Round",default=True,update=_rebuild,description="丢弃循环后，放置圆形的顶点\n 按回他们从的圆形。更少的分段\n 在原点圆形的内部内切一个多边形，因此\n 零件读数比实际厚度薄；这拆分了错误" "真半径的任一侧，而不是内部的全部。 " "与LoopTools“圆形”的相同想法。不是的循环" "实际上，圆是保持不变的")
	hs_mirror: BoolProperty(name="Mirror Retopology",default=False,description="构建一并反映它，对于\n 已经对称。重新考虑整个事情会给\n 两半不同的边流动，接缝沿着" "中间是最糟糕的地方")
	hs_mirror_axis: EnumProperty(name="Axis",default="AUTO",items=[("AUTO", "Auto", "找到模型对称的平面"),("X", "X", "跨局部YZ平面的镜像"),("Y", "Y", "跨局部XZ平面的镜像"),("Z", "Z", "跨局部XY平面的镜像")],description="哪个平面要折叠。自动测试全部三个和\n 选择模型实际匹配的一")
	hs_wireframe: BoolProperty(name="Show Wireframe",default=True,description="在重构后，启用线框覆盖，以便\n 新建拓扑是可视的。关离开视口" "覆盖完全相同")
	hs_replace: BoolProperty(name="Replace Original",default=False,description="将结果写入原点对象，而不是\n 将其放在旁边。它置换的网格保持不变，因此\n 恢复原点仍然可以撤消它，并且每次重构都是" "从保持网格的从而不是从最后的从来衡量" "结果-因此，拖动时减少不能复合")
	weld_close: FloatProperty(name="Weld Close Lines",default=0.0002,min=0.0,max=0.02,soft_min=0.0,soft_max=0.01,step=1,precision=5,update=_rebuild,description="合并两条运行比这更近的线\n 模型的分数。他们之间的地带是全部\n 边界和无表面-倒角没有适合的空间\n 在那里，所以斜边塌陷成边是a的一小部分" "毫米长，读取为松散的顶点。测量日期：" "屏障，38条这样的线支撑着整个的倒角" "型号设置为1.2 mm.0转向关")
	auto_prune: BoolProperty(name="Drop Lines That Change Nothing",default=True,update=_live,description="在阈值运行后，测试每个线段的\n 重构需要它，而不是它有多锋利。A\n 线段分隔了两个区域，因此删除它会合并它们，\n 只有在当合并的子区域将" "以不同的方式重构。在浓缩咖啡机上测量，" "这采取3073行下降到506行，结果仍然如此" "就坐在原点表面上")
	use_type: BoolProperty(name="Flat/Curved Boundaries",default=True,update=_live,description="包括平直和弯曲区域之间的边界。这些\n 几乎没有二面角角度，因此仅折痕测试" "永远找不到他们")
	gap_span: FloatProperty(name="Gap Reach",default=0.35,min=0.0,max=4.0,soft_min=0.0,soft_max=4.0,step=1,precision=3,update=_live,description="一个悬垂的一端可以走多远才能找到另一个一，就像\n 模型的一小部分。在“打开端点”时将其升高\n 不是零-开放的线段在重构中留下了一个洞。  \n 在1.0以上，行进可以比" "模型是宽的，它是一条围绕形状弯曲的线段" "需要。其它是转弯限制：延续" "超过56度的关从未发生")
	straighten: FloatProperty(name="Straighten",default=0.0002,min=0.0,max=0.005,step=1,precision=5,update=_rebuild,description="放置位于直运行上的线段顶点，作为\n 模型的分数。检测到的线段每\n 它穿过的网格的顶点，每个一成为一个梯级" "穿过倒角，没有任何东西来调整它。升高它" "太远，孔边开始失去圆度")
	chamfer: FloatProperty(name="Chamfer",default=0.0,min=0.0,max=1.0,soft_min=0.0,soft_max=1.0,step=1,precision=4,update=_rebuild,description="倒角宽度作为模型的一部分，仅应用于\n 检测到的线。0使边锐边。过去的一些\n 百分之一的频带从从开始" "会议；钳制重叠防止它们从" "彼此其它，这使得宽设置可用")
	chamfer_segments: bpy.props.IntProperty(name="Segments",default=2,min=1,max=8,update=_rebuild,description="穿过倒角的行。保持平衡：奇数数量\n 在每个三向角的中间留下一个三角形，" "在基准体上测量36个")
	chamfer_profile: FloatProperty(name="Profile",default=0.5,min=0.0,max=1.0,step=10,precision=2,update=_rebuild,description="0.5是圆形弧形，越低越平，越高的凸起外面")
	chamfer_clamp: BoolProperty(name="Clamp Overlap",default=True,update=_rebuild,description="保持宽度在面板太窄而无法携带的位置\n 而不是让倒角自己折叠")
	support: FloatProperty(name="Support",default=0.0,min=0.0,max=0.05,step=1,precision=4,update=_rebuild,description="从倒角到保持循环的距离，作为\n 模型的分数。循环与\n 沿面板全部排列，因此是细分" "无法打开边缘。0添加无")
	support_loops: bpy.props.IntProperty(name="Loops",default=1,min=1,max=3,update=_rebuild,description="每个面板内部有多少个许多。每个一\n 坐在它前面的一的从距离")
	close_gaps: BoolProperty(name="Close Gaps",default=True,update=_live,description="沿现有网格边悬垂的桥接端点。A线段\n 间隙使其子区域停止关闭，而子区域是" "然后跳过，留下一个洞")
class QUADREMESH_OT_lines_preview(Operator):
	bl_idname= "mesh.quadremesh_lines_preview";bl_label= g("Show Feature Lines");bl_description= "根据当前阈值构建线段对象";bl_options={"REGISTER", "UNDO"}
	@classmethod
	def poll(cls,context):
		o=context.active_object
		return o is not None and o.type== "MESH" and len(o.data.polygons)
	def execute(self,context):
		obj=context.active_object
		if obj.name.endswith((SUFFIX,PANEL_SUFFIX,BUILD_SUFFIX)):
			src=bpy.data.objects.get(context.scene.quadremesh_lines.source)
			if src is None:
				GR(self,"WARNING", "select the source mesh,not the lines")
				return {"CANCELLED"}
			obj=src
		st=context.scene.quadremesh_lines
		st.source=obj.name
		cache=get_cache(obj)
		auto_c,auto_f=HS.auto_thresholds(cache)
		if st.auto_thresholds:
			st.crease_deg,st.flat_deg=round(auto_c,1),round(auto_f,2)
		out=rebuild_preview(context,obj)
		if out is None:
			GR(self,"WARNING", "no lines at these thresholds")
			return {"CANCELLED"}
		GR(self,"INFO",st.info)
		return {"FINISHED"}
class QUADREMESH_OT_panels_preview(Operator):
	bl_idname= "mesh.quadremesh_panels_preview";bl_label= g("Show Panels");bl_description=("为当前线路雕刻出来的面板上色。每个\n 颜色是重构将作为单处理的一子区域 " "flat face");bl_options={"REGISTER", "UNDO"}
	@classmethod
	def poll(cls,context):
		o=context.active_object
		return o is not None and o.type== "MESH" and len(o.data.polygons)
	def execute(self,context):
		obj=context.active_object
		if obj.name.endswith((SUFFIX,PANEL_SUFFIX,BUILD_SUFFIX)):
			src=bpy.data.objects.get(context.scene.quadremesh_lines.source)
			if src is None:
				GR(self,"WARNING", "select the source mesh")
				return {"CANCELLED"}
			obj=src
		st=context.scene.quadremesh_lines
		st.source=obj.name
		cache=get_cache(obj)
		auto_c,auto_f=HS.auto_thresholds(cache)
		if st.auto_thresholds:
			st.crease_deg,st.flat_deg=round(auto_c,1),round(auto_f,2)
		out=rebuild_panels(context,obj)
		if out is None:
			return {"CANCELLED"}
		for area in context.screen.areas:
			if area.type== "VIEW_3D":
				sp=area.spaces.active
				sp.shading.type= "SOLID"
				sp.shading.color_type= "VERTEX"
				sp.shading.light= "FLAT"
		obj.hide_set(True)
		for o in list(context.selected_objects):
			o.select_set(False)
		out.select_set(True)
		context.view_layer.objects.active=out
		GR(self,"INFO",st.panel_info)
		return {"FINISHED"}
class QUADREMESH_OT_panels_build(Operator):
	bl_idname= "mesh.quadremesh_panels_build";bl_label= g("Remesh Hardsurface");bl_description=("将面板转换为几何。结果的每个边缘\n 是检测到的线段-孔洞被切割打开，孔得到 " "quad wall instead of being capped shut");bl_options={"REGISTER", "UNDO"}
	@classmethod
	def poll(cls,context):
		o=context.active_object
		return o is not None and o.type== "MESH" and len(o.data.polygons)
	def execute(self,context):
		obj=context.active_object
		for suffix in (SUFFIX,PANEL_SUFFIX,BUILD_SUFFIX):
			if obj.name.endswith(suffix):
				src=bpy.data.objects.get(context.scene.quadremesh_lines.source)
				if src is None:
					GR(self,"WARNING", "select the source mesh")
					return {"CANCELLED"}
				obj=src
				break
		st=context.scene.quadremesh_lines
		st.source=obj.name
		if obj.mode== "EDIT":
			bpy.ops.object.mode_set(mode="OBJECT")
		cache=get_cache(obj)
		auto_c,auto_f=HS.auto_thresholds(cache)
		if st.auto_thresholds:
			st.crease_deg,st.flat_deg=round(auto_c,1),round(auto_f,2)
		cur=bpy.data.objects.get(st.result)
		reuse=None
		if (cur is not None and cur.get("quadremesh_source")==obj.name
				and cur.get("quadremesh_kind")== "hardsurface"
				and at_same_place(cur,obj)):
			reuse=cur.name
		out=build_maybe_mirrored(context,obj,reuse=reuse,report=self.report)
		if out is None:
			GR(self,"WARNING",st.build_info or "nothing built")
			return {"CANCELLED"}
		if st.hs_wireframe:
			for area in context.screen.areas:
				if area.type== "VIEW_3D":
					sp=area.spaces.active
					sp.overlay.show_wireframes=True
					sp.overlay.wireframe_threshold=1.0
		for suffix in (SUFFIX,PANEL_SUFFIX):
			o=bpy.data.objects.get(st.source + suffix)
			if o is not None:
				o.hide_set(True)
		for o in list(context.selected_objects):
			o.select_set(False)
		out.select_set(True)
		context.view_layer.objects.active=out
		GR(self,"INFO",st.build_info)
		return {"FINISHED"}
class QUADREMESH_OT_lines_clear(Operator):
	bl_idname= "mesh.quadremesh_lines_clear";bl_label= g("Clear");bl_description= "移除线段预览对象"
	def execute(self,context):
		st=context.scene.quadremesh_lines
		for suffix in (SUFFIX,PANEL_SUFFIX,BUILD_SUFFIX):
			o=bpy.data.objects.get((st.source or "") + suffix)
			if o is not None:
				d=o.data
				bpy.data.objects.remove(o)
				if d.users==0:
					bpy.data.meshes.remove(d)
		src=bpy.data.objects.get(st.source)
		if src is not None:
			src.hide_set(False)
		st.source= ""
		st.info= ""
		st.panel_info= ""
		st.build_info= ""
		return {"FINISHED"}
class QUADREMESH_OT_panelize(Operator):
	"""Dissolve every edge that is not one of the lines you marked.
	Works in place on the active object,in Object Mode or Edit Mode. It is an
	edit like Blender's own Dissolve,so Ctrl+Z is the way back - it does not
	build a result object beside the original the way Remesh Hardsurface does,because the input here is a mesh the user has already marked up by hand
	and duplicating it would strand those marks on the copy.
	"""
	bl_idname= "mesh.quadremesh_panelize";bl_label=g("Dissolve Between Lines");bl_description=("保持你标记的线条，溶解一切\n 在它们之间，每个面板留有一n-gon。标记线 " "with Edge ▸ Mark Sharp,or just select them");bl_options={"REGISTER", "UNDO"}
	@classmethod
	def poll(cls,context):
		ob=context.active_object
		return ob is not None and ob.type== "MESH"
	def execute(self,context):
		st=context.scene.quadremesh_lines
		ob=context.active_object
		editing=ob.mode== "EDIT"
		live=bmesh.from_edit_mesh(ob.data) if editing else None
		if editing:
			bm=live.copy()
		else:
			bm=bmesh.new()
			bm.from_mesh(ob.data)
		bm.edges.ensure_lookup_table()
		bm.faces.ensure_lookup_table()
		marks=PZ.count_marked(bm,use_sharp=st.pz_use_sharp,use_selection=st.pz_use_selection)
		if marks["usable"]==0:
			if not editing:
				bm.free()
			GR(self,"ERROR","No lines marked. Mark edges Sharp in Edit Mode,or " "select them,then press again")
			return {"CANCELLED"}
		doomed,n_regions=PZ.inside_marked_loops(bm,use_sharp=st.pz_use_sharp,use_selection=st.pz_use_selection)
		if not doomed:
			if editing:
				bm.free()
			else:
				bm.free()
			GR(self,"ERROR","Your lines do not close off any area. Make the marked " "edges form a complete loop around what you want " "flattened.")
			return {"CANCELLED"}
		keep={e.index for e in bm.edges} - doomed
		box_before=PZ.bounds(bm)
		try:
			res=PZ.panelize(bm,keep,dissolve_verts=st.pz_dissolve_verts)
		except Exception as exc:
			bm.free()
			GR(self,"ERROR",f"Dissolve failed: {exc}")
			return {"CANCELLED"}
		note=PZ.check(bm,box_before,res)
		if editing:
			PZ.panelize(live,keep,dissolve_verts=st.pz_dissolve_verts)
			bm.free()
			bmesh.update_edit_mesh(ob.data,loop_triangles=True,destructive=True)
		else:
			bm.to_mesh(ob.data)
			bm.free()
			ob.data.update()
		st.panelize_info=(f"{res['faces_before']} -> {res['faces_after']} faces, " f"{res['edges_removed']} edges and {res['verts_removed']} vertices " f"removed,{res['lines_kept']} lines kept")
		if note:
			st.panelize_info += "  |  " + note
			GR(self,"WARNING",note)
		else:
			GR(self,"INFO",st.panelize_info)
		return {"FINISHED"}
class QUADREMESH_OT_panelize_mark(Operator):
	"""标记选定的边锐边，使他们生存图层解散."""
	bl_idname= "mesh.quadremesh_panelize_mark";bl_label=g("Mark Selected as Lines");bl_description=("标记选定的边锐边。它们变成青色，是\n 与网格一起保存，并且是“溶解于” " "Lines keeps");bl_options={"REGISTER", "UNDO"}
	def draw(S,_):L=S.layout;[GP(L,S,n) for n in S.__annotations__]
	clear: BoolProperty(name="Clear Instead",default=False,options={"HIDDEN"})
	@classmethod
	def poll(cls,context):
		ob=context.active_object
		return (ob is not None and ob.type== "MESH" and ob.mode== "EDIT")
	def execute(self,context):
		ob=context.active_object
		bm=bmesh.from_edit_mesh(ob.data)
		n=0
		for e in bm.edges:
			if self.clear:
				if not e.smooth:
					e.smooth=True; n +=1
			elif e.select:
				if e.smooth:
					e.smooth=False; n +=1
		bmesh.update_edit_mesh(ob.data)
		GR(self,"INFO",f"{'cleared' if self.clear else 'marked'} {n} edges")
		return {"FINISHED"}
class QUADREMESH_OT_clean_between(Operator):
	"""Dissolve everything that is not a feature line,in place.
	Uses the same mask `Remesh Hardsurface` builds from - detector plus the
	user's own marked edges,after the prune - so the lines that survive here
	are exactly the lines that survive there. It is not a second algorithm;
	it is the same decision applied to the original mesh instead of to a
	freshly built one.
	"""
	bl_idname= "mesh.quadremesh_clean_between";bl_label=g("Clean Between Lines");bl_description=("清理选定的边包围的区域。  \n 其它线路，以及该区域之外的任何东西都被留下 " "alone");bl_options={"REGISTER", "UNDO"}
	@classmethod
	def poll(cls,context):
		o=context.active_object
		return o is not None and o.type== "MESH" and len(o.data.polygons)
	def execute(self,context):
		st=context.scene.quadremesh_lines
		obj=context.active_object
		editing=obj.mode== "EDIT"
		if editing:
			bpy.ops.object.mode_set(mode="OBJECT")
		st.source=obj.name
		cache=get_cache(obj)
		mask,info,plog,crease,flat,auto_c,auto_f=detect(context,cache,st)
		E=cache["edges"]
		want=set()
		for i in np.flatnonzero(mask).tolist():
			a,b=int(E[i][0]),int(E[i][1])
			want.add((a,b) if a < b else (b,a))
		stash=bpy.data.meshes.get(obj.get(PZ_ORIG_KEY) or "")
		if stash is None:
			stash=obj.data.copy()
			stash.name=obj.data.name + "_preclean"
			stash.use_fake_user=True
			obj[PZ_ORIG_KEY]=stash.name
			_remember_base(obj,stash)
		bm=bmesh.new()
		bm.from_mesh(stash)
		bm.edges.ensure_lookup_table()
		bm.faces.ensure_lookup_table()
		n_sel=0
		for e in bm.edges:
			e.tag=e.select or (not e.smooth)
			if e.select:
				n_sel +=1
		if not n_sel:
			bm.free()
			if editing:
				bpy.ops.object.mode_set(mode="EDIT")
			GR(self,"ERROR","Select the lines to clean between,in Edit Mode. Any number - " "every area they close off is cleaned.")
			return {"CANCELLED"}
		doomed=PZ.enclosed_interior(bm,require_selected=True)
		doomed=PZ.thin_out(doomed,st.pz_amount)
		before=len(bm.faces)
		if doomed:
			PZ.dissolve_keeping_rims(bm,doomed,region=PZ.region_faces(bm))
		bm.normal_update()
		bm.to_mesh(obj.data)
		bm.free()
		obj.data.update()
		if editing:
			bpy.ops.object.mode_set(mode="EDIT")
		st.build_info=(f"{before} -> {len(obj.data.polygons)} faces  |  "
						 f"{len(want)} lines kept"
						 + (f"  |  {info['n_marked']} of your own"
							if info.get("n_marked") else ""))
		GR(self,"INFO",st.build_info)
		return {"FINISHED"}
class QUADREMESH_OT_clean_reset(Operator):
	"""Put the mesh back as it was before the cleaning started.
	The stash the percentage slider redoes from is also the way back,so this
	is just handing it over and forgetting it. After this the slider starts a
	fresh stash from whatever the mesh is then.
	"""
	bl_idname= "mesh.quadremesh_clean_reset";bl_label=g("Reset");bl_description=("完全撤消清理并忘记它，因此下一步\n 滑块移动再次从现在的网格从");bl_options={"REGISTER", "UNDO"}
	@classmethod
	def poll(cls,context):
		o=context.active_object
		return (o is not None and o.type== "MESH"
				and bool(o.get(PZ_ORIG_KEY)))
	def execute(self,context):
		obj=context.active_object
		st=context.scene.quadremesh_lines
		stash=bpy.data.meshes.get(obj.get(PZ_ORIG_KEY) or "")
		if stash is None:
			obj.pop(PZ_ORIG_KEY,None)
			GR(self,"WARNING", "nothing stored to go back to")
			return {"CANCELLED"}
		editing=obj.mode== "EDIT"
		if editing:
			bpy.ops.object.mode_set(mode="OBJECT")
		before=len(obj.data.polygons)
		bm=bmesh.new()
		bm.from_mesh(stash)
		bm.to_mesh(obj.data)
		bm.free()
		obj.data.update()
		obj.pop(PZ_ORIG_KEY,None)
		stash.use_fake_user=False
		if stash.users==0:
			bpy.data.meshes.remove(stash)
		if editing:
			bpy.ops.object.mode_set(mode="EDIT")
		with suspend_live():
			st.pz_amount=100.0
		st.build_info=f"reset  |  {before} -> {len(obj.data.polygons)} faces"
		GR(self,"INFO",st.build_info)
		return {"FINISHED"}
class QUADREMESH_OT_clean_confirm(Operator):
	"""Accept the cleaned area and stop the slider touching it again.
	Dropping the stash is what does it: the slider rebuilds from the stash
	every time,so once there is none the current mesh is simply the new
	starting point. The selection is cleared too,which is what keeps the
	slider quiet until the next area is picked.
	"""
	bl_idname= "mesh.quadremesh_clean_confirm";bl_label=g("Confirm");bl_description=("保持这个区域现在的样子。滑块停止影响\n 它并保持关，直到您选择下一个区域");bl_options={"REGISTER", "UNDO"}
	@classmethod
	def poll(cls,context):
		o=context.active_object
		return o is not None and o.type== "MESH" and bool(o.get(PZ_ORIG_KEY))
	def execute(self,context):
		obj=context.active_object
		st=context.scene.quadremesh_lines
		stash=bpy.data.meshes.get(obj.get(PZ_ORIG_KEY) or "")
		obj.pop(PZ_ORIG_KEY,None)
		if stash is not None:
			stash.use_fake_user=False
			if stash.users==0:
				bpy.data.meshes.remove(stash)
		if obj.mode== "EDIT":
			bm=bmesh.from_edit_mesh(obj.data)
			for e in bm.edges:
				e.select=False
			for v in bm.verts:
				v.select=False
			for f in bm.faces:
				f.select=False
			bm.select_flush(False)
			bmesh.update_edit_mesh(obj.data)
		else:
			for e in obj.data.edges:
				e.select=False
			for v in obj.data.vertices:
				v.select=False
			for f in obj.data.polygons:
				f.select=False
		with suspend_live():
			st.pz_amount=100.0
		st.build_info=f"confirmed  |  {len(obj.data.polygons)} faces"
		GR(self,"INFO",st.build_info)
		return {"FINISHED"}
class QUADREMESH_OT_clean_revert_all(Operator):
	"""Undo every cleaning on this object,confirmed ones included.
	Reset only steps back to the last stash,which Confirm throws away. This
	works from the snapshot taken the first time the object was touched,so it
	reaches past every Confirm in the session.
	"""
	bl_idname= "mesh.quadremesh_clean_revert_all";bl_label=g("Revert All Cleaning");bl_description=("把这个对象放回清理前的样子，\n 包括已确认的区域");bl_options={"REGISTER", "UNDO"}
	all_objects: BoolProperty(name="Every Object",default=False,description="对文件中已清理的每个对象执行该操作，\n 不仅仅是这个一")
	@classmethod
	def poll(cls,context):
		if any(o.get(PZ_BASE_KEY) for o in bpy.data.objects):
			return True
		o=context.active_object
		return o is not None and bool(o.get(PZ_BASE_KEY))
	def invoke(self,context,event):
		return context.window_manager.invoke_props_dialog(self,width=340)
	def draw(self,context):
		col=self.layout.column(align=True)
		GL(col,"Undoes all cleaning,confirmed areas included.")
		GP(col,self, "all_objects",text="Every Object")
	def execute(self,context):
		st=context.scene.quadremesh_lines
		act=context.active_object
		if act is not None and act.mode== "EDIT":
			bpy.ops.object.mode_set(mode="OBJECT")
		targets=([o for o in bpy.data.objects if o.type== "MESH" and o.get(PZ_BASE_KEY)]
				   if self.all_objects
				   else ([act] if act is not None and act.get(PZ_BASE_KEY) else []))
		if not targets:
			GR(self,"WARNING", "nothing has been cleaned")
			return {"CANCELLED"}
		done=0
		for obj in targets:
			base=bpy.data.meshes.get(obj.get(PZ_BASE_KEY) or "")
			if base is None:
				obj.pop(PZ_BASE_KEY,None)
				continue
			bm=bmesh.new()
			bm.from_mesh(base)
			bm.to_mesh(obj.data)
			bm.free()
			obj.data.update()
			for key in (PZ_ORIG_KEY,PZ_BASE_KEY,PZ_DROP_KEY):
				name=obj.get(key)
				obj.pop(key,None)
				m=bpy.data.meshes.get(name or "")
				if m is not None:
					m.use_fake_user=False
					if m.users==0:
						bpy.data.meshes.remove(m)
			done +=1
		with suspend_live():
			st.pz_amount=100.0
		st.build_info=f"reverted {done} object{'s' if done !=1 else ''}"
		GR(self,"INFO",st.build_info)
		return {"FINISHED"}
class QUADREMESH_OT_drop_useless(Operator):
	"""Remove every edge loop that is not holding any shape.
	No marking needed. Each loop is measured by how far the surface turns
	across it: a loop down the middle of a flat panel turns nothing and is
	only costing vertices,while one round a fillet turns a lot and is the
	shape itself. Only the first kind goes.
	Always measured against the mesh as it was before the first run,never
	against the last result. Removing a loop lengthens the edges crossing its
	neighbours,which flattens how they measure,so working from the current
	mesh made every press eat further into the model. From a fixed baseline a
	second press at the same setting simply reproduces the first.
	"""
	bl_idname= "mesh.quadremesh_drop_useless";bl_label=g("Drop Useless Loops");bl_description=("移除没有形状的循环边，在\n 整个模型。首先不需要标记任何内容，并且 " "pressing it again changes nothing");bl_options={"REGISTER", "UNDO"}
	@classmethod
	def poll(cls,context):
		o=context.active_object
		return o is not None and o.type== "MESH" and len(o.data.polygons)
	def execute(self,context):
		st=context.scene.quadremesh_lines
		obj=context.active_object
		editing=obj.mode== "EDIT"
		if editing:
			bpy.ops.object.mode_set(mode="OBJECT")
		base=bpy.data.meshes.get(obj.get(PZ_DROP_KEY) or "")
		if base is None:
			base=obj.data.copy()
			base.name=obj.data.name + "_predrop"
			base.use_fake_user=True
			obj[PZ_DROP_KEY]=base.name
		bm=bmesh.new()
		bm.from_mesh(base)
		bm.edges.ensure_lookup_table()
		bm.faces.ensure_lookup_table()
		PZ.tag_marked(bm)
		before=len(bm.faces)
		dropped=partial=0
		if st.pz_every >=1:
			doomed,n2=PZ.thin_every(bm,st.pz_every,keep_marked=st.pz_keep_marked,axes=(st.pz_axis_x,st.pz_axis_y,st.pz_axis_z))
			if doomed:
				PZ.dissolve_keeping_rims(bm,doomed,polish=True)
				PZ.heal_stubs(bm)
				PZ.polish_verts(bm)
				dropped +=n2
		if st.pz_useless > 0.0:
			n1,partial=PZ.drop_loops(bm,tol_deg=st.pz_useless,keep_marked=st.pz_keep_marked,sag_pct=0.0,axes=(st.pz_axis_x,st.pz_axis_y,st.pz_axis_z))
			dropped +=n1
		PZ.polish_verts(bm)
		bm.to_mesh(obj.data)
		bm.free()
		obj.data.update()
		if editing:
			bpy.ops.object.mode_set(mode="EDIT")
		st.build_info=(f"{dropped} loop{'s' if dropped !=1 else ''} dropped"
						 f"  |  {before} -> {len(obj.data.polygons)} faces"
						 + (f"  |  {partial} left alone,they do not run to " "a clean end" if partial else ""))
		GR(self,"INFO",st.build_info)
		return {"FINISHED"}
class QUADREMESH_OT_force_loop(Operator):
	"""切割一个通过n个gon和极点进行类似操作的边循环."""
	bl_idname= "mesh.quadremesh_force_loop";bl_label=g("Force Edge Loop");bl_description=("单击视口中的边以切割循环\n 它，就在你点击的地方-不像Blender的\n 循环-切割-它一直通过n-gons。逃逸或 " "right-click to cancel");bl_options={"REGISTER", "UNDO"}
	@classmethod
	def poll(cls,context):
		o=context.active_object
		return o is not None and o.type== "MESH" and o.mode== "EDIT"
	def invoke(self,context,event):
		if context.area is None or context.area.type != "VIEW_3D":
			GR(self,"ERROR", "works in the 3D viewport")
			return {"CANCELLED"}
		context.window.cursor_modal_set("KNIFE")
		context.area.header_text_set("Force Edge Loop: click an edge to cut through it  |  " "Esc / right-click to cancel")
		context.window_manager.modal_handler_add(self)
		return {"RUNNING_MODAL"}
	def _finish(self,context):
		context.window.cursor_modal_restore()
		context.area.header_text_set(None)
	def modal(self,context,event):
		if event.type in {"RIGHTMOUSE", "ESC"}:
			self._finish(context)
			return {"CANCELLED"}
		if event.type != "LEFTMOUSE" or event.value != "PRESS":
			return {"RUNNING_MODAL"}
		from bpy_extras import view3d_utils
		obj=context.active_object
		region=context.region
		rv3d=context.region_data
		co=(event.mouse_region_x,event.mouse_region_y)
		origin=view3d_utils.region_2d_to_origin_3d(region,rv3d,co)
		direction=view3d_utils.region_2d_to_vector_3d(region,rv3d,co)
		inv=obj.matrix_world.inverted()
		o_local=inv @ origin
		d_local=(inv.to_3x3() @ direction).normalized()
		bm=bmesh.from_edit_mesh(obj.data)
		bm.faces.ensure_lookup_table()
		from mathutils.bvhtree import BVHTree
		tree=BVHTree.FromBMesh(bm)
		hit=tree.ray_cast(o_local,d_local)
		if hit is None or hit[0] is None:
			return {"RUNNING_MODAL"}
		loc,_n,fidx,_d=hit
		face=bm.faces[fidx]
		edge=min(face.edges,key=lambda e: (loc - (e.verts[0].co + e.verts[1].co) / 2).length)
		a,b=edge.verts[0].co,edge.verts[1].co
		ab=b - a
		t=0.5 if ab.length_squared < 1e-18 else             (loc - a).dot(ab) / ab.length_squared
		t=min(max(t,0.05),0.95)
		axis=context.scene.quadremesh_lines.pz_loop_axis
		if axis== "AUTO":
			cuts=PZ.force_loop(bm,edge,factor=t)
		else:
			no={"X": Vector((1,0,0)), "Y": Vector((0,1,0)),"Z": Vector((0,0,1))}[axis]
			no_local=(inv.to_3x3() @ no).normalized()
			res=bmesh.ops.bisect_plane(bm,geom=list(bm.verts) + list(bm.edges) + list(bm.faces),plane_co=loc,plane_no=no_local)
			cuts=sum(1 for g in res["geom_cut"]
					   if isinstance(g,bmesh.types.BMEdge))
		bmesh.update_edit_mesh(obj.data,loop_triangles=True,destructive=True)
		self._finish(context)
		if not cuts:
			GR(self,"WARNING", "could not cut from there")
			return {"CANCELLED"}
		GR(self,"INFO",f"cut through {cuts} faces")
		return {"FINISHED"}
	def execute(self,context):
		obj=context.active_object
		bm=bmesh.from_edit_mesh(obj.data)
		sel=[e for e in bm.edges if e.select]
		if len(sel) !=1:
			GR(self,"ERROR", "select exactly one edge to start from")
			return {"CANCELLED"}
		cuts=PZ.force_loop(bm,sel[0])
		bmesh.update_edit_mesh(obj.data,loop_triangles=True,destructive=True)
		if not cuts:
			GR(self,"WARNING", "could not cut from here")
			return {"CANCELLED"}
		GR(self,"INFO",f"cut through {cuts} faces")
		return {"FINISHED"}
def _uv_seam_edges(bm):
	uv=bm.loops.layers.uv.active
	if uv is None:
		return []
	out=[]
	for e in bm.edges:
		faces=e.link_faces
		seam=False
		if len(faces)==1:
			seam=True
		elif len(faces)==2:
			for v in e.verts:
				uvs=[]
				for f in faces:
					for l in f.loops:
						if l.vert is v:
							uvs.append(l[uv].uv)
							break
				if len(uvs)==2 and (uvs[0] - uvs[1]).length > 1e-5:
					seam=True
					break
		if seam:
			out.append(e)
	return out
def _with_bmesh(obj,fn):
	if obj.mode== "EDIT":
		bm=bmesh.from_edit_mesh(obj.data)
		n=fn(bm)
		bmesh.update_edit_mesh(obj.data,loop_triangles=False,destructive=False)
	else:
		bm=bmesh.new()
		bm.from_mesh(obj.data)
		n=fn(bm)
		bm.to_mesh(obj.data)
		bm.free()
		obj.data.update()
	return n
def _uv_show_update(self,context):
	obj=context.active_object
	if obj is None or obj.type != "MESH" or not obj.data.uv_layers:
		return
	on=self.uv_show_seams
	def apply(bm):
		n=0
		for e in _uv_seam_edges(bm):
			e.seam=on
			n +=1
		return n
	_with_bmesh(obj,apply)
	for area in context.screen.areas:
		if area.type== "VIEW_3D":
			area.spaces.active.overlay.show_edge_seams=True
def _uv_sharp_update(self,context):
	obj=context.active_object
	if obj is None or obj.type != "MESH" or not obj.data.uv_layers:
		return
	on=self.uv_seams_sharp
	def apply(bm):
		n=0
		for e in _uv_seam_edges(bm):
			e.smooth=not on
			n +=1
		return n
	_with_bmesh(obj,apply)
	if on:
		self.hs_use_marked=True
	for area in context.screen.areas:
		if area.type== "VIEW_3D":
			area.spaces.active.overlay.show_edge_sharp=True
def _source_disp_scale(src_obj):
	for slot in src_obj.material_slots:
		m=slot.material
		if not (m and m.use_nodes):
			continue
		out=next((n for n in m.node_tree.nodes if n.type== "OUTPUT_MATERIAL"),None)
		if out and out.inputs["Displacement"].is_linked:
			dn=out.inputs["Displacement"].links[0].from_node
			if "Scale" in dn.inputs:
				return dn.inputs["Scale"].default_value
	return 1.0
def _bake_via_emission(src_obj,socket_name,default_is_color):
	undo=[]
	for slot in src_obj.material_slots:
		mat=slot.material
		if mat is None or not mat.use_nodes:
			continue
		nt=mat.node_tree
		out=next((n for n in nt.nodes
					if n.type== "OUTPUT_MATERIAL" and n.is_active_output),None) or next((n for n in nt.nodes if n.type== "OUTPUT_MATERIAL"),None)
		bsdf=next((n for n in nt.nodes if n.type== "BSDF_PRINCIPLED"),None)
		if out is None:
			continue
		if socket_name== "Height":
			d=out.inputs["Displacement"]
			dn=d.links[0].from_node if d.is_linked else None
			if dn is None or "Height" not in dn.inputs:
				continue
			sock=dn.inputs["Height"]
		else:
			if bsdf is None or socket_name not in bsdf.inputs:
				continue
			sock=bsdf.inputs[socket_name]
		emit=nt.nodes.new("ShaderNodeEmission")
		emit.name= "qr_bake_emit"
		if sock.is_linked:
			nt.links.new(sock.links[0].from_socket,emit.inputs["Color"])
		else:
			v=sock.default_value
			if default_is_color:
				emit.inputs["Color"].default_value=(v[0],v[1],v[2],1.0)
			else:
				emit.inputs["Color"].default_value=(v,v,v,1.0)
		prev=[(l.from_socket,l.to_socket) for l in out.inputs["Surface"].links]
		for l in list(out.inputs["Surface"].links):
			nt.links.remove(l)
		nt.links.new(emit.outputs["Emission"],out.inputs["Surface"])
		undo.append((nt,emit,out,prev))
	def restore():
		for nt,emit,out,prev in undo:
			for l in list(out.inputs["Surface"].links):
				nt.links.remove(l)
			for fs,ts in prev:
				nt.links.new(fs,ts)
			nt.nodes.remove(emit)
	return restore
BAKE_UNDO_MATS= "quadremesh_prebake_mats"
BAKE_UNDO_UV= "quadremesh_prebake_uv"
def _worst_drift(target,src_obj):
	from mathutils.bvhtree import BVHTree
	me=src_obj.data
	if not len(me.polygons) or not len(target.data.vertices):
		return 0.0
	mw=src_obj.matrix_world
	tree=BVHTree.FromPolygons([(mw @ v.co)[:] for v in me.vertices],[p.vertices[:] for p in me.polygons])
	tw=target.matrix_world
	verts=target.data.vertices
	step=max(1,len(verts) // 3000)
	worst=0.0
	for i in range(0,len(verts),step):
		hit=tree.find_nearest(tw @ verts[i].co)
		if hit and hit[3] is not None and hit[3] > worst:
			worst=hit[3]
	return worst
class QUADREMESH_OT_unbake(Operator):
	"""将模型放回烘焙从原点之前的样子."""
	bl_idname= "mesh.quadremesh_unbake";bl_label=g("Undo Bake");bl_description=("恢复该模型的材质和UV映射\n 在烘焙之前，删除烘焙图像");bl_options={"REGISTER", "UNDO"}
	@classmethod
	def poll(cls,context):
		o=context.active_object
		return (o is not None and o.type== "MESH" and BAKE_UNDO_MATS in o)
	def execute(self,context):
		obj=context.active_object
		if obj.mode != "OBJECT":
			bpy.ops.object.mode_set(mode="OBJECT")
		me=obj.data
		baked=[m for m in me.materials if m]
		me.materials.clear()
		for name in obj.get(BAKE_UNDO_MATS,[]):
			me.materials.append(bpy.data.materials.get(name) if name else None)
		n_img=0
		for mat in baked:
			if mat.users > 0 or not mat.use_nodes:
				continue
			for node in list(mat.node_tree.nodes):
				img=getattr(node, "image",None)
				if img is not None and img.users <=1:
					bpy.data.images.remove(img)
					n_img +=1
			bpy.data.materials.remove(mat)
		layer=me.uv_layers.get("BakeUV")
		if layer is not None and len(me.uv_layers) > 1:
			me.uv_layers.remove(layer)
		want=obj.get(BAKE_UNDO_UV) or ""
		back=me.uv_layers.get(want)
		if back is not None:
			me.uv_layers.active=back
			back.active_render=True
		del obj[BAKE_UNDO_MATS]
		obj.pop(BAKE_UNDO_UV,None)
		me.update()
		GR(self,"INFO",f"bake undone,{n_img} images removed")
		return {"FINISHED"}
def _uv_tiles(me,layer):
	import numpy as _np
	n=len(layer.data)
	arr=_np.empty(n * 2,dtype=_np.float32)
	layer.data.foreach_get("uv",arr)
	arr=arr.reshape(n,2)
	u=_np.clip(_np.floor(arr[:,0]).astype(int),0,9)
	v=_np.clip(_np.floor(arr[:,1]).astype(int),0,None)
	nums=sorted({1001 + int(a) + 10 * int(b) for a,b in zip(u,v)})
	return nums or [1001]
def _new_bake_image(name,size,tiles,colorspace):
	img=bpy.data.images.new(name,size,size,tiled=len(tiles) > 1)
	img.colorspace_settings.name=colorspace
	if len(tiles) > 1:
		first=tiles[0]
		img.tiles[0].number=first
		for t in tiles[1:]:
			img.tiles.new(tile_number=t)
		with bpy.context.temp_override(edit_image=img):
			for t in img.tiles:
				img.tiles.active=t
				bpy.ops.image.tile_fill(width=size,height=size,color=(0,0,0,1),alpha=True)
	return img
def _prefill_from_source(img,src_obj,socket):
	found=None
	for slot in src_obj.material_slots:
		mat=slot.material
		if not (mat and mat.use_nodes):
			continue
		bsdf=next((n for n in mat.node_tree.nodes if n.type== "BSDF_PRINCIPLED"),None)
		if bsdf is None or socket not in bsdf.inputs:
			continue
		inp=bsdf.inputs[socket]
		if socket== "Normal" and inp.is_linked:
			nm=inp.links[0].from_node
			if "Color" in nm.inputs and nm.inputs["Color"].is_linked:
				inp=nm.inputs["Color"]
		if not inp.is_linked:
			continue
		node=inp.links[0].from_node
		if node.type== "TEX_IMAGE" and node.image:
			found=node.image
			break
	if found is None or tuple(found.size)==(0,0):
		return False
	tmp=found.copy()
	try:
		if tuple(tmp.size) !=tuple(img.size):
			tmp.scale(img.size[0],img.size[1])
		px=np.empty(img.size[0] * img.size[1] * 4,dtype=np.float32)
		tmp.pixels.foreach_get(px)
		img.pixels.foreach_set(px)
		img.update()
	finally:
		bpy.data.images.remove(tmp)
	return True
def _build_cage(target,src_obj,floor):
	from mathutils.bvhtree import BVHTree
	me=src_obj.data
	if not len(me.polygons):
		return None,floor
	mw=src_obj.matrix_world
	tree=BVHTree.FromPolygons([(mw @ v.co)[:] for v in me.vertices],[p.vertices[:] for p in me.polygons])
	cage_me=target.data.copy()
	cage_me.name=target.name + "_cage"
	tw=target.matrix_world
	n=len(cage_me.vertices)
	co=np.empty(n * 3,dtype=np.float32)
	cage_me.vertices.foreach_get("co",co)
	co=co.reshape(n,3)
	nor=np.empty(n * 3,dtype=np.float32)
	cage_me.vertices.foreach_get("normal",nor)
	nor=nor.reshape(n,3)
	worst=0.0
	for i in range(n):
		hit=tree.find_nearest(tw @ Vector(co[i]))
		d=hit[3] if hit and hit[3] is not None else 0.0
		worst=max(worst,d)
		push=max(d * 1.5,floor)
		co[i]=co[i] + nor[i] * push
	cage_me.vertices.foreach_set("co",co.reshape(-1))
	cage_me.update()
	cage=bpy.data.objects.new(target.name + "_cage",cage_me)
	bpy.context.scene.collection.objects.link(cage)
	cage.matrix_world=target.matrix_world.copy()
	cage.hide_render=True
	return cage,max(worst * 3.0,floor * 3.0)
class QUADREMESH_OT_bake_from_original(Operator):
	"""为重新绘制的模型提供新的UV，并烘焙原点的纹理到其上."""
	bl_idname= "mesh.quadremesh_bake_from_original";bl_label=g("Bake From Original");bl_description=("解包重新包装的模型，并烘焙原点\n 模型的颜色(以及可选的法线)。\n 独立于UV岛，因此即使在 " "original has surfaces lying on top of each other");bl_options={"REGISTER", "UNDO"}
	@classmethod
	def poll(cls,context):
		o=context.active_object
		return o is not None and o.type== "MESH" and (bool(o.get("quadremesh_source"))
			or bool(o.get("quadremesh_orig_mesh")))
	def execute(self,context):
		st=context.scene.quadremesh_lines
		target=context.active_object
		scene=context.scene
		src_obj=bpy.data.objects.get(target.get("quadremesh_source") or "")
		temp=None
		if src_obj is None:
			me=bpy.data.meshes.get(target.get("quadremesh_orig_mesh") or "")
			if me is None:
				GR(self,"ERROR", "the original model is gone")
				return {"CANCELLED"}
			temp=bpy.data.objects.new("qr_bake_src",me)
			scene.collection.objects.link(temp)
			temp.matrix_world=target.matrix_world.copy()
			src_obj=temp
		if not any(m for m in src_obj.data.materials):
			if temp is not None:
				bpy.data.objects.remove(temp,do_unlink=True)
			GR(self,"ERROR", "the original has no material to bake from")
			return {"CANCELLED"}
		if target.mode != "OBJECT":
			bpy.ops.object.mode_set(mode="OBJECT")
		size=int(st.bake_size)
		margin=max(16,size // 128)
		base=target.name.replace("_S-Remesh", "")
		ext=max(target.dimensions) or 1.0
		drift=_worst_drift(target,src_obj)
		cage=min(max(drift * 1.5,ext * 0.0005),ext * 0.01)
		ray=cage * 1.2
		prev_uv=(target.data.uv_layers.active.name if target.data.uv_layers.active else "")
		for o in context.selected_objects:
			o.select_set(False)
		target.select_set(True)
		context.view_layer.objects.active=target
		keep_uv=st.uv_keep_islands and bool(target.data.uv_layers)
		if keep_uv:
			uv=next((l for l in target.data.uv_layers if l.active_render),target.data.uv_layers[0])
			target.data.uv_layers.active=uv
			uv.active_render=True
		else:
			uv=target.data.uv_layers.new(name="BakeUV")
			target.data.uv_layers.active=uv
			uv.active_render=True
			bpy.ops.object.mode_set(mode="EDIT")
			bpy.ops.mesh.select_all(action="SELECT")
			saved_seams=[e.use_seam for e in target.data.edges]
			bpy.ops.uv.smart_project(angle_limit=math.radians(45.0),island_margin=0.001,correct_aspect=True,scale_to_bounds=False)
			bpy.ops.uv.seams_from_islands()
			def overlapping():
				bpy.ops.mesh.select_all(action="DESELECT")
				bpy.ops.uv.select_all(action="DESELECT")
				bpy.ops.uv.select_overlap()
				bpy.ops.object.mode_set(mode="OBJECT")
				n=sum(1 for f in target.data.polygons if f.select)
				bpy.ops.object.mode_set(mode="EDIT")
				return n
			try:
				for _round in range(4):
					if not overlapping():
						break
					bpy.ops.mesh.region_to_loop()
					bpy.ops.mesh.mark_seam(clear=False)
					bpy.ops.mesh.select_all(action="SELECT")
					bpy.ops.uv.unwrap(method="ANGLE_BASED",margin=0.001)
			except RuntimeError:
				pass
			bpy.ops.mesh.select_all(action="SELECT")
			try:
				bpy.ops.uv.average_islands_scale()
			except RuntimeError:
				pass
			try:
				bpy.ops.uv.pack_islands(rotate=True,scale=True,merge_overlap=False,margin=0.002,margin_method="FRACTION",shape_method="CONCAVE")
			except TypeError:
				bpy.ops.uv.pack_islands(rotate=True,margin=0.002)
			bpy.ops.object.mode_set(mode="OBJECT")
			for e,was in zip(target.data.edges,saved_seams):
				e.use_seam=was
		tiles=_uv_tiles(target.data,uv) if keep_uv else [1001]
		mat=bpy.data.materials.new(base + "_Baked")
		mat.use_nodes=True
		nodes=mat.node_tree.nodes
		links=mat.node_tree.links
		bsdf=nodes.get("Principled BSDF")
		color=_new_bake_image(base + "_Color",size,tiles, "sRGB")
		if keep_uv:
			_prefill_from_source(color,src_obj, "Base Color")
		n_col=nodes.new("ShaderNodeTexImage")
		n_col.image=color
		n_col.location=(-400,300)
		extra=[]
		height_node=None
		if st.bake_pbr:
			COLOR_SOCKETS={"Emission Color", "Subsurface Radius","Coat Tint", "Sheen Tint", "Specular Tint"}
			driven=[]
			seen=set()
			for slot in src_obj.material_slots:
				m=slot.material
				if not (m and m.use_nodes):
					continue
				b=next((n for n in m.node_tree.nodes if n.type== "BSDF_PRINCIPLED"),None)
				if b is None:
					continue
				for inp in b.inputs:
					if inp.name in ("Base Color", "Normal", "切线","Coat Normal", "Weight"):
						continue
					if inp.type not in ("VALUE", "RGBA"):
						continue
					if inp.is_linked and inp.name not in seen:
						seen.add(inp.name)
						driven.append(inp.name)
				if ("Emission Color" in b.inputs
						and "Emission Color" not in seen):
					e=b.inputs["Emission Color"]
					st_=b.inputs.get("Emission Strength")
					if st_ and st_.default_value > 0 \
							and max(e.default_value[:3]) > 0:
						seen.add("Emission Color")
						driven.append("Emission Color")
				out=next((n for n in m.node_tree.nodes if n.type== "OUTPUT_MATERIAL"),None)
				if out and out.inputs["Displacement"].is_linked \
						and "Height" not in seen:
					seen.add("Height")
					driven.append("Height")
			y=-350
			for sock in driven:
				suffix= "_" + sock.replace(" ", "")
				img=_new_bake_image(base + suffix,size,tiles,"sRGB" if sock in COLOR_SOCKETS else "Non-Color")
				if keep_uv:
					_prefill_from_source(img,src_obj,sock)
				node=nodes.new("ShaderNodeTexImage")
				node.image=img
				node.location=(-400,y)
				y -=250
				if sock== "Height":
					height_node=node
				else:
					extra.append((sock,node))
		n_nrm=None
		if st.bake_pbr:
			normal=_new_bake_image(base + "_Normal",size,tiles,"Non-Color")
			if keep_uv:
				_prefill_from_source(normal,src_obj, "Normal")
			n_nrm=nodes.new("ShaderNodeTexImage")
			n_nrm.image=normal
			n_nrm.location=(-600,-100)
			nmap=nodes.new("ShaderNodeNormalMap")
			nmap.location=(-300,-100)
			links.new(n_nrm.outputs["Color"],nmap.inputs["Color"])
			links.new(nmap.outputs["Normal"],bsdf.inputs["Normal"])
		old_mats=[m for m in target.data.materials]
		target[BAKE_UNDO_MATS]=[m.name if m else "" for m in old_mats]
		target[BAKE_UNDO_UV]=prev_uv
		target.data.materials.clear()
		target.data.materials.append(mat)
		engine=scene.render.engine
		bake=scene.render.bake
		cage_obj=None
		cyc=scene.cycles
		saved=(bake.use_selected_to_active,bake.cage_extrusion,bake.max_ray_distance,bake.use_pass_direct,bake.use_pass_indirect,bake.use_pass_color,bake.margin)
		saved_cyc=(cyc.device,cyc.samples,cyc.use_denoising)
		shadings=[]
		for area in context.screen.areas:
			if area.type== "VIEW_3D":
				sp=area.spaces.active
				shadings.append((sp,sp.shading.type))
				sp.shading.type= "SOLID"
		try:
			scene.render.engine= "CYCLES"
			cyc.device= "CPU"
			cyc.samples=1
			cyc.use_denoising=False
			src_obj.hide_set(False)
			src_obj.hide_render=False
			src_obj.select_set(True)
			target.select_set(True)
			context.view_layer.objects.active=target
			cage_obj,ray=_build_cage(target,src_obj,cage)
			bake.use_selected_to_active=True
			bake.use_cage=cage_obj is not None
			if cage_obj is not None:
				bake.cage_object=cage_obj
			bake.cage_extrusion=cage
			bake.max_ray_distance=ray
			bake.margin=margin
			try:
				bake.margin_type= "ADJACENT_FACES"
			except Exception:
				pass
			bake.use_pass_direct=False
			bake.use_pass_indirect=False
			bake.use_pass_color=True
			nodes.active=n_col
			restore=_bake_via_emission(src_obj, "Base Color",True)
			try:
				bpy.ops.object.bake(type="EMIT",use_selected_to_active=True,cage_extrusion=cage,max_ray_distance=ray,margin=margin)
			finally:
				restore()
			color.pack()
			jobs=list(extra)
			if height_node is not None:
				jobs.append(("Height",height_node))
			for sock,node in jobs:
				is_color=sock in COLOR_SOCKETS if st.bake_pbr else False
				restore=_bake_via_emission(src_obj,sock,is_color)
				try:
					nodes.active=node
					bpy.ops.object.bake(type="EMIT",use_selected_to_active=True,cage_extrusion=cage,max_ray_distance=ray,margin=margin)
					node.image.pack()
				finally:
					restore()
			if n_nrm is not None:
				nodes.active=n_nrm
				bpy.ops.object.bake(type="NORMAL",use_selected_to_active=True,cage_extrusion=cage,max_ray_distance=ray,margin=margin)
				n_nrm.image.pack()
		except Exception as e:
			target.data.materials.clear()
			for m in old_mats:
				target.data.materials.append(m)
			GR(self,"ERROR",f"bake failed: {e}")
			return {"CANCELLED"}
		finally:
			bake.use_cage=False
			bake.cage_object=None
			if cage_obj is not None:
				cm=cage_obj.data
				bpy.data.objects.remove(cage_obj,do_unlink=True)
				if cm.users==0:
					bpy.data.meshes.remove(cm)
			scene.render.engine=engine
			(bake.use_selected_to_active,bake.cage_extrusion,bake.max_ray_distance,bake.use_pass_direct,bake.use_pass_indirect,bake.use_pass_color,bake.margin)=saved
			cyc.device,cyc.samples,cyc.use_denoising=saved_cyc
			links.new(n_col.outputs["Color"],bsdf.inputs["Base Color"])
			for sock,node in extra:
				if sock in bsdf.inputs:
					links.new(node.outputs["Color"],bsdf.inputs[sock])
					if sock== "Emission Color" and "Emission Strength" in bsdf.inputs:
						bsdf.inputs["Emission Strength"].default_value=1.0
			if height_node is not None:
				out=next((n for n in nodes if n.type== "OUTPUT_MATERIAL"),None)
				if out is not None:
					disp=nodes.new("ShaderNodeDisplacement")
					disp.location=(0,-900)
					disp.inputs["Scale"].default_value=\
						_source_disp_scale(src_obj)
					links.new(height_node.outputs["Color"],disp.inputs["Height"])
					links.new(disp.outputs["Displacement"],out.inputs["Displacement"])
			for sp,kind in shadings:
				sp.shading.type=kind
			if temp is not None:
				bpy.data.objects.remove(temp,do_unlink=True)
			else:
				src_obj.select_set(False)
			target.select_set(True)
			context.view_layer.objects.active=target
		GR(self,"INFO",f"baked {size}x{size} onto {target.name}")
		return {"FINISHED"}
class QUADREMESH_OT_drop_original(Operator):
	"""全部返回：撤消该对象上的每个拖放和每个确认."""
	bl_idname= "mesh.quadremesh_drop_original";bl_label=g("Back To Start");bl_description=("回到首先之前的网格\n 落下，擦拭途中的每个确认阶段");bl_options={"REGISTER", "UNDO"}
	@classmethod
	def poll(cls,context):
		o=context.active_object
		return o is not None and o.type== "MESH" and bool(o.get(PZ_FIRST_KEY))
	def execute(self,context):
		st=context.scene.quadremesh_lines
		obj=context.active_object
		first=bpy.data.meshes.get(obj.get(PZ_FIRST_KEY) or "")
		if first is None:
			obj.pop(PZ_FIRST_KEY,None)
			GR(self,"WARNING", "nothing stored to go back to")
			return {"CANCELLED"}
		editing=obj.mode== "EDIT"
		if editing:
			bpy.ops.object.mode_set(mode="OBJECT")
		before=len(obj.data.polygons)
		bm=bmesh.new()
		bm.from_mesh(first)
		bm.to_mesh(obj.data)
		bm.free()
		obj.data.update()
		for key in (PZ_DROP_KEY,PZ_FIRST_KEY):
			stored=bpy.data.meshes.get(obj.get(key) or "")
			obj.pop(key,None)
			if stored is not None:
				stored.use_fake_user=False
				if stored.users==0:
					bpy.data.meshes.remove(stored)
		if editing:
			bpy.ops.object.mode_set(mode="EDIT")
		with suspend_live():
			st.pz_useless=1.0
			st.pz_every=0
			st.pz_keep_marked=True
			st.pz_axis_x=st.pz_axis_y=st.pz_axis_z=True
		st.build_info=(f"back to start  |  {before} -> "
						 f"{len(obj.data.polygons)} faces")
		GR(self,"INFO",st.build_info)
		return {"FINISHED"}
class QUADREMESH_OT_drop_confirm(Operator):
	"""接受跌落，并制作成为新建开始点."""
	bl_idname= "mesh.quadremesh_drop_confirm";bl_label=g("Confirm");bl_description=("保留当前结果。滑块从从\n 在这里，因此下一个拖放堆栈在顶部，而不是重做 " "this one");bl_options={"REGISTER", "UNDO"}
	@classmethod
	def poll(cls,context):
		o=context.active_object
		return o is not None and o.type== "MESH" and bool(o.get(PZ_DROP_KEY))
	def execute(self,context):
		st=context.scene.quadremesh_lines
		obj=context.active_object
		base=bpy.data.meshes.get(obj.get(PZ_DROP_KEY) or "")
		obj.pop(PZ_DROP_KEY,None)
		if base is not None:
			base.use_fake_user=False
			if base.users==0:
				bpy.data.meshes.remove(base)
		st.build_info=f"confirmed at {len(obj.data.polygons)} faces"
		GR(self,"INFO",st.build_info)
		return {"FINISHED"}
class QUADREMESH_OT_drop_reset(Operator):
	"""放回所有东西删除无用的循环."""
	bl_idname= "mesh.quadremesh_drop_reset";bl_label=g("Reset");bl_description= "撤消删除此对象上的无用循环";bl_options={"REGISTER", "UNDO"}
	@classmethod
	def poll(cls,context):
		o=context.active_object
		return o is not None and o.type== "MESH" and bool(o.get(PZ_DROP_KEY))
	def execute(self,context):
		st=context.scene.quadremesh_lines
		obj=context.active_object
		base=bpy.data.meshes.get(obj.get(PZ_DROP_KEY) or "")
		if base is None:
			obj.pop(PZ_DROP_KEY,None)
			GR(self,"WARNING", "nothing stored to go back to")
			return {"CANCELLED"}
		editing=obj.mode== "EDIT"
		if editing:
			bpy.ops.object.mode_set(mode="OBJECT")
		before=len(obj.data.polygons)
		bm=bmesh.new()
		bm.from_mesh(base)
		bm.to_mesh(obj.data)
		bm.free()
		obj.data.update()
		obj.pop(PZ_DROP_KEY,None)
		base.use_fake_user=False
		if base.users==0:
			bpy.data.meshes.remove(base)
		if editing:
			bpy.ops.object.mode_set(mode="EDIT")
		with suspend_live():
			st.pz_useless=1.0
			st.pz_every=0
			st.pz_keep_marked=True
			st.pz_axis_x=st.pz_axis_y=st.pz_axis_z=True
		st.build_info=f"drop reset  |  {before} -> {len(obj.data.polygons)} faces"
		GR(self,"INFO",st.build_info)
		return {"FINISHED"}
class QUADREMESH_OT_min_valence(Operator):
	"""移除每个少于三条边的顶点."""
	bl_idname= "mesh.quadremesh_min_valence";bl_label=g("At Least 3 Edges");bl_description=("清理外面每个顶点少于三个边：\n 将删除杂散点和马刺，并删除顶点 " "sitting between just two edges is dissolved");bl_options={"REGISTER", "UNDO"}
	@classmethod
	def poll(cls,context):
		o=context.active_object
		return o is not None and o.type== "MESH" and len(o.data.vertices)
	def execute(self,context):
		st=context.scene.quadremesh_lines
		obj=context.active_object
		editing=obj.mode== "EDIT"
		if editing:
			bpy.ops.object.mode_set(mode="OBJECT")
		bm=bmesh.new()
		bm.from_mesh(obj.data)
		bm.verts.ensure_lookup_table()
		before=len(bm.verts)
		got=PZ.min_three_edges(bm)
		bm.to_mesh(obj.data)
		bm.free()
		obj.data.update()
		if editing:
			bpy.ops.object.mode_set(mode="EDIT")
		st.build_info=(f"{before} -> {len(obj.data.vertices)} verts  |  " f"{got['loose']} stray,{got['spurs']} spurs, " f"{got['two_edge']} two-edge")
		if got["of_those_on_a_curve"]:
			st.build_info +=(f"  |  {got['of_those_on_a_curve']} of those sat " "on a curve and joining them squares it off")
			GR(self,"WARNING",st.build_info)
		else:
			GR(self,"INFO",st.build_info)
		return {"FINISHED"}
class QUADREMESH_PT_lines(Panel):
	bl_idname="QUADREMESH_PT_lines";bl_label= "";bl_space_type= "VIEW_3D";bl_region_type="UI";bl_category=TB;bl_parent_id="SMART_REMESH_PT_M";bl_order=20
	def draw_header(S,_):GL(S.layout,"Smart Remesh (Hardsurface)")
	def draw(self,context):
		layout=self.layout
		st=context.scene.quadremesh_lines
		row=layout.row(align=True)
		row.scale_y=1.4
		GO(row,"mesh.quadremesh_panels_build",text="Remesh Hardsurface",icon="MESH_GRID")
		row.operator("mesh.quadremesh_restore",text="",icon="LOOP_BACK")
		row.operator("mesh.quadremesh_lines_clear",text="",icon="X")
		GP(layout,st, "hs_replace",text="Replace Original")
		row=layout.row(align=True)
		GP(row,st, "hs_mirror",text="Mirror Retopology")
		if st.hs_mirror:
			row.prop(st, "hs_mirror_axis",text="")
		GP(layout,st, "hs_wireframe",text="Show Wireframe")
		layout.separator()
		row=layout.row()
		GO(row,"mesh.quadremesh_reset_all",text="Reset Everything",icon="FILE_REFRESH")
		if st.source:
			GL(layout,f"Source: {st.source}",icon="MESH_DATA")
		row=layout.row(align=True)
		row.prop(st, "preset",text="")
		row.operator("mesh.quadremesh_preset_save",text="",icon="ADD")
		row.operator("mesh.quadremesh_preset_delete",text="",icon="REMOVE")
		col=layout.column(align=True)
		GP(col,st, "auto_thresholds",text="Automatic")
		sub=col.column(align=True)
		sub.enabled=not st.auto_thresholds
		GP(sub,st, "crease_deg",text="Crease")
		GP(sub,st, "flat_deg",text="Coplanar")
		layout.separator()
		col=layout.column(align=True)
		GP(col,st, "auto_prune",text="Drop Lines That Change Nothing")
		GP(col,st, "weld_close",text="Weld Close Lines")
		GP(col,st, "dissolve_straight",text="Remove Straight Loops")
		GP(col,st, "refit_circles",text="Keep Circles Round")
		GP(col,st, "min_chain",text="Min Length")
		GP(col,st, "use_type",text="Flat/Curved Boundaries")
		GP(col,st, "close_gaps",text="Close Gaps")
		sub=col.row()
		sub.enabled=st.close_gaps
		GP(sub,st, "gap_span",text="Gap Reach")
		layout.separator()
		box=layout.box()
		GL(box,"Smart Cleanup",icon="EDGESEL")
		col=box.column(align=True)
		GP(col,st, "hs_use_marked",text="Include My Lines")
		GP(col,st, "hs_only_marked",text="Only My Lines")
		col.separator()
		r=col.row()
		r.scale_y=1.3
		GO(r,"mesh.quadremesh_clean_between",text="Clean Between Lines",icon="MOD_DECIM")
		r.operator("mesh.quadremesh_clean_confirm",text="",icon="CHECKMARK")
		r.operator("mesh.quadremesh_clean_reset",text="",icon="LOOP_BACK")
		GP(col,st, "pz_amount",slider=True)
		GP(col,st, "pz_confine",text="Stay Inside Lines")
		GO(col,"mesh.quadremesh_clean_revert_all",text="Revert All Cleaning",icon="TRASH")
		GL(col,"or press Remesh Hardsurface above")
		layout.separator()
		box=layout.box()
		GL(box,"UV",icon="UV")
		GP(box,st, "uv_keep_islands",text="Bake Into Existing UV")
		GP(box,st, "uv_show_seams",text="Show UV Seams")
		GP(box,st, "uv_seams_sharp",text="Seams As Sharp")
		box.separator()
		rbk=box.row(align=True)
		GO(rbk,"mesh.quadremesh_bake_from_original",text="Bake From Original",icon="RENDER_STILL")
		rbk.operator("mesh.quadremesh_unbake",text="",icon="LOOP_BACK")
		rb=box.row(align=True)
		rb.prop(st, "bake_size",text="")
		GP(rb,st, "bake_pbr",toggle=True)
		GL(box,"If the UV is stretched after a remesh,bake it.",icon="INFO")
		layout.separator()
		box=layout.box()
		GL(box,"Erase Useless Loops",icon="MOD_DECIM")
		sub=box.column(align=True)
		r4=sub.row(align=True)
		GO(r4,"mesh.quadremesh_drop_useless",text="Drop Useless Loops",icon="MOD_DECIM")
		r4.operator("mesh.quadremesh_drop_confirm",text="",icon="CHECKMARK")
		r4.operator("mesh.quadremesh_drop_reset",text="",icon="LOOP_BACK")
		GO(sub,"mesh.quadremesh_drop_original",text="Back To Start",icon="FILE_REFRESH")
		r3=sub.row(align=True)
		GP(r3,st, "pz_useless",text="Flat Below")
		GP(r3,st, "pz_keep_marked",toggle=True)
		GP(sub,st, "pz_every",text="Remove Per Kept")
		r5=sub.row(align=True)
		GL(r5,"Only Axis")
		GP(r5,st, "pz_axis_x",toggle=True)
		GP(r5,st, "pz_axis_y",toggle=True)
		GP(r5,st, "pz_axis_z",toggle=True)
		layout.separator()
		box=layout.box()
		GL(box,"Chamfer",icon="MOD_BEVEL")
		GP(box,st, "planar_tol",text="Flatten Below")
		GP(box,st, "straighten",text="Straighten")
		GP(box,st, "chamfer",text="Chamfer")
		sub=box.column(align=True)
		sub.enabled=st.chamfer > 0.0
		GP(sub,st, "chamfer_segments",text="Segments")
		if st.chamfer > 0.0 and st.chamfer_segments % 2:
			GL(sub,"odd count leaves corner triangles",icon="ERROR")
		GP(sub,st, "chamfer_profile",text="Profile")
		GP(sub,st, "chamfer_clamp",text="Clamp Overlap")
class QUADREMESH_PT_report(Panel):
	"""The numbers behind the last run.
	These used to sit open under the buttons,which is a lot of text to scroll
	past on every run when the answer you want is usually just the model in the
	viewport. Same information,one click away instead of always on screen.
	"""
	bl_idname= "QUADREMESH_PT_report";bl_label=g("Report");bl_space_type= "VIEW_3D";bl_region_type="UI";bl_category=TB;bl_parent_id="SMART_REMESH_PT_M";bl_parent_id= "QUADREMESH_PT_lines";bl_options={"DEFAULT_CLOSED"}
	@classmethod
	def poll(cls,context):
		st=context.scene.quadremesh_lines
		return bool(st.info or st.panel_info or st.build_info)
	def draw(self,context):
		layout=self.layout
		st=context.scene.quadremesh_lines
		for text,title,icon in ((st.info, "Lines", "MOD_EDGESPLIT"),(st.panel_info, "Panels", "FACESEL"),(st.build_info, "Built Mesh", "MESH_GRID")):
			if not text:
				continue
			box=layout.box()
			GL(box,title,icon=icon)
			for part in text.split("|"):
				GL(box,part.strip())
CLASSES=(QuadRemeshLines,QUADREMESH_OT_lines_preview,QUADREMESH_OT_panelize_mark,QUADREMESH_OT_clean_between,QUADREMESH_OT_clean_reset,QUADREMESH_OT_clean_confirm,QUADREMESH_OT_drop_useless,QUADREMESH_OT_bake_from_original,QUADREMESH_OT_unbake,QUADREMESH_OT_force_loop,QUADREMESH_OT_drop_original,QUADREMESH_OT_drop_confirm,QUADREMESH_OT_drop_reset,QUADREMESH_OT_min_valence,QUADREMESH_OT_clean_revert_all,QUADREMESH_OT_panels_preview,QUADREMESH_OT_panels_build,QUADREMESH_OT_lines_clear,QUADREMESH_OT_preset_save,QUADREMESH_OT_preset_delete,QUADREMESH_PT_lines,QUADREMESH_PT_report)
def register():
	load_user_presets()
	RCL(CLASSES)
	SAF(setattr,bpy.types.Scene,'quadremesh_lines',bpy.props.PointerProperty(type=QuadRemeshLines))
def unregister():
	if hasattr(bpy.types.Scene, "quadremesh_lines"):
		DAS("quadremesh_lines","Scene")
	for c in reversed(CLASSES):
		try:
			UCL(c)
		except Exception:
			pass
	_CACHE.clear()