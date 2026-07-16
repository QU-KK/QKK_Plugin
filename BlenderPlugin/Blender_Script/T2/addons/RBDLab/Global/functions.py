import re
import os
import ast
import bpy
import bmesh
from mathutils import Matrix
from mathutils import Vector
from datetime import datetime
from typing import Union, List
from mathutils.bvhtree import BVHTree
from ..addon.naming import RBDLabNaming
from bpy.types import Object, Material, Collection, Context, Area
from ..Global.basics import context_override
from addon_utils import check


###########################################################################
# BASIC FUNCTIONS
###########################################################################
from .basics import enter_object_mode, enter_edit_mode, select_object, set_active_object, deselect_all_objects


def get_constraints_from_obj(obj):
    key_constraints = RBDLabNaming.CONSTRAINTS
    if obj:
        if key_constraints in obj:
            const_a = obj[key_constraints].split()
            return const_a
        else:
            return False
    # else:
    #     print("get_constraints_from_obj no obj recived!")


def get_array_data_from_obj(context, key, obj):
    if not isinstance(obj, Object):
        if isinstance(obj, str):
            if obj in context.scene.objects:
                obj = context.scene.objects.get(obj)
        else:
            return False

    if key in obj:
        data = obj[key].split()
        return data
    else:
        return False

# def append_constraints_to_obj(obj, item):
#    key_constraints = RBDLabNaming.CONSTRAINTS
#    if key_constraints in obj:
#        obj[key_constraints] += " " + item


def append_attribute_to_obj(obj, attribute, value):
    if attribute in obj:
        obj[attribute] += " " + str(value)
    else:
        obj[attribute] = str(value)


def clear_custom_attribute_to_obj(obj, attribute):
    if obj:
        if attribute in obj:
            del obj[attribute]


def select_pieces_mass_less_than(context, delimiter):
    scn = context.scene
    rbdlab = scn.rbdlab
    tcoll_list = rbdlab.lists.target_coll_list
    chunks = tcoll_list.get_current_active_tcoll_valild_objects(context)

    masas = []
    bpy.ops.object.select_all(action='DESELECT')

    if rbdlab.filtered_target_collection:
        deselect_all_objects(context)

        for obj in chunks:
            if obj.rigid_body is None:
                continue
            if not hasattr(obj.rigid_body, "mass"):
                continue
            m = obj.rigid_body.mass
            masas.append(m)
            if m <= delimiter:
                select_object(context, obj)
                context.view_layer.objects.active = obj

    rbdlab.chunks_selected = len(context.selected_objects)


def select_pieces_dimensions_less_than(rbdlab, context, delimiter, only_with_particles):
    d = []

    tcoll = rbdlab.filtered_target_collection
    if tcoll is None:
        return

    tcoll_list = rbdlab.lists.target_coll_list
    chunks = tcoll_list.get_current_active_tcoll_valild_objects(context)

    deselect_all_objects(context)

    for obj in chunks:

        if only_with_particles:
            if len(obj.particle_systems) == 0:
                continue

        s = obj.dimensions.x + obj.dimensions.y + obj.dimensions.z
        d.append(s)
        if s <= delimiter:
            obj.select_set(True)
            context.view_layer.objects.active = obj

    rbdlab.chunks_selected = len(context.selected_objects)


def select_pieces_dimensions_more_than(rbdlab, context):
    tcoll = rbdlab.filtered_target_collection
    if tcoll is None:
        return

    d = []
    delimiter = rbdlab.size_delimiter_big / 10
    bpy.ops.object.select_all(action='DESELECT')

    deselect_all_objects(context)

    for obj in tcoll.objects:
        if obj.type == 'MESH' and obj.visible_get():
            s = obj.dimensions.x + obj.dimensions.y + obj.dimensions.z
            d.append(s)
            if s >= delimiter:
                obj.select_set(True)
                context.view_layer.objects.active = obj

    rbdlab.chunks_selected = len(context.selected_objects)


def have_rigidbodies_in_active_group(context):
    rbdlab = context.scene.rbdlab
    tcoll = rbdlab.filtered_target_collection

    if tcoll is None:
        return False

    valid_objects = [obj for obj in tcoll.objects if obj.type ==
                     'MESH' and RBDLabNaming.PASSIVE not in obj and obj.rigid_body]

    return len(valid_objects) > 0


def have_constraint_in_target_collection(context):
    rbdlab = context.scene.rbdlab
    tcoll = rbdlab.filtered_target_collection

    if tcoll is None:
        return

    return (any([obj for obj in tcoll.objects if
                 get_array_data_from_obj(context, RBDLabNaming.CONSTRAINTS, obj)]))


def add_material(context, ob_x: Union[str, Object], material_name: str, color4: tuple) -> Material:

    if isinstance(ob_x, str):
        ob = bpy.data.objects.get(ob_x)

    if isinstance(ob_x, Object):
        ob = ob_x

    if ob is None:
        raise ValueError(f"No valid object found.")

    if material_name not in bpy.data.materials:
        mat = bpy.data.materials.new(name=material_name)
        mat.use_nodes = True
    else:
        mat = bpy.data.materials.get(material_name)

    if not isinstance(mat, Material) or mat is None:
        raise ValueError(f"Cannot get material {material_name}.")

    if material_name not in ob.data.materials:
        ob.data.materials.append(mat)
        ob.active_material_index = ob.data.materials.find(mat.name)

        principled_node = ob.active_material.node_tree.nodes.get(RBDLabNaming.PRINCIPLED)
        if principled_node is not None:
            principled_node.inputs["Base Color"].default_value = color4
        else:
            if bpy.context.preferences.view.use_translate_new_dataname:
                lang = bpy.context.preferences.view.language
                print("[ WARNING ] Principled BSDF is not found because the " + lang.upper() +
                      " language is being used for Data translations. ")

        ob.active_material.diffuse_color = color4

    return mat


def get_pack_islands(target_collection):
    pack_islands = {}
    for obj in target_collection.objects:
        if obj.type == 'MESH' and obj.visible_get():

            key_island = obj[RBDLabNaming.FROM]
            chunk_name = obj.name

            if key_island in pack_islands:
                pack_islands[key_island].append(chunk_name)
            else:
                pack_islands[key_island] = [chunk_name]

    return pack_islands


def remove_special_chars_in_name(input_name):
    # input_name = "".join(e for e in input_name if e.isalnum())
    input_name = re.sub("[^A-Za-z0-9]+", "_", input_name)
    return input_name


def create_modifier(ob: Object, name: str, type_name: str, position=None):
    
    mod = ob.modifiers.get(name)
    if not mod:
        ob.modifiers.new(name=name, type=type_name)
        mod = ob.modifiers[-1]

    if position:
        current_index_mod = ob.modifiers.find(name)
        ob.modifiers.move(current_index_mod, position)
        # bpy.ops.object.modifier_move_to_index(modifier=name, index=position)

    return mod


def add_fluid_modifier_to_active_object(context, type_fluid='FLOW'):
    ob = context.object
    if ob:
        smoke_mod_name = RBDLabNaming.SMOKE_MOD
        if smoke_mod_name not in ob.modifiers:
            smoke_mod_name = create_modifier(ob, smoke_mod_name, 'FLUID')
            smoke_mod_name.fluid_type = type_fluid
            # density by default to 0:
            if smoke_mod_name:
                if hasattr(smoke_mod_name, "flow_settings"):
                    if hasattr(smoke_mod_name.flow_settings, "density"):
                        smoke_mod_name.flow_settings.density = 0
                return smoke_mod_name
            else:
                return None
    else:
        return None


