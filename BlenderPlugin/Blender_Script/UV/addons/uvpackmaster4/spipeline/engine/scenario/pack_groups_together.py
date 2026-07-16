from ..g_scheme import GSchemePackScenario
from ..pack_utils import SingleStageScenarioMixin, TilesScenarioMixin


class Scenario(TilesScenarioMixin, SingleStageScenarioMixin, GSchemePackScenario):

    def _get_stage_params(self):
        stage_params = super()._get_stage_params()
        stage_params.groups_together = True
        stage_params.grouping_compactness = self.g_scheme.options.base.grouping_compactness

        return stage_params

    def _get_input_islands(self):
        return [group.islands for group in self.g_scheme.groups if group.islands is not None]
