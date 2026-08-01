import bpy
# 导出FBX
bpy.ops.export_scene.fbx(
    'INVOKE_DEFAULT', 
    use_selection=True, 
    global_scale=1.0, 
    apply_scale_options='FBX_SCALE_NONE', 
    use_space_transform=True, 
    bake_space_transform=False, 
    object_types={'MESH'}, 
    use_mesh_modifiers=True, 
    colors_type='SRGB', 
    prioritize_active_color=True, 
    use_custom_props=True, 
    bake_anim=False, 
    use_batch_own_dir=False, 
    axis_forward='-Z', 
    axis_up='Y')