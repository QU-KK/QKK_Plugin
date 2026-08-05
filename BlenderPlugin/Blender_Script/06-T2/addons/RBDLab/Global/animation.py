from typing import List
from bpy.types import Object


def check_if_have_previous_kf(ob:Object, frame:int, dpath:str) -> bool:
    if not ob.animation_data or not ob.animation_data.action or not ob.animation_data.action.fcurves:
        return False

    pre_anim = ob.animation_data.action.fcurves.find(dpath)
    if pre_anim:
        prev_keyframes = pre_anim.keyframe_points
        return next((True for kp in prev_keyframes if kp.co.x == frame), False)
        # return any(kp.co.x == frame for kp in prev_keyframes)

    return False


def remove_keyframe_x(dpath:str, objects:List[Object], frame_target:int) -> list:

    """ Elimina el frame especifico frame_target de la curva, del data path indicado a los objetos del listado """

    axis = 0 # X

    altered_obs = set()

    for ob in objects:
        if not ob.animation_data:
            continue

        action = ob.animation_data.action
        if not action:
            continue

        if not ob.animation_data.action.fcurves:
            continue

        fcurve = action.fcurves.find(data_path=dpath, index=axis)
        if not fcurve:
            continue

        # Con esta manera de eliminar keyframes, parece que siempre 
        # tiene que existir un ultimo keyframe (sin ser borrado) en la curva:
        
        for p in fcurve.keyframe_points:
            if int(p.co.x) == frame_target:
                fcurve.keyframe_points.remove(p)
            
        # Si solo queda un solo keyframe en la curva la borramos por completo:
        if len(fcurve.keyframe_points) == 1:
            action.fcurves.remove(fcurve)
        
        altered_obs.add(ob)
    
    return list(altered_obs)