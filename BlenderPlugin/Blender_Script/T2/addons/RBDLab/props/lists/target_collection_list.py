import bpy
from uuid import uuid4
from typing import List
from bpy.types import PropertyGroup, Collection, Operator, Menu, Area, Object
from bpy.props import BoolProperty, IntProperty, PointerProperty, CollectionProperty, StringProperty, EnumProperty
from ...Global.functions import hide_collection_in_viewport, unhide_collection_in_viewport, hide_collection_in_render
from bpy.types import UIList
from bpy.props import BoolProperty
from ...addon.naming import RBDLabNaming
from .metal_list import MetalList
from ..metal.metal import RBDLabMetalData
from ...Global.lists import reorder_list
from ...Global.basics import context_override
from ...Global.get_common_vars import get_common_vars

""" Target Collection list """


class RBDLAB_UL_draw_target_coll_list(UIList):
    case_sensitive: BoolProperty(name="aA", description="Use case sensitive or not", default=False)

    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):

        # Si el item es None:
        if item is None:
            layout.prop(item, "remove", text="Clear", icon='X')
            return
        
        # Si el item no tiene id_name:
        if not item.id_name:
            layout.prop(item, "remove", text="Clear", icon='X')
            return
        
        # Si el item no tiene Collection:
        if not item.coll:
            layout.prop(item, "remove", text="Clear", icon='X')
            return

        rbdlab = get_common_vars(context, get_rbdlab=True)

        tcoll = item.coll
        id_name = item.id_name
        row = layout.row(align=True)

        # no permitir renombrar la collection:
        row.label(text=tcoll.name, icon_value=layout.icon(tcoll))
        # row.prop(tcoll, "name", text="", emboss=False, icon_value=layout.icon(tcoll))

        have_rbdlab_boolean_mod = rbdlab.have_rbdlab_boolean_modifier()
        right_icons = layout.row(align=True)
        right_icons.enabled = not have_rbdlab_boolean_mod

        # si tiene rbd muestro icono:
        if RBDLabNaming.COLL_WITH_RBD in tcoll:
            # los activamos o desactivamos su Dynamic:
            right_icons.prop(item, "enable_disable_rbd", text="", icon='PHYSICS'
                             if item.enable_disable_rbd else 'MESH_CIRCLE', emboss=False)

        # si tiene particulas muestro icono:
        if RBDLabNaming.COLL_WITH_PARTICLES in tcoll:
            icon = 'PARTICLE_DATA' if item.enable_disable_particles else 'MOD_PARTICLES'
            right_icons.prop(item, "enable_disable_particles", text="", icon=icon, emboss=False)

        # si tiene smoke:
        if RBDLabNaming.COLL_WITH_SMOKE in tcoll:
            icon = 'OUTLINER_OB_VOLUME' if item.enable_disable_smoke else 'VOLUME_DATA'
            right_icons.prop(item, "enable_disable_smoke", text="", icon=icon, emboss=False)
        
        right_icons.prop(item, "select", text="", emboss=False, icon='RESTRICT_SELECT_OFF' if item.select else 'RESTRICT_SELECT_ON')
        right_icons.prop(item, "visibility", text="", emboss=False, icon='HIDE_OFF' if item.visibility else 'HIDE_ON')

        # isolate icon:
        if item.isolate:
            icon_isolate = 'OBJECT_DATA'
        else:
            icon_isolate = 'OBJECT_HIDDEN'
        right_icons.prop(item, "isolate", text="", emboss=False, icon=icon_isolate)

        right_icons.separator(factor=0.8)
        rm_button = right_icons.row(align=True)
        rm_button.alert = True
        rm_button.operator("rbdlab.rm_target_coll_from_list", text="", emboss=False, icon='X').to_rm = id_name

    def draw_filter(self, context, layout):
        """UI code for the filtering/sorting/search area."""
        layout.separator()
        col = layout.column(align=True)
        row = col.row(align=True)
        row.prop(self, "filter_name", text="", icon='VIEWZOOM')
        case_sensititve = row.row(align=True)
        case_sensititve.scale_x = 0.35
        case_sensititve.prop(self, "case_sensitive", toggle=True, text="aA")
        row.prop(self, "use_filter_invert", text="", icon='ARROW_LEFTRIGHT')

    def filter_items(self, context, data, propname):
        items = getattr(data, propname)

        filtered_flags = []
        new_order = [i for i in range(len(items))]

        for item in items:

            if item.coll:

                if self.case_sensitive:
                    match = self.filter_name in item.coll.name
                else:
                    match = self.filter_name.lower() in item.coll.name.lower()

                if match:
                    filtered_flags.append(self.bitflag_filter_item)
                else:
                    filtered_flags.append(0)

        # print(filtered_flags, new_order)
        return filtered_flags, new_order


