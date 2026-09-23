from __future__ import annotations
"""End-to-end pipeline: polygon mesh in,quad-dominant mesh out.
No Blender operator is involved at any stage - this is our own field-guided
remesher. The only dependency is numpy,which Blender already ships.
"""
import time,numpy as np
from .extract import (build_graph,cleanup,cluster_geometry,collapse,extract_faces,orient_adjacency,orient_faces,smooth)
from .field import comb_field,orientation_field,position_field
from .mesh import TriMesh
from .sizing import estimate_faces,fit_to_target,sizing_field
def target_scale(mesh: TriMesh,target_faces: int | None=None,target_edge: float | None=None,adaptive: float=0.0) -> float:
	if target_edge:
		return float(target_edge)
	if target_faces:
		return float(np.sqrt(mesh.total_area / max(target_faces,1)))
	return mesh.mean_edge * 2.0
def remesh(V,face_verts,face_sizes,*,target_faces: int | None=None,target_edge: float | None=None,feature_angle: float=30.0,orient_iterations: int=40,position_iterations: int=40,smooth_iterations: int=0,use_curvature: bool=True,adaptive: bool=False,feature_density: float=1.0,curvature_density: float=1.0,inner_density: float=0.0,outer_density: float=0.0,thin_strength: float=1.0,min_size_ratio: float=0.5,feature_band: float=3.0,gradient_limit: float=0.1,max_sides: int=8,progress=None) -> dict:
	t0=time.perf_counter()
	log: dict={}
	def step(name,frac):
		if progress is not None:
			progress(name,frac)
	mesh=TriMesh.from_polys(np.asarray(V,dtype=np.float64),face_verts,face_sizes)
	if mesh.nf==0:
		raise ValueError("网格没有面")
	log["input"]={"verts": mesh.nv, "tris": mesh.nf}
	scale=target_scale(mesh,target_faces,target_edge)
	if not np.isfinite(scale) or scale <=0:
		raise ValueError(f"无效目标缩放 {scale}")
	log["scale"]=scale
	sizing=scale
	if adaptive:
		step("sizing field",0.03)
		sizing=sizing_field(mesh,scale,feature_angle=feature_angle,feature_strength=feature_density,curvature_strength=curvature_density,inner_density=inner_density,outer_density=outer_density,thin_strength=thin_strength,min_ratio=min_size_ratio,band=feature_band,gradient_limit=gradient_limit)
		if target_faces:
			sizing=fit_to_target(mesh,sizing,target_faces)
		log["adaptive"]={"size_min": float(sizing.min()),"size_max": float(sizing.max()), "ratio": float(sizing.max() / max(sizing.min(),1e-20)), "predicted_faces": round(estimate_faces(mesh,sizing)),}
	step("orientation field",0.05)
	o,locked,corner,feat_tangent=orientation_field(mesh,iterations=orient_iterations,feature_angle=feature_angle,use_curvature=use_curvature)
	log["feature_verts"]=int(locked.sum())
	log["corner_verts"]=int(corner.sum())
	step("combing field",0.3)
	o=comb_field(mesh,o)
	step("position field",0.35)
	p=position_field(mesh,o,sizing,iterations=position_iterations,locked=locked,corner=corner,feat_tangent=feat_tangent)
	step("collapsing lattice",0.65)
	labels,nc,sv=collapse(mesh,p,sizing)
	log["clusters"]=nc
	if nc < 4:
		raise ValueError(f"lattice collapsed to {nc} sites - target size is far too large "
			f"for this mesh (scale={scale:.4g})")
	Vo,No,Oo,So=cluster_geometry(mesh,p,labels,nc,o,sv)
	E=build_graph(mesh,labels,nc,Vo,No,Oo,So)
	log["graph_edges"]=int(len(E))
	if len(E) < 4:
		raise ValueError("没有晶格邻接幸存-位置域" "不收敛；尝试更多位置迭代")
	step("extracting faces",0.8)
	adj=orient_adjacency(Vo,No,E)
	faces,holes,unfilled=extract_faces(Vo,No,adj,max_sides=max_sides)
	log["holes_filled"]=holes
	log["holes_unfilled"]=unfilled
	if not faces:
		raise ValueError("面提取无效-尝试较小的" "目标尺寸或更多位置迭代")
	faces=orient_faces(Vo,No,faces)
	Vo,faces=cleanup(Vo,faces)
	step("relaxing",0.92)
	if smooth_iterations:
		Vo=smooth(Vo,faces,iterations=smooth_iterations)
	sizes=np.array([len(f) for f in faces])
	log["output"]={"verts": int(len(Vo)),"faces": int(len(faces)),"quads": int((sizes==4).sum()),"tris": int((sizes==3).sum()), "ngons": int((sizes > 4).sum()), "quad_ratio": float((sizes==4).mean()) if len(sizes) else 0.0,}
	log["seconds"]=time.perf_counter() - t0
	step("done",1.0)
	return {"V": Vo, "faces": faces, "log": log}