import bpy,bmesh
from bpy.props import StringProperty,IntProperty,BoolProperty

def face_indices(obj,face_index):
    if face_index is None:return ()
    if obj.mode=='EDIT':
        mesh=bmesh.from_edit_mesh(obj.data);mesh.faces.ensure_lookup_table();mesh.faces.index_update()
        if not 0<=face_index<len(mesh.faces):return ()
        hovered=mesh.faces[face_index]
        if hovered.select:return tuple(f.index for f in mesh.faces if f.select and not f.hide)
    return (face_index,)

def face_segments(obj,face_index):
    indices=face_indices(obj,face_index)
    if obj.mode=='EDIT':
        mesh=bmesh.from_edit_mesh(obj.data);mesh.faces.ensure_lookup_table();mesh.verts.index_update()
        faces=[mesh.faces[i] for i in indices]
        polygons=[[(v.index,v.co.copy()) for v in face.verts] for face in faces]
    else:
        polygons=[[(i,obj.data.vertices[i].co.copy()) for i in obj.data.polygons[index].vertices] for index in indices]
    edges={}
    counts={}
    for polygon in polygons:
        for (i,start),(j,end) in zip(polygon,polygon[1:]+polygon[:1]):
            key=tuple(sorted((i,j)))
            edges[key]=(start,end)
            counts[key]=counts.get(key,0)+1
    return [edges[key] for key,count in counts.items() if count==1]

def assign(obj,material,face_index=None):
    if not obj.is_editable or not obj.data or not hasattr(obj.data,'materials') or not obj.data.is_editable:return False
    if obj.type=='MESH' and face_index is not None:
        count=len(bmesh.from_edit_mesh(obj.data).faces) if obj.mode=='EDIT' else len(obj.data.polygons)
        if not 0<=face_index<count:return False
    changed=material.name not in obj.data.materials
    if changed:obj.data.materials.append(material)
    index=list(obj.data.materials).index(material)
    if obj.type=='MESH' and obj.mode=='EDIT':
        mesh=bmesh.from_edit_mesh(obj.data);mesh.faces.ensure_lookup_table()
        if face_index is None or not 0<=face_index<len(mesh.faces):return False
        for target in face_indices(obj,face_index):
            changed=changed or mesh.faces[target].material_index!=index
            mesh.faces[target].material_index=index
        bmesh.update_edit_mesh(obj.data)
    elif obj.type=='MESH':
        if face_index is None:
            for face in obj.data.polygons:
                changed=changed or face.material_index!=index
                face.material_index=index
        elif 0<=face_index<len(obj.data.polygons):
            changed=changed or obj.data.polygons[face_index].material_index!=index
            obj.data.polygons[face_index].material_index=index
        else:return False
    else:
        changed=changed or obj.active_material_index!=index
        obj.active_material_index=index
    return changed

def pick(context,x,y,face=False):
    from bpy_extras.view3d_utils import region_2d_to_origin_3d,region_2d_to_vector_3d
    from mathutils.bvhtree import BVHTree
    region=context.region;view=context.space_data.region_3d
    origin=region_2d_to_origin_3d(region,view,(x,y))
    direction=region_2d_to_vector_3d(region,view,(x,y))
    edits=[obj for obj in context.view_layer.objects if obj.type=='MESH' and obj.mode=='EDIT']
    best=None
    for obj in edits:
        mesh=bmesh.from_edit_mesh(obj.data);mesh.faces.ensure_lookup_table();mesh.faces.index_update()
        inverse=obj.matrix_world.inverted()
        hit,normal,index,distance=BVHTree.FromBMesh(mesh).ray_cast(inverse@origin,(inverse.to_3x3()@direction).normalized())
        if hit is not None:
            distance=(obj.matrix_world@hit-origin).length
            if best is None or distance<best[0]:best=(distance,obj,index)
    if best:
        _,obj,index=best
        matrix=obj.matrix_world
    else:
        hit,location,normal,index,obj,matrix=context.scene.ray_cast(context.evaluated_depsgraph_get(),origin,direction)
        if not hit:return None
        obj=obj.original
        if face and obj.modifiers:return None
        if not face:index=None
    return obj,index,matrix

def outliner_drop(material):
    try:return bpy.ops.object.drop_named_material('INVOKE_DEFAULT',name=material.name,session_uid=material.session_uid)
    except (RuntimeError,TypeError):return {'CANCELLED'}

class MS_OT_drop_material(bpy.types.Operator):
    bl_idname='ms.drop_material'
    bl_label='Assign Dropped Material'
    bl_options={'UNDO'}
    material:StringProperty()
    x:IntProperty()
    y:IntProperty()
    face:BoolProperty()
    def execute(self,context):
        from .catalog import label
        mat=bpy.data.materials.get(self.material)
        if mat is None:return {'CANCELLED'}
        if context.area.type=='OUTLINER':
            # Blender resolves the object under the current mouse position.
            result=outliner_drop(mat)
            if 'CANCELLED' in result:
                def notice(self,context):
                    self.layout.label(text=label('请拖拽到正确对象','Please drag onto a valid object'))
                context.window_manager.popup_menu(notice,title=label('无法赋予材质','Cannot assign material'),icon='INFO')
            return result
        if context.area.type!='VIEW_3D':return {'CANCELLED'}
        result=pick(context,self.x,self.y,self.face)
        if result is None:return {'CANCELLED'}
        obj,index,matrix=result
        if not assign(obj,mat,index):return {'CANCELLED'}
        from .material_previews import request
        request()
        return {'FINISHED'}

classes=[MS_OT_drop_material]
