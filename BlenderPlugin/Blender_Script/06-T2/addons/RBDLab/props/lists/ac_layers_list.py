# import bpy
from typing import List
from ...addon.naming import RBDLabNaming
# from ...addon.paths import RBDLabPreferences
# from ...Global.functions import set_active_object
from bpy.types import PropertyGroup, UIList, Object, Collection
from bpy.props import StringProperty, IntProperty, CollectionProperty, IntProperty, BoolProperty, PointerProperty, FloatProperty, EnumProperty
# from ...Global.functions import hide_collection_in_viewport, unhide_collection_in_viewport, hide_collection_in_render
from .common_list_methods import CommonList
from .activators_list import Activators_list



""" Activators Layers List """

convert = 255.0
# iconos y su correspondiente color:
color_icons_and_colors = {
                    'SEQUENCE_COLOR_01': [225/convert, 96/convert, 92/convert, 1],
                    'SEQUENCE_COLOR_02': [240/convert, 162/convert, 85/convert, 1],
                    'SEQUENCE_COLOR_03': [240/convert, 219/convert, 85/convert, 1],
                    'SEQUENCE_COLOR_04': [122/convert, 203/convert, 122/convert, 1],
                    'SEQUENCE_COLOR_05': [93/convert, 181/convert, 233/convert, 1],
                    'SEQUENCE_COLOR_06': [140/convert, 89/convert, 217/convert, 1],
                    'SEQUENCE_COLOR_07': [197/convert, 114/convert, 183/convert, 1],
                    'SEQUENCE_COLOR_08': [121/convert, 84/convert, 65/convert, 1],
                    'SEQUENCE_COLOR_09': [95/convert, 95/convert, 95/convert, 1],
                }

# Relaciones de types con su color de iconos:
types_and_color_icons = {
            'DYNAMIC':          'SEQUENCE_COLOR_01', 
            'DEACTIVATION':     'SEQUENCE_COLOR_02', 
            'VERTEX_GROUPS':    'SEQUENCE_COLOR_03', 
            'KINEMATIC':        'SEQUENCE_COLOR_04', 
            'INITIALVEL':       'SEQUENCE_COLOR_04', 
            'CONSTRAINTS':      'SEQUENCE_COLOR_06'
        }

class RBDLAB_UL_draw_ac_layers(UIList):

    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        self.use_filter_show = False

        if not item.id_name:
            layout.prop(item, "remove", text="Clear", icon='X')
            return

        row = layout.row(align=True)
        
        sep_fac = 1.2

        # items:
        curr_type = item.get_type(item)
        row.label(text="", icon=types_and_color_icons[curr_type])
        
        compute = row.row(align=True)
        compute.separator(factor=sep_fac)
        compute.separator(factor=sep_fac)

        # compute.scale_x = 1
        compute.prop(item, "compute", text="")

        row.prop(item, "label_txt", text="", emboss=False) #, icon='GROUP_VERTEX')

        # Si tiene creado el metal mesh, para visualizar o el metal o los chunks o ambos:
        right_sect = row.row(align=True)
        right_sect.alignment = 'RIGHT'
        
        # Recorded icon:
        rec_bt = right_sect.row(align=True)
        rec_bt.separator(factor=sep_fac)
        rec_bt.scale_x = 1.2
        rec_bt.label(text="", icon='KEYFRAME_HLT' if item.recorded else 'KEYFRAME')
        
        right_sect.separator(factor=sep_fac)

        # Select icon:
        sel_bt = rec_bt.row(align=True)
        sel_bt.enabled = item.visible
        sel_bt.prop(item, "select_includes", text="", icon='RESTRICT_SELECT_OFF' if item.select_includes else 'RESTRICT_SELECT_ON', emboss=False)
        
        right_sect.separator(factor=sep_fac)
        
        # Visibility icon:
        right_sect.prop(item, "visible", text="", icon='HIDE_OFF' if item.visible else 'HIDE_ON', emboss=False)
        right_sect.separator(factor=sep_fac)

        # Remove icon:
        rm_button = right_sect.row(align=True)
        rm_button.alert = True
        rm_button.scale_x = 1.2
        rm_button.operator("rbdlab.ac_layers_rm_item", text="", emboss=False, icon='X').id_to_rm = item.id_name



