import bpy
from mathutils import Vector
from .geomerty import GeometryNode
from .function import FunctionNode
from .shader import ShaderNode


def check(context):
    space = context.space_data
    valid_trees = [
        "ShaderNodeTree",
        "CompositorNodeTree",
        "TextureNodeTree",
        "GeometryNodeTree",
    ]

    return space.type == "NODE_EDITOR" and space.node_tree is not None and space.tree_type in valid_trees


class Node(GeometryNode, FunctionNode, ShaderNode):
    @classmethod
    def poll(cls, context):
        return check(context)

    def group(self, name: str, type: str = "GEOMETRY") -> bpy.types.NodeGroup:
        """Create a node group.

        name (str) - The name of the node group.
        type (str, optional) - The type of the node group.
        return (bpy.types.NodeGroup) - The node group.
        """
        group = bpy.data.node_groups.get(name)
        if not group:
            group = bpy.data.node_groups.new(name, f"{type.title()}NodeTree")
        self.node_group = group
        return group

    def group_input(
        self,
        name: str = "Group Input",
        label: str = None,
        position: Vector = Vector((0, 0)),
    ) -> bpy.types.Node:
        """Create a group input node.

        group (bpy.types.NodeGroup) - The node group to add the node to.
        name (str, optional) - The name of the input node.
        label (str, optional) - The label of the input node.
        position (2D Vector, optional) - The position to insert the node in the node group.
        return (bpy.types.Node) - The group input node.
        """
        group = self.node_group
        group_input = group.nodes.get(name)
        if not group_input:
            group_input = group.nodes.new("NodeGroupInput")
            group_input.name = name
        if label is not None:
            group_input.label = label
        group_input.location = position
        return group_input

    def input(
        self,
        name: str = "Input",
        type: str = "FLOAT",
        default: bpy.types.AnyType = None,
        min: float = None,
        max: float = None,
        tooltip: str = None,
        hide_value: bool = False,
    ) -> bpy.types.NodeSocket:
        """Create an input node.

        group (bpy.types.NodeGroup) - The node group to add the node to.
        name (str, optional) - The name of the input node.
        type (str, optional) - The type of the input node.
        default (bpy.types.AnyType, optional) - The default value of the input node.
        min (float, optional) - The minimum value of the input node.
        max (float, optional) - The maximum value of the input node.
        tooltip (str, optional) - The tooltip of the input node.
        hide_value (bool, optional) - Hide the value of the input node.
        return (bpy.types.NodeSocket) - The input node socket.
        """
        group = self.node_group
        input = group.inputs.get(name)
        if not input:
            input = group.inputs.new(f"NodeSocket{type.title()}", name)
        if tooltip is not None:
            input.description = tooltip
        if type in {"STRING", "BOOL", "VECTOR", "INT", "FLOAT", "COLOR"}:
            if default is not None:
                input.default_value = default
            if type in {"VECTOR", "INT", "FLOAT"}:
                if min is not None:
                    input.min_value = min
                if max is not None:
                    input.max_value = max
        input.hide_value = hide_value
        return input

    def group_output(
        self,
        name: str = "Group Output",
        label: str = None,
        position: Vector = Vector((0, 0)),
    ) -> bpy.types.Node:
        """Create a group output node.

        group (bpy.types.NodeGroup) - The node group to add the node to.
        name (str, optional) - The name of the output node.
        label (str, optional) - The label of the output node.
        position (2D Vector, optional) - The position to insert the node in the node group.
        return (bpy.types.Node) - The group output node.
        """
        group = self.node_group
        group_output = group.nodes.get(name)
        if not group_output:
            group_output = group.nodes.new("NodeGroupOutput")
            group_output.name = name
        if label is not None:
            group_output.label = label
        group_output.location = position
        return group_output

    def output(
        self,
        name: str = "Output",
        type: str = "FLOAT",
        default: float = None,
        min: float = None,
        max: float = None,
        tooltip: str = None,
        hide_value: bool = False,
    ) -> bpy.types.NodeSocket:
        """Create an output node.

        group (bpy.types.NodeGroup) - The node group to add the node to.
        name (str, optional) - The name of the output node.
        type (str, optional) - The type of the output node.
        default (bpy.types.AnyType, optional) - The default value of the output node.
        min (float, optional) - The minimum value of the output node.
        max (float, optional) - The maximum value of the output node.
        tooltip (str, optional) - The tooltip of the output node.
        hide_value (bool, optional) - Hide the value of the output node.
        return (bpy.types.NodeSocket) - The output node socket.
        """
        group = self.node_group
        output = group.outputs.get(name)
        if not output:
            output = group.outputs.new(f"NodeSocket{type.title()}", name)
        if tooltip is not None:
            output.description = tooltip
        if type in {"STRING", "BOOLEAN", "VECTOR", "INT", "FLOAT", "COLOR"}:
            if default is not None:
                output.default_value = default
            if type in {"VECTOR", "INT", "FLOAT"}:
                if min is not None:
                    output.min_value = min
                if max is not None:
                    output.max_value = max
        output.hide_value = hide_value
        return output

    def frame(self) -> bpy.types.NodeFrame:
        """Create a frame node.

        return (bpy.types.NodeFrame) - The frame node.
        """
        return self.Frame(self.node_group)

    def reroute(self, group: bpy.types.NodeGroup, name: str, position: Vector = Vector((0, 0))) -> bpy.types.Node:
        """Create a new node and reroute the group input to it

        group (bpy.types.NodeGroup) - The node group to add the node to.
        name (str, optional) - The name of the new node.
        position (2D Vector, optional) - The position of the new node.
        return (bpy.types.Node) - The reroute node.
        """
        reroute = group.nodes.get(name)
        if not reroute:
            reroute = group.nodes.new("NodeReroute")
            reroute.name = name
        reroute.location = position
        return reroute

    def link(
        self,
        from_node: bpy.types.Node,
        to_node: bpy.types.Node,
        from_socket: list,
        to_socket: list,
    ):
        """Link two nodes together.

        group (bpy.types.NodeGroup) - The node group to add the node to.
        from_node (bpy.types.Node) - The node to link from.
        to_node (bpy.types.Node) - The node to link to.
        from_socket (list) - The socket to link from.
        to_socket (list) - The socket to link to.
        """
        group = self.node_group
        group.links.new(from_node.outputs[from_socket], to_node.inputs[to_socket])

    # GeometryNode

    def resample_curve(
        self,
        name: str = "Resample Curve",
        label: str = None,
        mode: str = None,
        count: int = None,
        length: float = None,
        position: Vector = Vector((0, 0)),
    ) -> bpy.types.Node:
        return super().resample_curve(self.node_group, name, label, mode, count, length, position)

    def set_spline_cyclic(
        self,
        name: str = "Set Spline Cyclic",
        label: str = None,
        cyclic: bool = False,
        position: Vector = Vector((0, 0)),
    ) -> bpy.types.Node:
        return super().set_spline_cyclic(self.node_group, name, label, cyclic, position)

    def curve_spiral(
        self,
        name: str = "Spiral",
        label: str = None,
        resolution: int = None,
        rotation: float = None,
        start_radius: float = None,
        end_radius: float = None,
        height: float = None,
        reverse: bool = None,
        position: Vector = Vector((0, 0)),
    ) -> bpy.types.Node:
        return super().curve_spiral(
            self.node_group,
            name,
            label,
            resolution,
            rotation,
            start_radius,
            end_radius,
            height,
            reverse,
            position,
        )

    def set_position(
        self,
        name: str = "Set Position",
        label: str = None,
        offset: Vector = None,
        position: Vector = Vector((0, 0)),
    ) -> bpy.types.Node:
        return super().set_position(self.node_group, name, label, offset, position)

    def transform(
        self,
        name: str = "Transform",
        label: str = None,
        translation: Vector = None,
        rotation: Vector = None,
        scale: Vector = None,
        position: Vector = Vector((0, 0)),
    ) -> bpy.types.Node:
        return super().transform(self.node_group, name, label, translation, rotation, scale, position)

    def object_info(
        self,
        name: str = "Object Info",
        label: str = None,
        transform_space: str = None,
        object: bpy.types.Object = None,
        as_instance: bool = False,
        position: Vector = Vector((0, 0)),
    ) -> bpy.types.Node:
        return super().object_info(self.node_group, name, label, transform_space, object, as_instance, position)

    def input_id(self, name: str = "ID", label: str = None, position: Vector = Vector((0, 0))) -> bpy.types.Node:
        return super().input_id(self.node_group, name, label, position)

    def input_position(
        self,
        name: str = "Position",
        label: str = None,
        position: Vector = Vector((0, 0)),
    ) -> bpy.types.Node:
        return super().input_position(self.node_group, name, label, position)

    def instance_on_points(
        self,
        name: str = "Instance on Point",
        label: str = None,
        pick_instance: bool = False,
        rotation: float = None,
        scale: float = None,
        position: Vector = Vector((0, 0)),
    ) -> bpy.types.Node:
        return super().instance_on_points(self.node_group, name, label, pick_instance, rotation, scale, position)

    def realize_instances(
        self,
        name: str = "Realize Instances",
        label: str = None,
        position: Vector = Vector((0, 0)),
    ) -> bpy.types.Node:
        return super().realize_instances(self.node_group, name, label, position)

    def mesh_to_curve(
        self,
        name: str = "Mesh to Curve",
        label: str = None,
        position: Vector = Vector((0, 0)),
    ) -> bpy.types.Node:
        return super().mesh_to_curve(self.node_group, name, label, position)

    def mesh_line(
        self,
        name: str = "Mesh Line",
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
        return super().mesh_line(
            self.node_group,
            name,
            label,
            mode,
            count_mode,
            count,
            resolution,
            start_location,
            end_location,
            offset,
            position,
        )

    def switch(
        self,
        name: str = "Switch",
        label: str = None,
        type: str = None,
        set_switch: bool = False,
        false: bpy.types.AnyType = None,
        true: bpy.types.AnyType = None,
        position: Vector = Vector((0, 0)),
    ) -> bpy.types.Node:
        return super().switch(self.node_group, name, label, type, set_switch, false, true, position)

    # FunctionNode

    def vector(
        self,
        name: str = "Vector",
        label: str = None,
        vector: Vector = None,
        position: Vector = Vector((0, 0)),
    ) -> bpy.types.Node:
        return super().vector(self.node_group, name, label, vector, position)

    def align_euler_to_vector(
        self,
        name: str = "Align Euler to Vector",
        label: str = None,
        axis: str = None,
        pivot: str = None,
        factor: float = None,
        vector: Vector = None,
        position: Vector = Vector((0, 0)),
    ) -> bpy.types.Node:
        return super().align_euler_to_vector(self.node_group, name, label, axis, pivot, factor, vector, position)

    def random_value(
        self,
        name: str = "Random Value",
        label: str = None,
        type: str = None,
        min: list = None,
        max: list = None,
        probability: float = None,
        seed: int = None,
        position: Vector = Vector((0, 0)),
    ) -> bpy.types.Node:
        return super().random_value(self.node_group, name, label, type, min, max, probability, seed, position)

    def rotate_euler(
        self,
        name: str = "Rotate Euler",
        label: str = None,
        type: str = None,
        space: str = None,
        axis: list = None,
        rotate: list = None,
        angle: float = None,
        position: Vector = Vector((0, 0)),
    ) -> bpy.types.Node:
        return super().rotate_euler(self.node_group, name, label, type, space, axis, rotate, angle, position)

    # ShaderNode

    def color_attribute(
        self,
        name: str = "Color Attribute",
        label: str = None,
        layer_name: str = "",
        position: Vector = Vector((0, 0)),
    ) -> bpy.types.Node:
        return super().color_attribute(self.node_group, name, label, layer_name, position)

    def geometry(
        self,
        name: str = "Geomerty",
        label: str = None,
        position: Vector = Vector((0, 0)),
    ) -> bpy.types.Node:
        return super().geometry(self.node_group, name, label, position)

    def image_texture(
        self,
        name: str = "Image Texture",
        label: str = None,
        image: bpy.types.Image = None,
        position: Vector = Vector((0, 0)),
    ) -> bpy.types.Node:
        return super().image_texture(self.node_group, name, label, image, position)

    def map_range(
        self,
        name: str = "Map Range",
        label: str = None,
        type: str = None,
        clamp: bool = False,
        input_0: float = None,
        input_1: float = None,
        input_2: float = None,
        input_3: float = None,
        input_4: float = None,
        input_5: float = None,
        position: Vector = Vector((0, 0)),
    ) -> bpy.types.Node:
        return super().map_range(
            self.node_group,
            name,
            label,
            type,
            clamp,
            input_0,
            input_1,
            input_2,
            input_3,
            input_4,
            input_5,
            position,
        )

    def math(
        self,
        name: str = "Math",
        label: str = None,
        operation: str = None,
        use_clamp: bool = False,
        input_0: float = None,
        input_1: float = None,
        input_2: float = None,
        position: Vector = Vector((0, 0)),
    ) -> bpy.types.Node:
        return super().math(
            self.node_group,
            name,
            label,
            operation,
            use_clamp,
            input_0,
            input_1,
            input_2,
            position,
        )

    def combine_xyz(
        self,
        name: str = "Combine XYZ",
        label: str = None,
        vector: Vector = None,
        position: Vector = Vector((0, 0)),
    ) -> bpy.types.Node:
        return super().combine_xyz(self.node_group, name, label, vector, position)

    def separate_xyz(
        self,
        name: str = "Separate XYZ",
        label: str = None,
        vector: Vector = None,
        position: Vector = Vector((0, 0)),
    ) -> bpy.types.Node:
        return super().separate_xyz(self.node_group, name, label, vector, position)

    def vector_math(
        self,
        name: str = "Vector Math",
        label: str = None,
        operation: str = None,
        input_0: Vector = None,
        input_1: Vector = None,
        input_2: Vector = None,
        input_3: Vector = None,
        position: Vector = Vector((0, 0)),
    ) -> bpy.types.Node:
        return super().vector_math(
            self.node_group,
            name,
            label,
            operation,
            input_0,
            input_1,
            input_2,
            input_3,
            position,
        )

    def vector_rotate(
        self,
        name: str = "Vector Rotate",
        label: str = None,
        type: str = None,
        invert: bool = False,
        center: Vector = None,
        axis: Vector = None,
        angle: float = None,
        rotation: Vector = None,
        position: Vector = Vector((0, 0)),
    ) -> bpy.types.Node:
        return super().vector_rotate(
            self.node_group,
            name,
            label,
            type,
            invert,
            center,
            axis,
            angle,
            rotation,
            position,
        )

    def color_ramp(
        self,
        name: str = "Color Ramp",
        label: str = None,
        position: Vector = Vector((0, 0)),
    ) -> bpy.types.Node:
        return super().color_ramp(self.node_group, name, label, position)

    class Frame:
        def __init__(self, group) -> None:
            self.group = group

        def new(
            self,
            parent: bpy.types.NodeFrame = None,
            name: str = "Frame",
            label: str = None,
            label_size: int = None,
            color: list = None,
            shrink: bool = True,
            position: Vector = Vector((0, 0)),
        ) -> bpy.types.NodeFrame:
            """Create a node frame.

            group (bpy.types.NodeGroup) - The node group to add the node frame to.
            parent (bpy.types.NodeFrame, optional) - The parent node frame of the frame.
            name (str, optional) - The name of the frame.
            label (str, optional) - The label of the frame.
            label_size (int, optional) - The size of the label.
            color (list, optional) - The color of the frame.
            shrink (bool, optional) - Shrink the frame.
            position (2D Vector, optional) - The position to insert the node in the node group.
            return (bpy.types.NodeFrame) - The node frame.
            """
            group = self.group
            frame = group.nodes.get(name)
            if not frame:
                frame = group.nodes.new("NodeFrame")
                frame.name = name
            if parent is not None:
                frame.parent = parent
            if label is not None:
                frame.label = label
            if label_size is not None:
                frame.label_size = label_size
            if shrink is not None:
                frame.shrink = shrink
            frame.location = position
            self.bl_obj = frame
            return frame

        def node(self) -> bpy.types.Node:
            """Create a node.

            return (bpy.types.Node) - The node.
            """
            return self.Node(self)

        class Node(GeometryNode, FunctionNode, ShaderNode):
            def __init__(self, frame) -> None:
                self.frame = frame.bl_obj
                self.group = frame.group

            def group_input(
                self,
                name: str = "Group Input",
                label: str = None,
                position: Vector = Vector((0, 0)),
            ) -> bpy.types.Node:
                """Create a group input node.

                group (bpy.types.NodeGroup) - The node group to add the node to.
                name (str, optional) - The name of the input node.
                label (str, optional) - The label of the input node.
                position (2D Vector, optional) - The position to insert the node in the node group.
                return (bpy.types.Node) - The group input node.
                """
                group = self.group
                group_input = group.nodes.get(name)
                if not group_input:
                    group_input = group.nodes.new("NodeGroupInput")
                    group_input.name = name
                if label is not None:
                    group_input.label = label
                group_input.location = position
                group_input.parent = self.frame
                return group_input

            def input(
                self,
                name: str = "Input",
                type: str = "FLOAT",
                default: bpy.types.AnyType = None,
                min: float = None,
                max: float = None,
                tooltip: str = None,
                hide_value: bool = False,
            ) -> bpy.types.NodeSocket:
                """Create an input node.

                group (bpy.types.NodeGroup) - The node group to add the node to.
                name (str, optional) - The name of the input node.
                type (str, optional) - The type of the input node.
                default (bpy.types.AnyType, optional) - The default value of the input node.
                min (float, optional) - The minimum value of the input node.
                max (float, optional) - The maximum value of the input node.
                tooltip (str, optional) - The tooltip of the input node.
                hide_value (bool, optional) - Hide the value of the input node.
                return (bpy.types.NodeSocket) - The input node socket.
                """
                group = self.group
                input = group.inputs.get(name)
                if not input:
                    input = group.inputs.new(f"NodeSocket{type.title()}", name)
                if tooltip is not None:
                    input.description = tooltip
                if type in {"STRING", "BOOL", "VECTOR", "INT", "FLOAT", "COLOR"}:
                    if default is not None:
                        input.default_value = default
                    if type in {"VECTOR", "INT", "FLOAT"}:
                        if min is not None:
                            input.min_value = min
                        if max is not None:
                            input.max_value = max
                input.hide_value = hide_value
                return input

            def group_output(
                self,
                name: str = "Group Output",
                label: str = None,
                position: Vector = Vector((0, 0)),
            ) -> bpy.types.Node:
                """Create a group output node.

                group (bpy.types.NodeGroup) - The node group to add the node to.
                name (str, optional) - The name of the output node.
                label (str, optional) - The label of the output node.
                position (2D Vector, optional) - The position to insert the node in the node group.
                return (bpy.types.Node) - The group output node.
                """
                group = self.group
                group_output = group.nodes.get(name)
                if not group_output:
                    group_output = group.nodes.new("NodeGroupOutput")
                    group_output.name = name
                if label is not None:
                    group_output.label = label
                group_output.location = position
                group_output.parent = self.frame
                return group_output

            def output(
                self,
                name: str = "Output",
                type: str = "FLOAT",
                default: bpy.types.AnyType = None,
                min: float = None,
                max: float = None,
                tooltip: str = None,
                hide_value: bool = False,
            ) -> bpy.types.NodeSocket:
                """Create an output node.

                group (bpy.types.NodeGroup) - The node group to add the node to.
                name (str, optional) - The name of the output node.
                type (str, optional) - The type of the output node.
                default (bpy.types.AnyType, optional) - The default value of the output node.
                min (float, optional) - The minimum value of the output node.
                max (float, optional) - The maximum value of the output node.
                tooltip (str, optional) - The tooltip of the output node.
                hide_value (bool, optional) - Hide the value of the output node.
                return (bpy.types.NodeSocket) - The output node socket.
                """
                group = self.group
                output = group.outputs.get(name)
                if not output:
                    output = group.outputs.new(f"NodeSocket{type.title()}", name)
                if tooltip is not None:
                    output.description = tooltip
                if type in {"STRING", "BOOLEAN", "VECTOR", "INT", "FLOAT", "COLOR"}:
                    if default is not None:
                        output.default_value = default
                    if type in {"VECTOR", "INT", "FLOAT"}:
                        if min is not None:
                            output.min_value = min
                        if max is not None:
                            output.max_value = max
                output.hide_value = hide_value
                return output

            # GeometryNode

            def resample_curve(
                self,
                name: str = "Resample Curve",
                label: str = None,
                mode: str = None,
                count: int = None,
                length: float = None,
                position: Vector = Vector((0, 0)),
            ) -> bpy.types.Node:
                resample_curve = super().resample_curve(self.group, name, label, mode, count, length, position)
                resample_curve.parent = self.frame
                return resample_curve

            def set_spline_cyclic(
                self,
                name: str = "Set Spline Cyclic",
                label: str = None,
                cyclic: bool = False,
                position: Vector = Vector((0, 0)),
            ) -> bpy.types.Node:
                set_spline_cyclic = super().set_spline_cyclic(self.group, name, label, cyclic, position)
                set_spline_cyclic.parent = self.frame
                return set_spline_cyclic

            def curve_spiral(
                self,
                name: str = "Spiral",
                label: str = None,
                resolution: int = None,
                rotation: float = None,
                start_radius: float = None,
                end_radius: float = None,
                height: float = None,
                reverse: bool = None,
                position: Vector = Vector((0, 0)),
            ) -> bpy.types.Node:
                curve_spiral = super().curve_spiral(
                    self.group,
                    name,
                    label,
                    resolution,
                    rotation,
                    start_radius,
                    end_radius,
                    height,
                    reverse,
                    position,
                )
                curve_spiral.parent = self.frame
                return curve_spiral

            def set_position(
                self,
                name: str = "Set Position",
                label: str = None,
                offset: Vector = None,
                position: Vector = Vector((0, 0)),
            ) -> bpy.types.Node:
                set_position = super().set_position(self.group, name, label, offset, position)
                set_position.parent = self.frame
                return set_position

            def transform(
                self,
                name: str = "Transform",
                label: str = None,
                translation: Vector = None,
                rotation: Vector = None,
                scale: Vector = None,
                position: Vector = Vector((0, 0)),
            ) -> bpy.types.Node:
                transform = super().transform(self.group, name, label, translation, rotation, scale, position)
                transform.parent = self.frame
                return transform

            def object_info(
                self,
                name: str = "Object Info",
                label: str = None,
                transform_space: str = None,
                object: bpy.types.Object = None,
                as_instance: bool = False,
                position: Vector = Vector((0, 0)),
            ) -> bpy.types.Node:
                object_info = super().object_info(
                    self.group,
                    name,
                    label,
                    transform_space,
                    object,
                    as_instance,
                    position,
                )
                object_info.parent = self.frame
                return object_info

            def input_id(
                self,
                name: str = "ID",
                label: str = None,
                position: Vector = Vector((0, 0)),
            ) -> bpy.types.Node:
                input_id = super().input_id(self.group, name, label, position)
                input_id.parent = self.frame
                return input_id

            def input_position(
                self,
                name: str = "Position",
                label: str = None,
                position: Vector = Vector((0, 0)),
            ) -> bpy.types.Node:
                input_position = super().input_position(self.group, name, label, position)
                input_position.parent = self.frame
                return input_position

            def instance_on_points(
                self,
                name: str = "Instance on Point",
                label: str = None,
                pick_instance: bool = False,
                rotation: float = None,
                scale: float = None,
                position: Vector = Vector((0, 0)),
            ) -> bpy.types.Node:
                instance_on_points = super().instance_on_points(self.group, name, label, pick_instance, rotation, scale, position)
                instance_on_points.parent = self.frame
                return instance_on_points

            def realize_instances(
                self,
                name: str = "Realize Instances",
                label: str = None,
                position: Vector = Vector((0, 0)),
            ) -> bpy.types.Node:
                realize_instances = super().realize_instances(self.group, name, label, position)
                realize_instances.parent = self.frame
                return realize_instances

            def mesh_to_curve(
                self,
                name: str = "Mesh to Curve",
                label: str = None,
                position: Vector = Vector((0, 0)),
            ) -> bpy.types.Node:
                mesh_to_curve = super().mesh_to_curve(self.group, name, label, position)
                mesh_to_curve.parent = self.frame
                return mesh_to_curve

            def mesh_line(
                self,
                name: str = "Mesh Line",
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
                mesh_line = super().mesh_line(
                    self.group,
                    name,
                    label,
                    mode,
                    count_mode,
                    count,
                    resolution,
                    start_location,
                    end_location,
                    offset,
                    position,
                )
                mesh_line.parent = self.frame
                return mesh_line

            def switch(
                self,
                name: str = "Switch",
                label: str = None,
                type: str = None,
                set_switch: bool = False,
                false: bpy.types.AnyType = None,
                true: bpy.types.AnyType = None,
                position: Vector = Vector((0, 0)),
            ) -> bpy.types.Node:
                switch = super().switch(self.group, name, label, type, set_switch, false, true, position)
                switch.parent = self.frame
                return switch

            # FunctionNode

            def vector(
                self,
                name: str = "Vector",
                label: str = None,
                vector: Vector = None,
                position: Vector = Vector((0, 0)),
            ) -> bpy.types.Node:
                vector = super().vector(self.group, name, label, vector, position)
                vector.parent = self.frame
                return vector

            def align_euler_to_vector(
                self,
                name: str = "Align Euler to Vector",
                label: str = None,
                axis: str = None,
                pivot: str = None,
                factor: float = None,
                vector: Vector = None,
                position: Vector = Vector((0, 0)),
            ) -> bpy.types.Node:
                align_euler_to_vector = super().align_euler_to_vector(self.group, name, label, axis, pivot, factor, vector, position)
                align_euler_to_vector.parent = self.frame
                return align_euler_to_vector

            def random_value(
                self,
                name: str = "Random Value",
                label: str = None,
                type: str = None,
                min: list = None,
                max: list = None,
                probability: float = None,
                seed: int = None,
                position: Vector = Vector((0, 0)),
            ) -> bpy.types.Node:
                random_value = super().random_value(self.group, name, label, type, min, max, probability, seed, position)
                random_value.parent = self.frame
                return random_value

            def rotate_euler(
                self,
                name: str = "Rotate Euler",
                label: str = None,
                type: str = None,
                space: str = None,
                axis: list = None,
                rotate: list = None,
                angle: float = None,
                position: Vector = Vector((0, 0)),
            ) -> bpy.types.Node:
                rotate_euler = super().rotate_euler(self.group, name, label, type, space, axis, rotate, angle, position)
                rotate_euler.parent = self.frame
                return rotate_euler

            # ShaderNode

            def color_attribute(
                self,
                name: str = "Color Attribute",
                label: str = None,
                layer_name: str = "",
                position: Vector = Vector((0, 0)),
            ) -> bpy.types.Node:
                color_attribute = super().color_attribute(self.group, name, label, layer_name, position)
                color_attribute.parent = self.frame
                return color_attribute

            def geometry(
                self,
                name: str = "Geometry",
                label: str = None,
                position: Vector = Vector((0, 0)),
            ) -> bpy.types.Node:
                geometry = super().geometry(self.group, name, label, position)
                geometry.parent = self.frame
                return geometry

            def image_texture(
                self,
                name: str = "Image Texture",
                label: str = None,
                image: bpy.types.Image = None,
                position: Vector = Vector((0, 0)),
            ) -> bpy.types.Node:
                image_texture = super().image_texture(self.group, name, label, image, position)
                image_texture.parent = self.frame
                return image_texture

            def map_range(
                self,
                name: str = "Map Range",
                label: str = None,
                type: str = None,
                clamp: bool = False,
                input_0: float = None,
                input_1: float = None,
                input_2: float = None,
                input_3: float = None,
                input_4: float = None,
                input_5: float = None,
                position: Vector = Vector((0, 0)),
            ) -> bpy.types.Node:
                map_range = super().map_range(
                    self.group,
                    name,
                    label,
                    type,
                    clamp,
                    input_0,
                    input_1,
                    input_2,
                    input_3,
                    input_4,
                    input_5,
                    position,
                )
                map_range.parent = self.frame
                return map_range

            def math(
                self,
                name: str = "Math",
                label: str = None,
                operation: str = None,
                use_clamp: bool = False,
                input_0: float = None,
                input_1: float = None,
                input_2: float = None,
                position: Vector = Vector((0, 0)),
            ) -> bpy.types.Node:
                math = super().math(
                    self.group,
                    name,
                    label,
                    operation,
                    use_clamp,
                    input_0,
                    input_1,
                    input_2,
                    position,
                )
                math.parent = self.frame
                return math

            def combine_xyz(
                self,
                name: str = "Combine XYZ",
                label: str = None,
                vector: Vector = None,
                position: Vector = Vector((0, 0)),
            ) -> bpy.types.Node:
                combine_xyz = super().combine_xyz(self.group, name, label, vector, position)
                combine_xyz.parent = self.frame
                return combine_xyz

            def separate_xyz(
                self,
                name: str = "Separate XYZ",
                label: str = None,
                vector: Vector = None,
                position: Vector = Vector((0, 0)),
            ) -> bpy.types.Node:
                separate_xyz = super().separate_xyz(self.group, name, label, vector, position)
                separate_xyz.parent = self.frame
                return separate_xyz

            def vector_math(
                self,
                name: str = "Vector Math",
                label: str = None,
                operation: str = None,
                input_0: Vector = None,
                input_1: Vector = None,
                input_2: Vector = None,
                input_3: Vector = None,
                position: Vector = Vector((0, 0)),
            ) -> bpy.types.Node:
                vector_math = super().vector_math(
                    self.group,
                    name,
                    label,
                    operation,
                    input_0,
                    input_1,
                    input_2,
                    input_3,
                    position,
                )
                vector_math.parent = self.frame
                return vector_math

            def vector_rotate(
                self,
                name: str = "Vector Rotate",
                label: str = None,
                type: str = None,
                invert: bool = False,
                center: Vector = None,
                axis: Vector = None,
                angle: float = None,
                rotation: Vector = None,
                position: Vector = Vector((0, 0)),
            ) -> bpy.types.Node:
                vector_rotate = super().vector_rotate(
                    self.group,
                    name,
                    label,
                    type,
                    invert,
                    center,
                    axis,
                    angle,
                    rotation,
                    position,
                )
                vector_rotate.parent = self.frame
                return vector_rotate

            def color_ramp(
                self,
                name: str = "Color Ramp",
                label: str = None,
                position: Vector = Vector((0, 0)),
            ) -> bpy.types.Node:
                color_ramp = super().color_ramp(self.group, name, label, position)
                color_ramp.parent = self.frame
                return color_ramp
