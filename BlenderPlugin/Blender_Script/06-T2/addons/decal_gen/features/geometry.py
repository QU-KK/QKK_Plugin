# SPDX-License-Identifier: GPL-2.0-or-later
"""Edge-chain extraction, strip construction, adaptive width, AO/crevice filtering, slicing, and geometry utilities.

Loaded into the add-on package shared namespace by __init__.py.
"""


EDGEDECAL_PREPARED_SOURCE_CACHE = {}
EDGEDECAL_PREPARED_SOURCE_CACHE_STATS = {
    "prepared_hits": 0,
    "prepared_misses": 0,
    "chain_hits": 0,
    "chain_misses": 0,
}


def prepared_source_cache_key(
    source_obj,
    angle_limit=radians(5.0),
    apply_limited_dissolve=True,
):
    if (
        source_obj is None
        or getattr(source_obj, "type", None) != "MESH"
        or getattr(source_obj, "data", None) is None
    ):
        return None
    return (
        int(source_obj.data.as_pointer()),
        round(max(0.0, float(angle_limit)), 10),
        bool(apply_limited_dissolve),
    )


def clear_prepared_source_cache(source=None, reset_stats=False):
    """Free cached BMeshes for one source mesh, or for every source."""
    if source is None:
        target_pointer = None
    elif isinstance(source, int):
        target_pointer = int(source)
    else:
        mesh = (
            source.data
            if getattr(source, "type", None) == "MESH"
            else source
        )
        target_pointer = int(mesh.as_pointer()) if mesh is not None else None

    keys = [
        key
        for key in EDGEDECAL_PREPARED_SOURCE_CACHE
        if target_pointer is None or key[0] == target_pointer
    ]
    for key in keys:
        entry = EDGEDECAL_PREPARED_SOURCE_CACHE.pop(key, None)
        cached_bmesh = entry.get("bmesh") if entry is not None else None
        if cached_bmesh is not None:
            try:
                if cached_bmesh.is_valid:
                    cached_bmesh.free()
            except (ReferenceError, RuntimeError):
                pass

    if reset_stats:
        for stat_name in EDGEDECAL_PREPARED_SOURCE_CACHE_STATS:
            EDGEDECAL_PREPARED_SOURCE_CACHE_STATS[stat_name] = 0


def _cache_matrix_signature(matrix):
    return tuple(
        round(float(value), 10)
        for row in matrix
        for value in row
    )


def _update_mesh_cache_digest(digest, collection, property_name, typecode, count):
    if count <= 0:
        return
    zero = 0.0 if typecode in {"f", "d"} else 0
    values = array(typecode, [zero]) * int(count)
    collection.foreach_get(property_name, values)
    digest.update(values.tobytes())


def source_mesh_prepared_cache_signature(mesh):
    """Fingerprint geometry inputs while ignoring selection-only updates."""
    if mesh is None:
        return ""

    digest = hashlib.blake2b(digest_size=20)
    digest.update(
        (
            f"{len(mesh.vertices)}:{len(mesh.edges)}:"
            f"{len(mesh.loops)}:{len(mesh.polygons)}"
        ).encode("ascii")
    )
    _update_mesh_cache_digest(
        digest, mesh.vertices, "co", "f", len(mesh.vertices) * 3
    )
    _update_mesh_cache_digest(
        digest, mesh.edges, "vertices", "i", len(mesh.edges) * 2
    )
    _update_mesh_cache_digest(
        digest, mesh.edges, "use_seam", "b", len(mesh.edges)
    )
    if len(mesh.edges):
        try:
            _update_mesh_cache_digest(
                digest,
                mesh.edges,
                "use_edge_sharp",
                "b",
                len(mesh.edges),
            )
        except (AttributeError, TypeError):
            pass
    _update_mesh_cache_digest(
        digest, mesh.loops, "vertex_index", "i", len(mesh.loops)
    )
    _update_mesh_cache_digest(
        digest, mesh.polygons, "loop_start", "i", len(mesh.polygons)
    )
    _update_mesh_cache_digest(
        digest, mesh.polygons, "loop_total", "i", len(mesh.polygons)
    )
    _update_mesh_cache_digest(
        digest,
        mesh.polygons,
        "material_index",
        "i",
        len(mesh.polygons),
    )
    for uv_layer in mesh.uv_layers:
        digest.update(uv_layer.name.encode("utf-8", errors="replace"))
        _update_mesh_cache_digest(
            digest,
            uv_layer.data,
            "uv",
            "f",
            len(uv_layer.data) * 2,
        )
    return digest.hexdigest()


def invalidate_prepared_source_cache_if_changed(mesh):
    """Clear one mesh's entries only when its generation inputs changed."""
    if mesh is None:
        return False
    mesh_pointer = int(mesh.as_pointer())
    entries = [
        entry
        for key, entry in EDGEDECAL_PREPARED_SOURCE_CACHE.items()
        if key[0] == mesh_pointer
    ]
    if not entries:
        return False

    current_signature = source_mesh_prepared_cache_signature(mesh)
    pending_entries = [
        entry
        for entry in entries
        if entry.get("source_signature") is None
    ]
    for entry in pending_entries:
        # Generation builds the snapshot while the source is in Edit Mode.
        # The first depsgraph evaluation publishes that same edit BMesh to the
        # Mesh datablock; adopt it as the comparison baseline instead of
        # mistaking the mode/selection synchronization for a geometry edit.
        entry["source_signature"] = current_signature

    if all(
        entry.get("source_signature", "") == current_signature
        for entry in entries
    ):
        return False

    clear_prepared_source_cache(mesh_pointer)
    return True


# Fraction of the full side width kept at a sliced/tapered end. A value of 0
# collapses the tip to the centerline (a sharp triangle); a small positive
# value produces a blunt flat cap while still reading as a taper.
SLICE_TAPER_TIP_WIDTH_FACTOR = 0.34






def source_mesh_max_dimension(source_obj):
    """Return the largest world-space axis span of a mesh object."""
    if source_obj is None or source_obj.data is None:
        return 1.0

    world_matrix = source_obj.matrix_world
    points = [world_matrix @ vertex.co for vertex in source_obj.data.vertices]
    if not points:
        return 1.0

    span_x = max(point.x for point in points) - min(point.x for point in points)
    span_y = max(point.y for point in points) - min(point.y for point in points)
    span_z = max(point.z for point in points) - min(point.z for point in points)
    return max(span_x, span_y, span_z, 1.0e-6)




def resolve_relative_face_width(face_width, all_source_edges, world_matrix):
    """Resolve Face Width as a fraction of the source mesh world-space size."""
    try:
        settings = bpy.context.scene.edge_decal_settings
        use_relative = bool(getattr(settings, "relative_face_width", True))
    except Exception:
        use_relative = True

    # Clamp here as well as in RNA properties so old files, presets, and
    # scripted calls cannot feed crash-prone near-zero widths into geometry.
    requested = max(float(face_width), MIN_FACE_WIDTH)
    if not use_relative:
        return requested

    unique = {}
    for edge in all_source_edges or ():
        for vert in edge.verts:
            unique[vert.index] = world_matrix @ vert.co
    if not unique:
        return requested

    points = list(unique.values())
    span_x = max(p.x for p in points) - min(p.x for p in points)
    span_y = max(p.y for p in points) - min(p.y for p in points)
    span_z = max(p.z for p in points) - min(p.z for p in points)
    reference = max(span_x, span_y, span_z, 1.0e-6)
    return max(requested * reference, reference * 1.0e-7)


def resolve_random_face_width_bounds(
    minimum_face_width,
    maximum_face_width,
    all_source_edges,
    world_matrix,
):
    """Return ordered, world-space bounds for randomized strip widths."""
    width_a = resolve_relative_face_width(
        minimum_face_width,
        all_source_edges,
        world_matrix,
    )
    width_b = resolve_relative_face_width(
        maximum_face_width,
        all_source_edges,
        world_matrix,
    )
    return min(width_a, width_b), max(width_a, width_b)


def randomized_face_width(
    minimum_face_width,
    maximum_face_width,
    seed,
    signature,
):
    """Choose one deterministic width for a source path."""
    minimum = max(float(minimum_face_width), 1.0e-8)
    maximum = max(float(maximum_face_width), 1.0e-8)
    minimum, maximum = min(minimum, maximum), max(minimum, maximum)
    if maximum - minimum <= EPSILON:
        return minimum
    rng = random.Random(
        chain_random_stream_seed(seed, signature, 0xD1CEB00C)
    )
    return rng.uniform(minimum, maximum)

def build_selected_edge_graph(selected_edges):
    graph = {}

    for edge in selected_edges:
        v0, v1 = edge.verts
        graph.setdefault(v0, []).append(edge)
        graph.setdefault(v1, []).append(edge)

    return graph


def selected_edge_graph_component_count(selected_edges):
    """Count vertex-connected components without choosing branch paths."""
    graph = build_selected_edge_graph(selected_edges)
    remaining = set(graph)
    component_count = 0

    while remaining:
        component_count += 1
        seed = remaining.pop()
        pending = [seed]
        while pending:
            vertex = pending.pop()
            for edge in graph.get(vertex, ()):
                neighbor = edge.other_vert(vertex)
                if neighbor not in remaining:
                    continue
                remaining.remove(neighbor)
                pending.append(neighbor)

    return component_count


def partition_selected_edge_graph_by_angle(
    selected_edges,
    world_matrix,
    split_angle,
):
    """Partition an edge graph wherever every continuation turns too far.

    Two incident edges remain in the same partition when traversing from one
    into the other changes direction by at most ``split_angle``. This extends
    Split Edge Paths to branched graph generation without reducing the graph
    to one arbitrarily chosen ordered chain.
    """
    edges = list(dict.fromkeys(selected_edges or ()))
    if not edges:
        return []

    parent = {edge: edge for edge in edges}

    def find(edge):
        root = edge
        while parent[root] is not root:
            root = parent[root]
        while parent[edge] is not edge:
            next_edge = parent[edge]
            parent[edge] = root
            edge = next_edge
        return root

    def union(edge_a, edge_b):
        root_a = find(edge_a)
        root_b = find(edge_b)
        if root_a is root_b:
            return
        if root_a.index <= root_b.index:
            parent[root_b] = root_a
        else:
            parent[root_a] = root_b

    threshold = max(0.0, min(pi, float(split_angle)))
    graph = build_selected_edge_graph(edges)

    for vertex, incident_edges in graph.items():
        if len(incident_edges) < 2:
            continue
        vertex_point = world_matrix @ vertex.co
        directions = {}
        for edge in incident_edges:
            other = edge.other_vert(vertex)
            directions[edge] = safe_normalized(
                (world_matrix @ other.co) - vertex_point,
                Vector((1.0, 0.0, 0.0)),
            )

        for index_a in range(len(incident_edges) - 1):
            edge_a = incident_edges[index_a]
            for index_b in range(index_a + 1, len(incident_edges)):
                edge_b = incident_edges[index_b]
                # Directions point away from the shared vertex. Traversal into
                # the vertex reverses edge A, so straight continuation is 0.
                turn_cosine = max(
                    -1.0,
                    min(1.0, -directions[edge_a].dot(directions[edge_b])),
                )
                turn_angle = acos(turn_cosine)
                if turn_angle <= threshold + EPSILON:
                    union(edge_a, edge_b)

    grouped = {}
    for edge in edges:
        grouped.setdefault(find(edge), []).append(edge)

    groups = [
        sorted(group, key=lambda edge: edge.index)
        for group in grouped.values()
    ]
    groups.sort(key=lambda group: group[0].index)
    return groups


def extract_edge_chains(selected_edges, world_matrix):
    """
    Build ordered chains while preserving straight continuation through
    vertices that have more than two selected edges.

    At a junction, selected edges are paired by the straightest world-space
    continuation. This prevents a flat edge loop crossing another selected
    edge from being split for no geometric reason.
    """
    graph = build_selected_edge_graph(selected_edges)
    selected_set = set(selected_edges)

    def edge_direction_away(edge, vertex):
        other = edge.verts[1] if edge.verts[0] == vertex else edge.verts[0]
        vertex_world = world_matrix @ vertex.co
        other_world = world_matrix @ other.co
        return safe_normalized(other_world - vertex_world)

    # pairing[vertex][edge] = the edge that continues through the vertex.
    pairing = {}

    for vertex, incident_edges in graph.items():
        remaining = list(incident_edges)
        vertex_pairs = {}

        while len(remaining) >= 2:
            best_pair = None
            best_score = 1.0

            for i, edge_a in enumerate(remaining[:-1]):
                direction_a = edge_direction_away(edge_a, vertex)

                for edge_b in remaining[i + 1:]:
                    direction_b = edge_direction_away(edge_b, vertex)

                    # Opposite outward directions mean a straight continuation.
                    score = direction_a.dot(direction_b)

                    if score < best_score:
                        best_score = score
                        best_pair = (edge_a, edge_b)

            if best_pair is None:
                break

            edge_a, edge_b = best_pair
            vertex_pairs[edge_a] = edge_b
            vertex_pairs[edge_b] = edge_a
            remaining.remove(edge_a)
            remaining.remove(edge_b)

        pairing[vertex] = vertex_pairs

    unvisited = set(selected_edges)
    chains = []

    def paired_next(vertex, incoming_edge):
        return pairing.get(vertex, {}).get(incoming_edge)

    def walk(start_vertex, start_edge):
        chain_vertices = [start_vertex]
        chain_edges = []
        current_vertex = start_vertex
        current_edge = start_edge

        while current_edge in unvisited:
            unvisited.remove(current_edge)
            chain_edges.append(current_edge)

            v0, v1 = current_edge.verts
            next_vertex = v1 if current_vertex == v0 else v0
            chain_vertices.append(next_vertex)

            next_edge = paired_next(next_vertex, current_edge)
            if next_edge is None or next_edge not in unvisited:
                break

            current_vertex = next_vertex
            current_edge = next_edge

        return chain_vertices, chain_edges

    # Start from unpaired ends first.
    for vertex, incident_edges in graph.items():
        for edge in incident_edges:
            if edge not in unvisited:
                continue

            if paired_next(vertex, edge) is None:
                verts, edges = walk(vertex, edge)
                if edges:
                    chains.append((verts, edges, False))

    # Remaining components are closed paired loops.
    while unvisited:
        start_edge = next(iter(unvisited))
        start_vertex = start_edge.verts[0]
        verts, edges = walk(start_vertex, start_edge)

        closed = (
            len(verts) > 2
            and verts[-1] == verts[0]
        )

        if closed:
            verts = verts[:-1]

        if edges:
            chains.append((verts, edges, closed))

    return chains


def topological_edge_loop_continuation(current_edge, vertex):
    """Return the unique continuation through a quad grid or strip border.

    A Blender-style edge loop continues through a four-edge vertex along the
    one incident edge that does not share either adjacent quad with the current
    edge. A quad strip may also border an n-gon, as on an arch cut into one
    large front face. In that case the border vertices normally have valence
    three: exclude the edge inside the quad strip and continue along the one
    remaining manifold border edge. Ambiguous poles and branches still stop.
    """
    if (
        current_edge is None
        or current_edge.hide
        or len(current_edge.link_faces) != 2
        or vertex not in current_edge.verts
    ):
        return None

    quad_faces = [
        face
        for face in current_edge.link_faces
        if len(face.verts) == 4
    ]
    if not quad_faces:
        return None

    adjacent_in_quads = set()
    for face in quad_faces:
        for candidate in face.edges:
            if candidate != current_edge and vertex in candidate.verts:
                adjacent_in_quads.add(candidate)

    candidates = [
        edge
        for edge in vertex.link_edges
        if (
            edge != current_edge
            and edge not in adjacent_in_quads
            and not edge.hide
            and len(edge.link_faces) == 2
        )
    ]
    return candidates[0] if len(candidates) == 1 else None


def walk_topological_edge_loop(bm, start_edge_index):
    """Return the manifold quad edge loop containing ``start_edge_index``."""
    bm.edges.ensure_lookup_table()
    if not (0 <= start_edge_index < len(bm.edges)):
        return []

    start_edge = bm.edges[start_edge_index]
    if start_edge.hide or len(start_edge.link_faces) != 2:
        return [start_edge_index]

    visited = {start_edge}

    def walk_from(start_vertex):
        current_edge = start_edge
        current_vertex = start_vertex
        while True:
            next_edge = topological_edge_loop_continuation(
                current_edge,
                current_vertex,
            )
            if next_edge is None or next_edge in visited:
                break
            visited.add(next_edge)
            current_vertex = next_edge.other_vert(current_vertex)
            current_edge = next_edge

    walk_from(start_edge.verts[0])
    walk_from(start_edge.verts[1])
    return sorted(edge.index for edge in visited)


def expand_automatic_edge_loop_seeds(bm, seed_edge_indices):
    """Expand strict angle seeds along only their quad-topology edge loops.

    This is intentionally different from lowering the global angle threshold:
    parallel low-angle loops without a qualifying seed remain excluded.
    """
    bm.edges.ensure_lookup_table()
    expanded = set()

    for edge_index in seed_edge_indices or ():
        try:
            edge_index = int(edge_index)
        except (TypeError, ValueError):
            continue
        if not (0 <= edge_index < len(bm.edges)):
            continue
        edge = bm.edges[edge_index]
        if edge.hide or len(edge.link_faces) != 2:
            continue
        expanded.update(walk_topological_edge_loop(bm, edge_index))

    return sorted(expanded)


def filter_automatic_edges_by_angle(
    bm,
    minimum_face_angle,
    candidate_edge_indices=None,
):
    """Return visible manifold candidates that satisfy Auto Edge Angle.

    Loop expansion is allowed to discover topology, but it must never turn a
    qualifying seed into permission to generate on softer or coplanar edges.
    Keeping this as the final automatic-selection gate makes the UI threshold
    an invariant even when Auto Follow Edge Loops is enabled.
    """
    bm.edges.ensure_lookup_table()
    threshold = max(0.0, min(pi, float(minimum_face_angle)))
    candidates = (
        range(len(bm.edges))
        if candidate_edge_indices is None
        else candidate_edge_indices
    )
    qualified = set()

    for edge_index in candidates:
        try:
            edge_index = int(edge_index)
        except (TypeError, ValueError):
            continue
        if not (0 <= edge_index < len(bm.edges)):
            continue
        edge = bm.edges[edge_index]
        if edge.hide or len(edge.link_faces) != 2:
            continue
        try:
            face_angle = edge.calc_face_angle(0.0)
        except ValueError:
            continue
        if face_angle >= threshold:
            qualified.add(edge_index)

    return sorted(qualified)


def traversal_turn_angle(point_before, shared_point, point_after):
    """
    Return the path's direction-change angle in radians.

    A straight continuation is 0 degrees. A right-angle turn is 90 degrees.
    """
    incoming = safe_normalized(shared_point - point_before)
    outgoing = safe_normalized(point_after - shared_point)

    dot_value = max(-1.0, min(1.0, incoming.dot(outgoing)))
    return acos(dot_value)


def screen_distance_to_segment(point, segment_start, segment_end):
    """Return the 2D distance from point to a screen-space segment."""
    segment = segment_end - segment_start
    segment_length_squared = segment.length_squared

    if segment_length_squared <= EPSILON:
        return (point - segment_start).length

    factor = (point - segment_start).dot(segment) / segment_length_squared
    factor = max(0.0, min(1.0, factor))
    closest = segment_start + segment * factor
    return (point - closest).length


