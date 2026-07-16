import bpy


class Export:
    @staticmethod
    def export_fbx(
        filepath: str,
        properties: bpy.types.Property = None,
        path_mode="COPY",
        embed_textures=True,
        batch_mode="OFF",
        use_batch_own_dir=True,
        use_selection=True,
        use_visible=False,
        use_active_collection=False,
        object_types={"EMPTY", "CAMERA", "LIGHT", "ARMATURE", "MESH", "OTHER"},
        use_custom_props=True,
        global_scale=1,
        apply_scale_options="FBX_SCALE_NONE",
        axis_forward="-Z",
        axis_up="Y",
        apply_unit_scale=True,
        use_space_transform=True,
        bake_space_transform=False,
        mesh_smooth_type="FACE",
        use_subsurf=False,
        use_mesh_modifiers=True,
        use_mesh_edges=False,
        use_triangles=False,
        use_tspace=False,
        primary_bone_axis="Y",
        secondary_bone_axis="X",
        armature_nodetype="NULL",
        use_armature_deform_only=False,
        add_leaf_bones=True,
        bake_anim=True,
        bake_anim_use_all_bones=True,
        bake_anim_use_nla_strips=True,
        bake_anim_use_all_actions=False,
        bake_anim_force_startend_keying=True,
        bake_anim_step=1,
        bake_anim_simplify_factor=1,
    ):
        """Export FBX file.

        path (str) - Filepath to save the file to.
        name (str) - Name of the file.
        properties (dict) - Properties to set on the FBX file.
        """
        bpy.ops.export_scene.fbx(
            filepath=filepath,
            check_existing=True,
            # Set export options based on provided arguments or defaults
            path_mode=path_mode if properties is None else properties.path_mode,
            embed_textures=embed_textures if properties is None else properties.embed_textures,
            batch_mode=batch_mode if properties is None else properties.batch_mode,
            use_batch_own_dir=use_batch_own_dir if properties is None else properties.use_batch_own_dir,
            use_selection=use_selection if properties is None else properties.use_selection,
            use_visible=use_visible if properties is None else properties.use_visible,
            use_active_collection=use_active_collection if properties is None else properties.use_active_collection,
            object_types=object_types if properties is None else properties.object_types,
            use_custom_props=use_custom_props if properties is None else properties.use_custom_props,
            global_scale=global_scale if properties is None else properties.global_scale,
            apply_scale_options=apply_scale_options if properties is None else properties.apply_scale_options,
            axis_forward=axis_forward if properties is None else properties.axis_forward,
            axis_up=axis_up if properties is None else properties.axis_up,
            apply_unit_scale=apply_unit_scale if properties is None else properties.apply_unit_scale,
            use_space_transform=use_space_transform if properties is None else properties.use_space_transform,
            bake_space_transform=bake_space_transform if properties is None else properties.bake_space_transform,
            mesh_smooth_type=mesh_smooth_type if properties is None else properties.mesh_smooth_type,
            use_subsurf=use_subsurf if properties is None else properties.use_subsurf,
            use_mesh_modifiers=use_mesh_modifiers if properties is None else properties.use_mesh_modifiers,
            use_mesh_edges=use_mesh_edges if properties is None else properties.use_mesh_edges,
            use_triangles=use_triangles if properties is None else properties.use_triangles,
            use_tspace=use_tspace if properties is None else properties.use_tspace,
            primary_bone_axis=primary_bone_axis if properties is None else properties.primary_bone_axis,
            secondary_bone_axis=secondary_bone_axis if properties is None else properties.secondary_bone_axis,
            armature_nodetype=armature_nodetype if properties is None else properties.armature_nodetype,
            use_armature_deform_only=use_armature_deform_only if properties is None else properties.use_armature_deform_only,
            add_leaf_bones=add_leaf_bones if properties is None else properties.add_leaf_bones,
            bake_anim=bake_anim if properties is None else properties.bake_anim,
            bake_anim_use_all_bones=bake_anim_use_all_bones if properties is None else properties.bake_anim_use_all_bones,
            bake_anim_use_nla_strips=bake_anim_use_nla_strips if properties is None else properties.bake_anim_use_nla_strips,
            bake_anim_use_all_actions=bake_anim_use_all_actions if properties is None else properties.bake_anim_use_all_actions,
            bake_anim_force_startend_keying=bake_anim_force_startend_keying if properties is None else properties.bake_anim_force_startend_keying,
            bake_anim_step=bake_anim_step if properties is None else properties.bake_anim_step,
            bake_anim_simplify_factor=bake_anim_simplify_factor if properties is None else properties.bake_anim_simplify_factor,
        )
        return filepath

    @staticmethod
    def fbx_export(
        filepath: str,
        properties: bpy.types.Property = None,
        path_mode="COPY",
        embed_textures=True,
        batch_mode="OFF",
        use_batch_own_dir=True,
        use_selection=True,
        use_visible=False,
        use_active_collection=False,
        object_types={"EMPTY", "CAMERA", "LIGHT", "ARMATURE", "MESH", "OTHER"},
        use_custom_props=True,
        global_scale=1,
        apply_scale_options="FBX_SCALE_NONE",
        axis_forward="-Z",
        axis_up="Y",
        apply_unit_scale=True,
        use_space_transform=True,
        bake_space_transform=False,
        mesh_smooth_type="FACE",
        use_subsurf=False,
        use_mesh_modifiers=True,
        use_mesh_edges=False,
        use_triangles=False,
        use_tspace=False,
        colors_type="SRGB",
        prioritize_active_color=False,
        primary_bone_axis="Y",
        secondary_bone_axis="X",
        armature_nodetype="NULL",
        use_armature_deform_only=False,
        add_leaf_bones=True,
        bake_anim=True,
        bake_anim_use_all_bones=True,
        bake_anim_use_nla_strips=True,
        bake_anim_use_all_actions=False,
        bake_anim_force_startend_keying=True,
        bake_anim_step=1,
        bake_anim_simplify_factor=1,
    ):
        """Export FBX file.

        path (str) - Filepath to save the file to.
        name (str) - Name of the file.
        properties (dict) - Properties to set on the FBX file.
        """
        bpy.ops.export_scene.fbx(
            filepath=filepath,
            check_existing=True,
            # Set export options based on provided arguments or defaults
            path_mode=path_mode if properties is None else properties.path_mode,
            embed_textures=embed_textures if properties is None else properties.embed_textures,
            batch_mode=batch_mode if properties is None else properties.batch_mode,
            use_batch_own_dir=use_batch_own_dir if properties is None else properties.use_batch_own_dir,
            use_selection=use_selection if properties is None else properties.use_selection,
            use_visible=use_visible if properties is None else properties.use_visible,
            use_active_collection=use_active_collection if properties is None else properties.use_active_collection,
            object_types=object_types if properties is None else properties.object_types,
            use_custom_props=use_custom_props if properties is None else properties.use_custom_props,
            global_scale=global_scale if properties is None else properties.global_scale,
            apply_scale_options=apply_scale_options if properties is None else properties.apply_scale_options,
            axis_forward=axis_forward if properties is None else properties.axis_forward,
            axis_up=axis_up if properties is None else properties.axis_up,
            apply_unit_scale=apply_unit_scale if properties is None else properties.apply_unit_scale,
            use_space_transform=use_space_transform if properties is None else properties.use_space_transform,
            bake_space_transform=bake_space_transform if properties is None else properties.bake_space_transform,
            mesh_smooth_type=mesh_smooth_type if properties is None else properties.mesh_smooth_type,
            use_subsurf=use_subsurf if properties is None else properties.use_subsurf,
            use_mesh_modifiers=use_mesh_modifiers if properties is None else properties.use_mesh_modifiers,
            use_mesh_edges=use_mesh_edges if properties is None else properties.use_mesh_edges,
            use_triangles=use_triangles if properties is None else properties.use_triangles,
            use_tspace=use_tspace if properties is None else properties.use_tspace,
            colors_type=colors_type if properties is None else properties.colors_type,
            prioritize_active_color=prioritize_active_color if properties is None else properties.prioritize_active_color,
            primary_bone_axis=primary_bone_axis if properties is None else properties.primary_bone_axis,
            secondary_bone_axis=secondary_bone_axis if properties is None else properties.secondary_bone_axis,
            armature_nodetype=armature_nodetype if properties is None else properties.armature_nodetype,
            use_armature_deform_only=use_armature_deform_only if properties is None else properties.use_armature_deform_only,
            add_leaf_bones=add_leaf_bones if properties is None else properties.add_leaf_bones,
            bake_anim=bake_anim if properties is None else properties.bake_anim,
            bake_anim_use_all_bones=bake_anim_use_all_bones if properties is None else properties.bake_anim_use_all_bones,
            bake_anim_use_nla_strips=bake_anim_use_nla_strips if properties is None else properties.bake_anim_use_nla_strips,
            bake_anim_use_all_actions=bake_anim_use_all_actions if properties is None else properties.bake_anim_use_all_actions,
            bake_anim_force_startend_keying=bake_anim_force_startend_keying if properties is None else properties.bake_anim_force_startend_keying,
            bake_anim_step=bake_anim_step if properties is None else properties.bake_anim_step,
            bake_anim_simplify_factor=bake_anim_simplify_factor if properties is None else properties.bake_anim_simplify_factor,
        )
        return filepath

    @staticmethod
    def export_obj(
        filepath: str,
        properties: bpy.types.Property = None,
        use_selection=True,
        use_blen_objects=True,
        group_by_object=False,
        group_by_material=False,
        use_animation=True,
        global_scale=1,
        path_mode="COPY",
        axis_forward="-Z",
        axis_up="Y",
        use_mesh_modifiers=True,
        use_smooth_groups=False,
        use_smooth_groups_bitflags=False,
        use_normals=True,
        use_uvs=True,
        use_materials=True,
        use_triangles=True,
        use_nurbs=False,
        use_vertex_groups=False,
        keep_vertex_order=False,
    ):
        """Export the current scene to a file.

        filepath (str) - Filepath to save the file to.
        """
        bpy.ops.export_scene.obj(
            filepath=filepath,
            check_existing=True,
            use_selection=use_selection if properties is None else properties.use_selection,
            use_blen_objects=use_blen_objects if properties is None else properties.use_blen_objects,
            group_by_object=group_by_object if properties is None else properties.group_by_object,
            group_by_material=group_by_material if properties is None else properties.group_by_material,
            use_animation=use_animation if properties is None else properties.use_animation,
            global_scale=global_scale if properties is None else properties.global_scale,
            path_mode=path_mode if properties is None else properties.path_mode,
            axis_forward=axis_forward if properties is None else properties.axis_forward,
            axis_up=axis_up if properties is None else properties.axis_up,
            use_mesh_modifiers=use_mesh_modifiers if properties is None else properties.use_mesh_modifiers,
            use_smooth_groups=use_smooth_groups if properties is None else properties.use_smooth_groups,
            use_smooth_groups_bitflags=use_smooth_groups_bitflags if properties is None else properties.use_smooth_groups_bitflags,
            use_normals=use_normals if properties is None else properties.use_normals,
            use_uvs=use_uvs if properties is None else properties.use_uvs,
            use_materials=use_materials if properties is None else properties.use_materials,
            use_triangles=use_triangles if properties is None else properties.use_triangles,
            use_nurbs=use_nurbs if properties is None else properties.use_nurbs,
            use_vertex_groups=use_vertex_groups if properties is None else properties.use_vertex_groups,
            keep_vertex_order=keep_vertex_order if properties is None else properties.keep_vertex_order,
        )
        return filepath

    @staticmethod
    def obj_export(
        filepath: str,
        properties: bpy.types.Property = None,
        export_selected_objects=True,
        global_scale=1,
        forward_axis="NEGATIVE_Z",
        up_axis="Y",
        apply_modifiers=True,
        export_eval_mode="DAG_EVAL_VIEWPORT",
        export_uv=True,
        export_normals=True,
        export_colors=False,
        export_triangulated_mesh=False,
        export_curves_as_nurbs=False,
        export_materials=True,
        export_pbr_extensions=False,
        path_mode="COPY",
        export_object_groups=False,
        export_material_groups=False,
        export_vertex_groups=False,
        export_smooth_groups=False,
        smooth_group_bitflags=False,
        export_animation=True,
        start_frame=1,
        end_frame=250,
    ):
        """Export the current scene to a file.

        filepath (str) - Filepath to save the file to.
        """
        bpy.ops.wm.obj_export(
            filepath=filepath,
            check_existing=True,
            export_selected_objects=export_selected_objects if properties is None else properties.export_selected_objects,
            global_scale=global_scale if properties is None else properties.global_scale,
            forward_axis=forward_axis if properties is None else properties.forward_axis,
            up_axis=up_axis if properties is None else properties.up_axis,
            apply_modifiers=apply_modifiers if properties is None else properties.apply_modifiers,
            export_eval_mode=export_eval_mode if properties is None else properties.export_eval_mode,
            export_uv=export_uv if properties is None else properties.export_uv,
            export_normals=export_normals if properties is None else properties.export_normals,
            export_colors=export_colors if properties is None else properties.export_colors,
            export_triangulated_mesh=export_triangulated_mesh if properties is None else properties.export_triangulated_mesh,
            export_curves_as_nurbs=export_curves_as_nurbs if properties is None else properties.export_curves_as_nurbs,
            export_materials=export_materials if properties is None else properties.export_materials,
            export_pbr_extensions=export_pbr_extensions if properties is None else properties.export_pbr_extensions,
            path_mode=path_mode if properties is None else properties.path_mode,
            export_object_groups=export_object_groups if properties is None else properties.export_object_groups,
            export_material_groups=export_material_groups if properties is None else properties.export_material_groups,
            export_vertex_groups=export_vertex_groups if properties is None else properties.export_vertex_groups,
            export_smooth_groups=export_smooth_groups if properties is None else properties.export_smooth_groups,
            smooth_group_bitflags=smooth_group_bitflags if properties is None else properties.smooth_group_bitflags,
            export_animation=export_animation if properties is None else properties.export_animation,
            start_frame=start_frame if properties is None else properties.start_frame,
            end_frame=end_frame if properties is None else properties.end_frame,
        )
        return filepath

    @staticmethod
    def export_off(filepath: str, mesh: bpy.types.Mesh):
        """Export triangulated mesh to Object File Format.

        mesh (bpy.types.Mesh): The mesh to export.
        filepath (str): Filepath to save the file to.
        """
        with open(filepath, "wb") as off:
            off.write(b"OFF\n")
            off.write(str.encode(f"{len(mesh.vertices)} {len(mesh.polygons)} 0\n"))
            for vert in mesh.vertices:
                off.write(str.encode("{:g} {:g} {:g}\n".format(*vert.co)))
            for face in mesh.polygons:
                off.write(str.encode("3 {} {} {}\n".format(*face.vertices)))
