# ##### BEGIN GPL LICENSE BLOCK #####
#
#  This program is free software; you can redistribute it and/or
#  modify it under the terms of the GNU General Public License
#  as published by the Free Software Foundation; either version 2
#  of the License, or (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program; if not, write to the Free Software Foundation,
#  Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301, USA.
#
# ##### END GPL LICENSE BLOCK #####

""" Init Zen UV """
import bpy

import sys
import importlib
import os
import json
import urllib.request
import ssl
from timeit import default_timer as timer

from ZenUV.utils.blender_zen_utils import ZenPolls
from ZenUV.utils.vlog import Log
from ZenUV.utils.translations import translations_dict


APP_BACKGROUND = bpy.app.background
user_module = None


bl_info = {
    "name": "Zen UV",
    "author": "Valeriy Yatsenko, Alex Zhornyak, Sergey Tyapkin, Viktor [VAN] Teplov",
    "version": (5, 0, 3, 0),
    "description": "Optimize UV mapping workflow",
    "blender": (3, 6, 0),
    "location": "View3D > Sidebar > Zen UV",
    "category": "UV",
    "tracker_url": "https://support.zenmasters.team/",
    "doc_url": "https://zenmastersteam.github.io/Zen-UV/latest/"
}


module_names = [
    ('.ico', 'ZenUV'),
    ('.adv_generic_ui_list', 'ZenUV.utils'),
    ('.user_presets', 'ZenUV.user_data'),
    ('.ops', 'ZenUV'),
    ('.prop', 'ZenUV'),
    ('.ui', 'ZenUV'),
    ('.zen_checker', 'ZenUV'),
    ('.stacks', 'ZenUV'),
    ('.sticky_uv_editor', 'ZenUV'),
    ('.addon_test', 'ZenUV.utils.tests'),
    ('.clib', 'ZenUV.utils'),
    ('.system_operators', 'ZenUV.utils.tests'),
    ('.keymap_manager', 'ZenUV.ui')
]


def register():
    """ Register classes """

    ZenPolls.ADDON_PACKAGE = __package__
    ZenPolls.doc_url = bl_info['doc_url']
    ZenPolls.support_url = bl_info['tracker_url']
    ZenPolls.register_session()

    try:
        if Log.ENABLE_DEBUG:
            base_dir = os.path.dirname(__file__)
            with open(os.path.join(base_dir, 'log.json'), 'r', encoding='utf-8-sig') as f:
                data = json.load(f)
                Log.CATEGORY = data['Category']
    except Exception:
        pass

    for name, package in module_names:
        mod = importlib.import_module(name, package)
        mod.register()

    bpy.app.translations.register(__name__, translations_dict)

    from ZenUV.prop.zuv_preferences import get_prefs
    addon_prefs = get_prefs()


    try:
        if addon_prefs.user_script.active and addon_prefs.user_script.file_path:
            if os.path.exists(addon_prefs.user_script.file_path):
                spec = importlib.util.spec_from_file_location(
                    "ZenUV.user_script", addon_prefs.user_script.file_path)
                global user_module
                user_module = importlib.util.module_from_spec(spec)
                sys.modules["ZenUV.user_script"] = user_module
                spec.loader.exec_module(user_module)
                user_module.register()
    except Exception as e:
        Log.error('LOAD USER SCRIPT:', str(e))

    if not APP_BACKGROUND:
        p_rename_templates = addon_prefs.adv_maps.rename_templates
        if len(p_rename_templates) == 0:
            t_default = (
                'UVMap',
                'Channel',
                'Lightmap',
                'Diffuse',
                'Bake'
            )

            for p_item in t_default:
                p_rename_templates.add()
                p_rename_templates[-1].name = p_item

        try:
            if ZenPolls.internet_enabled() and addon_prefs.check_for_updates:
                interval = timer()
                ssl_context = ssl._create_unverified_context()
                s_version_url = 'https://raw.githubusercontent.com/ZenMastersTeam/Zen-UV/main/README.md'
                with urllib.request.urlopen(s_version_url, context=ssl_context) as f:
                    config = f.read().decode('utf-8')  # type: str

                    t_lines = config.split('\n')
                    for line in t_lines:
                        if line.startswith("# Zen-UV"):
                            s_version = line.replace("# Zen-UV", '').strip()
                            t_version = [int(v) for v in s_version.split('.')]
                            t_version = tuple(t_version[:3])
                            t_was_version = tuple(bl_info["version"][:3])
                            if t_was_version < t_version:
                                ZenPolls.new_addon_version = t_version
                            break
                Log.debug('>>> CHECK ADDON VER:', timer() - interval)

        except Exception as e:
            Log.error('CHECK UPDATES:', e)



def unregister():
    """ Unregister classes """


    ZenPolls.unregister_session()

    if user_module:
        try:
            user_module.unregister()
        except Exception as e:
            Log.error('UNLOAD USER SCRIPT:', str(e))

    bpy.app.translations.unregister(__name__)

    for name, package in reversed(module_names):
        mod_name = package + name
        mod = sys.modules.get(mod_name)
        if mod:
            mod.unregister()