def remove_modifier_from_active_object(context, type: str = 'FLUID', once: bool = False):
    remove_modifier_from_object(context, context.active_object, type, once)


def remove_modifier_from_object(context, object, type: str = 'FLUID', once: bool = False):
    if object and isinstance(object, str):
        object = get_object_from_scene(context, object)
    if not object:
        return
    for modifier in object.modifiers:
        if modifier.type == type:
            object.modifiers.remove(modifier)
            if once:
                break


def get_object_from_scene(context, name):
    return context.scene.objects.get(name, None)


def get_valid_objects(coll_name):
    objects = []
    for obj in bpy.data.collections[coll_name].objects:
        if obj.type == 'MESH' and obj.visible_get():
            objects.append(obj)
    if objects:
        return objects
    else:
        print("no valid objects returned!")


def generic_copy(source, target):
    blacklist = ["__doc__", "__module__", "__slots__", "bl_rna"]
    # if attribute is not in black list, and is not readonly (with dir get all modifier attributes):
    [setattr(target, attr, getattr(source, attr)) for attr in dir(source) if attr not in blacklist and not target.is_property_readonly(attr)]
    return


def copy_modifier_by_name_from_active_to_selected(context, white_list_mods):

    """ copiamos los modificadores de la lista blanca del objeto activo a la seleccion """
    
    ob_active = context.active_object

    if ob_active and len(context.selected_objects) > 0 and len(white_list_mods) > 0:

        for ob in context.selected_objects:
            
            for org_modifier in ob_active.modifiers:

                org_mod_name = org_modifier.name
                if org_mod_name not in white_list_mods or org_mod_name in ob.modifiers:
                    continue
            
                org_mod_type = org_modifier.type
                new_modifier = ob.modifiers.new(
                    type=org_mod_type,
                    name=org_mod_name
                )
                if new_modifier:
                    # copiamos sus settings:
                    generic_copy(org_modifier, new_modifier)


def select_chunks_with_break_constraints(context, coll_name):
    # rbdlab = context.scene.rbdlab
    # chunks = rbdlab.get_chunks()
    objects = [obj for obj in bpy.data.collections[coll_name].objects if obj.type == 'MESH' and obj.visible_get()]
    if not objects:
        return []
    deselect_all_objects(context)
    from ..ops.constraints.detect import get_broken_chunks_at_frame_inv
    objects = get_broken_chunks_at_frame_inv(objects, context.scene.frame_current)
    {ob.select_set(True) for ob in objects}
    return objects

    ''' New neighbor system
    ps_props = rbdlab.get_particles_properties()
    last_current_frame = context.scene.frame_current
    broken_threshold = float(format(ps_props.broken_threshold, ".6f"))
    valid_objects = [obj for obj in bpy.data.collections[coll_name].objects if obj.type == 'MESH' and obj.visible_get()]
    for obj in valid_objects:
        constrainsts = get_array_data_from_obj(RBDLabNaming.CONSTRAINTS, obj)
        if constrainsts:
            for const in constrainsts:
                const_ob = context.view_layer.objects[const]
                dist = const_ob[RBDLabNaming.CONST_DIST]
                obj1 = const_ob.rigid_body_constraint.object1
                obj2 = const_ob.rigid_body_constraint.object2
                if obj1 is None and obj2 is None:
                    continue
                context.scene.frame_set(context.scene.frame_end)
                current_dist = (
                    context.scene.objects[obj1].matrix_world.translation - context.scene.objects[obj2].matrix_world.translation).length
                # vect_lenght = (current_dist - dist)
                # print("original dist", dist, "current dist", current_dist)
                # print("len", vect_lenght, " > ", (current_dist + broken_threshold))
                # print(current_dist, " > ", (dist + broken_threshold))
                if current_dist > (dist + broken_threshold):
                    select_object(context, obj1)
                    select_object(context, obj2)
        else:
            select_object(context, obj)

    context.scene.frame_current = last_current_frame
    objects = context.selected_objects
    deselect_all_objects(context)
    
    return objects
    '''


def set_shading_color(context, color_type='OBJECT', light=None, shading='SOLID', xray=None):
    
    """ Establece el tipo de sombreado y el color en el viewport """

    # para los colores por colección via objeto
    
    # sobreescribir el contexto:
    def callback(context) -> None:
        area = context.area  # Accedemos al área desde el contexto
        for space in area.spaces:  # Itera a través de los espacios en el área VIEW_3D actual
            if space.type == 'VIEW_3D':  # Verifica si el espacio es una vista 3D
                space.shading.type = shading
                # si quisiera quitar los outliners:
                # if color_type == 'OBJECT':
                #     space.shading.show_object_outline = False
                # else:
                #     space.shading.show_object_outline = True
                space.shading.color_type = color_type
                if light:
                    space.shading.light = light

                if xray is not None:
                    if shading == 'WIREFRAME':
                        space.shading.show_xray_wireframe = xray
                    else:
                        space.shading.show_xray = xray
        area.tag_redraw()

    context_override(context=context, area_type='VIEW_3D', callback=callback)




def get_folder_addon_name():
    script_file = os.path.realpath(__file__)
    directory = os.path.dirname(script_file)
    # print(os.path.basename(os.path.normpath(directory)))
    # print(os.path.basename(os.path.dirname(directory)))
    return os.path.basename(os.path.dirname(directory))


###########################################################################
# COLLECTIONS
###########################################################################

def find_layer_coll_by_coll_name(data, container, coll_name):
    if isinstance(data, bpy.types.bpy_prop_collection):
        for vl in data:
            if hasattr(vl, "layer_collection"):
                if len(vl.layer_collection.children) > 0:
                    lc = vl.layer_collection
                    for child in lc.children:
                        # print("Layer Collection:", lc.name  + ", ", "Collection:", child.name)
                        if child.name == coll_name:
                            container.append(lc)
                        else:
                            find_layer_coll_by_coll_name(child, container, coll_name)
    elif isinstance(data, bpy.types.ViewLayer):
        for vl in data:
            lc = vl.layer_collection
            if len(lc.children) > 0:
                for child in lc.children:
                    # print("Layer Collection:", lc.name + ", ", "Collection:", child.name)
                    if child.name == coll_name:
                        container.append(lc)
                    else:
                        find_layer_coll_by_coll_name(child, container, coll_name)
    elif isinstance(data, bpy.types.LayerCollection):
        if len(data.children) > 0:
            for lc in data.children:
                # print("Layer Collection:", data.name + ", ", "Collection:", lc.name)
                if lc.name == coll_name:
                    container.append(lc)
                else:
                    find_layer_coll_by_coll_name(lc, container, coll_name)
    if container:
        return container[0]


def set_active_collection_to_root_scn_coll(context):
    scn = context.scene
    scn_collection = scn.view_layers[context.view_layer.name].layer_collection
    context.view_layer.active_layer_collection = scn_collection


