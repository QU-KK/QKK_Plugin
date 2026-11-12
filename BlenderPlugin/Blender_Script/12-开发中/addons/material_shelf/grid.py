"""One geometry source for thumbnail rendering, picking and drop feedback."""
import bpy, blf, gpu, time
from gpu_extras.batch import batch_for_shader
_cache={}
_icons={}
_transparent_shader=None
_checked={}
_sources={}
_missing=set()
drag=None

def clear():
    global drag
    _sources.clear();_missing.clear()
    _icons.clear()
    _cache.clear()
    _checked.clear()
    drag=None

def invalidate_resolution():
    _cache.clear()
    _checked.clear()

def source_pixels(mat):
    mat.preview_ensure()
    for size,pixels in [(mat.preview.image_size,mat.preview.image_pixels_float),(mat.preview.icon_size,mat.preview.icon_pixels_float)]:
        w,h=size
        if not w or not h:continue
        data=list(pixels)
        if len(data)==w*h*4 and any(value>.001 for i,value in enumerate(data) if i%4!=3):
            _sources[mat.as_pointer()]=(w,h,data)
            _missing.discard(mat.as_pointer())
            return w,h,data
    key=mat.as_pointer()
    if key in _sources:return _sources[key]
    if key not in _missing:
        from . import material_previews
        _missing.add(key)
        material_previews._states.pop(key,None)
        material_previews._dirty.add(key)
        material_previews._watch[key]=time.monotonic()+30
        material_previews.request()
    return 0,0,[]

def quad(x,y,w,h,color):
    shader=gpu.shader.from_builtin('UNIFORM_COLOR')
    shader.bind()
    shader.uniform_float('color',color)
    batch_for_shader(shader,'TRIS',{'pos':[(x,y),(x+w,y),(x+w,y+h),(x,y),(x+w,y+h),(x,y+h)]}).draw(shader)

def border(x,y,w,h,color):
    for a,b,c,d in [(x,y,w,2),(x,y+h-2,w,2),(x,y,2,h),(x+w-2,y,2,h)]:
        quad(a,b,c,d,color)

def dashed_border(x,y,w,h,color):
    scale=bpy.context.preferences.system.ui_scale
    dash=max(4,round(7*scale))
    gap=max(3,round(4*scale))
    thickness=max(1,round(2*scale))
    for start in range(0,max(0,int(w)),dash+gap):
        length=min(dash,w-start)
        quad(x+start,y,length,thickness,color)
        quad(x+start,y+h-thickness,length,thickness,color)
    for start in range(0,max(0,int(h)),dash+gap):
        length=min(dash,h-start)
        quad(x,y+start,thickness,length,color)
        quad(x+w-thickness,y+start,thickness,length,color)

def protection_icon(protected,x,y,size):
    from pathlib import Path
    name='fake_user_on' if protected else 'fake_user_off'
    if name not in _icons:
        data=(Path(__file__).parent/'assets'/(name+'.rgba')).read_bytes()
        pixels=[v/255 for v in data]
        _icons[name]=gpu.types.GPUTexture((64,64),format='RGBA32F',data=gpu.types.Buffer('FLOAT',len(pixels),pixels))
    gpu.state.blend_set('ALPHA')
    shader=gpu.shader.from_builtin('IMAGE')
    shader.bind();shader.uniform_sampler('image',_icons[name])
    batch_for_shader(shader,'TRI_FAN',{'pos':[(x,y),(x+size,y),(x+size,y+size),(x,y+size)],'texCoord':[(0,0),(1,0),(1,1),(0,1)]}).draw(shader)

def transparent_shader():
    global _transparent_shader
    if _transparent_shader is None:
        interface=gpu.types.GPUStageInterfaceInfo('ms_preview_uv')
        interface.smooth('VEC2','uv')
        info=gpu.types.GPUShaderCreateInfo()
        info.vertex_in(0,'VEC2','pos');info.vertex_in(1,'VEC2','texCoord')
        info.vertex_out(interface);info.fragment_out(0,'VEC4','fragColor')
        info.sampler(0,'FLOAT_2D','image')
        info.push_constant('MAT4','mvp')
        info.push_constant('FLOAT','opacity')
        info.vertex_source('void main(){uv=texCoord;gl_Position=mvp*vec4(pos,0.0,1.0);}')
        info.fragment_source('void main(){vec4 c=texture(image,uv);fragColor=vec4(c.rgb,c.a*opacity);}')
        _transparent_shader=gpu.shader.create_from_info(info)
    return _transparent_shader

