# SPDX-License-Identifier: GPL-2.0-or-later
"""UV island collection, alignment, texel density, quadrify, unwrap, and post-processing.

Loaded into the add-on package shared namespace by __init__.py.
"""





def call_operator_by_idname(bl_idname):
    category, operator_name = bl_idname.split(".", 1)
    operator_group = getattr(bpy.ops, category, None)

    if operator_group is None:
        raise RuntimeError(f"Operator category not found: {category}")

    operator = getattr(operator_group, operator_name, None)

    if operator is None:
        raise RuntimeError(f"Operator not found: {bl_idname}")

    return operator("EXEC_DEFAULT")



class _BufferedUVLoop:
    __slots__ = ("uv",)

    def __init__(self, uv):
        self.uv = uv


class _BufferedUVLayer:
    __slots__ = ("data",)

    def __init__(self, coordinates):
        self.data = [
            _BufferedUVLoop(Vector(coordinate))
            for coordinate in coordinates
        ]


def buffered_uv_layer(uv_layer):
    """Copy one Blender UV layer into inexpensive in-memory vectors."""
    loop_count = len(uv_layer.data)
    flat_coordinates = [0.0] * (loop_count * 2)

    try:
        uv_layer.data.foreach_get("uv", flat_coordinates)
        coordinates = (
            (flat_coordinates[index], flat_coordinates[index + 1])
            for index in range(0, len(flat_coordinates), 2)
        )
    except (AttributeError, RuntimeError, TypeError, ValueError):
        coordinates = (
            item.uv.copy()
            for item in uv_layer.data
        )

    return _BufferedUVLayer(coordinates)


def flush_buffered_uv_layer(buffered_layer, uv_layer):
    """Write buffered UV coordinates back to Blender in one bulk update."""
    flat_coordinates = [
        component
        for item in buffered_layer.data
        for component in item.uv
    ]

    try:
        uv_layer.data.foreach_set("uv", flat_coordinates)
    except (AttributeError, RuntimeError, TypeError, ValueError):
        for target, source in zip(uv_layer.data, buffered_layer.data):
            target.uv = source.uv


def collect_selected_uv_islands(
    mesh,
    selected_only=True,
    uv_layer=None,
):
    """
    Return UV islands, optionally using every polygon without touching mesh
    selection state.
    """
    if uv_layer is None:
        uv_layer = mesh.uv_layers.active

    if uv_layer is None:
        return []

    polygons = mesh.polygons
    loops = mesh.loops
    uv_data = uv_layer.data

    if selected_only:
        participating_polygons = [
            polygon
            for polygon in polygons
            if polygon.select
        ]
    else:
        participating_polygons = list(polygons)

    if not participating_polygons:
        return []

    adjacency = {
        polygon.index: set()
        for polygon in participating_polygons
    }
    edge_users = {}

    for polygon in participating_polygons:
        loop_indices = polygon.loop_indices
        loop_total = len(loop_indices)

        for local_index, loop_index in enumerate(loop_indices):
            next_loop_index = loop_indices[
                (local_index + 1) % loop_total
            ]

            vertex_a = loops[loop_index].vertex_index
            vertex_b = loops[next_loop_index].vertex_index

            if vertex_a <= vertex_b:
                edge_key = (vertex_a, vertex_b)
            else:
                edge_key = (vertex_b, vertex_a)

            edge_users.setdefault(edge_key, []).append(
                (
                    polygon.index,
                    vertex_a,
                    uv_data[loop_index].uv.copy(),
                    vertex_b,
                    uv_data[next_loop_index].uv.copy(),
                )
            )

    uv_tolerance_sq = 1.0e-12

    for edge_key, users in edge_users.items():
        if len(users) != 2:
            continue

        (
            polygon_a,
            vertex_a_0,
            uv_a_0,
            vertex_a_1,
            uv_a_1,
        ) = users[0]
        (
            polygon_b,
            vertex_b_0,
            uv_b_0,
            vertex_b_1,
            uv_b_1,
        ) = users[1]

        uv_map_a = {
            vertex_a_0: uv_a_0,
            vertex_a_1: uv_a_1,
        }
        uv_map_b = {
            vertex_b_0: uv_b_0,
            vertex_b_1: uv_b_1,
        }

        edge_vertex_a, edge_vertex_b = edge_key

        if (
            (uv_map_a[edge_vertex_a] - uv_map_b[edge_vertex_a]).length_squared
            <= uv_tolerance_sq
            and
            (uv_map_a[edge_vertex_b] - uv_map_b[edge_vertex_b]).length_squared
            <= uv_tolerance_sq
        ):
            adjacency[polygon_a].add(polygon_b)
            adjacency[polygon_b].add(polygon_a)

    unvisited = set(adjacency)
    islands = []

    while unvisited:
        start_polygon = unvisited.pop()
        stack = [start_polygon]
        polygon_group = {start_polygon}

        while stack:
            polygon_index = stack.pop()

            for neighbor in adjacency[polygon_index]:
                if neighbor in unvisited:
                    unvisited.remove(neighbor)
                    polygon_group.add(neighbor)
                    stack.append(neighbor)

        loop_indices = [
            loop_index
            for polygon_index in polygon_group
            for loop_index in polygons[polygon_index].loop_indices
        ]

        if loop_indices:
            islands.append({
                "polygons": sorted(polygon_group),
                "loops": loop_indices,
            })

    return islands


def rotate_uv_island(uv_layer, loop_indices, angle):
    """Rotate one UV island around its centroid by an arbitrary angle."""
    center = Vector((0.0, 0.0))

    for loop_index in loop_indices:
        center += uv_layer.data[loop_index].uv

    center /= len(loop_indices)

    cosine = cos(angle)
    sine = sin(angle)

    for loop_index in loop_indices:
        uv = uv_layer.data[loop_index].uv
        relative = uv - center

        rotated = Vector((
            relative.x * cosine - relative.y * sine,
            relative.x * sine + relative.y * cosine,
        ))

        uv_layer.data[loop_index].uv = center + rotated


def principal_uv_axis_angle(uv_layer, loop_indices):
    """
    Return the angle of the island's dominant UV direction.

    Bounding-box tests are unreliable for short or nearly square islands.
    A covariance/principal-axis calculation remains stable even when the
    unwrapped island is diagonal or compact.
    """
    unique_uvs = []
    seen = set()

    for loop_index in loop_indices:
        uv = uv_layer.data[loop_index].uv.copy()
        key = (round(uv.x, 8), round(uv.y, 8))

        if key not in seen:
            seen.add(key)
            unique_uvs.append(uv)

    if len(unique_uvs) < 2:
        return 0.0

    center = Vector((0.0, 0.0))
    for uv in unique_uvs:
        center += uv
    center /= len(unique_uvs)

    xx = 0.0
    yy = 0.0
    xy = 0.0

    for uv in unique_uvs:
        delta = uv - center
        xx += delta.x * delta.x
        yy += delta.y * delta.y
        xy += delta.x * delta.y

    # Principal eigenvector angle for a 2x2 covariance matrix.
    return 0.5 * atan2(2.0 * xy, xx - yy)



def centerline_uv_axis_angle(
    decal_obj,
    uv_layer,
    loop_indices,
    center_vertices=None,
):
    """
    Return the UV angle of the actual generated decal centerline.

    This avoids short or compact islands being rotated from their overall
    bounding shape instead of from the real edge direction.
    """
    if center_vertices is None:
        center_vertices = get_center_vertex_indices(decal_obj)

    if not center_vertices:
        return None

    mesh = decal_obj.data
    center_uvs = []
    seen = set()

    for loop_index in loop_indices:
        vertex_index = mesh.loops[loop_index].vertex_index

        if vertex_index not in center_vertices:
            continue

        uv = uv_layer.data[loop_index].uv.copy()
        key = (round(uv.x, 8), round(uv.y, 8))

        if key not in seen:
            seen.add(key)
            center_uvs.append(uv)

    if len(center_uvs) < 2:
        return None

    # Use the farthest pair of centerline UV points. This is stable for both
    # long strips and very short compact decals.
    best_a = None
    best_b = None
    best_distance_sq = -1.0

    for index_a in range(len(center_uvs)):
        for index_b in range(index_a + 1, len(center_uvs)):
            delta = center_uvs[index_b] - center_uvs[index_a]
            distance_sq = delta.length_squared

            if distance_sq > best_distance_sq:
                best_distance_sq = distance_sq
                best_a = center_uvs[index_a]
                best_b = center_uvs[index_b]

    if best_a is None or best_b is None or best_distance_sq <= 1.0e-16:
        return None

    direction = best_b - best_a
    return atan2(direction.y, direction.x)


