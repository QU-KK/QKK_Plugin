from __future__ import annotations
from ..G import *
"""Hard-surface rebuild: flat panels as n-gons,geometry only at the edges.
Modelled on what the reference assets actually do rather than on what a
remesher usually produces. Measured on a real bevelled asset (Sci-Fi
Container): 5,012 quads in the chamfer bands,337 n-gons for the panels,the
largest a 72-gon,and edge lengths varying 37x between band and panel. Only 3%
of its edges are flat - because the panels have no interior edges at all.
Pipeline:
  1. group faces into flat regions (dihedral below a threshold)
  2. extract each region's boundary as closed loops
  3. simplify the boundary network *globally*,once
  4. inset each loop and build a chamfer band in the gap
  5. emit the remaining interior as a single n-gon
EXPERIMENTAL. Known defects are listed in the module docstring of the operator
and reported in the returned log - read them before trusting the output.
numpy only,so it runs inside Blender.
"""
from collections import defaultdict
import numpy as np
from .extract import DisjointSet
def _topology(V,face_verts,face_sizes):
	nv=len(V)
	nf=len(face_sizes)
	starts=np.concatenate([[0],np.cumsum(face_sizes)[:-1]])
	nxt=(np.arange(len(face_verts)) - np.repeat(starts,face_sizes) + 1) \
		% np.repeat(face_sizes,face_sizes) + np.repeat(starts,face_sizes)
	a,b=face_verts,face_verts[nxt]
	owner=np.repeat(np.arange(nf),face_sizes)
	key=np.minimum(a,b) * np.int64(nv) + np.maximum(a,b)
	order=np.argsort(key,kind="stable")
	ks=key[order]
	first=np.concatenate([[True],ks[1:] !=ks[:-1]])
	eid=np.cumsum(first) - 1
	ne=int(eid[-1]) + 1 if len(eid) else 0
	uk=ks[first]
	edges=np.stack([uk // nv,uk % nv],axis=1)
	gstart=np.searchsorted(eid,np.arange(ne))
	rank=np.arange(len(eid)) - gstart[eid]
	pair=np.full((ne,2),-1,dtype=np.int64)
	ow=owner[order]
	for s in (0,1):
		sel=rank==s
		pair[eid[sel],s]=ow[sel]
	return starts,edges,pair
def _face_normals_areas(V,face_verts,face_sizes,starts):
	p0=V[face_verts]
	nxt=(np.arange(len(face_verts)) - np.repeat(starts,face_sizes) + 1) \
		% np.repeat(face_sizes,face_sizes) + np.repeat(starts,face_sizes)
	p1=V[face_verts[nxt]]
	newell=0.5 * np.add.reduceat(np.cross(p0,p1),starts,axis=0)
	area=np.linalg.norm(newell,axis=1)
	normal=newell / np.maximum(area,1e-20)[:,None]
	return normal,area
def _dp(pts,idxs,tol):
	if len(idxs) < 3:
		return list(idxs)
	keep=[0,len(idxs) - 1]
	stack=[(0,len(idxs) - 1)]
	while stack:
		i,j=stack.pop()
		if j - i < 2:
			continue
		a,b=pts[i],pts[j]
		ab=b - a
		L=np.linalg.norm(ab)
		if L < 1e-15:
			d=np.linalg.norm(pts[i + 1:j] - a,axis=1)
		else:
			t=np.clip(((pts[i + 1:j] - a) @ ab) / (L * L),0,1)
			d=np.linalg.norm(pts[i + 1:j] - (a + t[:,None] * ab),axis=1)
		if not len(d):
			continue
		m=int(np.argmax(d))
		if d[m] > tol:
			k=i + 1 + m
			keep.append(k)
			stack.append((i,k))
			stack.append((k,j))
	return [idxs[k] for k in sorted(set(keep))]
def analyse(V,fv,fs,starts,edges,pair,fn,fa,*,iterations=18,sigma_r=0.35):
	nf=len(fs)
	man=(pair[:,0] >=0) & (pair[:,1] >=0)
	A,B=pair[man,0],pair[man,1]
	fc=np.empty((nf,3))
	for k in range(3):
		fc[:,k]=np.add.reduceat(V[fv][:,k],starts) / fs
	sig_s=2.0 * float(np.linalg.norm(fc[A] - fc[B],axis=1).mean())
	ws=np.exp(-np.einsum("ij,ij->i",fc[A] - fc[B],fc[A] - fc[B])
				/ (2 * sig_s * sig_s))
	n=fn.copy()
	for _ in range(iterations):
		dn=np.einsum("ij,ij->i",n[A] - n[B],n[A] - n[B])
		w=ws * np.exp(-dn / (2 * sigma_r * sigma_r))
		acc=np.zeros_like(n)
		for k in range(3):
			acc[:,k]=np.bincount(A,weights=w * fa[B] * n[B,k],minlength=nf)
			acc[:,k] +=np.bincount(B,weights=w * fa[A] * n[A,k],minlength=nf)
		acc +=fn * fa[:,None]
		n=acc / np.maximum(np.linalg.norm(acc,axis=1,keepdims=True),1e-20)
	ang=np.degrees(np.arccos(np.clip(np.einsum("ij,ij->i",n[A],n[B]),-1,1)))
	ssum=np.zeros(nf)
	scnt=np.zeros(nf)
	np.add.at(ssum,A,ang)
	np.add.at(scnt,A,1)
	np.add.at(ssum,B,ang)
	np.add.at(scnt,B,1)
	bend=ssum / np.maximum(scnt,1)
	for _ in range(2):
		s2=np.zeros(nf)
		c2=np.zeros(nf)
		np.add.at(s2,A,bend[B])
		np.add.at(c2,A,1)
		np.add.at(s2,B,bend[A])
		np.add.at(c2,B,1)
		bend=0.5 * bend + 0.5 * (s2 / np.maximum(c2,1))
	nbrA=(ssum[A] - ang) / np.maximum(scnt[A] - 1,1)
	nbrB=(ssum[B] - ang) / np.maximum(scnt[B] - 1,1)
	raw=np.degrees(np.arccos(np.clip(np.einsum("ij,ij->i",fn[A],fn[B]),-1,1)))
	return {"V": V, "edges": edges, "fa": fa, "nf": nf,"fv": fv, "fs": fs, "starts": starts,"man": man, "A": A, "B": B, "idx": np.flatnonzero(man), "pair": pair,"ang": ang, "bend": bend, "raw_ang": raw, "persist": ang - 0.5 * (nbrA + nbrB), "diag": float(np.linalg.norm(V.max(0) - V.min(0))) or 1.0,}
def coplanar_regions(cache,tol_deg,min_area=0.004):
	A,B,nf,fa=cache["A"],cache["B"],cache["nf"],cache["fa"]
	ds=DisjointSet(nf)
	flat=cache["raw_ang"] < tol_deg
	for x,y in zip(A[flat].tolist(),B[flat].tolist()):
		ds.union(x,y)
	root=np.fromiter((ds.find(i) for i in range(nf)),dtype=np.int64,count=nf)
	_,lab=np.unique(root,return_inverse=True)
	area=np.bincount(lab,weights=fa)
	total=max(float(fa.sum()),1e-20)
	big=area >=min_area * total
	return lab,big[lab],float(area[big].sum()) / total
def auto_thresholds(cache):
	def otsu(vals,lo,hi):
		vals=np.asarray(vals,dtype=np.float64)
		if not len(vals) or vals.max() <=0:
			return lo
		h,be=np.histogram(vals,bins=180,range=(0,float(vals.max()) + 1e-9))
		p=h / max(h.sum(),1)
		cw=np.cumsum(p)
		cm=np.cumsum(p * ((be[:-1] + be[1:]) / 2))
		den=cw * (1 - cw)
		sb=np.where(den > 1e-12,(cm[-1] * cw - cm) ** 2 / np.maximum(den,1e-12),0)
		return float(np.clip((be[:-1] + be[1:])[int(np.argmax(sb))] / 2,lo,hi))
	return otsu(np.maximum(cache["persist"],0),5.0,55.0),2.0
def classify(cache,crease_deg,flat_deg,min_chain=0.02,use_type=True,close_gaps=True,majority=3,gap_span=0.35):
	V,edges=cache["V"],cache["edges"]
	A,B,idx=cache["A"],cache["B"],cache["idx"]
	persist,bend,fa,nf=cache["persist"],cache["bend"],cache["fa"],cache["nf"]
	diag=cache["diag"]
	out=np.zeros(len(edges),dtype=bool)
	crease=np.zeros(len(edges),dtype=bool)
	crease[idx[persist > crease_deg]]=True
	typ=np.zeros(len(edges),dtype=bool)
	panel_pct=0.0
	if use_type:
		lab,is_panel,panel_pct=coplanar_regions(cache,flat_deg)
		typ[idx[is_panel[A] !=is_panel[B]]]=True
		typ[idx[is_panel[A] & is_panel[B] & (lab[A] !=lab[B])]]=True
	feat=crease | typ
	sel=np.flatnonzero(feat)
	if not len(sel):
		return out,{"n_crease": 0, "n_type": 0, "final": 0, "open_ends": 0, "panel_pct": panel_pct}
	ds2=DisjointSet(len(V))
	for a,b in zip(edges[sel,0].tolist(),edges[sel,1].tolist()):
		ds2.union(a,b)
	root2=np.fromiter((ds2.find(int(x)) for x in edges[sel,0]),dtype=np.int64,count=len(sel))
	_,inv=np.unique(root2,return_inverse=True)
	elen=np.linalg.norm(V[edges[sel,0]] - V[edges[sel,1]],axis=1)
	comp_len=np.bincount(inv,weights=elen)
	out[sel[comp_len[inv] > min_chain * diag]]=True
	if close_gaps:
		out=_close_gaps(V,edges,out,diag,max_span=gap_span)
	E=edges[out]
	val=np.bincount(E.ravel(),minlength=len(V)) if len(E) else np.zeros(1)
	return out,{"n_crease": int(crease.sum()), "n_type": int(typ.sum()),"final": int(out.sum()), "open_ends": int((val==1).sum()), "panel_pct": panel_pct}
def feature_edges(V,fv,fs,starts,edges,pair,fn,fa,*,iterations=18,sigma_r=0.35,min_chain=0.02,crease_deg=None,flat_deg=None):
	cache=analyse(V,fv,fs,starts,edges,pair,fn,fa,iterations=iterations,sigma_r=sigma_r)
	auto_c,auto_f=auto_thresholds(cache)
	c=auto_c if crease_deg is None else float(crease_deg)
	f=auto_f if flat_deg is None else float(flat_deg)
	mask,_info=classify(cache,c,f,min_chain=min_chain)
	return mask,c
def _feature_edges_legacy(V,fv,fs,starts,edges,pair,fn,fa,*,iterations=18,sigma_r=0.35,min_chain=0.02):
	nf=len(fs)
	man=(pair[:,0] >=0) & (pair[:,1] >=0)
	out=np.zeros(len(edges),dtype=bool)
	if not man.any():
		return out,0.0
	A,B=pair[man,0],pair[man,1]
	fc=np.empty((nf,3))
	for k in range(3):
		fc[:,k]=np.add.reduceat(V[fv][:,k],starts) / fs
	sig_s=2.0 * float(np.linalg.norm(fc[A] - fc[B],axis=1).mean())
	ws=np.exp(-np.einsum("ij,ij->i",fc[A] - fc[B],fc[A] - fc[B])
				/ (2 * sig_s * sig_s))
	n=fn.copy()
	for _ in range(iterations):
		dn=np.einsum("ij,ij->i",n[A] - n[B],n[A] - n[B])
		w=ws * np.exp(-dn / (2 * sigma_r * sigma_r))
		acc=np.zeros_like(n)
		for k in range(3):
			acc[:,k]=np.bincount(A,weights=w * fa[B] * n[B,k],minlength=nf)
			acc[:,k] +=np.bincount(B,weights=w * fa[A] * n[A,k],minlength=nf)
		acc +=fn * fa[:,None]
		n=acc / np.maximum(np.linalg.norm(acc,axis=1,keepdims=True),1e-20)
	ang=np.degrees(np.arccos(np.clip(np.einsum("ij,ij->i",n[A],n[B]),-1,1)))
	diag=float(np.linalg.norm(V.max(0) - V.min(0))) or 1.0
	idx=np.flatnonzero(man)
	def otsu(vals,lo,hi,bins=180):
		h,be=np.histogram(vals,bins=bins,range=(0,float(vals.max()) + 1e-9))
		p=h / max(h.sum(),1)
		cw=np.cumsum(p)
		cm=np.cumsum(p * ((be[:-1] + be[1:]) / 2))
		den=cw * (1 - cw)
		sb=np.where(den > 1e-12,(cm[-1] * cw - cm) ** 2 / np.maximum(den,1e-12),0)
		return float(np.clip((be[:-1] + be[1:])[int(np.argmax(sb))] / 2,lo,hi))
	ssum=np.zeros(nf)
	scnt=np.zeros(nf)
	np.add.at(ssum,A,ang)
	np.add.at(scnt,A,1)
	np.add.at(ssum,B,ang)
	np.add.at(scnt,B,1)
	bend=ssum / np.maximum(scnt,1)
	for _ in range(2):
		s2=np.zeros(nf)
		c2=np.zeros(nf)
		np.add.at(s2,A,bend[B])
		np.add.at(c2,A,1)
		np.add.at(s2,B,bend[A])
		np.add.at(c2,B,1)
		bend=0.5 * bend + 0.5 * (s2 / np.maximum(c2,1))
	nbrA=(ssum[A] - ang) / np.maximum(scnt[A] - 1,1)
	nbrB=(ssum[B] - ang) / np.maximum(scnt[B] - 1,1)
	persist=ang - 0.5 * (nbrA + nbrB)
	high=otsu(np.maximum(persist,0),12.0,55.0)
	crease=np.zeros(len(edges),dtype=bool)
	crease[idx[persist > high]]=True
	tflat=otsu(bend,1.0,60.0)
	curved=bend > tflat
	for _ in range(3):
		votes=np.zeros(nf)
		tot=np.zeros(nf)
		np.add.at(votes,A,curved[B].astype(float))
		np.add.at(tot,A,1)
		np.add.at(votes,B,curved[A].astype(float))
		np.add.at(tot,B,1)
		frac=votes / np.maximum(tot,1)
		flip=((frac > 0.75) & ~curved) | ((frac < 0.25) & curved)
		if not flip.any():
			break
		curved=np.where(flip,~curved,curved)
	ds=DisjointSet(nf)
	same=(curved[A]==curved[B]) & (persist <=high)
	for x,y in zip(A[same].tolist(),B[same].tolist()):
		ds.union(x,y)
	root=np.fromiter((ds.find(i) for i in range(nf)),dtype=np.int64,count=nf)
	_,flab=np.unique(root,return_inverse=True)
	area=np.bincount(flab,weights=fa)
	total=max(area.sum(),1e-20)
	for _ in range(3):
		small=area[flab] < 0.004 * total
		cross=flab[A] !=flab[B]
		cand=cross & (small[A] !=small[B])
		if not cand.any():
			break
		for x,y in zip(A[cand].tolist(),B[cand].tolist()):
			if area[flab[x]] < area[flab[y]]:
				flab[flab==flab[x]]=flab[y]
			else:
				flab[flab==flab[y]]=flab[x]
		_,flab=np.unique(flab,return_inverse=True)
		area=np.bincount(flab,weights=fa)
	typ=np.zeros(len(edges),dtype=bool)
	typ[idx[flab[A] !=flab[B]]]=True
	feat=crease | typ
	sel=np.flatnonzero(feat)
	if not len(sel):
		return out,high
	ds2=DisjointSet(len(V))
	for a,b in zip(edges[sel,0].tolist(),edges[sel,1].tolist()):
		ds2.union(a,b)
	root2=np.fromiter((ds2.find(int(x)) for x in edges[sel,0]),dtype=np.int64,count=len(sel))
	_,inv=np.unique(root2,return_inverse=True)
	elen=np.linalg.norm(V[edges[sel,0]] - V[edges[sel,1]],axis=1)
	comp_len=np.bincount(inv,weights=elen)
	keep=comp_len[inv] > min_chain * diag
	out[sel[keep]]=True
	out=_close_gaps(V,edges,out,diag)
	return out,high
def _close_gaps(V,edges,feat,diag,max_span=0.35,max_steps=4000,min_dot=0.55):
	nv=len(V)
	adj=defaultdict(list)
	for e,(a,b) in enumerate(edges.tolist()):
		adj[a].append((b,e))
		adj[b].append((a,e))
	for _round in range(4):
		sel=np.flatnonzero(feat)
		if not len(sel):
			return feat
		val=np.bincount(edges[sel].ravel(),minlength=nv)
		ends=np.flatnonzero(val==1)
		if not len(ends):
			return feat
		on_net=val > 0
		extended=False
		for s in ends.tolist():
			if val[s] !=1:
				continue
			prev=None
			for w,e in adj[s]:
				if feat[e]:
					prev=w
					break
			if prev is None:
				continue
			d=V[s] - V[prev]
			nd=np.linalg.norm(d)
			if nd < 1e-12:
				continue
			d=d / nd
			cur=s
			came=prev
			path=[]
			travelled=0.0
			hit=False
			for _step in range(max_steps):
				best=None
				for w,e in adj[cur]:
					if w==came or feat[e]:
						continue
					v=V[w] - V[cur]
					L=np.linalg.norm(v)
					if L < 1e-12:
						continue
					dot=float(np.dot(v / L,d))
					if dot < min_dot:
						continue
					score=dot
					if on_net[w]:
						score +=0.25
					if best is None or score > best[0]:
						best=(score,w,e,v / L,L)
				if best is None:
					break
				_sc,w,e,step_dir,L=best
				travelled +=L
				if travelled > max_span * diag:
					break
				path.append(e)
				if on_net[w]:
					hit=True
					break
				d=0.75 * d + 0.25 * step_dir
				nd=np.linalg.norm(d)
				if nd < 1e-12:
					break
				d /=nd
				came,cur=cur,w
			if hit and path:
				for e in path:
					feat[e]=True
				extended=True
				sel=np.flatnonzero(feat)
				val=np.bincount(edges[sel].ravel(),minlength=nv)
				on_net=val > 0
		if not extended:
			break
	return feat
def _plane_basis(P):
	Q=P - P.mean(axis=0)
	_,_,vt=np.linalg.svd(Q,full_matrices=False)
	return vt[0],vt[1]
def _pt_in_poly(p,poly):
	x,y=float(p[0]),float(p[1])
	inside=False
	n=len(poly)
	j=n - 1
	for i in range(n):
		xi,yi=poly[i]
		xj,yj=poly[j]
		if (yi > y) !=(yj > y):
			if x < (xj - xi) * (y - yi) / ((yj - yi) or 1e-30) + xi:
				inside=not inside
		j=i
	return inside
def _cut_holes(P2,outline,holes):
	polys=[list(outline)]
	orphan=0
	for H in sorted(holes,key=lambda h: -abs(_sarea(P2[h]))):
		c=P2[H].mean(axis=0)
		tgt=next((k for k,poly in enumerate(polys)
					if _pt_in_poly(c,P2[poly])),None)
		if tgt is None:
			polys.append(list(H))
			orphan +=1
			continue
		O=polys[tgt]
		res=_split_annulus(O,P2[O],list(H),P2[H])
		if res is None:
			orphan +=1
			continue
		polys[tgt:tgt + 1]=[list(res[0]),list(res[1])]
	return polys,orphan
def _straighten(V,edges,mask,tol):
	E=edges[mask]
	if not len(E) or tol <=0:
		return np.ones(len(V),dtype=bool)
	nbr=defaultdict(list)
	for a,b in E.tolist():
		nbr[a].append(b)
		nbr[b].append(a)
	node={v for v,ns in nbr.items() if len(ns) !=2}
	keep=np.zeros(len(V),dtype=bool)
	keep[list(node)]=True
	seen,done=set(),set(node)
	for s in node:
		for first in nbr[s]:
			if (s,first) in seen:
				continue
			chain=[s,first]
			seen.add((s,first))
			prev,cur=s,first
			while cur not in node:
				nxt=nbr[cur][0] if nbr[cur][1]==prev else nbr[cur][1]
				seen.add((cur,nxt))
				seen.add((nxt,cur))
				prev,cur=cur,nxt
				chain.append(cur)
			seen.add((chain[-1],chain[-2]))
			done.update(chain)
			keep[_dp(V[np.asarray(chain)],chain,tol)]=True
	for v in list(nbr):
		if v in done:
			continue
		ring,prev,cur=[v],v,nbr[v][0]
		while cur !=v and len(ring) <=len(nbr):
			ring.append(cur)
			nxt=nbr[cur][0] if nbr[cur][1]==prev else nbr[cur][1]
			prev,cur=cur,nxt
		done.update(ring)
		if cur !=v:
			keep[np.asarray(ring)]=True
			continue
		ring.append(v)
		keep[_dp(V[np.asarray(ring)],ring,tol)]=True
	return keep
def _bridge_loops(V,L1,L2):
	L1,L2=list(L1),list(L2)
	P1,P2=V[np.asarray(L1)],V[np.asarray(L2)]
	ax=P2.mean(0) - P1.mean(0)
	nn=np.linalg.norm(ax)
	ax=ax / nn if nn > 1e-12 else np.array([0.0,0.0,1.0])
	def wind(P):
		Q=P - P.mean(0)
		return float(np.sum(np.cross(Q,np.roll(Q,-1,axis=0)) @ ax))
	if wind(P1) * wind(P2) < 0:
		L2=L2[::-1]
		P2=V[np.asarray(L2)]
	k=int(np.argmin(np.linalg.norm(P2 - P1[0],axis=1)))
	L2,P2=L2[k:] + L2[:k],np.roll(P2,-k,axis=0)
	n1,n2=len(L1),len(L2)
	if n1==n2:
		return [[L1[i],L1[(i + 1) % n1],L2[(i + 1) % n1],L2[i]]
				for i in range(n1)],0
	def par(P):
		d=np.linalg.norm(np.roll(P,-1,axis=0) - P,axis=1)
		s=np.concatenate([[0.0],np.cumsum(d)])
		return s / max(s[-1],1e-12)
	s1,s2=par(P1),par(P2)
	faces,i,j=[],0,0
	while i < n1 or j < n2:
		if j >=n2 or (i < n1 and s1[i + 1] <=s2[j + 1]):
			faces.append([L1[i % n1],L1[(i + 1) % n1],L2[j % n2]])
			i +=1
		else:
			faces.append([L1[i % n1],L2[(j + 1) % n2],L2[j % n2]])
			j +=1
	return faces,len(faces)
def _region_planarity(V,verts):
	P=V[verts]
	if len(P) < 4:
		return 0.0
	Q=P - P.mean(axis=0)
	s=np.linalg.svd(Q,compute_uv=False)
	return float(s[2] / max(s[0],1e-12))
def panels_to_mesh(cache,mask,straighten=0.0,planar_tol=0.02,pinned=None):
	V,edges=cache["V"],cache["edges"]
	A,B,idx=cache["A"],cache["B"],cache["idx"]
	nf,fa=cache["nf"],cache["fa"]
	ds=DisjointSet(nf)
	for e,x,y in zip(idx.tolist(),A.tolist(),B.tolist()):
		if not mask[e]:
			ds.union(x,y)
	root=np.fromiter((ds.find(i) for i in range(nf)),dtype=np.int64,count=nf)
	_,lab=np.unique(root,return_inverse=True)
	nreg=int(lab.max()) + 1
	la=np.full(len(edges),-1,dtype=np.int64)
	lb=np.full(len(edges),-1,dtype=np.int64)
	la[idx]=lab[A]
	lb[idx]=lab[B]
	pair=cache.get("pair")
	if pair is not None:
		solo=((pair[:,0] >=0) ^ (pair[:,1] >=0))
		if solo.any():
			f_one=np.where(pair[:,0] >=0,pair[:,0],pair[:,1])
			la[solo]=lab[f_one[solo]]
			lb[solo]=-1
	is_bnd=mask & (la !=lb)
	fv,fs,starts=cache["fv"],cache["fs"],cache["starts"]
	reg_faces=defaultdict(list)
	for i in range(nf):
		reg_faces[int(lab[i])].append(i)
	curved=np.zeros(nreg,dtype=bool)
	for r,fl in reg_faces.items():
		vs=np.unique(np.concatenate([fv[starts[i]:starts[i] + fs[i]] for i in fl]))
		curved[r]=_region_planarity(V,vs) > planar_tol
	def chain_loops(sel,filt=None):
		E=edges[sel]
		inc=defaultdict(list)
		for i,(x,y) in enumerate(E.tolist()):
			inc[x].append(i)
			inc[y].append(i)
		used=np.zeros(len(E),dtype=bool)
		loops,broken=[],False
		for e0 in range(len(E)):
			if used[e0]:
				continue
			ch=[int(E[e0,0]),int(E[e0,1])]
			used[e0]=True
			for _ in range(len(E) + 2):
				v=ch[-1]
				k=next((i for i in inc[v] if not used[i]),None)
				if k is None:
					break
				used[k]=True
				x,y=int(E[k,0]),int(E[k,1])
				ch.append(y if x==v else x)
				if ch[-1]==ch[0]:
					break
			if ch[-1]==ch[0] and len(ch) > 3:
				c=ch[:-1] if filt is None else [v for v in ch[:-1] if filt[v]]
				if len(c) > 2:
					loops.append(c)
			else:
				broken=True
		return loops,broken
	region_sel={}
	for r in range(nreg):
		s=np.flatnonzero(is_bnd & ((la==r) | (lb==r)))
		if len(s):
			region_sel[r]=s
	as_is=np.zeros(nreg,dtype=bool)
	for r,s in region_sel.items():
		if curved[r]:
			as_is[r]=True
		else:
			_,broken=chain_loops(s)
			as_is[r]=broken
	hold=np.zeros(len(V),dtype=bool)
	for r,s in region_sel.items():
		if as_is[r]:
			hold[edges[s]]=True
	keep=_straighten(V,edges,mask,straighten * cache["diag"])
	if pinned is not None:
		keep=keep | np.asarray(pinned,dtype=bool)
	keep |=hold
	faces=[]
	line_pairs=set()
	rep={"panels": 0, "open": 0, "multi_loop": 0, "holes": 0, "orphan": 0,"bores": 0, "bridge_tris": 0, "dropped": int((~keep).sum()), "bore_faces": [], "face_panel": [], "kept_curved": 0, "fallback": 0, "curved_area_pct": 0.0}
	tot_area=max(float(fa.sum()),1e-20)
	for r,sel in region_sel.items():
		def as_source(reason,r=r,sel=sel):
			for i in reg_faces[r]:
				faces.append([int(x) for x in fv[starts[i]:starts[i] + fs[i]]])
				rep["face_panel"].append(r)
			for e in sel:
				x,y=int(edges[e,0]),int(edges[e,1])
				line_pairs.add((min(x,y),max(x,y)))
			rep[reason] +=1
			rep["curved_area_pct"] +=float(fa[reg_faces[r]].sum()) / tot_area
			rep["panels"] +=1
		if curved[r]:
			as_source("kept_curved")
			continue
		loops,broken=chain_loops(sel,keep)
		if broken or not loops:
			rep["open"] +=1
			as_source("fallback")
			continue
		for c in loops:
			for k in range(len(c)):
				x,y=c[k],c[(k + 1) % len(c)]
				line_pairs.add((min(x,y),max(x,y)))
		if len(loops)==1:
			faces.append(loops[0])
			rep["face_panel"].append(r)
			rep["panels"] +=1
			continue
		rep["multi_loop"] +=1
		ring_v=np.unique(np.concatenate([np.asarray(c) for c in loops]))
		Q=V[ring_v] - V[ring_v].mean(axis=0)
		sv=np.linalg.svd(Q,compute_uv=False)
		if len(loops)==2 and sv[2] > 0.05 * sv[0]:
			fs_,ntri=_bridge_loops(V,loops[0],loops[1])
			rep["bore_faces"].extend(range(len(faces),len(faces) + len(fs_)))
			rep["face_panel"].extend([-1] * len(fs_))
			faces.extend(fs_)
			rep["bores"] +=1
			rep["bridge_tris"] +=ntri
			rep["panels"] +=len(fs_)
			continue
		u,w=_plane_basis(V[ring_v])
		P2=np.zeros((len(V),2))
		P2[ring_v,0]=V[ring_v] @ u
		P2[ring_v,1]=V[ring_v] @ w
		areas=[abs(_sarea(P2[np.asarray(c)])) for c in loops]
		o=int(np.argmax(areas))
		loops=[c if _sarea(P2[np.asarray(c)]) > 0 else c[::-1] for c in loops]
		holes=[np.asarray(c) for k,c in enumerate(loops) if k !=o]
		rep["holes"] +=len(holes)
		polys,orphan=_cut_holes(P2,loops[o],holes)
		rep["orphan"] +=orphan
		rep["face_panel"].extend([r] * len(polys))
		faces.extend(polys)
		rep["panels"] +=len(polys)
	used_v=np.unique(np.concatenate([np.asarray(f) for f in faces])) \
		if faces else np.zeros(0,dtype=np.int64)
	remap=np.full(len(V),-1,dtype=np.int64)
	remap[used_v]=np.arange(len(used_v))
	faces=[[int(remap[i]) for i in f] for f in faces]
	lines=set()
	for a,b in line_pairs:
		x,y=int(remap[a]),int(remap[b])
		if x >=0 and y >=0:
			lines.add((min(x,y),max(x,y)))
	return V[used_v],faces,rep,lines
def _sarea(q):
	return 0.5 * np.sum(q[:,0] * np.roll(q[:,1],-1)
						- np.roll(q[:,0],-1) * q[:,1])
def _offset_ring(q2,W,slope=0.35,sgn=1.0,floor=0.08):
	L=len(q2)
	s=(1.0 if _sarea(q2) > 0 else -1.0) * sgn
	pv,nx=np.roll(q2,1,axis=0),np.roll(q2,-1,axis=0)
	d1=q2 - pv
	d1 /=np.maximum(np.linalg.norm(d1,axis=1,keepdims=True),1e-12)
	d2=nx - q2
	d2 /=np.maximum(np.linalg.norm(d2,axis=1,keepdims=True),1e-12)
	n1=np.stack([-d1[:,1],d1[:,0]],axis=1) * s
	n2=np.stack([-d2[:,1],d2[:,0]],axis=1) * s
	bis=n1 + n2
	bl=np.linalg.norm(bis,axis=1,keepdims=True)
	bis=np.where(bl > 1e-9,bis / np.maximum(bl,1e-12),n1)
	D=np.linalg.norm(q2[:,None,:] - q2[None,:,:],axis=2)
	k=np.arange(L)
	sep=np.abs(k[:,None] - k[None,:])
	sep=np.minimum(sep,L - sep)
	D[sep <=1]=np.inf
	Wv=np.minimum(W,0.45 * D.min(axis=1))
	seg=np.linalg.norm(np.roll(q2,-1,axis=0) - q2,axis=1)
	for _ in range(L):
		new=np.minimum(np.minimum(Wv,np.roll(Wv,1) + slope * np.roll(seg,1)),np.roll(Wv,-1) + slope * seg)
		if np.allclose(new,Wv):
			break
		Wv=new
	Wv=np.maximum(Wv,floor * W)
	den=np.sum(bis * n1,axis=1)
	step=np.minimum(np.where(np.abs(den) > 1e-6,Wv / np.maximum(np.abs(den),1e-6),Wv),2.0 * Wv)
	return q2 + bis * step[:,None]
def _weld_ring(pts,eps):
	n=len(pts)
	keep=[0]
	mapping=[0] * n
	for i in range(1,n):
		if np.linalg.norm(pts[i] - pts[keep[-1]]) < eps:
			mapping[i]=keep[-1]
		else:
			keep.append(i)
			mapping[i]=i
	if len(keep) > 2 and np.linalg.norm(pts[keep[-1]] - pts[keep[0]]) < eps:
		mapping[keep[-1]]=keep[0]
		keep.pop()
	return keep,mapping
def _split_annulus(O,PO,H,PH):
	LO,LH=len(O),len(H)
	D=np.linalg.norm(np.asarray(PO)[:,None,:] - np.asarray(PH)[None,:,:],axis=2)
	i1,j1=np.unravel_index(np.argmin(D),D.shape)
	best,bi,bj=None,-1,-1
	for i in range(LO):
		if min((i - i1) % LO,(i1 - i) % LO) < 2:
			continue
		j=int(np.argmin(D[i]))
		if min((j - j1) % LH,(j1 - j) % LH) < 2:
			continue
		if best is None or D[i,j] < best:
			best,bi,bj=float(D[i,j]),i,j
	if bi < 0:
		return None
	i2,j2=bi,bj
	A=[O[(i1 + k) % LO] for k in range((i2 - i1) % LO + 1)] + \
		[H[(j2 - k) % LH] for k in range((j2 - j1) % LH + 1)]
	B=[O[(i2 + k) % LO] for k in range((i1 - i2) % LO + 1)] + \
		[H[(j1 - k) % LH] for k in range((j1 - j2) % LH + 1)]
	for R in (A,B):
		if len(R) !=len(set(R)) or len(R) < 4:
			return None
	return A,B
def rebuild(V,face_verts,face_sizes,*,flat_angle: float=12.0,chamfer: float=0.008,simplify: float=0.004,use_detector: bool=True,crease_deg: float | None=None,flat_deg: float | None=None,progress=None) -> dict:
	V=np.ascontiguousarray(V,dtype=np.float64)
	face_verts=np.asarray(face_verts,dtype=np.int64)
	face_sizes=np.asarray(face_sizes,dtype=np.int64)
	nv,nf=len(V),len(face_sizes)
	diag=float(np.linalg.norm(V.max(0) - V.min(0))) or 1.0
	log: dict={}
	def step(name,frac):
		if progress:
			progress(name,frac)
	step("grouping panels",0.05)
	starts,edges,pair=_topology(V,face_verts,face_sizes)
	fn,fa=_face_normals_areas(V,face_verts,face_sizes,starts)
	man=(pair[:,0] >=0) & (pair[:,1] >=0)
	ang=np.zeros(len(edges))
	ang[man]=np.degrees(np.arccos(np.clip(np.einsum("ij,ij->i",fn[pair[man,0]],fn[pair[man,1]]),-1,1)))
	feat,otsu=feature_edges(V,face_verts,face_sizes,starts,edges,pair,fn,fa,crease_deg=crease_deg,flat_deg=flat_deg)
	if use_detector:
		cut=feat
		log["crease_angle"]=round(otsu,1)
		log["crease_source"]= "detector (bilateral + Otsu + hysteresis)"
	else:
		cut=man & (ang >=flat_angle)
		log["crease_angle"]=float(flat_angle)
		log["crease_source"]= "fixed angle"
	log["feature_edges"]=int(cut.sum())
	ds=DisjointSet(nf)
	flat=man & ~cut
	for x,y in zip(pair[flat,0].tolist(),pair[flat,1].tolist()):
		ds.union(x,y)
	root=np.fromiter((ds.find(i) for i in range(nf)),dtype=np.int64,count=nf)
	_,lab=np.unique(root,return_inverse=True)
	nreg=int(lab.max()) + 1 if nf else 0
	log["regions_raw"]=nreg
	elen=np.linalg.norm(V[edges[:,0]] - V[edges[:,1]],axis=1)
	merged=0
	for _ in range(4):
		area=np.bincount(lab,weights=fa,minlength=nreg)
		la_=np.where(pair[:,0] >=0,lab[np.clip(pair[:,0],0,None)],-1)
		lb_=np.where(pair[:,1] >=0,lab[np.clip(pair[:,1],0,None)],-1)
		cross=(la_ !=lb_) & (la_ >=0) & (lb_ >=0)
		perim=np.zeros(nreg)
		np.add.at(perim,la_[cross],elen[cross])
		np.add.at(perim,lb_[cross],elen[cross])
		total=max(area.sum(),1e-20)
		thin=np.zeros(nreg,dtype=bool)
		ok_p=perim > 1e-20
		thin[ok_p]=(area[ok_p] / (perim[ok_p] ** 2)) < 0.004
		tiny=area < 0.0004 * total
		bad=np.flatnonzero(thin | tiny)
		if not len(bad):
			break
		shared=defaultdict(float)
		for x,y,w in zip(la_[cross].tolist(),lb_[cross].tolist(),
						   elen[cross].tolist()):
			shared[(x,y)] +=w
			shared[(y,x)] +=w
		changed=False
		badset=set(bad.tolist())
		for r in bad.tolist():
			best,bw=-1,0.0
			for (x,y),w in shared.items():
				if x==r and y not in badset and w > bw:
					best,bw=y,w
			if best >=0:
				lab[lab==r]=best
				merged +=1
				changed=True
		if not changed:
			break
		_,lab=np.unique(lab,return_inverse=True)
		nreg=int(lab.max()) + 1
	log["regions"]=nreg
	log["slivers_merged"]=merged
	la=np.where(pair[:,0] >=0,lab[np.clip(pair[:,0],0,None)],-1)
	lb=np.where(pair[:,1] >=0,lab[np.clip(pair[:,1],0,None)],-1)
	isb=la !=lb
	BE=edges[isb]
	step("simplifying boundaries",0.25)
	inc=defaultdict(list)
	for i,(x,y) in enumerate(BE.tolist()):
		inc[x].append(i)
		inc[y].append(i)
	junction={v for v in inc if len(inc[v]) !=2}
	keep=set(junction)
	used=np.zeros(len(BE),dtype=bool)
	def walk(v0,e0,stop_at_junction):
		chain=[v0]
		e,cur=e0,v0
		while True:
			used[e]=True
			x,y=int(BE[e,0]),int(BE[e,1])
			cur=y if x==cur else x
			chain.append(cur)
			if stop_at_junction and cur in junction:
				break
			if not stop_at_junction and cur==chain[0]:
				break
			nxt=[i for i in inc[cur] if not used[i]]
			if not nxt:
				break
			e=nxt[0]
		return chain
	tol_open=simplify * diag
	for v0 in list(junction):
		for e0 in list(inc[v0]):
			if used[e0]:
				continue
			ch=walk(v0,e0,True)
			keep.update(_dp(V[np.asarray(ch)],ch,tol_open))
	for e0 in range(len(BE)):
		if used[e0]:
			continue
		ch=walk(int(BE[e0,0]),e0,False)[:-1]
		P=V[np.asarray(ch)]
		extent=float(np.linalg.norm(P.max(0) - P.min(0)))
		keep.update(_dp(P,ch,min(tol_open,0.06 * extent)))
	log["boundary_verts"]={"before": int(len(set(BE.ravel().tolist()))),"after": int(len(keep)), "junctions": int(len(junction))}
	def loops_of(r):
		mask=isb & ((la==r) | (lb==r))
		E=edges[mask]
		if not len(E):
			return []
		i2=defaultdict(list)
		for i,(x,y) in enumerate(E.tolist()):
			i2[x].append(i)
			i2[y].append(i)
		us=np.zeros(len(E),dtype=bool)
		res=[]
		for e0 in range(len(E)):
			if us[e0]:
				continue
			ch=[int(E[e0,0]),int(E[e0,1])]
			us[e0]=True
			for _ in range(len(E) + 2):
				v=ch[-1]
				k=next((i for i in i2[v] if not us[i]),None)
				if k is None:
					break
				us[k]=True
				x,y=int(E[k,0]),int(E[k,1])
				ch.append(y if x==v else x)
				if ch[-1]==ch[0]:
					break
			if ch[-1]==ch[0] and len(ch) > 3:
				s_=[v for v in ch[:-1] if v in keep]
				if len(s_) >=3:
					res.append(s_)
		return res
	step("building bands",0.5)
	W=chamfer * diag
	outV=[list(map(float,p)) for p in V]
	outF: list=[]
	rep={"plain": 0, "holed": 0, "flat_only": 0, "original": 0}
	kept_orig=np.zeros(nf,dtype=bool)
	def ring_has_area(ring):
		if len(ring) < 3:
			return False
		P=np.asarray([outV[i] for i in ring])
		c=P.mean(0)
		nrm=np.zeros(3)
		for k in range(len(P)):
			nrm +=np.cross(P[k] - c,P[(k + 1) % len(P)] - c)
		span=float(np.linalg.norm(P.max(0) - P.min(0)))
		return 0.5 * float(np.linalg.norm(nrm)) >=1e-4 * span * span
	def emit_panel(ring):
		if not ring_has_area(ring):
			return False
		P=np.asarray([outV[i] for i in ring])
		if len(ring)==3:
			L=[float(np.linalg.norm(P[(k + 1) % 3] - P[k])) for k in range(3)]
			k=int(np.argmax(L))
			mid=(P[k] + P[(k + 1) % 3]) * 0.5
			outV.append(list(map(float,mid)))
			ring=ring[:k + 1] + [len(outV) - 1] + ring[k + 1:]
		outF.append(list(ring))
		return True
	for r in range(nreg):
		Ls=loops_of(r)
		fr=np.flatnonzero(lab==r)
		if not Ls or not len(fr):
			continue
		w=fa[fr]
		nrm=(fn[fr] * w[:,None]).sum(0)
		nl=np.linalg.norm(nrm)
		if nl < 1e-12:
			kept_orig[fr]=True
			rep["original"] +=1
			continue
		nrm /=nl
		allv=np.concatenate([np.asarray(L_) for L_ in Ls])
		C=V[allv].mean(0)
		h=np.zeros(3)
		h[int(np.argmin(np.abs(nrm)))]=1
		U=np.cross(nrm,h)
		U /=np.linalg.norm(U)
		Vb=np.cross(nrm,U)
		def proj(idx):
			P=V[np.asarray(idx)] - C
			return np.stack([P @ U,P @ Vb],axis=1)
		def to2d(i):
			d=np.asarray(outV[i]) - C
			return (float(d @ U),float(d @ Vb))
		areas=[abs(_sarea(proj(L_))) for L_ in Ls]
		oi=int(np.argmax(areas))
		outer=Ls[oi]
		holes=[Ls[i] for i in range(len(Ls)) if i !=oi]
		try:
			qo=proj(outer)
			io=_offset_ring(qo,W,sgn=1.0)
			if _sarea(io) * _sarea(qo) <=0 or abs(_sarea(io)) < 0.12 * abs(_sarea(qo)):
				raise ValueError("插入折叠")
			Lo=len(outer)
			keep_i,map_i=_weld_ring(io,1e-4 * W)
			base=len(outV)
			slot={k: base + n_ for n_,k in enumerate(keep_i)}
			outV.extend([list(map(float,C + io[k][0] * U + io[k][1] * Vb)) for k in keep_i])
			gid=[slot[map_i[i]] for i in range(Lo)]
			faces_here=[]
			for i in range(Lo):
				a,b=gid[i],gid[(i + 1) % Lo]
				if outer[i]==outer[(i + 1) % Lo]:
					continue
				if a==b:
					faces_here.append([outer[i],outer[(i + 1) % Lo],a])
				else:
					faces_here.append([outer[i],outer[(i + 1) % Lo],b,a])
			ring=[slot[k] for k in keep_i]
			ringP=[tuple(io[k]) for k in keep_i]
			done=False
			for H in holes:
				qh=proj(H)
				ih=_offset_ring(qh,W,sgn=-1.0)
				bh=len(outV)
				outV.extend([list(map(float,C + p[0] * U + p[1] * Vb)) for p in ih])
				Lh=len(H)
				faces_here +=[[H[i],bh + i,bh + (i + 1) % Lh,H[(i + 1) % Lh]] for i in range(Lh)]
				cur=ih
				cur_idx=[bh + i for i in range(Lh)]
				hub=cur.mean(axis=0)
				panel_span=float(np.linalg.norm(io.max(0) - io.min(0)))
				for _ in range(4):
					span=float(np.linalg.norm(cur.max(0) - cur.min(0)))
					if span >=0.30 * panel_span:
						break
					nxt=hub + (cur - hub) * 1.9
					gap=float(np.min(np.linalg.norm(nxt[:,None,:] - io[None,:,:],axis=2)))
					if gap < 1.5 * W:
						break
					nb=len(outV)
					outV.extend([list(map(float,C + p[0] * U + p[1] * Vb)) for p in nxt])
					nxt_idx=[nb + i for i in range(Lh)]
					faces_here +=[[cur_idx[i],nxt_idx[i],nxt_idx[(i + 1) % Lh],cur_idx[(i + 1) % Lh]] for i in range(Lh)]
					cur,cur_idx=nxt,nxt_idx
				res=_split_annulus(ring,ringP,cur_idx,[tuple(p) for p in cur])
				if res is None:
					raise ValueError("环空拆分失败")
				if not (ring_has_area(res[0]) and ring_has_area(res[1])):
					raise ValueError("环裂产生退化的面")
				faces_here.append(res[1])
				ring=res[0]
				ringP=[to2d(i) for i in ring]
				done=True
			if done:
				faces_here.append(ring)
			if not done:
				faces_here.append(ring)
			outF.extend(faces_here)
			rep["holed" if holes else "plain"] +=1
		except Exception:
			ok=emit_panel(outer)
			if ok:
				rep["flat_only"] +=1
			else:
				kept_orig[fr]=True
				rep["original"] +=1
	for f in np.flatnonzero(kept_orig).tolist():
		s0=starts[f]
		outF.append([int(x) for x in face_verts[s0:s0 + face_sizes[f]]])
	outV=np.asarray(outV,dtype=np.float64)
	used=np.zeros(len(outV),dtype=bool)
	for f in outF:
		used[np.asarray(f,dtype=np.int64)]=True
	remap=np.full(len(outV),-1,dtype=np.int64)
	remap[used]=np.arange(int(used.sum()))
	log["loose_verts_dropped"]=int((~used).sum())
	outV=outV[used]
	outF=[[int(remap[i]) for i in f] for f in outF]
	log["panels"]=rep
	sizes=np.asarray([len(f) for f in outF])
	log["output"]={"verts": len(outV), "faces": len(outF),"quads": int((sizes==4).sum()), "tris": int((sizes==3).sum()),"ngons": int((sizes > 4).sum()),"max_sides": int(sizes.max()) if len(sizes) else 0, "quad_ratio": float((sizes==4).mean()) if len(sizes) else 0.0,"input_faces": int(nf), "reduction": round(nf / max(len(outF),1),1),}
	step("done",1.0)
	return {"V": outV, "faces": outF, "log": log}