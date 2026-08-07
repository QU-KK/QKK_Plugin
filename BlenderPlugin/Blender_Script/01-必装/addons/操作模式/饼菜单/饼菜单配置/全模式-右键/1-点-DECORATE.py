import bpy
# 切换视图模式
def Switch_Mode(Mode):
    # 进入编辑模式
    bpy.ops.object.mode_set(mode='EDIT')
    # 设置为面模式
    bpy.ops.mesh.select_mode(type=Mode)
    # 设置为选择模式
    bpy.ops.wm.tool_set_by_id(name='builtin.select_box')

# 切换为点模式
Mode = 'VERT'
selected_objects = bpy.context.selected_objects #获取选择的物体
if bpy.context.active_object != None: #是否存在活动物体
    if bpy.context.active_object.select_get(): #活动物体选中状态
        Switch_Mode(Mode)
        print('活动物体被选中，进入编辑模式')
    else:
        if len(selected_objects) == 0: #选择数等于0
            Switch_Mode(Mode)
            print('活动物体未选中，没有选择物体，进入编辑模式')
        else:
            for obj in selected_objects:
                bpy.context.view_layer.objects.active = obj
                break
            Switch_Mode(Mode)
            print('活动物体未选中，有选择物体，进入编辑模式')
else:
    if len(selected_objects) > 0: #选择数大于0
        for obj in selected_objects:
            bpy.context.view_layer.objects.active = obj
            break
        Switch_Mode(Mode)
        print('没有活动物体，有选择物体，进入编辑模式')
