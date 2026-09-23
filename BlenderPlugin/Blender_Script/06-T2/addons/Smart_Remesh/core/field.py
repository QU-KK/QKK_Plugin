from __future__ import annotations
from ..G import *
"""Orientation and position fields - the two halves of field-guided remeshing.
The orientation field decides which way the quads run; the position field
decides where their corners land. Both are solved by Jacobi iteration over the
edge list,which vectorises cleanly and needs no linear solver.
Neither uses any Blender operator. The only external dependency is numpy.
"""
import numpy as np
from . import hierarchy as HR
def _accumulate(nv: int,idx: np.ndarray,vals: np.ndarray) -> np.ndarray:
	out=np.empty((nv,3))
	for k in range(3):
		out[:,k]=np.bincount(idx,weights=vals[:,k],minlength=nv)
	return out
def _normalize(x: np.ndarray,eps: float=1e-20) -> np.ndarray:
	return x / np.maximum(np.linalg.norm(x,axis=1,keepdims=True),eps)
def _project(x: np.ndarray,n: np.ndarray) -> np.ndarray:
	return x - np.sum(x * n,axis=1,keepdims=True) * n
def _best_rosy(target: np.ndarray,other: np.ndarray,n: np.ndarray) -> np.ndarray:
	a=_normalize(_project(other,n))
	b=np.cross(n,a)
	da=np.sum(target * a,axis=1)
	db=np.sum(target * b,axis=1)
	use_a=np.abs(da) >=np.abs(db)
	chosen=np.where(use_a[:,None],a,b)
	sign=np.where(use_a,np.sign(da),np.sign(db))
	sign=np.where(sign==0,1.0,sign)
	return chosen * sign[:,None]
def feature_constraints(mesh,feature_mask: np.ndarray):
	e=mesh.edges[feature_mask]
	n=mesh.normal
	u,v=mesh.frames
	nv=mesh.nv
	locked=np.zeros(nv,dtype=bool)
	if not len(e):
		return locked,np.zeros((nv,3)),np.zeros(nv,dtype=bool),\
			np.zeros((nv,3))
	d=mesh.V[e[:,1]] - mesh.V[e[:,0]]
	d=_normalize(d)
	zr=np.zeros(nv)
	zi=np.zeros(nv)
	tang=np.zeros((nv,3))
	count=np.zeros(nv)
	for side,sign in ((e[:,0],1.0),(e[:,1],-1.0)):
		dp=_normalize(_project(d * sign,n[side]))
		th=np.arctan2(np.sum(dp * v[side],axis=1),np.sum(dp * u[side],axis=1))
		zr +=np.bincount(side,weights=np.cos(4 * th),minlength=nv)
		zi +=np.bincount(side,weights=np.sin(4 * th),minlength=nv)
		count +=np.bincount(side,minlength=nv)
		tang +=_accumulate(nv,side,dp)
	locked=count > 0
	theta=np.arctan2(zi,zr) / 4.0
	direction=np.cos(theta)[:,None] * u + np.sin(theta)[:,None] * v
	direction=_normalize(_project(direction,n))
	coherence=np.hypot(zr,zi) / np.maximum(count,1)
	tang=_normalize(tang)
	corner=locked & (coherence < 0.5)
	corner |=count >=3
	return locked,direction,corner,tang
def orientation_field(mesh,iterations: int=40,feature_angle: float=30.0,use_curvature: bool=True,progress=None):
	n=mesh.normal
	e=mesh.edges
	i,j=e[:,0],e[:,1]
	nv=mesh.nv
	feat=mesh.feature_edges(feature_angle)
	locked,locked_dir,corner,feat_tangent=feature_constraints(mesh,feat)
	if use_curvature:
		_,_,dir1,aniso=mesh.curvature()
		o=_normalize(_project(dir1,n))
		bad=~np.isfinite(o).all(axis=1) | (np.linalg.norm(o,axis=1) < 0.5)
		if bad.any():
			u,_=mesh.frames
			o[bad]=u[bad]
	else:
		u,_=mesh.frames
		o=u.copy()
	o[locked]=locked_dir[locked]
	w=np.ones(len(e))
	w[feat]=8.0
	def sweep(o_,n_,e_,w_,its,lock=None,lock_dir=None,cb=None):
		ii,jj=e_[:,0],e_[:,1]
		m=len(n_)
		for k in range(its):
			acc=np.zeros((m,3))
			acc +=_accumulate(m,ii,_best_rosy(o_[ii],o_[jj],n_[ii]) * w_[:,None])
			acc +=_accumulate(m,jj,_best_rosy(o_[jj],o_[ii],n_[jj]) * w_[:,None])
			acc +=o_
			nxt=_normalize(_project(acc,n_))
			degenerate=np.linalg.norm(nxt,axis=1) < 0.5
			nxt[degenerate]=o_[degenerate]
			o_=nxt
			if lock is not None:
				o_[lock]=lock_dir[lock]
			if cb is not None and k % 5==0:
				cb(k / max(its,1))
		return o_
	levels=HR.build(mesh.V,n,e)
	if len(levels) > 1:
		coarse=o
		for lv in range(len(levels) - 1):
			coarse=HR.restrict(levels[lv]["parent"],levels[lv + 1]["nv"],coarse)
		for lv in range(len(levels) - 1,0,-1):
			L=levels[lv]
			if len(L["edges"]):
				coarse=_normalize(_project(coarse,L["normal"]))
				bad=np.linalg.norm(coarse,axis=1) < 0.5
				if bad.any():
					coarse[bad]=_normalize(_project(np.roll(L["normal"][bad],1,axis=1),L["normal"][bad]))
				coarse=sweep(coarse,L["normal"],L["edges"],np.ones(len(L["edges"])),iterations)
			coarse=HR.prolong(levels[lv - 1]["parent"],coarse)
		seeded=_normalize(_project(coarse,n))
		ok=np.linalg.norm(seeded,axis=1) >=0.5
		o[ok]=seeded[ok]
		o[locked]=locked_dir[locked]
	o=sweep(o,n,e,w,iterations,locked,locked_dir,progress)
	return o,locked,corner,feat_tangent
