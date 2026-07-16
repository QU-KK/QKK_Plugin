from ..pipeline import GenericScenario
from ..geom import islands_inside_box
from ..geom.box import Box
from ..uc_entry import uc


class Scenario(GenericScenario):

    fully_inside : bool
    active_box : Box
    modified_box : Box

    def run(self):
        islands_inside = islands_inside_box(self.cx.selected_islands, self.active_box, self.fully_inside)
        box_offset = self.modified_box.min_corner - self.active_box.min_corner

        transformed_islands = uc.IslandSet()

        for island in islands_inside:
            tr_island = island.offset(box_offset.x, box_offset.y)
            transformed_islands.append(tr_island)

        uc.packer.send_out_islands(transformed_islands, send_transform=True)
        return uc.RetCode.SUCCESS