def split_chain_by_angle(chain_verts, chain_edges, closed, world_matrix, split_angle):
    """
    Split an ordered source chain into connected subchains whenever the path
    direction changes more than split_angle.

    The returned subchains are independent mesh islands, but all islands are
    later written into the same generated Blender object.
    """
    edge_count = len(chain_edges)

    if edge_count <= 1:
        return [(chain_verts, chain_edges, False if not closed else closed)]

    world_points = [world_matrix @ vert.co for vert in chain_verts]

    if not closed:
        split_vertices = []

        for vertex_index in range(1, len(chain_verts) - 1):
            angle = traversal_turn_angle(
                world_points[vertex_index - 1],
                world_points[vertex_index],
                world_points[vertex_index + 1],
            )

            if angle > split_angle:
                split_vertices.append(vertex_index)

        if not split_vertices:
            return [(chain_verts, chain_edges, False)]

        result = []
        start_vertex = 0

        for split_vertex in split_vertices:
            sub_verts = chain_verts[start_vertex:split_vertex + 1]
            sub_edges = chain_edges[start_vertex:split_vertex]

            if sub_edges:
                result.append((sub_verts, sub_edges, False))

            start_vertex = split_vertex

        sub_verts = chain_verts[start_vertex:]
        sub_edges = chain_edges[start_vertex:]

        if sub_edges:
            result.append((sub_verts, sub_edges, False))

        return result

    # Closed loop: test every vertex, including the seam between last and first.
    break_indices = []

    for vertex_index in range(len(chain_verts)):
        previous_index = (vertex_index - 1) % len(chain_verts)
        next_index = (vertex_index + 1) % len(chain_verts)

        angle = traversal_turn_angle(
            world_points[previous_index],
            world_points[vertex_index],
            world_points[next_index],
        )

        if angle > split_angle:
            break_indices.append(vertex_index)

    if not break_indices:
        return [(chain_verts, chain_edges, True)]

    result = []
    break_indices = sorted(set(break_indices))

    for break_list_index, start_vertex in enumerate(break_indices):
        end_vertex = break_indices[(break_list_index + 1) % len(break_indices)]

        sub_verts = [chain_verts[start_vertex]]
        sub_edges = []
        current_vertex = start_vertex

        while current_vertex != end_vertex:
            edge_index = current_vertex
            sub_edges.append(chain_edges[edge_index])

            current_vertex = (current_vertex + 1) % len(chain_verts)
            sub_verts.append(chain_verts[current_vertex])

        if sub_edges:
            result.append((sub_verts, sub_edges, False))

    return result


def edge_surface_bend_class(
    edge,
    world_matrix,
    normal_matrix,
    flat_angle=1.0e-4,
):
    """Return -1 for concave, 0 for flat, and 1 for convex edges."""
    if len(edge.link_faces) != 2:
        return 0

    normal_a = transform_normal(normal_matrix, edge.link_faces[0].normal)
    normal_b = transform_normal(normal_matrix, edge.link_faces[1].normal)
    angle = acos(max(-1.0, min(1.0, normal_a.dot(normal_b))))

    if angle <= flat_angle:
        return 0

    try:
        return 1 if edge.is_convex else -1
    except (AttributeError, RuntimeError):
        return 0


def extract_edge_chains_by_surface_bend(
    selected_edges,
    world_matrix,
    normal_matrix,
):
    """Extract convex, concave, and flat paths as independent chains.

    Partitioning before path pairing is the only topology intervention: it
    prevents opposite bends from being joined without changing the proven
    27.227.2 strip builder or manufacturing extra endpoint geometry.
    """
    grouped_edges = {-1: [], 0: [], 1: []}

    for edge in selected_edges:
        grouped_edges[
            edge_surface_bend_class(edge, world_matrix, normal_matrix)
        ].append(edge)

    chains = []
    for bend_class in (-1, 0, 1):
        if grouped_edges[bend_class]:
            chains.extend(
                extract_edge_chains(grouped_edges[bend_class], world_matrix)
            )

    return chains


def extract_cached_edge_chains_by_surface_bend(
    work_bmesh,
    selected_edges,
    world_matrix,
    normal_matrix,
    cache_key=None,
):
    """Reuse chain topology while rebuilding decal positions."""
    entry = (
        EDGEDECAL_PREPARED_SOURCE_CACHE.get(cache_key)
        if cache_key is not None
        else None
    )
    if entry is None:
        return extract_edge_chains_by_surface_bend(
            selected_edges,
            world_matrix,
            normal_matrix,
        )

    work_bmesh.verts.ensure_lookup_table()
    work_bmesh.edges.ensure_lookup_table()
    work_bmesh.verts.index_update()
    work_bmesh.edges.index_update()
    chain_key = (
        tuple(sorted(int(edge.index) for edge in selected_edges)),
        _cache_matrix_signature(world_matrix),
    )
    cached_chains = entry["chains"].get(chain_key)
    if cached_chains is not None:
        try:
            result = [
                (
                    [work_bmesh.verts[index] for index in vert_indices],
                    [work_bmesh.edges[index] for index in edge_indices],
                    bool(closed),
                )
                for vert_indices, edge_indices, closed in cached_chains
            ]
            EDGEDECAL_PREPARED_SOURCE_CACHE_STATS["chain_hits"] += 1
            return result
        except (IndexError, ReferenceError):
            entry["chains"].pop(chain_key, None)

    EDGEDECAL_PREPARED_SOURCE_CACHE_STATS["chain_misses"] += 1
    result = extract_edge_chains_by_surface_bend(
        selected_edges,
        world_matrix,
        normal_matrix,
    )
    entry["chains"][chain_key] = tuple(
        (
            tuple(int(vert.index) for vert in chain_verts),
            tuple(int(edge.index) for edge in chain_edges),
            bool(closed),
        )
        for chain_verts, chain_edges, closed in result
    )
    return result


def build_limited_dissolve_generation_bmesh(
    source_bmesh,
    angle_limit=radians(5.0),
    apply_limited_dissolve=True,
    cache_source=None,
    use_cache=False,
):
    """Return a non-destructive generation copy and source-edge mapping.

    When enabled, every vertex and edge is submitted to the same five-degree
    cleanup pass, including selected decal paths. Authored seam, sharp,
    material, and UV boundaries remain delimiters. Interactive generation can
    disable the pass and operate on an unchanged topology copy. The returned
    original-index mapping stays attached to surviving edge objects even after
    indices are compacted.
    """
    cache_key = (
        prepared_source_cache_key(
            cache_source,
            angle_limit,
            apply_limited_dissolve,
        )
        if use_cache
        else None
    )
    cached_entry = (
        EDGEDECAL_PREPARED_SOURCE_CACHE.get(cache_key)
        if cache_key is not None
        else None
    )
    cached_bmesh = (
        cached_entry.get("bmesh")
        if cached_entry is not None
        else None
    )
    if cached_bmesh is not None and cached_bmesh.is_valid:
        work_bmesh = cached_bmesh.copy()
        work_bmesh.verts.ensure_lookup_table()
        work_bmesh.edges.ensure_lookup_table()
        work_bmesh.faces.ensure_lookup_table()
        work_bmesh.verts.index_update()
        work_bmesh.edges.index_update()
        work_bmesh.faces.index_update()
        original_layer = work_bmesh.edges.layers.int.get(
            "edge_decal_original_index"
        )
        original_index_by_edge = {
            edge: int(edge[original_layer]) - 1
            for edge in work_bmesh.edges
            if original_layer is not None and int(edge[original_layer]) > 0
        }
        EDGEDECAL_PREPARED_SOURCE_CACHE_STATS["prepared_hits"] += 1
        return work_bmesh, original_index_by_edge

    if cache_key is not None:
        EDGEDECAL_PREPARED_SOURCE_CACHE_STATS["prepared_misses"] += 1

    source_bmesh.verts.ensure_lookup_table()
    source_bmesh.edges.ensure_lookup_table()
    source_bmesh.faces.ensure_lookup_table()

    work_bmesh = source_bmesh.copy()
    work_bmesh.normal_update()
    work_bmesh.verts.ensure_lookup_table()
    work_bmesh.edges.ensure_lookup_table()
    work_bmesh.faces.ensure_lookup_table()

    original_layer = None
    if cache_key is not None:
        original_layer = work_bmesh.edges.layers.int.new(
            "edge_decal_original_index"
        )
        for edge in work_bmesh.edges:
            edge[original_layer] = int(edge.index) + 1

    original_index_by_edge = {
        edge: edge.index
        for edge in work_bmesh.edges
    }
    dissolve_candidates = list(work_bmesh.edges)

    if apply_limited_dissolve and dissolve_candidates:
        bmesh.ops.dissolve_limit(
            work_bmesh,
            angle_limit=max(0.0, float(angle_limit)),
            use_dissolve_boundaries=False,
            verts=list(work_bmesh.verts),
            edges=dissolve_candidates,
            delimit={"MATERIAL", "SEAM", "SHARP", "UV"},
        )

    work_bmesh.normal_update()
    work_bmesh.verts.ensure_lookup_table()
    work_bmesh.edges.ensure_lookup_table()
    work_bmesh.faces.ensure_lookup_table()

    if cache_key is not None:
        # BMElement hashes can depend on their compacted index. Persist the
        # source mapping before index_update(), then rebuild the dictionary
        # afterward so its keys remain usable by the generation pass.
        work_bmesh.verts.index_update()
        work_bmesh.edges.index_update()
        work_bmesh.faces.index_update()
        original_index_by_edge = {
            edge: int(edge[original_layer]) - 1
            for edge in work_bmesh.edges
            if int(edge[original_layer]) > 0
        }

        previous_entry = EDGEDECAL_PREPARED_SOURCE_CACHE.pop(cache_key, None)
        previous_bmesh = (
            previous_entry.get("bmesh")
            if previous_entry is not None
            else None
        )
        if previous_bmesh is not None and previous_bmesh.is_valid:
            previous_bmesh.free()
        EDGEDECAL_PREPARED_SOURCE_CACHE[cache_key] = {
            "bmesh": work_bmesh.copy(),
            "chains": {},
            "source_signature": (
                None
                if cache_source.data.is_editmode
                else source_mesh_prepared_cache_signature(cache_source.data)
            ),
        }

    return work_bmesh, original_index_by_edge


def transform_normal(normal_matrix, normal):
    return safe_normalized(normal_matrix @ normal, Vector((0.0, 0.0, 1.0)))


def face_inward_direction(face, edge, world_matrix, normal_matrix, tangent):
    """
    Return the direction from the edge into this face.

    This uses the face-loop winding rather than the face center. Face-center
    tests are unreliable on concave or long n-gons and can flip the offset to
    the wrong side, producing spikes and crossed strip geometry.
    """
    face_normal_world = transform_normal(normal_matrix, face.normal)

    matching_loop = None
    for loop in face.loops:
        if loop.edge == edge:
            matching_loop = loop
            break

    if matching_loop is None:
        fallback = face_normal_world.cross(tangent)
        return safe_normalized(fallback, Vector((1.0, 0.0, 0.0)))

    loop_start_local = matching_loop.vert.co
    loop_end_local = matching_loop.link_loop_next.vert.co

    loop_start_world = world_matrix @ loop_start_local
    loop_end_world = world_matrix @ loop_end_local
    loop_direction = safe_normalized(
        loop_end_world - loop_start_world,
        tangent,
    )

    # For a consistently wound face, the interior lies to the left of the
    # directed boundary edge when viewed from the face normal.
    inward = face_normal_world.cross(loop_direction)

    # Keep the result exactly in the face plane.
    inward -= face_normal_world * inward.dot(face_normal_world)

    return safe_normalized(
        inward,
        face_normal_world.cross(tangent),
    )



def faces_are_coplanar(face_a, face_b, normal_tolerance=0.9999):
    """
    Treat topology-split faces as one support surface when they share a vertex
    and their normals are effectively identical.

    This prevents a straight edge from being broken merely because an
    unrelated edge loop divides the surrounding flat surface into more faces.
    """
    return face_a.normal.dot(face_b.normal) >= normal_tolerance


def assign_face_sides(face_data, previous_pair=None):
    """
    Keep side A/B stable along a chain.

    Matching the actual source face is weighted much more strongly than merely
    comparing normals. This prevents the two sides from swapping when nearby
    faces have similar orientations.
    """
    if previous_pair is None:
        return face_data[0], face_data[1]

    a0, a1 = face_data
    p0, p1 = previous_pair

    direct_score = (
        (
            10.0
            if (
                a0["face"] == p0["face"]
                or faces_are_coplanar(a0["face"], p0["face"])
            )
            else 0.0
        )
        + (
            10.0
            if (
                a1["face"] == p1["face"]
                or faces_are_coplanar(a1["face"], p1["face"])
            )
            else 0.0
        )
        + a0["normal"].dot(p0["normal"])
        + a1["normal"].dot(p1["normal"])
    )

    swapped_score = (
        (
            10.0
            if (
                a1["face"] == p0["face"]
                or faces_are_coplanar(a1["face"], p0["face"])
            )
            else 0.0
        )
        + (
            10.0
            if (
                a0["face"] == p1["face"]
                or faces_are_coplanar(a0["face"], p1["face"])
            )
            else 0.0
        )
        + a1["normal"].dot(p0["normal"])
        + a0["normal"].dot(p1["normal"])
    )

    if swapped_score > direct_score:
        return a1, a0

    return a0, a1


def oriented_face_with_uvs(indices, uvs, vertices, target_normal):
    """Orient a generated face and keep its UV loop order in sync.

    Blender stores UV coordinates per face loop. Reversing only the vertex
    order changes which UV belongs to each corner and can fold or fan an island,
    especially after Decal Amount trims a chain and changes face orientation.
    """
    indices = tuple(indices)
    uvs = tuple(uvs)
    p0 = vertices[indices[0]]
    p1 = vertices[indices[1]]
    p2 = vertices[indices[2]]
    polygon_normal = (p1 - p0).cross(p2 - p0)

    if polygon_normal.dot(target_normal) < 0.0:
        return tuple(reversed(indices)), tuple(reversed(uvs))

    return indices, uvs


def oriented_quad(indices, vertices, target_normal):
    # Kept for compatibility with any external/internal callers that only need
    # geometry orientation. New decal builders must use oriented_face_with_uvs.
    oriented_indices, _ = oriented_face_with_uvs(
        indices,
        tuple((0.0, 0.0) for _ in indices),
        vertices,
        target_normal,
    )
    return oriented_indices



def ray_segment_distance_in_plane(
    ray_origin,
    ray_direction,
    segment_start,
    segment_end,
    plane_normal,
):
    """
    Return the positive distance from a ray to a segment in one plane.

    Returns None when the lines are parallel, the intersection lies behind
    the ray, or the intersection falls outside the segment.
    """
    direction = safe_normalized(ray_direction)
    segment = segment_end - segment_start
    normal = safe_normalized(plane_normal)

    denominator = normal.dot(direction.cross(segment))

    if abs(denominator) <= EPSILON:
        return None

    delta = segment_start - ray_origin
    ray_distance = normal.dot(delta.cross(segment)) / denominator
    segment_factor = normal.dot(delta.cross(direction)) / denominator

    if ray_distance <= 1.0e-6:
        return None

    if segment_factor < -1.0e-6 or segment_factor > 1.0 + 1.0e-6:
        return None

    return ray_distance


def _spatial_cell_index(value, inv_cell_size):
    scaled = value * inv_cell_size
    cell = int(scaled)
    if scaled < 0.0 and scaled != cell:
        cell -= 1
    return cell


def _segment_point_distance_sq(point, seg_start, seg_end):
    segment = seg_end - seg_start
    length_sq = segment.length_squared
    if length_sq <= EPSILON:
        delta = point - seg_start
        return delta.length_squared

    factor = max(
        0.0,
        min(1.0, (point - seg_start).dot(segment) / length_sq),
    )
    closest = seg_start + segment * factor
    delta = point - closest
    return delta.length_squared


def build_adaptive_width_search_context(
    all_source_edges,
    selected_edge_set,
    world_matrix,
    clamp_boundaries,
    clamp_selected_overlaps,
    search_radius,
):
    """
    Precompute world-space clamp candidates and a coarse 3D grid index.

    Adaptive width previously scanned every mesh edge for every generated
    segment side. On dense auto-generated selections that becomes
    O(segments × mesh_edges). The index limits each sample to nearby edges.
    """
    if not clamp_boundaries and not clamp_selected_overlaps:
        return None

    search_radius = max(float(search_radius), 1.0e-5)
    cell_size = search_radius
    inv_cell_size = 1.0 / cell_size
    search_radius_sq = search_radius * search_radius
    entries = []
    seen = set()
    grid = {}

    # A selected path must never compete with another segment of itself. The
    # old test excluded only edges that shared an immediate vertex, so a ray
    # from a short curved segment could hit the next-but-one segment of the
    # same arch/loop. Those false hits produced rapidly alternating widths and
    # the graph miter solver stretched them into long spikes. Use the same
    # straightest-continuation paths as strip extraction instead of broad
    # connected components: automatic sharp-edge graphs often connect front,
    # back, opening, and depth paths at corners, but those distinct paths still
    # need to clamp against one another.
    selected = set(selected_edge_set or ())
    selected_path_by_edge = {}
    selected_local_path_edges = {}
    for path_index, (_verts, path_edges, path_closed) in enumerate(
        extract_edge_chains(selected, world_matrix)
    ):
        edge_lengths = []
        for path_edge in path_edges:
            selected_path_by_edge[path_edge] = path_index
            path_start = world_matrix @ path_edge.verts[0].co
            path_end = world_matrix @ path_edge.verts[1].co
            edge_lengths.append((path_end - path_start).length)

        # Ignore only the nearby portion of the same stroke. Curved segments
        # within one requested width are part of the local offset construction
        # and must not clamp one another. Remote portions of the same path can
        # still approach and overlap (for example the two legs of a U), so an
        # entire-path exclusion is incorrect.
        edge_centers = []
        distance = 0.0
        for edge_length in edge_lengths:
            edge_centers.append(distance + edge_length * 0.5)
            distance += edge_length
        total_length = distance
        for edge_index, path_edge in enumerate(path_edges):
            local_edges = set()
            for candidate_index, candidate_edge in enumerate(path_edges):
                path_distance = abs(
                    edge_centers[edge_index] - edge_centers[candidate_index]
                )
                if path_closed and total_length > EPSILON:
                    path_distance = min(
                        path_distance,
                        total_length - path_distance,
                    )
                if path_distance <= search_radius + EPSILON:
                    local_edges.add(candidate_edge)
            selected_local_path_edges[path_edge] = local_edges

    def add_edge(edge, is_selected):
        edge_index = edge.index
        if edge_index in seen:
            return

        seen.add(edge_index)
        p0 = world_matrix @ edge.verts[0].co
        p1 = world_matrix @ edge.verts[1].co
        entry = {
            "edge": edge,
            "p0": p0,
            "p1": p1,
            "is_selected": is_selected,
            "verts": frozenset(edge.verts),
            "selected_path": selected_path_by_edge.get(edge),
        }
        entries.append(entry)

        bounds_min = Vector((
            min(p0.x, p1.x) - search_radius,
            min(p0.y, p1.y) - search_radius,
            min(p0.z, p1.z) - search_radius,
        ))
        bounds_max = Vector((
            max(p0.x, p1.x) + search_radius,
            max(p0.y, p1.y) + search_radius,
            max(p0.z, p1.z) + search_radius,
        ))
        i0 = _spatial_cell_index(bounds_min.x, inv_cell_size)
        j0 = _spatial_cell_index(bounds_min.y, inv_cell_size)
        k0 = _spatial_cell_index(bounds_min.z, inv_cell_size)
        i1 = _spatial_cell_index(bounds_max.x, inv_cell_size)
        j1 = _spatial_cell_index(bounds_max.y, inv_cell_size)
        k1 = _spatial_cell_index(bounds_max.z, inv_cell_size)

        for cell_i in range(i0, i1 + 1):
            for cell_j in range(j0, j1 + 1):
                for cell_k in range(k0, k1 + 1):
                    grid.setdefault(
                        (cell_i, cell_j, cell_k),
                        [],
                    ).append(entry)

    if clamp_boundaries:
        for candidate_edge in all_source_edges or ():
            add_edge(candidate_edge, candidate_edge in selected)

    if clamp_selected_overlaps:
        for candidate_edge in selected:
            add_edge(candidate_edge, True)

    if not entries:
        return None

    return {
        "grid": grid,
        "inv_cell_size": inv_cell_size,
        "search_radius_sq": search_radius_sq,
        "selected_path_by_edge": selected_path_by_edge,
        "selected_local_path_edges": selected_local_path_edges,
    }