def set_active_collection_to_master_coll(context):
    scn = context.scene
    rbdlab = scn.rbdlab
    coll_name = RBDLabNaming._RBDLab_name
    if not rbdlab.root_collection:
        context.view_layer.active_layer_collection = context.view_layer.layer_collection
        root_coll = bpy.data.collections.new(coll_name)
        rbdlab.root_collection = root_coll
        context.scene.collection.children.link(root_coll)

    # coll_name = root_coll.name
    # if coll_name not in bpy.data.collections:
    #     # si no existe primero hago activa el master collection
    #     # para crear RBDLab en la raiz:
    #     context.view_layer.active_layer_collection = context.view_layer.layer_collection
    #     # ahora creo RBDLab como master collection:
    #     new_coll_target = bpy.data.collections.new(coll_name)
    #     context.scene.collection.children.link(new_coll_target)

    # la hacemos la activa:
    # pero primero la buscamos recursivamente:
    data = context.scene.view_layers
    container = []
    layer_collection = find_layer_coll_by_coll_name(data, container, coll_name)
    if layer_collection:

        if coll_name in layer_collection.children:
            to_coll = layer_collection.children[coll_name]
        else:
            to_coll = layer_collection
        # print("to_coll", to_coll)
        # to_coll = context.view_layer.layer_collection.children["RBDLab"]
        context.view_layer.active_layer_collection = to_coll
    else:
        print("No se encontro el layer collection de " + coll_name)


def set_active_collection_by_name(context, coll_name):
    if coll_name:
        data = context.scene.view_layers
        container = []
        to_coll = find_layer_coll_by_coll_name(data, container, coll_name)
        if to_coll:
            # to_coll = context.view_layer.layer_collection.children["RBDLab"].children[coll_name]
            context.view_layer.active_layer_collection = to_coll


# def check_if_collection_is_visible(context, coll_name):
#     scn = context.scene
#     rbdlab = scn.rbdlab
#     # para luego restaurarlo:
#     current_layer_active = context.view_layer.active_layer_collection.name

#     set_active_collection_by_name(context, coll_name)
#     hide_viewport = context.view_layer.active_layer_collection.hide_viewport
#     # print("coleccion", coll_name, "hide in viewport:", context.view_layer.active_layer_collection.hide_viewport)
#     # si es visible dice false

#     # restauro en la que estaba activa antes:
#     # if current_layer_active == "Master Collection":
#     if current_layer_active == rbdlab.root_collection.name:
#         set_active_collection_to_master_coll(context)
#     else:
#         set_active_collection_by_name(context, current_layer_active)

#     return hide_viewport


def hide_collection_in_viewport(context, coll_name):
    # print("** hide: " + coll_name)
    scn = context.scene
    rbdlab = scn.rbdlab
    if coll_name in bpy.data.collections:
        if rbdlab.root_collection:
            data = context.scene.view_layers
            container = []
            layer_collection = find_layer_coll_by_coll_name(data, container, coll_name)
            if layer_collection:
                # layer_collection = context.view_layer.layer_collection.children["RBDLab"].children[coll_name]
                # layer_collection = context.view_layer.active_layer_collection
                context.view_layer.active_layer_collection = layer_collection
                context.view_layer.active_layer_collection.hide_viewport = True
        else:
            layer_collection = context.view_layer.layer_collection.children[coll_name]
            context.view_layer.active_layer_collection = layer_collection
            context.view_layer.active_layer_collection.hide_viewport = True


def unhide_collection_in_viewport(context, coll_name):
    # print("** unhide: " + coll_name)
    scn = context.scene
    rbdlab = scn.rbdlab
    if coll_name in bpy.data.collections:
        if rbdlab.root_collection:
            data = context.scene.view_layers
            container = []
            layer_collection = find_layer_coll_by_coll_name(data, container, coll_name)
            if layer_collection:
                # layer_collection = context.view_layer.layer_collection.children["RBDLab"].children[coll_name]
                # layer_collection = context.view_layer.active_layer_collection
                context.view_layer.active_layer_collection = layer_collection
                context.view_layer.active_layer_collection.hide_viewport = False
        else:
            layer_collection = context.view_layer.layer_collection.children[coll_name]
            context.view_layer.active_layer_collection = layer_collection
            context.view_layer.active_layer_collection.hide_viewport = False


def hide_collection_in_render(coll_name):
    if coll_name in bpy.data.collections:
        if coll_name in bpy.data.collections:
            bpy.data.collections[coll_name].hide_render = True


def unhide_collection_in_render(coll_name):
    if coll_name in bpy.data.collections:
        bpy.data.collections[coll_name].hide_render = False


def remove_collection(context: Context, coll: Collection, and_objects: bool = True) -> None:

    if isinstance(coll, Collection):
        if and_objects:
            if len(coll.objects) > 0:
                obs = [o for o in coll.objects if o.users == 1]
                while obs:
                    bpy.data.objects.remove(obs.pop())
        else:
            if len(coll.objects) > 0:
                for ob in coll.objects:
                    if len(ob.users_collection) <= 0:
                        context.scene.collection.objects.link(ob)
        
        bpy.data.collections.remove(coll)


def remove_collection_if_is_empty(context: Context, coll: Union[Collection,str]) -> None:

    if isinstance(coll, str):
    
        coll = bpy.data.collections.get(coll)
        if coll:
            remove_collection_if_is_empty(context, coll)

    elif isinstance(coll, Collection):
    
        if len(coll.objects) == 0 and len(coll.children_recursive) == 0:
            remove_collection(context, coll, False)


def remove_collection_by_name(context, coll_name, and_objects: bool = True) -> None:

    coll = bpy.data.collections.get(coll_name)
    if coll:
        remove_collection(context, coll, and_objects)


def create_new_collection(context, new_collection_name:str) -> Collection:
    scn = context.scene
    rbdlab = scn.rbdlab
    set_active_collection_to_master_coll(context)

    if new_collection_name not in rbdlab.root_collection.children:
        new_coll_target = bpy.data.collections.new(new_collection_name)
        rbdlab.root_collection.children.link(new_coll_target)
        # context.scene.collection.children["RBDLab"].children.link(new_coll_target)
    else:
        new_coll_target = bpy.data.collections.get(new_collection_name)

    # se devuelve la nueva collection creada:
    return new_coll_target


def move_object_from_collection_to_collection(obj, coll_origin, coll_dest):
    # lo meto en la nueva si no estuviera:
    if obj.name not in bpy.data.collections[coll_dest].objects:
        bpy.data.collections[coll_dest].objects.link(obj)
    # lo quito de la collection original
    if obj.name in bpy.data.collections[coll_origin].objects:
        bpy.data.collections[coll_origin].objects.unlink(obj)


############################################################################################################################
# Particles
############################################################################################################################

# def have_particles_in_motion(context):
#     rbdlab = context.scene.rbdlab
#     have = False

#     if rbdlab.filtered_target_collection:
#         coll_name = rbdlab.filtered_target_collection.name
#         if coll_name:

#             # si esta oculta la desoculto para el get first mesh visible
#             # chk_visible = check_if_collection_is_visible(coll_name)
#             # if chk_visible:
#             #     unhide_collection_in_viewport(context, coll_name)

#             objects = get_valid_objects(coll_name)
#             i = 0
#             if objects:
#                 while not have and i < len(objects):
#                     if len(objects[i].modifiers) > 0:
#                         for mod in objects[i].modifiers:
#                             ps_selected_name = context.scene.ps_list_selected
#                             if ps_selected_name:
#                                 if ps_selected_name in mod.name:
#                                     # if mod.name.startswith("Motion_"):
#                                     have = True
#                                     i = len(objects) + 1
#                             else:
#                                 return False
#                     i += 1

