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
import addon_utils

import sys
import importlib
import os

# from timeit import default_timer as timer

from .utils.blender_zen_utils import ZenPolls
# from .utils.vlog import Log
# from .utils.translations import translations_dict


APP_BACKGROUND = bpy.app.background
user_module = None
from .import iBlender_ZenUV


bl_info = {
    "name": "Zen UV",
    "author": "Valeriy Yatsenko, iBlender@taobao.com, Alex Zhornyak, Sergey Tyapkin, Viktor [VAN] Teplov",
    "version": (5, 2, 1, 1),
    "description": "Optimize UV mapping workflow",
    "blender": (3, 6, 0),
    "location": "View3D > Sidebar > Zen UV",
    "category": "UV",
    "tracker_url": "https://item.taobao.com/item.htm?ft=t&id=750706645566",
    "doc_url": "https://blendermarket.com/products/zen-uv"
}


# NOTE: something weird happens with Blender extension system,
#       it does not recognize 'bl_info' variable, seems to be removed,
#       so, we are using proxy dictionary
proxy_info = bl_info.copy()


module_names = [
    ('.ico', __package__),
    ('.adv_generic_ui_list', f'{__package__}.utils'),
    ('.user_presets', f'{__package__}.user_data'),
    ('.ops', __package__),
    ('.prop', __package__),
    ('.ui', __package__),
    ('.zen_checker', __package__),
    ('.stacks', __package__),
    ('.sticky_uv_editor', __package__),
    ('.addon_test', f'{__package__}.utils.tests'),
    ('.clib', f'{__package__}.utils'),
    ('.system_operators', f'{__package__}.utils.tests'),
    ('.keymap_manager', f'{__package__}.ui')
]


def check_addon_duplicated():

    ORIGINAL_ID = "ZenUV"

    def check_addon_name(s_package):
        if s_package != ORIGINAL_ID:
            raise RuntimeError(f"We do not allow to rename folder other than {ORIGINAL_ID}!")

    if not ZenPolls.version_since_4_2_0:
        # NOTE: here we will check only the name of the addon package
        check_addon_name(__package__)
        return

    # NOTE: the checking system is essential only after Blender 4.2 when extensions were introduced
    from bl_pkg.bl_extension_ui import pkg_repo_module_prefix  # type: ignore

    from collections import defaultdict

    extension_repos = bpy.context.preferences.extensions.repos

    repo_ids = {pkg_repo_module_prefix(repo_item) for repo_item in extension_repos if repo_item.enabled}

    # NOTE: the list of all ready-to-use modules
    t_used_modules = {module.__name__: module.__file__ for module in addon_utils.modules()}

    # NOTE: 'bl_ext.RepoNNN.ZenUV' will be truncated to 'ZenUV'
    def get_identifier(module_name):
        for id in repo_ids:
            if module_name.startswith(id):
                return module_name.replace(id, "")
        return module_name

    this_addon_id = get_identifier(__package__)

    check_addon_name(this_addon_id)

    # NOTE: dict of active addons {'ZenUV': ['bl_ext.Repo1.ZenUV', 'bl_ext.RepoNNN.ZenUV']}
    active_addons = defaultdict(list)
    for addon in bpy.context.preferences.addons:
        s_module_name = addon.module
        if s_module_name == __package__ or s_module_name not in t_used_modules:
            continue

        addon_id = get_identifier(s_module_name)

        active_addons[addon_id].append(s_module_name)

    p_addon_copies = active_addons.get(this_addon_id, [])
    if len(p_addon_copies) > 0:
        s_version = ".".join(map(str, proxy_info['version']))
        error_lines = [
            f"Can not activate {this_addon_id} {s_version}:",
            f"  1) {__file__}",
            "Other version detected:"
        ]

        # for idx, item in enumerate(p_addon_copies):
        #     error_lines.append(f"  {idx + 2}) {item} - {t_used_modules.get(item, '')}")

        raise RuntimeError("\n".join(error_lines))


def register():
    iBlender_ZenUV.register()
    """ Register classes """

    # NOTE: weird behaviour in Blender when 2 or more same extensions are allowed to be active in the moment
    #       https://projects.blender.org/blender/blender/issues/144187
    #       so, prevent it by ourselves
    check_addon_duplicated()

    # NOTE: we should detect addon package name to support extensions
    ZenPolls.ADDON_PACKAGE = __package__
    ZenPolls.ADDON_DIR = os.path.abspath(os.path.dirname(__file__))
    ZenPolls.ADDON_VERSION = proxy_info['version']
    ZenPolls.doc_url = proxy_info['doc_url']
    ZenPolls.support_url = proxy_info['tracker_url']
    ZenPolls.register_session()


    for name, package in module_names:
        mod = importlib.import_module(name, package)
        mod.register()


    from .prop.zuv_preferences import get_prefs
    addon_prefs = get_prefs()


    try:
        if addon_prefs.user_script.active and addon_prefs.user_script.file_path:
            if os.path.exists(addon_prefs.user_script.file_path):
                spec = importlib.util.spec_from_file_location(
                    f"{__package__}.user_script", addon_prefs.user_script.file_path)
                global user_module
                user_module = importlib.util.module_from_spec(spec)
                sys.modules[f"{__package__}.user_script"] = user_module
                spec.loader.exec_module(user_module)
                user_module.register()
    except Exception as e:
        print('LOAD USER SCRIPT:', str(e))

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




def unregister():
    """ Unregister classes """


    ZenPolls.unregister_session()

    if user_module:
        try:
            user_module.unregister()
        except Exception as e:
            print('UNLOAD USER SCRIPT:', str(e))

    bpy.app.translations.unregister(__name__)

    for name, package in reversed(module_names):
        mod_name = package + name
        mod = sys.modules.get(mod_name)
        if mod:
            mod.unregister()
    iBlender_ZenUV.unregister()
