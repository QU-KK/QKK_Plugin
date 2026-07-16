import os

# PySide 模块用于构建自定义 UI
from PySide6 import QtWidgets

# Substance 3D Painter 模块
import substance_painter.ui
import substance_painter.export
import substance_painter.project
import substance_painter.textureset

#C:\Program Files\Adobe\Adobe Substance 3D Painter\resources\starter_assets\export-presets   模版路径
#C:\Users\qukuikui\Documents\Adobe\Adobe Substance 3D Painter\assets\export-presets   临时模版路径
#C:\Users\qukuikui\Documents\Adobe\Adobe Substance 3D Painter\python\plugins    插件路径


plugin_widgets = []
# 记录已添加的 UI 元素，用于清理


def start_plugin():
    #print('start_plugin启动')


    def testing_project():
        if substance_painter.project.is_open():
            return True
        else:
            print('没有打开的工程！')
            return False


    def export_tex(mat_tex):
        print('导出材质：',mat_tex)
        # 构建导出预设模版的 URL
        export_preset = substance_painter.resource.ResourceID(context="starter_assets",name="Qkk_Export").url() #资源库名称、模版名称

        # 设置导出路径，在这种情况下，纹理将被放置在 spp 项目文件旁边的磁盘上
        Path = substance_painter.project.file_path()
        Path = os.path.dirname(Path) + "/"

        # 构建配置
        config = { #字典，配置导出参数
            "exportList":[ { "rootPath" : str(mat_tex) } ], #导出的材质纹理集
            "exportPath":Path, #输出目录
            "defaultExportPreset":export_preset, #导出模板
            "exportShaderParams":False, #导出着色器参数
            "exportParameters":[{"parameters" : { "paddingAlgorithm": "infinite" } }] #参数：填充算法设置

            #"exportPresets" : [ { "name" : "default", "maps" : [] } ], #导出预设列表，使用名为 default 的模板，maps 为空
        }
        substance_painter.export.export_project_textures( config )


    def export_all_tex(cd):
        print(cd.isChecked())
        if testing_project():
            for mat_tex in substance_painter.textureset.all_texture_sets(): # 全部纹理集
                export_tex(mat_tex)

    def export_active_tex():
        if testing_project():
            mat_tex = substance_painter.textureset.get_active_stack() # 当前活动材质纹理集
            export_tex(mat_tex)



    # 创建Ui面板容器
    container_widget = QtWidgets.QWidget()
    # 垂直布局
    layout = QtWidgets.QVBoxLayout(container_widget)


    # 第一个按钮
    export_button = QtWidgets.QPushButton("导出纹理集")
    export_button.clicked.connect(export_all_tex)

    all_a = QtWidgets.QCheckBox("All")
    all_a.setChecked(True)


    layout.addWidget(export_button)
    layout.addWidget(all_a)

    layout.addStretch()

    # 将该控件作为一个 dock 添加到界面
    substance_painter.ui.add_dock_widget(container_widget)



    # 记录以便后续清理
    plugin_widgets.append(container_widget)


def close_plugin():
    # 我们需要从 UI 中移除所有已添加的控件
    for widget in plugin_widgets:
        substance_painter.ui.delete_ui_element(widget)
    plugin_widgets.clear()


if __name__ == "__main__":
    start_plugin()