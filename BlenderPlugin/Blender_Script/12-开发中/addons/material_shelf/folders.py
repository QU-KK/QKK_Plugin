import bpy,uuid
from bpy.props import StringProperty,PointerProperty,CollectionProperty,BoolProperty,EnumProperty
from .catalog import label

def unique_name(state,name,exclude=''):
    base=name.strip() or label('文件夹','Folder')
    used={f.name.casefold() for f in state.folders if f.uid!=exclude}
    candidate=base
    number=1
    while candidate.casefold() in used:
        candidate=base+'.'+str(number).zfill(3)
        number+=1
    return candidate

class MSFolder(bpy.types.PropertyGroup):
    uid:StringProperty()
    parent:StringProperty()
    opened:BoolProperty(default=False)
    name:StringProperty(name='Name')
class MSFolderLink(bpy.types.PropertyGroup):
    material:PointerProperty(type=bpy.types.Material)
    folder:StringProperty()
class MSFolders(bpy.types.PropertyGroup):
    folders:CollectionProperty(type=MSFolder)
    links:CollectionProperty(type=MSFolderLink)
    current:StringProperty()
    selected:StringProperty()

def visible(context):
    return [f for f in context.scene.ms_folders.folders if f.parent==context.scene.ms_folders.current]

def associated_folders(scene,material_names):
    return {link.folder for link in scene.ms_folders.links
            if link.material and link.material.name in material_names}

def move(context,materials,uid):
    state=context.scene.ms_folders
    for mat in materials:
        for index in reversed(range(len(state.links))):
            if state.links[index].material==mat:state.links.remove(index)
        if uid:
            link=state.links.add();link.material=mat;link.folder=uid

def copy_material(context,source,folder=None):
    copy=source.copy()
    independent_groups(copy.node_tree,{})
    copy.pop('ms_created',None)
    copy.pop('ms_order',None)
    uid=folder
    if uid is None:
        uid=next((link.folder for link in context.scene.ms_folders.links if link.material==source),'')
    if uid and any(f.uid==uid for f in context.scene.ms_folders.folders):
        link=context.scene.ms_folders.links.add();link.material=copy;link.folder=uid
    return copy

def independent_groups(tree, copies):
    if tree is None:return
    for node in tree.nodes:
        source=getattr(node,'node_tree',None)
        if source is None:continue
        key=source.as_pointer()
        if key not in copies:
            copies[key]=source.copy()
            independent_groups(copies[key],copies)
        node.node_tree=copies[key]

class MS_OT_folder(bpy.types.Operator):
    bl_idname='ms.folder'
    bl_label='Material Folder'
    bl_options={'UNDO'}
    action:StringProperty()
    uid:StringProperty()
    name:StringProperty(name='Name')
    def invoke(self,context,event):
        folder=next((f for f in context.scene.ms_folders.folders if f.uid==self.uid),None)
        if folder:self.name=folder.name
        elif self.action=='NEW':self.name=unique_name(context.scene.ms_folders,label('文件夹','Folder'))
        if self.action=='DELETE':
            import json
            from . import multiselect
            selected=multiselect.folder_ids(context.window)
            targets=list(selected) if self.uid in selected else [self.uid]
            return bpy.ops.ms.delete_selection('INVOKE_DEFAULT',folder_targets=json.dumps(targets),material_targets='[]')
        if self.action in {'NEW','RENAME'}:
            from . import material_events
            material_events.dialog_open=True
            return context.window_manager.invoke_props_dialog(self)
        return self.execute(context)
    def draw(self,context):
        if self.action=='DELETE':self.layout.label(text=label('删除文件夹，材质移回全部','Delete folder and return materials to All'))
        else:self.layout.prop(self,'name',text=label('名称','Name'))
    def cancel(self,context):
        from . import material_events
        material_events.dialog_open=False

    def execute(self,context):
        from . import material_events
        material_events.dialog_open=False
        state=context.scene.ms_folders
        folder=next((f for f in state.folders if f.uid==self.uid),None)
        if self.action=='OPEN':
            state.current=self.uid
            if folder:folder.opened=True
        elif self.action=='CLOSE':
            if folder:folder.opened=False
            if state.current==self.uid:state.current=''
        elif self.action=='NEW':
            parent=next((f for f in state.folders if f.uid==state.current),None)
            if parent and parent.parent:
                def notice(self,context):self.layout.label(text=label('此级别不可创建文件夹','Folders cannot be created at this level'))
                context.window_manager.popup_menu(notice,title=label('无法创建文件夹','Cannot create folder'),icon='INFO')
                return {'CANCELLED'}
            name=unique_name(state,self.name)
            folder=state.folders.add();folder.uid=uuid.uuid4().hex;folder.name=name;folder.parent=state.current
        elif folder and self.action=='RENAME':folder.name=unique_name(state,self.name,folder.uid)
        elif folder and self.action=='COPY':
            source_uid=folder.uid
            source_name=folder.name
            parent=folder.parent
            children=[(f.uid,f.name) for f in state.folders if f.parent==source_uid]
            entries={uid:[link.material for link in state.links if link.folder==uid and link.material] for uid in [source_uid]+[c[0] for c in children]}
            root=state.folders.add();root.uid=uuid.uuid4().hex;root.name=unique_name(state,source_name+label(' 副本',' Copy'),root.uid);root.parent=parent
            mapping={source_uid:root.uid}
            for uid,name in children:
                child=state.folders.add();child.uid=uuid.uuid4().hex;child.name=unique_name(state,name,child.uid);child.parent=root.uid
                mapping[uid]=child.uid
            for uid,materials in entries.items():
                for mat in materials:copy_material(context,mat,mapping[uid])
        elif folder and self.action=='DELETE':
            removed={self.uid}|{f.uid for f in state.folders if f.parent==self.uid}
            for index in reversed(range(len(state.links))):
                if state.links[index].folder in removed:state.links.remove(index)
            for index in reversed(range(len(state.folders))):
                if state.folders[index].uid in removed:state.folders.remove(index)
            if state.current in removed:state.current=''
            if state.selected in removed:state.selected=''
        elif self.action=='MOVE':
            from .multiselect import ids
            mats=[m for m in bpy.data.materials if m.session_uid in ids(context.window)]
            if not mats and context.window_manager.ms_material:mats=[context.window_manager.ms_material]
            if mats and all(any(link.material==mat and link.folder==self.uid for link in state.links) if self.uid else not any(link.material==mat for link in state.links) for mat in mats):return {'CANCELLED'}
            move(context,mats,self.uid)
        else:return {'CANCELLED'}
        for area in context.screen.areas:area.tag_redraw()
        return {'FINISHED'}
