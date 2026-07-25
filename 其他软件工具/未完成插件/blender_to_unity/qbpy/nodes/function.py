import bpy
from mathutils import Vector


class FunctionNode:
    # Input
    @staticmethod
    def vector(
        group: bpy.types.NodeGroup,
        name: str,
        label: str = None,
        vector: Vector = None,
        position: Vector = Vector((0, 0)),
    ) -> bpy.types.Node:
        """Create a vector node.

        group (bpy.types.NodeGroup) - The node group to add the node to.
        name (str) - Unique node identifier.
        label (str, optional) - Optional custom node label.
        vector (3D Vector, optional) - The vector of the vector node.
        position (2D Vector, optional) - The position to insert the node in the node group.
        return (bpy.types.Node) - The vector node.
        """
        vector = group.nodes.get(name)
        if not vector:
            vector = group.nodes.new("FunctionNodeInputVector")
            vector.name = name
        if label is not None:
            vector.label = label
        if vector is not None:
            vector.vector[0] = vector[0]
            vector.vector[1] = vector[1]
            vector.vector[2] = vector[2]
        vector.location = position
        return vector

    # Utilities
    @staticmethod
    def align_euler_to_vector(
        group: bpy.types.NodeGroup,
        name: str,
        label: str = None,
        axis: str = None,
        pivot: str = None,
        factor: float = None,
        vector: Vector = None,
        position: Vector = Vector((0, 0)),
    ) -> bpy.types.Node:
        """Create an align euler to vector node.

        group (bpy.types.NodeGroup) - The node group to add the node to.
        name (str) - Unique node identifier.
        label (str, optional) - Optional custom node label.
        axis (str, optional) - The axis of the align euler to vector node.
        pivot (str, optional) - The pivot of the align euler to vector node.
        factor (float, optional) - The factor of the align euler to vector node.
        vector (3D Vector, optional) - The vector of the align euler to vector node.
        position (2D Vector, optional) - The position to insert the node in the node group.
        return (bpy.types.Node) - The align euler to vector node.
        """
        align_euler_to_vector = group.nodes.get(name)
        if not align_euler_to_vector:
            align_euler_to_vector = group.nodes.new("FunctionNodeAlignEulerToVector")
            align_euler_to_vector.name = name
        if label is not None:
            align_euler_to_vector.label = label
        if axis is not None:
            align_euler_to_vector.axis = axis
        if pivot is not None:
            align_euler_to_vector.pivot = pivot
        if factor is not None:
            align_euler_to_vector.inputs[1].default_value = factor
        if vector is not None:
            align_euler_to_vector.inputs[2].default_value[0] = vector[0]
            align_euler_to_vector.inputs[2].default_value[1] = vector[1]
            align_euler_to_vector.inputs[2].default_value[2] = vector[2]
        align_euler_to_vector.location = position
        return align_euler_to_vector

    @staticmethod
    def random_value(
        group: bpy.types.NodeGroup,
        name: str,
        label: str = None,
        type: str = None,
        min: list = None,
        max: list = None,
        probability: float = None,
        seed: int = None,
        position: Vector = Vector((0, 0)),
    ) -> bpy.types.Node:
        """Create a random value node.

        group (bpy.types.NodeGroup) - The node group to add the node to.
        name (str) - Unique node identifier.
        label (str, optional) - Optional custom node label.
        type (enum in ['FLOAT', 'INT', 'FLOAT_VECTOR', 'BOOLEAN'], default 'FLOAT') - The type of the random value node.
        min (list, optional) - The minimum value.
        max (list, optional) - The maximum value.
        probability (float, optional) - The probability.
        seed (int, optional) - The seed.
        position (2D Vector, optional) - The position to insert the node in the node group.
        return (bpy.types.Node) - The random value node.
        """
        random_value = group.nodes.get(name)
        if not random_value:
            random_value = group.nodes.new("FunctionNodeRandomValue")
            random_value.name = name
        if type is not None:
            random_value.data_type = type
        if label is not None:
            random_value.label = label
        if random_value.data_type in {"FLOAT"}:
            if min is not None:
                random_value.inputs[2].default_value = min[0]
            if max is not None:
                random_value.inputs[3].default_value = max[0]
        if random_value.data_type in {"INT"}:
            if min is not None:
                random_value.inputs[4].default_value = min[0]
            if max is not None:
                random_value.inputs[5].default_value = max[0]
        if random_value.data_type in {"FLOAT_VECTOR"}:
            if min is not None:
                random_value.inputs[0].default_value[0] = min[0]
                random_value.inputs[0].default_value[1] = min[1]
                random_value.inputs[0].default_value[2] = min[2]
            if max is not None:
                random_value.inputs[1].default_value[0] = max[0]
                random_value.inputs[1].default_value[1] = max[1]
                random_value.inputs[1].default_value[2] = max[2]
        if random_value.data_type in {"BOOLEAN"} and probability is not None:
            random_value.inputs[6].default_value = probability
        if seed is not None:
            random_value.inputs[8].default_value = seed
        random_value.location = position
        return random_value

    @staticmethod
    def rotate_euler(
        group: bpy.types.NodeGroup,
        name: str,
        label: str = None,
        type: str = None,
        space: str = None,
        axis: list = None,
        rotate: list = None,
        angle: float = None,
        position: Vector = Vector((0, 0)),
    ) -> bpy.types.Node:
        """Create a rotate eular node.

        group (bpy.types.NodeGroup) - The node group to add the node to.
        name (str) - Unique node identifier.
        label (str, optional) - Optional custom node label.
        type (enum in ['AXIS_ANGLE', 'EULAR'], default 'EULAR') - The type of the rotate eular node.
        space (enum in ['OBJECT', 'LOCAL'], default 'OBJECT') - The space of the rotate eular node.
        axis (list, optional) - The axis of the rotate eular node.
        rotate (list, optional) - The rotate eular.
        angle (float, optional) - The angle.
        position (2D Vector, optional) - The position to insert the node in the node group.
        return (bpy.types.Node) - The rotate eular node.
        """
        rotate_euler = group.nodes.get(name)
        if not rotate_euler:
            rotate_euler = group.nodes.new("FunctionNodeRotateEuler")
            rotate_euler.name = name
        if label is not None:
            rotate_euler.label = label
        if type is not None:
            rotate_euler.type = type
        if space is not None:
            rotate_euler.space = space
        if type == "EULER" and rotate is not None:
            rotate_euler.inputs[1].default_value[0] = rotate[0]
            rotate_euler.inputs[1].default_value[1] = rotate[1]
            rotate_euler.inputs[1].default_value[2] = rotate[2]
        if type == "AXIS_ANGLE":
            if axis is not None:
                rotate_euler.inputs[2].default_value[0] = axis[0]
                rotate_euler.inputs[2].default_value[1] = axis[1]
                rotate_euler.inputs[2].default_value[2] = axis[2]
            if angle is not None:
                rotate_euler.inputs[3].default_value = angle
        rotate_euler.location = position
        return rotate_euler
