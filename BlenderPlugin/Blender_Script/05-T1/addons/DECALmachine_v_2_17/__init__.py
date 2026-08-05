bl_info = {
    "name": "DECALmachine",
    "author": "MACHIN3, AR, MX, proxeIO, mem, Justo Figueroa",
    "version": (2, 17, 0),
    "blender": (4, 3, 0),
    "location": "Pie Menu: D key, MACHIN3 N Panel",
    "revision": "593d50af3db3f07aa84b5529b63d982fdea8f57a",
    "description": "A complete mesh-decal and trim sheet pipeline: Use decals as objects or use trims on the mesh level, design your own custom decals or import trim sheets, export decal assets via atlasing or baking.",
    "warning": "",
    "doc_url": "https://cgb3d.taobao.com",
    "tracker_url": "https://cgb3d.taobao.com",
    "category": "3D View"}

def reload_modules(name):
    import os
    import importlib

    dbg = False

    from . import registration, items, colors

    for module in [registration, items, colors]:
        importlib.reload(module)

    utils_modules = sorted([name[:-3] for name in os.listdir(os.path.join(__path__[0], "utils")) if name.endswith('.py')])

    for module in utils_modules:
        impline = "from . utils import %s" % (module)

        if dbg:
            print(f"reloading {name}.utils.{module}")

        exec(impline)
        importlib.reload(eval(module))

    from . import handlers

    if dbg:
        print("reloading", handlers.__name__)

    importlib.reload(handlers)

    modules = []

    for label in registration.classes:
        entries = registration.classes[label]
        for entry in entries:
            path = entry[0].split('.')
            module = path.pop(-1)

            if (path, module) not in modules:
                modules.append((path, module))

    for path, module in modules:
        if path:
            impline = f"from . {'.'.join(path)} import {module}"
        else:
            impline = f"from . import {module}"

        if dbg:
            print(f"reloading {name}.{'.'.join(path)}.{module}")

        exec(impline)
        importlib.reload(eval(module))

if 'bpy' in locals():
    reload_modules(bl_info['name'])

import bpy
from bpy.props import BoolProperty, EnumProperty, PointerProperty, CollectionProperty
from bpy.utils import previews
from .zh.translations import unregister_translation_dict, register_translation_dict
from typing import Tuple
import os
import importlib
from time import time

from . properties import DecalSceneProperties, DecalObjectProperties, DecalMaterialProperties, DecalImageProperties, DecalCollectionProperties, ExcludeCollection
from . utils.assets import verify_assetspath
from . utils.material import is_legacy_material
from . utils.registration import get_addon, get_assetspath_dict, get_path, get_core, get_menus, get_tools, get_gizmos, get_prefs, is_decal_registered, is_trimsheet_registered, register_classes, unregister_classes, register_keymaps, unregister_keymaps
from . utils.registration import register_decals, unregister_decals, register_instant_decals, unregister_instant_decals, register_lockedlib, unregister_lockedlib
from . utils.registration import register_infotextures, unregister_infotextures, register_infofonts, unregister_infofonts, register_trimtextures, unregister_trimtextures
from . utils.registration import register_trims, unregister_trims, register_atlases
from . utils.system import get_PIL_image_module_path, verify_user_sitepackages, verify_update, install_update, printd
from . handlers import undo_and_redo_post, load_post, depsgraph_update_post

