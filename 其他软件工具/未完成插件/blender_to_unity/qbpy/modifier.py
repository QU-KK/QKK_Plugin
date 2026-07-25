import bpy
from .mesh import Mesh
from math import radians


class Modifier:
    # Array Modifier
    @staticmethod
    def add_array_modifier(
        object: bpy.types.Object,
        name: str = "Array",
        relative_offset: bool = True,
        constant_offset: bool = False,
        object_offset: bool = False,
        merge_vertices: bool = False,
        check: bool = True,
    ) -> bpy.types.Modifier:
        """Add an array modifier.

        object (bpy.types.Object) - The object to add the modifier to.
        name (str, optional) - The name of the modifier.
        check (bool, optional) - Check if the modifier exists.
        return (bpy.types.Modifier) - Array modifier.
        """
        if check:
            array = object.modifiers.get(name)
            if not array:
                array = object.modifiers.new(name, "ARRAY")
        else:
            array = object.modifiers.new(name, "ARRAY")

        array.use_relative_offset = relative_offset
        array.use_constant_offset = constant_offset
        array.use_object_offset = object_offset
        array.use_merge_vertices = merge_vertices
        return array

    # Bevel Modifier
    @staticmethod
    def add_bevel_modifier(
        object: bpy.types.Object,
        name: str = "Bevel",
        affect: str = "EDGES",
        offset_type: str = "OFFSET",
        width: float = 0.1,
        segments: int = 1,
        angle_limit: float = 30,
        limit_method: str = "ANGLE",
        vertex_group: str = "",
        profile_type: str = "SUPERELLIPSE",
        profile: float = 0.5,
        miter_outer: str = "MITER_SHARP",
        miter_inner: str = "MITER_SHARP",
        vmesh_method: str = "ADJ",
        use_clamp_overlap: bool = True,
        loop_slide: bool = True,
        harden_normals: bool = False,
        mark_seam: bool = False,
        mark_sharp: bool = False,
        material: int = -1,
        face_strength_mode: str = "FSTR_NONE",
        check: bool = True,
    ) -> bpy.types.Modifier:
        """Add a bevel modifier.

        object (bpy.types.Object) - The object to add the modifier to.
        name (str, optional) - The name of the modifier.
        affect (enum in ['VERTICES', 'EDGES'], default 'EDGES') - The type of bevel.
        offset_type (enum in ['OFFSET', 'WIDTH', 'DEPTH', 'PERCENT', 'ABSOLUTE'], default 'OFFSET') - Width Type
        width (float) - Bevel amount.
        segments (int) - Number of segments.
        limit_method (enum in ['NONE', 'ANGLE', 'WEIGHT', 'VGROUP'], default 'ANGLE') - The method of limiting the bevel.
        angle_limit (int, optional) - The angle of the bevel.
        vertex_group (str, optional) - The name of the vertex group to use.
        profile_type (enum in ['SUPERELLIPSE', 'CUSTOM'], default 'SUPERELLIPSE') - Profile Type.
        profile (float) - The profile shape (0.5 = round).
        miter_outer (enum in ['MITER_SHARP', 'MITER_PATCH', 'MITER_ARC'], default 'MITER_SHARP') - Milter Outer.
        miter_inner (enum in ['MITER_SHARP', 'MITER_ARC'], default 'MITER_SHARP') - Milter Inner.
        vmesh_method (enum in ['ADJ', 'CUTOFF'], default 'ADJ') - Interdections.
        use_clamp_overlap (bool) - Clamp Overlap.
        loop_slide (bool) - Loop Slide.
        harden_normals (bool) - Harden Normals.
        mark_seam (bool) - Mark Seam.
        mark_sharp (bool) - Mark Sharp.
        material (int) - Material Index.
        face_strength_mode (enum in ['FSTR_NONE', 'FSTR_NEW', 'FSTR_AFFECTED', 'FSTR_ALL'], default 'FSTR_NONE') - Face Strength
        check (bool, optional) - Check if the modifier exists.
        return (bpy.types.Modifier) - Bevel modifier.
        """
        if check:
            bevel = object.modifiers.get(name)
            if not bevel:
                bevel = object.modifiers.new(name, "BEVEL")
        else:
            bevel = object.modifiers.new(name, "BEVEL")

        bevel.affect = affect
        bevel.offset_type = offset_type
        bevel.width = width
        bevel.segments = segments
        bevel.limit_method = limit_method
        bevel.angle_limit = radians(angle_limit)
        bevel.vertex_group = vertex_group
        bevel.profile_type = profile_type
        bevel.profile = profile
        bevel.miter_outer = miter_outer
        bevel.miter_inner = miter_inner
        bevel.vmesh_method = vmesh_method
        bevel.use_clamp_overlap = use_clamp_overlap
        bevel.loop_slide = loop_slide
        bevel.harden_normals = harden_normals
        bevel.mark_seam = mark_seam
        bevel.mark_sharp = mark_sharp
        bevel.material = material
        bevel.face_strength_mode = face_strength_mode
        return bevel

    # Boolean Modifier
    @staticmethod
    def add_boolean_modifier(
        object: bpy.types.Object,
        bool_object,
        operation="DIFFERENCE",
        solver: str = "EXACT",
        use_self: bool = False,
        use_hole_tolerant: bool = False,
        check: bool = True,
    ) -> bpy.types.Modifier:
        """Add a boolean modifier.

        object (bpy.types.Object) - The object to add the modifier to.
        bool_object (bpy.types.Object) - The object to use for the boolean operation.
        operation (enum in ['DIFFERENCE', 'UNION', 'INTERSECT'], default 'DIFFERENCE') - The operation to perform on the object.
        solver (enum in ['EXACT', 'FAST'], default 'EXACT') - The solver for the boolean operation.
        use_self (bool) - Self Intersection.
        use_hole_tolerant (bool) - Hole Tolerant.
        check (bool, optional) - Check if the modifier exists.
        return (bpy.types.Modifier) - Boolean modifier.
        """
        if check:
            boolean = object.modifiers.get("Boolean")
            if not boolean:
                boolean = object.modifiers.new("Boolean", "BOOLEAN")
            boolean.operation = operation
            boolean.object = bool_object
            boolean.solver = solver
            boolean.use_self = use_self
            boolean.use_hole_tolerant = use_hole_tolerant
        else:
            boolean = object.modifiers.new("Boolean", "BOOLEAN")
            boolean.operation = operation
            boolean.object = bool_object
            boolean.solver = solver
            boolean.use_self = use_self
            boolean.use_hole_tolerant = use_hole_tolerant
        return boolean

    # Decimate Modifier
    @staticmethod
    def add_decimate_modifier(
        object: bpy.types.Object,
        name: str = "Decimate",
        decimate_type: str = "DISSOLVE",
        angle_limit: float = 0.05,
        delimit: str = None,
        check: bool = True,
    ) -> bpy.types.Modifier:
        """Add a decimate modifier.

        object (bpy.types.Object) - The object to add the modifier to.
        name (str, optional) - The name of the modifier.
        check (bool, optional) - Check if the modifier exists.
        return (bpy.types.Modifier) - Decimate modifier.
        """
        if delimit is None:
            delimit = {"SHARP", "NORMAL"}
        if check:
            decimate = object.modifiers.get(name)
            if not decimate:
                decimate = object.modifiers.new(name, "DECIMATE")
                decimate.decimate_type = decimate_type
                decimate.angle_limit = radians(angle_limit)
                decimate.delimit = delimit
        else:
            decimate = object.modifiers.new(name, "DECIMATE")
            decimate.decimate_type = decimate_type
            decimate.angle_limit = radians(angle_limit)
            decimate.delimit = delimit
        return decimate

    # Geometry Node Modifier
    @staticmethod
    def add_geometry_node_modifier(
        object: bpy.types.Object,
        name: str = "GeometryNodes",
        node_group=None,
        check: bool = True,
    ) -> bpy.types.Modifier:
        """Add a geometry node modifier.

        object (bpy.types.Object) - The object to add the modifier to.
        name (str, optional) - The name of the modifier.
        node_group (bpy.types.NodeGroup, optional) - The node group to use.
        check (bool, optional) - Check if the modifier exists.
        return (bpy.types.Modifier) - Modifier.
        """
        if check:
            geometry_node = object.modifiers.get(name)
            if not geometry_node:
                geometry_node = object.modifiers.new(name, "NODES")
            if node_group is not None:
                geometry_node.node_group = node_group
        else:
            geometry_node = object.modifiers.new(name, "NODES")
            if node_group is not None:
                geometry_node.node_group = node_group
        return geometry_node

    # Edge Split Modifier
    @staticmethod
    def add_edge_split_modifier(object: bpy.types.Object, name: str = "EdgeSplit", check: bool = True) -> bpy.types.Modifier:
        """Add an edge split modifier.

        object (bpy.types.Object) - The object to add the modifier to.
        name (str, optional) - The name of the modifier.
        check (bool, optional) - Check if the modifier exists.
        return (bpy.types.Modifier) - Edge Split modifier.
        """
        if check:
            edge_split = object.modifiers.get(name)
            if not edge_split:
                edge_split = object.modifiers.new(name, "EDGE_SPLIT")
        else:
            edge_split = object.modifiers.new(name, "EDGE_SPLIT")
        return edge_split

    # Mirror Modifier
    @staticmethod
    def add_mirror_modifier(
        object: bpy.types.Object,
        name: str = "Mirror",
        mirror_object=None,
        use_clip=True,
        check: bool = True,
    ) -> bpy.types.Modifier:
        """Add a mirror modifier.

        object (bpy.types.Object) - The object to add the modifier to.
        name (str, optional) - The name of the modifier.
        mirror_object (bpy.types.Object, optional) - Object to use as mirror.
        use_clip (bool, optional) - Prevent vertices from going through the mirror during transfrom.
        check (bool, optional) - Check if the modifier exists.
        return (bpy.types.Modifier) - Mirror modifier.
        """
        if check:
            mirror = object.modifiers.get(name)
            if not mirror:
                mirror = object.modifiers.new(name, "MIRROR")
                mirror.use_axis[0] = False
            if mirror_object is not None:
                mirror.mirror_object = mirror_object
            mirror.use_clip = use_clip
        else:
            mirror = object.modifiers.new(name, "MIRROR")
            mirror.use_axis[0] = False
            if mirror_object is not None:
                mirror.mirror_object = mirror_object
            mirror.use_clip = use_clip
        return mirror

    # Remesh Modifier
    @staticmethod
    def add_remesh_modifier(
        object: bpy.types.Object,
        name: str = "Remesh",
        mode=None,
        smooth_shading=True,
        check: bool = True,
    ) -> bpy.types.Modifier:
        """Add a remesh modifier.

        object (bpy.types.Object) - The object to add the modifier to.
        name (str, optional) - The name of the modifier.
        mode (str, optional) - The mode to use.
        smooth_shading (bool, optional) - Smooth shading.
        check (bool, optional) - Check if the modifier exists.
        return (bpy.types.Modifier) - Remesh modifier.
        """
        if check:
            remesh = object.modifiers.get(name)
            if not remesh:
                remesh = object.modifiers.new(name, "REMESH")
            if mode is not None:
                remesh.mode = mode
            remesh.use_smooth_shade = smooth_shading
        else:
            remesh = object.modifiers.new(name, "REMESH")
            if mode is not None:
                remesh.mode = mode
            remesh.use_smooth_shade = smooth_shading
        return remesh

    # Screw Modifier
    @staticmethod
    def add_screw_modifier(object: bpy.types.Object, name: str = "Screw", check: bool = True) -> bpy.types.Modifier:
        """Add a screw modifier.

        object (bpy.types.Object) - The object to add the modifier to.
        name (str, optional) - The name of the modifier.
        check (bool, optional) - Check if the modifier exists.
        return (bpy.types.Modifier) - Screw modifier.
        """
        if check:
            screw = object.modifiers.get(name)
            if not screw:
                screw = object.modifiers.new(name, "SCREW")
                screw.steps = 36
                screw.render_steps = 36
        else:
            screw = object.modifiers.new(name, "SCREW")
            screw.steps = 36
            screw.render_steps = 36
        return screw

    # Skin Modifier
    @staticmethod
    def add_skin_modifier(object: bpy.types.Object, name: str = "Skin", check: bool = True) -> bpy.types.Modifier:
        """Add a skin modifier.

        object (bpy.types.Object) - The object to add the modifier to.
        name (str, optional) - The name of the modifier.
        check (bool, optional) - Check if the modifier exists.
        return (bpy.types.Modifier) - Skin modifier.
        """
        if check:
            skin = object.modifiers.get(name)
            if not skin:
                skin = object.modifiers.new(name, "SKIN")
                skin.use_smooth_shade = True
                skin.use_x_symmetry = False
                skin.use_y_symmetry = False
                skin.use_z_symmetry = False
        else:
            skin = object.modifiers.new(name, "SKIN")
            skin.use_smooth_shade = True
            skin.use_x_symmetry = False
            skin.use_y_symmetry = False
            skin.use_z_symmetry = False
        return skin

    # Solidify Modifier
    @staticmethod
    def add_solidify_modifier(
        object: bpy.types.Object,
        name: str = "Solidify",
        offset: float = 0.0,
        use_even_offset: bool = True,
        use_quality_normals: bool = True,
        check: bool = True,
    ) -> bpy.types.Modifier:
        """Add a solidify modifier.

        object (bpy.types.Object) - The object to add the modifier to.
        name (str, optional) - The name of the modifier.
        offset (float, optional) - The offset to use for the modifier.
        use_even_offset (bool, optional) - Whether to use even offset or not.
        use_quality_normals (bool, optional) - Whether to use quality normals or not.
        check (bool, optional) - Check if the modifier exists.
        return (bpy.types.Modifier) - Solidify modifier.
        """
        if check:
            solidify = object.modifiers.get(name)
            if not solidify:
                solidify = object.modifiers.new(name, "SOLIDIFY")
                solidify.offset = offset
                solidify.use_even_offset = use_even_offset
                solidify.use_quality_normals = use_quality_normals
        else:
            solidify = object.modifiers.new(name, "SOLIDIFY")
            solidify.offset = offset
            solidify.use_even_offset = use_even_offset
            solidify.use_quality_normals = use_quality_normals
        return solidify

    # Subsurf Modifier
    @staticmethod
    def add_subsurf_modifier(
        object: bpy.types.Object,
        name: str = "Subdivision",
        subdivision_type: str = "CATMULL_CLARK",
        check: bool = True,
    ) -> bpy.types.Modifier:
        """Add a subdivision surface modifier.

        object (bpy.types.Object) - The object to add the modifier to.
        name (str, optional) - The name of the modifier.
        subdivision_type (str, optional) - The subdivision type to use for the modifier.
        check (bool, optional) - Check if the modifier exists.
        return (bpy.types.Modifier) - Subsurf modifier.
        """
        if check:
            subsurf = object.modifiers.get(name)
            if not subsurf:
                subsurf = object.modifiers.new(name, "SUBSURF")
                subsurf.subdivision_type = subdivision_type
                subsurf.levels = 2
        else:
            subsurf = object.modifiers.new(name, "SUBSURF")
            subsurf.subdivision_type = subdivision_type
            subsurf.levels = 2
        return subsurf

    # Triangulate Modifier
    @staticmethod
    def add_triangulate_modifier(object: bpy.types.Object, name: str = "Triangulate", check: bool = True) -> bpy.types.Modifier:
        """Add a triangulate modifier.

        object (bpy.types.Object) - The object to add the modifier to.
        name (str, optional) - The name of the modifier.
        check (bool, optional) - Check if the modifier exists.
        return (bpy.types.Modifier) - Triangulate modifier.
        """
        if check:
            triangulate = object.modifiers.get(name)
            if not triangulate:
                triangulate = object.modifiers.new(name, "TRIANGULATE")
                triangulate.min_vertices = 5
        else:
            triangulate = object.modifiers.new(name, "TRIANGULATE")
            triangulate.min_vertices = 5
        return triangulate

    # Weld Modifier
    @staticmethod
    def add_weld_modifier(object: bpy.types.Object, name: str = "Weld", check: bool = True) -> bpy.types.Modifier:
        """Add a weld modifier.

        object (bpy.types.Object) - The object to add the modifier to.
        name (str, optional) - The name of the modifier.
        check (bool, optional) - Check if the modifier exists.
        return (bpy.types.Modifier) - Weld modifier.
        """
        if check:
            weld = object.modifiers.get(name)
            if not weld:
                weld = object.modifiers.new(name, "WELD")
        else:
            weld = object.modifiers.new(name, "WELD")
        return weld

    # Wireframe Modifier
    @staticmethod
    def add_wireframe_modifier(object: bpy.types.Object, name: str = "Wireframe", check: bool = True) -> bpy.types.Modifier:
        """Add a wireframe modifier.

        object (bpy.types.Object) - The object to add the modifier to.
        name (str, optional) - The name of the modifier.
        check (bool, optional) - Check if the modifier exists.
        return (bpy.types.Modifier) - Wireframe modifier.
        """
        if check:
            wireframe = object.modifiers.get(name)
            if not wireframe:
                wireframe = object.modifiers.new(name, "WIREFRAME")
                wireframe.use_boundary = True
        else:
            wireframe = object.modifiers.new(name, "WIREFRAME")
            wireframe.use_boundary = True
        return wireframe

    # Weighted Normal Modifier
    @staticmethod
    def add_wnormal_modifier(object: bpy.types.Object, name: str = "WeightedNormal", check: bool = True) -> bpy.types.Modifier:
        """Add a weighted normal modifier.

        object (bpy.types.Object) - The object to add the modifier to.
        name (str, optional) - The name of the modifier.
        check (bool, optional) - Check if the modifier exists.
        return (bpy.types.Modifier) - Weighted Normal modifier.
        """
        if check:
            wnormal = object.modifiers.get(name)
            if not wnormal:
                wnormal = object.modifiers.new(name, "WEIGHTED_NORMAL")
        else:
            wnormal = object.modifiers.new(name, "WEIGHTED_NORMAL")
        return wnormal

    # Cast Modifier
    @staticmethod
    def add_cast_modifier(object: bpy.types.Object, name: str = "Cast", check: bool = True) -> bpy.types.Modifier:
        """Add a cast modifier.

        object (bpy.types.Object) - The object to add the modifier to.
        name (str, optional) - The name of the modifier.
        check (bool, optional) - Check if the modifier exists.
        return (bpy.types.Modifier) - Cast modifier.
        """
        if check:
            cast = object.modifiers.get(name)
            if not cast:
                cast = object.modifiers.new(name, "CAST")
        else:
            cast = object.modifiers.new(name, "CAST")
        return cast

    # Curve Modifier
    @staticmethod
    def add_curve_modifier(
        object: bpy.types.Object,
        name: str = "Curve",
        curve_object: bpy.types.Curve = None,
        deform_axis: str = "POS_X",
        vertex_group: str = "",
        check: bool = True,
    ) -> bpy.types.Modifier:
        """Add a curve modifier.

        object (bpy.types.Object) - The object to add the modifier to.
        name (str, optional) - Modifier name.
        curve_object (bpy.types.Curve) - Curve object to deform with.
        deform_axis (enum in ['POS_X', 'POS_Y', 'POS_Z', 'NEG_X', 'NEG_Y', 'NEG_Z'], default 'POS_X') - The axis that the curve deforms along.
        vertex_group (str, optional) - Name of Vertex Group which determines influence of modifier per point.
        check (bool, optional) - Check if the modifier exists.
        return (bpy.types.Modifier) - Curve modifier.
        """
        if check:
            curve = object.modifiers.get(name) or object.modifiers.new(name, "CURVE")
        else:
            curve = object.modifiers.new(name, "CURVE")

        curve.object = curve_object
        curve.deform_axis = deform_axis
        curve.vertex_group = vertex_group
        return curve

    # Displace Modifier
    @staticmethod
    def add_displace_modifier(
        object: bpy.types.Object,
        name: str = "Displace",
        strength=1.0,
        mid_level=0.5,
        check: bool = True,
    ) -> bpy.types.Modifier:
        """Add a displace modifier.

        object (bpy.types.Object) - The object to add the modifier to.
        name (str, optional) - The name of the modifier.
        strength (float, optional) - The strength of the modifier.
        mid_level (float, optional) - The mid-level of the modifier.
        check (bool, optional) - Check if the modifier exists.
        return (bpy.types.Modifier) - Displace modifier.
        """
        if check:
            displace = object.modifiers.get(name)
            if not displace:
                displace = object.modifiers.new(name, "DISPLACE")
                displace.strength = strength
                displace.mid_level = mid_level
        else:
            displace = object.modifiers.new(name, "DISPLACE")
            displace.strength = strength
            displace.mid_level = mid_level
        return displace

    # Shrinkwrap Modifier
    @staticmethod
    def add_shrinkwrap_modifier(object: bpy.types.Object, target, name: str = "Shrinkwrap", check: bool = True) -> bpy.types.Modifier:
        """Add a shrinkwrap modifier.

        object (bpy.types.Object) - The object to add the modifier to.
        target (bpy.types.Object) - The object to use as the target.
        name (str, optional) - The name of the modifier.
        check (bool, optional) - Check if the modifier exists.
        return (bpy.types.Modifier) - Shrinkwrap modifier.
        """
        if check:
            shrinkwrap = object.modifiers.get(name)
            if not shrinkwrap:
                shrinkwrap = object.modifiers.new(name, "SHRINKWRAP")
                shrinkwrap.wrap_method = "PROJECT"
                shrinkwrap.use_negative_direction = True
                shrinkwrap.use_invert_cull = True
                shrinkwrap.target = target
        else:
            shrinkwrap = object.modifiers.new(name, "SHRINKWRAP")
            shrinkwrap.wrap_method = "PROJECT"
            shrinkwrap.use_negative_direction = True
            shrinkwrap.use_invert_cull = True
            shrinkwrap.target = target
        return shrinkwrap

    # Simple Deform Modifier
    @staticmethod
    def add_deform_modifier(
        object: bpy.types.Object,
        name: str = "SimpleDeform",
        deform_method="TWIST",
        check: bool = True,
    ) -> bpy.types.Modifier:
        """Add a simple Deform modifier.

        object (bpy.types.Object) - The object to add the modifier to.
        name (str, optional) - The name of the modifier.
        deform_method (enum in ['TWIST', 'BEND', 'TAPER', 'STRETCH'], default 'TWIST') - The deform method to use.
        check (bool, optional) - Check if the modifier exists.
        return (bpy.types.Modifier) - Simple Deform modifier.
        """
        if check:
            deform = object.modifiers.get(name)
            if not deform:
                deform = object.modifiers.new(name, "SIMPLE_DEFORM")
                deform.deform_method = deform_method
                deform.angle = radians(45)
                deform.deform_axis = "X"
        else:
            deform = object.modifiers.new(name, "SIMPLE_DEFORM")
            deform.deform_method = deform_method
            deform.angle = radians(45)
            deform.deform_axis = "X"
        return deform

    # Smooth Modifier
    @staticmethod
    def add_smooth_modifier(object: bpy.types.Object, name: str = "Smooth", check: bool = True) -> bpy.types.Modifier:
        """Add a smooth modifier.

        object (bpy.types.Object) - The object to add the modifier to.
        name (str, optional) - The name of the modifier.
        check (bool, optional) - Check if the modifier exists.
        return (bpy.types.Modifier) - Smooth modifier.
        """
        if check:
            smooth = object.modifiers.get(name)
            if not smooth:
                smooth = object.modifiers.new(name, "SMOOTH")
        else:
            smooth = object.modifiers.new(name, "SMOOTH")
        return smooth

    # Smooth Corrective Modifier
    @staticmethod
    def add_smooth_corrective_modifier(object: bpy.types.Object, name: str = "CorrectiveSmooth", check: bool = True) -> bpy.types.Modifier:
        """Add a smooth corrective modifier.

        object (bpy.types.Object) - The object to add the modifier to.
        name (str, optional) - The name of the modifier.
        check (bool, optional) - Check if the modifier exists.
        return (bpy.types.Modifier) - Smooth Corrective modifier.
        """
        if check:
            corrective_smooth = object.modifiers.get(name)
            if not corrective_smooth:
                corrective_smooth = object.modifiers.new(name, "CORRECTIVE_SMOOTH")
        else:
            corrective_smooth = object.modifiers.new(name, "CORRECTIVE_SMOOTH")
        return corrective_smooth

    # Smooth Laplacian Modifier
    @staticmethod
    def add_smooth_laplacian_modifier(object: bpy.types.Object, name: str = "LaplacianSmooth", check: bool = True) -> bpy.types.Modifier:
        """Add a smooth laplacian modifier.

        object (bpy.types.Object) - The object to add the modifier to.
        name (str, optional) - The name of the modifier.
        check (bool, optional) - Check if the modifier exists.
        return (bpy.types.Modifier) - Smooth Laplacian modifier.
        """
        if check:
            laplacian_smooth = object.modifiers.get(name)
            if not laplacian_smooth:
                laplacian_smooth = object.modifiers.new(name, "LAPLACIANSMOOTH")
        else:
            laplacian_smooth = object.modifiers.new(name, "LAPLACIANSMOOTH")
        return laplacian_smooth

    # Wave Modifier
    @staticmethod
    def add_wave_modifier(object: bpy.types.Object, name: str = "Wave", check: bool = True) -> bpy.types.Modifier:
        """Add a wave modifier.

        object (bpy.types.Object) - The object to add the modifier to.
        name (str, optional) - The name of the modifier.
        check (bool, optional) - Check if the modifier exists.
        return (bpy.types.Modifier) - Wave modifier.
        """
        if check:
            wave = object.modifiers.get(name)
            if not wave:
                wave = object.modifiers.new(name, "WAVE")
        else:
            wave = object.modifiers.new(name, "WAVE")
        return wave

    # Cloth Modifier
    @staticmethod
    def add_cloth_modifier(object: bpy.types.Object, name: str = "Cloth", check: bool = True) -> bpy.types.Modifier:
        """Add a cloth modifier.

        object (bpy.types.Object) - The object to add the modifier to.
        name (str, optional) - The name of the modifier.
        check (bool, optional) - Check if the modifier exists.
        return (bpy.types.Modifier) - Cloth modifier.
        """
        if check:
            cloth = object.modifiers.get(name)
            if not cloth:
                cloth = object.modifiers.new(name, "CLOTH")
                cloth.settings.use_pressure = True
                cloth.settings.quality = 5
                cloth.settings.time_scale = 0.5
                cloth.settings.uniform_pressure_force = 15
                cloth.settings.shrink_min = -0.3
                Mesh.create_vgroup(object, cloth)
        else:
            cloth = object.modifiers.new(name, "CLOTH")
            cloth.settings.use_pressure = True
            cloth.settings.quality = 5
            cloth.settings.time_scale = 0.5
            cloth.settings.uniform_pressure_force = 15
            cloth.settings.shrink_min = -0.3
            Mesh.create_vgroup(object, cloth)
        return cloth

    @staticmethod
    def get_modifiers(object: bpy.types.Object, type=None) -> list:
        """Get the modifiers.

        object (bpy.types.Object) - The object to get modifiers from.
        type (str, optional) - The type of modifier to get.
        return (list) - Modifiers.
        """
        if type is None:
            return list(object.modifiers)
        else:
            return [modifier for modifier in object.modifiers if modifier.type == type]

    @staticmethod
    def get_active_modifier(object: bpy.types.Object, type: str) -> bpy.types.Modifier:
        """Get the active modifier.

        object (bpy.types.Object) - The object to get the modifier from.
        type (str) - The type of modifier to get.
        return (bpy.types.Modifier) - The modifier.
        """
        if object.modifiers.active.type == type:
            active = object.modifiers.active
        else:
            active = Modifier.get_modifiers(object, type)[-1]
            active.is_active = True
        # active.show_expanded = True
        return active

    @staticmethod
    def show_modifier(object: bpy.types.Object, modifier: bpy.types.Modifier, toggle: str):
        """Show the modifier.

        object (bpy.types.Object) - The object to get modifier from.
        modifier (bpy.types.Modifier) - The modifier to show.
        toggle (enum in ['EXPANDED', 'ON_CAGE', 'IN_EDITMODE', 'VIEWPORT', 'RENDER']) - The state to set the modifier to.
        """
        if toggle == "EXPANDED":
            object.modifiers[modifier.name].show_expanded = not object.modifiers[modifier.name].show_expanded
        if toggle == "ON_CAGE":
            object.modifiers[modifier.name].show_on_cage = not object.modifiers[modifier.name].show_on_cage
        if toggle == "IN_EDITMODE":
            object.modifiers[modifier.name].show_in_editmode = not object.modifiers[modifier.name].show_in_editmode
        if toggle == "VIEWPORT":
            object.modifiers[modifier.name].show_viewport = not object.modifiers[modifier.name].show_viewport
        if toggle == "RENDER":
            object.modifiers[modifier.name].show_render = not object.modifiers[modifier.name].show_render

    @staticmethod
    def switch_modifier(object: bpy.types.Object, modifier: bpy.types.Modifier, select: str) -> bpy.types.Modifier:
        """Switch the modifier.

        object (bpy.types.Object) - The object to get modifier from.
        modifier (bpy.types.Modifier) - The modifier to switch.
        select (enum in ['PREV', 'NEXT']) - The state to switch the modifier to.
        return (bpy.types.Modifier) - The modifier that was switched to.
        """
        modifs = Modifier.get_modifiers(object, modifier.type)
        index = modifs.index(modifier)
        if select == "PREV":
            modifier = modifs[index - 1]
        if select == "NEXT":
            modifier = modifs[(index + 1) % len(modifs)]
        modifier.is_active = True
        return modifier

    @staticmethod
    def move_modifier(modifier: bpy.types.Modifier, move: str):
        """Move the modifier in the modifier stack.

        modifier (bpy.types.Modifier) - The modifier to move.
        move (enum in ['UP', 'DOWN']) - The direction to move the modifier.
        """
        if move == "UP":
            bpy.ops.object.modifier_move_up(modifier=modifier.name)
        if move == "DOWN":
            bpy.ops.object.modifier_move_down(modifier=modifier.name)

    @staticmethod
    def apply_modifier(modifier: bpy.types.Modifier):
        """Apply the modifier.

        modifier (bpy.types.Modifier) - The modifier to apply.
        """
        bpy.ops.object.modifier_apply(modifier=modifier.name)

    @staticmethod
    def copy_modifier(modifier: bpy.types.Modifier):
        """Copy the modifier.

        modifier (bpy.types.Modifier) - The modifier to copy.
        """
        bpy.ops.object.modifier_copy(modifier=modifier.name)

    @staticmethod
    def remove_modifier(object: bpy.types.Object, modifier: bpy.types.Modifier):
        """Remove the modifier.

        object (bpy.types.Object) - The object to remove the modifier from.
        modifier (bpy.types.Modifier) - The modifier to remove.
        """
        object.modifiers.remove(modifier)

    @staticmethod
    def remove_modifiers(object: bpy.types.Object):
        """Remove all modifiers.

        object (bpy.types.Object) - The object to remove the modifiers from.
        """
        for modifier in object.modifiers:
            object.modifiers.remove(modifier)

    @staticmethod
    def sort_mod(object: bpy.types.Object):
        """Work in progress..."""
        modifiers = object.modifiers
        subsurf_mods = boolean_mods = bevel_mods = mirror_mods = 0
        for mod in modifiers:
            if mod.type == "SUBSURF":
                bpy.ops.object.modifier_move_to_index(modifier=mod.name, index=subsurf_mods)
                subsurf_mods += 1
            elif mod.type == "BOOLEAN":
                bpy.ops.object.modifier_move_to_index(modifier=mod.name, index=subsurf_mods + boolean_mods)
                boolean_mods += 1
            elif mod.type == "BEVEL":
                bpy.ops.object.modifier_move_to_index(modifier=mod.name, index=subsurf_mods + boolean_mods + bevel_mods)
                bevel_mods += 1
            elif mod.type == "MIRROR":
                bpy.ops.object.modifier_move_to_index(
                    modifier=mod.name,
                    index=subsurf_mods + boolean_mods + bevel_mods + mirror_mods,
                )
                mirror_mods += 1
            elif mod.type == "WEIGHTED_NORMAL":
                bpy.ops.object.modifier_move_to_index(modifier=mod.name, index=len(modifiers) - 1)
