from __future__ import annotations
"""Adaptive quad refinement on top of a clean quad mesh.
Instant Meshes produces an excellent uniform pure-quad mesh and has no way to
vary its density. So the density is added afterwards: take its result,decide
which quads sit on a detected edge,and refine only those - keeping the mesh
100% quads throughout.
The trick that makes it all-quad is a parity rule. A quad with `k` of its edges
split has a boundary of `4 + k` vertices once the midpoints are inserted,and
any *even* polygon can be cut into quads by fanning alternate vertices to a
centroid. So `k` is forced even before any geometry is built,and no special
transition templates are needed at all:
	k=0   left alone
	k=2   becomes 3 quads
	k=4   becomes 4 quads (the ordinary 1-to-4 split)
numpy only,no scipy - it has to run inside Blender.
"""
import numpy as np
def grid_nearest(src: np.ndarray,query: np.ndarray,cell: float) -> np.ndarray:
	lo=np.minimum(src.min(axis=0),query.min(axis=0)) - cell
	dims=np.maximum(np.ceil((np.maximum(src.max(axis=0),query.max(axis=0)) + cell - lo)
				/ cell).astype(np.int64),1)
	def key_of(P):
		c=np.clip(((P - lo) / cell).astype(np.int64),0,dims - 1)
		return (c[:,0] * dims[1] + c[:,1]) * dims[2] + c[:,2],c
	skey,_=key_of(src)
	order=np.argsort(skey)
	skey_sorted=skey[order]
	_,qc=key_of(query)
	best=np.full(len(query),-1,dtype=np.int64)
	best_d=np.full(len(query),np.inf)
	offsets=[(a,b,c) for a in (-1,0,1) for b in (-1,0,1) for c in (-1,0,1)]
	for radius in (1,2,4):
		if radius > 1:
			offsets=[(a,b,c) for a in range(-radius,radius + 1) for b in range(-radius,radius + 1) for c in range(-radius,radius + 1)]
		todo=np.flatnonzero(best < 0)
		if not len(todo):
			break
		for da,db,dc in offsets:
			cc=qc[todo] + np.array([da,db,dc])
			valid=np.all((cc >=0) & (cc < dims),axis=1)
			if not valid.any():
				continue
			idx=todo[valid]
			k=(cc[valid,0] * dims[1] + cc[valid,1]) * dims[2] + cc[valid,2]
			lo_i=np.searchsorted(skey_sorted,k, "left")
			hi_i=np.searchsorted(skey_sorted,k, "right")
			for q,a,b in zip(idx.tolist(),lo_i.tolist(),hi_i.tolist()):
				if a==b:
					continue
				cand=order[a:b]
				d=np.einsum("ij,ij->i",src[cand] - query[q],src[cand] - query[q])
				m=int(np.argmin(d))
				if d[m] < best_d[q]:
					best_d[q]=d[m]
					best[q]=cand[m]
	todo=np.flatnonzero(best < 0)
	for q in todo.tolist():
		d=np.einsum("ij,ij->i",src - query[q],src - query[q])
		best[q]=int(np.argmin(d))
	return best
def transfer(src_V: np.ndarray,values: np.ndarray,dst_V: np.ndarray,cell: float | None=None) -> np.ndarray:
	if cell is None:
		span=src_V.max(axis=0) - src_V.min(axis=0)
		cell=float(np.linalg.norm(span)) / 64.0
	idx=grid_nearest(src_V,dst_V,max(cell,1e-9))
	return values[idx]
def _edge_table(faces: list,nv: int):
	fa,fb,fid,slot=[],[],[],[]
	for i,f in enumerate(faces):
		n=len(f)
		for k in range(n):
			fa.append(f[k])
			fb.append(f[(k + 1) % n])
			fid.append(i)
			slot.append(k)
	a=np.asarray(fa,dtype=np.int64)
	b=np.asarray(fb,dtype=np.int64)
	key=np.minimum(a,b) * np.int64(nv) + np.maximum(a,b)
	uniq,inv=np.unique(key,return_inverse=True)
	return uniq,inv,np.asarray(fid),np.asarray(slot)
def adaptive_subdivide(V: np.ndarray,faces: list,mark: np.ndarray,passes: int=1,pure_quad: bool=False):
	V=np.asarray(V,dtype=np.float64)
	for _ in range(max(passes,1)):
		V,faces,mark=_one_pass(V,faces,mark,pure_quad)
	return V,faces
def _split_even(boundary: list,cid: int) -> list:
	m=len(boundary)
	return [[boundary[j - 1],boundary[j],boundary[(j + 1) % m],cid] for j in range(0,m,2)]
def _split_odd(boundary: list) -> list:
	m=len(boundary)
	out=[]
	j=0
	anchors=[boundary[0]]
	while j + 3 < m:
		out.append([boundary[j],boundary[j + 1],boundary[j + 2],boundary[j + 3]])
		j +=3
		anchors.append(boundary[j])
	anchors.append(boundary[m - 1] if j !=m - 1 else boundary[0])
	tri=[boundary[0],boundary[j],boundary[m - 1]]
	if len(set(tri))==3:
		out.append(tri)
	return out
