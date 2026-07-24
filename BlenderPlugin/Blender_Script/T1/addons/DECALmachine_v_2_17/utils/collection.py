from re import S
import bpy

from typing import Union

from . system import printd

def get_scene_collections(context, debug=False):
    layer_collections = []

    get_layer_collections_recursively(context.view_layer.layer_collection, layer_collections)

    collections = {}

    for lcol in layer_collections:
        if lcol.collection == context.scene.collection:
            continue

        if (col := lcol.collection) in collections:
            collections[col]['layer_collections'].append(lcol)

        else:
            collections[col] = {'layer_collections': [lcol]}

    for col, data in collections.items():

        data['excluded'] = all(lcol.exclude for lcol in data['layer_collections'])

        data['hidden'] = col.hide_viewport or all(lcol.hide_viewport for lcol in data['layer_collections'])

        data['visible'] = any(lcol.visible_get() for lcol in data['layer_collections'])

    if debug:
        printd(collections)

    return collections

def get_layer_collections_recursively(lcol, layer_collections):
    layer_collections.append(lcol)

    for lc in lcol.children:
        get_layer_collections_recursively(lc, layer_collections)

def set_collection_visibility(context, collection, exclude=None, hide_viewport=None):
    if exclude is not None or hide_viewport is not None:
        layer_col = context.view_layer.layer_collection.children.get(collection.name)

        if not layer_col:
            scene_collections = get_scene_collections(context)

            for col, data in scene_collections.items():
                if col == collection:
                    layer_col = data['layer_collections'][0]
                    break

        if layer_col:
            if exclude is not None:
                layer_col.exclude = exclude

            if hide_viewport is not None:
                layer_col.hide_viewport = hide_viewport

        else:
            print(f"WARNING: Could not set visibility for collection {collection.name}, as no layer collection could be found on the view layer")

def get_decals_collection(context, name='_Decals', color_tag='COLOR_06', scene_collections=None, create=True, exclude:Union[None, bool]=False, hide_viewport:Union[None, bool]=None):
    if context.scene.DM.hide_decaltype_collections:
        name = f".{name}"

    if not scene_collections:
        scene_collections = get_scene_collections(context)

    decals_cols = [col for col in scene_collections if col.name.startswith(name)]

    if decals_cols:
        dcol = decals_cols[0]

    elif create:
        dcol = bpy.data.collections.new(name)
        dcol.color_tag = color_tag
        context.scene.collection.children.link(dcol)

        set_collection_visibility(context, dcol, exclude=exclude, hide_viewport=hide_viewport)

    else:
        return

    dcol.DM.isdecaltypecol = True
    return dcol

def get_decaltype_collection(context, decaltype):
    scene = context.scene

    dcol = get_decals_collection(context)

    typename = f".{decaltype.title()}" if scene.DM.hide_decaltype_collections else decaltype.title()

    dtcol = None

    for col in dcol.children:
        if col.name.startswith(typename):
            dtcol = col
            break

    if not dtcol:
        dtcol = bpy.data.collections.new(name=typename)
        dcol.children.link(dtcol)
        dtcol.DM.isdecaltypecol = True

    return dtcol

def get_parent_collections(scene, obj):
    scene_collections = get_scene_collections(bpy.context)

    dpcols = []

    if obj.parent:
        pcols = [col for col in obj.parent.users_collection if col in scene_collections and not col.DM.isdecaltypecol]

        for col in pcols:
            dpcol = None

            for childcol in col.children:
                if childcol.DM.isdecalparentcol:
                    dpcol = childcol
                    break

            if not dpcol:
                dpcol = bpy.data.collections.new("tempdecals")
                dpcol.DM.isdecalparentcol = True

                if obj.name not in col.children:
                    col.children.link(dpcol)

            dpcol.name = f".{col.name}_Decals" if scene.DM.hide_decalparent_collections else f"{col.name}_Decals"
            dpcols.append(dpcol)

    return dpcols

def get_atlas_collection(context, atlas):
    scene = context.scene
    mcol = scene.collection

    acol = bpy.data.collections.get(atlas.name)

    if acol:
        return acol

    else:
        acol = bpy.data.collections.new(name=atlas.name)
        mcol.children.link(acol)

    return acol

def unlink_object_from_all_collections(obj):
    for col in obj.users_collection:
        col.objects.unlink(obj)

def purge_decal_collections(debug=False):
    scene_cols = get_scene_collections(bpy.context)
    dcol = get_decals_collection(bpy.context, scene_collections=scene_cols, create=False)

    purge_collections = [col for col in scene_cols if (col.DM.isdecaltypecol and col != dcol or col.DM.isdecalparentcol) and (not col.objects and not col.children)]

    for col in purge_collections:
        if debug:
            print(f"Removing collection: {col.name}")

        bpy.data.collections.remove(col, do_unlink=True)

    if dcol and dcol.DM.isdecaltypecol and not dcol.objects and not dcol.children:
        if debug:
            print(f"Removing collection: {dcol.name}")

        bpy.data.collections.remove(dcol, do_unlink=True)

def sort_into_collections(context, obj, purge=True):
    scene = context.scene
    mcol = scene.collection
    scene_collections = get_scene_collections(context)

    is_decaltype_col = scene.DM.collection_decaltype
    is_parent_col = scene.DM.collection_decalparent
    is_active_col = scene.DM.collection_active

    sorted_collections = []

    if is_decaltype_col:
        dtcol = get_decaltype_collection(context, obj.DM.decaltype)

        if obj.name not in dtcol.objects:
            dtcol.objects.link(obj)

            if obj.name in mcol.objects:
                mcol.objects.unlink(obj)

        sorted_collections.append(dtcol)

    if is_parent_col:
        dpcols = get_parent_collections(scene, obj)

        for dpcol in dpcols:
            if obj.name not in dpcol.objects:
                dpcol.objects.link(obj)

                if obj.name in mcol.objects:
                    mcol.objects.unlink(obj)

        sorted_collections.extend(dpcols)

    if is_active_col:
        acol = bpy.context.view_layer.active_layer_collection.collection

        if not any([acol.DM.isdecaltypecol, acol.DM.isdecalparentcol]):
            if obj.name not in acol.objects:
                acol.objects.link(obj)

                if obj.name in mcol.objects and mcol != acol:
                    mcol.objects.unlink(obj)

            sorted_collections.append(acol)

    unlink_collections = [col for col in obj.users_collection if col in scene_collections and col not in sorted_collections]

    for col in unlink_collections:
        col.objects.unlink(obj)

    if not any([is_decaltype_col, is_parent_col, is_active_col]) or not obj.users_collection:

        if obj.name not in mcol.objects:
            mcol.objects.link(obj)

        sorted_collections.append(mcol)

    if purge:
        purge_decal_collections()
