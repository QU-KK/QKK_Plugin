from bpy.types import Object
from ....addon.naming import RBDLabNaming

def move_mod(ob:Object, mod_target_name:str, desired_index:int) -> None:
    ob.modifiers.move(ob.modifiers.find(mod_target_name), desired_index)


def reorder_modifiers(ob:Object) -> None:

    """ Reordenamos los 2 o 3 o 5 modificadores principales de arriba (Remesh, Decimate, Displace, SurfaceDeform, Canvas) """

    # Utilizado en: 
    #    Add Layer
    #    Create Metal Mesh
    #    Add Modifiers
    #    Move Modifiers
    #    Rebind

    # Posicionamos los modifiers de arriba si los hubiera:
    # RBDLab_Remesh (puede o no existir)
    # RBDLab_Decimate (puede o no existir)
    # RBDLab_Displace (normalmente existe)
    # RBDLab_SurfaceDeform (normalmente existe)
    # RBDLab_Canvas (puede o on existir)

    modifier_order = (
        RBDLabNaming.REMESH_ORIGNAL, 
        RBDLabNaming.DECIMATE_ORIGINAL, 
        RBDLabNaming.DISPLACE_FOR_DDFORM,
        RBDLabNaming.SURFACE_DEFORM,
        RBDLabNaming.ACT_CANVAS_MOD,
    )

    # Los nombres y la posicion de los modificadores que tiene el objeto:
    from_idx = {mod.name: i for i, mod in enumerate(ob.modifiers)}

    # Empezamos sin modifiers:
    positions = [-1]

    # Me recorro en orden mis modificadores:
    for mod_name in modifier_order:
        
        # si el modificador no está en los que tiene el objeto lo skipeamos:
        if mod_name not in from_idx:
            continue

        # la nueva posicion, si tiene remesh original será 0, sino la que le corresponda:
        new_pos = 0 if mod_name == RBDLabNaming.REMESH_ORIGNAL else positions[-1]+1
        if new_pos < 0 or new_pos >= len(ob.modifiers):
            continue
        
        # movemos el modificador
        # print(mod_name, from_idx[mod_name], new_pos)
        ob.modifiers.move(from_idx[mod_name], new_pos)
        positions.append(new_pos)