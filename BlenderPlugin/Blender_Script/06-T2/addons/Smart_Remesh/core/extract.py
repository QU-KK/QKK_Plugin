from __future__ import annotations
"""Turning a converged position field into an actual quad mesh.
Vertices whose position fields landed on the same lattice site are collapsed
into one output vertex. What remains is a graph embedded in the surface,and
its faces *are* the quads - so they are recovered by walking the rotation
system (`next=rotate . twin`),the standard half-edge face traversal.
"""
import math,numpy as np
class DisjointSet:
	__slots__=("parent", "rank")
	def __init__(self,n: int) -> None:
		self.parent=list(range(n))
		self.rank=[0] * n
	def find(self,x: int) -> int:
		p=self.parent
		root=x
		while p[root] !=root:
			root=p[root]
		while p[x] !=root:
			p[x],x=root,p[x]
		return root
	def union(self,a: int,b: int) -> None:
		ra,rb=self.find(a),self.find(b)
		if ra==rb:
			return
		if self.rank[ra] < self.rank[rb]:
			ra,rb=rb,ra
		self.parent[rb]=ra
		if self.rank[ra]==self.rank[rb]:
			self.rank[ra] +=1
def collapse(mesh,p: np.ndarray,scale: float,radius: float=0.5):
	e=mesh.edges
	d=np.linalg.norm(p[e[:,1]] - p[e[:,0]],axis=1)
	order=np.argsort(d)
	ds=DisjointSet(mesh.nv)
	px=p[:,0].tolist()
	py=p[:,1].tolist()
	pz=p[:,2].tolist()
	W=[1.0] * mesh.nv
	sv=(np.full(mesh.nv,float(scale)) if np.isscalar(scale)
		  else np.asarray(scale,float))
	S=sv.tolist()
	find=ds.find
	union=ds.union
	for a,b in zip(e[order,0].tolist(),e[order,1].tolist()):
		ca,cb=find(a),find(b)
		if ca==cb:
			continue
		dx=px[ca] - px[cb]
		dy=py[ca] - py[cb]
		dz=pz[ca] - pz[cb]
		limit=radius * 0.5 * (S[ca] + S[cb])
		if dx * dx + dy * dy + dz * dz > limit * limit:
			continue
		union(ca,cb)
		root=find(ca)
		wa,wb=W[ca],W[cb]
		inv=1.0 / (wa + wb)
		px[root]=(px[ca] * wa + px[cb] * wb) * inv
		py[root]=(py[ca] * wa + py[cb] * wb) * inv
		pz[root]=(pz[ca] * wa + pz[cb] * wb) * inv
		S[root]=(S[ca] * wa + S[cb] * wb) * inv
		W[root]=wa + wb
	roots=np.fromiter((ds.find(k) for k in range(mesh.nv)),dtype=np.int64,count=mesh.nv)
	_,labels=np.unique(roots,return_inverse=True)
	nc=int(labels.max()) + 1 if mesh.nv else 0
	return labels,nc,sv
def cluster_geometry(mesh,p: np.ndarray,labels: np.ndarray,nc: int,o: np.ndarray,sizing: np.ndarray | None=None):
	cnt=np.maximum(np.bincount(labels,minlength=nc),1)
	V=np.empty((nc,3))
	N=np.empty((nc,3))
	for k in range(3):
		V[:,k]=np.bincount(labels,weights=p[:,k],minlength=nc) / cnt
		N[:,k]=np.bincount(labels,weights=mesh.normal[:,k],minlength=nc) / cnt
	N /=np.maximum(np.linalg.norm(N,axis=1,keepdims=True),1e-20)
	rep=np.zeros(nc,dtype=np.int64)
	rep[labels]=np.arange(len(labels))
	O=o[rep]
	O -=np.sum(O * N,axis=1,keepdims=True) * N
	O /=np.maximum(np.linalg.norm(O,axis=1,keepdims=True),1e-20)
	if sizing is None:
		return V,N,O,None
	S=np.bincount(labels,weights=sizing,minlength=nc) / cnt
	return V,N,O,S