def align_uv_island_horizontally(
    decal_obj,
    uv_layer,
    loop_indices,
    center_vertices=None,
):
    """
    Rotate the decal's true centerline onto the U axis.

    Falls back to the island principal axis only when centerline metadata is
    unavailable.
    """
    axis_angle = centerline_uv_axis_angle(
        decal_obj,
        uv_layer,
        loop_indices,
        center_vertices=center_vertices,
    )

    if axis_angle is None:
        axis_angle = principal_uv_axis_angle(
            uv_layer,
            loop_indices,
        )

    rotate_uv_island(
        uv_layer,
        loop_indices,
        -axis_angle,
    )



def uv_polygon_area(uv_layer, polygon):
    """Calculate one polygon's signed UV area using the shoelace formula."""
    loop_indices = list(polygon.loop_indices)

    if len(loop_indices) < 3:
        return 0.0

    area = 0.0

    for index, loop_index in enumerate(loop_indices):
        next_loop_index = loop_indices[(index + 1) % len(loop_indices)]
        uv_a = uv_layer.data[loop_index].uv
        uv_b = uv_layer.data[next_loop_index].uv
        area += uv_a.x * uv_b.y - uv_b.x * uv_a.y

    return abs(area) * 0.5


def scale_uv_island_about_center(uv_layer, loop_indices, scale):
    center = Vector((0.0, 0.0))

    for loop_index in loop_indices:
        center += uv_layer.data[loop_index].uv

    center /= len(loop_indices)

    for loop_index in loop_indices:
        uv = uv_layer.data[loop_index].uv
        uv_layer.data[loop_index].uv = center + (uv - center) * scale


def average_uv_island_scales(mesh, uv_layer, islands):
    """
    Equalize UV scale using mesh area versus UV area.

    This mirrors the intent of Blender's Average Islands Scale: islands receive
    a common texel density while retaining their relative real-world sizes.
    """
    measurements = []
    total_mesh_area = 0.0
    total_uv_area = 0.0

    for island in islands:
        mesh_area = sum(
            mesh.polygons[index].area
            for index in island["polygons"]
        )
        uv_area = sum(
            uv_polygon_area(uv_layer, mesh.polygons[index])
            for index in island["polygons"]
        )

        if mesh_area <= EPSILON or uv_area <= EPSILON:
            measurements.append(None)
            continue

        measurements.append((mesh_area, uv_area))
        total_mesh_area += mesh_area
        total_uv_area += uv_area

    if total_mesh_area <= EPSILON or total_uv_area <= EPSILON:
        return

    target_density = (total_uv_area / total_mesh_area) ** 0.5

    for island, measurement in zip(islands, measurements):
        if measurement is None:
            continue

        mesh_area, uv_area = measurement
        current_density = (uv_area / mesh_area) ** 0.5

        if current_density <= EPSILON:
            continue

        scale_uv_island_about_center(
            uv_layer,
            island["loops"],
            target_density / current_density,
        )



def set_uv_texel_density(
    mesh,
    uv_layer,
    islands,
    pixels_per_centimeter,
    texture_resolution,
    scene_scale_length,
):
    """
    Scale every island to the requested texel density.

    Blender polygon areas are measured in Blender units squared. The scene
    unit scale converts one Blender unit into meters:

        pixels per Blender unit =
            px/cm * 100 cm/m * scene scale length

        UV units per Blender unit =
            pixels per Blender unit / texture resolution
    """
    if texture_resolution <= 0 or pixels_per_centimeter <= 0.0:
        return

    unit_scale = scene_scale_length if scene_scale_length > 0.0 else 1.0
    target_uv_per_blender_unit = (
        pixels_per_centimeter * 100.0 * unit_scale
    ) / float(texture_resolution)

    for island in islands:
        mesh_area = sum(
            mesh.polygons[index].area
            for index in island["polygons"]
        )
        uv_area = sum(
            uv_polygon_area(uv_layer, mesh.polygons[index])
            for index in island["polygons"]
        )

        if mesh_area <= EPSILON or uv_area <= EPSILON:
            continue

        current_uv_per_blender_unit = (uv_area / mesh_area) ** 0.5

        if current_uv_per_blender_unit <= EPSILON:
            continue

        scale_uv_island_about_center(
            uv_layer,
            island["loops"],
            target_uv_per_blender_unit / current_uv_per_blender_unit,
        )




def apply_uv_scale_multiplier(uv_layer, islands, scale):
    """
    Uniformly scale each UV island around its own center.

    This is intentionally applied last, so the F9 slider gives a predictable
    visual multiplier over the final generated UV layout.
    """
    if abs(scale - 1.0) <= EPSILON:
        return

    for island in islands:
        scale_uv_island_about_center(
            uv_layer,
            island["loops"],
            scale,
        )


def measured_texel_density(
    mesh,
    uv_layer,
    islands,
    texture_resolution,
    scene_scale_length,
):
    """Return the area-weighted UV texel density in pixels per centimeter."""
    total_mesh_area = 0.0
    total_uv_area = 0.0

    for island in islands:
        total_mesh_area += sum(
            mesh.polygons[index].area
            for index in island["polygons"]
        )
        total_uv_area += sum(
            uv_polygon_area(uv_layer, mesh.polygons[index])
            for index in island["polygons"]
        )

    if total_mesh_area <= EPSILON or total_uv_area <= EPSILON:
        return 0.0

    unit_scale = scene_scale_length if scene_scale_length > 0.0 else 1.0
    uv_per_blender_unit = (total_uv_area / total_mesh_area) ** 0.5
    pixels_per_blender_unit = uv_per_blender_unit * texture_resolution

    return pixels_per_blender_unit / (100.0 * unit_scale)


def translate_uv_island_to_center(
    uv_layer,
    loop_indices,
    target_center,
    scale=1.0,
):
    min_u, max_u, min_v, max_v = uv_bounds(uv_layer, loop_indices)
    current_center = Vector((
        (min_u + max_u) * 0.5,
        (min_v + max_v) * 0.5,
    ))

    for loop_index in loop_indices:
        uv = uv_layer.data[loop_index].uv
        uv_layer.data[loop_index].uv = (
            target_center + (uv - current_center) * scale
        )



def place_exact_density_islands_in_quarter_strips(
    uv_layer,
    islands,
    strip_indices,
):
    """
    Move islands into quarter-height bands without scaling them.

    This preserves the requested texel density exactly. Long islands may extend
    beyond U=0..1, which is preferable to silently changing their density.
    """
    strip_height = 0.25

    for island, strip_index in zip(islands, strip_indices):
        min_u, max_u, min_v, max_v = uv_bounds(
            uv_layer,
            island["loops"],
        )

        current_center = Vector((
            (min_u + max_u) * 0.5,
            (min_v + max_v) * 0.5,
        ))
        target_center = Vector((
            0.5,
            strip_index * strip_height + strip_height * 0.5,
        ))
        translation = target_center - current_center

        for loop_index in island["loops"]:
            uv_layer.data[loop_index].uv += translation


def place_averaged_islands_in_quarter_strips(
    uv_layer,
    islands,
    strip_indices,
    padding,
):
    """
    Place islands into 0.25-height bands using one common scale factor.

    Because every island receives the same final scale, the averaged texel
    density is preserved instead of each island being independently stretched
    to fill its strip.
    """
    strip_height = 0.25
    safe_padding = min(max(padding, 0.0), strip_height * 0.49)
    available_width = max(1.0 - safe_padding * 2.0, EPSILON)
    available_height = max(strip_height - safe_padding * 2.0, EPSILON)

    common_scale = float("inf")

    for island in islands:
        min_u, max_u, min_v, max_v = uv_bounds(
            uv_layer,
            island["loops"],
        )
        width = max(max_u - min_u, EPSILON)
        height = max(max_v - min_v, EPSILON)

        common_scale = min(
            common_scale,
            available_width / width,
            available_height / height,
        )

    if common_scale == float("inf"):
        common_scale = 1.0

    # Preserve target texel density whenever the islands already fit.
    # Only shrink globally when an island cannot fit inside its 0.25 band.
    common_scale = min(1.0, common_scale)

    for island, strip_index in zip(islands, strip_indices):
        target_center = Vector((
            0.5,
            strip_index * strip_height + strip_height * 0.5,
        ))

        translate_uv_island_to_center(
            uv_layer,
            island["loops"],
            target_center,
            common_scale,
        )


def uv_bounds(uv_layer, loop_indices):
    iterator = iter(loop_indices)

    try:
        first_index = next(iterator)
    except StopIteration:
        return 0.0, 0.0, 0.0, 0.0

    first_uv = uv_layer.data[first_index].uv
    min_u = max_u = first_uv.x
    min_v = max_v = first_uv.y

    for loop_index in iterator:
        uv = uv_layer.data[loop_index].uv
        min_u = min(min_u, uv.x)
        max_u = max(max_u, uv.x)
        min_v = min(min_v, uv.y)
        max_v = max(max_v, uv.y)

    return min_u, max_u, min_v, max_v





