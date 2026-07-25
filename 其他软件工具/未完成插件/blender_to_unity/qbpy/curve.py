import bpy
from math import radians, degrees
from mathutils import Vector, Matrix


class Curve:
    @staticmethod
    def curve(context, name="Curve", points=None, cuts=0, axis="POS_Y", check=True) -> bpy.types.Object:
        if check:
            curve = bpy.data.curves.get(name)
            if not curve:
                curve = bpy.data.curves.new(name, "CURVE")
            curve.use_path = False
            curve.use_stretch = True
            curve.use_deform_bounds = True
            curve.dimensions = "3D"

            curve_object = bpy.data.objects.get(name)
            if not curve_object:
                curve_object = bpy.data.objects.new(name, curve)
            curve_object.show_in_front = True
            self.link_object(object=curve_object, collecion=context.object.users_collection[0])
        else:
            curve = bpy.data.curves.new(name, "CURVE")
            curve.use_path = False
            curve.use_stretch = True
            curve.use_deform_bounds = True
            curve.dimensions = "3D"

            curve_object = bpy.data.objects.new(name, curve)
            curve_object.show_in_front = True
            self.link_object(object=curve_object, collecion=context.object.users_collection[0])
        Curve.spline(curve_object, points=Curve.subdivide(points, cuts=cuts), deform_axis=axis)

        return curve_object

    @staticmethod
    def spline(object, points, type="BEZIER", deform_axis="POS_Y", resolution_u=36, order_u=3):
        axis = {
            "POS_X": 0,
            "POS_Y": 90,
            "POS_Z": 180,
            "NEG_X": -90,
            "NEG_Y": 180,
            "NEG_Z": -90,
        }

        object.data.splines.clear()
        spline = object.data.splines.new(type)
        spline.use_endpoint_u = True
        count = len(points)
        tilt = radians(axis[deform_axis])
        spline.resolution_u = resolution_u

        if type == "BEZIER":
            spline.bezier_points.add(count - 1)
            handle_offset = ((points[-1] - points[0]) / count) * 0.5

            for point, vec in zip(spline.bezier_points, points):
                point.co = vec
                point.radius = 1
                point.tilt = tilt

                point.handle_left_type = "ALIGNED"
                point.handle_right_type = "ALIGNED"
                point.handle_right = vec + handle_offset
                point.handle_left = vec - handle_offset

        else:
            spline.points.add(count - 1)
            spline.order_u = order_u

            for point, vec in zip(spline.points, points):
                point.co[0] = vec[0]
                point.co[1] = vec[1]
                point.co[2] = vec[2]
                point.co[3] = 1
                point.radius = 1
                point.tilt = tilt

    @staticmethod
    def subdivide(point, cuts=0) -> list:
        direction = point[1] - point[0]
        divisor = 1 + cuts
        increment = direction * (1 / divisor)
        points = []
        for i in range(divisor + 1):
            vector = point[0] + (increment * i)
            points.append(vector)
        return points
