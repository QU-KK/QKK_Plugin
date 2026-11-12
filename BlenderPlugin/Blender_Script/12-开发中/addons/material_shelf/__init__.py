



import bpy
from bpy.app.handlers import persistent
from . import drag_feedback,material_drop,protection,asset_export,cleanup,folders,translations,features,materials,material_dock,material_events,material_editors,material_previews,selection
classes=material_previews.classes+material_drop.classes+protection.classes+asset_export.classes+cleanup.classes+folders.classes+features.classes+materials.classes+material_dock.classes+material_events.classes
from . import history
# These actions can be called inside the long-lived grid modal or nested in a
# batch. Use one explicit checkpoint at the outer boundary in either case.
for cls in classes:
    if getattr(cls,'bl_idname','') in {'ms.drop_material','ms.manage','ms.folder','ms.delete_selection','ms.reorder','ms.material_new','ms.material_assign','ms.protect','ms.cleanup'}:
        cls.execute=history.undo_step(cls.execute)
        cls.bl_options=set(cls.bl_options)-{'UNDO','UNDO_GROUPED'}
_registered=[]

def header(self,context):
    self.layout.operator('ms.materials',text='',icon='MATERIAL')

class MS_PT_launcher(bpy.types.Panel):
    bl_label='Material Shelf'
    bl_idname='MS_PT_launcher'
    bl_space_type='VIEW_3D'
    bl_region_type='UI'
    bl_category='Material Shelf'
    def draw(self,context):
        self.layout.operator('ms.materials',text='Material Shelf',icon='MATERIAL')

def tick():
    latest=max((m.get('ms_created',0) for m in bpy.data.materials),default=0)
    for mat in sorted(bpy.data.materials,key=lambda m:m.session_uid):
        if not mat.library and 'ms_created' not in mat:
            latest+=1
            mat['ms_created']=latest
            mat['ms_order']=max((m.get('ms_order',m.get('ms_created',0)) for m in bpy.data.materials),default=0)+1
    protection.sync(bpy.context.scene)
    selection.focus()
    for window in bpy.context.window_manager.windows:
        if material_dock.is_open(window):material_events.start(window)
    return .5

@persistent
def load_pre(_):
    drag_feedback.clear()
    history.reset()
    material_events.stop()
    material_previews.stop()
    material_editors.stop()
    material_dock._areas.clear()
    selection._last.clear()
    from . import multiselect
    multiselect.clear()

@persistent
def load_post(_):
    material_previews.request()

@persistent
def undo_post(_):
    history._last_mode=bpy.context.mode
    drag_feedback.clear()
    material_previews.stop()
    from . import grid,multiselect
    grid.clear()
    multiselect.clear()
    material_previews.request()

def register():
    history.reset()
    try:
        bpy.app.translations.register(__name__,{'zh_HANS':translations.ZH,'zh_CN':translations.ZH})
        for cls in classes+[MS_PT_launcher]:
            bpy.utils.register_class(cls)
            _registered.append(cls)
        bpy.types.Scene.ms_folders=bpy.props.PointerProperty(type=folders.MSFolders)
        bpy.types.Scene.ms_settings=bpy.props.PointerProperty(type=features.MSSettings)
        bpy.types.WindowManager.ms_material=bpy.props.PointerProperty(type=bpy.types.Material)
        bpy.types.VIEW3D_HT_header.append(header)
        material_dock.install()
        drag_feedback.start()
        bpy.app.handlers.save_pre.append(protection.save_pre)
        bpy.app.handlers.depsgraph_update_post.append(material_previews.deps_changed)
        bpy.app.handlers.undo_post.append(undo_post)
        bpy.app.handlers.redo_post.append(undo_post)
        bpy.app.handlers.load_pre.append(load_pre)
        bpy.app.handlers.load_post.append(load_post)
        if not bpy.app.background:bpy.app.timers.register(tick,first_interval=.5,persistent=True)
    except Exception:
        unregister()
        raise

def unregister():
    drag_feedback.stop()
    if bpy.app.timers.is_registered(tick):bpy.app.timers.unregister(tick)
    for handlers,fn in ((bpy.app.handlers.save_pre,protection.save_pre),(bpy.app.handlers.depsgraph_update_post,material_previews.deps_changed),(bpy.app.handlers.undo_post,undo_post),(bpy.app.handlers.redo_post,undo_post),(bpy.app.handlers.load_pre,load_pre),(bpy.app.handlers.load_post,load_post)):
        if fn in handlers:handlers.remove(fn)
    material_events.stop()
    material_previews.stop()
    material_editors.stop()
    material_dock.stop()
    bpy.app.translations.unregister(__name__)
    selection._last.clear()
    from . import multiselect
    multiselect.clear()
    bpy.types.VIEW3D_HT_header.remove(header)
    if hasattr(bpy.types.WindowManager,'ms_material'):del bpy.types.WindowManager.ms_material
    if hasattr(bpy.types.Scene,'ms_folders'):del bpy.types.Scene.ms_folders
    if hasattr(bpy.types.Scene,'ms_settings'):del bpy.types.Scene.ms_settings
    for cls in reversed(_registered):bpy.utils.unregister_class(cls)
    _registered.clear()