def _adaptive_width_nearby_entries(width_search_context, sample_point):
    if width_search_context is None:
        return None

    inv_cell_size = width_search_context["inv_cell_size"]
    search_radius_sq = width_search_context["search_radius_sq"]
    grid = width_search_context["grid"]
    cell_i = _spatial_cell_index(sample_point.x, inv_cell_size)
    cell_j = _spatial_cell_index(sample_point.y, inv_cell_size)
    cell_k = _spatial_cell_index(sample_point.z, inv_cell_size)

    nearby = []
    seen = set()

    # Every entry is inserted into all cells touched by its segment AABB after
    # that AABB is expanded by the search radius. Therefore every segment that
    # can be within range of this point is already present in the point's own
    # cell; searching the 26 neighboring cells only repeats candidates.
    for entry in grid.get((cell_i, cell_j, cell_k), ()):
        edge_index = entry["edge"].index
        if edge_index in seen:
            continue

        # Mark the entry before the exact distance test so an out-of-range
        # duplicate can never trigger another relatively expensive test.
        seen.add(edge_index)

        if (
            _segment_point_distance_sq(
                sample_point,
                entry["p0"],
                entry["p1"],
            )
            > search_radius_sq
        ):
            continue

        nearby.append(entry)

    return nearby


def adaptive_width_for_edge_side(
    edge,
    side,
    tangent,
    requested_width,
    clearance,
    sample_count,
    selected_edge_set,
    all_source_edges,
    world_matrix,
    clamp_boundaries=True,
    clamp_selected_overlaps=False,
    overlap_clearance=0.98,
    width_search_context=None,
):
    """
    Clamp one edge side independently to the free space on its support plane.

    Non-selected mesh edges behave as hard boundaries and use ``clearance``.
    Other selected decal edges use half of the available gap because both
    strips can grow toward one another. This makes only the affected segment
    stop increasing while wider, unobstructed segments keep the requested
    width.
    """
    if requested_width <= EPSILON:
        return requested_width

    if not clamp_boundaries and not clamp_selected_overlaps:
        return requested_width

    p0 = world_matrix @ edge.verts[0].co
    p1 = world_matrix @ edge.verts[1].co
    face_normal = safe_normalized(side["normal"])
    inward = safe_normalized(side["inward"])

    nearest_safe_width = None
    plane_tolerance = max(1.0e-5, requested_width * 1.0e-4)

    sample_sets = {
        1: (0.5,),
        2: (0.25, 0.75),
        3: (0.15, 0.5, 0.85),
        4: (0.1, 0.35, 0.65, 0.9),
        5: (0.08, 0.25, 0.5, 0.75, 0.92),
    }
    sample_factors = sample_sets.get(
        max(1, min(5, int(sample_count))),
        sample_sets[3],
    )

    edge_vertices = set(edge.verts)
    use_spatial_index = width_search_context is not None
    current_selected_path = (
        width_search_context.get("selected_path_by_edge", {}).get(edge)
        if use_spatial_index
        else None
    )

    for factor in sample_factors:
        sample_point = p0.lerp(p1, factor)

        if use_spatial_index:
            candidate_entries = _adaptive_width_nearby_entries(
                width_search_context,
                sample_point,
            )
        else:
            candidates = set()
            if clamp_boundaries:
                candidates.update(all_source_edges)
            if clamp_selected_overlaps:
                candidates.update(selected_edge_set)
            candidate_entries = [
                {
                    "edge": candidate,
                    "p0": world_matrix @ candidate.verts[0].co,
                    "p1": world_matrix @ candidate.verts[1].co,
                    "is_selected": candidate in selected_edge_set,
                    "verts": frozenset(candidate.verts),
                    "selected_path": None,
                }
                for candidate in candidates
            ]

        for entry in candidate_entries:
            candidate = entry["edge"]
            if candidate == edge:
                continue

            candidate_is_selected = entry["is_selected"]

            if candidate_is_selected:
                if not clamp_selected_overlaps:
                    continue

                # Connected selected edges belong to the same path/corner and
                # should be solved by the miter system rather than clamped.
                if edge_vertices.intersection(entry["verts"]):
                    continue

                # Nearby segments on the same stroke are part of its local
                # curve construction. Remote segments on that same stroke are
                # real collision candidates and must remain active.
                candidate_path = entry.get("selected_path")
                if (
                    current_selected_path is not None
                    and candidate_path == current_selected_path
                    and candidate in width_search_context.get(
                        "selected_local_path_edges", {}
                    ).get(edge, ())
                ):
                    continue
            elif not clamp_boundaries:
                continue

            candidate_start = entry["p0"]
            candidate_end = entry["p1"]

            # Only consider edges lying on the same support plane.
            if abs(face_normal.dot(candidate_start - sample_point)) > plane_tolerance:
                continue
            if abs(face_normal.dot(candidate_end - sample_point)) > plane_tolerance:
                continue

            distance = ray_segment_distance_in_plane(
                sample_point,
                inward,
                candidate_start,
                candidate_end,
                face_normal,
            )

            if distance is None:
                continue

            if candidate_is_selected:
                # Two strips share the gap, so each gets at most half. The
                # clearance leaves a small stable gap and avoids z-fighting.
                safe_width = distance * 0.5 * overlap_clearance
            else:
                safe_width = distance * clearance

            if (
                nearest_safe_width is None
                or safe_width < nearest_safe_width
            ):
                nearest_safe_width = safe_width

    if nearest_safe_width is None:
        return requested_width

    return max(
        1.0e-5,
        min(requested_width, nearest_safe_width),
    )


def stabilize_width_sequence(widths, edge_lengths, closed, maximum_slope=1.0):
    """Return a conservative distance-based envelope for path side widths.

    Every raw clamp result remains an upper bound. Width may recover away from
    a narrow obstacle only by ``maximum_slope`` units per world-space unit of
    path length. This prevents short tessellated segments from alternating
    between a narrow clamp and the full requested width, which creates invalid
    graph miters and long triangular-looking quads.
    """
    widths = [max(1.0e-5, float(width)) for width in widths]
    count = len(widths)
    if count < 2:
        return widths

    lengths = [max(0.0, float(length)) for length in edge_lengths]

    def center_distance(index_a, index_b):
        return max(
            1.0e-6,
            (lengths[index_a] + lengths[index_b]) * 0.5,
        )

    stabilized = list(widths)
    passes = count if closed else 1
    for _pass in range(passes):
        changed = False
        pair_count = count if closed else count - 1
        for index in range(pair_count):
            following = (index + 1) % count
            distance = center_distance(index, following)
            allowed = stabilized[index] + distance * maximum_slope
            if stabilized[following] > allowed + EPSILON:
                stabilized[following] = allowed
                changed = True
        for index in range(pair_count - 1, -1, -1):
            following = (index + 1) % count
            distance = center_distance(index, following)
            allowed = stabilized[following] + distance * maximum_slope
            if stabilized[index] > allowed + EPSILON:
                stabilized[index] = allowed
                changed = True
        if not changed:
            break
    return stabilized


def stabilize_selected_graph_overlap_widths(
    edge_data,
    selected_edges,
    world_matrix,
):
    """Build a continuous local-width field over the selected curve graph.

    Each edge/face slot starts with its own collision-safe width.  Neighboring
    slots share one authored outer vertex, so their widths are coupled by a
    distance-based Lipschitz constraint rather than collapsed to the global
    minimum.  This preserves local maximum width while preventing alternating
    narrow/wide edges from producing crossed miters or disconnected rails.
    """
    selected_edge_set = set(selected_edges)
    slots = {
        (edge, face)
        for edge in selected_edge_set
        for face in edge.link_faces
        if edge in edge_data and face in edge_data[edge]["sides"]
    }
    adjacency = {slot: set() for slot in slots}
    for source_vertex in {
        vertex for edge in selected_edge_set for vertex in edge.verts
    }:
        incident_faces = list(source_vertex.link_faces)
        face_adjacency = {face: set() for face in incident_faces}
        for radial_edge in source_vertex.link_edges:
            if radial_edge in selected_edge_set:
                continue
            radial_faces = [
                face for face in radial_edge.link_faces
                if face in face_adjacency
            ]
            for face_a in radial_faces:
                for face_b in radial_faces:
                    if face_a is not face_b:
                        face_adjacency[face_a].add(face_b)

        remaining_faces = set(incident_faces)
        face_components = []
        while remaining_faces:
            seed_face = remaining_faces.pop()
            face_component = {seed_face}
            pending_faces = [seed_face]
            while pending_faces:
                current_face = pending_faces.pop()
                for neighbor_face in face_adjacency[current_face]:
                    if neighbor_face not in remaining_faces:
                        continue
                    remaining_faces.remove(neighbor_face)
                    face_component.add(neighbor_face)
                    pending_faces.append(neighbor_face)
            face_components.append(face_component)

        # Match the exact surface-sector connectivity used later to share
        # graph miter vertices. This includes smoothly bent face fans, not just
        # coplanar faces; if two slots share one outer point they must also
        # share one width or the intervening edge becomes a visible taper.
        for face_component in face_components:
            vertex_slots = [
                (edge, face)
                for edge in source_vertex.link_edges
                if edge in selected_edge_set and edge in edge_data
                for face in edge.link_faces
                if (
                    face in face_component
                    and (edge, face) in slots
                )
            ]
            for index, slot_a in enumerate(vertex_slots[:-1]):
                for slot_b in vertex_slots[index + 1:]:
                    if slot_a[0] == slot_b[0]:
                        continue
                    adjacency[slot_a].add(slot_b)
                    adjacency[slot_b].add(slot_a)

    # First apply a local cap for the longitudinal space consumed by endpoint
    # miters.  This is per slot; a short corner no longer narrows an entire arch
    # or loop several meters away.
    widths = {
        slot: max(
            1.0e-5,
            float(edge_data[slot[0]]["sides"][slot[1]]["width"]),
        )
        for slot in slots
    }
    for edge, face in slots:
        data = edge_data[edge]
        side = data["sides"][face]
        consumption = 0.0
        for source_vertex in edge.verts:
            neighbors = [
                neighbor
                for neighbor in adjacency[(edge, face)]
                if source_vertex in neighbor[0].verts
            ]
            if len(neighbors) != 1:
                continue
            neighbor_edge, neighbor_face = neighbors[0]
            neighbor_side = edge_data[neighbor_edge]["sides"][neighbor_face]
            origin = world_matrix @ source_vertex.co
            current_tangent = safe_normalized(
                (world_matrix @ edge.other_vert(source_vertex).co) - origin,
                data["tangent"],
            )
            neighbor_tangent = safe_normalized(
                (
                    world_matrix
                    @ neighbor_edge.other_vert(source_vertex).co
                ) - origin,
                edge_data[neighbor_edge]["tangent"],
            )
            unit_miter = planar_line_intersection(
                origin,
                current_tangent,
                neighbor_tangent,
                side["inward"],
                neighbor_side["inward"],
                side["normal"],
                1.0,
                1.0,
                1.0e6,
            )
            consumption += max(
                0.0,
                (unit_miter - origin).dot(current_tangent),
            )
        if consumption > EPSILON:
            widths[(edge, face)] = min(
                widths[(edge, face)],
                data["length"] * 0.9 / consumption,
            )

    # Compute the greatest field below those local caps whose change along a
    # path is bounded. Repeated relaxation is a graph form of the conservative
    # forward/backward envelope used for ordered chains, and also works at
    # branches without choosing an arbitrary continuation.
    maximum_slope = 0.75
    ordered_links = sorted(
        {
            tuple(sorted(
                (slot, neighbor),
                key=lambda item: (item[0].index, item[1].index),
            ))
            for slot in slots
            for neighbor in adjacency[slot]
            if slot != neighbor
        },
        key=lambda pair: (
            pair[0][0].index,
            pair[0][1].index,
            pair[1][0].index,
            pair[1][1].index,
        ),
    )
    for _pass in range(max(1, len(slots))):
        changed = False
        for first, second in ordered_links:
            travel = max(
                1.0e-6,
                (
                    edge_data[first[0]]["length"]
                    + edge_data[second[0]]["length"]
                ) * 0.5,
            )
            first_limit = widths[second] + travel * maximum_slope
            second_limit = widths[first] + travel * maximum_slope
            if widths[first] > first_limit + EPSILON:
                widths[first] = first_limit
                changed = True
            if widths[second] > second_limit + EPSILON:
                widths[second] = second_limit
                changed = True
        if not changed:
            break

    for (edge, face), width in widths.items():
        edge_data[edge]["sides"][face]["width"] = max(1.0e-5, width)


def stabilize_segment_overlap_widths(segment_data, closed):
    """Keep each ordered ribbon side at one collision-safe visual width."""
    if len(segment_data) < 2:
        return
    for width_key in ("a_width", "b_width"):
        safe_width = min(segment[width_key] for segment in segment_data)
        for segment in segment_data:
            segment[width_key] = safe_width


def planar_line_intersection(
    vertex_point,
    previous_tangent,
    next_tangent,
    previous_inward,
    next_inward,
    face_normal,
    previous_width,
    next_width,
    miter_limit,
):
    """
    Intersect two offset lines inside one shared source-face plane.

    The result remains exactly `width` away from both source edge segments.
    """
    line_a_point = vertex_point + previous_inward * previous_width
    line_b_point = vertex_point + next_inward * next_width

    direction_a = safe_normalized(previous_tangent)
    direction_b = safe_normalized(next_tangent)
    normal = safe_normalized(face_normal)

    denominator = normal.dot(direction_a.cross(direction_b))

    if abs(denominator) <= EPSILON:
        return (line_a_point + line_b_point) * 0.5

    delta = line_b_point - line_a_point
    parameter = normal.dot(delta.cross(direction_b)) / denominator
    intersection = line_a_point + direction_a * parameter

    offset = intersection - vertex_point
    maximum = max(previous_width, next_width) * max(1.0, miter_limit)

    if offset.length > maximum:
        offset = safe_normalized(
            previous_inward + next_inward,
            next_inward,
        ) * maximum
        intersection = vertex_point + offset

    return intersection


def bound_overlap_miter_point(origin, point, incident_segments):
    """Contract a clamp-mode miter so adjacent outer rails cannot cross."""
    offset = point - origin
    scale = 1.0
    radial_limit = max(
        float(segment["width"])
        for segment in incident_segments
    ) * 1.5
    if offset.length > radial_limit and radial_limit > EPSILON:
        scale = min(scale, radial_limit / offset.length)

    for segment in incident_segments:
        tangent = safe_normalized(segment["tangent"])
        longitudinal_reach = abs(offset.dot(tangent))
        reach_limit = max(float(segment["length"]) * 0.45, 1.0e-6)
        if longitudinal_reach > reach_limit:
            scale = min(scale, reach_limit / longitudinal_reach)
    return origin + offset * scale



def offset_point_from_face_normals(
    point,
    normals,
    distance,
):
    """
    Offset a source vertex onto the intersection of its parallel face planes.

    Moving a shared edge vertex along an averaged normal produces decal quads
    that are no longer parallel to either source face. This solver instead
    finds a displacement whose signed distance from every relevant face plane
    is `distance`. Two-face edges use the exact bisector intersection; corners
    use an exact independent triple when possible and a least-squares solution
    otherwise.
    """
    if distance <= EPSILON:
        return point.copy()

    unique_normals = []

    for normal in normals:
        candidate = safe_normalized(normal)

        if candidate.length_squared <= EPSILON:
            continue

        if any(
            candidate.dot(existing) > 0.999999
            for existing in unique_normals
        ):
            continue

        unique_normals.append(candidate)

    if not unique_normals:
        return point.copy()

    if len(unique_normals) == 1:
        return point + unique_normals[0] * distance

    def solve_pair(normal_a, normal_b):
        denominator = 1.0 + normal_a.dot(normal_b)

        if denominator <= 1.0e-8:
            return normal_a * distance

        return (
            normal_a + normal_b
        ) * (distance / denominator)

    if len(unique_normals) == 2:
        return point + solve_pair(
            unique_normals[0],
            unique_normals[1],
        )

    # Prefer an exact independent triple. At ordinary polyhedral corners this
    # lands on all three offset planes exactly.
    best_matrix = None
    best_determinant = 0.0

    for index_a in range(len(unique_normals) - 2):
        for index_b in range(index_a + 1, len(unique_normals) - 1):
            for index_c in range(index_b + 1, len(unique_normals)):
                matrix = Matrix((
                    tuple(unique_normals[index_a]),
                    tuple(unique_normals[index_b]),
                    tuple(unique_normals[index_c]),
                ))
                determinant = abs(matrix.determinant())

                if determinant > best_determinant:
                    best_determinant = determinant
                    best_matrix = matrix

    if best_matrix is not None and best_determinant > 1.0e-8:
        displacement = best_matrix.inverted() @ Vector((
            distance,
            distance,
            distance,
        ))
        residual = max(
            abs(normal.dot(displacement) - distance)
            for normal in unique_normals
        )

        if residual <= max(1.0e-7, distance * 1.0e-4):
            return point + displacement

    # More than three non-coplanar planes may not have one exact common point.
    # Solve the minimum-error normal equations instead of averaging normals.
    matrix_values = [[0.0, 0.0, 0.0] for _ in range(3)]
    right_hand_side = Vector((0.0, 0.0, 0.0))

    for normal in unique_normals:
        right_hand_side += normal * distance

        for row in range(3):
            for column in range(3):
                matrix_values[row][column] += (
                    normal[row] * normal[column]
                )

    regularization = 1.0e-10
    for axis in range(3):
        matrix_values[axis][axis] += regularization

    normal_matrix = Matrix(tuple(tuple(row) for row in matrix_values))
    displacement = normal_matrix.inverted_safe() @ right_hand_side

    if displacement.length_squared <= EPSILON:
        # Degenerate fallback: use the most independent normal pair.
        best_pair = (unique_normals[0], unique_normals[1])
        lowest_dot = abs(best_pair[0].dot(best_pair[1]))

        for index_a in range(len(unique_normals) - 1):
            for index_b in range(index_a + 1, len(unique_normals)):
                pair_dot = abs(
                    unique_normals[index_a].dot(unique_normals[index_b])
                )

                if pair_dot < lowest_dot:
                    lowest_dot = pair_dot
                    best_pair = (
                        unique_normals[index_a],
                        unique_normals[index_b],
                    )

        displacement = solve_pair(*best_pair)

    return point + displacement


