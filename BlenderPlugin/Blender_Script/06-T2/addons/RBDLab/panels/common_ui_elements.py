from bpy.types import UILayout, Object, Modifier
# from bpy.props import BoolProperty
from ..Global.get_common_vars import get_common_vars


def title_header(col, title: str):
    header = col.box().row(align=True)
    header.alignment = 'CENTER'
    header.label(text=title)


def button_prop_with_without_icon(icon_add, button_settings):
    if button_settings["icon"]:
        icon_add.prop(
            button_settings["from"],
            button_settings["prop"],
            text=button_settings["text"],
            toggle=button_settings["toggle"],
            expand=button_settings["expand"],
            icon=button_settings["icon"],
        )
    else:
        icon_add.prop(
            button_settings["from"],
            button_settings["prop"],
            toggle=button_settings["toggle"],
            expand=button_settings["expand"],
            text=button_settings["text"]
        )

    if "scale_x" in button_settings:
        icon_add.scale_x = button_settings["scale_x"]

    if "scale_y" in button_settings:
        icon_add.scale_y = button_settings["scale_y"]


def button_op_with_without_icon(icon_add, button_settings):
    if "depress" in button_settings:
        if button_settings["icon"]:
            icon_add.operator(
                button_settings["prop"],
                text=button_settings["text"],
                icon=button_settings["icon"], depress=button_settings["depress"]
            )
        else:
            icon_add.operator(
                button_settings["prop"],
                text=button_settings["text"], depress=button_settings["depress"]
            )
    else:
        if button_settings["icon"]:
            icon_add.operator(
                button_settings["prop"],
                text=button_settings["text"],
                icon=button_settings["icon"]
            )
        else:
            icon_add.operator(
                button_settings["prop"],
                text=button_settings["text"]
            )

    if "scale_x" in button_settings:
        icon_add.scale_x = button_settings["scale_x"]

    if "scale_y" in button_settings:
        icon_add.scale_y = button_settings["scale_y"]


def collapsable(
        layout, contain_prop, show_hide_str: str, mytext: str, myicon: str = None, align=True,
        button_settings1: dict[str, str] = {},
        button_settings2: dict[str, str] = {}):
    show_hide = getattr(contain_prop, show_hide_str)

    header = layout.box()
    subheader = header.row(align=True)

    toggle = subheader.row(align=True)
    toggle.use_property_split = False
    toggle.alignment = 'LEFT'
    toggle.emboss = 'NONE'
    toggle.prop(contain_prop, show_hide_str, icon='DISCLOSURE_TRI_DOWN' if show_hide else 'DISCLOSURE_TRI_RIGHT', text="")

    if len(button_settings1) > 0:
        row = subheader.row(align=True)
        row.emboss = 'NORMAL'
        row.alignment = 'RIGHT'
        icon_add1 = row.row(align=True)
        icon_add2 = row.row(align=True)
        icon_add1.emboss = 'NORMAL'
        icon_add1.alignment = 'RIGHT'
        icon_add2.emboss = 'NORMAL'
        icon_add2.alignment = 'RIGHT'
        icon_add1.separator()

        if "enabled" in button_settings1:
            icon_add1.enabled = button_settings1["enabled"]

        if "enabled" in button_settings2:
            icon_add2.enabled = button_settings2["enabled"]

        if button_settings1["type"] == "prop":
            button_prop_with_without_icon(icon_add1, button_settings1)
            if len(button_settings2) > 0:
                button_prop_with_without_icon(icon_add2, button_settings2)

        elif button_settings1["type"] == "operator":
            button_op_with_without_icon(icon_add1, button_settings1)
            if len(button_settings2) > 0:
                button_op_with_without_icon(icon_add2, button_settings2)

    if myicon:
        toggle.prop(contain_prop, show_hide_str, text=mytext, icon=myicon)
    else:
        toggle.prop(contain_prop, show_hide_str, text=mytext)

    if show_hide:
        settings = layout.box().column(align=align)
        return settings


def cheker_item_visibility(context):

    tcoll_list = get_common_vars(context, get_tcoll_list=True)

    item = tcoll_list.active_item
    if item:
        return item.visibility
    else:
        return True


def multiline_print(layout: UILayout, text: str, max_words: int, without_box:bool=False, icon:str='INFO', first_line_crop:int=0) -> None:

    if without_box:
        feedback = layout.column(align=True)
    else:
        feedback = layout.box().column(align=True)

    words = text.split()

    # con recorte de primera linea:
    if first_line_crop != 0:
        
        crop = max_words-first_line_crop
        feedback.label(text=" ".join(words[:crop]), icon=icon)
        rest_words = words[crop:]        
        for i in range(0, len(rest_words), max_words):
            feedback.label(text=" ".join(rest_words[i:i+max_words]))

    else:
        # sin recorte de primera linea:
        for i in range(0, len(words), max_words):
            if i == 0:
                feedback.label(text=" ".join(words[i:i+max_words]), icon=icon)
            else:
                feedback.label(text=" ".join(words[i:i+max_words]))


