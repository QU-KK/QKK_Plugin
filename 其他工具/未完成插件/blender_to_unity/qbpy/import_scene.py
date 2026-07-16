import bpy


class Import:
    @staticmethod
    def import_obj(
        filepath: str,
        properties: bpy.types.Property = None,
        use_image_search=True,
        use_smooth_groups=True,
        use_edges=True,
        global_clamp_size=0.0,
        axis_forward="-Z",
        axis_up="Y",
        split_mode="ON",
        use_split_objects=True,
        use_split_groups=False,
        use_groups_as_vgroups=False,
    ):
        """Import OBJ file.

        filepath (str) - Filepath of OBJ file.
        """
        bpy.ops.import_scene.obj(
            filepath=filepath,
            use_image_search=use_image_search if properties is None else properties.use_image_search,
            use_smooth_groups=use_smooth_groups if properties is None else properties.use_smooth_groups,
            use_edges=use_edges if properties is None else properties.use_edges,
            global_clamp_size=global_clamp_size if properties is None else properties.global_clamp_size,
            axis_forward=axis_forward if properties is None else properties.axis_forward,
            axis_up=axis_up if properties is None else properties.axis_up,
            split_mode=split_mode if properties is None else properties.split_mode,
            use_split_objects=use_split_objects if properties is None else properties.use_split_objects,
            use_split_groups=use_split_groups if properties is None else properties.use_split_groups,
            use_groups_as_vgroups=use_groups_as_vgroups if properties is None else properties.use_groups_as_vgroups,
        )

    @staticmethod
    def obj_import(
        filepath: str,
        properties: bpy.types.Property = None,
        directory="",
        files=[],
        check_existing=False,
        global_scale=1,
        clamp_size=0,
        forward_axis="NEGATIVE_Z",
        up_axis="Y",
        use_split_objects=True,
        use_split_groups=False,
        import_vertex_groups=False,
        validate_meshes=False,
    ):
        """Import OBJ file.

        filepath (str) - Filepath of OBJ file.
        """
        bpy.ops.wm.obj_import(
            filepath=filepath,
            directory=directory,
            files=files,
            check_existing=check_existing,
            global_scale=global_scale if properties is None else properties.global_scale,
            clamp_size=clamp_size if properties is None else properties.clamp_size,
            forward_axis=forward_axis if properties is None else properties.forward_axis,
            up_axis=up_axis if properties is None else properties.up_axis,
            use_split_objects=use_split_objects if properties is None else properties.use_split_objects,
            use_split_groups=use_split_groups if properties is None else properties.use_split_groups,
            import_vertex_groups=import_vertex_groups if properties is None else properties.import_vertex_groups,
            validate_meshes=validate_meshes if properties is None else properties.validate_meshes,
        )
