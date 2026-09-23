from __future__ import annotations
"""Instant Meshes as a remeshing backend,driven in batch mode.
This is the "stable" backend: a known-good reference implementation of the same
family of algorithm ours is working towards. Keeping it alongside ours means
there is always a usable result,and - more usefully - an objective yardstick
to measure ours against with TopoLens.
Instant Meshes is by Wenzel Jakob,Daniele Panozzo,Marco Tarini and Olga
Sorkine-Hornung (SIGGRAPH Asia 2015),BSD-licensed. We ship the official
prebuilt binary unmodified; see vendor/LICENSE-instant-meshes.txt.
"""
import os,shutil,subprocess,sys,tempfile,time,numpy as np
EXE_NAME= "Instant Meshes.exe" if os.name== "nt" else "Instant Meshes"
def find_exe(explicit: str= "") -> str | None:
	candidates=[]
	if explicit:
		candidates.append(explicit)
	here=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
	candidates.append(os.path.join(here, "bin",EXE_NAME))
	repo=os.path.dirname(os.path.dirname(here))
	candidates.append(os.path.join(repo, "vendor", "instant-meshes",EXE_NAME))
	found=shutil.which(EXE_NAME)
	if found:
		candidates.append(found)
	for c in candidates:
		if c and os.path.isfile(c):
			return c
	return None
QUARANTINE= "com.apple.quarantine"
def ensure_executable(path: str) -> None:
	if os.name== "nt":
		return
	try:
		mode=os.stat(path).st_mode
		if not mode & 0o111:
			os.chmod(path,mode | 0o755)
	except OSError:
		pass
def is_quarantined(path: str) -> bool:
	if sys.platform != "darwin":
		return False
	try:
		return QUARANTINE in os.listxattr(path)
	except (OSError,AttributeError):
		return False
def clear_quarantine(path: str) -> tuple[bool,str]:
	if sys.platform != "darwin":
		return True, ""
	folder=os.path.dirname(os.path.abspath(path))
	try:
		proc=subprocess.run(["xattr", "-dr",QUARANTINE,folder],capture_output=True,text=True,timeout=60)
	except Exception as exc:
		return False,str(exc)
	if is_quarantined(path):
		return False,(proc.stderr or proc.stdout or "").strip() or             "the flag is still set"
	return True, ""
def write_obj(path: str,V: np.ndarray,face_verts: np.ndarray,face_sizes: np.ndarray) -> None:
	starts=np.concatenate([[0],np.cumsum(face_sizes)[:-1]])
	with open(path, "w") as fh:
		fh.write("# written by quadremesh\n")
		for x,y,z in V:
			fh.write(f"v {x:.8g} {y:.8g} {z:.8g}\n")
		for s,n in zip(starts.tolist(),face_sizes.tolist()):
			idx=face_verts[s:s + n] + 1
			fh.write("f " + " ".join(str(int(i)) for i in idx) + "\n")
def _f(tok: str) -> float:
	try:
		v=float(tok)
	except ValueError:
		return float("nan")
	return v
def read_obj(path: str):
	verts: list=[]
	faces: list=[]
	with open(path, "r",errors="replace") as fh:
		for line in fh:
			if not line:
				continue
			c=line[0]
			if c== "v" and line[1]== " ":
				p=line.split()
				verts.append((_f(p[1]),_f(p[2]),_f(p[3])))
			elif c== "f":
				p=line.split()
				idx=[]
				for tok in p[1:]:
					slash=tok.find("/")
					s=tok if slash < 0 else tok[:slash]
					if s:
						i=int(s)
						idx.append(i - 1 if i > 0 else len(verts) + i)
				if len(idx) >=3:
					faces.append(idx)
	V=np.asarray(verts,dtype=np.float64)
	if not len(V):
		return V,faces,0
	good=np.isfinite(V).all(axis=1)
	n_bad=int((~good).sum())
	if n_bad:
		faces=[f for f in faces
				 if all(0 <=i < len(V) and good[i] for i in f)]
		remap=np.full(len(V),-1,dtype=np.int64)
		remap[good]=np.arange(int(good.sum()))
		faces=[[int(remap[i]) for i in f] for f in faces]
		V=V[good]
	return V,faces,n_bad