class ListItem(PropertyGroup):
    
    metal_props: PointerProperty(type=RBDLabMetalData)
    metal_list: PointerProperty(type=MetalList)

    coll: PointerProperty(type=Collection)
    id_name: StringProperty(default="")

    handler: PointerProperty(type=Object)

    dswitch_at_frame: IntProperty(default=-1)

    def do_remove(self, context):
        if not self.remove:
            return

        tcoll_list = get_common_vars(context, get_tcoll_list=True)

        self.remove = False
        tcoll_list.remove_coll_list(self)
        tcoll_list.list_index = len(tcoll_list.list)-1

    remove: BoolProperty(default=False, update=do_remove)

    def visibility_update(self, context):
        scn = context.scene
        rbdlab = scn.rbdlab

        coll = self.coll

        if rbdlab.low_or_high_visibility_viewport == 'High':

            # si estamos viendo los high:
            if RBDLabNaming.SUFIX_LOW in coll.name:
                target_coll_name = coll.name.replace(RBDLabNaming.SUFIX_LOW, RBDLabNaming.SUFIX_HIGH)
            else:
                target_coll_name = coll.name + RBDLabNaming.SUFIX_HIGH
        
        else:
            # si estamos viendo los low:
            target_coll_name =  coll.name

        target_coll = bpy.data.collections.get(target_coll_name) 
        
        if target_coll:

            if self.visibility:
                unhide_collection_in_viewport(context, target_coll.name)
            else:
                hide_collection_in_viewport(context, target_coll.name)

    visibility: BoolProperty(name="Visibility", description="Show or Hide this Target Collection", default=True, update=visibility_update)


    def select_update(self, context):

        rbdlab = get_common_vars(context, get_rbdlab=True)

        # tcoll_list = rbdlab.lists.target_coll_list
        coll_name = self.coll.name

        if rbdlab.low_or_high_visibility_viewport == "Low":
            target_coll_name = coll_name
        else:
            if RBDLabNaming.SUFIX_LOW in coll_name:
                target_coll_name = coll_name.replace(RBDLabNaming.SUFIX_LOW, RBDLabNaming.SUFIX_HIGH)
            else:
                target_coll_name = coll_name + RBDLabNaming.SUFIX_HIGH

        target_coll = bpy.data.collections.get(target_coll_name)
        if target_coll:
            chunks = [ob for ob in target_coll.objects if ob.type == 'MESH' and ob.visible_get() and ob.name in context.view_layer.objects]
            if chunks:
                [ob.select_set(self.select) for ob in chunks]

    select: BoolProperty(name="Select/Deselect Chunks", description="Select/Deselect all chunks in this Target Collection",  default=False, update=select_update)

    def enable_disable_rbd_update(self, context):
        coll = self.coll
        valid_objects = [ob for ob in coll.objects]

        status = self.enable_disable_rbd
        unlinkeds = False
        rbdw_coll = bpy.data.collections["RigidBodyWorld"]
        if len(valid_objects) > 0:
            for ob in valid_objects:
                if hasattr(ob, "rigid_body"):
                    if ob.rigid_body:
                        # ob.rigid_body.enabled = self.enable_disable_rbd
                        if status:
                            if not ob.name in rbdw_coll.objects:
                                rbdw_coll.objects.link(ob)
                        else:
                            if ob.name in rbdw_coll.objects:
                                rbdw_coll.objects.unlink(ob)
                                unlinkeds = True
        if unlinkeds:
            coll[RBDLabNaming.RBD_DISABLED] = True
        else:
            if RBDLabNaming.RBD_DISABLED in coll:
                del coll[RBDLabNaming.RBD_DISABLED]

    enable_disable_rbd: BoolProperty(
        name="Enable/Disable RBD",
        description="Enable/Disable RBD for this collection",
        default=True,
        update=enable_disable_rbd_update
    )

    def enable_disable_particles_update(self, context):
        # scn = context.scene
        # rbdlab = scn.rbdlab

        coll = self.coll
        # p_type = rbdlab.ui.selected_particle_type
        particle_types = ("debris", "dust", "smoke")
        valid_objects = [obj for obj in coll.objects if obj.type == 'MESH' and obj.visible_get()]
        # current_active_tcoll = rbdlab.lists.target_coll_list.active

        # para todos los tipos de particulas:
        for p_type in particle_types:

            ps_name = coll.name + "_" + p_type

            # para todos los chunks validos:
            for obj in valid_objects:
                obj_muted = False

                # si es un chunk muteado lo skipeo:
                custom_properties = list(obj.keys())
                for cp in custom_properties:
                    if cp == "rbdlab_mute_particles_" + p_type:
                        obj_muted = True

                if obj_muted:
                    continue

                # para todos los modifiers de particulas:
                for ps_modifier in obj.modifiers:

                    # si no es del tipo de particula actual skipeo:
                    if not ps_modifier.name.startswith(ps_name):
                        continue

                    # solo trabajo con la visibilidad de viewport:
                    n_v_status = self.enable_disable_particles
                    ps_modifier.show_viewport = n_v_status

                    key = "particles_%s_%s" % (p_type, "viewport")
                    coll[key] = n_v_status

    enable_disable_particles: BoolProperty(
        name="Enable/Disable Particles",
        description="Enable/Disable All Particles in viewport for this collection",
        default=True,
        update=enable_disable_particles_update
    )

    def enable_disable_smoke_update(self, context):
        coll = self.coll
        valid_objects = [ob for ob in coll.objects if ob.type == 'MESH' and ob.visible_get()]

        for obj in valid_objects:

            # si no tiene el modifier de flow skipeo:
            if RBDLabNaming.SMOKE_MOD not in obj.modifiers:
                continue

            # obtengo el modifier de particle system:
            ps_mod = [mod for mod in obj.modifiers if mod.type == 'PARTICLE_SYSTEM' and "smoke_motion_" in mod.name]

            for mod in obj.modifiers:

                # si el mod no empiza por el nombre del flow mod skipeo el mod:
                if not mod.name.startswith(RBDLabNaming.SMOKE_MOD):
                    continue

                mod.show_viewport = self.enable_disable_smoke

                # si tenía particulas:
                if ps_mod:
                    # para apagar los flow de particulas hay que desvincularas o volver a vincularlas:
                    if self.enable_disable_smoke:
                        mod.flow_settings.particle_system = ps_mod[0].particle_system
                    else:
                        mod.flow_settings.particle_system = None

    enable_disable_smoke: BoolProperty(
        name="Enable/Disable Smoke",
        description="Enable/Disable Smoke in viewport for this collection",
        default=True,
        update=enable_disable_smoke_update
    )

    # collection with:
    # with_rbd: BoolProperty(default=False)
    # with_constraints: BoolProperty(default=False)
    # with_particles: BoolProperty(default=False)
    # with_smoke: BoolProperty(default=False)

    def isolate_update(self, context):
        import bpy

        rbdlab, tcoll_list = get_common_vars(context, get_rbdlab=True, get_tcoll_list=True)

        # coll_name = self.coll.name
        # context_colls = context.view_layer.layer_collection.collection.children_recursive

        bpy.ops.object.select_all(action='DESELECT')

        # primero detecto si estamos en local view:
        areas = context.screen.areas
        is_in_local_view = len([area for area in areas if area.type == 'VIEW_3D' and area.spaces[0].local_view]) > 0
        if is_in_local_view:

            # Si estamos en local view obtenemos los objetos involucrados:
            # sobreescribir el contexto:            
            def callback(area:Area) -> None:
                area = context.area  # Accedemos al área desde el contexto
                for space in area.spaces:
                    if space.type == 'VIEW_3D':
                        objects = [ob for ob in context.view_layer.objects if ob.visible_get(viewport=space)]

                # los seleccionamos:
                for obj in objects:
                    obj.select_set(True)
                
                area.tag_redraw() 
            context_override(context=context, area_type='VIEW_3D', callback=callback)

            # si hay alguno seleccionado le quitamos el local view:
            if context.selected_objects:
                bpy.ops.view3d.localview(frame_selected=False)

        valid_objects = []
        coll = None

        # recopilamos todos los objetos del listado:
        for coll_item in tcoll_list.list:

            # seteamos cual es el coll ya sea high o low:
            if rbdlab.low_or_high_visibility_viewport == "High":
                work_coll = coll_item.coll.name.replace(RBDLabNaming.SUFIX_LOW, RBDLabNaming.SUFIX_HIGH)
                coll = bpy.data.collections.get(work_coll)
            else:
                coll = coll_item.coll

            # al haber algunas collections con high y otras con low y estar el viewport en modo high
            # posiblemente nos de un coll none ya que no se a seteado el coll de las que no tengan high
            # por eso insisto aquí para que si es none use el coll del item.
            if coll is None:
                coll = coll_item.coll

            if coll:
                # print(coll.name)
                # si tiene el isolate el item del listado:
                if coll_item.isolate:
                    # recolectamos los objetos:
                    for obj in coll.objects:
                        if obj.type == 'MESH' and obj not in valid_objects:
                            valid_objects.append(obj)
                else:
                    # si no, quitamos los objetos del listado:
                    for obj in coll.objects:
                        if obj in valid_objects:
                            valid_objects.remove(obj)

        # si hay objetos con los que trabajar:
        if valid_objects:
            # print(valid_objects)
            # deseleccionamos todo por si acaso:
            bpy.ops.object.select_all(action='DESELECT')

            # seleccionamos:
            for obj in valid_objects:
                # print(obj.name)
                obj.select_set(True)

            # y isolamos:
            if context.selected_objects:
                bpy.ops.view3d.localview(frame_selected=False)

        bpy.ops.object.select_all(action='DESELECT')

    isolate: BoolProperty(
        default=False,
        update=isolate_update
    )

    


