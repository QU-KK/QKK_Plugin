import bpy
import bmesh
import itertools
from bpy.utils import units
import math
from mathutils import Vector, Matrix
from .blender import preferences
from .collection import Collection
from .curve import Curve
from .export_scene import Export
from .image import Image
from .import_scene import Import
from .lattice import Lattice
from .material import Material
from .mesh import Mesh
from .modifier import Modifier
from .property import Property
from .scene import Scene


class Object(
    Collection,
    Curve,
    Export,
    Image,
    Import,
    Lattice,
    Material,
    Mesh,
    Modifier,
    Property,
    Scene,
):
    @staticmethod
    def apply_scale():
        bpy.ops.object.transform_apply(scale=True)

    @staticmethod
    def show_wire(context):
        context.object.show_wire = not context.object.show_wire

    @staticmethod
    def rename_object(object: bpy.types.Object, name: str):
        """
        Rename object.

        object (bpy.types.Object) - The object to rename.
        name (str) - The new name.
        """
        object.name = name
        if object.type in {"MESH", "ARMATURE"}:
            object.data.name = name

    @staticmethod
    def copy_object(object: bpy.types.Object, name: str, check: bool = True) -> bpy.types.Object:
        """
        Copy object with data.

        object (bpy.types.Object) - The object to copy.
        check (bool, optional) - Check if the object exists.
        return (bpy.types.Object) - The copied object.
        """
        if check:
            copied_object = bpy.data.objects.get(name)
            if not copied_object:
                copied_object = object.copy()
                mesh = object.data.copy()
                copied_object.data = mesh
                Object.rename_object(object=copied_object, name=name)
        else:
            copied_object = object.copy()
            mesh = object.data.copy()
            copied_object.data = mesh
            Object.rename_object(object=copied_object, name=name)
        return copied_object

    @staticmethod
    def parent_object(
        parent: bpy.types.Object,
        child: bpy.types.Object,
        copy_transform: bool = True,
        target: bpy.types.Object = None,
    ):
        """
        Parent object to another object.

        parent (bpy.types.Object) - The parent object.
        child (bpy.types.Object) - The object to parent.
        """
        child.parent = parent
        if copy_transform and parent:
            child.matrix_parent_inverse = target.matrix_world.inverted() if target else parent.matrix_world.inverted()

    @staticmethod
    def object_origin(object, origin):
        """
        Change object origin location.

        object (bpy.types.Object) - The object to change origin of.
        origin (3D Vector) - The location to change the origin to.
        """
        local_origin = object.matrix_world.inverted() @ origin
        object.data.transform(Matrix.Translation(-local_origin))
        object.matrix_world.translation += origin - object.matrix_world.translation

    @staticmethod
    def remove_object(object: bpy.types.Object):
        """
        Remove object.

        object (bpy.types.Object) - The object to remove.
        """
        if object.type in {"MESH"}:
            bpy.data.meshes.remove(object.data)
        else:
            bpy.data.objects.remove(object)

    @staticmethod
    def get_objects(type: str = None):
        """
        Get all objects of a type.

        type (enum in ['MESH', 'CURVE', 'SURFACE', 'META', 'FONT', 'CURVES', 'POINTCLOUD', 'VOLUME', 'GPENCIL', 'ARMATURE', 'LATTICE', 'EMPTY', 'LIGHT', 'LIGHT_PROBE', 'CAMERA', 'SPEAKER'], default 'MESH'') - The type of objects to get.
        return (list) - The objects of the type.
        """
        if type is None:
            type = {"MESH"}
        return [obj for obj in bpy.data.objects if obj.type in type]

    @staticmethod
    def link_object(
        object: bpy.types.Object,
        collection: bpy.types.Collection = None,
        unlink: bool = True,
    ):
        """Link object to collection.

        object (bpy.types.Object) - Object to link.
        collection (bpy.types.Collection) - Collection to link to.
        unlink (bool) - Unlink collection before link.
        """
        if unlink:
            Object.unlink_object(object)

        if collection:
            if not collection.objects.get(object.name):
                collection.objects.link(object)

        elif not bpy.context.scene.collection.objects.get(object.name):
            bpy.context.scene.collection.objects.link(object)

    @staticmethod
    def unlink_object(object: bpy.types.Object):
        """Unlink object from all collections.

        object (bpy.types.Object) - Object to unlink.
        """
        for col in object.users_collection:
            col.objects.unlink(object)

    @staticmethod
    def bound_to_diagonal(bound: list) -> Vector:
        """Returns the diagonal of the bounding box.

        bound (list of Vector) - List of vectors representing the bounding box.
        return (Vector) - Diagonal of the bounding box.
        """
        minimum = []
        maximum = []

        for i in range(len(bound[0])):
            var = [vec[i] for vec in bound]
            minimum.append(min(var))
            maximum.append(max(var))

        return Vector(minimum), Vector(maximum)

    @staticmethod
    def bound_to_point(object: bpy.types.Object, axis: str = "POS_X") -> Vector:
        """Returns the minimum and maximun points of the bounding box.

        object (bpy.types.Object) - Object to get the bounding box.
        axis (enum in ['POS_X', 'POS_Y', 'POS_Z', 'NEG_X', 'NEG_Y', 'NEG_Z'], default 'POS_X') - Axis to get the bounding box.
        return (Vector) - Minimum and maximun points of the bounding box.
        """
        location, rotation, scale = object.matrix_world.decompose()
        self.matrix_scale = Matrix.Translation(location) @ rotation.to_matrix().to_4x4()
        self.scale = Matrix.Diagonal((*scale, 1))
        self.bounds = [self.scale @ Vector(v) for v in object.bound_box]
        self.min_corner, self.max_corner = self.bound_to_diagonal(self.bounds)
        self.center = (self.min_corner + self.max_corner) / 2

        min = self.min_corner - self.center
        max = self.max_corner - self.center

        index = "XYZ".index(axis[-1])
        points = [min, max] if axis.startswith("POS") else [max, min]

        for vec, i in itertools.product(points, range(3)):
            if i != index:
                vec[i] = 0.0

        return points

    @staticmethod
    def maximum_dimension(object: bpy.types.Object) -> str:
        """Axis from maximum dimension of an object.

        object (bpy.types.Object) - Object to get the maximum dimension.
        return (str) - Maximum dimension axis.
        """
        if object.dimensions.x >= object.dimensions.y and object.dimensions.x >= object.dimensions.z:
            return "POS_X"
        elif object.dimensions.y >= object.dimensions.x and object.dimensions.y >= object.dimensions.z:
            return "POS_Y"
        elif object.dimensions.z >= object.dimensions.x and object.dimensions.z >= object.dimensions.y:
            return "POS_Z"
        else:
            return "POS_Z"

    @staticmethod
    def minimum_dimension(object: bpy.types.Object) -> str:
        """Axis from maximum dimension of an object.

        object (bpy.types.Object) - Object to get the maximum dimension.
        return (str) - Maximum dimension axis.
        """
        if object.dimensions.x <= object.dimensions.y and object.dimensions.x <= object.dimensions.z:
            return "POS_X"
        elif object.dimensions.y <= object.dimensions.x and object.dimensions.y <= object.dimensions.z:
            return "POS_Y"
        elif object.dimensions.z <= object.dimensions.x and object.dimensions.z <= object.dimensions.y:
            return "POS_Z"
        else:
            return "POS_Z"
