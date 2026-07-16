from ..pipeline import GenericScenario
from ..utils import eprint
from ..geom import islands_inside_box
from ..geom.box import Box
from ..uc_entry import uc


class Scenario(GenericScenario):

    fully_inside : bool
    select : bool
    active_box : Box

    def run(self):
        target_islands = self.cx.unselected_islands if self.select else self.cx.selected_islands
        islands_inside = islands_inside_box(target_islands, self.active_box, self.fully_inside)

        if self.select:
            islands_inside.set_flags(uc.IslandFlag.SELECTED)
        else:
            islands_inside.clear_flags(uc.IslandFlag.SELECTED)

        uc.packer.send_out_islands(islands_inside, send_flags=True)
        return uc.RetCode.SUCCESS
