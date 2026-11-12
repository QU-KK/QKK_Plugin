"""Embedded material editor with stable, immediately available sphere thumbnails."""
import bpy
import bpy.utils.previews
from .catalog import label
_areas=set();_items=[];_draws=[];_polls=[]
_highlight_handle=None

def ordered_materials():
    scene=bpy.context.scene
    used={slot.material for obj in scene.objects for slot in obj.material_slots} if scene else set()
    settings=scene.ms_settings if scene else None
    active=bpy.context.view_layer.objects.active
    active_materials={s.material for s in active.material_slots} if active else set()
    state=scene.ms_folders if scene else None
    folder_materials={link.material for link in state.links if link.folder==state.current} if state and state.current else {m for m in bpy.data.materials if not state or not any(link.material==m for link in state.links)}
    return sorted(
        (m for m in bpy.data.materials
         if (folder_materials is None or m in folder_materials) and (not settings or (settings.search.casefold() in m.name.casefold()
             and (settings.filter=='ALL' or settings.filter=='OBJECT' and m in active_materials
                  or settings.filter=='FAVORITES' and m.get('ms_favorite',False)
                  or settings.filter=='UNUSED' and not any(m==s.material for o in bpy.data.objects for s in o.material_slots)))) and not getattr(m,'is_grease_pencil',False)
         and (not m.get('ms_factory_material') or m in used)),
        key=lambda m:(m.get('ms_order',m.get('ms_created',0)),m.session_uid),reverse=True)

def object_materials(window):
    return {slot.material for obj in window.view_layer.objects if obj.select_get()
            for slot in obj.material_slots if slot.material}

def highlighted(window):
    return {mat.name for mat in object_materials(window)}

def is_dock(area):
    if area is None:return False
    if area.as_pointer() in _areas:return True
    if area.type!='PROPERTIES':return False
    space=area.spaces.active
    if space.context!='SCENE' or not space.use_pin_id or not isinstance(space.pin_id,bpy.types.Scene):return False
    return any(w.screen.get('ms_dock_index', -1)==i for w in bpy.context.window_manager.windows for i,a in enumerate(w.screen.areas) if a==area)

def is_open(window):return any(is_dock(a) for a in window.screen.areas)
def items(self,context):
    global _items
    result=[]
    for i,mat in enumerate(ordered_materials()):
        if getattr(mat,'is_grease_pencil',False):continue
        mat.preview_ensure()
        result.append((mat.name,mat.name,'Native material preview',mat.preview.icon_id,i))
    _items=result
    return _items

def selected(self,context):
    mat=bpy.data.materials.get(self.ms_material_tile)
    if mat:self.ms_material=mat

def toggle(context):
    window=context.window
    if is_open(window):
        dock=next(a for a in window.screen.areas if is_dock(a));view=next((a for a in window.screen.areas if a.type=='VIEW_3D' and abs(a.y-dock.y)<5 and abs(a.height-dock.height)<5),None)
        if not view:return {'CANCELLED'}
        _areas.discard(dock.as_pointer())
        if 'ms_dock_index' in window.screen:del window.screen['ms_dock_index']
        from .layout import join
        join(window,view,dock);return {'FINISHED'}
    view=max((a for a in window.screen.areas if a.type=='VIEW_3D'),key=lambda a:a.width*a.height)
    before={a.as_pointer() for a in window.screen.areas}
    with context.temp_override(area=view):bpy.ops.screen.area_split(direction='VERTICAL',factor=max(.5,1-300/view.width))
    new=next(a for a in window.screen.areas if a.as_pointer() not in before)
    def finish():
        dock=max((view,new),key=lambda a:a.x)
        window.screen['ms_dock_index']=list(window.screen.areas).index(dock)
        dock.type='PROPERTIES';_areas.add(dock.as_pointer());dock.spaces.active.context='SCENE'
        dock.spaces.active.pin_id=window.scene;dock.spaces.active.use_pin_id=True
        nav=next((r for r in dock.regions if r.type=='NAVIGATION_BAR'),None)
        if nav and nav.width>4:
            with bpy.context.temp_override(window=window,area=dock):bpy.ops.screen.region_toggle(region_type='NAVIGATION_BAR')
        from . import material_events
        material_events.start(window)
        dock.tag_redraw()
        return None
    bpy.app.timers.register(finish,first_interval=.3)
    from . import material_previews
    material_previews.request()
    install();return {'FINISHED'}

_outlines=None
_outline_states={}

def outlined_icon(material):
    # The border is part of the native thumbnail, so UI scaling and scrolling
    # transform both the preview and its outline together.
    global _outlines
    if _outlines is None:_outlines=bpy.utils.previews.new()
    source=material.preview
    width,height=source.image_size
    pixels=list(source.image_pixels_float)
    if not width or not height:
        width,height=source.icon_size
        pixels=list(source.icon_pixels_float)
    if not width or not height:return source.icon_id
    token=str(material.session_uid)
    state=(width,height,hash(tuple(pixels)))
    if _outline_states.get(token)!=state:
        if token in _outlines:del _outlines[token]
        border=max(2,round(min(width,height)*.025))
        color=[.035,.65,1.,1.]
        for y in range(height):
            for x in range(width):
                if x<border or y<border or x>=width-border or y>=height-border:
                    index=(y*width+x)*4
                    pixels[index:index+4]=color
        preview=_outlines.new(token)
        preview.image_size=(width,height)
        preview.image_pixels_float=pixels
        preview.icon_size=(width,height)
        preview.icon_pixels_float=pixels
        _outline_states[token]=state
    return _outlines[token].icon_id

