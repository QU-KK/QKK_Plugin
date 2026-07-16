import bpy
from mathutils import Vector


class GeometryNode:
    # Curve
    @staticmethod
    def resample_curve(
        group: bpy.types.NodeGroup,
        name: str,
        label: str = None,
        mode: str = None,
        count: int = None,
        length: float = None,
        position: Vector = Vector((0, 0)),
    ) -> bpy.types.Node:
        """Create a Resample Curve node.

        group (bpy.types.NodeGroup) - The node group to add the node to.
        name (str) - Unique node identifier.
        label (str, optional) - Optional custom node label.
        mode (enum in ['EVALUATED', 'COUNT', 'LENGTH'], default 'COUNT') - The mode of the resample curve node.
        count (int, optional) - The count of the resample curve node.
        length (float, optional) - The length of the resample curve node.
        position (2D Vector, optional) - The position to insert the node in the node group.
        return (bpy.types.Node) - The Resample Curve node.
        """
        node = group.nodes.get(name)
        if not node:
            node = group.nodes.new("GeometryNodeResampleCurve")
            node.name = name
        if label is not None:
            node.label = label
        if mode is not None:
            node.mode = mode
        if node.mode == "COUNT" and count is not None:
            node.count = count
        if node.mode == "LENGTH" and length is not None:
            node.length = length
        node.location = position
        return node

    @staticmethod
    def set_spline_cyclic(
        group: bpy.types.NodeGroup,
        name: str,
        label: str = None,
        cyclic: bool = False,
        position: Vector = Vector((0, 0)),
    ) -> bpy.types.Node:
        """Create a Set Spline Cyclic node.

        group (bpy.types.NodeGroup) - The node group to add the node to.
        name (str) - Unique node identifier.
        label (str, optional) - Optional custom node label.
        cyclic (bool, optional) - Set the spline to cyclic.
        position (2D Vector, optional) - The position to insert the node in the node group.
        return (bpy.types.Node) - The Set Spline Cyclic node.
        """
        node = group.nodes.get(name)
        if not node:
            node = group.nodes.new("GeometryNodeSetSplineCyclic")
            node.name = name
        if label is not None:
            node.label = label
        if cyclic is not None:
            node.inputs[2].default_value = cyclic
        node.location = position
        return node

    # Curve Primitives
    @staticmethod
    def curve_spiral(
        group: bpy.types.NodeGroup,
        name: str,
        label: str = None,
        resolution: int = None,
        rotation: float = None,
        start_radius: float = None,
        end_radius: float = None,
        height: float = None,
        reverse: bool = None,
        position: Vector = Vector((0, 0)),
    ) -> bpy.types.Node:
        """Create a Spiral Curve node.

        group (bpy.types.NodeGroup) - The node group to add the node to.
        name (str) - Unique node identifier.
        label (str, optional) - Optional custom node label.
        resolution (int, optional) - The resolution of the spiral curve.
        rotation (float, optional) - The rotation of the spiral curve.
        start_radius (float, optional) - The start radius of the spiral curve.
        end_radius (float, optional) - The end radius of the spiral curve.
        height (float, optional) - The height of the spiral curve.
        reverse (bool, optional) - Reverse the spiral curve.
        position (2D Vector, optional) - The position to insert the node in the node group.
        return (bpy.types.Node) - The Spiral Curve node.
        """
        node = group.nodes.get(name)
        if not node:
            node = group.nodes.new("GeometryNodeCurveSpiral")
            node.name = name
        if label is not None:
            node.label = label
        if resolution is not None:
            node.inputs[0].default_value = resolution
        if rotation is not None:
            node.inputs[1].default_value = rotation
        if start_radius is not None:
            node.inputs[2].default_value = start_radius
        if end_radius is not None:
            node.inputs[3].default_value = end_radius
        if height is not None:
            node.inputs[4].default_value = height
        if reverse is not None:
            node.inputs[5].default_value = reverse
        node.location = position
        return node

    # Geometry
    @staticmethod
    def set_position(
        group: bpy.types.NodeGroup,
        name: str,
        label: str = None,
        offset: Vector = None,
        position: Vector = Vector((0, 0)),
    ) -> bpy.types.Node:
        """Create a Set Position node.

        group (bpy.types.NodeGroup) - The node group to add the node to.
        name (str) - Unique node identifier.
        label (str, optional) - Optional custom node label.
        offset (3D Vector, optional) - The offset of the set position node.
        position (2D Vector, optional) - The position to insert the node in the node group.
        return (bpy.types.Node) - The Set Position node.
        """
        node = group.nodes.get(name)
        if not node:
            node = group.nodes.new("GeometryNodeSetPosition")
            node.name = name
        if label is not None:
            node.label = label
        if offset is not None:
            node.inputs[3].default_value[0] = offset[0]
            node.inputs[3].default_value[1] = offset[1]
            node.inputs[3].default_value[2] = offset[2]
        node.location = position
        return node

    @staticmethod
    def transform(
        group: bpy.types.NodeGroup,
        name: str,
        label: str = None,
        translation: Vector = None,
        rotation: Vector = None,
        scale: Vector = None,
        position: Vector = Vector((0, 0)),
    ) -> bpy.types.Node:
        """Create a Transform node.

        group (bpy.types.NodeGroup) - The node group to add the node to.
        name (str) - Unique node identifier.
        label (str, optional) - Optional custom node label.
        translation (3D Vector, optional) - The translation of the transform node.
        rotation (3D Vector, optional) - The rotation of the transform node.
        scale (3D Vector, optional) - The scale of the transform node.
        position (2D Vector, optional) - The position to insert the node in the node group.
        return (bpy.types.Node) - The Transform node.
        """
        node = group.nodes.get(name)
        if not node:
            node = group.nodes.new("GeometryNodeTransform")
            node.name = name
        if label is not None:
            node.label = label
        if translation is not None:
            node.inputs[1].default_value[0] = translation[0]
            node.inputs[1].default_value[1] = translation[1]
            node.inputs[1].default_value[2] = translation[2]
        if rotation is not None:
            node.inputs[2].default_value[0] = rotation[0]
            node.inputs[2].default_value[1] = rotation[1]
            node.inputs[2].default_value[2] = rotation[2]
        if scale is not None:
            node.inputs[3].default_value[0] = scale[0]
            node.inputs[3].default_value[1] = scale[1]
            node.inputs[3].default_value[2] = scale[2]
        node.location = position
        return node

    # Input
    @staticmethod
    def object_info(
        group: bpy.types.NodeGroup,
        name: str,
        label: str = None,
        transform_space: str = None,
        object: bpy.types.Object = None,
        as_instance: bool = False,
        position: Vector = Vector((0, 0)),
    ) -> bpy.types.Node:
        """Create an Object Info node.

        group (bpy.types.NodeGroup) - The node group to add the node to.
        name (str) - Unique node identifier.
        label (str, optional) - Optional custom node label.
        transform_space (str, optional) - The transform space of the object info node.
        object (bpy.types.Object) - The object to use.
        as_instance (bool, optional) - Use the object as an instance.
        position (2D Vector, optional) - The position to insert the node in the node group.
        return (bpy.types.Node) - The Object Info node.
        """
        node = group.nodes.get(name)
        if not node:
            node = group.nodes.new("GeometryNodeObjectInfo")
            node.name = name
        if label is not None:
            node.label = label
        if transform_space is not None:
            node.transform_space = transform_space
        if object is not None:
            node.inputs[0].default_value = object
        node.inputs[1].default_value = as_instance
        node.location = position
        return node

    @staticmethod
    def input_id(
        group: bpy.types.NodeGroup,
        name: str,
        label: str = None,
        position: Vector = Vector((0, 0)),
    ) -> bpy.types.Node:
        """Create an ID node.

        group (bpy.types.NodeGroup) - The node group to add the node to.
        name (str) - Unique node identifier.
        label (str, optional) - Optional custom node label.
        position (2D Vector, optional) - The position to insert the node in the node group.
        return (bpy.types.Node) - The ID node.
        """
        node = group.nodes.get(name)
        if not node:
            node = group.nodes.new("GeometryNodeInputID")
            node.name = name
        if label is not None:
            node.label = label
        node.location = position
        return node

    @staticmethod
    def input_position(
        group: bpy.types.NodeGroup,
        name: str,
        label: str = None,
        position: Vector = Vector((0, 0)),
    ) -> bpy.types.Node:
        """Create a Position node.

        group (bpy.types.NodeGroup) - The node group to add the node to.
        name (str) - The name of the position node.
        label (str, optional) - The label of the position node.
        position (2D Vector, optional) - The position to insert the node in the node group.
        return (bpy.types.Node) - The Position node.
        """
        node = group.nodes.get(name)
        if not node:
            node = group.nodes.new("GeometryNodeInputPosition")
            node.name = name
        if label is not None:
            node.label = label
        node.location = position
        return node

    # Instance

    def instance_on_points(
        group: bpy.types.NodeGroup,
        name: str,
        label: str = None,
        pick_instance: bool = False,
        rotation: float = None,
        scale: float = None,
        position: Vector = Vector((0, 0)),
    ) -> bpy.types.Node:
        """Create an Instance on Points node.

        group (bpy.types.NodeGroup) - The node group to add the node to.
        name (str) - Unique node identifier.
        label (str, optional) - Optional custom node label.
        pick_instance (bool, optional) - Pick an instance to use.
        rotation (float, optional) - The rotation of the instance on point node.
        scale (float, optional) - The scale of the instance on point node.
        position (2D Vector, optional) - The position to insert the node in the node group.
        return (bpy.types.Node) - The Instance on Points node.
        """
        node = group.nodes.get(name)
        if not node:
            node = group.nodes.new("GeometryNodeInstanceOnPoints")
            node.name = name
        if label is not None:
            node.label = label
        if rotation is not None:
            node.inputs[5].default_value = rotation
        if scale is not None:
            node.inputs[6].default_value = scale
        node.inputs[3].default_value = pick_instance
        node.location = position
        return node

    @staticmethod
    def realize_instances(
        group: bpy.types.NodeGroup,
        name: str,
        label: str = None,
        position: Vector = Vector((0, 0)),
    ) -> bpy.types.Node:
        """Create a realize instance node.

        group (bpy.types.NodeGroup) - The node group to add the node to.
        name (str) - Unique node identifier.
        label (str, optional) - Optional custom node label.
        position (2D Vector, optional) - The position to insert the node in the node group.
        return (bpy.types.Node) - The realize instance node.
        """
        node = group.nodes.get(name)
        if not node:
            node = group.nodes.new("GeometryNodeRealizeInstances")
            node.name = name
        if label is not None:
            node.label = label
        node.location = position
        return node

    # Mesh
    @staticmethod
    def mesh_to_curve(
        group: bpy.types.NodeGroup,
        name: str,
        label: str = None,
        position: Vector = Vector((0, 0)),
    ) -> bpy.types.Node:
        """Create a Mesh to Curve node.

        group (bpy.types.NodeGroup) - The node group to add the node to.
        name (str) - Unique node identifier.
        label (str, optional) - Optional custom node label.
        position (2D Vector, optional) - The position to insert the node in the node group.
        return (bpy.types.Node) - The Mesh to Curve node.
        """
        node = group.nodes.get(name)
        if not node:
            node = group.nodes.new("GeometryNodeMeshToCurve")
            node.name = name
        if label is not None:
            node.label = label
        node.location = position
        return node

    # Mesh Primitives
    @staticmethod
    def mesh_line(
        group: bpy.types.NodeGroup,
        name: str,
        label: str = None,
        mode: str = None,
        count_mode: str = None,
        count: int = None,
        resolution: float = None,
        start_location: Vector = None,
        end_location: Vector = None,
        offset: Vector = None,
        position: Vector = Vector((0, 0)),
    ) -> bpy.types.Node:
        """Create a Mesh Line node.

        group (bpy.types.NodeGroup) - The node group to add the node to.
        name (str) - Unique node identifier.
        label (str, optional) - Optional custom node label.
        mode (enum in ['OFFSET', 'END_POINTS'], default 'OFFSET') - The mode of the mesh line node.
        count_mode (enum in ['TOTAL', 'RESOLUTION'], default 'TOTAL') - The count mode of the mesh line node.
        count (int, optional) - The count of the mesh line node.
        resolution (float, optional) - The resolution of the mesh line node.
        start_location (3D Vector, optional) - The start location of the mesh line node.
        end_location (3D Vector, optional) - The end location of the mesh line node.
        offset (3D Vector, optional) - The offset of the mesh line node.
        position (2D Vector, optional) - The position to insert the node in the node group.
        return (bpy.types.Node) - The Mesh Line node.
        """
        node = group.nodes.get(name)
        if not node:
            node = group.nodes.new("GeometryNodeMeshLine")
            node.name = name
        if label is not None:
            node.label = label
        if mode is not None:
            node.mode = mode
        if count_mode is not None:
            node.count_mode = count_mode
        if node.count_mode == "TOTAL" and count is not None:
            node.inputs[0].default_value = count
        if node.count_mode == "RESOLUTION" and resolution is not None:
            node.inputs[0].default_value = resolution
        if node.mode == "OFFSET":
            if start_location is not None:
                node.inputs[2].default_value[0] = start_location[0]
                node.inputs[2].default_value[1] = start_location[1]
                node.inputs[2].default_value[2] = start_location[2]
            if offset is not None:
                node.inputs[3].default_value[0] = offset[0]
                node.inputs[3].default_value[1] = offset[1]
                node.inputs[3].default_value[2] = offset[2]
        if node.mode == "END_POINTS":
            if start_location is not None:
                node.inputs[2].default_value[0] = start_location[0]
                node.inputs[2].default_value[1] = start_location[1]
                node.inputs[2].default_value[2] = start_location[2]
            if end_location is not None:
                node.inputs[3].default_value[0] = end_location[0]
                node.inputs[3].default_value[1] = end_location[1]
                node.inputs[3].default_value[2] = end_location[2]
        node.location = position
        return node

    # Utilities
    @staticmethod
    def switch(
        group: bpy.types.NodeGroup,
        name: str,
        label: str = None,
        type: str = None,
        set_switch: bool = False,
        false: bpy.types.AnyType = None,
        true: bpy.types.AnyType = None,
        position: Vector = Vector((0, 0)),
    ) -> bpy.types.Node:
        """Create a Switch node.

        group (bpy.types.NodeGroup) - The node group to add the node to.
        name (str) - Unique node identifier.
        label (str, optional) - Optional custom node label.
        type (enum in ['FLOAT', 'INT', 'BOOLEAN', 'VECTOR', 'STRING', 'RGBA', 'OBJECT', 'IMAGE', 'GEOMETRY', 'COLLECTION', 'TEXTURE', 'MATERIAL'], default 'FLOAT') - The type of the switch node.
        set_switch (bool, optional) - Set the switch node.
        false (bpy.types.AnyType, optional) - The false value of the switch node.
        true (bpy.types.AnyType, optional) - The true value of the switch node.
        position (2D Vector, optional) - The position to insert the node in the node group.
        return (bpy.types.Node) - The Switch node.
        """
        node = group.nodes.get(name)
        if not node:
            node = group.nodes.new("GeometryNodeSwitch")
            node.name = name
        node.inputs[0].default_value = set_switch
        if label is not None:
            node.label = label
        if type is not None:
            node.input_type = type
        if node.input_type in {"FLOAT"}:
            if false is not None:
                node.inputs[2].default_value = false
            if true is not None:
                node.inputs[3].default_value = true
        if node.input_type in {"INT"}:
            if false is not None:
                node.inputs[4].default_value = false
            if true is not None:
                node.inputs[5].default_value = true
        if node.input_type in {"VECTOR"}:
            if false is not None:
                node.inputs[8].default_value[0] = false[0]
                node.inputs[8].default_value[1] = false[1]
                node.inputs[8].default_value[2] = false[2]
            if true is not None:
                node.inputs[9].default_value[0] = true[0]
                node.inputs[9].default_value[1] = true[1]
                node.inputs[9].default_value[2] = true[2]
        if node.input_type in {"RGBA"}:
            if false is not None:
                node.inputs[10].default_value = false
            if true is not None:
                node.inputs[11].default_value = true
        if node.input_type in {"STRING"}:
            if false is not None:
                node.inputs[12].default_value = false
            if true is not None:
                node.inputs[13].default_value = true
        if node.input_type in {"OBJECT"}:
            if false is not None:
                node.inputs[16].default_value = false
            if true is not None:
                node.inputs[17].default_value = true
        if node.input_type in {"COLLECTION"}:
            if false is not None:
                node.inputs[18].default_value = false
            if true is not None:
                node.inputs[19].default_value = true
        if node.input_type in {"TEXTURE"}:
            if false is not None:
                node.inputs[20].default_value = false
            if true is not None:
                node.inputs[21].default_value = true
        if node.input_type in {"MATERIAL"}:
            if false is not None:
                node.inputs[22].default_value = false
            if true is not None:
                node.inputs[23].default_value = true
        node.location = position
        return node
