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

import struct

from ..app_iface import *
from ..log import LogManager
from ..spipeline.engine.types import UvpmLogType, PackOpType, UvpmRetCode, RETCODE_METADATA, OperationStatus, UvpmLogFlags
from ..utils import lower_first, CollectionPropertyDictWrapper
from ..overlay import EngineOverlayManager
from ..operator import UVPM4_OT_ModalStateMachine, UVPM4_OT_Engine
from ..event import EscPressFinishConditionMixin, space_press_event
from ..geom import UvMapView
from ..id_collection.main_props import MainPropSetAccess
from ..spipeline.operators.pack_operator import UVPM4_OT_Pack

from .props import get_uvpm4_props, is_valid_obj, UvMapRepackCollectionAccess
from .cluster import RepackClusterAccess


def _format_object_name(name):
    return '<t color=\"green\">{}</t>'.format(name)     
 

def _format_map_name(name):
    return '<t color=\"white\">{}</t>'.format(name)     


class ObjectToRepack:

    def __init__(self, op, obj, uv_data):
        self.__obj = obj
        self.op = op
        self.uv_data = uv_data
        self.repack_props = get_uvpm4_props(self.__obj).repack_props

        self.mesh = self.__obj.data
        self.mesh_props = get_uvpm4_props(self.mesh)
        uv_hash_array = CollectionPropertyDictWrapper(self.mesh_props.uv_hash_array, 'name', None)
        self.hash_entry = uv_hash_array[uv_data.name]

        try:
            self.main_props = get_main_props(self.op.context, main_props_uuid=uv_data.main_prop_access_desc.active_item_uuid)

        except AttributeError:
            self.main_props = None

    def get(self):
        return self.__obj
    
    def select(self):
        self.get().select_set(True)
        self.mesh.uv_layers.active = self.mesh.uv_layers[self.uv_data.name]
        uv_name = self.uv_map_name
            
        uv_view = UvMapView(self.op.context, self.get(), uv_name)
        has_hidden = uv_view.select_all(True)
        uv_view.commit()

        return has_hidden
    
    @property
    def name(self):
        return self.get().name
    
    @property
    def uv_map_id(self):
        return (self.mesh.name, self.uv_map_name)
    
    @property
    def uv_map_name(self):
        return self.uv_data.name
    
    def __str__(self):    
        return "{} [{}]".format(_format_object_name(self.name), _format_map_name(self.uv_map_name))
    

class TrivialCluster:

    HASH_VERSION = 1

    def __init__(self, op, obj=None):
        self.op = op
        self._objects = []

        if obj:
            self._objects.append(obj)

    def append(self, obj):
        self._objects.append(obj)

    def hidden(self):
        return any(not obj.get().visible_get() for obj in self._objects)
    
    @property
    def main_props(self):
        assert len(self._objects) == 1
        return self._objects[0].main_props
    
    @property
    def hash_entry(self):
        assert len(self._objects) == 1
        return self._objects[0].hash_entry
    
    @property
    def force_repack(self):
        return any(obj.repack_props.force_repack for obj in self._objects)
    
    def pre_repack(self):
        pass

    def select(self):
        has_hidden = False

        for obj in self._objects:
            has_hidden != obj.select()

        self.op.context.view_layer.objects.active = self._objects[0].get() if len(self._objects) > 0 else None

        return has_hidden
    
    def calc_uv_hash(self, select):
        import hashlib
        from ..pack_context import PackContext, PackConfig

        has_hidden = None

        if select:
            has_hidden = self.select()

        mode = self.op.prefs.get_mode(self.main_props.active_pack_mode_id, self.op.context, auto_repack=True)
        context = self.op.context

        class TmpOperator:
            def __init__(self):
                self.p_context = PackContext(context, _mode=mode)
            
            def get_scenario_id(self):
                return mode.SCENARIO_ID

        op = TmpOperator()
        mode.pre_operation(op)

        config = PackConfig()
        op.p_context.init_config(config)

        to_hash = struct.pack('i', self.HASH_VERSION)
        to_hash += op.p_context.config.engine_params.serialize()
        to_hash += op.p_context.serialize_uv_maps()[0]

        return hashlib.sha256(to_hash).hexdigest(), has_hidden
    
    @property
    def main_props_name(self):
        return self.main_props.name if self.main_props else ''
    
    @property
    def main_props_str_suffix(self):
        return ' (<t color=\"(0.0, 1.0, 1.0)\">{}</t>)'.format(self.main_props_name) if self.main_props_name else ''
    
    def __str__(self):
        assert len(self._objects) == 1
        return "Object {}{}".format(str(self._objects[0]), self.main_props_str_suffix)


class ErrorCluster(TrivialCluster):

    def __init__(self, op, obj, error_msg):
        super().__init__(op, obj)
        self.error_msg = error_msg

    def pre_repack(self):
        super().pre_repack()
        raise RuntimeError(self.error_msg)
    
    @property
    def main_props(self):
        return None


