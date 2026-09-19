from __future__ import annotations
"""Drop the feature lines that do not change the rebuilt mesh.
The thresholds in the Feature Lines panel answer "how sharp is this edge",
which is the wrong question. What decides whether a line is worth having is
what the rebuild does with it,and that is measurable rather than a matter of
taste: a line separates two regions,so deleting it merges them,and the only
question is whether the merged region still rebuilds the same way.
`panels_to_mesh` has exactly two outcomes for a region. Flat enough,and it
becomes one n-gon on the detected lines. Not flat enough,and it keeps its own
faces. So merging two regions is free in three cases and costly in one:
	flat  + flat  -> merged still flat     free,one n-gon instead of two
	curved + curved                        free,both keep their faces either way
	flat  + flat  -> merged now curved     COSTLY,a bend gets flattened
	flat  + curved                         COSTLY,this is a real panel edge
The curved+curved case is free geometrically but would collapse every curved
shell into one region,losing the crease where two curved shells meet. That is
settled without another user-facing angle: a boundary is a feature when it is
sharper than the interiors of the regions it separates. Comparing a boundary to
its own neighbourhood needs no global threshold,and it is what a fixed crease
angle only approximates.
The one number here,`planar_tol`,is not a new knob - it is the same value the
rebuild already uses to decide flat from curved,so pruning agrees with the
rebuild by construction.
"""
from collections import defaultdict
import numpy as np
from .hardsurface import DisjointSet,_region_planarity
def _region_vertices(cache,lab,nreg):
	fv,fs,starts,nf=cache["fv"],cache["fs"],cache["starts"],cache["nf"]
	acc=defaultdict(list)
	for i in range(nf):
		acc[int(lab[i])].append(fv[starts[i]:starts[i] + fs[i]])
	return {r: np.unique(np.concatenate(v)) for r,v in acc.items()}
