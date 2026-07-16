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


import platform
import subprocess
import struct
import os

from .version import UvpmVersionInfo

from .os_iface import os_platform_check, os_engine_path
from .spipeline.engine.types import UvpmMessageCode, UvpmOpcode, UvpmDeviceFlags
from .utils import get_engine_execpath, process_file_path, print_backtrace_if_debug, get_engine_path, redraw_ui
from .connection import force_read_int, send_finish_confirmation, connection_rcv_message, decode_string
from .app_iface import *


class BenchmarkEntry:

    def __init__(self):
        self.reset()

    def reset(self):
        self.progress = 0
        self.iter_count = 0
        self.total_time = 0
        self.avg_time = 0

    def decode(self, benchmark_msg):
        self.progress = force_read_int(benchmark_msg)
        self.iter_count = force_read_int(benchmark_msg)
        self.total_time = force_read_int(benchmark_msg)
        self.avg_time = -1 if self.iter_count == 0 else int(float(self.total_time) / self.iter_count)


class DeviceDesc:

    def __init__(self, id, name, supported, supports_groups_together, saved_settings):
        self.id = id
        self.name = name
        self.supported = supported
        self.supports_groups_together = supports_groups_together
        self.saved_settings = saved_settings
        self.settings = saved_settings.settings
        self.bench_entry = BenchmarkEntry()

    def reset(self):
        self.bench_entry.reset()

    def help_url_suffix(self):
        return self.saved_settings.get_metadata().help_url_suffix


def platform_check():
    unsupported_msg = 'Unsupported platform detected. Supported platforms are Linux 64 bit, Windows 64 bit, MacOS 64 bit'

    sys = platform.system()
    if sys != 'Linux' and sys != 'Windows' and sys != 'Darwin':
        raise RuntimeError(unsupported_msg)

    is_64bit = platform.machine().endswith('64')
    if not is_64bit:
        raise RuntimeError(unsupported_msg)

    os_platform_check(get_engine_execpath())


def get_engine_version():
    engine_args = [get_engine_execpath(), '-E', '-o', str(UvpmOpcode.REPORT_VERSION)]
    engine_args += get_prefs().get_engine_args()
    
    version_msg = None
    
    with subprocess.Popen(engine_args, stdin=subprocess.PIPE, stdout=subprocess.PIPE) as engine_proc:
        send_finish_confirmation(engine_proc)

        try:
            engine_proc.wait(5)
        except:
            engine_proc.terminate()
            raise

        in_stream = engine_proc.stdout

        while True:
            msg = connection_rcv_message(in_stream)
            msg_code = force_read_int(msg)

            if msg_code == UvpmMessageCode.VERSION:
                version_msg = msg
                break

    if version_msg is None:
        raise RuntimeError('Could not read the UVPM version')

    # TODO: make sure this won't block
    version_major = force_read_int(version_msg)
    version_minor = force_read_int(version_msg)
    version_patch = force_read_int(version_msg)
    version_suffix = decode_string(version_msg, str_len=1)

    feature_cnt = struct.unpack('i', version_msg.read(4))[0]
    feature_codes = []

    for i in range(feature_cnt):
        feature_codes.append(force_read_int(version_msg))

    dev_cnt = force_read_int(version_msg)
    devices = []

    for i in range(dev_cnt):
        id = decode_string(version_msg)
        name = decode_string(version_msg)

        dev_flags = force_read_int(version_msg)
        devices.append((id, name, dev_flags))

    engine_version = (version_major, version_minor, version_patch)
    return engine_version, version_suffix, devices


@persistent_handler
def load_post_handler(scene):
    get_prefs().reset_box_params()

    from .repack import repack_load_post_handler
    repack_load_post_handler()

    from .tdensity import tdensity_post_handler
    tdensity_post_handler()

    return None


def register_specific(isolated_engine_path=None):
    append_load_post_handler(load_post_handler)
    
    from .multi_panel_manager import MultiPanelManager
    MultiPanelManager.reset()

    if isolated_engine_path:
        paths_to_check = [isolated_engine_path]
    else:
        addon_engine_path = os.path.join(os.path.dirname(os.path.abspath(process_file_path(__file__))), 'engine4')
        paths_to_check = [get_prefs().engine_path, addon_engine_path, os_engine_path()]

    for path in paths_to_check:

        if path is None:
            continue

        try:
            register_engine(path)
        except:
            continue

        break


def check_engine():
    engine_release_filepath = os.path.join(get_engine_path(), 'release-{}.uvpmi'.format(UvpmVersionInfo.engine_version_string()))
    return os.path.isfile(engine_release_filepath)