def randomize_uv_islands_horizontally(
    uv_layer,
    islands,
    rng,
    padding,
    amount=1.0,
):
    """Give every UV island a distinct randomized horizontal tile phase.

    Constraining fitted islands to 0-1 leaves wide strips with no useful room
    to move. Instead, assign island centers to shuffled strata across one U
    tile and allow their bounds to tile outside it. Width and texel density are
    unchanged, while every island receives a visibly independent X position.
    """
    if not islands:
        return

    ordered_islands = sorted(
        islands,
        key=lambda island: tuple(island.get("polygons", ())),
    )
    island_count = len(ordered_islands)
    horizontal_span = max(0.0, float(amount))
    if horizontal_span <= EPSILON:
        return
    phase = rng.random()
    target_centers = [
        (
            ((slot + phase) / island_count) - 0.5
        ) * horizontal_span
        for slot in range(island_count)
    ]
    rng.shuffle(target_centers)

    for island, target_center_u in zip(ordered_islands, target_centers):
        loops = island["loops"]
        min_u, max_u, _min_v, _max_v = uv_bounds(uv_layer, loops)
        current_center_u = (min_u + max_u) * 0.5
        translation_u = target_center_u - current_center_u

        for loop_index in loops:
            uv_layer.data[loop_index].uv.x += translation_u


def randomize_decal_uv_islands_horizontally(
    decal_obj,
    random_seed,
    padding=0.0,
    amount=1.0,
):
    """Apply cheap horizontal island randomization without a full unwrap."""
    if decal_obj is None or decal_obj.data is None:
        return 0

    mesh = decal_obj.data
    blender_uv_layer = mesh.uv_layers.active
    if blender_uv_layer is None:
        return 0

    uv_layer = buffered_uv_layer(blender_uv_layer)
    islands = collect_selected_uv_islands(
        mesh,
        selected_only=False,
        uv_layer=uv_layer,
    )
    if not islands:
        return 0

    randomize_uv_islands_horizontally(
        uv_layer,
        islands,
        random.Random(random_seed),
        padding,
        amount,
    )
    flush_buffered_uv_layer(uv_layer, blender_uv_layer)
    mesh.update()
    return len(islands)



def get_center_vertex_indices(decal_obj):
    """Return vertices belonging to the generated center-edge row."""
    group = decal_obj.vertex_groups.get("EdgeDecal_Center")
    if group is None:
        return set()

    group_index = group.index
    result = set()

    for vertex in decal_obj.data.vertices:
        for membership in vertex.groups:
            if membership.group == group_index and membership.weight > 0.0:
                result.add(vertex.index)
                break

    return result


def align_uv_centerlines_to_strips(
    decal_obj,
    uv_layer,
    islands,
    strip_indices,
    center_vertices=None,
):
    """
    Align the actual generated middle edge to the center of each 0.25 UV band.

    This is more accurate than centering the island bounding box, because the
    two sides of an edge decal can have different widths.
    """
    if center_vertices is None:
        center_vertices = get_center_vertex_indices(decal_obj)

    if not center_vertices:
        return

    strip_height = 0.25
    mesh = decal_obj.data

    for island, strip_index in zip(islands, strip_indices):
        center_loop_indices = [
            loop_index
            for loop_index in island["loops"]
            if mesh.loops[loop_index].vertex_index in center_vertices
        ]

        if not center_loop_indices:
            continue

        min_center_v = min(
            uv_layer.data[index].uv.y
            for index in center_loop_indices
        )
        max_center_v = max(
            uv_layer.data[index].uv.y
            for index in center_loop_indices
        )
        current_center_v = (min_center_v + max_center_v) * 0.5
        target_center_v = (
            strip_index * strip_height
            + strip_height * 0.5
        )
        offset_v = target_center_v - current_center_v

        for loop_index in island["loops"]:
            uv_layer.data[loop_index].uv.y += offset_v





def postprocess_generated_uvs(
    decal_obj,
    uv_scale,
    set_target_density,
    target_texel_density,
    texture_resolution,
    scene_scale_length,
    average_island_scale,
    align_horizontally,
    place_in_quarter_strips,
    randomize_quarter_strip,
    randomize_horizontal_offset,
    horizontal_randomize_amount,
    random_seed,
    strip_padding,
):
    """
    Average texel density, align islands horizontally, and optionally place
    them into four 0.25-height UV bands.
    """
    mesh = decal_obj.data
    blender_uv_layer = mesh.uv_layers.active

    if blender_uv_layer is None:
        return 0, 0.0

    uv_layer = buffered_uv_layer(blender_uv_layer)

    islands = collect_selected_uv_islands(
        mesh,
        selected_only=False,
        uv_layer=uv_layer,
    )

    if not islands:
        return 0, 0.0

    # UV pins are the final scale authority. Running texel-density averaging or
    # target-density normalization before pin fitting is redundant and becomes
    # numerically unstable for tiny/short islands.
    try:
        scene = bpy.context.scene
        pins_are_authoritative = bool(
            getattr(scene.edge_decal_settings, "auto_use_uv_pins", False)
            and uv_pins_for_decal_layer_material(scene, decal_obj)
        )
    except Exception:
        pins_are_authoritative = False

    if pins_are_authoritative:
        average_island_scale = False
        set_target_density = False

    center_vertices = (
        get_center_vertex_indices(decal_obj)
        if align_horizontally or place_in_quarter_strips
        else None
    )

    # First orient and correct every island from the actual decal geometry.
    # Texel-density operations must happen afterwards, otherwise correcting
    # the face-width aspect changes the requested density.
    for island in islands:
        if align_horizontally:
            align_uv_island_horizontally(
                decal_obj,
                uv_layer,
                island["loops"],
                center_vertices=center_vertices,
            )

    # Exact target-density scaling independently normalizes every island and
    # fully supersedes an earlier average-scale pass.
    if average_island_scale and not set_target_density:
        average_uv_island_scales(
            mesh,
            uv_layer,
            islands,
        )

    if set_target_density:
        set_uv_texel_density(
            mesh,
            uv_layer,
            islands,
            target_texel_density,
            texture_resolution,
            scene_scale_length,
        )

    rng = (
        random.Random(random_seed)
        if randomize_quarter_strip or randomize_horizontal_offset
        else None
    )
    strip_indices = None

    if place_in_quarter_strips:
        strip_indices = []

        for island_index in range(len(islands)):
            if randomize_quarter_strip:
                strip_indices.append(rng.randrange(4))
            else:
                strip_indices.append(island_index % 4)

        if average_island_scale and not set_target_density:
            place_averaged_islands_in_quarter_strips(
                uv_layer,
                islands,
                strip_indices,
                strip_padding,
            )
        else:
            # Translation only. Do not normalize every island independently,
            # because that would make thin and thick decals occupy the same
            # strip height and erase the Face Width difference.
            place_exact_density_islands_in_quarter_strips(
                uv_layer,
                islands,
                strip_indices,
            )

    apply_uv_scale_multiplier(
        uv_layer,
        islands,
        uv_scale,
    )

    if randomize_horizontal_offset:
        randomize_uv_islands_horizontally(
            uv_layer,
            islands,
            rng,
            strip_padding,
            horizontal_randomize_amount,
        )

    if strip_indices is not None:
        align_uv_centerlines_to_strips(
            decal_obj,
            uv_layer,
            islands,
            strip_indices,
            center_vertices=center_vertices,
        )

    density = 0.0

    if set_target_density:
        density = measured_texel_density(
            mesh,
            uv_layer,
            islands,
            texture_resolution,
            scene_scale_length,
        )

    flush_buffered_uv_layer(uv_layer, blender_uv_layer)
    mesh.update()

    return len(islands), density








def edge_decal_uv_centroid(loops, uv_layer):
    center = Vector((0.0, 0.0))
    count = 0

    for loop in loops:
        center += loop[uv_layer].uv
        count += 1

    return center / max(count, 1)


def edge_decal_quad_components(bm):
    """Return connected quad-only components without crossing seams."""
    unvisited = {
        face
        for face in bm.faces
        if len(face.verts) == 4
    }
    components = []

    while unvisited:
        start_face = unvisited.pop()
        stack = [start_face]
        component = [start_face]

        while stack:
            face = stack.pop()

            for edge in face.edges:
                if edge.seam or not edge.is_manifold:
                    continue

                for linked_face in edge.link_faces:
                    if linked_face in unvisited:
                        unvisited.remove(linked_face)
                        stack.append(linked_face)
                        component.append(linked_face)

        components.append(component)

    return components


def edge_decal_walk_quad_edgeloop(start_loop, allowed_faces):
    """Walk corresponding edges across a connected quad strip."""
    first_edge = start_loop.edge
    loop = start_loop
    visited_edges = set()

    while True:
        edge = loop.edge

        if edge in visited_edges:
            break

        visited_edges.add(edge)
        yield edge

        if edge.seam or not edge.is_manifold:
            break

        radial_loop = loop.link_loop_radial_next

        if (
            radial_loop.face not in allowed_faces
            or len(radial_loop.face.verts) != 4
        ):
            break

        loop = radial_loop.link_loop_next.link_loop_next

        if loop.edge is first_edge:
            break


