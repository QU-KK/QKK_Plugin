from ..similarity_utils import SimilarityScenario
from ..utils import eprint
from ..uc_entry import uc


class SplitMetadata:
    def __init__(self):
        self.split_offset = 0
        self.processed = False


class Scenario(SimilarityScenario):

    MAX_GROUPS_EXCEEDED_ERROR_STR_ARRAY = [
        "Maximum number of groups exceeded",
        "Consider increasing the 'Minimum Group Size' value"
    ]

    target_iparam_name : str
    min_group_size : int

    def run(self):
        target_iparam_desc = self.int_iparams_manager.iparam_desc(self.target_iparam_name)

        uc.packer.send_log(uc.LogType.STATUS, "Determining similarity groups...")

        input_islands = self.cx.input_islands
        simi_groups = input_islands.split_by_similarity(self.simi_params)

        group_num = target_iparam_desc.min_value

        if self.min_group_size > 1:
            idx = 0
            while idx < len(simi_groups):
                group = simi_groups[idx]

                if len(group) < self.min_group_size:
                    group.set_iparam(target_iparam_desc, group_num)
                    del simi_groups[idx]
                    continue

                idx += 1

        group_num += 1

        for group in simi_groups:
            if group_num > target_iparam_desc.max_value:
                for error_str in self.MAX_GROUPS_EXCEEDED_ERROR_STR_ARRAY:
                    uc.packer.send_log(uc.LogType.ERROR, error_str)
                return uc.RetCode.INVALID_INPUT

            group.set_iparam(target_iparam_desc, group_num)
            group_num += 1

        target_iparam_desc.mark_dirty()
        uc.packer.send_out_islands(input_islands, send_iparams=True)
        return uc.RetCode.SUCCESS