def thumbnail(mat,x,y,size,opacity=1):
    from .material_previews import _watch
    key=mat.as_pointer()
    now=time.monotonic()
    refresh=key not in _cache or (_watch.get(key,0)>now and now-_checked.get(key,0)>.5)
    if refresh:
        _checked[key]=now
        resolution=int(bpy.context.scene.ms_settings.preview_resolution)
        w,h,pixels=source_pixels(mat)
        if w and h and max(w,h)>resolution:
            target_w=max(1,round(w*resolution/max(w,h)))
            target_h=max(1,round(h*resolution/max(w,h)))
            reduced=[]
            for row in range(target_h):
                for column in range(target_w):
                    index=((row*h//target_h)*w+column*w//target_w)*4
                    reduced.extend(pixels[index:index+4])
            w,h,pixels=target_w,target_h,reduced
        if not w or not h:
            if mat.as_pointer() not in _cache:return
            state=_cache[mat.as_pointer()][0]
        else:state=(w,h,hash(tuple(pixels)))
        if mat.as_pointer() in _cache and not any(value>.001 for i,value in enumerate(pixels) if i%4!=3):
            state=_cache[mat.as_pointer()][0]
        key=mat.as_pointer()
        if key not in _cache or _cache[key][0]!=state:
            texture=gpu.types.GPUTexture((w,h),format='RGBA32F',data=gpu.types.Buffer('FLOAT',len(pixels),pixels))
            _cache[key]=(state,texture)
    gpu.state.blend_set('ALPHA')
    shader=transparent_shader() if opacity<1 else gpu.shader.from_builtin('IMAGE')
    shader.bind()
    shader.uniform_sampler('image',_cache[key][1])
    if opacity<1:
        shader.uniform_float('mvp',gpu.matrix.get_projection_matrix()@gpu.matrix.get_model_view_matrix())
        shader.uniform_float('opacity',opacity)
    batch_for_shader(shader,'TRI_FAN',{'pos':[(x,y),(x+size,y),(x+size,y+size),(x,y+size)],'texCoord':[(0,0),(1,0),(1,1),(0,1)]}).draw(shader)

def draw():
    from .material_dock import is_dock,ordered_materials,highlighted
    from .material_events import rectangles,hit
    context=bpy.context
    if not context.window or not is_dock(context.area):return
    region=context.region
    mats=ordered_materials()
    live={m.as_pointer() for m in bpy.data.materials}
    for key in list(_cache):
        if key not in live:_cache.pop(key,None)
    active=context.window_manager.ms_material
    associated=highlighted(context.window)
    from .protection import usage_counts
    counts=usage_counts()
    from . import multiselect
    selected=multiselect.ids(context.window)
    gpu.state.blend_set('ALPHA')
    try:
        from .material_events import tab_rectangles,tab_hit
        from .catalog import label
        for uid,name,(left,top,width,height) in tab_rectangles(region):
            a,b=region.view2d.view_to_region(left,top,clip=False)
            c,d=region.view2d.view_to_region(left+width,top-height,clip=False)
            selected_tab=context.scene.ms_folders.current==uid
            quad(a,d,c-a-2,b-d,(.18,.36,.63,1) if selected_tab else (.23,.23,.23,1))
            blf.size(0,12);blf.color(0,1,1,1,1);blf.position(0,a+5,d+6,0)
            blf.draw(0,name[:max(1,int((c-a-28)/8))] if uid else label('全部','All'))
            if uid:
                blf.position(0,c-16,d+6,0);blf.draw(0,'×')
        from .folders import visible,associated_folders
        linked_folders=associated_folders(context.scene,associated)
        from .material_events import all_rectangles
        folders=visible(context)
        for folder,(left,top,width,height) in zip(folders,all_rectangles(context.area,region,len(folders)+len(mats))):
            x,y=region.view2d.view_to_region(left,top,clip=False)
            right,bottom=region.view2d.view_to_region(left+width,top-height,clip=False)
            size=max(12,min(right-x-20,y-bottom-34))
            fx=x+(right-x-size)/2
            fy=bottom+28
            # Blender file_folder.svg geometry, normalized from its 16x15 view.
            color=(.8,.8,.8,1)
            quad(fx+size/16,fy+size/15,size*14/16,size*8/15,color)
            quad(fx+size/16,fy+size*10/15,size*14/16,size*2/15,color)
            quad(fx+size/16,fy+size*12/15,size*5/16,size*2/15,color)
            if folder.uid in linked_folders:
                dashed_border(x+2,bottom+25,right-x-4,y-bottom-27,(.02,.65,1,1))
            if folder.uid in multiselect.folder_ids(context.window):
                quad(x+2,bottom+3,right-x-4,20,(.18,.36,.63,1))
            if drag and time.monotonic()-drag[1]>=.35:
                mx,my=drag[2]-region.x,drag[3]-region.y
                if x<=mx<right and bottom<=my<y:border(x+2,bottom+2,right-x-4,y-bottom-4,(.1,.65,1,1))
            blf.size(0,12);blf.color(0,1,1,1,1);blf.position(0,x+6,bottom+8,0);blf.draw(0,folder.name[:18])
        for mat,(left,top,width,height) in zip(mats,rectangles(context.area,region,len(mats))):
            x,y=region.view2d.view_to_region(left,top,clip=False)
            right,bottom=region.view2d.view_to_region(left+width,top-height,clip=False)
            if y<0 or bottom>region.height:continue
            cell=right-x
            size=min(cell-8,y-bottom-30)
            thumbnail(mat,x+(cell-size)/2,bottom+26,size)
            from .material_previews import _errors
            if mat.as_pointer() not in _sources or mat.as_pointer() in _errors:
                from .material_previews import preview_status
                blf.size(0,11);blf.color(0,.85,.85,.85,1)
                blf.position(0,x+5,bottom+35,0);blf.draw(0,preview_status(mat))
            # Read Blender's own usage and fake-user flags directly.
            bx=right-28
            count=counts.get(mat,0)
            protection_icon(mat.use_fake_user and count==0,bx,y-20,18)
            blf.size(0,11);blf.color(0,1,.25,.25,1) if count==0 else blf.color(0,1,1,1,1)
            blf.position(0,bx+18,y-17,0);blf.draw(0,str(count))
            quad(x+2,bottom+3,cell-4,20,(.18,.36,.63,1) if mat.session_uid in selected else (.23,.23,.23,1))
            blf.size(0,12)
            blf.color(0,1,1,1,1)
            name=mat.name
            while name and blf.dimensions(0,name)[0]>cell-10:name=name[:-1]
            blf.position(0,x+6,bottom+8,0)
            blf.draw(0,name)
            if mat.name in associated:border(x+2,bottom+25,cell-4,y-bottom-27,(.02,.65,1,1))
        if multiselect.box and multiselect.box[0]==context.area.as_pointer():
            _,a,b,c,d=multiselect.box
            border(min(a,c),min(b,d),abs(c-a),abs(d-b),(1,1,1,1))
        if drag and time.monotonic()-drag[1]>=.35:
            source,_,mx,my=drag
            x,y=mx-region.x,my-region.y
            if 0<=x<region.width and 0<=y<region.height:
                mat=bpy.data.materials.get(source)
                quad(x+12,y-21,21,21,(.12,.12,.12,.63))
                if mat:thumbnail(mat,x+14,y-19,17,opacity=.7)
                border(x+12,y-21,21,21,(.02,.65,1,.7))
                target=hit(context.area,region,x,y,[m.name for m in mats])
                if target:
                    index=[m.name for m in mats].index(target)
                    left,top,_,height=rectangles(context.area,region,len(mats))[index]
                    a,b=region.view2d.view_to_region(left,top,clip=False)
                    _,c=region.view2d.view_to_region(left,top-height,clip=False)
                    quad(a,b-(b-c),3,b-c,(1,.65,.1,1))
    finally:
        gpu.state.blend_set('NONE')
