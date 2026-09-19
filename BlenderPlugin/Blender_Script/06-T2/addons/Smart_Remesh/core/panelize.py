from __future__ import annotations
from ..G import *
"""Dissolve everything between lines the user marked,leaving flat panels.
The rest of Hardsurface decides for itself which edges carry shape. This is
the manual counterpart: the user says where the panel borders are,and every
edge that is not one of them goes. What is left is one n-gon per region.
Nothing here moves a vertex. Dissolving an edge only removes it,so the
silhouette and every kept line stay exactly where they were - the only thing
that changes is a region that was not flat,which becomes a single n-gon and
therefore reads as flat. `protect_angle` exists for that case.
"""
import math,bmesh
STRAIGHT=math.radians(179.0)
CONTINUES=math.radians(160.0)
def planar_groups(bm,tol_deg,flat_dist):
	import math
	from mathutils import Vector
	cos_tol=math.cos(math.radians(tol_deg))
	group={}
	for seed in bm.faces:
		if seed.index in group:
			continue
		gid=len(set(group.values())) if group else 0
		gid=seed.index
		n0=seed.normal.copy()
		if n0.length < 1e-12:
			group[seed.index]=gid
			continue
		d0=n0.dot(seed.calc_center_median())
		stack=[seed]
		group[seed.index]=gid
		while stack:
			f=stack.pop()
			for e in f.edges:
				for g in e.link_faces:
					if g.index in group:
						continue
					ng=g.normal
					if ng.length < 1e-12 or ng.dot(n0) < cos_tol:
						continue
					if max(abs(n0.dot(v.co) - d0) for v in g.verts) > flat_dist:
						continue
					group[g.index]=gid
					stack.append(g)
	return group
def keepers(bm,*,use_sharp=True,use_selection=True,keep_boundary=True,keep_creased=True,protect_angle=0.0,keep_seams=False,flat_dist=None):
	keep=set()
	crease=bm.edges.layers.float.get("crease_edge")
	groups=None
	if protect_angle > 0:
		if flat_dist is None:
			xs=[v.co for v in bm.verts]
			if xs:
				span=max(max(p[i] for p in xs) - min(p[i] for p in xs)
						   for i in range(3))
				flat_dist=span * 0.0002
			else:
				flat_dist=1e-4
		groups=planar_groups(bm,protect_angle,flat_dist)
	for e in bm.edges:
		n=len(e.link_faces)
		if n !=2:
			if keep_boundary or n > 2:
				keep.add(e.index)
			continue
		if use_sharp and not e.smooth:
			keep.add(e.index); continue
		if use_selection and e.select:
			keep.add(e.index); continue
		if keep_seams and e.seam:
			keep.add(e.index); continue
		if keep_creased and crease is not None and e[crease] > 0.0:
			keep.add(e.index); continue
		if groups is not None:
			a,b=e.link_faces[0].index,e.link_faces[1].index
			if groups.get(a) !=groups.get(b):
				keep.add(e.index)
	return keep
def panelize(bm,keep,*,dissolve_verts=True):
	doomed=[e for e in bm.edges if e.index not in keep]
	before_e,before_f,before_v=len(bm.edges),len(bm.faces),len(bm.verts)
	area_before=sum(f.calc_area() for f in bm.faces)
	if doomed:
		bmesh.ops.dissolve_edges(bm,edges=doomed,use_verts=dissolve_verts,use_face_split=False)
	bm.normal_update()
	return {"edges_removed": before_e - len(bm.edges),"faces_before": before_f,"faces_after": len(bm.faces),"verts_removed": before_v - len(bm.verts), "lines_kept": len(keep),"area_before": area_before, "area_after": sum(f.calc_area() for f in bm.faces),}
def count_marked(bm,*,use_sharp=True,use_selection=True):
	sharp=sum(1 for e in bm.edges if not e.smooth and len(e.link_faces)==2)
	sel=sum(1 for e in bm.edges if e.select and len(e.link_faces)==2)
	return {"sharp": sharp, "selected": sel, "usable": (sharp if use_sharp else 0) + (sel if use_selection else 0)}
def bounds(bm):
	if not bm.verts:
		return None
	lo=[min(v.co[i] for v in bm.verts) for i in range(3)]
	hi=[max(v.co[i] for v in bm.verts) for i in range(3)]
	return lo,hi
def check(bm,before,res,*,area_drop=0.35,span_shrink=0.10):
	if res["faces_after"]==0:
		return ("Every face was removed. The regions between your lines had \n nothing holding them open - Ctrl+Z,then mark more lines or " "raise Protect Above.")
	a0=res.get("area_before",0.0)
	a1=res.get("area_after",0.0)
	if a0 > 0 and (a0 - a1) / a0 > area_drop:
		pct=100 * (a0 - a1) / a0
		return (f"{pct:.0f}% of the surface is gone - a region collapsed " "instead of merging. Ctrl+Z if that was not what you wanted.")
	after=bounds(bm)
	if before is None or after is None:
		return "The mesh came out empty."
	for i,axis in enumerate("XYZ"):
		span_b=before[1][i] - before[0][i]
		span_a=after[1][i] - after[0][i]
		if span_b > 1e-12 and (span_b - span_a) / span_b > span_shrink:
			pct=100 * (span_b - span_a) / span_b
			return (f"The model shrank {pct:.0f}% on {axis} - a region " "collapsed instead of merging. Ctrl+Z if that was not " "what you wanted.")
	return ""
