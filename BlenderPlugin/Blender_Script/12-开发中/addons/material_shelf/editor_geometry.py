"""Remember the shader editor's native window geometry for this project session."""
import os
import sys
import bpy
_saved=None
_handle=None
_api=None

def api():
    global _api
    if sys.platform!='win32':return None
    if _api is None:
        import ctypes
        from ctypes import wintypes
        user=ctypes.WinDLL('user32',use_last_error=True)
        callback=ctypes.WINFUNCTYPE(wintypes.BOOL,wintypes.HWND,wintypes.LPARAM)
        user.EnumWindows.argtypes=[callback,wintypes.LPARAM]
        user.IsWindow.argtypes=[wintypes.HWND]
        user.IsWindowVisible.argtypes=[wintypes.HWND]
        user.IsIconic.argtypes=[wintypes.HWND]
        user.IsZoomed.argtypes=[wintypes.HWND]
        user.ShowWindow.argtypes=[wintypes.HWND,ctypes.c_int]
        user.SetForegroundWindow.argtypes=[wintypes.HWND]
        user.BringWindowToTop.argtypes=[wintypes.HWND]
        user.GetWindowThreadProcessId.argtypes=[wintypes.HWND,ctypes.POINTER(wintypes.DWORD)]
        user.GetWindowRect.argtypes=[wintypes.HWND,ctypes.POINTER(wintypes.RECT)]
        user.SetWindowPos.argtypes=[wintypes.HWND,wintypes.HWND,ctypes.c_int,ctypes.c_int,ctypes.c_int,ctypes.c_int,wintypes.UINT]
        _api=(user,ctypes,wintypes,callback)
    return _api

def windows():
    service=api()
    if service is None:return set()
    user,ctypes,types,callback=service
    result=set()
    def visit(handle,_):
        pid=types.DWORD()
        user.GetWindowThreadProcessId(handle,ctypes.byref(pid))
        if pid.value==os.getpid() and user.IsWindowVisible(handle):result.add(handle)
        return True
    user.EnumWindows(callback(visit),0)
    return result

def rect(handle):
    user,ctypes,types,_=api()
    value=types.RECT()
    if not user.GetWindowRect(handle,ctypes.byref(value)):return None
    return (value.left,value.top,value.right-value.left,value.bottom-value.top)

def remember():
    global _saved,_handle
    if not _handle:return None
    user,_,_,_=api()
    if not user.IsWindow(_handle):
        _handle=None
        return None
    if not user.IsIconic(_handle) and not user.IsZoomed(_handle):
        value=rect(_handle)
        if value and value[2]>0 and value[3]>0:_saved=value
    return .1

def restore(previous, parent_size=None):
    global _handle,_saved
    service=api()
    if service is None:return
    created=windows()-previous
    # Only touch the single native window created by area_dupli.
    if len(created)!=1:return
    _handle=created.pop()
    value=rect(_handle)
    if value is None:return
    if _saved is None:
        x,y,w,h=value
        parent_width,parent_height=parent_size or (w,h)
        width=max(120,parent_width//3)
        height=max(100,parent_height//3)
        _saved=(x+(w-width)//2,y+(h-height)//2,width,height)
    user,_,_,_=service
    user.SetWindowPos(_handle,None,*_saved,0x0014)
    if not bpy.app.timers.is_registered(remember):bpy.app.timers.register(remember,first_interval=.1)

def activate():
    service=api()
    if service is None or not _handle:return False
    user,ctypes,types,_=service
    if not user.IsWindow(_handle):return False
    process=types.DWORD()
    user.GetWindowThreadProcessId(_handle,ctypes.byref(process))
    if process.value!=os.getpid():return False
    if user.IsIconic(_handle):user.ShowWindow(_handle,9)
    elif not user.IsWindowVisible(_handle):user.ShowWindow(_handle,5)
    user.BringWindowToTop(_handle)
    user.SetForegroundWindow(_handle)
    return True

def stop():
    global _saved,_handle
    if bpy.app.timers.is_registered(remember):bpy.app.timers.unregister(remember)
    _saved=None
    _handle=None
