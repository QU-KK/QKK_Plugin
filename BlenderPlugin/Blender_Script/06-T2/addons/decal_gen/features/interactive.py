# SPDX-License-Identifier: GPL-2.0-or-later
"""Interactive viewport generation, stroke editing, width controls, slicing, and custom undo.

Loaded into the add-on package shared namespace by __init__.py.
"""


def resolve_interactive_preview_width(
    face_width,
    relative_face_width,
    source_reference_size,
):
    """Resolve the overlay half-width exactly like generated strip geometry."""
    requested = max(float(face_width), MIN_FACE_WIDTH)
    if not relative_face_width:
        return requested
    reference = max(float(source_reference_size), 1.0e-6)
    return max(requested * reference, reference * 1.0e-7)



class EDGEDECAL_OT_interactive_generate(Operator):
    bl_idname = "mesh.edge_decal_interactive_generate"
    bl_label = "Interactive Generate"
    bl_description = (
        "Hover source mesh edges and click to generate decals without manually selecting them"
    )
    bl_options = {"REGISTER", "UNDO"}

    _draw_handle = None
    _remove_draw_handle = None
    _mouse_region = (0, 0)
    _hovered_edge_index = -1
    _hovered_edge_indices = None
    _hovered_edge_points = None
    _edge_pick_radius = 14.0
    _source_object_name = ""
    _started_in_edit_mode = False
    _alt_down = False
    _shift_down = False
    _ctrl_down = False
    _ctrl_slice_interval = None
    _ctrl_fraction = 0.30
    _ctrl_control_points = None
    _ctrl_active_point = -1
    _shift_preview_edge_indices = None
    _shift_preview_edge_points = None
    _shift_fraction = 1.0
    _shift_span_edges = 0.0
    _shift_path_key = None
    _shift_terminal_edge_index = -1
    _shift_slice_interval = None
    _shift_connection_path = None
    _pending_edge_indices = None
    _pending_edge_points = None
    _pending_partial_edge_index = -1
    _pending_partial_fraction = 1.0
    _path_anchor_edge_index = -1
    _last_generated_object_name = ""
    _action_history = None
    _remove_mode = False
    _remove_components = None
    _hovered_remove_index = -1
    _remove_target_radius = 18.0
    _last_stroke_vertex_indices = None
    _width_drag_active = False
    _width_drag_start_x = 0
    _width_drag_start_value = 0.06
    _width_drag_current_value = 0.06
    _interactive_face_width = 0.06
    _interactive_width_reference_size = 1.0
    _help_draw_handle = None
    _interactive_event_timer = None
    _endpoint_taper_enabled = False
    _auto_merge_enabled = True
    _show_help_overlay = False
    _last_click_edge_index = -1
    _last_click_time = 0.0
    _last_remove_click_edge_index = -1
    _last_remove_click_time = 0.0
    _last_remove_click_mouse_region = (0, 0)
    _last_remove_connected_indices = None
    _last_remove_action = None
    _consume_next_remove_double_click = False

    @classmethod
    def poll(cls, context):
        source_obj = (
            context.edit_object
            if context.mode == "EDIT_MESH"
            else edge_decal_context_source(context)
        )
        return (
            context.area is not None
            and context.area.type == "VIEW_3D"
            and context.mode in {"OBJECT", "EDIT_MESH"}
            and source_obj is not None
            and source_obj.type == "MESH"
            and not source_obj.get("edge_decal_generated")
        )

    def _source_object(self, context):
        if not self._source_object_name:
            return None
        return context.view_layer.objects.get(self._source_object_name)

    def _activate_source(self, context, edit_mode=False):
        source_obj = self._source_object(context)
        if source_obj is None:
            return None

        if context.mode != "OBJECT":
            try:
                bpy.ops.object.mode_set(mode="OBJECT")
            except RuntimeError:
                return None

        for candidate in context.view_layer.objects:
            try:
                candidate.select_set(False)
            except RuntimeError:
                pass

        source_obj.select_set(True)
        context.view_layer.objects.active = source_obj

        if edit_mode:
            try:
                bpy.ops.object.mode_set(mode="EDIT")
            except RuntimeError:
                return None

        return source_obj

    def _clear_edit_selection(self, source_obj):
        bm = bmesh.from_edit_mesh(source_obj.data)
        bm.verts.ensure_lookup_table()
        bm.edges.ensure_lookup_table()
        bm.faces.ensure_lookup_table()

        for vertex in bm.verts:
            vertex.select = False
        for edge in bm.edges:
            edge.select = False
        for face in bm.faces:
            face.select = False

        bmesh.update_edit_mesh(
            source_obj.data,
            loop_triangles=False,
            destructive=False,
        )

    def _restore_working_mode(self, context):
        source_obj = self._activate_source(
            context,
            edit_mode=self._started_in_edit_mode,
        )
        if source_obj is None:
            return None

        if self._started_in_edit_mode:
            self._clear_edit_selection(source_obj)

        return source_obj

    def _open_bmesh_for_read(self, source_obj):
        if bpy.context.mode == "EDIT_MESH" and bpy.context.edit_object == source_obj:
            bm = bmesh.from_edit_mesh(source_obj.data)
            bm.edges.ensure_lookup_table()
            bm.verts.ensure_lookup_table()
            return bm, False

        bm = bmesh.new()
        bm.from_mesh(source_obj.data)
        bm.edges.ensure_lookup_table()
        bm.verts.ensure_lookup_table()
        return bm, True

    def _iter_hover_edges(self, source_obj):
        bm, owns_bm = self._open_bmesh_for_read(source_obj)
        try:
            for edge in bm.edges:
                if edge.hide or len(edge.link_faces) != 2:
                    continue
                yield (
                    edge.index,
                    edge.verts[0].co.copy(),
                    edge.verts[1].co.copy(),
                )
        finally:
            if owns_bm:
                bm.free()

    def _topological_edge_loop(self, source_obj, start_edge_index):
        """Follow the source mesh's actual quad-topology edge loop."""
        bm, owns_bm = self._open_bmesh_for_read(source_obj)

        try:
            return walk_topological_edge_loop(bm, start_edge_index)
        finally:
            if owns_bm:
                bm.free()

    def _effective_path_anchor(self, source_obj):
        """Pick the pending-run edge to start Shift path-finding from.

        The clicked edge under the cursor is often a mid-run segment of a
        beveled edge that is split into several mesh edges. Starting the path
        there makes the connection branch off the middle of the pending run,
        producing a T-junction that ``extract_edge_chains`` later splits into
        two separate islands - the visible gap in the merged strip.

        Instead, anchor at the pending run's free endpoint nearest the hovered
        target so the connection attaches to the end of the run and the whole
        selection builds as one continuous chain.
        """
        pending = [int(index) for index in (self._pending_edge_indices or [])]
        if not pending:
            return self._path_anchor_edge_index
        if len(pending) == 1:
            return pending[0]

        target = self._hovered_edge_index
        bm, owns_bm = self._open_bmesh_for_read(source_obj)
        try:
            edge_count = len(bm.edges)
            pending_valid = [index for index in pending if 0 <= index < edge_count]
            if not pending_valid:
                return self._path_anchor_edge_index

            world_matrix = source_obj.matrix_world

            # Count how many pending edges touch each vertex. A run endpoint is
            # a vertex owned by exactly one pending edge.
            vertex_pending_count = {}
            for index in pending_valid:
                for vert in bm.edges[index].verts:
                    vertex_pending_count[vert.index] = (
                        vertex_pending_count.get(vert.index, 0) + 1
                    )

            endpoint_candidates = []
            for index in pending_valid:
                for vert in bm.edges[index].verts:
                    if vertex_pending_count.get(vert.index, 0) == 1:
                        endpoint_candidates.append(
                            (index, world_matrix @ vert.co)
                        )

            if not endpoint_candidates:
                if self._path_anchor_edge_index in set(pending_valid):
                    return self._path_anchor_edge_index
                return pending_valid[0]

            if not (0 <= target < edge_count):
                return endpoint_candidates[0][0]

            target_verts = bm.edges[target].verts
            target_mid = (
                (world_matrix @ target_verts[0].co)
                + (world_matrix @ target_verts[1].co)
            ) * 0.5

            best = None
            for index, endpoint_co in endpoint_candidates:
                distance = (endpoint_co - target_mid).length_squared
                if best is None or distance < best[0]:
                    best = (distance, index)
            return best[1]
        finally:
            if owns_bm:
                bm.free()

    def _edge_path_between(self, source_obj, start_edge_index, end_edge_index):
        """Return a short, smooth manifold path between two source edges.

        This uses Dijkstra rather than unweighted breadth-first search. The
        path cost combines world-space edge length with a turn penalty, so it
        prefers the physically shorter route while avoiding unnecessary sharp
        detours through nearby topology.
        """
        bm, owns_bm = self._open_bmesh_for_read(source_obj)
        world_matrix = source_obj.matrix_world

        try:
            if not (
                0 <= start_edge_index < len(bm.edges)
                and 0 <= end_edge_index < len(bm.edges)
            ):
                return []

            start_edge = bm.edges[start_edge_index]
            end_edge = bm.edges[end_edge_index]

            if start_edge.hide or end_edge.hide:
                return []
            if len(start_edge.link_faces) != 2 or len(end_edge.link_faces) != 2:
                return []
            if start_edge == end_edge:
                return [start_edge.index]

            valid_edges = [
                edge for edge in bm.edges
                if not edge.hide and len(edge.link_faces) == 2
            ]
            if not valid_edges:
                return []

            average_length = sum(
                ((world_matrix @ edge.verts[1].co) -
                 (world_matrix @ edge.verts[0].co)).length
                for edge in valid_edges
            ) / max(1, len(valid_edges))

            # A 90-degree turn costs about two average edge lengths. This is
            # strong enough to avoid zig-zagging without forcing a longer loop.
            turn_weight = max(average_length * 2.0, 1.0e-6)

            # State: (edge_index, entry_vertex_index). The edge is traversed
            # from entry_vertex to its opposite vertex.
            distances = {}
            previous = {}
            queue = []
            serial = 0

            for entry_vertex in start_edge.verts:
                state = (start_edge.index, entry_vertex.index)
                distances[state] = 0.0
                previous[state] = None
                heapq.heappush(queue, (0.0, serial, state))
                serial += 1

            goal_state = None

            while queue:
                current_cost, _serial, state = heapq.heappop(queue)
                if current_cost > distances.get(state, float("inf")) + EPSILON:
                    continue

                edge_index, entry_vertex_index = state
                current_edge = bm.edges[edge_index]

                if current_edge == end_edge:
                    goal_state = state
                    break

                entry_vertex = bm.verts[entry_vertex_index]
                if entry_vertex not in current_edge.verts:
                    continue

                exit_vertex = current_edge.other_vert(entry_vertex)
                current_direction = safe_normalized(
                    (world_matrix @ exit_vertex.co)
                    - (world_matrix @ entry_vertex.co),
                    Vector((1.0, 0.0, 0.0)),
                )

                for neighbor in exit_vertex.link_edges:
                    if (
                        neighbor == current_edge
                        or neighbor.hide
                        or len(neighbor.link_faces) != 2
                    ):
                        continue

                    other_vertex = neighbor.other_vert(exit_vertex)
                    next_direction = safe_normalized(
                        (world_matrix @ other_vertex.co)
                        - (world_matrix @ exit_vertex.co),
                        current_direction,
                    )
                    dot_value = max(-1.0, min(1.0, current_direction.dot(next_direction)))
                    turn_angle = acos(dot_value)
                    neighbor_length = (
                        (world_matrix @ other_vertex.co)
                        - (world_matrix @ exit_vertex.co)
                    ).length

                    transition_cost = neighbor_length + turn_angle * turn_weight
                    next_state = (neighbor.index, exit_vertex.index)
                    new_cost = current_cost + transition_cost

                    if new_cost + EPSILON < distances.get(next_state, float("inf")):
                        distances[next_state] = new_cost
                        previous[next_state] = state
                        heapq.heappush(queue, (new_cost, serial, next_state))
                        serial += 1

            if goal_state is None:
                return []

            path_states = []
            state = goal_state
            while state is not None:
                path_states.append(state)
                state = previous[state]
            path_states.reverse()

            path = []
            for edge_index, _entry_vertex_index in path_states:
                if not path or path[-1] != edge_index:
                    path.append(edge_index)
            return path
        finally:
            if owns_bm:
                bm.free()

    def _edge_world_segments(self, source_obj, edge_indices):
        bm, owns_bm = self._open_bmesh_for_read(source_obj)
        world_matrix = source_obj.matrix_world
        segments = []

        try:
            for edge_index in edge_indices:
                if 0 <= edge_index < len(bm.edges):
                    edge = bm.edges[edge_index]
                    segments.extend((
                        world_matrix @ edge.verts[0].co,
                        world_matrix @ edge.verts[1].co,
                    ))
        finally:
            if owns_bm:
                bm.free()

        return tuple(segments)

    def _refresh_pending_overlay(self, context):
        source_obj = self._source_object(context)
        if source_obj is None or not self._pending_edge_indices:
            self._pending_edge_points = None
            return

        full_edges = [
            edge_index for edge_index in self._pending_edge_indices
            if edge_index != self._pending_partial_edge_index
        ]
        points = list(self._edge_world_segments(source_obj, full_edges))

        if (
            self._pending_partial_edge_index >= 0
            and self._pending_partial_fraction < 1.0 - EPSILON
        ):
            bm, owns_bm = self._open_bmesh_for_read(source_obj)
            try:
                if 0 <= self._pending_partial_edge_index < len(bm.edges):
                    edge = bm.edges[self._pending_partial_edge_index]
                    world_matrix = source_obj.matrix_world
                    world_a = world_matrix @ edge.verts[0].co
                    world_b = world_matrix @ edge.verts[1].co

                    # Use the neighboring pending edge to determine which side
                    # of the terminal edge belongs to the connected stroke.
                    previous_edge = None
                    for candidate_index in reversed(self._pending_edge_indices):
                        if candidate_index == self._pending_partial_edge_index:
                            continue
                        if 0 <= candidate_index < len(bm.edges):
                            candidate = bm.edges[candidate_index]
                            if any(vertex in candidate.verts for vertex in edge.verts):
                                previous_edge = candidate
                                break

                    shared = (
                        next((vertex for vertex in edge.verts if previous_edge and vertex in previous_edge.verts), None)
                    )
                    fraction = max(0.05, min(1.0, self._pending_partial_fraction))
                    if shared is edge.verts[0]:
                        points.extend((world_a, world_a.lerp(world_b, fraction)))
                    elif shared is edge.verts[1]:
                        points.extend((world_b, world_b.lerp(world_a, fraction)))
                    else:
                        points.extend((world_a, world_b))
            finally:
                if owns_bm:
                    bm.free()
        else:
            points.extend(self._edge_world_segments(
                source_obj,
                [self._pending_partial_edge_index]
                if self._pending_partial_edge_index >= 0 else [],
            ))

        self._pending_edge_points = tuple(points)

    def _clear_pending_path(self, context):
        self._pending_edge_indices = []
        self._pending_edge_points = None
        self._pending_partial_edge_index = -1
        self._pending_partial_fraction = 1.0
        self._path_anchor_edge_index = -1
        self._shift_preview_edge_indices = []
        self._shift_preview_edge_points = None
        self._shift_fraction = 1.0
        self._shift_span_edges = 0.0
        self._shift_path_key = None
        self._shift_terminal_edge_index = -1
        self._shift_slice_interval = None
        self._shift_connection_path = []
        if context.area:
            context.area.tag_redraw()

    def _find_hovered_edge(self, context):
        source_obj = self._source_object(context)
        if source_obj is None or context.region is None or context.space_data is None:
            return -1, [], None

        region = context.region
        region_3d = context.space_data.region_3d
        mouse = Vector(self._mouse_region)
        best_index = -1
        best_distance = self._edge_pick_radius
        world_matrix = source_obj.matrix_world

        for edge_index, local_a, local_b in self._iter_hover_edges(source_obj):
            world_a = world_matrix @ local_a
            world_b = world_matrix @ local_b
            point_a = view3d_utils.location_3d_to_region_2d(
                region, region_3d, world_a
            )
            point_b = view3d_utils.location_3d_to_region_2d(
                region, region_3d, world_b
            )

            if point_a is None or point_b is None:
                continue

            distance, screen_factor = self._screen_distance_and_factor_to_segment(
                mouse,
                point_a,
                point_b,
            )
            if distance >= best_distance:
                continue

            factor = self._world_factor_from_screen_factor(
                region_3d,
                world_a,
                world_b,
                screen_factor,
            )
            hit_point = world_a.lerp(world_b, factor)
            hit_screen = point_a.lerp(point_b, screen_factor)
            if not self._source_point_is_view_visible(
                context,
                source_obj,
                hit_point,
                hit_screen,
            ):
                continue

            best_distance = distance
            best_index = edge_index

        if best_index < 0:
            return -1, [], None

        edge_indices = (
            self._topological_edge_loop(source_obj, best_index)
            if self._alt_down
            else [best_index]
        )
        points = self._edge_world_segments(source_obj, edge_indices)
        return best_index, edge_indices, points

    def _ctrl_partial_preview(self, context, edge_index):
        source_obj = self._source_object(context)
        if source_obj is None or edge_index < 0:
            return None, None, None, -1

        bm, owns_bm = self._open_bmesh_for_read(source_obj)
        try:
            if not (0 <= edge_index < len(bm.edges)):
                return None, None, None, -1

            edge = bm.edges[edge_index]
            world_matrix = source_obj.matrix_world
            world_a = world_matrix @ edge.verts[0].co
            world_b = world_matrix @ edge.verts[1].co
            world_mid = world_a.lerp(world_b, 0.5)

            region = context.region
            region_3d = context.space_data.region_3d
            screen_points = [
                view3d_utils.location_3d_to_region_2d(region, region_3d, point)
                for point in (world_a, world_mid, world_b)
            ]
            if any(point is None for point in screen_points):
                return None, None, None, -1

            mouse = Vector(self._mouse_region)
            active_index = min(
                range(3),
                key=lambda index: (mouse - screen_points[index]).length,
            )

            fraction = max(0.05, min(1.0, float(self._ctrl_fraction)))
            if active_index == 0:
                interval = (0.0, fraction)
            elif active_index == 1:
                half = fraction * 0.5
                interval = (0.5 - half, 0.5 + half)
            else:
                interval = (1.0 - fraction, 1.0)

            partial_start = world_a.lerp(world_b, interval[0])
            partial_end = world_a.lerp(world_b, interval[1])
            control_points = (world_a, world_mid, world_b)
            return interval, (partial_start, partial_end), control_points, active_index
        finally:
            if owns_bm:
                bm.free()

    def _update_hover(self, context):
        (
            self._hovered_edge_index,
            self._hovered_edge_indices,
            self._hovered_edge_points,
        ) = self._find_hovered_edge(context)
        self._ctrl_slice_interval = None
        self._ctrl_control_points = None
        self._ctrl_active_point = -1
        if (
            self._ctrl_down
            and not self._alt_down
            and not self._shift_down
            and self._hovered_edge_index >= 0
        ):
            interval, points, control_points, active_point = self._ctrl_partial_preview(
                context,
                self._hovered_edge_index,
            )
            if interval is not None and points is not None:
                self._ctrl_slice_interval = interval
                self._ctrl_control_points = control_points
                self._ctrl_active_point = active_point
                self._hovered_edge_indices = [self._hovered_edge_index]
                self._hovered_edge_points = points

    def _shift_partial_target_segment(self, source_obj, path, terminal_edge_index, fraction):
        """Return the visible portion of the current terminal Shift edge."""
        if not path or terminal_edge_index < 0:
            return None

        bm, owns_bm = self._open_bmesh_for_read(source_obj)
        try:
            if not (0 <= terminal_edge_index < len(bm.edges)):
                return None
            target = bm.edges[terminal_edge_index]
            world_matrix = source_obj.matrix_world
            world_a = world_matrix @ target.verts[0].co
            world_b = world_matrix @ target.verts[1].co
            fraction = max(0.05, min(1.0, float(fraction)))

            target_position = path.index(terminal_edge_index) if terminal_edge_index in path else -1
            if target_position > 0 and 0 <= path[target_position - 1] < len(bm.edges):
                previous = bm.edges[path[target_position - 1]]
                shared = next((v for v in target.verts if v in previous.verts), None)
                if shared is target.verts[0]:
                    return (world_a, world_a.lerp(world_b, fraction))
                if shared is target.verts[1]:
                    return (world_b, world_b.lerp(world_a, fraction))

            return (world_a, world_b)
        finally:
            if owns_bm:
                bm.free()

    def _compute_shift_slice_interval(self, context, target_edges, path):
        """Trim the current terminal edge at the Shift-scroll endpoint."""
        self._shift_slice_interval = None
        terminal_edge_index = self._shift_terminal_edge_index
        fraction = max(0.05, min(1.0, float(self._shift_fraction)))
        if (
            fraction >= 1.0 - EPSILON
            or len(path or []) < 2
            or terminal_edge_index < 0
        ):
            return None

        source_obj = self._source_object(context)
        if source_obj is None:
            return None

        bm, owns_bm = self._open_bmesh_for_read(source_obj)
        try:
            selected = [bm.edges[i] for i in target_edges if 0 <= i < len(bm.edges)]
            chains = extract_edge_chains(selected, source_obj.matrix_world)
            target_edge = bm.edges[terminal_edge_index]
            path_position = path.index(terminal_edge_index) if terminal_edge_index in path else -1
            previous_edge = (
                bm.edges[path[path_position - 1]]
                if path_position > 0 and 0 <= path[path_position - 1] < len(bm.edges)
                else None
            )
            shared = next(
                (v for v in target_edge.verts if previous_edge and v in previous_edge.verts),
                None,
            )
            if shared is None:
                return None

            for chain_verts, chain_edges, closed in chains:
                if closed or target_edge not in chain_edges:
                    continue
                edge_index = chain_edges.index(target_edge)
                if edge_index + 1 >= len(chain_verts):
                    continue

                lengths = []
                for i, edge in enumerate(chain_edges):
                    p0 = source_obj.matrix_world @ chain_verts[i].co
                    p1 = source_obj.matrix_world @ chain_verts[i + 1].co
                    lengths.append((p1 - p0).length)
                total = sum(lengths)
                if total <= EPSILON:
                    return None

                before = sum(lengths[:edge_index])
                edge_length = lengths[edge_index]
                start_vertex = chain_verts[edge_index]
                end_vertex = chain_verts[edge_index + 1]

                if shared == start_vertex:
                    interval = (0.0, (before + edge_length * fraction) / total)
                elif shared == end_vertex:
                    interval = ((before + edge_length * (1.0 - fraction)) / total, 1.0)
                else:
                    return None

                self._shift_slice_interval = (
                    max(0.0, min(1.0, interval[0])),
                    max(0.0, min(1.0, interval[1])),
                )
                return self._shift_slice_interval
        finally:
            if owns_bm:
                bm.free()
        return None

    def _update_shift_preview(self, context):
        """Preview a scroll-adjustable endpoint that may cross multiple edges."""
        self._shift_preview_edge_indices = []
        self._shift_preview_edge_points = None
        self._shift_connection_path = []
        self._shift_slice_interval = None
        self._shift_terminal_edge_index = -1

        if (
            self._remove_mode
            or not self._shift_down
            or self._hovered_edge_index < 0
            or not self._pending_edge_indices
            or self._path_anchor_edge_index < 0
        ):
            return

        source_obj = self._source_object(context)
        if source_obj is None:
            return

        full_path = self._edge_path_between(
            source_obj,
            self._effective_path_anchor(source_obj),
            self._hovered_edge_index,
        )
        if not full_path:
            return

        existing = set(self._pending_edge_indices)
        new_edges = [edge_index for edge_index in full_path if edge_index not in existing]
        if not new_edges:
            new_edges = [self._hovered_edge_index]

        path_key = tuple(full_path)
        if self._shift_path_key != path_key:
            self._shift_path_key = path_key
            self._shift_span_edges = float(len(new_edges))

        self._shift_span_edges = max(
            0.05,
            min(float(len(new_edges)), float(self._shift_span_edges)),
        )
        full_count = int(self._shift_span_edges)
        remainder = self._shift_span_edges - full_count
        if remainder <= EPSILON:
            included_count = max(1, full_count)
            terminal_fraction = 1.0
        else:
            included_count = min(len(new_edges), full_count + 1)
            terminal_fraction = remainder

        included_new = new_edges[:included_count]
        terminal_edge_index = included_new[-1]
        self._shift_terminal_edge_index = terminal_edge_index
        self._shift_fraction = terminal_fraction

        terminal_position = full_path.index(terminal_edge_index)
        included_path = full_path[:terminal_position + 1]
        self._shift_connection_path = list(included_path)
        self._shift_preview_edge_indices = list(included_new)

        full_preview_edges = list(included_new)
        if terminal_fraction < 1.0 - EPSILON:
            full_preview_edges = full_preview_edges[:-1]
        points = list(self._edge_world_segments(source_obj, full_preview_edges))
        partial_target = self._shift_partial_target_segment(
            source_obj,
            included_path,
            terminal_edge_index,
            terminal_fraction,
        )
        if partial_target is not None and terminal_fraction < 1.0 - EPSILON:
            points.extend(partial_target)
        self._shift_preview_edge_points = tuple(points)

    def _build_width_preview_ribbon(self, context, segment_points, width):
        if (
            not segment_points
            or len(segment_points) < 2
            or context.space_data is None
            or context.space_data.region_3d is None
        ):
            return [], []

        region_3d = context.space_data.region_3d
        view_direction = region_3d.view_rotation @ Vector((0.0, 0.0, -1.0))
        if view_direction.length_squared <= EPSILON:
            view_direction = Vector((0.0, 0.0, -1.0))
        else:
            view_direction.normalize()

        half_width = max(0.0, float(width))
        triangles = []
        outlines = []

        for index in range(0, len(segment_points) - 1, 2):
            point_a = Vector(segment_points[index])
            point_b = Vector(segment_points[index + 1])
            direction = point_b - point_a
            if direction.length_squared <= EPSILON:
                continue
            direction.normalize()

            side = direction.cross(view_direction)
            if side.length_squared <= EPSILON:
                fallback = Vector((0.0, 0.0, 1.0))
                side = direction.cross(fallback)
                if side.length_squared <= EPSILON:
                    fallback = Vector((0.0, 1.0, 0.0))
                    side = direction.cross(fallback)
            if side.length_squared <= EPSILON:
                continue
            side.normalize()
            side *= half_width

            left_a = point_a + side
            left_b = point_b + side
            right_a = point_a - side
            right_b = point_b - side

            triangles.extend((
                left_a, left_b, right_b,
                left_a, right_b, right_a,
            ))
            outlines.extend((
                left_a, left_b,
                right_a, right_b,
            ))

        return triangles, outlines

    def _draw_width_preview(self, context, shader, segment_points, width, fill_color, line_color):
        triangles, outlines = self._build_width_preview_ribbon(
            context,
            segment_points,
            width,
        )
        if triangles:
            shader.uniform_float("color", fill_color)
            batch_for_shader(shader, "TRIS", {"pos": triangles}).draw(shader)
        if outlines:
            gpu.state.line_width_set(2.0)
            shader.uniform_float("color", line_color)
            batch_for_shader(shader, "LINES", {"pos": outlines}).draw(shader)



    def _screen_distance_to_segment(self, point, a, b):
        distance, _factor = self._screen_distance_and_factor_to_segment(
            point,
            a,
            b,
        )
        return distance

    def _screen_distance_and_factor_to_segment(self, point, a, b):
        point = Vector(point)
        a = Vector(a)
        b = Vector(b)
        segment = b - a
        length_sq = segment.length_squared
        if length_sq <= EPSILON:
            return (point - a).length, 0.0
        factor = max(
            0.0,
            min(1.0, (point - a).dot(segment) / length_sq),
        )
        closest = a + segment * factor
        return (point - closest).length, factor

    def _world_factor_from_screen_factor(
        self,
        region_3d,
        world_a,
        world_b,
        screen_factor,
    ):
        """Convert projected segment interpolation to its 3D edge parameter.

        Perspective projection preserves a straight line but not the linear
        parameter along it.  Reusing a screen-space factor with ``Vector.lerp``
        therefore produces a world point that is not under the tested screen
        point.  That mismatch is especially noticeable on recessed edges, where
        the visibility ray can hit a neighboring crevice face first.
        """
        screen_factor = max(0.0, min(1.0, float(screen_factor)))
        if region_3d is None:
            return screen_factor

        clip_a = region_3d.perspective_matrix @ world_a.to_4d()
        clip_b = region_3d.perspective_matrix @ world_b.to_4d()
        denominator = (
            (1.0 - screen_factor) * clip_b.w
            + screen_factor * clip_a.w
        )
        if abs(denominator) <= EPSILON:
            return screen_factor

        world_factor = screen_factor * clip_a.w / denominator
        return max(0.0, min(1.0, float(world_factor)))

    def _source_point_is_view_visible(
        self,
        context,
        source_obj,
        world_point,
        screen_point,
    ):
        region = context.region
        space_data = context.space_data
        if (
            source_obj is None
            or region is None
            or space_data is None
            or space_data.region_3d is None
        ):
            return True

        region_3d = space_data.region_3d
        ray_origin = view3d_utils.region_2d_to_origin_3d(
            region,
            region_3d,
            screen_point,
        )
        ray_direction = view3d_utils.region_2d_to_vector_3d(
            region,
            region_3d,
            screen_point,
        )
        target_distance = (world_point - ray_origin).dot(ray_direction)
        if target_distance <= EPSILON:
            return True

        depsgraph = context.evaluated_depsgraph_get()
        eval_obj = source_obj.evaluated_get(depsgraph)
        inverse_world = eval_obj.matrix_world.inverted_safe()
        local_origin = inverse_world @ ray_origin
        local_target = inverse_world @ world_point
        local_direction = local_target - local_origin
        local_distance = local_direction.length
        if local_distance <= EPSILON:
            return True

        local_direction.normalize()
        hit, local_hit, _normal, _face_index = eval_obj.ray_cast(
            local_origin,
            local_direction,
            distance=local_distance + 0.01,
        )
        if not hit:
            return True

        world_hit = eval_obj.matrix_world @ local_hit
        hit_distance = (world_hit - ray_origin).dot(ray_direction)
        tolerance = max(0.002, min(0.05, target_distance * 0.002))
        return hit_distance + tolerance >= target_distance

    def _interactive_help_shortcuts(self):
        taper_state = "ON" if self._endpoint_taper_enabled else "OFF"
        merge_state = "ON" if self._auto_merge_enabled else "OFF"
        return [
            ("LMB", "Add / edit edge"),
            ("Shift + LMB", "Shortest path / join partial"),
            ("Shift + Wheel", "Shortest path length"),
            ("Ctrl + LMB", "Partial edge (standalone)"),
            ("Ctrl + Wheel", "Partial length"),
            ("Alt", "Topology edge loop"),
            ("E", f"Endpoint taper ({taper_state})"),
            ("F", f"Auto-merge neighbor ({merge_state})"),
            ("R + LMB", "Remove edge"),
            ("R + Double LMB", "Remove connected edges"),
            ("W + Wheel", "Adjust width"),
            ("Ctrl + Z", "Undo"),
            ("Del / X", "Clear pending path"),
            ("H", "Toggle this help"),
            ("RMB / Esc", "Finish"),
        ]

    def _auto_neighbor_merge_allowed(self, event):
        return bool(self._auto_merge_enabled and not event.shift)

    def _help_overlay_box_x(self, context, box_width, margin):
        sidebar_width = max(
            (
                area_region.width
                for area_region in context.area.regions
                if area_region.type == "UI"
            ),
            default=0,
        )
        # Leave a generous right-side lane for the Edge Decal sidebar even
        # when Blender reports a collapsed or overlay-style UI region.
        right_clearance = max(360.0, float(sidebar_width) + 48.0)
        return max(
            float(margin),
            float(context.region.width)
            - float(margin)
            - float(box_width)
            - right_clearance,
        )

    def _draw_interactive_mode_badge(self, context):
        """Draw a persistent viewport badge while the modal tool is running."""
        if (
            not EDGEDECAL_INTERACTIVE_RUNNING
            or context.area is None
            or context.region is None
        ):
            return

        region = context.region
        margin = 18
        top_clearance = 96
        pad_x = 26
        badge_height = 64
        font_id = 0
        label = "INTERACTIVE MODE"
        help_hint = "Press H for help"
        exit_hint = "Esc / RMB to finish"

        blf.size(font_id, 26)
        label_width, label_height = blf.dimensions(font_id, label)
        blf.size(font_id, 22)
        help_width, help_height = blf.dimensions(font_id, help_hint)
        exit_width, exit_height = blf.dimensions(font_id, exit_hint)

        dot_size = 16
        content_gap = 18
        text_gap = 32
        badge_width = (
            pad_x * 2
            + dot_size
            + content_gap
            + label_width
            + text_gap
            + help_width
            + text_gap
            + exit_width
        )
        badge_x = max(margin, (float(region.width) - badge_width) * 0.5)
        badge_y = max(
            margin,
            float(region.height) - top_clearance - badge_height,
        )

        shader = gpu.shader.from_builtin("UNIFORM_COLOR")
        gpu.state.blend_set("ALPHA")
        vertices = (
            (badge_x, badge_y),
            (badge_x + badge_width, badge_y),
            (badge_x + badge_width, badge_y + badge_height),
            (badge_x, badge_y + badge_height),
        )
        indices = ((0, 1, 2), (0, 2, 3))
        shader.bind()
        shader.uniform_float("color", (0.055, 0.07, 0.08, 0.92))
        batch_for_shader(shader, "TRIS", {"pos": vertices}, indices=indices).draw(
            shader
        )

        shader.uniform_float("color", (0.30, 0.68, 0.95, 0.90))
        gpu.state.line_width_set(2.0)
        border = (
            (badge_x, badge_y),
            (badge_x + badge_width, badge_y),
            (badge_x + badge_width, badge_y + badge_height),
            (badge_x, badge_y + badge_height),
            (badge_x, badge_y),
        )
        batch_for_shader(shader, "LINE_STRIP", {"pos": border}).draw(shader)
        gpu.state.line_width_set(1.0)

        dot_x = badge_x + pad_x
        dot_y = badge_y + (badge_height - dot_size) * 0.5
        dot_vertices = (
            (dot_x, dot_y),
            (dot_x + dot_size, dot_y),
            (dot_x + dot_size, dot_y + dot_size),
            (dot_x, dot_y + dot_size),
        )
        shader.uniform_float("color", (0.25, 0.72, 1.0, 1.0))
        batch_for_shader(
            shader,
            "TRIS",
            {"pos": dot_vertices},
            indices=indices,
        ).draw(shader)

        label_x = dot_x + dot_size + content_gap
        blf.size(font_id, 26)
        blf.position(
            font_id,
            label_x,
            badge_y + (badge_height - label_height) * 0.5,
            0,
        )
        blf.color(font_id, 0.45, 0.85, 1.0, 1.0)
        blf.draw(font_id, label)

        blf.size(font_id, 22)
        help_x = label_x + label_width + text_gap
        blf.position(
            font_id,
            help_x,
            badge_y + (badge_height - help_height) * 0.5,
            0,
        )
        blf.color(font_id, 0.45, 0.85, 1.0, 1.0)
        blf.draw(font_id, help_hint)

        blf.position(
            font_id,
            help_x + help_width + text_gap,
            badge_y + (badge_height - exit_height) * 0.5,
            0,
        )
        blf.color(font_id, 0.72, 0.76, 0.80, 1.0)
        blf.draw(font_id, exit_hint)
        gpu.state.blend_set("NONE")

    def _draw_help_overlay(self, context):
        if context.area is None:
            return

        self._draw_interactive_mode_badge(context)
        if not self._show_help_overlay:
            return

        region = context.region
        margin = 24
        pad_x = 18
        pad_y = 15
        line_height = 24
        header_gap = 9
        column_gap = 27
        font_id = 0
        blf.size(font_id, 18)

        header = "Interactive Edge Decals (H)"
        shortcuts = self._interactive_help_shortcuts()

        header_width, _ = blf.dimensions(font_id, header)
        key_width = max(
            (blf.dimensions(font_id, key_text)[0] for key_text, _ in shortcuts),
            default=0.0,
        )
        desc_width = max(
            (blf.dimensions(font_id, desc_text)[0] for _, desc_text in shortcuts),
            default=0.0,
        )

        box_width = pad_x * 2 + key_width + column_gap + desc_width
        box_width = max(box_width, header_width + pad_x * 2, 390.0)
        box_height = (
            pad_y * 2
            + line_height
            + header_gap
            + line_height * len(shortcuts)
        )

        # Keep the help card left of the Edge Decal sidebar instead of docking
        # it beneath the right-side UI.
        box_x = self._help_overlay_box_x(context, box_width, margin)
        box_y = margin

        shader = gpu.shader.from_builtin("UNIFORM_COLOR")
        gpu.state.blend_set("ALPHA")
        vertices = (
            (box_x, box_y),
            (box_x + box_width, box_y),
            (box_x + box_width, box_y + box_height),
            (box_x, box_y + box_height),
        )
        indices = ((0, 1, 2), (0, 2, 3))
        shader.bind()
        shader.uniform_float("color", (0.08, 0.08, 0.10, 0.88))
        batch_for_shader(shader, "TRIS", {"pos": vertices}, indices=indices).draw(
            shader
        )
        shader.uniform_float("color", (0.30, 0.68, 0.95, 0.45))
        border = (
            (box_x, box_y),
            (box_x + box_width, box_y),
            (box_x + box_width, box_y + box_height),
            (box_x, box_y + box_height),
            (box_x, box_y),
        )
        batch_for_shader(shader, "LINE_STRIP", {"pos": border}).draw(shader)

        text_top = box_y + box_height - pad_y
        blf.position(font_id, box_x + pad_x, text_top - line_height, 0)
        blf.color(font_id, 0.45, 0.92, 1.0, 1.0)
        blf.draw(font_id, header)

        key_x = box_x + pad_x
        desc_x = key_x + key_width + column_gap
        first_row_y = text_top - line_height - header_gap - line_height

        for row_index, (key_text, desc_text) in enumerate(shortcuts):
            row_y = first_row_y - row_index * line_height
            blf.position(font_id, key_x, row_y, 0)
            blf.color(font_id, 0.72, 0.82, 0.95, 1.0)
            blf.draw(font_id, key_text)
            blf.position(font_id, desc_x, row_y, 0)
            blf.color(font_id, 0.92, 0.92, 0.92, 1.0)
            blf.draw(font_id, desc_text)

        gpu.state.blend_set("NONE")

    def _draw_overlay(self, context):
        if context.area is None or context.area.type != "VIEW_3D":
            return

        shader = gpu.shader.from_builtin("UNIFORM_COLOR")
        gpu.state.blend_set("ALPHA")
        gpu.state.depth_test_set("NONE")

        settings = context.scene.edge_decal_settings
        preview_width = resolve_interactive_preview_width(
            self._interactive_face_width,
            bool(settings.relative_face_width),
            self._interactive_width_reference_size,
        )

        # Keep the connected-stroke data internally, but only show the
        # magenta existing-path overlay while Shift is held. This prevents a
        # generated edge from staying purple after a normal click.
        if self._pending_edge_points and self._shift_down:
            self._draw_width_preview(
                context,
                shader,
                self._pending_edge_points,
                preview_width,
                (1.0, 0.15, 0.75, 0.08),
                (1.0, 0.4, 0.9, 0.30),
            )
            gpu.state.line_width_set(4.0)
            shader.uniform_float("color", (1.0, 0.15, 0.75, 0.95))
            batch_for_shader(
                shader,
                "LINES",
                {"pos": self._pending_edge_points},
            ).draw(shader)

            gpu.state.point_size_set(7.0)
            shader.uniform_float("color", (1.0, 0.45, 0.9, 1.0))
            batch_for_shader(
                shader,
                "POINTS",
                {"pos": self._pending_edge_points},
            ).draw(shader)

        if self._shift_preview_edge_points and not self._suppress_hover_until_mousemove:
            self._draw_width_preview(
                context,
                shader,
                self._shift_preview_edge_points,
                preview_width,
                (0.25, 1.0, 0.2, 0.10),
                (0.45, 1.0, 0.35, 0.45),
            )
            gpu.state.line_width_set(7.0)
            shader.uniform_float("color", (0.25, 1.0, 0.2, 1.0))
            batch_for_shader(
                shader,
                "LINES",
                {"pos": self._shift_preview_edge_points},
            ).draw(shader)

            gpu.state.point_size_set(10.0)
            shader.uniform_float("color", (0.65, 1.0, 0.35, 1.0))
            batch_for_shader(
                shader,
                "POINTS",
                {"pos": self._shift_preview_edge_points},
            ).draw(shader)

        if self._ctrl_down and self._ctrl_control_points:
            inactive_points = [
                point for index, point in enumerate(self._ctrl_control_points)
                if index != self._ctrl_active_point
            ]
            active_points = (
                [self._ctrl_control_points[self._ctrl_active_point]]
                if 0 <= self._ctrl_active_point < len(self._ctrl_control_points)
                else []
            )

            if inactive_points:
                gpu.state.point_size_set(12.0)
                shader.uniform_float("color", (0.7, 0.25, 1.0, 0.95))
                batch_for_shader(shader, "POINTS", {"pos": inactive_points}).draw(shader)

            if active_points:
                gpu.state.point_size_set(18.0)
                shader.uniform_float("color", (1.0, 0.85, 0.15, 1.0))
                batch_for_shader(shader, "POINTS", {"pos": active_points}).draw(shader)

        if self._hovered_edge_points and not self._suppress_hover_until_mousemove:
            hover_fill = (
                (0.75, 0.25, 1.0, 0.10)
                if self._ctrl_down and self._ctrl_slice_interval is not None
                else (0.1, 0.85, 1.0, 0.10)
                if self._alt_down
                else (1.0, 0.55, 0.05, 0.10)
            )
            hover_line = (
                (0.85, 0.45, 1.0, 0.45)
                if self._ctrl_down and self._ctrl_slice_interval is not None
                else (0.25, 0.9, 1.0, 0.45)
                if self._alt_down
                else (1.0, 0.75, 0.2, 0.45)
            )
            self._draw_width_preview(
                context,
                shader,
                self._hovered_edge_points,
                preview_width,
                hover_fill,
                hover_line,
            )
            gpu.state.line_width_set(6.0)
            shader.uniform_float(
                "color",
                (
                    (0.75, 0.25, 1.0, 1.0)
                    if self._ctrl_down and self._ctrl_slice_interval is not None
                    else (0.1, 0.85, 1.0, 1.0)
                    if self._alt_down
                    else (1.0, 0.55, 0.05, 1.0)
                ),
            )
            batch_for_shader(
                shader,
                "LINES",
                {"pos": self._hovered_edge_points},
            ).draw(shader)

            gpu.state.point_size_set(9.0)
            shader.uniform_float("color", (1.0, 0.9, 0.2, 1.0))
            batch_for_shader(
                shader,
                "POINTS",
                {"pos": self._hovered_edge_points},
            ).draw(shader)

        gpu.state.point_size_set(1.0)
        gpu.state.line_width_set(1.0)
        gpu.state.depth_test_set("NONE")
        gpu.state.blend_set("NONE")

    def _draw_remove_overlay(self, context):
        return

        shader = gpu.shader.from_builtin("UNIFORM_COLOR")
        gpu.state.blend_set("ALPHA")
        for component_index, point_2d in self._project_remove_targets(context):
            hovered = component_index == self._hovered_remove_index
            self._draw_remove_target(
                shader,
                point_2d,
                self._remove_target_radius + (3.0 if hovered else 0.0),
                (1.0, 0.75, 0.05, 1.0) if hovered else (1.0, 0.02, 0.02, 0.95),
                5.0 if hovered else 4.0,
            )
        gpu.state.line_width_set(1.0)
        gpu.state.blend_set("NONE")

    def _remove_stroke_source_indices(self, object_name, edge_indices):
        """Remove a replaced interactive stroke from the master's regeneration data."""
        obj = bpy.data.objects.get(object_name) if object_name else None
        if obj is None or not obj.get("edge_decal_generated"):
            return

        data = obj.edge_decal_object_settings
        if not data.initialized:
            return

        removed = set(edge_indices or [])
        remaining = [
            index for index in parsed_source_indices(data)
            if index not in removed
        ]
        set_stored_source_indices(obj, remaining)

    def _remove_master_vertices(self, object_name, vertex_indices):
        obj = bpy.data.objects.get(object_name) if object_name else None
        if obj is None or obj.type != "MESH" or not vertex_indices:
            return False

        bm = bmesh.new()
        try:
            bm.from_mesh(obj.data)
            bm.verts.ensure_lookup_table()
            vertices = [
                bm.verts[index]
                for index in vertex_indices
                if 0 <= index < len(bm.verts)
            ]
            if not vertices:
                return False
            bmesh.ops.delete(bm, geom=vertices, context="VERTS")
            bm.to_mesh(obj.data)
            obj.data.update(calc_edges=True)
        finally:
            bm.free()
        return True

    def _load_interactive_strokes(self, object_name):
        obj = bpy.data.objects.get(object_name) if object_name else None
        if obj is None:
            return []

        raw = obj.get("edge_decal_interactive_strokes", "[]")
        if isinstance(raw, (list, tuple)):
            data = raw
        else:
            try:
                data = json.loads(raw)
            except Exception:
                data = []

        strokes = []
        for entry in data:
            if not isinstance(entry, dict):
                continue
            try:
                edges = sorted(set(int(index) for index in entry.get("edges", [])))
                vertices = sorted(set(int(index) for index in entry.get("vertices", [])))
            except Exception:
                continue
            if not edges:
                continue
            interval = entry.get("slice_interval")
            if not (isinstance(interval, (list, tuple)) and len(interval) == 2):
                interval = None
            edge_local_interval = entry.get("edge_local_slice_interval")
            if not (
                isinstance(edge_local_interval, (list, tuple))
                and len(edge_local_interval) == 2
            ):
                edge_local_interval = None
            try:
                edge_local_edge_index = int(
                    entry.get("edge_local_slice_edge_index", -1)
                )
            except (TypeError, ValueError):
                edge_local_edge_index = -1
            if edge_local_edge_index not in edges:
                edge_local_edge_index = edges[0] if len(edges) == 1 else -1
            slice_space = str(entry.get("slice_space", "edge_local"))
            source_name = obj.get("edge_decal_source")
            source_obj = (
                bpy.data.objects.get(source_name)
                if source_name
                else None
            )
            if (
                edge_local_interval is None
                and interval is not None
                and source_obj is not None
                and len(edges) == 1
            ):
                if slice_space != "chain":
                    edge_local_interval = list(interval)
                else:
                    edge_local_interval = self._chain_interval_to_edge_local(
                        source_obj,
                        edges[0],
                        interval,
                    )
            if (
                interval is not None
                and slice_space != "chain"
                and source_obj is not None
                and len(edges) == 1
            ):
                converted = self._edge_local_slice_to_chain_interval(
                    source_obj,
                    edges[0],
                    interval,
                )
                if converted is not None:
                    interval = list(converted)
                    slice_space = "chain"
            try:
                stroke_face_width = float(entry.get("face_width", 0.0))
            except (TypeError, ValueError):
                stroke_face_width = 0.0
            try:
                taper_vertices = sorted(
                    set(int(index) for index in entry.get("taper_vertices", []))
                )
            except Exception:
                taper_vertices = []
            try:
                merge_open_vertices = sorted(
                    set(int(index) for index in entry.get("merge_open_vertices", []))
                )
            except Exception:
                merge_open_vertices = []
            try:
                merge_tip_vertices = sorted(
                    set(int(index) for index in entry.get("merge_tip_vertices", []))
                )
            except Exception:
                merge_tip_vertices = []
            stroke_record = {
                "id": str(entry.get("id", "")),
                "edges": edges,
                "vertices": vertices,
                "force_connected": bool(entry.get("force_connected", False)),
                "slice_interval": interval,
                "slice_space": slice_space if interval is not None else None,
                "edge_local_slice_interval": (
                    list(edge_local_interval)
                    if edge_local_interval is not None
                    else None
                ),
                "edge_local_slice_edge_index": edge_local_edge_index,
                "face_width": stroke_face_width,
                "taper_vertices": taper_vertices,
                "merge_open_vertices": merge_open_vertices,
                "merge_tip_vertices": merge_tip_vertices,
            }
            if source_obj is not None and not merge_open_vertices and not merge_tip_vertices:
                open_corners, tip_corners = self._rebuild_merge_corners_for_stroke(
                    source_obj,
                    stroke_record,
                )
                stroke_record["merge_open_vertices"] = sorted(open_corners)
                stroke_record["merge_tip_vertices"] = sorted(tip_corners)
            strokes.append(stroke_record)
        return strokes

    def _save_interactive_strokes(self, object_name, strokes):
        obj = bpy.data.objects.get(object_name) if object_name else None
        if obj is None:
            return
        serialized = []
        for index, stroke in enumerate(strokes or []):
            serialized.append({
                "id": str(stroke.get("id", index)),
                "edges": sorted(set(int(value) for value in stroke.get("edges", []))),
                "vertices": sorted(set(int(value) for value in stroke.get("vertices", []))),
                "force_connected": bool(stroke.get("force_connected", False)),
                "slice_interval": stroke.get("slice_interval"),
                "slice_space": (
                    stroke.get("slice_space")
                    if stroke.get("slice_interval") is not None
                    else None
                ),
                "edge_local_slice_interval": stroke.get("edge_local_slice_interval"),
                "edge_local_slice_edge_index": int(
                    stroke.get("edge_local_slice_edge_index", -1)
                ),
                "face_width": float(stroke.get("face_width", 0.0) or 0.0),
                "taper_vertices": sorted(
                    set(int(value) for value in stroke.get("taper_vertices", []) or [])
                ),
                "merge_open_vertices": sorted(
                    set(int(value) for value in stroke.get("merge_open_vertices", []) or [])
                ),
                "merge_tip_vertices": sorted(
                    set(int(value) for value in stroke.get("merge_tip_vertices", []) or [])
                ),
            })
        obj["edge_decal_interactive_strokes"] = json.dumps(serialized)

    def _register_interactive_stroke(
        self, object_name, edge_indices, vertex_indices,
        force_connected=False, slice_interval=None, face_width=None,
        taper_vertices=None, edge_local_slice_interval=None,
        edge_local_slice_edge_index=None,
        preserve_stroke_ids=None,
        merge_open_vertices=None, merge_tip_vertices=None,
    ):
        obj = bpy.data.objects.get(object_name) if object_name else None
        if obj is None:
            return
        source_obj = self._source_object(bpy.context)
        if (
            merge_open_vertices is None
            and merge_tip_vertices is None
            and source_obj is not None
        ):
            if (
                edge_local_slice_interval is not None
                and len(edge_indices or []) == 1
            ):
                merge_open_vertices, merge_tip_vertices = (
                    self._partial_merge_corners_from_edge(
                        source_obj,
                        int(edge_indices[0]),
                        edge_local_slice_interval,
                    )
                )
            elif slice_interval is None:
                merge_open_vertices, merge_tip_vertices = (
                    self._full_stroke_merge_corners(
                        source_obj,
                        edge_indices,
                        taper_vertices,
                    )
                )
            else:
                merge_open_vertices, merge_tip_vertices = (
                    self._rebuild_merge_corners_for_stroke(
                        source_obj,
                        {
                            "edges": edge_indices or [],
                            "slice_interval": list(slice_interval),
                            "slice_space": "chain",
                            "taper_vertices": taper_vertices or [],
                        },
                    )
                )
        strokes = self._load_interactive_strokes(object_name)
        new_edge_set = {int(index) for index in edge_indices or []}
        preserved_ids = {
            str(value) for value in (preserve_stroke_ids or [])
        }
        if new_edge_set:
            strokes = [
                stroke
                for stroke in strokes
                if not (
                    {int(index) for index in stroke.get("edges", [])}
                    & new_edge_set
                    and str(stroke.get("id", "")) not in preserved_ids
                    and not self._partial_strokes_can_share_source_edge(
                        stroke,
                        new_edge_set,
                        edge_local_slice_interval,
                        source_obj=source_obj,
                    )
                )
            ]
        next_id = max([int(stroke.get("id", 0) or 0) for stroke in strokes] + [0]) + 1
        strokes.append({
            "id": str(next_id),
            "edges": sorted(set(int(index) for index in edge_indices or [])),
            "vertices": sorted(set(int(index) for index in vertex_indices or [])),
            "force_connected": bool(force_connected),
            "slice_interval": list(slice_interval) if slice_interval is not None else None,
            "slice_space": "chain" if slice_interval is not None else None,
            "edge_local_slice_interval": (
                list(edge_local_slice_interval)
                if edge_local_slice_interval is not None
                else None
            ),
            "edge_local_slice_edge_index": (
                int(edge_local_slice_edge_index)
                if edge_local_slice_edge_index is not None
                else (
                    int(edge_indices[0])
                    if edge_local_slice_interval is not None
                    and len(edge_indices or []) == 1
                    else -1
                )
            ),
            "face_width": float(
                self._interactive_face_width
                if face_width is None
                else face_width
            ),
            "taper_vertices": sorted(
                set(int(index) for index in (taper_vertices or []))
            ),
            "merge_open_vertices": sorted(
                set(int(index) for index in (merge_open_vertices or []))
            ),
            "merge_tip_vertices": sorted(
                set(int(index) for index in (merge_tip_vertices or []))
            ),
        })
        self._save_interactive_strokes(object_name, strokes)

        if edge_indices:
            append_stored_source_indices(obj, edge_indices)
            if "edge_decal_base_source_indices" not in obj:
                obj["edge_decal_base_source_indices"] = ""

    def _remove_interactive_stroke_record(
        self,
        object_name,
        edge_indices=None,
        vertex_indices=None,
        stroke_id=None,
    ):
        strokes = self._load_interactive_strokes(object_name)
        remaining = []
        edge_set = set(int(index) for index in (edge_indices or []))
        vertex_set = set(int(index) for index in (vertex_indices or []))
        for stroke in strokes:
            matches = False
            if stroke_id is not None and str(stroke.get("id", "")) == str(stroke_id):
                matches = True
            elif edge_set and set(stroke.get("edges", [])) == edge_set:
                matches = True
            elif vertex_set and set(stroke.get("vertices", [])) == vertex_set:
                matches = True
            if not matches:
                remaining.append(stroke)
        self._save_interactive_strokes(object_name, remaining)

    def _ensure_interactive_master(self, context):
        """Resolve a valid merge master for the current source object.

        Returns the master object or None. When the tracked
        ``_interactive_layer_name`` no longer resolves to a decal belonging to
        the active source, it is refreshed from the source's active layer so
        following strokes merge into it instead of creating standalone decals.
        """
        source_obj = self._source_object(context)
        if source_obj is None:
            return None

        master = bpy.data.objects.get(self._interactive_layer_name)
        if (
            decal_layer_is_valid(master, source_obj)
            and not master.get("edge_decal_locked", False)
        ):
            return master

        stale_name = self._interactive_layer_name
        ensure_source_decal_layers_ready(source_obj, context)

        refreshed = active_decal_layer_for_source(source_obj, include_locked=False)
        if refreshed is not None:
            self._interactive_layer_name = refreshed.name_full
            self._last_generated_object_name = refreshed.name_full
            return refreshed

        self._interactive_layer_name = ""
        if self._last_generated_object_name == stale_name:
            self._last_generated_object_name = ""
        return None

    def _interactive_layer_object(self, context):
        """Return the decal layer object interactive mode is editing."""
        source_obj = self._source_object(context)
        if source_obj is None:
            return None

        layer_obj = bpy.data.objects.get(self._interactive_layer_name)
        if (
            decal_layer_is_valid(layer_obj, source_obj)
            and not layer_obj.get("edge_decal_locked", False)
        ):
            return layer_obj

        return self._ensure_interactive_master(context)

    def _edge_owner_decal_layer(self, context, edge_index):
        """Return the active layer when it owns a source edge index.

        Source-edge ownership is layer-local. The same source edge may be
        generated independently on any number of decal layers.
        """
        source_obj = self._source_object(context)
        if source_obj is None:
            return None

        target_index = int(edge_index)
        decal_obj = self._interactive_layer_object(context)
        if not decal_layer_is_valid(decal_obj, source_obj):
            return None
        data = getattr(decal_obj, "edge_decal_object_settings", None)
        if data is not None and target_index in set(parsed_source_indices(data)):
            return decal_obj

        for stroke in self._load_interactive_strokes(decal_obj.name_full):
            if target_index in {int(index) for index in stroke.get("edges", [])}:
                return decal_obj
        return None

    def _edge_belongs_to_other_layer(self, context, edge_index):
        owner = self._edge_owner_decal_layer(context, edge_index)
        if owner is None:
            return False

        active = self._interactive_layer_object(context)
        if active is None:
            return False

        return owner.name_full != active.name_full

    def _other_layer_label(self, decal_obj):
        if decal_obj is None:
            return "another layer"
        return str(
            decal_obj.get(
                "edge_decal_layer_name",
                decal_obj.name,
            )
        )

    def _iter_interactive_stroke_records(self, context):
        """Yield interactive strokes on the active decal layer only."""
        layer_obj = self._interactive_layer_object(context)
        if layer_obj is None:
            return

        for stroke in self._load_interactive_strokes(layer_obj.name_full):
            yield layer_obj, stroke

    def _stroke_is_partial_slice(self, stroke):
        """True when a stroke record represents a sliced/partial edge placement."""
        if stroke.get("edge_local_slice_interval") is not None:
            return True
        return (
            self._normalized_slice_interval(stroke.get("slice_interval"))
            is not None
        )

    def _iter_neighbor_strokes_for_merge(self, context, clicked_edge_indices):
        """Yield strokes that do not cover the edge(s) being placed now."""
        clicked = {int(index) for index in (clicked_edge_indices or [])}
        for decal_obj, stroke in self._iter_interactive_stroke_records(context):
            stroke_edges = {
                int(index) for index in stroke.get("edges", [])
            }
            if clicked and stroke_edges & clicked:
                continue
            yield decal_obj, stroke

    def _open_endpoint_vertices_for_edges(self, source_obj, edge_indices):
        """Return open-chain endpoint vertex indices for a source edge set."""
        if not edge_indices:
            return set()

        bm, owns_bm = self._open_bmesh_for_read(source_obj)
        try:
            edges = [
                bm.edges[int(index)]
                for index in edge_indices
                if 0 <= int(index) < len(bm.edges)
            ]
            if not edges:
                return set()

            chains = extract_edge_chains(edges, source_obj.matrix_world)
            endpoints = set()
            for chain_verts, _chain_edges, closed in chains:
                if closed or len(chain_verts) < 2:
                    continue
                endpoints.add(chain_verts[0].index)
                endpoints.add(chain_verts[-1].index)
            return endpoints
        finally:
            if owns_bm:
                bm.free()

    def _vertex_candidates_at_chain_fraction(
        self,
        chain_verts,
        chain_edges,
        world_matrix,
        fraction,
    ):
        """Return source vertex indices at one normalized position on a chain."""
        world_points = [world_matrix @ vert.co for vert in chain_verts]
        edge_lengths = [
            (world_points[index + 1] - world_points[index]).length
            for index in range(len(chain_edges))
        ]
        total_length = sum(edge_lengths)
        if total_length <= EPSILON:
            return {chain_verts[0].index}

        distance_along = max(0.0, min(1.0, float(fraction))) * total_length
        distance_remaining = distance_along

        for edge_index, edge_length in enumerate(edge_lengths):
            if distance_remaining <= edge_length + EPSILON:
                if edge_length <= EPSILON:
                    factor = 0.0
                else:
                    factor = distance_remaining / edge_length

                if factor <= EPSILON:
                    return {chain_verts[edge_index].index}
                if factor >= 1.0 - EPSILON:
                    return {chain_verts[edge_index + 1].index}
                return {
                    chain_verts[edge_index].index,
                    chain_verts[edge_index + 1].index,
                }
            distance_remaining -= edge_length

        return {chain_verts[-1].index}

    def _slice_boundary_vertices(
        self,
        chain_verts,
        chain_edges,
        world_matrix,
        fraction,
        toward_start,
    ):
        """Vertices on the retained side of one slice boundary."""
        world_points = [world_matrix @ vert.co for vert in chain_verts]
        edge_lengths = [
            (world_points[index + 1] - world_points[index]).length
            for index in range(len(chain_edges))
        ]
        total_length = sum(edge_lengths)
        if total_length <= EPSILON:
            return {chain_verts[0].index}

        distance_along = max(0.0, min(1.0, float(fraction))) * total_length
        distance_remaining = distance_along

        for edge_index, edge_length in enumerate(edge_lengths):
            if distance_remaining <= edge_length + EPSILON:
                if edge_length <= EPSILON:
                    return {chain_verts[edge_index].index}

                factor = distance_remaining / edge_length
                if factor <= EPSILON:
                    return {chain_verts[edge_index].index}
                if factor >= 1.0 - EPSILON:
                    return {chain_verts[edge_index + 1].index}

                if toward_start:
                    return {chain_verts[edge_index].index}
                return {chain_verts[edge_index + 1].index}

            distance_remaining -= edge_length

        return {chain_verts[-1].index}

    def _stroke_connectable_vertices(self, source_obj, stroke):
        """Vertices where an existing stroke may be extended or joined.

        Partial strokes expose mesh corners on open sides and slice-boundary
        vertices on trimmed sides. Stored slice intervals are chain-relative.
        """
        stroke_edges = [int(index) for index in stroke.get("edges", [])]
        if not stroke_edges:
            return set()

        slice_interval = self._normalized_slice_interval(
            stroke.get("slice_interval")
        )

        bm, owns_bm = self._open_bmesh_for_read(source_obj)
        try:
            edges = [
                bm.edges[index]
                for index in stroke_edges
                if 0 <= index < len(bm.edges)
            ]
            if not edges:
                return set()

            world_matrix = source_obj.matrix_world
            chains = extract_edge_chains(edges, world_matrix)
            connectable = set()

            for chain_verts, chain_edges, closed in chains:
                if closed or len(chain_verts) < 2:
                    continue

                if slice_interval is not None:
                    start_fraction, end_fraction = slice_interval
                    start_trimmed = start_fraction > EPSILON
                    end_trimmed = end_fraction < 1.0 - EPSILON

                    if start_trimmed:
                        connectable.update(
                            self._slice_boundary_vertices(
                                chain_verts,
                                chain_edges,
                                world_matrix,
                                start_fraction,
                                toward_start=True,
                            )
                        )
                    else:
                        connectable.add(chain_verts[0].index)

                    if end_trimmed:
                        connectable.update(
                            self._slice_boundary_vertices(
                                chain_verts,
                                chain_edges,
                                world_matrix,
                                end_fraction,
                                toward_start=False,
                            )
                        )
                    else:
                        connectable.add(chain_verts[-1].index)
                else:
                    connectable.add(chain_verts[0].index)
                    connectable.add(chain_verts[-1].index)

            return connectable
        finally:
            if owns_bm:
                bm.free()

    def _stroke_connectable_vertices_near(
        self,
        source_obj,
        stroke,
        new_edge_indices,
    ):
        """Filter connectable vertices to the side nearest the hovered click."""
        connectable = self._stroke_connectable_vertices(source_obj, stroke)
        if not connectable:
            return set()

        new_endpoints = self._open_endpoint_vertices_for_edges(
            source_obj,
            new_edge_indices,
        )
        if not new_endpoints:
            return connectable

        bm, owns_bm = self._open_bmesh_for_read(source_obj)
        try:
            world_matrix = source_obj.matrix_world
            target_points = []
            for vertex_index in new_endpoints:
                if 0 <= vertex_index < len(bm.verts):
                    target_points.append(
                        world_matrix @ bm.verts[vertex_index].co
                    )
            if not target_points:
                return connectable

            best_vertices = set()
            best_distance_sq = float("inf")
            for vertex_index in connectable:
                if not (0 <= vertex_index < len(bm.verts)):
                    continue
                point = world_matrix @ bm.verts[vertex_index].co
                distance_sq = min(
                    (point - target_point).length_squared
                    for target_point in target_points
                )
                if distance_sq + EPSILON < best_distance_sq:
                    best_distance_sq = distance_sq
                    best_vertices = {vertex_index}
                elif abs(distance_sq - best_distance_sq) <= EPSILON:
                    best_vertices.add(vertex_index)

            return best_vertices or connectable
        finally:
            if owns_bm:
                bm.free()

    def _sync_active_layer_from_scene(self, context):
        """Follow decal-layer UI changes while the interactive modal is running."""
        source_obj = self._source_object(context)
        if source_obj is None:
            return

        active_layer = active_decal_layer_for_source(
            source_obj,
            context=context,
        )
        if active_layer is None:
            return

        active_name = active_layer.name_full
        if active_name != self._interactive_layer_name:
            self._interactive_layer_name = active_name
            self._last_generated_object_name = active_name
            self._pending_edge_indices = []
            self._path_anchor_edge_index = -1
            self._pending_edge_points = None
            self._pending_partial_edge_index = -1
            self._pending_partial_fraction = 1.0
            self._shift_preview_edge_indices = []
            self._shift_preview_edge_points = None
            self._shift_connection_path = []
            self._last_stroke_vertex_indices = []
            sync_scene_settings_from_decal_layer(
                context,
                source_obj,
                active_layer,
            )
            self._interactive_face_width = max(
                MIN_FACE_WIDTH,
                float(context.scene.edge_decal_settings.face_width),
            )
        elif not self._width_drag_active:
            scene_width = max(
                MIN_FACE_WIDTH,
                float(context.scene.edge_decal_settings.face_width),
            )
            if abs(scene_width - self._interactive_face_width) > 1e-9:
                self._interactive_face_width = scene_width

    def _set_interactive_face_width(self, context, width):
        """Keep modal stroke width and sidebar Face Width aligned."""
        width = max(MIN_FACE_WIDTH, float(width))
        self._interactive_face_width = width
        global EDGEDECAL_SCENE_SETTINGS_COPYING
        EDGEDECAL_SCENE_SETTINGS_COPYING = True
        try:
            context.scene.edge_decal_settings.face_width = width
        finally:
            EDGEDECAL_SCENE_SETTINGS_COPYING = False

        source_obj = self._source_object(context)
        if source_obj is not None:
            EDGEDECAL_SCENE_LIVE_SYNC_CACHE[
                scene_live_sync_cache_key(
                    source_obj,
                    active_decal_layer_for_source(
                        source_obj,
                        context=context,
                    ),
                )
            ] = scene_live_edit_signature(context.scene.edge_decal_settings)

    def _endpoints_can_connect(
        self,
        source_obj,
        connectable,
        new_endpoints,
        stroke_edges=(),
    ):
        """True when new geometry may join an existing stroke at one open end."""
        if not connectable or not new_endpoints:
            return False
        if connectable & new_endpoints:
            return True

        stroke_edge_set = {int(index) for index in stroke_edges}
        bm, owns_bm = self._open_bmesh_for_read(source_obj)
        try:
            for vertex_index in connectable:
                if not (0 <= vertex_index < len(bm.verts)):
                    continue
                for edge in bm.verts[vertex_index].link_edges:
                    if edge.index in stroke_edge_set:
                        continue
                    for vert in edge.verts:
                        if vert.index in new_endpoints:
                            return True
            return False
        finally:
            if owns_bm:
                bm.free()

    def _endpoint_vertex_sets_touch(self, source_obj, endpoints_a, endpoints_b):
        """True when two endpoint vertex sets share a vertex or a mesh edge."""
        if not endpoints_a or not endpoints_b:
            return False
        if endpoints_a & endpoints_b:
            return True

        bm, owns_bm = self._open_bmesh_for_read(source_obj)
        try:
            other = set(endpoints_b)
            for vertex_index in endpoints_a:
                if not (0 <= vertex_index < len(bm.verts)):
                    continue
                for edge in bm.verts[vertex_index].link_edges:
                    for vert in edge.verts:
                        if vert.index in other:
                            return True
            return False
        finally:
            if owns_bm:
                bm.free()

    def _nearest_stroke_endpoint_edge(
        self,
        source_obj,
        stroke_edges,
        target_edge_index,
        connectable_vertices=None,
    ):
        """Return the stroke edge nearest to one hovered target edge."""
        if not stroke_edges:
            return -1

        stroke_set = {int(index) for index in stroke_edges}
        endpoints = set(connectable_vertices or ())
        if not endpoints:
            endpoints = self._open_endpoint_vertices_for_edges(
                source_obj,
                stroke_edges,
            )
        if not endpoints:
            return int(stroke_edges[0])

        bm, owns_bm = self._open_bmesh_for_read(source_obj)
        try:
            if not (0 <= int(target_edge_index) < len(bm.edges)):
                return int(stroke_edges[0])

            target_edge = bm.edges[int(target_edge_index)]
            world_matrix = source_obj.matrix_world
            target_mid = (
                (world_matrix @ target_edge.verts[0].co)
                + (world_matrix @ target_edge.verts[1].co)
            ) * 0.5

            best_edge = -1
            best_distance_sq = float("inf")
            for vertex_index in endpoints:
                if not (0 <= vertex_index < len(bm.verts)):
                    continue
                for edge in bm.verts[vertex_index].link_edges:
                    if edge.index not in stroke_set:
                        continue
                    edge_mid = (
                        (world_matrix @ edge.verts[0].co)
                        + (world_matrix @ edge.verts[1].co)
                    ) * 0.5
                    distance_sq = (edge_mid - target_mid).length_squared
                    if distance_sq < best_distance_sq:
                        best_distance_sq = distance_sq
                        best_edge = edge.index

            return best_edge if best_edge >= 0 else int(stroke_edges[0])
        finally:
            if owns_bm:
                bm.free()

    def _edges_share_vertex(self, source_obj, edge_index, other_edge_indices):
        """True when edge_index shares a source-mesh vertex with other_edge_indices."""
        bm, owns_bm = self._open_bmesh_for_read(source_obj)
        try:
            if not (0 <= int(edge_index) < len(bm.edges)):
                return False

            edge = bm.edges[int(edge_index)]
            edge_vertices = {vert.index for vert in edge.verts}
            for other_index in other_edge_indices:
                other_index = int(other_index)
                if not (0 <= other_index < len(bm.edges)):
                    continue
                other = bm.edges[other_index]
                if edge_vertices & {vert.index for vert in other.verts}:
                    return True
            return False
        finally:
            if owns_bm:
                bm.free()

    def _shift_partial_merge_allowed(self, context, pending_edges, connection_edges):
        """RULE 3: Shift may join partial strokes only at their open end."""
        source_obj = self._source_object(context)
        if source_obj is None:
            return True, ""

        pending_set = {int(index) for index in (pending_edges or [])}
        connect_set = {int(index) for index in (connection_edges or [])}
        if not pending_set or not connect_set:
            return True, ""

        for _decal_obj, stroke in self._iter_interactive_stroke_records(context):
            if not self._stroke_is_partial_slice(stroke):
                continue
            stroke_edges = [int(index) for index in stroke.get("edges", [])]
            if not (set(stroke_edges) & connect_set):
                continue

            shared_pending = self._shared_source_vertices(
                source_obj,
                list(pending_set),
                stroke_edges,
            )
            if not shared_pending:
                continue

            open_vertices, tip_vertices = self._stroke_merge_corners(
                source_obj,
                stroke,
            )
            if shared_pending & tip_vertices:
                return False, (
                    "Shift merge: connect at the partial open end, "
                    "not the taper tip"
                )
            if not (shared_pending & open_vertices):
                return False, (
                    "Shift merge: partial open end does not meet the pending run"
                )
        return True, ""

    def _plan_auto_connect_to_pending_neighbor(
        self,
        context,
        new_edge_indices,
        edge_local_slice_interval=None,
    ):
        """Merge when the next click is on a mesh edge touching the pending run."""
        if (
            not self._pending_edge_indices
            or self._path_anchor_edge_index < 0
            or not new_edge_indices
        ):
            return None

        source_obj = self._source_object(context)
        if source_obj is None:
            return None

        hovered_edge = int(new_edge_indices[0])
        pending_edges = [int(index) for index in self._pending_edge_indices]
        if hovered_edge in pending_edges:
            return None

        if not self._edges_share_vertex(
            source_obj,
            hovered_edge,
            pending_edges,
        ):
            return None

        master = self._ensure_interactive_master(context)
        pending_stroke_ids = []
        if master is not None:
            pending_set = set(pending_edges)
            for _decal_obj, stroke in self._iter_neighbor_strokes_for_merge(
                context,
                new_edge_indices,
            ):
                stroke_edges = [
                    int(index) for index in stroke.get("edges", [])
                ]
                if not (set(stroke_edges) & pending_set):
                    continue

                if not self._merge_connection_allowed(
                    source_obj,
                    [hovered_edge],
                    stroke,
                    edge_local_slice_interval=edge_local_slice_interval,
                ):
                    return None
                pending_stroke_ids.append(str(stroke.get("id", "")))
                break

        anchor_edge = self._nearest_stroke_endpoint_edge(
            source_obj,
            pending_edges,
            hovered_edge,
        )
        if anchor_edge < 0:
            anchor_edge = int(self._path_anchor_edge_index)

        ordered = []
        seen = set()
        for edge_index in pending_edges + list(new_edge_indices):
            edge_index = int(edge_index)
            if edge_index not in seen:
                ordered.append(edge_index)
                seen.add(edge_index)

        return {
            "target_edges": ordered,
            "path": list(new_edge_indices),
            "anchor_edge": anchor_edge,
            "stroke_edges": pending_edges,
            "stroke_ids": pending_stroke_ids,
        }

    def _plan_auto_connect_to_touching_stroke(
        self,
        context,
        new_edge_indices,
        edge_local_slice_interval=None,
    ):
        """Plan a Shift-free merge when a new click touches an existing stroke."""
        if not new_edge_indices:
            return None

        source_obj = self._source_object(context)
        if source_obj is None:
            return None

        hovered_edge = int(new_edge_indices[0])
        for _decal_obj, stroke in self._iter_neighbor_strokes_for_merge(
            context,
            new_edge_indices,
        ):
            stroke_edges = [int(index) for index in stroke.get("edges", [])]
            if not stroke_edges:
                continue
            new_edges = {int(index) for index in new_edge_indices}
            if new_edges <= set(stroke_edges):
                continue

            new_endpoints = self._open_endpoint_vertices_for_edges(
                source_obj,
                new_edges,
            )
            if not new_endpoints:
                continue

            slice_interval = stroke.get("slice_interval")
            has_slice = (
                isinstance(slice_interval, (list, tuple))
                and len(slice_interval) == 2
            )
            shares_vertex = self._edges_share_vertex(
                source_obj,
                hovered_edge,
                stroke_edges,
            )

            if edge_local_slice_interval is not None and not shares_vertex:
                continue

            if not shares_vertex:
                stroke_endpoints = self._stroke_connectable_vertices(
                    source_obj,
                    stroke,
                )
                if not self._endpoints_can_connect(
                    source_obj,
                    stroke_endpoints,
                    new_endpoints,
                    stroke_edges,
                ):
                    continue

            stroke_open, _stroke_tips = self._stroke_merge_corners(
                source_obj,
                stroke,
            )
            if shares_vertex:
                shared_vertices = self._shared_source_vertices(
                    source_obj,
                    list(new_edge_indices),
                    stroke_edges,
                )
                anchor_vertices = stroke_open & shared_vertices
                if not anchor_vertices:
                    anchor_vertices = stroke_open or None
            else:
                anchor_vertices = (
                    self._stroke_connectable_vertices_near(
                        source_obj,
                        stroke,
                        list(new_edge_indices),
                    )
                    if has_slice
                    else None
                )

            anchor_edge = self._nearest_stroke_endpoint_edge(
                source_obj,
                stroke_edges,
                hovered_edge,
                connectable_vertices=anchor_vertices,
            )
            if anchor_edge < 0:
                continue

            if shares_vertex:
                if not self._merge_connection_allowed(
                    source_obj,
                    [hovered_edge],
                    stroke,
                    edge_local_slice_interval=edge_local_slice_interval,
                ):
                    continue
            elif edge_local_slice_interval is not None:
                continue

            if shares_vertex:
                ordered = []
                seen = set()
                for edge_index in stroke_edges + list(new_edge_indices):
                    edge_index = int(edge_index)
                    if edge_index not in seen:
                        ordered.append(edge_index)
                        seen.add(edge_index)
                return {
                    "target_edges": ordered,
                    "path": list(new_edge_indices),
                    "anchor_edge": anchor_edge,
                    "stroke_edges": stroke_edges,
                    "stroke_ids": [str(stroke.get("id", ""))],
                }

            path = self._edge_path_between(
                source_obj,
                anchor_edge,
                hovered_edge,
            )
            if not path:
                continue

            # Auto-connect only for a local bridge, never a long mesh detour.
            if len(path) > len(stroke_edges) + len(new_edges) + 2:
                continue

            if not self._merge_connection_allowed(
                source_obj,
                [hovered_edge],
                stroke,
                edge_local_slice_interval=edge_local_slice_interval,
            ):
                continue

            ordered = []
            seen = set()
            for edge_index in stroke_edges + path + list(new_edge_indices):
                edge_index = int(edge_index)
                if edge_index not in seen:
                    ordered.append(edge_index)
                    seen.add(edge_index)

            return {
                "target_edges": ordered,
                "path": path,
                "anchor_edge": anchor_edge,
                "stroke_edges": stroke_edges,
                "stroke_ids": [str(stroke.get("id", ""))],
            }

        return None

    def _edge_groups_touch(self, source_obj, edges_a, edges_b):
        """True when any edge in edges_a shares a source vertex with edges_b."""
        set_a = {int(index) for index in edges_a}
        set_b = {int(index) for index in edges_b}
        if not set_a or not set_b:
            return False
        if set_a & set_b:
            return True

        bm, owns_bm = self._open_bmesh_for_read(source_obj)
        try:
            bm.edges.ensure_lookup_table()
            verts_b = set()
            for index in set_b:
                if 0 <= index < len(bm.edges):
                    for vert in bm.edges[index].verts:
                        verts_b.add(vert.index)
            if not verts_b:
                return False
            for index in set_a:
                if 0 <= index < len(bm.edges):
                    for vert in bm.edges[index].verts:
                        if vert.index in verts_b:
                            return True
            return False
        finally:
            if owns_bm:
                bm.free()

    def _shared_source_vertices(self, source_obj, edges_a, edges_b):
        """Return source-mesh vertex indices shared between two edge groups."""
        set_a = {int(index) for index in edges_a}
        set_b = {int(index) for index in edges_b}
        if not set_a or not set_b:
            return set()

        bm, owns_bm = self._open_bmesh_for_read(source_obj)
        try:
            bm.edges.ensure_lookup_table()
            verts_a = set()
            for index in set_a:
                if 0 <= index < len(bm.edges):
                    for vert in bm.edges[index].verts:
                        verts_a.add(vert.index)
            verts_b = set()
            for index in set_b:
                if 0 <= index < len(bm.edges):
                    for vert in bm.edges[index].verts:
                        verts_b.add(vert.index)
            return verts_a & verts_b
        finally:
            if owns_bm:
                bm.free()

    def _normalized_slice_interval(self, slice_interval):
        if not (
            isinstance(slice_interval, (list, tuple))
            and len(slice_interval) == 2
        ):
            return None

        start_fraction = max(0.0, min(1.0, float(slice_interval[0])))
        end_fraction = max(0.0, min(1.0, float(slice_interval[1])))
        if end_fraction < start_fraction:
            start_fraction, end_fraction = end_fraction, start_fraction
        return start_fraction, end_fraction

    @staticmethod
    def _slice_intervals_overlap(first_interval, second_interval):
        """Return whether two normalized edge intervals overlap in their interiors."""
        normalized = []
        for interval in (first_interval, second_interval):
            if not (
                isinstance(interval, (list, tuple))
                and len(interval) == 2
            ):
                return True
            try:
                start = max(0.0, min(1.0, float(interval[0])))
                end = max(0.0, min(1.0, float(interval[1])))
            except (TypeError, ValueError):
                return True
            if end < start:
                start, end = end, start
            normalized.append((start, end))

        first, second = normalized
        return (
            min(first[1], second[1])
            > max(first[0], second[0]) + EPSILON
        )

    def _partial_strokes_can_share_source_edge(
        self,
        existing_stroke,
        new_edge_indices,
        new_edge_local_interval,
        source_obj=None,
    ):
        """Allow disjoint Ctrl coverage to coexist on one source edge."""
        new_edges = {int(index) for index in (new_edge_indices or [])}
        existing_edges = {
            int(index) for index in existing_stroke.get("edges", [])
        }
        if (
            len(new_edges) != 1
            or not (existing_edges & new_edges)
            or new_edge_local_interval is None
        ):
            return False

        target_edge_index = next(iter(new_edges))
        existing_interval = self._stroke_edge_local_coverage(
            source_obj,
            existing_stroke,
            target_edge_index,
        )
        if existing_interval is None:
            return False
        return not self._slice_intervals_overlap(
            existing_interval,
            new_edge_local_interval,
        )

    def _stroke_edge_local_coverage(self, source_obj, stroke, edge_index):
        """Map one stroke's actual coverage onto a source edge's local 0..1 space."""
        target_edge_index = int(edge_index)
        stroke_edges = {
            int(index) for index in stroke.get("edges", [])
        }
        if target_edge_index not in stroke_edges:
            return None

        explicit_interval = self._normalized_slice_interval(
            stroke.get("edge_local_slice_interval")
        )
        try:
            explicit_edge_index = int(
                stroke.get("edge_local_slice_edge_index", -1)
            )
        except (TypeError, ValueError):
            explicit_edge_index = -1
        if explicit_interval is not None and (
            explicit_edge_index == target_edge_index
            or len(stroke_edges) == 1
        ):
            return explicit_interval

        chain_interval = self._normalized_slice_interval(
            stroke.get("slice_interval")
        )
        if chain_interval is None:
            return 0.0, 1.0
        if source_obj is None:
            return explicit_interval

        bm, owns_bm = self._open_bmesh_for_read(source_obj)
        try:
            selected = [
                bm.edges[index]
                for index in sorted(stroke_edges)
                if 0 <= index < len(bm.edges)
            ]
            chains = extract_edge_chains(selected, source_obj.matrix_world)
            chain = next(
                (
                    item
                    for item in chains
                    if any(
                        edge.index == target_edge_index
                        for edge in item[1]
                    )
                ),
                None,
            )
            if chain is None:
                return explicit_interval

            chain_verts, chain_edges, closed = chain
            if closed or not chain_edges:
                return explicit_interval

            world_matrix = source_obj.matrix_world
            lengths = [
                (
                    world_matrix @ chain_verts[index + 1].co
                    - world_matrix @ chain_verts[index].co
                ).length
                for index in range(len(chain_edges))
            ]
            total_length = sum(lengths)
            if total_length <= EPSILON:
                return explicit_interval

            edge_position = next(
                index
                for index, edge in enumerate(chain_edges)
                if edge.index == target_edge_index
            )
            distance_before = sum(lengths[:edge_position])
            edge_length = lengths[edge_position]
            if edge_length <= EPSILON:
                return 0.0, 0.0

            coverage_start = max(
                chain_interval[0] * total_length,
                distance_before,
            )
            coverage_end = min(
                chain_interval[1] * total_length,
                distance_before + edge_length,
            )
            if coverage_end <= coverage_start + EPSILON:
                return 0.0, 0.0

            local_start = (coverage_start - distance_before) / edge_length
            local_end = (coverage_end - distance_before) / edge_length
            source_edge = chain_edges[edge_position]
            if (
                chain_verts[edge_position].index
                == source_edge.verts[0].index
            ):
                return local_start, local_end
            return 1.0 - local_end, 1.0 - local_start
        finally:
            if owns_bm:
                bm.free()

    def _full_edge_groups_form_junction(
        self,
        source_obj,
        clicked_edge_indices,
        stroke_edge_indices,
        shared_vertex_indices,
    ):
        """True when complete edge groups meet as a three-way junction.

        A two-edge stroke treats its shared corner as an internal chain vertex,
        so the normal endpoint-only merge rule cannot attach a third edge there.
        Full-edge graph generation supports that branch and must rebuild all
        three incident edges together. Partial strokes are excluded by the
        caller because their trimmed/tapered endpoint rules remain directional.
        """
        clicked = {int(index) for index in (clicked_edge_indices or [])}
        existing = {int(index) for index in (stroke_edge_indices or [])}
        shared = {int(index) for index in (shared_vertex_indices or [])}
        if not clicked or not existing or not shared:
            return False

        bm, owns_bm = self._open_bmesh_for_read(source_obj)
        try:
            for vertex_index in shared:
                if not (0 <= vertex_index < len(bm.verts)):
                    continue
                incident = {
                    edge.index for edge in bm.verts[vertex_index].link_edges
                }
                clicked_at_vertex = incident & clicked
                existing_at_vertex = incident & existing
                if (
                    clicked_at_vertex
                    and len(existing_at_vertex) >= 2
                    and len(clicked_at_vertex | existing_at_vertex) >= 3
                ):
                    return True
            return False
        finally:
            if owns_bm:
                bm.free()

    def _edge_local_slice_to_chain_interval(
        self,
        source_obj,
        edge_index,
        local_interval,
    ):
        """Convert a single-edge slice interval from edge.verts space to chain space.

        Ctrl previews parameterize an edge as 0.0 at ``edge.verts[0]`` and
        1.0 at ``edge.verts[1]``. The generator applies the same fractions along
        ``extract_edge_chains`` order, which may walk the edge backwards.
        """
        normalized = self._normalized_slice_interval(local_interval)
        if normalized is None or source_obj is None:
            return None

        start_fraction, end_fraction = normalized
        bm, owns_bm = self._open_bmesh_for_read(source_obj)
        try:
            edge_index = int(edge_index)
            if not (0 <= edge_index < len(bm.edges)):
                return normalized

            edge = bm.edges[edge_index]
            v0 = edge.verts[0].index
            v1 = edge.verts[1].index
            chains = extract_edge_chains([edge], source_obj.matrix_world)
            for chain_verts, _chain_edges, closed in chains:
                if closed or len(chain_verts) < 2:
                    continue

                chain_start = chain_verts[0].index
                chain_end = chain_verts[-1].index
                if chain_start == v0 and chain_end == v1:
                    return start_fraction, end_fraction
                if chain_start == v1 and chain_end == v0:
                    return (
                        max(0.0, min(1.0, 1.0 - end_fraction)),
                        max(0.0, min(1.0, 1.0 - start_fraction)),
                    )
            return normalized
        finally:
            if owns_bm:
                bm.free()

    def _normalize_slice_interval_for_edges(
        self,
        source_obj,
        edge_indices,
        slice_interval,
        *,
        interval_space="chain",
    ):
        """Return a chain-relative slice interval for generator/merge metadata."""
        normalized = self._normalized_slice_interval(slice_interval)
        if normalized is None:
            return None
        if interval_space == "chain":
            return normalized

        unique_edges = sorted({int(index) for index in (edge_indices or [])})
        if len(unique_edges) != 1 or source_obj is None:
            return normalized

        return self._edge_local_slice_to_chain_interval(
            source_obj,
            unique_edges[0],
            normalized,
        )

    def _chain_interval_to_edge_local(
        self,
        source_obj,
        edge_index,
        chain_interval,
    ):
        """Inverse of ``_edge_local_slice_to_chain_interval`` for one edge."""
        normalized = self._normalized_slice_interval(chain_interval)
        if normalized is None or source_obj is None:
            return None

        start_fraction, end_fraction = normalized
        bm, owns_bm = self._open_bmesh_for_read(source_obj)
        try:
            edge_index = int(edge_index)
            if not (0 <= edge_index < len(bm.edges)):
                return list(normalized)

            edge = bm.edges[edge_index]
            v0 = edge.verts[0].index
            v1 = edge.verts[1].index
            chains = extract_edge_chains([edge], source_obj.matrix_world)
            for chain_verts, _chain_edges, closed in chains:
                if closed or len(chain_verts) < 2:
                    continue

                chain_start = chain_verts[0].index
                chain_end = chain_verts[-1].index
                if chain_start == v0 and chain_end == v1:
                    return [start_fraction, end_fraction]
                if chain_start == v1 and chain_end == v0:
                    return [
                        max(0.0, min(1.0, 1.0 - end_fraction)),
                        max(0.0, min(1.0, 1.0 - start_fraction)),
                    ]
            return list(normalized)
        finally:
            if owns_bm:
                bm.free()

    def _partial_merge_corners_from_edge(
        self,
        source_obj,
        edge_index,
        edge_local_interval,
    ):
        """Open/tip mesh corners for one Ctrl partial (edge.verts[0] -> 0.0)."""
        normalized = self._normalized_slice_interval(edge_local_interval)
        if normalized is None or source_obj is None:
            return set(), set()

        start_fraction, end_fraction = normalized
        bm, owns_bm = self._open_bmesh_for_read(source_obj)
        try:
            edge_index = int(edge_index)
            if not (0 <= edge_index < len(bm.edges)):
                return set(), set()

            edge = bm.edges[edge_index]
            v0 = edge.verts[0].index
            v1 = edge.verts[1].index
            open_vertices = set()
            tip_vertices = set()

            if start_fraction <= EPSILON:
                open_vertices.add(v0)
            else:
                tip_vertices.add(v0)

            if end_fraction >= 1.0 - EPSILON:
                open_vertices.add(v1)
            else:
                tip_vertices.add(v1)

            return open_vertices, tip_vertices
        finally:
            if owns_bm:
                bm.free()

    def _full_stroke_merge_corners(
        self,
        source_obj,
        edge_indices,
        taper_vertices=None,
    ):
        """Open/tip mesh corners for a full-width stroke."""
        edge_indices = [int(index) for index in (edge_indices or [])]
        if not edge_indices or source_obj is None:
            return set(), set()

        bm, owns_bm = self._open_bmesh_for_read(source_obj)
        try:
            edges = [
                bm.edges[index]
                for index in edge_indices
                if 0 <= index < len(bm.edges)
            ]
            if not edges:
                return set(), set()

            chains = extract_edge_chains(edges, source_obj.matrix_world)
            open_vertices = set()
            for chain_verts, _chain_edges, closed in chains:
                if closed or len(chain_verts) < 2:
                    continue
                open_vertices.add(chain_verts[0].index)
                open_vertices.add(chain_verts[-1].index)

            tip_vertices = {
                int(index)
                for index in (taper_vertices or [])
            }
            open_vertices -= tip_vertices
            return open_vertices, tip_vertices
        finally:
            if owns_bm:
                bm.free()

    def _rebuild_merge_corners_for_stroke(
        self,
        source_obj,
        stroke,
        edge_local_slice_interval=None,
    ):
        """Recompute RULE 2a corners for one stroke record."""
        stroke_edges = [int(index) for index in stroke.get("edges", [])]
        if not stroke_edges or source_obj is None:
            return set(), set()

        edge_local = edge_local_slice_interval
        if edge_local is None:
            edge_local = stroke.get("edge_local_slice_interval")
        if edge_local is not None and len(stroke_edges) == 1:
            return self._partial_merge_corners_from_edge(
                source_obj,
                stroke_edges[0],
                edge_local,
            )

        # Once a Ctrl partial has merged around a corner (or across a
        # collinear split), it owns multiple source edges but still covers
        # only an interval of that expanded chain.  Treating it as a full
        # stroke makes the far source-chain endpoint look mergeable even
        # though the visible strip ends in the middle of an edge.  A later
        # click at the opposite end then absorbs both disjoint partials and
        # regenerates their convex hull, filling the intended gap.
        #
        # Preserve the same open/tip semantics used for a one-edge partial:
        # only a slice boundary that reaches a chain endpoint is open.  For a
        # mid-edge boundary, the corresponding chain endpoint is retained as
        # the directional tip marker used by the merge planner.
        chain_interval = self._normalized_slice_interval(
            stroke.get("slice_interval")
        )
        if chain_interval is not None:
            bm, owns_bm = self._open_bmesh_for_read(source_obj)
            try:
                edges = [
                    bm.edges[index]
                    for index in stroke_edges
                    if 0 <= index < len(bm.edges)
                ]
                chains = extract_edge_chains(edges, source_obj.matrix_world)
                if len(chains) == 1:
                    chain_verts, chain_edges, closed = chains[0]
                    if not closed and chain_edges and len(chain_verts) >= 2:
                        start_fraction, end_fraction = chain_interval
                        start_vertex = chain_verts[0].index
                        end_vertex = chain_verts[-1].index
                        open_vertices = set()
                        tip_vertices = set()

                        if start_fraction <= EPSILON:
                            open_vertices.add(start_vertex)
                        else:
                            tip_vertices.add(start_vertex)

                        if end_fraction >= 1.0 - EPSILON:
                            open_vertices.add(end_vertex)
                        else:
                            tip_vertices.add(end_vertex)

                        return open_vertices, tip_vertices
            finally:
                if owns_bm:
                    bm.free()

        return self._full_stroke_merge_corners(
            source_obj,
            stroke_edges,
            stroke.get("taper_vertices", []),
        )

    def _stroke_merge_corners(self, source_obj, stroke):
        """Return stored or derived open/tip corners for RULE 2a."""
        open_vertices, tip_vertices = self._rebuild_merge_corners_for_stroke(
            source_obj,
            stroke,
        )
        return set(open_vertices), set(tip_vertices)

    def _new_click_merge_corners(
        self,
        source_obj,
        edge_indices,
        edge_local_slice_interval=None,
    ):
        """Open/tip corners for the edge(s) about to be placed."""
        edge_indices = [int(index) for index in (edge_indices or [])]
        if not edge_indices or source_obj is None:
            return set(), set()

        if edge_local_slice_interval is not None and len(edge_indices) == 1:
            return self._partial_merge_corners_from_edge(
                source_obj,
                edge_indices[0],
                edge_local_slice_interval,
            )

        return self._full_stroke_merge_corners(source_obj, edge_indices)

    def _stroke_slice_corner_vertices(self, source_obj, stroke):
        """Return mesh-corner open ends and taper tips for merge taper rebuild."""
        return self._stroke_merge_corners(source_obj, stroke)

    def _stroke_taper_tip_vertices(self, source_obj, stroke):
        """Source vertices where a stroke has a tapered open end (RULE 2a)."""
        _open_vertices, tip_vertices = self._stroke_slice_corner_vertices(
            source_obj,
            stroke,
        )
        return tip_vertices

    def _stroke_merge_open_vertices(self, source_obj, stroke):
        """Mesh corner vertices where a stroke may merge (RULE 2a)."""
        open_vertices, _tip_vertices = self._stroke_slice_corner_vertices(
            source_obj,
            stroke,
        )
        return open_vertices

    def _stroke_open_connectable_vertices(self, source_obj, stroke):
        """Connectable vertices where a merge may attach (non-taper-tip ends)."""
        return self._stroke_merge_open_vertices(source_obj, stroke)

    def _merge_connection_allowed(
        self,
        source_obj,
        clicked_edge_indices,
        stroke,
        edge_local_slice_interval=None,
    ):
        """True when two strokes may join without consuming a partial tip."""
        stroke_edges = [int(index) for index in stroke.get("edges", [])]
        clicked_edges = [int(index) for index in (clicked_edge_indices or [])]
        if not stroke_edges or not clicked_edges:
            return False

        if not self._edge_groups_touch(source_obj, clicked_edges, stroke_edges):
            return False

        shared = self._shared_source_vertices(
            source_obj,
            clicked_edges,
            stroke_edges,
        )
        if not shared:
            return False

        exist_open, exist_tips = self._stroke_merge_corners(source_obj, stroke)
        new_open, new_tips = self._new_click_merge_corners(
            source_obj,
            clicked_edges,
            edge_local_slice_interval=edge_local_slice_interval,
        )

        # A newly placed partial must physically reach the shared source
        # corner at full width. Its opposite, trimmed boundary is represented
        # by the far source corner for direction tests and must never trigger
        # a merge merely because the source edges themselves touch.
        if edge_local_slice_interval is not None:
            if not (shared & new_open):
                return False
            if shared & new_tips:
                return False

        existing_is_partial = self._stroke_is_partial_slice(stroke)
        if shared & exist_tips and existing_is_partial:
            return False
        if shared & new_tips:
            return False
        if not (shared & exist_open) and not (
            shared & exist_tips and not existing_is_partial
        ):
            full_edge_junction = (
                edge_local_slice_interval is None
                and not existing_is_partial
                and self._full_edge_groups_form_junction(
                    source_obj,
                    clicked_edges,
                    stroke_edges,
                    shared,
                )
            )
            if not full_edge_junction:
                return False
        if edge_local_slice_interval is not None and not (shared & new_open):
            return False
        return True

    def _partial_merge_chain_interval(
        self,
        context,
        target_edges,
        partial_strokes,
    ):
        """Map accumulated stroke coverage onto an expanded merged chain."""
        source_obj = self._source_object(context)
        target_indices = sorted({int(index) for index in (target_edges or [])})
        if source_obj is None or not target_indices:
            return None

        if not any(
            self._stroke_is_partial_slice(stroke)
            for stroke in (partial_strokes or [])
        ):
            return None

        bm, owns_bm = self._open_bmesh_for_read(source_obj)
        try:
            selected = [
                bm.edges[index]
                for index in target_indices
                if 0 <= index < len(bm.edges)
            ]
            target_chains = extract_edge_chains(
                selected,
                source_obj.matrix_world,
            )
            if len(target_chains) != 1:
                return None
            target_verts, target_chain_edges, target_closed = target_chains[0]
            if target_closed or not target_chain_edges:
                return None

            world_matrix = source_obj.matrix_world
            target_lengths = [
                (
                    world_matrix @ target_verts[index + 1].co
                    - world_matrix @ target_verts[index].co
                ).length
                for index in range(len(target_chain_edges))
            ]
            target_total = sum(target_lengths)
            if target_total <= EPSILON:
                return None

            target_positions = {
                edge.index: position
                for position, edge in enumerate(target_chain_edges)
            }
            target_before = []
            running = 0.0
            for length in target_lengths:
                target_before.append(running)
                running += length

            def map_stroke_fraction(stroke_verts, stroke_edges, fraction):
                stroke_lengths = [
                    (
                        world_matrix @ stroke_verts[index + 1].co
                        - world_matrix @ stroke_verts[index].co
                    ).length
                    for index in range(len(stroke_edges))
                ]
                stroke_total = sum(stroke_lengths)
                if stroke_total <= EPSILON:
                    return None

                remaining = max(0.0, min(1.0, fraction)) * stroke_total
                edge_position = len(stroke_edges) - 1
                factor = 1.0
                for index, length in enumerate(stroke_lengths):
                    if remaining <= length + EPSILON:
                        edge_position = index
                        factor = 0.0 if length <= EPSILON else remaining / length
                        break
                    remaining -= length

                edge = stroke_edges[edge_position]
                target_position = target_positions.get(edge.index)
                if target_position is None:
                    return None
                stroke_start = stroke_verts[edge_position].index
                stroke_end = stroke_verts[edge_position + 1].index
                target_start = target_verts[target_position].index
                target_end = target_verts[target_position + 1].index
                if stroke_start == target_start and stroke_end == target_end:
                    target_factor = factor
                elif stroke_start == target_end and stroke_end == target_start:
                    target_factor = 1.0 - factor
                else:
                    return None
                return (
                    target_before[target_position]
                    + target_lengths[target_position] * target_factor
                ) / target_total

            coverage = []
            covered_edges = set()
            for stroke in partial_strokes or []:
                stroke_indices = sorted({
                    int(index)
                    for index in stroke.get("edges", [])
                    if int(index) in target_positions
                })
                if not stroke_indices:
                    continue
                covered_edges.update(stroke_indices)
                stroke_selected = [bm.edges[index] for index in stroke_indices]
                stroke_chains = extract_edge_chains(stroke_selected, world_matrix)
                if len(stroke_chains) != 1:
                    return None
                stroke_verts, stroke_chain_edges, stroke_closed = stroke_chains[0]
                if stroke_closed:
                    return None

                interval = self._normalized_slice_interval(
                    stroke.get("slice_interval")
                )
                edge_local = self._normalized_slice_interval(
                    stroke.get("edge_local_slice_interval")
                )
                if edge_local is not None and len(stroke_chain_edges) == 1:
                    edge = stroke_chain_edges[0]
                    start_vertex = stroke_verts[0].index
                    end_vertex = stroke_verts[1].index
                    if (
                        start_vertex == edge.verts[0].index
                        and end_vertex == edge.verts[1].index
                    ):
                        interval = edge_local
                    else:
                        interval = (
                            1.0 - edge_local[1],
                            1.0 - edge_local[0],
                        )
                if interval is None:
                    interval = (0.0, 1.0)

                coverage_start = map_stroke_fraction(
                    stroke_verts,
                    stroke_chain_edges,
                    interval[0],
                )
                coverage_end = map_stroke_fraction(
                    stroke_verts,
                    stroke_chain_edges,
                    interval[1],
                )
                if coverage_start is None or coverage_end is None:
                    return None
                coverage.append((
                    min(coverage_start, coverage_end),
                    max(coverage_start, coverage_end),
                ))

            # A newly clicked full edge has no stroke record yet. Preserve its
            # complete coverage when forming the union with existing slices.
            for edge in target_chain_edges:
                if edge.index in covered_edges:
                    continue
                position = target_positions[edge.index]
                coverage.append((
                    target_before[position] / target_total,
                    (
                        target_before[position] + target_lengths[position]
                    ) / target_total,
                ))

            if not coverage:
                return None
            interval_start = min(item[0] for item in coverage)
            interval_end = max(item[1] for item in coverage)
            if interval_start <= EPSILON and interval_end >= 1.0 - EPSILON:
                return None
            return interval_start, interval_end
        finally:
            if owns_bm:
                bm.free()

    def _compute_taper_tip_vertices(
        self,
        context,
        target_edges,
        slice_interval=None,
        merge_taper_start=False,
        merge_taper_end=False,
        force_all=False,
    ):
        """Source vertices that end up as tapered tips on a generated stroke.

        Only chain endpoints that coincide with real source vertices are
        recorded, because those are the only tips a future adjacent edge can
        connect to. Ctrl-partial slice tips fall mid-edge and never collide
        with an adjacent click, so they are intentionally ignored here.
        """
        source_obj = self._source_object(context)
        if source_obj is None or not target_edges:
            return set()

        # A partial slice tapers mid-edge points, not source vertices.
        if slice_interval is not None:
            return set()
        if not (force_all or merge_taper_start or merge_taper_end):
            return set()

        bm, owns_bm = self._open_bmesh_for_read(source_obj)
        try:
            selected = [
                bm.edges[int(index)]
                for index in target_edges
                if 0 <= int(index) < len(bm.edges)
            ]
            if not selected:
                return set()

            world_matrix = source_obj.matrix_world
            chains = extract_edge_chains(selected, world_matrix)
            tips = set()
            for chain_verts, _chain_edges, closed in chains:
                if closed or len(chain_verts) < 2:
                    continue
                if force_all or merge_taper_start:
                    tips.add(chain_verts[0].index)
                if force_all or merge_taper_end:
                    tips.add(chain_verts[-1].index)
            return tips
        finally:
            if owns_bm:
                bm.free()

    def _chain_end_for_edge(self, context, target_edges, hovered_edge):
        """Return 'start', 'end', or None for which run end a clicked edge sits on.

        Uses chain order: the first edge tapers the run start, the last edge
        tapers the run end (RULE 5). Middle edges return None.
        """
        source_obj = self._source_object(context)
        if source_obj is None or not target_edges:
            return None

        hovered = int(hovered_edge)
        bm, owns_bm = self._open_bmesh_for_read(source_obj)
        try:
            selected = [
                bm.edges[int(index)]
                for index in target_edges
                if 0 <= int(index) < len(bm.edges)
            ]
            if not selected:
                return None

            world_matrix = source_obj.matrix_world
            chains = extract_edge_chains(selected, world_matrix)
            for _chain_verts, chain_edges, closed in chains:
                if closed or len(chain_edges) < 1:
                    continue
                edge_indices = [edge.index for edge in chain_edges]
                if hovered not in edge_indices:
                    continue
                if hovered == edge_indices[0]:
                    return "start"
                if hovered == edge_indices[-1]:
                    return "end"
                return None
            return None
        finally:
            if owns_bm:
                bm.free()

    def _active_layer_source_edge_indices(self, context):
        """Return every source edge currently represented by the active layer."""
        layer_obj = self._interactive_layer_object(context)
        if layer_obj is None:
            return set()

        indices = set(
            parsed_source_indices(layer_obj.edge_decal_object_settings)
        )
        for stroke in self._load_interactive_strokes(layer_obj.name_full):
            indices.update(
                int(index)
                for index in stroke.get("edges", [])
            )
        return indices

    def _connected_active_layer_edge_component(
        self,
        context,
        seed_edge_indices,
    ):
        """Expand new edges through every vertex-connected edge on the layer."""
        source_obj = self._source_object(context)
        seeds = {int(index) for index in (seed_edge_indices or [])}
        if source_obj is None or not seeds:
            return sorted(seeds)

        candidates = self._active_layer_source_edge_indices(context) | seeds
        bm, owns_bm = self._open_bmesh_for_read(source_obj)
        try:
            valid_edges = {
                index: bm.edges[index]
                for index in candidates
                if 0 <= index < len(bm.edges)
            }
            vertex_edges = {}
            for index, edge in valid_edges.items():
                for vertex in edge.verts:
                    vertex_edges.setdefault(vertex.index, set()).add(index)

            component = {index for index in seeds if index in valid_edges}
            pending = list(component)
            while pending:
                current = pending.pop()
                for vertex in valid_edges[current].verts:
                    for neighbor in vertex_edges.get(vertex.index, ()):
                        if neighbor in component:
                            continue
                        component.add(neighbor)
                        pending.append(neighbor)
            return sorted(component)
        finally:
            if owns_bm:
                bm.free()

    def _clear_active_layer_for_atomic_rebuild(
        self,
        context,
        target_edge_indices,
    ):
        """Clear a fully covered layer so one generator call can replace it."""
        layer_obj = self._interactive_layer_object(context)
        source_obj = self._source_object(context)
        if layer_obj is None or source_obj is None:
            return False

        stored = self._active_layer_source_edge_indices(context)
        target = {int(index) for index in (target_edge_indices or [])}
        if not stored or not stored.issubset(target):
            return False

        clear_decal_mesh_inplace(layer_obj)
        self._save_interactive_strokes(layer_obj.name_full, [])
        set_stored_source_indices(layer_obj, [], source_obj=source_obj)
        layer_obj["edge_decal_base_source_indices"] = ""
        return True

    def _plan_click_merge_group(
        self,
        context,
        hovered_edge_index,
        clicked_edge_indices=None,
        edge_local_slice_interval=None,
    ):
        """Regenerate the full connected layer component touched by a click."""
        if hovered_edge_index is None or int(hovered_edge_index) < 0:
            return None

        source_obj = self._source_object(context)
        if source_obj is None or self._ensure_interactive_master(context) is None:
            return None

        hovered_edge = int(hovered_edge_index)
        clicked_edges = []
        clicked_seen = set()
        for edge_index in clicked_edge_indices or [hovered_edge]:
            edge_index = int(edge_index)
            if edge_index not in clicked_seen:
                clicked_edges.append(edge_index)
                clicked_seen.add(edge_index)
        if hovered_edge not in clicked_seen:
            clicked_edges.insert(0, hovered_edge)

        clicked_set = set(clicked_edges)
        strokes = [
            stroke
            for _decal_obj, stroke in self._iter_interactive_stroke_records(
                context,
            )
        ]
        if not strokes:
            return None

        mergeable_strokes = []
        for stroke in strokes:
            stroke_edges = {
                int(index) for index in stroke.get("edges", [])
            }
            overlaps_click = bool(stroke_edges & clicked_set)

            # Two Alt topology loops can contain the same source edge. The
            # overlap itself is sufficient evidence that their complete
            # strokes belong to one graph rebuild; excluding that stroke here
            # would append the new loop and author duplicate decal geometry on
            # every shared edge. Partials remain directional and continue
            # through the open/taper endpoint checks below.
            if (
                overlaps_click
                and len(clicked_set) > 1
                and edge_local_slice_interval is None
                and not self._stroke_is_partial_slice(stroke)
            ):
                mergeable_strokes.append(stroke)
                continue

            if overlaps_click:
                continue

            if self._merge_connection_allowed(
                source_obj,
                clicked_edges,
                stroke,
                edge_local_slice_interval=edge_local_slice_interval,
            ):
                mergeable_strokes.append(stroke)
        if not mergeable_strokes:
            return None

        # Source-edge connectivity is insufficient here because disjoint Ctrl
        # partials may legitimately share one edge index. Rebuild only stroke
        # records whose physical open end can join this click; each such record
        # already contains its previously merged multi-edge run.
        component = []
        component_seen = set()
        for stroke in mergeable_strokes:
            for edge_index in stroke.get("edges", []):
                edge_index = int(edge_index)
                if edge_index not in component_seen:
                    component.append(edge_index)
                    component_seen.add(edge_index)
        for edge_index in clicked_edges:
            if edge_index not in component_seen:
                component.append(edge_index)
                component_seen.add(edge_index)

        existing_edges = set(component) - clicked_set

        return {
            "target_edges": component,
            "path": list(clicked_edges),
            "anchor_edge": hovered_edge,
            "stroke_edges": sorted(existing_edges),
            "stroke_ids": [
                str(stroke.get("id", ""))
                for stroke in mergeable_strokes
            ],
            "atomic_component_rebuild": False,
        }

    def _collect_strokes_for_edges(self, context, edge_indices):
        """Return interactive stroke records that touch any listed source edge."""
        edge_set = {int(index) for index in (edge_indices or [])}
        if not edge_set:
            return []

        collected = []
        seen_ids = set()
        for _decal_obj, stroke in self._iter_interactive_stroke_records(context):
            stroke_edges = {
                int(index) for index in stroke.get("edges", [])
            }
            if not (stroke_edges & edge_set):
                continue
            stroke_id = str(stroke.get("id", ""))
            if stroke_id in seen_ids:
                continue
            seen_ids.add(stroke_id)
            collected.append(stroke)
        return collected

    def _compute_merge_endpoint_tapers(
        self,
        context,
        target_edges,
        absorbed_strokes,
    ):
        """Decide which open chain ends stay tapered after a merge rebuild.

        Partial strokes contribute taper only at their trimmed slice boundaries
        that remain exposed on the merged chain. The E toggle still tapers
        every open end. Junctions between merged parts stay square.
        """
        if self._endpoint_taper_enabled:
            return True, True

        if not target_edges:
            return False, False

        source_obj = self._source_object(context)
        if source_obj is None:
            return False, False

        bm, owns_bm = self._open_bmesh_for_read(source_obj)
        try:
            selected = [
                bm.edges[int(index)]
                for index in target_edges
                if 0 <= int(index) < len(bm.edges)
            ]
            if not selected:
                return False, False

            world_matrix = source_obj.matrix_world
            chains = extract_edge_chains(selected, world_matrix)
            taper_start = False
            taper_end = False

            for chain_verts, _chain_edges, closed in chains:
                if closed or len(chain_verts) < 2:
                    continue

                chain_start = chain_verts[0].index
                chain_end = chain_verts[-1].index

                for stroke in absorbed_strokes or []:
                    _open_corners, tip_corners = (
                        self._stroke_slice_corner_vertices(
                            source_obj,
                            stroke,
                        )
                    )
                    if chain_start in tip_corners:
                        taper_start = True
                    if chain_end in tip_corners:
                        taper_end = True

            return taper_start, taper_end
        finally:
            if owns_bm:
                bm.free()

    def _absorb_geometry_for_target_edges(
        self,
        context,
        edge_indices,
        extra_vertex_indices=None,
        geometry_candidate_edges=None,
        skip_promote=False,
    ):
        """Remove decal geometry only on edges being rebuilt.

        Interactive stroke metadata is trimmed edge-by-edge instead of dropping
        entire strokes, and polygon-based removal clears only faces whose
        centers are nearest to a target source edge. Only the active interactive
        decal layer is modified so other layers keep their geometry intact.

        When ``geometry_candidate_edges`` is set, only faces whose nearest source
        edge is one of those edges may be removed. Nearest-edge assignment still
        considers every stored source edge so neighbour strokes are not wiped.
        """
        self._ensure_interactive_master(context)
        target_set = {int(index) for index in (edge_indices or [])}
        if not target_set:
            return target_set

        source_obj = self._source_object(context)
        if source_obj is None:
            return target_set

        restrict_vertices = {
            int(index) for index in (extra_vertex_indices or [])
        }

        layer_obj = self._interactive_layer_object(context)
        if layer_obj is None:
            return target_set

        decal_obj = layer_obj
        object_name = decal_obj.name_full
        strokes = list(self._load_interactive_strokes(object_name))
        updated_strokes = []
        strokes_changed = False
        for stroke in strokes:
            stroke_edges = {
                int(index) for index in stroke.get("edges", [])
            }
            remaining_edges = sorted(stroke_edges - target_set)
            if not remaining_edges:
                if stroke_edges & target_set:
                    strokes_changed = True
                continue
            if remaining_edges != sorted(stroke_edges):
                strokes_changed = True
                stroke = dict(stroke)
                stroke["edges"] = remaining_edges
                stroke["vertices"] = []
            updated_strokes.append(stroke)
        if strokes_changed:
            self._save_interactive_strokes(object_name, updated_strokes)

        data = getattr(decal_obj, "edge_decal_object_settings", None)
        eligible_edge_indices = None
        if geometry_candidate_edges is not None:
            eligible_edge_indices = sorted({
                int(index)
                for index in geometry_candidate_edges
            })
        candidate_edge_indices = sorted(target_set)
        if data is not None and data.initialized:
            candidate_edge_indices = sorted(
                set(parsed_source_indices(data)) | target_set
            )

        self._remove_decal_geometry_for_source_edges(
            context,
            decal_obj,
            list(target_set),
            candidate_edge_indices=candidate_edge_indices,
            restrict_vertex_indices=restrict_vertices or None,
            source_obj=source_obj,
            eligible_edge_indices=eligible_edge_indices,
        )
        self._remove_stroke_source_indices(object_name, list(target_set))

        if not skip_promote:
            for edge_index in sorted(target_set):
                if not self._edge_has_generated_stroke(edge_index):
                    continue
                _decal_obj, interactive_stroke = (
                    self._find_interactive_stroke_by_edge(edge_index)
                )
                if interactive_stroke is not None:
                    continue
                self._promote_automatic_edge_to_interactive(
                    context,
                    edge_index,
                )

        return target_set

    def _iter_source_decals_for_edges(self, source_obj):
        """Yield decal edge ownership data for the active interactive layer only."""
        if source_obj is None:
            return

        layer_obj = bpy.data.objects.get(self._interactive_layer_name)
        if (
            layer_obj is None
            or layer_obj.get("edge_decal_source") != source_obj.name_full
        ):
            return

        strokes = self._load_interactive_strokes(layer_obj.name_full)
        interactive_edges = {
            int(index)
            for stroke in strokes
            for index in stroke.get("edges", [])
        }
        data = getattr(layer_obj, "edge_decal_object_settings", None)
        layer_indices = (
            set(parsed_source_indices(data)) if data is not None else set()
        )
        yield layer_obj, strokes, layer_indices, interactive_edges

    def _find_interactive_stroke_by_edge(self, edge_index):
        layer_obj = self._interactive_layer_object(bpy.context)
        if layer_obj is None:
            return None, None

        target_index = int(edge_index)
        for stroke in self._load_interactive_strokes(layer_obj.name_full):
            if target_index in stroke.get("edges", []):
                return layer_obj, stroke
        return None, None

    def _find_interactive_strokes_by_edge(self, edge_index):
        """Return every stroke occupying a source edge, including disjoint slices."""
        layer_obj = self._interactive_layer_object(bpy.context)
        if layer_obj is None:
            return None, []

        target_index = int(edge_index)
        strokes = [
            stroke
            for stroke in self._load_interactive_strokes(layer_obj.name_full)
            if target_index in {
                int(index) for index in stroke.get("edges", [])
            }
        ]
        return layer_obj, strokes

    def _remove_specific_interactive_strokes(
        self,
        context,
        decal_obj,
        strokes,
    ):
        """Remove selected stroke records/geometry without clearing co-owners."""
        if decal_obj is None or not strokes:
            return False

        stroke_ids = {str(stroke.get("id", "")) for stroke in strokes}
        edge_indices = sorted({
            int(index)
            for stroke in strokes
            for index in stroke.get("edges", [])
        })
        vertex_indices = sorted({
            int(index)
            for stroke in strokes
            for index in stroke.get("vertices", [])
        })
        if not stroke_ids or not edge_indices:
            return False

        object_name = decal_obj.name_full
        data = decal_obj.edge_decal_object_settings
        layer_strokes = self._load_interactive_strokes(object_name)
        candidate_edge_indices = sorted(
            set(parsed_source_indices(data))
            | {
                int(index)
                for stroke in layer_strokes
                for index in stroke.get("edges", [])
            }
            | set(edge_indices)
        )
        removed = self._remove_decal_geometry_for_source_edges(
            context,
            decal_obj,
            edge_indices,
            # Compare against every edge represented by the layer. A trimmed
            # stroke may legitimately have no stored vertex range; comparing
            # only against its target edge in that case classifies every face
            # in the layer as the target and wipes unrelated placements.
            candidate_edge_indices=candidate_edge_indices,
            restrict_vertex_indices=vertex_indices,
        )
        if not removed:
            self._remove_master_vertices(object_name, vertex_indices)

        remaining_strokes = [
            stroke
            for stroke in self._load_interactive_strokes(object_name)
            if str(stroke.get("id", "")) not in stroke_ids
        ]
        self._save_interactive_strokes(object_name, remaining_strokes)

        # Source-edge ownership is set-like at object level. Keep an edge in
        # regeneration data while another disjoint partial (or automatic base)
        # still owns it.
        remaining_interactive_edges = {
            int(index)
            for stroke in remaining_strokes
            for index in stroke.get("edges", [])
        }
        base_edges = set()
        base_raw = str(decal_obj.get("edge_decal_base_source_indices", ""))
        if base_raw:
            try:
                base_edges = {
                    int(token) for token in base_raw.split(",") if token.strip()
                }
            except (TypeError, ValueError):
                base_edges = set()

        stored_edges = set(parsed_source_indices(data))
        removable_edges = set(edge_indices) - remaining_interactive_edges - base_edges
        set_stored_source_indices(decal_obj, sorted(stored_edges - removable_edges))
        return True

    def _edge_has_generated_stroke(self, edge_index):
        layer_obj = self._interactive_layer_object(bpy.context)
        if layer_obj is None:
            return False

        target_index = int(edge_index)
        data = layer_obj.edge_decal_object_settings
        if target_index in set(parsed_source_indices(data)):
            return True

        for stroke in self._load_interactive_strokes(layer_obj.name_full):
            if target_index in {int(index) for index in stroke.get("edges", [])}:
                return True
        return False

    def _edge_has_automatic_generated_stroke(self, edge_index):
        """True when the edge still has automatic (non-interactive) decal data."""
        layer_obj = self._interactive_layer_object(bpy.context)
        if layer_obj is None:
            return False

        target_index = int(edge_index)
        data = layer_obj.edge_decal_object_settings
        layer_indices = set(parsed_source_indices(data))
        if target_index not in layer_indices:
            return False

        interactive_edges = {
            int(index)
            for stroke in self._load_interactive_strokes(layer_obj.name_full)
            for index in stroke.get("edges", [])
        }
        return target_index not in interactive_edges

    def _automatic_decal_for_edge(self, context, edge_index):
        """Return the active layer decal when its automatic base contains edge_index."""
        layer_obj = self._interactive_layer_object(context)
        if layer_obj is None:
            return None

        target_index = int(edge_index)
        interactive_edges = {
            int(index)
            for stroke in self._load_interactive_strokes(layer_obj.name_full)
            for index in stroke.get("edges", [])
        }

        data = layer_obj.edge_decal_object_settings
        all_indices = set(parsed_source_indices(data))

        base_raw = str(layer_obj.get("edge_decal_base_source_indices", ""))
        if base_raw:
            try:
                base_indices = {
                    int(token)
                    for token in base_raw.split(",")
                    if token.strip()
                }
            except Exception:
                base_indices = all_indices - interactive_edges
        else:
            base_indices = all_indices - interactive_edges

        if target_index in base_indices or (
            target_index in all_indices
            and target_index not in interactive_edges
        ):
            return layer_obj

        return None

    def _nearest_decal_component_vertices(self, context, decal_obj, edge_index):
        """
        Find the disconnected decal mesh component closest to one source edge.

        This allows an automatic edge to be promoted to an interactive stroke
        without regenerating the entire automatic decal and changing its seed,
        UV offsets, or unrelated geometry.
        """
        source_obj = self._source_object(context)
        if (
            source_obj is None
            or decal_obj is None
            or decal_obj.type != "MESH"
            or not decal_obj.data.vertices
        ):
            return []

        try:
            source_edge = source_obj.data.edges[int(edge_index)]
        except (IndexError, TypeError, ValueError):
            return []

        source_a = source_obj.matrix_world @ source_obj.data.vertices[
            source_edge.vertices[0]
        ].co
        source_b = source_obj.matrix_world @ source_obj.data.vertices[
            source_edge.vertices[1]
        ].co
        segment = source_b - source_a
        segment_length_sq = segment.length_squared

        mesh = decal_obj.data
        adjacency = {vertex.index: set() for vertex in mesh.vertices}
        for edge in mesh.edges:
            a, b = edge.vertices
            adjacency[a].add(b)
            adjacency[b].add(a)

        unvisited = set(adjacency)
        components = []
        while unvisited:
            start = unvisited.pop()
            stack = [start]
            component = {start}
            while stack:
                current = stack.pop()
                for neighbor in adjacency[current]:
                    if neighbor in unvisited:
                        unvisited.remove(neighbor)
                        component.add(neighbor)
                        stack.append(neighbor)
            components.append(component)

        center_group = decal_obj.vertex_groups.get("EdgeDecal_Center")
        center_indices = set()
        if center_group is not None:
            group_index = center_group.index
            for vertex in mesh.vertices:
                if any(
                    membership.group == group_index
                    and membership.weight > 0.0
                    for membership in vertex.groups
                ):
                    center_indices.add(vertex.index)

        def point_segment_distance_sq(point):
            if segment_length_sq <= EPSILON:
                return (point - source_a).length_squared
            factor = (point - source_a).dot(segment) / segment_length_sq
            factor = max(0.0, min(1.0, factor))
            closest = source_a + segment * factor
            return (point - closest).length_squared

        best_component = None
        best_score = float("inf")

        for component in components:
            sample_indices = component & center_indices
            if not sample_indices:
                sample_indices = component

            score = min(
                point_segment_distance_sq(
                    decal_obj.matrix_world @ mesh.vertices[index].co
                )
                for index in sample_indices
            )
            if score < best_score:
                best_score = score
                best_component = component

        if best_component is None:
            return []

        # Reject obviously unrelated components. The tolerance scales with the
        # stored decal width and still permits tapered ends, beveling, and
        # surface offset on automatic strips.
        data = decal_obj.edge_decal_object_settings
        face_width = float(getattr(data, "face_width", 0.06))
        surface_offset = float(getattr(data, "surface_offset", 0.002))
        segment_length = segment.length
        tolerance = max(
            0.02,
            face_width * 5.0,
            surface_offset * 12.0,
            segment_length * 0.35,
        )
        if best_score > tolerance * tolerance:
            return []

        return sorted(best_component)

    def _promote_automatic_edge_to_interactive(self, context, edge_index):
        """
        Remove only the automatic decal geometry for one source edge.

        Uses polygon-to-edge proximity instead of fragile mesh-component
        isolation so tapered and beveled automatic strips promote reliably.
        """
        decal_obj = self._automatic_decal_for_edge(context, edge_index)
        if decal_obj is None:
            return None, False

        source_obj = self._source_object(context)
        target_index = int(edge_index)
        data = decal_obj.edge_decal_object_settings
        interactive_edges = {
            int(index)
            for stroke in self._load_interactive_strokes(decal_obj.name_full)
            for index in stroke.get("edges", [])
        }

        base_raw = str(decal_obj.get("edge_decal_base_source_indices", ""))
        if base_raw:
            try:
                base_indices = {
                    int(token)
                    for token in base_raw.split(",")
                    if token.strip()
                }
            except Exception:
                base_indices = set(parsed_source_indices(data)) - interactive_edges
        else:
            base_indices = set(parsed_source_indices(data)) - interactive_edges

        if target_index not in base_indices:
            return decal_obj, False

        candidate_edge_indices = sorted(base_indices | interactive_edges)
        removed = self._remove_decal_geometry_for_source_edges(
            context,
            decal_obj,
            [target_index],
            candidate_edge_indices=candidate_edge_indices,
            source_obj=source_obj,
        )
        if not removed:
            component_vertices = self._nearest_decal_component_vertices(
                context,
                decal_obj,
                edge_index,
            )
            if component_vertices:
                removed = self._remove_master_vertices(
                    decal_obj.name_full,
                    component_vertices,
                )

        if not removed:
            return decal_obj, False

        stored_indices = [
            index
            for index in parsed_source_indices(data)
            if index != target_index
        ]
        set_stored_source_indices(decal_obj, stored_indices)

        base_indices.discard(target_index)
        decal_obj["edge_decal_base_source_indices"] = ",".join(
            str(index) for index in sorted(base_indices)
        )
        return decal_obj, True



    def _remove_decal_geometry_for_source_edges(
        self,
        context,
        decal_obj,
        target_edge_indices,
        candidate_edge_indices=None,
        restrict_vertex_indices=None,
        source_obj=None,
        eligible_edge_indices=None,
    ):
        """Remove decal faces whose centers are nearest to any target source edge."""
        if source_obj is None:
            source_obj = self._source_object(context)
        if decal_obj is None or source_obj is None or decal_obj.type != "MESH":
            return False

        mesh = decal_obj.data
        if mesh is None or not mesh.polygons:
            return False

        try:
            target_edge_set = {
                int(index) for index in (target_edge_indices or [])
            }
            if candidate_edge_indices is None:
                candidate_edge_indices = sorted(target_edge_set)
            else:
                candidate_edge_indices = sorted({
                    int(index) for index in candidate_edge_indices
                })
            eligible_edge_set = None
            if eligible_edge_indices is not None:
                eligible_edge_set = {
                    int(index) for index in eligible_edge_indices
                }
        except (TypeError, ValueError):
            return False

        if not target_edge_set or not candidate_edge_indices:
            return False

        source_segments = {}
        for index in candidate_edge_indices:
            if index < 0 or index >= len(source_obj.data.edges):
                continue
            edge = source_obj.data.edges[index]
            a = source_obj.matrix_world @ source_obj.data.vertices[edge.vertices[0]].co
            b = source_obj.matrix_world @ source_obj.data.vertices[edge.vertices[1]].co
            source_segments[index] = (a, b)

        if not source_segments:
            return False

        restricted = {int(index) for index in (restrict_vertex_indices or [])}

        def distance_sq_to_segment(point, a, b):
            segment = b - a
            length_sq = segment.length_squared
            if length_sq <= EPSILON:
                return (point - a).length_squared
            factor = (point - a).dot(segment) / length_sq
            factor = max(0.0, min(1.0, factor))
            return (point - (a + segment * factor)).length_squared

        polygons_to_remove = set()
        for polygon in mesh.polygons:
            polygon_vertices = set(polygon.vertices)
            if restricted and not polygon_vertices.intersection(restricted):
                continue
            center_local = sum(
                (mesh.vertices[index].co for index in polygon.vertices),
                Vector((0.0, 0.0, 0.0)),
            ) / max(len(polygon.vertices), 1)
            center_world = decal_obj.matrix_world @ center_local
            nearest_index = min(
                source_segments,
                key=lambda index: distance_sq_to_segment(
                    center_world, *source_segments[index]
                ),
            )
            if nearest_index not in target_edge_set:
                continue
            if (
                eligible_edge_set is not None
                and nearest_index not in eligible_edge_set
            ):
                continue
            polygons_to_remove.add(polygon.index)

        if not polygons_to_remove:
            return False

        uv_layer = mesh.uv_layers.active
        kept_faces = []
        kept_face_uvs = []
        kept_material_indices = []
        kept_smooth = []
        used_vertices = set()

        for polygon in mesh.polygons:
            if polygon.index in polygons_to_remove:
                continue
            face = tuple(polygon.vertices)
            kept_faces.append(face)
            used_vertices.update(face)
            kept_material_indices.append(polygon.material_index)
            kept_smooth.append(polygon.use_smooth)
            if uv_layer is not None:
                kept_face_uvs.append([
                    uv_layer.data[loop_index].uv.copy()
                    for loop_index in polygon.loop_indices
                ])
            else:
                kept_face_uvs.append([Vector((0.0, 0.0)) for _ in polygon.loop_indices])

        old_to_new = {old: new for new, old in enumerate(sorted(used_vertices))}
        vertices = [mesh.vertices[old].co.copy() for old in sorted(used_vertices)]
        faces = [tuple(old_to_new[index] for index in face) for face in kept_faces]

        group_memberships = {}
        for vertex in mesh.vertices:
            if vertex.index not in old_to_new:
                continue
            for membership in vertex.groups:
                group_memberships.setdefault(membership.group, []).append(
                    (old_to_new[vertex.index], membership.weight)
                )
        group_names = {group.index: group.name for group in decal_obj.vertex_groups}

        replacement = bpy.data.meshes.new(f"{mesh.name}_EdgeRemoved")
        replacement.from_pydata([tuple(co) for co in vertices], [], faces)
        replacement.update(calc_edges=True)
        for material in mesh.materials:
            replacement.materials.append(material)
        for polygon, material_index, smooth in zip(
            replacement.polygons, kept_material_indices, kept_smooth
        ):
            polygon.material_index = material_index
            polygon.use_smooth = smooth

        new_uv = replacement.uv_layers.new(
            name=uv_layer.name if uv_layer is not None else "UVMap"
        )
        for polygon, face_uvs in zip(replacement.polygons, kept_face_uvs):
            for loop_index, uv in zip(polygon.loop_indices, face_uvs):
                new_uv.data[loop_index].uv = uv

        old_mesh = decal_obj.data
        decal_obj.data = replacement
        for group in list(decal_obj.vertex_groups):
            decal_obj.vertex_groups.remove(group)
        for group_index in sorted(group_names):
            group = decal_obj.vertex_groups.new(name=group_names[group_index])
            for vertex_index, weight in group_memberships.get(group_index, []):
                group.add([vertex_index], weight, "REPLACE")

        strokes = self._load_interactive_strokes(decal_obj.name_full)
        for stroke in strokes:
            stroke["vertices"] = sorted(
                old_to_new[index]
                for index in stroke.get("vertices", [])
                if index in old_to_new
            )
        self._save_interactive_strokes(decal_obj.name_full, strokes)

        if old_mesh.users == 0:
            bpy.data.meshes.remove(old_mesh)
        return True

    def _remove_source_edge_geometry_in_place(
        self, decal_obj, source_obj, target_edge_index, candidate_edge_indices,
        restrict_vertex_indices=None,
    ):
        """Remove only polygons belonging to one source edge without regeneration."""
        return self._remove_decal_geometry_for_source_edges(
            bpy.context,
            decal_obj,
            [int(target_edge_index)],
            candidate_edge_indices=candidate_edge_indices,
            restrict_vertex_indices=restrict_vertex_indices,
            source_obj=source_obj,
        )

    def _rebuild_full_stroke_after_edge_removal(
        self,
        context,
        layer_obj,
        stroke,
        target_edge_index,
    ):
        """Rebuild a full stroke after removing one of its source edges.

        Graph junction geometry cuts each incident strip back to a shared
        center. Deleting only the removed edge's polygons leaves those cuts in
        the surviving strips, which becomes a visible hole when a degree-three
        pole turns into a two-edge corner. Replace the affected stroke with a
        fresh generation of its remaining edge graph instead.

        ``None`` means the stroke is partial or otherwise not eligible for a
        complete rebuild. ``False`` means a rebuild was attempted but failed.
        """
        if layer_obj is None or stroke is None:
            return None
        if self._stroke_is_partial_slice(stroke):
            return None

        original_edges = []
        seen = set()
        for edge_index in stroke.get("edges", []):
            edge_index = int(edge_index)
            if edge_index not in seen:
                original_edges.append(edge_index)
                seen.add(edge_index)
        target_edge_index = int(target_edge_index)
        if target_edge_index not in seen or len(original_edges) <= 1:
            return None

        remaining_edges = [
            edge_index
            for edge_index in original_edges
            if edge_index != target_edge_index
        ]
        if not remaining_edges:
            return None

        merge_taper_start, merge_taper_end = (
            self._compute_merge_endpoint_tapers(
                context,
                remaining_edges,
                [stroke],
            )
        )
        if not self._remove_specific_interactive_strokes(
            context,
            layer_obj,
            [stroke],
        ):
            return False

        vertex_count_before = len(layer_obj.data.vertices)
        stroke_width = float(stroke.get("face_width", 0.0) or 0.0)
        previous_width = self._interactive_face_width
        if stroke_width > 0.0:
            self._interactive_face_width = stroke_width

        try:
            success, _reason, generated_name = self._generate_from_edge_indices(
                context,
                remaining_edges,
                force_connected=True,
                slice_interval=None,
                merge_taper_start=merge_taper_start,
                merge_taper_end=merge_taper_end,
            )
        finally:
            self._interactive_face_width = previous_width

        if not success:
            return False

        merged_name, new_stroke_vertices = self._merge_new_decal_into_master(
            generated_name,
            vertex_count_before=vertex_count_before,
        )
        if not merged_name:
            return False

        new_taper_vertices = self._compute_taper_tip_vertices(
            context,
            remaining_edges,
            merge_taper_start=merge_taper_start,
            merge_taper_end=merge_taper_end,
        )
        self._register_interactive_stroke(
            merged_name,
            remaining_edges,
            new_stroke_vertices,
            force_connected=True,
            slice_interval=None,
            face_width=(stroke_width if stroke_width > 0.0 else previous_width),
            taper_vertices=new_taper_vertices,
        )
        return True

    def _connected_generated_edge_indices(
        self,
        source_obj,
        layer_obj,
        edge_index,
        bridge_removed_seed=False,
    ):
        """Return the active layer's generated edge component containing a seed.

        ``bridge_removed_seed`` supports Blender's double-click event sequence:
        the first click may already have removed the seed edge, so generated
        neighbours touching either of its endpoints become traversal seeds.
        """
        if source_obj is None or layer_obj is None:
            return set()

        mesh = getattr(source_obj, "data", None)
        data = getattr(layer_obj, "edge_decal_object_settings", None)
        if mesh is None or data is None:
            return set()

        generated = {
            int(index)
            for index in parsed_source_indices(data)
            if 0 <= int(index) < len(mesh.edges)
        }
        generated.update(
            int(index)
            for stroke in self._load_interactive_strokes(layer_obj.name_full)
            for index in stroke.get("edges", [])
            if 0 <= int(index) < len(mesh.edges)
        )
        if not generated:
            return set()

        target_index = int(edge_index)
        vertex_to_edges = {}
        for generated_index in generated:
            edge = mesh.edges[generated_index]
            for vertex_index in edge.vertices:
                vertex_to_edges.setdefault(int(vertex_index), set()).add(
                    generated_index
                )

        if target_index in generated:
            pending = [target_index]
        elif bridge_removed_seed and 0 <= target_index < len(mesh.edges):
            pending = sorted({
                neighbor_index
                for vertex_index in mesh.edges[target_index].vertices
                for neighbor_index in vertex_to_edges.get(int(vertex_index), set())
            })
        else:
            return set()

        connected = set()
        while pending:
            current_index = int(pending.pop())
            if current_index in connected:
                continue
            connected.add(current_index)
            current_edge = mesh.edges[current_index]
            for vertex_index in current_edge.vertices:
                for neighbor_index in vertex_to_edges.get(int(vertex_index), set()):
                    if neighbor_index not in connected:
                        pending.append(neighbor_index)
        return connected

    def _remove_connected_edges_from_active_layer(
        self,
        context,
        edge_index,
        bridge_removed_seed=False,
        record_history=True,
    ):
        """Remove one topologically connected generated component as one action."""
        source_obj = self._source_object(context)
        layer_obj = bpy.data.objects.get(self._interactive_layer_name)
        if (
            source_obj is None
            or layer_obj is None
            or layer_obj.get("edge_decal_source") != source_obj.name_full
        ):
            return set()

        target_indices = self._connected_generated_edge_indices(
            source_obj,
            layer_obj,
            edge_index,
            bridge_removed_seed=bridge_removed_seed,
        )
        if not target_indices:
            return set()

        return self._remove_generated_edge_indices_from_active_layer(
            context,
            target_indices,
            record_history=record_history,
        )

    def _remove_generated_edge_indices_from_active_layer(
        self,
        context,
        target_indices,
        record_history=True,
    ):
        """Remove an explicit set of generated source edges from the active layer."""
        source_obj = self._source_object(context)
        layer_obj = bpy.data.objects.get(self._interactive_layer_name)
        if (
            source_obj is None
            or layer_obj is None
            or layer_obj.get("edge_decal_source") != source_obj.name_full
        ):
            return set()

        data = layer_obj.edge_decal_object_settings
        all_indices = set(parsed_source_indices(data))
        all_indices.update(
            int(index)
            for stroke in self._load_interactive_strokes(layer_obj.name_full)
            for index in stroke.get("edges", [])
        )
        target_indices = {
            int(index) for index in (target_indices or [])
        }.intersection(all_indices)
        if not target_indices:
            return set()
        previous_pending = list(self._pending_edge_indices or [])
        previous_anchor = self._path_anchor_edge_index
        previous_last_vertices = list(self._last_stroke_vertex_indices or [])
        backup = (
            self._make_object_backup(layer_obj.name_full)
            if record_history
            else None
        )

        removed = self._remove_decal_geometry_for_source_edges(
            context,
            layer_obj,
            sorted(target_indices),
            candidate_edge_indices=sorted(all_indices),
            source_obj=source_obj,
        )
        if not removed:
            self._discard_object_backup(backup)
            return set()

        remaining_indices = all_indices - target_indices
        set_stored_source_indices(layer_obj, sorted(remaining_indices))

        strokes = self._load_interactive_strokes(layer_obj.name_full)
        remaining_strokes = []
        for stroke in strokes:
            stroke_edges = {
                int(index) for index in stroke.get("edges", [])
            }
            kept_edges = sorted(stroke_edges - target_indices)
            if not kept_edges:
                continue
            if kept_edges != sorted(stroke_edges):
                stroke = dict(stroke)
                stroke["edges"] = kept_edges
            remaining_strokes.append(stroke)
        self._save_interactive_strokes(layer_obj.name_full, remaining_strokes)

        interactive_edges = {
            int(index)
            for stroke in remaining_strokes
            for index in stroke.get("edges", [])
        }
        base_raw = str(layer_obj.get("edge_decal_base_source_indices", ""))
        if base_raw:
            try:
                base_indices = {
                    int(token) for token in base_raw.split(",") if token.strip()
                }
            except (TypeError, ValueError):
                base_indices = all_indices - interactive_edges
        else:
            base_indices = all_indices - interactive_edges
        base_indices.difference_update(target_indices)
        layer_obj["edge_decal_base_source_indices"] = ",".join(
            str(index) for index in sorted(base_indices)
        )

        self._interactive_layer_name = layer_obj.name_full
        self._last_generated_object_name = layer_obj.name_full
        self._last_stroke_vertex_indices = []
        if target_indices.intersection(self._pending_edge_indices or []):
            self._clear_pending_path(context)

        if record_history:
            self._action_history.append({
                "created_name": layer_obj.name_full,
                "deleted_backup": backup,
                "previous_pending": previous_pending,
                "previous_anchor": previous_anchor,
                "previous_last_name": layer_obj.name_full,
                "previous_last_stroke_vertices": previous_last_vertices,
            })

        if self._remove_mode:
            self._remove_components = self._collect_remove_components(context)
            self._hovered_remove_index = -1
        return target_indices

    def _clear_last_remove_click(self):
        self._last_remove_click_edge_index = -1
        self._last_remove_click_time = 0.0
        self._last_remove_click_mouse_region = (0, 0)
        self._last_remove_connected_indices = set()
        self._last_remove_action = None

    def _remove_click_matches_last(self, context, event):
        if (
            self._last_remove_click_edge_index < 0
            or not self._action_history
            or self._action_history[-1] is not self._last_remove_action
        ):
            return False

        double_click_delay = max(
            0.25,
            float(context.preferences.inputs.mouse_double_click_time) / 1000.0
            + 0.05,
        )
        previous_x, previous_y = self._last_remove_click_mouse_region
        mouse_distance_sq = (
            (event.mouse_region_x - previous_x) ** 2
            + (event.mouse_region_y - previous_y) ** 2
        )
        return bool(
            time.monotonic() - self._last_remove_click_time <= double_click_delay
            and mouse_distance_sq <= 144.0
        )

    def _expand_last_edge_removal(self, context):
        """Expand an immediate single-edge removal using its original component."""
        if (
            self._last_remove_click_edge_index < 0
            or not self._action_history
            or self._action_history[-1] is not self._last_remove_action
        ):
            self._clear_last_remove_click()
            return False

        clicked_index = int(self._last_remove_click_edge_index)
        remainder = set(self._last_remove_connected_indices or [])
        remainder.discard(clicked_index)
        removed_indices = self._remove_generated_edge_indices_from_active_layer(
            context,
            remainder,
            record_history=False,
        )
        removed_count = 1 + len(removed_indices)
        self._clear_last_remove_click()

        self.report(
            {"INFO"},
            f"Removed {removed_count} connected edge(s)",
        )
        self._suppress_hover_until_mousemove = True
        self._hovered_edge_index = -1
        self._hovered_edge_indices = []
        self._hovered_edge_points = None
        if context.area:
            context.area.tag_redraw()
        return True

    def _commit_connected_edge_removal(self, context, target_index):
        connected_indices = self._remove_connected_edges_from_active_layer(
            context,
            target_index,
            bridge_removed_seed=False,
            record_history=True,
        )
        if not connected_indices:
            self.report(
                {"WARNING"},
                "That edge is not part of the selected decal layer",
            )
            return False

        self.report(
            {"INFO"},
            f"Removed {len(connected_indices)} connected edge(s)",
        )
        self._suppress_hover_until_mousemove = True
        self._hovered_edge_index = -1
        self._hovered_edge_indices = []
        self._hovered_edge_points = None
        if context.area:
            context.area.tag_redraw()
        return True

    def _remove_edge_from_active_layer(self, context, edge_index):
        """Remove one edge locally while preserving all unrelated decal data."""
        source_obj = self._source_object(context)
        layer_obj = bpy.data.objects.get(self._interactive_layer_name)
        if (
            source_obj is None
            or layer_obj is None
            or layer_obj.get("edge_decal_source") != source_obj.name_full
        ):
            return False

        target_index = int(edge_index)
        data = layer_obj.edge_decal_object_settings
        all_indices = parsed_source_indices(data)
        if target_index not in all_indices:
            return False

        backup = self._make_object_backup(layer_obj.name_full)
        previous_pending = list(self._pending_edge_indices or [])
        previous_anchor = self._path_anchor_edge_index
        previous_last_vertices = list(self._last_stroke_vertex_indices or [])

        strokes = self._load_interactive_strokes(layer_obj.name_full)
        target_stroke_position = next(
            (
                position
                for position, stroke in enumerate(strokes)
                if target_index in stroke.get("edges", [])
            ),
            -1,
        )
        target_stroke = (
            strokes[target_stroke_position]
            if target_stroke_position >= 0
            else None
        )

        rebuilt_stroke = self._rebuild_full_stroke_after_edge_removal(
            context,
            layer_obj,
            target_stroke,
            target_index,
        )
        if rebuilt_stroke is not None:
            if not rebuilt_stroke:
                self._delete_generated_object(layer_obj.name_full)
                restored_name = self._restore_object_backup(backup)
                self._interactive_layer_name = restored_name or layer_obj.name_full
                self._last_generated_object_name = self._interactive_layer_name
                return False

            self._interactive_layer_name = layer_obj.name_full
            self._last_generated_object_name = layer_obj.name_full
            self._last_stroke_vertex_indices = []
            if target_index in set(self._pending_edge_indices or []):
                self._clear_pending_path(context)
            self._action_history.append({
                "created_name": layer_obj.name_full,
                "deleted_backup": backup,
                "previous_pending": previous_pending,
                "previous_anchor": previous_anchor,
                "previous_last_name": layer_obj.name_full,
                "previous_last_stroke_vertices": previous_last_vertices,
            })
            return True

        if target_stroke is not None:
            candidates = list(target_stroke.get("edges", []))
            restricted_vertices = list(target_stroke.get("vertices", []))
        else:
            interactive_edges = {
                int(index)
                for stroke in strokes
                for index in stroke.get("edges", [])
            }
            base_raw = str(layer_obj.get("edge_decal_base_source_indices", ""))
            if base_raw:
                try:
                    candidates = [int(token) for token in base_raw.split(",") if token.strip()]
                except Exception:
                    candidates = [index for index in all_indices if index not in interactive_edges]
            else:
                candidates = [index for index in all_indices if index not in interactive_edges]
            restricted_vertices = None

        if not self._remove_source_edge_geometry_in_place(
            layer_obj,
            source_obj,
            target_index,
            candidates,
            restrict_vertex_indices=restricted_vertices,
        ):
            self._discard_object_backup(backup)
            return False

        updated_strokes = self._load_interactive_strokes(layer_obj.name_full)
        cleaned_strokes = []
        for stroke_position, stroke in enumerate(updated_strokes):
            edges = [int(index) for index in stroke.get("edges", [])]
            if (
                target_stroke is not None
                and stroke_position == target_stroke_position
            ):
                edges = [index for index in edges if index != target_index]
            if not edges:
                continue
            stroke["edges"] = edges
            cleaned_strokes.append(stroke)
        self._save_interactive_strokes(layer_obj.name_full, cleaned_strokes)

        # Multiple disjoint partials can share one source edge. Removing one
        # partial must not clear the edge ownership of its siblings; otherwise
        # their geometry remains visible but subsequent R-clicks cannot find it.
        remaining_interactive_edges = {
            int(index)
            for stroke in cleaned_strokes
            for index in stroke.get("edges", [])
        }
        base_raw = str(layer_obj.get("edge_decal_base_source_indices", ""))
        if base_raw:
            try:
                base_indices = {
                    int(token) for token in base_raw.split(",") if token.strip()
                }
            except (TypeError, ValueError):
                base_indices = set()
        else:
            base_indices = set()

        if target_stroke is None:
            base_indices.discard(target_index)
        layer_obj["edge_decal_base_source_indices"] = ",".join(
            str(index) for index in sorted(base_indices)
        )

        retained_edges = remaining_interactive_edges | base_indices
        remaining_indices = [
            index
            for index in all_indices
            if index != target_index or target_index in retained_edges
        ]
        set_stored_source_indices(layer_obj, remaining_indices)

        self._interactive_layer_name = layer_obj.name_full
        self._last_generated_object_name = layer_obj.name_full
        self._last_stroke_vertex_indices = []

        if target_index in set(self._pending_edge_indices or []):
            self._clear_pending_path(context)

        self._action_history.append({
            "created_name": layer_obj.name_full,
            "deleted_backup": backup,
            "previous_pending": previous_pending,
            "previous_anchor": previous_anchor,
            "previous_last_name": layer_obj.name_full,
            "previous_last_stroke_vertices": previous_last_vertices,
        })
        return True

    def _remove_interactive_stroke_by_edge(
        self,
        context,
        edge_index,
        record_history=True,
    ):
        decal_obj, stroke = self._find_interactive_stroke_by_edge(edge_index)

        # Automatic-generation edges do not have per-stroke vertex ranges.
        # Remove them from the stored base selection, then rebuild the same
        # decal object in place. Interactive strokes are preserved separately.
        if decal_obj is None or stroke is None:
            source_obj = self._source_object(context)
            target_index = int(edge_index)
            decal_obj = self._interactive_layer_object(context)
            if source_obj is None or decal_obj is None:
                return False

            data = decal_obj.edge_decal_object_settings
            all_indices = parsed_source_indices(data)
            if target_index not in all_indices:
                return False

            interactive_edges = {
                int(index)
                for entry in self._load_interactive_strokes(decal_obj.name_full)
                for index in entry.get("edges", [])
            }
            if target_index in interactive_edges:
                return False

            base_raw = decal_obj.get("edge_decal_base_source_indices", "")
            if base_raw:
                try:
                    base_indices = [
                        int(token) for token in base_raw.split(",") if token.strip()
                    ]
                except Exception:
                    base_indices = [index for index in all_indices if index not in interactive_edges]
            else:
                base_indices = [index for index in all_indices if index not in interactive_edges]

            if target_index not in base_indices:
                return False

            backup = self._make_object_backup(decal_obj.name_full)
            base_indices = [index for index in base_indices if index != target_index]
            combined = sorted(set(base_indices) | interactive_edges)
            decal_obj["edge_decal_base_source_indices"] = ",".join(
                str(index) for index in sorted(set(base_indices))
            )
            set_stored_source_indices(decal_obj, combined)

            previous_active = context.view_layer.objects.active
            for selected in list(context.selected_objects):
                selected.select_set(False)
            decal_obj.select_set(True)
            context.view_layer.objects.active = decal_obj
            try:
                result = bpy.ops.object.edge_decal_regenerate(
                    "EXEC_DEFAULT",
                    preview=False,
                )
            except RuntimeError:
                result = {"CANCELLED"}

            self._restore_working_mode(context)
            if "FINISHED" not in result:
                self._delete_generated_object(decal_obj.name_full)
                self._restore_object_backup(backup)
                return False

            self._action_history.append({
                "created_name": decal_obj.name_full,
                "deleted_backup": backup,
                "previous_pending": list(self._pending_edge_indices or []),
                "previous_anchor": self._path_anchor_edge_index,
                "previous_last_name": self._last_generated_object_name,
                "previous_last_stroke_vertices": list(self._last_stroke_vertex_indices or []),
            })
            self._last_generated_object_name = decal_obj.name_full
            if target_index in set(self._pending_edge_indices or []):
                self._clear_pending_path(context)
            return True

        object_name = decal_obj.name_full
        backup = self._make_object_backup(object_name)

        stroke_edges = [int(index) for index in stroke.get("edges", [])]
        self._remove_stroke_source_indices(object_name, stroke_edges)
        removed = self._remove_decal_geometry_for_source_edges(
            context,
            decal_obj,
            stroke_edges,
            candidate_edge_indices=stroke_edges,
            restrict_vertex_indices=stroke.get("vertices", []),
        )
        if not removed:
            self._remove_master_vertices(
                object_name,
                stroke.get("vertices", []),
            )
        self._remove_interactive_stroke_record(
            object_name,
            stroke_id=stroke.get("id", ""),
        )

        modified_name = object_name
        obj = bpy.data.objects.get(object_name)
        if obj is not None and obj.type == "MESH" and len(obj.data.polygons) == 0:
            self._delete_generated_object(object_name)

        previous_last_vertices = list(self._last_stroke_vertex_indices or [])
        if self._last_generated_object_name == object_name:
            self._last_stroke_vertex_indices = []

        if record_history:
            self._action_history.append({
                "created_name": modified_name,
                "deleted_backup": backup,
                "previous_pending": list(self._pending_edge_indices or []),
                "previous_anchor": self._path_anchor_edge_index,
                "previous_last_name": self._last_generated_object_name,
                "previous_last_stroke_vertices": previous_last_vertices,
            })
        else:
            self._discard_object_backup(backup)

        if edge_index in set(self._pending_edge_indices or []):
            self._clear_pending_path(context)

        if self._remove_mode:
            self._remove_components = self._collect_remove_components(context)
            self._hovered_remove_index = -1

        return True

    def _merge_new_decal_into_master(self, generated_name, vertex_count_before=None):
        def finalize_master_state(master_obj):
            source_obj = self._source_object(bpy.context)
            if source_obj is not None and master_obj is not None:
                settings = bpy.context.scene.edge_decal_settings
                apply_decal_normal_settings(
                    master_obj,
                    settings.normal_mode,
                    settings.normal_keep_sharp,
                    settings.normal_weight,
                    settings.normal_threshold,
                )
                ensure_decal_match_source_bevel(master_obj, source_obj)
                ensure_decal_finish_modifiers(
                    master_obj,
                    source_obj,
                    settings,
                )
                set_active_decal_layer(source_obj, master_obj)
                sync_fn = globals().get("sync_source_layer_ui")
                if sync_fn is not None:
                    sync_fn(source_obj, active_layer=master_obj)
            return source_obj

        generated = bpy.data.objects.get(generated_name) if generated_name else None
        if generated is not None:
            master = bpy.data.objects.get(self._interactive_layer_name)
            if master is None or master == generated:
                self._interactive_layer_name = generated.name_full
                self._last_generated_object_name = generated.name_full
                finalize_master_state(generated)
                return generated.name_full, list(range(len(generated.data.vertices)))

            start_vertex = len(master.data.vertices)
            master = merge_generated_decal_objects(master, generated)
            end_vertex = len(master.data.vertices)
            finalize_master_state(master)
            self._interactive_layer_name = master.name_full
            self._last_generated_object_name = master.name_full
            return master.name_full, list(range(start_vertex, end_vertex))

        master = bpy.data.objects.get(self._interactive_layer_name)
        if master is None:
            source_obj = self._source_object(bpy.context)
            if source_obj is not None:
                master = active_decal_layer_for_source(
                    source_obj,
                    include_locked=False,
                )
        if master is None:
            return "", []

        vertex_count_after = len(master.data.vertices)
        start_vertex = (
            int(vertex_count_before)
            if vertex_count_before is not None
            else vertex_count_after
        )
        start_vertex = max(0, min(start_vertex, vertex_count_after))
        finalize_master_state(master)
        self._interactive_layer_name = master.name_full
        self._last_generated_object_name = master.name_full
        if vertex_count_after > start_vertex:
            return master.name_full, list(range(start_vertex, vertex_count_after))
        return master.name_full, []

    def _finalize_interactive_partial_uvs(self, context, decal_obj):
        """Run the full UV pipeline on a partial transaction's final master.

        Partial clicks and Shift-scroll placement are first generated as a
        temporary object and then appended to the interactive layer. UV work
        performed on that temporary object cannot account for the topology and
        islands already present in the final master. This is why Apply UVs
        repaired those transactions: it operated after the merge. Mirror that
        timing automatically whenever the complete UV workflow is enabled.
        """
        if decal_obj is None or decal_obj.data is None or not decal_obj.data.polygons:
            return True, ""

        settings = context.scene.edge_decal_settings
        if settings.fast_geometry_only:
            return True, ""

        use_auto_uv_pins = bool(settings.auto_use_uv_pins)
        pins = (
            uv_pins_for_decal_layer_material(
                context.scene,
                decal_obj,
                fallback_material=(
                    (
                        settings.decal_material
                        or bpy.data.materials.get(DEFAULT_MATERIAL_NAME)
                    )
                    if getattr(settings, "use_material", True)
                    else None
                ),
            )
            if use_auto_uv_pins
            else []
        )
        if not settings.auto_unwrap_uvs and not pins:
            return True, ""

        source_obj = self._source_object(context)
        try:
            unwrap_generated_decal(
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
                False,
                settings.horizontal_randomize_amount,
                settings.seed,
                settings.uv_strip_padding,
            )

            if pins:
                apply_uv_pins_to_decal_objects(
                    [decal_obj],
                    pins,
                    settings.seed,
                )

            # Pin fitting may translate an island in U. Match normal generation
            # by applying the explicit random phase after the pin pass.
            if settings.randomize_horizontal_offset:
                randomize_decal_uv_islands_horizontally(
                    decal_obj,
                    settings.seed,
                    settings.uv_strip_padding,
                    settings.horizontal_randomize_amount,
                )

            decal_obj["edge_decal_last_uv_signature"] = (
                decal_uv_settings_signature(settings)
            )
            return True, ""
        except RuntimeError as error:
            return False, str(error)
        finally:
            self._restore_working_mode(context)

    def _collect_remove_components(self, context):
        source_obj = self._source_object(context)
        components = []
        if source_obj is None:
            return components

        for decal_obj in iter_generated_decals(source_obj=source_obj):
            mesh = decal_obj.data
            if not mesh.polygons:
                continue

            vertex_to_polygons = {}
            for polygon in mesh.polygons:
                for vertex_index in polygon.vertices:
                    vertex_to_polygons.setdefault(vertex_index, []).append(polygon.index)

            adjacency = {polygon.index: set() for polygon in mesh.polygons}
            for users in vertex_to_polygons.values():
                if len(users) < 2:
                    continue
                for polygon_index in users:
                    adjacency[polygon_index].update(
                        other for other in users if other != polygon_index
                    )

            unvisited = set(adjacency)
            while unvisited:
                start = unvisited.pop()
                stack = [start]
                polygon_indices = {start}

                while stack:
                    polygon_index = stack.pop()
                    for neighbor in adjacency[polygon_index]:
                        if neighbor in unvisited:
                            unvisited.remove(neighbor)
                            polygon_indices.add(neighbor)
                            stack.append(neighbor)

                vertex_indices = sorted({
                    vertex_index
                    for polygon_index in polygon_indices
                    for vertex_index in mesh.polygons[polygon_index].vertices
                })
                if not vertex_indices:
                    continue

                center = Vector((0.0, 0.0, 0.0))
                for vertex_index in vertex_indices:
                    center += decal_obj.matrix_world @ mesh.vertices[vertex_index].co
                center /= len(vertex_indices)

                components.append({
                    "object_name": decal_obj.name_full,
                    "vertices": vertex_indices,
                    "center": center,
                })

        return components

    def _project_remove_targets(self, context):
        targets = []
        if context.region is None or context.space_data is None:
            return targets
        for index, component in enumerate(self._remove_components or []):
            point_2d = view3d_utils.location_3d_to_region_2d(
                context.region,
                context.space_data.region_3d,
                component["center"],
            )
            if point_2d is not None:
                targets.append((index, point_2d))
        return targets

    def _update_remove_hover(self, context):
        mouse = Vector(self._mouse_region)
        best_index = -1
        best_distance = self._remove_target_radius + 8.0
        for index, point_2d in self._project_remove_targets(context):
            distance = (point_2d - mouse).length
            if distance < best_distance:
                best_distance = distance
                best_index = index
        self._hovered_remove_index = best_index

    def _draw_remove_target(self, shader, center, radius, color, width):
        vertices = []
        segments = 40
        for index in range(segments + 1):
            angle = 2.0 * pi * index / segments
            vertices.append((
                center.x + cos(angle) * radius,
                center.y + sin(angle) * radius,
            ))
        gpu.state.line_width_set(width)
        shader.uniform_float("color", color)
        batch_for_shader(shader, "LINE_STRIP", {"pos": vertices}).draw(shader)
        cross = (
            (center.x - radius * 0.45, center.y),
            (center.x + radius * 0.45, center.y),
            (center.x, center.y - radius * 0.45),
            (center.x, center.y + radius * 0.45),
        )
        batch_for_shader(shader, "LINES", {"pos": cross}).draw(shader)

    def _remove_component(self, context, component):
        obj = bpy.data.objects.get(component.get("object_name", ""))
        if obj is None or obj.type != "MESH":
            return False

        backup = self._make_object_backup(obj.name_full)
        bm = bmesh.new()
        try:
            bm.from_mesh(obj.data)
            bm.verts.ensure_lookup_table()
            vertices = [
                bm.verts[index]
                for index in component.get("vertices", [])
                if 0 <= index < len(bm.verts)
            ]
            if not vertices:
                self._discard_object_backup(backup)
                return False
            bmesh.ops.delete(bm, geom=vertices, context="VERTS")
            bm.to_mesh(obj.data)
            obj.data.update(calc_edges=True)
        finally:
            bm.free()

        modified_name = obj.name_full
        if len(obj.data.polygons) == 0:
            self._delete_generated_object(modified_name)

        self._action_history.append({
            "created_name": modified_name,
            "deleted_backup": backup,
            "previous_pending": list(self._pending_edge_indices or []),
            "previous_anchor": self._path_anchor_edge_index,
            "previous_last_name": self._last_generated_object_name,
            "previous_last_stroke_vertices": list(self._last_stroke_vertex_indices or []),
        })
        self._last_stroke_vertex_indices = []
        self._remove_components = self._collect_remove_components(context)
        self._hovered_remove_index = -1
        return True

    def _merge_all_generated_decals(self, context):
        source_obj = self._source_object(context)
        if source_obj is None:
            return ""

        decals = list(iter_generated_decals(source_obj=source_obj))
        if not decals:
            return ""

        decals.sort(key=lambda obj: int(obj.get("edge_decal_index", 0)))
        master = decals[0]
        combined_strokes = self._load_interactive_strokes(master.name_full)
        for decal_obj in decals[1:]:
            if decal_obj.name not in bpy.data.objects:
                continue
            combined_strokes.extend(self._load_interactive_strokes(decal_obj.name_full))
            master = merge_generated_decal_objects(master, decal_obj)

        self._last_generated_object_name = master.name_full
        self._save_interactive_strokes(master.name_full, combined_strokes)
        return master.name_full

    def _finish(self, context):
        global EDGEDECAL_INTERACTIVE_RUNNING
        EDGEDECAL_INTERACTIVE_RUNNING = False
        self._cleanup_action_history()

        if self._draw_handle is not None:
            try:
                bpy.types.SpaceView3D.draw_handler_remove(
                    self._draw_handle,
                    "WINDOW",
                )
            except Exception:
                pass
            self._draw_handle = None

        if self._remove_draw_handle is not None:
            try:
                bpy.types.SpaceView3D.draw_handler_remove(
                    self._remove_draw_handle,
                    "WINDOW",
                )
            except Exception:
                pass
            self._remove_draw_handle = None

        if self._help_draw_handle is not None:
            try:
                bpy.types.SpaceView3D.draw_handler_remove(
                    self._help_draw_handle,
                    "WINDOW",
                )
            except Exception:
                pass
            self._help_draw_handle = None

        if self._interactive_event_timer is not None:
            try:
                context.window_manager.event_timer_remove(
                    self._interactive_event_timer
                )
            except Exception:
                pass
            self._interactive_event_timer = None

        self._restore_working_mode(context)

        if context.area:
            context.area.tag_redraw()

    def _execute_generator(
        self,
        context,
        safe_fallback=False,
        force_connected=False,
        generate_selected_graph=False,
        slice_interval=None,
        face_width=None,
        merge_taper_start=False,
        merge_taper_end=False,
    ):
        self._sync_active_layer_from_scene(context)
        settings = context.scene.edge_decal_settings

        # A Shift-connected stroke bypasses optional turn-angle splitting. The
        # generator still enforces convex/concave surface-bend boundaries,
        # because joining those classes can fold the generated mesh.
        previous_use_edge_split = settings.use_edge_split
        if force_connected:
            settings.use_edge_split = False

        try:
            return bpy.ops.mesh.generate_edge_decal_strips(
                "EXEC_DEFAULT",
                face_width=(
                    max(MIN_FACE_WIDTH, float(face_width))
                    if face_width is not None
                    else settings.face_width
                ),
                randomize_face_width=settings.randomize_face_width,
                minimum_face_width=settings.minimum_face_width,
                maximum_face_width=settings.maximum_face_width,
                crevice_removal=(
                    0.0
                    if safe_fallback or force_connected
                    else settings.crevice_removal
                ),
                crevice_detection_mode=settings.crevice_detection_mode,
                crevice_ao_distance=settings.crevice_ao_distance,
                crevice_ao_samples=settings.crevice_ao_samples,
                remove_short_edges=(
                    False
                    if safe_fallback or force_connected
                    else settings.remove_short_edges
                ),
                minimum_edge_length=settings.minimum_edge_length,
                minimum_length_per_edge=False,
                # A single interactive click honours the global Decal Amount,
                # exactly like Generate Automatically: lowering it shortens the
                # clicked edge and tapers the sliced ends (when Taper Sliced
                # Ends is on). A Shift-connected run, a safe fallback, and a
                # Ctrl partial placement keep full length so the connection or
                # explicit slice controls the geometry instead.
                decal_amount=(
                    1.0
                    if (
                        safe_fallback
                        or force_connected
                        or slice_interval is not None
                    )
                    else settings.decal_amount
                ),
                edge_slice=settings.edge_slice,
                interactive_slice_start=(
                    slice_interval[0] if slice_interval else -1.0
                ),
                interactive_slice_end=(
                    slice_interval[1] if slice_interval else -1.0
                ),
                interactive_detect_endpoint_taper=True,
                interactive_force_endpoint_taper=self._endpoint_taper_enabled,
                interactive_merge_taper_start=bool(merge_taper_start),
                interactive_merge_taper_end=bool(merge_taper_end),
                interactive_skip_limited_dissolve=True,
                generate_selected_edge_graph=bool(generate_selected_graph),
                maximum_decal_length=(
                    0.0
                    if safe_fallback or force_connected
                    else settings.maximum_decal_length
                ),
                taper_sliced_ends=(
                    True
                    if slice_interval is not None
                    else (
                        False
                        if force_connected
                        else settings.taper_sliced_ends
                    )
                ),
                slice_taper_length=settings.slice_taper_length,
                # Pass the user's current corner-trim preference through unchanged.
                # The operator property defaults to True and its execute() writes
                # every property back into scene settings, so omitting these two
                # would force auto_trim_corner_ends ON on every interactive click.
                auto_trim_corner_ends=settings.auto_trim_corner_ends,
                corner_end_trim_multiplier=settings.corner_end_trim_multiplier,
                randomize_horizontal_offset=settings.randomize_horizontal_offset,
                horizontal_randomize_amount=settings.horizontal_randomize_amount,
                seed=settings.seed,
                uv_scale=settings.uv_scale,
                auto_face_width=settings.auto_face_width,
                auto_width_samples=settings.auto_width_samples,
                auto_width_clearance=settings.auto_width_clearance,
                clamp_edge_overlaps=settings.clamp_edge_overlaps,
                overlap_clearance=settings.overlap_clearance,
                use_face_loop_slide=settings.use_face_loop_slide,
                fast_geometry_only=settings.fast_geometry_only,
                add_weld_modifier=settings.add_weld_modifier,
                add_bevel_modifier=settings.add_bevel_modifier,
                surface_offset=settings.surface_offset,
            )
        finally:
            settings.use_edge_split = previous_use_edge_split

    def _select_edge_indices(self, source_obj, edge_indices):
        bm = bmesh.from_edit_mesh(source_obj.data)
        bm.edges.ensure_lookup_table()
        bm.verts.ensure_lookup_table()
        bm.faces.ensure_lookup_table()
        self._clear_edit_selection(source_obj)
        bm = bmesh.from_edit_mesh(source_obj.data)
        bm.edges.ensure_lookup_table()

        valid_count = 0
        for edge_index in edge_indices or []:
            if not (0 <= edge_index < len(bm.edges)):
                continue
            edge = bm.edges[edge_index]
            if edge.hide or len(edge.link_faces) != 2:
                continue
            edge.select = True
            for vertex in edge.verts:
                vertex.select = True
            valid_count += 1

        context = bpy.context
        context.tool_settings.mesh_select_mode = (False, True, False)
        bmesh.update_edit_mesh(
            source_obj.data,
            loop_triangles=False,
            destructive=False,
        )
        return valid_count

    def _new_generated_object_name(self, source_obj, existing_names):
        candidates = [
            obj
            for obj in iter_generated_decals(source_obj=source_obj)
            if obj.name_full not in existing_names
        ]
        if not candidates:
            return ""
        newest = max(
            candidates,
            key=lambda obj: int(obj.get("edge_decal_index", 0)),
        )
        return newest.name_full

    def _delete_generated_object(self, object_name):
        if not object_name:
            return
        obj = bpy.data.objects.get(object_name)
        if obj is None or not obj.get("edge_decal_generated"):
            return
        mesh = obj.data if obj.type == "MESH" else None
        bpy.data.objects.remove(obj, do_unlink=True)
        if mesh is not None and mesh.users == 0:
            bpy.data.meshes.remove(mesh)


    def _make_object_backup(self, object_name):
        """Create an unlinked deep copy for the interactive Ctrl+Z stack."""
        if not object_name:
            return None

        obj = bpy.data.objects.get(object_name)
        if obj is None or not obj.get("edge_decal_generated"):
            return None

        backup = obj.copy()
        if obj.data is not None:
            backup.data = obj.data.copy()

        backup["edge_decal_interactive_backup"] = True
        # Keep undo snapshots in bpy.data without letting the layer scanner
        # mistake them for user-facing generated decal layers.
        backup["edge_decal_generated"] = False
        backup.hide_viewport = True
        backup.hide_render = True

        return {
            "object": backup,
            "original_name": obj.name_full,
            "mesh_name": obj.data.name if obj.data is not None else "",
            "collection_names": [collection.name for collection in obj.users_collection],
            "matrix_world": obj.matrix_world.copy(),
            "parent_name": obj.parent.name_full if obj.parent is not None else "",
            "matrix_parent_inverse": obj.matrix_parent_inverse.copy(),
            "hide_viewport": obj.hide_viewport,
            "hide_render": obj.hide_render,
            "hide_set": obj.hide_get(),
        }

    def _discard_object_backup(self, backup_data):
        if not backup_data:
            return

        backup = backup_data.get("object")
        if backup is None:
            return

        try:
            backup_name = backup.name
            mesh = backup.data if backup.type == "MESH" else None
        except ReferenceError:
            return

        if backup_name in bpy.data.objects:
            bpy.data.objects.remove(backup, do_unlink=True)
        if mesh is not None and mesh.users == 0:
            bpy.data.meshes.remove(mesh)

    def _restore_object_backup(self, backup_data):
        if not backup_data:
            return ""

        backup = backup_data.get("object")
        if backup is None:
            return ""

        try:
            backup_name = backup.name
        except ReferenceError:
            return ""

        if backup_name not in bpy.data.objects:
            return ""

        desired_name = backup_data.get("original_name", backup_name)
        backup.name = desired_name
        if backup.data is not None and backup_data.get("mesh_name"):
            backup.data.name = backup_data["mesh_name"]

        linked = False
        for collection_name in backup_data.get("collection_names", []):
            collection = bpy.data.collections.get(collection_name)
            if collection is not None:
                collection.objects.link(backup)
                linked = True

        if not linked:
            collection = get_or_create_collection(bpy.context.scene)
            collection.objects.link(backup)

        parent_name = backup_data.get("parent_name", "")
        backup.parent = bpy.data.objects.get(parent_name) if parent_name else None
        backup.matrix_parent_inverse = backup_data.get(
            "matrix_parent_inverse",
            Matrix.Identity(4),
        )
        backup.matrix_world = backup_data.get("matrix_world", Matrix.Identity(4))
        backup.hide_viewport = backup_data.get("hide_viewport", False)
        backup.hide_render = backup_data.get("hide_render", False)
        backup.hide_set(backup_data.get("hide_set", False))

        backup["edge_decal_generated"] = True
        if "edge_decal_interactive_backup" in backup:
            del backup["edge_decal_interactive_backup"]

        return backup.name_full

    def _cleanup_action_history(self):
        for action in self._action_history or []:
            self._discard_object_backup(action.get("deleted_backup"))
        self._action_history = []

    def _undo_last_action(self, context):
        if not self._action_history:
            self.report({"INFO"}, "Nothing to undo in Interactive Generate")
            return False

        action = self._action_history.pop()
        backup = action.get("deleted_backup")
        created_name = action.get("created_name", "")

        if backup:
            original_name = backup.get("original_name", "")
            target_name = created_name or original_name
            if target_name and bpy.data.objects.get(target_name):
                self._delete_generated_object(target_name)
            restored_name = self._restore_object_backup(backup)
        elif created_name:
            self._delete_generated_object(created_name)
            restored_name = action.get("previous_last_name", "")
        else:
            restored_name = ""

        self._pending_edge_indices = list(
            action.get("previous_pending", [])
        )
        self._path_anchor_edge_index = action.get(
            "previous_anchor",
            -1,
        )
        self._last_generated_object_name = (
            restored_name
            or action.get("previous_last_name", "")
        )
        self._interactive_layer_name = self._last_generated_object_name
        self._last_stroke_vertex_indices = list(
            action.get("previous_last_stroke_vertices", [])
        )

        source_obj = self._source_object(context)
        restored_obj = bpy.data.objects.get(self._interactive_layer_name)
        if source_obj is not None:
            set_active_decal_layer(source_obj, restored_obj)

        self._refresh_pending_overlay(context)
        if self._remove_mode:
            self._remove_components = self._collect_remove_components(context)
            self._hovered_remove_index = -1
        else:
            self._update_hover(context)

        if context.area:
            context.area.tag_redraw()

        self.report({"INFO"}, "Undid last interactive generate/remove action")
        return True

    def _generate_from_edge_indices(
        self,
        context,
        edge_indices,
        force_connected=False,
        slice_interval=None,
        merge_taper_start=False,
        merge_taper_end=False,
    ):
        global EDGEDECAL_STANDALONE_GENERATION

        generate_selected_graph = self._interactive_selection_uses_graph(
            edge_indices,
            force_connected=force_connected,
            slice_interval=slice_interval,
        )

        source_obj = self._activate_source(context, edit_mode=True)
        if source_obj is None:
            return False, "Could not enter the source mesh temporarily", ""

        if self._select_edge_indices(source_obj, edge_indices) == 0:
            self._restore_working_mode(context)
            return False, "No valid manifold edges were selected", ""

        existing_names = {
            obj.name_full
            for obj in iter_generated_decals(source_obj=source_obj)
        }
        settings = context.scene.edge_decal_settings
        previous_replace = settings.replace_previous
        previous_standalone = EDGEDECAL_STANDALONE_GENERATION
        settings.replace_previous = False
        # Interactive mode owns the merge transaction, stroke bookkeeping,
        # backup, and undo history. Generate each click as a distinct object
        # first so the normal generator cannot mutate an empty/new layer shell
        # in place before the interactive operator records what was created.
        EDGEDECAL_STANDALONE_GENERATION = True

        try:
            try:
                result = self._execute_generator(
                    context,
                    safe_fallback=False,
                    force_connected=force_connected,
                    generate_selected_graph=generate_selected_graph,
                    slice_interval=slice_interval,
                    face_width=self._interactive_face_width,
                    merge_taper_start=merge_taper_start,
                    merge_taper_end=merge_taper_end,
                )
            except RuntimeError as error:
                result = {"CANCELLED"}
                first_error = str(error)
            else:
                first_error = ""

            if "FINISHED" not in result:
                source_obj = self._activate_source(context, edit_mode=True)
                if source_obj is not None and self._select_edge_indices(source_obj, edge_indices) > 0:
                    try:
                        result = self._execute_generator(
                            context,
                            safe_fallback=True,
                            force_connected=force_connected,
                            generate_selected_graph=generate_selected_graph,
                            slice_interval=slice_interval,
                            face_width=self._interactive_face_width,
                            merge_taper_start=merge_taper_start,
                            merge_taper_end=merge_taper_end,
                        )
                    except RuntimeError as error:
                        first_error = str(error)
                        result = {"CANCELLED"}

            generated_name = ""
            if "FINISHED" in result:
                source_obj = self._source_object(context)
                if source_obj is not None:
                    generated_name = self._new_generated_object_name(
                        source_obj,
                        existing_names,
                    )
        finally:
            settings.replace_previous = previous_replace
            EDGEDECAL_STANDALONE_GENERATION = previous_standalone

        self._restore_working_mode(context)

        if "FINISHED" in result:
            return True, "", generated_name

        return False, first_error or "Generator cancelled this edge or chain", ""

    @staticmethod
    def _interactive_selection_uses_graph(
        edge_indices,
        force_connected=False,
        slice_interval=None,
    ):
        """Use graph topology for every complete multi-edge placement.

        A first Alt edge-loop placement is not a merge, but it still contains
        multiple connected source edges and must not pass through the legacy
        per-chain builder. Partial slices remain on the slicing-aware path.
        """
        return full_edge_selection_uses_graph(
            edge_indices,
            force_connected=force_connected,
            slice_interval=slice_interval,
        )


    def _connected_target_edges(self, context):
        source_obj = self._source_object(context)
        if source_obj is None or self._hovered_edge_index < 0:
            return [], "Hover a valid manifold edge first"

        hovered_edges = list(
            self._hovered_edge_indices
            or [self._hovered_edge_index]
        )

        if not self._pending_edge_indices:
            return hovered_edges, ""

        combined = list(self._pending_edge_indices)
        seen = set(combined)

        path = list(self._shift_connection_path or [])
        if not path:
            anchor_edge = self._path_anchor_edge_index
            if anchor_edge < 0:
                anchor_edge = self._effective_path_anchor(source_obj)
            if anchor_edge >= 0:
                path = self._edge_path_between(
                    source_obj,
                    anchor_edge,
                    self._hovered_edge_index,
                )

        if path:
            for edge_index in path:
                edge_index = int(edge_index)
                if edge_index not in seen:
                    combined.append(edge_index)
                    seen.add(edge_index)
            # RULE 4: collinear / split sub-edges with decals that touch the path
            # may be skipped by pathfinding but still sit between the endpoints.
            path_touch_edges = list(combined)
            for _decal_obj, stroke in self._iter_interactive_stroke_records(context):
                stroke_edges = [
                    int(index) for index in stroke.get("edges", [])
                ]
                if not stroke_edges:
                    continue
                if not self._edge_groups_touch(
                    source_obj,
                    stroke_edges,
                    path_touch_edges,
                ):
                    continue
                for edge_index in stroke_edges:
                    if edge_index not in seen:
                        combined.append(edge_index)
                        seen.add(edge_index)
        else:
            for edge_index in hovered_edges:
                edge_index = int(edge_index)
                if edge_index not in seen:
                    combined.append(edge_index)
                    seen.add(edge_index)

        if len(combined) <= len(self._pending_edge_indices):
            return [], "Could not find a connected manifold path between those edges"

        return combined, ""


    def invoke(self, context, event):
        source_obj = (
            context.edit_object
            if context.mode == "EDIT_MESH"
            else edge_decal_context_source(context)
        )
        if source_obj is None:
            return {"CANCELLED"}
        ensure_source_decal_layers_ready(source_obj, context)
        sync_decal_bevel_from_source(
            source_obj,
            context.scene.edge_decal_settings,
        )
        global EDGEDECAL_INTERACTIVE_RUNNING
        EDGEDECAL_INTERACTIVE_RUNNING = True

        existing_master = active_decal_layer_for_source(
            source_obj,
            include_locked=False,
        )
        if existing_master is None:
            decals = sorted_decal_layers_for_source(source_obj)
            if decals:
                existing_master = decals[0]
                set_active_decal_layer(source_obj, existing_master)
        existing_master_name = (
            existing_master.name_full if existing_master is not None else ""
        )
        sync_fn = globals().get("sync_source_layer_ui")
        if sync_fn is not None:
            sync_fn(source_obj, active_layer=existing_master)

        self._source_object_name = source_obj.name
        self._started_in_edit_mode = context.mode == "EDIT_MESH"
        self._interactive_layer_name = existing_master_name
        self._alt_down = bool(event.alt)
        self._shift_down = bool(event.shift)
        self._ctrl_down = bool(event.ctrl)
        self._ctrl_slice_interval = None
        self._ctrl_fraction = 0.30
        self._ctrl_control_points = None
        self._ctrl_active_point = -1
        self._shift_preview_edge_indices = []
        self._shift_preview_edge_points = None
        self._shift_span_edges = 0.0
        self._shift_path_key = None
        self._shift_terminal_edge_index = -1
        self._mouse_region = (
            event.mouse_region_x,
            event.mouse_region_y,
        )
        self._hovered_edge_index = -1
        self._hovered_edge_indices = []
        self._hovered_edge_points = None
        self._pending_edge_indices = []
        self._pending_edge_points = None
        self._pending_partial_edge_index = -1
        self._pending_partial_fraction = 1.0
        self._path_anchor_edge_index = -1
        self._last_generated_object_name = existing_master_name
        self._last_stroke_vertex_indices = []
        self._width_drag_active = False
        self._width_drag_start_x = event.mouse_region_x
        self._interactive_face_width = max(
            MIN_FACE_WIDTH,
            float(context.scene.edge_decal_settings.face_width),
        )
        self._interactive_width_reference_size = source_mesh_max_dimension(
            source_obj
        )
        self._width_drag_start_value = self._interactive_face_width
        self._width_drag_current_value = self._interactive_face_width
        self._action_history = []
        self._remove_mode = False
        self._r_remove_down = False
        self._remove_components = []
        self._hovered_remove_index = -1
        self._endpoint_taper_enabled = False
        self._auto_merge_enabled = True
        self._show_help_overlay = False
        self._last_click_edge_index = -1
        self._last_click_time = 0.0
        self._clear_last_remove_click()
        self._consume_next_remove_double_click = False
        self._update_hover(context)
        self._update_shift_preview(context)

        self._draw_handle = bpy.types.SpaceView3D.draw_handler_add(
            self._draw_overlay,
            (context,),
            "WINDOW",
            "POST_VIEW",
        )
        self._remove_draw_handle = None
        self._help_draw_handle = bpy.types.SpaceView3D.draw_handler_add(
            self._draw_help_overlay,
            (context,),
            "WINDOW",
            "POST_PIXEL",
        )
        self._interactive_event_timer = context.window_manager.event_timer_add(
            0.03,
            window=context.window,
        )
        context.window_manager.modal_handler_add(self)

        if context.area:
            context.area.tag_redraw()

        self.report(
            {"INFO"},
            "Interactive: click add/edit • R+click remove • R+double-click connected • H shortcuts",
        )
        return {"RUNNING_MODAL"}

    def modal(self, context, event):
        if event.type == "TIMER":
            self._sync_active_layer_from_scene(context)

        source_obj = self._source_object(context)
        if (
            source_obj is None
            or context.area is None
            or context.area.type != "VIEW_3D"
        ):
            self._finish(context)
            return {"CANCELLED"}

        mouse_x = getattr(event, "mouse_x", None)
        mouse_y = getattr(event, "mouse_y", None)
        if event.type != "TIMER" and mouse_x is not None and mouse_y is not None:
            # Area/sidebar separators are not guaranteed to belong to a UI
            # region. Treat only the actual 3D viewport WINDOW region as tool
            # input so Blender keeps ownership of sidebar scrollbars and resize
            # borders (including their cursor state).
            over_viewport_window = any(
                region.type == "WINDOW"
                and region.x <= mouse_x < region.x + region.width
                and region.y <= mouse_y < region.y + region.height
                for region in context.area.regions
            )
            if not over_viewport_window:
                return {"PASS_THROUGH"}

        alt_changed = self._alt_down != bool(event.alt)
        shift_changed = self._shift_down != bool(event.shift)
        ctrl_changed = self._ctrl_down != bool(event.ctrl)
        self._alt_down = bool(event.alt)
        self._shift_down = bool(event.shift)
        self._ctrl_down = bool(event.ctrl)

        if (
            not self._remove_mode
            and event.type == "W"
            and event.value == "PRESS"
            and not self._width_drag_active
        ):
            self._width_drag_active = True
            self._width_drag_start_value = max(
                MIN_FACE_WIDTH,
                float(self._interactive_face_width),
            )
            self._width_drag_current_value = self._width_drag_start_value
            self.report(
                {"INFO"},
                f"Width: {self._width_drag_current_value:.4f} — use mouse wheel",
            )
            return {"RUNNING_MODAL"}

        if self._width_drag_active:
            if (
                event.type in {"WHEELUPMOUSE", "WHEELDOWNMOUSE"}
                and event.value == "PRESS"
            ):
                multiplier = 1.10 if event.type == "WHEELUPMOUSE" else (1.0 / 1.10)
                width = max(
                    MIN_FACE_WIDTH,
                    float(self._interactive_face_width) * multiplier,
                )
                self._set_interactive_face_width(context, width)
                self._width_drag_current_value = width
                self._update_hover(context)
                self._update_shift_preview(context)
                context.area.tag_redraw()
                self.report({"INFO"}, f"Width: {width:.4f}")
                return {"RUNNING_MODAL"}

            if event.type == "MOUSEMOVE":
                self._suppress_hover_until_mousemove = False
                self._mouse_region = (
                    event.mouse_region_x,
                    event.mouse_region_y,
                )
                self._update_hover(context)
                self._update_shift_preview(context)
                context.area.tag_redraw()
                return {"PASS_THROUGH"}

            if event.type == "W" and event.value == "RELEASE":
                self._width_drag_active = False
                self._set_interactive_face_width(
                    context,
                    self._width_drag_current_value,
                )
                self.report(
                    {"INFO"},
                    f"Width set to {self._width_drag_current_value:.4f}",
                )
                return {"RUNNING_MODAL"}

            if event.type == "ESC" and event.value == "PRESS":
                self._set_interactive_face_width(
                    context,
                    self._width_drag_start_value,
                )
                self._width_drag_current_value = self._width_drag_start_value
                self._width_drag_active = False
                self._update_hover(context)
                self._update_shift_preview(context)
                context.area.tag_redraw()
                self.report({"INFO"}, "Width adjustment cancelled")
                return {"RUNNING_MODAL"}

            return {"RUNNING_MODAL"}

        self._sync_active_layer_from_scene(context)

        if (
            event.type == "E"
            and event.value == "PRESS"
            and not event.ctrl
            and not event.alt
        ):
            self._endpoint_taper_enabled = not self._endpoint_taper_enabled
            state = "ON" if self._endpoint_taper_enabled else "OFF"
            self.report({"INFO"}, f"Endpoint taper: {state}")
            if context.area:
                context.area.tag_redraw()
            return {"RUNNING_MODAL"}

        if (
            event.type == "H"
            and event.value == "PRESS"
            and not event.ctrl
            and not event.alt
        ):
            self._show_help_overlay = not self._show_help_overlay
            if context.area:
                context.area.tag_redraw()
            return {"RUNNING_MODAL"}

        if (
            event.type == "F"
            and event.value == "PRESS"
            and not event.ctrl
            and not event.alt
        ):
            self._auto_merge_enabled = not self._auto_merge_enabled
            state = "ON" if self._auto_merge_enabled else "OFF"
            self.report({"INFO"}, f"Neighbor auto-merge: {state}")
            if context.area:
                context.area.tag_redraw()
            return {"RUNNING_MODAL"}

        if event.type == "MOUSEMOVE" or alt_changed or shift_changed or ctrl_changed:
            if event.type == "MOUSEMOVE":
                self._suppress_hover_until_mousemove = False
            self._mouse_region = (
                event.mouse_region_x,
                event.mouse_region_y,
            )
            self._update_hover(context)
            self._update_shift_preview(context)
            context.area.tag_redraw()
            if event.type == "MOUSEMOVE":
                # Hover has already been updated; let Blender also process the
                # move so a cursor set by a sidebar/area separator is restored
                # as soon as the pointer returns to the viewport.
                return {"PASS_THROUGH"}

        if (
            not self._remove_mode
            and self._ctrl_down
            and self._hovered_edge_index >= 0
            and event.type in {"WHEELUPMOUSE", "WHEELDOWNMOUSE"}
            and event.value == "PRESS"
        ):
            delta = 0.05 if event.type == "WHEELUPMOUSE" else -0.05
            self._ctrl_fraction = max(0.05, min(1.0, self._ctrl_fraction + delta))
            self._update_hover(context)
            self._update_shift_preview(context)
            context.area.tag_redraw()
            self.report(
                {"INFO"},
                f"Ctrl segment length: {self._ctrl_fraction * 100:.0f}%",
            )
            return {"RUNNING_MODAL"}

        if (
            not self._remove_mode
            and self._shift_down
            and not self._ctrl_down
            and self._hovered_edge_index >= 0
            and self._pending_edge_indices
            and event.type in {"WHEELUPMOUSE", "WHEELDOWNMOUSE"}
            and event.value == "PRESS"
        ):
            delta = 0.25 if event.type == "WHEELUPMOUSE" else -0.25
            self._shift_span_edges = max(0.05, self._shift_span_edges + delta)
            self._update_hover(context)
            self._update_shift_preview(context)
            context.area.tag_redraw()
            whole_edges = int(self._shift_span_edges)
            edge_fraction = self._shift_span_edges - whole_edges
            self.report(
                {"INFO"},
                f"Shortest path length: {whole_edges} edge(s) + {edge_fraction * 100:.0f}%",
            )
            return {"RUNNING_MODAL"}

        if event.type == "R" and not event.ctrl and not event.alt:
            if event.value == "PRESS":
                # Blender can emit repeated PRESS events while a key is held.
                # Only react to the first transition into remove mode.
                if not self._r_remove_down:
                    self._r_remove_down = True
                    self._remove_mode = True
                    self._clear_last_remove_click()
                    self._consume_next_remove_double_click = False
                    self._mouse_region = (
                        event.mouse_region_x,
                        event.mouse_region_y,
                    )
                    self._update_hover(context)
                    self.report(
                        {"INFO"},
                        "Remove mode: click an edge, or double-click its connected component",
                    )
                    context.area.tag_redraw()
            elif event.value == "RELEASE":
                if self._r_remove_down:
                    self._r_remove_down = False
                    self._remove_mode = False
                    self._clear_last_remove_click()
                    self._consume_next_remove_double_click = False
                    self._mouse_region = (
                        event.mouse_region_x,
                        event.mouse_region_y,
                    )
                    self._update_hover(context)
                    self._update_shift_preview(context)
                    context.area.tag_redraw()
            return {"RUNNING_MODAL"}

        if (
            event.type == "LEFTMOUSE"
            and event.value == "DOUBLE_CLICK"
            and self._r_remove_down
        ):
            if self._consume_next_remove_double_click:
                self._consume_next_remove_double_click = False
                return {"RUNNING_MODAL"}

            if self._remove_click_matches_last(context, event):
                self._expand_last_edge_removal(context)
                return {"RUNNING_MODAL"}
            else:
                self._mouse_region = (
                    event.mouse_region_x,
                    event.mouse_region_y,
                )
                self._update_hover(context)
                target_index = int(self._hovered_edge_index)

            if target_index < 0:
                self.report({"WARNING"}, "No generated edge under cursor")
                return {"RUNNING_MODAL"}

            self._commit_connected_edge_removal(context, target_index)
            return {"RUNNING_MODAL"}

        if (
            event.type == "LEFTMOUSE"
            and event.value == "PRESS"
            and self._r_remove_down
        ):
            if self._remove_click_matches_last(context, event):
                self._consume_next_remove_double_click = True
                self._expand_last_edge_removal(context)
                return {"RUNNING_MODAL"}

            self._mouse_region = (
                event.mouse_region_x,
                event.mouse_region_y,
            )
            self._update_hover(context)

            if self._hovered_edge_index < 0:
                self.report({"WARNING"}, "No generated edge under cursor")
                return {"RUNNING_MODAL"}

            target_index = int(self._hovered_edge_index)
            source_obj = self._source_object(context)
            layer_obj = bpy.data.objects.get(self._interactive_layer_name)
            connected_indices = self._connected_generated_edge_indices(
                source_obj,
                layer_obj,
                target_index,
            )
            history_size = len(self._action_history or [])
            if not self._remove_edge_from_active_layer(context, target_index):
                self._clear_last_remove_click()
                self.report(
                    {"WARNING"},
                    "That edge is not part of the selected decal layer",
                )
                return {"RUNNING_MODAL"}

            self._last_remove_click_edge_index = target_index
            self._last_remove_click_time = time.monotonic()
            self._last_remove_click_mouse_region = (
                event.mouse_region_x,
                event.mouse_region_y,
            )
            self._last_remove_connected_indices = set(connected_indices)
            self._last_remove_action = (
                self._action_history[-1]
                if len(self._action_history or []) > history_size
                else None
            )
            self.report({"INFO"}, "Removed edge")
            self._suppress_hover_until_mousemove = True
            self._hovered_edge_index = -1
            self._hovered_edge_indices = []
            self._hovered_edge_points = None

            if context.area:
                context.area.tag_redraw()
            return {"RUNNING_MODAL"}

        if event.type == "LEFTMOUSE" and event.value == "DOUBLE_CLICK":
            return {"RUNNING_MODAL"}

        if event.type == "LEFTMOUSE" and event.value == "PRESS":
            self._mouse_region = (
                event.mouse_region_x,
                event.mouse_region_y,
            )
            self._alt_down = bool(event.alt)
            self._shift_down = bool(event.shift)
            self._ctrl_down = bool(event.ctrl)

            # Keep the merge master reference valid before resolving edge state.
            # If the tracked layer object was renamed, deleted, or never set,
            # subsequent strokes would otherwise spawn a standalone decal
            # instead of merging into the active layer.
            self._ensure_interactive_master(context)

            self._update_hover(context)
            self._update_shift_preview(context)

            if self._hovered_edge_index < 0:
                return {"PASS_THROUGH"}

            hovered_edge_index = int(self._hovered_edge_index)
            now = time.monotonic()
            if (
                hovered_edge_index == self._last_click_edge_index
                and now - self._last_click_time < 0.35
            ):
                return {"RUNNING_MODAL"}

            if self._edge_belongs_to_other_layer(context, hovered_edge_index):
                owner = self._edge_owner_decal_layer(context, hovered_edge_index)
                source_obj = self._source_object(context)
                activate_fn = globals().get("activate_decal_layer")
                if owner is not None and source_obj is not None and activate_fn is not None:
                    activate_fn(
                        context,
                        source_obj,
                        owner,
                        select_source=False,
                        select_layer=True,
                    )
                    self._interactive_layer_name = owner.name_full
                    self._last_generated_object_name = owner.name_full
                    self._pending_edge_indices = []
                    self._path_anchor_edge_index = -1
                    self._pending_edge_points = None
                    self._pending_partial_edge_index = -1
                    self._pending_partial_fraction = 1.0
                    self._shift_preview_edge_indices = []
                    self._shift_preview_edge_points = None
                    self._shift_connection_path = []
                    self._last_stroke_vertex_indices = []
                    self.report(
                        {"INFO"},
                        f"Switched to {self._other_layer_label(owner)}",
                    )
                else:
                    self.report(
                        {"WARNING"},
                        "Could not switch to that edge's decal layer",
                    )
                    return {"RUNNING_MODAL"}

            click_edge_local_slice = None
            generator_slice_interval = None
            click_source = self._source_object(context)
            ctrl_partial_click = bool(event.ctrl and not event.shift)
            if ctrl_partial_click:
                click_edge_local_slice = self._ctrl_slice_interval
                if self._ctrl_slice_interval is not None:
                    generator_slice_interval = (
                        self._normalize_slice_interval_for_edges(
                            click_source,
                            [hovered_edge_index],
                            self._ctrl_slice_interval,
                            interval_space="edge_local",
                        )
                        if click_source is not None
                        else self._ctrl_slice_interval
                    )
                else:
                    self.report(
                        {"WARNING"},
                        "Ctrl partial preview unavailable — hover the edge again",
                    )
                    return {"RUNNING_MODAL"}

            (
                existing_interactive_obj,
                existing_strokes_on_edge,
            ) = self._find_interactive_strokes_by_edge(hovered_edge_index)
            existing_interactive_stroke = (
                existing_strokes_on_edge[0]
                if existing_strokes_on_edge
                else None
            )
            existing_partial_edge_coverage = any(
                (
                    coverage := self._stroke_edge_local_coverage(
                        click_source,
                        stroke,
                        hovered_edge_index,
                    )
                ) is not None
                and (
                    coverage[0] > EPSILON
                    or coverage[1] < 1.0 - EPSILON
                )
                for stroke in existing_strokes_on_edge
            )
            existing_automatic_obj = None

            mutation_target = (
                existing_interactive_obj
                or bpy.data.objects.get(self._last_generated_object_name)
            )
            old_generated_name = (
                mutation_target.name_full
                if mutation_target is not None
                else self._last_generated_object_name
            )
            previous_pending = list(self._pending_edge_indices or [])
            previous_anchor = self._path_anchor_edge_index
            previous_last_stroke_vertices = list(self._last_stroke_vertex_indices or [])
            deleted_backup = (
                self._make_object_backup(old_generated_name)
                if old_generated_name
                else None
            )

            conflicting_ctrl_strokes = []
            if ctrl_partial_click:
                new_edge_set = {hovered_edge_index}
                conflicting_ctrl_strokes = [
                    stroke
                    for stroke in existing_strokes_on_edge
                    if not self._partial_strokes_can_share_source_edge(
                        stroke,
                        new_edge_set,
                        click_edge_local_slice,
                        source_obj=click_source,
                    )
                ]

            replacing_ctrl_partial = bool(
                ctrl_partial_click
                and (
                    conflicting_ctrl_strokes
                    or self._edge_has_automatic_generated_stroke(
                        hovered_edge_index
                    )
                )
            )
            if replacing_ctrl_partial:
                targeted_strokes = bool(conflicting_ctrl_strokes) and all(
                    {
                        int(index)
                        for index in stroke.get("edges", [])
                    } == {hovered_edge_index}
                    for stroke in conflicting_ctrl_strokes
                )
                if targeted_strokes:
                    self._remove_specific_interactive_strokes(
                        context,
                        existing_interactive_obj,
                        conflicting_ctrl_strokes,
                    )
                else:
                    replace_stroke_vertices = sorted({
                        int(index)
                        for stroke in conflicting_ctrl_strokes
                        for index in stroke.get("vertices", [])
                    })
                    self._absorb_geometry_for_target_edges(
                        context,
                        [hovered_edge_index],
                        extra_vertex_indices=replace_stroke_vertices,
                        geometry_candidate_edges=[hovered_edge_index],
                        skip_promote=True,
                    )
                existing_interactive_obj = None
                existing_interactive_stroke = None

            # A plain or Ctrl click that lands next to one or more compatible
            # decal strokes merges the whole connected run into one continuous
            # strip. Partials may merge only through their full-width end; the
            # tapered tip remains an outer endpoint.
            auto_neighbor_merge = self._auto_neighbor_merge_allowed(event)
            click_merge_plan = None
            if auto_neighbor_merge:
                clicked_edge_indices = list(
                    self._hovered_edge_indices
                    or [self._hovered_edge_index]
                )
                click_merge_plan = self._plan_click_merge_group(
                    context,
                    self._hovered_edge_index,
                    clicked_edge_indices=clicked_edge_indices,
                    edge_local_slice_interval=click_edge_local_slice,
                )

            # RULE 5: E toggled + click an edge that is part of a multi-edge run
            # tapers that run end while keeping the run connected.
            retaper_plan = None
            if (
                self._endpoint_taper_enabled
                and not event.shift
                and not event.ctrl
                and click_merge_plan is None
                and existing_interactive_stroke is not None
                and len(existing_interactive_stroke.get("edges", [])) > 1
                and int(self._hovered_edge_index) in {
                    int(index)
                    for index in existing_interactive_stroke.get("edges", [])
                }
            ):
                stroke_edges = [
                    int(index)
                    for index in existing_interactive_stroke.get("edges", [])
                ]
                which_end = self._chain_end_for_edge(
                    context,
                    stroke_edges,
                    self._hovered_edge_index,
                )
                if which_end is not None:
                    retaper_plan = {
                        "target_edges": stroke_edges,
                        "taper_start": which_end == "start",
                        "taper_end": which_end == "end",
                    }

            merge_blocked_info = None
            if (
                auto_neighbor_merge
                and not ctrl_partial_click
                and click_merge_plan is None
                and retaper_plan is None
            ):
                source_obj = self._source_object(context)
                if source_obj is not None:
                    hovered = int(self._hovered_edge_index)
                    for _decal_obj, stroke in self._iter_neighbor_strokes_for_merge(
                        context,
                        [hovered],
                    ):
                        stroke_edges = [
                            int(index)
                            for index in stroke.get("edges", [])
                        ]
                        if not self._edges_share_vertex(
                            source_obj,
                            hovered,
                            stroke_edges,
                        ):
                            continue
                        if self._merge_connection_allowed(
                            source_obj,
                            [hovered],
                            stroke,
                            edge_local_slice_interval=click_edge_local_slice,
                        ):
                            break
                        merge_blocked_info = (
                            "Adjacent decal: merge only at the open/full end "
                            "(not the taper tip). Use the other Ctrl control "
                            "point or click the open end side."
                        )
                        break

            replacing_existing_edge = bool(
                not event.shift
                and not event.ctrl
                and click_merge_plan is None
                and retaper_plan is None
                and (
                    (
                        existing_interactive_stroke is not None
                        and (
                            len(existing_interactive_stroke.get("edges", [])) <= 1
                            or existing_partial_edge_coverage
                        )
                    )
                    or (
                        existing_interactive_stroke is None
                        and self._edge_has_automatic_generated_stroke(
                            self._hovered_edge_index
                        )
                    )
                )
            )

            # Re-clicking inside a multi-edge stroke that has no adjacent decal
            # to merge with is a no-op, so it never wipes its own siblings.
            if (
                not event.shift
                and not event.ctrl
                and click_merge_plan is None
                and retaper_plan is None
                and existing_interactive_stroke is not None
                and len(existing_interactive_stroke.get("edges", [])) > 1
                and not existing_partial_edge_coverage
                and int(self._hovered_edge_index) in {
                    int(index)
                    for index in existing_interactive_stroke.get("edges", [])
                }
            ):
                self._discard_object_backup(deleted_backup)
                if context.area:
                    context.area.tag_redraw()
                return {"RUNNING_MODAL"}

            if replacing_existing_edge and existing_interactive_stroke is None:
                existing_automatic_obj = self._automatic_decal_for_edge(
                    context,
                    self._hovered_edge_index,
                )

            if replacing_existing_edge:
                if existing_interactive_stroke is not None:
                    # A full-edge placement supersedes every partial interval
                    # on that source edge. Clear all edge-local geometry in one
                    # transaction; multi-edge stroke records are trimmed so
                    # their geometry on neighboring edges remains intact.
                    replace_vertices = sorted({
                        int(index)
                        for stroke in existing_strokes_on_edge
                        for index in stroke.get("vertices", [])
                    })
                    self._absorb_geometry_for_target_edges(
                        context,
                        [hovered_edge_index],
                        extra_vertex_indices=replace_vertices,
                        geometry_candidate_edges=[hovered_edge_index],
                        skip_promote=True,
                    )
                    existing_interactive_obj = None
                    existing_interactive_stroke = None
                else:
                    promoted_obj, promoted = (
                        self._promote_automatic_edge_to_interactive(
                            context,
                            self._hovered_edge_index,
                        )
                    )
                    if not promoted:
                        replacing_existing_edge = False
                    elif promoted_obj is not None:
                        old_generated_name = promoted_obj.name_full
                        self._last_generated_object_name = promoted_obj.name_full

            auto_connect_plan = None
            if (
                auto_neighbor_merge
                and not replacing_existing_edge
            ):
                auto_connect_plan = click_merge_plan
                if auto_connect_plan is None:
                    auto_connect_plan = (
                        self._plan_auto_connect_to_touching_stroke(
                            context,
                            list(self._hovered_edge_indices or []),
                        )
                    )
                if auto_connect_plan is None:
                    auto_connect_plan = self._plan_auto_connect_to_pending_neighbor(
                        context,
                        list(self._hovered_edge_indices or []),
                        edge_local_slice_interval=click_edge_local_slice,
                    )

            force_connected = bool(
                event.shift
                or auto_connect_plan is not None
                or retaper_plan is not None
            )

            merge_taper_start = False
            merge_taper_end = False
            pre_absorb_strokes = []
            absorbed_strokes = []
            preserve_stroke_ids = set()

            if force_connected:
                if event.shift:
                    target_edges, reason = self._connected_target_edges(context)
                    if not target_edges:
                        self._discard_object_backup(deleted_backup)
                        self.report({"WARNING"}, reason)
                        return {"RUNNING_MODAL"}
                    new_connection_edges = [
                        int(index)
                        for index in target_edges
                        if index not in set(previous_pending)
                    ]
                    partial_ok, partial_reason = (
                        self._shift_partial_merge_allowed(
                            context,
                            previous_pending,
                            new_connection_edges,
                        )
                    )
                    if not partial_ok:
                        self._discard_object_backup(deleted_backup)
                        self.report({"WARNING"}, partial_reason)
                        return {"RUNNING_MODAL"}
                elif retaper_plan is not None:
                    target_edges = list(retaper_plan["target_edges"])
                    reason = ""
                else:
                    target_edges = list(auto_connect_plan["target_edges"])
                    reason = ""

                target_strokes = self._collect_strokes_for_edges(
                    context,
                    target_edges,
                )
                planned_stroke_ids = {
                    str(value)
                    for value in (
                        auto_connect_plan.get("stroke_ids", [])
                        if auto_connect_plan is not None
                        else []
                    )
                }
                if planned_stroke_ids:
                    absorbed_strokes = [
                        stroke
                        for stroke in target_strokes
                        if str(stroke.get("id", "")) in planned_stroke_ids
                    ]
                    preserve_stroke_ids = {
                        str(stroke.get("id", ""))
                        for stroke in target_strokes
                        if str(stroke.get("id", "")) not in planned_stroke_ids
                    }
                else:
                    absorbed_strokes = list(target_strokes)
                pre_absorb_strokes = list(absorbed_strokes)

                # A newly clicked partial is not stored yet, so include a
                # synthetic stroke while deciding which outer endpoint keeps
                # its taper after the connected rebuild.
                if ctrl_partial_click and click_edge_local_slice is not None:
                    pre_absorb_strokes.append({
                        "edges": [int(self._hovered_edge_index)],
                        "edge_local_slice_interval": list(
                            click_edge_local_slice
                        ),
                        "edge_local_slice_edge_index": int(
                            self._hovered_edge_index
                        ),
                        "slice_interval": None,
                        "taper_vertices": [],
                    })

                atomic_component_rebuild = bool(
                    auto_connect_plan is not None
                    and auto_connect_plan.get("atomic_component_rebuild", False)
                    and not any(
                        self._stroke_is_partial_slice(stroke)
                        for stroke in pre_absorb_strokes
                    )
                )
                cleared_atomically = False
                if atomic_component_rebuild:
                    cleared_atomically = (
                        self._clear_active_layer_for_atomic_rebuild(
                            context,
                            target_edges,
                        )
                    )

                # A full connected layer component is cleared and replaced as
                # one transaction. Mixed/partial layers retain the targeted
                # removal path so unrelated or sliced decals stay untouched.
                removed_specific_strokes = False
                if planned_stroke_ids and absorbed_strokes:
                    removed_specific_strokes = (
                        self._remove_specific_interactive_strokes(
                            context,
                            self._interactive_layer_object(context),
                            absorbed_strokes,
                        )
                    )

                if removed_specific_strokes:
                    target_set = {
                        int(index) for index in target_edges
                    }
                elif cleared_atomically:
                    target_set = {
                        int(index) for index in target_edges
                    }
                else:
                    target_set = self._absorb_geometry_for_target_edges(
                        context,
                        target_edges,
                    )

                # Preserve the actual connection order. Sorting source indices can
                # scramble a path at junctions and make the generator see separate
                # chains even though the preview showed one connection.
                ordered_target_edges = []
                ordered_seen = set()
                order_source = list(previous_pending)
                if event.shift:
                    order_source += list(self._shift_connection_path or [])
                elif auto_connect_plan is not None:
                    order_source += list(auto_connect_plan.get("stroke_edges", []))
                    order_source += list(auto_connect_plan.get("path", []))
                order_source += list(target_edges)

                for edge_index in order_source:
                    edge_index = int(edge_index)
                    if edge_index in target_set and edge_index not in ordered_seen:
                        ordered_target_edges.append(edge_index)
                        ordered_seen.add(edge_index)
                for edge_index in target_set:
                    if edge_index not in ordered_seen:
                        ordered_target_edges.append(edge_index)
                        ordered_seen.add(edge_index)
                target_edges = ordered_target_edges
            else:
                target_edges = list(self._hovered_edge_indices or [])

            if event.shift:
                slice_interval = self._compute_shift_slice_interval(
                    context,
                    target_edges,
                    self._shift_connection_path,
                )
                if any(
                    self._stroke_is_partial_slice(stroke)
                    for stroke in pre_absorb_strokes
                ):
                    slice_interval = None
            elif auto_connect_plan is not None:
                # Bridge adjacent strokes into one continuous strip while
                # preserving the exact retained length of a terminal partial.
                slice_interval = self._partial_merge_chain_interval(
                    context,
                    target_edges,
                    pre_absorb_strokes,
                )
            else:
                slice_interval = (
                    generator_slice_interval
                    if (
                        event.ctrl
                        and len(target_edges) == 1
                    )
                    else None
                )

            if force_connected and slice_interval is None:
                merge_taper_start, merge_taper_end = (
                    self._compute_merge_endpoint_tapers(
                        context,
                        target_edges,
                        pre_absorb_strokes,
                    )
                )

            # RULE 5: force a taper on the run end the clicked edge belongs to,
            # while the rest of the run stays connected.
            if retaper_plan is not None:
                if retaper_plan.get("taper_start"):
                    merge_taper_start = True
                if retaper_plan.get("taper_end"):
                    merge_taper_end = True

            master_before = self._ensure_interactive_master(context)
            vertex_count_before = (
                len(master_before.data.vertices)
                if (
                    master_before is not None
                    and master_before.data is not None
                )
                else 0
            )

            success, reason, generated_name = self._generate_from_edge_indices(
                context,
                target_edges,
                force_connected=force_connected,
                slice_interval=slice_interval,
                merge_taper_start=merge_taper_start,
                merge_taper_end=merge_taper_end,
            )

            new_taper_vertices = self._compute_taper_tip_vertices(
                context,
                target_edges,
                slice_interval=slice_interval,
                merge_taper_start=merge_taper_start,
                merge_taper_end=merge_taper_end,
                force_all=(
                    self._endpoint_taper_enabled and slice_interval is None
                ),
            )
            if slice_interval is not None:
                partial_stroke = {
                    "edges": target_edges,
                    "slice_interval": list(slice_interval),
                    "taper_vertices": [],
                }
                source_obj = self._source_object(context)
                if source_obj is not None:
                    new_taper_vertices = sorted(
                        set(new_taper_vertices)
                        | self._stroke_taper_tip_vertices(
                            source_obj,
                            partial_stroke,
                        )
                    )

            if success:
                merged_name, new_stroke_vertices = self._merge_new_decal_into_master(
                    generated_name,
                    vertex_count_before=vertex_count_before,
                )
                if slice_interval is not None:
                    final_master = bpy.data.objects.get(
                        merged_name or generated_name
                    )
                    uv_success, uv_reason = (
                        self._finalize_interactive_partial_uvs(
                            context,
                            final_master,
                        )
                    )
                    if not uv_success:
                        if deleted_backup:
                            self._delete_generated_object(
                                merged_name or generated_name
                            )
                            restored_name = self._restore_object_backup(
                                deleted_backup
                            )
                            self._interactive_layer_name = (
                                restored_name or old_generated_name
                            )
                            self._last_generated_object_name = (
                                self._interactive_layer_name
                            )
                            self._last_stroke_vertex_indices = (
                                previous_last_stroke_vertices
                            )
                        self.report(
                            {"WARNING"},
                            f"Could not finalize partial UVs: {uv_reason}",
                        )
                        return {"RUNNING_MODAL"}
                self._action_history.append({
                    "created_name": merged_name or generated_name,
                    "deleted_backup": deleted_backup,
                    "previous_pending": previous_pending,
                    "previous_anchor": previous_anchor,
                    "previous_last_name": old_generated_name,
                    "previous_last_stroke_vertices": previous_last_stroke_vertices,
                })

                # An unmerged Ctrl partial-edge click is a standalone sliced
                # stroke. Do not store the full source edge as the pending Shift
                # path, otherwise the overlay highlights the entire edge after
                # the partial segment is generated.
                if slice_interval is not None and event.ctrl and not event.shift:
                    self._pending_edge_indices = []
                    self._path_anchor_edge_index = -1
                    self._pending_edge_points = None
                    self._pending_partial_edge_index = -1
                    self._pending_partial_fraction = 1.0
                else:
                    self._pending_edge_indices = list(target_edges)
                    if event.shift and self._shift_terminal_edge_index >= 0:
                        self._path_anchor_edge_index = self._shift_terminal_edge_index
                        self._pending_partial_edge_index = (
                            self._shift_terminal_edge_index
                            if self._shift_fraction < 1.0 - EPSILON
                            else -1
                        )
                        self._pending_partial_fraction = self._shift_fraction
                    elif auto_connect_plan is not None:
                        self._path_anchor_edge_index = int(
                            auto_connect_plan["anchor_edge"]
                        )
                        self._pending_partial_edge_index = -1
                        self._pending_partial_fraction = 1.0
                    else:
                        self._path_anchor_edge_index = self._hovered_edge_index
                        self._pending_partial_edge_index = -1
                        self._pending_partial_fraction = 1.0
                    self._refresh_pending_overlay(context)

                # Never leave the just-generated source edge highlighted under
                # a stationary cursor. Hover feedback resumes only after the
                # mouse moves, for normal, Ctrl, Shift, Alt, and rebuilt edges.
                self._suppress_hover_until_mousemove = True
                self._hovered_edge_index = -1
                self._hovered_edge_indices = []
                self._hovered_edge_points = None
                self._shift_preview_edge_indices = []
                self._shift_preview_edge_points = None
                self._shift_connection_path = []

                self._last_generated_object_name = merged_name or generated_name
                self._last_stroke_vertex_indices = list(new_stroke_vertices)
                self._register_interactive_stroke(
                    self._last_generated_object_name,
                    target_edges,
                    new_stroke_vertices,
                    force_connected=force_connected,
                    slice_interval=slice_interval,
                    face_width=self._interactive_face_width,
                    taper_vertices=new_taper_vertices,
                    edge_local_slice_interval=click_edge_local_slice,
                    edge_local_slice_edge_index=(
                        hovered_edge_index
                        if click_edge_local_slice is not None
                        else None
                    ),
                    preserve_stroke_ids=preserve_stroke_ids,
                )
                self._last_click_edge_index = hovered_edge_index
                self._last_click_time = time.monotonic()
                if auto_connect_plan is not None:
                    self.report({"INFO"}, "Merged adjacent decal strips")
                elif merge_blocked_info:
                    self.report({"INFO"}, merge_blocked_info)
            else:
                # Shift may have temporarily removed the last stroke from the
                # master. Restore the complete pre-click master on failure.
                if deleted_backup:
                    self._delete_generated_object(old_generated_name)
                    restored_name = self._restore_object_backup(deleted_backup)
                    self._last_generated_object_name = restored_name or old_generated_name
                    self._last_stroke_vertex_indices = previous_last_stroke_vertices
                self.report(
                    {"WARNING"},
                    f"Could not generate decal: {reason}",
                )

            if not self._suppress_hover_until_mousemove:
                self._update_hover(context)
                self._update_shift_preview(context)
            if context.area:
                context.area.tag_redraw()
            return {"RUNNING_MODAL"}

        if (
            event.type == "Z"
            and event.value == "PRESS"
            and (event.ctrl or event.oskey)
        ):
            self._undo_last_action(context)
            return {"RUNNING_MODAL"}

        if event.type in {"DEL", "X", "BACK_SPACE"} and event.value == "PRESS":
            if self._pending_edge_indices:
                self._clear_pending_path(context)
                self.report({"INFO"}, "Cleared shortest-path continuation")
                return {"RUNNING_MODAL"}

        if event.type == "RIGHTMOUSE" and event.value == "PRESS":
            self._finish(context)
            return {"FINISHED"}

        if (
            event.type in {"RET", "NUMPAD_ENTER", "ESC"}
            and event.value == "PRESS"
        ):
            self._finish(context)
            return {"FINISHED"}

        return {"PASS_THROUGH"}