def inside_marked_loops(bm,*,use_sharp=True,use_selection=True):
	marked=set()
	for e in bm.edges:
		if len(e.link_faces) !=2:
			continue
		if use_sharp and not e.smooth:
			marked.add(e.index)
		elif use_selection and e.select:
			marked.add(e.index)
	if not marked:
		return set(),0
	region={}
	groups=[]
	for seed in bm.faces:
		if seed.index in region:
			continue
		gid=len(groups)
		stack=[seed]
		region[seed.index]=gid
		faces=[]
		while stack:
			f=stack.pop()
			faces.append(f)
			for e in f.edges:
				if e.index in marked:
					continue
				for g in e.link_faces:
					if g.index not in region:
						region[g.index]=gid
						stack.append(g)
		groups.append(faces)
	body_limit=0.4 * len(bm.faces)
	doomed=set()
	kept_regions=0
	for gid,faces in enumerate(groups):
		if len(faces) > body_limit:
			continue
		idx={f.index for f in faces}
		interior=set()
		enclosed=True
		for f in faces:
			for e in f.edges:
				if e.index in marked:
					continue
				if len(e.link_faces) !=2:
					enclosed=False
					break
				a,b=e.link_faces
				if a.index in idx and b.index in idx:
					interior.add(e.index)
			if not enclosed:
				break
		if enclosed and interior:
			doomed |=interior
			kept_regions +=1
	return doomed,kept_regions
def enclosed_interior(bm,*,require_selected=False):
	region={}
	groups=[]
	for seed in bm.faces:
		if seed.index in region:
			continue
		gid=len(groups)
		stack=[seed]
		region[seed.index]=gid
		faces=[]
		while stack:
			f=stack.pop()
			faces.append(f)
			for e in f.edges:
				if e.tag:
					continue
				for g in e.link_faces:
					if g.index not in region:
						region[g.index]=gid
						stack.append(g)
		groups.append(faces)
	order=sorted(range(len(groups)),key=lambda i: len(groups[i]),reverse=True)
	body=order[0] if len(order) > 1 else None
	doomed=set()
	for gi,faces in enumerate(groups):
		if gi==body:
			continue
		if require_selected:
			touched=any(e.select for f in faces for e in f.edges)
			if not touched:
				continue
		idx={f.index for f in faces}
		interior=set()
		ok=True
		for f in faces:
			for e in f.edges:
				if e.tag:
					continue
				if len(e.link_faces) !=2:
					continue
				a,b=e.link_faces
				if a.index in idx and b.index in idx:
					interior.add(e)
			if not ok:
				break
		if ok:
			doomed |=interior
	return doomed
def _next_in_loop(e,v):
	le=v.link_edges
	if len(le) !=4:
		return None
	ef=e.link_faces
	if len(ef)==2:
		f0,f1=ef[0],ef[1]
	elif len(ef)==1:
		f0=f1=ef[0]
	else:
		return None
	for o in le:
		if o is e:
			continue
		shared=False
		for f in o.link_faces:
			if f is f0 or f is f1:
				shared=True
				break
		if not shared:
			return o
	return None
def edge_loops(edges):
	pool=set(edges)
	loops=[]
	while pool:
		seed=pool.pop()
		loop=[seed]
		for start_vert in (seed.verts[0],seed.verts[1]):
			cur,v=seed,start_vert
			while True:
				nxt=_next_in_loop(cur,v)
				if nxt is None:
					break
				if nxt is seed or nxt not in pool:
					break
				pool.discard(nxt)
				loop.append(nxt)
				v=nxt.other_vert(v)
				cur=nxt
		loops.append(loop)
	return loops
def _loop_error(loop):
	worst=0.0
	for e in loop:
		for v in e.verts:
			across=[o for o in v.link_edges if o not in loop]
			if len(across) !=2:
				continue
			a=across[0].other_vert(v).co - v.co
			b=across[1].other_vert(v).co - v.co
			if a.length < 1e-12 or b.length < 1e-12:
				continue
			worst=max(worst,math.pi - a.angle(b))
	return worst
def _adjacent(loops):
	owner={}
	for i,loop in enumerate(loops):
		for e in loop:
			for f in e.link_faces:
				owner.setdefault(f.index,set()).add(i)
	near={i: set() for i in range(len(loops))}
	for shared in owner.values():
		for i in shared:
			near[i] |=shared - {i}
	return near
def thin_out(edges,percent):
	if percent >=100.0:
		return set(edges)
	if percent <=0.0:
		return set()
	loops=edge_loops(edges)
	order=sorted(range(len(loops)),
				   key=lambda i: (_loop_error(set(loops[i])),min(e.index for e in loops[i])))
	near=_adjacent(loops)
	want=len(edges) * percent / 100.0
	taken=set()
	out=set()
	for blocking in (True,False):
		progress=True
		while progress and len(out) < want:
			progress=False
			for i in order:
				if len(out) >=want:
					break
				if i in taken:
					continue
				if blocking and (near[i] & taken):
					continue
				taken.add(i)
				out.update(loops[i])
				progress=True
	return out
