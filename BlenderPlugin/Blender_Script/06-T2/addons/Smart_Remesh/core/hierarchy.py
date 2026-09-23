from __future__ import annotations
from ..G import *
"""Coarse-to-fine solving for the orientation field.
Jacobi iteration over the edge list moves information one edge per sweep. On a
33k-vertex statue that means a direction chosen at the head needs thousands of
sweeps to reach the feet,and it never gets there: measured on that model,the
field stops changing after about 400 sweeps and the result is *worse* than at
40 - boundary edges 244 -> 266 on a test sphere,because it has settled into a
local minimum rather than converged to the right answer.
Regions that end up disagreeing with their neighbours cannot be walked into
quads,and the extraction leaves them as 23- and 24-sided rings it refuses to
fill. That is where the boundary edges in the output come from. Filling them
anyway was tried and is worse - non-manifold edges went 22 -> 106 on the same
sphere - because those rings are not holes,they are the shape of the failure.
The fix is the one the Instant Meshes paper is built around (Jakob,Tarini,
Panozzo,Sorkine-Hornung,SIGGRAPH Asia 2015,`MultiResolutionHierarchy` in
their `hierarchy.cpp`): solve on a coarsened copy of the mesh first,where the
whole surface is a few hundred vertices and information crosses it in a handful
of sweeps,then carry that answer down and refine it. The solver itself does
not change - the same Jacobi sweep runs at every level. Only the starting point
changes,and that is what decides which minimum it lands in.
This module is only the hierarchy: how to coarsen,and how to carry a field up
and down it. The field maths stays in `field.py`.
"""
import numpy as np
def _pair_up(nv: int,edges: np.ndarray,weight: np.ndarray) -> np.ndarray:
	order=np.argsort(-weight,kind="stable")
	parent=np.full(nv,-1,dtype=np.int64)
	taken=np.zeros(nv,dtype=bool)
	nc=0
	for e in order:
		a=int(edges[e,0])
		b=int(edges[e,1])
		if taken[a] or taken[b]:
			continue
		taken[a]=taken[b]=True
		parent[a]=parent[b]=nc
		nc +=1
	free=np.flatnonzero(parent < 0)
	parent[free]=np.arange(nc,nc + len(free))
	return parent,nc + len(free)
def build(V: np.ndarray,normal: np.ndarray,edges: np.ndarray,min_verts: int=64,max_levels: int=12) -> list:
	levels=[{"V": V, "normal": normal, "edges": edges, "parent": None, "nv": len(V)}]
	while len(levels) < max_levels and levels[-1]["nv"] > min_verts:
		cur=levels[-1]
		e=cur["edges"]
		if len(e)==0:
			break
		d=cur["V"][e[:,0]] - cur["V"][e[:,1]]
		length=np.linalg.norm(d,axis=1)
		align=np.abs(np.einsum("ij,ij->i",cur["normal"][e[:,0]],cur["normal"][e[:,1]]))
		w=align / np.maximum(length,1e-12)
		parent,nc=_pair_up(cur["nv"],e,w)
		if nc >=cur["nv"]:
			break
		cV=np.zeros((nc,3))
		cN=np.zeros((nc,3))
		cnt=np.bincount(parent,minlength=nc).astype(np.float64)
		for k in range(3):
			cV[:,k]=np.bincount(parent,weights=cur["V"][:,k],minlength=nc)
			cN[:,k]=np.bincount(parent,weights=cur["normal"][:,k],minlength=nc)
		cV /=np.maximum(cnt,1)[:,None]
		bad=np.linalg.norm(cN,axis=1) < 1e-12
		if bad.any():
			first=np.zeros(nc,dtype=np.int64)
			first[parent[::-1]]=np.arange(cur["nv"])[::-1]
			cN[bad]=cur["normal"][first[bad]]
		cN /=np.maximum(np.linalg.norm(cN,axis=1),1e-12)[:,None]
		ce=parent[e]
		ce=ce[ce[:,0] !=ce[:,1]]
		if len(ce):
			ce=np.unique(np.sort(ce,axis=1),axis=0)
		cur["parent"]=parent
		levels.append({"V": cV, "normal": cN, "edges": ce, "parent": None, "nv": nc})
	return levels
def restrict(parent: np.ndarray,nc: int,x: np.ndarray) -> np.ndarray:
	out=np.zeros((nc,x.shape[1]))
	for k in range(x.shape[1]):
		out[:,k]=np.bincount(parent,weights=x[:,k],minlength=nc)
	cnt=np.maximum(np.bincount(parent,minlength=nc),1)[:,None]
	return out / cnt
def prolong(parent: np.ndarray,x: np.ndarray) -> np.ndarray:
	return x[parent]