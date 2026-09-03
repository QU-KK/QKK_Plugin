from ..G import *
"""Surface-constrained Voronoi construction for local overlap clamping.
The implementation builds connected coplanar surface charts from
the 3D mesh and propagates selected segment ownership across their internal
face boundaries.  All clipping and distance tests operate on world-space 3D
vectors.  No source object is globally projected or flattened.
Finite source segments are cropped by one-sided distance bands and shared
endpoint/miter dividers.  Only finite neighbouring segments whose cropped
bands can meet participate in ownership.  This produces the reference-style
rectangles/quads and corner triangles without dense point sampling.
Concave and non-planar source n-gons are accepted.  They are tessellated only
in a temporary local parameter space and generated points are mapped back to
the original 3D carrier triangles.
"""
SURFACE_VORONOI_TOLERANCE=1.0e-7
def surface_voronoi_polygon_normal(points,fallback=None):
	points=list(points or ())
	if len(points) < 3:
		return safe_normalized(fallback or Vector((0.0,0.0,1.0)),Vector((0.0,0.0,1.0)),)
	normal=Vector((0.0,0.0,0.0))
	for index,current in enumerate(points):
		following=points[(index + 1) % len(points)]
		normal.x +=(current.y - following.y) * (current.z + following.z)
		normal.y +=(current.z - following.z) * (current.x + following.x)
		normal.z +=(current.x - following.x) * (current.y + following.y)
	return safe_normalized(normal,fallback or Vector((0.0,0.0,1.0)),)
def surface_voronoi_polygon_centroid(points):
	points=list(points or ())
	if not points:
		return Vector((0.0,0.0,0.0))
	centroid=Vector((0.0,0.0,0.0))
	for point in points:
		centroid +=point
	return centroid / len(points)
def surface_voronoi_polygon_area(points,normal=None):
	points=list(points or ())
	if len(points) < 3:
		return 0.0
	normal=safe_normalized(normal or surface_voronoi_polygon_normal(points),Vector((0.0,0.0,1.0)),)
	area_vector=Vector((0.0,0.0,0.0))
	for index,point in enumerate(points):
		area_vector +=point.cross(points[(index + 1) % len(points)])
	return abs(area_vector.dot(normal)) * 0.5
def surface_voronoi_float32_polygon_area(points):
	from struct import pack,unpack
	quantized=[Vector(tuple(unpack("f",pack("f",component))[0] for component in point)) for point in points or ()]
	if len(quantized) < 3:
		return 0.0
	origin=quantized[0]
	area_vector=Vector((0.0,0.0,0.0))
	for index in range(1,len(quantized) - 1):
		area_vector +=(quantized[index] - origin).cross(quantized[index + 1] - origin)
	return area_vector.length * 0.5
def surface_voronoi_clean_polygon(points,tolerance=SURFACE_VORONOI_TOLERANCE):
	cleaned=[]
	for point in points or ():
		point=point.copy()
		if cleaned and (point - cleaned[-1]).length <=tolerance:
			continue
		cleaned.append(point)
	if len(cleaned) > 1 and (cleaned[0] - cleaned[-1]).length <=tolerance:
		cleaned.pop()
	changed=True
	while changed and len(cleaned) >=3:
		changed=False
		reduced=[]
		count=len(cleaned)
		for index,point in enumerate(cleaned):
			previous=cleaned[(index - 1) % count]
			following=cleaned[(index + 1) % count]
			previous_vector=point - previous
			following_vector=following - point
			scale=max(previous_vector.length,following_vector.length,1.0)
			if (previous_vector.length <=tolerance
				or following_vector.length <=tolerance
				or previous_vector.cross(following_vector).length
				<=tolerance * scale):
				changed=True
				continue
			reduced.append(point)
		if len(reduced) < 3:
			break
		cleaned=reduced
	return cleaned
def surface_voronoi_clip_halfspace(polygon,plane_normal,plane_offset,tolerance=SURFACE_VORONOI_TOLERANCE,):
	polygon=list(polygon or ())
	if len(polygon) < 3:
		return []
	result=[]
	previous=polygon[-1]
	previous_value=plane_normal.dot(previous) - plane_offset
	previous_inside=previous_value <=tolerance
	for current in polygon:
		current_value=plane_normal.dot(current) - plane_offset
		current_inside=current_value <=tolerance
		if current_inside !=previous_inside:
			denominator=previous_value - current_value
			if abs(denominator) > EPSILON:
				factor=max(0.0,min(1.0,previous_value / denominator))
				result.append(previous.lerp(current,factor))
		if current_inside:
			result.append(current.copy())
		previous=current
		previous_value=current_value
		previous_inside=current_inside
	return surface_voronoi_clean_polygon(result,tolerance)
def surface_voronoi_face_is_planar(points,normal,tolerance=SURFACE_VORONOI_TOLERANCE,):
	points=list(points or ())
	if len(points) < 3:
		return False
	origin=points[0]
	scale=max(max((point - origin).length for point in points),1.0,)
	return all(abs(normal.dot(point - origin)) <=tolerance * scale for point in points[1:])
def surface_voronoi_face_is_convex(points,normal,tolerance=SURFACE_VORONOI_TOLERANCE,):
	points=list(points or ())
	if len(points) < 3:
		return False
	turn_sign=0
	scale=max(max((points[index] - points[(index - 1) % len(points)]).length
			for index in range(len(points))),1.0,)
	for index,point in enumerate(points):
		previous=points[(index - 1) % len(points)]
		following=points[(index + 1) % len(points)]
		signed_turn=(point - previous).cross(following - point).dot(normal)
		if abs(signed_turn) <=tolerance * scale * scale:
			continue
		candidate_sign=1 if signed_turn > 0.0 else -1
		if turn_sign and candidate_sign !=turn_sign:
			return False
		turn_sign=candidate_sign
	return turn_sign !=0
def surface_voronoi_site_data(face_points,face_normal,site):
	start=site["start"].copy()
	end=site["end"].copy()
	tangent=end - start
	length=tangent.length
	if length <=EPSILON:
		raise ValueError("表面Voronoi场地必须具有非零长度.")
	tangent /=length
	centroid=surface_voronoi_polygon_centroid(face_points)
	midpoint=(start + end) * 0.5
	supplied_inward=site.get("inward")
	if supplied_inward is None:
		inward=safe_normalized(face_normal.cross(tangent),centroid - midpoint,)
		if inward.dot(centroid - midpoint) < 0.0:
			inward.negate()
	else:
		inward=safe_normalized(supplied_inward,face_normal.cross(tangent),)
	return {**site,"start": start,"end": end,"tangent": tangent, "length": length,"inward": inward, "line_offset": inward.dot(start),}
def surface_voronoi_endpoint_join(site,endpoint,sites,face_normal,face_width,tolerance=SURFACE_VORONOI_TOLERANCE,):
	if (site["start"] - endpoint).length <=tolerance * 8.0:
		endpoint_vertex=site.get("start_vertex")
		site_away=site["tangent"]
	else:
		endpoint_vertex=site.get("end_vertex")
		site_away=-site["tangent"]
	candidates=[]
	for other in sites:
		if other is site:
			continue
		if (endpoint_vertex is not None
			and other.get("start_vertex") is endpoint_vertex):
			other_away=other["tangent"]
		elif (endpoint_vertex is not None
			and other.get("end_vertex") is endpoint_vertex):
			other_away=-other["tangent"]
		elif endpoint_vertex is None and (other["start"] - endpoint).length <=tolerance * 8.0:
			other_away=other["tangent"]
		elif endpoint_vertex is None and (other["end"] - endpoint).length <=tolerance * 8.0:
			other_away=-other["tangent"]
		else:
			continue
		denominator=site["tangent"].cross(other["tangent"]).dot(face_normal)
		if abs(denominator) <=tolerance:
			continue
		site_origin=endpoint + site["inward"] * face_width
		other_origin=endpoint + other["inward"] * face_width
		factor=((other_origin - site_origin).cross(other["tangent"]).dot( face_normal) / denominator)
		join=site_origin + site["tangent"] * factor
		distance=(join - endpoint).length
		if distance <=tolerance:
			continue
		turn=abs(site_away.cross(other_away).dot(face_normal))
		same_curve=(site.get("curve_id") is not None
			and site.get("curve_id")==other.get("curve_id"))
		candidates.append((0 if same_curve else 1,-turn,distance,str(other.get("id")),join,))
	if not candidates:
		return endpoint + site["inward"] * face_width
	join=min(candidates,key=lambda item: item[:4])[4]
	delta=join - endpoint
	miter_limit=face_width * 3.0
	if delta.length > miter_limit:
		join=endpoint + delta.normalized() * miter_limit
	return join
