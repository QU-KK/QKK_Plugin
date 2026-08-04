import bpy
import ctypes

from .vlog import Log

# Handler type enum. Operator is 3
WM_HANDLER_TYPE_GIZMO = 1
WM_HANDLER_TYPE_UI = 2
WM_HANDLER_TYPE_OP = 3
WM_HANDLER_TYPE_DROPBOX = 4
WM_HANDLER_TYPE_KEYMAP = 5


# Generate listbase of appropriate type. None: generic
def listbase(type_=None):
    ptr = ctypes.POINTER(type_)
    fields = ("first", ptr), ("last", ptr)
    return type("ListBase", (ctypes.Structure,), {'_fields_': fields})


# Mini struct for Op handlers. *not* bContext!
class OpContext(ctypes.Structure):
    pass


class wmEventHandler(ctypes.Structure):  # Generic
    pass


class wmEventHandler_Op(ctypes.Structure):  # Operator
    pass


class wmWindow(ctypes.Structure):
    pass


class uiItem(ctypes.Structure):
    pass


class uiLayout(ctypes.Structure):
    pass


uiItem._fields_ = (
    ("next", ctypes.c_void_p),
    ("prev", ctypes.c_void_p),
    ("type", ctypes.c_int),  # Enum
    ("flag", ctypes.c_int),
)


uiLayout._fields_ = (
    ("item", uiItem),

    ("root", ctypes.c_void_p),
    ("context", ctypes.c_void_p),
    ("parent", ctypes.c_void_p),

    ("items", listbase(type_=None)),

    ("heading", ctypes.c_char * 128),

    ("child_items_layout", ctypes.c_void_p),

    ("x", ctypes.c_int),
    ("y", ctypes.c_int),
    ("w", ctypes.c_int),
    ("h", ctypes.c_int),

    ("scale", ctypes.c_float * 2),
    ("space", ctypes.c_short),
    ("align", ctypes.c_bool),
    ("active", ctypes.c_bool),
    ("active_default", ctypes.c_bool),
    ("activate_init", ctypes.c_bool),
    ("enabled", ctypes.c_bool),
    ("redalert", ctypes.c_bool),
    ("keepaspect", ctypes.c_bool),
    ("variable_size", ctypes.c_bool),
    ("alignment", ctypes.c_char),
    ("emboss", ctypes.c_int),
    ("units", ctypes.c_float * 2),
)


wmEventHandler._fields_ = (
    ("next", ctypes.POINTER(wmEventHandler)),
    ("prev", ctypes.POINTER(wmEventHandler)),
    ("type", ctypes.c_int),  # Enum
    ("flag", ctypes.c_char),
    ("poll", ctypes.c_void_p),
)


if bpy.app.version < (2, 93, 0):
    wmWindow._fields_ = (  # from DNA_windowmanager_types.h
        ("next", ctypes.POINTER(wmWindow)),
        ("prev", ctypes.POINTER(wmWindow)),
        ("ghostwin", ctypes.c_void_p),
        ("gpuctx", ctypes.c_void_p),
        ("parent", ctypes.POINTER(wmWindow)),
        ("scene", ctypes.c_void_p),
        ("new_scene", ctypes.c_void_p),
        ("view_layer_name", ctypes.c_char * 64),
        ("workspace_hook", ctypes.c_void_p),
        ("global_areas", listbase(type_=None) * 3),
        ("screen", ctypes.c_void_p),
        ("posx", ctypes.c_short),
        ("posy", ctypes.c_short),
        ("sizex", ctypes.c_short),
        ("sizey", ctypes.c_short),
        ("windowstate", ctypes.c_char),
        ("active", ctypes.c_char),
        ("_pad0", ctypes.c_char * 4),
        ("cursor", ctypes.c_short),
        ("lastcursor", ctypes.c_short),
        ("modalcursor", ctypes.c_short),
        ("grabcursor", ctypes.c_short)
    )
