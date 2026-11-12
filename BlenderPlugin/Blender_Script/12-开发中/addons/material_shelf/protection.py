import bpy
from bpy.app.handlers import persistent
from .catalog import label

def setting_changed(self,context):
    for mat in bpy.data.materials:
        if mat.library:continue
        mat.pop('ms_protect_override',None)
    sync(context.scene)

def usage_counts():
    # Blender users includes add-on PointerProperties. Those references keep
    # materials alive but do not represent material use in the scene.
    counts={mat:max(0,mat.users-int(mat.use_fake_user)) for mat in bpy.data.materials}
    for manager in bpy.data.window_managers:
        mat=getattr(manager,'ms_material',None)
        if mat in counts:counts[mat]-=1
    for scene in bpy.data.scenes:
        state=getattr(scene,'ms_folders',None)
        if state:
            for link in state.links:
                if link.material in counts:counts[link.material]-=1
    return {mat:max(0,count) for mat,count in counts.items()}

def sync(scene):
    counts=usage_counts()
    enabled=scene.ms_settings.auto_protect
    for mat,count in counts.items():
        if mat.library:continue
        if count:
            if mat.use_fake_user:mat.use_fake_user=False
            mat.pop('ms_protect_override',None)
        elif not mat.get('ms_protect_override'):
            if mat.use_fake_user!=enabled:mat.use_fake_user=enabled

@persistent
def save_pre(_):
    if bpy.context.scene and hasattr(bpy.context.scene,'ms_settings'):sync(bpy.context.scene)

class MS_OT_protect(bpy.types.Operator):
    bl_idname='ms.protect'
    bl_label='Protect Material'
    bl_options={'UNDO'}
    material:bpy.props.StringProperty()
    def execute(self,context):
        mat=bpy.data.materials.get(self.material)
        if mat is None or mat.library:return {'CANCELLED'}
        if usage_counts().get(mat,0)>0:return {'CANCELLED'}
        mat.use_fake_user=not mat.use_fake_user
        mat['ms_protect_override']=True
        for area in context.screen.areas:area.tag_redraw()
        return {'FINISHED'}
classes=[MS_OT_protect]