def update_check():
    def get_version_as_string():
        return '.'.join(str(v) for v in bl_info['version'])

    def get_version_as_semver_string():
        version = [v for v in bl_info['version']]

        if len(version) == 3:
            return ".".join([str(v) for v in version])

        else:
            sign = "-" if any(version[3] == rt for rt in ['alpha', 'beta', 'rc']) else "+"
            basever = ".".join([str(v) for v in version[:3]]) + f"{sign}{version[3]}"

            if version[4:]:
                tailver = ".".join(str(v) for v in version[4:])
                return f"{basever}.{tailver}"

            else:
                return basever

    def hook(resp, *args, **kwargs):
        if resp:
            if resp.text == 'true':
                get_prefs().update_available = True

            else:
                get_prefs().update_available = False

            if debug:
                print(" received response:", resp.text)

            write_update_check(update_path, time(), debug=debug)

    def init_update_check(debug=False):
        if debug:
            print()
            print("initiating update check for version", get_version_as_string(), "semver:", get_version_as_semver_string())

        import platform
        import hashlib
        from . modules.requests_futures.sessions import FuturesSession

        machine = hashlib.sha1(platform.node().encode('utf-8')).hexdigest()[0:7]

        headers = {'User-Agent': f"{bl_info['name']}/{get_version_as_semver_string()} Blender/{'.'.join([str(v) for v in bpy.app.version])} ({platform.uname()[0]}; {platform.uname()[2]}; {platform.uname()[4]}; {machine})"}
        session = FuturesSession()

        try:
            if debug:
                print(" sending update request")

            session.post("https://drum.machin3.io/update", data={'revision': bl_info['revision']}, headers=headers, hooks={'response': hook})
        except:
            pass

    def write_update_check(update_path, update_time, debug=False):
        if debug:
            print()
            print("writing update check data")

        update_available = get_prefs().update_available

        msg = [f"version: {get_version_as_string()}",
               f"update time: {update_time}",
               f"update available: {update_available}\n"]

        with open(update_path, mode='w') as f:
            f.write('\n'.join(m for m in msg))

        if debug:
            print(" written to", update_path)

        return update_time, update_available

    def read_update_check(update_path, debug=False) -> Tuple[bool, str, float, bool]:
        if debug:
            print()
            print(f"reading {bl_info['name']} update check data")

        with open(update_path) as f:
            lines = [l[:-1] for l in f.readlines()]

        if len(lines) == 3:
            version = lines[0].replace('version: ', '')
            update_time_str = lines[1].replace('update time: ', '')
            update_available_str = lines[2].replace('update available: ', '')

            if debug:
                print(" fetched version:", version)
                print(" fetched update available:", update_available_str)
                print(" fetched update time:", update_time_str)

            try:
                update_time = float(update_time_str)
            except:
                update_time = None

            try:
                update_available = True if update_available_str == 'True' else False if update_available_str == 'False' else None
            except:
                update_available = None

            if version and update_time is not None and update_available is not None:
                return True, version, update_time, update_available

        return False, None, None, None

    debug = False

    update_path = os.path.join(get_path(), 'update_check')

    if not os.path.exists(update_path):
        if debug:
            print(f"init {bl_info['name']} update check as file does not exist")

        init_update_check(debug=debug)

    else:
        valid, version, update_time, update_available = read_update_check(update_path, debug=debug)

        if valid:

            if debug:
                print(f" comparing stored {bl_info['name']} version:", version, "with bl_info['version']:", get_version_as_string())

            if version != get_version_as_string():
                if debug:
                    print(f"init {bl_info['name']} update check, as the versions differ due to user updating the addon since the last update check")

                init_update_check(debug=debug)
                return

            now = time()
            delta_time = now - update_time

            if debug:
                print(" comparing", now, "and", update_time)
                print("  delta time:", delta_time)

            if delta_time > 72000:
                if debug:
                    print(f"init {bl_info['name']} update check, as it has been over 20 hours since the last one")

                init_update_check(debug=debug)
                return

            if debug:
                print(f"no {bl_info['name']} update check required, setting update available prefs from stored file")

            get_prefs().update_available = update_available

        else:
            if debug:
                print(f"init {bl_info['name']} update check as fetched file is invalid")

            init_update_check(debug=debug)

