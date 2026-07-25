import bpy
from mathutils import Vector


class CompositorNode:
    # Input
    @staticmethod
    def image(
        group: bpy.types.NodeGroup,
        name: str,
        label: str = None,
        image: bpy.types.Image = None,
        hide: bool = True,
        position: Vector = Vector((0, 0)),
    ) -> bpy.types.Node:
        """Create an Image node.

        group (bpy.types.NodeGroup) - The node group to add the node to.
        name (str) - Unique node identifier.
        label (str, optional) - Optional custom node label.
        image (bpy.types.Image, optional) - Image data-block referencing an external or packed image.
        position (2D Vector, optional) - The position to insert the node in the node group.
        return (bpy.types.Node) - The Image node.
        """
        node = group.nodes.get(name)
        if not node:
            node = group.nodes.new("CompositorNodeImage")
            node.name = name
        if label is not None:
            node.label = label
        node.image = image
        node.hide = hide
        node.location = position
        return node

    # Output

    @staticmethod
    def composite(
        group: bpy.types.NodeGroup,
        name: str = "Composite",
        label: str = None,
        use_alpha: bool = True,
        position: Vector = Vector((0, 0)),
    ) -> bpy.types.Node:
        """Create a Composite node.

        group (bpy.types.NodeGroup) - The node group to add the node to.
        name (str, optional) - Unique node identifier.
        label (str, optional) - Optional custom node label.
        use_alpha (bool, optional) - Colors are treated alpha premultiplied. or colors output straight (alpha gets set to 1).
        position (2D Vector, optional) - The position to insert the node in the node group.
        return (bpy.types.Node) - The Composite node.
        """
        node = group.nodes.get(name)
        if not node:
            node = group.nodes.new("CompositorNodeComposite")
            node.name = name
        if label is not None:
            node.label = label
        node.use_alpha = use_alpha
        node.location = position
        return node

    @staticmethod
    def file_output(
        group: bpy.types.NodeGroup,
        name: str = "File Output",
        label: str = None,
        base_path: str = bpy.app.tempdir,
        position: Vector = Vector((0, 0)),
    ) -> bpy.types.Node:
        """Create a File Output node.

        group (bpy.types.NodeGroup) - The node group to add the node to.
        name (str, optional) - Unique node identifier.
        label (str, optional) - Optional custom node label.
        base_path (str, optional) - Base output path for the image.
        position (2D Vector, optional) - The position to insert the node in the node group.
        return (bpy.types.Node) - The File Output node.
        """
        node = group.nodes.get(name)
        if not node:
            node = group.nodes.new("CompositorNodeOutputFile")
            node.name = name
        if label is not None:
            node.label = label
        node.base_path = base_path
        node.location = position
        return node

    @staticmethod
    def viewer(
        group: bpy.types.NodeGroup,
        name: str = "Viewer",
        label: str = None,
        use_alpha: bool = True,
        position: Vector = Vector((0, 0)),
    ) -> bpy.types.Node:
        """Create a Viewer node.

        group (bpy.types.NodeGroup) - The node group to add the node to.
        name (str, optional) - Unique node identifier.
        label (str, optional) - Optional custom node label.
        use_alpha (bool, optional) - Colors are treated alpha premultiplied. or colors output straight (alpha gets set to 1).
        position (2D Vector, optional) - The position to insert the node in the node group.
        return (bpy.types.Node) - The Viewer node.
        """
        node = group.nodes.get(name)
        if not node:
            node = group.nodes.new("CompositorNodeViewer")
            node.name = name
        if label is not None:
            node.label = label
        node.use_alpha = use_alpha
        node.location = position
        return node

    # Converter

    @staticmethod
    def combine_color(
        group: bpy.types.NodeGroup,
        name: str = "Combine Color",
        label: str = None,
        mode: str = "RGB",
        position: Vector = Vector((0, 0)),
    ) -> bpy.types.Node:
        """Create a Combine Color node.

        group (bpy.types.NodeGroup) - The node group to add the node to.
        name (str, optional) - Unique node identifier.
        label (str, optional) - Optional custom node label.
        mode (enum in ['RGB', 'HSV', 'HSL', 'YCC', 'YUV'], optional) - Mode of color processing.
        position (2D Vector, optional) - The position to insert the node in the node group.
        return (bpy.types.Node) - The Combine Color node.
        """
        node = group.nodes.get(name)
        if not node:
            node = group.nodes.new("CompositorNodeCombineColor")
            node.name = name
        if label is not None:
            node.label = label
        node.mode = mode
        node.location = position
        return node

    @staticmethod
    def separate_color(
        group: bpy.types.NodeGroup,
        name: str = "Separate Color",
        label: str = None,
        mode: str = "RGB",
        position: Vector = Vector((0, 0)),
    ) -> bpy.types.Node:
        """Create a Separarte Color node.

        group (bpy.types.NodeGroup) - The node group to add the node to.
        name (str, optional) - Unique node identifier.
        label (str, optional) - Optional custom node label.
        mode (enum in ['RGB', 'HSV', 'HSL', 'YCC', 'YUV'], optional) - Mode of color processing.
        position (2D Vector, optional) - The position to insert the node in the node group.
        return (bpy.types.Node) - The Separarte Color node.
        """
        node = group.nodes.get(name)
        if not node:
            node = group.nodes.new("CompositorNodeSeparateColor")
            node.name = name
        if label is not None:
            node.label = label
        node.mode = mode
        node.location = position
        return node

    # Filter

    @staticmethod
    def denoise(
        group: bpy.types.NodeGroup,
        name: str = "Denoise",
        label: str = None,
        prefilter: str = "ACCURATE",
        use_hdr: bool = True,
        position: Vector = Vector((0, 0)),
    ) -> bpy.types.Node:
        """Create a Denoise node.

        group (bpy.types.NodeGroup) - The node group to add the node to.
        name (str, optional) - Unique node identifier.
        label (str, optional) - Optional custom node label.
        prefilter (enum in ['NONE', 'ACCURATE', 'FAST'], default 'ACCURATE') - Denoise image and guiding passes together. Improves quality whrn guiding passed are noisy using least anount of extra processing time.
        use_hdr (bool) - Precess HDR images.
        position (2D Vector, optional) - The position to insert the node in the node group.
        return (bpy.types.Node) - The Denoise node.
        """
        node = group.nodes.get(name)
        if not node:
            node = group.nodes.new("CompositorNodeDenoise")
            node.name = name
        if label is not None:
            node.label = label
        node.prefilter = prefilter
        node.use_hdr = use_hdr
        node.location = position
        return node
