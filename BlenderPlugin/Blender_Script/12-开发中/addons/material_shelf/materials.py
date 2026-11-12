import bpy
from bpy.props import StringProperty
from .catalog import label
class MS_OT_materials(bpy.types.Operator):
    bl_idname='ms.materials';bl_label='Materials'
    bl_description='Browse material previews and inspect the objects using each material'
    def invoke(self,context,event):return self.execute(context)
    def execute(self,context):
        from .material_dock import toggle
        return toggle(context)
class MS_OT_material_new(bpy.types.Operator):
    bl_idname='ms.material_new';bl_label='New Material';bl_options={'REGISTER','UNDO'}
    def execute(self,context):
        mat=bpy.data.materials.new(bpy.app.translations.pgettext_data('Material'));mat.use_nodes=True
        mat['ms_created']=max((m.get('ms_created',0) for m in bpy.data.materials),default=0)+1
        mat['ms_order']=max((m.get('ms_order',m.get('ms_created',0)) for m in bpy.data.materials),default=0)+1
        from .folders import move
        move(context,[mat],context.scene.ms_folders.current)
        from . import material_previews
        material_previews.request()
        mat.use_fake_user=context.scene.ms_settings.auto_protect
        context.window_manager.ms_material=mat
        result=bpy.ops.ms.material_assign(material=mat.name)
        from . import material_editors
        material_editors.select(context,mat)
        return result
class MS_OT_material_assign(bpy.types.Operator):
    bl_idname='ms.material_assign';bl_label='Assign Material';bl_options={'REGISTER','UNDO'}
    material:StringProperty()
    def execute(self,context):
        mat=bpy.data.materials.get(self.material)
        if not mat:return {'CANCELLED'}
        for obj in [o for o in context.view_layer.objects if o.select_get()]:
            if hasattr(obj.data,'materials'):
                if mat.name not in obj.data.materials:obj.data.materials.append(mat)
                index=list(obj.data.materials).index(mat);obj.active_material_index=index
                if obj.type=='MESH':
                    for face in obj.data.polygons:face.material_index=index
        return {'FINISHED'}
class MS_OT_material_user(bpy.types.Operator):
    bl_idname='ms.material_user';bl_label='Select Material User';bl_options={'UNDO'}
    object:StringProperty()
    def execute(self,context):
        obj=context.scene.objects.get(self.object)
        if not obj:return {'CANCELLED'}
        context.view_layer.update()
        if context.view_layer.objects.get(obj.name) != obj:
            message=label('该物体不在视图层，无法选中！','This object is not in the current view layer and cannot be selected.')
            def draw_notice(self,context):
                self.layout.label(text=message)
            context.window_manager.popup_menu(draw_notice,title=label('无法选中物体','Cannot select object'),icon='INFO')
            return {'CANCELLED'}
        for item in context.view_layer.objects:
            if item.select_get():item.select_set(False)
        obj.hide_set(False);obj.select_set(True);context.view_layer.objects.active=obj
        return {'FINISHED'}
class MS_OT_material_delete(bpy.types.Operator):
    bl_idname='ms.material_delete';bl_label='Delete Material';bl_options={'REGISTER'}
    material:StringProperty()
    def execute(self,context):
        mat=bpy.data.materials.get(self.material) if self.material else context.window_manager.ms_material
        if mat is None:return {'CANCELLED'}
        undo=not bpy.app.background and context.preferences.edit.use_global_undo
        if undo:bpy.ops.ed.undo_push(message='Before Delete Material')
        from . import material_editors
        names=[m.name for m in bpy.data.materials if not getattr(m,'is_grease_pencil',False)]
        index=names.index(mat.name);names.remove(mat.name)
        material_editors.before_remove(context,mat)
        bpy.data.materials.remove(mat,do_unlink=True)
        if names:material_editors.select(context,bpy.data.materials.get(names[min(index,len(names)-1)]))
        if undo:bpy.ops.ed.undo_push(message='Delete Material')
        for area in context.screen.areas:area.tag_redraw()
        return {'FINISHED'}

classes=[MS_OT_materials,MS_OT_material_new,MS_OT_material_assign,MS_OT_material_user,MS_OT_material_delete]