class RepackCluster(TrivialCluster):

    def __init__(self, op, cluster_item):
        super().__init__(op)
        self.cluster_item = cluster_item

        try:
            self.__main_props = get_main_props(self.op.context, main_props_uuid=self.cluster_item.main_prop_access_desc.active_item_uuid)

        except AttributeError:
            self.__main_props = None

    def pre_repack(self):
        super().pre_repack()
        obj_names = set()
        uv_maps = set()

        for obj in self._objects:
            if obj.get().name in obj_names:
                raise RuntimeError('Object added to the cluster twice: {}'.format(obj.get().name))
            
            obj_names.add(obj.get().name)

            uv_map = obj.uv_map_id
            if uv_map in uv_maps:
                raise RuntimeError('Map added to the cluster twice: {}'.format(obj.uv_map_name))
            
            uv_maps.add(uv_map)

    @property
    def main_props(self):
        return self.__main_props
    
    @property
    def hash_entry(self):
        return self.cluster_item.uv_hash
    
    def __str__(self):
        assert len(self._objects) > 0
        name_formatted = '<t color=\"yellow\">{}</t>'.format(self.cluster_item.name)
        return 'Cluster {} &lt{}&gt{}'.format(name_formatted, '; '.join(str(obj) for obj in self._objects), self.main_props_str_suffix)