def surface_voronoi_clip_endpoint_divider(polygon,endpoint,join,site_midpoint,face_normal,tolerance=SURFACE_VORONOI_TOLERANCE,):
	divider=join - endpoint
	if divider.length_squared <=tolerance * tolerance:
		return polygon
	plane_normal=safe_normalized(face_normal.cross(divider))
	plane_offset=plane_normal.dot(endpoint)
	if plane_normal.dot(site_midpoint) - plane_offset > 0.0:
		plane_normal.negate()
		plane_offset=-plane_offset
	return surface_voronoi_clip_halfspace(polygon,plane_normal,plane_offset,tolerance,)
def surface_voronoi_point_segment_distance_squared(point,start,end):
	delta=end - start
	length_squared=delta.length_squared
	if length_squared <=EPSILON:
		return (point - start).length_squared
	factor=max(0.0,min(1.0,(point - start).dot(delta) / length_squared))
	return (point - start.lerp(end,factor)).length_squared
def surface_voronoi_segments_are_local(first,second,face_width,tolerance=SURFACE_VORONOI_TOLERANCE,):
	distance_squared=min(surface_voronoi_point_segment_distance_squared(first["start"],second["start"],second["end"]),surface_voronoi_point_segment_distance_squared(first["end"],second["start"],second["end"]),surface_voronoi_point_segment_distance_squared(second["start"],first["start"],first["end"]),surface_voronoi_point_segment_distance_squared(second["end"],first["start"],first["end"] ),)
	reach=face_width * 2.0 + tolerance * 8.0
	return distance_squared <=reach * reach
def surface_voronoi_partition_face(face_points,sites,face_width,face_normal=None,tolerance=SURFACE_VORONOI_TOLERANCE,):
	face_points=[point.copy() for point in face_points or ()]
	if len(face_points) < 3:
		return []
	face_width=max(float(face_width),0.0)
	if face_width <=tolerance:
		return []
	normal=surface_voronoi_polygon_normal(face_points,face_normal)
	if face_normal is not None and normal.dot(face_normal) < 0.0:
		normal.negate()
	if (len(face_points) > 3
		and not surface_voronoi_face_is_planar(face_points,normal,
			tolerance,)):
		raise ValueError("表面Voronoi需要平面支撑面.")
	if not surface_voronoi_face_is_convex(face_points,normal,tolerance):
		raise ValueError("表面Voronoi当前需要凸包支撑面.")
	all_prepared_sites=[surface_voronoi_site_data(face_points,normal,site) for site in sites or ()]
	active_sites=[]
	for site in all_prepared_sites:
		signed_distances=[site["inward"].dot(point) - site["line_offset"] for point in face_points]
		longitudinal=[(point - site["start"]).dot(site["tangent"]) for point in face_points]
		if max(signed_distances) < -tolerance:
			continue
		if min(signed_distances) > face_width + tolerance:
			continue
		if max(longitudinal) < -face_width - tolerance:
			continue
		if min(longitudinal) > site["length"] + face_width + tolerance:
			continue
		active_sites.append(site)
	prepared_sites=active_sites
	prepared_sites.sort(key=lambda site: (str(type(site.get("id")).__name__),str(site.get("id", "")),tuple(round(value,12) for value in site["start"]),tuple(round(value,12) for value in site["end"]),))
	cells=[]
	for site in prepared_sites:
		polygon=[point.copy() for point in face_points]
		polygon=surface_voronoi_clip_halfspace(polygon,-site["inward"],-site["line_offset"],tolerance,)
		polygon=surface_voronoi_clip_halfspace(polygon,site["inward"],site["line_offset"] + face_width,tolerance,)
		midpoint=(site["start"] + site["end"]) * 0.5
		start_join=surface_voronoi_endpoint_join(site,site["start"],all_prepared_sites,normal,face_width,tolerance,)
		end_join=surface_voronoi_endpoint_join(site,site["end"],all_prepared_sites,normal,face_width,tolerance,)
		polygon=surface_voronoi_clip_endpoint_divider(polygon,site["start"],start_join,midpoint,normal,tolerance,)
		polygon=surface_voronoi_clip_endpoint_divider(polygon,site["end"],end_join,midpoint,normal,tolerance,)
		for other in prepared_sites:
			if other is site or len(polygon) < 3:
				continue
			if not surface_voronoi_segments_are_local(site,other,
				face_width,tolerance,):
				continue
			ownership_normal=site["inward"] - other["inward"]
			ownership_offset=site["line_offset"] - other["line_offset"]
			polygon=surface_voronoi_clip_halfspace(polygon,ownership_normal,ownership_offset,tolerance,)
		polygon=surface_voronoi_clean_polygon(polygon,tolerance)
		area=surface_voronoi_polygon_area(polygon,normal)
		if len(polygon) < 3 or area <=tolerance * tolerance:
			continue
		cells.append({"id": site.get("id"),"polygon": polygon,"normal": normal.copy(),"inward": site["inward"].copy(),"line_offset": site["line_offset"],"area": area,"type": ("TRIANGLE" if len(polygon)==3
				else "QUAD" if len(polygon)==4 else "IRREGULAR"), "site": site,})
	return cells
def surface_voronoi_face_world_data(face,world_matrix,normal_matrix):
	points=[world_matrix @ vertex.co for vertex in face.verts]
	normal=surface_voronoi_polygon_normal(points,transform_normal(normal_matrix,face.normal),)
	return {"face": face,"points": points, "normal": normal, "centroid": surface_voronoi_polygon_centroid(points),}
def surface_voronoi_barycentric_map(point,flat_triangle,surface_triangle):
	origin,point_b,point_c=flat_triangle
	edge_b=point_b - origin
	edge_c=point_c - origin
	relative=point - origin
	dot_bb=edge_b.dot(edge_b)
	dot_bc=edge_b.dot(edge_c)
	dot_cc=edge_c.dot(edge_c)
	dot_rb=relative.dot(edge_b)
	dot_rc=relative.dot(edge_c)
	denominator=dot_bb * dot_cc - dot_bc * dot_bc
	if abs(denominator) <=EPSILON:
		return surface_triangle[0].copy()
	weight_b=(dot_cc * dot_rb - dot_bc * dot_rc) / denominator
	weight_c=(dot_bb * dot_rc - dot_bc * dot_rb) / denominator
	weight_a=1.0 - weight_b - weight_c
	return (surface_triangle[0] * weight_a + surface_triangle[1] * weight_b + surface_triangle[2] * weight_c)
