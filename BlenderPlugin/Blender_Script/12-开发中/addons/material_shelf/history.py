"""Explicit undo boundaries for actions launched by the persistent grid modal."""
import bpy
from functools import wraps
_depth=0
_seeded=False
_last_mode=None

def reset():
    global _seeded,_last_mode
    _seeded=False
    _last_mode=None

def step_name(operator):
    from .catalog import label
    action=getattr(operator,'action','')
    names={
        'DELETE':('删除材质或文件夹','Delete materials or folders'),
        'MOVE':('移动材质到文件夹','Move materials to folder'),
        'ASSIGN':('赋予材质','Assign material'),
        'NEW':('新建文件夹','New folder'),
        'COPY':('复制文件夹','Duplicate folder'),
        'DUPLICATE':('创建材质副本','Duplicate materials'),
        'PASTE':('粘贴材质','Paste materials'),
        'UNLINK':('解除材质分配','Unlink materials'),
        'REPLACE':('替换材质','Replace materials'),
    }
    ids={'ms.drop_material':('拖放赋予材质','Drop material assignment'),
         'ms.reorder':('调整材质顺序','Reorder materials'),
         'ms.delete_selection':('删除所选材质与文件夹','Delete selected materials and folders')}
    text=ids.get(getattr(operator,'bl_idname',''),names.get(action))
    return label(*text) if text else getattr(operator,'bl_label','Material Shelf')

def undo_step(execute):
    @wraps(execute)
    def wrapped(self,context):
        global _depth,_seeded,_last_mode
        action=getattr(self,'action','')
        navigation=getattr(self,'bl_idname','')=='ms.folder' and action in {'OPEN','CLOSE'}
        clipboard=getattr(self,'bl_idname','')=='ms.manage' and action=='COPY'
        record=not navigation and not clipboard and not bpy.app.background and context.preferences.edit.use_global_undo
        outer=_depth==0 and record
        if outer and (not _seeded or _last_mode!=context.mode):
            bpy.ops.ed.undo_push(message='Before Material Shelf operation')
            _seeded=True
            _last_mode=context.mode
        _depth+=1
        try:
            result=execute(self,context)
            if outer and 'FINISHED' in result:
                bpy.ops.ed.undo_push(message=step_name(self))
                _last_mode=context.mode
            return result
        finally:_depth-=1
    return wrapped
