
import time

from ..uc_entry import uc
from ..geom.box import Box
from ..geom import PACK_RATIO
from ..utils import area_to_string, rgb_to_rgba, eprint
from ..box_utils import BoxRenderInfo
from ..json import JsonUtils


class StageMetadata:

    def __init__(self, name, color):
        self.name = name
        self.color = color


class DynamicTilesConfig:

    start_tile : tuple[int, int] = None
    tile_step : tuple[int, int] = None
    tiles_in_row : int = None

    def __init__(self, start_tile=None, tile_step=None, tiles_in_row=None):
        self.start_tile = start_tile
        self.tile_step = tile_step
        self.tiles_in_row = tiles_in_row


def pack_manager_result_handler(self, task, result):
    self.result_handler(task, result)


class ResultHandlerSharedData:

    def __init__(self):
        self.boxes_used = []


class ResultHandler:

    dirty = False
    target_boxes_dirty = False
    _result = None

    def __init__(self, task_data):
        self.task_data = task_data

    @property
    def is_cancelled(self):
        return self.ret_code == uc.RetCode.CANCELLED
    
    @property
    def result(self):
        return self.task_data.task.result if self._result is None else self._result

    @property
    def is_set(self):
        return self.result is not None

    @property
    def ret_code(self):
        return self.result.ret_code
    
    @property
    def non_packed_islands(self):
        return self.result.non_packed_islands
    
    @property
    def invalid_islands(self):
        return self.result.invalid_islands
    
    @property
    def islands(self):
        return self.result.islands


class StdResultHandler(ResultHandler):

    PRIORITY = 0

    def handle_result(self, result, shared_data : ResultHandlerSharedData):
        if result is not None:
            self._result = result
            self.dirty = True

        for stage in self.task_data.stages:
            shared_data.boxes_used += Box.from_uc_boxes(stage.target)

    def get_target_boxes(self):
        return [(stage.metadata, Box.from_uc_boxes(stage.target)) for stage in self.task_data.stages]


class DynamicTilesResultHandlerBase(ResultHandler):

    pass


class DynamicTilesResultHandler(DynamicTilesResultHandlerBase):

    PRIORITY = 10

    first_dynamic_tile = None
    dynamic_tile_count = None
    dynamic_result = None
    dynamic_target_boxes = None


    def __init__(self, task_data):
        super().__init__(task_data)

        target = uc.InfStageTarget(Box.unit_box().to_uc_box(), 1, 0)

        for stage in self.task_data.stages:
            stage.target = target
            stage.static_islands = None

    @property
    def tiles_in_row(self):
        return self.task_data.dt_config.tiles_in_row

    @property
    def islands(self):
        return self.dynamic_result

    def __first_dynamic_tile(self, shared_data : ResultHandlerSharedData):
        if self.dynamic_tile_count is None:
            return None
        
        def box_available(box):
            for box_used in shared_data.boxes_used:
                if box_used.intersects(box):
                    return False
                
            return True
        
        unit_box = Box.unit_box()
        curr_tile_num = 0

        while True:
            boxes_available = True

            for tile_idx in range(self.dynamic_tile_count):
                if not box_available(unit_box.tile_from_number(curr_tile_num + tile_idx, self.tiles_in_row)):
                    boxes_available = False
                    break

            if boxes_available:
                return curr_tile_num
                
            curr_tile_num += 1

    def handle_result(self, result, shared_data : ResultHandlerSharedData):
        rework_needed = False

        if result is not None:
            rework_needed = True
            self._result = result
            self.dynamic_tile_count = 0

            for island in self._result.islands:
                i_bbox = Box.from_uc_box(island.bbox())
                i_tile_x, __ = i_bbox.tile_coords()
                self.dynamic_tile_count = max(self.dynamic_tile_count, i_tile_x + 1)

        if self._result is not None:
            first_dynamic_tile = self.__first_dynamic_tile(shared_data)
            
            if self.first_dynamic_tile != first_dynamic_tile:
                self.first_dynamic_tile = first_dynamic_tile
                rework_needed = True

        if rework_needed:
            assert self._result is not None
            assert self.first_dynamic_tile is not None
            
            dynamic_result = uc.IslandSet()
            unit_box = Box.unit_box()

            for island in self._result.islands:
                i_bbox = Box.from_uc_box(island.bbox())
                i_tile_x, i_tile_y = i_bbox.tile_coords()
                assert i_tile_y == 0

                dst_tile = unit_box.tile_from_number(self.first_dynamic_tile + i_tile_x, self.tiles_in_row)
                
                d_island = island.offset(dst_tile.p1_x - i_tile_x * PACK_RATIO.get(), dst_tile.p1_y - i_tile_y)
                dynamic_result.append(d_island)

            self.dynamic_result = dynamic_result
            self.dynamic_target_boxes =\
                [unit_box.tile_from_number(self.first_dynamic_tile + tile_idx, self.tiles_in_row) for tile_idx in range(self.dynamic_tile_count)]
            self.dirty = True
            self.target_boxes_dirty = True

        if self._result is not None:
            assert self.dynamic_target_boxes is not None
            shared_data.boxes_used += self.dynamic_target_boxes

    def get_target_boxes(self):
        if self.dynamic_target_boxes is None:
            return []
        
        return [(stage.metadata, self.dynamic_target_boxes) for stage in self.task_data.stages]
    

