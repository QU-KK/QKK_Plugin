from __future__ import annotations
"""Per-vertex target edge length - the adaptive sizing field.
Instant Meshes has no equivalent: its batch mode only takes one global `-s`.
This is therefore something our solver can do that the reference cannot,rather
than another thing it does better.
Two things drive density: proximity to a crease,and curvature. Both produce a
raw request for "smaller quads here",and both are useless on their own - the
field also has to be *gradient limited*,or the mesh is asked to jump from
large to small quads in one step and simply cannot.
"""
import numpy as np
RELAX_MAX=128
def _relax_min(edges: np.ndarray,length: np.ndarray,value: np.ndarray,slope: float,nv: int,max_iter: int=RELAX_MAX) -> np.ndarray:
	i,j=edges[:,0],edges[:,1]
	v=value.copy()
	step=slope * length
	for _ in range(max_iter):
		cand_i=np.full(nv,np.inf)
		cand_j=np.full(nv,np.inf)
		np.minimum.at(cand_i,i,v[j] + step)
		np.minimum.at(cand_j,j,v[i] + step)
		new=np.minimum(v,np.minimum(cand_i,cand_j))
		if np.allclose(new,v,rtol=0,atol=1e-12):
			return new
		v=new
	return v
def local_thickness(mesh):
	try:
		from mathutils import Vector
		from mathutils.bvhtree import BVHTree
	except ImportError:
		return None
	V=np.asarray(mesh.V,dtype=float)
	F=np.asarray(mesh.F,dtype=int)
	if not len(F):
		return None
	N=getattr(mesh, "VN",None)
	if N is None:
		N=np.zeros_like(V)
		tri=V[F]
		fn=np.cross(tri[:,1] - tri[:,0],tri[:,2] - tri[:,0])
		for k in range(3):
			np.add.at(N,F[:,k],fn)
		ln=np.linalg.norm(N,axis=1,keepdims=True)
		N=N / np.maximum(ln,1e-20)
	tree=BVHTree.FromPolygons([tuple(v) for v in V],[tuple(f) for f in F])
	span=float(np.ptp(V,axis=0).max()) or 1.0
	eps=span * 1e-5
	out=np.full(len(V),np.inf)
	for i in range(len(V)):
		n=Vector(N[i])
		o=Vector(V[i]) - n * eps
		hit=tree.ray_cast(o,-n,span)
		if hit and hit[0] is not None and hit[3] > eps:
			out[i]=hit[3]
	return out
def sizing_field(mesh,base: float,feature_angle: float=30.0,feature_strength: float=1.0,curvature_strength: float=1.0,inner_density: float=0.0,outer_density: float=0.0,thin_strength: float=1.0,min_ratio: float=0.3,band: float=2.5,gradient_limit: float=0.4) -> np.ndarray:
	nv=mesh.nv
	edges=mesh.edges
	elen=np.linalg.norm(mesh.V[edges[:,0]] - mesh.V[edges[:,1]],axis=1)
	floor=base * float(min_ratio)
	request=np.full(nv,base)
	if feature_strength > 0.0:
		feat=mesh.feature_edges(feature_angle)
		if feat.any():
			seed=np.zeros(nv,dtype=bool)
			seed[edges[feat].ravel()]=True
			dist=np.where(seed,0.0,np.inf)
			dist=_relax_min(edges,elen,dist,1.0,nv)
			reach=max(band * base,1e-20)
			t=np.clip(dist / reach,0.0,1.0)
			near=floor + (base - floor) * t
			request=np.minimum(request,base + (near - base) * float(feature_strength))
	if curvature_strength > 0.0:
		k1,k2,_,_=mesh.curvature()
		kmag=np.maximum(np.abs(k1),np.abs(k2))
		kmag=np.nan_to_num(kmag,nan=0.0,posinf=0.0,neginf=0.0)
		ref=np.percentile(kmag,95) if nv else 0.0
		if ref > 1e-12:
			t=np.clip(kmag / ref,0.0,1.0)
			curv=base + (floor - base) * t
			request=np.minimum(request,base + (curv - base) * float(curvature_strength))
	if inner_density > 0.0 or outer_density > 0.0:
		from .detect import edge_field
		ef=edge_field(mesh,feature_angle,inner_weight=float(inner_density),outer_weight=float(outer_density))
		imp=np.clip(np.maximum(ef["inner"],ef["outer"]),0.0,1.0)
		request=np.minimum(request,base + (floor - base) * imp)
	if thin_strength > 0.0:
		thin=local_thickness(mesh)
		if thin is not None:
			want=thin * 0.7
			want=np.where(np.isfinite(want) & (want > 0.0),want,base)
			request=np.minimum(request,base + (np.minimum(want,base) - base)
				* float(thin_strength))
	request=np.clip(request,floor,base)
	return _relax_min(edges,elen,request,float(gradient_limit),nv)
def estimate_faces(mesh,sizing: np.ndarray) -> float:
	tri=mesh.F
	s=sizing[tri].mean(axis=1)
	return float(np.sum(mesh.face_area / np.maximum(s * s,1e-20)))
def fit_to_target(mesh,sizing: np.ndarray,target_faces: int,iterations: int=12) -> np.ndarray:
	if not target_faces:
		return sizing
	lo,hi=0.05,1.0
	for _ in range(60):
		if estimate_faces(mesh,sizing * hi) <=target_faces:
			break
		lo=hi
		hi *=2.0
	for _ in range(max(iterations,40)):
		mid=0.5 * (lo + hi)
		if estimate_faces(mesh,sizing * mid) > target_faces:
			lo=mid
		else:
			hi=mid
	return sizing * (0.5 * (lo + hi))