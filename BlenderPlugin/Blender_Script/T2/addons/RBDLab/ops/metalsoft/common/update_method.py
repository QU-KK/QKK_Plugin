from typing import List
from bpy.types import Object
from ....Global.functions import generic_copy



def update_modifiers(active_ob:Object, objects:List[Object], blacklist:tuple=None, modifiers_names:List[str]=None) -> None:

    if active_ob.type != 'MESH':
        print(f"[update_modifiers method]: Your {active_ob.name} object is not of type valid mesh!")
        return

    for ob in objects:

        # Si estamos con el mismo ob que el activo, skipeamos:
        if ob == active_ob or ob.type != 'MESH':
            continue
        
        # Para todos sus modificadores:
        for current_mod in ob.modifiers:
            
            # Si disponemos de un blacklist para skipeos:
            if blacklist is not None:
                if current_mod.name in blacklist:
                    continue
            
            # Si disponemos de un modifiers names para filtrar y skipear:
            if modifiers_names is not None:
                # Si el modificador actual no está en modifiers_names lo skipeamos:
                if current_mod.name not in modifiers_names:
                    continue
            
            # Si el modificador actual no lo tiene el first object lo skipeamos:
            org_modifier = active_ob.modifiers.get(current_mod.name)
            if not org_modifier:
                continue
            
            # Copiamos los mismos settings:
            generic_copy(org_modifier, current_mod)