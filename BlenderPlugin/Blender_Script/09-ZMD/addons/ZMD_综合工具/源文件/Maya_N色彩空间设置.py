import maya.cmds as cmds

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

设置法线色彩空间