class UVPM4_OT_AutoRepack(UVPM4_OT_ModalStateMachine, EscPressFinishConditionMixin):

    bl_idname = 'uvpackmaster4.auto_repack'
    bl_label = 'Auto Repack'
    bl_description = 'Repack all objects and UV maps configured for the process. Press the Help button to learn more'
    bl_options = {'UNDO'}

    RETCODE_DESC_OVERRIDE = {
        UvpmRetCode.SUCCESS: 'Repacked successfully'
    }

    SHOW_TIME = 0
    ov_manager = None
    cluster_to_process = None
    last_processed_cluster = None


    class State:
        GET_CLUSTER = 0
        REPACK = 1
        SHOW = 2
        OP_DONE = 3

    @classmethod
    def poll(cls, context):
        return UVPM4_OT_Pack.poll(context)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.register_state(self.State.GET_CLUSTER, self.get_cluster_handler)
        self.register_state(self.State.REPACK, self.repack_handler)
        self.register_state(self.State.SHOW, self.show_handler)
        self.register_state(self.State.OP_DONE, self.op_done_handler)
        
    def get_cluster_handler(self, event):
        self.log_manager.op_status = None

        if len(self.__clusters_to_process) > 0:
            self.cluster_to_process = self.__clusters_to_process[0]
            del self.__clusters_to_process[0]

            self.log_cluster(self.cluster_to_process, UvpmLogType.STATUS, "Repacking")
            return self.State.REPACK
        
        return self.handle_esc()
    
    def repack_handler(self, event):
        assert self.cluster_to_process
        cluster_to_process = self.cluster_to_process
        self.cluster_to_process = None
        self.last_processed_cluster = cluster_to_process
        op_status = self.repack_cluster(cluster_to_process)
        self.log_manager.op_status = op_status

        return self.State.SHOW if self.show_result else self.State.GET_CLUSTER
    
    def show_handler(self, event):
        if space_press_event(event) or (self.SHOW_TIME > 0 and self.state_time() > self.SHOW_TIME):
            bpy.ops.object.mode_set(mode='OBJECT')
            return self.State.GET_CLUSTER
        
        if self.context.mode != 'EDIT':
            self.log_cluster(self.last_processed_cluster, UvpmLogType.STATUS, "showing result - press SPACE to continue")
            bpy.ops.object.mode_set(mode='EDIT')
        
        return self.State.SHOW
    
    def op_done_handler(self, event):
        if self.operation_done_finish_condition(event):
            return None
        
        return self.State.OP_DONE
    
    def all_clusters_processed(self):
        return len(self.__clusters_to_process) == 0 and self.cluster_to_process is None
    
    def handle_esc(self):
        if self._curr_state == self.State.OP_DONE:
            return None
        
        bpy.ops.object.mode_set(mode='OBJECT')
        cancelled = not self.all_clusters_processed()

        self.log_manager.op_status_from_last_logged = True
        self.log_manager.log(UvpmLogType.STATUS, 'Repacking cancelled' if cancelled else 'Repacking done')
        self.log_manager.log(UvpmLogType.HINT, self.operation_done_hint())
        
        return self.State.OP_DONE
    
    def handle_exit(self):
        if self.ov_manager is not None:
            self.ov_manager.finish()

        self.redraw_context_area()

    def log_cluster(self, cluster, log_type, log_str):
        self.log_manager.log(log_type, '{}: {}'.format(cluster, lower_first(log_str)), log_flags=UvpmLogFlags.PARSE)
    
    def repack_cluster(self, cluster : TrivialCluster):
        bpy.ops.object.select_all(action='DESELECT')
        
        if cluster.hidden():
            self.log_cluster(cluster, UvpmLogType.WARNING, 'object hidden - skipping')
            return OperationStatus.WARNING

        op_status = OperationStatus.ERROR
        cluster.select()

        try:
            bpy.ops.object.mode_set(mode='EDIT')
            cluster.pre_repack()

            if cluster.main_props is None:
                raise RuntimeError('Option set not selected')
            
            if cluster.main_props.uuid:
                self.main_prop_access.set_active_item_uuid(cluster.main_props.uuid)

            curr_hash, has_hidden = cluster.calc_uv_hash(select=True)
            force_repack = self.repack_props.force_repack or cluster.force_repack
            hash_entry = cluster.hash_entry

            if (not force_repack) and hash_entry.hash == curr_hash:
                self.log_cluster(cluster, UvpmLogType.INFO, 'Up to date - skipping')
                return OperationStatus.CORRECT
            
            repacking_forced = hash_entry.hash == curr_hash

            mode_id = UVPM4_OT_Engine.ACTIVE_META_VALUE
            pack_op_type = PackOpType.PACK.value()

            bpy.ops.uvpackmaster4.pack(mode_id=mode_id, pack_op_type=pack_op_type, auto_repack=True)

            engine_retcode = self.prefs.engine_retcode
            ret_metadata = RETCODE_METADATA[engine_retcode]
            op_status = ret_metadata.op_status

            log_str = self.RETCODE_DESC_OVERRIDE.get(engine_retcode)
            if not log_str:
                log_str = ret_metadata.desc

            if op_status is None or not log_str:
                raise RuntimeError('Incorrect operation status')
            
            if has_hidden:
                op_status = min(OperationStatus.WARNING, op_status)
                log_str += ' (hidden UVs not packed)'

            log_type = LogManager.OPSTATUS_TO_LOGTYPE[op_status]

            if repacking_forced and hash_entry.hash == curr_hash:
                log_str += ' ({})'.format(EngineOverlayManager.format_string(OperationStatus.WARNING, 'repacking forced'))

            self.log_cluster(cluster, log_type, log_str)

            if op_status != OperationStatus.ERROR:
                hash_entry.hash, __not_used = cluster.calc_uv_hash(select=False)

        except RuntimeError as err:
            self.log_cluster(cluster, UvpmLogType.ERROR, str(err))
            op_status = OperationStatus.ERROR

        finally:
            bpy.ops.object.mode_set(mode='OBJECT')

        return op_status
    
    def __get_cluster(self, cluster_item):
        cluster = self.__cluster_dict.get(cluster_item.uuid)

        if cluster is None:
            cluster = RepackCluster(self, cluster_item)
            self.__clusters_to_process.append(cluster)
            self.__cluster_dict[cluster_item.uuid] = cluster

        return cluster
    
    def execute_impl2(self, context):
        bpy.ops.object.mode_set(mode='OBJECT')

        self.repack_props = self.scene_props.repack_props
        self.show_result = self.repack_props.show_results
        self.main_prop_access = MainPropSetAccess(self.context)
        self.cluster_access = RepackClusterAccess(self.context)

        def post_log_op(log_type, log_str):
            self.redraw_context_area()

        self.log_manager = LogManager(post_log_op, info_max_log_count=0, op_status_from_last_logged=False)
        self.log_manager.log(UvpmLogType.STATUS, "Initialization")
        self.log_manager.log(UvpmLogType.HINT, "Press ESC to cancel")

        self.ov_manager = EngineOverlayManager(self, None, None)
        self.__clusters_to_process = []
        self.__cluster_dict = {}
        uv_maps = {}
        
        for obj in bpy.data.objects:
            if not is_valid_obj(obj, accept_hidden=True):
                continue

            obj_props = get_uvpm4_props(obj)
            if not obj_props.repack_props.repack_enable:
                continue

            uv_access = UvMapRepackCollectionAccess(self.context, obj.name)

            for uv_data in uv_access.entries():
                obj_to_repack = ObjectToRepack(self, obj, uv_data)

                uv_map_id = obj_to_repack.uv_map_id

                obj_name = uv_maps.get(uv_map_id)
                if obj_name is not None:
                    self.__clusters_to_process.append(
                        ErrorCluster(self, obj_to_repack,
                                     error_msg='Map already configured for repack using another object: {}'.format(_format_object_name(obj_name))))
                    continue

                uv_maps[uv_map_id] = obj_to_repack.name
                
                if uv_data.add_to_cluster:
                    cluster_item = self.cluster_access.get_item_by_uuid(uv_data.repack_cluster_access_desc.active_item_uuid)

                    if cluster_item is None:
                        self.__clusters_to_process.append(ErrorCluster(self, obj_to_repack, error_msg='Map not added to a cluster'))

                    else:
                        cluster = self.__get_cluster(cluster_item)
                        cluster.append(obj_to_repack)

                else:
                    self.__clusters_to_process.append(TrivialCluster(self, obj_to_repack))

        return {'RUNNING_MODAL'}
    