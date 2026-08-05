from ..pipeline import GenericScenario
from ..utils import eprint, flag_islands
from ..props import MainProps
from ..uc_entry import uc
from ..island_params import SplitOffsetXIParamInfo, SplitOffsetYIParamInfo, AlignPriorityIParamInfo

import math


class SplitMetadata:

    def __init__(self, x_tile):
        self.split_offset = (0, 0)
        self.processed = False
        self.x_tile = x_tile


class Scenario(GenericScenario):

    main_props : MainProps

    @staticmethod
    def ignore_overlaps(o_map, ignore_func):
        out_map = {}

        for island, overlapping in o_map.items():
            new_overlapping = uc.IslandSet()

            for o_island in overlapping:
                if not ignore_func(island, o_island):
                    new_overlapping.append(o_island)

            out_map[island] = new_overlapping

        return out_map

    def run(self):
        split_props = self.main_props.split_props

        detection_mode = uc.OverlapDetectionMode(split_props.detection_mode)
        max_tile_x = split_props.max_tile_x
        
        iparam_names = (SplitOffsetXIParamInfo.SCRIPT_NAME, SplitOffsetYIParamInfo.SCRIPT_NAME)
        iparam_descriptors = tuple(self.int_iparams_manager.iparam_desc(name) for name in iparam_names)

        align_priority_iparam_desc = self.int_iparams_manager.iparam_desc(AlignPriorityIParamInfo.SCRIPT_NAME) if self.main_props.align_priority_enabled() else None

        sort_by_overlapping_count = lambda island: len(island.overlapping)
        sort_by_align_priority = lambda island: -island.get_iparam(align_priority_iparam_desc)
        
        if align_priority_iparam_desc:
            sort_key = lambda island: (sort_by_align_priority(island), sort_by_overlapping_count(island))
        else:
            sort_key = sort_by_overlapping_count

        dont_split_priorities = align_priority_iparam_desc and split_props.dont_split_priorities

        offset_step = 1

        exceeding_x_tile = uc.IslandSet()
        processed = uc.IslandSet()
        to_process = self.cx.selected_islands.clone()

        for island in to_process:
            x_tile = None
            if max_tile_x > 0:
                bbox = island.bbox()

                max_x = bbox.max_corner.x
                if max_x >= max_tile_x or max_x < 0.0:
                    exceeding_x_tile.append(island)

                x_tile = int(max_x)

            island.metadata = SplitMetadata(x_tile)

        if len(exceeding_x_tile) > 0:
            flag_islands(to_process, exceeding_x_tile)
            raise uc.InputError("Some UVs have the X coord lower than 0 or greater than the 'Max Tile (X)' value: {}. The problematic islands were selected. Aborting.".format(max_tile_x))
        
        def free_to_split_offset_delta(island, free_offset):
            if max_tile_x <= 0:
                return (free_offset, 0)

            y_offset = 0

            metadata = island.metadata
            orig_x_tile = metadata.x_tile

            assert orig_x_tile < max_tile_x
            x_offset = orig_x_tile + free_offset

            while x_offset >= max_tile_x:
                x_offset -= max_tile_x
                y_offset += 1

            metadata.x_tile = x_offset
            x_offset -= orig_x_tile

            return (x_offset, y_offset)


        while len(to_process) > 0:
            to_check = to_process.clone()
            to_check += processed

            o_map = to_check.overlapping_map(detection_mode)
            # eprint(o_map)

            if dont_split_priorities:
                o_map = self.ignore_overlaps(o_map, lambda i1, i2: i1.get_iparam(align_priority_iparam_desc) == i2.get_iparam(align_priority_iparam_desc))

            overlapping_islands = []
            for island in to_check:
                island.overlapping = o_map[island]

                if len(island.overlapping) == 0:
                    if not island.metadata.processed:
                        island.metadata.processed = True
                        processed.append(island)
                    continue

                if island.metadata.processed:
                    island.metadata.local_offset = 0
                    continue
            
                island.metadata.local_offset = None
                overlapping_islands.append(island)

            overlapping_islands.sort(key=sort_key)
            to_process.clear()

            for island in overlapping_islands:

                free_offset = None
                offset_to_check = 0

                while True:
                    offset_found = True

                    for other_island in island.overlapping:
                        if other_island.metadata.local_offset is not None and other_island.metadata.local_offset == offset_to_check:
                            offset_found = False
                            break

                    if offset_found:
                        free_offset = offset_to_check
                        break

                    offset_to_check += offset_step

                split_offset_delta = free_to_split_offset_delta(island, free_offset)
                split_offset = island.metadata.split_offset

                island.metadata.local_offset = free_offset
                island.metadata.split_offset = tuple(split_offset[c] + split_offset_delta[c] for c in range(len(split_offset)))

                if free_offset != 0:
                    to_process.append(island.offset(split_offset_delta[0], split_offset_delta[1]))
                else:
                    to_process.append(island)

        assert(len(processed) == len(self.cx.selected_islands))

        moved_count = 0

        for island in processed:
            split_offset = island.metadata.split_offset

            if split_offset[0] != 0 or split_offset[1] != 0:
                moved_count += 1

            for c in range(len(split_offset)):
                island.set_iparam(iparam_descriptors[c], split_offset[c])
            
        for desc in iparam_descriptors:
            desc.mark_dirty()

        uc.packer.send_out_islands(processed, send_transform=True, send_iparams=True)
        uc.packer.send_log(uc.LogType.STATUS, "Done. Islands moved: {}".format(moved_count))
        return uc.RetCode.SUCCESS