def surface_voronoi_partition_surface_face(face_data,sites,face_width,tolerance=SURFACE_VORONOI_TOLERANCE,):
	points=face_data["points"]
	normal=face_data["normal"]
	if (surface_voronoi_face_is_planar(points,normal,tolerance)
		and surface_voronoi_face_is_convex(points,normal,tolerance)):
		cells=surface_voronoi_partition_face(points,sites,face_width,face_normal=normal,tolerance=tolerance,)
		for cell in cells:
			cell["surface_polygon_raw"]=[point.copy() for point in cell["polygon"]]
			cell["parameter_polygon"]=[point.copy() for point in cell["polygon"]]
		return cells
	from mathutils.geometry import tessellate_polygon
	origin=face_data["centroid"]
	axis_u=None
	for index,point in enumerate(points):
		candidate=points[(index + 1) % len(points)] - point
		candidate -=normal * candidate.dot(normal)
		if candidate.length_squared > EPSILON:
			axis_u=candidate.normalized()
			break
	if axis_u is None:
		raise ValueError("表面Voronoi无法参数化支撑面.")
	axis_v=safe_normalized(normal.cross(axis_u))
	def flatten(point):
		delta=point - origin
		return (origin
			+ axis_u * delta.dot(axis_u)
			+ axis_v * delta.dot(axis_v))
	flat_points=[flatten(point) for point in points]
	flat_sites=[]
	for site in sites:
		flat_site=dict(site)
		flat_site["start"]=flatten(site["start"])
		flat_site["end"]=flatten(site["end"])
		supplied_inward=site.get("inward")
		if supplied_inward is not None:
			projected=supplied_inward - normal * supplied_inward.dot(normal)
			flat_site["inward"]=safe_normalized(projected,axis_v,)
		flat_sites.append(flat_site)
	triangles=list(tessellate_polygon([flat_points]))
	if not triangles:
		raise ValueError("表面Voronoi无法三角化支持面.")
	cells=[]
	for triangle in triangles:
		if triangle and isinstance(triangle[0],int):
			original_indices=list(triangle)
			flat_triangle=[flat_points[index].copy() for index in original_indices]
		else:
			flat_triangle=[point.copy() for point in triangle]
			original_indices=[min(range(len(flat_points)),
					key=lambda index: (flat_points[index] - point).length_squared,) for point in flat_triangle]
		surface_triangle=[points[index].copy() for index in original_indices]
		triangle_normal=surface_voronoi_polygon_normal(surface_triangle,normal,)
		if triangle_normal.dot(normal) < 0.0:
			flat_triangle.reverse()
			surface_triangle.reverse()
			triangle_normal.negate()
		triangle_cells=surface_voronoi_partition_face(flat_triangle,flat_sites,face_width,face_normal=normal,tolerance=tolerance,)
		for cell in triangle_cells:
			parameter_polygon=[point.copy() for point in cell["polygon"]]
			surface_polygon=[surface_voronoi_barycentric_map(point,flat_triangle,surface_triangle,) for point in parameter_polygon]
			cell["normal"]=triangle_normal.copy()
			cell["surface_polygon_raw"]=surface_polygon
			cell["parameter_polygon"]=parameter_polygon
			cell["area"]=surface_voronoi_polygon_area(surface_polygon,triangle_normal,)
			cells.append(cell)
	return cells
def surface_voronoi_clip_polygon_to_convex_carrier(polygon,carrier_points,carrier_normal,tolerance=SURFACE_VORONOI_TOLERANCE,):
	polygon=[point.copy() for point in polygon or ()]
	carrier_points=[point.copy() for point in carrier_points or ()]
	if len(polygon) < 3 or len(carrier_points) < 3:
		return []
	normal=safe_normalized(carrier_normal)
	if surface_voronoi_polygon_normal(carrier_points,normal,).dot(normal) < 0.0:
		carrier_points.reverse()
	for index,start in enumerate(carrier_points):
		end=carrier_points[(index + 1) % len(carrier_points)]
		edge_direction=end - start
		if edge_direction.length_squared <=tolerance * tolerance:
			continue
		inward=safe_normalized(normal.cross(edge_direction))
		polygon=surface_voronoi_clip_halfspace(polygon,-inward,(-inward).dot(start),tolerance,)
		if len(polygon) < 3:
			return []
	polygon=surface_voronoi_clean_polygon(polygon,tolerance)
	if (len(polygon) < 3
		or surface_voronoi_polygon_area(polygon,normal)
		<=tolerance * tolerance):
		return []
	if surface_voronoi_polygon_normal(polygon,normal).dot(normal) < 0.0:
		polygon.reverse()
	return polygon
def surface_voronoi_clip_polygon_to_surface_face(polygon,face_data,chart_normal,tolerance=SURFACE_VORONOI_TOLERANCE,):
	face_points=[point.copy() for point in face_data["points"]]
	normal=safe_normalized(chart_normal,face_data["normal"])
	if len(face_points) < 3:
		return []
	if surface_voronoi_face_is_convex(face_points,normal,tolerance):
		clipped=surface_voronoi_clip_polygon_to_convex_carrier(polygon,face_points,normal,tolerance,)
		return [clipped] if clipped else []
	from mathutils.geometry import tessellate_polygon
	triangles=tessellate_polygon([face_points])
	fragments=[]
	for triangle in triangles:
		triangle_points=([face_points[index].copy() for index in triangle]
			if triangle and isinstance(triangle[0],int)
			else [point.copy() for point in triangle])
		clipped=surface_voronoi_clip_polygon_to_convex_carrier(polygon,triangle_points,normal,tolerance,)
		if clipped:
			fragments.append(clipped)
	return fragments
def surface_voronoi_faces_are_coplanar(reference,candidate,tolerance=SURFACE_VORONOI_TOLERANCE,):
	if reference["normal"].dot(candidate["normal"]) < 1.0 - 1.0e-6:
		return False
	origin=reference["points"][0]
	scale=max(max((point - origin).length for point in reference["points"]),max((point - origin).length for point in candidate["points"]),1.0,)
	return all(abs(reference["normal"].dot(point - origin)) <=tolerance * 8.0 * scale for point in candidate["points"])
def surface_voronoi_build_surface_charts(selected_edges,world_matrix,normal_matrix,tolerance=SURFACE_VORONOI_TOLERANCE,):
	seed_faces={face for edge in selected_edges for face in edge.link_faces}
	world_data={}
	def data(face):
		record=world_data.get(face)
		if record is None:
			record=surface_voronoi_face_world_data(face,world_matrix,normal_matrix,)
			world_data[face]=record
		return record
	charts=[]
	face_to_chart={}
	for seed in sorted(seed_faces,key=lambda face: face.index):
		if seed in face_to_chart:
			continue
		chart_index=len(charts)
		reference=data(seed)
		pending=[seed]
		chart_faces=[]
		face_to_chart[seed]=chart_index
		while pending:
			face=pending.pop()
			chart_faces.append(face)
			for edge in face.edges:
				for neighbor in edge.link_faces:
					if neighbor==face or neighbor in face_to_chart:
						continue
					neighbor_data=data(neighbor)
					if not surface_voronoi_faces_are_coplanar(reference,neighbor_data,
						tolerance,):
						continue
					face_to_chart[neighbor]=chart_index
					pending.append(neighbor)
		charts.append({"index": chart_index,"faces": sorted(chart_faces,key=lambda face: face.index),"normal": reference["normal"].copy(),})
	return charts,face_to_chart,world_data
def surface_voronoi_face_edge_inward(face,edge,world_matrix,face_normal,fallback,):
	loop=next((item for item in face.loops if item.edge==edge),None)
	if loop is None:
		return safe_normalized(fallback)
	loop_start=world_matrix @ loop.vert.co
	loop_end=world_matrix @ loop.link_loop_next.vert.co
	loop_direction=safe_normalized(loop_end - loop_start)
	inward=face_normal.cross(loop_direction)
	inward -=face_normal * inward.dot(face_normal)
	return safe_normalized(inward,fallback)
def surface_voronoi_selected_vertex_normals(source_vertex,selected_edge_set,normal_matrix,):
	normals=[]
	for edge in source_vertex.link_edges:
		if edge not in selected_edge_set or not edge.link_faces:
			continue
		for face in edge.link_faces:
			normal=transform_normal(normal_matrix,face.normal)
			if any(normal.dot(existing) > 0.999999 for existing in normals):
				continue
			normals.append(normal)
	return normals
def surface_voronoi_lift_cell_point(point,cell,source_edge,selected_edge_set,world_matrix,normal_matrix,surface_offset,tolerance=SURFACE_VORONOI_TOLERANCE,):
	if surface_offset <=EPSILON:
		return point.copy()
	site=cell["site"]
	signed_distance=site["inward"].dot(point) - site["line_offset"]
	tangent=site["end"] - site["start"]
	length_squared=tangent.length_squared
	longitudinal=((point - site["start"]).dot(tangent) / max(tangent.length,EPSILON))
	if (abs(signed_distance) > tolerance
		or longitudinal < -tolerance
		or longitudinal > tangent.length + tolerance):
		return point + cell["normal"] * surface_offset
	start=site["start"]
	end=site["end"]
	factor=(max(0.0,min(1.0,(point - start).dot(tangent) / length_squared)) if length_squared > EPSILON else 0.0)
	endpoint_tolerance=tolerance * max(tangent.length,1.0)
	if (point - start).length <=endpoint_tolerance:
		source_vertex=source_edge.verts[0]
		if (world_matrix @ source_vertex.co - start).length > endpoint_tolerance:
			source_vertex=source_edge.verts[1]
		normals=surface_voronoi_selected_vertex_normals(source_vertex,selected_edge_set,normal_matrix,)
	elif (point - end).length <=endpoint_tolerance:
		source_vertex=source_edge.verts[0]
		if (world_matrix @ source_vertex.co - end).length > endpoint_tolerance:
			source_vertex=source_edge.verts[1]
		normals=surface_voronoi_selected_vertex_normals(source_vertex,selected_edge_set,normal_matrix,)
	else:
		normals=[transform_normal(normal_matrix,face.normal) for face in source_edge.link_faces]
	source_point=start.lerp(end,factor)
	return offset_point_from_face_normals(source_point,normals,surface_offset,)
