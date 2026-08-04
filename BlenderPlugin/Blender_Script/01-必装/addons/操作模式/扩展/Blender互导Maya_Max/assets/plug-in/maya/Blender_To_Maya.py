import maya.cmds as cmds
import maya.mel as mel

#导入fbx
def import_fbx(*args):
    cmds.loadPlugin('fbxmaya', quiet=True)

    linear_unit = cmds.currentUnit(query=True, linear=True)#获取当前工作单位
    
    mel.eval('FBXImportConvertUnitString linear_unit;')  # 设置导入单位

    mel.eval('FBXImportMode -v "add";')  # 设置导入模式为添加
    mel.eval('FBXImportScaleFactor 1;')  # 设置比例因子
    mel.eval('FBXImportUnlockNormals -v true;')  #解锁法线锁定
    mel.eval('FBXImportHardEdges -v false;')  # 逐顶点合并法线
    mel.eval('FBXImportCameras -v false;')  # 摄影机
    mel.eval('FBXImportLights -v false;')  # 灯光
    mel.eval('FBXExportAnimationOnly -v false')  # 动画
    mel.eval('FBXImportGenerateLog -v true;')  # 生成日志文件

    # 指定FBX文件路径
    file_path = r'C:\Blender_Cache\BlenderToMaya\Qkk_BlenderToMaya.fbx'
    cmds.file(file_path, i=True, type='FBX', ra=True, mergeNamespacesOnClash=False, namespace=':')


#导出fbx
def export_fbx(*args):
    cmds.loadPlugin('fbxmaya', quiet=True)  # 确保FBX插件已加载
    mel.eval('FBXExportSmoothingGroups -v true')  # 导出平滑组
    mel.eval('FBXExportHardEdges -v false')  # 导出硬边
    mel.eval('FBXExportScaleFactor 1.0')  # 设置比例因子
    mel.eval('FBXExportCameras -v false')  # 摄影机
    mel.eval('FBXExportLights -v false')  # 灯光
    mel.eval('FBXExportAnimationOnly -v false')  # 动画
    mel.eval('FBXExportUpAxis z')  # 轴向

    mel.eval('FBXExportGenerateLog -v true')  # 生成日志文件

    # 导出选中的对象为FBX文件
    file_path = r'C:\Blender_Cache\BlenderToMaya\Qkk_MayaToBlender.fbx'  # 更新为实际的文件路径
    cmds.file(file_path, force=True, type="FBX export", es=True)

#弹窗
def run():
    if cmds.window("Window001", exists=True):
        cmds.deleteUI("Window001")

    window = cmds.window("Window001", title="Blender-Maya互导", widthHeight=(300, 80))
    cmds.columnLayout(adjustableColumn=True)

    linear_unit = cmds.currentUnit(query=True, linear=True)#获取当前工作单位
    up_axis = cmds.upAxis(query=True, axis=True)
    cmds.text(label=f"当前单位 ( {linear_unit} )      当前向上轴( {up_axis})      建议Z轴向上 ",align='left')

    cmds.rowLayout(numberOfColumns=2)
    cmds.button(label="导入至Maya", command=import_fbx, width=140, height=40)
    cmds.button(label="导出至Blender", command=export_fbx, width=140, height=40)

    cmds.showWindow(window)
run()