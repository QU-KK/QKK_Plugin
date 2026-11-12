"""GPU silhouette mask; only its screen-space boundary is composited."""
import bpy,gpu
from gpu_extras.batch import batch_for_shader
_surface=None
_matrix=None
_mask=None
_dirty=False
_edge=None

def reset():
    global _surface,_matrix,_mask,_dirty
    _surface=None;_matrix=None;_dirty=False
    if _mask is not None:
        _mask.free();_mask=None

def prepare(obj,matrix,context):
    global _surface,_matrix,_dirty
    reset()
    evaluated=obj.evaluated_get(context.evaluated_depsgraph_get())
    mesh=evaluated.to_mesh()
    try:
        mesh.calc_loop_triangles()
        shader=gpu.shader.from_builtin('UNIFORM_COLOR')
        _surface=batch_for_shader(shader,'TRIS',{'pos':[v.co[:] for v in mesh.vertices]},indices=[t.vertices[:] for t in mesh.loop_triangles])
        _matrix=matrix.copy()
        _dirty=True
    finally:evaluated.to_mesh_clear()

def edge_shader():
    global _edge
    if _edge is None:
        interface=gpu.types.GPUStageInterfaceInfo('ms_silhouette_uv')
        interface.smooth('VEC2','uv')
        info=gpu.types.GPUShaderCreateInfo()
        info.vertex_in(0,'VEC2','pos')
        info.vertex_in(1,'VEC2','texCoord')
        info.vertex_out(interface)
        info.sampler(0,'FLOAT_2D','maskTexture')
        info.push_constant('VEC2','pixel')
        info.fragment_out(0,'VEC4','fragColor')
        info.vertex_source('void main(){uv=texCoord;gl_Position=vec4(pos,0.0,1.0);}')
        info.fragment_source("""
void main(){
    float lo=texture(maskTexture,uv).r;
    float hi=lo;
    for(int x=-1;x<=1;x++){
        for(int y=-1;y<=1;y++){
            float value=texture(maskTexture,uv+vec2(x,y)*pixel*1.8).r;
            lo=min(lo,value);hi=max(hi,value);
        }
    }
    fragColor=vec4(0.05,1.0,0.8,hi-lo);
}
""")
        _edge=gpu.shader.create_from_info(info)
    return _edge

def draw(context):
    global _mask,_dirty
    if _surface is None:return
    region=context.region
    if _mask is None:
        _mask=gpu.types.GPUOffScreen(region.width,region.height)
        _dirty=True
    viewport=gpu.state.viewport_get()
    if _dirty:
        try:
            with _mask.bind():
                gpu.state.viewport_set(0,0,region.width,region.height)
                gpu.state.active_framebuffer_get().clear(color=(0,0,0,1),depth=1)
                gpu.state.blend_set('NONE')
                gpu.state.depth_test_set('LESS_EQUAL')
                gpu.state.depth_mask_set(True)
                with gpu.matrix.push_pop(),gpu.matrix.push_pop_projection():
                    gpu.matrix.load_matrix(context.space_data.region_3d.view_matrix@_matrix)
                    gpu.matrix.load_projection_matrix(context.space_data.region_3d.window_matrix)
                    shader=gpu.shader.from_builtin('UNIFORM_COLOR')
                    shader.bind();shader.uniform_float('color',(1,1,1,1))
                    _surface.draw(shader)
            _dirty=False
        finally:gpu.state.viewport_set(*viewport)
    gpu.state.depth_test_set('NONE')
    gpu.state.blend_set('ALPHA')
    shader=edge_shader()
    shader.bind()
    shader.uniform_sampler('maskTexture',_mask.texture_color)
    shader.uniform_float('pixel',(1/region.width,1/region.height))
    batch_for_shader(shader,'TRI_FAN',{'pos':[(-1,-1),(1,-1),(1,1),(-1,1)],'texCoord':[(0,0),(1,0),(1,1),(0,1)]}).draw(shader)
