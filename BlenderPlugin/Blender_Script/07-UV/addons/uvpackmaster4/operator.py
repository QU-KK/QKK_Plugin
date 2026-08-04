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


import subprocess
import queue
import threading
import tempfile
import time
import json
import io
import os


from .props import EngineSceneProps
from .utils import (print_backtrace_if_debug,
                    print_backtrace,
                    in_debug_mode,
                    redraw_ui,
                    get_engine_execpath,
                    process_file_path,
                    print_log)

from .pack_context import PackConfig, PackContext
from .connection import read_int_array, force_read_int, decode_string, connection_thread_func, send_finish_confirmation
from .os_iface import os_cancel_sig, os_engine_creation_flags
from .register_utils import check_engine, unregister_engine
from .overlay import EngineOverlayManager, TextOverlayParser
from .prefs_scripted_utils import SCRIPTED_PIPELINE_DIRNAME, ENGINE_PACKAGE_DIRNAME, EngineParams
from .log import LogManager
from .box_utils import disable_box_rendering, BoxRenderer, BoxInfoArrayRenderAccess

from .spipeline.engine.types import (UvpmMessageCode,
                                     JsonMessageCode,
                                     UvpmLogType,
                                     UvpmLogFlags,
                                     UvpmRetCode,
                                     UvpmPhaseCode,
                                     UvpmOpcode,
                                     OpFinishedException,
                                     OpAbortedException)

from .event import DefaultFinishConditionMixin, esc_press_event
from .out_island import OutIslands
from .scripting import UVPM4_Scripting, ScriptEvent
from .operator_generic import UVPM4_OT_GenericHandler
from .app_iface import *


class NoUvFaceError(Exception):
    pass


class NoUvFaceSelectedError(NoUvFaceError):
    
    def __init__(self, send_pinned):
        super().__init__('No UV face selected{}'.format(' (pinned UVs are ignored)' if send_pinned else ''))


class NoUvFaceVisibleError(NoUvFaceError):
    
    def __init__(self):
        super().__init__('No UV face visible')


class ModeIdAttrMixin:

    mode_id : StringProperty(name='mode_id', default='')


class OpConfirmationMsgMixin:

    def invoke(self, context, event):
        self._confirm_msg = self.confirmation_msg() if hasattr(self, 'confirmation_msg') else self.CONFIRMATION_MSG

        wm = context.window_manager
        pix_per_char = 5
        dialog_width = pix_per_char * len(self._confirm_msg) + 50
        return wm.invoke_props_dialog(self, width=dialog_width)

    def draw(self, context):
        layout = self.layout
        col = layout.column()
        col.label(text=self._confirm_msg)


