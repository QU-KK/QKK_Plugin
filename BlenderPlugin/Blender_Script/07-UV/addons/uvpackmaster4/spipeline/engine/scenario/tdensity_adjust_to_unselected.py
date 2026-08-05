from ..pipeline import TexelDensityScenario
from ..geom import IslandWrapper
from ..uc_entry import uc


class Scenario(TexelDensityScenario):

    def run(self):
        if len(self.cx.unselected_islands) == 0:
            uc.packer.send_log(uc.LogType.WARNING, 'No unselected island found - adjustment could not be made')
            return uc.RetCode.WARNING

        unselected_merged = self.cx.unselected_islands.merge()
        unselected_tdensity = round(self.calc_tdensity(unselected_merged))

        if not IslandWrapper.is_valid_tdensity(unselected_tdensity):
            uc.packer.send_log(uc.LogType.WARNING, 'Texel density of the unselected islands is not valid - adjustment could not be made')
            return uc.RetCode.WARNING

        output = self.set_tdensity_to_islands(self.cx.selected_islands, unselected_tdensity)
        uc.packer.send_out_islands(output, send_transform=True, send_iparams=True)
        return uc.RetCode.SUCCESS