def build_selected_edge_graph_strip(
    selected_edges,
    all_source_edges,
    world_matrix,
    normal_matrix,
    face_width,
    surface_offset,
    miter_limit,
    vertices_out,
    faces_out,
    face_uvs_out,
    center_vertices_out,
    auto_face_width=False,
    auto_width_samples=1,
    auto_width_clearance=0.85,
    clamp_edge_overlaps=False,
    overlap_clearance=0.98,
    width_search_context=None,
    face_width_resolved=False,
    uv_scale=1.0,
    face_source_edges_out=None,
    face_width_by_edge=None,
    fold_nonplanar_sectors=False,
):
    """Build one connected ribbon directly from the selected edge graph.

    Selected edges partition the face fan around each source vertex. Every
    resulting surface sector owns one outer vertex, while every source vertex
    owns one center vertex. Consequently a three-edge junction is authored as
    one center plus three sector vertices instead of three overlapping strips.

    This deliberately avoids ordered-chain extraction: a chain walker must
    choose one continuation at a branch and therefore cannot preserve all
    degree-three (or higher) junctions in a single generation pass.
    """
    selected_edges = [
        edge for edge in selected_edges
        if len(edge.link_faces) == 2
    ]
    if not selected_edges:
        return 0

    selected_edge_set = set(selected_edges)
    if not face_width_resolved:
        face_width = resolve_relative_face_width(
            face_width,
            all_source_edges,
            world_matrix,
        )
    else:
        face_width = max(float(face_width), 1.0e-8)

    graph = build_selected_edge_graph(selected_edges)
    edge_data = {}

    for edge in selected_edges:
        v0, v1 = edge.verts
        p0 = world_matrix @ v0.co
        p1 = world_matrix @ v1.co
        tangent = safe_normalized(
            p1 - p0,
            Vector((1.0, 0.0, 0.0)),
        )
        sides = {}
        edge_face_width = max(
            float(
                face_width_by_edge.get(edge, face_width)
                if face_width_by_edge is not None
                else face_width
            ),
            1.0e-8,
        )

        for face in edge.link_faces:
            normal = transform_normal(normal_matrix, face.normal)
            inward = face_inward_direction(
                face,
                edge,
                world_matrix,
                normal_matrix,
                tangent,
            )
            side = {
                "face": face,
                "normal": normal,
                "inward": inward,
            }
            width = edge_face_width
            if auto_face_width or clamp_edge_overlaps:
                width = adaptive_width_for_edge_side(
                    edge,
                    side,
                    tangent,
                    edge_face_width,
                    auto_width_clearance,
                    auto_width_samples,
                    selected_edge_set,
                    all_source_edges,
                    world_matrix,
                    clamp_boundaries=auto_face_width,
                    clamp_selected_overlaps=clamp_edge_overlaps,
                    overlap_clearance=overlap_clearance,
                    width_search_context=width_search_context,
                )
            sides[face] = {
                **side,
                "width": width,
            }

        edge_data[edge] = {
            "verts": (v0, v1),
            "points": (p0, p1),
            "tangent": tangent,
            "length": (p1 - p0).length,
            "sides": sides,
        }

    if clamp_edge_overlaps:
        stabilize_selected_graph_overlap_widths(
            edge_data,
            selected_edges,
            world_matrix,
        )

    center_by_vertex = {}
    outer_by_slot = {}

    def append_vertex(point):
        index = len(vertices_out)
        vertices_out.append(point)
        return index

    def slot_outer_point(source_vertex, edge, face):
        source_point = world_matrix @ source_vertex.co
        side = edge_data[edge]["sides"][face]
        return (
            source_point
            + side["inward"] * side["width"]
            + side["normal"] * surface_offset
        )

    for source_vertex, incident_edges in graph.items():
        source_point = world_matrix @ source_vertex.co
        incident_normals = [
            edge_data[edge]["sides"][face]["normal"]
            for edge in incident_edges
            for face in edge.link_faces
        ]
        center_index = append_vertex(
            offset_point_from_face_normals(
                source_point,
                incident_normals,
                surface_offset,
            )
        )
        center_by_vertex[source_vertex] = center_index
        center_vertices_out.append(center_index)

        # One selected edge does not split a closed manifold face fan into two
        # connected components. Its two support faces still need independent
        # outer endpoints, so handle it explicitly.
        if len(incident_edges) == 1:
            edge = incident_edges[0]
            for face in edge.link_faces:
                outer_by_slot[(source_vertex, edge, face)] = append_vertex(
                    slot_outer_point(source_vertex, edge, face)
                )
            continue

        incident_faces = list(source_vertex.link_faces)
        face_adjacency = {
            face: set() for face in incident_faces
        }

        # Walk through non-selected radial edges only. Selected edges are the
        # barriers that divide the vertex face fan into ribbon sectors.
        for radial_edge in source_vertex.link_edges:
            if radial_edge in selected_edge_set:
                continue
            radial_faces = [
                face for face in radial_edge.link_faces
                if face in face_adjacency
            ]
            for face_a in radial_faces:
                for face_b in radial_faces:
                    if face_a is not face_b:
                        face_adjacency[face_a].add(face_b)

        remaining_faces = set(incident_faces)
        components = []
        while remaining_faces:
            seed = remaining_faces.pop()
            component = {seed}
            pending = [seed]
            while pending:
                current = pending.pop()
                for neighbor in face_adjacency[current]:
                    if neighbor not in remaining_faces:
                        continue
                    remaining_faces.remove(neighbor)
                    component.add(neighbor)
                    pending.append(neighbor)
            components.append(component)

        for component in components:
            slots = []
            for edge in incident_edges:
                for face in edge.link_faces:
                    if face in component:
                        slots.append((edge, face))

            if not slots:
                continue

            # A normal manifold fan sector is bounded by exactly two selected
            # edge-face slots. Fall back to independent endpoints for malformed
            # or non-manifold fans instead of welding unrelated boundaries.
            distinct_edges = {edge for edge, _face in slots}
            if len(slots) != 2 or len(distinct_edges) != 2:
                for edge, face in slots:
                    outer_by_slot[(source_vertex, edge, face)] = append_vertex(
                        slot_outer_point(source_vertex, edge, face)
                    )
                continue

            (edge_a, face_a), (edge_b, face_b) = slots
            component_normals = [
                transform_normal(normal_matrix, face.normal)
                for face in component
            ]
            support_normal = Vector((0.0, 0.0, 0.0))
            for normal in component_normals:
                support_normal += normal
            support_normal = safe_normalized(
                support_normal,
                component_normals[0],
            )
            sector_origin = offset_point_from_face_normals(
                source_point,
                component_normals,
                surface_offset,
            )

            def projected_slot_vectors(edge, face):
                other_vertex = edge.other_vert(source_vertex)
                tangent = (world_matrix @ other_vertex.co) - source_point
                tangent -= support_normal * tangent.dot(support_normal)
                tangent = safe_normalized(
                    tangent,
                    edge_data[edge]["tangent"],
                )
                raw_inward = edge_data[edge]["sides"][face]["inward"]
                inward = raw_inward - support_normal * raw_inward.dot(
                    support_normal
                )
                inward = safe_normalized(
                    inward,
                    support_normal.cross(tangent),
                )
                return tangent, inward

            tangent_a, inward_a = projected_slot_vectors(edge_a, face_a)
            tangent_b, inward_b = projected_slot_vectors(edge_b, face_b)
            width_a = edge_data[edge_a]["sides"][face_a]["width"]
            width_b = edge_data[edge_b]["sides"][face_b]["width"]
            if clamp_edge_overlaps:
                # Both rails terminate at this one authored sector vertex.
                # Intersecting offset lines at different distances displaces
                # the intersection far along the wider line and creates the
                # arrow-shaped flaps seen at width transitions.  A junction
                # therefore owns one scalar width: the largest value safe for
                # both incident slots.  Neighboring junctions may still own
                # different values, so the quad between them provides the
                # intended gradual local-width taper.
                junction_width = min(width_a, width_b)
                width_a = junction_width
                width_b = junction_width

            if (
                fold_nonplanar_sectors
                and len(component) == 2
                and component_normals[0].dot(component_normals[1]) < 0.9999
            ):
                # A Boolean seam can cross a genuine source crease at an
                # arbitrary angle. There is no single planar miter point in
                # that case: each face's offset rail reaches the shared fold
                # at a different position. Projecting both rails into an
                # averaged plane (the general graph fallback below) pulls the
                # result off both surfaces and creates the visible corner
                # wedges. Constrain their shared endpoint to the real fold.
                fold_edges = [
                    radial_edge
                    for radial_edge in source_vertex.link_edges
                    if (
                        radial_edge not in selected_edge_set
                        and face_a in radial_edge.link_faces
                        and face_b in radial_edge.link_faces
                    )
                ]
                if len(fold_edges) == 1:
                    fold_other = fold_edges[0].other_vert(source_vertex)
                    fold_direction = safe_normalized(
                        (world_matrix @ fold_other.co) - source_point,
                        Vector((1.0, 0.0, 0.0)),
                    )
                    fold_length = (
                        (world_matrix @ fold_other.co) - source_point
                    ).length

                    def rail_fold_intersection(edge, face, width):
                        side = edge_data[edge]["sides"][face]
                        edge_other = edge.other_vert(source_vertex)
                        tangent = safe_normalized(
                            (world_matrix @ edge_other.co) - source_point,
                            edge_data[edge]["tangent"],
                        )
                        rail_origin = (
                            source_point
                            + side["inward"] * width
                            + side["normal"] * surface_offset
                        )
                        denominator = side["normal"].dot(
                            tangent.cross(fold_direction)
                        )
                        if abs(denominator) <= EPSILON:
                            return None
                        parameter = side["normal"].dot(
                            (sector_origin - rail_origin).cross(
                                fold_direction
                            )
                        ) / denominator
                        point = rail_origin + tangent * parameter
                        fold_distance = (
                            point - sector_origin
                        ).dot(fold_direction)
                        fold_distance = max(
                            0.0,
                            min(fold_length, fold_distance),
                        )
                        point = (
                            sector_origin
                            + fold_direction * fold_distance
                        )
                        reach_limit = width * max(1.0, miter_limit)
                        if clamp_edge_overlaps:
                            reach_limit = min(reach_limit, width * 1.5)
                        if (
                            reach_limit <= EPSILON
                            or (point - sector_origin).length
                            > reach_limit + EPSILON
                        ):
                            return None
                        return point

                    fold_point_a = rail_fold_intersection(
                        edge_a,
                        face_a,
                        width_a,
                    )
                    fold_point_b = rail_fold_intersection(
                        edge_b,
                        face_b,
                        width_b,
                    )
                    if fold_point_a is not None and fold_point_b is not None:
                        # Both ideal rails lie on the same physical crease but
                        # can reach it at slightly different distances. Their
                        # midpoint is the least-error shared miter constrained
                        # to that crease. Keeping one vertex avoids the small
                        # open step produced by separate face-local endpoints.
                        sector_index = append_vertex(
                            (fold_point_a + fold_point_b) * 0.5
                        )
                        outer_by_slot[
                            (source_vertex, edge_a, face_a)
                        ] = sector_index
                        outer_by_slot[
                            (source_vertex, edge_b, face_b)
                        ] = sector_index
                        continue
            sector_point = planar_line_intersection(
                sector_origin,
                tangent_a,
                tangent_b,
                inward_a,
                inward_b,
                support_normal,
                width_a,
                width_b,
                miter_limit,
            )
            if clamp_edge_overlaps:
                # Non-planar face fans do not have one exact 2D miter plane.
                # Keep their averaged-plane solution local, while leaving the
                # longitudinal shape untouched. Planar short-edge safety was
                # already solved by reducing the complete boundary width.
                sector_offset = sector_point - sector_origin
                radial_limit = max(width_a, width_b) * 1.5
                if (
                    radial_limit > EPSILON
                    and sector_offset.length > radial_limit
                ):
                    sector_point = (
                        sector_origin
                        + sector_offset * (radial_limit / sector_offset.length)
                    )
            sector_index = append_vertex(sector_point)
            outer_by_slot[(source_vertex, edge_a, face_a)] = sector_index
            outer_by_slot[(source_vertex, edge_b, face_b)] = sector_index

    created_face_count = 0
    for edge in selected_edges:
        data = edge_data[edge]
        v0, v1 = data["verts"]
        center0 = center_by_vertex[v0]
        center1 = center_by_vertex[v1]
        u_length = max(
            data["length"] * max(float(uv_scale), 1.0e-8),
            1.0e-8,
        )

        for side_index, face in enumerate(edge.link_faces):
            outer0 = outer_by_slot.get((v0, edge, face))
            outer1 = outer_by_slot.get((v1, edge, face))
            if outer0 is None or outer1 is None:
                continue
            outer_v = 0.0 if side_index == 0 else 1.0
            indices, uvs = oriented_face_with_uvs(
                (center0, center1, outer1, outer0),
                (
                    (0.0, 0.5),
                    (u_length, 0.5),
                    (u_length, outer_v),
                    (0.0, outer_v),
                ),
                vertices_out,
                edge_data[edge]["sides"][face]["normal"],
            )
            faces_out.append(indices)
            face_uvs_out.append(uvs)
            if face_source_edges_out is not None:
                face_source_edges_out.append(edge)
            created_face_count += 1

    return created_face_count


def build_partitioned_selected_edge_graph_strip(
    selected_edges,
    edge_groups,
    vertices_out,
    faces_out,
    face_uvs_out,
    center_vertices_out,
    **builder_options,
):
    """Build full-graph miters while keeping angle partitions disconnected.

    Geometry is first solved against the complete selected graph so every cut
    corner retains its proper shared miter positions. Faces are then remapped
    through a separate vertex cache per angle partition. Neighboring islands
    therefore meet perfectly but do not share mesh vertices or edges.
    """
    selected_edges = list(dict.fromkeys(selected_edges or ()))
    if not selected_edges:
        return 0

    group_by_edge = {}
    for group_index, group in enumerate(edge_groups or ()):
        for edge in group:
            group_by_edge[edge] = group_index
    next_group = len(edge_groups or ())
    for edge in selected_edges:
        if edge not in group_by_edge:
            group_by_edge[edge] = next_group
            next_group += 1

    temporary_vertices = []
    temporary_faces = []
    temporary_uvs = []
    temporary_centers = []
    temporary_face_edges = []
    created = build_selected_edge_graph_strip(
        selected_edges=selected_edges,
        vertices_out=temporary_vertices,
        faces_out=temporary_faces,
        face_uvs_out=temporary_uvs,
        center_vertices_out=temporary_centers,
        face_source_edges_out=temporary_face_edges,
        **builder_options,
    )
    if created == 0:
        return 0

    center_set = set(temporary_centers)
    vertex_maps = {}
    published_centers = set()

    for temporary_face, face_uvs, source_edge in zip(
        temporary_faces,
        temporary_uvs,
        temporary_face_edges,
    ):
        group_index = group_by_edge[source_edge]
        vertex_map = vertex_maps.setdefault(group_index, {})
        remapped_face = []
        for temporary_index in temporary_face:
            output_index = vertex_map.get(temporary_index)
            if output_index is None:
                output_index = len(vertices_out)
                vertices_out.append(temporary_vertices[temporary_index])
                vertex_map[temporary_index] = output_index
                if (
                    temporary_index in center_set
                    and output_index not in published_centers
                ):
                    center_vertices_out.append(output_index)
                    published_centers.add(output_index)
            remapped_face.append(output_index)
        faces_out.append(tuple(remapped_face))
        face_uvs_out.append(face_uvs)

    return len(temporary_faces)


def endpoint_miter_point(
    source_vertex,
    current_edge,
    current_tangent_away,
    side,
    selected_edge_set,
    world_matrix,
    normal_matrix,
    vertex_point,
    face_width,
    miter_limit,
):
    """
    Solve an endpoint miter inside this side's actual supporting face.

    At a multi-edge junction there can be several selected neighbors, but a
    manifold support face has only one other edge leaving the source vertex.
    Choosing that face-local neighbor is deterministic and avoids pairing the
    current side with an unrelated branch across another surface sector.
    """
    fallback = (
        vertex_point
        + side["inward"] * face_width
    )
    support_face = side["face"]

    incident_selected = [
        edge
        for edge in source_vertex.link_edges
        if (
            edge in selected_edge_set
            and len(edge.link_faces) == 2
        )
    ]

    if current_edge not in incident_selected:
        return fallback

    neighbor_edges = [
        edge
        for edge in incident_selected
        if edge != current_edge and support_face in edge.link_faces
    ]
    if len(neighbor_edges) != 1:
        return fallback
    neighbor_edge = neighbor_edges[0]

    neighbor_support_face = None

    for candidate_face in neighbor_edge.link_faces:
        if (
            candidate_face == support_face
            or faces_are_coplanar(
                candidate_face,
                support_face,
            )
        ):
            neighbor_support_face = candidate_face
            break

    if neighbor_support_face is None:
        return fallback

    current_other = current_edge.other_vert(source_vertex)
    neighbor_other = neighbor_edge.other_vert(source_vertex)
    current_other_world = world_matrix @ current_other.co
    neighbor_other_world = world_matrix @ neighbor_other.co

    current_length = (
        current_other_world - vertex_point
    ).length
    neighbor_length = (
        neighbor_other_world - vertex_point
    ).length

    if (
        current_length <= EPSILON
        or neighbor_length <= EPSILON
    ):
        return fallback

    neighbor_tangent_away = safe_normalized(
        neighbor_other_world - vertex_point,
        current_tangent_away,
    )
    neighbor_inward = face_inward_direction(
        neighbor_support_face,
        neighbor_edge,
        world_matrix,
        normal_matrix,
        neighbor_tangent_away,
    )
    miter_point = planar_line_intersection(
        vertex_point,
        current_tangent_away,
        neighbor_tangent_away,
        side["inward"],
        neighbor_inward,
        side["normal"],
        face_width,
        face_width,
        miter_limit,
    )
    miter_reach = (
        miter_point - vertex_point
    ).length
    local_reach_limit = min(
        face_width * max(1.0, miter_limit),
        current_length * 0.75,
        neighbor_length * 0.75,
    )

    # A miter should never extend farther than the nearby source topology can
    # support. A square endpoint is much safer than a long self-intersection.
    if local_reach_limit <= EPSILON or miter_reach > local_reach_limit:
        return fallback

    return miter_point


def selected_face_junction_neighbor(
    source_vertex,
    current_edge,
    support_face,
    selected_edge_set,
):
    """Return the one selected neighbor sharing a junction support face."""
    candidates = [
        edge
        for edge in source_vertex.link_edges
        if (
            edge != current_edge
            and edge in selected_edge_set
            and len(edge.link_faces) == 2
            and support_face in edge.link_faces
        )
    ]
    return candidates[0] if len(candidates) == 1 else None


def source_vertex_at_world_point(
    chain_verts,
    world_matrix,
    point,
    tolerance=1.0e-7,
):
    """Map an untrimmed generated chain point back to its source vertex."""
    for source_vertex in chain_verts:
        if (
            (world_matrix @ source_vertex.co) - point
        ).length <= tolerance:
            return source_vertex
    return None


def selected_junction_center_point(
    source_vertex,
    selected_edge_set,
    world_matrix,
    normal_matrix,
    surface_offset,
):
    """Return one stable center point shared by every branch at a pole."""
    incident_faces = []
    seen_faces = set()
    for edge in source_vertex.link_edges:
        if edge not in selected_edge_set or len(edge.link_faces) != 2:
            continue
        for face in edge.link_faces:
            if face in seen_faces:
                continue
            seen_faces.add(face)
            incident_faces.append(face)

    point = world_matrix @ source_vertex.co
    normals = [
        transform_normal(normal_matrix, face.normal)
        for face in incident_faces
    ]
    return offset_point_from_face_normals(point, normals, surface_offset)


