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







# 设置法线色彩空间
# 获取场景中所有的材质
materials = cmds.ls(mat=True)

# 使用 set 来记录已处理过的节点，防止多个材质共用同一张贴图时重复处理
processed_nodes = set()
count = 0

for mat in materials:
    # 获取材质的历史连接节点
    # 使用 listHistory 可以深度遍历，防止贴图被 bump2d 等节点隔开而找不到
    history_nodes = cmds.listHistory(mat)
    
    if not history_nodes:
        continue
        
    # 在这些历史节点中，过滤出所有的 file 节点（贴图节点）
    file_nodes = cmds.ls(history_nodes, type='file')
    
    for file_node in file_nodes:
        # 如果已经处理过这个节点，则跳过
        if file_node in processed_nodes:
            continue
            
        # 检查节点名称中是否包含 'normalmap_texture'
        # 如果需要完全匹配，可以改为 if file_node == 'normalmap_texture':
        if 'normalmap_texture' in file_node:
            try:
                # 开启忽略色彩空间文件规则 (防止 Maya 的默认规则锁定色彩空间)
                cmds.setAttr(file_node + '.ignoreColorSpaceFileRules', 1)
                
                # 将色彩空间设置为 Raw
                cmds.setAttr(file_node + '.colorSpace', 'Raw', type='string')
                
                print(u"成功: 材质 [{}] 的贴图节点 [{}] 已设置为 Raw".format(mat, file_node))
                
                # 记录该节点，避免重复修改
                processed_nodes.add(file_node)
                count += 1
            except Exception as e:
                print(u"警告: 无法修改节点 {}. 原因: {}".format(file_node, e))

print(u"=============================================")
print(u"完成！共修改了 {} 个名称包含 normalmap_texture 的节点。".format(count))







# 设置NOR覆盖B为白色
# 获取场景中所有的材质节点
materials = cmds.ls(mat=True)

for mat in materials:
    # 检查材质是否有 normalCamera 属性（通常lambert, blinn, aiStandardSurface等都有）
    if not cmds.attributeQuery('normalCamera', node=mat, exists=True):
        continue
        
    # 获取连接到材质法线通道的节点
    normal_nodes = cmds.listConnections(mat + '.normalCamera', source=True, destination=False)
    if not normal_nodes:
        continue
        
    for n_node in normal_nodes:
        node_type = cmds.nodeType(n_node)
        file_nodes = []
        
        # 兼容 Maya 默认的 bump2d 节点和 Arnold 的 aiNormalMap 节点
        if node_type == 'bump2d':
            file_nodes = cmds.listConnections(n_node + '.bumpValue', type='file', source=True, destination=False) or []
        elif node_type == 'aiNormalMap':
            file_nodes = cmds.listConnections(n_node + '.input', type='file', source=True, destination=False) or []
        elif node_type == 'file':
            file_nodes = [n_node]
            
        # 遍历找到的法线贴图 (file 节点) 并进行操作
        for f_node in file_nodes:
            # 检查 B 通道是否已被连接，避免重复运行脚本导致报错
            if cmds.listConnections(f_node + '.colorOffsetB', source=True, destination=False):
                print("提示: 节点 {} 的 colorOffsetB 已存在连接，跳过。".format(f_node))
                continue
                
            # 1. 创建 luminance (亮度) 节点
            lum_node = cmds.shadingNode('luminance', asUtility=True, name=f_node + '_Luminance')
            
            # 2. 设值: luminance 节点的输入属性是 value (RGB)，将其设为 (1, 1, 1) 从而使 outValue 恒定输出 1
            cmds.setAttr(lum_node + '.value', 1.0, 1.0, 1.0, type='double3')
            
            # 3. 连接: 将 luminance 节点的 outValue 连接到 file 节点的 colorOffsetB 通道
            cmds.connectAttr(lum_node + '.outValue', f_node + '.colorOffsetB', force=True)
            
            print("处理成功: 已为材质 [{}] 的法线贴图 [{}] 增加并连接了 [{}]".format(mat, f_node, lum_node))

print("--- 场景材质法线 colorOffsetB 节点处理完毕 ---")




# 设置预览纹理开启
# 获取当前场景中所有的模型视图面板
model_panels = cmds.getPanel(type='modelPanel')

if model_panels:
    for panel in model_panels:
        # 开启每个面板的纹理显示 (displayTextures)
        cmds.modelEditor(panel, edit=True, displayTextures=True)
        
print("已成功开启视图的带纹理显示。")