def unregister_engine():
    prefs = get_prefs()
    prefs.engine_initialized = False
    prefs.engine_status_msg = 'UVPackmaster engine {} not detected. Press the button for help:'.format(UvpmVersionInfo.engine_version_string())
    prefs.engine_path = 'Engine not detected'

    prefs.reset_device_array()


def register_engine(engine_path):
    from .operator_generic import UVPM4_OT_Generic

    try:
        prefs = get_prefs()
        prefs.reset()
        prefs.engine_path = engine_path

        if not check_engine():
            raise RuntimeError('Engine version {} required'.format(UvpmVersionInfo.engine_version_string()))

        if not os.path.isfile(get_engine_execpath()):
            raise RuntimeError('Engine installation broken')

        platform_check()

        engine_version, version_suffix, devices = get_engine_version()

        if engine_version != UvpmVersionInfo.engine_version_tuple():
            raise RuntimeError(UVPM4_OT_Generic.UNEXPECTED_ERROR_MSG)

        edition_array = UvpmVersionInfo.uvpm_edition_array()
        edition_array_tmp = [edition_info for edition_info in edition_array if edition_info.suffix == version_suffix]
        if len(edition_array_tmp) != 1:
            raise RuntimeError(UVPM4_OT_Generic.UNEXPECTED_ERROR_MSG)

        edition_long_name = edition_array_tmp[0].long_name

        if len(devices) == 0 or devices[0][0] != 'cpu':
            raise RuntimeError(UVPM4_OT_Generic.UNEXPECTED_ERROR_MSG)

        register_devices(prefs, devices)

        prefs.engine_status_msg = 'UVPackmaster Engine: {} {}'.format(UvpmVersionInfo.engine_version_string(), edition_long_name)
        prefs.engine_initialized = True

    except Exception as ex:
        print_backtrace_if_debug(ex)
        unregister_engine()
        raise
    except:
        unregister_engine()
        raise


def register_devices(prefs, devices):
    dev_array = []

    for dev in devices:
        dev_id = dev[0]
        dev_name = dev[1]
        dev_flags = dev[2]

        # Search for saved device settings
        dev_saved_settings = None
        for saved_settings in prefs.saved_dev_settings:
            if saved_settings.dev_id == dev_id:
                dev_saved_settings = saved_settings
                break

        if dev_saved_settings is None:
            dev_saved_settings = prefs.saved_dev_settings.add()
            dev_saved_settings.init(dev_id)

        dev_desc = DeviceDesc(\
            dev_id,
            dev_name,
            supported=(dev_flags & UvpmDeviceFlags.SUPPORTED) > 0,
            supports_groups_together=(dev_flags & UvpmDeviceFlags.SUPPORTS_GROUPS_TOGETHER) > 0,
            saved_settings=dev_saved_settings)

        dev_array.append(dev_desc)

    type(prefs).dev_array = dev_array


def register_modes(modes_classes):
    from collections import defaultdict
    mode_type__mode_id_cls_pair = defaultdict(list)
    modes_ids = []

    for mode_cls in modes_classes:
        if mode_cls.MODE_ID in modes_ids:
            raise RuntimeError("The '{}' mode is duplicated".format(mode_cls.MODE_ID))

        modes_ids.append(mode_cls)
        mode_type__mode_id_cls_pair[mode_cls.MODE_TYPE].append((mode_cls.MODE_ID, mode_cls))

    type(get_prefs()).modes_dict = dict(mode_type__mode_id_cls_pair)


class UVPM4_OT_SetEnginePath(Operator, ImportHelper):

    bl_idname = 'uvpackmaster4.set_engine_path'
    bl_label = 'Set Engine Path'
    bl_description = 'Set a path to the UVPM engine'

    filename_ext = ".uvpmi"
    filter_glob : StringProperty(
        default="*.uvpmi",
        options={'HIDDEN'},
        )
    
    def execute(self, context):
        try:
            engine_path = os.path.abspath(os.path.dirname(self.filepath))
            register_engine(engine_path)
            self.report({'INFO'}, 'UVPM engine initialized. Save Blender preferences to make the path permanent')

        except RuntimeError as ex:
            print_backtrace_if_debug(ex)
            self.report({'ERROR'}, 'UVPM engine initialization failed: ' + str(ex))

        except Exception as ex:
            print_backtrace_if_debug(ex)
            self.report({'ERROR'}, 'UVPM initialization failed: Unexpected error')

        redraw_ui(context)

        return {'FINISHED'}
    
    def draw(self, context):
        pass

    def post_op(self):
        pass
    