from __future__ import annotations
"""Automatic remeshing: our analysis and search driving the Instant Meshes engine.
Instant Meshes is excellent at the part it does,and it is not going to be
out-implemented in a hurry. What it does not do is decide anything for you: the
crease angle is a number you guess,and the face target is taken as a hint it
routinely overshoots by 3x. Both of those cost more quality in practice than
the algorithmic differences do.
So this drives it:
  1. read the model and derive a crease angle from its own dihedral histogram
  2. calibrate the face target against what the engine actually returns
  3. run a small candidate set and keep whichever scores best on our metric
That last step is the part no standalone tool can do for you,because it needs
a definition of "good topology" to optimise against - which is what TopoLens
was built to provide.
"""
import time,numpy as np
from . import instantmeshes,score
from .detect import describe
from .mesh import TriMesh
def _run(V,fv,fs,*,faces,crease,dominant,smooth,exe):
	out=instantmeshes.remesh(V,fv,fs,target_faces=int(faces),feature_angle=float(crease),smooth_iterations=int(smooth),dominant=bool(dominant),exe=exe)
	out["score"]=score.evaluate(out["V"],out["faces"])
	return out
def auto_remesh(V,face_verts,face_sizes,*,target_faces: int=4000,crease_override: float | None=None,calibrate: bool=True,search: bool=True,smooth_iterations: int=2,exe: str= "",progress=None) -> dict:
	t0=time.perf_counter()
	V=np.asarray(V,dtype=np.float64)
	face_verts=np.asarray(face_verts,dtype=np.int64)
	face_sizes=np.asarray(face_sizes,dtype=np.int64)
	def step(name,frac):
		if progress:
			progress(name,frac)
	step("analysing model",0.05)
	mesh=TriMesh.from_polys(V,face_verts,face_sizes)
	info=describe(mesh)
	crease=float(crease_override if crease_override is not None else info["crease"]["angle"])
	log={"analysis": info, "crease_used": crease, "attempts": []}
	request=float(target_faces)
	if calibrate:
		step("calibrating face count",0.2)
		probe=_run(V,face_verts,face_sizes,faces=request,crease=crease,dominant=False,smooth=smooth_iterations,exe=exe)
		got=probe["score"]["faces"]
		log["attempts"].append({"stage": "probe", "request": int(request),"faces": got,"score": round(probe["score"]["overall"],1)})
		if got > 0:
			ratio=got / request
			if ratio > 1.15 or ratio < 0.87:
				request=max(8.0,request / ratio)
				log["calibration_ratio"]=round(ratio,3)
			else:
				log["calibration_ratio"]=round(ratio,3)
	step("searching parameters",0.45)
	candidates=[{"crease": crease, "dominant": False}]
	if search:
		for delta in (-10.0,10.0):
			c=float(np.clip(crease + delta,15.0,80.0))
			if abs(c - crease) > 1.0:
				candidates.append({"crease": c, "dominant": False})
		candidates.append({"crease": crease, "dominant": True})
	best=None
	for i,cand in enumerate(candidates):
		step(f"candidate {i + 1}/{len(candidates)}",0.45 + 0.5 * i / max(len(candidates),1))
		try:
			out=_run(V,face_verts,face_sizes,faces=request,crease=cand["crease"],dominant=cand["dominant"],smooth=smooth_iterations,exe=exe)
		except Exception as exc:
			log["attempts"].append({"crease": cand["crease"],"dominant": cand["dominant"],"error": str(exc)})
			continue
		s=out["score"]
		log["attempts"].append({"crease": round(cand["crease"],1),"dominant": cand["dominant"],"faces": s["faces"],"quads": round(s["quad_area_ratio"],3),"boundary": s["boundary_edges"],"nonmanifold": s["nonmanifold_edges"],"score": round(s["overall"],1),})
		if best is None or s["overall"] > best["score"]["overall"]:
			best=out
			best["chosen"]=dict(cand)
	if best is None:
		raise RuntimeError("每个候选人都失败-请参阅尝试日志")
	log["chosen"]=best["chosen"]
	log["final_score"]=round(best["score"]["overall"],1)
	log["output"]=best["log"]["output"]
	log["seconds"]=time.perf_counter() - t0
	step("done",1.0)
	return {"V": best["V"], "faces": best["faces"], "log": log, "score": best["score"]}