def surface_voronoi_sites_share_endpoint(first,second):
	first_vertices={vertex for vertex in (first.get("start_vertex"),first.get("end_vertex")) if vertex is not None}
	second_vertices={vertex for vertex in (second.get("start_vertex"),second.get("end_vertex")) if vertex is not None}
	if first_vertices and second_vertices:
		return bool(first_vertices & second_vertices)
	return any((first[first_key] - second[second_key]).length
		<=SURFACE_VORONOI_TOLERANCE * 8.0
		for first_key in ("start", "end")
		for second_key in ("start", "end"))
def surface_voronoi_assign_curve_ids(chart_index,sites):
	sites=list(sites or ())
	parents=list(range(len(sites)))
	def find(index):
		while parents[index] !=index:
			parents[index]=parents[parents[index]]
			index=parents[index]
		return index
	def union(first,second):
		first_root=find(first)
		second_root=find(second)
		if first_root==second_root:
			return
		if first_root > second_root:
			first_root,second_root=second_root,first_root
		parents[second_root]=first_root
	vertex_sites={}
	for index,site in enumerate(sites):
		for vertex in (site.get("start_vertex"),site.get("end_vertex")):
			if vertex is not None:
				vertex_sites.setdefault(vertex,[]).append(index)
	for indices in vertex_sites.values():
		if len(indices)==2:
			union(indices[0],indices[1])
	roots={}
	for index,site in enumerate(sites):
		root=find(index)
		component=roots.setdefault(root,len(roots))
		site["curve_id"]=(chart_index,component)
def surface_voronoi_conditional_band_ownership(polygon,competitor_band,ownership_normal,ownership_offset,face_normal,tolerance=SURFACE_VORONOI_TOLERANCE,):
	remaining=[point.copy() for point in polygon or ()]
	competitor=[point.copy() for point in competitor_band or ()]
	if len(remaining) < 3 or len(competitor) < 3:
		return [remaining] if len(remaining) >=3 else []
	normal=safe_normalized(face_normal)
	if surface_voronoi_polygon_normal(competitor,normal).dot(normal) < 0.0:
		competitor.reverse()
	outside_fragments=[]
	for index,start in enumerate(competitor):
		end=competitor[(index + 1) % len(competitor)]
		edge_direction=end - start
		if edge_direction.length_squared <=tolerance * tolerance:
			continue
		inward=safe_normalized(normal.cross(edge_direction))
		outside=surface_voronoi_clip_halfspace(remaining,inward,inward.dot(start),tolerance,)
		if len(outside) >=3:
			outside_fragments.append(outside)
		remaining=surface_voronoi_clip_halfspace(remaining,-inward,(-inward).dot(start),tolerance,)
		if len(remaining) < 3:
			return outside_fragments
	owned_overlap=surface_voronoi_clip_halfspace(remaining,ownership_normal,ownership_offset,tolerance,)
	if len(owned_overlap) >=3:
		outside_fragments.append(owned_overlap)
	return [cleaned for fragment in outside_fragments if len(cleaned:=surface_voronoi_clean_polygon(fragment,tolerance,)) >=3 and surface_voronoi_polygon_area(cleaned,normal) > tolerance * tolerance]
def surface_voronoi_reference_chart_cells(chart,sites,selected_edge_set,world_matrix,normal_matrix,face_width,surface_offset,tolerance=SURFACE_VORONOI_TOLERANCE,partition_ownership=True,):
	normal=chart["normal"]
	prepared_sites=[]
	for site in sites:
		prepared_sites.append(surface_voronoi_site_data([site["start"],site["end"],site["start"] + site["inward"],],normal,site,))
	prepared_sites.sort(key=lambda site: (str(type(site.get("id")).__name__),str(site.get("id", "")),))
	base_bands={}
	for site in prepared_sites:
		start_join=surface_voronoi_endpoint_join(site,site["start"],prepared_sites,normal,face_width,tolerance,)
		end_join=surface_voronoi_endpoint_join(site,site["end"],prepared_sites,normal,face_width,tolerance,)
		start_factor=(start_join - site["start"]).dot(site["tangent"])
		end_factor=(end_join - site["start"]).dot(site["tangent"])
		if start_factor >=end_factor - tolerance:
			inner=(start_join + end_join) * 0.5
			polygon=[site["start"],site["end"],inner]
		else:
			polygon=[site["start"],site["end"],end_join,start_join,]
		polygon=surface_voronoi_clean_polygon(polygon,tolerance)
		if len(polygon) < 3:
			continue
		if surface_voronoi_polygon_normal(polygon,normal).dot(normal) < 0.0:
			polygon.reverse()
		if (surface_voronoi_polygon_area(polygon,normal)
			<=tolerance * tolerance):
			continue
		base_bands[id(site)]=polygon
	records=[]
	for site in prepared_sites:
		polygon=base_bands.get(id(site))
		if polygon is None:
			continue
		fragments=[[point.copy() for point in polygon]]
		for other in prepared_sites if partition_ownership else ():
			if other is site or not fragments:
				continue
			if (site.get("curve_id") is not None
				and site.get("curve_id")==other.get("curve_id")):
				continue
			if surface_voronoi_sites_share_endpoint(site,other):
				continue
			if not surface_voronoi_segments_are_local(site,other,
				face_width,tolerance,):
				continue
			competitor_band=base_bands.get(id(other))
			if competitor_band is None:
				continue
			ownership_normal=site["inward"] - other["inward"]
			ownership_offset=site["line_offset"] - other["line_offset"]
			fragments=[owned_fragment for fragment in fragments for owned_fragment in surface_voronoi_conditional_band_ownership(fragment,competitor_band,ownership_normal,ownership_offset,normal,tolerance,) 	]
		source_edge=site["source_edge"]
		source_face=site["source_side_face"]
		cell_stub={"site": site, "normal": normal}
		for polygon in fragments:
			polygon=surface_voronoi_clean_polygon(polygon,tolerance)
			if len(polygon) < 3:
				continue
			if surface_voronoi_polygon_normal(polygon,normal,).dot(normal) < 0.0:
				polygon.reverse()
			area=surface_voronoi_polygon_area(polygon,normal)
			if area <=tolerance * tolerance:
				continue
			lifted=[surface_voronoi_lift_cell_point(point,cell_stub,source_edge,selected_edge_set,world_matrix,normal_matrix,surface_offset,tolerance,) for point in polygon]
			records.append({"id": site.get("id"),"polygon": lifted,"surface_polygon": [point.copy() for point in polygon],"surface_polygon_raw": [point.copy() for point in polygon],"parameter_polygon": [point.copy() for point in polygon],"normal": normal.copy(),"area": area,"type": ("TRIANGLE" if len(polygon)==3
					else "QUAD" if len(polygon)==4
					else "IRREGULAR"),"site": site,"source_edge": source_edge,"source_face": source_face,"source_side_face": source_face,"source_side_index": site["source_side_index"],"source_edge_index": source_edge.index,"source_face_index": source_face.index,"chart_index": chart["index"],"owner_id": (chart["index"],site["id"]),})
	return surface_voronoi_merge_chart_fragments(records,tolerance)
