import bpy
Path = 'C:\\Blender_Cache\\BlenderToMaya\\Qkk_BlenderToMaya.FBX'

#导出fbx
bpy.ops.export_scene.fbx(
filepath=Path,#模型路径

#包括
use_selection=True,#选择项
use_visible=False, #可见项
use_active_collection=False,#激活的集合
object_types={'MESH','EMPTY'},#数据类似
use_custom_props=True,#自定义属性

#变换
global_scale=1.0,#缩放
apply_scale_options='FBX_SCALE_NONE',#应用缩放
axis_forward='Y',#向前
axis_up='Z',#向上
apply_unit_scale=True,#应用单位
use_space_transform=True,#使用空间变换
bake_space_transform=False,#应用变换

#几何数据
mesh_smooth_type='EDGE',#平滑
use_subsurf=False,#导出表面细分
use_mesh_modifiers=True,#应用修改器
use_mesh_edges=False,#松散边
use_triangles=False,#三角面
use_tspace=False,#切向空间
colors_type='SRGB',#顶点色空间
prioritize_active_color=False,#活动颜色优先

#动画
bake_anim=False,#动画

#其他
path_mode='ABSOLUTE',#路径模式
embed_textures=False,#内嵌纹理
batch_mode='OFF',#批量模式
)