class UVPM4_OT_Engine(UVPM4_OT_GenericHandler, DefaultFinishConditionMixin):

    bl_options = {'UNDO'}

    MODAL_INTERVAL_S = 0.1
    STATUS_INITIAL = 'Initialization'
    HINT_INITIAL = 'press ESC to cancel'

    HANG_HINT = '<t color="warning">(engine process not responding for a longer time - press ESC to abort or wait for the process to respond)</t>'

    TIP_COLOR = 'green'
    TIP_HEADER = '<t color="{}">TIP:</t>'.format(TIP_COLOR)

    TOPO_HANG_TIPS = ["if the hang occurs during topology analysis:",
                 " - ensure that no UV island exhibits severely corrupted topology"] +\
                [" - for very dense UV maps: go to the 'Preferences' multi panel, 'Expert Options' and enable 'High-Prec Topology Analysis'"]\
                    if AppInterface.HIGHPREC_TOPO_ANALYSIS_SUPPORTED else []

    TOPO_HANG_TIP_LOGGED = False

    interactive = False

    cancel_sig_sent = False
    _timer = None

    operation_done = False
    engine_proc = None
    curr_phase = None
    p_context = None
    ov_manager = None
    box_renderer = None
    engine_box_renderer = None
    show_region_hud_saved = None
    log_manager = None
    app_state = None


    @classmethod
    def poll(cls, context):
        prefs = get_prefs()
        return prefs.engine_initialized

    def log_tip(self, tip_msg):
        if not self.log_manager:
            return

        if self.prefs.disable_tips:
            return
        
        self.log_manager.log(UvpmLogType.INFO, "{} {}".format(self.TIP_HEADER, tip_msg), log_flags=UvpmLogFlags.PARSE)

    def log_tips(self, tip_msgs):
        for msg in tip_msgs:
            self.log_tip(msg)

    def check_engine_retcode(self, retcode):
        if retcode in {UvpmRetCode.SUCCESS,
                       UvpmRetCode.INVALID_ISLANDS,
                       UvpmRetCode.NO_SPACE,
                       UvpmRetCode.NO_SIUTABLE_DEVICE,
                       UvpmRetCode.INVALID_INPUT,
                       UvpmRetCode.WARNING}:
            return

        if retcode == UvpmRetCode.CANCELLED:
            self.log_manager.log(UvpmLogType.STATUS, 'Operation cancelled by the user')
            return

        raise RuntimeError('Engine process returned an error')

    def get_scenario_id(self):
        if hasattr(self, 'SCENARIO_ID'):
            return self.SCENARIO_ID
        
        mode = self.get_mode()

        if mode is not None and hasattr(mode, 'SCENARIO_ID'):
            return mode.SCENARIO_ID

        raise RuntimeError("Scenario id not found")

    def mode_method_std_call(self, default_impl, method_name):
        mode = self.get_mode()
        if mode is not None and hasattr(mode, method_name):
            method = getattr(mode, method_name)
            return method()

        return default_impl()

    def raise_unexpected_output_error(self):
        raise RuntimeError('Unexpected output from the engine process')

    def set_report(self, report_type, report_str):
        if self.isolated_execution() and report_type != 'ERROR':
            return

        self.report({report_type}, report_str)

    def get_box_renderer(self):
        return self.mode_method_std_call(lambda: None, 'get_box_renderer')
    
    def engine_box_renderer_enable(self):
        return self.mode_method_std_call(lambda: False, 'engine_box_renderer_enable')

    def get_iparam_serializers(self):
        return None
    
    def get_save_iparam_handler(self):
        return None
    
    def update_context_meshes(self):
        if self.p_context is not None:
            self.p_context.update_meshes()
            self.redraw_context_area()

    def exit_common(self):
        if self.p_context is not None:
            if self._timer is not None:
                wm = self.p_context.context.window_manager
                wm.event_timer_remove(self._timer)

        if self.ov_manager is not None:
            self.ov_manager.finish()

        for renderer in (self.box_renderer, self.engine_box_renderer):
            if renderer is None:
                continue

            renderer.finish()

        if self.show_region_hud_saved is not None:
            self.context.area.spaces.active.show_region_hud = self.show_region_hud_saved

        self.update_context_meshes()

    def read_islands(self, islands_msg):
        self.refresh_bmesh()

        islands = []
        set_sizes = read_int_array(islands_msg)
        flags = read_int_array(islands_msg)
        island_cnt = len(flags)

        for i in range(island_cnt):
            islands.append(read_int_array(islands_msg))

        self.p_context.set_islands(set_sizes, islands, flags)

    def redraw_context_area(self):
        if self.interactive:
            super().redraw_context_area()

    def post_operation(self):
        pass

    def require_selection(self):
        return True

    def finish_after_operation_done(self):
        return not self.interactive
    
    def use_default_operation_done_status(self):
        return self.log_manager.last_log(UvpmLogType.STATUS) is None

    def handle_operation_done(self):
        if in_debug_mode():
            print('UVPM operation time: ' + str(time.time() - self.start_time))

        self.refresh_bmesh()

        self.operation_done = True
        self.exec_scripts(ScriptEvent.AFTER_OP)

        send_finish_confirmation(self.engine_proc)

        try:
            wait_timeout = 3600
            self.engine_proc.wait(wait_timeout)
        except:
            raise RuntimeError('The engine process wait timeout reached')

        self.connection_thread.join()

        engine_retcode = self.engine_proc.returncode
        self.prefs.engine_retcode = engine_retcode
        self.log_manager.log_engine_retcode(engine_retcode)
        self.check_engine_retcode(engine_retcode)

        if not self.p_context.islands_received():
            self.raise_unexpected_output_error()

        self.post_operation()

        if self.finish_after_operation_done():
            raise OpFinishedException()

        if self.use_default_operation_done_status():
            if self.log_manager.type_logged(UvpmLogType.ERROR):
                status_msg = 'Errors were reported'
            elif self.log_manager.type_logged(UvpmLogType.WARNING):
                status_msg = 'Warnings were reported'
            else:
                status_msg = 'Done'
        
            self.log_manager.log(UvpmLogType.STATUS, status_msg)

        hint_str = self.operation_done_hint()
        if hint_str is not None:
            self.log_manager.log(UvpmLogType.HINT, hint_str)

        if self.ov_manager is not None:
            self.ov_manager.print_dev_progress = False
            self.redraw_context_area()

    def finish_op(self, context):
        self.post_main()
        self.exit_common()
        return {'FINISHED', 'PASS_THROUGH'}

    def cancel_op(self, context):
        if self.engine_proc is not None:
            self.engine_proc.terminate()

        self.exit_common()
        return {'FINISHED'}

    def handle_engine_msg_spec(self, msg_code, msg):
        return False

    def handle_event_spec(self, event):
        return False

    def handle_out_islands_msg(self, out_islands_msg):
        self.refresh_bmesh()
        out_islands = OutIslands(out_islands_msg)
        self.p_context.apply_out_islands(out_islands, self.get_save_iparam_handler())

        if self.interactive:
            self.update_context_meshes()

    def handle_benchmark_msg(self, benchmark_msg):
        entry_count = force_read_int(benchmark_msg)

        for i in range(entry_count):
            dev_id = decode_string(benchmark_msg)
            dev_found = False

            for dev in self.prefs.device_array():
                if dev.id == dev_id:
                    dev_found = True
                    bench_entry = dev.bench_entry
                    bench_entry.decode(benchmark_msg)
                    break

            if not dev_found:
                self.raise_unexpected_output_error()

        self.redraw_context_area()

    def handle_log_msg(self, log_msg):
        log_type = force_read_int(log_msg)
        log_string = decode_string(log_msg)
        log_flags = force_read_int(log_msg)

        self.log_manager.log(log_type, log_string, log_flags)

    def handle_box_render_info_msg(self, payload):
        if not self.interactive:
            return

        if self.engine_box_renderer is None:
            raise RuntimeError('Box renderer not available')
        
        from .spipeline.engine.json import JsonBoxRenderInfoPayload
        payload_obj = JsonBoxRenderInfoPayload.from_engine_param(payload)
        access = BoxInfoArrayRenderAccess(payload_obj.box_info_array)
        self.engine_box_renderer.update_box_access(access)

    def handle_json_msg(self, json_msg):
        json_str = decode_string(json_msg)
        json_obj = json.loads(json_str)
        code = json_obj['code']
        payload = json_obj['payload']

        if code == JsonMessageCode.BOX_RENDER_INFO:
            self.handle_box_render_info_msg(payload)

        else:
            self.raise_unexpected_output_error()

    def handle_engine_msg(self, msg):
        msg_code = force_read_int(msg)

        if self.handle_engine_msg_spec(msg_code, msg):
            return

        if msg_code == UvpmMessageCode.PHASE:
            self.curr_phase = force_read_int(msg)

            # Inform the upper layer whether it should finish
            if self.curr_phase == UvpmPhaseCode.DONE:
                self.handle_operation_done()

        elif msg_code == UvpmMessageCode.ISLANDS:
            self.read_islands(msg)

        elif msg_code == UvpmMessageCode.OUT_ISLANDS:
            self.handle_out_islands_msg(msg)

        elif msg_code == UvpmMessageCode.BENCHMARK:
            self.handle_benchmark_msg(msg)

        elif msg_code == UvpmMessageCode.LOG:
            self.handle_log_msg(msg)

        elif msg_code == UvpmMessageCode.JSON:
            self.handle_json_msg(msg)

        else:
            self.raise_unexpected_output_error()

    def refresh_bmesh(self):
        if self.p_context:
            self.p_context.refresh_bmesh()

    def topology_analysis_in_progress(self):
        last_log = self.log_manager.last_log(UvpmLogType.STATUS)
        return last_log is not None and last_log.startswith('Topology analysis')

    def enter_hang_mode(self):
        if self.hang_detected:
            return

        self.hang_detected = True
        self.hang_saved_logs = (self.log_manager.last_log(UvpmLogType.HINT))
        self.log_manager.log(UvpmLogType.HINT, TextOverlayParser.parse_text(self.HANG_HINT))

        if not self.TOPO_HANG_TIP_LOGGED and self.topology_analysis_in_progress():
            self.TOPO_HANG_TIP_LOGGED = True
            self.log_tips(self.TOPO_HANG_TIPS)
        
    def quit_hang_mode(self):
        if not self.hang_detected:
            return

        self.hang_detected = False
        saved_hint = self.hang_saved_logs

        self.log_manager.log(UvpmLogType.HINT, saved_hint)

    def handle_communication(self):
        if self.operation_done:
            return

        msg_received = 0
        while True:
            try:
                item = self.progress_queue.get_nowait()
            except queue.Empty as ex:
                break

            if isinstance(item, str):
                raise RuntimeError(item)
            elif isinstance(item, io.BytesIO):
                self.quit_hang_mode()
                self.handle_engine_msg(item)

            else:
                raise RuntimeError('Unexpected output from the connection thread')
            
            msg_received += 1

        curr_time = time.time()

        if msg_received > 0:
            self.last_msg_time = curr_time
        else:
            if self.curr_phase != UvpmPhaseCode.STOPPED and curr_time - self.last_msg_time > self.hang_timeout:
                self.enter_hang_mode()

    def handle_event(self, event):
        # Kill the UVPM process unconditionally if a hang was detected
        if self.hang_detected and event.type == 'ESC':
            raise OpAbortedException()

        if self.handle_event_spec(event):
            return

        if self.operation_done and (self.operation_num != self.prefs.operation_counter or self.operation_done_finish_condition(event)):
            raise OpFinishedException()
        
        for renderer in (self.box_renderer, self.engine_box_renderer):
            if renderer is None:
                continue

            try:
                if renderer.coords_update_needed(event):
                    renderer.update_coords()

            except Exception as ex:
                print_backtrace_if_debug(ex)
                raise OpFinishedException()

        # Generic event processing code
        if event.type == 'ESC':
            if not self.cancel_sig_sent:
                self.engine_proc.send_signal(os_cancel_sig())
                self.cancel_sig_sent = True

        elif event.type == 'TIMER':
            self.handle_communication()

    def modal_ret_value(self, event):
        if self.operation_done:
            return {'PASS_THROUGH'}

        if event.type in {'MIDDLEMOUSE','WHEELDOWNMOUSE', 'WHEELUPMOUSE'}:
            return {'PASS_THROUGH'}

        return {'RUNNING_MODAL'}

    def modal_internal(self, context, event):
        cancel = False
        finish = False

        try:
            if self.context.mode != 'EDIT_MESH':
                if self.operation_done:
                    raise OpFinishedException()

                raise RuntimeError('Edit Mode exited - operation cancelled')

            self.handle_event(event)

            # Check whether the uvpm process is alive
            if not self.operation_done and self.engine_proc.poll() is not None:
                # It should not be required to but check once again to be on the safe side
                self.handle_communication()

                if not self.operation_done:
                    raise RuntimeError('Engine process died unexpectedly')

        except OpFinishedException:
            finish = True

        except OpAbortedException:
            self.prefs.engine_retcode = UvpmRetCode.ABORTED
            self.set_report('INFO', 'Engine process killed')
            cancel = True

        except RuntimeError as ex:
            if in_debug_mode():
                print_backtrace(ex)

            self.prefs.engine_retcode = UvpmRetCode.FATAL_ERROR
            self.set_report('ERROR', str(ex))
            cancel = True

        except Exception as ex:
            self.handle_unexpected_error(ex)

            self.prefs.engine_retcode = UvpmRetCode.FATAL_ERROR
            cancel = True

        if cancel:
            return self.cancel_op(context)

        if finish:
            return self.finish_op(context)

        return self.modal_ret_value(event)

    def modal(self, context, event):
        try:
            return self.modal_internal(context, event)

        except Exception as ex:
            self.handle_unexpected_error(ex)
            self.prefs.engine_retcode = UvpmRetCode.FATAL_ERROR

        return {'FINISHED'}

    def pre_main(self):
        pass

    def post_main(self):
        pass

    def pre_operation(self):
        mode = self.get_mode()
        if mode is not None:
            self.mode.pre_operation(self)

    def validate_operation(self):
        return self.mode_method_std_call(lambda: None, 'validate_operation')

    def scenario_in_progress(self):
        return self.engine_proc is not None

    def isolated_execution(self):
        return False
    
    def get_script_container_id(self):
        return self.mode_method_std_call(lambda: None, 'get_script_container_id')
    
    def exec_scripts(self, s_event):
        container_id = self.get_script_container_id()
        if not container_id:
            return
        
        UVPM4_Scripting.exec_scripts(self.context, s_event, container_id)

    def execute_scenario(self, scenario_id):
        if not check_engine():
            unregister_engine()
            redraw_ui(self.context)
            raise RuntimeError("UVPM engine broken")
        
        self.scenario_id = scenario_id

        self.exec_scripts(ScriptEvent.BEFORE_OP)
        self.prefs.reset_stats()

        self.p_context = PackContext(self.context, _mode=self.get_mode(),  _only_with_selected_faces=self.only_with_selected_faces())
        self.pre_operation()

        p_config = PackConfig()
        p_config.send_unselected_islands = self.send_unselected_islands()
        p_config.send_pinned_islands = self.send_pinned_islands()
        p_config.send_verts_3d = self.send_verts_3d()
        p_config.send_verts_3d_global = self.send_verts_3d_global()
        p_config.iparam_serializers = self.get_iparam_serializers()
        p_config.engine_params = self.setup_engine_params()

        self.p_context.init_config(p_config)

        self.validate_operation()

        serialized_maps, selected_count =\
            self.p_context.serialize_uv_maps()
        
        if self.require_selection():
            if selected_count == 0:
                raise NoUvFaceSelectedError(self.p_context.config.send_pinned_islands)
        
        else:
            if self.p_context.total_visible_faces_stored_count == 0:
                raise NoUvFaceVisibleError()

        engine_args_final = [get_engine_execpath(), '-E']
        engine_args_final += ['-o', str(UvpmOpcode.EXECUTE_SCENARIO)]
        engine_args_final += ['-t', str(self.prefs.thread_count)]
        engine_args_final += ['-b', str(os.getpid())]
        engine_args_final += self.prefs.get_engine_args()

        if self.prefs.orient_aware_uv_islands:
            engine_args_final.append('-e')

        if self.packing_operation():
            engine_args_final.append('-p')
        
        if self.p_context.topo_analysis_config.uv_connect_limit is not None:
            engine_args_final += ['-c', str(self.p_context.topo_analysis_config.uv_connect_limit)]

        if in_debug_mode():
            if self.prefs.seed > 0:
                engine_args_final += ['-S', str(self.prefs.seed)]

            if self.prefs.wait_for_debugger:
                engine_args_final.append('-G')

            engine_args_final += ['-T', str(self.prefs.test_param)]
            print('Pakcer args: ' + ' '.join(x for x in engine_args_final))
        
        # --- Setup engine params ---
        engine_params = self.p_context.config.engine_params
        engine_params.add_device_settings(self.prefs.device_array())

        engine_params['__skip_topology_parsing'] = self.skip_topology_parsing()
        engine_params['__disable_immediate_uv_update'] = self.scene_props.disable_immediate_uv_update
        engine_params['__disable_tips'] = self.prefs.disable_tips

        if in_debug_mode():
            engine_params['__test_param'] = self.prefs.test_param
        
        engine_pkg_dirpath = os.path.join(os.path.abspath(os.path.dirname(process_file_path(__file__))), SCRIPTED_PIPELINE_DIRNAME, ENGINE_PACKAGE_DIRNAME, '__init__.py')
        engine_params['__engine_package_path'] = engine_pkg_dirpath
        engine_params['__scenario_id'] = scenario_id

        out_data = engine_params.serialize()
        out_data += serialized_maps

        if self.prefs.write_to_file:
            out_filepath = os.path.join(tempfile.gettempdir(), 'uv_islands.data')
            out_file = open(out_filepath, 'wb')
            out_file.write(out_data)
            out_file.close()

        creation_flags = os_engine_creation_flags()
        popen_args = dict()

        if creation_flags is not None:
            popen_args['creationflags'] = creation_flags

        self.engine_proc = subprocess.Popen(engine_args_final,
                                            stdin=subprocess.PIPE,
                                            stdout=subprocess.PIPE,
                                            **popen_args)

        out_stream = self.engine_proc.stdin
        out_stream.write(out_data)
        out_stream.flush()

        self.start_time = time.time()

        self.last_msg_time = self.start_time
        self.hang_detected = False
        self.hang_timeout = 10.0

        # Start progress monitor thread
        self.progress_queue = queue.Queue()
        self.connection_thread = threading.Thread(target=connection_thread_func,
                                                    args=(self.engine_proc.stdout, self.progress_queue))
        self.connection_thread.daemon = True
        self.connection_thread.start()
        self.progress_array = [0]
        self.progress_msg = ''
        self.progress_sec_left = -1
        self.progress_iter_done = -1
        self.progress_last_update_time = 0.0

        if self.interactive:
            ov_dev_array = self.prefs.dev_array if self.packing_operation() else None
            self.ov_manager = EngineOverlayManager(self, ov_dev_array, self.p_context)
            self.box_renderer = self.get_box_renderer()
            self.engine_box_renderer = BoxRenderer(self.context, None) if self.engine_box_renderer_enable() else None

    def execute_internal(self, context):
        cancel = False
        self.scene_props = get_scene_props(context)
        self.e_scene_props = EngineSceneProps(context)
        self.app_state = AppState(context)

        self.operation_num = self.prefs.operation_counter + 1
        self.prefs.operation_counter += 1

        if not self.isolated_execution():
            # Disable any box rendering if active
            disable_box_rendering(None, context)

        if self.interactive and self.context.area.spaces.active.show_region_hud:
            self.show_region_hud_saved = self.context.area.spaces.active.show_region_hud
            self.context.area.spaces.active.show_region_hud = False

        try:
            def post_log_op(log_type, log_str):
                if in_debug_mode():
                    print_log(log_str)

                self.redraw_context_area()

            self.log_manager = LogManager(post_log_op)
            self.log_manager.log(UvpmLogType.STATUS, self.STATUS_INITIAL)
            self.log_manager.log(UvpmLogType.HINT, self.HINT_INITIAL)

            self.pre_main()

            scenario_id = self.get_scenario_id()
            if scenario_id is not None:
                self.execute_scenario(scenario_id)

        except NoUvFaceError as ex:
            self.prefs.engine_retcode = UvpmRetCode.WARNING
            self.set_report('WARNING', str(ex))

        except RuntimeError as ex:
            print_backtrace_if_debug(ex)

            self.prefs.engine_retcode = UvpmRetCode.FATAL_ERROR
            self.set_report('ERROR', str(ex))
            cancel = True
            
        except Exception as ex:
            self.handle_unexpected_error(ex)

            self.prefs.engine_retcode = UvpmRetCode.FATAL_ERROR
            cancel = True

        if cancel:
            return self.cancel_op(context)

        try:
            if self.scenario_in_progress():
                if self.interactive:
                    wm = context.window_manager
                    self._timer = wm.event_timer_add(self.MODAL_INTERVAL_S, window=context.window)
                    wm.modal_handler_add(self)
                    return {'RUNNING_MODAL'}

                class FakeTimerEvent:
                    def __init__(self):
                        self.type = 'TIMER'
                        self.value = 'NOTHING'
                        self.ctrl = False

                while True:
                    event = FakeTimerEvent()

                    ret = self.modal(context, event)
                    if ret.intersection({'FINISHED', 'CANCELLED'}):
                        return ret

                    time.sleep(self.MODAL_INTERVAL_S)
            else:
                self.post_main()

        except RuntimeError as ex:
            print_backtrace_if_debug(ex)

            self.prefs.engine_retcode = UvpmRetCode.FATAL_ERROR
            self.set_report('ERROR', str(ex))
            
        except Exception as ex:
            self.handle_unexpected_error(ex)
            self.prefs.engine_retcode = UvpmRetCode.FATAL_ERROR

        return {'FINISHED'}

    def execute_impl(self, context):
        try:
            self.prefs.engine_retcode = UvpmRetCode.NOT_SET
            return self.execute_internal(context)

        except RuntimeError as ex:
            if in_debug_mode():
                print_backtrace(ex)

            self.prefs.engine_retcode = UvpmRetCode.FATAL_ERROR
            self.set_report('ERROR', str(ex))

        except Exception as ex:
            self.handle_unexpected_error(ex)
            self.prefs.engine_retcode = UvpmRetCode.FATAL_ERROR

        return {'FINISHED'}

    def invoke(self, context, event):
        if not self.isolated_execution():
            self.interactive = True

        if hasattr(self, 'draw'):
            kwargs = {}
            if hasattr(self, 'props_dialog_width'):
                kwargs['width'] = self.props_dialog_width()

            return context.window_manager.invoke_props_dialog(self, **kwargs)
            
        return self.execute(context)

    def send_unselected_islands(self):
        return self.mode_method_std_call(lambda: False, 'send_unselected_islands')
    
    def only_with_selected_faces(self):
        return not self.send_unselected_islands()
    
    def send_pinned_islands(self):
        return None

    def get_grouping_config(self):
        return None

    def skip_topology_parsing(self):
        return self.mode_method_std_call(lambda: False, 'skip_topology_parsing')

    def setup_engine_params(self):
        def op_based_setup():
            params = EngineParams()
            from .spipeline.engine.scenario import get_scenario_annotations
            from .spipeline.engine.param import EngineParamUtils
            EngineParamUtils.to_params(self, get_scenario_annotations(self.scenario_id), params)

            return params
        
        return self.mode_method_std_call(op_based_setup, 'setup_engine_params')

    def packing_operation(self):
        return self.mode_method_std_call(lambda: False, 'packing_operation')

    def send_verts_3d(self):
        return None

    def send_verts_3d_global(self):
        return None