def surface_voronoi_point_in_polygon_2d(point,polygon,tolerance=SURFACE_VORONOI_TOLERANCE,):
	polygon=list(polygon or ())
	if len(polygon) < 3:
		return False
	inside=False
	for index,start in enumerate(polygon):
		end=polygon[(index + 1) % len(polygon)]
		edge=end - start
		relative=point - start
		edge_length_squared=edge.length_squared
		if edge_length_squared > EPSILON:
			factor=max(0.0,min(1.0,relative.dot(edge) / edge_length_squared),)
			if (point - start.lerp(end,factor)).length <=tolerance:
				return True
		if (start.y > point.y)==(end.y > point.y):
			continue
		crossing_x=(start.x
			+ (point.y - start.y) * (end.x - start.x)
			/ (end.y - start.y))
		if crossing_x >=point.x - tolerance:
			inside=not inside
	return inside
def surface_voronoi_bisector_segment_in_overlap(first_polygon,second_polygon,ownership_normal,ownership_offset,face_normal,tolerance=SURFACE_VORONOI_TOLERANCE,):
	if ownership_normal.length_squared <=tolerance * tolerance:
		return None
	overlap=surface_voronoi_clip_polygon_to_convex_carrier(first_polygon,second_polygon,face_normal,tolerance,)
	if len(overlap) < 3:
		return None
	intersections=[]
	def append_unique(point):
		if any((point - existing).length <=tolerance * 8.0 for existing in intersections):
			return
		intersections.append(point.copy())
	for index,start in enumerate(overlap):
		end=overlap[(index + 1) % len(overlap)]
		start_value=ownership_normal.dot(start) - ownership_offset
		end_value=ownership_normal.dot(end) - ownership_offset
		if abs(start_value) <=tolerance:
			append_unique(start)
		if start_value * end_value < -(tolerance * tolerance):
			factor=start_value / (start_value - end_value)
			append_unique(start.lerp(end,factor))
		elif abs(end_value) <=tolerance:
			append_unique(end)
	if len(intersections) < 2:
		return None
	return max(((first,second)
			for first_index,first in enumerate(intersections[:-1])
			for second in intersections[first_index + 1:]),
		key=lambda pair: (pair[1] - pair[0]).length_squared,)
def surface_voronoi_chart_arrangement_cells(chart,base_cells,world_data,selected_edge_set,world_matrix,normal_matrix,surface_offset,tolerance=SURFACE_VORONOI_TOLERANCE,overlap_clearance=1.0,):
	if not base_cells:
		return []
	overlap_clearance=max(0.0,min(1.0,float(overlap_clearance)))
	normal=safe_normalized(chart["normal"])
	origin=world_data[chart["faces"][0]]["points"][0].copy()
	axis_u=None
	for face in chart["faces"]:
		points=world_data[face]["points"]
		for index,point in enumerate(points):
			candidate=points[(index + 1) % len(points)] - point
			candidate -=normal * candidate.dot(normal)
			if candidate.length_squared > tolerance * tolerance:
				axis_u=candidate.normalized()
				break
		if axis_u is not None:
			break
	if axis_u is None:
		return []
	axis_v=safe_normalized(normal.cross(axis_u))
	def flatten(point):
		delta=point - origin
		return Vector((delta.dot(axis_u),delta.dot(axis_v)))
	def lift_parameter(point):
		return origin + axis_u * point.x + axis_v * point.y
	input_vertices=[]
	input_edges=[]
	edge_keys=set()
	vertex_buckets={}
	vertex_tolerance=max(tolerance * 8.0,1.0e-9)
	def vertex_for(point):
		key=(int(round(point.x / vertex_tolerance)),int(round(point.y / vertex_tolerance)),)
		for offset_x in (-1,0,1):
			for offset_y in (-1,0,1):
				for index in vertex_buckets.get((key[0] + offset_x,key[1] + offset_y),(),):
					if (input_vertices[index] - point).length <=vertex_tolerance:
						return index
		index=len(input_vertices)
		input_vertices.append(point.copy())
		vertex_buckets.setdefault(key,[]).append(index)
		return index
	def add_segment(start,end):
		first=vertex_for(flatten(start))
		second=vertex_for(flatten(end))
		if first==second:
			return
		key=tuple(sorted((first,second)))
		if key in edge_keys:
			return
		edge_keys.add(key)
		input_edges.append((first,second))
	def add_loop(points):
		for index,start in enumerate(points):
			add_segment(start,points[(index + 1) % len(points)])
	carrier_polygons_2d=[]
	for face in chart["faces"]:
		points=world_data[face]["points"]
		add_loop(points)
		carrier_polygons_2d.append([flatten(point) for point in points])
	band_polygons_2d=[]
	for cell in base_cells:
		polygon=cell["surface_polygon_raw"]
		add_loop(polygon)
		band_polygons_2d.append([flatten(point) for point in polygon])
	for first_index,first in enumerate(base_cells[:-1]):
		first_site=first["site"]
		first_polygon=first["surface_polygon_raw"]
		for second in base_cells[first_index + 1:]:
			second_site=second["site"]
			if (first_site.get("curve_id") is not None
				and first_site.get("curve_id")==second_site.get("curve_id")):
				continue
			if surface_voronoi_sites_share_endpoint(first_site,second_site):
				continue
			if not surface_voronoi_segments_are_local(first_site,second_site,max(max(first_site["inward"].dot(point)
						- first_site["line_offset"]
						for point in first_polygon),tolerance,),tolerance,):
				continue
			ownership_boundaries=((first_site["inward"]
					- second_site["inward"] * overlap_clearance,first_site["line_offset"]
					- second_site["line_offset"] * overlap_clearance,),(first_site["inward"] * overlap_clearance - second_site["inward"],first_site["line_offset"] * overlap_clearance - second_site["line_offset"],),)
			for ownership_normal,ownership_offset in ownership_boundaries:
				bisector=surface_voronoi_bisector_segment_in_overlap(first_polygon,second["surface_polygon_raw"],ownership_normal,ownership_offset,normal,tolerance,)
				if bisector is not None:
					add_segment(*bisector)
	if len(input_vertices) < 3:
		return []
	from mathutils.geometry import delaunay_2d_cdt
	output=delaunay_2d_cdt(input_vertices,input_edges,[],0,max(tolerance,1.0e-9),False,)
	output_vertices,_output_edges,output_faces=output[:3]
	records=[]
	for output_face in output_faces:
		if len(output_face) < 3:
			continue
		parameter_polygon=[output_vertices[index].copy() for index in output_face]
		centroid=sum(parameter_polygon,Vector((0.0,0.0))) / len(parameter_polygon)
		if not any(surface_voronoi_point_in_polygon_2d(centroid,carrier_polygon,tolerance * 8.0,)
			for carrier_polygon in carrier_polygons_2d):
			continue
		candidates=[cell for cell,band_polygon in zip(base_cells,band_polygons_2d) if surface_voronoi_point_in_polygon_2d(centroid,band_polygon,tolerance * 8.0,)]
		if not candidates:
			continue
		surface_centroid=lift_parameter(centroid)
		owner=min(candidates,
			key=lambda cell: (surface_voronoi_point_segment_distance_squared(surface_centroid,cell["site"]["start"],cell["site"]["end"],),str(cell["owner_id"]),),)
		competing_distances=[surface_voronoi_point_segment_distance_squared(surface_centroid,candidate["site"]["start"],candidate["site"]["end"],)
			for candidate in candidates
			if candidate["site"].get("curve_id")
			!=owner["site"].get("curve_id")]
		if competing_distances:
			owner_distance=surface_voronoi_point_segment_distance_squared(surface_centroid,owner["site"]["start"],owner["site"]["end"],)
			if (owner_distance
				> overlap_clearance * overlap_clearance
				* min(competing_distances)
				+ tolerance * tolerance):
				continue
		surface_polygon=[lift_parameter(point) for point in parameter_polygon]
		if surface_voronoi_polygon_normal(surface_polygon,normal,).dot(normal) < 0.0:
			surface_polygon.reverse()
			parameter_polygon.reverse()
		source_edge=owner["source_edge"]
		cell_stub={"site": owner["site"], "normal": normal}
		lifted_polygon=[surface_voronoi_lift_cell_point(point,cell_stub,source_edge,selected_edge_set,world_matrix,normal_matrix,surface_offset,tolerance,) for point in surface_polygon]
		area=surface_voronoi_polygon_area(surface_polygon,normal)
		if area <=tolerance * tolerance:
			continue
		records.append({**owner,"polygon": lifted_polygon,"surface_polygon": surface_polygon,"surface_polygon_raw": [point.copy() for point in surface_polygon],"parameter_polygon": [point.copy() for point in surface_polygon],"normal": normal.copy(),"area": area,"type": ("TRIANGLE" if len(surface_polygon)==3
				else "QUAD" if len(surface_polygon)==4 else "IRREGULAR"), "arrangement_cell": True,})
	return records
