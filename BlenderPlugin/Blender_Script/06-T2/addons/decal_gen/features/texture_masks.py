# SPDX-License-Identifier: GPL-2.0-or-later
"""Paintable per-layer texture masks and source-UV edge filtering.

Loaded into the add-on package shared namespace by __init__.py.
"""


EDGEDECAL_MASK_DEFAULT_RESOLUTION = 1024
EDGEDECAL_MASK_SAMPLE_SPACING_PIXELS = 8.0
EDGEDECAL_MASK_MAX_EDGE_SAMPLES = 128
EDGEDECAL_MASK_TRANSITION_REFINEMENT_STEPS = 10


def generation_mask_layer(source_obj, context=None):
    """Resolve the layer whose mask should constrain the current generation."""
    target_name = str(globals().get("EDGEDECAL_REGENERATE_TARGET") or "")
    if target_name:
        target = find_object_by_name_or_full(target_name)
        if decal_layer_is_valid(target, source_obj):
            return target

    return resolve_generation_target_layer(
        source_obj,
        context=context,
        include_locked=False,
    )


def layer_generation_mask_image(layer_obj):
    data = getattr(layer_obj, "edge_decal_object_settings", None)
    if data is None or not bool(getattr(data, "use_texture_mask", False)):
        return None
    image = getattr(data, "texture_mask", None)
    if image is None or int(image.size[0]) <= 0 or int(image.size[1]) <= 0:
        return None
    return image


def active_texture_mask_layer(context):
    source_obj = edge_decal_context_source(context)
    if source_obj is None:
        active_obj = getattr(context, "active_object", None)
        if active_obj is not None and active_obj.get("edge_decal_generated"):
            return active_obj
        return None
    return active_decal_layer_for_source(source_obj, context=context)


def texture_mask_paint_is_active(context, layer_obj=None):
    if context is None or context.mode != "PAINT_TEXTURE":
        return False
    if layer_obj is None:
        layer_obj = active_texture_mask_layer(context)
    image = layer_generation_mask_image(layer_obj)
    if image is None:
        return False
    image_paint = context.scene.tool_settings.image_paint
    return bool(
        image_paint.mode == "IMAGE"
        and image_paint.canvas == image
    )


def create_black_generation_mask(layer_obj, resolution=EDGEDECAL_MASK_DEFAULT_RESOLUTION):
    """Create a black generated image owned by one decal layer."""
    resolution = max(64, min(8192, int(resolution)))
    display_name = str(
        layer_obj.get("edge_decal_layer_name", layer_obj.name)
    )
    image = bpy.data.images.new(
        name=f"{display_name}_GenerationMask",
        width=resolution,
        height=resolution,
        alpha=False,
        float_buffer=False,
        is_data=True,
    )
    image.generated_color = (0.0, 0.0, 0.0, 1.0)
    image.use_fake_user = True
    image["edge_decal_generation_mask"] = True
    image["edge_decal_mask_layer"] = layer_obj.name_full
    try:
        image.colorspace_settings.name = "Non-Color"
    except (TypeError, ValueError):
        pass
    image.update()
    return image


def reset_generation_mask_black(image):
    if image is None or int(image.size[0]) <= 0 or int(image.size[1]) <= 0:
        return False
    pixel_count = int(image.size[0]) * int(image.size[1])
    black = array("f", (0.0, 0.0, 0.0, 1.0)) * pixel_count
    image.pixels.foreach_set(black)
    image.update()
    return True


def generation_mask_pixel_buffer(image):
    values = array("f", [0.0]) * len(image.pixels)
    image.pixels.foreach_get(values)
    return values


def generation_mask_status(source_bm, layer_obj):
    """Validate the active mask without changing the generation selection."""
    data = getattr(layer_obj, "edge_decal_object_settings", None)
    if data is None or not bool(getattr(data, "use_texture_mask", False)):
        return "DISABLED"
    if layer_generation_mask_image(layer_obj) is None:
        return "MISSING"
    if source_bm.loops.layers.uv.active is None:
        return "NO_UV"
    return "READY"