def merge_flat(bm,faces,angle_deg):
	if angle_deg <=0.0 or not faces:
		return 0
	keep={f.index for f in faces}
	edges=[e for e in bm.edges if len(e.link_faces)==2 and not e.tag and all(f.index in keep for f in e.link_faces)]
	if not edges:
		return 0
	verts={v for e in edges for v in e.verts}
	before=len(bm.faces)
	bmesh.ops.dissolve_limit(bm,angle_limit=math.radians(angle_deg),use_dissolve_boundaries=False,verts=list(verts),edges=edges,delimit={"NORMAL"})
	bm.normal_update()
	return before - len(bm.faces)
def region_faces(bm,require_selected=True):
	region={}
	groups=[]
	for seed in bm.faces:
		if seed.index in region:
			continue
		gid=len(groups)
		stack=[seed]
		region[seed.index]=gid
		faces=[]
		while stack:
			f=stack.pop()
			faces.append(f)
			for e in f.edges:
				if e.tag:
					continue
				for g in e.link_faces:
					if g.index not in region:
						region[g.index]=gid
						stack.append(g)
		groups.append(faces)
	if len(groups) < 2:
		return []
	body=max(range(len(groups)),key=lambda i: len(groups[i]))
	out=[]
	for gi,faces in enumerate(groups):
		if gi==body:
			continue
		if require_selected and not any(e.select for f in faces for e in f.edges):
			continue
		out +=faces
	return out
def _ring_of(faces):
	idx={f.index for f in faces}
	border=[]
	for f in faces:
		for e in f.edges:
			if len(e.link_faces) !=2:
				border.append(e)
			elif any(g.index not in idx for g in e.link_faces):
				border.append(e)
	border=list(dict.fromkeys(border))
	if len(border) < 3:
		return None
	link={}
	for e in border:
		for v in e.verts:
			link.setdefault(v,[]).append(e)
	if any(len(v) !=2 for v in link.values()):
		return None
	start=border[0]
	ring=[start.verts[0],start.verts[1]]
	cur,prev=start,ring[1]
	while True:
		nxt=next((e for e in link[prev] if e is not cur),None)
		if nxt is None:
			return None
		v=nxt.other_vert(prev)
		if v is ring[0]:
			break
		ring.append(v)
		cur,prev=nxt,v
		if len(ring) > len(border):
			return None
	return ring if len(ring)==len(border) else None
def fan_to_centre(bm,faces,snap=None):
	ring=_ring_of(faces)
	if ring is None or len(ring) < 3:
		return 0
	mid=ring[0].co.copy()
	for v in ring[1:]:
		mid=mid + v.co
	mid=mid / len(ring)
	if snap is not None:
		nrm=None
		for f in faces:
			n=f.normal
			if n.length > 1e-12:
				nrm=n.copy() if nrm is None else nrm + n
		if nrm is not None and nrm.length > 1e-12:
			nrm.normalize()
			best=None
			for direction in (nrm,-nrm):
				hit=snap.ray_cast(mid - direction * 1e-4,direction)
				if hit and hit[0] is not None:
					d=(hit[0] - mid).length
					if best is None or d < best[1]:
						best=(hit[0],d)
			if best is not None:
				mid=best[0]
			else:
				near=snap.find_nearest(mid)
				if near and near[0] is not None:
					mid=near[0]
	before=len(bm.faces)
	bmesh.ops.delete(bm,geom=list(faces),context="FACES")
	centre=bm.verts.new(mid)
	bm.verts.index_update()
	for i,v in enumerate(ring):
		w=ring[(i + 1) % len(ring)]
		try:
			bm.faces.new((v,w,centre))
		except ValueError:
			pass
	bm.normal_update()
	return before - len(bm.faces)
def heal_stubs(bm,*,straight_deg=170.0,confine=None,overrun=10):
	limit=math.radians(straight_deg)
	def stub_at(v):
		es=list(v.link_edges)
		if len(es) !=3:
			return None
		def usable(e):
			return not e.tag and len(e.link_faces)==2
		free=[e for e in es if not e.tag]
		if len(free)==1 and usable(free[0]):
			return free[0]
		sizes=sorted((len(f.verts) for f in v.link_faces),reverse=True)
		if len(v.link_faces)==3 and sizes[0] > 4:
			ranked=sorted((e for e in es if usable(e)),
				key=lambda e: -sum(len(f.verts) for f in e.link_faces))
			if ranked and sum(len(f.verts) for f in ranked[0].link_faces) > 8:
				return ranked[0]
		best=None
		for i in range(3):
			for j in range(i + 1,3):
				a=es[i].other_vert(v).co - v.co
				b=es[j].other_vert(v).co - v.co
				if a.length < 1e-12 or b.length < 1e-12:
					continue
				ang=a.angle(b)
				if best is None or ang > best[0]:
					best=(ang,3 - i - j)
		if best is None or best[0] < limit:
			return None
		e=es[best[1]]
		return e if usable(e) else None
	doomed=set()
	for v in list(bm.verts):
		e=stub_at(v)
		if e is None or e in doomed:
			continue
		run=[e]
		outside=0 if (confine is None or e in confine) else 1
		cur,at=e,e.other_vert(v)
		finished=True
		while True:
			nxt=_next_in_loop(cur,at)
			if nxt is None or nxt.tag or nxt in doomed:
				break
			if len(nxt.link_faces) !=2:
				break
			if confine is not None and nxt not in confine:
				outside +=1
				if outside > overrun:
					finished=False
					break
			run.append(nxt)
			at=nxt.other_vert(at)
			cur=nxt
		if finished:
			doomed.update(run)
	if doomed:
		dissolve_keeping_rims(bm,doomed)
	return len(doomed)
