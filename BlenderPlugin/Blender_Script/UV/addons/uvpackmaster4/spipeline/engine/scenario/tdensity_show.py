from ..pipeline import TexelDensityScenario
from ..uc_entry import uc


class Scenario(TexelDensityScenario):

    def run(self):
        for island in self.cx.input_islands:
            island.set_iparam(self.show_iparam_desc, self.calc_tdensity(island).to_s())

        uc.packer.send_out_islands(self.cx.input_islands, send_iparams=True)
        return uc.RetCode.SUCCESS