def sample_generation_mask_value(pixels, width, height, u, v):
    """Bilinearly sample mask luminance with UVs clamped to the image bounds."""
    u = max(0.0, min(1.0, float(u)))
    v = max(0.0, min(1.0, float(v)))
    x = u * max(0, width - 1)
    y = v * max(0, height - 1)
    x0 = int(x)
    y0 = int(y)
    x1 = min(width - 1, x0 + 1)
    y1 = min(height - 1, y0 + 1)
    tx = x - x0
    ty = y - y0

    def _luminance(px, py):
        offset = (py * width + px) * 4
        return (
            float(pixels[offset])
            + float(pixels[offset + 1])
            + float(pixels[offset + 2])
        ) / 3.0

    bottom = _luminance(x0, y0) * (1.0 - tx) + _luminance(x1, y0) * tx
    top = _luminance(x0, y1) * (1.0 - tx) + _luminance(x1, y1) * tx
    return bottom * (1.0 - ty) + top * ty


def generation_mask_sampler(source_bm, layer_obj):
    image = layer_generation_mask_image(layer_obj)
    if image is None:
        return None
    uv_layer = source_bm.loops.layers.uv.active
    if uv_layer is None:
        return None
    data = layer_obj.edge_decal_object_settings
    return {
        "image": image,
        "uv_layer": uv_layer,
        "pixels": generation_mask_pixel_buffer(image),
        "width": int(image.size[0]),
        "height": int(image.size[1]),
        "threshold": max(
            1.0e-6,
            min(1.0, float(data.texture_mask_threshold)),
        ),
    }


def generation_mask_edge_uv_pairs(edge, uv_layer):
    """Return UV endpoint pairs oriented from edge.verts[0] to edge.verts[1]."""
    pairs = []
    for loop in edge.link_loops:
        uv_a = loop[uv_layer].uv.copy()
        uv_b = loop.link_loop_next[uv_layer].uv.copy()
        if loop.vert == edge.verts[0]:
            pairs.append((uv_a, uv_b))
        else:
            pairs.append((uv_b, uv_a))
    return pairs


def generation_mask_value_on_edge(uv_pairs, sampler, factor):
    value = 0.0
    for uv_a, uv_b in uv_pairs:
        u = uv_a.x + (uv_b.x - uv_a.x) * factor
        v = uv_a.y + (uv_b.y - uv_a.y) * factor
        value = max(
            value,
            sample_generation_mask_value(
                sampler["pixels"],
                sampler["width"],
                sampler["height"],
                u,
                v,
            ),
        )
    return value


def generation_mask_edge_intervals(edge, sampler):
    """Return white intervals and refined transition factors on one edge."""
    uv_pairs = generation_mask_edge_uv_pairs(edge, sampler["uv_layer"])
    if not uv_pairs:
        return [], []

    pixel_length = max(
        (
            ((uv_b.x - uv_a.x) * sampler["width"]) ** 2
            + ((uv_b.y - uv_a.y) * sampler["height"]) ** 2
        ) ** 0.5
        for uv_a, uv_b in uv_pairs
    )
    sample_count = max(
        2,
        min(
            EDGEDECAL_MASK_MAX_EDGE_SAMPLES,
            int(pixel_length / EDGEDECAL_MASK_SAMPLE_SPACING_PIXELS) + 2,
        ),
    )
    threshold = sampler["threshold"]
    factors = [
        index / max(1, sample_count - 1)
        for index in range(sample_count)
    ]
    states = [
        generation_mask_value_on_edge(uv_pairs, sampler, factor) >= threshold
        for factor in factors
    ]

    transitions = []
    for index in range(len(factors) - 1):
        if states[index] == states[index + 1]:
            continue
        low = factors[index]
        high = factors[index + 1]
        low_state = states[index]
        for _step in range(EDGEDECAL_MASK_TRANSITION_REFINEMENT_STEPS):
            middle = (low + high) * 0.5
            middle_state = (
                generation_mask_value_on_edge(uv_pairs, sampler, middle)
                >= threshold
            )
            if middle_state == low_state:
                low = middle
            else:
                high = middle
        transition = (low + high) * 0.5
        if 1.0e-5 < transition < 1.0 - 1.0e-5:
            transitions.append(transition)

    boundaries = [0.0] + transitions + [1.0]
    white_intervals = []
    for start, end in zip(boundaries[:-1], boundaries[1:]):
        middle = (start + end) * 0.5
        if generation_mask_value_on_edge(uv_pairs, sampler, middle) >= threshold:
            white_intervals.append((start, end))
    return white_intervals, transitions