class UVPM4_OT_ScaleIslands(UVPM4_OT_GenericHandler):

    bl_options = {'UNDO'}

    @classmethod
    def poll(cls, context):
        return context.active_object is not None and context.active_object.mode == 'EDIT'

    def execute_impl(self, context):
        self.app_state = AppState(context)
        self.p_context = PackContext(context)
        self.p_context.scale_selected_faces(self.get_scale_factors())

        self.p_context.update_meshes()
        return {'FINISHED'}

    def get_scale_factors(self):
        return (1.0, 1.0)


class UVPM4_OT_AdjustIslandsToTexture(UVPM4_OT_ScaleIslands):

    bl_idname = 'uvpackmaster4.uv_adjust_islands_to_texture'
    bl_label = 'Adjust Islands To Texture'
    bl_description = "Adjust scale of selected islands so they are suitable for packing into the active texture. CAUTION: this operator should be used only when packing to a non-square texture. For for info regarding non-square packing click the help icon"

    def get_scale_factors(self):
        return (1.0 / self.app_state.active_image_ratio(), 1.0)


class UVPM4_OT_UndoIslandsAdjustmentToTexture(UVPM4_OT_ScaleIslands):

    bl_idname = 'uvpackmaster4.uv_undo_islands_adjustment_to_texture'
    bl_label = 'Undo Islands Adjustment'
    bl_description = "Undo adjustment performed by the 'Adjust Islands To Texture' operator so islands are again suitable for packing into a square texture. For for info regarding non-square packing read the documentation"

    def get_scale_factors(self):
        return (self.app_state.active_image_ratio(), 1.0)