class Ac_layers_lst_StoredObjects(PropertyGroup):
    ob: PointerProperty(type=Object)

class Ac_layers_lst_StoredTypes(PropertyGroup):
    type: StringProperty(default="")


class Ac_layers_lst_item(PropertyGroup):
    label_txt: StringProperty(name="Name")
    id_name: StringProperty(name="ID")
    from_coll: PointerProperty(type=Collection)
    activators_list: PointerProperty(type=Activators_list)
    type: StringProperty(name="Type")

    # para guardar el color actual del type:
    r_c: FloatProperty(name="Red Color", default=-1)
    g_c: FloatProperty(name="Green Color", default=-1)
    b_c: FloatProperty(name="Blue Color", default=-1)
    a_c: FloatProperty(name="Alpha Color", default=1)

    stored_includes: CollectionProperty(type=Ac_layers_lst_StoredObjects)
    def add_ob(self, ob:Object) -> None:
        # prevenimos guardar objectos que ya esten guardados:
        if not any(ob_item.ob == ob for ob_item in self.stored_includes):
            _item = self.stored_includes.add()
            _item.ob = ob
    
    # para poder borrar stored_includes:
    def remove_ob_by_name(self, ob: Object) -> None:
        for i, ob_item in enumerate(self.stored_includes):
            if ob_item.ob and ob_item.ob == ob:
                self.stored_includes.remove(i)
                break  # Salimos del bucle después de encontrar el objeto y eliminarlo
    
    def do_remove(self, context):
        scn = context.scene
        rbdlab = scn.rbdlab

        ac_layers_list = rbdlab.lists.ac_layers_list
        ac_layers_list.remove_item(self.id_name)
        ac_layers_list.list_index = 0

    remove: BoolProperty(
        default=False, 
        update=do_remove
    )

    def select_includes_update(self, context):
        scn = context.scene
        rbdlab = scn.rbdlab

        ac_layers_list = rbdlab.lists.ac_layers_list
        chunks = ac_layers_list.get_includes_by_id(self.id_name)
        selected_objects = [ob.select_set(self.select_includes) for ob in chunks]

        if self.select_includes and not selected_objects:
            print("No objects are included in this layer!")


    select_includes: BoolProperty(
        default=False, 
        update=select_includes_update
    )

    def visible_update(self, context):
        scn = context.scene
        rbdlab = scn.rbdlab

        ac_layers_list = rbdlab.lists.ac_layers_list
        chunks = ac_layers_list.get_includes_by_id(self.id_name)
        [ob.hide_set(not self.visible) for ob in chunks]


    visible: BoolProperty(
        default=True, 
        update=visible_update
    )

    compute: BoolProperty(
        name="Compute",
        description="Mark for Recording",
        default=True
    )

    recorded: BoolProperty(name="Recorded", default=False)
    #------------------------------------------------------------------------------------------------------------------------------
    # Other Properties:
    #------------------------------------------------------------------------------------------------------------------------------
    # Panel Dynamic:
    def start_on_off_toggle_update(self, context):
        scn = context.scene
        rbdlab = scn.rbdlab

        ac_layers_list = rbdlab.lists.ac_layers_list
        chunks = ac_layers_list.get_includes_by_id(self.id_name)
        value = True if self.start_on_off_toggle == 'ON' else False
        [setattr(ob.rigid_body, "enabled", value) for ob in chunks]

    start_on_off_toggle: EnumProperty(
        name="Start Mode", 
        description="Start with Dynamic On/Off",
        items=[
            ('ON', "Start On", "", 0),
            ('OFF', "Start Off", "", 1),
        ],
        default='OFF',
        update=start_on_off_toggle_update
    )

    actions: EnumProperty(
        items=[
            ('ON',      "On",       "Turn On Dynamics",     '', 0),
            ('OFF',     "Off",      "Turn Off Dynamics",    '', 1),
            ('ON_OFF',  "On/Off",   "Turn On/Off Dynamics", '', 2),
            ('OFF_ON',  "Off/On",   "Turn Off/On Dynamics", '', 3),
        ],
        default='ON',
    )
    frames_between_actions: IntProperty(
        min=0,
        # soft_max=10,
        default=3,
        description="Frames",
    )
    # copy_to_dynamic_anim: BoolProperty(default=False)

    # passes: EnumProperty(
    #     items=(
    #         ('1', '1', " "),
    #         ('2', '2', ""),
    #         ('3', '3', "")
    #     ),
    #     description="Passes to be performed by activators to compute. The more passes the better, but the longer it will take.",
    #     default='1',
    # )
    passes: IntProperty(
        min=1,
        max=3,
        default=1,
        description="Passes to be performed by activators to compute. The more passes the better, but the longer it will take.",
    )
    
    

    #------------------------------------------------------------------------------------------------------------------------------
    # Ahora hay un enum por cada layer type maestro, y todos traen settings + su correspondiente:

    def get_type(self, item):
        return item.type


    def activators_sect_sync(self, context):

        scn = context.scene
        rbdlab = scn.rbdlab

        tcoll_list = rbdlab.lists.target_coll_list
        tcoll = tcoll_list.active
        
        if not tcoll:
            print("Not valid Target Collection!")
            return
        
        ac_layers_list = rbdlab.lists.ac_layers_list
        if ac_layers_list.is_void:
            print("Activators list is void!")
            return
        
        all_items = ac_layers_list.get_all_items
        if not all_items:
            print("Cant get all item in the Activators list!")
            return

        relations_types_and_props = {
                            'KINEMATIC':        "activators_sect_init_vel", 
                            'CONSTRAINTS':      "activators_sect_constraints", 
                            'VERTEX_GROUPS':    "activators_sect_vertex_group",
                            'DYNAMIC':          "activators_sect_dynamics", 
                            'DEACTIVATION':     "activators_sect_deactivation", 
                        }
        
        # Obtengo el type del self item actual del listado:
        self_item_type = self.get_type(self)
        # Obtengo el nombre de la propiedad que le corresponde vinculada al tipo:
        self_item_prop = relations_types_and_props[self_item_type]
        # Obtengo el valor de la propiedad en cuestion:
        self_value = getattr(self, self_item_prop)

        # Me recorro todos los items:
        for item in all_items:
            
            # si es el mismo que tengo en self, skipeamos:
            if self.id_name == item.id_name:
                continue

            # Obtengo el type del item actual del loop del resto de items:
            other_item_type = self.get_type(item)
            # Obtengo el nombre de la propiedad que le corresponde vinculada al tipo:
            other_item_prop = relations_types_and_props[other_item_type]
            # Obtengo el valor de la propiedad en cuestion:
            other_value = getattr(item, other_item_prop)

            # Solo si es opposite:
            # Si el valor del self no es 'ACTIVATORS' (el comun en todos los enum de pares), entonces es el opposite:
            if self_value != 'ACTIVATORS':
                # Recuperamos el opposite del item actual en el loop del resto de items:
                # Sobreescribimos self_value con el nuevo value obtenido del item del loop en lugar del self, para q luego sea seteado:
                self_value = next((item.identifier for item in self.bl_rna.properties[other_item_prop].enum_items if item.identifier != 'ACTIVATORS'), None)
            
            # Si el valor previo del other item del loop, es igual al valor nuevo del self item valuem skipeamos:
            if other_value == self_value:
                continue

            # Seteamos el nuevo valor:
            setattr(item, other_item_prop, self_value)
            

    activators_sect_deactivation: EnumProperty(
        items=(
            # ('DEACTIVATION',        "Deactivation",     "",     'LOCKVIEW_OFF', 1),
            ('NONE',                  "",               "",     '',             0),
            ('ACTIVATORS',            "Activators",     "",     'SETTINGS',     1),
        ),
        default='ACTIVATORS',
        update=activators_sect_sync
    )
    activators_sect_constraints: EnumProperty(
        items=(
            ('CONSTRAINT',          "Constrinats",      "",     'MOD_SIMPLIFY', 0),
            ('ACTIVATORS',          "Activators",       "",     'SETTINGS',     1),
        ),
        default='CONSTRAINT',
        update=activators_sect_sync
    )
    activators_sect_dynamics: EnumProperty(
        items=(
            ('DYNAMIC',            "Dynamics",     "",     'ORIENTATION_GIMBAL',    0), # FORCE_MAGNETIC
            ('ACTIVATORS',         "Activators",   "",     'SETTINGS',              1),
        ),
        default='DYNAMIC',
        update=activators_sect_sync
    )
    activators_sect_init_vel: EnumProperty(
        items=(
            ('INIT_VEL',            "Initial Velocity", "",     'IPO_ELASTIC',  0),
            ('ACTIVATORS',          "Activators",       "",     'SETTINGS',     1),
        ),
        default='INIT_VEL',
        update=activators_sect_sync
    )
    activators_sect_vertex_group: EnumProperty(
        items=(
            ('VERTEX_GROUPS',        "Vertex Group",     "",     'STICKY_UVS_LOC',   0),
            ('ACTIVATORS',           "Activators",       "",     'SETTINGS',         1),
        ),
        default='VERTEX_GROUPS',
        update=activators_sect_sync
    )
    #------------------------------------------------------------------------------------------------------------------------------