def prune(cache,mask,planar_tol=0.02,sliver=0.0,merge=True,max_rounds=12,progress=None):
	edges=cache["edges"]
	A,B,idx=cache["A"],cache["B"],cache["idx"]
	raw=cache["raw_ang"]
	V,nf=cache["V"],cache["nf"]
	mask=np.asarray(mask,dtype=bool).copy()
	start_lines=int(mask.sum())
	ds=DisjointSet(nf)
	for e,x,y in zip(idx.tolist(),A.tolist(),B.tolist()):
		if not mask[e]:
			ds.union(x,y)
	root=np.fromiter((ds.find(i) for i in range(nf)),dtype=np.int64,count=nf)
	_,lab=np.unique(root,return_inverse=True)
	nreg=int(lab.max()) + 1
	rverts=_region_vertices(cache,lab,nreg)
	flat=np.zeros(nreg,dtype=bool)
	for r in range(nreg):
		flat[r]=_region_planarity(V,rverts[r]) <=planar_tol
	def build_pairs(lab):
		pairs=defaultdict(list)
		for k,(e,x,y) in enumerate(zip(idx.tolist(),A.tolist(),B.tolist())):
			if not mask[e]:
				continue
			ra,rb=int(lab[x]),int(lab[y])
			if ra==rb:
				continue
			pairs[(min(ra,rb),max(ra,rb))].append(k)
		return pairs
	uf=DisjointSet(nreg)
	merged_total=0
	reasons=defaultdict(int)
	for _round in range(max_rounds if merge else 0):
		cur=np.fromiter((uf.find(int(lab[i])) for i in range(nf)),dtype=np.int64,count=nf)
		_,cl=np.unique(cur,return_inverse=True)
		pairs=build_pairs(cl)
		if not pairs:
			break
		n_cur=int(cl.max()) + 1
		cverts=_region_vertices(cache,cl,n_cur)
		cflat=np.zeros(n_cur,dtype=bool)
		for r in range(n_cur):
			cflat[r]=_region_planarity(V,cverts[r]) <=planar_tol
		cinner=np.zeros(n_cur)
		acc=defaultdict(list)
		for k,(e,x,y) in enumerate(zip(idx.tolist(),A.tolist(),B.tolist())):
			if cl[x]==cl[y]:
				acc[int(cl[x])].append(raw[k])
		for r,vals in acc.items():
			cinner[r]=float(np.median(vals)) if vals else 0.0
		did=0
		for (ra,rb),ks in pairs.items():
			if uf.find(ra)==uf.find(rb):
				continue
			fa_,fb_=cflat[ra],cflat[rb]
			if fa_ !=fb_:
				reasons["kept: flat meets curved"] +=1
				continue
			if fa_ and fb_:
				union=np.union1d(cverts[ra],cverts[rb])
				if _region_planarity(V,union) <=planar_tol:
					uf.union(ra,rb); did +=1
					reasons["dropped: two flats,still flat merged"] +=1
				else:
					reasons["kept: merging would flatten a bend"] +=1
				continue
			b_med=float(np.median(raw[ks]))
			local=max(cinner[ra],cinner[rb])
			if b_med <=local:
				uf.union(ra,rb); did +=1
				reasons["dropped: no sharper than the surface around it"] +=1
			else:
				reasons["kept: crease between two curved shells"] +=1
		merged_total +=did
		if progress:
			progress("pruning",0.2 + 0.6 * (_round + 1) / max_rounds)
		if not did:
			break
	merged_slivers=0
	if sliver > 0.0:
		tol=sliver * float(cache["diag"])
		strength=np.zeros(len(edges))
		strength[idx]=cache["persist"]
		sel=np.flatnonzero(mask)
		if len(sel):
			P0,P1=V[edges[sel,0]],V[edges[sel,1]]
			mid=(P0 + P1) * 0.5
			cell=np.floor(mid / max(tol,1e-12)).astype(np.int64)
			buckets=defaultdict(list)
			for n,c in enumerate(map(tuple,cell.tolist())):
				buckets[c].append(n)
			def seg_gap(a0,a1,b0,b1):
				d=b1 - b0
				L2=float(d @ d)
				best=np.inf
				for t in (0.0,0.5,1.0):
					p=a0 + (a1 - a0) * t
					u=0.0 if L2 < 1e-18 else min(1.0,max(0.0,float((p - b0) @ d) / L2))
					best=min(best,float(np.linalg.norm(p - (b0 + d * u))))
				return best
			drop=set()
			for c,members in buckets.items():
				near=[]
				for dx in (-1,0,1):
					for dy in (-1,0,1):
						for dz in (-1,0,1):
							near.extend(buckets.get((c[0]+dx,c[1]+dy,c[2]+dz),()))
				for n in members:
					if n in drop:
						continue
					en=sel[n]
					for m2 in near:
						if m2 <=n or m2 in drop:
							continue
						em=sel[m2]
						if set(edges[en].tolist()) & set(edges[em].tolist()):
							continue
						if seg_gap(P0[n],P1[n],P0[m2],P1[m2]) >=tol:
							continue
						weak=em if strength[em] <=strength[en] else en
						drop.add(m2 if weak==em else n)
						if weak==en:
							break
			for n in drop:
				mask[sel[n]]=False
			merged_slivers=len(drop)
	final=np.fromiter((uf.find(int(lab[i])) for i in range(nf)),dtype=np.int64,count=nf)
	_,fl=np.unique(final,return_inverse=True)
	new_mask=np.zeros_like(mask)
	for k,(e,x,y) in enumerate(zip(idx.tolist(),A.tolist(),B.tolist())):
		if mask[e] and fl[x] !=fl[y]:
			new_mask[e]=True
	border=mask & ~np.isin(np.arange(len(edges)),idx)
	new_mask |=border
	kept=defaultdict(int)
	for k,(e,x,y) in enumerate(zip(idx.tolist(),A.tolist(),B.tolist())):
		if new_mask[e] and fl[x] !=fl[y]:
			kept[int(fl[x])] +=1
			kept[int(fl[y])] +=1
	for k,(e,x,y) in enumerate(zip(idx.tolist(),A.tolist(),B.tolist())):
		if mask[e] and not new_mask[e]:
			if kept[int(fl[x])]==0 or kept[int(fl[y])]==0:
				new_mask[e]=True
				kept[int(fl[x])] +=1
				kept[int(fl[y])] +=1
				log_restored=True
	log={"lines_before": start_lines,"lines_after": int(new_mask.sum()),"removed": start_lines - int(new_mask.sum()),"regions_before": nreg, "regions_after": int(fl.max()) + 1,"region_merges": merged_total, "sliver_merges": merged_slivers,"planar_tol": float(planar_tol), "why": dict(reasons),}
	return new_mask,log