def support_faces_share_edge_at_vertex(
    face_a,
    face_b,
    source_vertex,
):
    """True when two surface sectors meet across an edge at the pole."""
    if face_a is None or face_b is None or face_a == face_b:
        return False
    return any(
        edge in face_b.edges and source_vertex in edge.verts
        for edge in face_a.edges
    )


def append_cached_junction_vertex(
    vertices_out,
    junction_vertex_cache,
    key,
    point,
):
    """Append a junction vertex once and reuse its index across chains."""
    if junction_vertex_cache is not None and key is not None:
        cached = junction_vertex_cache.get(key)
        if cached is not None:
            return cached

    index = len(vertices_out)
    vertices_out.append(point)
    if junction_vertex_cache is not None and key is not None:
        junction_vertex_cache[key] = index
    return index


def append_endpoint_junction_vertex(
    vertices_out,
    junction_vertex_cache,
    source_vertex,
    current_edge,
    side,
    selected_edge_set,
    point,
    surface_offset,
):
    """Append or share one face-local outer vertex at a selected pole."""
    incident_selected = [
        edge
        for edge in source_vertex.link_edges
        if edge in selected_edge_set and len(edge.link_faces) == 2
    ]
    neighbor = selected_face_junction_neighbor(
        source_vertex,
        current_edge,
        side["face"],
        selected_edge_set,
    )
    cache_key = (
        ("outer", source_vertex.index, side["face"].index)
        if len(incident_selected) >= 3 and neighbor is not None
        else None
    )
    return append_cached_junction_vertex(
        vertices_out,
        junction_vertex_cache,
        cache_key,
        point + side["normal"] * surface_offset,
    )


def topology_sector_endpoint_indices(
    source_vertex,
    previous_edge,
    next_edge,
    previous_tangent_away,
    next_tangent_away,
    previous_side,
    next_side,
    previous_width,
    next_width,
    selected_edge_set,
    world_matrix,
    normal_matrix,
    vertex_point,
    miter_limit,
    surface_offset,
    vertices_out,
    junction_vertex_cache,
):
    """Build one shared outer vertex for a connected face-fan sector.

    The full selected-graph builder represents each sector with one vertex.
    The chain builders previously emitted one endpoint per incident edge here,
    leaving a triangular hole between otherwise continuous strips whenever the
    support plane changed. Solve the same averaged face-fan miter used by the
    graph builder so Amount-sliced output keeps identical junction topology.
    """
    incident_faces = set(source_vertex.link_faces)
    face_adjacency = {face: set() for face in incident_faces}
    for radial_edge in source_vertex.link_edges:
        if radial_edge in selected_edge_set:
            continue
        radial_faces = [
            face for face in radial_edge.link_faces
            if face in incident_faces
        ]
        for face_a in radial_faces:
            for face_b in radial_faces:
                if face_a is not face_b:
                    face_adjacency[face_a].add(face_b)

    component = {previous_side["face"]}
    pending = [previous_side["face"]]
    while pending:
        face = pending.pop()
        for neighbor in face_adjacency.get(face, ()):
            if neighbor in component:
                continue
            component.add(neighbor)
            pending.append(neighbor)
    if next_side["face"] not in component:
        component.add(next_side["face"])

    component_normals = [
        transform_normal(normal_matrix, face.normal)
        for face in component
    ]
    support_normal = Vector((0.0, 0.0, 0.0))
    for normal in component_normals:
        support_normal += normal
    support_normal = safe_normalized(
        support_normal,
        component_normals[0],
    )
    sector_origin = offset_point_from_face_normals(
        vertex_point,
        component_normals,
        surface_offset,
    )

    def projected_vectors(tangent, side):
        tangent_fallback = tangent.copy()
        tangent = tangent - support_normal * tangent.dot(support_normal)
        tangent = safe_normalized(tangent, tangent_fallback)
        inward = side["inward"] - support_normal * side["inward"].dot(
            support_normal
        )
        inward = safe_normalized(
            inward,
            support_normal.cross(tangent),
        )
        return tangent, inward

    previous_tangent, previous_inward = projected_vectors(
        previous_tangent_away,
        previous_side,
    )
    next_tangent, next_inward = projected_vectors(
        next_tangent_away,
        next_side,
    )
    sector_point = planar_line_intersection(
        sector_origin,
        previous_tangent,
        next_tangent,
        previous_inward,
        next_inward,
        support_normal,
        previous_width,
        next_width,
        miter_limit,
    )
    component_signature = tuple(sorted(face.index for face in component))
    sector_index = append_cached_junction_vertex(
        vertices_out,
        junction_vertex_cache,
        ("sector", source_vertex.index, component_signature),
        sector_point,
    )
    return sector_index, sector_index


def connected_face_loop_slide_direction(
    source_vertex,
    boundary_edges,
    support_faces,
    world_matrix,
    side_normal,
    side_inward,
    required_distance,
):
    """Return a connected face-loop direction usable for endpoint slide."""
    if source_vertex is None:
        return None

    boundary_edge_set = set(boundary_edges or ())
    support_faces = [face for face in support_faces or () if face is not None]
    if not support_faces:
        return None

    source_point = world_matrix @ source_vertex.co
    side_normal = safe_normalized(side_normal, Vector((0.0, 0.0, 1.0)))
    side_inward = safe_normalized(side_inward, Vector((1.0, 0.0, 0.0)))
    best_direction = None
    best_score = 0.0

    for edge in source_vertex.link_edges:
        if edge in boundary_edge_set or edge.hide or len(edge.link_faces) != 2:
            continue

        matching_face = None
        for edge_face in edge.link_faces:
            if any(
                edge_face == support_face
                or faces_are_coplanar(edge_face, support_face)
                for support_face in support_faces
            ):
                matching_face = edge_face
                break

        if matching_face is None:
            continue

        other_vertex = edge.other_vert(source_vertex)
        raw_direction = (world_matrix @ other_vertex.co) - source_point
        edge_length = raw_direction.length
        if edge_length + EPSILON < required_distance:
            continue

        direction = raw_direction - side_normal * raw_direction.dot(side_normal)
        if direction.length_squared <= EPSILON:
            continue

        direction.normalize()
        inward_score = direction.dot(side_inward)
        if inward_score <= 0.25:
            continue

        face_normal = transform_normal(
            world_matrix.inverted_safe().transposed().to_3x3(),
            matching_face.normal,
        )
        normal_score = max(0.0, face_normal.dot(side_normal))
        score = inward_score + normal_score * 0.1

        if score > best_score:
            best_score = score
            best_direction = direction

    return best_direction


def build_corner_strip(
    chain_verts,
    chain_edges,
    closed,
    selected_edge_set,
    all_source_edges,
    world_matrix,
    normal_matrix,
    face_width,
    decal_amount,
    slice_positions,
    forced_slice_interval,
    auto_face_width,
    auto_width_samples,
    auto_width_clearance,
    clamp_edge_overlaps,
    overlap_clearance,
    surface_offset,
    miter_limit,
    use_face_loop_slide,
    vertices_out,
    faces_out,
    face_uvs_out,
    center_vertices_out,
    width_search_context=None,
    face_width_resolved=False,
    junction_vertex_cache=None,
    **_ignored_taper_options,
):
    """
    Build one angle-split island.

    Thickness is solved only after splitting. Each side is offset inside its
    actual source-face plane. When consecutive segments share the same source
    face, they receive one exact planar miter vertex. When the supporting face
    changes, each segment keeps its own endpoint and a small local corner patch
    connects them, avoiding a stretched wedge across incompatible planes.
    """
    if not face_width_resolved:
        face_width = resolve_relative_face_width(
            face_width, all_source_edges, world_matrix
        )
    else:
        face_width = max(float(face_width), 1.0e-8)

    point_count = len(chain_verts)
    edge_count = len(chain_edges)

    if point_count < 2 or edge_count == 0:
        return 0

    if closed:
        work_world_points = [world_matrix @ vert.co for vert in chain_verts]
        work_chain_edges = chain_edges
        start_trimmed = False
        end_trimmed = False
    else:
        (
            work_world_points,
            work_chain_edges,
            start_trimmed,
            end_trimmed,
        ) = trim_open_chain_by_amount(
            chain_verts,
            chain_edges,
            world_matrix,
            decal_amount,
            slice_positions,
            forced_interval=forced_slice_interval,
        )

    point_count = len(work_world_points)
    edge_count = len(work_chain_edges)

    if point_count < 2 or edge_count == 0:
        return 0

    world_points = work_world_points
    segment_data = []
    previous_pair = None

    for segment_index, edge in enumerate(work_chain_edges):
        start_index = segment_index
        end_index = (segment_index + 1) % point_count if closed else segment_index + 1

        p0 = world_points[start_index]
        p1 = world_points[end_index]
        tangent = safe_normalized(p1 - p0, Vector((1.0, 0.0, 0.0)))

        linked_faces = list(edge.link_faces)
        if len(linked_faces) != 2:
            return 0

        face_data = []

        for face in linked_faces:
            normal = transform_normal(normal_matrix, face.normal)
            inward = face_inward_direction(
                face,
                edge,
                world_matrix,
                normal_matrix,
                tangent,
            )
            face_data.append({
                "face": face,
                "normal": normal,
                "inward": inward,
            })

        side_a, side_b = assign_face_sides(face_data, previous_pair)
        previous_pair = (side_a, side_b)

        width_a = face_width
        width_b = face_width

        if auto_face_width or clamp_edge_overlaps:
            width_a = adaptive_width_for_edge_side(
                edge,
                side_a,
                tangent,
                face_width,
                auto_width_clearance,
                auto_width_samples,
                selected_edge_set,
                all_source_edges,
                world_matrix,
                clamp_boundaries=auto_face_width,
                clamp_selected_overlaps=clamp_edge_overlaps,
                overlap_clearance=overlap_clearance,
                width_search_context=width_search_context,
            )
            width_b = adaptive_width_for_edge_side(
                edge,
                side_b,
                tangent,
                face_width,
                auto_width_clearance,
                auto_width_samples,
                selected_edge_set,
                all_source_edges,
                world_matrix,
                clamp_boundaries=auto_face_width,
                clamp_selected_overlaps=clamp_edge_overlaps,
                overlap_clearance=overlap_clearance,
                width_search_context=width_search_context,
            )

        segment_data.append({
            "tangent": tangent,
            "length": (p1 - p0).length,
            "a": side_a,
            "b": side_b,
            "a_width": width_a,
            "b_width": width_b,
        })

    if clamp_edge_overlaps:
        stabilize_segment_overlap_widths(segment_data, closed)

    # Shared center row. This remains continuous inside the island so the final
    # angle-limited bevel works as one strip.
    center_indices = []

    for vertex_index, point in enumerate(world_points):
        incident_normals = []

        if closed or vertex_index > 0:
            previous_segment = segment_data[(vertex_index - 1) % edge_count]
            incident_normals.extend((
                previous_segment["a"]["normal"],
                previous_segment["b"]["normal"],
            ))

        if closed or vertex_index < point_count - 1:
            next_segment = segment_data[vertex_index % edge_count]
            incident_normals.extend((
                next_segment["a"]["normal"],
                next_segment["b"]["normal"],
            ))

        source_vertex = source_vertex_at_world_point(
            chain_verts,
            world_matrix,
            point,
        )
        incident_selected = (
            [
                edge
                for edge in source_vertex.link_edges
                if edge in selected_edge_set and len(edge.link_faces) == 2
            ]
            if source_vertex is not None
            else []
        )
        center_key = None
        center_point = offset_point_from_face_normals(
            point,
            incident_normals,
            surface_offset,
        )
        if source_vertex is not None and len(incident_selected) >= 3:
            center_key = ("center", source_vertex.index)
            center_point = selected_junction_center_point(
                source_vertex,
                selected_edge_set,
                world_matrix,
                normal_matrix,
                surface_offset,
            )

        center_index = append_cached_junction_vertex(
            vertices_out,
            junction_vertex_cache,
            center_key,
            center_point,
        )
        center_indices.append(center_index)
        center_vertices_out.append(center_index)

    # Per-segment outer endpoint slots.
    outer = [
        {
            "a_start": None,
            "a_end": None,
            "b_start": None,
            "b_end": None,
        }
        for _ in range(edge_count)
    ]

    corner_patches = []

    def selected_boundary_direction_count(source_vertex, boundary_edges):
        if source_vertex is None:
            return 0

        source_point = world_matrix @ source_vertex.co
        unique_directions = []

        for edge in boundary_edges:
            try:
                other_vertex = edge.other_vert(source_vertex)
            except Exception:
                continue

            direction = safe_normalized(
                (world_matrix @ other_vertex.co) - source_point,
                Vector((1.0, 0.0, 0.0)),
            )

            if not any(
                direction.dot(existing) > 0.9995
                for existing in unique_directions
            ):
                unique_directions.append(direction)

        return len(unique_directions)

    def loop_slide_point(
        source_vertex,
        boundary_edges,
        side,
        width,
        point,
    ):
        if (
            not use_face_loop_slide
            or source_vertex is None
        ):
            return None

        # Only use loop-slide on a true one-direction endpoint. Internal
        # corners and junctions should keep the existing bounded miter logic.
        if selected_boundary_direction_count(
            source_vertex,
            boundary_edges,
        ) != 1:
            return None

        slide_direction = connected_face_loop_slide_direction(
            source_vertex,
            boundary_edges,
            [side["face"]],
            world_matrix,
            side["normal"],
            side["inward"],
            required_distance=width,
        )

        if slide_direction is None:
            return None

        return point + slide_direction * width

    def make_outer_vertex(point, side, width):
        index = len(vertices_out)
        vertices_out.append(
            point
            + side["inward"] * width
            + side["normal"] * surface_offset
        )
        return index

    def make_endpoint_outer_vertex(
        source_vertex,
        current_edge,
        side,
        point,
    ):
        return append_endpoint_junction_vertex(
            vertices_out,
            junction_vertex_cache,
            source_vertex,
            current_edge,
            side,
            selected_edge_set,
            point,
            surface_offset,
        )

    def assign_topology_sector_endpoints(
        vertex_index,
        side_key,
        previous_segment_index,
        next_segment_index,
        previous_segment,
        next_segment,
        previous_side,
        next_side,
        previous_slot,
        next_slot,
    ):
        source_vertex = source_vertex_at_world_point(
            chain_verts,
            world_matrix,
            world_points[vertex_index],
        )
        if (
            source_vertex is None
            or not support_faces_share_edge_at_vertex(
                previous_side["face"],
                next_side["face"],
                source_vertex,
            )
        ):
            return False

        previous_edge = work_chain_edges[previous_segment_index]
        next_edge = work_chain_edges[next_segment_index]
        previous_index, next_index = topology_sector_endpoint_indices(
            source_vertex=source_vertex,
            previous_edge=previous_edge,
            next_edge=next_edge,
            previous_tangent_away=-previous_segment["tangent"],
            next_tangent_away=next_segment["tangent"],
            previous_side=previous_side,
            next_side=next_side,
            previous_width=previous_segment[f"{side_key}_width"],
            next_width=next_segment[f"{side_key}_width"],
            selected_edge_set=selected_edge_set,
            world_matrix=world_matrix,
            normal_matrix=normal_matrix,
            vertex_point=world_points[vertex_index],
            miter_limit=miter_limit,
            surface_offset=surface_offset,
            vertices_out=vertices_out,
            junction_vertex_cache=junction_vertex_cache,
        )
        outer[previous_segment_index][previous_slot] = previous_index
        outer[next_segment_index][next_slot] = next_index
        return True

    def assign_local_bevel_join(
        vertex_index,
        side_key,
        previous_segment_index,
        next_segment_index,
        previous_segment,
        next_segment,
        previous_side,
        next_side,
        previous_slot,
        next_slot,
    ):
        """
        Replace an unstable shared miter with two bounded endpoints and a small
        center patch. This is effectively a bevel join instead of a miter join.
        """
        previous_width = previous_segment[
            f"{side_key}_width"
        ]
        next_width = next_segment[
            f"{side_key}_width"
        ]
        previous_point = (
            world_points[vertex_index]
            + previous_side["inward"] * previous_width
            + previous_side["normal"] * surface_offset
        )
        next_point = (
            world_points[vertex_index]
            + next_side["inward"] * next_width
            + next_side["normal"] * surface_offset
        )
        merge_tolerance = max(
            1.0e-6,
            surface_offset * 4.0,
            min(previous_width, next_width) * 0.12,
        )

        if (
            previous_point - next_point
        ).length <= merge_tolerance:
            shared_index = len(vertices_out)
            vertices_out.append(
                (previous_point + next_point) * 0.5
            )
            outer[previous_segment_index][
                previous_slot
            ] = shared_index
            outer[next_segment_index][
                next_slot
            ] = shared_index
            return

        previous_index = len(vertices_out)
        vertices_out.append(previous_point)

        next_index = len(vertices_out)
        vertices_out.append(next_point)

        outer[previous_segment_index][
            previous_slot
        ] = previous_index
        outer[next_segment_index][
            next_slot
        ] = next_index

        corner_patches.append({
            "side": side_key,
            "previous_index": previous_index,
            "next_index": next_index,
            "center_index": center_indices[vertex_index],
            "normal": safe_normalized(
                previous_side["normal"]
                + next_side["normal"],
                next_side["normal"],
            ),
            "vertex_index": vertex_index,
        })

    def solve_side_at_vertex(vertex_index, side_key):
        """
        Assign outer indices around one chain vertex for side A or B.
        """
        if not closed and vertex_index == 0:
            side = segment_data[0][side_key]
            side_width = segment_data[0][f"{side_key}_width"]

            if start_trimmed:
                point = world_points[0] + side["inward"] * side_width
            else:
                source_vertex = chain_verts[0]
                boundary_edges = [
                    edge
                    for edge in source_vertex.link_edges
                    if edge in selected_edge_set
                ]
                point = loop_slide_point(
                    source_vertex,
                    boundary_edges,
                    side,
                    side_width,
                    world_points[0],
                )

                if point is None:
                    point = endpoint_miter_point(
                        source_vertex=source_vertex,
                        current_edge=work_chain_edges[0],
                        current_tangent_away=segment_data[0]["tangent"],
                        side=side,
                        selected_edge_set=selected_edge_set,
                        world_matrix=world_matrix,
                        normal_matrix=normal_matrix,
                        vertex_point=world_points[0],
                        face_width=side_width,
                        miter_limit=miter_limit,
                    )

            if start_trimmed:
                index = len(vertices_out)
                vertices_out.append(
                    point + side["normal"] * surface_offset
                )
            else:
                index = make_endpoint_outer_vertex(
                    source_vertex,
                    work_chain_edges[0],
                    side,
                    point,
                )
            outer[0][f"{side_key}_start"] = index
            return

        if not closed and vertex_index == point_count - 1:
            side = segment_data[-1][side_key]
            side_width = segment_data[-1][f"{side_key}_width"]

            if end_trimmed:
                point = world_points[-1] + side["inward"] * side_width
            else:
                source_vertex = chain_verts[-1]
                boundary_edges = [
                    edge
                    for edge in source_vertex.link_edges
                    if edge in selected_edge_set
                ]
                point = loop_slide_point(
                    source_vertex,
                    boundary_edges,
                    side,
                    side_width,
                    world_points[-1],
                )

                if point is None:
                    point = endpoint_miter_point(
                        source_vertex=source_vertex,
                        current_edge=work_chain_edges[-1],
                        current_tangent_away=-segment_data[-1]["tangent"],
                        side=side,
                        selected_edge_set=selected_edge_set,
                        world_matrix=world_matrix,
                        normal_matrix=normal_matrix,
                        vertex_point=world_points[-1],
                        face_width=side_width,
                        miter_limit=miter_limit,
                    )

            if end_trimmed:
                index = len(vertices_out)
                vertices_out.append(
                    point + side["normal"] * surface_offset
                )
            else:
                index = make_endpoint_outer_vertex(
                    source_vertex,
                    work_chain_edges[-1],
                    side,
                    point,
                )
            outer[-1][f"{side_key}_end"] = index
            return

        previous_segment_index = (vertex_index - 1) % edge_count
        next_segment_index = vertex_index % edge_count

        previous_segment = segment_data[previous_segment_index]
        next_segment = segment_data[next_segment_index]
        previous_side = previous_segment[side_key]
        next_side = next_segment[side_key]

        previous_slot = f"{side_key}_end"
        next_slot = f"{side_key}_start"

        if (
            previous_side["face"] == next_side["face"]
            or faces_are_coplanar(
                previous_side["face"],
                next_side["face"],
            )
        ):
            previous_width = previous_segment[
                f"{side_key}_width"
            ]
            next_width = next_segment[
                f"{side_key}_width"
            ]
            corner_point = planar_line_intersection(
                world_points[vertex_index],
                previous_segment["tangent"],
                next_segment["tangent"],
                previous_side["inward"],
                next_side["inward"],
                previous_side["normal"],
                previous_width,
                next_width,
                miter_limit,
            )
            if clamp_edge_overlaps:
                corner_point = bound_overlap_miter_point(
                    world_points[vertex_index],
                    corner_point,
                    (
                        {
                            "tangent": previous_segment["tangent"],
                            "length": previous_segment["length"],
                            "width": previous_width,
                        },
                        {
                            "tangent": next_segment["tangent"],
                            "length": next_segment["length"],
                            "width": next_width,
                        },
                    ),
                )
            # Coplanar support faces must keep one shared planar miter vertex.
            # The previous local bevel fallback inserted a triangular wedge at
            # sharp turns, which made the decal leave the supporting face and
            # created a visible diagonal topology seam. planar_line_intersection
            # already applies the global miter limit, so keep the result shared.

            source_vertex = source_vertex_at_world_point(
                chain_verts,
                world_matrix,
                world_points[vertex_index],
            )
            incident_selected = (
                [
                    edge
                    for edge in source_vertex.link_edges
                    if edge in selected_edge_set and len(edge.link_faces) == 2
                ]
                if source_vertex is not None
                else []
            )
            cache_key = (
                ("outer", source_vertex.index, previous_side["face"].index)
                if source_vertex is not None and len(incident_selected) >= 3
                else None
            )
            index = append_cached_junction_vertex(
                vertices_out,
                junction_vertex_cache,
                cache_key,
                offset_point_from_face_normals(
                    corner_point,
                    (
                        previous_side["normal"],
                        next_side["normal"],
                    ),
                    surface_offset,
                ),
            )

            outer[previous_segment_index][
                previous_slot
            ] = index
            outer[next_segment_index][
                next_slot
            ] = index
            return

        # If the support faces meet across another source edge, solve one
        # shared face-fan sector vertex just like the selected-graph builder.
        if assign_topology_sector_endpoints(
            vertex_index,
            side_key,
            previous_segment_index,
            next_segment_index,
            previous_segment,
            next_segment,
            previous_side,
            next_side,
            previous_slot,
            next_slot,
        ):
            return

        # Other different support planes use the bounded bevel-join fallback.
        assign_local_bevel_join(
            vertex_index,
            side_key,
            previous_segment_index,
            next_segment_index,
            previous_segment,
            next_segment,
            previous_side,
            next_side,
            previous_slot,
            next_slot,
        )

    for vertex_index in range(point_count):
        solve_side_at_vertex(vertex_index, "a")
        solve_side_at_vertex(vertex_index, "b")

    cumulative_lengths = [0.0]

    for index in range(1, point_count):
        cumulative_lengths.append(
            cumulative_lengths[-1]
            + (world_points[index] - world_points[index - 1]).length
        )

    created_faces = 0

    for segment_index, segment in enumerate(segment_data):
        start_index = segment_index
        end_index = (segment_index + 1) % point_count if closed else segment_index + 1

        a0 = outer[segment_index]["a_start"]
        a1 = outer[segment_index]["a_end"]
        b0 = outer[segment_index]["b_start"]
        b1 = outer[segment_index]["b_end"]
        c0 = center_indices[start_index]
        c1 = center_indices[end_index]

        if None in (a0, a1, b0, b1):
            continue

        # Keep UV width independent from the generated Face Width.
        # Face Width changes only geometry while texture scale remains stable.
        v0 = cumulative_lengths[start_index]

        if closed and end_index == 0:
            closing_length = (world_points[0] - world_points[-1]).length
            v1 = cumulative_lengths[-1] + closing_length
        else:
            v1 = cumulative_lengths[end_index]

        width_a_uv = max(float(segment.get("a_width", face_width)), EPSILON)
        width_b_uv = max(float(segment.get("b_width", face_width)), EPSILON)
        center_u = width_a_uv
        outer_b_u = width_a_uv + width_b_uv
        side_a_indices, side_a_uvs = oriented_face_with_uvs(
            (a0, c0, c1, a1),
            ((0.0, v0), (center_u, v0), (center_u, v1), (0.0, v1)),
            vertices_out,
            segment["a"]["normal"],
        )
        side_b_indices, side_b_uvs = oriented_face_with_uvs(
            (c0, b0, b1, c1),
            ((center_u, v0), (outer_b_u, v0), (outer_b_u, v1), (center_u, v1)),
            vertices_out,
            segment["b"]["normal"],
        )
        faces_out.append(side_a_indices)
        faces_out.append(side_b_indices)
        face_uvs_out.append(side_a_uvs)
        face_uvs_out.append(side_b_uvs)

        created_faces += 2

    for patch in corner_patches:
        patch_v = cumulative_lengths[patch["vertex_index"]]

        if patch["side"] == "a":
            indices = (
                patch["previous_index"],
                patch["center_index"],
                patch["next_index"],
            )
            uvs = (
                (0.0, patch_v),
                (0.5, patch_v),
                (0.0, patch_v),
            )
        else:
            indices = (
                patch["previous_index"],
                patch["next_index"],
                patch["center_index"],
            )
            uvs = (
                (1.0, patch_v),
                (1.0, patch_v),
                (0.5, patch_v),
            )

        indices, uvs = oriented_face_with_uvs(
            indices,
            uvs,
            vertices_out,
            patch["normal"],
        )
        faces_out.append(indices)
        face_uvs_out.append(uvs)
        created_faces += 1

    return created_faces








