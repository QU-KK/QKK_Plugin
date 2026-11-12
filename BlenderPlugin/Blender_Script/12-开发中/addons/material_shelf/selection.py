import bpy
_last={}
_associated={}
def focus():
    from .material_dock import is_dock
    for window in bpy.context.window_manager.windows:
        from .material_dock import highlighted
        associated=highlighted(window)
        if _associated.get(window.as_pointer())!=associated:
            _associated[window.as_pointer()]=associated
            for area in window.screen.areas:
                if is_dock(area):area.tag_redraw()
        obj=window.view_layer.objects.active
        token=(obj.as_pointer() if obj else 0,window.scene.as_pointer())
        if _last.get(window.as_pointer())==token:continue
        _last[window.as_pointer()]=token
        for area in window.screen.areas:
            if area.type=='PROPERTIES' and not is_dock(area):
                space=area.spaces.active
                if isinstance(space.pin_id,bpy.types.Material):
                    space.use_pin_id=False
                    space.pin_id=None
                    try:space.context='OBJECT' if obj else 'TOOL'
                    except TypeError:pass
