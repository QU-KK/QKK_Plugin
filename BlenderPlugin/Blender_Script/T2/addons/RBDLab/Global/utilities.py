from datetime import datetime
from typing import Collection


def finding_home_for_orphaned_chunks(context, coll_low: Collection, coll_high: Collection) -> None:
    start = datetime.now()
    # ----------------------------------------------------------------------------------------------
    # emparentamos trozos de los highs que no tengan parent a la pieza mas cercana automaticamente
    # ----------------------------------------------------------------------------------------------

    scn = context.scene

    print("Auto parent for orphaned high chunks")

    orphan_parents = [obj for obj in coll_high.objects if not obj.parent]

    if orphan_parents:

        # print("orp_target.name", orp_target.name)
        if scn.frame_current != scn.frame_start:
            # scn.frame_current = scn.frame_start
            scn.frame_set(scn.frame_start)

        for orp_target in orphan_parents:
            # # forzando actualizar el depsgraph:
            # context.scene.frame_set(context.scene.frame_current + 1)
            # context.scene.frame_set(context.scene.frame_current - 1)

            # deselect_all_objects(context)
            # select_object(context, orp_target)
            # set_active_object(context, orp_target)

            current_loc = orp_target.matrix_world.copy()
            results = {}

            # orp_target.color = (1, 0, 0, 1)

            # results = dict((obj, (obj.location - orp_target.location).length_squared) for obj in coll_low_objects if obj.name not in results and obj.parent) # con este tenia q forzar el update del despgraph

            # results = dict(
            #     (obj, (obj.matrix_world.translation - orp_target.matrix_world.translation).length_squared)
            #     for obj in coll_high.objects if obj.name not in results and obj.parent
            # )

            results = dict(
                (obj, (obj.matrix_world.translation - orp_target.matrix_world.translation).length_squared)
                for obj in coll_low.objects if obj.name not in results
            )

            results = dict(sorted(results.items(), key=lambda item: item[1]))
            candidates = list(results.keys())

            if candidates:
                first_candidate = candidates[0]
                # first_candidate.select_set(True)
                orp_target.parent = first_candidate
                orp_target.matrix_world = current_loc

    print("finding_home_for_orphaned_chunks End: " + str(datetime.now() - start))
