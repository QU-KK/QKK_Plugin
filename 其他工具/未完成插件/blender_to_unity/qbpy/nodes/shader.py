import bpy
from mathutils import Vector


class ShaderNode:
    # Input
    @staticmethod
    def ambient_occlusion(
        group: bpy.types.NodeGroup,
        name: str,
        label: str = None,
        samples: int = 16,
        inside: bool = False,
        only_local: bool = False,
        color: tuple = (1, 1, 1, 1),
        distance: float = 1.0,
        position: Vector = Vector((0, 0)),
    ) -> bpy.types.Node:
        """Create an Ambient Occlusion node.

        group (bpy.types.NodeGroup) - The node group to add the node to.
        name (str) - The name of the ambient occlusion node.
        label (str, optional) - The label of the ambient occlusion node.
        samples (int, optional) - Number of rays to trace per shader evaluation.
        inside (bool, optional) - Trace rays towards the inside of the object.
        only_local (bool, optional) - Only consider the object itself when computing AO.
        color (tuple, optional) - Default color for ambient occlusion.
        distance (float) - Default distance for ambient occlusion.
        position (2D Vector, optional) - The position to insert the node in the node group.
        return (bpy.types.Node) - The Ambient Occlusion node.
        """
        node = group.nodes.get(name)
        if not node:
            node = group.nodes.new("ShaderNodeAmbientOcclusion")
            node.name = name
        if label is not None:
            node.label = label
        node.samples = samples
        node.inside = inside
        node.only_local = only_local
        node.inputs["Color"].default_value = color
        node.inputs["Distance"].default_value = distance
        node.location = position
        return node

    @staticmethod
    def bevel(
        group: bpy.types.NodeGroup,
        name: str,
        label: str = None,
        samples: int = 4,
        radius: float = 0.05,
        position: Vector = Vector((0, 0)),
    ) -> bpy.types.Node:
        """Create Bevel node.

        group (bpy.types.NodeGroup) - The node group to add the node to.
        name (str) - The name of the bevel node.
        label (str, optional) - The label of the bevel node.
        samples (int, optional) - Number of rays to trace per shader evaluation.
        radius (float, optional) - Radius of bevel node.
        position (2D Vector, optional) - The position to insert the node in the node group.
        return (bpy.types.Node) - The Bevel node.
        """
        node = group.nodes.get(name)
        if not node:
            node = group.nodes.new("ShaderNodeBevel")
            node.name = name
        if label is not None:
            node.label = label
        node.samples = samples
        node.inputs["Radius"].default_value = radius
        node.location = position
        return node

    @staticmethod
    def color_attribute(
        group: bpy.types.NodeGroup,
        name: str,
        label: str = None,
        layer_name: str = "",
        position: Vector = Vector((0, 0)),
    ) -> bpy.types.Node:
        """Create a Color Attribute node.

        group (bpy.types.NodeGroup) - The node group to add the node to.
        name (str) - The name of the color attribute node.
        label (str, optional) - The label of the color attribute node.
        layer_name (str, optional) - The uv layer name.
        position (2D Vector, optional) - The position to insert the node in the node group.
        return (bpy.types.Node) - The Color Attribute node.
        """
        node = group.nodes.get(name)
        if not node:
            node = group.nodes.new("ShaderNodeVertexColor")
            node.name = name
        if label is not None:
            node.label = label
        node.location = position
        node.layer_name = layer_name
        return node

    @staticmethod
    def geometry(
        group: bpy.types.NodeGroup,
        name: str,
        label: str = None,
        position: Vector = Vector((0, 0)),
    ) -> bpy.types.Node:
        """Create Geometry node.

        group (bpy.types.NodeGroup) - The node group to add the node to.
        name (str) - The name of the geometry node.
        label (str, optional) - The label of the geometry node.
        position (2D Vector, optional) - The position to insert the node in the node group.
        return (bpy.types.Node) - The Geometry node.
        """
        node = group.nodes.get(name)
        if not node:
            node = group.nodes.new("ShaderNodeNewGeometry")
            node.name = name
        if label is not None:
            node.label = label
        node.location = position
        return node

    @staticmethod
    def texture_coordinate(
        group: bpy.types.NodeGroup,
        name: str,
        label: str = None,
        position: Vector = Vector((0, 0)),
    ) -> bpy.types.Node:
        """Create Texture Coordinate node.

        group (bpy.types.NodeGroup) - The node group to add the node to.
        name (str) - The name of the texture coordinate node.
        label (str, optional) - The label of the texture coordinate node.
        position (2D Vector, optional) - The position to insert the node in the node group.
        return (bpy.types.Node) - The Texture Coordinate node.
        """
        node = group.nodes.get(name)
        if not node:
            node = group.nodes.new("ShaderNodeTexCoord")
            node.name = name
        if label is not None:
            node.label = label
        node.location = position
        return node

    @staticmethod
    def rgb(
        group: bpy.types.NodeGroup,
        name: str,
        label: str = None,
        color: tuple = (0.5, 0.5, 0.5, 1.0),
        position: Vector = Vector((0, 0)),
    ) -> bpy.types.Node:
        """Create a RGB node.

        group (bpy.types.NodeGroup) - The node group to add the node to.
        name (str) - The name of the RGB node.
        label (str, optional) - The label of the RGB node.
        color (RGBA tuple, optional) - The output color.
        position (2D Vector, optional) - The position to insert the node in the node group.
        return (bpy.types.Node) - The RGB node.
        """
        node = group.nodes.get(name)
        if not node:
            node = group.nodes.new("ShaderNodeRGB")
            node.name = name
        if label is not None:
            node.label = label
        if color is not None:
            node.outputs["Color"].default_value = color
        node.location = position
        return node

    @staticmethod
    def uvmap(
        group: bpy.types.NodeGroup,
        name: str,
        label: str = None,
        from_instancer: bool = False,
        uv_map: str = "",
        position: Vector = Vector((0, 0)),
    ) -> bpy.types.Node:
        """Create a Value node.

        group (bpy.types.NodeGroup) - The node group to add the node to.
        name (str) - The name of the value node.
        label (str, optional) - The label of the value node.
        from_instancer (bool, optional) - Use the parent of the instance object if possible.
        uv_map (str, optional) - UV coordinates to be useed for mapping.
        position (2D Vector, optional) - The position to insert the node in the node group.
        return (bpy.types.Node) - The Value node.
        """
        node = group.nodes.get(name)
        if not node:
            node = group.nodes.new("ShaderNodeUVMap")
            node.name = name
        if label is not None:
            node.label = label
        node.from_instancer = from_instancer
        node.uv_map = uv_map
        node.location = position
        return node

    @staticmethod
    def value(
        group: bpy.types.NodeGroup,
        name: str,
        label: str = None,
        value: float = None,
        position: Vector = Vector((0, 0)),
    ) -> bpy.types.Node:
        """Create a Value node.

        group (bpy.types.NodeGroup) - The node group to add the node to.
        name (str) - The name of the value node.
        label (str, optional) - The label of the value node.
        value (float, optional) - The float factor.
        position (2D Vector, optional) - The position to insert the node in the node group.
        return (bpy.types.Node) - The Value node.
        """
        node = group.nodes.get(name)
        if not node:
            node = group.nodes.new("ShaderNodeValue")
            node.name = name
        if label is not None:
            node.label = label
        if value is not None:
            node.outputs["Value"].default_value = value
        node.location = position
        return node

    # Output
    @staticmethod
    def material_output(
        group: bpy.types.NodeGroup,
        name: str,
        label: str = None,
        target: str = "ALL",
        position: Vector = Vector((0, 0)),
    ) -> bpy.types.Node:
        """Create a Material Output node.

        group (bpy.types.NodeGroup) - The node group to add the node to.
        name (str) - The name of the material output node.
        label (str, optional) - The label of the material output node.
        target (enum in ['ALL', 'EEVEE', 'CYCLES']) - The target of the material output node
        position (2D Vector, optional) - The position to insert the node in the node group.
        return (bpy.types.Node) - The Material Output node.
        """
        node = group.nodes.get(name)
        if not node:
            node = group.nodes.new("ShaderNodeOutputMaterial")
            node.name = name
        if label is not None:
            node.label = label
        node.target = target
        node.location = position
        return node

    # Shader
    @staticmethod
    def diffuse_bsdf(
        group: bpy.types.NodeGroup,
        name: str,
        label: str = None,
        color: tuple = (0.8, 0.8, 0.8, 1),
        roughness: float = 0.0,
        position: Vector = Vector((0, 0)),
    ) -> bpy.types.Node:
        """Create an Diffuse BSDF node.

        group (bpy.types.NodeGroup) - The node group to add the node to.
        name (str) - The name of the diffuse BSDF node.
        label (str, optional) - The label of the diffuse BSDF node.
        color (RGBA tuple, optional) - The color of the diffuse BSDF node.
        roughness (float, optional) - The roughness of the diffuse BSDF node.
        position (2D Vector, optional) - The position to insert the node in the node group.
        return (bpy.types.Node) - The Diffuse BSDF node.
        """
        node = group.nodes.get(name)
        if not node:
            node = group.nodes.new("ShaderNodeBsdfDiffuse")
            node.name = name
        if label is not None:
            node.label = label
        node.inputs["Color"].default_value = color
        node.inputs["Roughness"].default_value = roughness
        node.location = position
        return node

    @staticmethod
    def emission(
        group: bpy.types.NodeGroup,
        name: str,
        label: str = None,
        color: tuple = (1, 1, 1, 1),
        strength: float = 1.0,
        position: Vector = Vector((0, 0)),
    ) -> bpy.types.Node:
        """Create an Emission node.

        group (bpy.types.NodeGroup) - The node group to add the node to.
        name (str) - The name of the emission node.
        label (str, optional) - The label of the emission node.
        color (RGBA tuple, optional) - The color of the emission node.
        strength (float, optional) - The strength of the emission node.
        position (2D Vector, optional) - The position to insert the node in the node group.
        return (bpy.types.Node) - The Emission node.
        """
        node = group.nodes.get(name)
        if not node:
            node = group.nodes.new("ShaderNodeEmission")
            node.name = name
        if label is not None:
            node.label = label
        node.inputs["Color"].default_value = color
        node.inputs["Strength"].default_value = strength
        node.location = position
        return node

    @staticmethod
    def mix_shader(
        group: bpy.types.NodeGroup,
        name: str,
        label: str = None,
        fac: float = None,
        position: Vector = Vector((0, 0)),
    ) -> bpy.types.Node:
        """Create a Mix Shader node.

        group (bpy.types.NodeGroup) - The node group to add the node to.
        name (str) - The name of the mix shader node.
        label (str, optional) - The label of the mix shader node.
        fac (float, optional) - The float factor.
        position (2D Vector, optional) - The position to insert the node in the node group.
        return (bpy.types.Node) - The Mix Shader node.
        """
        node = group.nodes.get(name)
        if not node:
            node = group.nodes.new("ShaderNodeMixShader")
            node.name = name
        if label is not None:
            node.label = label
        if fac is not None:
            node.inputs["Fac"].default_value = fac
        node.location = position
        return node

    # Texture
    @staticmethod
    def gradient_texture(
        group: bpy.types.NodeGroup,
        name: str,
        label: str = None,
        gradient_type: str = "LINEAR",
        position: Vector = Vector((0, 0)),
    ) -> bpy.types.Node:
        """Create a Gradient Texture node.

        group (bpy.types.NodeGroup) - The node group to add the node to.
        name (str) - The name of the gradient texture node.
        label (str, optional) - The label of the gradient texture node.
        gradient_type (enum in ['LINEAR', 'QUADRATIC', 'EASING', 'DIAGONAL', 'SPHERICAL', 'QUADRATIC_SPHERE', 'RADIAL'], default 'LINEAR') - The type of the gradient
        position (2D Vector, optional) - The position to insert the node in the node group.
        return (bpy.types.Node) - The Gradient Texture node.
        """
        node = group.nodes.get(name)
        if not node:
            node = group.nodes.new("ShaderNodeTexGradient")
            node.name = name
        if label is not None:
            node.label = label
        node.gradient_type = gradient_type
        node.location = position
        return node

    @staticmethod
    def image_texture(
        group: bpy.types.NodeGroup,
        name: str,
        label: str = None,
        image: bpy.types.Image = None,
        position: Vector = Vector((0, 0)),
    ) -> bpy.types.Node:
        """Create an Image Texture node.

        group (bpy.types.NodeGroup) - The node group to add the node to.
        name (str) - The name of the image texture node.
        label (str, optional) - The label of the image texture node.
        image (bpy.types.Image, optional) - The image to use.
        position (2D Vector, optional) - The position to insert the node in the node group.
        return (bpy.types.Node) - The Image Texture node.
        """
        node = group.nodes.get(name)
        if not node:
            node = group.nodes.new("ShaderNodeTexImage")
            node.name = name
        if label is not None:
            node.label = label
        node.image = image
        node.location = position
        return node

    # Color
    @staticmethod
    def bright_contrast(
        group: bpy.types.NodeGroup,
        name: str,
        label: str = None,
        color: tuple = (1, 1, 1, 1),
        bright: float = 0.0,
        contrast: float = 0.0,
        position: Vector = Vector((0, 0)),
    ) -> bpy.types.Node:
        """Create a Bright/Contrast node.

        group (bpy.types.NodeGroup) - The node group to add the node to.
        name (str) - The name of the bright_contrast node.
        label (str, optional) - The label of the bright_contrast node.
        color (tuple) - The color of the bright_contrast node
        bright (float) - The bright of the bright_contrast node
        contrast (float) - The contrast of the bright_contrast node
        position (2D Vector, optional) - The position to insert the node in the node group.
        return (bpy.types.Node) - The Bright/Contrast node.
        """
        node = group.nodes.get(name)
        if not node:
            node = group.nodes.new("ShaderNodeBrightContrast")
            node.name = name
        if label is not None:
            node.label = label
        node.inputs["Color"].default_value = color
        node.inputs["Bright"].default_value = bright
        node.inputs["Contrast"].default_value = contrast
        node.location = position
        return node

    @staticmethod
    def invert(
        group: bpy.types.NodeGroup,
        name: str,
        label: str = None,
        fac: float = 1.0,
        color: tuple = (0, 0, 0, 1),
        position: Vector = Vector((0, 0)),
    ) -> bpy.types.Node:
        """Create an Invert node.

        group (bpy.types.NodeGroup) - The node group to add the node to.
        name (str) - The name of the invert node.
        label (str, optional) - The label of the invert node.
        fac (float) - The factor to use
        color (tuple) - The color of the invert node
        position (2D Vector, optional) - The position to insert the node in the node group.
        return (bpy.types.Node) - The Invert node.
        """
        node = group.nodes.get(name)
        if not node:
            node = group.nodes.new("ShaderNodeInvert")
            node.name = name
        if label is not None:
            node.label = label
        node.inputs["Fac"].default_value = fac
        node.inputs["Color"].default_value = color
        node.location = position
        return node

    @staticmethod
    def mix_rgb(
        group: bpy.types.NodeGroup,
        name: str,
        label: str = None,
        blend_type: str = "MIX",
        clamp: bool = False,
        fac: float = 0.5,
        color_1: float = (0.5, 0.5, 0.5, 1.0),
        color_2: float = (0.5, 0.5, 0.5, 1.0),
        position: Vector = Vector((0, 0)),
    ) -> bpy.types.Node:
        """Create a Mix RGB node.

        group (bpy.types.NodeGroup) - The node group to add the node to.
        name (str) - The name of the mix rgb node.
        label (str, optional) - The label of the mix rgb node.
        blend_type (enum in ['MIX', 'DARKEN', 'MULTIPLY', 'BURN', 'LIGHTEN', 'SCREEN', 'DODGE', 'ADD', 'OVERLAY', 'SOFT_LIGHT', 'LINEAR_LIGHT', 'DIFFERENCE', 'SUBTRACT', 'DIVIDE', 'HUE', 'SATURATION', 'COLOR', 'VALUE'] default 'MIX') - The blend type
        clamp (bool) - Whether to clamp
        fac (float) - The factor to use
        color_1 (tuple) - The color 1
        color_2 (tuple) - The color 2
        position (2D Vector, optional) - The position to insert the node in the node group.
        return (bpy.types.Node) - The Mix RGB node.
        """
        node = group.nodes.get(name)
        if not node:
            node = group.nodes.new("ShaderNodeMixRGB")
            node.name = name
        if label is not None:
            node.label = label
        node.blend_type = blend_type
        node.use_clamp = clamp
        node.inputs["Fac"].default_value = fac
        node.inputs["Color1"].default_value = color_1
        node.inputs["Color2"].default_value = color_2
        node.location = position
        return node

    # Vector
    @staticmethod
    def displacement(
        group: bpy.types.NodeGroup,
        name: str,
        label: str = None,
        space: str = "OBJECT",
        height: float = 0.0,
        midlevel: float = 0.5,
        scale: float = 1.0,
        position: Vector = Vector((0, 0)),
    ) -> bpy.types.Node:
        """Create a Displacement node.

        group (bpy.types.NodeGroup) - The node group to add the node to.
        name (str) - The name of the displacement node.
        label (str, optional) - The label of the displacement node.
        space (enum in ['OBJECT', 'WORLD'], default 'OBJECT') - Space of the input height.
        height (float, optional) - Default value of input height.
        midlevel (float, optional) - Default value of input midlevel.
        scale (float, optional) - Default value of input scale.
        position (2D Vector, optional) - The position to insert the node in the node group.
        return (bpy.types.Node) - The Displacement node.
        """
        node = group.nodes.get(name)
        if not node:
            node = group.nodes.new("ShaderNodeDisplacement")
            node.name = name
        if label is not None:
            node.label = label
        node.space = space
        node.inputs["Height"].default_value = height
        node.inputs["Midlevel"].default_value = midlevel
        node.inputs["Scale"].default_value = scale
        node.location = position
        return node

    @staticmethod
    def mapping(
        group: bpy.types.NodeGroup,
        name: str,
        label: str = None,
        type: str = "POINT",
        position: Vector = Vector((0, 0)),
    ) -> bpy.types.Node:
        """Create a Mapping node.

        group (bpy.types.NodeGroup) - The node group to add the node to.
        name (str) - The name of the mapping node.
        label (str, optional) - The label of the mapping node.
        type (enum in ['POINT', 'TEXTURE', 'VECTOR', 'NORMAL'], default 'POINT') - The vector inputs.
        position (2D Vector, optional) - The position to insert the node in the node group.
        return (bpy.types.Node) - The Mapping node.
        """
        node = group.nodes.get(name)
        if not node:
            node = group.nodes.new("ShaderNodeMapping")
            node.name = name
        if label is not None:
            node.label = label
        node.vector_type = type
        node.location = position
        return node

    @staticmethod
    def normal(
        group: bpy.types.NodeGroup,
        name: str,
        label: str = None,
        space: str = "TANGENT",
        uv_map: str = "",
        strength: float = 1.0,
        color: tuple = (0.5, 0.5, 1, 1),
        position: Vector = Vector((0, 0)),
    ) -> bpy.types.Node:
        """Create a Normal node.

        group (bpy.types.NodeGroup) - The node group to add the node to.
        name (str) - The name of the normal node.
        label (str, optional) - The label of the normal node.
        space (enum in ['TANGENT', 'OBJECT', 'WORLD', 'BLENDER_OBJECT', 'BLENDER_WORLD'], default 'TANGENT') - Space of the input normal.
        uv_map (str, optional) - UV Map for tangent space maps.
        strength (float, optional) - UV Map for tangent space maps.
        color (RGBA tuple, optional) - UV Map for tangent space maps.
        position (2D Vector, optional) - The position to insert the node in the node group.
        return (bpy.types.Node) - The Normal node.
        """
        node = group.nodes.get(name)
        if not node:
            node = group.nodes.new("ShaderNodeNormalMap")
            node.name = name
        if label is not None:
            node.label = label
        node.space = space
        node.uv_map = uv_map
        node.inputs["Strength"].default_value = strength
        node.inputs["Color"].default_value = color
        node.location = position
        return node

    @staticmethod
    def vector_rotate(
        group: bpy.types.NodeGroup,
        name: str,
        label: str = None,
        type: str = None,
        invert: bool = False,
        center: Vector = None,
        axis: Vector = None,
        angle: float = None,
        rotation: Vector = None,
        position: Vector = Vector((0, 0)),
    ) -> bpy.types.Node:
        """Add a Vector Rotate node.

        group (bpy.types.NodeGroup) - The node group to add the node to.
        name (str) - The name of the vector rotate node.
        label (str, optional) - The label of the vector rotate node.
        type (enum in ['AXIS_ANGLE', 'X_AXIS', 'Y_AXIS', 'Z_AXIS', 'EULER_XYZ'], default 'AXIS_ANGLE') - The type of the vector rotate node.
        invert (bool, optional) - Invert the rotation.
        center (3D Vector, optional) - The center of the rotation.
        axis (3D Vector, optional) - The axis of the rotation.
        angle (float, optional) - The angle of the rotation.
        rotation (3D Vector, optional) - The rotation of the rotation.
        position (2D Vector, optional) - The position of the node group.
        return (bpy.types.Node) - The Vector Rotate node.
        """
        node = group.nodes.get(name)
        if not node:
            node = group.nodes.new("ShaderNodeVectorRotate")
            node.name = name
        node.invert = invert
        if label is not None:
            node.label = label
        if type is not None:
            node.rotation_type = type
        if node.rotation_type in {
            "AXIS_ANGLE",
            "X_AXIS",
            "Y_AXIS",
            "Z_AXIS",
            "EULER_XYZ",
        }:
            if center is not None:
                node.inputs[1].default_value[0] = center[0]
                node.inputs[1].default_value[1] = center[1]
                node.inputs[1].default_value[2] = center[2]
            if node.rotation_type in {"AXIS_ANGLE"} and axis is not None:
                node.inputs[2].default_value[0] = axis[0]
                node.inputs[2].default_value[1] = axis[1]
                node.inputs[2].default_value[2] = axis[2]
            if node.rotation_type in {"EULER_XYZ"}:
                if rotation is not None:
                    node.inputs[4].default_value[0] = rotation[0]
                    node.inputs[4].default_value[1] = rotation[1]
                    node.inputs[4].default_value[2] = rotation[2]
            elif angle is not None:
                node.inputs[3].default_value = angle
        node.location = position
        return node

    # Converter
    @staticmethod
    def combine_xyz(
        group: bpy.types.NodeGroup,
        name: str,
        label: str = None,
        vector: Vector = None,
        position: Vector = Vector((0, 0)),
    ) -> bpy.types.Node:
        """Create a Combine XYZ node.

        group (bpy.types.NodeGroup) - The node group to add the node to.
        name (str) - The name of the combine xyz node.
        label (str, optional) - The label of the combine xyz node.
        vector (3D Vector, optional) - The vector inputs.
        position (2D Vector, optional) - The position to insert the node in the node group.
        return (bpy.types.Node) - The Combine XYZ node.
        """
        node = group.nodes.get(name)
        if not node:
            node = group.nodes.new("ShaderNodeCombineXYZ")
            node.name = name
        if label is not None:
            node.label = label
        if vector is not None:
            node.inputs[0].default_value = vector[0]
            node.inputs[1].default_value = vector[1]
            node.inputs[2].default_value = vector[2]
        node.location = position
        return node

    @staticmethod
    def color_ramp(
        group: bpy.types.NodeGroup,
        name: str,
        label: str = None,
        position: Vector = Vector((0, 0)),
    ) -> bpy.types.Node:
        """Create a Color Ramp node.

        group (bpy.types.NodeGroup) - The node group to add the node to.
        name (str) - The name of the color attribute node.
        label (str, optional) - The label of the color attribute node.
        position (2D Vector, optional) - The position to insert the node in the node group.
        return (bpy.types.Node) - The Color Ramp node.
        """
        node = group.nodes.get(name)
        if not node:
            node = group.nodes.new("ShaderNodeValToRGB")
            node.name = name
        if label is not None:
            node.label = label
        node.location = position
        return node

    @staticmethod
    def map_range(
        group: bpy.types.NodeGroup,
        name: str,
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
        """Create a Map Range node.

        group (bpy.types.NodeGroup) - The node group to add the node to.
        name (str) - The name of the map range node.
        label (str, optional) - The label of the map range node.
        type (enum in ['LINEAR', 'STEPPED', 'SMOOTHSTEP', 'SMOOTHERSTEP'], default 'LINEAR') - The type of the map range node.
        clamp (bool, optional) - Clamp the values.
        input_0 (float, optional) - The input 0 of the map range node.
        input_1 (float, optional) - The input 1 of the map range node.
        input_2 (float, optional) - The input 2 of the map range node.
        input_3 (float, optional) - The input 3 of the map range node.
        input_4 (float, optional) - The input 4 of the map range node.
        input_5 (float, optional) - The input 5 of the map range node.
        position (2D Vector, optional) - The position to insert the node in the node group.
        return (bpy.types.Node) - The Map Range node.
        """
        node = group.nodes.get(name)
        if not node:
            node = group.nodes.new("ShaderNodeMapRange")
            node.name = name
        if type is not None:
            node.interpolation_type = type
        if label is not None:
            node.label = label
        if input_0 is not None:
            node.inputs[0].default_value = input_0
        if input_1 is not None:
            node.inputs[1].default_value = input_1
        if input_2 is not None:
            node.inputs[2].default_value = input_2
        if input_3 is not None:
            node.inputs[3].default_value = input_3
        if input_4 is not None:
            node.inputs[4].default_value = input_4
        if node.interpolation_type in {"LINEAR", "STEPPED"}:
            node.clamp = clamp
        if node.interpolation_type in {"STEPPED"}:
            node.inputs[5].default_value = input_5
        node.location = position
        return node

    @staticmethod
    def math(
        group: bpy.types.NodeGroup,
        name: str,
        label: str = None,
        operation: str = None,
        use_clamp: bool = False,
        input_0: float = None,
        input_1: float = None,
        input_2: float = None,
        position: Vector = Vector((0, 0)),
    ) -> bpy.types.Node:
        """Create a Math node.

        group (bpy.types.NodeGroup) - The node group to add the node to.
        name (str) - The name of the math node.
        label (str, optional) - The label of the math node.
        operation (enum in [
            'ADD', 'SUBTRACT', 'MULTIPLY', 'DIVIDE', 'MULTIPLY_ADD',
            'POWER', 'LOGARITHM', 'SQRT', 'INVERSE_SQRT', 'ABSOLUTE', 'EXPONENT',
            'MINIMUM', 'MAXIMUM', 'LESS_THAN', 'GREATER_THAN', 'SIGN', 'COMPARE', 'SMOOTH_MIN', 'SMOOTH_MAX',
            'ROUND', 'FLOOR', 'CEIL', 'TRUNC',
            'FRACT', 'MODULO', 'WRAP', 'SNAP', 'PINGPONG',
            'SINE', 'COSINE', 'TANGENT',
            'ARCSINE', 'ARCCOSINE', 'ARCTANGENT', 'ARCTAN2',
            'SINH', 'COSH', 'TANH',
            'RADIANS', 'DEGREES'
        ], default 'ADD') - The operation of the math node.
        use_clamp (bool, optional) - Use clamp.
        input_0 (float, optional) - The input 0.
        input_1 (float, optional) - The input 1.
        input_2 (float, optional) - The input 2.
        position (2D Vector, optional) - The position to insert the node in the node group.
        return (bpy.types.Node) - The Math node.
        """
        node = group.nodes.get(name)
        if not node:
            node = group.nodes.new("ShaderNodeMath")
            node.name = name
        node.use_clamp = use_clamp
        if operation is not None:
            node.operation = operation
        if label is not None:
            node.label = label
        if (
            operation
            in {
                "SQRT",
                "INVERSE_SQRT",
                "ABSOLUTE",
                "EXPONENT",
                "SIGN",
                "ROUND",
                "FLOOR",
                "CEIL",
                "TRUNC",
                "FRACT",
                "SINE",
                "COSINE",
                "TANGENT",
                "ARCSINE",
                "ARCCOSINE",
                "ARCTANGENT",
                "SINH",
                "COSH",
                "TANH",
                "RADIANS",
                "DEGREES",
            }
            and input_0 is not None
        ):
            node.inputs[0].default_value = input_0
        if input_0 is not None:
            node.inputs[0].default_value = input_0
        if input_1 is not None:
            node.inputs[1].default_value = input_1
        if operation in {"MULTIPLY_ADD", "COMPARE", "SMOOTH_MIN", "SMOOTH_MAX", "WRAP"} and input_2 is not None:
            node.inputs[2].default_value = input_2
        node.location = position
        return node

    @staticmethod
    def separate_color(
        group: bpy.types.NodeGroup,
        name: str,
        label: str = None,
        mode: str = "RGB",
        color: tuple = (0.8, 0.8, 0.8, 1),
        position: Vector = Vector((0, 0)),
    ) -> bpy.types.Node:
        """Create a Separate Color node.

        group (bpy.types.NodeGroup) - The node group to add the node to.
        name (str) - The name of the separate xyz node.
        label (str, optional) - The label of the separate xyz node.
        mode (enum in ['RGB', 'HSV', 'HSL'], default 'RGB') - The vector inputs.
        color (RGBA tuple, optional) - The vector inputs.
        position (2D Vector, optional) - The position to insert the node in the node group.
        return (bpy.types.Node) - The Separate Color node.
        """
        node = group.nodes.get(name)
        if not node:
            node = group.nodes.new("ShaderNodeSeparateColor")
            node.name = name
        if label is not None:
            node.label = label
        node.mode = mode
        node.inputs["Color"].default_value = color
        node.location = position
        return node

    @staticmethod
    def separate_xyz(
        group: bpy.types.NodeGroup,
        name: str,
        label: str = None,
        vector: Vector = None,
        position: Vector = Vector((0, 0)),
    ) -> bpy.types.Node:
        """Create a Separate XYZ node.

        group (bpy.types.NodeGroup) - The node group to add the node to.
        name (str) - The name of the separate xyz node.
        label (str, optional) - The label of the separate xyz node.
        vector (3D Vector, optional) - The vector inputs.
        position (2D Vector, optional) - The position to insert the node in the node group.
        return (bpy.types.Node) - The Separate XYZ node.
        """
        node = group.nodes.get(name)
        if not node:
            node = group.nodes.new("ShaderNodeSeparateXYZ")
            node.name = name
        if label is not None:
            node.label = label
        if vector is not None:
            node.inputs[0].default_value[0] = vector[0]
            node.inputs[0].default_value[1] = vector[1]
            node.inputs[0].default_value[2] = vector[2]
        node.location = position
        return node

    @staticmethod
    def vector_math(
        group: bpy.types.NodeGroup,
        name: str,
        label: str = None,
        operation: str = None,
        input_0: Vector = None,
        input_1: Vector = None,
        input_2: Vector = None,
        input_3: Vector = None,
        position: Vector = Vector((0, 0)),
    ) -> bpy.types.Node:
        """Create a Vector Math node.

        group (bpy.types.NodeGroup) - The node group to add the node to.
        name (str) - The name of the vector math node.
        label (str, optional) - The label of the vector math node.
        operation (enum in [
            'ADD', 'SUBTRACT', 'MULTIPLY', 'DIVIDE', 'MULTIPLY_ADD',
            'CROSS_PRODUCT', 'PROJECT', 'REFLECT', 'REFRACT', 'FACEFORWARD', 'DOT_PRODUCT',
            'DISTANCE', 'LENGTH', 'SCALE',
            'NORMALIZE',
            'ABSOLUTE', 'MINIMUM', 'MAXIMUM', 'FLOOR', 'CEIL', 'FRACTION', 'MODULO', 'WRAP', 'SNAP',
            'SINE', 'COSINE', 'TANGENT'
        ], default 'ADD') - The operation of the vector math node.
        input_0 (3D Vector, optional) - The first vector input.
        input_1 (3D Vector, optional) - The second vector input.
        input_2 (3D Vector, optional) - The third vector input.
        input_3 (float, optional) - The fourth float input.
        position (2D Vector, optional) - The position to insert the node in the node group.
        return (bpy.types.Node) - The Vector Math node.
        """
        node = group.nodes.get(name)
        if not node:
            node = group.nodes.new("ShaderNodeVectorMath")
            node.name = name
        if operation is not None:
            node.operation = operation
        if label is not None:
            node.label = label
        if operation in {
            "MULTIPLY_ADD",
            "DOT_PRODUCT",
            "REFRACT",
            "FACEFORWARD",
            "WRAP",
        }:
            if input_0 is not None:
                node.inputs[0].default_value[0] = input_0[0]
                node.inputs[0].default_value[1] = input_0[1]
                node.inputs[0].default_value[2] = input_0[2]
            if input_1 is not None:
                node.inputs[1].default_value[0] = input_1[0]
                node.inputs[1].default_value[1] = input_1[1]
                node.inputs[1].default_value[2] = input_1[2]
            if operation in {"REFRACT"}:
                if input_0 is not None:
                    node.inputs[0].default_value[0] = input_0[0]
                    node.inputs[0].default_value[1] = input_0[1]
                    node.inputs[0].default_value[2] = input_0[2]
                if input_1 is not None:
                    node.inputs[1].default_value[0] = input_1[0]
                    node.inputs[1].default_value[1] = input_1[1]
                    node.inputs[1].default_value[2] = input_1[2]
                if input_3 is not None:
                    node.inputs[3].default_value = input_3
            elif input_2 is not None:
                node.inputs[2].default_value[0] = input_2[0]
                node.inputs[2].default_value[1] = input_2[1]
                node.inputs[2].default_value[2] = input_2[2]
        if input_0 is not None:
            node.inputs[0].default_value[0] = input_0[0]
            node.inputs[0].default_value[1] = input_0[1]
            node.inputs[0].default_value[2] = input_0[2]
        if operation not in {
            "MULTIPLY_ADD",
            "LENGTH",
            "NORMALIZE",
            "ABSOLUTE",
            "FLOOR",
            "CEIL",
            "FRACTION",
            "SINE",
            "COSINE",
            "TANGENT",
        }:
            if operation in {"SCALE"}:
                if input_3 is not None:
                    node.inputs[3].default_value = input_3
            elif input_1 is not None:
                node.inputs[1].default_value[0] = input_1[0]
                node.inputs[1].default_value[1] = input_1[1]
                node.inputs[1].default_value[2] = input_1[2]
        node.location = position
        return node