def _one_pass(V: np.ndarray,faces: list,mark: np.ndarray,pure_quad: bool=False):
	nv=len(V)
	uniq,inv,fid,slot=_edge_table(faces,nv)
	ne=len(uniq)
	sizes=np.array([len(f) for f in faces])
	split=np.zeros(ne,dtype=bool)
	quad=sizes==4
	want=mark & quad
	sel=want[fid]
	if sel.any():
		split[inv[sel]]=True
	corner_edge=inv
	slot_edge: dict={}
	for f_i,s_i,e_i in zip(fid.tolist(),slot.tolist(),corner_edge.tolist()):
		slot_edge[(f_i,s_i)]=e_i
	face_edges=[[slot_edge.get((i,k),-1) for k in range(len(f))] for i,f in enumerate(faces)]
	for _ in range(len(faces) + 2 if pure_quad else 0):
		counts=np.zeros(len(faces),dtype=np.int64)
		np.add.at(counts,fid,split[corner_edge].astype(np.int64))
		odd=quad & (counts % 2==1)
		if not odd.any():
			break
		changed=False
		for i in np.flatnonzero(odd).tolist():
			f=faces[i]
			best,best_len=-1,-1.0
			for k in range(4):
				e=face_edges[i][k]
				if e < 0 or split[e]:
					continue
				L=float(np.linalg.norm(V[f[k]] - V[f[(k + 1) % 4]]))
				if L > best_len:
					best_len,best=L,e
			if best >=0:
				split[best]=True
				changed=True
		if not changed:
			break
	mid_index=np.full(ne,-1,dtype=np.int64)
	which=np.flatnonzero(split)
	if not len(which):
		return V,faces,mark
	ea=uniq[which] // nv
	eb=uniq[which] % nv
	mids=0.5 * (V[ea] + V[eb])
	mid_index[which]=np.arange(len(which)) + nv
	new_V=[V,mids]
	new_faces: list=[]
	new_mark: list=[]
	next_index=nv + len(which)
	centroids=[]
	for i,f in enumerate(faces):
		n=len(f)
		if n !=4:
			new_faces.append(list(f))
			new_mark.append(False)
			continue
		boundary=[]
		k_split=0
		for k in range(4):
			boundary.append(int(f[k]))
			e=slot_edge.get((i,k),-1)
			if e >=0 and split[e]:
				boundary.append(int(mid_index[e]))
				k_split +=1
		if k_split==0:
			new_faces.append(list(f))
			new_mark.append(False)
			continue
		m=len(boundary)
		if m % 2:
			if pure_quad:
				raise RuntimeError(f"face {i} still has an odd split count ({k_split}); " "parity balancing did not converge")
			produced=_split_odd(boundary)
		else:
			centroids.append(np.mean(V[np.asarray(f,dtype=np.int64)],axis=0))
			produced=_split_even(boundary,next_index)
			next_index +=1
		for q in produced:
			new_faces.append(q)
			new_mark.append(bool(mark[i]))
	if centroids:
		new_V.append(np.asarray(centroids))
	return (np.vstack(new_V),new_faces,np.asarray(new_mark,dtype=bool))
def dilate(faces: list,nv: int,mark: np.ndarray,rings: int=1) -> np.ndarray:
	mark=np.asarray(mark,dtype=bool).copy()
	for _ in range(max(rings,0)):
		touched=np.zeros(nv,dtype=bool)
		for i in np.flatnonzero(mark).tolist():
			touched[np.asarray(faces[i],dtype=np.int64)]=True
		for i,f in enumerate(faces):
			if not mark[i] and touched[np.asarray(f,dtype=np.int64)].any():
				mark[i]=True
	return mark
def refine_edges(src_V,src_face_verts,src_face_sizes,V,faces,*,inner: float=1.0,outer: float=0.5,threshold: float=0.35,rings: int=1,passes: int=1,pure_quad: bool=False,feature_angle: float | None=None):
	from .detect import edge_field
	from .mesh import TriMesh
	src_V=np.asarray(src_V,dtype=np.float64)
	mesh=TriMesh.from_polys(src_V,src_face_verts,src_face_sizes)
	ef=edge_field(mesh,feature_angle,inner_weight=inner,outer_weight=outer)
	field=np.maximum(ef["inner"],ef["outer"])
	V=np.asarray(V,dtype=np.float64)
	importance=transfer(mesh.V,field,V)
	mark=mark_from_importance(V,faces,importance,threshold,rings)
	before=len(faces)
	if not mark.any():
		return V,faces,{"marked": 0, "before": before, "after": before, "crease": ef["feature_angle"],**ef["stats"]}
	V2,faces2=adaptive_subdivide(V,faces,mark,passes=passes,pure_quad=pure_quad)
	sizes=np.array([len(f) for f in faces2])
	return V2,faces2,{"marked": int(mark.sum()),"before": before,"after": len(faces2),"growth": round(len(faces2) / max(before,1),2), "tris": int((sizes==3).sum()),"tri_pct": round(100.0 * (sizes==3).mean(),2), "crease": round(ef["feature_angle"],1),**ef["stats"],}
def mark_from_importance(V: np.ndarray,faces: list,importance: np.ndarray,threshold: float=0.4,rings: int=1) -> np.ndarray:
	out=np.zeros(len(faces),dtype=bool)
	for i,f in enumerate(faces):
		out[i]=float(importance[np.asarray(f,dtype=np.int64)].mean()) > threshold
	return dilate(faces,len(V),out,rings)