def horizontal_line_separator(layout: UILayout) -> UILayout:
    layout = layout.box().column(align=True)
    return layout


def draw_collision_collections(layout, ob:Object, prop_name:str):

    """ 
        Esto dibuja dos bloques con 10 numeros (las old layers de blender) 
        para los rigidbodies, pero con numeros, algo así:
        [  1 ][  2 ][  3 ][  4 ][  5 ]  [  6 ][  7 ][  8 ][  9 ][ 10 ]
        [ 11 ][ 12 ][ 13 ][ 14 ][ 15 ]  [ 16 ][ 17 ][ 18 ][ 19 ][ 20 ]
    """
    
    col = layout.column(align=True)
    col.use_property_split = False
    col.use_property_decorate = False

    for y in range(2):

        row = col.row(align=True)

        for x in range(10):

            if y == 0:
                idx = str(x+1)
            else:
                idx = str(x + 1 + 10)

            if x == 5:
                row.separator(factor=2)

            row.prop_enum(ob.rbdlab, prop_name, idx, text=idx)
    
    return col


#----------------------------------------------------------------------------------------------------------------------------
# Modifiers UIS:
#----------------------------------------------------------------------------------------------------------------------------


def get_props_in_order(list_props, ref_list:list)-> list:
                            
    """ obtengo las propiedades que existan en valid_props, en el orden correcto que se pase en el listado de referencia """

    all_props_identifiers = set(prop.identifier for prop in list_props)
    # print(all_props_identifiers)
    result = [prop for prop in ref_list if prop in all_props_identifiers]

    return result


def vertex_groups(context, layout, vali_props, mod) -> None:
                            
    """ Maquetación de UI para Vertex Groups de los modifiers """

    vg_props_ui = layout.row(align=True)
    vg_props_names = ["vertex_group", "invert_vertex_group"]
    vg_props = get_props_in_order(vali_props, vg_props_names)
    for vg_prop in vg_props:
        if vg_prop == "invert_vertex_group":
            vg_props_ui.prop(mod, vg_prop, toggle=True, text="", icon='ARROW_LEFTRIGHT')
        else:
            vg_props_ui.prop_search(mod, vg_prop, context.object, "vertex_groups", text="Vertex Group")    

def ui_remesh_modifier(context, layout, mod:Modifier) -> None:
    
    vali_props = [prop for prop in mod.bl_rna.properties if not prop.is_hidden and prop.is_readonly == False] 
    common_props = [prop.identifier for prop in vali_props if prop.identifier in ["mode", "use_smooth_shade"]] 
    
    if mod.mode == 'BLOCKS':
        specific = ["octree_depth", "scale", "use_remove_disconnected", "threshold"]

    elif mod.mode == 'SMOOTH':
        specific = ["octree_depth", "scale", "use_remove_disconnected", "threshold"]

    elif mod.mode == 'SHARP':
        specific = ["octree_depth", "scale", "sharpness", "use_remove_disconnected", "threshold"]

    elif mod.mode == 'VOXEL':
        specific = ["voxel_size", "adaptivity"]
    
    specific_props = get_props_in_order(vali_props, specific)

    # Mode:
    mode_row = layout.row(align=True)
    mode_row.use_property_split = False
    mode_row.prop(mod, common_props[0], expand=True)
    layout.separator()

    # Propiedades especificas:
    for sp_prop in specific_props:
        layout.prop(mod, sp_prop)
    
    # Smooth Shading:
    layout.prop(mod, common_props[1])


def ui_smooth_modifier(context, layout, mod:Modifier) -> None:

    vali_props = [prop for prop in mod.bl_rna.properties if not prop.is_hidden and prop.is_readonly == False]

    axis = ["use_x", "use_y", "use_z"]
    axis_props = get_props_in_order(vali_props, axis)
    
    axis_row = layout.row(align=True)
    axis_row.use_property_split = False
    for axis_prop in axis_props:
        axis_row.prop(mod, axis_prop, toggle=True)
    
    layout.separator()

    rest_props_names = ["factor", "iterations"]
    rest_props = get_props_in_order(vali_props, rest_props_names)
    rest_props_ui = layout.column(align=True)
    for rst_prop in rest_props:
        rest_props_ui.prop(mod, rst_prop)
    
    vertex_groups(context, layout, vali_props, mod)


def ui_subsurf_modifier(context, layout, mod:Modifier) -> None:
    
    vali_props = [prop for prop in mod.bl_rna.properties if not prop.is_hidden and prop.is_readonly == False]

    subsurf_type = layout.row(align=True)
    subsurf_type.use_property_split = False
    subsurf_type.prop(mod, "subdivision_type", expand=True)
    
    layout.separator()

    rest_props_names = ["levels", "render_levels", "show_only_control_edges"]
    rest_props = get_props_in_order(vali_props, rest_props_names)
    rest_props_ui = layout.column(align=True)
    for rst_prop in rest_props:
        rest_props_ui.prop(mod, rst_prop)


