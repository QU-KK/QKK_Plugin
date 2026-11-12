"""Drag previews and high-priority viewport hover feedback."""
import bpy,gpu,time
from gpu_extras.batch import batch_for_shader
_handles=[]
_window=None
_area=None
_batch=None
_key=None
_status_workspace=None
_status_text=None
_world_segments=[]

def clear():
    clear_status()
    global _window,_area,_batch,_key,_world_segments
    from . import silhouette
    silhouette.reset()
    previous=_window
    _window=None;_area=None;_batch=None;_key=None;_world_segments=[]
    if previous:
        manager=getattr(bpy.context,'window_manager',None)
        if manager:
            for window in manager.windows:
                if window.as_pointer()==previous:
                    for area in window.screen.areas:
                        if area.type in {'VIEW_3D','OUTLINER'}:area.tag_redraw()

def clear_status():
    global _status_workspace,_status_text
    if _status_workspace is not None:
        try:_status_workspace.status_text_set(None)
        except ReferenceError:pass
    _status_workspace=None;_status_text=None

def status(context,area):
    global _status_workspace,_status_text
    from .catalog import label
    if area and area.type=='VIEW_3D':
        if context.mode=='EDIT_MESH':
            text=label('松开：赋予落点面；落点已选中时赋予整组选中面  |  Esc / 右键：取消','Release: assign hovered face, or selected faces when hovered face is selected  |  Esc / RMB: cancel')
        else:
            text=label('松开：赋予对象  |  Shift：赋予落点面  |  Esc / 右键：取消','Release: assign object  |  Shift: assign hovered face  |  Esc / RMB: cancel')
    elif area and area.type=='OUTLINER':
        text=label('松开：赋予鼠标下的对象  |  Esc / 右键：取消','Release: assign object under pointer  |  Esc / RMB: cancel')
    else:
        text=label('拖到材质：调整顺序  |  拖到文件夹标签：移动材质  |  拖到全部：移出文件夹  |  Esc / 右键：取消','Drop on material: reorder  |  Folder tab: move  |  All: return to root  |  Esc / RMB: cancel')
    if _status_workspace!=context.workspace:
        clear_status()
        _status_workspace=context.workspace
    if _status_text!=text:
        _status_workspace.status_text_set(text)
        _status_text=text

def bounding_segments(obj,face_index=None):
    from mathutils import Vector
    if face_index is None:
        corners=[Vector(co) for co in obj.bound_box]
        pairs=[(i,j) for i in range(8) for j in range(i+1,8) if sum(a!=b for a,b in zip(obj.bound_box[i],obj.bound_box[j]))==1]
        return [(corners[i],corners[j]) for i,j in pairs]
    if obj.mode=='EDIT':
        import bmesh
        mesh=bmesh.from_edit_mesh(obj.data);mesh.faces.ensure_lookup_table()
        if not 0<=face_index<len(mesh.faces):return []
        face=mesh.faces[face_index]
        vertices=[v.co.copy() for v in face.verts]
        normal=face.normal.copy()
    else:
        if not 0<=face_index<len(obj.data.polygons):return []
        face=obj.data.polygons[face_index]
        vertices=[obj.data.vertices[i].co.copy() for i in face.vertices]
        normal=face.normal.copy()
    if len(vertices)<3 or normal.length<1e-8:return []
    origin=vertices[0]
    tangent=next((v-origin for v in vertices[1:] if (v-origin).length>1e-8),None)
    if tangent is None:return []
    tangent.normalize()
    side=normal.cross(tangent).normalized()
    coordinates=[((v-origin).dot(tangent),(v-origin).dot(side)) for v in vertices]
    left=min(x for x,y in coordinates);right=max(x for x,y in coordinates)
    bottom=min(y for x,y in coordinates);top=max(y for x,y in coordinates)
    corners=[origin+tangent*x+side*y for x,y in [(left,bottom),(right,bottom),(right,top),(left,top)]]
    return [(corners[i],corners[(i+1)%4]) for i in range(4)]

