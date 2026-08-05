from typing import List


def check_keyframes(self, active_group, target_list, input_frames, objects, dpaths:List=[]):

    target_frames = None
    list_type = target_list.type 

    ###########################################################################################################
    # Comprobamos que el frame target (input_frames) no exista previamente.
    #----------------------------------------------------------------------------------------------------------
    # (Para saber si estamos trabajando sobre el mismo grupo ya procesado anteriormente o en distintos grupos.)
    # Obtengo los ids de los (constswitch items/ glue strength items) que tienen guardado el id de los from_active_group de donde 
    # fueron creados y que ya fueron procesados previamente, pero que ademas posean el keyframe que se quiere generar nuevo:
    
    # Sabemos que tipo de listado estamos usando:
    if list_type == "constswitch":
        
        # Para construir el target_frames en este caso necesito el target_frame:
        if isinstance(input_frames, int):
            target_frame = input_frames

        if isinstance(input_frames, List):
            
            if len(input_frames) > 0:
                target_frame = input_frames[0]

        # En constswitchs add usamos un single frame target: (se trabaja con target frame que es 1 solo frame)
        items_id_with_target_frame = target_list.get_id_from_active_group_if_have_target_keyframe(target_frame)
        target_frames = [target_frame-1, target_frame, target_frame+1]

    elif list_type in ("glue_strength", "springs"):

        if not dpaths:
            items_id_with_target_frame = target_list.get_id_from_active_group_if_have_target_keyframes(input_frames)
        
        else:
            # Si tengo dpaths, es porque es un list_type "springs" y compruebo también por dpaths:
            items_id_with_target_frame = target_list.get_id_from_active_group_if_have_target_keyframes(input_frames, dpaths)
        
        # en set glue keyframes usamos una lista de frames: (se trabaja con input_frames que son varios frames)
        target_frames = input_frames
    
    # si el from_active_group actual (desde donde estamos trabajando ahora para crear el nuevo item) ya esta en el listado y 
    # contiene keyframes en donde queremos ponerlos ahora:
    if active_group.idname in items_id_with_target_frame:

        # Chequeo si no existiera ya un keyframe en el mismo frame:
        all_keyframes_stored = target_list.all_keyframes_stored
        
        # para saber si tienen keyframes en comun las dos listas:
        frames_intersection = set(target_frames) & set(all_keyframes_stored) # devuelve los frames que coinciden
        
        # si hay frames en comun:
        if len(frames_intersection) > 0:

            # Pero al poder usar por seleccion también compruebo si hay algún 
            # target chunk entrante "de la seleccion y/o coll" que ya hubiera sido procesado previamente:
            if list_type == "constswitch":
                all_objects_stored = target_list.all_chunks_stored
                frames_str = str(target_frame)
            
            elif list_type in ("glue_strength", "springs"):
                all_objects_stored = target_list.all_const_stored
                frames_str = str(list(frames_intersection)[:])
            
            objects_interseccion = set(all_objects_stored) & set(objects) # devuelve los objetos que coinciden
            # si estan involucrados algunos objetos (chunks/constraints) en comun:
            if len(objects_interseccion) > 0:
                self.report({'ERROR'}, "Already exist keyframes in frame: " + frames_str + "!")
                return {'CANCELLED'}
