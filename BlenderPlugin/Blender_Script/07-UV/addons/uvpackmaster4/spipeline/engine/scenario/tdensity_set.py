from ..pipeline import TexelDensityScenario
from ..labels import Labels
from ..uc_entry import uc


class Scenario(TexelDensityScenario):

    def run(self):
        if not self.tdensity_to_set.is_defined():
            raise uc.InputError("'{}' parameter has to be greater than zero".format(Labels.TDENSITY_TO_SET_NAME))

        output = self.set_tdensity_to_islands(self.cx.input_islands, self.tdensity_to_set)
        uc.packer.send_out_islands(output, send_transform=True, send_iparams=True)
        return uc.RetCode.SUCCESS
