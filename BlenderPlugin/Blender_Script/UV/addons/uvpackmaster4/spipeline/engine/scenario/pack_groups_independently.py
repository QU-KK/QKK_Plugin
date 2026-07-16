
from ..g_scheme import GSchemeDistinctStagesPackScenario
from ..pack_utils import TilesScenarioMixin, TaskData
from ..utils import eprint
from ..uc_entry import uc


class Scenario(TilesScenarioMixin, GSchemeDistinctStagesPackScenario):

    def init_tasks(self):
        for group in self.g_scheme.groups:
            if group.islands is None:
                continue

            stage = group.to_stage()
            stage.target = self.op_target
            stage.input_islands = [group.islands]

            self.pack_manager.add_task(TaskData(self.pack_params, [stage]))

    def post_run_island_sets(self):
        packed_islands_array = []

        for task_data in self.pack_manager.tasks:
            handler = task_data.result_handler
            assert handler.is_set

            if uc.solution_available(handler.ret_code):
                packed_islands_array.append(handler.islands)

        return packed_islands_array, self.pack_manager.invalid_islands
