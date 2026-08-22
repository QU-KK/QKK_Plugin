import maya.cmds as cmds
import maya.mel as mel

cmds.loadPlugin('fbxmaya', quiet=True)

cmds.file(new=True, force=True)# 执行新建场景，force=True 不弹出确认

mel.eval('MLdeleteUnused;')#清理未使用的数据

linear_unit = cmds.currentUnit(query=True, linear=True)#获取当前工作单位

mel.eval('FBXImportConvertUnitString linear_unit;')  # 设置导入单位
mel.eval('FBXImportMode -v "add";')  # 设置导入模式为添加
mel.eval('FBXImportScaleFactor 1;')  # 设置比例因子
mel.eval('FBXImportHardEdges -v false;')  # 开启硬边导入（保留 FBX 中的软硬边/平滑组信息）
mel.eval('FBXImportUnlockNormals -v false;')  #解锁法线锁定
mel.eval('FBXImportHardEdges -v false;')  # 逐顶点合并法线
mel.eval('FBXImportCameras -v false;')  # 摄影机
mel.eval('FBXImportLights -v false;')  # 灯光
mel.eval('FBXExportAnimationOnly -v false')  # 动画
mel.eval('FBXImportGenerateLog -v true;')  # 生成日志文件

# 指定FBX文件路径
file_path = r'C:\Blender_Cache\BlenderToMaya\Qkk_BlenderToMaya.fbx'
imported_nodes = cmds.file(
	file_path,
	i=True,                                # True 表示导入 (Import)，False 表示打开 (Open)        
	type='FBX',                            # 指定文件类型为 FBX
	removeDuplicateNetworks=True,          # 删除重复的着色网络，防止材质球冗余
	namespace=':',                         # 使用根命名空间（即不添加前缀，Blender导入常用）
	returnNewNodes=True
)

#选中导入的模型
cmds.select(cmds.ls(imported_nodes, type='transform'), replace=True)
#物体冻结变换
# apply=True 表示应用变换，t=位移, r=旋转, s=缩放, n=正常冻结（不锁定历史）
cmds.makeIdentity(apply=True, t=True, r=True, s=True, n=False, pn=True)