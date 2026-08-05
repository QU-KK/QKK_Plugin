from ..pipeline import GenericScenario
from ..utils import eprint
from ..uc_entry import uc
from ..island_params import SplitOffsetXIParamInfo, SplitOffsetYIParamInfo


class Scenario(GenericScenario):

    def run(self):
        iparam_names = (SplitOffsetXIParamInfo.SCRIPT_NAME, SplitOffsetYIParamInfo.SCRIPT_NAME)
        iparam_descriptors = tuple(self.int_iparams_manager.iparam_desc(name) for name in iparam_names)

        processed = uc.IslandSet()
        moved_count = 0

        for island in self.cx.selected_islands:

            split_offset = tuple(island.get_iparam(desc) for desc in iparam_descriptors)

            for c in range(len(split_offset)):
                if split_offset[c] == iparam_descriptors[c].default_value:
                    raise uc.InputError("Split data not available for all selected islands")

            if split_offset[0] != 0 or split_offset[1] != 0:
                processed_island = island.offset(-split_offset[0], -split_offset[1])
                moved_count += 1
            else:
                processed_island = island

            for desc in iparam_descriptors:
                processed_island.set_iparam(desc, desc.default_value)
            processed.append(processed_island)
        
        for desc in iparam_descriptors:
            desc.mark_dirty()

        uc.packer.send_out_islands(processed, send_transform=True, send_iparams=True)
        uc.packer.send_log(uc.LogType.STATUS, "Done. Islands moved: {}".format(moved_count))
        return uc.RetCode.SUCCESS