def edge_decal_average_quad_edge_lengths(bm, faces):
    """Average corresponding mesh edge loops for stable strip proportions."""
    bm.edges.index_update()
    allowed_faces = set(faces)
    edge_lengths = {}

    for face in faces:
        for base_loop in (face.loops[0], face.loops[1]):
            opposite_loop = base_loop.link_loop_next.link_loop_next
            collected_edges = set()

            for start_loop in (base_loop, opposite_loop):
                if start_loop.edge in edge_lengths:
                    continue

                collected_edges.update(
                    edge_decal_walk_quad_edgeloop(
                        start_loop,
                        allowed_faces,
                    )
                )

            if not collected_edges:
                continue

            average_length = sum(
                edge.calc_length()
                for edge in collected_edges
            ) / len(collected_edges)

            for edge in collected_edges:
                edge_lengths[edge] = average_length

    return edge_lengths


def edge_decal_choose_quadrify_start_face(faces, uv_layer):
    """Choose the quad nearest the UV component center."""
    face_centers = {
        face: edge_decal_uv_centroid(face.loops, uv_layer)
        for face in faces
    }

    min_u = min(center.x for center in face_centers.values())
    max_u = max(center.x for center in face_centers.values())
    min_v = min(center.y for center in face_centers.values())
    max_v = max(center.y for center in face_centers.values())
    component_center = Vector((
        (min_u + max_u) * 0.5,
        (min_v + max_v) * 0.5,
    ))

    return min(
        faces,
        key=lambda face: (
            face_centers[face] - component_center
        ).length_squared,
    )


def edge_decal_assign_uv_to_matching_loops(
    loop,
    uv_layer,
    original_uv,
    target_uv,
):
    """Keep already-welded UV vertices welded while moving the seed quad."""
    tolerance_sq = 1.0e-12

    for linked_loop in loop.vert.link_loops:
        if (
            linked_loop[uv_layer].uv - original_uv
        ).length_squared <= tolerance_sq:
            linked_loop[uv_layer].uv = target_uv


def edge_decal_align_quadrify_seed_face(
    face,
    uv_layer,
    edge_lengths,
    even_shape=False,
    center_vertex_indices=None,
):
    """Axis-align the seed quad while preserving its semantic strip axes.

    Generated strips store their longitudinal direction on an edge whose two
    vertices belong to ``EdgeDecal_Center``.  Prefer that edge as the master
    axis instead of choosing from the current UV lengths.  UV-length guessing
    can flip width and length on very small or very short decals, causing the
    quadrify and pin-fit stages to stretch the island dramatically.
    """
    loops = list(face.loops)
    center_vertex_indices = center_vertex_indices or set()

    semantic_start = None
    for index, loop in enumerate(loops):
        next_loop = loop.link_loop_next
        if (
            loop.vert.index in center_vertex_indices
            and next_loop.vert.index in center_vertex_indices
        ):
            semantic_start = index
            break

    if semantic_start is not None:
        start_index = semantic_start
    else:
        first_uv_length = (
            loops[1][uv_layer].uv - loops[0][uv_layer].uv
        ).length
        second_uv_length = (
            loops[2][uv_layer].uv - loops[1][uv_layer].uv
        ).length
        start_index = 0 if first_uv_length >= second_uv_length else 1
    ordered = [
        loops[(start_index + offset) % 4]
        for offset in range(4)
    ]

    master_loop = ordered[0]
    ortho_loop = ordered[1]
    master_mesh_length = edge_lengths.get(
        master_loop.edge,
        master_loop.edge.calc_length(),
    )
    ortho_mesh_length = edge_lengths.get(
        ortho_loop.edge,
        ortho_loop.edge.calc_length(),
    )

    master_uv_vector = (
        ordered[1][uv_layer].uv - ordered[0][uv_layer].uv
    )
    master_uv_length = master_uv_vector.length

    if master_uv_length <= EPSILON:
        master_uv_length = 0.05

    if even_shape:
        ortho_uv_length = master_uv_length
    elif master_mesh_length > EPSILON:
        ortho_uv_length = (
            master_uv_length
            * ortho_mesh_length
            / master_mesh_length
        )
    else:
        ortho_uv_length = master_uv_length

    if abs(master_uv_vector.x) >= abs(master_uv_vector.y):
        axis = Vector((
            1.0 if master_uv_vector.x >= 0.0 else -1.0,
            0.0,
        ))
    else:
        axis = Vector((
            0.0,
            1.0 if master_uv_vector.y >= 0.0 else -1.0,
        ))

    master_vector = axis * master_uv_length
    ortho_vector = master_vector.orthogonal().normalized() * ortho_uv_length
    current_ortho = (
        ordered[3][uv_layer].uv - ordered[0][uv_layer].uv
    )

    if ortho_vector.dot(current_ortho) < 0.0:
        ortho_vector.negate()

    new_coordinates = [
        Vector((0.0, 0.0)),
        master_vector,
        master_vector + ortho_vector,
        ortho_vector,
    ]
    original_center = edge_decal_uv_centroid(ordered, uv_layer)
    new_center = sum(new_coordinates, Vector((0.0, 0.0))) / 4.0
    offset = original_center - new_center

    for loop, coordinate in zip(ordered, new_coordinates):
        original_uv = loop[uv_layer].uv.copy()
        target_uv = coordinate + offset
        edge_decal_assign_uv_to_matching_loops(
            loop,
            uv_layer,
            original_uv,
            target_uv,
        )


def edge_decal_yield_adjacent_quad_loops(start_face, faces):
    """Breadth-first quad distribution through the connected component."""
    from collections import deque

    allowed_faces = set(faces)
    visited_faces = {start_face}
    queue = deque([start_face])

    while queue:
        face = queue.popleft()

        for master_loop in face.loops:
            edge = master_loop.edge

            if edge.seam or not edge.is_manifold:
                continue

            next_loop = master_loop.link_loop_radial_next
            next_face = next_loop.face

            if (
                next_face not in allowed_faces
                or next_face in visited_faces
                or len(next_face.verts) != 4
            ):
                continue

            visited_faces.add(next_face)
            queue.append(next_face)
            yield next_loop


# Quadrify distribution adapted from Zen UV (C) 2024 Valeriy Yatsenko; modified by Gilad Baruch.
def edge_decal_quadrify_component(
    bm,
    faces,
    uv_layer,
    average_shape=True,
    even_shape=False,
    center_vertex_indices=None,
):
    """
    Self-contained GPL quadrify distribution algorithm.

    It aligns one seed face, then distributes neighboring quads breadth-first
    using the already-placed shared edge and mesh edge-loop proportions.
    """
    if not faces:
        return 0

    edge_lengths = (
        edge_decal_average_quad_edge_lengths(bm, faces)
        if average_shape
        else {}
    )
    start_face = edge_decal_choose_quadrify_start_face(
        faces,
        uv_layer,
    )
    edge_decal_align_quadrify_seed_face(
        start_face,
        uv_layer,
        edge_lengths,
        even_shape=even_shape,
        center_vertex_indices=center_vertex_indices,
    )

    processed_faces = 1

    for loop in edge_decal_yield_adjacent_quad_loops(
        start_face,
        faces,
    ):
        master_loop = loop.link_loop_radial_next
        master_vector = (
            master_loop[uv_layer].uv
            - master_loop.link_loop_next[uv_layer].uv
        )

        if master_vector.length_squared <= EPSILON:
            continue

        master_edge = loop.edge
        ortho_edge = loop.link_loop_next.edge

        if even_shape:
            ortho_uv_length = master_vector.length
        else:
            master_mesh_length = edge_lengths.get(
                master_edge,
                master_edge.calc_length(),
            )
            ortho_mesh_length = edge_lengths.get(
                ortho_edge,
                ortho_edge.calc_length(),
            )

            if master_mesh_length > EPSILON:
                ortho_uv_length = (
                    master_vector.length
                    * ortho_mesh_length
                    / master_mesh_length
                )
            else:
                ortho_uv_length = master_vector.length

        ortho_vector = (
            master_vector.orthogonal().normalized()
            * ortho_uv_length
        )

        # Place the new quad on the opposite side of the shared edge from the
        # already-solved master quad.  This is independent of the target
        # quad's old UVs, so Apply UVs can recover a manually edited layer even
        # when its UV coordinates are collapsed to zero.  The previous method
        # inferred the side from those old coordinates and could stack two
        # neighboring quads directly on top of one another.
        master_shared_mid = (
            master_loop[uv_layer].uv
            + master_loop.link_loop_next[uv_layer].uv
        ) * 0.5
        master_opposite_mid = (
            master_loop.link_loop_next.link_loop_next[uv_layer].uv
            + master_loop.link_loop_prev[uv_layer].uv
        ) * 0.5
        master_interior_vector = (
            master_opposite_mid - master_shared_mid
        )

        if (
            master_interior_vector.length_squared > EPSILON
            and ortho_vector.dot(master_interior_vector) > 0.0
        ):
            ortho_vector.negate()

        target_coordinates = (
            master_loop.link_loop_next[uv_layer].uv.copy(),
            master_loop[uv_layer].uv.copy(),
            master_loop[uv_layer].uv + ortho_vector,
            master_loop.link_loop_next[uv_layer].uv + ortho_vector,
        )
        target_loops = (
            loop,
            loop.link_loop_next,
            loop.link_loop_next.link_loop_next,
            loop.link_loop_prev,
        )

        for target_loop, coordinate in zip(
            target_loops,
            target_coordinates,
        ):
            target_loop[uv_layer].uv = coordinate

        processed_faces += 1

    return processed_faces



