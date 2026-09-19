from __future__ import annotations
"""Topology scoring for candidate results. numpy only,runs inside Blender.
A compact version of the TopoLens metrics - enough to rank candidates against
each other,which is all the parameter search needs. The full analyser stays
outside the add-on because it depends on scipy.
"""
import numpy as np
def _flatten(faces: list):
	sizes=np.fromiter((len(f) for f in faces),dtype=np.int64,count=len(faces))
	corners=(np.concatenate([np.asarray(f,dtype=np.int64) for f in faces])
			   if faces else np.zeros(0,dtype=np.int64))
	starts=np.concatenate([[0],np.cumsum(sizes)[:-1]]).astype(np.int64)
	return corners,sizes,starts
def evaluate(V: np.ndarray,faces: list) -> dict:
	if not faces:
		return {"overall": 0.0, "reason": "no faces"}
	V=np.asarray(V,dtype=np.float64)
	corners,sizes,starts=_flatten(faces)
	nv,nf=len(V),len(sizes)
	nxt=(np.arange(len(corners)) - np.repeat(starts,sizes) + 1) \
		% np.repeat(sizes,sizes) + np.repeat(starts,sizes)
	a,b=corners,corners[nxt]
	key=np.minimum(a,b) * np.int64(nv) + np.maximum(a,b)
	uniq,inv=np.unique(key,return_inverse=True)
	efc=np.bincount(inv)
	ne=len(uniq)
	boundary=int((efc==1).sum())
	nonmanifold=int((efc > 2).sum())
	area=0.5 * np.linalg.norm(np.add.reduceat(np.cross(V[a],V[b]),starts,axis=0),axis=1)
	total=max(area.sum(),1e-20)
	quad_area=float(area[sizes==4].sum() / total)
	edges=np.stack([uniq // nv,uniq % nv],axis=1)
	valence=np.bincount(edges.ravel(),minlength=nv)
	on_boundary=np.zeros(nv,dtype=bool)
	if boundary:
		on_boundary[edges[efc==1].ravel()]=True
	used=np.zeros(nv,dtype=bool)
	used[corners]=True
	interior=used & ~on_boundary
	regular=float((valence[interior]==4).mean()) if interior.any() else 0.0
	elen=np.linalg.norm(V[a] - V[b],axis=1)
	emax=np.maximum.reduceat(elen,starts)
	emin=np.minimum.reduceat(elen,starts)
	aspect=emax / np.maximum(emin,1e-20)
	bad_aspect=float((aspect > 4.0).mean())
	sub={"quad_purity": 100.0 * quad_area,"regularity": 100.0 * regular, "watertight": 100.0 * max(0.0,1.0 - (boundary / max(ne,1)) / 0.10),"manifold": 100.0 * max(0.0,1.0 - (nonmanifold / max(ne,1)) / 0.05), "face_shape": 100.0 * max(0.0,1.0 - bad_aspect / 0.25),}
	weights={"quad_purity": 0.28, "regularity": 0.22, "watertight": 0.25, "manifold": 0.15, "face_shape": 0.10}
	overall=sum(sub[k] * w for k,w in weights.items())
	return {"overall": float(overall),"sub": sub,"faces": int(nf),"verts": int(nv), "quads": int((sizes==4).sum()),"tris": int((sizes==3).sum()),"ngons": int((sizes > 4).sum()),"quad_area_ratio": quad_area, "boundary_edges": boundary,"nonmanifold_edges": nonmanifold, "edges": int(ne),}