def build_surface_voronoi_cells(selected_edges,world_matrix,normal_matrix,face_width,surface_offset=0.0,tolerance=SURFACE_VORONOI_TOLERANCE,overlap_clearance=1.0,):
	selected_edges=sorted({edge for edge in selected_edges or ()
			if len(edge.link_faces) >=1},key=lambda edge: edge.index,)
	if not selected_edges:
		return []
	selected_edge_set=set(selected_edges)
	charts,face_to_chart,world_data=(surface_voronoi_build_surface_charts(selected_edges,world_matrix,normal_matrix,tolerance,))
	records=[]
	for chart in charts:
		chart_index=chart["index"]
		chart_face_set=set(chart["faces"])
		sites=[]
		edge_by_id={}
		for edge in selected_edges:
			linked_chart_faces=[face for face in edge.link_faces if face in chart_face_set]
			if not linked_chart_faces:
				continue
			start=world_matrix @ edge.verts[0].co
			end=world_matrix @ edge.verts[1].co
			tangent=safe_normalized(end - start,Vector((1.0,0.0,0.0)))
			midpoint=(start + end) * 0.5
			emitted_inwards=[]
			for side_face in sorted(linked_chart_faces,
				key=lambda face: face.index,):
				side_data=world_data[side_face]
				inward=surface_voronoi_face_edge_inward(side_face,edge,world_matrix,chart["normal"],side_data["centroid"] - midpoint,)
				if any(inward.dot(existing) > 0.999999 for existing in emitted_inwards):
					continue
				emitted_inwards.append(inward)
				side_index=next(index
					for index,face in enumerate(edge.link_faces) if face==side_face)
				site_id=(edge.index,side_index)
				edge_by_id[site_id]=(edge,side_face,side_index)
				sites.append({"id": site_id,"start": start,"end": end,"inward": inward, "source_side_index": side_index,"source_edge": edge, "source_side_face": side_face,"start_vertex": edge.verts[0], "end_vertex": edge.verts[1],})
		surface_voronoi_assign_curve_ids(chart_index,sites)
		base_cells=surface_voronoi_reference_chart_cells(chart,sites,selected_edge_set,world_matrix,normal_matrix,face_width,0.0,tolerance,partition_ownership=False,)
		records.extend(surface_voronoi_chart_arrangement_cells(chart,base_cells,world_data,selected_edge_set,world_matrix,normal_matrix,surface_offset,tolerance,overlap_clearance,))
	return surface_voronoi_merge_chart_fragments(records,tolerance)
def surface_voronoi_vertex_key(point,tolerance=SURFACE_VORONOI_TOLERANCE,):
	quantum=max(float(tolerance),1.0e-10)
	return tuple(int(round(component / quantum)) for component in point)
def surface_voronoi_merge_chart_fragments(cells,tolerance=SURFACE_VORONOI_TOLERANCE,):
	groups={}
	for cell in cells or ():
		groups.setdefault(cell.get("owner_id",(cell.get("chart_index"),cell.get("id")),),[],).append(cell)
	merged=[]
	weld_tolerance=max(float(tolerance) * 8.0,1.0e-9)
	for owner_id in sorted(groups,key=lambda item: str(item)):
		fragments=groups[owner_id]
		if len(fragments)==1:
			merged.extend(fragments)
			continue
		nodes=[]
		buckets={}
		def node_for(surface_point,lifted_point,parameter_point):
			key=surface_voronoi_vertex_key(surface_point,weld_tolerance)
			for offset_x in (-1,0,1):
				for offset_y in (-1,0,1):
					for offset_z in (-1,0,1):
						neighbor=(key[0] + offset_x,key[1] + offset_y,key[2] + offset_z,)
						for index in buckets.get(neighbor,()):
							if (nodes[index][0] - surface_point).length <=weld_tolerance:
								return index
			index=len(nodes)
			nodes.append((surface_point.copy(),lifted_point.copy(),parameter_point.copy(),))
			buckets.setdefault(key,[]).append(index)
			return index
		polygon_node_loops=[]
		invalid=False
		for fragment in fragments:
			surface_polygon=list(fragment["surface_polygon"])
			lifted_polygon=list(fragment["polygon"])
			parameter_polygon=list(fragment.get("parameter_polygon",surface_polygon))
			if len(surface_polygon) !=len(lifted_polygon):
				invalid=True
				break
			normal=fragment["normal"]
			if surface_voronoi_polygon_normal(surface_polygon,normal,).dot(normal) < 0.0:
				surface_polygon.reverse()
				lifted_polygon.reverse()
				parameter_polygon.reverse()
			polygon_nodes=[node_for(surface_point,lifted_point,parameter_point) for surface_point,lifted_point,parameter_point in zip(surface_polygon,lifted_polygon,parameter_polygon,)]
			polygon_node_loops.append(polygon_nodes)
		if invalid:
			merged.extend(fragments)
			continue
		edge_uses={}
		for polygon_index,polygon_nodes in enumerate(polygon_node_loops):
			for edge_index,start in enumerate(polygon_nodes):
				end=polygon_nodes[(edge_index + 1) % len(polygon_nodes)]
				if start==end:
					continue
				start_point=nodes[start][0]
				end_point=nodes[end][0]
				delta=end_point - start_point
				length_squared=delta.length_squared
				if length_squared <=weld_tolerance * weld_tolerance:
					continue
				split_nodes=[(0.0,start),(1.0,end)]
				for candidate,node in enumerate(nodes):
					if candidate==start or candidate==end:
						continue
					relative=node[0] - start_point
					factor=relative.dot(delta) / length_squared
					if factor <=tolerance or factor >=1.0 - tolerance:
						continue
					closest=start_point + delta * factor
					if (node[0] - closest).length <=weld_tolerance:
						split_nodes.append((factor,candidate))
				split_nodes.sort(key=lambda item: (item[0],item[1]))
				for split_index in range(len(split_nodes) - 1):
					sub_start=split_nodes[split_index][1]
					sub_end=split_nodes[split_index + 1][1]
					if sub_start==sub_end:
						continue
					key=tuple(sorted((sub_start,sub_end)))
					edge_uses.setdefault(key,[]).append((sub_start,sub_end,polygon_index))
		parents=list(range(len(fragments)))
		def find_fragment(index):
			while parents[index] !=index:
				parents[index]=parents[parents[index]]
				index=parents[index]
			return index
		def union_fragments(first,second):
			first_root=find_fragment(first)
			second_root=find_fragment(second)
			if first_root==second_root:
				return
			if first_root > second_root:
				first_root,second_root=second_root,first_root
			parents[second_root]=first_root
		for uses in edge_uses.values():
			polygon_indices=sorted({use[2] for use in uses})
			for polygon_index in polygon_indices[1:]:
				union_fragments(polygon_indices[0],polygon_index)
		components={}
		for polygon_index in range(len(fragments)):
			components.setdefault(find_fragment(polygon_index),[],).append(polygon_index)
		for component_indices in components.values():
			component_set=set(component_indices)
			boundary_edges=[]
			for uses in edge_uses.values():
				component_uses=[use for use in uses if use[2] in component_set]
				if len(component_uses)==1:
					boundary_edges.append(component_uses[0][:2])
			outgoing={}
			for start,end in boundary_edges:
				outgoing.setdefault(start,[]).append(end)
			unused=set(boundary_edges)
			loops=[]
			component_invalid=False
			while unused:
				first=min(unused)
				start,current=first
				loop=[start]
				unused.remove(first)
				guard=0
				while current !=start and guard <=len(boundary_edges):
					loop.append(current)
					candidates=[end for end in outgoing.get(current,()) if (current,end) in unused]
					if not candidates:
						component_invalid=True
						break
					following=min(candidates)
					unused.remove((current,following))
					current=following
					guard +=1
				if component_invalid or current !=start:
					component_invalid=True
					break
				if len(loop) >=3:
					loops.append(loop)
			if component_invalid or len(loops) !=1:
				merged.extend(fragments[index] for index in component_indices)
				continue
			loop=loops[0]
			template=fragments[component_indices[0]]
			changed=True
			while changed and len(loop) > 3:
				changed=False
				for index,node_index in enumerate(loop):
					previous=nodes[loop[(index - 1) % len(loop)]][0]
					point=nodes[node_index][0]
					following=nodes[loop[(index + 1) % len(loop)]][0]
					before=point - previous
					after=following - point
					scale=max(before.length,after.length,1.0)
					if before.cross(after).length <=tolerance * scale:
						del loop[index]
						changed=True
						break
			surface_polygon=[nodes[index][0].copy() for index in loop]
			lifted_polygon=[nodes[index][1].copy() for index in loop]
			parameter_polygon=[nodes[index][2].copy() for index in loop]
			area=surface_voronoi_polygon_area(surface_polygon,template["normal"],)
			if area <=tolerance * tolerance:
				continue
			merged.append({**template,"polygon": lifted_polygon,"surface_polygon": surface_polygon,"parameter_polygon": parameter_polygon,"area": area,"type": ("TRIANGLE" if len(loop)==3
					else "QUAD" if len(loop)==4 else "IRREGULAR"),})
	return merged
