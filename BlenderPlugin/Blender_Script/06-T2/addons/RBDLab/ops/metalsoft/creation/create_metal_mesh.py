import bpy
from uuid import uuid4
from typing import List, Dict
from ....props.metal.metal import RBDLabMetalData
from bpy.types import Operator, Object, Collection
from collections import defaultdict
from ....addon.naming import RBDLabNaming
from ....Global.get_common_vars import get_common_vars
from ..common.reorder_modifiers import reorder_modifiers
from ....Global.functions import (
                                    create_modifier, 
                                    set_active_collection_by_name, 
                                    create_new_collection, 
                                    set_active_object, 
                                    hide_collection_in_viewport, 
                                    hide_collection_in_render, 
                                    set_active_collection_by_name, 
                                    create_originals_coll_if_not_exist,
                                    create_coll_if_not_exist
                                )


class RBDLAB_OT_create_metal_mesh(Operator):
    bl_idname = "rbdlab.metalsoft_creation_create_metal_mesh"
    bl_label = "Create Metal Mesh"
    bl_options = {'REGISTER', 'UNDO'}


    @classmethod
    def description(cls, _context, properties):
        return "Create Metal Mesh"
    

    def link_objects_to_collection(self, objects:List[Object], org_ob:Object, metal_links_coll:Collection) -> Collection:
        
        coll_id = str(uuid4())[:8]
        coll_name: str = coll_id

        or_link: Collection = bpy.data.collections.get(coll_name)
        if not or_link:
            or_link = bpy.data.collections.new(coll_name)

        if or_link:
            if or_link.name not in metal_links_coll.children:
                metal_links_coll.children.link(or_link)
                or_link[RBDLabNaming.METAL_LINKS_COLL] = True

        for ob in objects:
            if ob.name not in or_link.objects:
                or_link.objects.link(ob)

        return or_link


    def unified_methods(self, 
                        metal_props:RBDLabMetalData, 
                        chunks: List[Object], 
                        metal_links_coll: Collection, 
                        low_poly_objects: List[Object], 
                        high_poly_objects: List[Object]) -> Dict[Object, Collection]:
        
        org_ob_coll = defaultdict(list)
        metal_links_colls = set()

        # Determine the method to use based on the condition other_original bool:
        # Nota: Other original solo funciona con un unico objeto, si se quiere usar multiples hay que usar use_multiple_proxys.
        if metal_props.other_original:
            
            # Other Original Method:
            #---------------------------------------------------------------------------------------------------
            # Trabajamos con el single Other from:
            org_ob: Object = metal_props.ob_original_selector
            # org_ob_name: str = org_ob.name
            
            # Guardamos sus objetos (chunks) del other from:
            # objects: List[Object] = [ob for ob in chunks if ob.get("rbdlab_from") == org_ob_name]

            # Independientemente de si se llaman igual que el que se supone que era su original, usamos todos los chunks del tcoll, en lugar 
            # de objects, porque Tebito usa objetos proxy con otros nombres que no tienen porque cohincidir con el nombre del from que fuera:
            or_link: Collection = self.link_objects_to_collection(chunks, org_ob, metal_links_coll)
            metal_links_colls.add(or_link)
            org_ob_coll[org_ob] = or_link

        else:
            
            #------------------------------------------------------------------------------------------------------------------------------
            # Si usamos Auto Match Proxys (cuanto tienes objetos proxy modelados a mano en su collection MetalSoft_Proxys):
            if metal_props.use_multiple_proxys:

                # NOTA: Como el high podría tener dimensiones bastante diferentes a los proxy (imagina una antena larga y el proxy sin antena) 
                # ahora lo haremos por cohincidencia de origenes:

                for low_poly_obj in low_poly_objects:

                    for high_poly_obj in high_poly_objects:

                        # Recuerda que al trabajar con números de punto flotante, puede haber pequeñas variaciones debido a la 
                        # representación de punto flotante en la computadora. En este caso, es útil comparar si las diferencias son muy pequeñas 
                        # en lugar de exactamente iguales.

                        # Comparo si los vectores de location son muy similares:
                        umbral = 1e-6  # 1e-6 representa el número decimal 0.000001
                        similar_locations = all(abs(v1 - v2) < umbral for v1, v2 in zip(low_poly_obj.location, high_poly_obj.location))

                        if similar_locations:
                            # Establece una relación entre los objetos utilizando una propiedad personalizada o cualquier otro método
                            low_poly_obj["linked_high_poly"] = high_poly_obj.name


            
            # fin de trozo de integracion de Auto Match Proxys ----------------------------------------------------------------------------
            #------------------------------------------------------------------------------------------------------------------------------
            

            # Automatic Original Method:
            #---------------------------------------------------------------------------------------------------
            ob_by_from = defaultdict(list)
            target_prop = "linked_high_poly"

            # por cada from:
            for ob in chunks:
    
                from_name: str = ob.get("rbdlab_from")
                if from_name:
                    
                    #--------------------------------------------------------------------------------------------------------------
                    # Si usamos Auto Match Proxys (cuanto tienes objetos proxy modelados a mano en su collection MetalSoft_Proxys):
                    if metal_props.use_multiple_proxys:
                        # obtengo el objeto proxy:
                        from_ob: Object = bpy.data.objects.get(from_name)
                        if from_ob:
                            # si existe y tiene el property del high:
                            if target_prop in from_ob:
                                # ocultamos el proxy:
                                from_ob.hide_set(True)
                                # guardamos el nombre del high como si fuera su from:
                                from_name: str = from_ob.get(target_prop)
                    # fin de trozo de integracion de Auto Match Proxys ------------------------------------------------------------
                    #--------------------------------------------------------------------------------------------------------------
            
                    # Guardamos un diccionario con el key el from y sus objetos (chunks) correspondientes:
                    ob_by_from[from_name].append(ob)

            # por cada objeto trabajamos con sus froms:
            for org_ob_name, objects in ob_by_from.items():

                org_ob: Object = bpy.data.objects.get(org_ob_name)
                
                if not org_ob:
                    continue

                or_link: Collection = self.link_objects_to_collection(objects, org_ob, metal_links_coll)
                metal_links_colls.add(or_link)
                
                org_ob_coll[org_ob] = or_link

        return org_ob_coll, metal_links_colls
    

    def clean_chunks(self, tcoll_item) -> None:

        """ hacemos un clean primero, para q pueda bindear """

        metal_props = tcoll_item.metal_props
        
        # Guardamos las opciones de ui previamente:
        prev_metal_decimate_planar = metal_props.metal_decimate_planar
        prev_metal_triangulate = metal_props.metal_triangulate
        prev_metal_remove_doulbes = metal_props.metal_remove_doulbes
        prev_use_boundary = metal_props.use_boundary
        prev_use_multi_face = metal_props.use_multi_face

        # Seteamos nuestra limpieza:
        metal_props.metal_decimate_planar = True
        metal_props.metal_triangulate = True
        metal_props.metal_remove_doulbes = True
        metal_props.use_boundary = True
        metal_props.use_multi_face = True
        
        # Limpiamos:
        bpy.ops.rbdlab.metalsoft_creation_clean_fractures()

        # restauramos los previos:
        metal_props.metal_decimate_planar = prev_metal_decimate_planar
        metal_props.metal_triangulate = prev_metal_triangulate
        metal_props.metal_remove_doulbes = prev_metal_remove_doulbes
        metal_props.use_boundary = prev_use_boundary
        metal_props.use_multi_face = prev_use_multi_face


    def execute(self, context):

        scn, rbdlab, tcoll_list = get_common_vars(context, get_scn=True, get_rbdlab=True, get_tcoll_list=True)

        tcoll = tcoll_list.active

        if not tcoll:
            self.report({'ERROR'}, "Not valid Target Collection!!")
            return {'CANCELLED'}
        
        tcoll_item = tcoll_list.active_item
        metal_list = tcoll_item.metal_list
        metal_props = tcoll_item.metal_props
        
        #--------------------------------------------------------------------------------------------------------------
        # Si usamos Auto Match Proxys (cuanto tienes objetos proxy modelados a mano en su collection MetalSoft_Proxys):
        if metal_props.use_multiple_proxys:
            lows_coll = bpy.data.collections.get(RBDLabNaming.METAL_SOFT_PROXYS)
            if not lows_coll:
                self.report({'ERROR'}, "No " + RBDLabNaming.METAL_SOFT_PROXYS + " detected!")
                return {'CANCELLED'}
            
            low_poly_objects = lows_coll.objects[:]
            if len(low_poly_objects) < 1:
                self.report({'ERROR'}, "Put yours low poly proxys in " + RBDLabNaming.METAL_SOFT_PROXYS + " collection first!")
                return {'CANCELLED'}
            
            orgs_coll = bpy.data.collections.get(RBDLabNaming.ORIGINALS)
            if not lows_coll:
                self.report({'ERROR'}, "No " + RBDLabNaming.ORIGINALS + " detected!")
                return {'CANCELLED'}
            
            high_poly_objects = orgs_coll.objects[:]
            if len(high_poly_objects) < 1:
                self.report({'ERROR'}, "Put yours high poly objects in " + RBDLabNaming.METAL_SOFT_PROXYS + " collection first!")
                return {'CANCELLED'}
        
        else:
            # Si no usamos automatic match de los proxys, le pasamos a unified_methods los arrays vacios, para que no proteste:
            low_poly_objects = [] 
            high_poly_objects = []
        
        # fin de trozo de integracion de Auto Match Proxys ------------------------------------------------------------
        #--------------------------------------------------------------------------------------------------------------
        

        # nos aseguramos de que si se quiere usar other from, exista uno valido:
        if metal_props.other_original:
            if metal_props.ob_original_selector is None:
                self.report({'ERROR'}, "Invalid Other Object!")
                return {'CANCELLED'}

        current_item_names = metal_list.get_all_items_names
        if tcoll.name in current_item_names:
            self.report({'WARNING'}, tcoll.name + " already added!!")
            return {'CANCELLED'}
        
        originals_coll = create_originals_coll_if_not_exist(context, rbdlab)
        create_coll_if_not_exist(context, rbdlab, originals_coll, RBDLabNaming.METAL_SOFT_PROXYS)
        
        # desocultamos los chunks:
        item = tcoll_list.active_item
        item.visibility = True

        # tcoll[RBDLabNaming.CREATED_METAL_MESH] = True
        chunks = tcoll_list.get_current_active_tcoll_valild_objects(context)

        # Creamos RBDLab_Metal_Meshes Collection:
        metal_meshesh_coll = create_new_collection(context, RBDLabNaming.METAL_MESHES)
        set_active_collection_by_name(context, RBDLabNaming.METAL_MESHES)
        hide_collection_in_render(RBDLabNaming.METAL_MESHES)

        # Creamos la subCollection Metal_Links:
        # NOTA: si te aparecen muchas collections en Metal links, cuidado porque pueden ser del orphan data de Tebito de hacer pruebas, 
        # ya que estoy recuperando la collection si existe previamente, así que limpiar las escenas de prueba si tuvieran metal links residuales en el limbo.
        metal_links_coll = bpy.data.collections.get(RBDLabNaming.METAL_LINKS_COLL)
        if not metal_links_coll:
            metal_links_coll = bpy.data.collections.new(RBDLabNaming.METAL_LINKS_COLL)
            hide_collection_in_render(RBDLabNaming.METAL_LINKS_COLL)

        if metal_links_coll.name not in metal_meshesh_coll.children:
            metal_meshesh_coll.children.link(metal_links_coll)

        self.clean_chunks(tcoll_item)

        # Usando el metodo de Single Other From, o el Automatic froms:
        org_ob_coll, metal_links_collections = self.unified_methods(metal_props, chunks, metal_links_coll, low_poly_objects, high_poly_objects)

        all_gn_obs = set()
        current_frame = scn.frame_current
        
        # seteamos RBDLab_Metal_Meshes como collection activa, para crear dentro los GN:
        set_active_collection_by_name(context, RBDLabNaming.METAL_MESHES)

        # Por cada "from" (el objeto original), creo un plane con el GN: 
        for org_ob, coll in org_ob_coll.items():

            org_ob_name = org_ob.name

            bpy.ops.mesh.primitive_plane_add(size=2, enter_editmode=False, align='WORLD', location=(0, 0, 0), scale=(1, 1, 1))
            GN_ob = context.active_object
            GN_ob.name = org_ob_name + RBDLabNaming.SUFIX_DUMMY_METAL_OB
            all_gn_obs.add(GN_ob)

            bpy.ops.object.modifier_add(type='NODES')
            GN_mod = GN_ob.modifiers[-1]

            # Creando el node group:
            node_group = bpy.data.node_groups.new(GN_ob.name, "GeometryNodeTree")
            nodes = node_group.nodes

            # conectamos el nodegroup al modifier:
            GN_mod.node_group = node_group

            # Creando los nodos:
            node_input = nodes.new("NodeGroupInput")
            node_input.select = False

            if bpy.app.version < (4, 0, 0):
                node_group.inputs.new("NodeSocketGeometry", "Geometry")
            else: # Blender 4.0 en adelante:
                node_group.interface.new_socket("Geometry", description="Geometry", in_out='INPUT', socket_type='NodeSocketGeometry', parent=None)

            
            node_output = nodes.new("NodeGroupOutput", )
            node_output.select = False
            node_output.location.x += 550

            if bpy.app.version < (4, 0, 0):
                node_group.outputs.new("NodeSocketGeometry", "Geometry")
            else: # Blender 4.0 en adelante:
                node_group.interface.new_socket("Geometry", description="Geometry", in_out='OUTPUT', socket_type='NodeSocketGeometry', parent=None)


            coll_info = nodes.new("GeometryNodeCollectionInfo")
            coll_info.select = False
            coll_info.location.y += 200
            coll_info.transform_space = 'RELATIVE'
            coll_info.inputs["Collection"].default_value = coll

            realize_instances = nodes.new("GeometryNodeRealizeInstances")
            realize_instances.select = False
            realize_instances.location.x += 250
            realize_instances.location.y += 100

            # Haciendo las conexiones:
            node_group.links.new(coll_info.outputs['Instances'], realize_instances.inputs['Geometry'])
            node_group.links.new(realize_instances.outputs['Geometry'], node_output.inputs['Geometry'])


            triangulate_mod = create_modifier(GN_ob, RBDLabNaming.TRIANGULATE, 'TRIANGULATE')

            displace_mod = create_modifier(org_ob, RBDLabNaming.DISPLACE_FOR_DDFORM, 'DISPLACE')
            displace_mod.strength = 0.001

            surface_deform_mod = create_modifier(org_ob, RBDLabNaming.SURFACE_DEFORM, 'SURFACE_DEFORM')
            surface_deform_mod.target = GN_ob

            reorder_modifiers(org_ob)
            
            # bindeo:
            scn.frame_set(scn.frame_start)
            set_active_object(context, org_ob)
            bpy.ops.object.surfacedeform_bind(modifier=RBDLabNaming.SURFACE_DEFORM)

            org_ob.hide_set(False)
            org_ob.hide_render = False
            GN_ob.hide_set(True)

        if current_frame != scn.frame_current:
            scn.frame_set(current_frame)

        hide_collection_in_viewport(context, tcoll.name)
        hide_collection_in_render(tcoll.name)

        for coll in org_ob_coll.values():
            hide_collection_in_viewport(context, coll.name)


        # agregamos el item a la lista y guardamos la data:
        item_list_id = str(uuid4())[:8]
        metal_list.add_item(
            tcoll.name, 
            item_list_id, 
            tcoll=tcoll,
            from_coll_id=tcoll_item.id_name, 
            originals = list(org_ob_coll.keys()), 
            link_coll=list(metal_links_collections), 
            GN_ob=list(all_gn_obs)
        )

        return {'FINISHED'}
