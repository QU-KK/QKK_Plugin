import importlib
import logging
import sys
from . import addon_updater_ops
from . import addon_updater
from . import quicksnap_utils
from . import quicksnap_snapdata
from . import quicksnap_render
from . import quicksnap





bl_info = {
    "name": "QuickSnap",
    "author": "Julien Heijmans",
    "blender": (2, 93, 0),
    'version': (1, 4, 8),
    "category": "3D View",
    "description": "Quickly snap objects/vertices/curve points",
    "warning": "",
    "doc_url": "https://github.com/JulienHeijmans/quicksnap",
    "releases_url": "https://github.com/JulienHeijmans/quicksnap/releases",
    "tracker_url": "https://github.com/JulienHeijmans/quicksnap/issues",
}


# 模块名称列表
modulesNames = ['addon_updater', 'addon_updater_ops', 'quicksnap_utils', 'quicksnap_snapdata', 'quicksnap_render',
                'quicksnap']

# 创建一个字典，用于存储模块的完整名称
modulesFullNames = {}
for currentModuleName in modulesNames:
    # 将模块名称格式化为完整路径，存储到字典中
    modulesFullNames[currentModuleName] = (format(__name__, currentModuleName))

# 遍历完整模块名称的值
for currentModuleFullName in modulesFullNames.values():
    # 如果模块已经被导入，则重新加载模块
    if currentModuleFullName in sys.modules:
        importlib.reload(sys.modules[currentModuleFullName])
    else:
        # 否则，导入模块并将其添加到全局命名空间中
        globals()[currentModuleFullName] = importlib.import_module(currentModuleFullName)
        # 为导入的模块设置模块名称属性
        setattr(globals()[currentModuleFullName], 'modulesNames', modulesFullNames)

# 注册函数
def register():
    # 遍历完整模块名称的值
    for current_module_name in modulesFullNames.values():
        # 如果模块已经被导入
        if current_module_name in sys.modules:
            # 检查模块是否具有注册函数
            if hasattr(sys.modules[current_module_name], 'register'):
                # 特殊处理特定模块
                if current_module_name == f"{__name__}.addon_updater_ops":
                    sys.modules[current_module_name].register(bl_info)
                else:
                    # 调用模块的注册函数
                    print(current_module_name)
                    sys.modules[current_module_name].register()

# 注销函数
def unregister():
    # 遍历完整模块名称的值
    for current_module_name in modulesFullNames.values():
        # 如果模块已经被导入
        if current_module_name in sys.modules:
            # 检查模块是否具有注销函数
            if hasattr(sys.modules[current_module_name], 'unregister'):
                # 调用模块的注销函数
                sys.modules[current_module_name].unregister()


logger = logging.getLogger(__name__)
logger.handlers = []
logger.setLevel(logging.NOTSET)
console_handler = logging.StreamHandler()
console_handler.setFormatter(fmt=logging.Formatter('[%(levelname)s] %(asctime)s %(message)s'))
logger.addHandler(console_handler)
