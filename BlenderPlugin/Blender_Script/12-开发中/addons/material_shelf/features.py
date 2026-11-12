import bpy
import bmesh
import json
from bpy.props import StringProperty, EnumProperty, IntProperty, BoolProperty
from .catalog import label

_clipboard=[]

def resolution_changed(self,context):
    from . import grid
    grid.invalidate_resolution()

from .protection import setting_changed

class MSSettings(bpy.types.PropertyGroup):
    search: StringProperty(name="Search")
    filter: EnumProperty(name="Filter", items=[('ALL','All',''),('OBJECT','Active object',''),('FAVORITES','Favorites',''),('UNUSED','Unused','')])
    size: IntProperty(name="Thumbnail size", default=4, min=2, max=8)
    auto_protect:BoolProperty(name='Auto-protect new materials',default=True,update=setting_changed)
    open_properties:BoolProperty(name="Open properties on material click",default=True)
    preview_resolution:EnumProperty(name='Preview resolution',items=[('32','32 px',''),('64','64 px',''),('128','128 px','')],default='64',update=resolution_changed)

def users(mat):
    return [o for o in bpy.data.objects if any(s.material==mat for s in o.material_slots)]

class MS_OT_manage(bpy.types.Operator):
    bl_idname='ms.manage'
    bl_label='Material Action'
    bl_options={'REGISTER','UNDO'}
    action: EnumProperty(items=[(x,x.replace('_',' ').title(),'') for x in ('ASSIGN','RENAME','DUPLICATE','COPY','PASTE','SELECT_USERS','REPLACE','UNLINK','DELETE','SINGLE_USER','FAVORITE')])
    name: StringProperty(name='Name')
    replacement: StringProperty(name='Replacement material')
    targets: StringProperty(options={'HIDDEN'})
    def invoke(self,context,event):
        mat=context.window_manager.ms_material
        if mat is None and self.action!='PASTE':return {'CANCELLED'}
        if self.action=='PASTE':return self.execute(context)
        self.name=mat.name
        self.capture(context)
        if self.action in {'RENAME','REPLACE','DELETE'}:
            from . import material_events
            material_events.dialog_open=True
            return context.window_manager.invoke_props_dialog(self)
        return self.execute(context)
    def draw(self,context):
        mat=context.window_manager.ms_material
        if self.action=='RENAME':self.layout.prop(self,'name')
        elif self.action=='REPLACE':self.layout.prop_search(self,'replacement',bpy.data,'materials')
        elif mat:
            targets=[bpy.data.materials.get(n) for n in json.loads(self.targets or '[]')]
            targets=[m for m in targets if m]
            self.layout.label(text=label('删除材质数量：','Materials to delete: ')+str(len(targets)))
            self.layout.label(text=label('受影响对象数量：','Affected objects: ')+str(len({o for m in targets for o in users(m)})))
    def capture(self,context):
        from . import multiselect,material_dock
        selected=multiselect.ids(context.window)
        targets=[m for m in bpy.data.materials if m.session_uid in selected]
        active=context.window_manager.ms_material
        if not targets and active:targets=[active]
        if self.action=='RENAME':targets=[active] if active else []
        self.targets=json.dumps([m.name for m in targets])

    def cancel(self,context):
        from . import material_events
        material_events.dialog_open=False

    def execute(self,context):
        from . import material_events
        material_events.dialog_open=False
        global _clipboard
        if self.action=='PASTE':
            from .folders import copy_material
            copies=[]
            for uid,folder in _clipboard:
                source=next((m for m in bpy.data.materials if m.session_uid==uid),None)
                if source:copies.append(copy_material(context,source,folder))
            if not copies:return {'CANCELLED'}
            from . import multiselect,material_editors
            multiselect.update(context.window,copies)
            material_editors.select(context,copies[-1])
            from .material_previews import request
            request()
            return {'FINISHED'}
        if not self.targets:self.capture(context)
        targets=[bpy.data.materials.get(n) for n in json.loads(self.targets)]
        targets=[m for m in targets if m and m.is_editable]
        if not targets:return {'CANCELLED'}
        active=context.window_manager.ms_material
        if self.action=='COPY':
            _clipboard=[(m.session_uid,next((link.folder for link in context.scene.ms_folders.links if link.material==m),'')) for m in targets]
            return {'FINISHED'}
        # Batch assignment adds every selected material as a slot. Only the
        # active material is applied to faces, preserving a meaningful result.
        if self.action=='ASSIGN' and len(targets)>1:
            for obj in context.view_layer.objects:
                if not obj.select_get():continue
                if obj.is_editable and hasattr(obj.data,'materials') and obj.data.is_editable:
                    for material in targets:
                        if material.name not in obj.data.materials:obj.data.materials.append(material)
            targets=[active] if active in targets else targets[:1]
        if self.action=='SELECT_USERS':
            objects={o for m in targets for o in users(m)}
            for obj in context.view_layer.objects:obj.select_set(False)
            for obj in objects:
                if obj.name in context.view_layer.objects:
                    obj.hide_set(False);obj.select_set(True);context.view_layer.objects.active=obj
            return {'FINISHED'}
        active_name=active.name if active else ''
        favorite=not all(m.get('ms_favorite',False) for m in targets)
        try:
            for material in targets:
                context.window_manager.ms_material=material
                if self.action=='FAVORITE':
                    material['ms_favorite']=favorite
                    if favorite:material.asset_mark()
                else:
                    result=self.execute_single(context)
                    if 'CANCELLED' in result:return result
        finally:
            context.window_manager.ms_material=bpy.data.materials.get(active_name)
        return {'FINISHED'}

    def execute_single(self,context):
        mat=context.window_manager.ms_material
        if mat is None:return {'CANCELLED'}
        selected=[o for o in context.view_layer.objects if o.select_get()]
        if self.action=='RENAME':
            if not mat.is_editable:return {'CANCELLED'}
            mat.name=self.name
        elif self.action=='DUPLICATE':
            from .folders import copy_material
            copy=copy_material(context,mat)
            from .material_editors import select
            select(context,copy)
        elif self.action=='FAVORITE':
            if not mat.is_editable:return {'CANCELLED'}
            mat['ms_favorite']=not mat.get('ms_favorite',False)
            if mat['ms_favorite']:mat.asset_mark()
        elif self.action=='SELECT_USERS':
            for obj in context.view_layer.objects:obj.select_set(False)
            for obj in users(mat):
                if obj.name in context.view_layer.objects:
                    obj.hide_set(False);obj.select_set(True)
                    context.view_layer.objects.active=obj
        elif self.action in {'ASSIGN','SINGLE_USER'}:
            target=mat
            if self.action=='SINGLE_USER' and not selected:return {'CANCELLED'}
            for obj in selected:
                if not obj.is_editable or not hasattr(obj.data,'materials'):continue
                if self.action=='SINGLE_USER':
                    if not obj.data.is_editable:continue
                    if obj.data.users>1:obj.data=obj.data.copy()
                    target=mat.copy()
                    target.pop('ms_created',None)
                    target.pop('ms_order',None)
                    for slot in obj.material_slots:
                        if slot.material==mat:slot.material=target
                    continue
                if not obj.data.is_editable:continue
                if mat.name not in obj.data.materials:obj.data.materials.append(mat)
                index=list(obj.data.materials).index(mat)
                obj.active_material_index=index
                if obj.type=='MESH':
                    if obj.mode=='EDIT':
                        mesh=bmesh.from_edit_mesh(obj.data)
                        for face in mesh.faces:
                            if face.select:face.material_index=index
                        bmesh.update_edit_mesh(obj.data)
                    else:
                        for face in obj.data.polygons:face.material_index=index
        elif self.action in {'REPLACE','UNLINK'}:
            if self.action=='REPLACE' and bpy.data.materials.get(self.replacement) is None:return {'CANCELLED'}
            for obj in selected:
                if not obj.is_editable:continue
                if self.action=='REPLACE':
                    for slot in obj.material_slots:
                        if slot.material==mat:slot.material=bpy.data.materials.get(self.replacement)
                    continue
                indices=[i for i,slot in enumerate(obj.material_slots) if slot.material==mat]
                if not indices:continue
                if not obj.data.is_editable:
                    self.report({'WARNING'},'Cannot remove slots from linked object data')
                    continue
                editing=context.mode=='EDIT_MESH'
                if editing:bpy.ops.object.mode_set(mode='OBJECT')
                try:
                    # Slot removal changes data shared by all instances.
                    # Give this selected object its own data before changing slots.
                    if obj.data.users>1:obj.data=obj.data.copy()
                    with context.temp_override(object=obj,active_object=obj,selected_objects=[obj],selected_editable_objects=[obj]):
                        for index in reversed(indices):
                            obj.active_material_index=index
                            bpy.ops.object.material_slot_remove()
                finally:
                    if editing:bpy.ops.object.mode_set(mode='EDIT')
        elif self.action=='DELETE':
            if not mat.is_editable:return {'CANCELLED'}
            from .material_editors import before_remove
            before_remove(context,mat)
            bpy.data.materials.remove(mat,do_unlink=True)
        from .material_previews import request
        request()
        for window in context.window_manager.windows:
            for area in window.screen.areas:area.tag_redraw()
        return {'FINISHED'}