elif bpy.app.version < (3, 3, 0):
    wmWindow._fields_ = (  # from DNA_windowmanager_types.h
        ("next", ctypes.POINTER(wmWindow)),
        ("prev", ctypes.POINTER(wmWindow)),
        ("ghostwin", ctypes.c_void_p),
        ("gpuctx", ctypes.c_void_p),
        ("parent", ctypes.POINTER(wmWindow)),
        ("scene", ctypes.c_void_p),
        ("new_scene", ctypes.c_void_p),
        ("view_layer_name", ctypes.c_char * 64),
        ("workspace_hook", ctypes.c_void_p),
        ("global_areas", listbase(type_=None) * 3),
        ("screen", ctypes.c_void_p),
        ("winid", ctypes.c_int),
        ("posx", ctypes.c_short),
        ("posy", ctypes.c_short),
        ("sizex", ctypes.c_short),
        ("sizey", ctypes.c_short),
        ("windowstate", ctypes.c_char),
        ("active", ctypes.c_char),
        ("cursor", ctypes.c_short),
        ("lastcursor", ctypes.c_short),
        ("modalcursor", ctypes.c_short),
        ("grabcursor", ctypes.c_short)
    )
else:
    wmWindow._fields_ = (  # from DNA_windowmanager_types.h
        ("next", ctypes.POINTER(wmWindow)),
        ("prev", ctypes.POINTER(wmWindow)),
        ("ghostwin", ctypes.c_void_p),
        ("gpuctx", ctypes.c_void_p),
        ("parent", ctypes.POINTER(wmWindow)),
        ("scene", ctypes.c_void_p),
        ("new_scene", ctypes.c_void_p),
        ("view_layer_name", ctypes.c_char * 64),
        ("unpinned_scene", ctypes.c_void_p),
        ("workspace_hook", ctypes.c_void_p),
        ("global_areas", listbase(type_=None) * 3),
        ("screen", ctypes.c_void_p),
        ("winid", ctypes.c_int),
        ("posx", ctypes.c_short),
        ("posy", ctypes.c_short),
        ("sizex", ctypes.c_short),
        ("sizey", ctypes.c_short),
        ("windowstate", ctypes.c_char),
        ("active", ctypes.c_char),
        ("cursor", ctypes.c_short),
        ("lastcursor", ctypes.c_short),
        ("modalcursor", ctypes.c_short),
        ("grabcursor", ctypes.c_short)
    )


OpContext._fields_ = (
    ("win", ctypes.POINTER(wmWindow)),
    ("area", ctypes.c_void_p),  # <-- ScrArea ptr
    ("region", ctypes.c_void_p),  # <-- ARegion ptr
    ("region_type", ctypes.c_short)
)
wmEventHandler_Op._fields_ = (
    ("head", wmEventHandler),
    ("op", ctypes.c_void_p),  # <-- wmOperator
    ("is_file_select", ctypes.c_bool),
    ("context", OpContext)
)


def get_window_state(window: bpy.types.Window):
    win = ctypes.cast(window.as_pointer(), ctypes.POINTER(wmWindow)).contents

    if window.x != win.posx or window.y != win.posy or window.width != win.sizex or window.height != win.sizey:
        raise RuntimeError("Inject internal error!")

    return int.from_bytes(win.windowstate, "big")


def is_modal_procedure(context: bpy.types.Context):
    try:
        b_is_modal = False
        for wnd in context.window_manager.windows:
            p_win = ctypes.cast(wnd.as_pointer(), ctypes.POINTER(wmWindow)).contents
            b_is_modal = p_win.modalcursor != 0 or p_win.grabcursor != 0
            if b_is_modal:
                break
        return b_is_modal
    except Exception as e:
        Log.error(e)
    return True


def test_layout(layout: bpy.types.UILayout):
    ui = ctypes.cast(layout.as_pointer(), ctypes.POINTER(uiLayout)).contents
    print(ui.x, ui.y, ui.w, ui.h, 'type:[', ui.item.type, ']', ui.units[0], ui.units[1])


def test(mode='DEFAULT'):
    window = bpy.context.window
    win = ctypes.cast(window.as_pointer(), ctypes.POINTER(wmWindow)).contents

    if mode == 'DEFAULT':
        print(
            'CURSOR===>', win.cursor,
            'MODAL====>', win.modalcursor,
            'GRAB====>', win.grabcursor,
            'WINMOVE====>', win.addmousemove)

        handle = win.modalhandlers.first
        while handle:
            if handle.contents.type == WM_HANDLER_TYPE_OP:
                print("Modal running")
                break
            handle = handle.contents.next
        else:
            print("No running modals")
    elif mode == 'PIE':
        print(
            'LAST_PIE====>', win.last_pie_event,
            'LOCK_PIE====>', win.lock_pie_event,
        )