def register():
    global classes, keymaps

    core_classes = register_classes(get_core())

    bpy.types.Scene.DM = PointerProperty(type=DecalSceneProperties)
    bpy.types.Object.DM = PointerProperty(type=DecalObjectProperties)
    bpy.types.Material.DM = PointerProperty(type=DecalMaterialProperties)
    bpy.types.Image.DM = PointerProperty(type=DecalImageProperties)
    bpy.types.Collection.DM = PointerProperty(type=DecalCollectionProperties)

    bpy.types.WindowManager.matchmaterial = EnumProperty(name="Materials, that can be matched", description="Match specificly selected Material only", items=[("None", "None", "Blender White", 0, 0), ("Default", "Default", "DECALmachine Metal", 0, 1)])

    bpy.types.WindowManager.collectinfotextures = BoolProperty()
    bpy.types.WindowManager.excludeimages = CollectionProperty(type=ExcludeCollection)

    bpy.types.WindowManager.collectinfofonts = BoolProperty()
    bpy.types.WindowManager.excludefonts = CollectionProperty(type=ExcludeCollection)
    bpy.types.WindowManager.collecttrimtextures = BoolProperty()

    assetspath = verify_assetspath()

    decals = register_decals()
    trims = register_trims()
    atlases = register_atlases()
    register_instant_decals()
    register_lockedlib()

    register_infotextures()
    register_infofonts()
    register_trimtextures()

    menu_classlists, menu_keylists = get_menus()
    tool_classlists, tool_keylists = get_tools()
    gizmo_classlists = get_gizmos()

    classes = register_classes(menu_classlists + tool_classlists + gizmo_classlists) + core_classes
    keymaps = register_keymaps(menu_keylists + tool_keylists)

    bpy.app.handlers.undo_post.append(undo_and_redo_post)
    bpy.app.handlers.redo_post.append(undo_and_redo_post)

    bpy.app.handlers.load_post.append(load_post)
    bpy.app.handlers.depsgraph_update_post.append(depsgraph_update_post)

    DECALmachineManager.register_icons()

    DECALmachineManager.clear_addons()

    try:
        verify_user_sitepackages()

        import PIL
        from PIL import Image

        Image.MAX_IMAGE_PIXELS = None

        get_prefs().pil = True
        get_prefs().pilrestart = False
        path = get_PIL_image_module_path(Image)
    except:
        get_prefs().pil = False
        get_prefs().pilrestart = False
        path = ''

    if get_prefs().registration_debug:

        print(f"Registered {bl_info['name']} {'.'.join([str(i) for i in bl_info['version']])} with {len(decals)} decal libraries, {len(trims)} trim sheet libraries and {len(atlases)} atlases.", f"PIL {PIL.__version__} Image Module: {path}" if get_prefs().pil else "PIL is not installed.")
        print("Decals, Trimsheets and Atlases are located in", assetspath)

        for libname, libtype, _ in decals + trims:
            print(f" • {libtype} library: {libname}")

        for atlas in atlases:
            print(f" • atlas: {atlas}")

    update_check()

    verify_update()
    if bpy.context.preferences.view.use_translate_interface and bpy.context.preferences.view.language.startswith('zh'):
        register_translation_dict()


def unregister():
    global classes, keymaps

    debug = get_prefs().registration_debug
    keep_assets = get_prefs().update_keep_assets

    from . handlers import trimgridVIEW3D

    if trimgridVIEW3D and "RNA_HANDLE_REMOVED" not in str(trimgridVIEW3D):
        bpy.types.SpaceView3D.draw_handler_remove(trimgridVIEW3D, 'WINDOW')

    bpy.app.handlers.redo_post.remove(undo_and_redo_post)
    bpy.app.handlers.undo_post.remove(undo_and_redo_post)

    bpy.app.handlers.load_post.remove(load_post)
    bpy.app.handlers.depsgraph_update_post.remove(depsgraph_update_post)

    unregister_decals()
    unregister_instant_decals()
    unregister_lockedlib()

    unregister_trims()

    unregister_infotextures()
    unregister_infofonts()
    unregister_trimtextures()

    unregister_keymaps(keymaps)

    del bpy.types.Scene.DM
    del bpy.types.Object.DM
    del bpy.types.Material.DM
    del bpy.types.Image.DM
    del bpy.types.Collection.DM

    del bpy.types.WindowManager.matchmaterial

    del bpy.types.Scene.userdecallibs
    del bpy.types.WindowManager.newdecalidx
    del bpy.types.WindowManager.decaluuids
    del bpy.types.WindowManager.paneldecals
    del bpy.types.WindowManager.instantdecaluuids

    del bpy.types.WindowManager.trimsheets
    del bpy.types.WindowManager.atlases

    del bpy.types.WindowManager.collectinfotextures
    del bpy.types.WindowManager.excludeimages

    del bpy.types.WindowManager.collectinfofonts
    del bpy.types.WindowManager.excludefonts
    del bpy.types.WindowManager.instanttrimsheetcount
    del bpy.types.WindowManager.instantatlascount

    unregister_classes(classes)

    DECALmachineManager.unregister_icons()

    if debug:
        print("Unregistered %s %s" % (bl_info["name"], ".".join([str(i) for i in bl_info['version']])))

    install_update(keep_assets=keep_assets)
    unregister_translation_dict()