def build_corner_strip_tapered(
    chain_verts,
    chain_edges,
    closed,
    selected_edge_set,
    all_source_edges,
    world_matrix,
    normal_matrix,
    face_width,
    decal_amount,
    slice_positions,
    forced_slice_interval,
    taper_sliced_ends,
    force_taper_start,
    force_taper_end,
    slice_taper_length,
    auto_face_width,
    auto_width_samples,
    auto_width_clearance,
    clamp_edge_overlaps,
    overlap_clearance,
    surface_offset,
    miter_limit,
    use_face_loop_slide,
    vertices_out,
    faces_out,
    face_uvs_out,
    center_vertices_out,
    width_search_context=None,
    face_width_resolved=False,
    junction_vertex_cache=None,
):
    """
    Build one angle-split island.

    Thickness is solved only after splitting. Each side is offset inside its
    actual source-face plane. When consecutive segments share the same source
    face, they receive one exact planar miter vertex. When the supporting face
    changes, each segment keeps its own endpoint and a small local corner patch
    connects them, avoiding a stretched wedge across incompatible planes.
    """
    if not face_width_resolved:
        face_width = resolve_relative_face_width(
            face_width, all_source_edges, world_matrix
        )
    else:
        face_width = max(float(face_width), 1.0e-8)

    point_count = len(chain_verts)
    edge_count = len(chain_edges)

    if point_count < 2 or edge_count == 0:
        return 0

    if closed:
        work_world_points = [world_matrix @ vert.co for vert in chain_verts]
        work_chain_edges = chain_edges
        start_trimmed = False
        end_trimmed = False
    else:
        (
            work_world_points,
            work_chain_edges,
            start_trimmed,
            end_trimmed,
        ) = trim_open_chain_by_amount(
            chain_verts,
            chain_edges,
            world_matrix,
            decal_amount,
            slice_positions,
            forced_interval=forced_slice_interval,
        )
        start_trimmed = start_trimmed or bool(force_taper_start)
        end_trimmed = end_trimmed or bool(force_taper_end)

        # Keep the strip entirely quad-based. A virtual shoulder creates the
        # taper distance, while the sliced endpoint keeps a very small width
        # instead of collapsing to the centerline. This preserves the exact UV
        # and Quadrify topology used by v27.106.
        if taper_sliced_ends and slice_taper_length > EPSILON:
            if start_trimmed and len(work_world_points) >= 2:
                vector = work_world_points[1] - work_world_points[0]
                length = vector.length
                if length > EPSILON:
                    distance = min(slice_taper_length, length * 0.49)
                    if distance > max(1.0e-6, length * 1.0e-4):
                        shoulder = work_world_points[0] + vector.normalized() * distance
                        work_world_points.insert(1, shoulder)
                        work_chain_edges.insert(0, work_chain_edges[0])

            if end_trimmed and len(work_world_points) >= 2:
                vector = work_world_points[-2] - work_world_points[-1]
                length = vector.length
                if length > EPSILON:
                    distance = min(slice_taper_length, length * 0.49)
                    if distance > max(1.0e-6, length * 1.0e-4):
                        shoulder = work_world_points[-1] + vector.normalized() * distance
                        work_world_points.insert(len(work_world_points) - 1, shoulder)
                        work_chain_edges.append(work_chain_edges[-1])

    point_count = len(work_world_points)
    edge_count = len(work_chain_edges)

    if point_count < 2 or edge_count == 0:
        return 0

    world_points = work_world_points
    segment_data = []
    previous_pair = None

    for segment_index, edge in enumerate(work_chain_edges):
        start_index = segment_index
        end_index = (segment_index + 1) % point_count if closed else segment_index + 1

        p0 = world_points[start_index]
        p1 = world_points[end_index]
        tangent = safe_normalized(p1 - p0, Vector((1.0, 0.0, 0.0)))

        linked_faces = list(edge.link_faces)
        if len(linked_faces) != 2:
            return 0

        face_data = []

        for face in linked_faces:
            normal = transform_normal(normal_matrix, face.normal)
            inward = face_inward_direction(
                face,
                edge,
                world_matrix,
                normal_matrix,
                tangent,
            )
            face_data.append({
                "face": face,
                "normal": normal,
                "inward": inward,
            })

        side_a, side_b = assign_face_sides(face_data, previous_pair)
        previous_pair = (side_a, side_b)

        width_a = face_width
        width_b = face_width

        if auto_face_width or clamp_edge_overlaps:
            width_a = adaptive_width_for_edge_side(
                edge,
                side_a,
                tangent,
                face_width,
                auto_width_clearance,
                auto_width_samples,
                selected_edge_set,
                all_source_edges,
                world_matrix,
                clamp_boundaries=auto_face_width,
                clamp_selected_overlaps=clamp_edge_overlaps,
                overlap_clearance=overlap_clearance,
                width_search_context=width_search_context,
            )
            width_b = adaptive_width_for_edge_side(
                edge,
                side_b,
                tangent,
                face_width,
                auto_width_clearance,
                auto_width_samples,
                selected_edge_set,
                all_source_edges,
                world_matrix,
                clamp_boundaries=auto_face_width,
                clamp_selected_overlaps=clamp_edge_overlaps,
                overlap_clearance=overlap_clearance,
                width_search_context=width_search_context,
            )

        segment_data.append({
            "tangent": tangent,
            "length": (p1 - p0).length,
            "a": side_a,
            "b": side_b,
            "a_width": width_a,
            "b_width": width_b,
        })

    if clamp_edge_overlaps:
        stabilize_segment_overlap_widths(segment_data, closed)

    # Shared center row. This remains continuous inside the island so the final
    # angle-limited bevel works as one strip.
    center_indices = []

    for vertex_index, point in enumerate(world_points):
        incident_normals = []

        if closed or vertex_index > 0:
            previous_segment = segment_data[(vertex_index - 1) % edge_count]
            incident_normals.extend((
                previous_segment["a"]["normal"],
                previous_segment["b"]["normal"],
            ))

        if closed or vertex_index < point_count - 1:
            next_segment = segment_data[vertex_index % edge_count]
            incident_normals.extend((
                next_segment["a"]["normal"],
                next_segment["b"]["normal"],
            ))

        source_vertex = source_vertex_at_world_point(
            chain_verts,
            world_matrix,
            point,
        )
        incident_selected = (
            [
                edge
                for edge in source_vertex.link_edges
                if edge in selected_edge_set and len(edge.link_faces) == 2
            ]
            if source_vertex is not None
            else []
        )
        center_key = None
        center_point = offset_point_from_face_normals(
            point,
            incident_normals,
            surface_offset,
        )
        if source_vertex is not None and len(incident_selected) >= 3:
            center_key = ("center", source_vertex.index)
            center_point = selected_junction_center_point(
                source_vertex,
                selected_edge_set,
                world_matrix,
                normal_matrix,
                surface_offset,
            )

        center_index = append_cached_junction_vertex(
            vertices_out,
            junction_vertex_cache,
            center_key,
            center_point,
        )
        center_indices.append(center_index)
        center_vertices_out.append(center_index)

    # Per-segment outer endpoint slots.
    outer = [
        {
            "a_start": None,
            "a_end": None,
            "b_start": None,
            "b_end": None,
        }
        for _ in range(edge_count)
    ]

    corner_patches = []

    def selected_boundary_direction_count(source_vertex, boundary_edges):
        if source_vertex is None:
            return 0

        source_point = world_matrix @ source_vertex.co
        unique_directions = []

        for edge in boundary_edges:
            try:
                other_vertex = edge.other_vert(source_vertex)
            except Exception:
                continue

            direction = safe_normalized(
                (world_matrix @ other_vertex.co) - source_point,
                Vector((1.0, 0.0, 0.0)),
            )

            if not any(
                direction.dot(existing) > 0.9995
                for existing in unique_directions
            ):
                unique_directions.append(direction)

        return len(unique_directions)

    def loop_slide_point(
        source_vertex,
        boundary_edges,
        side,
        width,
        point,
    ):
        if (
            not use_face_loop_slide
            or source_vertex is None
        ):
            return None

        # Only use loop-slide on a true one-direction endpoint. Internal
        # corners and junctions should keep the existing bounded miter logic.
        if selected_boundary_direction_count(
            source_vertex,
            boundary_edges,
        ) != 1:
            return None

        slide_direction = connected_face_loop_slide_direction(
            source_vertex,
            boundary_edges,
            [side["face"]],
            world_matrix,
            side["normal"],
            side["inward"],
            required_distance=width,
        )

        if slide_direction is None:
            return None

        return point + slide_direction * width

    def make_outer_vertex(point, side, width):
        index = len(vertices_out)
        vertices_out.append(
            point
            + side["inward"] * width
            + side["normal"] * surface_offset
        )
        return index

    def assign_local_bevel_join(
        vertex_index,
        side_key,
        previous_segment_index,
        next_segment_index,
        previous_segment,
        next_segment,
        previous_side,
        next_side,
        previous_slot,
        next_slot,
    ):
        """
        Replace an unstable shared miter with two bounded endpoints and a small
        center patch. This is effectively a bevel join instead of a miter join.
        """
        previous_width = previous_segment[
            f"{side_key}_width"
        ]
        next_width = next_segment[
            f"{side_key}_width"
        ]
        previous_point = (
            world_points[vertex_index]
            + previous_side["inward"] * previous_width
            + previous_side["normal"] * surface_offset
        )
        next_point = (
            world_points[vertex_index]
            + next_side["inward"] * next_width
            + next_side["normal"] * surface_offset
        )
        merge_tolerance = max(
            1.0e-6,
            surface_offset * 4.0,
            min(previous_width, next_width) * 0.12,
        )

        if (
            previous_point - next_point
        ).length <= merge_tolerance:
            shared_index = len(vertices_out)
            vertices_out.append(
                (previous_point + next_point) * 0.5
            )
            outer[previous_segment_index][
                previous_slot
            ] = shared_index
            outer[next_segment_index][
                next_slot
            ] = shared_index
            return

        previous_index = len(vertices_out)
        vertices_out.append(previous_point)

        next_index = len(vertices_out)
        vertices_out.append(next_point)

        outer[previous_segment_index][
            previous_slot
        ] = previous_index
        outer[next_segment_index][
            next_slot
        ] = next_index

        corner_patches.append({
            "side": side_key,
            "previous_index": previous_index,
            "next_index": next_index,
            "center_index": center_indices[vertex_index],
            "normal": safe_normalized(
                previous_side["normal"]
                + next_side["normal"],
                next_side["normal"],
            ),
            "vertex_index": vertex_index,
        })

    def solve_side_at_vertex(vertex_index, side_key):
        """
        Assign outer indices around one chain vertex for side A or B.
        """
        if not closed and vertex_index == 0:
            side = segment_data[0][side_key]
            side_width = segment_data[0][f"{side_key}_width"]

            if (
                start_trimmed
                and taper_sliced_ends
                and slice_taper_length > EPSILON
            ):
                # Keep a small flat cap at the taper tip instead of collapsing
                # both outer vertices onto the centerline. A collapsed tip reads
                # as a single sharp triangle; a narrow blunt end keeps the quad
                # topology and matches the requested taper silhouette.
                tip_width = side_width * SLICE_TAPER_TIP_WIDTH_FACTOR
                point = world_points[0] + side["inward"] * tip_width
                index = len(vertices_out)
                vertices_out.append(point + side["normal"] * surface_offset)
                outer[0][f"{side_key}_start"] = index
                return

            if start_trimmed:
                point = world_points[0] + side["inward"] * side_width
            else:
                source_vertex = chain_verts[0]
                boundary_edges = [
                    edge
                    for edge in source_vertex.link_edges
                    if edge in selected_edge_set
                ]
                point = loop_slide_point(
                    source_vertex,
                    boundary_edges,
                    side,
                    side_width,
                    world_points[0],
                )

                if point is None:
                    point = endpoint_miter_point(
                        source_vertex=source_vertex,
                        current_edge=work_chain_edges[0],
                        current_tangent_away=segment_data[0]["tangent"],
                        side=side,
                        selected_edge_set=selected_edge_set,
                        world_matrix=world_matrix,
                        normal_matrix=normal_matrix,
                        vertex_point=world_points[0],
                        face_width=side_width,
                        miter_limit=miter_limit,
                    )

            if start_trimmed:
                index = len(vertices_out)
                vertices_out.append(
                    point + side["normal"] * surface_offset
                )
            else:
                index = append_endpoint_junction_vertex(
                    vertices_out,
                    junction_vertex_cache,
                    source_vertex,
                    work_chain_edges[0],
                    side,
                    selected_edge_set,
                    point,
                    surface_offset,
                )
            outer[0][f"{side_key}_start"] = index
            return

        if not closed and vertex_index == point_count - 1:
            side = segment_data[-1][side_key]
            side_width = segment_data[-1][f"{side_key}_width"]

            if (
                end_trimmed
                and taper_sliced_ends
                and slice_taper_length > EPSILON
            ):
                # Keep a small flat cap at the taper tip (see start-side note).
                tip_width = side_width * SLICE_TAPER_TIP_WIDTH_FACTOR
                point = world_points[-1] + side["inward"] * tip_width
                index = len(vertices_out)
                vertices_out.append(point + side["normal"] * surface_offset)
                outer[-1][f"{side_key}_end"] = index
                return

            if end_trimmed:
                point = world_points[-1] + side["inward"] * side_width
            else:
                source_vertex = chain_verts[-1]
                boundary_edges = [
                    edge
                    for edge in source_vertex.link_edges
                    if edge in selected_edge_set
                ]
                point = loop_slide_point(
                    source_vertex,
                    boundary_edges,
                    side,
                    side_width,
                    world_points[-1],
                )

                if point is None:
                    point = endpoint_miter_point(
                        source_vertex=source_vertex,
                        current_edge=work_chain_edges[-1],
                        current_tangent_away=-segment_data[-1]["tangent"],
                        side=side,
                        selected_edge_set=selected_edge_set,
                        world_matrix=world_matrix,
                        normal_matrix=normal_matrix,
                        vertex_point=world_points[-1],
                        face_width=side_width,
                        miter_limit=miter_limit,
                    )

            if end_trimmed:
                index = len(vertices_out)
                vertices_out.append(
                    point + side["normal"] * surface_offset
                )
            else:
                index = append_endpoint_junction_vertex(
                    vertices_out,
                    junction_vertex_cache,
                    source_vertex,
                    work_chain_edges[-1],
                    side,
                    selected_edge_set,
                    point,
                    surface_offset,
                )
            outer[-1][f"{side_key}_end"] = index
            return

        previous_segment_index = (vertex_index - 1) % edge_count
        next_segment_index = vertex_index % edge_count

        previous_segment = segment_data[previous_segment_index]
        next_segment = segment_data[next_segment_index]
        previous_side = previous_segment[side_key]
        next_side = next_segment[side_key]

        previous_slot = f"{side_key}_end"
        next_slot = f"{side_key}_start"

        if (
            previous_side["face"] == next_side["face"]
            or faces_are_coplanar(
                previous_side["face"],
                next_side["face"],
            )
        ):
            previous_width = previous_segment[
                f"{side_key}_width"
            ]
            next_width = next_segment[
                f"{side_key}_width"
            ]
            corner_point = planar_line_intersection(
                world_points[vertex_index],
                previous_segment["tangent"],
                next_segment["tangent"],
                previous_side["inward"],
                next_side["inward"],
                previous_side["normal"],
                previous_width,
                next_width,
                miter_limit,
            )
            if clamp_edge_overlaps:
                corner_point = bound_overlap_miter_point(
                    world_points[vertex_index],
                    corner_point,
                    (
                        {
                            "tangent": previous_segment["tangent"],
                            "length": previous_segment["length"],
                            "width": previous_width,
                        },
                        {
                            "tangent": next_segment["tangent"],
                            "length": next_segment["length"],
                            "width": next_width,
                        },
                    ),
                )
            # Coplanar support faces must keep one shared planar miter vertex.
            # The previous local bevel fallback inserted a triangular wedge at
            # sharp turns, which made the decal leave the supporting face and
            # created a visible diagonal topology seam. planar_line_intersection
            # already applies the global miter limit, so keep the result shared.

            source_vertex = source_vertex_at_world_point(
                chain_verts,
                world_matrix,
                world_points[vertex_index],
            )
            incident_selected = (
                [
                    edge
                    for edge in source_vertex.link_edges
                    if edge in selected_edge_set and len(edge.link_faces) == 2
                ]
                if source_vertex is not None
                else []
            )
            cache_key = (
                ("outer", source_vertex.index, previous_side["face"].index)
                if source_vertex is not None and len(incident_selected) >= 3
                else None
            )
            index = append_cached_junction_vertex(
                vertices_out,
                junction_vertex_cache,
                cache_key,
                offset_point_from_face_normals(
                    corner_point,
                    (
                        previous_side["normal"],
                        next_side["normal"],
                    ),
                    surface_offset,
                ),
            )

            outer[previous_segment_index][
                previous_slot
            ] = index
            outer[next_segment_index][
                next_slot
            ] = index
            return

        source_vertex = source_vertex_at_world_point(
            chain_verts,
            world_matrix,
            world_points[vertex_index],
        )
        if (
            source_vertex is not None
            and support_faces_share_edge_at_vertex(
                previous_side["face"],
                next_side["face"],
                source_vertex,
            )
        ):
            previous_index, next_index = topology_sector_endpoint_indices(
                source_vertex=source_vertex,
                previous_edge=work_chain_edges[previous_segment_index],
                next_edge=work_chain_edges[next_segment_index],
                previous_tangent_away=-previous_segment["tangent"],
                next_tangent_away=next_segment["tangent"],
                previous_side=previous_side,
                next_side=next_side,
                previous_width=previous_segment[f"{side_key}_width"],
                next_width=next_segment[f"{side_key}_width"],
                selected_edge_set=selected_edge_set,
                world_matrix=world_matrix,
                normal_matrix=normal_matrix,
                vertex_point=world_points[vertex_index],
                miter_limit=miter_limit,
                surface_offset=surface_offset,
                vertices_out=vertices_out,
                junction_vertex_cache=junction_vertex_cache,
            )
            outer[previous_segment_index][previous_slot] = previous_index
            outer[next_segment_index][next_slot] = next_index
            return

        # Other different support planes use the bounded bevel-join fallback.
        assign_local_bevel_join(
            vertex_index,
            side_key,
            previous_segment_index,
            next_segment_index,
            previous_segment,
            next_segment,
            previous_side,
            next_side,
            previous_slot,
            next_slot,
        )

    for vertex_index in range(point_count):
        solve_side_at_vertex(vertex_index, "a")
        solve_side_at_vertex(vertex_index, "b")

    # Build longitudinal UV distance from the final generated centerline,
    # after taper tips and shoulder vertices have been inserted and after the
    # surface offset has been solved. This keeps the taper UV length aligned
    # with the actual finished geometry rather than the pre-taper source path.
    final_center_points = [vertices_out[index] for index in center_indices]
    cumulative_lengths = [0.0]

    for index in range(1, point_count):
        cumulative_lengths.append(
            cumulative_lengths[-1]
            + (final_center_points[index] - final_center_points[index - 1]).length
        )

    created_faces = 0

    for segment_index, segment in enumerate(segment_data):
        start_index = segment_index
        end_index = (segment_index + 1) % point_count if closed else segment_index + 1

        a0 = outer[segment_index]["a_start"]
        a1 = outer[segment_index]["a_end"]
        b0 = outer[segment_index]["b_start"]
        b1 = outer[segment_index]["b_end"]
        c0 = center_indices[start_index]
        c1 = center_indices[end_index]

        if None in (a0, a1, b0, b1):
            continue

        # Resolve longitudinal UV coordinates before constructing the face UVs.
        # The previous build referenced v0/v1 before assigning them, which made
        # the Generate operator stop with a runtime NameError.
        v0 = cumulative_lengths[start_index]

        if closed and end_index == 0:
            closing_length = (world_points[0] - world_points[-1]).length
            v1 = cumulative_lengths[-1] + closing_length
        else:
            v1 = cumulative_lengths[end_index]

        # A sliced taper tip merges both outer vertices into the centerline.
        # Emit real triangles at that end rather than degenerate quads. UVs keep
        # the tip at U=0.5 and the shoulder at the original side boundaries.
        side_a_indices = (a0, c0, c1, a1)
        side_b_indices = (c0, b0, b1, c1)
        # Tapered/sliced strips are authored in their final horizontal UV
        # orientation. U follows distance along the generated centerline and V
        # spans the two decal sides. This avoids relying on a later centerline
        # rotation, which becomes ambiguous on very short Amount-cut islands.
        width_a_uv = max(float(segment.get("a_width", face_width)), EPSILON)
        width_b_uv = max(float(segment.get("b_width", face_width)), EPSILON)
        center_v = width_a_uv
        outer_b_v = width_a_uv + width_b_uv
        side_a_uvs = ((v0, 0.0), (v0, center_v), (v1, center_v), (v1, 0.0))
        side_b_uvs = ((v0, center_v), (v0, outer_b_v), (v1, outer_b_v), (v1, center_v))

        if a0 == c0:
            side_a_indices = (c0, c1, a1)
            side_a_uvs = ((v0, center_v), (v1, center_v), (v1, 0.0))
        elif a1 == c1:
            side_a_indices = (a0, c0, c1)
            side_a_uvs = ((v0, 0.0), (v0, center_v), (v1, center_v))

        if b0 == c0:
            side_b_indices = (c0, b1, c1)
            side_b_uvs = ((v0, center_v), (v1, outer_b_v), (v1, center_v))
        elif b1 == c1:
            side_b_indices = (c0, b0, c1)
            side_b_uvs = ((v0, center_v), (v0, outer_b_v), (v1, center_v))

        side_a_indices, side_a_uvs = oriented_face_with_uvs(
            side_a_indices,
            side_a_uvs,
            vertices_out,
            segment["a"]["normal"],
        )
        side_b_indices, side_b_uvs = oriented_face_with_uvs(
            side_b_indices,
            side_b_uvs,
            vertices_out,
            segment["b"]["normal"],
        )
        faces_out.append(side_a_indices)
        face_uvs_out.append(side_a_uvs)
        faces_out.append(side_b_indices)
        face_uvs_out.append(side_b_uvs)

        created_faces += 2

    for patch in corner_patches:
        patch_v = cumulative_lengths[patch["vertex_index"]]

        if patch["side"] == "a":
            indices = (
                patch["previous_index"],
                patch["center_index"],
                patch["next_index"],
            )
            uvs = (
                (patch_v, 0.0),
                (patch_v, 0.5),
                (patch_v, 0.0),
            )
        else:
            indices = (
                patch["previous_index"],
                patch["next_index"],
                patch["center_index"],
            )
            uvs = (
                (patch_v, 1.0),
                (patch_v, 1.0),
                (patch_v, 0.5),
            )

        indices, uvs = oriented_face_with_uvs(
            indices,
            uvs,
            vertices_out,
            patch["normal"],
        )
        faces_out.append(indices)
        face_uvs_out.append(uvs)
        created_faces += 1

    return created_faces







