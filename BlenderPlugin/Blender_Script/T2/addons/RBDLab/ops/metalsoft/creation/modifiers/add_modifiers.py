import re
from uuid import uuid4
from bpy.types import Operator
from bpy.props import BoolProperty
from .....addon.naming import RBDLabNaming
from .....Global.get_common_vars import get_common_vars
from .....Global.functions import create_modifier
from ...common.reorder_modifiers import reorder_modifiers


avalidable_modifiers = {
                        'SUBSURF'           : 'MOD_SUBSURF',
                        'DISPLACE'          : 'MOD_DISPLACE', 
                        'SMOOTH'            : 'MOD_SMOOTH', 
                        'REMESH'            : 'MOD_REMESH', 
                        'SOLIDIFY'          : 'MOD_SOLIDIFY', 
                        'DECIMATE'          : 'MOD_DECIM',
                        # 'SIMPLE_DEFORM'     : 'MOD_SIMPLEDEFORM', 
                        # 'SHRINKWRAP'        : 'MOD_SHRINKWRAP', 
                        # 'TRIANGULATE'       : 'MOD_TRIANGULATE', 
                        # 'WELD'              : 'AUTOMERGE_OFF', 
                        # 'WIREFRAME'         : 'MOD_WIREFRAME',
                        # 'CORRECTIVE_SMOOTH' : 'MOD_SMOOTH',
}



class RBDLAB_OT_metal_add_modifiers(Operator):
    bl_idname = "rbdlab.metalsoft_creation_add_modifiers"
    bl_label = "Add Modifiers"
    bl_options = {'REGISTER', 'UNDO'}

    decimate: BoolProperty(default=False)
    remesh: BoolProperty(default=False)
    subsurf: BoolProperty(default=False)
    displace: BoolProperty(default=False)
    solidify: BoolProperty(default=False)
    smooth: BoolProperty(default=False)
    subdivision: BoolProperty(default=False)    
    simple_deform: BoolProperty(default=False)
    shrinkwrap: BoolProperty(default=False)
    triangulate: BoolProperty(default=False)
    weld: BoolProperty(default=False)
    wireframe: BoolProperty(default=False)
    corrective_smooth: BoolProperty(default=False)


    @classmethod
    def description(cls, _context, properties):
        return "Add Modifiers"


    def execute(self, context):
        # Obtengo el listado de Target Collection:
        tcoll_list = get_common_vars(context, get_tcoll_list=True)
        
        # Obtengo los modificadores que quiere crear el usuario:
        desired_mods = [mod_name for mod_name in avalidable_modifiers.keys() if getattr(self, mod_name.lower())]
        
        # construyo las variables de los listados:
        tcoll_item = tcoll_list.active_item
        metal_list = tcoll_item.metal_list
        metal_active = metal_list.active
        modifiers_list = metal_active.modifiers

        # obtengo todos los nombres del listado:
        all_modifiers_names = modifiers_list.get_all_items_names

        # limpio los nombres del listado de los sufijos _0X para quedarme solo con los nombres:
        all_modifiers_names_clear = []
        for m_n in all_modifiers_names:
            result = re.search(r"(.*)(_[0-9]+)", m_n)
            if result:
                result = result.group(1)
                result = result.replace("_Layer", "")
                all_modifiers_names_clear.append(result)

        # obtengo todos los objetos a los que hay q ponerles los modifiers:
        all_originals = metal_list.get_all_originals

        # Mod Type : id
        mod_and_id = {}

        # Por cada uno de los modifiers que desea el usuario:
        for mod_type in desired_mods:

            # busco el nombre sin numeros en el listado limpiado de numeros previamente:
            # list_name_clear = RBDLabNaming._RBDLab_name + "_" + mod_type.title()
            list_name_clear = mod_type.title()
            total = all_modifiers_names_clear.count(list_name_clear)
            
            # Como el usuario puede renombrar los nombres el listado puede haber cambiado.
            # Para probar monto un nombre_0X para saber si realmente ya esta o no en el listado:
            tmp_padding = len(str(total)) + 1
            tmp_list_name = list_name_clear + "_" + str(total).zfill(tmp_padding)
            
            # Compruebo si el nombre temporal montado ya esta en el listado:
            if tmp_list_name in all_modifiers_names:
                # Si ya está en el listado le sumo 2 en lugar de 1 para que pase a la cifra siguiente
                padding = len(str(total)) + 2
                list_name = list_name_clear + "_Layer" + "_" + str(total).zfill(padding)
            else:
                # si no está en el listado montaoms el nombre con el tmp_padding
                list_name = list_name_clear + "_Layer" + "_" + str(total).zfill(tmp_padding)
        
            # Genero un id unico para mos modifiers del mismo tipo:
            if mod_type not in mod_and_id:
                mod_id = str(uuid4())[:8]
                # Guardamos el id en el diccionario:
                mod_and_id[mod_type] = mod_id

            # el mod_id con el que se trabaja por el type actual:
            mod_id = mod_and_id[mod_type]

            # max chars per name 63:
            # le restamos al id chars para que sea igual que el string acotado a 63 chars en blender mod.name:
            while len(list_name) + len(mod_id) > (63-1): # le resto 1 por el "_"
                    mod_id = mod_id[:-1]

            # list_name es el nombre final.
            # los nombres de los modifiers les pongo de sufijo el id:
            mod_name = list_name + "_" +  mod_id
            icon = avalidable_modifiers[mod_type]

            # Para todos los objetos ogiginales:
            # Creamos los modifiers y los items en el listado:
            for org_ob in all_originals:
                create_modifier(org_ob, mod_name, mod_type)
                modifiers_list.add_item(list_name, mod_id, mod_type, icon, mod_name)
                # el active item despues de un add_item es el que se acaba de agregar.
                active_item = modifiers_list.active
                active_item.add_ob(org_ob)
                reorder_modifiers(org_ob)

        return {'FINISHED'}
    
    
    def invoke(self, context, event):
        
        # Primero reseteamos los modifiers deseados:
        for mod_name in avalidable_modifiers.keys():
            setattr(self, mod_name.lower(), False)

        return context.window_manager.invoke_props_dialog(self, width=200)
        

    def draw(self, context):
        layout = self.layout
        col = layout.column()
        
        for mod_name, icon in avalidable_modifiers.items():
            col.prop(self, mod_name.lower(), text=mod_name.title().replace("_"," "), icon=icon)
