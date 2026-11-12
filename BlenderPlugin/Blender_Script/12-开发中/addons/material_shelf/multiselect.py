"""Material selection, independent from object-associated outlines."""
_selected={}
_folders={}
box=None

def ids(window):
    import bpy
    selected=_selected.setdefault(window.as_pointer(),set())
    selected.intersection_update(m.session_uid for m in bpy.data.materials)
    return selected

def update(window,materials,mode='SET'):
    values={m.session_uid for m in materials}
    current=ids(window)
    if mode=='ADD':current.update(values)
    elif mode=='SUBTRACT':current.difference_update(values)
    else:current.clear();current.update(values)
    for area in window.screen.areas:area.tag_redraw()

def folder_ids(window):
    import bpy
    ids=_folders.setdefault(window.as_pointer(),set())
    ids.intersection_update(f.uid for f in window.scene.ms_folders.folders)
    return ids

def update_folders(window,folders,mode='SET'):
    values={f.uid for f in folders}
    ids=folder_ids(window)
    if mode=='ADD':ids.update(values)
    elif mode=='SUBTRACT':ids.difference_update(values)
    else:ids.clear();ids.update(values)
    window.scene.ms_folders.selected=next(iter(ids),'')
    for area in window.screen.areas:area.tag_redraw()

def clear():
    global box
    _selected.clear();_folders.clear()
    box=None