def capture_taper_triangle_uv_bindings(bm, uv_layer):
    """Capture triangle UV shape relative to an adjacent quad shared edge."""
    bindings = []
    for face in bm.faces:
        if len(face.verts) != 3:
            continue
        shared_edge = None
        quad_face = None
        for edge in face.edges:
            if not edge.is_manifold:
                continue
            other = next((linked for linked in edge.link_faces if linked is not face), None)
            if other is not None and len(other.verts) == 4:
                shared_edge = edge
                quad_face = other
                break
        if shared_edge is None or quad_face is None:
            continue

        a_vert, b_vert = shared_edge.verts
        tip_vert = next((vert for vert in face.verts if vert not in shared_edge.verts), None)
        if tip_vert is None:
            continue

        def face_loop_for_vert(target_face, vert):
            return next((loop for loop in target_face.loops if loop.vert is vert), None)

        a_loop = face_loop_for_vert(face, a_vert)
        b_loop = face_loop_for_vert(face, b_vert)
        tip_loop = face_loop_for_vert(face, tip_vert)
        if None in (a_loop, b_loop, tip_loop):
            continue

        uv_a = a_loop[uv_layer].uv.copy()
        uv_b = b_loop[uv_layer].uv.copy()
        uv_tip = tip_loop[uv_layer].uv.copy()
        axis = uv_b - uv_a
        length_sq = axis.length_squared
        if length_sq <= 1.0e-12:
            continue

        delta = uv_tip - uv_a
        along = delta.dot(axis) / length_sq
        signed_height = (axis.x * delta.y - axis.y * delta.x) / length_sq
        bindings.append({
            "face_index": face.index,
            "quad_index": quad_face.index,
            "a_index": a_vert.index,
            "b_index": b_vert.index,
            "tip_index": tip_vert.index,
            "along": along,
            "signed_height": signed_height,
        })
    return bindings


def restore_taper_triangle_uv_bindings(bm, uv_layer, bindings):
    """Stitch taper triangles to their quadrified neighbor and preserve shape."""
    bm.faces.ensure_lookup_table()

    def loop_for_vert(face, vertex_index):
        return next((loop for loop in face.loops if loop.vert.index == vertex_index), None)

    for binding in bindings:
        face_index = binding["face_index"]
        quad_index = binding["quad_index"]
        if not (0 <= face_index < len(bm.faces) and 0 <= quad_index < len(bm.faces)):
            continue
        tri = bm.faces[face_index]
        quad = bm.faces[quad_index]
        if len(tri.verts) != 3 or len(quad.verts) != 4:
            continue

        qa = loop_for_vert(quad, binding["a_index"])
        qb = loop_for_vert(quad, binding["b_index"])
        ta = loop_for_vert(tri, binding["a_index"])
        tb = loop_for_vert(tri, binding["b_index"])
        tt = loop_for_vert(tri, binding["tip_index"])
        if None in (qa, qb, ta, tb, tt):
            continue

        uv_a = qa[uv_layer].uv.copy()
        uv_b = qb[uv_layer].uv.copy()
        axis = uv_b - uv_a
        if axis.length_squared <= 1.0e-12:
            continue
        perpendicular = Vector((-axis.y, axis.x))
        uv_tip = (
            uv_a
            + axis * float(binding["along"])
            + perpendicular * float(binding["signed_height"])
        )

        ta[uv_layer].uv = uv_a
        tb[uv_layer].uv = uv_b
        tt[uv_layer].uv = uv_tip

def ensure_decal_mesh_uv_layers(mesh):
    """Guarantee a usable active UV layer exists on a generated decal mesh."""
    if mesh is None:
        return None

    if not mesh.uv_layers:
        uv_layer = mesh.uv_layers.new(name="UVMap")
    else:
        uv_layer = mesh.uv_layers[0]

    mesh.uv_layers.active = uv_layer
    if hasattr(mesh.uv_layers, "active_render"):
        mesh.uv_layers.active_render = uv_layer
    mesh.update()
    return uv_layer


SECOND_UV_LAYER_NAME = "UVMap.001"


def closest_point_on_triangle(point, point_a, point_b, point_c):
    """Return the closest point on a triangle to an arbitrary 3D point."""
    edge_ab = point_b - point_a
    edge_ac = point_c - point_a
    offset_a = point - point_a
    dot_ab_a = edge_ab.dot(offset_a)
    dot_ac_a = edge_ac.dot(offset_a)
    if dot_ab_a <= 0.0 and dot_ac_a <= 0.0:
        return point_a.copy()

    offset_b = point - point_b
    dot_ab_b = edge_ab.dot(offset_b)
    dot_ac_b = edge_ac.dot(offset_b)
    if dot_ab_b >= 0.0 and dot_ac_b <= dot_ab_b:
        return point_b.copy()

    area_c = dot_ab_a * dot_ac_b - dot_ab_b * dot_ac_a
    if area_c <= 0.0 and dot_ab_a >= 0.0 and dot_ab_b <= 0.0:
        factor = dot_ab_a / max(dot_ab_a - dot_ab_b, EPSILON)
        return point_a + edge_ab * factor

    offset_c = point - point_c
    dot_ab_c = edge_ab.dot(offset_c)
    dot_ac_c = edge_ac.dot(offset_c)
    if dot_ac_c >= 0.0 and dot_ab_c <= dot_ac_c:
        return point_c.copy()

    area_b = dot_ab_c * dot_ac_a - dot_ab_a * dot_ac_c
    if area_b <= 0.0 and dot_ac_a >= 0.0 and dot_ac_c <= 0.0:
        factor = dot_ac_a / max(dot_ac_a - dot_ac_c, EPSILON)
        return point_a + edge_ac * factor

    area_a = dot_ab_b * dot_ac_c - dot_ab_c * dot_ac_b
    edge_bc = point_c - point_b
    if area_a <= 0.0 and (dot_ac_b - dot_ab_b) >= 0.0 and (
        dot_ab_c - dot_ac_c
    ) >= 0.0:
        numerator = dot_ac_b - dot_ab_b
        denominator = numerator + dot_ab_c - dot_ac_c
        factor = numerator / max(denominator, EPSILON)
        return point_b + edge_bc * factor

    denominator = area_a + area_b + area_c
    if abs(denominator) <= EPSILON:
        return point_a.copy()
    inverse = 1.0 / denominator
    weight_b = area_b * inverse
    weight_c = area_c * inverse
    return point_a + edge_ab * weight_b + edge_ac * weight_c


def triangle_interpolated_uv(point, triangle_points, triangle_uvs):
    """Barycentrically interpolate UV coordinates on one source triangle."""
    point_a, point_b, point_c = triangle_points
    edge_ab = point_b - point_a
    edge_ac = point_c - point_a
    offset = point - point_a
    dot_ab_ab = edge_ab.dot(edge_ab)
    dot_ab_ac = edge_ab.dot(edge_ac)
    dot_ac_ac = edge_ac.dot(edge_ac)
    dot_offset_ab = offset.dot(edge_ab)
    dot_offset_ac = offset.dot(edge_ac)
    denominator = dot_ab_ab * dot_ac_ac - dot_ab_ac * dot_ab_ac
    if abs(denominator) <= EPSILON:
        return triangle_uvs[0].copy()
    inverse = 1.0 / denominator
    weight_b = (
        dot_ac_ac * dot_offset_ab - dot_ab_ac * dot_offset_ac
    ) * inverse
    weight_c = (
        dot_ab_ab * dot_offset_ac - dot_ab_ac * dot_offset_ab
    ) * inverse
    weight_a = 1.0 - weight_b - weight_c
    return (
        triangle_uvs[0] * weight_a
        + triangle_uvs[1] * weight_b
        + triangle_uvs[2] * weight_c
    )


