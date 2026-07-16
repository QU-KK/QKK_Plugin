from bpy.types import Operator
from bpy.props import StringProperty
from .....Global.get_common_vars import get_common_vars
from .....Global.lists import reorder_list
from ...common.reorder_modifiers import reorder_modifiers


class RBDLAB_OT_metal_modifiers_list_item_move(Operator):
    bl_idname = "rbdlab.metalsoft_creation_modifiers_list_item_move"
    bl_label = "Move Item"
    bl_description = "Move Item in List"
    bl_options = {'REGISTER', 'UNDO'}

    direction: StringProperty(default="")


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

        # Reordenamos el listado:
        reorder_list(modifiers_list, self.direction)

        # Obtengo el nombre del modificador activo:
        active_mod = modifiers_list.active
        mod_name = active_mod.mod_name

        # Obtengo todos los objetos que les puse el modifier:
        objects = modifiers_list.get_current_stored_objects
        for ob in objects:

            current_index_mod = ob.modifiers.find(mod_name)

            # si no existe el mod porque lo borro el usuario dará -1:
            if current_index_mod < 0:
                continue

            new_pos = current_index_mod-1 if self.direction == 'UP' else current_index_mod+1
            
            if new_pos >= 0 and new_pos < len(ob.modifiers) and new_pos != current_index_mod:
                ob.modifiers.move(current_index_mod, new_pos)
                # bpy.ops.object.modifier_move_to_index(modifier=mod_name, index=new_pos)
        
            reorder_modifiers(ob)


        return {'FINISHED'}