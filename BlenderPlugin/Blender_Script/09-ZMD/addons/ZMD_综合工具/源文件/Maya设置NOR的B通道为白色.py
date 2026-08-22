import maya.cmds as cmds

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