def remesh(V,face_verts,face_sizes,*,target_faces: int | None=None,target_edge: float | None=None,feature_angle: float=30.0,smooth_iterations: int=2,dominant: bool=False,deterministic: bool=True,align_boundaries: bool=True,threads: int=0,exe: str= "",timeout: int=1800,progress=None) -> dict:
	t0=time.perf_counter()
	binary=find_exe(exe)
	if binary is None:
		raise RuntimeError(f"Instant Meshes binary not found - expected <addon>/bin/{EXE_NAME}, "
			"或在首选项>加载项>智能重构中设置的路径. "
			"Smart Remesh (Hardsurface) needs no binary and works everywhere.")
	ensure_executable(binary)
	if is_quarantined(binary):
		raise RuntimeError("macOS has quarantined the Organic engine,so it cannot start. \n Press “Allow Organic Engine” in the Smart Remesh panel,\n or run this in Terminal:\n\n"
			f'    xattr -dr com.apple.quarantine "{os.path.dirname(binary)}"')
	if progress:
		progress("writing input",0.05)
	work=tempfile.mkdtemp(prefix="quadremesh_im_")
	src=os.path.join(work, "in.obj")
	dst=os.path.join(work, "out.obj")
	try:
		write_obj(src,np.asarray(V,dtype=np.float64),np.asarray(face_verts,dtype=np.int64),np.asarray(face_sizes,dtype=np.int64))
		cmd=[binary,src, "-o",dst, "-c",str(float(feature_angle)),"-S",str(int(smooth_iterations))]
		if target_edge:
			cmd +=["-s",str(float(target_edge))]
		elif target_faces:
			cmd +=["-f",str(int(target_faces))]
		if dominant:
			cmd.append("-D")
		if deterministic:
			cmd.append("-d")
		if align_boundaries:
			cmd.append("-b")
		if threads > 0:
			cmd +=["-t",str(int(threads))]
		if progress:
			progress("running Instant Meshes",0.2)
		try:
			proc=subprocess.run(cmd,capture_output=True,text=True,timeout=timeout)
		except OSError as exc:
			if getattr(exc, "errno",None)==86 or "cpu type" in str(exc).lower():
				raise RuntimeError("The Organic engine needs Rosetta,which is not installed \n on this Mac. Install it once by running this in \n Terminal:\n\n\n     softwareupdate --install-rosetta\n\n\n Smart Remesh (Hardsurface) does not need it and works "
					"无论哪种方式.") from exc
			raise
		if not os.path.isfile(dst):
			tail= "\n".join((proc.stdout + proc.stderr).splitlines()[-15:])
			raise RuntimeError(f"即时网格未生成输出:\n{tail}")
		if progress:
			progress("reading result",0.9)
		Vo,faces,n_bad=read_obj(dst)
	finally:
		shutil.rmtree(work,ignore_errors=True)
	if not faces:
		raise RuntimeError("Instant Meshes returned nothing usable"
			+ (f" ({n_bad} non-finite vertices)" if n_bad else ""))
	sizes=np.array([len(f) for f in faces]) if faces else np.zeros(0,int)
	log={"backend": "instant-meshes","binary": binary,"command": " ".join(cmd[1:]),"input": {"verts": int(len(V)), "faces": int(len(face_sizes))},"output": {"verts": int(len(Vo)),"faces": int(len(faces)),"quads": int((sizes==4).sum()),"tris": int((sizes==3).sum()), "ngons": int((sizes > 4).sum()),"quad_ratio": float((sizes==4).mean()) if len(sizes) else 0.0,}, "seconds": time.perf_counter() - t0, "dropped_nonfinite_verts": n_bad,}
	if progress:
		progress("done",1.0)
	return {"V": Vo, "faces": faces, "log": log}