def surface_voronoi_cell_uvs(cell,face_width,uv_scale=1.0):
	site=cell["site"]
	source_edge=cell["source_edge"]
	source_face=cell["source_face"]
	side_index=cell.get("source_side_index")
	if side_index is None:
		side_index=next((index
				for index,face in enumerate(source_edge.link_faces) if face==source_face),0,)
	outer_v=0.0 if side_index==0 else 1.0
	safe_width=max(float(face_width),EPSILON)
	safe_scale=max(float(uv_scale),1.0e-8)
	uvs=[]
	parameter_polygon=cell.get("parameter_polygon",cell["surface_polygon"],)
	for point in parameter_polygon:
		longitudinal=(point - site["start"]).dot(site["tangent"]) * safe_scale
		distance=(site["inward"].dot(point) - site["line_offset"])
		width_factor=max(0.0,min(1.0,distance / safe_width))
		transverse=0.5 + (outer_v - 0.5) * width_factor
		uvs.append((longitudinal,transverse))
	return uvs
def surface_voronoi_clean_generated_loop(records):
	cleaned=[]
	for record in records:
		if cleaned and cleaned[-1][0]==record[0]:
			continue
		cleaned.append(record)
	if len(cleaned) > 1 and cleaned[0][0]==cleaned[-1][0]:
		cleaned.pop()
	return cleaned
def surface_voronoi_split_self_touching_loop(records):
	records=surface_voronoi_clean_generated_loop(records)
	if len(records) < 3:
		return []
	first_position={}
	for position,record in enumerate(records):
		vertex_index=record[0]
		if vertex_index not in first_position:
			first_position[vertex_index]=position
			continue
		start=first_position[vertex_index]
		first_loop=records[start:position]
		second_loop=records[position:] + records[:start]
		return (surface_voronoi_split_self_touching_loop(first_loop)
			+ surface_voronoi_split_self_touching_loop(second_loop))
	return [records]
def surface_voronoi_generated_loop_is_safe_quad(records,vertices,target_normal,tolerance=SURFACE_VORONOI_TOLERANCE,):
	if len(records) !=4:
		return False
	points=[vertices[record[0]] for record in records]
	origin=points[0]
	scale=max(max((point - origin).length for point in points),1.0)
	if surface_voronoi_float32_polygon_area(points) <=tolerance * tolerance:
		return False
	turn_sign=0
	for index,point in enumerate(points):
		previous=points[(index - 1) % 4]
		following=points[(index + 1) % 4]
		turn=(point - previous).cross(following - point).dot(target_normal)
		if abs(turn) <=tolerance * scale * scale:
			return False
		candidate=1 if turn > 0.0 else -1
		if turn_sign and candidate !=turn_sign:
			return False
		turn_sign=candidate
	return True
def surface_voronoi_generated_loop_is_safe_ngon(records,vertices,target_normal,tolerance=SURFACE_VORONOI_TOLERANCE,):
	if len(records) < 5:
		return False
	indices=[record[0] for record in records]
	if len(set(indices)) !=len(indices):
		return False
	points=[vertices[index] for index in indices]
	normal=safe_normalized(target_normal)
	origin=points[0]
	scale=max(max((point - origin).length for point in points),1.0)
	if any(abs(normal.dot(point - origin)) > tolerance * 16.0 * scale
		for point in points[1:]):
		return False
	if surface_voronoi_float32_polygon_area(points) <=tolerance * tolerance:
		return False
	axis_u=None
	for point in points[1:]:
		candidate=point - origin
		candidate -=normal * candidate.dot(normal)
		if candidate.length_squared > tolerance * tolerance:
			axis_u=candidate.normalized()
			break
	if axis_u is None:
		return False
	axis_v=safe_normalized(normal.cross(axis_u))
	flat=[Vector(((point - origin).dot(axis_u),(point - origin).dot(axis_v))) for point in points]
	def cross_2d(first,second):
		return first.x * second.y - first.y * second.x
	def segments_intersect(a,b,c,d):
		ab=b - a
		cd=d - c
		denominator=cross_2d(ab,cd)
		relative=c - a
		if abs(denominator) <=tolerance:
			if abs(cross_2d(relative,ab)) > tolerance * scale:
				return False
			axis=0 if abs(ab.x) >=abs(ab.y) else 1
			first_min,first_max=sorted((a[axis],b[axis]))
			second_min,second_max=sorted((c[axis],d[axis]))
			return min(first_max,second_max) - max(first_min,second_min) > tolerance
		first_factor=cross_2d(relative,cd) / denominator
		second_factor=cross_2d(relative,ab) / denominator
		return (tolerance < first_factor < 1.0 - tolerance and tolerance < second_factor < 1.0 - tolerance)
	count=len(flat)
	for first_index in range(count):
		first_next=(first_index + 1) % count
		for second_index in range(first_index + 1,count):
			second_next=(second_index + 1) % count
			if (first_index==second_index
				or first_index==second_next
				or first_next==second_index):
				continue
			if segments_intersect(flat[first_index],flat[first_next],
				flat[second_index],flat[second_next],):
				return False
	return True
