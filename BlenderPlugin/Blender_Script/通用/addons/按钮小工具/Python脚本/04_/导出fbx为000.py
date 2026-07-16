import bpy

transform_list = []

for obj in bpy.context.selected_objects:
    obj.rotation_mode = 'QUATERNION'
    obj.rotation_mode = 'XYZ'
    
    name = str(obj.name)
    location = list(obj.location)
    rotation_euler = list(obj.rotation_euler)
    scale = list(obj.scale)

    data = [name,location,rotation_euler,scale]

    transform_list.append(data)
print(transform_list)
bpy.ops.object.location_clear()
bpy.ops.object.rotation_clear()
bpy.ops.object.scale_clear()
print(transform_list)


bpy.ops.export_scene.fbx(
#输出路径
filepath='C:\\Users\\qukuikui\\Desktop\\小罐子\\SM.fbx',

#包括
use_selection=True,#选定物体
use_visible=False,#可见物体
use_active_collection=False,#活动集合
#collection='',#集合名称
object_types={'MESH'},#导出类型
use_custom_props=True,#自定义属性

#变换
global_scale=1.0,#缩放
apply_scale_options='FBX_SCALE_NONE',#应用缩放
axis_forward='Y',
axis_up='Z',
apply_unit_scale=True,#应用单位
use_space_transform=True,#使用空间变换
bake_space_transform=False,#应用变换 True   Ue可能出问题

#几何数据
mesh_smooth_type='EDGE',#平滑类型  OFF FACE EDGE SMOOTH_GROUP
use_subsurf=False,#导出表面细分
use_mesh_modifiers=False,#应用修改器
use_mesh_modifiers_render=False,#应用修改器（渲染）
use_mesh_edges=False,#松散边
use_triangles=False,#三角化
use_tspace=False,#切向空间
colors_type='SRGB',#顶点色类型
prioritize_active_color=False,#活动颜色优先

#骨架
primary_bone_axis='Y',#主骨骼轴向
secondary_bone_axis='X',#次骨骼轴向
armature_nodetype='NULL',#骨架FBXNode类型
add_leaf_bones=False,#仅形变骨骼
use_armature_deform_only=False,#添加叶骨

#动画
bake_anim=False,
bake_anim_use_all_bones=False,
bake_anim_use_nla_strips=False,
bake_anim_use_all_actions=False,
bake_anim_force_startend_keying=False,
bake_anim_step=1.0,
bake_anim_simplify_factor=1.0,

#其他
check_existing=False,#检查是否存在
filter_glob='',#过滤
path_mode='AUTO',#路径模式
embed_textures=False,#内嵌纹理
batch_mode='OFF',#批量模式
use_batch_own_dir=False,#批处理路径
use_metadata=False,#使用元数据
)


for data in transform_list:
    obj = bpy.data.objects[data[0]]
    obj.location = data[1]
    obj.rotation_euler = data[2]
    obj.scale = data[3]