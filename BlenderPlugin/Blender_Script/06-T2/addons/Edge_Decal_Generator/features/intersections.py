from ..G import *
"""Generate two-sided decal ribbons where two selected meshes intersect.
Loaded into the add-on package shared namespace by __init__.py.
"""
def _intersection_quantized_vector(vector,tolerance):
	scale=1.0 / max(float(tolerance),1.0e-9)
	return tuple(int(round(component * scale)) for component in vector)
def _intersection_unique_points(points,tolerance):
	unique=[]
	tolerance_squared=tolerance * tolerance
	for point in points:
		if any((point - existing).length_squared <=tolerance_squared for existing in unique):
			continue
		unique.append(point.copy())
	return unique
def _intersection_point_in_triangle(point,triangle,tolerance):
	a,b,c=triangle
	v0=b - a
	v1=c - a
	v2=point - a
	dot00=v0.dot(v0)
	dot01=v0.dot(v1)
	dot11=v1.dot(v1)
	dot20=v2.dot(v0)
	dot21=v2.dot(v1)
	denominator=dot00 * dot11 - dot01 * dot01
	if abs(denominator) <=EPSILON:
		return False
	inverse=1.0 / denominator
	u=(dot11 * dot20 - dot01 * dot21) * inverse
	v=(dot00 * dot21 - dot01 * dot20) * inverse
	barycentric_tolerance=tolerance / max(v0.length,v1.length,(c - b).length,1.0e-8,)
	return (u >=-barycentric_tolerance and v >=-barycentric_tolerance and u + v <=1.0 + barycentric_tolerance)
def _intersection_triangle_plane_points(triangle,other_triangle,plane_point,plane_normal,tolerance,):
	points=[]
	distances=[plane_normal.dot(vertex - plane_point) for vertex in triangle]
	for index in range(3):
		start=triangle[index]
		end=triangle[(index + 1) % 3]
		start_distance=distances[index]
		end_distance=distances[(index + 1) % 3]
		if (abs(start_distance) <=tolerance
			and _intersection_point_in_triangle(start,other_triangle,tolerance)):
			points.append(start.copy())
		if start_distance * end_distance < -(tolerance * tolerance):
			factor=start_distance / (start_distance - end_distance)
			point=start.lerp(end,factor)
			if _intersection_point_in_triangle(point,other_triangle,tolerance):
				points.append(point)
	return points
def intersect_world_triangles(triangle_a,triangle_b,tolerance=1.0e-6):
	normal_a=(triangle_a[1] - triangle_a[0]).cross(triangle_a[2] - triangle_a[0])
	normal_b=(triangle_b[1] - triangle_b[0]).cross(triangle_b[2] - triangle_b[0])
	if normal_a.length_squared <=EPSILON or normal_b.length_squared <=EPSILON:
		return None
	normal_a.normalize()
	normal_b.normalize()
	if abs(normal_a.dot(normal_b)) >=0.999999:
		return None
	points=_intersection_triangle_plane_points(triangle_a,triangle_b,triangle_b[0],normal_b,tolerance,)
	points.extend(_intersection_triangle_plane_points(triangle_b,triangle_a,triangle_a[0],normal_a,tolerance,))
	points=_intersection_unique_points(points,tolerance)
	if len(points) < 2:
		return None
	start=points[0]
	end=points[1]
	longest_squared=(end - start).length_squared
	for first_index,first in enumerate(points):
		for second in points[first_index + 1:]:
			length_squared=(second - first).length_squared
			if length_squared > longest_squared:
				start=first
				end=second
				longest_squared=length_squared
	if longest_squared <=tolerance * tolerance:
		return None
	return start,end,normal_a,normal_b
class _IntersectionSegment:
	"""Four-value segment compatible with the original public test API.
	The supporting triangle indices are deliberately metadata instead of
	additional tuple values.  Existing callers can keep unpacking
	``start,end,normal_a,normal_b`` while the surface-strip builder can
	trace each rail on the evaluated source mesh that produced the segment.
	"""
	__slots__=("start","end","normal_a","normal_b", "triangle_a_index","triangle_b_index",)
	def __init__(self,start,end,normal_a,normal_b,triangle_a_index=None,triangle_b_index=None,):
		self.start=start.copy()
		self.end=end.copy()
		self.normal_a=normal_a.copy()
		self.normal_b=normal_b.copy()
		self.triangle_a_index=triangle_a_index
		self.triangle_b_index=triangle_b_index
	def _public_values(self):
		return (self.start,self.end,self.normal_a,self.normal_b)
	def __iter__(self):
		return iter(self._public_values())
	def __len__(self):
		return 4
	def __getitem__(self,key):
		return self._public_values()[key]
def _evaluated_world_surface(obj,depsgraph,tolerance=1.0e-7):
	evaluated=obj.evaluated_get(depsgraph)
	mesh=evaluated.to_mesh(preserve_all_data_layers=False,depsgraph=depsgraph,)
	try:
		mesh.calc_loop_triangles()
		world_matrix=evaluated.matrix_world
		world_vertices=[world_matrix @ vertex.co for vertex in mesh.vertices]
		triangle_vertex_indices=[tuple(loop_triangle.vertices) for loop_triangle in mesh.loop_triangles]
		triangles=[tuple(world_vertices[index].copy() for index in indices) for indices in triangle_vertex_indices]
	finally:
		evaluated.to_mesh_clear()
	edge_owners={}
	adjacency=[[None,None,None] for _triangle in triangles]
	shared_edges={}
	for triangle_index,indices in enumerate(triangle_vertex_indices):
		for opposite_index in range(3):
			edge=tuple(sorted((indices[(opposite_index + 1) % 3],indices[(opposite_index + 2) % 3],)))
			previous=edge_owners.get(edge)
			if previous is None:
				edge_owners[edge]=(triangle_index,opposite_index)
				continue
			previous_triangle,previous_opposite=previous
			adjacency[triangle_index][opposite_index]=previous_triangle
			adjacency[previous_triangle][previous_opposite]=triangle_index
			world_edge=(world_vertices[edge[0]].copy(),world_vertices[edge[1]].copy(),)
			shared_edges[(triangle_index,previous_triangle)]=world_edge
			shared_edges[(previous_triangle,triangle_index)]=world_edge
	normals=[]
	for triangle in triangles:
		normal=(triangle[1] - triangle[0]).cross(triangle[2] - triangle[0])
		normals.append(safe_normalized(normal,Vector((0.0,0.0,1.0))))
	bvh=BVHTree.FromPolygons([vertex for triangle in triangles for vertex in triangle],[tuple(range(index * 3,index * 3 + 3)) for index in range(len(triangles))],all_triangles=True,epsilon=tolerance,) if triangles else None
	return {"triangles": triangles,"normals": normals, "adjacency": adjacency,"shared_edges": shared_edges, "bvh": bvh,}
def _evaluated_world_triangles(obj,depsgraph):
	return _evaluated_world_surface(obj,depsgraph)["triangles"]
def _intersection_append_evaluated_bmesh(target_bmesh,obj,depsgraph,source_id):
	evaluated=obj.evaluated_get(depsgraph)
	mesh=evaluated.to_mesh(preserve_all_data_layers=False,depsgraph=depsgraph,)
	source_bmesh=bmesh.new()
	try:
		source_bmesh.from_mesh(mesh)
		source_bmesh.transform(evaluated.matrix_world)
		vertex_map={vertex: target_bmesh.verts.new(vertex.co) for vertex in source_bmesh.verts}
		for face in source_bmesh.faces:
			try:
				new_face=target_bmesh.faces.new(tuple(vertex_map[vertex] for vertex in face.verts))
			except ValueError:
				continue
			new_face.material_index=source_id
			new_face.select=source_id==0
	finally:
		source_bmesh.free()
		evaluated.to_mesh_clear()
def _exact_intersection_segments(obj_a,obj_b,depsgraph,surface_a,surface_b,tolerance,):
	context=bpy.context
	if context.mode != "OBJECT":
		return []
	view_layer=context.view_layer
	active_before=view_layer.objects.active
	selected_before=list(context.selected_objects)
	select_mode_before=tuple(context.tool_settings.mesh_select_mode)
	temporary_mesh=None
	temporary_object=None
	try:
		combined=bmesh.new()
		try:
			_intersection_append_evaluated_bmesh(combined,obj_a,depsgraph,0,)
			_intersection_append_evaluated_bmesh(combined,obj_b,depsgraph,1,)
			if not combined.faces:
				return []
			temporary_mesh=bpy.data.meshes.new("_EdgeDecalExactIntersection")
			combined.to_mesh(temporary_mesh)
		finally:
			combined.free()
		temporary_object=bpy.data.objects.new("_EdgeDecalExactIntersection",temporary_mesh,)
		context.scene.collection.objects.link(temporary_object)
		for selected_object in list(context.selected_objects):
			selected_object.select_set(False)
		temporary_object.select_set(True)
		view_layer.objects.active=temporary_object
		bpy.ops.object.mode_set(mode="EDIT")
		context.tool_settings.mesh_select_mode=(False,False,True)
		result=bpy.ops.mesh.intersect(mode="SELECT_UNSELECT",separate_mode="NONE",threshold=max(float(tolerance),1.0e-7),solver="EXACT",)
		if "FINISHED" not in result:
			return []
		edit_bmesh=bmesh.from_edit_mesh(temporary_mesh)
		edit_bmesh.normal_update()
		segments=[]
		for edge in edit_bmesh.edges:
			source_ids={face.material_index for face in edge.link_faces}
			if source_ids !={0,1}:
				continue
			start=edge.verts[0].co.copy()
			end=edge.verts[1].co.copy()
			if (end - start).length <=tolerance:
				continue
			normals_a=[face.normal for face in edge.link_faces if face.material_index==0]
			normals_b=[face.normal for face in edge.link_faces if face.material_index==1]
			if not normals_a or not normals_b:
				continue
			normal_a=safe_normalized(sum(normals_a,Vector((0.0,0.0,0.0)),))
			normal_b=safe_normalized(sum(normals_b,Vector((0.0,0.0,0.0)),))
			midpoint=(start + end) * 0.5
			nearest_a=surface_a["bvh"].find_nearest(midpoint)
			nearest_b=surface_b["bvh"].find_nearest(midpoint)
			triangle_a_index=nearest_a[2] if nearest_a is not None else None
			triangle_b_index=nearest_b[2] if nearest_b is not None else None
			segments.append(_IntersectionSegment(start,end,normal_a,normal_b,triangle_a_index,triangle_b_index,))
		return segments
	except (RuntimeError,ValueError,TypeError):
		return []
	finally:
		if temporary_object is not None:
			try:
				if temporary_object.mode != "OBJECT":
					bpy.ops.object.mode_set(mode="OBJECT")
			except RuntimeError:
				pass
			bpy.data.objects.remove(temporary_object,do_unlink=True)
		if temporary_mesh is not None and temporary_mesh.users==0:
			bpy.data.meshes.remove(temporary_mesh)
		for selected_object in list(context.selected_objects):
			selected_object.select_set(False)
		for selected_object in selected_before:
			if selected_object.name_full in bpy.data.objects:
				selected_object.select_set(True)
		context.tool_settings.mesh_select_mode=select_mode_before
		if active_before is not None and active_before.name_full in bpy.data.objects:
			view_layer.objects.active=active_before