def build_world_bvh_from_bmesh(bm, world_matrix):
    """Build one world-space BVH for local crevice raycasts."""
    bm.verts.ensure_lookup_table()
    bm.faces.ensure_lookup_table()

    vertices = [
        world_matrix @ vert.co
        for vert in bm.verts
    ]
    polygons = [
        tuple(vert.index for vert in face.verts)
        for face in bm.faces
        if len(face.verts) >= 3
    ]

    if not vertices or not polygons:
        return None

    return BVHTree.FromPolygons(
        vertices,
        polygons,
        all_triangles=False,
    )


def resolved_crevice_ao_distance(
    requested_distance,
    face_width,
):
    if requested_distance > EPSILON:
        return requested_distance

    return max(
        face_width * 4.0,
        1.0e-4,
    )


def crevice_ao_threshold(removal_amount):
    """
    Map Crevice Removal to required local occlusion.

    Low values only remove strongly enclosed crevices. At 1.0, even a modest
    but consistent local occlusion score is enough.
    """
    amount = max(0.0, min(1.0, removal_amount))
    return 0.78 - amount * 0.63


def local_cross_section_ao_score(
    bvh,
    sample_frames,
    distance,
    ray_samples,
    bias,
):
    """
    Cast a fan of rays in the cross-section perpendicular to the edge path.

    Convex outer edges point into largely empty space and receive few hits.
    Concave grooves are enclosed by nearby surfaces and receive many hits.
    """
    if bvh is None or not sample_frames:
        return 0.0

    ray_samples = max(4, int(ray_samples))
    distance = max(distance, bias * 4.0, 1.0e-5)
    fan_limit = radians(82.0)
    hit_count = 0
    ray_count = 0

    for point, open_normal, tangent in sample_frames:
        tangent = safe_normalized(
            tangent,
            Vector((1.0, 0.0, 0.0)),
        )
        open_normal = (
            open_normal
            - tangent * open_normal.dot(tangent)
        )
        open_normal = safe_normalized(
            open_normal,
            Vector((0.0, 0.0, 1.0)),
        )
        side = safe_normalized(
            tangent.cross(open_normal),
            Vector((0.0, 1.0, 0.0)),
        )
        open_normal = safe_normalized(
            side.cross(tangent),
            open_normal,
        )
        origin = point + open_normal * bias

        for sample_index in range(ray_samples):
            factor = (
                (sample_index + 0.5)
                / ray_samples
            )
            angle = (
                -fan_limit
                + factor * fan_limit * 2.0
            )
            direction = safe_normalized(
                open_normal * cos(angle)
                + side * sin(angle),
                open_normal,
            )
            location, _normal, _index, hit_distance = bvh.ray_cast(
                origin,
                direction,
                distance,
            )
            ray_count += 1

            if (
                location is not None
                and hit_distance is not None
                and hit_distance > bias * 0.25
            ):
                hit_count += 1

    if ray_count == 0:
        return 0.0

    return hit_count / ray_count


def edge_ao_score(
    edge,
    world_matrix,
    normal_matrix,
    bvh,
    distance,
    ray_samples,
    bias,
):
    if len(edge.link_faces) != 2:
        return 0.0

    point_a = world_matrix @ edge.verts[0].co
    point_b = world_matrix @ edge.verts[1].co
    tangent = safe_normalized(
        point_b - point_a,
        Vector((1.0, 0.0, 0.0)),
    )
    normal_a = transform_normal(
        normal_matrix,
        edge.link_faces[0].normal,
    )
    normal_b = transform_normal(
        normal_matrix,
        edge.link_faces[1].normal,
    )
    open_normal = safe_normalized(
        normal_a + normal_b,
        normal_a,
    )
    sample_frames = [
        (
            point_a.lerp(point_b, factor),
            open_normal,
            tangent,
        )
        for factor in (0.2, 0.5, 0.8)
    ]

    return local_cross_section_ao_score(
        bvh,
        sample_frames,
        distance,
        ray_samples,
        bias,
    )


def edge_is_concave_geometric(
    edge,
    world_matrix,
    normal_matrix,
):
    """
    Classify a manifold edge without relying only on BMEdge.is_convex.

    For a convex outer corner, each neighboring face center lies behind the
    other face's outward plane. For an inward crevice, both cross-plane tests
    are positive. This remains independent of edge vertex order.
    """
    if len(edge.link_faces) != 2:
        return False

    face_a, face_b = edge.link_faces
    point_a = world_matrix @ edge.verts[0].co
    point_b = world_matrix @ edge.verts[1].co
    midpoint = (point_a + point_b) * 0.5
    tangent = safe_normalized(
        point_b - point_a,
        Vector((1.0, 0.0, 0.0)),
    )

    center_a = world_matrix @ face_a.calc_center_median()
    center_b = world_matrix @ face_b.calc_center_median()

    direction_a = center_a - midpoint
    direction_b = center_b - midpoint

    # Remove any along-edge component so long or skewed polygons do not bias
    # the test.
    direction_a -= tangent * direction_a.dot(tangent)
    direction_b -= tangent * direction_b.dot(tangent)

    if direction_a.length_squared <= EPSILON:
        direction_a = Vector((0.0, 0.0, 0.0))
    else:
        direction_a.normalize()

    if direction_b.length_squared <= EPSILON:
        direction_b = Vector((0.0, 0.0, 0.0))
    else:
        direction_b.normalize()

    normal_a = transform_normal(
        normal_matrix,
        face_a.normal,
    )
    normal_b = transform_normal(
        normal_matrix,
        face_b.normal,
    )

    score = (
        normal_a.dot(direction_b)
        + normal_b.dot(direction_a)
    )

    if abs(score) > 1.0e-5:
        return score > 0.0

    # Degenerate fallback for unusually symmetric topology.
    try:
        return not edge.is_convex
    except (AttributeError, RuntimeError):
        try:
            return edge.calc_face_angle_signed(0.0) < 0.0
        except (AttributeError, ValueError, RuntimeError):
            return False


def filter_edges_by_crevice(
    edges,
    removal_amount,
    world_matrix,
    normal_matrix,
    detection_mode="AO",
    bvh=None,
    ao_distance=0.0,
    ao_samples=8,
    face_width=0.06,
    surface_offset=0.002,
):
    """Remove locally occluded crevice edges while retaining exposed edges."""
    amount = max(0.0, min(1.0, removal_amount))

    if amount <= EPSILON:
        return list(edges)

    angle_threshold = pi * (1.0 - amount)
    ao_threshold = crevice_ao_threshold(amount)
    resolved_distance = resolved_crevice_ao_distance(
        ao_distance,
        face_width,
    )
    bias = max(
        surface_offset * 2.0,
        resolved_distance * 0.005,
        1.0e-5,
    )
    kept = []

    for edge in edges:
        if len(edge.link_faces) != 2:
            kept.append(edge)
            continue

        try:
            face_angle = edge.calc_face_angle(0.0)
        except (ValueError, RuntimeError):
            kept.append(edge)
            continue

        if face_angle <= 1.0e-4:
            kept.append(edge)
            continue

        if detection_mode == "AO" and bvh is not None:
            if face_angle < angle_threshold:
                kept.append(edge)
                continue

            if not edge_is_concave_geometric(
                edge,
                world_matrix,
                normal_matrix,
            ):
                kept.append(edge)
                continue

            score = edge_ao_score(
                edge,
                world_matrix,
                normal_matrix,
                bvh,
                resolved_distance,
                ao_samples,
                bias,
            )
            should_remove = score >= ao_threshold
        else:
            should_remove = (
                edge_is_concave_geometric(
                    edge,
                    world_matrix,
                    normal_matrix,
                )
                and face_angle >= angle_threshold
            )

        if should_remove:
            continue

        kept.append(edge)

    return kept


def select_edges_by_crevice_mask(
    edges,
    world_matrix,
    normal_matrix,
    detection_mode="AO",
    bvh=None,
    ao_distance=0.0,
    ao_samples=8,
    face_width=0.06,
    surface_offset=0.002,
):
    """Invert the full-strength Crevice Removal mask.

    The returned edges are exactly those the existing mask would remove at
    strength 1.0. This keeps Generate Crevices consistent with the established
    AO/Geometry classifier without overloading the removal slider's meaning.
    """
    candidates = list(edges)
    kept = set(filter_edges_by_crevice(
        candidates,
        1.0,
        world_matrix,
        normal_matrix,
        detection_mode,
        bvh,
        ao_distance,
        ao_samples,
        face_width,
        surface_offset,
    ))
    return [edge for edge in candidates if edge not in kept]


def filter_edges_by_minimum_length(
    edges,
    world_matrix,
    minimum_length,
):
    """Keep only edges whose transformed world-space length meets the limit."""
    if minimum_length <= 0.0:
        return list(edges)

    kept = []

    for edge in edges:
        p0 = world_matrix @ edge.verts[0].co
        p1 = world_matrix @ edge.verts[1].co

        if (p1 - p0).length >= minimum_length:
            kept.append(edge)

    return kept


def filter_edge_chains_by_minimum_length(
    edges,
    world_matrix,
    minimum_length,
):
    """
    Keep complete connected chains whose total world-space length meets the
    limit.

    Manual Edit Mode selection should not lose small intermediate segments from
    an otherwise valid continuous edge. Automatic generation still uses the
    original per-edge filter to reject isolated tiny topology.
    """
    if minimum_length <= 0.0:
        return list(edges)

    kept = []
    seen = set()

    for _chain_verts, chain_edges, _closed in extract_edge_chains(
        edges,
        world_matrix,
    ):
        total_length = 0.0

        for edge in chain_edges:
            point_a = world_matrix @ edge.verts[0].co
            point_b = world_matrix @ edge.verts[1].co
            total_length += (point_b - point_a).length

        if total_length + EPSILON < minimum_length:
            continue

        for edge in chain_edges:
            if edge in seen:
                continue

            seen.add(edge)
            kept.append(edge)

    return kept