def _parallel_adjacent(loops):
	owner={}
	for i,loop in enumerate(loops):
		for e in loop:
			for f in e.link_faces:
				owner.setdefault(f,[]).append((i,e))
	near={i: set() for i in range(len(loops))}
	for f,entries in owner.items():
		if len(entries) < 2 or len(f.edges) !=4:
			continue
		ring=list(f.edges)
		for a in range(len(entries)):
			for b in range(a + 1,len(entries)):
				ia,ea=entries[a]
				ib,eb=entries[b]
				if ia==ib:
					continue
				try:
					if abs(ring.index(ea) - ring.index(eb))==2:
						near[ia].add(ib)
						near[ib].add(ia)
				except ValueError:
					pass
	return near
def thin_alternate(edges,percent=100.0):
	loops=edge_loops(edges)
	if not loops:
		return set()
	near=_parallel_adjacent(loops)
	colour={}
	order=[]
	for seed in range(len(loops)):
		if seed in colour:
			continue
		colour[seed]=0
		queue=[seed]
		while queue:
			i=queue.pop(0)
			order.append(i)
			for j in near[i]:
				if j not in colour:
					colour[j]=1 - colour[i]
					queue.append(j)
	picks=[i for i in order if colour[i]==0]
	if percent < 100.0:
		picks=picks[:int(round(len(picks) * max(percent,0.0) / 100.0))]
	out=set()
	for i in picks:
		out.update(loops[i])
	return out
def dissolve_keeping_rims(bm,doomed,region=None,sag_limit=0.0,polish=False):
	if not doomed:
		return
	bmesh.ops.dissolve_edges(bm,edges=list(doomed),use_verts=False,use_face_split=False)
	bm.normal_update()
	stranded=[]
	for v in bm.verts:
		es=list(v.link_edges)
		if len(es) !=2:
			continue
		if es[0].tag or es[1].tag:
			continue
		a=es[0].other_vert(v).co - v.co
		b=es[1].other_vert(v).co - v.co
		if a.length < 1e-12 or b.length < 1e-12:
			continue
		if polish:
			stranded.append(v)
			continue
		if a.angle(b) >=STRAIGHT:
			stranded.append(v)
		elif sag_limit > 0.0:
			ab=b - a
			n=ab.length
			if n > 1e-12:
				t=min(max((-a).dot(ab) / (n * n),0.0),1.0)
				if (-(a + ab * t)).length <=sag_limit:
					stranded.append(v)
	if stranded:
		bmesh.ops.dissolve_verts(bm,verts=stranded)
		bm.normal_update()
def parallel_chains(loops):
	near=_parallel_adjacent(loops)
	seen=set()
	chains=[]
	for start in range(len(loops)):
		if start in seen:
			continue
		end,guard=start,0
		prev=None
		while guard < len(loops):
			guard +=1
			nxt=[j for j in near[end] if j !=prev]
			if not nxt:
				break
			prev,end=end,nxt[0]
			if end==start:
				break
		chain,prev,cur=[],None,end
		while cur is not None and cur not in seen:
			seen.add(cur)
			chain.append(cur)
			nxt=[j for j in near[cur] if j !=prev and j not in seen]
			prev,cur=cur,(nxt[0] if nxt else None)
		if chain:
			chains.append(chain)
	return chains
def thin_regular(edges,percent):
	if percent >=100.0:
		return set(edges)
	if percent <=0.0:
		return set()
	loops=edge_loops(edges)
	if not loops:
		return set()
	out=set()
	for chain in parallel_chains(loops):
		n=len(chain)
		take=int(round(n * percent / 100.0))
		if take <=0:
			continue
		if take >=n:
			for i in chain:
				out.update(loops[i])
			continue
		step=n / take
		for k in range(take):
			out.update(loops[chain[min(int(k * step + step / 2),n - 1)]])
	return out
def thin_keep_every(edges,n):
	if n <=1:
		return set()
	loops=edge_loops(edges)
	if not loops:
		return set()
	out=set()
	for chain in parallel_chains(loops):
		for k,i in enumerate(chain):
			if k % n:
				out.update(loops[i])
	return out
def region_border(faces):
	idx={f.index for f in faces}
	border=[]
	for f in faces:
		for e in f.edges:
			if len(e.link_faces) !=2 or any(g.index not in idx for g in e.link_faces):
				border.append(e)
	border=list(dict.fromkeys(border))
	if len(border) < 4:
		return border,False
	at={}
	for e in border:
		for v in e.verts:
			at.setdefault(v,[]).append(e)
	single=all(len(v)==2 for v in at.values())
	return border,single