class UVPM4_OT_ModalStateMachine(UVPM4_OT_GenericHandler):

    MODAL_INTERVAL_S = 0.01
    _timer = None
    _state_dict = {}
    _curr_state = None
    _state_set_time = None


    def register_state(self, state, handler):
        self._state_dict[state] = handler
        if self._curr_state is None:
            self.__set_state(state)

    def __set_state(self, state):
        if state != self._curr_state:
            self._state_set_time = time.time()
            self._curr_state = state

    def state_time(self):
        assert self._state_set_time is not None
        return time.time() - self._state_set_time

    def modal_ret_value(self, event):
        if event.type in {'MIDDLEMOUSE','WHEELDOWNMOUSE', 'WHEELUPMOUSE'}:
            return {'PASS_THROUGH'}

        return {'RUNNING_MODAL'}

    def modal(self, context, event):
        try:
            esc_state = None

            if esc_press_event(event):
                esc_state = self.handle_esc()
    
            if esc_state is None:
                self.__set_state(self._state_dict[self._curr_state](event))

            else:
                self.__set_state(esc_state)

            if self._curr_state is None:
                raise OpFinishedException()
            
            return self.modal_ret_value(event)
        
        except OpFinishedException:
            pass
        
        except Exception as ex:
            self.handle_unexpected_error(ex)

        return self.exit_common()

    def exit_common(self):
        self.handle_exit()

        if self._timer is not None:
            wm = self.context.window_manager
            wm.event_timer_remove(self._timer)

        return {'FINISHED'}

    def execute_impl(self, context):
        self.prefs = get_prefs()
        self.scene_props = get_scene_props(context)
        self.context = context

        wm = context.window_manager
        self._timer = wm.event_timer_add(self.MODAL_INTERVAL_S, window=context.window)
        wm.modal_handler_add(self)

        return self.execute_impl2(context)