class Ac_layers_list(PropertyGroup, CommonList):

    def list_index_update(self, context):

        item = self.active
        if not item:
            return
        
        #-----------------------------------------------------
        # solo cambiamos de color si no fue recorded primero:
        # scn = context.scene
        # rbdlab = scn.rbdlab
        # tcoll_list = rbdlab.lists.target_coll_list
        # tcoll = tcoll_list.active
        #
        # if not tcoll:
        #     return
        #
        # if "activators_recorded" in tcoll:
        #     return
        # fin check de si fue recorded primero.
        #-----------------------------------------------------
        
        curr_type = self.get_current_type
        includes = self.get_current_includes
        
        if curr_type and includes:
            for ob in includes:
                ob.color = color_icons_and_colors[types_and_color_icons[curr_type]]

        # addon_preferences = RBDLabPreferences.get_prefs(context)

    list_index: IntProperty(name="Layer List", description="The Layer List", default=-1, update=list_index_update)
    list: CollectionProperty(type=Ac_layers_lst_item)


    def add_item(self, label_txt:str, item_id:str, tcoll:Collection, objects:List[Object], work_with:str) -> None:

        item = self.list.add()
        item.id_name = item_id
        item.label_txt = label_txt
        item.from_coll = tcoll

        # agregamos los objetos (los includes):
        if objects:
            [item.add_ob(ob) for ob in objects]
        
        if work_with:
            item.type = work_with
        
            # Guardo su color (r,g,b,a) en el item
            # para poder hacer la animcacion de desvanecimiento de activacion:
            curr_type = item.get_type(item)
            item.r_c = color_icons_and_colors[types_and_color_icons[curr_type]][0]
            item.g_c = color_icons_and_colors[types_and_color_icons[curr_type]][1]
            item.b_c = color_icons_and_colors[types_and_color_icons[curr_type]][2]
            item.a_c = color_icons_and_colors[types_and_color_icons[curr_type]][3]
        
        # seteamos el ultimo elemento como activo:
        self.list_index = self.length-1

 

    @property
    def clear_includes(self):
        
        active = self.active
        if not active:
            return
        
        active.stored_includes.clear()


    @property
    def get_all_includes(self):
        return list(set([o.ob for item in self.list for o in item.stored_includes]))


    @property
    def get_all_computable_includes(self):        
        return list(set([o.ob for item in self.list if item.compute for o in item.stored_includes]))
    

    @property
    def store_activators_in_chunks(self) -> None:
        # Guardo los activators que le corresponden a cada chunk:
        for item in self.list:
            activators_list = item.activators_list
            for o in item.stored_includes:
                ob = o.ob
                
                if RBDLabNaming.CHUNK_ACTIVATORS not in ob:
                    ob[RBDLabNaming.CHUNK_ACTIVATORS] = activators_list.get_all_activators
                else:

                    # BUG reportado, si ob[RBDLabNaming.CHUNK_ACTIVATORS] estaba vacio daba error.
                    
                    chunks_activators = ob[RBDLabNaming.CHUNK_ACTIVATORS]
                    activators = activators_list.get_all_activators

                    # Se usa or para verificar si al menos una de las listas tiene elementos:
                    if len(chunks_activators) > 0 or len(activators) > 0:
                        
                        # Se utiliza set(chunks_activators) | set(activators) para crear un conjunto combinado de elementos únicos de ambas listas.
                        # Sería equivalente a set(lista1 + lista2)
                        combined_activators = set(chunks_activators) | set(activators)
                        
                        # Se actualiza ob[RBDLabNaming.CHUNK_ACTIVATORS] solo si hay elementos en al menos una de las listas.
                        ob[RBDLabNaming.CHUNK_ACTIVATORS] = list(combined_activators)

    

    @property
    def get_all_computable_includes_from_active(self):

        active = self.active
        if not active:
            return
        
        if not active.compute:
            return
        
        return [o.ob for o in active.stored_includes]        

    @property
    def get_current_includes(self):
        
        active = self.active
        if not active:
            return

        return list(set([o.ob for o in active.stored_includes]))

    
    @property
    def get_all_types(self):
        return [item.type for item in self.list ]
    
    
    @property
    def get_all_computable_types(self):
        return list(set([item.type for item in self.list if item.compute]))
    
    @property
    def get_all_computable_items(self):
        return list(set([item for item in self.list if item.compute]))
    
    @property
    def get_all_items(self):
        return list(set([item for item in self.list]))


    @property
    def get_all_computable_activators(self):

        items = self.get_all_computable_items
        if items:
            
            all_activators = set()

            for layer in items:
                all_activators_items = layer.activators_list.get_all_items
                for item in all_activators_items:

                    # solo los que esten marcados como para computar:
                    if not item.compute:
                        continue
                    
                    all_activators.add(item.activator)
            
            if all_activators:
                return all_activators
    

    @property
    def get_all_computable_activators_from_active(self):

        active = self.active
        if not active:
            return

        # return active.activators_list.get_all_activators
        return active.activators_list.get_all_computable_activators
    

    @property
    def has_any_activator_with_mesh_type(self):

        items = self.get_all_computable_items
        if items:
            
            for layer in items:
            
                all_activators_items = layer.activators_list.get_all_items
                for item in all_activators_items:

                    # solo los que esten marcados como para computar:
                    if not item.compute:
                        continue

                    if item.type == 'MESH':
                        return True
                    
        return False
    

    def set_all_computable_recorded(self, in_status:bool) -> None:
        items = self.get_all_computable_items
        if items:
            for layer in items:
                
                # Para evitar poner el icono de keyframes si no tiene activators validos:
                all_computable_activators = layer.activators_list.get_all_computable_activators
                if len(all_computable_activators) < 1:
                    continue

                layer.recorded = in_status



    @property
    def get_current_type(self):
        active = self.active
        if not active:
            return
        return active.type
    

    def get_includes_by_id(self, id_name):
        for list_item in self.list:
            if list_item.id_name == id_name:
                return list(set([o.ob for o in list_item.stored_includes]))

    def get_color_by_id(self, id_name):
        # Nota: guardo el color por type en el item del listado, para poder recuperarlo luego.
        for list_item in self.list:
            if list_item.id_name == id_name:
                return [list_item.r_c, list_item.g_c, list_item.b_c, list_item.a_c]


    def get_item_from_active_group_id(self, active_group_id):
        return next((item.id_name for item in self.list if item.from_active_group == active_group_id), None) 


    def check_if_ob_in_any_item_by_type(self, ob:Object, target_type:str) -> bool:
        all_items = list(set([item for item in self.list if item.type == target_type]))

        stored_obs = set()
        
        for item in all_items:
            for o in item.stored_includes:
                stored_obs.add(o.ob)
        
        return ob in stored_obs