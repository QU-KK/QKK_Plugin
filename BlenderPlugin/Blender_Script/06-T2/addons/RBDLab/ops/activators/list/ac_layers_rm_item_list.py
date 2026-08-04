import bpy
from bpy.types import Operator
from bpy.props import StringProperty
from ....addon.naming import RBDLabNaming


class ACTIVATORS_OT_ac_layers_rm_item(Operator):
    bl_idname = "rbdlab.ac_layers_rm_item"
    bl_label = "Remove Item"
    bl_description = "Remove Item from list"
    bl_options = {'REGISTER', 'UNDO'}

    id_to_rm: StringProperty(default="")

    def remove_animation_color(self, ob):
        
        # Get Animation Data:
        ad = ob.animation_data
        if not ad:
            return
        
        # Get Action:
        action = ad.action
        if not action:
            return
        
        # Remove Fcurves
        fcurves = [fc for fc in action.fcurves if fc.data_path.startswith("color")]
        while (fcurves):
            fc = fcurves.pop()
            action.fcurves.remove(fc)


    def restore_color(self, ob, color_to_rm):

        # para el exclude:
        # if RBDLabNaming.ACETONABLE in ob:
        #     del ob[RBDLabNaming.ACETONABLE]
        
        self.remove_animation_color(ob)
        
        # restore color:
        ob.color_stack.rm_color(color_to_rm)
        color = ob.color_stack.get_last_color()
        if color:
            ob.color = color


    def execute(self, context):
        
        scn = context.scene
        rbdlab = scn.rbdlab

        tcoll_list = rbdlab.lists.target_coll_list
        tcoll = tcoll_list.active
        
        # Si no hay target coll skip:
        if not tcoll:
            return {'CANCELLED'}

        ac_layers_list = rbdlab.lists.ac_layers_list
    
        # Si estuviera vácio skip:
        if ac_layers_list.is_void:
            return {'CANCELLED'}
        

        # primero antes de quitarlo del listado borro sus activators:
        target_layer = ac_layers_list.get_item_from_id(self.id_to_rm)
        if not target_layer:
            return {'CANCELLED'}
        
        #-------------------------------------------------------------------
        # Borramos los records previos, solo del que vamos a borrar:
        #-------------------------------------------------------------------
        all_computable_items = ac_layers_list.get_all_computable_items
        if target_layer in all_computable_items:
            all_computable_items.remove(target_layer)
        
        [setattr(item, "compute", False) for item in all_computable_items]
        target_layer.compute = True
    
        # si no hay includes daba error:
        includes = ac_layers_list.get_current_includes
        if len(includes) > 0:
            bpy.ops.rbdlab.act_rm_record(mode='NORMAL')
    
        [setattr(item, "compute", True) for item in all_computable_items]
        #-------------------------------------------------------------------
        
        all_activators_id = target_layer.activators_list.get_all_items_ids
        for a_id in all_activators_id:
            bpy.ops.rbdlab.act_rm_item(id_to_rm=a_id)

        # Obtenemos los objetos/chunks incluidos:
        includes = ac_layers_list.get_includes_by_id(self.id_to_rm)

        # Eliminamos los canvas si tuvieran:
        for ob in includes:
            # Si el modificador existe, elimínalo
            if canvas_mod := ob.modifiers.get(RBDLabNaming.ACT_CANVAS_MOD):
                ob.modifiers.remove(canvas_mod)
        
        # Restauramos el color a los chunks includeds:
        color_to_rm = ac_layers_list.get_color_by_id(self.id_to_rm)
        if color_to_rm:
            [self.restore_color(ob, color_to_rm) for ob in includes]

        # Lo quitamos del listado de layers:
        ac_layers_list.remove_item(self.id_to_rm)

        # Si al terminar esa vacio el listado volvemos a creation tab:
        if ac_layers_list.is_void:
            rbdlab.ui.activators_mode = 'CREATION'

        # Si ya no hay layers de DYNAMIC: 
        all_types = ac_layers_list.get_all_types
        if 'DYNAMIC' not in all_types:

            # Restauramos el enabled:
            for ob in includes:
                if ob.rigid_body:
                    ob.rigid_body.enabled = True
        
        else: # Cuando hay más de un Layer de tipo DYNAMIC:

            # Recolectamos los chunks de nuestro layer a eliminar, que no formen parte de otros grupos DYNAMIC
            # Para restaurarles el Dynamic:
            all_items = ac_layers_list.get_all_items
            obs_to_restore_dynamic = set()

            for item in all_items:

                # Si es el listado con el que se está trabajando skipeamos:
                if item.id_name == self.id_to_rm:
                    continue
                
                # Si es un Layer no DY skipeamos:
                if item.type != 'DYNAMIC':
                    continue
                
                # Si es un Layer DY obtenemos sus chunks includeds:
                item_includes = list(set([o.ob for o in item.stored_includes]))
            
                # Por cada ob del Layer actual:
                for ob in includes:

                    # Si este objeto está en otro Layer de tipo Dynamic lo skipeamos:
                    if ob in item_includes:
                        continue
                    
                    # Guardamos el objeto para su restauración:
                    obs_to_restore_dynamic.add(ob)
            
            # print("obs_to_restore_dynamic", obs_to_restore_dynamic)
            # Restauramos el enabled:
            for ob in obs_to_restore_dynamic:
                if ob.rigid_body:
                    ob.rigid_body.enabled = True
        
        
        return {'FINISHED'}