#         despues la vuelvo a ocultar
#         if chk_visible:
#             hide_collection_in_viewport(context, coll_name)

#         return have
#     else:
#         return False


def have_particle_sytem_debris(context):
    scn = context.scene
    rbdlab = scn.rbdlab
    
    tcoll_list = rbdlab.lists.target_coll_list
    ob = tcoll_list.get_first_valid_ob(context)
    
    if ob:
        ps_name = rbdlab.filtered_target_collection.name + "_Debris"
        if ps_name in ob.particle_systems:
            return True
        else:
            return False


def have_particle_sytem_dust(context):
    scn = context.scene
    rbdlab = scn.rbdlab
    
    tcoll_list = rbdlab.lists.target_coll_list
    ob = tcoll_list.get_first_valid_ob(context)

    if ob:
        ps_name = rbdlab.filtered_target_collection.name + "_Dust"
        if ps_name in ob.particle_systems:
            return True
        else:
            return False


# def have_particle_sytem_smoke(context):
#     scn = context.scene
#     rbdlab = scn.rbdlab
    
#     tcoll_list = rbdlab.lists.target_coll_list
#     ob = tcoll_list.get_first_valid_ob(context)

#     if ob:
#         ps_name = rbdlab.filtered_target_collection.name + "_Smoke"
#         if ps_name in ob.particle_systems:
#             return True
#         else:
#             return False


def next_seed(context):
    rbdlab = context.scene.rbdlab

    # rand seed
    rbdlab.iter_seed = 0
    for obj in bpy.data.collections[rbdlab.filtered_target_collection.name].objects:
        if obj.type == 'MESH' and obj.visible_get():
            for ps in obj.particle_systems:
                ps.seed += rbdlab.iter_seed
                rbdlab.iter_seed += 1


# def add_driver(context, modifier_name):
#     if len(context.selected_objects) > 0:
#         for obj in context.selected_objects:
#             if modifier_name in obj.modifiers:
#                 my_driver = obj.modifiers[modifier_name].flow_settings.driver_add(
#                     "density")
#                 var = my_driver.driver.variables.new()
#                 var.name = "smoke_density"
#                 var.type = 'SINGLE_PROP'
#                 my_driver.driver.expression = var.name
#                 var.targets[0].id_type = 'SCENE'
#                 var.targets[0].id = bpy.data.scenes[context.scene.name]
#                 var.targets[0].data_path = "rbdlab.smoke_density"


# def copy_modifier_to_selected_objects(context, mod_name):
#     obj_from = context.active_object
#     for obj in context.selected_objects:
#         if obj.name != obj_from.name:
#             set_active_object(context, obj)
#             bpy.ops.object.modifier_add(type='FLUID')


def append_collection(context, coll_name):
    enter_object_mode(context)
    # importo la coleccion de debris basicos:
    from os.path import dirname, realpath, join
    fpath = join(dirname(dirname(realpath(__file__))),
                 "libs")  # va al root y luego a "libs"
    fname = join("debris_basics.blend", "Collection")

    if coll_name not in bpy.data.collections:
        bpy.ops.wm.append(filename=coll_name, directory=join(fpath, fname))
        hide_collection_in_viewport(context, coll_name)


def append_materials(context, obj_name, mat_name):
    if obj_name in context.scene.objects:
        obj = context.scene.objects.get(obj_name)

        if mat_name not in bpy.data.materials:
            from os.path import dirname, realpath, join
            blend_file_name = "smoke_mat.blend"
            fpath = join(dirname(dirname(realpath(__file__))),
                         "libs")  # va al root y luego a "libs"
            fname = join(blend_file_name)
            # print("fname", fname, "fpath", fpath, "obj_name", obj_name, "directory", join(fpath, fname))
            path = join(fpath, fname)

            with bpy.data.libraries.load(path) as (data_from, data_to):
                data_to.materials = data_from.materials

        if mat_name in bpy.data.materials:
            obj.active_material = bpy.data.materials.get(mat_name)


def check_void_chunks(context, obj):
    dg = context.evaluated_depsgraph_get()
    obj = obj.evaluated_get(dg)
    me = obj.to_mesh()
    bm = bmesh.new()
    bm.from_mesh(me)

    # Allow indexed access for vertices and edges
    # bm.verts.ensure_lookup_table()
    bm.edges.ensure_lookup_table()

    # deteccion chunks invisibles parcial o completamente:
    # if len(me.vertices) < 3:
    #     obj.to_mesh_clear()
    #     bm.clear()
    #     if len(obj.data.vertices) > 0:
    #         return True
    #     else:
    #         return False
    # else:
    i = 0
    bad_chunks = None
    match = False
    while i < len(bm.edges) and match == False:
        edge = bm.edges[i]
        if edge.is_boundary:
            bad_chunks = edge.is_boundary
            match = True
        i += 1
    obj.to_mesh_clear()
    bm.clear()
    if bad_chunks and len(obj.data.vertices) > 0:
        return True
    else:
        return False


def check_string_contain_digit(s):
    digits = []

    for char in s:
        if char.isdigit():
            digits.append(char)
        else:
            if char == "#":
                digits.append(char)

    if len(digits) > 0:
        return True
    else:
        return False


################################################
# generate bounding box for multiple objects   #
################################################
def create_vertex(context, verts=[Vector((0.0, 0.0, 0.0))], name="BoundingBox"):
    me = bpy.data.meshes.new(name + "_Mesh")
    obj = bpy.data.objects.new(name, me)
    context.collection.objects.link(obj)
    me.from_pydata(verts, [], [])
    me.update()
    return obj


def get_bounds(context, objects, where):
    if objects:

        bounds_x = []
        bounds_y = []
        bounds_z = []
        depsgraph = context.evaluated_depsgraph_get()

        if where == "Start":
            context.scene.frame_set(context.scene.frame_start)

            for obj in objects:
                if obj:
                    obj_eval = obj.evaluated_get(depsgraph)
                    for bound in obj_eval.bound_box:
                        bounds_x.append(bound[0] + obj_eval.matrix_world.translation.x)
                        bounds_y.append(bound[1] + obj_eval.matrix_world.translation.y)
                        bounds_z.append(bound[2] + obj_eval.matrix_world.translation.z)

        elif where == "End":
            context.scene.frame_set(context.scene.frame_end)

            for obj in objects:
                obj_eval = obj.evaluated_get(depsgraph)
                for bound in obj_eval.bound_box:
                    bounds_x.append(bound[0] + obj_eval.matrix_world.translation.x)
                    bounds_y.append(bound[1] + obj_eval.matrix_world.translation.y)
                    bounds_z.append(bound[2] + obj_eval.matrix_world.translation.z)

        elif where == "StartEnd":
            # start
            context.scene.frame_set(context.scene.frame_start)

            for obj in objects:
                obj_eval = obj.evaluated_get(depsgraph)
                for bound in obj_eval.bound_box:
                    bounds_x.append(bound[0] + obj_eval.matrix_world.translation.x)
                    bounds_y.append(bound[1] + obj_eval.matrix_world.translation.y)
                    bounds_z.append(bound[2] + obj_eval.matrix_world.translation.z)

            # end
            context.scene.frame_set(context.scene.frame_end)

            for obj in objects:
                obj_eval = obj.evaluated_get(depsgraph)
                for bound in obj_eval.bound_box:
                    bounds_x.append(bound[0] + obj_eval.matrix_world.translation.x)
                    bounds_y.append(bound[1] + obj_eval.matrix_world.translation.y)
                    bounds_z.append(bound[2] + obj_eval.matrix_world.translation.z)

        return bounds_x, bounds_y, bounds_z