class DECALmachineManager:

    pil_version = "10.1.0"

    draw = {'MESHCUT': []}

    addons = {}

    @classmethod
    def get_addon(cls, name='SomeAddon', version=False, debug=False):

        addon = cls.addons.setdefault(name.lower(), {'enabled': None, 'version': None, 'foldername': '', 'path': '', 'module': None, 'prefs': None})
        if addon['enabled'] is None:
            addon['enabled'],  addon['foldername'],  addon['version'],  addon['path'] = get_addon(name)

            if addon['enabled']:
                addon['module'] = importlib.import_module(addon['foldername'])
                addon['prefs'] = bpy.context.preferences.addons.get(addon['foldername']).preferences

            if debug:
                printd(addon, name)

        return (addon['enabled'], addon['version']) if version else addon['enabled']

    @classmethod
    def clear_addons(cls):
        cls.addons.clear()

    @classmethod
    def register_icons(cls):
        cls.icons = previews.new()

        path = os.path.join(get_prefs().path, "icons")

        for i in sorted(os.listdir(path)):
            if i.endswith(".png"):
                iconname = i[:-4]
                filepath = os.path.join(path, i)

                cls.icons.load(iconname, filepath, 'IMAGE')

    @classmethod
    def unregister_icons(cls):
        previews.remove(cls.icons)
        del cls.icons

    assets = None

    decal_libraries = []
    trim_libraries = []

    locked = None
    instantdecals = None
    infotextures = None
    infofonts = None
    trimtextures = None

    @classmethod
    def get_assets_dict(cls, force=False):
        if force or cls.assets is None:
            cls.assets = get_assetspath_dict()

        return cls.assets

    legacy = None

    @classmethod
    def get_legacy_materials(cls, force=False, debug=False):

        if force or cls.legacy is None:
            cls.legacy = {
                'DECAL': {},
                'TRIM': {}
            }

            decalmats = [mat for mat in bpy.data.materials if mat.DM.isdecalmat and 'LIBRARY_DECAL' not in mat.name]
            sheetmats = [mat for mat in bpy.data.materials if mat.DM.istrimsheetmat]

            for mat in decalmats:
                if version := is_legacy_material(mat):

                    name = mat.DM.decallibrary + ' - ' + mat.DM.decalname.replace(f"{mat.DM.decallibrary}_", '')

                    if version not in cls.legacy['DECAL']:
                        cls.legacy['DECAL'][version] = {
                            'materials': [mat],
                            'names': [name],
                            'registered': {name: bool(is_decal_registered(mat.DM.uuid))},
                            'count': {name: 1}
                        }

                    else:
                        cls.legacy['DECAL'][version]['materials'].append(mat)

                        if name not in cls.legacy['DECAL'][version]['names']:
                            cls.legacy['DECAL'][version]['names'].append(name)
                            cls.legacy['DECAL'][version]['registered'][name] = bool(is_decal_registered(mat.DM.uuid))
                            cls.legacy['DECAL'][version]['count'][name] = 1

                        else:
                            cls.legacy['DECAL'][version]['count'][name] += 1

            for mat in sheetmats:
                if version := is_legacy_material(mat):
                    if version not in cls.legacy['TRIM']:
                        cls.legacy['TRIM'][version] = {
                            'materials': [mat],
                            'names': [mat.DM.trimsheetname],
                            'registered': {mat.DM.trimsheetname: bool(is_trimsheet_registered(mat.DM.trimsheetuuid))},
                            'count': {mat.DM.trimsheetname: 1}
                        }

                    else:
                        cls.legacy['TRIM'][version]['materials'].append(mat)

                        if mat.DM.trimsheetname not in cls.legacy['TRIM'][version]['names']:
                            cls.legacy['TRIM'][version]['names'].append(mat.DM.trimsheetname)
                            cls.legacy['TRIM'][version]['registered'][mat.DM.trimsheetname] = bool(is_trimsheet_registered(mat.DM.trimsheetuuid))
                            cls.legacy['TRIM'][version]['count'][mat.DM.trimsheetname] = 1

                        else:
                            cls.legacy['TRIM'][version]['count'][mat.DM.trimsheetname] += 1

            if debug:
                printd(cls.legacy, name="legacy materials")

        return cls.legacy