class MS_MT_folder_actions(bpy.types.Menu):
    bl_idname='MS_MT_folder_actions'
    bl_label='Folder'
    def draw(self,context):
        self.layout.operator_context='INVOKE_DEFAULT'
        uid=context.scene.ms_folders.selected
        for action,cn,en in [('OPEN','打开','Open'),('RENAME','重命名','Rename'),('COPY','复制文件夹及材质','Duplicate folder and materials'),('DELETE','删除文件夹','Delete folder')]:
            op=self.layout.operator('ms.folder',text=label(cn,en))
            op.action=action;op.uid=uid


class MS_OT_delete_selection(bpy.types.Operator):
    bl_idname='ms.delete_selection'
    bl_label='Delete Selection'
    bl_options={'UNDO'}
    folder_targets:StringProperty(options={'HIDDEN'})
    material_targets:StringProperty(options={'HIDDEN'})
    contents:EnumProperty(name='Folder contents',items=[
        ('KEEP','Move back to All','Keep folder materials'),
        ('DELETE','Delete together','Delete folder materials too')],default='KEEP')
    def capture(self,context):
        import json
        from . import multiselect
        self.folder_targets=json.dumps(list(multiselect.folder_ids(context.window)))
        self.material_targets=json.dumps([m.name for m in bpy.data.materials if m.session_uid in multiselect.ids(context.window)])
    def invoke(self,context,event):
        if not self.folder_targets:self.capture(context)
        from . import material_events
        material_events.dialog_open=True
        return context.window_manager.invoke_props_dialog(self)
    def draw(self,context):
        import json
        folder_ids=json.loads(self.folder_targets or '[]')
        materials=[bpy.data.materials.get(name) for name in json.loads(self.material_targets or '[]')]
        materials=[mat for mat in materials if mat]
        if not folder_ids:
            from .features import users
            self.layout.label(text=label('删除材质数量：','Materials to delete: ')+str(len(materials)))
            self.layout.label(text=label('受影响对象数量：','Affected objects: ')+str(len({obj for mat in materials for obj in users(mat)})))
        else:
            self.layout.label(text=label('删除选中的材质和文件夹后，文件夹内材质','After deleting selected materials and folders, their contents') if materials else label('删除选中的文件夹后，文件夹内材质','After deleting selected folders, their materials'))
            row=self.layout.row(align=True)
            row.prop_enum(self,'contents','KEEP',text=label('移回全部','Move back to All'))
            row.prop_enum(self,'contents','DELETE',text=label('共同删除','Delete together'))
    def cancel(self,context):
        from . import material_events
        material_events.dialog_open=False
    def execute(self,context):
        import json
        if not self.folder_targets:self.capture(context)
        self.cancel(context)
        folder_ids=set(json.loads(self.folder_targets))
        folder_ids.update(f.uid for f in context.scene.ms_folders.folders if f.parent in folder_ids)
        names=set(json.loads(self.material_targets or '[]'))
        if self.contents=='DELETE':
            names.update(link.material.name for link in context.scene.ms_folders.links if link.folder in folder_ids and link.material)
        for uid in list(folder_ids):
            if any(f.uid==uid for f in context.scene.ms_folders.folders):bpy.ops.ms.folder(action='DELETE',uid=uid)
        names=list(names)
        if names:bpy.ops.ms.manage(action='DELETE',targets=json.dumps(names))
        from . import multiselect
        multiselect.update_folders(context.window,[])
        multiselect.update(context.window,[])
        return {'FINISHED'}

classes=[MS_OT_delete_selection,MS_MT_folder_actions,MSFolder,MSFolderLink,MSFolders,MS_OT_folder]