def build_graph(mesh,labels: np.ndarray,nc: int,V: np.ndarray,N: np.ndarray,O: np.ndarray,scale) -> np.ndarray:
	e=mesh.edges
	a=labels[e[:,0]]
	b=labels[e[:,1]]
	keep=a !=b
	a,b=a[keep],b[keep]
	lo=np.minimum(a,b)
	hi=np.maximum(a,b)
	key=np.unique(lo * np.int64(nc) + hi)
	a,b=key // nc,key % nc
	T=np.cross(N,O)
	delta=V[b] - V[a]
	s=(np.full(len(a),float(scale)) if np.isscalar(scale)
		 else 0.5 * (np.asarray(scale,float)[a] + np.asarray(scale,float)[b]))
	ka=np.abs(np.round(np.sum(delta * O[a],axis=1) / s))
	kb=np.abs(np.round(np.sum(delta * T[a],axis=1) / s))
	step=(np.maximum(ka,kb) <=1) & ((ka + kb)==1)
	return np.stack([a[step],b[step]],axis=1)
def orient_adjacency(V: np.ndarray,N: np.ndarray,E: np.ndarray) -> list:
	nv=len(V)
	adj=[[] for _ in range(nv)]
	for a,b in zip(E[:,0].tolist(),E[:,1].tolist()):
		adj[a].append(b)
		adj[b].append(a)
	helper=np.zeros_like(N)
	helper[np.arange(nv),np.argmin(np.abs(N),axis=1)]=1.0
	S=np.cross(N,helper)
	S /=np.maximum(np.linalg.norm(S,axis=1,keepdims=True),1e-20)
	T=np.cross(N,S)
	Vl=V.tolist()
	Sl,Tl=S.tolist(),T.tolist()
	for i in range(nv):
		if len(adj[i]) < 2:
			continue
		px,py,pz=Vl[i]
		sx,sy,sz=Sl[i]
		tx,ty,tz=Tl[i]
		def angle(j,px=px,py=py,pz=pz):
			qx,qy,qz=Vl[j]
			dx,dy,dz=qx - px,qy - py,qz - pz
			return -math.atan2(dx * tx + dy * ty + dz * tz,dx * sx + dy * sy + dz * sz)
		adj[i].sort(key=angle)
	return adj
WALK_LIMIT=64
def _walk(adj: list,used: list,cur: int,cur_idx: int,target: int):
	initial=cur
	result=[]
	success=False
	while True:
		if used[cur][cur_idx] or (target > 0 and len(result) + 1 > target):
			break
		if len(result) > WALK_LIMIT:
			break
		result.append((cur,cur_idx))
		nxt=adj[cur][cur_idx]
		rank=len(adj[nxt])
		if rank==1:
			break
		try:
			idx=adj[nxt].index(cur)
		except ValueError:
			break
		cur=nxt
		cur_idx=(idx + 1) % rank
		if cur==initial:
			success=target==0 or len(result)==target
			break
	if not success:
		return None
	for a,b in result:
		used[a][b]=True
	return [a for a,_ in result]
