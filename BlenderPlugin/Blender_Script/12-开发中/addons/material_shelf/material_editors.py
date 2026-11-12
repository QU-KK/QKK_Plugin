"""Material selection routes to native Properties and one reusable shader window."""
import bpy
_windows=set()

def sync_nodes(context,material):
    live={w.as_pointer():w for w in context.window_manager.windows}
    _windows.update(w.as_pointer() for w in live.values() if w.screen.get('ms_material_nodes',False) and any(a.type=='NODE_EDITOR' for a in w.screen.areas))
    _windows.intersection_update(k for k,w in live.items() if any(a.type=='NODE_EDITOR' for a in w.screen.areas))
    for key in list(_windows):
        window=live[key]
        for area in window.screen.areas:
            if area.type=='NODE_EDITOR':
                space=area.spaces.active;space.tree_type='ShaderNodeTree';space.shader_type='OBJECT';space.pin=True
                space.node_tree=material.node_tree
                area.tag_redraw()

def select(context,material):
    if material is None:return
    context.window_manager.ms_material=material
    from . import multiselect
    multiselect.ids(context.window).add(material.session_uid)
    from . import selection
    active=context.window.view_layer.objects.active
    selection._last[context.window.as_pointer()]=(active.as_pointer() if active else 0,context.window.scene.as_pointer())
    from .material_dock import is_dock
    for area in context.window.screen.areas:
        if context.scene.ms_settings.open_properties and area.type=='PROPERTIES' and not is_dock(area):
            space=area.spaces.active;space.pin_id=material;space.use_pin_id=True
            try:space.context='MATERIAL'
            except TypeError:
                def retry(target=area,mat=material,attempts=[0]):
                    try:
                        if not bpy.context.scene.ms_settings.open_properties:return None
                        if bpy.context.window_manager.ms_material!=mat:return None
                        if target.spaces.active.pin_id!=mat or not target.spaces.active.use_pin_id:return None
                        target.spaces.active.context='MATERIAL';target.tag_redraw()
                    except TypeError:
                        attempts[0]+=1
                        if attempts[0]<10:return .1
                    except ReferenceError:pass
                    return None
                bpy.app.timers.register(retry,first_interval=.1)
            area.tag_redraw()
    sync_nodes(context,material)
    for area in context.window.screen.areas:area.tag_redraw()

def open_nodes(context,material):
    if material is None:return {'CANCELLED'}
    if not material.use_nodes:material.use_nodes=True
    select(context,material)
    live={w.as_pointer() for w in context.window_manager.windows}
    _windows.intersection_update(live)
    from . import editor_geometry
    if _windows:
        editor_geometry.activate()
        return {'FINISHED'}
    editor_geometry.remember()
    native_before=editor_geometry.windows()
    parent_size=(context.window.width,context.window.height)
    before=set(live)
    source=max((a for a in context.window.screen.areas if a.type=='VIEW_3D'),key=lambda a:a.width*a.height,default=context.area)
    with context.temp_override(area=source,region=next(r for r in source.regions if r.type=='WINDOW')):result=bpy.ops.screen.area_dupli('INVOKE_DEFAULT')
    if 'CANCELLED' in result:return result
    created=[w for w in context.window_manager.windows if w.as_pointer() not in before]
    if not created:return {'CANCELLED'}
    window=created[0];_windows.add(window.as_pointer())
    editor_geometry.restore(native_before,parent_size)
    window.screen['ms_material_nodes']=True
    area=max(window.screen.areas,key=lambda a:a.width*a.height);area.type='NODE_EDITOR'
    area.spaces.active.show_region_ui=False
    sync_nodes(context,material)
    def frame():
        if window.as_pointer() not in {w.as_pointer() for w in bpy.context.window_manager.windows}:return None
        with bpy.context.temp_override(window=window,area=area,region=next(r for r in area.regions if r.type=='WINDOW')):
            bpy.ops.node.view_all()
        return None
    bpy.app.timers.register(frame,first_interval=.4)
    return {'FINISHED'}

def stop():
    _windows.clear()
    from . import editor_geometry
    editor_geometry.stop()

def before_remove(context,material):
    tree=material.node_tree
    for window in context.window_manager.windows:
        for area in window.screen.areas:
            space=area.spaces.active
            if area.type=='PROPERTIES' and space.pin_id==material:
                space.use_pin_id=False;space.pin_id=None
                try:space.context='TOOL'
                except TypeError:pass
            elif area.type=='NODE_EDITOR' and space.tree_type=='ShaderNodeTree' and tree and space.node_tree==tree:
                space.node_tree=None;space.pin=False
            area.tag_redraw()
    if context.window_manager.ms_material==material:context.window_manager.ms_material=None
