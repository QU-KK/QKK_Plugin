from ..pipeline import GenericScenario
from ..uc_entry import uc


class Scenario(GenericScenario):

    def run(self):
        uc.packer.send_out_islands(self.cx.input_islands, send_iparams=True)
        return uc.RetCode.SUCCESS