def rebuild_region(bm,faces,snap=None):
	border,single=region_border(faces)
	if not single or len(border) < 4:
		return 0
	if len(border) % 2:
		return 0
	before=len(faces)
	recipe=[[v for v in f.verts] for f in faces]
	bmesh.ops.delete(bm,geom=list(faces),context="FACES_ONLY")
	bm.verts.index_update()
	bm.edges.index_update()
	bm.faces.ensure_lookup_table()
	known={v.index for v in bm.verts}
	made=0
	try:
		n0=len(bm.faces)
		bmesh.ops.grid_fill(bm,edges=border,mat_nr=0,use_smooth=False,use_interp_simple=False)
		made=len(bm.faces) - n0
	except Exception:
		made=0
	if made <=0:
		for verts in recipe:
			if all(v.is_valid for v in verts):
				try:
					bm.faces.new(verts)
				except ValueError:
					pass
		bm.faces.ensure_lookup_table()
		bm.normal_update()
		return 0
	bm.normal_update()
	if snap is not None:
		for v in bm.verts:
			if v.index in known:
				continue
			hit=snap.find_nearest(v.co)
			if hit and hit[0] is not None:
				v.co=hit[0]
		bm.normal_update()
	return before
def min_three_edges(bm):
	loose=[v for v in bm.verts if len(v.link_edges)==0]
	spurs=[v for v in bm.verts if len(v.link_edges)==1]
	pairs=[v for v in bm.verts if len(v.link_edges)==2]
	bent=0
	for v in pairs:
		a,b=(e.other_vert(v).co - v.co for e in v.link_edges)
		if a.length > 1e-12 and b.length > 1e-12 and a.angle(b) < STRAIGHT:
			bent +=1
	if loose or spurs:
		bmesh.ops.delete(bm,geom=loose + spurs,context="VERTS")
		bm.verts.ensure_lookup_table()
		pairs=[v for v in bm.verts if len(v.link_edges)==2]
	if pairs:
		bmesh.ops.dissolve_verts(bm,verts=pairs)
	bm.normal_update()
	return {"loose": len(loose), "spurs": len(spurs), "two_edge": len(pairs), "of_those_on_a_curve": bent}
def _ordered_ring(border):
	at={}
	for e in border:
		for v in e.verts:
			at.setdefault(v,[]).append(e)
	if any(len(v) !=2 for v in at.values()):
		return None
	start=border[0]
	ring=[start.verts[0],start.verts[1]]
	cur,prev=start,ring[1]
	while True:
		nxt=next((e for e in at[prev] if e is not cur),None)
		if nxt is None:
			return None
		v=nxt.other_vert(prev)
		if v is ring[0]:
			break
		ring.append(v)
		cur,prev=nxt,v
		if len(ring) > len(border):
			return None
	return ring if len(ring)==len(border) else None
def rebuild_region_rings(bm,faces,snap=None,rings=None):
	border,single=region_border(faces)
	if not single or len(border) < 4:
		return 0
	ring=_ordered_ring(border)
	if ring is None or len(ring) < 4:
		return 0
	n=len(ring)
	mid=ring[0].co.copy()
	for v in ring[1:]:
		mid=mid + v.co
	mid=mid / n
	if rings is None:
		step=sum((ring[i].co - ring[(i + 1) % n].co).length
				   for i in range(n)) / n
		reach=sum((v.co - mid).length for v in ring) / n
		rings=max(1,min(24,int(round(reach / max(step,1e-9)))))
	before=len(faces)
	recipe=[[v for v in f.verts] for f in faces]
	bmesh.ops.delete(bm,geom=list(faces),context="FACES_ONLY")
	bm.verts.ensure_lookup_table()
	made=[]
	outer=ring
	try:
		for k in range(1,rings + 1):
			t=k / (rings + 1)
			if k==rings:
				inner=None
			else:
				inner=[]
				for v in outer:
					p=v.co.lerp(mid,1.0 / (rings + 1 - (k - 1)))
					if snap is not None:
						hit=snap.find_nearest(p)
						if hit and hit[0] is not None:
							p=hit[0]
					inner.append(bm.verts.new(p))
				bm.verts.index_update()
			if inner is None:
				made.append(bm.faces.new(outer))
				break
			for i in range(n):
				a,b=outer[i],outer[(i + 1) % n]
				c,d=inner[(i + 1) % n],inner[i]
				made.append(bm.faces.new((a,b,c,d)))
			outer=inner
	except Exception:
		for f in made:
			if f.is_valid:
				bm.faces.remove(f)
		for verts in recipe:
			if all(v.is_valid for v in verts):
				try:
					bm.faces.new(verts)
				except ValueError:
					pass
		bm.faces.ensure_lookup_table()
		bm.normal_update()
		return 0
	bm.faces.ensure_lookup_table()
	bm.normal_update()
	return before