def get_min_and_max_bounds(bounds_x, bounds_y, bounds_z, clamp):
    # get the mins and max from boundings boxes:
    min_x = bounds_x[bounds_x.index(min(bounds_x))]
    max_x = bounds_x[bounds_x.index(max(bounds_x))]

    min_y = bounds_y[bounds_y.index(min(bounds_y))]
    max_y = bounds_y[bounds_y.index(max(bounds_y))]

    min_z = bounds_z[bounds_z.index(min(bounds_z))]
    max_z = bounds_z[bounds_z.index(max(bounds_z))]

    # if have clamp value, clamp it:
    if clamp:
        positive_clamp = clamp
        negative_clamp = (clamp * -1)
        if max_x > positive_clamp:
            max_x = positive_clamp
        if max_y > positive_clamp:
            max_y = positive_clamp
        if max_z > positive_clamp:
            max_z = positive_clamp

        if min_x < negative_clamp:
            min_x = negative_clamp
        if min_y < negative_clamp:
            min_y = negative_clamp
        if min_z < negative_clamp:
            min_z = negative_clamp

    # print(max_x, min_x)

    return min_x, max_x, min_y, max_y, min_z, max_z


def generate_bounding_box(
        self,
        context,
        objects: List[Object],
        bound_type="Empty",
        with_parent=True,
        offset_x=0, offset_y=0, offset_z=0,
        bb_name="BoundingBox", where="Start",
        clamp=None) -> Object:

    if with_parent:
        for obj in objects:

            if obj.parent:
                self.report({'WARNING'}, "They already have a parent!")
                return

    bpy.ops.object.select_all(action='DESELECT')

    bounds_x, bounds_y, bounds_z = get_bounds(context, objects, where)
    min_x, max_x, min_y, max_y, min_z, max_z = get_min_and_max_bounds(bounds_x, bounds_y, bounds_z, clamp)

    verts = []

    min_value_supported = 1
    max_value_supported = 60

    # if min_z < 0:
    #     min_z = 0
    # if min_z - max_z <= min_value_supported_z:
    #     max_z = min_z + min_value_supported_z

    # minimos:
    if max_x <= min_x:
        print("expand bounding box max_x to: " + str(min_value_supported))
        max_x += min_value_supported

    if max_y <= min_y:
        print("expand bounding box max_y to: " + str(min_value_supported))
        max_y += min_value_supported

    if max_z <= min_z:
        print("expand bounding box max_z to: " + str(min_value_supported))
        max_z += min_value_supported

    # maximos:
    if max_x > max_value_supported:
        print("clamp bounding box max_x to: " + str(max_value_supported))
        max_x = max_value_supported

    if max_y > max_value_supported:
        print("clamp bounding box max_y to: " + str(max_value_supported))
        max_y = max_value_supported

    if max_z > max_value_supported:
        print("clamp bounding box max_z to: " + str(max_value_supported))
        max_z = max_value_supported

    # create the 8 vertex for convex hull:
    coords = Vector((min_x, min_y, min_z))
    verts.append(coords)
    #
    coords = Vector((max_x, min_y, min_z))
    verts.append(coords)
    #
    coords = Vector((max_x, max_y, min_z))
    verts.append(coords)
    #
    coords = Vector((min_x, max_y, min_z))
    verts.append(coords)
    #
    coords = Vector((max_x, max_y, max_z))
    verts.append(coords)
    #
    coords = Vector((min_x, min_y, max_z))
    verts.append(coords)
    #
    coords = Vector((max_x, min_y, max_z))
    verts.append(coords)
    #
    coords = Vector((min_x, max_y, max_z))
    verts.append(coords)

    bb_obj = create_vertex(context, verts, bb_name)

    bpy.ops.object.select_all(action='DESELECT')

    # create convex hull
    if not bb_obj:
        return

    bb_obj.select_set(True)
    set_active_object(context, bb_obj)
    enter_object_mode(context)
    bb_obj.display_type = 'WIRE'
    bpy.ops.object.origin_set(type='ORIGIN_GEOMETRY', center='MEDIAN')
    enter_edit_mode(context)
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.mesh.convex_hull()
    enter_object_mode(context)
    # end create convex hull

    if bound_type == "Empty":
        # Create emprty
        bpy.ops.object.empty_add(type='CUBE', align='WORLD',
                                 location=bb_obj.matrix_world.translation, scale=(1, 1, 1))
        empty = context.active_object
        bpy.ops.object.scale_clear(clear_delta=False)

        # Adjust empty dimensions:
        bpy.ops.object.select_all(action='DESELECT')
        empty.select_set(True)

        empty.scale = bb_obj.scale
        empty.scale.x = bb_obj.dimensions.x / 2
        empty.scale.y = bb_obj.dimensions.y / 2
        empty.scale.z = bb_obj.dimensions.z / 2
        empty.name = bb_name

        # remove tmp bb_obj:
        bpy.ops.object.select_all(action='DESELECT')
        bb_obj.select_set(True)
        bpy.ops.object.delete(use_global=False)

        # set father:
        father = empty
    else:
        domain = bb_obj
        bpy.ops.object.scale_clear(clear_delta=False)
        domain.name = bb_name

        # set father:
        father = bb_obj

    bpy.ops.object.select_all(action='DESELECT')
    father.select_set(True)

    father.scale.x += offset_x
    father.scale.y += offset_y
    father.scale.z += offset_z

    # para que no estropee el empty el apply transforms:
    bpy.ops.object.visual_transform_apply()

    # parent:
    if with_parent:
        for obj in objects:
            if obj.name != father.name:
                obj.parent = father
                obj.matrix_parent_inverse = father.matrix_world.inverted()

    if father:
        return father


##################################################
# end generate bounding box for multiple objects #
##################################################


