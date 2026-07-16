bl_info = {
    "name": "CURVEmachine",
    "author": "MACHIN3",
    "version": (1, 2, 1),
    "blender": (3, 6, 0),
    "location": "Edit Curve Mode Menu: Y key",
    "revision": "4206d6da0324f137c067be3259cd08a1252c4a24",
    "description": "The missing (POLY) Curve essentials.",
    "warning": "",
    "doc_url": "https://machin3.io/CURVEmachine/docs",
    "tracker_url": "https://machin3.io/CURVEmachine/docs/faq/#get-support",
    "category": "Curve"}

import bpy
from . utils.registration import get_core, get_ops, get_prefs
from . utils.registration import register_classes, unregister_classes, register_keymaps, unregister_keymaps, register_icons, unregister_icons
from . handlers import curve_selection_history
from . ui.menus import add_object_buttons, context_menu

def update_check():
    def hook(resp, *args, **kwargs):
        if resp:
            if resp.text == 'true':
                get_prefs().update_available = True

    import platform
    import hashlib
    from . modules.requests_futures.sessions import FuturesSession

    get_prefs().update_available = False

    machine = hashlib.sha1(platform.node().encode('utf-8')).hexdigest()[0:7]

    headers = {'User-Agent': f"CURVEmachine/{'.'.join([str(v) for v in bl_info.get('version')])} Blender/{'.'.join([str(v) for v in bpy.app.version])} ({platform.uname()[0]}; {platform.uname()[2]}; {platform.uname()[4]}; {machine})"}
    session = FuturesSession()

    try:
        session.post("https://drum.machin3.io/update", data={'revision': bl_info['revision']}, headers=headers, hooks={'response': hook})
    except:
        pass

def register():
    global classes, keymaps, icons

    core_classlists, core_keylists = get_core()
    core_classes = register_classes(core_classlists)

    ops_classlists, ops_keylists = get_ops()

    classes = register_classes(ops_classlists) + core_classes

    bpy.types.VIEW3D_MT_curve_add.prepend(add_object_buttons)
    bpy.types.VIEW3D_MT_edit_curve_context_menu.prepend(context_menu)

    keymaps = register_keymaps(core_keylists + ops_keylists)

    bpy.app.handlers.depsgraph_update_post.append(curve_selection_history)

    icons = register_icons()

    if get_prefs().registration_debug:
        print(f"Registered {bl_info['name']} {'.'.join([str(i) for i in bl_info['version']])}")

    update_check()

def unregister():
    global classes, keymaps, icons

    debug = get_prefs().registration_debug

    bpy.app.handlers.depsgraph_update_post.remove(curve_selection_history)

    unregister_keymaps(keymaps)

    bpy.types.VIEW3D_MT_curve_add.remove(add_object_buttons)
    bpy.types.VIEW3D_MT_edit_curve_context_menu.remove(context_menu)

    unregister_classes(classes)

    unregister_icons(icons)

    if debug:
        print(f"Unregistered {bl_info['name']} {'.'.join([str(i) for i in bl_info['version']])}")
