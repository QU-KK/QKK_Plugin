from uuid import uuid4
from bpy.types import Operator
from bpy.props import StringProperty
from .....addon.naming import RBDLabNaming
from .....Global.get_common_vars import get_common_vars


avalidable_modifiers = {
                        'DECIMATE'          : 'MOD_DECIM',
                        'REMESH'            : 'MOD_REMESH', 
                        'DISPLACE'          : 'MOD_DISPLACE', 
                        'SOLIDIFY'          : 'MOD_SOLIDIFY', 
                        'SMOOTH'            : 'MOD_SMOOTH', 
                        'SIMPLE_DEFORM'     : 'MOD_SIMPLEDEFORM', 
                        'SHRINKWRAP'        : 'MOD_SHRINKWRAP', 
                        'TRIANGULATE'       : 'MOD_TRIANGULATE', 
                        'WELD'              : 'AUTOMERGE_OFF', 
                        'WIREFRAME'         : 'MOD_WIREFRAME',
                        'CORRECTIVE_SMOOTH' : 'MOD_SMOOTH'
}


class RBDLAB_OT_metal_remove_modifiers(Operator):
    bl_idname = "rbdlab.metalsoft_creation_remove_modifiers"
    bl_label = "Remove Modifiers"

    id_to_rm: StringProperty(default="")

    @classmethod
    def description(cls, _context, properties):
        return "Remove Modifiers"


    def execute(self, context):
        # Obtengo el listado del Target Collection: 
        tcoll_list = get_common_vars(context, get_tcoll_list=True)
        
        # Obtengo el item actvio del Target Collection:
        tcoll_item = tcoll_list.active_item

        # Obtengo el listado de metales asociado:
        metal_list = tcoll_item.metal_list
        metal_active = metal_list.active
        
        # Obtengo el listado de modificadores asociado:
        modifiers_list = metal_active.modifiers

        # Obtenemos los objetos que tienen los modifiers:
        all_originals = metal_list.get_all_originals

        item = modifiers_list.get_item_from_id(self.id_to_rm)
        all_items = modifiers_list.get_all_items

        # Nueva implementación:
        # Para todos los objetos ogiginales:

        indices_to_rm = set()
        for org_ob in all_originals:

            mod_to_rm = next((mod for mod in org_ob.modifiers if mod.name.endswith(self.id_to_rm)), None)
            # Si existe el modifier:
            if mod_to_rm:
                # Eliminamos el modifier del objeto:
                org_ob.modifiers.remove(mod_to_rm)

            # Guardamos los indices a eliminar del listado:
            indices_to_rm.add(all_items.index(item))
        
        for i in indices_to_rm:
            modifiers_list.remove_item(self.id_to_rm)
            # modifiers_list.list.remove(i)
        
        return {'FINISHED'}
