import bpy,os,json,tempfile
from bpy.props import StringProperty,BoolProperty,EnumProperty
from .catalog import label

def dependencies(materials):
    images=set()
    trees=set()
    external=[]
    def visit(tree):
        if tree is None or tree.as_pointer() in trees:return
        trees.add(tree.as_pointer())
        for node in tree.nodes:
            image=getattr(node,'image',None)
            if image:images.add(image)
            if node.bl_idname in {'ShaderNodeTexIES','ShaderNodeScript'} and getattr(node,'mode','')=='EXTERNAL':
                external.append(node)
            visit(getattr(node,'node_tree',None))
    for mat in materials:visit(mat.node_tree)
    return images,external

def dependency_issues(materials):
    issues=[]
    images,external=dependencies(materials)
    for image in images:
        if image.source in {'MOVIE','SEQUENCE'}:
            issues.append(label('暂不支持打包视频或序列：','Movie/sequence packing is unsupported: ')+image.name)
            continue
        if image.packed_file or len(image.packed_files):continue
        path=bpy.path.abspath(image.filepath,library=image.library)
        if image.source=='TILED':
            for tile in image.tiles:
                tile_path=path.replace('<UDIM>',str(tile.number)).replace('<UVTILE>','u'+str((tile.number-1001)%10+1)+'_v'+str((tile.number-1001)//10+1))
                if not os.path.isfile(tile_path):issues.append(label('缺失 UDIM 贴图：','Missing UDIM tile: ')+image.name+' ['+str(tile.number)+']')
        elif image.source=='FILE' and not os.path.isfile(path) and not image.is_dirty:
            issues.append(label('缺失贴图：','Missing image: ')+image.name)
    for node in external:
        path=bpy.path.abspath(node.filepath,library=node.id_data.library)
        if not os.path.isfile(path):issues.append(label('缺失外部着色器资源：','Missing external shader resource: ')+node.name)
        elif node.bl_idname=='ShaderNodeScript' and path.lower().endswith('.oso'):
            issues.append(label('请使用 OSL 源文件而非编译文件：','Use OSL source instead of compiled bytecode: ')+node.name)
    return issues

class MS_OT_export_asset(bpy.types.Operator):
    bl_idname='ms.export_asset'
    bl_label='Save as Material Asset'
    directory:StringProperty(subtype='DIR_PATH')
    filter_folder:BoolProperty(default=True,options={'HIDDEN'})
    targets:StringProperty(options={'HIDDEN'})
    mode:EnumProperty(name='Export mode',items=[('SEPARATE','Separate projects','One blend file for each material'),('COMBINED','Combined project','One blend file containing all selected materials')])
    filename:StringProperty(name='Project name',default='Materials.blend')
    def invoke(self,context,event):
        from . import multiselect,material_dock
        selected=multiselect.ids(context.window)
        materials=[m for m in bpy.data.materials if m.session_uid in selected]
        if not materials and context.window_manager.ms_material:materials=[context.window_manager.ms_material]
        if not materials:return {'CANCELLED'}
        self.targets=json.dumps([m.name for m in materials])
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}
    def draw(self,context):
        self.layout.prop(self,'mode',text=label('导出方式','Export mode'))
        if self.mode=='COMBINED':self.layout.prop(self,'filename',text=label('工程名称','Project name'))
    def execute(self,context):
        folder=bpy.path.abspath(self.directory)
        if not self.directory or not os.path.isdir(folder):
            self.report({'ERROR'},label('请选择有效的文件夹','Choose an existing folder'))
            return {'CANCELLED'}
        names=json.loads(self.targets) if self.targets else [context.window_manager.ms_material.name] if context.window_manager.ms_material else []
        materials=[bpy.data.materials.get(name) for name in names]
        materials=[m for m in materials if m and m.is_editable]
        if not materials:return {'CANCELLED'}
        issues=dependency_issues(materials)
        if issues:
            def notice(self,context):
                for text in issues:self.layout.label(text=text)
            context.window_manager.popup_menu(notice,title=label('材质资产依赖检查','Material asset dependency check'),icon='ERROR')
            return {'CANCELLED'}
        groups=[materials] if self.mode=='COMBINED' else [[m] for m in materials]
        names=[bpy.path.clean_name(os.path.splitext(os.path.basename(self.filename))[0] or 'Materials')+'.blend'] if self.mode=='COMBINED' else [bpy.path.clean_name(m.name)+'.blend' for m in materials]
        paths=[os.path.join(folder,name) for name in names]
        if len(set(os.path.normcase(p) for p in paths))!=len(paths) or any(os.path.exists(p) for p in paths):
            self.report({'ERROR'},label('文件已存在或名称冲突，请更换文件夹或重命名材质','File exists or names conflict; choose another folder or rename the materials'))
            return {'CANCELLED'}
        packed=[]
        converted=[]
        staged=[]
        marked=[]
        try:
            images,external=dependencies(materials)
            for image in images:
                if image.source in {'MOVIE','SEQUENCE'}:
                    raise RuntimeError(label('视频或序列贴图暂不支持完整打包：','Movie or sequence textures cannot yet be fully packed: ')+image.name)
                if image.packed_file or len(image.packed_files):continue
                if image.source in {'FILE','TILED'} and not image.has_data:image.reload()
                original=image.filepath_raw
                image.pack()
                if not image.packed_file and not len(image.packed_files):raise RuntimeError('Cannot pack image: '+image.name)
                packed.append((image,original))
            for node in external:
                path=bpy.path.abspath(node.filepath,library=node.id_data.library)
                text=bpy.data.texts.load(path,internal=True)
                old=(node.mode,getattr(node,'script',None),getattr(node,'ies',None))
                converted.append((node,old,text))
                node.mode='INTERNAL'
                if node.bl_idname=='ShaderNodeTexIES':node.ies=text
                else:node.script=text
            for mat in materials:
                if mat.asset_data is None:mat.asset_mark();marked.append(mat)
            for group,path in zip(groups,paths):
                handle,temp=tempfile.mkstemp(suffix='.blend',prefix='.material-shelf-',dir=folder)
                os.close(handle)
                staged.append((temp,path))
                bpy.data.libraries.write(temp,set(group),path_remap='ABSOLUTE',fake_user=True)
            for (temp,path),group in zip(staged,groups):
                with bpy.data.libraries.load(temp) as (source,target):
                    if not {mat.name for mat in group}.issubset(set(source.materials)):
                        raise RuntimeError(label('导出验证失败，文件未发布','Export validation failed; files were not finalized'))
            for temp,path in staged:os.rename(temp,path)
        except (OSError,RuntimeError,ValueError) as exc:
            self.report({'ERROR'},str(exc))
            return {'CANCELLED'}
        finally:
            for temp,_ in staged:
                if os.path.exists(temp):os.remove(temp)
            for node,(mode,script,ies),text in reversed(converted):
                node.mode=mode
                if node.bl_idname=='ShaderNodeTexIES':node.ies=ies
                else:node.script=script
                if text.users==0:bpy.data.texts.remove(text)
            for image,path in packed:
                image.unpack(method='REMOVE')
                image.filepath_raw=path
            for mat in marked:mat.asset_clear()
        self.report({'INFO'},label('导出完成：工程 ','Export complete: projects ')+str(len(paths))+label('，材质 ',', materials ')+str(len(materials))+label('，贴图 ',', images ')+str(len(images)))
        return {'FINISHED'}
classes=[MS_OT_export_asset]