# for smokes:
def calculate_motions(context, speed_threshold, objects, frange_min, frange_max):
    scn = context.scene
    rbdlab = scn.rbdlab

    # si alguno no tiene motions
    not_have_motions = [obj for obj in objects if "rbdlab_motions" not in obj]

    if not_have_motions:
        start = datetime.now()
        print("Calculate motions...")

        ps_props = rbdlab.get_particles_properties()
        obj_in_motion = {}

        # print("frange_min, frange_max", frange_min, frange_max)

        if not objects:
            print("calculate_motions: Not objects recived!")
            print("Check if your Cache Bake is not Outdated!")
            return -1

        for obj in objects:
            frame = None
            velocity = None
            frames = {}

            # primer array
            if obj.name not in obj_in_motion:
                obj_in_motion[obj.name] = []

            # primer array
            if obj.name not in frames:
                frames[obj.name] = []

            # obtener el array de los frame velocity:
            key_name = RBDLabNaming.VELOCITIES
            if key_name in obj:
                # obtengo los array de velocidades y frames (solo en los q hay vel superior a x)
                array_data = get_array_data_from_obj(context, key_name, obj)
                a_frames = []
                a_velocities = []

                for i in range(len(array_data)):
                    if i % 2 == 0:
                        a_frames.append(array_data[i])
                    else:
                        a_velocities.append(array_data[i])

                for i in range(len(a_frames)):
                    frame = int(a_frames[i])
                    velocity = float(a_velocities[i])
                    # velocity = format(float(a_velocities[i]), ".15f")

                    # print("frame:", frame, "velocity:", velocity)

                    if frame is not None and velocity is not None:
                        # print("frange_min", frange_min, "frame:", frame, "frange_max:", frange_max)
                        if frange_min <= frame <= frange_max:
                            # print("frame:", frame, "velocity:", velocity)
                            # print("frange_min", frange_min, "frame:", frame, "frange_max:", frange_max)
                            # print("velocity", velocity, "speed_threshold", speed_threshold)
                            # print("velocity < speed_threshold:", velocity < speed_threshold)
                            # print("velocity <= 0:", velocity <= 0)
                            if velocity < speed_threshold or velocity <= 0:

                                frames[obj.name] = []
                                continue

                            if frame not in frames[obj.name]:
                                frames[obj.name].append(frame)
                                # frames[obj.name].append(f_ranges)

                            # print("obj_in_motion[obj.name]", obj_in_motion[obj.name])
                            # print("frames["+obj.name+"]:", frames[obj.name])
                            if frames[obj.name] not in obj_in_motion[obj.name]:
                                if frames[obj.name]:
                                    obj_in_motion[obj.name].append(frames[obj.name])
            # print(frames)
            #         else:
            #             print(obj.name, "No velocities detected!")
            # else:
            #     print(obj.name, "No velocities property detected!")

            # if not frames[obj.name]:
            #     del obj_in_motion[obj.name]

        # obj_in_motion = diccionario con obj.name y array con sus correspondientes motions

        # print("### obj_in_motion1", obj_in_motion)
        if obj_in_motion:

            for key in list(obj_in_motion):
                # print("key", key)
                # print("obj_in_motion", obj_in_motion)
                if not obj_in_motion[key]:
                    del obj_in_motion[key]

            if len(obj_in_motion) == 0:
                return -1

            # determinamos cuantos motions para crear particles systems son permitidos:
            if ps_props.max_particle_systems > 0:
                for key, value in obj_in_motion.items():
                    # print("key:", key, "value:", value)
                    if len(value) > ps_props.max_particle_systems:
                        for i in range(len(value) - ps_props.max_particle_systems):
                            del value[-1]
                        obj_in_motion[key] = value

            # guardo los frames start y end en los chunks:

            for o_name, a in obj_in_motion.items():

                obj_target = scn.objects.get(o_name)

                if a:
                    obj_target["rbdlab_motions"] = ""

                    frame_start_end_motion = []

                    check_first_frame = None
                    check_end_frame = None

                    for f in a:
                        # print("*** f", f)

                        # solo el primer y ultimo frame:
                        check_first_frame = f[0]
                        check_end_frame = f[-1]

                        if check_first_frame and check_end_frame:
                            # print("check_first_frame, check_end_frame:", check_first_frame, check_end_frame)

                            data_frames = [check_first_frame, check_end_frame]
                            # print("data_frames", data_frames)
                            frame_start_end_motion.append(data_frames)
                            obj_target["rbdlab_motions"] += "[" + str(
                                check_first_frame) + "," + str(check_end_frame) + "]"

                    if frame_start_end_motion:
                        # print("frame_start_end_motion", frame_start_end_motion)
                        obj_in_motion[o_name] = frame_start_end_motion

            rbdlab.filtered_target_collection["computed_motions"] = True
            # print("### obj_in_motion", obj_in_motion)
            print("Calculate motions End: " + str(datetime.now() - start))
            return obj_in_motion
        else:
            if "computed_motions" in rbdlab.filtered_target_collection:
                del rbdlab.filtered_target_collection["computed_motions"]

            print("motion could not be delivered")
            return -1
    else:
        print("Already has motions, they will be reused")
        # if they already had the motions computed, we rescued them.
        obj_in_motion = {}

        for obj in objects:
            if "rbdlab_motions" not in obj:
                continue
            if obj not in obj_in_motion:
                obj_in_motion[obj.name] = []

            if "][" in obj["rbdlab_motions"]:
                obj["rbdlab_motions"] = "[" + obj["rbdlab_motions"].replace("][", "],[") + "]"

            obj_in_motion[obj.name].append(ast.literal_eval(obj["rbdlab_motions"]))

        # print("*********** obj_in_motion", obj_in_motion)
        if obj_in_motion:
            return obj_in_motion
        else:
            return -1


def normalize(value, min_n, max_n):
    # clamped = max(min(max_n, value), min_n)
    # normalized = (clamped - min_n) / (max_n - min_n)
    normalized = (value - min_n) / (max_n - min_n)
    return normalized

# def change_scale_to_value(value, new_min, new_max):
#     old_min = 0
#     old_max = value
#
#     old_range = (old_max - old_min)
#     old_value = value
#
#     if old_range == 0:
#         new_value = new_min
#     else:
#         new_range = (new_max - new_min)
#         result = (((old_value - old_min) * new_range) / old_range) + new_min
#
#     return result


def remove_smoke_from_chunks(context):
    deselect_all_objects(context)

    scn = context.scene
    rbdlab = scn.rbdlab

    tcoll_list = rbdlab.lists.target_coll_list
    # tcoll = tcoll_list.active
    chunks = tcoll_list.get_current_active_tcoll_valild_objects(context)

    if len(chunks) <= 0:
        return False

    first_chunk = chunks[0]
    if not first_chunk:
        return False

    select_object(context, first_chunk)
    set_active_object(context, first_chunk)

    # No importa si el primero no tiene smoke, al final es el resultado que queremos y evitamos un loop extra.
    remove_modifier_from_active_object(context, 'FLUID')

    for obj in chunks:
        if RBDLabNaming.SMOKE_MOD in obj.modifiers:
            select_object(context, obj)
            set_active_object(context, obj)
            remove_modifier_from_active_object(context, 'FLUID', False)

    # bpy.ops.object.make_links_data(type='MODIFIERS')

    return True  # Everything OK.


# def avalidable_ps_update(self, context):
#     current = context.scene.rbdlab_avalidable_ps
#
#
# def avalidable_ps(cItems):
#     if cItems:
#         bpy.types.Scene.rbdlab_avalidable_ps = EnumProperty(
#             items=cItems,
#             name="rbdlab_avalidable_ps",
#             description="Avalidable Particles",
#             default=None,
#             update=avalidable_ps_update
#         )


def get_keyframes_and_value_from(obj, dpath="rigid_body.kinematic"):
    if obj and dpath:
        array_kfs = []
        fcurves = obj.animation_data.action.fcurves

        for curve in fcurves:
            if curve.data_path == dpath:
                for keyframe in curve.keyframe_points:
                    kf = keyframe.co[0]
                    kfv = keyframe.co[1]
                    array_kfs.append([kf, kfv])

        if array_kfs:
            return array_kfs
        else:
            return -1

    else:
        return -1


