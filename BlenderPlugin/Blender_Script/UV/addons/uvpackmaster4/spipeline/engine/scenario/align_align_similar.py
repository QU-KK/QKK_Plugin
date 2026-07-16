from ..similarity_utils import SimilarityScenario
from ..uc_entry import uc


class Scenario(SimilarityScenario):

    def run(self):
        uc.packer.send_log(uc.LogType.STATUS, "Similar islands aligning...")

        if self.stack_group_iparam_desc:
            self.send_tip('aligning with Stack Groups enabled - note some islands may not be compared against each other')
            self.send_tip('refer to Stack Groups documentation for more info')
            (aligned_groups, non_aligned_islands) = self.align_similar_by_stack_group(self.cx.selected_islands)
        else:
            (aligned_groups, non_aligned_islands) = self.align_similar(self.cx.selected_islands)

        aligned_islands = uc.IslandSet()
        for group in aligned_groups:
            aligned_islands += group

        send_kwargs = {'send_vertices' if self.simi_params.correct_vertices else 'send_transform' : True}
        uc.packer.send_out_islands(aligned_islands, **send_kwargs)
        uc.packer.send_log(uc.LogType.STATUS, "Done. Islands aligned: {}".format(len(aligned_islands)))
        return uc.RetCode.SUCCESS