def mesh_intersection_data(obj_a,obj_b,depsgraph,tolerance=1.0e-6):
	surface_a=_evaluated_world_surface(obj_a,depsgraph,tolerance)
	surface_b=_evaluated_world_surface(obj_b,depsgraph,tolerance)
	triangles_a=surface_a["triangles"]
	triangles_b=surface_b["triangles"]
	if not triangles_a or not triangles_b:
		return [],surface_a,surface_b
	exact_segments=_exact_intersection_segments(obj_a,obj_b,depsgraph,surface_a,surface_b,tolerance,)
	if exact_segments:
		return exact_segments,surface_a,surface_b
	bvh_a=BVHTree.FromPolygons([vertex for triangle in triangles_a for vertex in triangle],[tuple(range(index * 3,index * 3 + 3)) for index in range(len(triangles_a))],all_triangles=True,epsilon=tolerance,)
	bvh_b=BVHTree.FromPolygons([vertex for triangle in triangles_b for vertex in triangle],[tuple(range(index * 3,index * 3 + 3)) for index in range(len(triangles_b))],all_triangles=True,epsilon=tolerance,)
	unique={}
	for triangle_a_index,triangle_b_index in bvh_a.overlap(bvh_b):
		segment=intersect_world_triangles(triangles_a[triangle_a_index],triangles_b[triangle_b_index],tolerance,)
		if segment is None:
			continue
		start,end,normal_a,normal_b=segment
		start_key=_intersection_quantized_vector(start,tolerance)
		end_key=_intersection_quantized_vector(end,tolerance)
		if end_key < start_key:
			start,end=end,start
			start_key,end_key=end_key,start_key
		key=(start_key,end_key)
		candidate=_IntersectionSegment(start,end,normal_a,normal_b,triangle_a_index,triangle_b_index,)
		previous=unique.get(key)
		if previous is None:
			unique[key]=candidate
			continue
		previous_score=previous.normal_a.cross(previous.normal_b).length_squared
		candidate_score=normal_a.cross(normal_b).length_squared
		if candidate_score > previous_score + 1.0e-10:
			unique[key]=candidate
	return list(unique.values()),surface_a,surface_b
def mesh_intersection_segments(obj_a,obj_b,depsgraph,tolerance=1.0e-6):
	segments,_surface_a,_surface_b=mesh_intersection_data(obj_a,obj_b,depsgraph,tolerance=tolerance,)
	return segments
def _intersection_direction_clusters(directions,minimum_dot=0.7):
	clusters=[]
	for direction in directions:
		candidate=safe_normalized(direction)
		matching=next((cluster
				for cluster in clusters
				if safe_normalized(cluster["sum"]).dot(candidate) >=minimum_dot),None,)
		if matching is None:
			clusters.append({"sum": candidate.copy(), "count": 1})
		else:
			matching["sum"] +=candidate
			matching["count"] +=1
	return [safe_normalized(cluster["sum"]) for cluster in clusters]
def _intersection_triangle_pair_score(points,first,second):
	normal_a=(points[first[1]] - points[first[0]]).cross(points[first[2]] - points[first[0]])
	normal_b=(points[second[1]] - points[second[0]]).cross(points[second[2]] - points[second[0]])
	if (normal_a.length_squared <=EPSILON
		or normal_b.length_squared <=EPSILON):
		return -1.0
	return normal_a.normalized().dot(normal_b.normalized())
def _intersection_oriented_face_parts(indices,uvs,vertices,target_normal,):
	points=[vertices[index] for index in indices]
	default_score=_intersection_triangle_pair_score(points,(0,1,2),(0,2,3),)
	alternate_score=_intersection_triangle_pair_score(points,(0,1,3),(1,2,3),)
	if default_score >=-1.0e-6 or alternate_score <=default_score:
		return (oriented_face_with_uvs(indices,uvs,vertices,target_normal,),)
	parts=[]
	for corners in ((0,1,3),(1,2,3)):
		parts.append(oriented_face_with_uvs(tuple(indices[index] for index in corners),tuple(uvs[index] for index in corners),vertices,target_normal,))
	return tuple(parts)
def _intersection_triangle_barycentric(point,triangle):
	a,b,c=triangle
	edge_ab=b - a
	edge_ac=c - a
	relative=point - a
	dot_ab_ab=edge_ab.dot(edge_ab)
	dot_ab_ac=edge_ab.dot(edge_ac)
	dot_ac_ac=edge_ac.dot(edge_ac)
	dot_relative_ab=relative.dot(edge_ab)
	dot_relative_ac=relative.dot(edge_ac)
	denominator=dot_ab_ab * dot_ac_ac - dot_ab_ac * dot_ab_ac
	if abs(denominator) <=EPSILON:
		return None
	coordinate_b=(dot_ac_ac * dot_relative_ab - dot_ab_ac * dot_relative_ac) / denominator
	coordinate_c=(dot_ab_ab * dot_relative_ac - dot_ab_ac * dot_relative_ab) / denominator
	return (1.0 - coordinate_b - coordinate_c,coordinate_b,coordinate_c)
def _intersection_rotate_across_edge(direction,old_normal,new_normal,edge):
	edge_axis=safe_normalized(edge[1] - edge[0])
	sine=edge_axis.dot(old_normal.cross(new_normal))
	cosine=max(-1.0,min(1.0,old_normal.dot(new_normal)))
	angle=atan2(sine,cosine)
	rotated=Matrix.Rotation(angle,3,edge_axis) @ direction
	rotated -=new_normal * rotated.dot(new_normal)
	return safe_normalized(rotated,direction)
def _intersection_walk_surface(surface,start,direction,distance,triangle_index,tolerance,):
	if (surface is None
		or triangle_index is None
		or triangle_index < 0
		or triangle_index >=len(surface["triangles"])):
		return start + safe_normalized(direction) * distance,None,triangle_index
	current=start.copy()
	current_triangle=triangle_index
	previous_triangle=None
	remaining=max(0.0,float(distance))
	tangent=safe_normalized(direction)
	barycentric_tolerance=max(tolerance * 4.0,1.0e-8)
	for _step in range(128):
		triangle=surface["triangles"][current_triangle]
		normal=surface["normals"][current_triangle]
		current -=normal * normal.dot(current - triangle[0])
		tangent -=normal * tangent.dot(normal)
		tangent=safe_normalized(tangent)
		if remaining <=tolerance:
			return current,normal,current_triangle
		target=current + tangent * remaining
		current_barycentric=_intersection_triangle_barycentric(current,triangle)
		target_barycentric=_intersection_triangle_barycentric(target,triangle)
		if current_barycentric is None or target_barycentric is None:
			break
		if min(target_barycentric) >=-barycentric_tolerance:
			return target,normal,current_triangle
		crossings=[]
		for opposite_index,(start_weight,end_weight) in enumerate(zip(current_barycentric,target_barycentric,)):
			if end_weight >=-barycentric_tolerance:
				continue
			denominator=start_weight - end_weight
			if denominator <=EPSILON:
				continue
			factor=start_weight / denominator
			if factor >=-barycentric_tolerance and factor <=1.0 + barycentric_tolerance:
				crossings.append((max(0.0,min(1.0,factor)),opposite_index))
		if not crossings:
			break
		crossings.sort(key=lambda item: item[0])
		chosen=None
		for factor,opposite_index in crossings:
			neighbor=surface["adjacency"][current_triangle][opposite_index]
			if neighbor is None or neighbor==previous_triangle:
				continue
			chosen=(factor,opposite_index,neighbor)
			break
		if chosen is None:
			factor,opposite_index=crossings[0]
			neighbor=surface["adjacency"][current_triangle][opposite_index]
			if neighbor is None:
				boundary_point=current.lerp(target,factor)
				return boundary_point,normal,current_triangle
			chosen=(factor,opposite_index,neighbor)
		factor,_opposite_index,neighbor=chosen
		crossing_point=current.lerp(target,factor)
		edge=surface["shared_edges"].get((current_triangle,neighbor))
		if edge is None:
			break
		next_normal=surface["normals"][neighbor]
		tangent=_intersection_rotate_across_edge(tangent,normal,next_normal,edge,)
		travelled=remaining * factor
		remaining=max(0.0,remaining - travelled)
		previous_triangle,current_triangle=current_triangle,neighbor
		current=crossing_point
	bvh=surface.get("bvh") if surface is not None else None
	nearest=bvh.find_nearest(current + tangent * remaining) if bvh else None
	if nearest is not None:
		location,normal,nearest_triangle,_distance=nearest
		return location.copy(),safe_normalized(normal),nearest_triangle
	return current,None,current_triangle
def _intersection_project_to_surface(surface,point,surface_offset=0.0):
	bvh=surface.get("bvh") if surface is not None else None
	nearest=bvh.find_nearest(point) if bvh else None
	if nearest is None:
		return point.copy(),None,None
	location,normal,triangle_index,_distance=nearest
	normal=safe_normalized(normal)
	return location + normal * surface_offset,normal,triangle_index
