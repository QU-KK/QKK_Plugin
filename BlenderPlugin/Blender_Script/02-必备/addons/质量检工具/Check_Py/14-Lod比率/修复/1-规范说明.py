import os
# 规范说明
# 获取当前脚本所在目录
dir_path = os.path.dirname(os.path.abspath(__file__))
file_path = os.path.join(dir_path, "说明","lod比率规范说明.png")
os.startfile(file_path)