def _loop_impact(loop):
	worst=0.0
	for e in loop:
		for v in e.verts:
			across=[o for o in v.link_edges if o not in loop]
			if len(across) !=2:
				continue
			a=across[0].other_vert(v).co
			b=across[1].other_vert(v).co
			ab=b - a
			n=ab.length
			if n < 1e-12:
				continue
			t=(v.co - a).dot(ab) / (n * n)
			t=min(max(t,0.0),1.0)
			worst=max(worst,(v.co - (a + ab * t)).length)
	return worst
def _axis_match(loop,axes):
	x=y=z=0.0
	for e in loop:
		d=e.verts[0].co - e.verts[1].co
		x +=abs(d.x); y +=abs(d.y); z +=abs(d.z)
	if not any(axes):
		return True
	total=x + y + z
	if total <=0.0:
		return True
	share=sum(c for c,on in zip((x,y,z),axes) if on)
	return share / total >=0.4
def thin_every(bm,n,keep_marked=True,axes=(True,True,True)):
	if n < 1:
		return set(),0
	pool=[]
	for e in bm.edges:
		if len(e.link_faces) !=2:
			continue
		if keep_marked and e.tag:
			continue
		pool.append(e)
	if not pool:
		return set(),0
	whole,_partial=complete_loops(pool)
	if not all(axes):
		whole=[lp for lp in whole if _axis_match(lp,axes)]
	if not whole:
		return set(),0
	doomed=set()
	dropped=0
	period=n + 1
	for chain in parallel_chains(whole):
		mids=[]
		for idx in chain:
			xs=ys=zs=cnt=0.0
			for e in whole[idx]:
				for v in e.verts:
					xs +=v.co.x; ys +=v.co.y; zs +=v.co.z; cnt +=1
			mids.append((xs / cnt,ys / cnt,zs / cnt))
		pos=[0.0]
		for a,b in zip(mids,mids[1:]):
			pos.append(pos[-1] + math.dist(a,b))
		total=pos[-1]
		keep_n=max(1,round(len(chain) / period))
		if total <=0.0:
			keep=set(range(0,len(chain),period))
		else:
			stride=total / keep_n
			keep={0}
			last=pos[0]
			k=1
			while k < len(chain):
				target=last + stride
				best=None
				for j in range(k,len(chain)):
					if pos[j] - last < stride * 0.6:
						continue
					if best is None or abs(pos[j] - target) < abs(pos[best] - target):
						best=j
					if pos[j] > target:
						break
				if best is None:
					break
				keep.add(best)
				last=pos[best]
				k=best + 1
		for k,idx in enumerate(chain):
			if k not in keep:
				doomed.update(whole[idx])
				dropped +=1
	return doomed,dropped
def polish_verts(bm):
	total=0
	for _ in range(8):
		stranded=[]
		for v in bm.verts:
			es=v.link_edges
			if len(es) !=2:
				continue
			if es[0].tag or es[1].tag:
				continue
			stranded.append(v)
		if not stranded:
			break
		bmesh.ops.dissolve_verts(bm,verts=stranded)
		total +=len(stranded)
	if total:
		bm.normal_update()
	return total
