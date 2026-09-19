from __future__ import annotations
"""Our own mesh analysis - what the engine should be told about this model.
A fixed dihedral threshold is not detection,it is a guess the user has to make
for every model,and getting it wrong wrecks the result. This module derives
the parameters from the mesh itself.
numpy only,so it runs inside Blender unchanged.
"""
import numpy as np
def dihedral_angles(mesh) -> np.ndarray:
	ef=mesh.edge_faces
	inner=(ef[:,0] >=0) & (ef[:,1] >=0)
	fn=mesh.face_normal
	mag=np.linalg.norm(fn,axis=1,keepdims=True)
	fnn=fn / np.maximum(mag,1e-20)
	cos=np.sum(fnn[ef[inner,0]] * fnn[ef[inner,1]],axis=1)
	return np.degrees(np.arccos(np.clip(cos,-1.0,1.0)))
def crease_angle(mesh,lo: float=18.0,hi: float=75.0,target_fraction: float=0.03) -> dict:
	ang=dihedral_angles(mesh)
	if not len(ang):
		return {"angle": 30.0, "method": "default (no interior edges)", "crease_fraction": 0.0}
	ang_sorted=np.sort(ang)
	fallback=float(np.clip(np.percentile(ang_sorted,100.0 * (1.0 - target_fraction)),lo,hi))
	bins=np.linspace(lo,hi,25)
	counts,_=np.histogram(ang,bins=bins)
	centres=0.5 * (bins[:-1] + bins[1:])
	total=max(counts.sum(),1)
	above=counts[::-1].cumsum()[::-1] / total
	valley=None
	usable=(above > 0.005) & (above < 0.25)
	if usable.any():
		idx=np.flatnonzero(usable)
		valley=int(idx[np.argmin(counts[idx])])
	if valley is not None and counts[valley] < 0.25 * counts.mean():
		angle=float(centres[valley])
		method= "histogram valley"
	else:
		angle=fallback
		method=f"top {target_fraction:.0%} of edges"
	frac=float((ang > angle).mean())
	return {"angle": float(np.clip(angle,lo,hi)), "method": method,"crease_fraction": frac, "dihedral_p50": float(np.percentile(ang,50)), "dihedral_p99": float(np.percentile(ang,99))}
def _smooth_positions(mesh,iterations: int,strength: float=0.5):
	start,nbr=mesh.adjacency
	counts=np.diff(start)
	P=mesh.V.copy()
	src=np.repeat(np.arange(mesh.nv),counts)
	for _ in range(iterations):
		acc=np.zeros_like(P)
		for k in range(3):
			acc[:,k]=np.bincount(src,weights=P[nbr,k],minlength=mesh.nv)
		acc /=np.maximum(counts,1)[:,None]
		P +=strength * (acc - P)
	return P
def orientation_sign(mesh) -> float:
	P=mesh.V[mesh.F]
	vol=float(np.sum(np.einsum("ij,ij->i",P[:,0],
								 np.cross(P[:,1],P[:,2]))) / 6.0)
	if abs(vol) > 1e-12 and (mesh.edge_faces[:,1] < 0).sum()==0:
		return 1.0 if vol > 0 else -1.0
	centre=mesh.V.mean(axis=0)
	away=mesh.V - centre
	agree=float(np.sum(np.sum(away * mesh.normal,axis=1)))
	return 1.0 if agree >=0 else -1.0
def cavity(mesh,scales=(1,4,16)) -> dict:
	sign=orientation_sign(mesh)
	n=mesh.normal * sign
	diag=mesh.diagonal
	out={"orientation": sign}
	combined=np.zeros(mesh.nv)
	for s in scales:
		P=_smooth_positions(mesh,s)
		d=np.sum((P - mesh.V) * n,axis=1) / diag
		ref=np.percentile(np.abs(d),95)
		dn=d / max(ref,1e-12)
		out[f"scale_{s}"]=dn
		combined +=dn
	combined /=len(scales)
	out["signed"]=combined
	out["concave"]=np.clip(combined,0.0,None)
	out["convex"]=np.clip(-combined,0.0,None)
	return out
def edge_field(mesh,feature_angle: float | None=None,inner_weight: float=1.0,outer_weight: float=1.0) -> dict:
	if feature_angle is None:
		feature_angle=crease_angle(mesh)["angle"]
	nv=mesh.nv
	ang=dihedral_angles(mesh)
	ef=mesh.edge_faces
	inner_mask=(ef[:,0] >=0) & (ef[:,1] >=0)
	e=mesh.edges[inner_mask]
	sharp=np.zeros(nv)
	val=np.clip(ang / max(feature_angle,1e-6),0.0,2.0)
	np.maximum.at(sharp,e[:,0],val)
	np.maximum.at(sharp,e[:,1],val)
	k1,k2,_,_=mesh.curvature()
	kmag=np.nan_to_num(np.maximum(np.abs(k1),np.abs(k2))) * mesh.diagonal
	kref=np.percentile(kmag,95) if nv else 1.0
	kn=np.clip(kmag / max(kref,1e-12),0.0,1.0)
	cav=cavity(mesh)
	concave=np.clip(cav["concave"],0.0,1.0)
	convex=np.clip(cav["convex"],0.0,1.0)
	strength=np.maximum(np.clip(sharp,0.0,1.0),kn)
	inner=strength * concave * float(inner_weight)
	outer=strength * convex * float(outer_weight)
	return {"sharpness": sharp,"curvature": kn,"signed_cavity": cav["signed"],"inner": inner,"outer": outer,"importance": np.clip(np.maximum(inner,outer),0.0,1.0),"feature_angle": float(feature_angle),"stats": {"inner_verts": int((inner > 0.3).sum()), "outer_verts": int((outer > 0.3).sum()), "sharp_verts": int((sharp > 1.0).sum()),},}
def describe(mesh) -> dict:
	ang=dihedral_angles(mesh)
	ef=mesh.edge_faces
	boundary=int((ef[:,1] < 0).sum())
	k1,k2,_,aniso=mesh.curvature()
	kmag=np.nan_to_num(np.maximum(np.abs(k1),np.abs(k2)))
	diag=mesh.diagonal
	kn=kmag * diag
	cre=crease_angle(mesh)
	flat_frac=float((kn < 1.0).mean())
	return {"verts": int(mesh.nv),"tris": int(mesh.nf),"mean_edge": float(mesh.mean_edge),"diagonal": float(diag),"area": float(mesh.total_area),"boundary_edges": boundary,"closed": boundary==0,"crease": cre, "flat_fraction": flat_frac,"curvature_p90": float(np.percentile(kn,90)) if len(kn) else 0.0, "dihedral_mean": float(ang.mean()) if len(ang) else 0.0,"kind": "hard-surface" if flat_frac > 0.55 and cre["crease_fraction"] < 0.15 else "organic",}