class DynamicStartTileResultHandler(DynamicTilesResultHandlerBase):

    PRIORITY = 0
    dynamic_target_boxes = None


    def __init__(self, task_data):
        super().__init__(task_data)
        dt_config = self.task_data.dt_config

        first_dynamic_tile = Box.unit_box().tile(*dt_config.start_tile)
        self.dynamic_target_boxes = [first_dynamic_tile]

        uc_first_tile = first_dynamic_tile.to_uc_box()
        target = uc.InfStageTarget(uc_first_tile, dt_config.tile_step[0], dt_config.tile_step[1])

        for stage in self.task_data.stages:
            stage.target = target

    def handle_result(self, result, shared_data : ResultHandlerSharedData):
        if result is not None :
            self._result = result
            used_tiles = set()

            for island in self._result.islands:
                i_bbox = Box.from_uc_box(island.bbox())
                used_tiles.add(i_bbox.tile_coords())

            unit_box = Box.unit_box()

            self.dynamic_target_boxes = [unit_box.tile(x, y) for x, y in used_tiles]
            self.dirty = True
            self.target_boxes_dirty = True

        assert self.dynamic_target_boxes is not None
        shared_data.boxes_used += self.dynamic_target_boxes

    def get_target_boxes(self):
        assert self.dynamic_target_boxes is not None
        return [(stage.metadata, self.dynamic_target_boxes) for stage in self.task_data.stages]


class TaskData:

    dt_config = None


    def __init__(self, pack_params, stages, dt_config : DynamicTilesConfig=None):
        self.task = uc.PackTask(0, pack_params)
        self.stages = stages
        self.groups_together = False
        self.dt_config = dt_config
        self.manager = None

        if self.dt_config is not None:
            if self.dt_config.start_tile is not None:
                self.result_handler = DynamicStartTileResultHandler(self)

            else:
                self.result_handler = DynamicTilesResultHandler(self)

        else:
            self.result_handler = StdResultHandler(self)

        for stage in self.stages:
            self.__add_stage(stage)

    def __add_stage(self, stage):
        if stage.params.groups_together:
            self.groups_together = True

        self.task.add_stage(stage)


