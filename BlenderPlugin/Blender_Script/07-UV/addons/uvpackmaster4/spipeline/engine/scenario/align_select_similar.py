from ..similarity_utils import SimilarityScenario
from ..uc_entry import uc


class Scenario(SimilarityScenario):

    def run(self):
        uc.packer.send_log(uc.LogType.STATUS, "Looking for similar islands...")
        simi_islands = self.cx.selected_islands.find_similar(self.simi_params, self.cx.unselected_islands)

        for island in simi_islands:
            island.set_flags(uc.IslandFlag.SELECTED)

        uc.packer.send_out_islands(simi_islands, send_flags=True)
        uc.packer.send_log(uc.LogType.STATUS, "Done. Similar islands found: {}".format(len(simi_islands)))
        return uc.RetCode.SUCCESS