def update(context,event):
    global _window,_area,_batch,_key,_world_segments
    from . import grid
    drag=grid.drag
    if not drag or time.monotonic()-drag[1]<.35:
        clear();return
    _window=context.window.as_pointer()
    area=next((a for a in context.screen.areas if a.x<=event.mouse_x<a.x+a.width and a.y<=event.mouse_y<a.y+a.height and a.type in {'VIEW_3D','OUTLINER'}),None)
    if area is None:
        clear()
        status(context,None)
        return
    status(context,area)
    _area=area.as_pointer()
    if area.type=='VIEW_3D' and event.type in {'MOUSEMOVE','LEFT_SHIFT','RIGHT_SHIFT'}:
        region=next((r for r in area.regions if r.type=='WINDOW'),None)
        if region is None:return
        from bpy_extras.view3d_utils import location_3d_to_region_2d
        from .material_drop import pick,face_indices,face_segments
        with context.temp_override(area=area,region=region):
            view=area.spaces.active.region_3d
            result=pick(context,event.mouse_x-region.x,event.mouse_y-region.y,getattr(event,'shift',False))
            obj,index,matrix=result if result else (None,None,None)
            key=(area.as_pointer(),obj.as_pointer(),face_indices(obj,index),tuple(tuple(row) for row in matrix),tuple(tuple(row) for row in view.perspective_matrix),region.width,region.height) if obj else None
            if key!=_key:
                _key=key;_batch=None;_world_segments=[]
                from . import silhouette
                silhouette.reset()
                if obj and index is None:
                    silhouette.prepare(obj,matrix,context)
                elif obj:
                    points=[]
                    _world_segments=[(matrix@start,matrix@end) for start,end in face_segments(obj,index)]
                    for start,end in face_segments(obj,index):
                        a=location_3d_to_region_2d(region,view,matrix@start)
                        b=location_3d_to_region_2d(region,view,matrix@end)
                        if a is not None and b is not None:points.extend((a,b))
                    if not points and obj.mode=='EDIT':silhouette.prepare(obj,matrix,context)
                    if points:
                        shader=gpu.shader.from_builtin('UNIFORM_COLOR')
                        _batch=batch_for_shader(shader,'LINES',{'pos':points})
    for target in context.screen.areas:
        if target.type in {'VIEW_3D','OUTLINER','PROPERTIES'}:target.tag_redraw()

def draw():
    from . import grid
    context=bpy.context
    drag=grid.drag
    if not drag or time.monotonic()-drag[1]<.35 or not context.window:return
    if context.window.as_pointer()!=_window or context.area.as_pointer()!=_area:return
    region=context.region
    x,y=drag[2]-region.x,drag[3]-region.y
    if not(0<=x<region.width and 0<=y<region.height):return
    blend=gpu.state.blend_get()
    depth=gpu.state.depth_test_get()
    width=gpu.state.line_width_get()
    try:
        gpu.state.blend_set('ALPHA')
        gpu.state.depth_test_set('NONE')
        if context.area.type=='VIEW_3D':
            from . import silhouette
            silhouette.draw(context)
        if _batch is not None and context.area.type=='VIEW_3D':
            # Pixel overlay is drawn after native selection highlighting.
            gpu.state.line_width_set(3)
            shader=gpu.shader.from_builtin('UNIFORM_COLOR')
            shader.bind();shader.uniform_float('color',(.05,1,.8,1))
            from bpy_extras.view3d_utils import location_3d_to_region_2d
            points=[]
            for start,end in _world_segments:
                a=location_3d_to_region_2d(region,context.space_data.region_3d,start)
                b=location_3d_to_region_2d(region,context.space_data.region_3d,end)
                if a is not None and b is not None:points.extend((a,b))
            if points:batch_for_shader(shader,'LINES',{'pos':points}).draw(shader)
        mat=bpy.data.materials.get(drag[0])
        grid.quad(x+14,y-29,27,27,(.08,.08,.08,.665))
        if mat:grid.thumbnail(mat,x+15.5,y-27.5,24,opacity=.7)
        grid.border(x+14,y-29,27,27,(.05,1,.8,.7))
    finally:
        gpu.state.line_width_set(width)
        gpu.state.depth_test_set(depth)
        gpu.state.blend_set(blend)

def start():
    if bpy.app.background or _handles:return
    for space in (bpy.types.SpaceView3D,bpy.types.SpaceOutliner):
        _handles.append((space,space.draw_handler_add(draw,(),'WINDOW','POST_PIXEL')))

def stop():
    for space,handle in _handles:
        try:space.draw_handler_remove(handle,'WINDOW')
        except (ValueError,ReferenceError):pass
    _handles.clear()
    clear()
