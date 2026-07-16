# https://blender.stackexchange.com/a/288739?noredirect=1


import bpy
import gpu
from gpu_extras.batch import batch_for_shader
from mathutils.geometry import intersect_line_plane
from math import pi, cos, sin, floor, ceil, log10
from bpy_extras import view3d_utils
from gpu_extras.presets import draw_circle_2d
from mathutils import Vector


class Snap:
    def __init__(self):
        self.radius = 20
        self.steps = 12
        self.hit_location = None
        self.hit_object = None
        self.hit_grid = False

    def draw_callback_px(self, context):
        if self is None:
            print("self is None")
        color = (0, 0, 1, 1) if self.hit_grid else (0, 1, 0, 1)

        if self.hit_object or self.hit_grid:
            circle_loc = view3d_utils.location_3d_to_region_2d(self.region, self.rv3d, self.hit_location)
            if circle_loc is not None:
                gpu.state.line_width_set(4.0)
                draw_circle_2d(circle_loc, color, self.radius)

    # ray_cast adding the view point in the result
    def ray_cast(self, context, depsgraph, position):
        origin = view3d_utils.region_2d_to_origin_3d(self.region, self.rv3d, position)
        direction = view3d_utils.region_2d_to_vector_3d(self.region, self.rv3d, position)
        return *context.scene.ray_cast(depsgraph, origin, direction), origin

    # try to find the best hit point on the scene
    def best_hit(self, context, depsgraph, mouse_pos):
        # at first we raycast from the mouse position as it is
        result, location, normal, index, object, matrix, view_point = self.ray_cast(context, depsgraph, mouse_pos)
        if result:
            return result, location, index, object, view_point

        # but if we are near but outside the object surface, we need to inspect around the
        # mouse position and keep the closest location
        best_result = False
        best_index = index
        best_location = best_object = None
        best_distance = 0

        angle = 0
        delta_angle = 2 * pi / self.steps

        for _ in range(self.steps):
            pos = mouse_pos + self.radius * Vector((cos(angle), sin(angle)))
            result, location, normal, index, object, matrix, view_point = self.ray_cast(context, depsgraph, pos)

            if result and (best_object is None or (view_point - location).length < best_distance):
                best_ditance = (view_point - location).length
                best_result = True
                best_location = location
                best_index = index
                best_object = object
            angle += delta_angle

        return best_result, best_location, best_index, best_object, view_point

    def search_edge_pos(self, mouse, v1, v2, epsilon=0.0001):
        # dichotomic search for the nearest point along an edge, compare to the mouse position
        # not optimized, but easy to write... ;)
        while (v1 - v2).length > epsilon:
            v12D = view3d_utils.location_3d_to_region_2d(self.region, self.rv3d, v1)
            v22D = view3d_utils.location_3d_to_region_2d(self.region, self.rv3d, v2)
            if v12D is None:
                return v2
            if v22D is None:
                return v1
            if (v12D - mouse).length < (v22D - mouse).length:
                v2 = (v1 + v2) / 2
            else:
                v1 = (v1 + v2) / 2
        return v1

    def snap_to_geometry(self, context, vertices):
        # first snap to vertices
        # loop over vertices and keep the one which is closer once projected on screen
        snap_location = None
        best_distance = 0
        for co in vertices:
            co2D = view3d_utils.location_3d_to_region_2d(self.region, self.rv3d, co)
            if co2D is not None:
                distance = (co2D - self.mouse_pos).length
                if distance < self.radius and (snap_location is None or distance < best_distance):
                    snap_location = co
                    best_distance = distance

        if snap_location is not None:
            self.hit_location = snap_location
            return

        # then, if no vertex is found, try to snap to edges
        for co1, co2 in zip(vertices[1:] + vertices[:1], vertices):
            v = self.search_edge_pos(self.mouse_pos, co1, co2)
            v2D = view3d_utils.location_3d_to_region_2d(self.region, self.rv3d, v)
            if v2D is not None:
                distance = (v2D - self.mouse_pos).length
                if distance < self.radius and (snap_location is None or distance < best_distance):
                    snap_location = v
                    best_distance = distance

        if snap_location is not None:
            self.hit_location = snap_location
            return

    def snap_to_verts(self, context, data, vertices):
        # first snap to vertices
        # loop over vertices and keep the one which is closer once projected on screen
        snap_location = None
        vert_index = -1
        best_distance = 0
        for vert, co in vertices.items():
            co2D = view3d_utils.location_3d_to_region_2d(self.region, self.rv3d, co)
            if co2D is not None:
                distance = (co2D - self.mouse_pos).length
                if distance < self.radius and (snap_location is None or distance < best_distance):
                    snap_location = co
                    vert_index = vert.index
                    best_distance = distance

        if snap_location is not None:
            self.hit_location = snap_location
            self.vertex_index = vert_index
            return

        # then, if no vertex is found, try to snap to edges
        for co1, co2 in zip(
            list(vertices.values())[1:] + list(vertices.values())[:1],
            list(vertices.values()),
        ):
            v = self.search_edge_pos(self.mouse_pos, co1, co2)
            v2D = view3d_utils.location_3d_to_region_2d(self.region, self.rv3d, v)
            if v2D is not None:
                distance = (v2D - self.mouse_pos).length
                if distance < self.radius and (snap_location is None or distance < best_distance):
                    snap_location = v
                    best_distance = distance

        if snap_location is not None:
            self.hit_location = snap_location
            return

    def snap_to_object(self, context, depsgraph):
        # the object need to be evaluated (if modifiers, for instance)
        evaluated = self.hit_object.evaluated_get(depsgraph)
        data = evaluated.data if self.hit_object.modifiers else self.hit_object.data
        polygon = data.polygons[self.hit_face_index]
        matrix = evaluated.matrix_world

        # get evaluated vertices of the wanted polygon, in world coordinates
        vertices = {data.vertices[i]: matrix @ data.vertices[i].co for i in polygon.vertices}
        self.snap_to_verts(context, data, vertices)

    def floor_fit(self, v, scale):
        return floor(v / scale) * scale

    def ceil_fit(self, v, scale):
        return ceil(v / scale) * scale

    def snap_to_grid(self, context, ctrl):
        view_point = view3d_utils.region_2d_to_origin_3d(self.region, self.rv3d, self.mouse_pos)
        view_vector = view3d_utils.region_2d_to_vector_3d(self.region, self.rv3d, self.mouse_pos)
        norm = view_vector if self.rv3d.is_orthographic_side_view else Vector((0, 0, 1))

        # At which scale the grid is
        # (log10 is 1 for meters => 10 ** (1 - 1) = 1
        # (log10 is 0 for 10 centimeters => 10 ** (0 - 1) = 0.1
        scale = 10 ** (round(log10(self.rv3d.view_distance)) - 1)
        # ... to be improved with grid scale, subdivisions, etc.

        # here no ray cast, but intersection between the view line and the grid plane
        max_float = 1.0e38
        co = intersect_line_plane(view_point, view_point + max_float * view_vector, (0, 0, 0), norm)

        if co is not None:
            self.hit_grid = True
            if ctrl:
                # depending on the view angle, create the list of vertices for a plane around the hit point
                # which size is adapted to the view scale (view distance)
                if abs(norm.x) > 0:
                    vertices = [
                        Vector(
                            (
                                0,
                                self.floor_fit(co.y, scale),
                                self.floor_fit(co.z, scale),
                            )
                        ),
                        Vector((0, self.floor_fit(co.y, scale), self.ceil_fit(co.z, scale))),
                        Vector((0, self.ceil_fit(co.y, scale), self.ceil_fit(co.z, scale))),
                        Vector((0, self.ceil_fit(co.y, scale), self.floor_fit(co.z, scale))),
                    ]
                elif abs(norm.y) > 0:
                    vertices = [
                        Vector(
                            (
                                self.floor_fit(co.x, scale),
                                0,
                                self.floor_fit(co.z, scale),
                            )
                        ),
                        Vector((self.floor_fit(co.x, scale), 0, self.ceil_fit(co.z, scale))),
                        Vector((self.ceil_fit(co.x, scale), 0, self.ceil_fit(co.z, scale))),
                        Vector((self.ceil_fit(co.x, scale), 0, self.floor_fit(co.z, scale))),
                    ]
                else:
                    vertices = [
                        Vector(
                            (
                                self.floor_fit(co.x, scale),
                                self.floor_fit(co.y, scale),
                                0,
                            )
                        ),
                        Vector((self.floor_fit(co.x, scale), self.ceil_fit(co.y, scale), 0)),
                        Vector((self.ceil_fit(co.x, scale), self.ceil_fit(co.y, scale), 0)),
                        Vector((self.ceil_fit(co.x, scale), self.floor_fit(co.y, scale), 0)),
                    ]
                # and snap on this plane
                self.snap_to_geometry(context, vertices)

            # if no snap or out of snapping, keep the co
            if self.hit_location is None:
                # self.hit_location = Vector(co) # this was causing the grid issue
                self.hit_location = view3d_utils.region_2d_to_location_3d(self.region, self.rv3d, self.mouse_pos, depth_location=(0, 0, 0))

    def snap(self, context, event) -> Vector:
        self.region = context.region
        self.rv3d = context.region_data
        self.mouse_pos = Vector((event.mouse_region_x, event.mouse_region_y))

        depsgraph = context.evaluated_depsgraph_get()
        result, location, index, object, view_point = self.best_hit(context, depsgraph, self.mouse_pos)

        self.hit_location = location
        self.hit_face_index = index
        self.hit_object = object
        self.view_point = view_point
        self.vertex_index = -1

        if result and event.ctrl:
            self.snap_to_object(context, depsgraph)
        elif not result:
            self.snap_to_grid(context, event.ctrl)

        return {
            "hit_location": self.hit_location,
            "hit_object": self.hit_object,
            "vertex_index": self.vertex_index,
            "face_index": self.hit_face_index,
        }