class BudgetThinner:
	"""`drop_to_budget` taken one round at a time.
	Blender cannot draw while an operator is inside a loop,so a job that
	runs for ten seconds looks exactly like a hang - no bar,no cursor,no
	way out. Handing the rounds back one at a time lets the operator return
	control between them,which is what makes a progress bar move and Escape
	work.
	"""
	def __init__(self,bm,target_faces,keep_marked=True,crease_deg=25.0):
		self.bm=bm
		self.target=target_faces
		self.keep_marked=keep_marked
		self.removed=0
		self.start_faces=len(bm.faces)
		self.span=max(self.start_faces - target_faces,1)
		self.ratio=1.0
		crease=math.radians(crease_deg)
		self.hard=set()
		for e in bm.edges:
			if len(e.link_faces) !=2:
				continue
			a,b=e.link_faces
			if a.normal.angle(b.normal,0.0) >=crease:
				self.hard.add(e)
				for v in e.verts:
					self.hard.update(v.link_edges)
	@property
	def fraction(self):
		return min(1.0,(self.start_faces - len(self.bm.faces)) / self.span)
	def round(self):
		bm=self.bm
		if len(bm.faces) <=self.target:
			return False
		bm.edges.ensure_lookup_table()
		pool=[e for e in bm.edges if len(e.link_faces)==2 and not (self.keep_marked and e.tag)]
		if not pool:
			return False
		whole,_partial=complete_loops(pool)
		if not whole:
			return False
		cost=[]
		for lp in whole:
			imp=_loop_impact(set(lp))
			span=0.0
			for e in lp:
				span +=(e.verts[0].co - e.verts[1].co).length
			span /=max(len(lp),1)
			c=imp / max(span,1e-12)
			touching=sum(1 for e in lp if e in self.hard)
			if touching:
				c *=1.0 + 40.0 * (touching / len(lp))
			cost.append(c)
		near=_parallel_adjacent(whole)
		order=sorted(range(len(whole)),key=lambda i: (cost[i],i))
		over=max(1,int((len(bm.faces) - self.target) / self.ratio))
		bite=max(1,len(whole) // 2)
		doomed=set()
		taken=set()
		freed=0
		for i in order:
			if near[i] & taken:
				continue
			if freed and freed + len(whole[i]) > over:
				continue
			taken.add(i)
			doomed.update(whole[i])
			freed +=len(whole[i])
			if freed >=over or len(taken) >=bite:
				break
		if not doomed:
			return False
		before=len(bm.faces)
		bmesh.ops.dissolve_edges(bm,edges=list(doomed),use_verts=False,use_face_split=False)
		bm.normal_update()
		bm.verts.ensure_lookup_table()
		stranded=[]
		for v in bm.verts:
			es=v.link_edges
			if len(es) !=2 or es[0].tag or es[1].tag:
				continue
			a=es[0].other_vert(v).co - v.co
			b=es[1].other_vert(v).co - v.co
			if a.length < 1e-12 or b.length < 1e-12:
				continue
			if a.angle(b) >=STRAIGHT:
				stranded.append(v)
		if stranded:
			bmesh.ops.dissolve_verts(bm,verts=stranded)
		bm.faces.ensure_lookup_table()
		if len(bm.faces) >=before:
			return False
		actual=before - len(bm.faces)
		if freed > 0 and actual > 0:
			seen=actual / freed
			self.ratio=self.ratio * 0.4 + seen * 0.6
		self.removed +=len(taken)
		return len(bm.faces) > self.target
	def finish(self):
		heal_stubs(self.bm)
		polish_verts(self.bm)
		self.bm.faces.ensure_lookup_table()
		tri=[f for f in self.bm.faces if len(f.verts)==3]
		if tri:
			bmesh.ops.join_triangles(self.bm,faces=tri,angle_face_threshold=3.14,angle_shape_threshold=3.14,cmp_seam=False,cmp_sharp=False,cmp_uvs=False,cmp_vcols=False,cmp_materials=False)
		return self.removed
def drop_to_budget(bm,target_faces,keep_marked=True,rounds=40,crease_deg=25.0,progress=None):
	crease=math.radians(crease_deg)
	hard=set()
	for e in bm.edges:
		if len(e.link_faces) !=2:
			continue
		a,b=e.link_faces
		if a.normal.angle(b.normal,0.0) >=crease:
			hard.add(e)
			for v in e.verts:
				hard.update(v.link_edges)
	start_faces=len(bm.faces)
	span=max(start_faces - target_faces,1)
	if progress:
		progress(f"spreading {start_faces:,} -> {target_faces:,} faces",0.0)
	removed=0
	for _ in range(rounds):
		now=len(bm.faces)
		if progress:
			progress(f"spreading {now:,} -> {target_faces:,} faces",min(1.0,(start_faces - now) / span))
		if now <=target_faces:
			break
		bm.edges.ensure_lookup_table()
		pool=[e for e in bm.edges if len(e.link_faces)==2 and not (keep_marked and e.tag)]
		if not pool:
			break
		whole,_partial=complete_loops(pool)
		if not whole:
			break
		cost=[]
		for lp in whole:
			imp=_loop_impact(set(lp))
			span=0.0
			for e in lp:
				span +=(e.verts[0].co - e.verts[1].co).length
			span /=max(len(lp),1)
			c=imp / max(span,1e-12)
			touching=sum(1 for e in lp if e in hard)
			if touching:
				c *=1.0 + 40.0 * (touching / len(lp))
			cost.append(c)
		near=_parallel_adjacent(whole)
		order=sorted(range(len(whole)),key=lambda i: (cost[i],i))
		bite=max(1,len(whole) // 3)
		doomed=set()
		taken=set()
		for i in order:
			if near[i] & taken:
				continue
			taken.add(i)
			doomed.update(whole[i])
			if len(taken) >=bite:
				break
		if not doomed:
			break
		before=len(bm.faces)
		dissolve_keeping_rims(bm,doomed)
		bm.faces.ensure_lookup_table()
		if len(bm.faces) >=before:
			break
		removed +=len(taken)
		if progress:
			progress(f"spreading {len(bm.faces):,} -> {target_faces:,} faces",min(1.0,(start_faces - len(bm.faces)) / span))
	return removed
def drop_loops(bm,tol_deg=1.0,keep_marked=True,sag_pct=0.0,axes=(True,True,True)):
	limit=sag_limit(bm,sag_pct)
	total=0
	partial=0
	for _ in range(24):
		doomed,dropped,part=useless_loops(bm,tol_deg=tol_deg,keep_marked=keep_marked,sag_pct=sag_pct,axes=axes)
		partial=part
		if not doomed:
			break
		dissolve_keeping_rims(bm,doomed,sag_limit=limit,polish=True)
		heal_stubs(bm)
		total +=dropped
		if not dropped:
			break
	polish_verts(bm)
	return total,partial
def force_loop(bm,start,factor=0.5):
	import bmesh.utils
	def exit_edge(face,entry):
		ev=set(entry.verts)
		d1=(entry.verts[1].co - entry.verts[0].co).normalized()
		best=None
		score=-1.0
		for e in face.edges:
			if e is entry:
				continue
			if ev & set(e.verts):
				continue
			v=e.verts[1].co - e.verts[0].co
			if v.length < 1e-12:
				continue
			far=((e.verts[0].co + e.verts[1].co) / 2 -
				   (entry.verts[0].co + entry.verts[1].co) / 2).length
			sc=abs(d1.dot(v.normalized())) + far * 1e-3
			if sc > score:
				score=sc
				best=e
		if best is None:
			for e in face.edges:
				if e is not entry:
					return e
		return best
	faces=list(start.link_faces)
	if not faces:
		return 0
	_e,first_vert=bmesh.utils.edge_split(start,start.verts[0],factor)
	cuts=0
	for direction in faces[:2]:
		face=direction
		entry=start
		entry_vert=first_vert
		visited=set()
		while face is not None and face not in visited:
			visited.add(face)
			out=exit_edge(face,entry)
			if out is None:
				break
			closing=entry_vert is not first_vert and first_vert in out.verts
			if closing:
				out_vert=first_vert
			else:
				_e2,out_vert=bmesh.utils.edge_split(out,out.verts[0],factor)
			try:
				res=bmesh.ops.connect_vert_pair(bm,verts=[entry_vert,out_vert])
				if res.get("edges"):
					cuts +=1
			except Exception:
				break
			if closing:
				face=None
				break
			nxt=[f for f in out_vert.link_edges
				   for ff in f.link_faces] and None
			link=[f for f in out.link_faces if f not in visited]
			nxt_face=None
			for e in out_vert.link_edges:
				for f in e.link_faces:
					if f not in visited and entry_vert not in f.verts:
						nxt_face=f
						break
				if nxt_face:
					break
			entry_vert=out_vert
			entry=out
			face=nxt_face
		if face is None:
			break
	return cuts
def tag_marked(bm):
	total=len(bm.edges)
	sel=0
	for e in bm.edges:
		if e.select:
			sel +=1
	use_sel=0 < sel < total * 0.9
	n=0
	for e in bm.edges:
		e.tag=(not e.smooth) or (use_sel and e.select)
		if e.tag:
			n +=1
	return n
def sag_limit(bm,pct):
	if pct <=0.0:
		return 0.0
	co=[v.co for v in bm.verts]
	if not co:
		return 0.0
	span=max(max(p[i] for p in co) - min(p[i] for p in co) for i in range(3))
	return span * pct / 100.0
def _clean_pole(edge,v):
	es=[e for e in v.link_edges if e is not edge]
	if len(es) >=4:
		return True
	if len(es) !=2:
		return False
	a=es[0].other_vert(v).co - v.co
	b=es[1].other_vert(v).co - v.co
	if a.length < 1e-12 or b.length < 1e-12:
		return False
	return a.angle(b) >=CONTINUES
def complete_loops(edges,allow_poles=False):
	pool=set(edges)
	whole,partial=[],[]
	while pool:
		seed=pool.pop()
		loop=[seed]
		clean=True
		closed=False
		for start in (seed.verts[0],seed.verts[1]):
			cur,v=seed,start
			while True:
				nxt=_next_in_loop(cur,v)
				if nxt is seed:
					closed=True
					break
				if nxt is None:
					if not (allow_poles or _clean_pole(cur,v)):
						clean=False
					break
				if nxt.tag:
					break
				if nxt not in pool:
					clean=False
					break
				pool.discard(nxt)
				loop.append(nxt)
				v=nxt.other_vert(v)
				cur=nxt
			if closed:
				break
		(whole if (clean or closed) else partial).append(loop)
	return whole,partial
def surface_drift(bm,ref):
	worst=0.0
	for f in bm.faces:
		hit=ref.find_nearest(f.calc_center_median())
		if hit and hit[0] is not None:
			d=(f.calc_center_median() - hit[0]).length
			if d > worst:
				worst=d
	return worst
def useless_loops(bm,tol_deg=1.0,keep_marked=True,sag_pct=0.0,size=None,axes=(True,True,True)):
	limit=math.radians(tol_deg)
	pool=[]
	for e in bm.edges:
		if len(e.link_faces) !=2:
			continue
		if keep_marked and e.tag:
			continue
		pool.append(e)
	if not pool:
		return set(),0,0
	whole,partial=complete_loops(pool)
	if not all(axes):
		whole=[lp for lp in whole if _axis_match(lp,axes)]
	doomed=set()
	dropped=0
	left=[]
	for loop in whole:
		if _loop_error(set(loop)) <=limit:
			doomed.update(loop)
			dropped +=1
		else:
			left.append(loop)
	if sag_pct > 0.0 and left:
		if size is None:
			xs=[v.co for v in bm.verts]
			size=max(max(p[i] for p in xs) - min(p[i] for p in xs)
					   for i in range(3)) if xs else 1.0
		sag_limit=size * sag_pct / 100.0
		near=_parallel_adjacent(left)
		order=sorted(range(len(left)),
					   key=lambda i: (_loop_impact(set(left[i])),min(e.index for e in left[i])))
		taken=set()
		for i in order:
			if near[i] & taken:
				continue
			if _loop_impact(set(left[i])) > sag_limit:
				continue
			taken.add(i)
			doomed.update(left[i])
			dropped +=1
	return doomed,dropped,len(partial)
def _key(e):
	a,b=e.verts[0].index,e.verts[1].index
	return (a,b) if a < b else (b,a)