def install():
    global _highlight_handle
    if _highlight_handle is None and not bpy.app.background:
        from .grid import draw
        _highlight_handle=bpy.types.SpaceProperties.draw_handler_add(draw,(),'WINDOW','POST_PIXEL')
    if _draws:return
    def wrap(original):
        def draw(self,context):
            if not is_dock(context.area):original(self,context)
        return draw
    for cls in bpy.types.Panel.__subclasses__():
        cls=getattr(bpy.types,cls.__name__,cls)
        if cls.__module__.startswith('bl_ui.') and 'bl_rna' in cls.__dict__ and getattr(cls,'bl_context',None)=='scene' and hasattr(cls,'draw'):
            original=cls.draw
            original_poll=getattr(cls,'poll',None)
            def make_poll(fn):
                def poll(cls,context):return not is_dock(context.area) and (fn(context) if fn else True)
                return classmethod(poll)
            had_poll='poll' in cls.__dict__;own_poll=cls.__dict__.get('poll')
            _polls.append((cls,had_poll,own_poll));cls.poll=make_poll(original_poll)
            draw=wrap(original)
            cls.draw=draw;_draws.append((cls,original,draw))
            bpy.utils.unregister_class(cls);bpy.utils.register_class(cls)

def stop():
    global _highlight_handle,_outlines
    if _outlines is not None:
        bpy.utils.previews.remove(_outlines)
        _outlines=None
    _outline_states.clear()
    from . import grid
    grid.clear()
    if _highlight_handle is not None:
        try:bpy.types.SpaceProperties.draw_handler_remove(_highlight_handle,'WINDOW')
        except (ValueError,ReferenceError):pass
        _highlight_handle=None
    for cls,original,wrapper in _draws:
        if cls.draw is wrapper:cls.draw=original
    for cls,had_poll,own_poll in _polls:
        if had_poll:cls.poll=own_poll
        else:delattr(cls,'poll')
        bpy.utils.unregister_class(cls);bpy.utils.register_class(cls)
    _polls.clear()
    _draws.clear();_areas.clear();_items.clear()

class MS_PT_material_dock(bpy.types.Panel):
    bl_label='Materials';bl_idname='MS_PT_material_dock';bl_space_type='PROPERTIES';bl_region_type='WINDOW';bl_context='scene';bl_options={'HIDE_HEADER'}
    @classmethod
    def poll(cls,context):return is_dock(context.area)
    def draw(self,context):
        l=self.layout;wm=context.window_manager
        settings=context.scene.ms_settings
        from .material_events import grid_columns
        import math
        from .folders import visible
        count=len(ordered_materials())+len(visible(context))
        rows=math.ceil(count/grid_columns(context.region,count)) if count else 1
        row=l.row(align=True)
        row.label(text=label('材质','Materials'))
        row=l.row(align=True)
        row.prop(settings,'search',text='',icon='VIEWZOOM')
        row.prop(settings,'filter',text='')
        l.prop(settings,'open_properties',text=label('点击材质即打开属性','Open properties on material click'))
        l.prop(settings,'auto_protect',text=label('创建材质自动保护','Automatically protect new materials'))
        l.prop(settings,'preview_resolution',text=label('预览分辨率','Preview resolution'))
        l.prop(settings,'size',text=label('缩略图大小','Thumbnail size'))
        row=l.row(align=True)
        row.alignment='RIGHT'
        op=row.operator('ms.folder',text='',icon='NEWFOLDER');op.action='NEW'
        row.operator('ms.material_new',text='',icon='ADD')
        row.operator('ms.material_refresh',text='',icon='FILE_REFRESH')
        row.operator('ms.delete_selection',text='',icon='TRASH')
        row=l.row(align=True)
        row.label(text='')
        spacer=l.row()
        from .material_events import grid_top
        spacer.scale_y=max(1,((grid_top(context.region)-260)+rows*(settings.size*20+32)+56)/20)
        spacer.label(text='')
        mat=wm.ms_material
        if not mat:
            l.label(text=label('使用对象数：','Objects using material: ')+'0')
            l.label(text=label('材质球总数：','Total materials: ')+str(sum(not getattr(m,'is_grease_pencil',False) for m in bpy.data.materials)))
            l.label(text=label('使用此材质的对象','Objects using this material'))
        if mat and mat.name in bpy.data.materials:
            from .features import users
            l.separator()
            l.label(text=label('使用对象数：','Objects using material: ')+str(len(users(mat))))
            from .protection import usage_counts
            l.label(text=label('数据使用次数：','Data users: ')+str(usage_counts().get(mat,0)))
            l.label(text=label('材质球总数：','Total materials: ')+str(sum(not getattr(m,'is_grease_pencil',False) for m in bpy.data.materials)))
            l.label(text=label('使用此材质的对象','Objects using this material'))
            for obj in context.scene.objects:
                if any(s.material==mat for s in obj.material_slots):l.operator('ms.material_user',text=obj.name,icon='OBJECT_DATA').object=obj.name
        from . import material_previews
        l.label(text=material_previews.status(),icon='INFO')
class MS_OT_material_pick(bpy.types.Operator):
    bl_idname='ms.material_pick';bl_label='Select Material'
    material:bpy.props.StringProperty()
    def invoke(self,context,event):
        from . import material_editors
        mat=bpy.data.materials.get(self.material)
        if event.value=='DOUBLE_CLICK':return material_editors.open_nodes(context,mat)
        return self.execute(context)
    def execute(self,context):
        from . import material_editors
        material_editors.select(context,bpy.data.materials.get(self.material))
        return {'FINISHED'}

class MS_OT_material_refresh(bpy.types.Operator):
    bl_idname='ms.material_refresh';bl_label='Refresh Rendered Previews'
    def execute(self,context):
        from . import material_previews
        material_previews.request(force=True);return {'FINISHED'}

classes=[MS_PT_material_dock,MS_OT_material_pick,MS_OT_material_refresh]