class PackManager:

    HEURISTIC_HINT = 'press ESC to stop'

    GROUP_TOGETHER_HEURISTIC_WARNING_SENT = False
    GROUP_TOGETHER_HEURISTIC_WARNINGS = [
        "Packing groups together requires heuristic search enabled to produce the optimal result",
        "It is strongly recommended to enable heuristic search when using this mode"
    ]

    tasks : list[TaskData]

    def __init__(self, scenario, runconfig):
        self.scenario = scenario
        self.runconfig = runconfig
        self.tasks = []
        # self.target_bbox = Box.flipped_box()
        self.packed_islands = None
        self.invalid_islands = None
        self.log_result_area = False

    def add_task(self, task_data : TaskData):
        cls = type(self)

        if (not cls.GROUP_TOGETHER_HEURISTIC_WARNING_SENT) and\
           (not self.runconfig.heuristic_search_enabled()) and task_data.groups_together:
            
            for warn in cls.GROUP_TOGETHER_HEURISTIC_WARNINGS:
                uc.packer.send_log(uc.LogType.WARNING, warn)
            cls.GROUP_TOGETHER_HEURISTIC_WARNING_SENT = True

        self.tasks.append(task_data)

    def get_target_boxes(self):
        t_boxes = []
        for task_data in self.tasks:
            for s_metadata, boxes in task_data.result_handler.get_target_boxes():
                t_boxes += boxes

        return t_boxes

    def send_target_boxes(self):
        box_info_array = []

        class IntWrapper:
            def __init__(self):
                self.val = 0

        from collections import defaultdict
        text_line_dict = defaultdict(IntWrapper)

        for task_data in self.tasks:
            handler = task_data.result_handler
            handler.target_boxes_dirty = False

            for s_metadata, boxes in handler.get_target_boxes():
                z_coord = 0.0

                for box_idx, box in enumerate(boxes):
                    text_line_num = text_line_dict[box]
                    text = "{} (Box {})".format(s_metadata.name, box_idx) if s_metadata.name else ''

                    box_info = BoxRenderInfo(
                                    glob_idx = len(box_info_array),
                                    box = box,
                                    color = rgb_to_rgba(s_metadata.color),
                                    text = text,
                                    text_line_num = text_line_num.val,
                                    z_coord = z_coord)

                    text_line_num.val += 1
                    box_info_array.append(box_info)

        JsonUtils.send_box_render_info(box_info_array)

    def send_dirty_results(self):
        if self.scenario.config.disable_immediate_uv_update:
            return
        
        result_islands = uc.IslandSet()
        non_packed = uc.IslandSet()

        for task_data in self.tasks:
            handler = task_data.result_handler
            if not handler.dirty:
                continue

            assert handler.is_set
            result_islands += handler.islands

            if handler.non_packed_islands is not None:
                non_packed += handler.non_packed_islands

            handler.dirty = False

        to_send = []
        if len(result_islands) > 0:
            to_send.append(result_islands)

        if len(non_packed) > 0:
            to_send.append(non_packed)

        if len(to_send) > 0:
            self.scenario.send_out_islands(to_send, send_transform=True)

    def result_handler(self, task, result):
        shared_data = ResultHandlerSharedData()

        target_boxes_dirty = False

        for idx, task_data in enumerate(self.tasks):
            handler = task_data.result_handler
            handler.handle_result(result if task.id == idx else None, shared_data)
            target_boxes_dirty |= handler.target_boxes_dirty

        if target_boxes_dirty:
            self.send_target_boxes()

        self.send_dirty_results()

        if self.log_result_area:
            area_sum = 0.0

            for task_data in self.tasks:
                handler = task_data.result_handler
                if not handler.is_set:
                    continue

                area_sum += handler.islands.area()

            if area_sum > 0.0:
                uc.packer.send_log(uc.LogType.INFO, "Current result area: {}".format(area_to_string(area_sum)))

    def standard_log(self):
        return 'Packing in progress', -1

    def heuristic_search_log(self):
        return 'Heuristic search in progress', -1

    def heuristic_search_time_log(self):
        now = time.time()
        run_time = now - self.start_time
        time_left = max(0, int(round(float(self.runconfig.heuristic_search_time) - run_time)))
        return "{} (time left: {} s.)".format(self.heuristic_search_log()[0], time_left), 1000

    def init_log_method(self):
        heuristic_search_time = self.runconfig.heuristic_search_time
        hint_str = None
        
        if heuristic_search_time >= 0:
            self.log_result_area = True
            hint_str = self.HEURISTIC_HINT

            if heuristic_search_time > 0:
                self.start_time = time.time()
                # self.time_left = float(heuristic_search_time)
                self.log_method = self.heuristic_search_time_log
            else:
                self.log_method = self.heuristic_search_log
        else:
            self.log_method = self.standard_log

        if hint_str is not None:
            uc.packer.send_log(uc.LogType.HINT, hint_str)

    def pack(self):
        self.tasks.sort(key=lambda task_data: task_data.result_handler.PRIORITY)

        for idx, task_data in enumerate(self.tasks):
            task_data.task.id = idx

        self.send_target_boxes()

        self.runconfig.asyn = True
        self.runconfig.realtime_solution = True
        self.runconfig.set_result_handler(pack_manager_result_handler, self)

        self.init_log_method()

        for task_data in self.tasks:
            uc.packer.run_task(task_data.task, self.runconfig)

        all_tasks_completed = False
        while not all_tasks_completed:
            log_str, time_to_wait = self.log_method()
            uc.packer.send_log(uc.LogType.STATUS, log_str)
            all_tasks_completed = uc.packer.wait_for_all_tasks(time_to_wait)

        ret_code = uc.RetCode.NOT_SET
        self.packed_islands = uc.IslandSet()
        self.non_packed_islands = uc.IslandSet()
        self.invalid_islands = uc.IslandSet()

        for task_data in self.tasks:
            handler = task_data.result_handler
            assert handler.is_set
            ret_code = uc.append_ret_codes(ret_code, handler.ret_code)

            if handler.ret_code == uc.RetCode.INVALID_ISLANDS:
                self.invalid_islands += handler.invalid_islands

            if uc.solution_available(handler.ret_code):
                if handler.islands is not None:
                    self.packed_islands += handler.islands
                if handler.non_packed_islands is not None:
                    self.non_packed_islands += handler.non_packed_islands

        if self.scenario.config.disable_immediate_uv_update and uc.solution_available(ret_code):
            self.scenario.send_out_islands([self.packed_islands, self.non_packed_islands], send_transform=True)

        return ret_code