def comb_field(mesh,o: np.ndarray) -> np.ndarray:
	start,nbr=mesh.adjacency
	n=mesh.normal
	ox,oy,oz=(o[:,0].tolist(),o[:,1].tolist(),o[:,2].tolist())
	nx,ny,nz=(n[:,0].tolist(),n[:,1].tolist(),n[:,2].tolist())
	nbr_l=nbr.tolist()
	start_l=start.tolist()
	visited=bytearray(mesh.nv)
	for seed in range(mesh.nv):
		if visited[seed]:
			continue
		visited[seed]=1
		stack=[seed]
		while stack:
			a=stack.pop()
			ax,ay,az=ox[a],oy[a],oz[a]
			for k in range(start_l[a],start_l[a + 1]):
				b=nbr_l[k]
				if visited[b]:
					continue
				visited[b]=1
				bx,by,bz=ox[b],oy[b],oz[b]
				mx,my,mz=nx[b],ny[b],nz[b]
				cx=my * bz - mz * by
				cy=mz * bx - mx * bz
				cz=mx * by - my * bx
				da=ax * bx + ay * by + az * bz
				db=ax * cx + ay * cy + az * cz
				if da * da >=db * db:
					if da < 0.0:
						bx,by,bz=-bx,-by,-bz
				else:
					bx,by,bz=(cx,cy,cz) if db >=0.0 else (-cx,-cy,-cz)
				ox[b],oy[b],oz[b]=bx,by,bz
				stack.append(b)
	return np.stack([np.asarray(ox),np.asarray(oy),np.asarray(oz)],axis=1)
def position_field(mesh,o: np.ndarray,scale,iterations: int=40,locked: np.ndarray | None=None,corner: np.ndarray | None=None,feat_tangent: np.ndarray | None=None,progress=None) -> np.ndarray:
	n=mesh.normal
	e=mesh.edges
	i,j=e[:,0],e[:,1]
	nv=mesh.nv
	V=mesh.V
	t=np.cross(n,o)
	p=V.copy()
	anchor=1.0
	sv=np.full(nv,float(scale)) if np.isscalar(scale) else np.asarray(scale,float)
	se=0.5 * (sv[i] + sv[j])
	for it in range(iterations):
		acc=np.zeros((nv,3))
		cnt=np.zeros(nv)
		for a,b in ((i,j),(j,i)):
			delta=p[b] - p[a]
			ka=np.round(np.sum(delta * o[a],axis=1) / se)
			kb=np.round(np.sum(delta * t[a],axis=1) / se)
			q=p[b] - se[:,None] * (ka[:,None] * o[a] + kb[:,None] * t[a])
			acc +=_accumulate(nv,a,q)
			cnt +=np.bincount(a,minlength=nv)
		acc +=anchor * V
		cnt +=anchor
		p=acc / cnt[:,None]
		p=V + _project(p - V,n)
		d=p - V
		L=np.linalg.norm(d,axis=1)
		leash=0.5 * sv
		far=L > leash
		if far.any():
			p[far]=V[far] + d[far] * (leash[far] / L[far])[:,None]
		if locked is not None and feat_tangent is not None:
			m=locked & ~(corner if corner is not None
						   else np.zeros(nv,dtype=bool))
			if m.any():
				dd=p[m] - V[m]
				tg=feat_tangent[m]
				p[m]=V[m] + np.sum(dd * tg,axis=1)[:,None] * tg
			if corner is not None and corner.any():
				p[corner]=V[corner]
		if progress is not None and it % 5==0:
			progress(it / iterations)
	return p