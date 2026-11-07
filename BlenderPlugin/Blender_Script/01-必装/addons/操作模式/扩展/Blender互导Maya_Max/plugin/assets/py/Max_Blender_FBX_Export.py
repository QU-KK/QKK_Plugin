import bpy
#导入fbx
bpy.ops.import_scene.fbx(
filepath=filepath_Max_To_Blender, #文件路径

#包括
use_custom_normals=True, #自定义法向
use_subsurf=False, #细分曲面
use_custom_props=True, #自定义属性
use_custom_props_enum_as_string=True, #导入枚举为字符串
use_image_search=True, #图像查找
colors_type='SRGB', #顶点色

#比啊变换
global_scale=1.0, #缩放
decal_offset=0.0, #贴花偏移
bake_space_transform=True, #应用变换
use_prepost_rot=True,#预旋转

#轴向
use_manual_orientation=True, #手动朝向
axis_forward='Y', #向前
axis_up='Z', #向上

#动画
use_anim=False, #动画
anim_offset=0.0, #动画偏移

#骨骼
ignore_leaf_bones=False, #忽略叶骨骼
force_connect_children=False, #强制连接子骨骼
automatic_bone_orientation=False, #自动骨骼坐标系
primary_bone_axis='Y', #主骨骼轴向
secondary_bone_axis='X' #次骨骼轴向

#其他
use_alpha_decals=False, #Alpa贴花

)