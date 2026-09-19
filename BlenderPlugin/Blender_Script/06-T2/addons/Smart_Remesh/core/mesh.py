from __future__ import annotations
from ..G import *
"""Mesh preparation for the field solver. numpy only - Blender ships no scipy.
Everything here is built from sorting and scatter-adds rather than sparse
matrix libraries,for that reason.
"""
import numpy as np
class TriMesh:
	"""Triangulated working copy with the adjacency the field solver needs.
	The original polygon structure is remembered only through `virtual_edge`:
	edges that exist purely because a polygon was fanned into triangles. Those
	must never be treated as real geometry - in particular a diagonal across a
	flat n-gon is not a feature edge,however the dihedral angle comes out.
	"""
	def __init__(self,V: np.ndarray,tris: np.ndarray,virtual: np.ndarray | None=None) -> None:
		self.V=np.ascontiguousarray(V,dtype=np.float64)
		self.F=np.ascontiguousarray(tris,dtype=np.int64)
		self._virtual_pairs=virtual
	@classmethod
	def from_polys(cls,V,face_verts,face_sizes) -> "TriMesh":
		face_verts=np.asarray(face_verts,dtype=np.int64)
		face_sizes=np.asarray(face_sizes,dtype=np.int64)
		starts=np.concatenate([[0],np.cumsum(face_sizes)[:-1]])
		per=face_sizes - 2
		tri_face=np.repeat(np.arange(len(face_sizes)),per)
		tstarts=np.concatenate([[0],np.cumsum(per)[:-1]])
		off=np.arange(int(per.sum())) - np.repeat(tstarts,per)
		base=starts[tri_face]
		tris=np.stack([face_verts[base],face_verts[base + off + 1],face_verts[base + off + 2]],axis=1)
		nxt=(np.arange(len(face_verts)) - np.repeat(starts,face_sizes) + 1) \
			% np.repeat(face_sizes,face_sizes) + np.repeat(starts,face_sizes)
		real=np.stack([face_verts,face_verts[nxt]],axis=1)
		real=np.sort(real,axis=1)
		return cls(V,tris,virtual=real)
	@property
	def nv(self) -> int:
		return len(self.V)
	@property
	def nf(self) -> int:
		return len(self.F)
	def _cache(self,key,fn):
		cache=self.__dict__.setdefault("_c",{})
		if key not in cache:
			cache[key]=fn()
		return cache[key]
	@property
	def edges(self) -> np.ndarray:
		return self._cache("edges",self._build_edges)[0]
	@property
	def edge_faces(self) -> np.ndarray:
		return self._cache("edges",self._build_edges)[1]
	def _build_edges(self):
		F=self.F
		pairs=np.concatenate([F[:,[0,1]],F[:,[1,2]],F[:,[2,0]]])
		owner=np.tile(np.arange(self.nf),3)
		key=np.sort(pairs,axis=1)
		flat=key[:,0] * np.int64(self.nv) + key[:,1]
		order=np.argsort(flat,kind="stable")
		flat_s=flat[order]
		first=np.concatenate([[True],flat_s[1:] !=flat_s[:-1]])
		eid=np.cumsum(first) - 1
		ne=int(eid[-1]) + 1 if len(eid) else 0
		edges=np.empty((ne,2),dtype=np.int64)
		uniq=flat_s[first]
		edges[:,0]=uniq // self.nv
		edges[:,1]=uniq % self.nv
		ef=np.full((ne,2),-1,dtype=np.int64)
		grp_start=np.searchsorted(eid,np.arange(ne))
		rank=np.arange(len(eid)) - grp_start[eid]
		owner_sorted=owner[order]
		for s in (0,1):
			sel=rank==s
			ef[eid[sel],s]=owner_sorted[sel]
		return edges,ef
	@property
	def deg(self) -> np.ndarray:
		return self._cache("deg",lambda: np.bincount(self.edges.ravel(),minlength=self.nv))
	@property
	def adjacency(self):
		return self._cache("adj",self._adjacency)
	def _adjacency(self):
		e=self.edges
		src=np.concatenate([e[:,0],e[:,1]])
		dst=np.concatenate([e[:,1],e[:,0]])
		order=np.argsort(src,kind="stable")
		cnt=np.bincount(src,minlength=self.nv)
		start=np.concatenate([[0],np.cumsum(cnt)])
		return start,dst[order]
	@property
	def face_normal(self) -> np.ndarray:
		return self._cache("fn",self._face_normal)
	def _face_normal(self):
		P=self.V[self.F]
		n=np.cross(P[:,1] - P[:,0],P[:,2] - P[:,0])
		return n
	@property
	def face_area(self) -> np.ndarray:
		return self._cache("fa",lambda: 0.5 * np.linalg.norm(self.face_normal,axis=1))
	@property
	def normal(self) -> np.ndarray:
		return self._cache("vn",self._vertex_normal)
	def _vertex_normal(self):
		n=np.zeros_like(self.V)
		for k in range(3):
			np.add.at(n,self.F[:,k],self.face_normal)
		mag=np.linalg.norm(n,axis=1,keepdims=True)
		return n / np.maximum(mag,1e-20)
	@property
	def frames(self):
		return self._cache("frames",self._frames)
	def _frames(self):
		n=self.normal
		helper=np.zeros_like(n)
		helper[np.arange(self.nv),np.argmin(np.abs(n),axis=1)]=1.0
		u=np.cross(n,helper)
		u /=np.maximum(np.linalg.norm(u,axis=1,keepdims=True),1e-20)
		return u,np.cross(n,u)
	@property
	def mean_edge(self) -> float:
		e=self.edges
		return float(np.linalg.norm(self.V[e[:,0]] - self.V[e[:,1]],axis=1).mean())
	@property
	def total_area(self) -> float:
		return float(self.face_area.sum())
	@property
	def diagonal(self) -> float:
		lo,hi=self.V.min(axis=0),self.V.max(axis=0)
		return float(np.linalg.norm(hi - lo)) or 1.0
	def curvature(self):
		return self._cache("curv",self._curvature)
	def _curvature(self):
		u,v=self.frames
		n=self.normal
		e=self.edges
		i,j=e[:,0],e[:,1]
		M=np.zeros((self.nv,3,3))
		rhs=np.zeros((self.nv,3))
		for a,b in ((i,j),(j,i)):
			d=self.V[b] - self.V[a]
			dn=n[b] - n[a]
			L=np.maximum(np.linalg.norm(d,axis=1),1e-20)
			ex=np.sum(d * u[a],axis=1) / L
			ey=np.sum(d * v[a],axis=1) / L
			dx=np.sum(dn * u[a],axis=1) / L
			dy=np.sum(dn * v[a],axis=1) / L
			r1=np.stack([ex,ey,np.zeros_like(ex)],axis=1)
			r2=np.stack([np.zeros_like(ex),ex,ey],axis=1)
			np.add.at(M,a,r1[:,:,None] * r1[:,None,:] + r2[:,:,None] * r2[:,None,:])
			np.add.at(rhs,a,r1 * dx[:,None] + r2 * dy[:,None])
		M +=np.eye(3) * 1e-9 * np.maximum(np.trace(M,axis1=1,axis2=2),
										   1e-12)[:,None,None]
		coef=np.linalg.solve(M,rhs[:,:,None])[:,:,0]
		coef=np.nan_to_num(coef)
		a_,b_,c_=coef[:,0],coef[:,1],coef[:,2]
		tr=a_ + c_
		disc=np.sqrt(np.maximum(((a_ - c_) * 0.5) ** 2 + b_ * b_,0.0))
		k1=tr * 0.5 + disc
		k2=tr * 0.5 - disc
		ex=np.where(np.abs(b_) > 1e-14,b_,1.0)
		ey=np.where(np.abs(b_) > 1e-14,k1 - a_,0.0)
		mag=np.maximum(np.hypot(ex,ey),1e-20)
		dir1=(ex / mag)[:,None] * u + (ey / mag)[:,None] * v
		aniso=np.abs(k1 - k2) / (np.abs(k1) + np.abs(k2) + 1e-12)
		return k1,k2,dir1,aniso
	def feature_edges(self,angle_deg: float=30.0) -> np.ndarray:
		ef=self.edge_faces
		boundary=ef[:,1] < 0
		fn=self.face_normal
		mag=np.linalg.norm(fn,axis=1,keepdims=True)
		fnn=fn / np.maximum(mag,1e-20)
		a=np.clip(ef[:,0],0,None)
		b=np.clip(ef[:,1],0,None)
		cos=np.sum(fnn[a] * fnn[b],axis=1)
		sharp=(~boundary) & (cos < np.cos(np.radians(angle_deg)))
		if self._virtual_pairs is not None:
			rp=self._virtual_pairs
			real_key=np.unique(rp[:,0] * np.int64(self.nv) + rp[:,1])
			keys=np.sort(self.edges,axis=1)
			is_real=np.isin(keys[:,0] * np.int64(self.nv) + keys[:,1],real_key)
			sharp &=is_real
			boundary &=is_real
		return sharp | boundary