def split_bmesh_edges_by_generation_mask(
    work_bmesh,
    edges,
    layer_obj,
):
    """Split temporary source edges at mask transitions and keep white pieces."""
    sampler = generation_mask_sampler(work_bmesh, layer_obj)
    if sampler is None:
        return list(edges), {
            "cut_count": 0,
            "partial_edge_count": 0,
            "cut_vertex_indices": set(),
        }

    selected_segments = []
    cut_count = 0
    partial_edge_count = 0
    cut_vertices = []
    for edge in list(edges):
        if not edge.is_valid:
            continue
        white_intervals, transitions = generation_mask_edge_intervals(
            edge,
            sampler,
        )
        if not transitions:
            if white_intervals:
                selected_segments.append(edge)
            continue

        partial_edge_count += 1
        cut_count += len(transitions)
        interval_records = []
        boundaries = [0.0] + transitions + [1.0]
        for start, end in zip(boundaries[:-1], boundaries[1:]):
            middle = (start + end) * 0.5
            enabled = any(
                white_start - EPSILON <= middle <= white_end + EPSILON
                for white_start, white_end in white_intervals
            )
            interval_records.append((start, end, enabled))

        current_edge = edge
        current_start_vertex = edge.verts[0]
        previous_factor = 0.0
        split_segments = []
        for transition in transitions:
            remaining = max(EPSILON, 1.0 - previous_factor)
            local_factor = (transition - previous_factor) / remaining
            prefix_edge, new_vertex = bmesh.utils.edge_split(
                current_edge,
                current_start_vertex,
                max(EPSILON, min(1.0 - EPSILON, local_factor)),
            )
            split_segments.append(prefix_edge)
            cut_vertices.append(new_vertex)
            current_start_vertex = new_vertex
            previous_factor = transition
        split_segments.append(current_edge)

        for segment, (_start, _end, enabled) in zip(
            split_segments,
            interval_records,
        ):
            if enabled:
                selected_segments.append(segment)

    work_bmesh.normal_update()
    work_bmesh.verts.ensure_lookup_table()
    work_bmesh.edges.ensure_lookup_table()
    work_bmesh.faces.ensure_lookup_table()
    work_bmesh.verts.index_update()
    work_bmesh.edges.index_update()
    work_bmesh.faces.index_update()
    return selected_segments, {
        "cut_count": cut_count,
        "partial_edge_count": partial_edge_count,
        "cut_vertex_indices": {
            int(vertex.index)
            for vertex in cut_vertices
            if vertex.is_valid
        },
    }