class MS_MT_actions(bpy.types.Menu):
    bl_idname='MS_MT_actions'
    bl_label='Material'
    def draw(self,context):
        self.layout.operator_context='INVOKE_DEFAULT'
        for action,cn,en in [('ASSIGN','分配给选中对象/面','Assign to selected objects/faces'),('RENAME','重命名','Rename'),('DUPLICATE','创建副本','Duplicate'),('COPY','复制','Copy'),('PASTE','粘贴','Paste'),('SELECT_USERS','选择全部使用者','Select all users'),('REPLACE','替换选中对象上的材质','Replace on selected objects'),('UNLINK','从选中对象解除分配','Unlink from selected objects'),('SINGLE_USER','为选中对象创建独享副本','Make single user for selected objects'),('FAVORITE','切换收藏','Toggle favorite'),('DELETE','删除材质','Delete material')]:
            self.layout.operator('ms.manage',text=label(cn,en)).action=action
        self.layout.operator('ms.preview_retry',text=label('重试当前材质预览','Retry current material preview'),icon='FILE_REFRESH')
        self.layout.operator('ms.export_asset',text=label('保存为材质资产','Save as material asset'),icon='ASSET_MANAGER')


class MS_OT_reorder(bpy.types.Operator):
    bl_idname='ms.reorder'
    bl_label='Reorder Materials'
    bl_options={'UNDO','INTERNAL'}
    source: StringProperty()
    target: StringProperty()
    def execute(self,context):
        source=bpy.data.materials.get(self.source)
        target=bpy.data.materials.get(self.target)
        if source is None or target is None or source==target:return {'CANCELLED'}
        if source.library or target.library:return {'CANCELLED'}
        materials=sorted((m for m in bpy.data.materials if not m.library),key=lambda m:(m.get('ms_order',m.get('ms_created',0)),m.session_uid),reverse=True)
        materials.remove(source)
        materials.insert(materials.index(target),source)
        for index,mat in enumerate(materials):mat['ms_order']=len(materials)-index
        for area in context.screen.areas:area.tag_redraw()
        return {'FINISHED'}


classes=[MSSettings,MS_OT_manage,MS_MT_actions,MS_OT_reorder]