def _intersection_hard_join_edge_point(surface,triangle_a_index,triangle_b_index,point_a,point_b,):
	if surface is None or triangle_a_index is None or triangle_b_index is None:
		return None
	edge=surface["shared_edges"].get((triangle_a_index,triangle_b_index))
	if edge is None:
		return None
	edge_direction=safe_normalized(edge[1] - edge[0])
	normal_a=surface["normals"][triangle_a_index]
	normal_b=surface["normals"][triangle_b_index]
	sine=edge_direction.dot(normal_b.cross(normal_a))
	cosine=max(-1.0,min(1.0,normal_b.dot(normal_a)))
	unfold_angle=atan2(sine,cosine)
	point_b_unfolded=(edge[0]
		+ Matrix.Rotation(unfold_angle,3,edge_direction) @ (point_b - edge[0]))
	edge_perpendicular=safe_normalized(normal_a.cross(edge_direction))
	distance_a=(point_a - edge[0]).dot(edge_perpendicular)
	distance_b=(point_b_unfolded - edge[0]).dot(edge_perpendicular)
	denominator=distance_a - distance_b
	if abs(denominator) > 1.0e-8:
		factor=distance_a / denominator
		crossing=point_a.lerp(point_b_unfolded,factor)
	else:
		crossing=(point_a + point_b_unfolded) * 0.5
	edge_length=(edge[1] - edge[0]).length
	edge_factor=(crossing - edge[0]).dot(edge_direction)
	edge_factor=max(0.0,min(edge_length,edge_factor))
	return edge[0] + edge_direction * edge_factor
def _intersection_project_miter_to_shared_edge(surface,triangle_a_index,triangle_b_index,candidate,):
	if surface is None or triangle_a_index is None or triangle_b_index is None:
		return None
	edge=surface["shared_edges"].get((triangle_a_index,triangle_b_index))
	if edge is None:
		return None
	edge_vector=edge[1] - edge[0]
	edge_length_squared=edge_vector.length_squared
	if edge_length_squared <=EPSILON:
		return None
	factor=(candidate - edge[0]).dot(edge_vector) / edge_length_squared
	factor=max(0.0,min(1.0,factor))
	return edge[0].lerp(edge[1],factor)
def _intersection_surface_miter_is_valid(origin,candidate,sides,normals,face_width,maximum_distance,tolerance,minimum_width_ratio=0.55,maximum_plane_error_ratio=0.025,):
	displacement=candidate - origin
	distance=displacement.length
	if distance <=tolerance or distance > maximum_distance * 1.05:
		return False
	minimum_width=face_width * minimum_width_ratio
	maximum_width=face_width * 1.55
	maximum_plane_error=max(tolerance * 8.0,face_width * maximum_plane_error_ratio,)
	for side,normal in zip(sides,normals):
		measured_width=displacement.dot(side)
		if measured_width < minimum_width or measured_width > maximum_width:
			return False
		if abs(displacement.dot(normal)) > maximum_plane_error:
			return False
	return True