def transfer_source_first_uv_to_decal(source_obj, decal_obj):
    """Project the source mesh's first UV map onto decal UVMap.001.

    A decal polygon first selects its nearest source polygon. Every decal loop
    is then projected onto that polygon's rendered loop triangles and receives
    barycentrically interpolated source UV coordinates. Selecting the support
    polygon per decal face, while writing the result per loop, preserves the
    two independent UV values found on opposite sides of a source UV seam.
    """
    if (
        source_obj is None
        or source_obj.type != "MESH"
        or source_obj.data is None
        or decal_obj is None
        or decal_obj.type != "MESH"
        or decal_obj.data is None
    ):
        return None

    source_mesh = source_obj.data
    decal_mesh = decal_obj.data
    if not source_mesh.uv_layers or not source_mesh.polygons:
        return None
    if not decal_mesh.polygons:
        return None

    if source_obj.mode == "EDIT":
        try:
            bmesh.update_edit_mesh(
                source_mesh,
                loop_triangles=True,
                destructive=False,
            )
        except RuntimeError:
            pass
    source_mesh.calc_loop_triangles()
    source_uv_layer = source_mesh.uv_layers[0]
    if len(source_uv_layer.data) < len(source_mesh.loops):
        return None
    source_world = source_obj.matrix_world.copy()
    decal_world = decal_obj.matrix_world.copy()
    source_vertices = [
        source_world @ vertex.co
        for vertex in source_mesh.vertices
    ]

    triangle_records = []
    triangle_indices = []
    triangles_by_polygon = {}
    for loop_triangle in source_mesh.loop_triangles:
        vertex_indices = tuple(loop_triangle.vertices)
        points = tuple(source_vertices[index] for index in vertex_indices)
        if (points[1] - points[0]).cross(points[2] - points[0]).length_squared <= (
            EPSILON * EPSILON
        ):
            continue
        record = {
            "polygon_index": int(loop_triangle.polygon_index),
            "points": points,
            "uvs": tuple(
                source_uv_layer.data[loop_index].uv.copy()
                for loop_index in loop_triangle.loops
            ),
        }
        record_index = len(triangle_records)
        triangle_records.append(record)
        triangle_indices.append(vertex_indices)
        triangles_by_polygon.setdefault(record["polygon_index"], []).append(
            record_index
        )

    if not triangle_records:
        return None

    source_bvh = BVHTree.FromPolygons(
        source_vertices,
        triangle_indices,
        all_triangles=True,
    )
    if source_bvh is None:
        return None

    primary_uv_layer = ensure_decal_mesh_uv_layers(decal_mesh)
    second_uv_layer = decal_mesh.uv_layers.get(SECOND_UV_LAYER_NAME)
    if second_uv_layer is None:
        if len(decal_mesh.uv_layers) >= 2:
            second_uv_layer = decal_mesh.uv_layers[1]
            second_uv_layer.name = SECOND_UV_LAYER_NAME
        else:
            second_uv_layer = decal_mesh.uv_layers.new(
                name=SECOND_UV_LAYER_NAME
            )
        for primary_uv, second_uv in zip(
            primary_uv_layer.data,
            second_uv_layer.data,
        ):
            second_uv.uv = primary_uv.uv

    transferred_loops = 0
    failed_polygons = 0
    for polygon in decal_mesh.polygons:
        center_world = decal_world @ polygon.center
        nearest = source_bvh.find_nearest(center_world)
        triangle_index = nearest[2] if nearest is not None else None
        if triangle_index is None or triangle_index >= len(triangle_records):
            failed_polygons += 1
            continue

        source_polygon_index = triangle_records[triangle_index][
            "polygon_index"
        ]
        candidate_indices = triangles_by_polygon.get(
            source_polygon_index,
            (triangle_index,),
        )
        for loop_index in polygon.loop_indices:
            vertex_index = decal_mesh.loops[loop_index].vertex_index
            point_world = decal_world @ decal_mesh.vertices[vertex_index].co
            best_record = None
            best_point = None
            best_distance_squared = None
            for candidate_index in candidate_indices:
                record = triangle_records[candidate_index]
                projected = closest_point_on_triangle(
                    point_world,
                    *record["points"],
                )
                distance_squared = (projected - point_world).length_squared
                if (
                    best_distance_squared is None
                    or distance_squared < best_distance_squared
                ):
                    best_record = record
                    best_point = projected
                    best_distance_squared = distance_squared
            if best_record is None:
                continue
            second_uv_layer.data[loop_index].uv = triangle_interpolated_uv(
                best_point,
                best_record["points"],
                best_record["uvs"],
            )
            transferred_loops += 1

    decal_obj["edge_decal_second_uv_mode"] = "SOURCE_FIRST_UV"
    decal_obj["edge_decal_second_uv_source_layer"] = source_uv_layer.name
    decal_obj["edge_decal_second_uv_transferred_loops"] = transferred_loops
    decal_obj["edge_decal_second_uv_failed_polygons"] = failed_polygons
    decal_mesh.uv_layers.active = primary_uv_layer
    if hasattr(decal_mesh.uv_layers, "active_render"):
        decal_mesh.uv_layers.active_render = primary_uv_layer
    decal_mesh.update()
    return second_uv_layer


def decal_uses_source_matched_uv(decal_obj):
    """Return whether UV2 is reserved for copied source-material images."""
    if decal_obj is None:
        return False
    data = getattr(decal_obj, "edge_decal_object_settings", None)
    if data is not None and bool(
        getattr(data, "match_source_material", False)
    ):
        return True
    mesh = getattr(decal_obj, "data", None)
    return bool(
        mesh is not None
        and any(
            material is not None
            and material.get("edge_decal_source_matched")
            for material in mesh.materials
        )
    )


def generate_conformal_second_uv(
    context,
    decal_obj,
    target_texel_density,
    texture_resolution,
    scene_scale_length,
):
    """Create UV channel two with an unrectified Conformal unwrap.

    UV2 deliberately bypasses the primary strip workflow: no quadrify, shape
    averaging, horizontal alignment, strip placement, randomization, UV scale,
    or UV-pin fitting is applied. The shared texel-density math is the only
    post-process, and UV1 is restored as the active/render layer afterwards.
    """
    if decal_obj is None or decal_obj.data is None:
        return 0, 0.0

    mesh = decal_obj.data
    primary_uv_layer = ensure_decal_mesh_uv_layers(mesh)

    if len(mesh.uv_layers) < 2:
        second_uv_layer = mesh.uv_layers.new(name=SECOND_UV_LAYER_NAME)
    else:
        second_uv_layer = mesh.uv_layers[1]
        if second_uv_layer.name != SECOND_UV_LAYER_NAME:
            second_uv_layer.name = SECOND_UV_LAYER_NAME

    temporary_mesh = None
    temporary_object = None

    try:
        force_object_mode(context)

        temporary_mesh = bpy.data.meshes.new(
            f"{mesh.name}_SecondUVUnwrap"
        )
        temporary_mesh.from_pydata(
            [tuple(vertex.co) for vertex in mesh.vertices],
            [],
            [tuple(polygon.vertices) for polygon in mesh.polygons],
        )
        temporary_mesh.update(calc_edges=True)

        seam_keys = {
            frozenset(edge.vertices)
            for edge in mesh.edges
            if edge.use_seam
        }
        for edge in temporary_mesh.edges:
            edge.use_seam = frozenset(edge.vertices) in seam_keys
        temporary_mesh.update()

        temporary_object = bpy.data.objects.new(
            f"{decal_obj.name}_SecondUVUnwrap",
            temporary_mesh,
        )
        context.scene.collection.objects.link(temporary_object)
        temporary_mesh.uv_layers.new(name=SECOND_UV_LAYER_NAME)

        for selected in list(context.selected_objects):
            selected.select_set(False)
        temporary_object.select_set(True)
        context.view_layer.objects.active = temporary_object

        bpy.ops.object.mode_set(mode="EDIT")
        bpy.ops.mesh.select_all(action="SELECT")
        bpy.ops.uv.unwrap(method="CONFORMAL")

        temporary_bmesh = bmesh.from_edit_mesh(temporary_mesh)
        temporary_bmesh.faces.ensure_lookup_table()
        temporary_bmesh.faces.index_update()
        temporary_bmesh_uv = temporary_bmesh.loops.layers.uv.active
        conformal_face_uvs = {
            face.index: [
                (loop.vert.index, loop[temporary_bmesh_uv].uv.copy())
                for loop in face.loops
            ]
            for face in temporary_bmesh.faces
        }
        force_object_mode(context)

        for polygon in mesh.polygons:
            source_corners = conformal_face_uvs.get(polygon.index, ())
            if not source_corners:
                continue

            uv_by_vertex = {}
            for vertex_index, uv in source_corners:
                uv_by_vertex.setdefault(vertex_index, []).append(uv)
            used_by_vertex = {}

            for loop_index in polygon.loop_indices:
                vertex_index = mesh.loops[loop_index].vertex_index
                candidates = uv_by_vertex.get(vertex_index)
                if not candidates:
                    continue
                used_index = used_by_vertex.get(vertex_index, 0)
                second_uv_layer.data[loop_index].uv = candidates[
                    min(used_index, len(candidates) - 1)
                ]
                used_by_vertex[vertex_index] = used_index + 1

        uv_layer = buffered_uv_layer(second_uv_layer)
        islands = collect_selected_uv_islands(
            mesh,
            selected_only=False,
            uv_layer=uv_layer,
        )

        if not islands:
            return 0, 0.0

        set_uv_texel_density(
            mesh,
            uv_layer,
            islands,
            target_texel_density,
            texture_resolution,
            scene_scale_length,
        )
        density = measured_texel_density(
            mesh,
            uv_layer,
            islands,
            texture_resolution,
            scene_scale_length,
        )
        flush_buffered_uv_layer(uv_layer, second_uv_layer)
        mesh.update()
        decal_obj["edge_decal_second_uv_islands"] = len(islands)
        decal_obj["edge_decal_second_uv_texel_density_px_cm"] = density
        decal_obj["edge_decal_second_uv_mode"] = "CONFORMAL"
        return len(islands), density
    finally:
        force_object_mode(context)
        if temporary_object is not None:
            bpy.data.objects.remove(temporary_object, do_unlink=True)
        if temporary_mesh is not None and temporary_mesh.users == 0:
            bpy.data.meshes.remove(temporary_mesh)
        decal_obj.select_set(True)
        context.view_layer.objects.active = decal_obj
        mesh.uv_layers.active = primary_uv_layer
        if hasattr(mesh.uv_layers, "active_render"):
            mesh.uv_layers.active_render = primary_uv_layer
        mesh.update()


