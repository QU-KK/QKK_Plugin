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

from .utils import in_debug_mode, print_debug
from .app_iface import *
from .connection import encode_string

import json


SCRIPTED_PIPELINE_DIRNAME = "spipeline"
ENGINE_PACKAGE_DIRNAME = "engine"


class EngineParams(dict):

    DEVICE_SETTINGS_PARAM_NAME = '__device_settings'
    SYS_PATH_PARAM_NAME = '__sys_path'
    GROUPING_SCHEME_PARAM_NAME = '__grouping_scheme'

    def __init__(self):
        self[self.SYS_PATH_PARAM_NAME] = []

    def add_device_settings(self, dev_array):
        settings_params = []

        for dev in dev_array:
            settings = dev.settings
            settings_params.append({'id': dev.id, 'enabled': settings.enabled})

        self[self.DEVICE_SETTINGS_PARAM_NAME] = settings_params

    def add_sys_path(self, sys_path):
        sys_path_param = self[self.SYS_PATH_PARAM_NAME]
        sys_path_param.append(sys_path)

    def serialize(self):
        if in_debug_mode(2):
            print_debug('Engine params: {}'.format(self))

        return encode_string(json.dumps(self))