def surface_voronoi_finalize_generated_loop(records,vertices,target_normal,tolerance=SURFACE_VORONOI_TOLERANCE,minimum_area=0.0,):
	records=surface_voronoi_clean_generated_loop(records)
	if len(records) < 3 or len({record[0] for record in records}) < 3:
		return []
	def has_area(candidate):
		points=[vertices[record[0]] for record in candidate]
		edge_scale=max((points[(index + 1) % len(points)] - point).length
			for index,point in enumerate(points))
		area_threshold=max(float(minimum_area),tolerance * tolerance,tolerance * edge_scale * edge_scale,)
		return surface_voronoi_float32_polygon_area(points) > area_threshold
	if len(records)==3:
		return [records] if has_area(records) else []
	if surface_voronoi_generated_loop_is_safe_quad(records,vertices,
		target_normal,):
		return [records]
	from mathutils.geometry import tessellate_polygon
	parameter_points=[record[3] for record in records]
	triangles=list(tessellate_polygon([parameter_points]))
	triangle_loops=[]
	for triangle in triangles:
		if triangle and isinstance(triangle[0],int):
			positions=list(triangle)
		else:
			positions=[min(range(len(parameter_points)),
					key=lambda index: (parameter_points[index] - point).length_squared,) for point in triangle]
		triangle_records=[records[position] for position in positions]
		triangle_records=surface_voronoi_clean_generated_loop(triangle_records)
		if (len(triangle_records)==3
			and len({record[0] for record in triangle_records})==3):
			if has_area(triangle_records):
				triangle_loops.append(triangle_records)
	def paired_quad(first,second):
		edge_counts={}
		for triangle_loop in (first,second):
			for index,record in enumerate(triangle_loop):
				following=triangle_loop[(index + 1) % 3]
				key=tuple(sorted((record[0],following[0])))
				edge_counts.setdefault(key,[]).append((record,following))
		boundary=[uses[0] for uses in edge_counts.values() if len(uses)==1]
		if len(boundary) !=4:
			return None
		records_by_vertex={record[0]: record for triangle_loop in (first,second) for record in triangle_loop}
		adjacency={}
		for start,end in boundary:
			adjacency.setdefault(start[0],[]).append(end[0])
			adjacency.setdefault(end[0],[]).append(start[0])
		if len(adjacency) !=4 or any(len(items) !=2 for items in adjacency.values()):
			return None
		start=min(adjacency)
		loop_indices=[start]
		previous=None
		current=start
		while len(loop_indices) < 4:
			candidates=[item for item in adjacency[current] if item !=previous]
			if not candidates:
				return None
			following=min(candidates)
			if following in loop_indices:
				return None
			loop_indices.append(following)
			previous,current=current,following
		quad=[records_by_vertex[index] for index in loop_indices]
		if not surface_voronoi_generated_loop_is_safe_quad(quad,vertices,
			target_normal,tolerance,):
			quad.reverse()
			if not surface_voronoi_generated_loop_is_safe_quad(quad,vertices,
				target_normal,tolerance,):
				return None
		return quad
	pair_candidates=[]
	for first_index in range(len(triangle_loops) - 1):
		for second_index in range(first_index + 1,len(triangle_loops)):
			quad=paired_quad(triangle_loops[first_index],triangle_loops[second_index],)
			if quad is None:
				continue
			points=[vertices[record[0]] for record in quad]
			lengths=[(points[(index + 1) % 4] - point).length for index,point in enumerate(points)]
			quality=min(lengths) / max(max(lengths),tolerance)
			pair_candidates.append((-quality,first_index,second_index,quad))
	used=set()
	finalized=[]
	for _score,first_index,second_index,quad in sorted(pair_candidates,
		key=lambda item: item[:3],):
		if first_index in used or second_index in used:
			continue
		used.add(first_index)
		used.add(second_index)
		finalized.append(quad)
	finalized.extend(triangle_loop
		for index,triangle_loop in enumerate(triangle_loops) if index not in used)
	return finalized
def build_surface_voronoi_graph_strip(selected_edges,world_matrix,normal_matrix,face_width,surface_offset,vertices_out,faces_out,face_uvs_out,center_vertices_out,uv_scale=1.0,tolerance=SURFACE_VORONOI_TOLERANCE,face_source_edges_out=None,overlap_clearance=1.0,):
	cells=build_surface_voronoi_cells(selected_edges,world_matrix,normal_matrix,face_width,surface_offset=surface_offset,tolerance=tolerance,overlap_clearance=overlap_clearance,)
	if not cells:
		return 0
	cells=surface_voronoi_merge_chart_fragments(cells,tolerance)
	weld_tolerance=max(float(tolerance) * 8.0,abs(float(face_width)) * 1.0e-6,1.0e-9,)
	surface_weld_tolerance=max(float(tolerance) * 32.0,abs(float(face_width)) * 1.0e-6,1.0e-9,)
	surface_groups=[]
	surface_group_buckets={}
	def surface_group_for(point,create=False):
		key=surface_voronoi_vertex_key(point,surface_weld_tolerance)
		for offset_x in (-1,0,1):
			for offset_y in (-1,0,1):
				for offset_z in (-1,0,1):
					neighbor_key=(key[0] + offset_x,key[1] + offset_y,key[2] + offset_z,)
					for group_index in surface_group_buckets.get(neighbor_key,(),):
						group=surface_groups[group_index]
						if (group["surface_point"] - point).length <=surface_weld_tolerance:
							return group
		if not create:
			return None
		group={"surface_point": point.copy(),"normals": [], "lifted_points": [], "canonical_point": None,}
		group_index=len(surface_groups)
		surface_groups.append(group)
		surface_group_buckets.setdefault(key,[]).append(group_index)
		return group
	for cell in cells:
		for surface_point,lifted_point in zip(cell["surface_polygon"],cell["polygon"],):
			group=surface_group_for(surface_point,create=True)
			normal=safe_normalized(cell["normal"])
			if not any(normal.dot(existing) > 0.999999
				for existing in group["normals"]):
				group["normals"].append(normal)
			group["lifted_points"].append(lifted_point.copy())
	for group in surface_groups:
		if surface_offset <=EPSILON:
			group["canonical_point"]=group["surface_point"].copy()
		elif len(group["normals"]) > 1:
			group["canonical_point"]=offset_point_from_face_normals(group["surface_point"],group["normals"],surface_offset,)
		else:
			group["canonical_point"]=sum(group["lifted_points"],Vector((0.0,0.0,0.0)),) / len(group["lifted_points"])
	def canonical_lifted_point(surface_point,fallback):
		group=surface_group_for(surface_point)
		if group is None or group["canonical_point"] is None:
			return fallback
		return group["canonical_point"]
	vertex_cache={}
	for index,point in enumerate(vertices_out):
		key=surface_voronoi_vertex_key(point,weld_tolerance)
		vertex_cache.setdefault(key,[]).append(index)
	center_vertex_set=set(center_vertices_out)
	emitted_face_keys={tuple(sorted(face)) for face in faces_out}
	created_face_count=0
	def find_or_append_vertex(point):
		key=surface_voronoi_vertex_key(point,weld_tolerance)
		for offset_x in (-1,0,1):
			for offset_y in (-1,0,1):
				for offset_z in (-1,0,1):
					neighbor_key=(key[0] + offset_x,key[1] + offset_y,key[2] + offset_z,)
					for candidate in vertex_cache.get(neighbor_key,()):
						if (vertices_out[candidate] - point).length <=weld_tolerance:
							return candidate
		index=len(vertices_out)
		vertices_out.append(point.copy())
		vertex_cache.setdefault(key,[]).append(index)
		return index
	for cell in cells:
		indices=[]
		center_flags=[]
		site=cell["site"]
		parameter_polygon=cell.get("parameter_polygon",cell["surface_polygon"],)
		for surface_point,lifted_point,parameter_point in zip(cell["surface_polygon"],cell["polygon"],
			parameter_polygon,):
			vertex_index=find_or_append_vertex(canonical_lifted_point(surface_point,lifted_point))
			indices.append(vertex_index)
			signed_distance=(site["inward"].dot(parameter_point) - site["line_offset"])
			longitudinal=(parameter_point - site["start"]).dot(site["tangent"])
			center_flags.append(abs(signed_distance) <=tolerance and -tolerance <=longitudinal <=site["length"] + tolerance)
		uvs=surface_voronoi_cell_uvs(cell,face_width,uv_scale)
		records=list(zip(indices,uvs,center_flags,parameter_polygon,))
		simple_loops=surface_voronoi_split_self_touching_loop(records)
		for simple_loop in simple_loops:
			for final_loop in surface_voronoi_finalize_generated_loop(simple_loop,vertices_out,cell["normal"],tolerance=tolerance,
				minimum_area=(abs(float(face_width)) * 1.0e-4) ** 2,):
				final_indices=tuple(record[0] for record in final_loop)
				final_uvs=tuple(record[1] for record in final_loop)
				final_center_flags=tuple(record[2] for record in final_loop)
				original_indices=final_indices
				final_indices,final_uvs=oriented_face_with_uvs(final_indices,final_uvs,vertices_out,cell["normal"],)
				if final_indices !=original_indices:
					final_center_flags=tuple(reversed(final_center_flags))
				face_key=tuple(sorted(final_indices))
				if face_key in emitted_face_keys:
					continue
				emitted_face_keys.add(face_key)
				faces_out.append(final_indices)
				face_uvs_out.append(final_uvs)
				if face_source_edges_out is not None:
					face_source_edges_out.append(cell["source_edge"])
				for vertex_index,is_center in zip(final_indices,final_center_flags,):
					if is_center and vertex_index not in center_vertex_set:
						center_vertex_set.add(vertex_index)
						center_vertices_out.append(vertex_index)
				created_face_count +=1
	return created_face_count