def generate_decal_second_uv(
    context,
    source_obj,
    decal_obj,
    target_texel_density,
    texture_resolution,
    scene_scale_length,
):
    """Generate UV2 using source UVs for matched decals, else Conformal."""
    if source_obj is not None and decal_uses_source_matched_uv(decal_obj):
        transferred = transfer_source_first_uv_to_decal(
            source_obj,
            decal_obj,
        )
        if transferred is not None:
            return 0, 0.0
    return generate_conformal_second_uv(
        context,
        decal_obj,
        target_texel_density,
        texture_resolution,
        scene_scale_length,
    )


def integrated_quadrify_decal_mesh(
    decal_obj,
    average_shape=True,
    even_shape=False,
):
    """Run integrated quadrify while writing back UV coordinates only.

    A decal can contain user-edited topology.  Replacing the mesh through
    ``BMesh.to_mesh`` after a UV operation is unnecessary and can rewrite
    element ordering or unrelated custom data.  Keep BMesh as a temporary UV
    solver, then copy its loop UVs onto the existing mesh datablock.
    """
    mesh = decal_obj.data

    if not mesh.polygons:
        return 0, 0

    mesh_uv_layer = ensure_decal_mesh_uv_layers(mesh)

    bm = bmesh.new()

    try:
        bm.from_mesh(mesh)
        bm.faces.ensure_lookup_table()
        bm.edges.ensure_lookup_table()
        uv_layer = bm.loops.layers.uv.active

        if uv_layer is None:
            uv_layer = bm.loops.layers.uv.new("UVMap")

        taper_triangle_bindings = capture_taper_triangle_uv_bindings(bm, uv_layer)
        components = edge_decal_quad_components(bm)
        center_vertex_indices = set(get_center_vertex_indices(decal_obj))
        processed_components = 0
        processed_faces = 0

        for component in components:
            count = edge_decal_quadrify_component(
                bm,
                component,
                uv_layer,
                average_shape=average_shape,
                even_shape=even_shape,
                center_vertex_indices=center_vertex_indices,
            )

            if count:
                processed_components += 1
                processed_faces += count

        restore_taper_triangle_uv_bindings(
            bm,
            uv_layer,
            taper_triangle_bindings,
        )

        # ``bm.from_mesh`` preserves polygon and loop order.  Copy only UV
        # coordinates back so Apply UVs can guarantee topology preservation.
        bm.faces.index_update()
        for face in bm.faces:
            if not (0 <= face.index < len(mesh.polygons)):
                continue
            polygon = mesh.polygons[face.index]
            if len(face.loops) != len(polygon.loop_indices):
                continue
            for source_loop, loop_index in zip(
                face.loops,
                polygon.loop_indices,
            ):
                mesh_uv_layer.data[loop_index].uv = source_loop[uv_layer].uv

        mesh.update()
        return processed_components, processed_faces
    finally:
        bm.free()


def follow_active_quads_per_component(decal_obj):
    """
    Straighten every connected quad component with Follow Active Quads.

    The current UV layout is used as the active-quad reference, so the initial
    Conformal unwrap supplies a valid aspect ratio while Follow Active Quads
    becomes the final strip layout. Components containing non-quads retain
    their Conformal result.
    """
    bm = bmesh.from_edit_mesh(decal_obj.data)
    bm.faces.ensure_lookup_table()

    quad_faces = {
        face
        for face in bm.faces
        if len(face.verts) == 4
    }

    if not quad_faces:
        return 0

    unvisited = set(quad_faces)
    components = []

    while unvisited:
        start_face = unvisited.pop()
        stack = [start_face]
        component = [start_face]

        while stack:
            face = stack.pop()

            for edge in face.edges:
                for linked_face in edge.link_faces:
                    if linked_face in unvisited:
                        unvisited.remove(linked_face)
                        stack.append(linked_face)
                        component.append(linked_face)

        components.append(component)

    processed = 0

    for component in components:
        if len(component) < 2:
            continue

        for face in bm.faces:
            face.select = False

        for face in component:
            face.select = True

        active_face = max(
            component,
            key=lambda face: face.calc_area(),
        )
        bm.faces.active = active_face

        bmesh.update_edit_mesh(
            decal_obj.data,
            loop_triangles=False,
            destructive=False,
        )

        try:
            bpy.ops.uv.select_all(action="SELECT")
            bpy.ops.uv.follow_active_quads(
                mode="LENGTH_AVERAGE",
            )
            processed += 1
        except RuntimeError:
            # Keep the existing Conformal result for unsupported components.
            continue

    for face in bm.faces:
        face.select = True

    if bm.faces:
        bm.faces.active = bm.faces[0]

    bmesh.update_edit_mesh(
        decal_obj.data,
        loop_triangles=False,
        destructive=False,
    )

    return processed


def unwrap_generated_decal(
    context,
    source_obj,
    decal_obj,
    use_integrated_quadrify,
    integrated_average_shape,
    integrated_even_shape,
    use_follow_active_quads,
    uv_scale,
    set_target_density,
    target_texel_density,
    texture_resolution,
    scene_scale_length,
    generate_second_uv,
    average_island_scale,
    align_horizontally,
    place_in_quarter_strips,
    randomize_quarter_strip,
    randomize_horizontal_offset,
    horizontal_randomize_amount,
    random_seed,
    strip_padding,
):
    """Unwrap final topology, quadrify it, then run shared UV processing.

    Generated strip UVs are useful provisional coordinates, but graph poles,
    interactive merges, and junction rebuilds can leave a zero-length shared
    UV edge in that provisional layout. Quadrify propagates from shared UV
    edges, so choosing such an edge can leave part of an island untouched.
    Apply UVs appeared to fix the problem because it already established a
    fresh Angle Based unwrap before entering this function. Do the same for
    every full automatic UV pass so generation and Apply UVs share one stable
    baseline.
    """
    if context.mode == "EDIT_MESH":
        bpy.ops.object.mode_set(mode="OBJECT")

    for selected_object in context.selected_objects:
        selected_object.select_set(False)

    decal_obj.select_set(True)
    context.view_layer.objects.active = decal_obj

    if decal_obj.data.uv_layers.active is None:
        decal_obj.data.uv_layers.new(name="UVMap")

    unwrap_current_decal_topology(context, decal_obj)

    quadrify_result = "DIRECT_STRIP"

    if use_integrated_quadrify:
        component_count, face_count = integrated_quadrify_decal_mesh(
            decal_obj,
            average_shape=integrated_average_shape,
            even_shape=integrated_even_shape,
        )

        if component_count:
            quadrify_result = "INTEGRATED"
            decal_obj["edge_decal_quadrified_components"] = component_count
            decal_obj["edge_decal_quadrified_faces"] = face_count
    elif use_follow_active_quads:
        bpy.ops.object.mode_set(mode="EDIT")
        bpy.ops.mesh.select_all(action="SELECT")

        if use_follow_active_quads:
            follow_count = follow_active_quads_per_component(
                decal_obj,
            )

            if follow_count > 0:
                quadrify_result = "FOLLOW_ACTIVE_QUADS"

        bpy.ops.object.mode_set(mode="OBJECT")

    processed_islands, measured_density = postprocess_generated_uvs(
        decal_obj,
        uv_scale,
        set_target_density,
        target_texel_density,
        texture_resolution,
        scene_scale_length,
        average_island_scale,
        align_horizontally,
        place_in_quarter_strips,
        randomize_quarter_strip,
        randomize_horizontal_offset,
        horizontal_randomize_amount,
        random_seed,
        strip_padding,
    )

    if generate_second_uv:
        generate_decal_second_uv(
            context,
            source_obj,
            decal_obj,
            target_texel_density,
            texture_resolution,
            scene_scale_length,
        )

    ensure_decal_mesh_uv_layers(decal_obj.data)
    force_object_mode(context)
    return quadrify_result, processed_islands, measured_density


