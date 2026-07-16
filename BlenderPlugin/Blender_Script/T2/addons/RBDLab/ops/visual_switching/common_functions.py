from typing import List
from bpy.types import Object
from ...addon.naming import RBDLabNaming


def obtain_lows_and_highs(self, context, tcoll) -> List[Object]:
    """
        Esta funcion, busca los highs, y si existen retorna un listado con 
        TODOS, los LOWS y los HIGHS.
    """

    low_chunks = None
    high_chunks = None

    if RBDLabNaming.USE_HIGHS in tcoll:
        # se supone q si entra aquí debería haber highs
        coll_high_name = tcoll.name.replace(RBDLabNaming.SUFIX_LOW, RBDLabNaming.SUFIX_HIGH)
        # nos aseguramos de que si:
        if coll_high_name in [coll.name for coll in context.collection.children]:
            high_coll = context.collection.children.get(coll_high_name)
            high_chunks = [ob for ob in high_coll.objects if ob.type ==
                           'MESH' and ob.name in context.view_layer.objects]

    # Si existen highs los agregamos a los low, para tener todos en un mismo listado:
    low_chunks = [ob for ob in tcoll.objects if ob.type == 'MESH' and ob.name in context.view_layer.objects]
    if low_chunks is not None:

        if high_chunks is None:
            # de lo contratioo devolvemos solo los low:
            return low_chunks
        else:
            # si existen highs los incluyo a target chunks:
            return low_chunks + high_chunks

    else:
        self.report({'ERROR'}, "Not valid chunks in Target Collection!")
        return {'CANCELLED'}
