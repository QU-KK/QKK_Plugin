"""Hit testing for native preview tiles; route clicks before icon zoom handles them."""
import bpy,math,time
_running={};_generation=0
dialog_open=False

def grid_columns(region,count=None):
    left=region.view2d.region_to_view(0,0)[0];right=region.view2d.region_to_view(region.width,0)[0]
    scale=bpy.context.preferences.system.ui_scale
    columns=max(1,int((right-left)/((bpy.context.scene.ms_settings.size*20+5)*scale)))
    return columns

def all_rectangles(area,region,count,scale=None):
    scale=bpy.context.preferences.system.ui_scale if scale is None else scale
    columns=grid_columns(region,count)
    left=region.view2d.region_to_view(0,0)[0]
    right=region.view2d.region_to_view(region.width,0)[0]
    cell=(right-left-20*scale)/columns
    height=(bpy.context.scene.ms_settings.size*20+32)*scale
    return [(10*scale+(i%columns)*cell,-(grid_top(region)*scale+(i//columns)*height),cell,height) for i in range(count)]

def rectangles(area,region,count,scale=None):
    from .folders import visible
    folders=len(visible(bpy.context))
    return all_rectangles(area,region,count+folders,scale)[folders:]

def tab_rectangles(region):
    state=bpy.context.scene.ms_folders
    tabs=[('', '全部')]+[(f.uid,f.name) for f in state.folders if f.opened]
    scale=bpy.context.preferences.system.ui_scale
    left=region.view2d.region_to_view(0,0)[0]
    right=region.view2d.region_to_view(region.width,0)[0]
    import blf
    from .catalog import label
    blf.size(0,12)
    x=10*scale;row=0;result=[]
    for uid,name in tabs:
        text=name if uid else label('全部','All')
        width=min(right-left-20*scale,max(36*scale,blf.dimensions(0,text)[0]+(30 if uid else 16)*scale))
        if x+width>right-10*scale and x>10*scale:x=10*scale;row+=1
        result.append((uid,name,(x,-(228+row*28)*scale,width,24*scale)))
        x+=width+4*scale
    return result

def grid_top(region):
    scale=bpy.context.preferences.system.ui_scale
    return 32-tab_rectangles(region)[-1][2][1]/scale

def tab_hit(region,x,y):
    vx,vy=region.view2d.region_to_view(x,y)
    for uid,name,(left,top,width,height) in tab_rectangles(region):
        if left<=vx<left+width and top-height<=vy<=top:
            return uid,bool(uid and vx>left+width-20*bpy.context.preferences.system.ui_scale)
    return None

def root_rect(region):return tab_rectangles(region)[0][2]
def root_hit(region,x,y):
    result=tab_hit(region,x,y)
    return result is not None and result[0]==''

def folder_hit(area,region,x,y):
    from .folders import visible
    tab=tab_hit(region,x,y)
    if tab and tab[0]:return tab[0]
    folders=visible(bpy.context)
    from .material_dock import ordered_materials
    vx,vy=region.view2d.region_to_view(x,y)
    for folder,(left,top,width,height) in zip(folders,all_rectangles(area,region,len(folders)+len(ordered_materials()))):
        if left<=vx<left+width and top-height<=vy<=top:return folder.uid
    return None

def box_zone(area,region,x,y):
    from .material_dock import ordered_materials
    from .folders import visible
    scale=bpy.context.preferences.system.ui_scale
    vx,vy=region.view2d.region_to_view(x,y)
    right=region.view2d.region_to_view(region.width,0)[0]
    if vy>-200*scale:return False
    # Keep the actual toolbar buttons interactive, while allowing blank toolbar space.
    if vy>-228*scale and vx>right-110*scale:return False
    count=len(ordered_materials())+len(visible(bpy.context))
    rows=max(1,math.ceil(count/grid_columns(region,count)))
    bottom=-(grid_top(region)+rows*(bpy.context.scene.ms_settings.size*20+32)+100)*scale
    return vy>=bottom

def hit(area,region,x,y,names):
    # Convert through View2D so scrolling and Properties zoom stay in sync.
    vx,vy=region.view2d.region_to_view(x,y)
    for name,(left,top,width,height) in zip(names,rectangles(area,region,len(names))):
        if left<=vx<left+width and top-height<=vy<=top:return name
    return None

class MS_OT_material_events(bpy.types.Operator):
    bl_idname='ms.material_events';bl_label='Material Tile Interaction';bl_options={'INTERNAL'}
    def invoke(self,context,event):
        key=context.window.as_pointer()
        if _running.get(key)==_generation:return {'CANCELLED'}
        self.key=key;self.generation=_generation;self.last_name='';self.last_time=0;self.pressed=None;self.box_start=None;self.popup=False
        _running[key]=_generation;context.window_manager.modal_handler_add(self);return {'RUNNING_MODAL'}
    def modal(self,context,event):
        if self.generation!=_generation:
            if _running.get(self.key)==self.generation:_running.pop(self.key,None)
            return {'CANCELLED'}
        if dialog_open:return {'PASS_THROUGH'}
        if event.type=='Z' and event.value=='PRESS' and event.ctrl:
            self.pressed=None;self.box_start=None
            from . import grid,drag_feedback,multiselect
            grid.drag=None;multiselect.box=None
            drag_feedback.clear()
            context.window.cursor_modal_restore()
            return {'PASS_THROUGH'}

        if self.popup:
            if event.type=='RIGHTMOUSE' and event.value=='PRESS':
                # A second right click may have dismissed the previous popup.
                # Route this fresh click normally instead of leaving the grid
                # permanently suspended.
                self.popup=False
            else:
                if (event.type=='LEFTMOUSE' and event.value=='RELEASE') or event.type in {'ESC','RET','NUMPAD_ENTER','WINDOW_DEACTIVATE'}:self.popup=False
                return {'PASS_THROUGH'}
        from . import multiselect,material_dock
        if self.box_start:
            area,region,sx,sy,mode=self.box_start
            if event.type in {'ESC','WINDOW_DEACTIVATE','RIGHTMOUSE'}:
                self.box_start=None;multiselect.box=None
                area.tag_redraw()
                return {'RUNNING_MODAL'}
            x,y=event.mouse_x-region.x,event.mouse_y-region.y
            multiselect.box=(area.as_pointer(),sx,sy,x,y)
            area.tag_redraw()
            if event.type=='LEFTMOUSE' and event.value=='RELEASE':
                with context.temp_override(area=area,region=region):
                    mats=material_dock.ordered_materials()
                    selected=[]
                    for mat,(left,top,width,height) in zip(mats,rectangles(area,region,len(mats))):
                        a,b=region.view2d.view_to_region(left,top,clip=False)
                        c,d=region.view2d.view_to_region(left+width,top-height,clip=False)
                        if min(sx,x)<c and max(sx,x)>a and min(sy,y)<b and max(sy,y)>d:selected.append(mat)
                    multiselect.update(context.window,selected,mode)
                    from .folders import visible
                    folders=visible(context)
                    chosen=[]
                    for folder,(left,top,width,height) in zip(folders,all_rectangles(area,region,len(folders)+len(mats))):
                        a,b=region.view2d.view_to_region(left,top,clip=False)
                        c,d=region.view2d.view_to_region(left+width,top-height,clip=False)
                        if min(sx,x)<c and max(sx,x)>a and min(sy,y)<b and max(sy,y)>d:chosen.append(folder)
                    multiselect.update_folders(context.window,chosen,mode)
                self.box_start=None;multiselect.box=None
            return {'RUNNING_MODAL'}
        if self.pressed and event.type in {'ESC','WINDOW_DEACTIVATE','RIGHTMOUSE'}:
            self.pressed=None
            from . import grid
            grid.drag=None
            context.window.cursor_modal_restore()
        from . import grid
        if self.pressed:
            grid.drag=(self.pressed[0],self.pressed[1],event.mouse_x,event.mouse_y)
            for a in context.screen.areas:
                if a.type=='PROPERTIES':a.tag_redraw()
        else:grid.drag=None
        from . import drag_feedback
        drag_feedback.update(context,event)
        if self.pressed and event.type=='MOUSEMOVE' and time.monotonic()-self.pressed[1]>=.35:
            if getattr(self,'drag_ids',None):
                multiselect.ids(context.window).update(self.drag_ids)
            context.window.cursor_modal_set('SCROLL_XY')
        if self.pressed and event.type=='LEFTMOUSE' and event.value=='RELEASE':
            from . import drag_feedback
            drag_feedback.clear()
            source,started=self.pressed
            self.pressed=None
            from . import grid
            grid.drag=None
            context.window.cursor_modal_restore()
            if time.monotonic()-started>=.35:
                target_area=next((a for a in context.screen.areas if a.x<=event.mouse_x<a.x+a.width and a.y<=event.mouse_y<a.y+a.height and a.type in {'VIEW_3D','OUTLINER'}),None)
                if target_area:
                    target_region=next((r for r in target_area.regions if r.type=='WINDOW'),None)
                    if target_region:
                        with context.temp_override(area=target_area,region=target_region):
                            bpy.ops.ms.drop_material(material=source,x=event.mouse_x-target_region.x,y=event.mouse_y-target_region.y,face=event.shift)
                    return {'RUNNING_MODAL'}
                from . import material_dock
                for area in context.screen.areas:
                    if not material_dock.is_dock(area):continue
                    region=next((r for r in area.regions if r.type=='WINDOW'),None)
                    if region is None:continue
                    x,y=event.mouse_x-region.x,event.mouse_y-region.y
                    if not (0<=x<region.width and 0<=y<region.height):continue
                    with context.temp_override(area=area,region=region):
                        if root_hit(region,x,y):
                            bpy.ops.ms.folder(action='MOVE',uid='')
                            return {'RUNNING_MODAL'}
                        folder=folder_hit(area,region,x,y)
                        if folder:
                            bpy.ops.ms.folder(action='MOVE',uid=folder)
                            return {'RUNNING_MODAL'}
                        target=hit(area,region,x,y,[m.name for m in material_dock.ordered_materials()])
                        if target:bpy.ops.ms.reorder(source=source,target=target)
                return {'RUNNING_MODAL'}
        if event.type=='LEFTMOUSE' and event.value=='RELEASE':
            area=next((a for a in context.window.screen.areas if a.x<=event.mouse_x<a.x+a.width and a.y<=event.mouse_y<a.y+a.height),None)
            if area and area.type in {'VIEW_3D','OUTLINER'}:
                window=context.window
                def follow_object():
                    from . import selection
                    try:
                        obj=window.view_layer.objects.active
                        if not obj or not obj.select_get():
                            multiselect.update(window,[])
                            window.scene.ms_folders.selected=''
                        if obj and obj.select_get():
                            selection._last.pop(window.as_pointer(),None);selection.focus()
                    except ReferenceError:pass
                    return None
                bpy.app.timers.register(follow_object,first_interval=.1)
        rightclick=event.type=='RIGHTMOUSE' and event.value=='PRESS'
        deleting=event.type=='DEL' and event.value=='PRESS'
        select_all=event.type=='A' and event.value=='PRESS' and not (event.ctrl or event.alt)
        if not select_all and not deleting and not rightclick and (event.type!='LEFTMOUSE' or event.value not in {'PRESS','DOUBLE_CLICK'}):return {'PASS_THROUGH'}
        from . import material_dock,material_editors
        for area in context.window.screen.areas:
            if not material_dock.is_dock(area):continue
            region=next((r for r in area.regions if r.type=='WINDOW'),None)
            if region is None:continue
            x=event.mouse_x-region.x;y=event.mouse_y-region.y
            if not (0<=x<region.width and 0<=y<region.height):continue
            if select_all:
                if region.view2d.region_to_view(x,y)[1]>=-grid_top(region)*context.preferences.system.ui_scale:return {'PASS_THROUGH'}
                multiselect.update(context.window,material_dock.ordered_materials())
                context.scene.ms_folders.selected=''
                return {'RUNNING_MODAL'}
            if deleting:
                self.popup=True
                with context.temp_override(area=area,region=region):
                    bpy.ops.ms.delete_selection('INVOKE_DEFAULT')
                return {'RUNNING_MODAL'}
            tab=tab_hit(region,x,y)
            if tab and event.type=='LEFTMOUSE' and event.value=='PRESS':
                bpy.ops.ms.folder(action='CLOSE' if tab[1] else 'OPEN',uid=tab[0])
                return {'RUNNING_MODAL'}
            if event.type=='LEFTMOUSE' and event.value=='PRESS' and root_hit(region,x,y):
                bpy.ops.ms.folder(action='OPEN',uid='')
                return {'RUNNING_MODAL'}
            folder=folder_hit(area,region,x,y)
            if folder:
                value=next(f for f in context.scene.ms_folders.folders if f.uid==folder)
                if event.type=='LEFTMOUSE':
                    multiselect.update_folders(context.window,[value],'SUBTRACT' if event.ctrl else 'ADD' if event.shift else 'SET')
                    if not(event.ctrl or event.shift):multiselect.update(context.window,[])
                elif folder not in multiselect.folder_ids(context.window):
                    multiselect.update_folders(context.window,[value])
                context.scene.ms_folders.selected=folder if folder in multiselect.folder_ids(context.window) else ''
                area.tag_redraw()
                if event.type=='RIGHTMOUSE' and event.value=='PRESS':
                    self.popup=True
                    with context.temp_override(area=area,region=region):bpy.ops.wm.call_menu(name='MS_MT_folder_actions')
                elif event.type=='LEFTMOUSE' and event.value in {'PRESS','DOUBLE_CLICK'}:
                    now=time.monotonic()
                    double=event.value=='DOUBLE_CLICK' or (self.last_name==folder and now-self.last_time<.4)
                    self.last_name=folder;self.last_time=now
                    if double and not(event.ctrl or event.shift):
                        with context.temp_override(area=area,region=region):bpy.ops.ms.folder(action='OPEN',uid=folder)
                return {'RUNNING_MODAL'}
            names=[item[0] for item in material_dock.items(context.window_manager,context)]
            name=hit(area,region,x,y,names)
            if name and event.type=='LEFTMOUSE' and event.value=='PRESS':
                mat_index=names.index(name)
                left,top,width,height=rectangles(area,region,len(names))[mat_index]
                vx,vy=region.view2d.region_to_view(x,y)
                scale=context.preferences.system.ui_scale
                if vx>=left+width-32*scale and vy>=top-24*scale:
                    bpy.ops.ms.protect(material=name)
                    return {'RUNNING_MODAL'}

            if not name:
                if rightclick:
                    self.popup=True
                    with context.temp_override(area=area,region=region):bpy.ops.wm.call_menu(name='MS_MT_empty')
                    return {'RUNNING_MODAL'}
                if not box_zone(area,region,x,y):return {'PASS_THROUGH'}
                if event.type=='LEFTMOUSE' and event.value=='PRESS':
                    multiselect.update(context.window,[])
                    context.scene.ms_folders.selected=''
                vx,vy=region.view2d.region_to_view(x,y)
                if event.type=='LEFTMOUSE' and event.value=='PRESS':
                    multiselect.update_folders(context.window,[])
                    self.box_start=(area,region,x,y,'SUBTRACT' if event.ctrl else 'ADD' if event.shift else 'SET')
                    return {'RUNNING_MODAL'}
                return {'PASS_THROUGH'}
            if event.type=='LEFTMOUSE' and event.value=='PRESS' and not (event.shift or event.ctrl):
                self.drag_ids=set(multiselect.ids(context.window))
                self.pressed=(name,time.monotonic())
            if not(event.ctrl or event.shift):multiselect.update_folders(context.window,[])
            mat=bpy.data.materials.get(name)
            if not rightclick and not (event.shift or event.ctrl):multiselect.update(context.window,[mat])
            now=time.monotonic();double=event.value=='DOUBLE_CLICK' or (self.last_name==name and now-self.last_time<.4)
            self.last_name=name;self.last_time=now
            with context.temp_override(area=area,region=region):
                if event.ctrl and not rightclick:
                    multiselect.update(context.window,[mat],'SUBTRACT')
                elif event.shift and not rightclick:
                    multiselect.update(context.window,[mat],'ADD')
                    material_editors.select(context,mat)
                elif rightclick:
                    self.popup=True
                    if mat.session_uid not in multiselect.ids(context.window):multiselect.update(context.window,[mat])
                    material_editors.select(context,mat)
                    bpy.ops.wm.call_menu(name='MS_MT_actions')
                elif double:material_editors.open_nodes(context,mat)
                else:
                    multiselect.update(context.window,[mat])
                    material_editors.select(context,mat)
            return {'RUNNING_MODAL'}
        return {'PASS_THROUGH'}

def start(window):
    if window.as_pointer() not in _running:
        with bpy.context.temp_override(window=window):bpy.ops.ms.material_events('INVOKE_DEFAULT')

def stop():
    global _generation
    _generation+=1;_running.clear()
classes=[MS_OT_material_events]
