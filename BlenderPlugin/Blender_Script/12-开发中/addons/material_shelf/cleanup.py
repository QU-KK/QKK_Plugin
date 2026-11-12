import bpy
from bpy.props import EnumProperty
from .catalog import label

def comparable(material):
    if material.library or material.asset_data or material.animation_data:return None
    from .material_previews import signature
    values=[]
    for prop in material.bl_rna.properties:
        if prop.identifier in {'name','name_full','users','use_fake_user','is_updated','is_updated_data','session_uid','preview','node_tree'}:continue
        if prop.is_readonly:continue
        if prop.type in {'BOOLEAN','INT','FLOAT','ENUM','STRING'}:
            values.append((prop.identifier,str(getattr(material,prop.identifier))))
    tree=material.node_tree
    refs=[]
    if tree:
        if tree.animation_data:return None
        for node in tree.nodes:
            for prop in node.bl_rna.properties:
                if prop.type=='POINTER' and prop.identifier not in {'rna_type'}:
                    value=getattr(node,prop.identifier,None)
                    if isinstance(value,bpy.types.ID):refs.append((node.name,prop.identifier,value.as_pointer()))
    custom=tuple(sorted((k,str(v)) for k,v in material.items() if not k.startswith('ms_')))
    return tuple(values),signature(material),tuple(refs),custom,bool(material.get('ms_favorite'))

class MS_OT_cleanup(bpy.types.Operator):
    bl_idname='ms.cleanup'
    bl_label='Material Management'
    bl_options={'REGISTER','UNDO'}
    action:EnumProperty(items=[('UNUSED','Delete unused',''),('MERGE','Merge duplicates',''),('SORT','Sort A–Z','')])
    def invoke(self,context,event):
        if self.action=='SORT':return self.execute(context)
        from . import material_events
        material_events.dialog_open=True
        return context.window_manager.invoke_props_dialog(self)
    def draw(self,context):
        self.layout.label(text=label('操作当前项目中的材质，可撤销','Process materials in this project; undo is available'))
    def cancel(self,context):
        from . import material_events
        material_events.dialog_open=False
    def execute(self,context):
        self.cancel(context)
        from . import material_dock,material_editors,multiselect
        count=0
        if self.action=='SORT':
            materials=sorted(material_dock.ordered_materials(),key=lambda m:m.name.casefold())
            # Reuse this directory's existing ranks to avoid disturbing other folders.
            maximum=max((m.get('ms_order',m.get('ms_created',0)) for m in bpy.data.materials),default=0)+len(materials)
            ranks=range(maximum,maximum-len(materials),-1)
            for mat,rank in zip(materials,ranks):
                if mat.is_editable:mat['ms_order']=rank
        elif self.action=='UNUSED':
            for mat in list(bpy.data.materials):
                if not mat.library and not mat.asset_data and not mat.use_fake_user and mat.users==0:
                    material_editors.before_remove(context,mat)
                    bpy.data.materials.remove(mat)
                    count+=1
        else:
            known={}
            for mat in list(bpy.data.materials):
                key=comparable(mat)
                if key is None:continue
                if key not in known:known[key]=mat;continue
                target=known[key]
                material_editors.before_remove(context,mat)
                mat.user_remap(target)
                bpy.data.materials.remove(mat)
                count+=1
        multiselect.ids(context.window)
        from .material_previews import request
        request()
        for area in context.screen.areas:area.tag_redraw()
        self.report({'INFO'},label('处理材质数量：','Materials processed: ')+str(count))
        return {'FINISHED'}

class MS_OT_select_object_materials(bpy.types.Operator):
    bl_idname='ms.select_object_materials'
    bl_label='Select All Materials of Selected Objects'
    def execute(self,context):
        from . import material_dock,multiselect,material_editors
        materials=material_dock.object_materials(context.window)
        multiselect.update(context.window,materials)
        multiselect.update_folders(context.window,[])
        if materials:
            active=context.window_manager.ms_material
            if active not in materials:
                active=next(m for m in bpy.data.materials if m in materials)
            material_editors.select(context,active)
        return {'FINISHED'}

class MS_MT_empty(bpy.types.Menu):
    bl_idname='MS_MT_empty'
    bl_label='Materials'
    def draw(self,context):
        self.layout.operator_context='INVOKE_DEFAULT'
        self.layout.operator('ms.material_new',text=label('新增材质','New material'),icon='ADD')
        self.layout.operator('ms.folder',text=label('新建文件夹','New folder'),icon='NEWFOLDER').action='NEW'
        self.layout.operator('ms.select_object_materials',text=label('选择选中项的所有材质','Select all materials of selected objects'),icon='RESTRICT_SELECT_OFF')
        for action,cn,en in [('UNUSED','删除未使用材质','Delete unused materials'),('MERGE','合并重复材质','Merge duplicate materials'),('SORT','排列材质 A~Z','Sort materials A–Z')]:
            self.layout.operator('ms.cleanup',text=label(cn,en)).action=action
classes=[MS_OT_select_object_materials,MS_OT_cleanup,MS_MT_empty]