class EDGEDECAL_OT_texture_mask_add(Operator):
    bl_idname = "object.edge_decal_texture_mask_add"
    bl_label = "Add Layer Mask"
    bl_description = (
        "Create a solid-black mask for this layer; paint white where decals "
        "are allowed to generate"
    )
    bl_options = {"REGISTER", "UNDO"}

    resolution: IntProperty(
        name="Resolution",
        default=EDGEDECAL_MASK_DEFAULT_RESOLUTION,
        min=64,
        max=8192,
        subtype="PIXEL",
    )

    def execute(self, context):
        layer_obj = active_texture_mask_layer(context)
        if layer_obj is None:
            self.report({"ERROR"}, "No active decal layer")
            return {"CANCELLED"}

        data = layer_obj.edge_decal_object_settings
        image = getattr(data, "texture_mask", None)
        if image is None:
            image = create_black_generation_mask(layer_obj, self.resolution)
            data.texture_mask = image
        data.use_texture_mask = True
        self.report(
            {"INFO"},
            "Black mask created. Paint white where this layer may generate.",
        )
        return {"FINISHED"}


class EDGEDECAL_OT_texture_mask_remove(Operator):
    bl_idname = "object.edge_decal_texture_mask_remove"
    bl_label = "Remove Layer Mask"
    bl_description = "Detach the texture mask and restore unmasked generation"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        layer_obj = active_texture_mask_layer(context)
        if layer_obj is None:
            return {"CANCELLED"}
        data = layer_obj.edge_decal_object_settings
        data.use_texture_mask = False
        data.texture_mask = None
        return {"FINISHED"}


class EDGEDECAL_OT_texture_mask_reset(Operator):
    bl_idname = "object.edge_decal_texture_mask_reset"
    bl_label = "Reset Mask to Black"
    bl_description = "Erase the whole mask so this layer generates nowhere"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        layer_obj = active_texture_mask_layer(context)
        image = layer_generation_mask_image(layer_obj)
        if image is None or not reset_generation_mask_black(image):
            return {"CANCELLED"}
        self.report({"INFO"}, "Layer mask reset to black")
        return {"FINISHED"}


class EDGEDECAL_OT_texture_mask_paint(Operator):
    bl_idname = "object.edge_decal_texture_mask_paint"
    bl_label = "Paint Layer Mask"
    bl_description = (
        "Use this mask as Blender's Texture Paint canvas on the source mesh"
    )

    def execute(self, context):
        layer_obj = active_texture_mask_layer(context)
        image = layer_generation_mask_image(layer_obj)
        if layer_obj is None or image is None:
            self.report({"ERROR"}, "Add and enable a layer mask first")
            return {"CANCELLED"}
        if texture_mask_paint_is_active(context, layer_obj):
            try:
                bpy.ops.object.mode_set(mode="OBJECT")
            except RuntimeError as error:
                self.report({"ERROR"}, f"Could not exit Texture Paint: {error}")
                return {"CANCELLED"}
            self.report({"INFO"}, "Exited layer mask Texture Paint")
            return {"FINISHED"}

        data = layer_obj.edge_decal_object_settings
        source_obj = getattr(data, "source_object", None)
        if source_obj is None:
            source_obj = find_object_by_name_or_full(
                str(layer_obj.get("edge_decal_source", ""))
            )
        if source_obj is None or source_obj.type != "MESH":
            self.report({"ERROR"}, "The layer's source mesh is missing")
            return {"CANCELLED"}
        if source_obj.data.uv_layers.active is None:
            self.report(
                {"ERROR"},
                "Texture painting the layer mask needs an active source UV map",
            )
            return {"CANCELLED"}

        if context.mode != "OBJECT":
            try:
                bpy.ops.object.mode_set(mode="OBJECT")
            except RuntimeError:
                self.report({"ERROR"}, "Could not leave the current mode")
                return {"CANCELLED"}

        select_only_object(context, source_obj)
        image_paint = context.scene.tool_settings.image_paint
        try:
            image_paint.mode = "IMAGE"
            image_paint.canvas = image
            bpy.ops.object.mode_set(mode="TEXTURE_PAINT")
        except (AttributeError, RuntimeError, TypeError, ValueError) as error:
            self.report({"ERROR"}, f"Could not start Texture Paint: {error}")
            return {"CANCELLED"}
        self.report(
            {"INFO"},
            "Texture Paint ready: paint white to generate and black to block",
        )
        return {"FINISHED"}
