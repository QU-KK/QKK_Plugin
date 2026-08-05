import bpy
import bmesh
from typing import Union, Callable
from bpy.types import Object, Context
from ..addon.naming import RBDLabNaming


def enter_object_mode(context):
    if context.mode != 'OBJECT':
        bpy.ops.object.mode_set(mode='OBJECT', toggle=False)


def enter_edit_mode(context, mode:Union[str, tuple]=None) -> None:
    
    """ 
        Con una tupla en mode usara context.tool_settings.mesh_select_mode. 
        Pero con un string tipo 'VERT', entonces usa el operador ops.mesh.select_mode.
        NOTA: Parece ser que el de operador funciona mejor que con la tupla.
    """
    
    active = context.active_object
    if active:
        if active.type == 'MESH':
            if context.mode != 'EDIT':
                bpy.ops.object.mode_set(mode='EDIT', toggle=False)
                
                if mode:

                    if isinstance(mode, tuple):
                        # creo q normalmente este debería ir pero con el mesh.select_non_manifold no me sirvió...
                        context.tool_settings.mesh_select_mode = mode
    
                    elif isinstance(mode, str):
                        # preferia usar el de la tupla pero el operador de mesh.select_non_manifold no detectaba el cambio a vertex.
                        bpy.ops.mesh.select_mode(use_extend=False, use_expand=False, type=mode)
        else:
            print(
                "Is necessary the active object is of the MESH type for enter in edit mode!")
    else:
        print("Is necessary the active object for enter in edit mode!")


def select_object(context, obj_input: Object, with_print: bool = False) -> None:
    scn = context.scene
    view_layer = context.view_layer
    ob = None
    if obj_input:
        if isinstance(obj_input, str):
            if obj_input in bpy.data.objects and obj_input in scn.objects:
                ob = scn.objects[obj_input]
        elif isinstance(obj_input, Object):
            if obj_input.name in bpy.data.objects and obj_input.name in scn.objects:
                ob = obj_input
    if ob:
        if ob.name in view_layer.objects:
            if ob.visible_get():
                ob.select_set(True)
            else:
                if with_print:
                    print(ob.name + " is not visible in viewport!, not selecting.")


def deselect_object(ob):
    ob.select_set(False)


def deselect_all_objects_no_meshes(context):
    for ob in context.selected_objects:
        if ob.type != 'MESH':
            deselect_object(ob)


def set_active_object(context: Context, ob: Union[str, Object], only_selected_ob: bool = False) -> None:
    # Si se recibe un string, intentamos encontrar el objeto en la escena
    if isinstance(ob, str):
        ob = context.scene.objects.get(ob)

        # Si el objeto no se encuentra, imprimimos un mensaje de error y salimos de la función
        if not ob:
            print(f"ERROR: No se puede encontrar el objeto '{ob}'")
            return
    
    # Luego verificamos si el objeto es válido
    if not isinstance(ob, Object):
        print(f"ERROR: El argumento 'ob' debe ser una instancia de Object o una cadena")
        return
    
    # Intentamos seleccionar el objeto activo
    try:
        if only_selected_ob:
            bpy.ops.object.select_all(action='DESELECT')
            ob.select_set(True)
        # Establece el objeto activo
        # print("haciendo activo", ob.name)
        context.view_layer.objects.active = ob
        # print("[DEBUG] context.active_object, context.view_layer.objects.active:", context.active_object, context.view_layer.objects.active)
    except Exception as e:
        print(f"ERROR: No se puede hacer activo el objeto '{ob.name}': {e}")
        return
  
    # Aseguramos que el objeto esté seleccionado
    if ob != context.view_layer.objects.active:
        print(f"ERROR: El objeto '{ob.name}' no está activo!")
        return
    
    # Marcamos que el objeto ha sido actualizado en la escena
    ob.update_tag()
            
        

            

def deselect_all_objects(context):
    enter_object_mode(context)
    bpy.ops.object.select_all(action='DESELECT')


def select_all_vertices(context):
    obj = context.object
    if obj:
        if obj.type == 'MESH':
            me = obj.data
            bm = bmesh.from_edit_mesh(me)

            for v in bm.verts:
                v.select_set(True)

            bmesh.update_edit_mesh(me)


def get_object_from_data(name):
    return bpy.data.objects.get(name, None)


def rm_ob(target: Union[str, Object]) -> None:
    ob = None
    if isinstance(target, str):
        ob = get_object_from_data(target)
    elif isinstance(target, Object):
        ob = target
    else:
        print("[rm_ob]: not valid type obj recived!")
    if ob:
        if ob.name in bpy.data.objects:
            bpy.data.objects.remove(ob, do_unlink=True)
        else:
            print("[rm_ob]:", ob, "Not in bpy.data.objects, cant remove object!")
    else:
        print("[rm_ob]:", ob, "Not valid object, cant remove object!")


def get_first_high_mesh_visible(context):
    rbdlab = context.scene.rbdlab
    tcoll = rbdlab.filtered_target_collection

    if tcoll is None:
        return

    coll_high_name = None
    coll_name = tcoll.name

    if coll_name.endswith(RBDLabNaming.SUFIX_LOW):
        coll_high_name = coll_name.replace(RBDLabNaming.SUFIX_LOW, RBDLabNaming.SUFIX_HIGH)
    else:
        coll_high_name = coll_name + RBDLabNaming.SUFIX_HIGH

    coll_high = bpy.data.collections.get(coll_high_name)
    if coll_high:

        valid_objects = [obj for obj in coll_high.objects if obj.type == 'MESH']

        if valid_objects:
            return valid_objects[0]


def get_first_mesh(context):
    rbdlab = context.scene.rbdlab
    tcoll = rbdlab.filtered_target_collection

    if tcoll is None:
        return

    return next((obj for obj in tcoll.objects if obj.type == 'MESH'), None)


def ocultar_post_panel_settings():
    # ocultar ventana modal de dialogo de properties tras ejecutar un operador:
    
    # me da este error:
    # Warning: 1 x Draw window and swap:  ms, average:  ms
    # bpy.ops.wm.redraw_timer(type='DRAW_WIN_SWAP', iterations=1)
    
    pass


def context_override(context, area_type: str, callback: Callable) -> None:
    """ Context Override Blender 4.0 """
    area = next((a for a in context.screen.areas if a.type == area_type), None)
    if area:
        # Encuentra una región adecuada dentro del área especificada
        region = next((r for r in area.regions if r.type == 'WINDOW'), None)
        if region:
            override_context = context.copy()
            override_context['window'] = context.window
            override_context['screen'] = context.screen
            override_context['area'] = area
            override_context['region'] = region
            
            with context.temp_override(**override_context):
                callback(context)  # Pasamos el contexto sobrescrito
            
            # with context.temp_override(window=context.window, area=area, region=region):
            #    callback(area)