def build_intersection_decal_mesh(segments,face_width,surface_offset,uv_scale,miter_limit=4.0,seam_edges_out=None,surface_a=None,surface_b=None,):
	vertices=[]
	faces=[]
	face_uvs=[]
	center_vertices=set()
	segment_points=[point
		for segment in segments
		for point in segment[:2]]
	if segment_points:
		span=max(max(point[axis] for point in segment_points)
			- min(point[axis] for point in segment_points)
			for axis in range(3))
		coordinate_scale=max(abs(component) for point in segment_points for component in point)
	else:
		span=0.0
		coordinate_scale=0.0
	vertex_tolerance=max(face_width * 1.0e-4,span * 1.0e-6,coordinate_scale * 1.0e-9,1.0e-7,)
	def append_vertex(point,is_center=False):
		index=len(vertices)
		vertices.append(point.copy())
		if is_center:
			center_vertices.add(index)
		return index
	graph_nodes={}
	node_buckets={}
	next_node_key=0
	def graph_node_key(point):
		nonlocal next_node_key
		bucket=tuple(int(component // vertex_tolerance) for component in point)
		for offset_x in (-1,0,1):
			for offset_y in (-1,0,1):
				for offset_z in (-1,0,1):
					nearby_bucket=(bucket[0] + offset_x,bucket[1] + offset_y,bucket[2] + offset_z,)
					for candidate_key in node_buckets.get(nearby_bucket,()):
						node=graph_nodes[candidate_key]
						if not node["points"]:
							continue
						representative=node["point_sum"] / len(node["points"])
						if (point - representative).length <=vertex_tolerance:
							return candidate_key
		node_key=next_node_key
		next_node_key +=1
		graph_nodes[node_key]={"points": [],"point_sum": Vector((0.0,0.0,0.0)), "incidents": [],}
		node_buckets.setdefault(bucket,[]).append(node_key)
		return node_key
	prepared_segments=[]
	for source_segment in segments:
		start,end,normal_a,normal_b=source_segment
		tangent=end - start
		length=tangent.length
		if length <=vertex_tolerance:
			continue
		tangent.normalize()
		side_a=normal_b - normal_a * normal_a.dot(normal_b)
		side_b=normal_a - normal_b * normal_b.dot(normal_a)
		if side_a.length_squared <=EPSILON or side_b.length_squared <=EPSILON:
			continue
		side_a.normalize()
		side_b.normalize()
		start_key=graph_node_key(start)
		end_key=graph_node_key(end)
		if start_key==end_key:
			continue
		segment_index=len(prepared_segments)
		prepared_segments.append({"start": start.copy(),"end": end.copy(),"start_key": start_key,"end_key": end_key,"length": length,"normal_a": normal_a.copy(),"normal_b": normal_b.copy(),"side_a": side_a,"side_b": side_b,"triangle_a_index": getattr(source_segment,"triangle_a_index",
				None,),"triangle_b_index": getattr(source_segment,"triangle_b_index",None,),})
		graph_nodes[start_key]["points"].append(start.copy())
		graph_nodes[end_key]["points"].append(end.copy())
		graph_nodes[start_key]["point_sum"] +=start
		graph_nodes[end_key]["point_sum"] +=end
		graph_nodes[start_key]["incidents"].append((segment_index, "start"))
		graph_nodes[end_key]["incidents"].append((segment_index, "end"))
	healing_distance=max(vertex_tolerance * 12.0,face_width * 0.01,span * 2.0e-6,)
	open_node_keys=[node_key
		for node_key,node in graph_nodes.items()
		if len(node["incidents"])==1]
	consumed_open_nodes=set()
	for node_key in open_node_keys:
		if node_key in consumed_open_nodes or node_key not in graph_nodes:
			continue
		node=graph_nodes[node_key]
		origin=node["point_sum"] / len(node["points"])
		best_match=None
		best_distance=healing_distance
		for candidate_key in open_node_keys:
			if (candidate_key==node_key
				or candidate_key in consumed_open_nodes
				or candidate_key not in graph_nodes):
				continue
			candidate=graph_nodes[candidate_key]
			candidate_origin=candidate["point_sum"] / len(candidate["points"])
			distance=(candidate_origin - origin).length
			if distance >=best_distance:
				continue
			best_match=candidate_key
			best_distance=distance
		if best_match is None:
			continue
		candidate=graph_nodes[best_match]
		for candidate_segment_index,candidate_endpoint in candidate["incidents"]:
			prepared_segments[candidate_segment_index][f"{candidate_endpoint}_key"]=node_key
		node["points"].extend(candidate["points"])
		node["point_sum"] +=candidate["point_sum"]
		node["incidents"].extend(candidate["incidents"])
		del graph_nodes[best_match]
		consumed_open_nodes.add(node_key)
		consumed_open_nodes.add(best_match)
	center_by_node={}
	outer_by_node_incident_slot={}
	bevel_join_specs=[]
	closed_component_seam_nodes=[]
	unvisited_nodes=set(graph_nodes)
	while unvisited_nodes:
		start_node=unvisited_nodes.pop()
		component_nodes={start_node}
		pending_nodes=[start_node]
		while pending_nodes:
			current_node=pending_nodes.pop()
			for segment_index,endpoint in graph_nodes[current_node]["incidents"]:
				segment=prepared_segments[segment_index]
				neighbor=segment["end_key" if endpoint== "start" else "start_key"]
				if neighbor in unvisited_nodes:
					unvisited_nodes.remove(neighbor)
					component_nodes.add(neighbor)
					pending_nodes.append(neighbor)
		if component_nodes and all(len(graph_nodes[node_key]["incidents"])==2
			for node_key in component_nodes):
			closed_component_seam_nodes.append(min(component_nodes,
					key=lambda node_key: tuple(graph_nodes[node_key]["point_sum"]
						/ len(graph_nodes[node_key]["points"])),) 	)
	maximum_miter_distance=max(face_width,face_width * min(max(1.0,float(miter_limit)),1.5),)
	for node_key,node in graph_nodes.items():
		origin=sum(node["points"],Vector((0.0,0.0,0.0))) / len(node["points"])
		normals_a=[]
		normals_b=[]
		for segment_index,_endpoint in node["incidents"]:
			segment=prepared_segments[segment_index]
			normals_a.append(segment["normal_a"])
			normals_b.append(segment["normal_b"])
		all_normals=(_intersection_direction_clusters(normals_a)
			+ _intersection_direction_clusters(normals_b))
		center_point=offset_point_from_face_normals(origin,all_normals,surface_offset,)
		center_by_node[node_key]=append_vertex(center_point,is_center=True)
		for slot in ("a", "b"):
			rail_group=[(segment_index,endpoint,slot)
				for segment_index,endpoint in node["incidents"]]
			normals=[prepared_segments[segment_index][f"normal_{slot}"] for segment_index,_endpoint,slot in rail_group]
			sides=[prepared_segments[segment_index][f"side_{slot}"] for segment_index,_endpoint,slot in rail_group]
			normal_clusters=_intersection_direction_clusters(normals)
			side_clusters=_intersection_direction_clusters(sides)
			owned_surface=surface_a if slot== "a" else surface_b
			averaged_side=safe_normalized(sum(side_clusters,Vector((0.0,0.0,0.0))),side_clusters[0],)
			alignments=[averaged_side.dot(side) for side in sides]
			weakest_alignment=min(alignments,default=1.0)
			requested_miter_distance=(face_width / weakest_alignment
				if weakest_alignment > 1.0e-4
				else float("inf"))
			hard_normal_transition=(owned_surface is not None
				and
				len(normals)==2
				and normals[0].dot(normals[1]) < 0.85)
			miter_distance=min(requested_miter_distance,maximum_miter_distance,)
			free_outer_point=origin + averaged_side * miter_distance
			hard_edge_miter=None
			hard_edge_candidate=None
			capped_surface_miter=None
			capped_surface_normal=None
			if hard_normal_transition:
				first_segment=prepared_segments[rail_group[0][0]]
				second_segment=prepared_segments[rail_group[1][0]]
				hard_edge_candidate=_intersection_project_miter_to_shared_edge(owned_surface,first_segment[f"triangle_{slot}_index"],second_segment[f"triangle_{slot}_index"],free_outer_point,)
				if (hard_edge_candidate is not None
					and _intersection_surface_miter_is_valid(origin,hard_edge_candidate,sides,normals,face_width,maximum_miter_distance,
						vertex_tolerance,)):
					hard_edge_miter=hard_edge_candidate
			if (requested_miter_distance > maximum_miter_distance
				and hard_edge_miter is None
				and owned_surface is not None):
				(capped_candidate,capped_normal,_capped_triangle,)=_intersection_project_to_surface(owned_surface,free_outer_point,0.0,)
				if _intersection_surface_miter_is_valid(origin,capped_candidate,sides,normals,face_width,maximum_miter_distance,vertex_tolerance,minimum_width_ratio=0.12,
					maximum_plane_error_ratio=0.12,):
					capped_surface_miter=capped_candidate
					capped_surface_normal=capped_normal
			if (len(rail_group)==2
				and owned_surface is not None
				and hard_edge_miter is None
				and capped_surface_miter is None):
				if hard_edge_candidate is not None:
					capped_surface_miter=hard_edge_candidate
					capped_surface_normal=safe_normalized(sum(normals,Vector((0.0,0.0,0.0)),))
				else:
					(capped_surface_miter,capped_surface_normal,_capped_triangle,)=_intersection_project_to_surface(owned_surface,free_outer_point,0.0,)
			use_surface_join=(len(rail_group)==2
				and ((requested_miter_distance > maximum_miter_distance and hard_edge_miter is None and capped_surface_miter is None)
					or (hard_normal_transition and hard_edge_miter is None and capped_surface_miter is None)))
			if not use_surface_join:
				if hard_edge_miter is not None:
					outer_point=offset_point_from_face_normals(hard_edge_miter,normals,surface_offset,)
				elif capped_surface_miter is not None:
					outer_point=(capped_surface_miter
						+ safe_normalized(capped_surface_normal) * surface_offset)
				elif owned_surface is not None:
					outer_point,_outer_normal,_triangle_index=(_intersection_project_to_surface(owned_surface,free_outer_point,surface_offset,))
				else:
					outer_point=offset_point_from_face_normals(free_outer_point,normal_clusters,surface_offset,)
				outer_index=append_vertex(outer_point)
				for segment_index,_endpoint,group_slot in rail_group:
					outer_by_node_incident_slot[(node_key,segment_index,group_slot)]=outer_index
				continue
			join_outer_indices=[]
			join_normals=[]
			join_triangle_indices=[]
			join_surface_points=[]
			for segment_index,_endpoint,group_slot in rail_group:
				segment=prepared_segments[segment_index]
				normal=segment[f"normal_{group_slot}"]
				side=segment[f"side_{group_slot}"]
				triangle_index=segment[f"triangle_{group_slot}_index"]
				if owned_surface is not None and triangle_index is not None:
					surface_point,traced_normal,traced_triangle=(_intersection_walk_surface(owned_surface,origin,side,face_width,triangle_index,vertex_tolerance,))
					resolved_normal=traced_normal or normal
					outer_point=surface_point + resolved_normal * surface_offset
					join_surface_points.append(surface_point)
					join_triangle_indices.append(traced_triangle)
					join_normals.append(resolved_normal)
				else:
					surface_point=origin + side * face_width
					outer_point=offset_point_from_face_normals(surface_point,(normal,),surface_offset,)
					join_surface_points.append(surface_point)
					join_triangle_indices.append(triangle_index)
					join_normals.append(normal)
				outer_index=append_vertex(outer_point)
				outer_by_node_incident_slot[(node_key,segment_index,group_slot)]=outer_index
				join_outer_indices.append(outer_index)
			if (len(join_outer_indices)==2
				and (vertices[join_outer_indices[0]]
					- vertices[join_outer_indices[1]]).length <=max(vertex_tolerance * 4.0,face_width * 1.0e-4)):
				shared_outer_index=join_outer_indices[0]
				second_segment_index,_second_endpoint,second_slot=rail_group[1]
				outer_by_node_incident_slot[(node_key,second_segment_index,second_slot)]=shared_outer_index
				if join_outer_indices[1]==len(vertices) - 1:
					vertices.pop()
				join_outer_indices=[shared_outer_index]
			if len(join_outer_indices)==2:
				edge_point=_intersection_hard_join_edge_point(owned_surface,join_triangle_indices[0],join_triangle_indices[1],join_surface_points[0],join_surface_points[1],)
				if (edge_point is not None
					and (edge_point - origin).length > vertex_tolerance
					and all((edge_point - point).length > vertex_tolerance for point in join_surface_points)):
					edge_outer_point=offset_point_from_face_normals(edge_point,join_normals,surface_offset,)
					edge_outer_index=append_vertex(edge_outer_point)
					join_outer_indices.insert(1,edge_outer_index)
			minimum_join_area=max(vertex_tolerance * vertex_tolerance,face_width * face_width * 1.0e-6,)
			if len(join_outer_indices)==3:
				center_index=center_by_node[node_key]
				first_area=(vertices[join_outer_indices[0]] - vertices[center_index]).cross(vertices[join_outer_indices[1]] - vertices[center_index]).length
				second_area=(vertices[join_outer_indices[1]] - vertices[center_index]).cross(vertices[join_outer_indices[2]] - vertices[center_index]).length
				if first_area <=minimum_join_area:
					first_segment_index,_first_endpoint,first_slot=rail_group[0]
					outer_by_node_incident_slot[(node_key,first_segment_index,first_slot)]=join_outer_indices[1]
					join_outer_indices.pop(0)
				if (len(join_outer_indices)==3
					and second_area <=minimum_join_area):
					second_segment_index,_second_endpoint,second_slot=rail_group[1]
					outer_by_node_incident_slot[(node_key,second_segment_index,second_slot)]=join_outer_indices[1]
					join_outer_indices.pop()
			if len(join_outer_indices)==2:
				first_outer_index,second_outer_index=join_outer_indices
				join_area=(vertices[first_outer_index]
					- vertices[center_by_node[node_key]]).cross(vertices[second_outer_index]
					- vertices[center_by_node[node_key]]).length
				if join_area <=minimum_join_area:
					fallback_surface_point=hard_edge_candidate
					fallback_normal=safe_normalized(sum(join_normals,Vector((0.0,0.0,0.0)),))
					if fallback_surface_point is None and owned_surface is not None:
						(fallback_surface_point,fallback_normal,_fallback_triangle,)=_intersection_project_to_surface(owned_surface,free_outer_point,0.0,)
					if fallback_surface_point is not None:
						vertices[first_outer_index]=(fallback_surface_point + fallback_normal * surface_offset)
						second_segment_index,_second_endpoint,second_slot=(rail_group[1])
						outer_by_node_incident_slot[(node_key,second_segment_index,second_slot)]=first_outer_index
						if second_outer_index==len(vertices) - 1:
							vertices.pop()
						join_outer_indices=[first_outer_index]
			if len(join_outer_indices) >=2:
				bevel_join_specs.append({"center": center_by_node[node_key],"outer_chain": tuple(join_outer_indices),"normals": tuple(join_normals), "slot": slot,})
	if seam_edges_out is not None:
		for node_key in closed_component_seam_nodes:
			center_index=center_by_node[node_key]
			segment_index=graph_nodes[node_key]["incidents"][0][0]
			for slot in ("a", "b"):
				seam_edges_out.append((center_index,outer_by_node_incident_slot[(node_key,segment_index,slot)],))
	for segment_index,segment in enumerate(prepared_segments):
		start=segment["start"]
		end=segment["end"]
		length=segment["length"]
		center_start_index=center_by_node[segment["start_key"]]
		center_end_index=center_by_node[segment["end_key"]]
		u_length=max(length * max(float(uv_scale),1.0e-8),1.0e-8)
		for side_index,slot in enumerate(("a", "b")):
			normal=segment[f"normal_{slot}"]
			outer_start_index=outer_by_node_incident_slot[(segment["start_key"],segment_index,slot)]
			outer_end_index=outer_by_node_incident_slot[(segment["end_key"],segment_index,slot)]
			outer_v=0.0 if side_index==0 else 1.0
			face_parts=_intersection_oriented_face_parts((center_start_index,center_end_index,outer_end_index,outer_start_index,),((0.0,0.5),(u_length,0.5),(u_length,outer_v),(0.0,outer_v),),vertices,normal,)
			for indices,uvs in face_parts:
				faces.append(indices)
				face_uvs.append(uvs)
	for join_spec in bevel_join_specs:
		center_index=join_spec["center"]
		outer_chain=join_spec["outer_chain"]
		normals=join_spec["normals"]
		slot=join_spec["slot"]
		if len(outer_chain) < 2:
			continue
		outer_v=0.0 if slot== "a" else 1.0
		for chain_index,(first_outer,second_outer) in enumerate(zip(outer_chain,
			outer_chain[1:],)):
			triangle_normal=(vertices[first_outer] - vertices[center_index]).cross(vertices[second_outer] - vertices[center_index] 	)
			if triangle_normal.length_squared <=EPSILON:
				continue
			if len(outer_chain)==3 and len(normals)==2:
				target_normal=normals[min(chain_index,1)]
			else:
				target_normal=safe_normalized(sum(normals,Vector((0.0,0.0,0.0))),triangle_normal,)
			u_start=(chain_index
				* max(face_width * float(uv_scale),1.0e-8))
			u_end=((chain_index + 1)
				* max(face_width * float(uv_scale),1.0e-8))
			indices,uvs=oriented_face_with_uvs((center_index,first_outer,second_outer),((0.0,0.5),(u_start,outer_v),(u_end,outer_v),),vertices,target_normal,)
			faces.append(indices)
			face_uvs.append(uvs)
	used_vertex_indices=sorted({vertex_index for face in faces for vertex_index in face})
	if len(used_vertex_indices) !=len(vertices):
		compact_index={old_index: new_index for new_index,old_index in enumerate(used_vertex_indices)}
		vertices=[vertices[index] for index in used_vertex_indices]
		faces=[tuple(compact_index[index] for index in face) for face in faces]
		center_vertices={compact_index[index] for index in center_vertices if index in compact_index}
		if seam_edges_out is not None:
			seam_edges_out[:]=[(compact_index[first],compact_index[second])
				for first,second in seam_edges_out
				if (first in compact_index
					and second in compact_index
					and compact_index[first] !=compact_index[second]) 	]
	return vertices,faces,face_uvs,sorted(center_vertices)
def _mark_intersection_decal_seams(mesh,seam_edges):
	seam_keys={frozenset(edge) for edge in seam_edges}
	marked=0
	for edge in mesh.edges:
		edge.use_seam=frozenset(edge.vertices) in seam_keys
		if edge.use_seam:
			marked +=1
	mesh.update()
	return marked
def process_intersection_decal_uvs(context,source_obj,decal_obj,layer_settings,):
	scene_settings=context.scene.edge_decal_settings
	fast_geometry_only=bool(scene_settings.fast_geometry_only)
	use_auto_uv_pins=bool(scene_settings.auto_use_uv_pins and not fast_geometry_only)
	pins=uv_pins_for_decal_layer_material(context.scene,decal_obj,fallback_material=((layer_settings.decal_material
				or scene_settings.decal_material
				or bpy.data.materials.get(DEFAULT_MATERIAL_NAME)) if scene_settings.use_material else None),)
	force_full_uv_for_pins=bool(use_auto_uv_pins and pins)
	quadrify_result= "DISABLED"
	processed_islands=0
	measured_density=0.0
	pinned_islands=0
	if ((scene_settings.auto_unwrap_uvs or force_full_uv_for_pins)
		and not fast_geometry_only):
		(quadrify_result,processed_islands,measured_density,)=unwrap_generated_decal(context,source_obj,decal_obj,scene_settings.use_integrated_quadrify,scene_settings.integrated_quadrify_average_shape,scene_settings.integrated_quadrify_even_shape,scene_settings.use_follow_active_quads,layer_settings.uv_scale,scene_settings.set_target_texel_density,scene_settings.target_texel_density,scene_settings.texture_resolution,context.scene.unit_settings.scale_length,scene_settings.generate_second_uv,scene_settings.average_uv_island_scale,scene_settings.align_uvs_horizontally,scene_settings.place_in_quarter_strips,scene_settings.randomize_quarter_strip,False,scene_settings.horizontal_randomize_amount,layer_settings.seed,scene_settings.uv_strip_padding,)
	if use_auto_uv_pins and pins:
		pinned_islands=apply_uv_pins_to_decal_objects([decal_obj],pins,layer_settings.seed,)
	if scene_settings.randomize_horizontal_offset:
		processed_islands=max(processed_islands,randomize_decal_uv_islands_horizontally(decal_obj,layer_settings.seed,scene_settings.uv_strip_padding,scene_settings.horizontal_randomize_amount,),)
	decal_obj["edge_decal_intersection_uv_result"]=quadrify_result
	decal_obj["edge_decal_intersection_uv_islands"]=processed_islands
	decal_obj["edge_decal_intersection_uv_pinned_islands"]=pinned_islands
	decal_obj["edge_decal_last_uv_signature"]=decal_uv_settings_signature(layer_settings)
	if measured_density > 0.0:
		decal_obj["edge_decal_texel_density_px_cm"]=measured_density
	return quadrify_result,processed_islands,measured_density,pinned_islands
def _intersection_source_objects(layer_obj):
	source_a=find_object_by_name_or_full(layer_obj.get("edge_decal_intersection_source_a", ""))
	source_b=find_object_by_name_or_full(layer_obj.get("edge_decal_intersection_source_b", ""))
	return source_a,source_b
def _intersection_face_width(settings,source_obj,other_obj,reference_size):
	relative=bool(getattr(settings, "relative_face_width",True))
	face_width=max(float(settings.face_width),MIN_FACE_WIDTH)
	if not bool(getattr(settings, "randomize_face_width",False)):
		return face_width * reference_size if relative else face_width
	minimum=max(float(getattr(settings, "minimum_face_width",MIN_FACE_WIDTH)),MIN_FACE_WIDTH,)
	maximum=max(float(getattr(settings, "maximum_face_width",MIN_FACE_WIDTH)),MIN_FACE_WIDTH,)
	if relative:
		minimum *=reference_size
		maximum *=reference_size
	names= "\0".join(sorted((source_obj.name_full,other_obj.name_full)))
	signature=int.from_bytes(hashlib.blake2b(names.encode("utf-8"),digest_size=8).digest(),"big",)
	return randomized_face_width(minimum,maximum,int(getattr(settings, "seed",0)),signature,)
def _write_intersection_decal_geometry(context,layer_obj,source_obj,other_obj,settings,):
	reference_size=max(source_mesh_max_dimension(source_obj),source_mesh_max_dimension(other_obj),)
	face_width=_intersection_face_width(settings,source_obj,other_obj,reference_size,)
	tolerance=max(reference_size * 1.0e-6,1.0e-7)
	segments,surface_a,surface_b=mesh_intersection_data(source_obj,other_obj,context.evaluated_depsgraph_get(),tolerance=tolerance,)
	if not segments:
		return False, "The stored source meshes do not intersect"
	seam_edges=[]
	vertices,faces,face_uvs,center_indices=build_intersection_decal_mesh(segments,face_width,max(0.0,float(settings.surface_offset)),settings.uv_scale,getattr(context.scene.edge_decal_settings, "miter_limit",4.0),seam_edges_out=seam_edges,surface_a=surface_a,surface_b=surface_b,)
	if not faces:
		return False, "No usable intersection curve was found"
	local_matrix=layer_obj.matrix_world.inverted_safe()
	local_vertices=[local_matrix @ vertex for vertex in vertices]
	mesh=layer_obj.data
	mesh.clear_geometry()
	mesh.from_pydata([tuple(vertex) for vertex in local_vertices],[],faces)
	mesh.update(calc_edges=True)
	marked_seams=_mark_intersection_decal_seams(mesh,seam_edges)
	uv_layer=mesh.uv_layers.active
	if uv_layer is None:
		uv_layer=mesh.uv_layers.new(name="UVMap")
	for polygon,polygon_uvs in zip(mesh.polygons,face_uvs):
		for loop_index,uv in zip(polygon.loop_indices,polygon_uvs):
			uv_layer.data[loop_index].uv=uv
	center_group=layer_obj.vertex_groups.get("EdgeDecal_Center")
	if center_group is None:
		center_group=layer_obj.vertex_groups.new(name="EdgeDecal_Center")
	if center_indices:
		center_group.add(center_indices,1.0, "REPLACE")
	layer_obj["edge_decal_intersection_segment_count"]=len(segments)
	layer_obj["edge_decal_intersection_seam_edge_count"]=marked_seams
	return True,len(segments)
def regenerate_intersection_decal(context,layer_obj,operator=None):
	source_obj,other_obj=_intersection_source_objects(layer_obj)
	if source_obj is None or other_obj is None:
		if operator is not None:
			GR(operator,"ERROR", "An intersection source object is missing")
		return {"CANCELLED"}
	data=layer_obj.edge_decal_object_settings
	success,result=_write_intersection_decal_geometry(context,layer_obj,source_obj,other_obj,data,)
	if not success:
		if operator is not None:
			GR(operator,"WARNING",result)
		return {"CANCELLED"}
	apply_decal_normal_settings(layer_obj,data.normal_mode,data.normal_keep_sharp,data.normal_weight,data.normal_threshold,)
	apply_decal_mesh_material_direct(layer_obj,data.decal_material)
	process_intersection_decal_uvs(context,source_obj,layer_obj,data,)
	set_active_decal_layer(source_obj,layer_obj)
	sync_source_layer_ui(source_obj,active_layer=layer_obj)
	finish_decal_generation(context,source_obj,layer_obj)
	if operator is not None:
		GR(operator,"INFO",f"Updated intersection decal from {result} segment(s)")
	return {"FINISHED"}
def _intersection_selected_meshes(context):
	return [obj for obj in context.selected_objects if obj.type== "MESH" and not obj.get("edge_decal_generated")]
class EDGEDECAL_OT_generate_intersections(Operator):
	bl_idname= "object.generate_edge_decals_at_intersections";bl_label= g("Generate Intersections");bl_description=("在正好两个选定的网格对象相交的位置生成包裹边贴花");bl_options={"REGISTER", "UNDO"}
	@classmethod
	def poll(cls,context):
		return context.mode== "OBJECT" and len(_intersection_selected_meshes(context))==2
	def execute(self,context):
		selected=_intersection_selected_meshes(context)
		if len(selected) !=2:
			GR(self,"ERROR", "Select exactly two mesh objects")
			return {"CANCELLED"}
		active=context.view_layer.objects.active
		source_obj=active if active in selected else selected[0]
		other_obj=selected[1] if selected[0] is source_obj else selected[0]
		settings=context.scene.edge_decal_settings
		reference_size=max(source_mesh_max_dimension(source_obj),source_mesh_max_dimension(other_obj),)
		face_width=_intersection_face_width(settings,source_obj,other_obj,reference_size,)
		tolerance=max(reference_size * 1.0e-6,1.0e-7)
		segments,surface_a,surface_b=mesh_intersection_data(source_obj,other_obj,context.evaluated_depsgraph_get(),tolerance=tolerance,)
		if not segments:
			GR(self,"WARNING", "The selected meshes do not intersect")
			return {"CANCELLED"}
		seam_edges=[]
		vertices,faces,face_uvs,center_indices=build_intersection_decal_mesh(segments,face_width,max(0.0,float(settings.surface_offset)),settings.uv_scale,settings.miter_limit,seam_edges_out=seam_edges,surface_a=surface_a,surface_b=surface_b,)
		if not faces:
			GR(self,"WARNING", "No usable intersection curve was found")
			return {"CANCELLED"}
		ensure_source_decal_layers_ready(source_obj,context)
		layer_obj=find_generation_shell_layer(source_obj,context=context,include_locked=False,)
		if layer_obj is None:
			decal_index=next_decal_index(source_obj)
			base_name=f"{source_obj.name}_IntersectionDecal_{decal_index:02d}"
			mesh=bpy.data.meshes.new(f"{base_name}_Mesh")
			layer_obj=bpy.data.objects.new(base_name,mesh)
			configure_decal_object(layer_obj,source_obj=source_obj,scene=context.scene)
			layer_obj.matrix_world=Matrix.Identity(4)
			decal_world_matrix=layer_obj.matrix_world.copy()
			layer_obj.parent=source_obj
			layer_obj.matrix_parent_inverse=source_obj.matrix_world.inverted_safe()
			layer_obj.matrix_world=decal_world_matrix
			layer_obj["edge_decal_index"]=decal_index
		else:
			mesh=layer_obj.data
		local_matrix=layer_obj.matrix_world.inverted_safe()
		local_vertices=[local_matrix @ vertex for vertex in vertices]
		mesh.clear_geometry()
		mesh.from_pydata([tuple(vertex) for vertex in local_vertices],[],faces)
		mesh.update(calc_edges=True)
		marked_seams=_mark_intersection_decal_seams(mesh,seam_edges)
		uv_layer=mesh.uv_layers.active
		if uv_layer is None:
			uv_layer=mesh.uv_layers.new(name="UVMap")
		for polygon,polygon_uvs in zip(mesh.polygons,face_uvs):
			for loop_index,uv in zip(polygon.loop_indices,polygon_uvs):
				uv_layer.data[loop_index].uv=uv
		center_group=layer_obj.vertex_groups.get("EdgeDecal_Center")
		if center_group is None:
			center_group=layer_obj.vertex_groups.new(name="EdgeDecal_Center")
		if center_indices:
			center_group.add(center_indices,1.0, "REPLACE")
		layer_obj["edge_decal_generated"]=True
		layer_obj["edge_decal_source"]=source_obj.name_full
		layer_obj["edge_decal_mode"]= "INTERSECTIONS"
		layer_obj["edge_decal_intersection_source_a"]=source_obj.name_full
		layer_obj["edge_decal_intersection_source_b"]=other_obj.name_full
		layer_obj["edge_decal_intersection_segment_count"]=len(segments)
		layer_obj["edge_decal_intersection_seam_edge_count"]=marked_seams
		resolve_material=globals().get("ensure_edge_decal_preset_material_for_use")
		if resolve_material is not None and getattr(settings, "use_material",True):
			_material,asset_warnings,expected_material=resolve_material(context,settings,)
			if expected_material and _material is None:
				GR(self,"WARNING","Could not load preset assets: " + ", ".join(asset_warnings),)
		store_decal_settings(layer_obj,source_obj,"INTERSECTIONS",[],settings,{"face_width": settings.face_width,"relative_face_width": settings.relative_face_width, "surface_offset": settings.surface_offset, "uv_scale": settings.uv_scale,},)
		ensure_decal_finish_modifiers(layer_obj,source_obj,settings)
		apply_decal_normal_settings(layer_obj,settings.normal_mode,settings.normal_keep_sharp,settings.normal_weight,settings.normal_threshold,)
		finalize_generated_decal_layer(source_obj,layer_obj,settings)
		process_intersection_decal_uvs(context,source_obj,layer_obj,layer_obj.edge_decal_object_settings,)
		sync_source_layer_ui(source_obj,active_layer=layer_obj)
		finish_decal_generation(context,source_obj,layer_obj)
		GR(self,"INFO",f"Generated intersection decal from {len(segments)} segment(s)",)
		return {"FINISHED"}
def _existing_boolean_decal_layer(source_obj,context=None,):
	matches=[decal_obj for decal_obj in iter_generated_decals(source_obj=source_obj,mode="BOOLEAN",)]
	if not matches:
		return None
	active_layer=active_decal_layer_for_source(source_obj,context=context,)
	if active_layer in matches:
		return active_layer
	return max(matches,
		key=lambda decal_obj: int(decal_obj.get("edge_decal_index",0)),)
def _remove_boolean_temporary_datablocks(objects,meshes,materials):
	for obj in objects:
		if obj is not None and obj.name in bpy.data.objects:
			bpy.data.objects.remove(obj,do_unlink=True)
	for mesh in meshes:
		if mesh is not None and mesh.users==0:
			bpy.data.meshes.remove(mesh)
	for material in materials:
		if material is not None and material.users==0:
			bpy.data.materials.remove(material)
def build_boolean_decal_mesh(context,source_obj,cutter_obj,settings,source_boolean_modifier=None,):
	temporary_objects=[]
	temporary_meshes=[]
	temporary_materials=[]
	result_bm=None
	try:
		if cutter_obj.mode== "EDIT":
			cutter_obj.update_from_editmode()
			context.view_layer.update()
		depsgraph=context.evaluated_depsgraph_get()
		source_evaluation_object=source_obj
		if source_boolean_modifier is not None:
			source_pre_boolean_mesh=source_obj.data.copy()
			source_pre_boolean=source_obj.copy()
			source_pre_boolean.data=source_pre_boolean_mesh
			source_pre_boolean.parent=None
			context.scene.collection.objects.link(source_pre_boolean)
			source_pre_boolean.matrix_world=source_obj.matrix_world.copy()
			temporary_objects.append(source_pre_boolean)
			temporary_meshes.append(source_pre_boolean_mesh)
			copied_boolean=source_pre_boolean.modifiers.get(source_boolean_modifier.name)
			if copied_boolean is None:
				return None, "The stored Boolean modifier could not be evaluated"
			source_pre_boolean.modifiers.remove(copied_boolean)
			context.view_layer.update()
			source_evaluation_object=source_pre_boolean
			depsgraph=context.evaluated_depsgraph_get()
		source_mesh=bpy.data.meshes.new_from_object(source_evaluation_object.evaluated_get(depsgraph),preserve_all_data_layers=True,depsgraph=depsgraph,)
		cutter_mesh=bpy.data.meshes.new_from_object(cutter_obj.evaluated_get(depsgraph),preserve_all_data_layers=True,depsgraph=depsgraph,)
		temporary_meshes.extend((source_mesh,cutter_mesh))
		source_temp=bpy.data.objects.new("__EdgeDecalBooleanSource",source_mesh)
		cutter_temp=bpy.data.objects.new("__EdgeDecalBooleanCutter",cutter_mesh)
		temporary_objects.extend((source_temp,cutter_temp))
		context.scene.collection.objects.link(source_temp)
		context.scene.collection.objects.link(cutter_temp)
		source_temp.matrix_world=source_obj.matrix_world.copy()
		cutter_temp.matrix_world=cutter_obj.matrix_world.copy()
		source_marker=bpy.data.materials.new("__EdgeDecalBooleanOriginal")
		cutter_marker=bpy.data.materials.new("__EdgeDecalBooleanAffected")
		temporary_materials.extend((source_marker,cutter_marker))
		for mesh in (source_mesh,cutter_mesh):
			mesh.materials.clear()
			mesh.materials.append(source_marker)
			mesh.materials.append(cutter_marker)
		for polygon in source_mesh.polygons:
			polygon.material_index=0
		for polygon in cutter_mesh.polygons:
			polygon.material_index=1
		temporary_boolean=source_temp.modifiers.new(name="Edge Decal Temporary Difference",type="BOOLEAN",)
		temporary_boolean.operation=(source_boolean_modifier.operation if source_boolean_modifier is not None else "DIFFERENCE")
		temporary_boolean.solver=(source_boolean_modifier.solver if source_boolean_modifier is not None else "EXACT")
		temporary_boolean.object=cutter_temp
		for property_name in ("use_self","use_hole_tolerant","double_threshold","material_mode",):
			if (source_boolean_modifier is not None
				and hasattr(source_boolean_modifier,property_name)
				and hasattr(temporary_boolean,property_name)):
				setattr(temporary_boolean,property_name,getattr(source_boolean_modifier,property_name),)
		context.view_layer.update()
		result_depsgraph=context.evaluated_depsgraph_get()
		result_mesh=bpy.data.meshes.new_from_object(source_temp.evaluated_get(result_depsgraph),preserve_all_data_layers=True,depsgraph=result_depsgraph,)
		temporary_meshes.append(result_mesh)
		result_bm=bmesh.new()
		result_bm.from_mesh(result_mesh)
		result_bm.normal_update()
		result_bm.verts.ensure_lookup_table()
		result_bm.edges.ensure_lookup_table()
		result_bm.faces.ensure_lookup_table()
		result_bm.edges.index_update()
		affected_edges=[edge for edge in result_bm.edges if (len(edge.link_faces)==2 and {face.material_index for face in edge.link_faces}=={0,1}) 	]
		if not affected_edges:
			return None, "The Boolean did not create any seam edges"
		world_matrix=source_obj.matrix_world.copy()
		try:
			normal_matrix=world_matrix.to_3x3().inverted().transposed()
		except ValueError:
			return None,("The source object has a non-invertible transform; " "check for zero scale")
		all_source_edges=list(result_bm.edges)
		resolved_face_width=max(float(settings.face_width),MIN_FACE_WIDTH)
		if bool(getattr(settings, "relative_face_width",True)):
			resolved_face_width *=source_mesh_max_dimension(source_obj)
		random_width_minimum=resolved_face_width
		random_width_maximum=resolved_face_width
		if bool(getattr(settings, "randomize_face_width",False)):
			random_width_minimum=max(float(getattr(settings, "minimum_face_width",MIN_FACE_WIDTH)),MIN_FACE_WIDTH,)
			random_width_maximum=max(float(getattr(settings, "maximum_face_width",MIN_FACE_WIDTH)),MIN_FACE_WIDTH,)
			if bool(getattr(settings, "relative_face_width",True)):
				reference_size=source_mesh_max_dimension(source_obj)
				random_width_minimum *=reference_size
				random_width_maximum *=reference_size
			random_width_minimum,random_width_maximum=(min(random_width_minimum,random_width_maximum),max(random_width_minimum,random_width_maximum),)
		scene_settings=context.scene.edge_decal_settings
		selected_edge_set=set(affected_edges)
		width_search_context=build_adaptive_width_search_context(all_source_edges,selected_edge_set,world_matrix,clamp_boundaries=settings.auto_face_width,clamp_selected_overlaps=settings.clamp_edge_overlaps,search_radius=max(random_width_maximum * 4.0,1.0e-4),)
		edge_groups=partition_selected_edge_graph_by_angle(affected_edges,world_matrix,(scene_settings.split_angle if scene_settings.use_edge_split else pi),)
		face_width_by_edge=None
		if bool(getattr(settings, "randomize_face_width",False)):
			face_width_by_edge=randomized_face_widths_for_edge_groups(edge_groups,random_width_minimum,random_width_maximum,int(getattr(settings, "seed",0)),world_matrix,)
		vertices=[]
		faces=[]
		face_uvs=[]
		center_indices=[]
		created_face_count=build_partitioned_selected_edge_graph_strip(selected_edges=affected_edges,edge_groups=edge_groups,all_source_edges=all_source_edges,world_matrix=world_matrix,normal_matrix=normal_matrix,face_width=resolved_face_width,surface_offset=max(0.0,float(settings.surface_offset)),miter_limit=scene_settings.miter_limit,vertices_out=vertices,faces_out=faces,face_uvs_out=face_uvs,center_vertices_out=center_indices,auto_face_width=settings.auto_face_width,auto_width_samples=settings.auto_width_samples,auto_width_clearance=settings.auto_width_clearance,clamp_edge_overlaps=settings.clamp_edge_overlaps,overlap_clearance=settings.overlap_clearance,width_search_context=width_search_context,face_width_resolved=True,uv_scale=settings.uv_scale,face_width_by_edge=face_width_by_edge,)
		if created_face_count==0 or not faces:
			return None, "No valid decal strip could be built from the Boolean seam"
		return (vertices,faces,face_uvs,sorted(set(center_indices)),len(affected_edges),),None
	finally:
		if result_bm is not None:
			result_bm.free()
		_remove_boolean_temporary_datablocks(temporary_objects,temporary_meshes,temporary_materials,)
def _enabled_source_boolean_modifiers(source_obj):
	if source_obj is None:
		return []
	return [modifier for modifier in source_obj.modifiers if (modifier.type== "BOOLEAN" and modifier.show_viewport and getattr(modifier, "operand_type", "OBJECT")== "OBJECT" and modifier.object is not None and modifier.object.type== "MESH")]
def _snap_zero_offset_boolean_vertices_to_surface(vertices,result_bm,world_matrix,):
	if not vertices or result_bm is None:
		return 0
	result_bvh=BVHTree.FromBMesh(result_bm)
	inverse_world=world_matrix.inverted_safe()
	snapped=0
	for index,vertex in enumerate(vertices):
		local_point=inverse_world @ vertex
		nearest=result_bvh.find_nearest(local_point)
		if nearest is None:
			continue
		surface_point,_normal,_face_index,distance=nearest
		if distance <=1.0e-7:
			continue
		vertices[index]=world_matrix @ surface_point
		snapped +=1
	return snapped
def build_combined_boolean_decal_mesh(context,source_obj,boolean_modifiers,settings,):
	boolean_modifiers=list(boolean_modifiers or ())
	if not boolean_modifiers:
		return None, "The source has no enabled Object Boolean modifiers"
	temporary_objects=[]
	temporary_meshes=[]
	temporary_materials=[]
	result_bm=None
	try:
		source_mesh=source_obj.data.copy()
		source_temp=source_obj.copy()
		source_temp.data=source_mesh
		source_temp.parent=None
		context.scene.collection.objects.link(source_temp)
		source_temp.matrix_world=source_obj.matrix_world.copy()
		temporary_objects.append(source_temp)
		temporary_meshes.append(source_mesh)
		markers=[bpy.data.materials.new("__EdgeDecalBooleanOriginal")] + [bpy.data.materials.new(f"__EdgeDecalBooleanAffected_{index:02d}") for index in range(1,len(boolean_modifiers) + 1)]
		temporary_materials.extend(markers)
		source_mesh.materials.clear()
		for marker in markers:
			source_mesh.materials.append(marker)
		for polygon in source_mesh.polygons:
			polygon.material_index=0
		modifier_by_name={modifier.name: (index,modifier) for index,modifier in enumerate(boolean_modifiers,start=1)}
		for copied_modifier in source_temp.modifiers:
			if copied_modifier.type != "BOOLEAN":
				continue
			record=modifier_by_name.get(copied_modifier.name)
			if record is None:
				copied_modifier.show_viewport=False
				continue
			marker_index,original_modifier=record
			cutter_obj=original_modifier.object
			if cutter_obj.mode== "EDIT":
				cutter_obj.update_from_editmode()
				context.view_layer.update()
			depsgraph=context.evaluated_depsgraph_get()
			cutter_mesh=bpy.data.meshes.new_from_object(cutter_obj.evaluated_get(depsgraph),preserve_all_data_layers=True,depsgraph=depsgraph,)
			cutter_temp=bpy.data.objects.new(f"__EdgeDecalBooleanCutter_{marker_index:02d}",cutter_mesh,)
			context.scene.collection.objects.link(cutter_temp)
			cutter_temp.matrix_world=cutter_obj.matrix_world.copy()
			temporary_objects.append(cutter_temp)
			temporary_meshes.append(cutter_mesh)
			cutter_mesh.materials.clear()
			for marker in markers:
				cutter_mesh.materials.append(marker)
			for polygon in cutter_mesh.polygons:
				polygon.material_index=marker_index
			copied_modifier.object=cutter_temp
			copied_modifier.show_viewport=True
			if hasattr(copied_modifier, "material_mode"):
				copied_modifier.material_mode= "TRANSFER"
		context.view_layer.update()
		result_depsgraph=context.evaluated_depsgraph_get()
		result_mesh=bpy.data.meshes.new_from_object(source_temp.evaluated_get(result_depsgraph),preserve_all_data_layers=True,depsgraph=result_depsgraph,)
		temporary_meshes.append(result_mesh)
		result_bm=bmesh.new()
		result_bm.from_mesh(result_mesh)
		result_bm.normal_update()
		result_bm.verts.ensure_lookup_table()
		result_bm.edges.ensure_lookup_table()
		result_bm.faces.ensure_lookup_table()
		result_bm.edges.index_update()
		affected_edges=[edge for edge in result_bm.edges if (len(edge.link_faces)==2 and len({face.material_index for face in edge.link_faces}) > 1 and any(face.material_index > 0 for face in edge.link_faces)) 	]
		if not affected_edges:
			return None, "The Boolean stack did not create any surviving seam edges"
		world_matrix=source_obj.matrix_world.copy()
		try:
			normal_matrix=world_matrix.to_3x3().inverted().transposed()
		except ValueError:
			return None,("The source object has a non-invertible transform; " "check for zero scale")
		all_source_edges=list(result_bm.edges)
		resolved_face_width=max(float(settings.face_width),MIN_FACE_WIDTH)
		if bool(getattr(settings, "relative_face_width",True)):
			resolved_face_width *=source_mesh_max_dimension(source_obj)
		random_width_minimum=resolved_face_width
		random_width_maximum=resolved_face_width
		if bool(getattr(settings, "randomize_face_width",False)):
			random_width_minimum=max(float(getattr(settings, "minimum_face_width",MIN_FACE_WIDTH)),MIN_FACE_WIDTH,)
			random_width_maximum=max(float(getattr(settings, "maximum_face_width",MIN_FACE_WIDTH)),MIN_FACE_WIDTH,)
			if bool(getattr(settings, "relative_face_width",True)):
				reference_size=source_mesh_max_dimension(source_obj)
				random_width_minimum *=reference_size
				random_width_maximum *=reference_size
			random_width_minimum,random_width_maximum=(min(random_width_minimum,random_width_maximum),max(random_width_minimum,random_width_maximum),)
		scene_settings=context.scene.edge_decal_settings
		selected_edge_set=set(affected_edges)
		width_search_context=build_adaptive_width_search_context(all_source_edges,selected_edge_set,world_matrix,clamp_boundaries=settings.auto_face_width,clamp_selected_overlaps=settings.clamp_edge_overlaps,search_radius=max(random_width_maximum * 4.0,1.0e-4),)
		edge_groups=partition_selected_edge_graph_by_angle(affected_edges,world_matrix,scene_settings.split_angle if scene_settings.use_edge_split else pi,)
		face_width_by_edge=None
		if bool(getattr(settings, "randomize_face_width",False)):
			face_width_by_edge=randomized_face_widths_for_edge_groups(edge_groups,random_width_minimum,random_width_maximum,int(getattr(settings, "seed",0)),world_matrix,)
		vertices=[]
		faces=[]
		face_uvs=[]
		center_indices=[]
		created_face_count=build_partitioned_selected_edge_graph_strip(selected_edges=affected_edges,edge_groups=edge_groups,all_source_edges=all_source_edges,world_matrix=world_matrix,normal_matrix=normal_matrix,face_width=resolved_face_width,surface_offset=max(0.0,float(settings.surface_offset)),miter_limit=scene_settings.miter_limit,vertices_out=vertices,faces_out=faces,face_uvs_out=face_uvs,center_vertices_out=center_indices,auto_face_width=settings.auto_face_width,auto_width_samples=settings.auto_width_samples,auto_width_clearance=settings.auto_width_clearance,clamp_edge_overlaps=settings.clamp_edge_overlaps,overlap_clearance=settings.overlap_clearance,width_search_context=width_search_context,face_width_resolved=True,uv_scale=settings.uv_scale,face_width_by_edge=face_width_by_edge,fold_nonplanar_sectors=True,)
		if created_face_count==0 or not faces:
			return None, "No valid decal strip could be built from the Boolean seams"
		if max(0.0,float(settings.surface_offset)) <=EPSILON:
			_snap_zero_offset_boolean_vertices_to_surface(vertices,result_bm,world_matrix,)
		return (vertices,faces,face_uvs,sorted(set(center_indices)),len(affected_edges),),None
	finally:
		if result_bm is not None:
			result_bm.free()
		_remove_boolean_temporary_datablocks(temporary_objects,temporary_meshes,temporary_materials,)
def _store_combined_boolean_metadata(layer_obj,source_obj,boolean_modifiers,affected_edge_count,):
	boolean_modifiers=list(boolean_modifiers or ())
	layer_obj["edge_decal_boolean_combined"]=True
	layer_obj["edge_decal_boolean_source"]=source_obj.name_full
	layer_obj["edge_decal_boolean_modifiers"]=json.dumps([modifier.name for modifier in boolean_modifiers])
	layer_obj["edge_decal_boolean_cutters"]=json.dumps([modifier.object.name_full for modifier in boolean_modifiers])
	layer_obj["edge_decal_boolean_modifier_count"]=len(boolean_modifiers)
	layer_obj["edge_decal_boolean_edge_count"]=affected_edge_count
	layer_obj["edge_decal_boolean_operation"]= "COMBINED"
	for legacy_key in ("edge_decal_boolean_cutter","edge_decal_boolean_modifier",):
		if legacy_key in layer_obj:
			del layer_obj[legacy_key]
def _write_combined_boolean_decal_geometry(context,layer_obj,source_obj,boolean_modifiers,settings,):
	result,error=build_combined_boolean_decal_mesh(context,source_obj,boolean_modifiers,settings,)
	if result is None:
		return False,error
	vertices,faces,face_uvs,center_indices,affected_edge_count=result
	local_matrix=layer_obj.matrix_world.inverted_safe()
	local_vertices=[local_matrix @ vertex for vertex in vertices]
	mesh=layer_obj.data
	mesh.clear_geometry()
	mesh.from_pydata([tuple(vertex) for vertex in local_vertices],[],faces)
	mesh.update(calc_edges=True)
	uv_layer=mesh.uv_layers.active
	if uv_layer is None:
		uv_layer=mesh.uv_layers.new(name="UVMap")
	for polygon,polygon_uvs in zip(mesh.polygons,face_uvs):
		for loop_index,uv in zip(polygon.loop_indices,polygon_uvs):
			uv_layer.data[loop_index].uv=uv
	center_group=layer_obj.vertex_groups.get("EdgeDecal_Center")
	if center_group is None:
		center_group=layer_obj.vertex_groups.new(name="EdgeDecal_Center")
	if center_indices:
		center_group.add(center_indices,1.0, "REPLACE")
	_store_combined_boolean_metadata(layer_obj,source_obj,boolean_modifiers,affected_edge_count,)
	return True,affected_edge_count
def regenerate_boolean_decal(context,layer_obj,operator=None,):
	source_obj=find_object_by_name_or_full(layer_obj.get("edge_decal_boolean_source",layer_obj.get("edge_decal_source", ""),))
	if source_obj is None:
		if operator is not None:
			GR(operator,"ERROR", "The Boolean source object is missing")
		return {"CANCELLED"}
	boolean_modifiers=_enabled_source_boolean_modifiers(source_obj)
	if not boolean_modifiers:
		if operator is not None:
			GR(operator,"ERROR","The source has no enabled Object Boolean modifiers",)
		return {"CANCELLED"}
	data=layer_obj.edge_decal_object_settings
	success,result=_write_combined_boolean_decal_geometry(context,layer_obj,source_obj,boolean_modifiers,data,)
	if not success:
		if operator is not None:
			GR(operator,"WARNING",result)
		return {"CANCELLED"}
	apply_decal_normal_settings(layer_obj,data.normal_mode,data.normal_keep_sharp,data.normal_weight,data.normal_threshold,)
	apply_decal_mesh_material_direct(layer_obj,data.decal_material)
	process_intersection_decal_uvs(context,source_obj,layer_obj,data)
	data.live_update=False
	set_active_decal_layer(source_obj,layer_obj)
	sync_source_layer_ui(source_obj,active_layer=layer_obj)
	finish_decal_generation(context,source_obj,layer_obj)
	if operator is not None:
		GR(operator,"INFO",f"Updated combined Boolean decal from {result} seam edge(s)",)
	return {"FINISHED"}
class EDGEDECAL_OT_generate_boolean(Operator):
	bl_idname= "object.generate_edge_decals_from_boolean";bl_label= g("Generate From Booleans");bl_description=("从所有全部启用对象布尔生成一合成贴花\n 选定的源网格上已存在修改器");bl_options={"REGISTER", "UNDO"}
	@classmethod
	def poll(cls,context):
		selected=_intersection_selected_meshes(context)
		active=context.view_layer.objects.active
		return (context.mode== "OBJECT"
			and len(selected)==1 and active in selected)
	def execute(self,context):
		selected=_intersection_selected_meshes(context)
		active=context.view_layer.objects.active
		if len(selected) !=1 or active not in selected:
			GR(self,"ERROR","Select exactly one source mesh",)
			return {"CANCELLED"}
		source_obj=active
		settings=context.scene.edge_decal_settings
		boolean_modifiers=_enabled_source_boolean_modifiers(source_obj)
		if not boolean_modifiers:
			GR(self,"WARNING","The source has no enabled Object Boolean modifiers",)
			return {"CANCELLED"}
		existing_layer=_existing_boolean_decal_layer(source_obj,context=context,)
		if existing_layer is not None:
			if existing_layer.get("edge_decal_locked",False):
				GR(self,"WARNING","The matching Boolean decal layer is locked",)
				return {"CANCELLED"}
			return regenerate_boolean_decal(context,existing_layer,operator=self,)
		result,error=build_combined_boolean_decal_mesh(context,source_obj,boolean_modifiers,settings,)
		if result is None:
			GR(self,"WARNING",error)
			return {"CANCELLED"}
		vertices,faces,face_uvs,center_indices,affected_edge_count=result
		ensure_source_decal_layers_ready(source_obj,context)
		layer_obj=find_generation_shell_layer(source_obj,context=context,include_locked=False,)
		if layer_obj is None:
			decal_index=next_decal_index(source_obj)
			base_name=f"{source_obj.name}_BooleanDecal_{decal_index:02d}"
			mesh=bpy.data.meshes.new(f"{base_name}_Mesh")
			layer_obj=bpy.data.objects.new(base_name,mesh)
			configure_decal_object(layer_obj,source_obj=source_obj,scene=context.scene,)
			layer_obj.matrix_world=Matrix.Identity(4)
			decal_world_matrix=layer_obj.matrix_world.copy()
			layer_obj.parent=source_obj
			layer_obj.matrix_parent_inverse=source_obj.matrix_world.inverted_safe()
			layer_obj.matrix_world=decal_world_matrix
			layer_obj["edge_decal_index"]=decal_index
		else:
			mesh=layer_obj.data
		local_matrix=layer_obj.matrix_world.inverted_safe()
		local_vertices=[local_matrix @ vertex for vertex in vertices]
		mesh.clear_geometry()
		mesh.from_pydata([tuple(vertex) for vertex in local_vertices],[],faces)
		mesh.update(calc_edges=True)
		uv_layer=mesh.uv_layers.active
		if uv_layer is None:
			uv_layer=mesh.uv_layers.new(name="UVMap")
		for polygon,polygon_uvs in zip(mesh.polygons,face_uvs):
			for loop_index,uv in zip(polygon.loop_indices,polygon_uvs):
				uv_layer.data[loop_index].uv=uv
		center_group=layer_obj.vertex_groups.get("EdgeDecal_Center")
		if center_group is None:
			center_group=layer_obj.vertex_groups.new(name="EdgeDecal_Center")
		if center_indices:
			center_group.add(center_indices,1.0, "REPLACE")
		layer_obj["edge_decal_generated"]=True
		layer_obj["edge_decal_source"]=source_obj.name_full
		layer_obj["edge_decal_mode"]= "BOOLEAN"
		_store_combined_boolean_metadata(layer_obj,source_obj,boolean_modifiers,affected_edge_count,)
		resolve_material=globals().get("ensure_edge_decal_preset_material_for_use")
		if resolve_material is not None and getattr(settings, "use_material",True):
			_material,asset_warnings,expected_material=resolve_material(context,settings,)
			if expected_material and _material is None:
				GR(self,"WARNING","Could not load preset assets: " + ", ".join(asset_warnings),)
		store_decal_settings(layer_obj,source_obj,"BOOLEAN",[],settings,{"face_width": settings.face_width,"relative_face_width": settings.relative_face_width, "surface_offset": settings.surface_offset, "uv_scale": settings.uv_scale,},)
		ensure_decal_finish_modifiers(layer_obj,source_obj,settings)
		apply_decal_normal_settings(layer_obj,settings.normal_mode,settings.normal_keep_sharp,settings.normal_weight,settings.normal_threshold,)
		finalize_generated_decal_layer(source_obj,layer_obj,settings)
		layer_obj.edge_decal_object_settings.live_update=False
		process_intersection_decal_uvs(context,source_obj,layer_obj,layer_obj.edge_decal_object_settings,)
		sync_source_layer_ui(source_obj,active_layer=layer_obj)
		finish_decal_generation(context,source_obj,layer_obj)
		GR(self,"INFO",f"Generated combined Boolean decal from {affected_edge_count} seam edge(s)",)
		return {"FINISHED"}