def ui_displace_modifier(context, layout, mod:Modifier) -> None:

    vali_props = [prop for prop in mod.bl_rna.properties if not prop.is_hidden and prop.is_readonly == False]

    rest_props_names = ["texture", "texture_coords", "direction", "strength", "mid_level"]
    rest_props = get_props_in_order(vali_props, rest_props_names)
    rest_props_ui = layout.column(align=True)
    for rst_prop in rest_props:

        if rst_prop != "texture":
    
            rest_props_ui.prop(mod, rst_prop)
    
        else: # Si es texture:

            row = rest_props_ui.row(align=True)
            row.scale_x = 1.5
            
            if not mod.texture:

                row.prop(mod, rst_prop, text="Add Texture")
                op_bt = row.row(align=True)
                op_bt.scale_x = 2.6
                # op_bt.operator("texture.new", text="New")
                op_bt.operator("rbdlab.metalsoft_creation_displace_new_texture", text="New")
                rest_props_ui.separator()

            else:

                rest_props_ui.prop(mod, "texture")
                texture_props = ("type", "noise_basis", "noise_type", "cloud_type", "noise_scale", "noise_depth", "nabla")
                for txt_prop in texture_props:
                    all_identifiers = (prop.identifier for prop in mod.texture.bl_rna.properties) 
                    if txt_prop in all_identifiers:
                        rest_props_ui.prop(mod.texture, txt_prop)
   
                rest_props_ui.separator()


    
    vertex_groups(context, layout, vali_props, mod)


def ui_decimate_modifier(context, layout, mod:Modifier) -> None:

    vali_props = [prop for prop in mod.bl_rna.properties if not prop.is_hidden and prop.is_readonly == False]

    decimate_type = layout.row(align=True)
    decimate_type.use_property_split = False
    decimate_type.prop(mod, "decimate_type", expand=True)
    
    layout.separator()

    if mod.decimate_type == 'COLLAPSE':

        col = layout.column(align=False, heading="Symmetry")
        col.use_property_decorate = False
        use_sym_row = col.row(align=True)
        use_sym_row.prop(mod, "use_symmetry", text="")
        axis = use_sym_row.row(align=True)
        axis.enabled =  mod.use_symmetry
        axis.prop(mod, "symmetry_axis", expand=True)

        layout.prop(mod, "use_collapse_triangulate")

        layout.separator()
        vertex_groups(context, layout, vali_props, mod)
        layout.separator()

        vgf = layout.row(align=True)
        vgf.enabled = len(mod.vertex_group) > 0
        vgf.prop(mod, "vertex_group_factor")
    
    elif mod.decimate_type == 'UNSUBDIV':

        layout.prop(mod, "iterations")
    
    elif mod.decimate_type == 'DISSOLVE':
        layout.prop(mod, "angle_limit")
        layout.separator()
        layout.prop(mod, "delimit")
        layout.prop(mod, "use_dissolve_boundaries")


def ui_solidify_modifier(context, layout, mod:Modifier) -> None:

    vali_props = [prop for prop in mod.bl_rna.properties if not prop.is_hidden and prop.is_readonly == False]

    solidify_type = layout.row(align=True)
    # solidify_type.use_property_split = False
    solidify_type.prop(mod, "solidify_mode")
    
    layout.separator()
    if mod.solidify_mode == 'EXTRUDE': # Simple
    
        rest_props_names = [
                            "thickness", 
                            "offset", 
                            "use_even_offset", 
                            "use_rim", 
                            "use_rim_only"
                            ]
    
    elif mod.solidify_mode == 'NON_MANIFOLD': # Complex

        rest_props_names = [
                            "nonmanifold_thickness_mode", 
                            "nonmanifold_boundary_mode", 
                            "thickness", 
                            "offset", 
                            "nonmanifold_merge_threshold",
                            "use_even_offset", 
                            "use_rim", 
                            "use_rim_only"
                            ]

    rest_props = get_props_in_order(vali_props, rest_props_names)
    rest_props_ui = layout.column(align=True)
    for rst_prop in rest_props:

        if rst_prop == "use_rim_only":
            row = rest_props_ui.row(align=True)
            row.prop(mod, rst_prop)
            row.enabled = mod.use_rim
        else:
            rest_props_ui.prop(mod, rst_prop)

    layout.separator()
    vertex_groups(context, layout, vali_props, mod)
    layout.separator()

    vgf = layout.column(align=True)
    vgf.enabled = len(mod.vertex_group) > 0
    vgf.prop(mod, "thickness_vertex_group")
    vgf.prop(mod, "use_flat_faces")

#----------------------------------------------------------------------------------------------------------------------------
# En Modifiers UIS
#----------------------------------------------------------------------------------------------------------------------------