class RBDLab_PG_TargetCollectionList(PropertyGroup):
    ''' Target Collection List '''

    def list_index_update(self, context):
        
        rbdlab, ui = get_common_vars(context, get_rbdlab=True, get_ui=True)
        
        if len(self.list) > 0:
            tcoll = self.list[self.list_index].coll

            if not tcoll:
                return
            
            rbdlab.filtered_target_collection = tcoll

            # if ui.main_modules == 'PARTICLES':

            # para bloquear solo los motion si no tiene vecinos:
            if RBDLabNaming.COMPUTED_NEIGHBORS not in tcoll:
                rbdlab.particles.debris.create.options = {'MOTION'}
                rbdlab.particles.dust.create.options = {'MOTION'}
                rbdlab.particles.smoke.create.options = {'MOTION'}
            else:
                rbdlab.particles.debris.create.options = {'BROKEN', 'MOTION'}
                rbdlab.particles.dust.create.options = {'BROKEN', 'MOTION'}
                rbdlab.particles.smoke.create.options = {'BROKEN', 'MOTION'}

    list_index: IntProperty(default=0, update=list_index_update)
    list: CollectionProperty(type=ListItem)


    def remove_coll_list(self, coll_list_item: ListItem):
        coll_index = next((i for i, item in enumerate(self.list) if item == coll_list_item), -1)
        if coll_index != -1:
            self.list.remove(coll_index)
        

    @property
    def get_all_target_collections(self) -> List[Collection]:
        return [item.coll for item in self.list]

    def get_item_by_name(self, coll_name: str) -> ListItem:
        return next((item for item in self.list if item.coll.name == coll_name), None)
    
    def get_item_by_id_name(self, id_name: str) -> ListItem:
        return next((item for item in self.list if item.id_name == id_name), None)
    
    def get_id_name_from_coll_name(self, coll_name: str) -> ListItem:
        return next((item.id_name for item in self.list if item.coll.name == coll_name), None)

    def get_coll_by_name(self, coll_name: str) -> ListItem:
        return next((item.coll for item in self.list if item.coll.name == coll_name), None)

    def add_tcoll(self, coll: Collection) -> None:
        
        # si no estaba ya la agregamos:
        all_target_collections = self.get_all_target_collections
        if coll not in all_target_collections:

            item: Collection = self.list.add()
            item.coll = coll
            item.id_name = str(uuid4())
            self.list_index = len(self.list)-1
            
            # las marcamos como nuestras para q aparezcan en el listado de Constraints:
            if 'RBDLAB' not in coll:
                coll['RBDLAB'] = 1
            
            # auto load collections for constraints:
            bpy.ops.rbdlab.const_init_work_group()
    
    @property
    def active_item(self):
        if len(self.list) > 0:
            return self.list[self.list_index]
    
    @property
    def active_item_id_name(self) -> ListItem:
        if len(self.list) > 0:
            return self.list[self.list_index].id_name

    def get_current_active_tcoll_valild_objects(self, context):
        if len(self.list) > 0:
            return [ob for ob in self.list[self.list_index].coll.objects if ob.type == 'MESH' and ob.visible_get() and ob.name in context.view_layer.objects]
    
    def get_first_valid_ob(self, context):
        if len(self.list) > 0:
            return next((ob for ob in self.list[self.list_index].coll.objects if ob.type == 'MESH' and ob.visible_get() and ob.name in context.view_layer.objects), None)
    
    @property
    def has_rigidbodies(self):
        if len(self.list) > 0:
            return next((True for ob in self.list[self.list_index].coll.objects if ob.type == 'MESH' and ob.rigid_body), False)

    @property
    def active(self):
        if len(self.list) > 0:
            return self.active_item.coll


class RBDLAB_OT_target_collection_list_item_move(Operator):
    bl_idname = "rbdlab.target_collection_list_item_move"
    bl_label = "Move Item"
    bl_description = "Move Item in List"
    bl_options = {'REGISTER', 'UNDO'}

    direction: StringProperty(default="")

    def execute(self, context):
        tcoll_list = get_common_vars(context, get_tcoll_list=True)
        reorder_list(tcoll_list, self.direction)
        return {'FINISHED'}


class RBDLAB_MT_target_collection_submenu(Menu):
    bl_label = "Target Collection List Submenu"

    def draw(self, context):

        layout = self.layout
        col = layout.column()

        tcoll_list = get_common_vars(context, get_tcoll_list=True)
        tcoll = tcoll_list.active
        
        col.operator("rbdlab.target_collection_dropdown_select_objects", text="Select All")
        col.operator("rbdlab.target_collection_dropdown_merge_collections", text="Merge Collections")
        
        if "fracture_applied" in tcoll:
            col.enabled = tcoll["fracture_applied"] == 1
        else:
            col.enabled = False