# def check_if_have_velocities_and_add_if_not_have(context):
#     rbdlab = context.scene.rbdlab
#     if rbdlab.filtered_target_collection:
#         if rbdlab.filtered_target_collection.name:
#             coll_name = rbdlab.filtered_target_collection.name

#             # busco si algun chunk tiene velocities:
#             match = False
#             i = 0
#             while not match and i < len(bpy.data.collections[coll_name].objects):
#                 if RBDLabNaming.VELOCITIES not in bpy.data.collections[coll_name].objects[i]:
#                     match = True
#                 i += 1

#             # si ningun chunk tiene velocities las intento calcular:
#             if not match:
#                 bpy.ops.rbdlab.compute_velocities()

#         else:
#             print("target collection empty")
#     else:
#         print("target collection empty")


def move_objects_to_collection(context, objects: list[Object], coll_name: str, with_print=True) -> Collection:
    rbdlab = context.scene.rbdlab
    new_coll = None

    print("move object to collection:", coll_name)

    # si no existe su coll target la creamos
    # if coll_name not in rbdlab.root_collection.children:
    #     new_coll = create_new_collection(context, coll_name)
    new_coll = bpy.data.collections.get(coll_name)
    if not new_coll:
        new_coll = create_new_collection(context, coll_name)

    # Para moverlos a su coleccion (antes solo soportaba el primer nivel ahora recursivamente, el primero q encuentre):
    # coll_target = rbdlab.root_collection.children.get(coll_name) # <- solo de primer nivel.
    coll_target = next((coll for coll in rbdlab.root_collection.children_recursive if coll.name == coll_name), None)

    if coll_target:

        moved = 0
        for obj in objects:

            # deslinko de donde esten
            if obj.name in coll_target.objects:
                if with_print:
                    print(obj.name + " It is already in the collection: " + coll_target.name)
                continue

            for coll in obj.users_collection:
                if coll.name != RBDLabNaming.RBD_WORLD:
                    coll.objects.unlink(obj)

            # los muevo a su coleccion
            # move object to collection
            coll_target.objects.link(obj)
            moved += 1

        rbdlab.chunks_selected = moved
    else:
        print("Not detected " + coll_name + " in RBDLab collection!")

    # si se a creado una nueva collection se returna:
    return new_coll


def chunk_are_inside_original(chunks):
    valid_chunks = []
    org_visibility = None

    for obj in chunks:
        obj_vector = obj.location
        # obj_vector = obj.matrix_world.translation

        original = None
        if not original:
            original = bpy.data.objects.get(obj[RBDLabNaming.FROM])
            org_visibility = original.hide_get()
            original.hide_set(False)

            bm = bmesh.new()
            bm.from_mesh(original.data)

        if original and bm:
            bvh = BVHTree.FromBMesh(bm, epsilon=0.0001)
            fco, normal, _, _ = bvh.find_nearest(obj_vector)
            p2 = fco - Vector(obj_vector)
            v = p2.dot(normal)
            if not v < 0.0:
                valid_chunks.append(obj)

    if org_visibility:
        original.hide_set(org_visibility)

    return valid_chunks


# ya no se usa mas, fue sustituida por select_inner_faces_by_attribute
def select_by_inner_material(context, obj, aditive: bool = True):
    # nos aseguramos de que la seleccion sea por el material interno:
    if obj:

        if context.view_layer.objects.active != obj:
            set_active_object(context, obj)

        enter_edit_mode(context)

        if not aditive:
            bpy.ops.mesh.select_all(action='DESELECT')

        inner_mat = None
        for i, mat_slot in enumerate(obj.material_slots):
            if RBDLabNaming.INNER_MAT_TAG in mat_slot.material:
                inner_mat = mat_slot.name
                obj.active_material_index = i
            bpy.ops.object.material_slot_select()

        if not inner_mat:
            if obj:
                print(obj.name + " Dont have inner_mat for Material selection!")


def select_inner_faces_by_attribute(context, objects: list[Object], debug: bool = False) -> Union[None, bool]:

    if objects:
        deselect_all_objects(context)

        for ob in objects:
            ob.select_set(True)

        enter_edit_mode(context)
        context.tool_settings.mesh_select_mode = (False, False, True)
        bpy.ops.mesh.select_all(action='DESELECT')
        enter_object_mode(context)

        # material_index es un attributo que ya crea cell fracture al usar materiales
        # attr_name = "material_index"

        # uso mi attribute porque este no me lo borran al borrar los materiales:
        attr_name = "Inner_faces"

        for ob in objects:
            me = ob.data
            attributes = me.attributes
            if attr_name not in attributes:
                print(f"Your object {ob.name} do not have the attribute {attr_name}!")
                continue

            bm = bmesh.new()
            bm.from_mesh(me)
            # bm.from_edit_mesh(me)

            # si es mayor q 0 es una cara interna:
            target_faces = [face for face in bm.faces if attributes[attr_name].data[face.index].value > 0]
            for face in target_faces:
                face.select = True

            # to refresh and see changes
            # bmesh.update_edit_mesh(me)
            bm.to_mesh(me)
            bm.free()

        enter_edit_mode(context)

        selected_any = any([
            context.active_object.data.total_vert_sel > 0,
            context.active_object.data.total_edge_sel > 0,
            context.active_object.data.total_face_sel > 0
        ])
        
        if debug:
            if not selected_any:
                print(f"[DEBUG] select_inner_faces_by_attribute not have selected anything! attr: {attr_name}!")
            else:
                print(f"[DEBUG] select_inner_faces_by_attribute Cool, have selected anything! attr: {attr_name}!")

        return selected_any


def store_inner_faces_in_attribute(ob: Object) -> None:
    """
        Ahora utilizamos esta función, ya que cell fracture ya crea uno llamado material_index, pero
        si borras los materiales lo pierdes!!.
    """

    # Guardar un attribute custom:
    # tendremos por cada cara un 1 si es innet y un 0 es no es inner:
    attr_name = "Inner_faces"
    me = ob.data
    attributes = me.attributes

    if attr_name not in attributes:
        attributes.new(name=attr_name, type='INT', domain='FACE')

    valid_mats_index = [ob.material_slots.find(mat.name) for mat in ob.material_slots if "Inner_mat" in mat.name]
    attribute_values = [int(poly.material_index in valid_mats_index) for poly in ob.data.polygons]
    if len(attribute_values) > 0:
        attribute = attributes[attr_name]
        attribute.data.foreach_set("value", attribute_values)

# def apply_modifiers_low_level(context, obj):
#     # esto es mas lento que conter bpy.ops.object.convert(target='MESH')
#     old_mesh = obj.data
#     dg = context.evaluated_depsgraph_get()
#     obj_eval = obj.evaluated_get(dg)
#     mesh_from_eval = bpy.data.meshes.new_from_object(obj_eval)
#     obj.data = mesh_from_eval
#     obj.modifiers.clear()
#     bpy.data.meshes.remove(old_mesh)