def _emit_face(V: np.ndarray,ring: list,faces: list) -> None:
	ring=list(ring)
	while len(ring) > 2:
		n=len(ring)
		if n <=4:
			faces.append(ring)
			return
		best_score=None
		best_i=0
		for i in range(n):
			score=0.0
			for k in range(4):
				v0=V[ring[(i + k) % n]]
				v1=V[ring[(i + k + 1) % n]]
				v2=V[ring[(i + k + 2) % n]]
				d0=v0 - v1
				d1=v2 - v1
				l0=math.sqrt(d0[0] ** 2 + d0[1] ** 2 + d0[2] ** 2)
				l1=math.sqrt(d1[0] ** 2 + d1[1] ** 2 + d1[2] ** 2)
				if l0 < 1e-12 or l1 < 1e-12:
					score +=90.0
					continue
				c=(d0[0] * d1[0] + d0[1] * d1[1] + d0[2] * d1[2]) / (l0 * l1)
				score +=abs(math.degrees(math.acos(max(-1.0,min(1.0,c)))) - 90.0)
			if best_score is None or score < best_score:
				best_score=score
				best_i=i
		faces.append([ring[(best_i + k) % n] for k in range(4)])
		drop={(best_i + 1) % n,(best_i + 2) % n}
		ring=[v for k,v in enumerate(ring) if k not in drop]
def extract_faces(V: np.ndarray,N: np.ndarray,adj: list,max_sides: int=8):
	nv=len(adj)
	used=[[False] * len(a) for a in adj]
	faces: list=[]
	for target in (4,3,5,6,7,8):
		if target > max_sides:
			continue
		for i in range(nv):
			ai=adj[i]
			for j in range(len(ai)):
				ring=_walk(adj,used,i,j,target)
				if ring:
					_emit_face(V,ring,faces)
	keep=[[False] * len(a) for a in adj]
	for i in range(nv):
		for j,b in enumerate(adj[i]):
			if used[i][j]:
				continue
			try:
				k=adj[b].index(i)
			except ValueError:
				continue
			if used[b][k]:
				keep[i][j]=True
				keep[b][k]=True
	adj2=[[b for j,b in enumerate(adj[i]) if keep[i][j]] for i in range(nv)]
	used2=[[False] * len(a) for a in adj2]
	holes=0
	unfilled=0
	for i in range(nv):
		for j in range(len(adj2[i])):
			ring=_walk(adj2,used2,i,j,0)
			if not ring:
				continue
			if len(ring) < 3 or len(ring) > 12:
				unfilled +=1
				continue
			_emit_face(V,ring,faces)
			holes +=1
	return faces,holes,unfilled
def orient_faces(V: np.ndarray,N: np.ndarray,faces: list) -> list:
	out=[]
	for f in faces:
		P=V[f]
		c=P.mean(axis=0)
		nrm=np.zeros(3)
		for k in range(len(f)):
			nrm +=np.cross(P[k] - c,P[(k + 1) % len(f)] - c)
		if np.dot(nrm,N[f].mean(axis=0)) < 0:
			f=f[::-1]
		out.append(f)
	return out
def cleanup(V: np.ndarray,faces: list):
	seen=set()
	kept=[]
	for f in faces:
		if len(set(f)) !=len(f):
			continue
		key=tuple(sorted(f))
		if key in seen:
			continue
		seen.add(key)
		kept.append(f)
	used=np.zeros(len(V),dtype=bool)
	for f in kept:
		used[f]=True
	remap=np.full(len(V),-1,dtype=np.int64)
	remap[used]=np.arange(int(used.sum()))
	kept=[[int(remap[i]) for i in f] for f in kept]
	return V[used],kept
def smooth(V: np.ndarray,faces: list,iterations: int=2,strength: float=0.5) -> np.ndarray:
	if not faces or iterations <=0:
		return V
	pairs=[]
	for f in faces:
		for k in range(len(f)):
			pairs.append((f[k],f[(k + 1) % len(f)]))
	P=np.asarray(pairs,dtype=np.int64)
	a=np.concatenate([P[:,0],P[:,1]])
	b=np.concatenate([P[:,1],P[:,0]])
	V=V.copy()
	nv=len(V)
	cnt=np.maximum(np.bincount(a,minlength=nv),1)
	for _ in range(iterations):
		acc=np.empty((nv,3))
		for k in range(3):
			acc[:,k]=np.bincount(a,weights=V[b][:,k],minlength=nv)
		V +=strength * (acc / cnt[:,None] - V)
	return V