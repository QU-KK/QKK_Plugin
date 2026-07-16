from bpy.types import Context, Object
from mathutils import Vector
from math import dist
from collections import defaultdict

from ..constraints.detect import check_separated_neighbor_chunks as _calculate_broken_neighbours
from ...props.rbdlab_object import RBDLabObjectData


def update_broken_neighbours_and_motions(context: Context,
                                         chunks_objects: list[Object],
                                         step: int = 1,
                                         distance_threshold: float = 0.01,
                                         # condition: str = 'GREATER_THAN',
                                         velocity_threshold: float = 0.2,
                                         max_motions: int = 1,
                                         flag: set[str] = {'BROKEN', 'MOTION'}):
    
    frame_start: int = context.scene.frame_start
    frame_end: int = context.scene.frame_end
    fps: float = context.scene.render.fps * (1 / context.scene.render.fps_base)
    seconds_per_frame: float = 1 / fps
    object_count: int = len(chunks_objects)

    # stop_velocity_threshold = max(velocity_threshold * .5, 0.01)

    use_calculate_motions: bool = 'MOTION' in flag
    use_calculate_broken: bool = 'BROKEN' in flag

    if use_calculate_motions:
        in_motion: dict[Object, list[float]] = defaultdict(list)  # Object related with motion start frame.
        maxed_out_chunks: set[Object] = set()
        # ps_created_per_chunk: dict[Object, int] = {}
        maxed_out_object_count: int = 0
        all_prev_pos: dict[Object, Vector] = {}

    if use_calculate_broken:
        broken_object_count: int = 0
        separated_neighbor_chunks: dict[Object, list[Object]] = defaultdict(set)
        completely_separated_chunks: set[Object] = set()
        separated_but_joint: set[Object] = set()

    context.scene.frame_set(frame=frame_start)

    if use_calculate_broken:
        for chunk in chunks_objects:
            if "broken_state" in chunk:
                del chunk["broken_state"]
            if "broken_at_frame" in chunk:
                del chunk["broken_at_frame"]
            chunk.rbdlab.broken_at_frame = -1

    if use_calculate_motions:
        for ob in chunks_objects:
            # Initialize first frame data.
            all_prev_pos[ob] = ob.matrix_world.translation.to_tuple()

            # Cleanup motions data.
            ob.rbdlab.clear_motions()
            ob.rbdlab.ok_distance_threshold = False

            if "has_motions" in ob:
                del ob["has_motions"]

        def start__check_velocity_at_frame(vel) -> bool: return vel > velocity_threshold
        def end__check_velocity_at_frame(vel) -> bool: return vel <= velocity_threshold # velocity_threshold

    def _calculate_motions(frame: int, ob: Object):
        nonlocal seconds_per_frame
        nonlocal maxed_out_object_count
        nonlocal max_motions
        nonlocal maxed_out_chunks
        nonlocal start__check_velocity_at_frame
        nonlocal end__check_velocity_at_frame

        curr_pos: Vector = ob.matrix_world.translation.to_tuple()
        prev_pos: Vector = all_prev_pos[ob]

        distance_between_frames: float = dist(prev_pos, curr_pos)
        # print("distance...", distance_between_frames)
        speed_at_curr_frame: float = distance_between_frames / seconds_per_frame
        # print("velocity...", speed_at_curr_frame)

        if ob in in_motion:
            in_motion[ob].append((frame, speed_at_curr_frame))

            if end__check_velocity_at_frame(speed_at_curr_frame):
                # Object is stopping motion...
                tot_motion_frames = frame - ob["temp__frame_start"]
                motion_data = in_motion.pop(ob)
                if tot_motion_frames <= 3:
                    # SKIP MOTION...
                    pass
                else:
                    ob_rbdlab: RBDLabObjectData = ob.rbdlab
                    motion = ob_rbdlab.add_motion(ob["temp__frame_start"], frame)
                    for velocity_data in motion_data:
                        motion.add_velocity(*velocity_data)

                    if len(ob_rbdlab.motions) >= max_motions:
                        # MAXED OUT! No more motions for this object!
                        maxed_out_chunks.add(ob)
                        maxed_out_object_count += 1

                    if "has_motions" not in ob:
                        ob["has_motions"] = 1
                        ob["motion_1"] = (ob["temp__frame_start"], frame)
                    else:
                        ob["has_motions"] += 1
                        ob["motion_%i"%ob["has_motions"]] = (ob["temp__frame_start"], frame)

                del ob["temp__frame_start"]

        elif start__check_velocity_at_frame(speed_at_curr_frame):
            # Object is init motion...
            ob["temp__frame_start"] = frame
            in_motion[ob].append((frame, speed_at_curr_frame))

        # Update prev position.
        all_prev_pos[ob] = curr_pos

    # end local funct _calculate_motions

    # Process frames.
    for frame in range(frame_start+1, frame_end, step):
        context.scene.frame_set(frame=frame)

        if use_calculate_motions:
            if maxed_out_object_count != object_count:
                for ob in chunks_objects:
                    if ob in maxed_out_chunks:
                        continue
                    _calculate_motions(frame, ob)

        if use_calculate_broken:
            if broken_object_count != object_count:
                separated_neighbor_chunks, separated_but_joint, completely_separated_chunks = _calculate_broken_neighbours(
                    context,
                    distance_threshold,
                    chunks_objects,
                    separated_neighbor_chunks,
                    separated_but_joint,
                    completely_separated_chunks,
                    skip_partially_separated=False,
                    use_partial_broken=True
                )
                broken_object_count = len([True for ob in chunks_objects if ob.rbdlab.broken_at_frame != -1])

        skip_1 = maxed_out_object_count == object_count if use_calculate_motions else True
        skip_2 = broken_object_count == object_count if use_calculate_broken else True
        if skip_1 and skip_2:
            break

    # Remaining objects in motion...
    # Siguen en movimiento a pesar de terminar el rango de frame...
    # De momento lo resolvemos terminando el movimiento de forma artificial para que así emita partículas.
    if use_calculate_motions:
        for ob, velocity_data_list in in_motion.items():
            # Object is stopping motion...
            ob_rbdlab: RBDLabObjectData = ob.rbdlab
            motion = ob_rbdlab.add_motion(ob["temp__frame_start"], frame)
            for velocity_data in velocity_data_list:
                motion.add_velocity(*velocity_data)

            if "has_motions" not in ob:
                ob["has_motions"] = 1
                ob["motion_1"] = (ob["temp__frame_start"], frame)
            else:
                ob["has_motions"] += 1
                ob["motion_%i"%ob["has_motions"]] = (ob["temp__frame_start"], frame)

            del ob["temp__frame_start"]

    # Return to start.
    context.scene.frame_set(frame=frame_start)

    # Cleanup.
    if use_calculate_motions:
        del all_prev_pos
        del in_motion
        del maxed_out_chunks
        # del maxed_out_at_curr_frame