def filter_edges_by_amount(edges, amount, seed):
    """
    Keep an exact percentage of eligible edges using a deterministic shuffle.

    1.0 keeps every edge.
    0.5 keeps roughly half as disconnected/randomly distributed edge segments.
    0.0 keeps no edges.
    """
    edge_list = list(edges)

    if not edge_list:
        return []

    clamped_amount = max(0.0, min(1.0, amount))

    if clamped_amount >= 1.0 - EPSILON:
        return edge_list

    if clamped_amount <= EPSILON:
        return []

    keep_count = int(round(len(edge_list) * clamped_amount))
    keep_count = max(1, min(len(edge_list), keep_count))

    # Sort first so the same mesh and seed always produce the same result.
    edge_list.sort(key=lambda edge: edge.index)

    rng = random.Random(seed)
    rng.shuffle(edge_list)

    kept = edge_list[:keep_count]
    kept.sort(key=lambda edge: edge.index)
    return kept




def chain_world_length(chain_verts, chain_edges, closed, world_matrix):
    """Return the transformed length of one ordered source chain."""
    if not chain_edges or len(chain_verts) < 2:
        return 0.0

    points = [world_matrix @ vert.co for vert in chain_verts]
    total = sum(
        (points[index + 1] - points[index]).length
        for index in range(len(points) - 1)
    )

    if closed and len(points) > 2:
        total += (points[0] - points[-1]).length

    return total


def mix_random_u64(value):
    """Avalanche one integer into a well-distributed deterministic 64-bit value."""
    mask = (1 << 64) - 1
    value = (int(value) + 0x9E3779B97F4A7C15) & mask
    value = ((value ^ (value >> 30)) * 0xBF58476D1CE4E5B9) & mask
    value = ((value ^ (value >> 27)) * 0x94D049BB133111EB) & mask
    return (value ^ (value >> 31)) & mask


def chain_random_signature(chain_verts, chain_edges, world_matrix):
    """Return an orientation-independent identity for one source path.

    Edge indices distinguish separate paths on one object. Quantized world
    positions additionally decorrelate repeated topology such as neighboring
    arches, while sorting makes reversing the chain walker leave the result
    unchanged.
    """
    signature = 0xCBF29CE484222325
    for edge_index in sorted(edge.index for edge in chain_edges):
        signature = mix_random_u64(
            signature ^ mix_random_u64(edge_index + 1)
        )

    quantized_points = sorted(
        tuple(int(round(component * 100000.0)) for component in point)
        for point in (world_matrix @ vertex.co for vertex in chain_verts)
    )
    for point in quantized_points:
        for component in point:
            signature = mix_random_u64(
                signature ^ mix_random_u64(component)
            )
    return signature


def chain_random_stream_seed(seed, signature, stream):
    """Derive an independent repeatable random stream for one source path."""
    return mix_random_u64(
        mix_random_u64(seed)
        ^ mix_random_u64(signature)
        ^ mix_random_u64(stream)
    )


def randomized_face_widths_for_edge_groups(
    edge_groups,
    minimum_face_width,
    maximum_face_width,
    seed,
    world_matrix,
):
    """Map every edge to a stable width per disconnected decal path."""
    widths = {}
    all_edges = list(dict.fromkeys(
        edge
        for group in (edge_groups or ())
        for edge in group
    ))
    selected_edge_set = set(all_edges)
    remaining = set(all_edges)

    while remaining:
        first_edge = min(remaining, key=lambda edge: edge.index)
        remaining.remove(first_edge)
        component_edges = []
        pending = [first_edge]
        while pending:
            edge = pending.pop()
            component_edges.append(edge)
            for vertex in edge.verts:
                for neighbor in vertex.link_edges:
                    if neighbor in remaining and neighbor in selected_edge_set:
                        remaining.remove(neighbor)
                        pending.append(neighbor)

        component_edges.sort(key=lambda edge: edge.index)
        component_vertices = list({
            vertex
            for edge in component_edges
            for vertex in edge.verts
        })
        width = randomized_face_width(
            minimum_face_width,
            maximum_face_width,
            seed,
            chain_random_signature(
                component_vertices,
                component_edges,
                world_matrix,
            ),
        )
        for edge in component_edges:
            widths[edge] = width
    return widths


def select_chains_by_global_amount(
    source_chains,
    amount,
    seed,
    world_matrix,
    pins,
    minimum_fragment_length=0.0,
    edge_slice=0.0,
    maximum_decal_length=0.0,
    decal_layer=None,
    minimum_gap_length=0.0,
):
    """Resolve Decal Amount proportionally inside every connected chain.

    The old implementation consumed one global length budget in randomized
    chain order. That made short chains survive whole (or disappear whole)
    before long chains were ever fragmented. Here each chain receives the same
    coverage ratio, so reducing Amount immediately cuts long chains into
    separated retained intervals while shorter chains are trimmed rather than
    treated as all-or-nothing selections.
    """
    amount = max(0.0, min(1.0, amount))
    maximum_decal_length = max(0.0, maximum_decal_length)
    minimum = max(0.0, minimum_fragment_length)
    minimum_gap = max(0.0, float(minimum_gap_length))

    if amount <= EPSILON:
        return []

    records = []
    for source_index, (verts, edges, closed) in enumerate(source_chains):
        length = chain_world_length(verts, edges, closed, world_matrix)
        if length <= EPSILON:
            continue
        records.append({
            "verts": verts,
            "edges": edges,
            "closed": closed,
            "length": length,
            "source_index": source_index,
            "random_signature": chain_random_signature(
                verts,
                edges,
                world_matrix,
            ),
            "pin_index": pin_index_for_layer_cycle(
                source_index,
                pins,
                decal_layer,
                seed,
            ),
        })

    if not records:
        return []

    selected = []

    # Give connected chains different seeded densities while preserving the
    # requested total world-space coverage. This produces localized worn and
    # clean regions instead of applying the same ratio everywhere.
    target_keep_length = sum(record["length"] for record in records) * amount
    density_weights = []
    for record in records:
        rng = random.Random(
            chain_random_stream_seed(
                seed,
                record["random_signature"],
                0x5F3759DF,
            )
        )
        density_weights.append(__import__('math').exp(rng.uniform(-0.9, 0.9)))

    low_scale = 0.0
    high_scale = max(1.0 / min(density_weights), 1.0)
    for _iteration in range(48):
        middle = (low_scale + high_scale) * 0.5
        allocated = sum(
            record["length"] * min(1.0, middle * weight)
            for record, weight in zip(records, density_weights)
        )
        if allocated < target_keep_length:
            low_scale = middle
        else:
            high_scale = middle

    chain_keep_lengths = [
        record["length"] * min(1.0, high_scale * weight)
        for record, weight in zip(records, density_weights)
    ]

    def randomized_partition(total, count, rng, minimum_value=0.0, maximum_value=None):
        """Split total into deterministic uneven positive pieces."""
        if count <= 0:
            return []
        if count == 1:
            return [total]

        minimum_value = max(0.0, min(float(minimum_value), total / count))
        values = [minimum_value] * count
        remaining = max(0.0, total - minimum_value * count)
        active = set(range(count))

        while remaining > EPSILON and active:
            weights = {
                index: 0.08 + rng.random() ** 2.2
                for index in active
            }
            weight_total = sum(weights.values())
            distributed = 0.0
            saturated = set()
            for index in active:
                addition = remaining * weights[index] / weight_total
                if maximum_value is not None:
                    capacity = max(0.0, float(maximum_value) - values[index])
                    addition = min(addition, capacity)
                    if capacity - addition <= EPSILON:
                        saturated.add(index)
                values[index] += addition
                distributed += addition
            if distributed <= EPSILON:
                break
            remaining -= distributed
            active -= saturated

        if remaining > EPSILON:
            values[-1] += remaining
        return values

    for record, keep_length in zip(records, chain_keep_lengths):
        length = record["length"]

        # Full amount preserves the untouched chain exactly.
        if amount >= 1.0 - EPSILON and maximum_decal_length <= EPSILON:
            kept = dict(record)
            kept["amount"] = 1.0
            kept["slice_interval"] = None
            selected.append(kept)
            continue

        if keep_length <= EPSILON:
            continue

        local_amount = max(0.0, min(1.0, keep_length / length))

        # A locally saturated chain becomes one dense region even when other
        # chains are sparse. Maximum Decal Length may still split it below.
        if (
            local_amount >= 1.0 - EPSILON
            and maximum_decal_length <= EPSILON
        ):
            kept = dict(record)
            kept["amount"] = 1.0
            kept["slice_interval"] = None
            selected.append(kept)
            continue

        # Long chains should begin fragmenting as soon as Amount is reduced.
        # The preferred maximum uninterrupted piece shrinks with Amount, while
        # Maximum Decal Length remains a strict user-supplied cap.
        automatic_limit = length * max(0.06, 0.48 * local_amount)
        fragment_limit = automatic_limit
        if maximum_decal_length > EPSILON:
            fragment_limit = min(fragment_limit, maximum_decal_length)
        fragment_limit = max(fragment_limit, EPSILON)

        fragment_count = max(1, int(__import__('math').ceil(keep_length / fragment_limit)))

        # A genuinely long reduced chain should never remain one uninterrupted
        # island when enough room exists for a visible gap.
        enough_for_two = length >= max(minimum * 3.0, keep_length * 1.28)
        if local_amount < 1.0 - EPSILON and enough_for_two:
            fragment_count = max(fragment_count, 2)

        # Avoid generating fragments below the practical minimum. Very short
        # chains remain one trimmed interval rather than disappearing whole.
        if minimum > EPSILON and keep_length >= minimum:
            fragment_count = min(
                fragment_count,
                max(1, int(keep_length / minimum)),
            )
        elif keep_length < minimum:
            fragment_count = 1

        removed_length = max(0.0, length - keep_length)

        # Independent fragments need a real visible gap between them. The
        # old zero-minimum partition regularly produced gaps far narrower
        # than the decal itself. Their separately tapered endpoint rows then
        # looked like split vertices or triangular cracks, especially when a
        # tiny gap landed near a segmented source-edge junction.
        if fragment_count > 1 and minimum_gap > EPSILON:
            maximum_fragments_for_visible_gaps = (
                1 + int((removed_length + EPSILON) / minimum_gap)
            )
            fragment_count = min(
                fragment_count,
                max(1, maximum_fragments_for_visible_gaps),
            )

        rng = random.Random(
            chain_random_stream_seed(
                seed,
                record["random_signature"],
                0xA511E9B3,
            )
        )

        # Vary both fragment and gap lengths. Squared random weights create a
        # few dominant gaps and several small ones, visually clustering nearby
        # fragments while keeping the exact allocated coverage.
        strict_fragment_maximum = (
            maximum_decal_length
            if maximum_decal_length > EPSILON
            else None
        )
        fragment_lengths = randomized_partition(
            keep_length,
            fragment_count,
            rng,
            minimum_value=(
                minimum
                if minimum > EPSILON and keep_length >= minimum * fragment_count
                else 0.0
            ),
            maximum_value=strict_fragment_maximum,
        )
        internal_gap_total = minimum_gap * max(0, fragment_count - 1)
        remaining_gap_length = max(0.0, removed_length - internal_gap_total)
        gap_lengths = randomized_partition(
            remaining_gap_length,
            fragment_count + 1,
            rng,
        )
        for gap_index in range(1, fragment_count):
            gap_lengths[gap_index] += minimum_gap

        cursor = gap_lengths[0]
        for fragment_index in range(fragment_count):
            fragment_length = fragment_lengths[fragment_index]
            start_distance = max(0.0, min(length, cursor))
            end_distance = max(start_distance, min(length, start_distance + fragment_length))
            cursor = end_distance + gap_lengths[fragment_index + 1]

            start_fraction = start_distance / length
            end_fraction = end_distance / length
            if end_fraction - start_fraction <= 1.0e-5:
                continue

            kept = dict(record)
            kept["amount"] = 1.0
            kept["slice_interval"] = (start_fraction, end_fraction)
            kept["fragment_index"] = fragment_index

            # Closed loops are linearized before interval trimming. Each kept
            # interval then becomes an open tapered island with real gaps.
            if kept["closed"]:
                kept["verts"] = list(kept["verts"]) + [kept["verts"][0]]
                kept["closed"] = False

            selected.append(kept)

    selected.sort(key=lambda record: (
        record["source_index"],
        record.get("fragment_index", -1),
    ))
    return selected

def interactive_endpoint_taper_flags(chain_verts, chain_edges, selected_edge_set, world_matrix, continuation_dot_threshold=0.75):
    """Return (taper_start, taper_end) for interactive open chains.

    Interactive placement of a whole edge/chain now keeps SQUARE ends. Automatic
    endpoint detection was unreliable on production meshes: it either pointed
    every short split-edge junction or pointed real corners, producing the
    spindle shapes shown in user reports.

    Tapered ends are still produced for explicit cuts:
    - Ctrl partial-edge placement (an interactive slice interval), and
    - a global/positive Decal Amount or Maximum Decal Length slice,
    both of which route through the ``taper_sliced_ends`` slice path rather than
    this function. Those are the genuine "marked part" cuts a user asks to point.

    Keeping full edges square here means clicking an edge that is split into two
    or more segments no longer tapers each end.
    """
    return False, False


def current_uv_slice_positions(pin_index=None):
    """Return slice positions owned by one UV pin.

    Generated chains are assigned to UV pins cyclically, matching the later UV
    placement pass. Passing no index uses the currently selected UV pin.
    """
    scene = getattr(bpy.context, "scene", None)

    if scene is None:
        return []

    pins = getattr(scene, "edge_decal_uv_pins", None)
    if not pins:
        return []

    if pin_index is None:
        pin_index = int(getattr(scene, "edge_decal_uv_pin_index", -1))

    if pin_index < 0:
        return []

    pin = pins[pin_index % len(pins)]
    return sorted({
        round(max(0.0, min(1.0, float(slice_pin.u))), 6)
        for slice_pin in pin.slice_pins
        if 1.0e-5 < float(slice_pin.u) < 1.0 - 1.0e-5
    })


def snapped_slice_interval(amount, slice_positions):
    amount = max(0.0, min(1.0, amount))

    if amount >= 1.0 - EPSILON or not slice_positions:
        trim = max(0.0, (1.0 - amount) * 0.5)
        return trim, 1.0 - trim

    candidates = sorted(
        set(
            [0.0, 1.0]
            + [
                round(max(0.0, min(1.0, position)), 6)
                for position in slice_positions
            ]
        )
    )
    best = None

    for start_index, start in enumerate(candidates[:-1]):
        for end in candidates[start_index + 1:]:
            retained = end - start

            if retained <= EPSILON:
                continue

            center = (start + end) * 0.5
            score = abs(retained - amount) + abs(center - 0.5) * 0.20

            if best is None or score < best[0]:
                best = (score, start, end)

    if best is None:
        trim = max(0.0, (1.0 - amount) * 0.5)
        return trim, 1.0 - trim

    return best[1], best[2]


def trim_open_chain_by_amount(
    chain_verts,
    chain_edges,
    world_matrix,
    decal_amount,
    slice_positions=None,
    forced_interval=None,
):
    """
    Trim an open source chain inward from both ends.

    The returned path keeps the middle portion of the connected chain, so a low
    Decal Amount creates one short patch rather than shrinking every edge
    independently.
    """
    world_points = [world_matrix @ vert.co for vert in chain_verts]
    edge_count = len(chain_edges)

    if edge_count == 0 or len(world_points) < 2:
        return world_points, chain_edges, False, False

    amount = max(0.0, min(1.0, decal_amount))

    # Interactive Ctrl-click supplies an explicit interval even when the normal
    # Decal Amount is 1.0. Do not bypass trimming in that case.
    if forced_interval is None and amount >= 1.0 - EPSILON:
        return world_points, chain_edges, False, False

    edge_lengths = [
        (world_points[index + 1] - world_points[index]).length
        for index in range(edge_count)
    ]
    total_length = sum(edge_lengths)

    if total_length <= EPSILON:
        return world_points, chain_edges, False, False

    if forced_interval is not None:
        start_fraction = max(0.0, min(1.0, float(forced_interval[0])))
        end_fraction = max(0.0, min(1.0, float(forced_interval[1])))
        if end_fraction < start_fraction:
            start_fraction, end_fraction = end_fraction, start_fraction
    else:
        start_fraction, end_fraction = snapped_slice_interval(
            amount,
            slice_positions or [],
        )
    start_trimmed = start_fraction > EPSILON
    end_trimmed = end_fraction < 1.0 - EPSILON

    start_distance = total_length * start_fraction
    end_distance = total_length * end_fraction

    if end_distance - start_distance <= total_length * 1.0e-4:
        midpoint_distance = (start_distance + end_distance) * 0.5
        half_tiny = total_length * 5.0e-5
        start_distance = max(0.0, midpoint_distance - half_tiny)
        end_distance = min(total_length, midpoint_distance + half_tiny)

    def sample_at_distance(distance_along_chain):
        distance_remaining = max(0.0, min(distance_along_chain, total_length))

        for edge_index, edge_length in enumerate(edge_lengths):
            if distance_remaining <= edge_length + EPSILON:
                if edge_length <= EPSILON:
                    factor = 0.0
                else:
                    factor = distance_remaining / edge_length

                point = world_points[edge_index].lerp(
                    world_points[edge_index + 1],
                    factor,
                )
                return edge_index, factor, point

            distance_remaining -= edge_length

        return edge_count - 1, 1.0, world_points[-1]

    start_edge_index, start_factor, start_point = sample_at_distance(
        start_distance
    )
    end_edge_index, end_factor, end_point = sample_at_distance(
        end_distance
    )

    if start_factor >= 1.0 - EPSILON and start_edge_index < edge_count - 1:
        start_edge_index += 1
        start_factor = 0.0
        start_point = world_points[start_edge_index]

    if end_factor <= EPSILON and end_edge_index > 0:
        end_edge_index -= 1
        end_factor = 1.0
        end_point = world_points[end_edge_index + 1]

    if start_edge_index > end_edge_index:
        midpoint = world_points[0].lerp(world_points[-1], 0.5)
        return [midpoint, midpoint], [chain_edges[0]], start_trimmed, end_trimmed

    if start_edge_index == end_edge_index:
        if (end_point - start_point).length <= EPSILON:
            tangent = safe_normalized(
                world_points[start_edge_index + 1] - world_points[start_edge_index],
                Vector((1.0, 0.0, 0.0)),
            )
            tiny = max(total_length * 1.0e-4, 1.0e-6)
            start_point = midpoint = (start_point + end_point) * 0.5
            start_point = midpoint - tangent * (tiny * 0.5)
            end_point = midpoint + tangent * (tiny * 0.5)

        return [start_point, end_point], [chain_edges[start_edge_index]], start_trimmed, end_trimmed

    trimmed_points = [start_point]
    trimmed_edges = []

    for edge_index in range(start_edge_index, end_edge_index):
        trimmed_edges.append(chain_edges[edge_index])
        trimmed_points.append(world_points[edge_index + 1])

    trimmed_edges.append(chain_edges[end_edge_index])
    trimmed_points.append(end_point)

    return trimmed_points, trimmed_edges, start_trimmed, end_trimmed