def rm_ob(target: Union[str, Object]) -> None:

    # Comprobar si se trata de una cadena o de un objeto
    if isinstance(target, str):
        ob = bpy.data.objects.get(target)

    elif isinstance(target, Object):
        ob = target

    else:
        raise ValueError("[rm_ob] Invalid type of object received!")

    # Comprobar si se ha encontrado el objeto y, si es así, eliminarlo
    if ob:
        try:

            # si tiene rigidbodies:
            if ob.rigid_body:
                if ob.name in bpy.data.collections[RBDLabNaming.RBD_WORLD]:
                    # lo deslinko de RigidBodyWorld:
                    bpy.data.collections[RBDLabNaming.RBD_WORLD].objects.unlink(ob)

            # si es un constraint:
            if ob.rigid_body_constraint:
                if ob.name in bpy.data.collections[RBDLabNaming.RBD_CONSTRAINTS]:
                    # lo deslinko de RigidBodyConstraints:
                    bpy.data.collections[RBDLabNaming.RBD_CONSTRAINTS].objects.unlink(ob)

            if ob.name in bpy.data.objects:
                bpy.data.objects.remove(ob, do_unlink=True)

        except:
            raise ValueError("[rm_ob] Object not found in bpy.data.objects or could not be removed!")
    else:
        raise ValueError("[rm_ob] Invalid object received, cannot remove object!")


def remove_all_keyframes_in_action(context, ob: Object, action_name: str):
    if ob is not None:
        action = ob.animation_data.action if ob.animation_data is not None else None
        # Verifica que el action de animacion sea el correcto
        if action is not None:
            # Itera sobre todos los fcurves, eliminando los keyframes
            for fcurve in action.fcurves:
                # print(fcurve.data_path, action_name)
                if fcurve.data_path != action_name:
                    continue
                # fcurve.keyframe_points.clear()
                action.fcurves.remove(fcurve)


def set_interpolation_curve_to(ob: Object, data_path, interpolation_type: str = 'LINEAR'):
    if ob is None or ob.animation_data is None:
        return

    valid_interpolation_types = {'CONSTANT', 'LINEAR', 'BEZIER'}
    if interpolation_type not in valid_interpolation_types:
        raise ValueError(f"Tipo de interpolación inválido. Valores aceptados: {valid_interpolation_types}")

    # Busca la curva con la propiedad dada
    matching_fcurves = [fc for fc in ob.animation_data.action.fcurves if fc.data_path == data_path]

    # Asignar el tipo de interpolación a cada keyframe en la curva
    for curve in matching_fcurves:
        for kf in curve.keyframe_points:
            kf.interpolation = interpolation_type


def get_high_collection_objects(collection: Collection) -> List[Object] :
    coll_name = collection.name
    
    if coll_name.endswith(RBDLabNaming.SUFIX_LOW):
        coll_high_name = coll_name.replace(RBDLabNaming.SUFIX_LOW, RBDLabNaming.SUFIX_HIGH)
    else:
        coll_high_name = coll_name + RBDLabNaming.SUFIX_HIGH

    high_coll = bpy.data.collections.get(coll_high_name)
    if high_coll:
        return high_coll.objects[:]
    
    return []


def apply_transfroms_low_level(ob, use_location=False, use_rotation=False, use_scale=False):
    mb = ob.matrix_basis
    I = Matrix()
    loc, rot, scale = mb.decompose()

    # rotation
    T = Matrix.Translation(loc)
    #R = rot.to_matrix().to_4x4()
    R = mb.to_3x3().normalized().to_4x4()
    S = Matrix.Diagonal(scale).to_4x4()

    transform = [I, I, I]
    basis = [T, R, S]

    def swap(i):
        transform[i], basis[i] = basis[i], transform[i]

    if use_location:
        swap(0)
    if use_rotation:
        swap(1)
    if use_scale:
        swap(2)
        
    M = transform[0] @ transform[1] @ transform[2]
    if hasattr(ob.data, "transform"):
        ob.data.transform(M)
    for c in ob.children:
        c.matrix_local = M @ c.matrix_local
        
    ob.matrix_basis = basis[0] @ basis[1] @ basis[2]


def create_coll_if_not_exist(context, rbdlab, father_coll: Collection, new_coll_name:str) -> Collection:
    if not rbdlab.root_collection:
        set_active_collection_to_master_coll(context) 

    # Si no existe la collection MetalSoft_Proxys, la creamos:
    new_coll = bpy.data.collections.get(new_coll_name)
    
    if not new_coll:
        set_active_collection_by_name(context, father_coll.name)
        new_coll = bpy.data.collections.new(new_coll_name)
        father_coll.children.link(new_coll)
    
    return new_coll


def create_originals_coll_if_not_exist(context, rbdlab) -> Collection:
    if not rbdlab.root_collection:
        set_active_collection_to_master_coll(context) 
    
    # Si no existe la collection Originals, la creamos:
    originals_coll = create_coll_if_not_exist(context, rbdlab, rbdlab.root_collection, RBDLabNaming.ORIGINALS)
    rbdlab.originals_collection = originals_coll 
    return originals_coll


def low_level_duplicate_ob(obj_to_duplicate: Object) -> Object:
    
    collections = obj_to_duplicate.users_collection

    # Crea una copia del objeto
    new_obj = obj_to_duplicate.copy()
    new_obj.data = obj_to_duplicate.data.copy()

    # Agrega la copia al escenario
    for coll in collections:
        coll.objects.link(new_obj)

    # Opcional: selecciona la nueva copia
    # bpy.context.view_layer.objects.active = new_obj
    # new_obj.select_set(True)

    return new_obj


def collapse_collections(context: Context, state: int) -> None:
    
    """ 
        State:
        1 = Abierto 
        2 = Cerrado
    """

    # sobreescribir el contexto:
    def callback(context) -> None:
        bpy.ops.outliner.show_hierarchy('INVOKE_DEFAULT')
        for i in range(state):
            bpy.ops.outliner.expanded_toggle()
            context.area.tag_redraw()

    context_override(context=context, area_type='OUTLINER', callback=callback)


def cell_fracture_installed_and_enabled():
    
    # Ya no es necesario porque incluimos cellfracture dentro de nuestr lib

    print("[RBDLab] Check Cell Fracture")
    
    # A partir de la 4.2 cambiaron las extensiones y addons y ahora se llama diferente:
    cell_fracture_name = "bl_ext.blender_org.cell_fracture" if bpy.app.version >= (4, 2, 0) else "object_fracture_cell"
    
    is_enabled, is_loaded = check(cell_fracture_name)
    if not all([is_enabled, is_loaded]):

        if bpy.app.version >= (4, 2, 0):
        
            # Si se supone que hay conexion a internet:
            if bpy.context.preferences.system.use_online_access:
                
                # Instalamos la extension:
                print("[RBDLab] Trying to install cell fracture from the internet...")
                bpy.ops.extensions.package_install(repo_index=0, pkg_id="cell_fracture")

            else:
                # feedback:
                print(f"[RBDLab] You did not grant blender permissions to access the internet, we cannot install cell fracture automatically. \nIf you want you can install it offline manually.")
        
            # Vuelvo a chekear por si acaso (aunque parece q el instalar la extension la activa luego):
            # Si no está enabled, porque loaded al ser built in de blender si debería incluirlo, lo activamos:
            is_enabled, is_loaded = check(cell_fracture_name)
            if not is_enabled:
                print("[RBDLab] Activating cell fracture...")
                bpy.ops.preferences.addon_enable(module=cell_fracture_name)
        
        else:
            # si anterior a blendr 4.2 simplemente lo activamos:
            print("[RBDLab] Activating cell fracture...")
            bpy.ops.preferences.addon_enable(module=cell_fracture_name)