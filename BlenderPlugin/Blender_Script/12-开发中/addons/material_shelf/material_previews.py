"""Blender-owned material thumbnails. Device and engine choices remain native."""
import bpy,time
_pending=False;_states={};_changed={}
_errors={}

def signature(mat,seen=None):
    seen=set() if seen is None else seen
    tree=mat.node_tree if isinstance(mat,bpy.types.Material) else mat
    if not tree or tree.as_pointer() in seen:return ()
    seen.add(tree.as_pointer());result=[]
    for node in tree.nodes:
        values=[]
        for socket in list(node.inputs)+list(node.outputs):
            value=getattr(socket,'default_value',None)
            if value is not None and not isinstance(value,(str,int,float,bool)):
                try:value=tuple(value)
                except TypeError:value=str(value)
            values.append((socket.identifier,str(value)))
        properties=[]
        for prop in node.bl_rna.properties:
            if prop.is_readonly or prop.identifier in {'name','label','location','width','height','select','show_options','show_preview','show_texture'}:continue
            if prop.type in {'BOOLEAN','INT','FLOAT','STRING','ENUM'}:
                value=getattr(node,prop.identifier,None)
                properties.append((prop.identifier,str(value)))
        values.append(('properties',str(properties)))
        ramp=getattr(node,'color_ramp',None);image=getattr(node,'image',None)
        result.append((node.name,node.bl_idname,node.mute,tuple(values),tuple((e.position,tuple(e.color)) for e in ramp.elements) if ramp else (),(image.name,image.filepath,image.is_dirty) if image else None,tuple((k,str(getattr(node,k))) for k in ('operation','blend_type','distribution','noise_dimensions','projection','extension') if hasattr(node,k)),ramp.interpolation if ramp else None,signature(node.node_tree,seen) if getattr(node,'node_tree',None) else ()))
    return tuple(result),tuple((l.from_node.name,l.from_socket.identifier,l.to_node.name,l.to_socket.identifier) for l in tree.links)

def key(mat,context):return (context.scene.render.engine,tuple(mat.diffuse_color),mat.preview_render_type,mat.use_preview_world,signature(mat))

_dirty=set()
_updates=set()
_dependencies={}
_watch={}
_last_active=0

def deps_changed(scene,depsgraph):
    for update in depsgraph.updates:
        if isinstance(update.id,(bpy.types.Material,bpy.types.NodeTree,bpy.types.Image)):
            _updates.add(update.id.original.as_pointer())

def dependencies(material):
    result={material.as_pointer()}
    def visit(tree):
        if tree is None or tree.as_pointer() in result:return
        result.add(tree.as_pointer())
        for node in tree.nodes:
            image=getattr(node,'image',None)
            if image:result.add(image.as_pointer())
            visit(getattr(node,'node_tree',None))
    visit(material.node_tree)
    return result

_refreshing=False
_last_submit=-float('inf')
_last_force=-float('inf')

def preview_busy():
    try:return bpy.app.is_job_running('RENDER_PREVIEW')
    except (ValueError,TypeError):return False

def request(force=False):
    global _pending,_refreshing,_last_force
    if force:
        now=time.monotonic()
        if _pending or _refreshing or preview_busy() or now-_last_force<2:return False
        _last_force=now
        _refreshing=True
        _pending=True
    if not bpy.app.background and not bpy.app.timers.is_registered(tick):
        bpy.app.timers.register(tick,first_interval=.25)
    return True

def generate(material):
    material.asset_generate_preview()

def tick():
    global _pending,_last_active,_refreshing,_last_submit
    from . import material_dock,material_editors
    manager=bpy.context.window_manager
    docks=[(w,a) for w in manager.windows for a in w.screen.areas if material_dock.is_dock(a)]
    if not docks:return .5
    now=time.monotonic()
    materials={m.as_pointer():m for m in bpy.data.materials if not getattr(m,'is_grease_pencil',False)}
    for pointer in materials:
        if pointer not in _states:_dirty.add(pointer)
    if _pending:
        _states.clear();_errors.clear()
        _dirty.update(materials)
        _pending=False
    if _updates:
        for pointer,ids in _dependencies.items():
            if ids.intersection(_updates):_dirty.add(pointer)
        _updates.clear()
    active=manager.ms_material
    if active and now-_last_active>=.5:
        _dirty.add(active.as_pointer())
        _last_active=now
    for pointer in list(_states):
        if pointer not in materials:
            _states.pop(pointer,None);_dependencies.pop(pointer,None);_watch.pop(pointer,None)
    rendered=False
    changed=False
    for pointer in list(_dirty):
        mat=materials.get(pointer)
        if mat is None:
            _dirty.discard(pointer);continue
        current=key(mat,bpy.context)
        _dependencies[pointer]=dependencies(mat)
        if _states.get(pointer)==current:
            _dirty.discard(pointer);_changed.pop(pointer,None);continue
        if _changed.get(pointer,(None,))[0]!=current:
            _changed[pointer]=(current,now)
            continue
        if rendered or preview_busy() or now-_last_submit<.8 or now-_changed[pointer][1]<.3:continue
        try:generate(mat)
        except RuntimeError:
            _errors[pointer]=True
            _states[pointer]=current
            _dirty.discard(pointer)
            _changed.pop(pointer,None)
            continue
        _errors.pop(pointer,None)
        _last_submit=now
        _states[pointer]=current
        _changed.pop(pointer,None)
        _dirty.discard(pointer)
        _watch[pointer]=now+30
        rendered=True;changed=True
    if _refreshing and not _pending and not _dirty and not preview_busy() and now-_last_submit>=.8:
        _refreshing=False
    if active:material_editors.sync_nodes(bpy.context,active)
    if changed or any(until>now for until in _watch.values()):
        for _,area in docks:area.tag_redraw()
    return .3

def status():
    from .catalog import label
    if _refreshing:return label('正在刷新材质预览…','Refreshing material previews…')
    return label('当前项目材质的管理工作','Material management for the current project')
def stop():
    global _pending,_last_active,_refreshing,_last_submit,_last_force
    _refreshing=False;_last_submit=-float('inf');_last_force=-float('inf')
    _pending=False;_last_active=0
    _errors.clear();_states.clear();_changed.clear();_dirty.clear();_updates.clear();_dependencies.clear();_watch.clear()
    if bpy.app.timers.is_registered(tick):bpy.app.timers.unregister(tick)


def preview_status(material):
    from .catalog import label
    pointer=material.as_pointer()
    if pointer in _errors:return label('预览失败，请重试','Preview failed; retry')
    if pointer in _dirty or pointer not in _states:return label('等待预览','Waiting for preview')
    from . import grid
    if pointer in grid._sources:return ''
    if _watch.get(pointer,0)>time.monotonic():return label('生成预览中','Generating preview')
    return label('预览不可用，请重试','Preview unavailable; retry')

class MS_OT_preview_retry(bpy.types.Operator):
    bl_idname='ms.preview_retry'
    bl_label='Retry Material Preview'
    material:bpy.props.StringProperty()
    def execute(self,context):
        mat=bpy.data.materials.get(self.material) if self.material else context.window_manager.ms_material
        if mat is None:return {'CANCELLED'}
        pointer=mat.as_pointer()
        if preview_busy():return {'CANCELLED'}
        _errors.pop(pointer,None);_states.pop(pointer,None)
        _dirty.add(pointer)
        from . import grid
        grid._missing.discard(pointer)
        request()
        return {'FINISHED'}
classes=[MS_OT_preview_retry]
