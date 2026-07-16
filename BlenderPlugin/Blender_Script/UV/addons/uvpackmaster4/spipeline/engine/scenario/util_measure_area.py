from ..pipeline import GenericScenario
from ..utils import area_to_string
from ..uc_entry import uc


class Scenario(GenericScenario):

    merged : bool

    def run(self):
        uc.packer.send_log(uc.LogType.STATUS, "Measuring area...")

        if self.merged:
            merged_island = self.cx.selected_islands.merge()
            area = merged_island.area()
            msg = "Selected islands merged area: {}".format(area_to_string(area))
        else:
            area = self.cx.selected_islands.area()
            msg = "Selected islands area: {}".format(area_to_string(area))

        uc.packer.send_log(uc.LogType.STATUS, msg)
        return uc.RetCode.SUCCESS
