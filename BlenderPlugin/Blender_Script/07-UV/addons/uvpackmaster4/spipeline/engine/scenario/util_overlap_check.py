from ..pipeline import GenericScenario
from ..utils import flag_islands
from ..uc_entry import uc


class Scenario(GenericScenario):

    def run(self):
        uc.packer.send_log(uc.LogType.STATUS, "Looking for overlapping islands...")

        islands_to_check = self.cx.selected_islands
        overlapping = islands_to_check.overlapping_islands(islands_to_check)[0]
        overlapping.set_flags(uc.IslandFlag.OVERLAPS)

        flag_islands(islands_to_check, overlapping)

        ret_code = uc.RetCode.NOT_SET

        if len(overlapping) > 0:
            ret_code = uc.RetCode.WARNING
            log_msg = 'Overlapping islands detected (check selected islands)'
        else:
            ret_code = uc.RetCode.SUCCESS
            log_msg = 'No overlapping islands detected'

        uc.packer.send_log(uc.LogType.STATUS, log_msg)
        return ret_code