def unwrap_current_decal_topology(context, decal_obj):
    """Create a fresh UV baseline from the decal's current faces only."""
    force_object_mode(context)

    for selected in list(context.selected_objects):
        selected.select_set(False)
    decal_obj.select_set(True)
    context.view_layer.objects.active = decal_obj

    ensure_decal_mesh_uv_layers(decal_obj.data)
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")

    try:
        bpy.ops.uv.unwrap(
            method="ANGLE_BASED",
            margin=0.001,
        )
    finally:
        force_object_mode(context)


class EDGEDECAL_OT_apply_uvs(Operator):
    bl_idname = "object.edge_decal_apply_uvs"
    bl_label = "Apply UVs"
    bl_description = (
        "Run the decal UV pipeline on the current layer without regenerating "
        "or replacing its manually edited topology"
    )
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        decal_obj = resolved_editable_decal_layer(context)
        return bool(
            decal_obj is not None
            and decal_obj.type == "MESH"
            and decal_obj.data is not None
            and len(decal_obj.data.polygons) > 0
            and not decal_obj.get("edge_decal_locked", False)
        )

    def execute(self, context):
        decal_obj = resolved_editable_decal_layer(context)
        if (
            decal_obj is None
            or decal_obj.data is None
            or not decal_obj.data.polygons
        ):
            self.report({"ERROR"}, "No populated decal layer is available.")
            return {"CANCELLED"}

        settings = context.scene.edge_decal_settings
        source_obj = getattr(
            decal_obj.edge_decal_object_settings,
            "source_object",
            None,
        )
        if source_obj is None or source_obj.name not in bpy.data.objects:
            source_obj = find_object_by_name_or_full(
                decal_obj.get("edge_decal_source", "")
            )

        active_before = getattr(context.view_layer.objects, "active", None)
        selected_before = [
            obj.name_full
            for obj in context.selected_objects
        ]
        edit_obj_before = getattr(context, "edit_object", None)
        started_in_edit_mode = context.mode == "EDIT_MESH"

        # Flush the user's latest Edit Mode topology before recording the
        # invariant snapshot.  Reading Mesh arrays while still in Edit Mode
        # can otherwise see the pre-edit datablock.
        force_object_mode(context)

        vertex_selection = tuple(
            vertex.select for vertex in decal_obj.data.vertices
        )
        edge_selection = tuple(
            edge.select for edge in decal_obj.data.edges
        )
        polygon_selection = tuple(
            polygon.select for polygon in decal_obj.data.polygons
        )
        vertex_count = len(decal_obj.data.vertices)
        edge_count = len(decal_obj.data.edges)
        polygon_count = len(decal_obj.data.polygons)
        polygon_topology = tuple(
            tuple(polygon.vertices)
            for polygon in decal_obj.data.polygons
        )

        quadrify_result = "DIRECT_STRIP"
        processed_islands = 0
        measured_density = 0.0
        pinned_islands = 0

        try:
            ensure_decal_mesh_uv_layers(decal_obj.data)

            (
                quadrify_result,
                processed_islands,
                measured_density,
            ) = unwrap_generated_decal(
                context,
                source_obj,
                decal_obj,
                settings.use_integrated_quadrify,
                settings.integrated_quadrify_average_shape,
                settings.integrated_quadrify_even_shape,
                settings.use_follow_active_quads,
                settings.uv_scale,
                settings.set_target_texel_density,
                settings.target_texel_density,
                settings.texture_resolution,
                context.scene.unit_settings.scale_length,
                settings.generate_second_uv,
                settings.average_uv_island_scale,
                settings.align_uvs_horizontally,
                settings.place_in_quarter_strips,
                settings.randomize_quarter_strip,
                settings.randomize_horizontal_offset,
                settings.horizontal_randomize_amount,
                settings.seed,
                settings.uv_strip_padding,
            )

            if (
                settings.auto_use_uv_pins
                and uv_pins_for_decal_layer_material(
                    context.scene,
                    decal_obj,
                )
            ):
                pinned_islands = apply_uv_pins_to_decal_objects(
                    [decal_obj],
                    uv_pins_for_decal_layer_material(
                        context.scene,
                        decal_obj,
                    ),
                    settings.seed,
                )

            # This is a hard invariant for the UV-only workflow.  If a future
            # UV implementation accidentally changes topology, fail loudly
            # instead of presenting the operation as topology-preserving.
            topology_unchanged = (
                len(decal_obj.data.vertices) == vertex_count
                and len(decal_obj.data.edges) == edge_count
                and len(decal_obj.data.polygons) == polygon_count
                and tuple(
                    tuple(polygon.vertices)
                    for polygon in decal_obj.data.polygons
                ) == polygon_topology
            )
            if not topology_unchanged:
                raise RuntimeError(
                    "The UV pipeline unexpectedly changed decal topology."
                )

            decal_obj["edge_decal_last_uv_signature"] = (
                decal_uv_settings_signature(settings)
            )
            if measured_density > 0.0:
                decal_obj[
                    "edge_decal_texel_density_px_cm"
                ] = measured_density

        except RuntimeError as error:
            self.report({"ERROR"}, f"Apply UVs failed: {error}")
            return {"CANCELLED"}
        finally:
            force_object_mode(context)

            for vertex, was_selected in zip(
                decal_obj.data.vertices,
                vertex_selection,
            ):
                vertex.select = was_selected
            for edge, was_selected in zip(
                decal_obj.data.edges,
                edge_selection,
            ):
                edge.select = was_selected
            for polygon, was_selected in zip(
                decal_obj.data.polygons,
                polygon_selection,
            ):
                polygon.select = was_selected
            decal_obj.data.update()

            for selected in list(context.selected_objects):
                selected.select_set(False)

            for object_name in selected_before:
                selected = find_object_by_name_or_full(object_name)
                if selected is not None:
                    try:
                        selected.select_set(True)
                    except RuntimeError:
                        pass

            if (
                active_before is not None
                and active_before.name in bpy.data.objects
            ):
                context.view_layer.objects.active = active_before

            if (
                started_in_edit_mode
                and edit_obj_before is not None
                and edit_obj_before.name in bpy.data.objects
            ):
                try:
                    edit_obj_before.select_set(True)
                    context.view_layer.objects.active = edit_obj_before
                    bpy.ops.object.mode_set(mode="EDIT")
                except RuntimeError:
                    force_object_mode(context)

        details = [f"Applied UVs to {processed_islands} island(s)"]
        if quadrify_result == "INTEGRATED":
            details.append("quadrified")
        elif quadrify_result == "FOLLOW_ACTIVE_QUADS":
            details.append("followed active quads")
        if pinned_islands:
            details.append(f"pinned {pinned_islands}")
        details.append("topology preserved")
        self.report({"INFO"}, "; ".join(details))
        return {"FINISHED"}


def chain_endpoint_corner_trim_interval(
    chain_verts,
    chain_edges,
    closed,
    world_matrix,
    bevel_width,
    multiplier=1.0,
):
    """Trim only open chain ends that stop beside a genuine turning edge."""
    if closed or not chain_edges or len(chain_verts) < 2 or bevel_width <= EPSILON:
        return None

    total_length = sum(
        ((world_matrix @ chain_verts[index + 1].co) -
         (world_matrix @ chain_verts[index].co)).length
        for index in range(len(chain_edges))
    )
    if total_length <= EPSILON:
        return None

    selected = set(chain_edges)

    def endpoint_needs_trim(vertex, neighbor):
        endpoint_world = world_matrix @ vertex.co
        inward = safe_normalized((world_matrix @ neighbor.co) - endpoint_world)
        for candidate in vertex.link_edges:
            if candidate in selected or candidate.hide or len(candidate.link_faces) != 2:
                continue
            other = candidate.other_vert(vertex)
            outward = safe_normalized((world_matrix @ other.co) - endpoint_world)
            turn = acos(max(-1.0, min(1.0, inward.dot(outward))))
            if turn > radians(22.5):
                return True
        return False

    trim_distance = max(0.0, float(bevel_width) * max(0.0, float(multiplier)))
    trim_distance = min(trim_distance, total_length * 0.45)
    start_trim = trim_distance if endpoint_needs_trim(chain_verts[0], chain_verts[1]) else 0.0
    end_trim = trim_distance if endpoint_needs_trim(chain_verts[-1], chain_verts[-2]) else 0.0

    if start_trim <= EPSILON and end_trim <= EPSILON:
        return None

    start = start_trim / total_length
    end = 1.0 - (end_trim / total_length)
    return (start, end) if end - start > 0.05 else None
