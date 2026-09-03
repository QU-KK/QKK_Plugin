from .G import *
EDGEDECAL_ADDON_VERSION=(1,2,1)
import bpy
from bpy.app.handlers import persistent
import bmesh,random,json,heapq
from math import radians,acos,degrees,pi,atan2,cos,sin
from mathutils import Vector,Matrix
from mathutils.bvhtree import BVHTree
from bpy.props import BoolProperty,FloatProperty,FloatVectorProperty,IntProperty,StringProperty,PointerProperty,CollectionProperty,EnumProperty
from bpy.types import AddonPreferences,Operator,Panel,PropertyGroup,UIList
import gpu,time,hashlib
from array import array
import blf
from gpu_extras.batch import batch_for_shader
from bpy_extras import view3d_utils
bl_info={"name":"🌸 边缘贴花 (Edge Decal Generator)","description":"沿网格边生成可自定义贴花","author":"MKLK 汉化：GJJ","blender":(4,5,0),"version":(1,2,1),"category":"Mesh"}
EDGEDECAL_UV_PIN_DRAW_HANDLE=None
EDGEDECAL_ADDON_KEYMAPS=[]
EDGEDECAL_INTERACTIVE_RUNNING=False
EDGEDECAL_STANDALONE_GENERATION=False
EDGEDECAL_SETTINGS_SYNCING=False
EDGEDECAL_REGENERATE_TARGET=None
EPSILON=1.0e-8
MIN_FACE_WIDTH=0.001
COLLECTION_NAME= "Edge Decals"
DEFAULT_MATERIAL_NAME= "M_Edge_Decal"
import os as _os
_FEATURE_FILES=("core_state.py","texture_masks.py","geometry.py","surface_voronoi.py","uv_processing.py","generation.py","intersections.py","bundled_assets.py", "presets.py","uv_pins.py","ui_sections.py","interactive.py","unreal_export.py","layers.py", "lifecycle.py",)
def _load_feature_file(_filename):
	_path=_os.path.join(_os.path.dirname(__file__), "features",_filename)
	with open(_path, "r",encoding="utf-8") as _handle:
		_source=_handle.read()
	# 临时设置 __package__，使 feature 文件中的 from ..G 相对导入能正确解析。
	# 必须继续使用 globals() 作为 exec 命名空间，保证所有 feature 文件共享同一全局字典，
	# 先加载文件中的函数能引用后加载文件定义的名称。
	_saved_package=globals().get("__package__")
	globals()["__package__"]=__package__+".features"
	try:
		exec(compile(_source,_path, "exec"),globals(),globals())
	finally:
		if _saved_package is not None:
			globals()["__package__"]=_saved_package
		else:
			globals().pop("__package__",None)
for _feature_file in _FEATURE_FILES:
	_load_feature_file(_feature_file)
del _feature_file
del _load_feature_file
del _FEATURE_FILES
del _os
