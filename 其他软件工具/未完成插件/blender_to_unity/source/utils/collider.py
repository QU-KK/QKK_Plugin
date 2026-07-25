import bpy
import bmesh
from ...qbpy.blender import preferences
from ...qbpy.object import Object
from ...qbpy.material import Material
from ...qbpy.modifier import Modifier
from ...qbpy.collection import Collection
import itertools
import math
from mathutils import Vector, Matrix
import numpy as np


class Collider:
    @classmethod
    def poll(cls, context):
        for obj in context.selected_objects:
            if obj.type != "MESH":
                return False
            return "LOD" not in obj.name.split("_")[-1] and "Collider" not in obj.name.split("_")[-1]

    def add_collision(self, context, mat_name, color):
        """Add a collision object to the selected objects.

        mat_name (str): Name of the material to use.
        color (RGBA): Color to use for the collision object.
        """
        unity = preferences().unity
        material = Material.get_material(name=mat_name, use_nodes=False)

        for object in context.selected_objects:
            if object != context.object:
                object.name = f"{context.object.name}_Collider"
                object.data.name = object.name
                Object.parent_object(parent=context.object, child=object)
                self.collision_object_color(object=object, material=material, color=color)

                if unity.object_collection:
                    collision_object_collection = Collection.get_collection(collection=context.object.name)
                    Collection.link_collection(collection=collision_object_collection)
                    Object.link_object(object=object, collection=collision_object_collection)
                else:
                    Object.link_object(object=object, collection=context.object.users_collection[0])

    def collision_object_color(self, object, material, color):
        """Set the color of the collision object.

        object (bpy.types.Object): The object to set the color of.
        material (bpy.types.Material): The material to set the color of.
        color (RGBA): The color to set the material to.
        """
        if object.data.materials:
            object.data.materials[0] = material
        else:
            object.data.materials.append(material)

        object.material_slots[0].material.diffuse_color = color

    def get_verts(self, object, modifier=False) -> list:
        """Get the verts of the object.

        object (bpy.types.Object): The object to get the verts from.
        modifier (bool): Whether to get the verts from the modifier or not.
        return (list): List of vertices.
        """
        mesh = object.data
        mesh.update()

        if object.mode == "EDIT":
            if modifier:
                depsgraph = bpy.context.evaluated_depsgraph_get()
                bm = bmesh.new()
                bm.from_object(object, depsgraph)
                bm.verts.ensure_lookup_table()
            else:
                bm = bmesh.from_edit_mesh(mesh)

            verts = [v for v in bm.verts if v.select]
            bm.free()

        elif modifier:
            depsgraph = bpy.context.evaluated_depsgraph_get()
            bm = bmesh.new()
            bm.from_object(object, depsgraph)
            bm.verts.ensure_lookup_table()
            verts = bm.verts
            bm.free()

        else:
            verts = mesh.vertices

        return verts

    def bounding_box(self, verts) -> list:
        """Create a bounding box from the given vertices.

        positions_x (list): list of x coordinates
        positions_y (list): list of y coordinates
        positions_z (list): list of z coordinates
        return (list): verts of bounding box
        """
        positions_x = []
        positions_y = []
        positions_z = []

        for vert in verts:
            positions_x.append(vert.co.x)
            positions_y.append(vert.co.y)
            positions_z.append(vert.co.z)

        coords = [
            Vector((max(positions_x), max(positions_y), min(positions_z))),
            Vector((max(positions_x), min(positions_y), min(positions_z))),
            Vector((min(positions_x), min(positions_y), min(positions_z))),
            Vector((min(positions_x), max(positions_y), min(positions_z))),
            Vector((max(positions_x), max(positions_y), max(positions_z))),
            Vector((max(positions_x), min(positions_y), max(positions_z))),
            Vector((min(positions_x), min(positions_y), max(positions_z))),
            Vector((min(positions_x), max(positions_y), max(positions_z))),
        ]

        dimensions = [
            abs(max(positions_x) - min(positions_x)),
            max(positions_y) - min(positions_y),
            abs(max(positions_z) - min(positions_z)),
        ]
        return {"coords": coords, "dimensions": dimensions}

    def hypothenuse(self, a, b) -> float:
        """Calculate the hypothenuse of two points.

        a (Vector): First point
        b (Vector): Second point
        return (float): Hypothenuse of the two points
        """
        return math.sqrt((a * 0.5) ** 2 + (b * 0.5) ** 2)

    def create_convex(self, name, object) -> bpy.types.Object:
        """Create a convex hull for the selected object.

        name (str): The name of the convex hull object.
        object (bpy.types.Object): The object to create the convex hull for.
        return (bpy.types.Object): Convex hull object.
        """
        if object.mode == "EDIT":
            bm = bmesh.from_edit_mesh(object.data).copy()
            if len([f for f in bm.faces if f.select]) >= 3:
                bmesh.ops.delete(bm, geom=[v for v in bm.verts if not v.select])
        else:
            bm = bmesh.new()
            bm.from_mesh(object.data)

        hull = bmesh.ops.convex_hull(bm, input=bm.verts, use_existing_faces=True)
        bmesh.ops.delete(bm, geom=hull["geom_interior"])

        mesh = bpy.data.meshes.new(name)
        bm.to_mesh(mesh)
        mesh.update()
        bm.free()

        convex = bpy.data.objects.new(name, mesh)
        Modifier.add_decimate_modifier(object=convex, angle_limit=5)
        Modifier.add_triangulate_modifier(object=convex)
        return convex

    # https://gist.github.com/iyadahmed/512883896348a7e06f7a43f3ea8580af

    def create_oriented_box(self, object, name) -> bpy.types.Object:
        """Create a oriented box object.

        object (bpy.types.Object): Object to create the oriented box from.
        name (str): Name of the object.
        return (bpy.types.Object): Oriented box created.
        """

        CUBE_FACE_INDICES = (
            (0, 1, 3, 2),
            (2, 3, 7, 6),
            (6, 7, 5, 4),
            (4, 5, 1, 0),
            (2, 6, 4, 0),
            (7, 3, 1, 5),
        )

        def gen_cube_verts():
            yield from itertools.product(range(-1, 2, 2), range(-1, 2, 2), range(-1, 2, 2))

        if object.mode == "EDIT":
            bm = bmesh.from_edit_mesh(object.data).copy()
            if [f for f in bm.faces if f.select]:
                bmesh.ops.delete(bm, geom=[v for v in bm.verts if not v.select])
        else:
            bm = bmesh.new()
            bm.from_mesh(object.data)

        chull_out = bmesh.ops.convex_hull(bm, input=bm.verts, use_existing_faces=False)
        chull_geom = chull_out["geom"]
        chull_points = np.array([bmelem.co for bmelem in chull_geom if isinstance(bmelem, bmesh.types.BMVert)])

        bases = []

        for elem in chull_geom:
            if not isinstance(elem, bmesh.types.BMFace):
                continue
            if len(elem.verts) != 3:
                continue

            face_normal = elem.normal
            if np.allclose(face_normal, 0, atol=0.00001):
                continue

            for e in elem.edges:
                v0, v1 = e.verts
                edge_vec = (v0.co - v1.co).normalized()
                co_tangent = face_normal.cross(edge_vec)
                basis = (edge_vec, co_tangent, face_normal)
                bases.append(basis)

        def rotating_calipers(hull_points: np.ndarray, bases):
            min_bb_basis = None
            min_bb_min = None
            min_bb_max = None
            min_vol = math.inf
            for basis in bases:
                rot_points = hull_points.dot(np.linalg.inv(basis))
                # Equivalent to: rot_points = hull_points.dot(np.linalg.inv(np.transpose(basis)).T)

                bb_min = rot_points.min(axis=0)
                bb_max = rot_points.max(axis=0)
                volume = (bb_max - bb_min).prod()
                if volume < min_vol:
                    min_bb_basis = basis
                    min_vol = volume

                    min_bb_min = bb_min
                    min_bb_max = bb_max

            return np.array(min_bb_basis), min_bb_max, min_bb_min

        bb_basis, bb_max, bb_min = rotating_calipers(chull_points, bases)
        bm.free()
        bb_basis_mat = bb_basis.T

        bb_dim = bb_max - bb_min
        bb_center = (bb_max + bb_min) / 2

        matrix = Matrix.Translation(bb_center.dot(bb_basis)) @ Matrix(bb_basis_mat).to_4x4() @ Matrix(np.identity(3) * bb_dim / 2).to_4x4()

        mesh = bpy.data.meshes.new(name)
        mesh.from_pydata(vertices=list(gen_cube_verts()), edges=[], faces=CUBE_FACE_INDICES)
        mesh.validate()
        mesh.transform(matrix)
        mesh.update()
        return bpy.data.objects.new(name, mesh)

    def create_box(self, object, name) -> bpy.types.Object:
        """Create a box object.

        name (str): Name of the object.
        object (bpy.types.Object): Object to create the box from.
        return (bpy.types.Object): Box.
        """
        faces = [
            (0, 1, 2, 3),
            (4, 7, 6, 5),
            (0, 4, 5, 1),
            (1, 5, 6, 2),
            (2, 6, 7, 3),
            (4, 0, 3, 7),
        ]

        if object.mode == "EDIT":
            bm = bmesh.from_edit_mesh(object.data).copy()
            if [f for f in bm.faces if f.select]:
                bmesh.ops.delete(bm, geom=[v for v in bm.verts if not v.select])
        else:
            bm = bmesh.new()
            bm.from_mesh(object.data)

        bound = self.bounding_box(verts=bm.verts)
        coords = bound["coords"]

        bmesh.ops.delete(bm, geom=list(bm.verts))

        for coord in coords:
            bm.verts.new(coord)

        bm.verts.ensure_lookup_table()
        for face in faces:
            bm.faces.new([bm.verts[i] for i in face])

        mesh = bpy.data.meshes.new(name)
        bm.to_mesh(mesh)
        mesh.update()
        bm.free()
        return bpy.data.objects.new(name, mesh)

    def create_single_box(self, context, name) -> bpy.types.Object:
        """Create a box object.

        name (str): Name of the object.
        object (bpy.types.Object): Object to create the box from.
        return (bpy.types.Object): Box.
        """
        faces = [
            (0, 1, 2, 3),
            (4, 7, 6, 5),
            (0, 4, 5, 1),
            (1, 5, 6, 2),
            (2, 6, 7, 3),
            (4, 0, 3, 7),
        ]

        bm = bmesh.new()

        for object in context.selected_objects:
            if object.type == "MESH" and "Collider" not in object.name:
                if object.mode == "EDIT":
                    tmp_mesh = bpy.data.meshes.new("temp")
                    temp_bm = bmesh.from_edit_mesh(object.data).copy()
                    if [f for f in temp_bm.faces if f.select]:
                        bmesh.ops.delete(temp_bm, geom=[v for v in temp_bm.verts if not v.select])
                    temp_bm.to_mesh(tmp_mesh)
                    tmp_mesh.update()
                    temp_bm.free()
                else:
                    tmp_mesh = object.data.copy()

                tmp_mesh.transform(object.matrix_world)
                bm.from_mesh(tmp_mesh)
                if tmp_mesh:
                    bpy.data.meshes.remove(tmp_mesh)

        bound = self.bounding_box(verts=bm.verts)
        coords = bound["coords"]
        bmesh.ops.delete(bm, geom=list(bm.verts))

        for coord in coords:
            bm.verts.new(coord)

        bm.verts.ensure_lookup_table()
        for face in faces:
            bm.faces.new([bm.verts[i] for i in face])

        mesh = bpy.data.meshes.new(name)
        bm.to_mesh(mesh)
        mesh.update()
        bm.free()
        return bpy.data.objects.new(name, mesh)

    def create_capsule(self, object, name) -> bpy.types.Object:
        """Create a capsule object.

        object (bpy.types.Object): Object to create the capsule from.
        name (str): Name of the object.
        return (bpy.types.Object): Capsule created.
        """
        if object.mode == "EDIT":
            bm = bmesh.from_edit_mesh(object.data).copy()
            if [f for f in bm.faces if f.select]:
                bmesh.ops.delete(bm, geom=[v for v in bm.verts if not v.select])
        else:
            bm = bmesh.new()
            bm.from_mesh(object.data)

        bound = self.bounding_box(verts=bm.verts)
        coords = bound["coords"]
        dimensions = bound["dimensions"]
        center = sum(coords, Vector()) / len(coords)
        bmesh.ops.delete(bm, geom=list(bm.verts))

        axis = Object.minimum_dimension(object=object)
        if axis == "POS_X":
            depth = dimensions[0]
            radius = dimensions[2] / 2
            rot_matrix = Matrix.Rotation(math.radians(90), 3, "Y")
        elif axis == "POS_Y":
            depth = dimensions[1]
            radius = dimensions[0] / 2
            rot_matrix = Matrix.Rotation(math.radians(90), 3, "X")
        else:
            depth = dimensions[2]
            radius = dimensions[1] / 2
            rot_matrix = Matrix.Rotation(math.radians(90), 3, "Z")

        bmesh.ops.create_uvsphere(bm, u_segments=8, v_segments=9, radius=radius)
        bm.verts.ensure_lookup_table()
        for vert in bm.verts:
            if vert.co[2] < 0:
                vert.co[2] -= depth / math.pi - radius / math.pi
            elif vert.co[2] > 0:
                vert.co[2] += depth / math.pi - radius / math.pi

        matrix = Matrix.LocRotScale(center, rot_matrix, None)
        bm.transform(matrix=matrix)

        mesh = bpy.data.meshes.new(name)
        bm.to_mesh(mesh)
        mesh.update()
        bm.free()
        return bpy.data.objects.new(name, mesh)

    def create_cylinder(self, object, name, segments) -> bpy.types.Object:
        """Create a cylinder object.

        name (str): Name of the object.
        object (bpy.types.Object): Object to create the cylinder from.
        return (bpy.types.Object): Cylinder created.
        """
        if object.mode == "EDIT":
            bm = bmesh.from_edit_mesh(object.data).copy()
            if [f for f in bm.faces if f.select]:
                verts = [v for v in bm.verts if v.select]
                bmesh.ops.delete(bm, geom=[v for v in bm.verts if not v.select])
        else:
            bm = bmesh.new()
            bm.from_mesh(object.data)

        bound = self.bounding_box(verts=bm.verts)
        coords = bound["coords"]
        dimensions = bound["dimensions"]
        bmesh.ops.delete(bm, geom=list(bm.verts))

        axis = Object.minimum_dimension(object=object)
        if axis == "POS_X":
            depth = dimensions[0]
            radius = dimensions[2] / 2
            rot_matrix = Matrix.Rotation(math.radians(90), 3, "Y")
        elif axis == "POS_Y":
            depth = dimensions[1]
            radius = dimensions[0] / 2
            rot_matrix = Matrix.Rotation(math.radians(90), 3, "X")
        else:
            depth = dimensions[2]
            radius = dimensions[1] / 2
            rot_matrix = Matrix.Rotation(math.radians(90), 3, "Z")

        center = sum(coords, Vector()) / len(coords)
        matrix = Matrix.LocRotScale(center, rot_matrix, None)
        bmesh.ops.create_cone(
            bm,
            cap_ends=True,
            cap_tris=False,
            segments=segments,
            radius1=radius,
            radius2=radius,
            depth=depth,
            matrix=matrix,
        )

        mesh = bpy.data.meshes.new(name)
        bm.to_mesh(mesh)
        mesh.update()
        bm.free()

        cylinder = bpy.data.objects.new(name, mesh)
        Modifier.add_triangulate_modifier(object=cylinder)
        return cylinder

    def calculate_bounding_sphere(self, object, verts):
        def distance_vec(point1: Vector, point2: Vector):
            """Calculate distance between two points."""
            return (point2 - point1).length

        def midpoint(p1, p2):
            return (p1 + p2) * 0.5

        # Get verts wit min and may values
        for i, vertex in enumerate(verts):
            # convert to global space
            v = object.matrix_world @ vertex.co

            # ignore 1. point since it's already saved
            if i == 0:
                min_x = v
                max_x = v
                min_y = v
                max_y = v
                min_z = v
                max_z = v

            # compare points to previous min and max
            # v.co returns mathutils.Vector
            else:
                min_x = v if v.x < min_x.x else min_x
                max_x = v if v.x > max_x.x else max_x
                min_y = v if v.y < min_y.y else min_y
                max_y = v if v.y > max_y.y else max_y
                min_z = v if v.z < min_z.z else min_z
                max_z = v if v.z > max_z.z else max_z

        # calculate distances between min and max of every axis
        dx = distance_vec(min_x, max_x)
        dy = distance_vec(min_y, max_y)
        dz = distance_vec(min_z, max_z)

        mid_point = None
        radius = None

        # Generate sphere for biggest distance
        if dx >= dy and dx >= dz:
            mid_point = midpoint(min_x, max_x)
            radius = dx / 2

        elif dy >= dz:
            mid_point = midpoint(min_y, max_y)
            radius = dy / 2

        else:
            mid_point = midpoint(min_z, max_z)
            radius = dz / 2

        # second pass
        for vertex in verts:
            # convert to global space
            v = object.matrix_world @ vertex.co

            # calculate distance to center to find out if the point is in or outside the sphere
            distance_center_to_v = distance_vec(mid_point, v)

            # point is outside the collision sphere
            if distance_center_to_v > radius:
                radius = (radius + distance_center_to_v) / 2
                old_to_new = distance_center_to_v - radius

                # calculate new_midpoint
                mid_point = (mid_point * radius + v * old_to_new) / distance_center_to_v

        return mid_point, radius

    def create_sphere(self, object, name) -> bpy.types.Object:
        """Create a sphere object.

        object (bpy.types.Object): Object to create the sphere from.
        name (str): Name of the object.
        return (bpy.types.Object): Sphere created.
        """
        if object.mode == "EDIT":
            bm = bmesh.from_edit_mesh(object.data).copy()
            if len([f for f in bm.faces if f.select]) >= 1:
                bmesh.ops.delete(bm, geom=[v for v in bm.verts if not v.select])
        else:
            bm = bmesh.new()
            bm.from_mesh(object.data)

        center, radius = self.calculate_bounding_sphere(object=object, verts=bm.verts)
        bmesh.ops.delete(bm, geom=list(bm.verts))

        matrix = Matrix.Translation(center)
        bmesh.ops.create_uvsphere(bm, u_segments=8, v_segments=8, radius=radius, matrix=matrix)

        mesh = bpy.data.meshes.new(name)
        bm.to_mesh(mesh)
        mesh.update()
        bm.free()
        return bpy.data.objects.new(name, mesh)

    # def create_sphere(self, object, name) -> bpy.types.Object:
    #     ''' Create a sphere object.

    #     object (bpy.types.Object): Object to create the sphere from.
    #     name (str): Name of the object.
    #     return (bpy.types.Object): Sphere created.
    #     '''
    #     if object.mode == 'EDIT':
    #         bm = bmesh.from_edit_mesh(object.data).copy()
    #         if len([f for f in bm.faces if f.select]) >= 1:
    #             bmesh.ops.delete(bm, geom=[v for v in bm.verts if not v.select])
    #     else:
    #         bm = bmesh.new()
    #         bm.from_mesh(object.data)

    #     bound = self.bounding_box(verts=bm.verts)
    #     coords = bound['coords']
    #     center = sum(coords, Vector()) / len(coords)
    #     bmesh.ops.delete(bm, geom=[v for v in bm.verts])

    #     def vsub(a, b):
    #         return (a[0] - b[0], a[1] - b[1], a[2] - b[2])
    #     def vlen(v):
    #         return math.sqrt(v[0] * v[0] + v[1] * v[1] + v[2] * v[2])

    #     l1 = vlen(vsub(coords[0], coords[1]))
    #     l2 = vlen(vsub(coords[0], coords[3]))
    #     l3 = vlen(vsub(coords[0], coords[4]))

    #     radius = math.sqrt(l1 * l1 + l2 * l2 + l3 * l3) / math.pi
    #     matrix = Matrix.Translation(center)
    #     bmesh.ops.create_uvsphere(bm, u_segments=8, v_segments=8, radius=radius, matrix=matrix)

    #     mesh = bpy.data.meshes.new(name)
    #     bm.to_mesh(mesh)
    #     mesh.update()
    #     bm.free()
    #     return bpy.data.objects.new(name, mesh)
