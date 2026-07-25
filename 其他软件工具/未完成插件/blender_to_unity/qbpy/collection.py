import bpy
from typing import List, Union


class Collection:
    @staticmethod
    def selected_collections(name_only: bool = False) -> List[bpy.types.Collection]:
        """
        Get selected collections.

        name_only (bool) - Selected collections' names only.
        return (List[bpy.types.Collection]) - Return selected collections.
        """
        for area in bpy.context.screen.areas:
            if area.type == "OUTLINER":
                for region in area.regions:
                    if region.type == "WINDOW":
                        with bpy.context.temp_override(area=area, region=region):
                            selected_ids = bpy.context.selected_ids
                            if collections := [item.name if name_only else item for item in selected_ids if isinstance(item, bpy.types.Collection)]:
                                return collections
        return []

    @staticmethod
    def get_collection(
        collection: Union[bpy.types.Collection, str],
        color_tag: str = "NONE",
        hide_select: bool = False,
        hide_viewport: bool = False,
        hide_render: bool = False,
    ) -> bpy.types.Collection:
        """
        Get or create a collection with properties.

        collection (Union[bpy.types.Collection, str]) - Collection or name of the collection.
        color_tag (enum in ['NONE', 'COLOR_01', 'COLOR_02' ,'COLOR_03' ,'COLOR_04' ,'COLOR_05' , 'COLOR_06', 'COLOR_07', 'COLOR_08'], default 'NONE') - Color of the collection.
        hide_select (bool, optional) - Hide collection in selection.
        hide_viewport (bool, optional) - Disable in viewports.
        hide_render (bool, optional) - Disable in renders.
        return (bpy.types.Collection) - Collection.
        """
        if isinstance(collection, str):
            if existing_collection := bpy.data.collections.get(collection):
                collection = existing_collection
            else:
                collection = bpy.data.collections.new(collection)

        collection.color_tag = color_tag
        collection.hide_select = hide_select
        collection.hide_viewport = hide_viewport
        collection.hide_render = hide_render

        return collection

    @staticmethod
    def get_collections(
        collections: List[Union[bpy.types.Collection, str]],
        color_tag: str = "NONE",
        hide_select: bool = False,
        hide_viewport: bool = False,
        hide_render: bool = False,
    ) -> List[bpy.types.Collection]:
        """
        Get or create collections with properties.

        collections (List[Union[bpy.types.Collection, str]]) - List of collections or names of collections.
        color_tag (enum in ['NONE', 'COLOR_01', 'COLOR_02' ,'COLOR_03' ,'COLOR_04' ,'COLOR_05' , 'COLOR_06', 'COLOR_07', 'COLOR_08'], default 'NONE') - Color of the collections.
        hide_select (bool, optional) - Hide collections in selection.
        hide_viewport (bool, optional) - Disable in viewports.
        hide_render (bool, optional) - Disable in renders.
        return (List[bpy.types.Collection]) - Collections.
        """
        collections_list = []

        for collection in collections:
            if isinstance(collection, str):
                if existing_collection := bpy.data.collections.get(collection):
                    collection = existing_collection
                else:
                    collection = bpy.data.collections.new(collection)

            collection.color_tag = color_tag
            collection.hide_select = hide_select
            collection.hide_viewport = hide_viewport
            collection.hide_render = hide_render

            collections_list.append(collection)

        return collections_list

    @staticmethod
    def get_parent_collection(collection: Union[bpy.types.Collection, str]) -> Union[bpy.types.Collection, None]:
        """
        Get parent collection.

        collection (Union[bpy.types.Collection, str]) - Collection or name of the collection.
        return (Union[bpy.types.Collection, None]) - Parent collection or None.
        """
        if isinstance(collection, str):
            collection = bpy.data.collections.get(collection)
            if not collection:
                return None

        for col in [
            bpy.context.scene.collection,
            *bpy.context.scene.collection.children_recursive,
        ]:
            if col.user_of_id(collection):
                return col

    @staticmethod
    def set_parent_collection(
        collection: Union[bpy.types.Collection, str],
        parent: Union[bpy.types.Collection, str],
    ):
        """
        Set parent collection.

        collection (Union[bpy.types.Collection, str]) - Collection or name of the collection to parent.
        parent (Union[bpy.types.Collection, str]) - Collection to parent to.
        """
        if isinstance(parent, str):
            parent = bpy.data.collections.get(parent)
            if not parent:
                return None

        if parent_collection := Collection.get_parent_collection(collection):
            parent_collection.children.unlink(collection)
            parent.children.link(collection)

    @staticmethod
    def set_collection(
        collection: Union[bpy.types.Collection, str],
        color_tag: str = "NONE",
        exclude: bool = False,
        hide_select: bool = False,
        hide_layer: bool = False,
        hide_viewport: bool = False,
        hide_render: bool = False,
        children: bool = False,
        recursive: bool = False,
    ) -> Union[bpy.types.Collection, None]:
        """
        Set collection properties.

        collection (bpy.types.Collection or str) - Collection or name of the collection.
        color_tag (enum in ['NONE', 'COLOR_01', 'COLOR_02', 'COLOR_03', 'COLOR_04', 'COLOR_05', 'COLOR_06', 'COLOR_07', 'COLOR_08'], default 'NONE') - Color of the collection.
        exclude (bool, optional) - Exclude from view layer.
        hide_select (bool, optional) - Hide collection in selection.
        hide_layer (bool, optional) - Hide Layer in viewport.
        hide_viewport (bool, optional) - Disable in viewports.
        hide_render (bool, optional) - Disable in renders.
        return (bpy.types.Collection) - Collection.
        """
        if isinstance(collection, str):
            collection = bpy.data.collections.get(collection)
            if not collection:
                return None

        if children or recursive:
            layer_collections = Collection.get_layer_collection(collection, children, recursive)
            for lc in layer_collections:
                lc.collection.color_tag = color_tag
                lc.collection.hide_select = hide_select
                lc.collection.hide_viewport = hide_viewport
                lc.collection.hide_render = hide_render
                lc.exclude = exclude
                lc.hide_viewport = hide_layer
        else:
            layer_collection = Collection.get_layer_collection(collection)
            layer_collection.collection.color_tag = color_tag
            layer_collection.collection.hide_select = hide_select
            layer_collection.collection.hide_viewport = hide_viewport
            layer_collection.collection.hide_render = hide_render
            layer_collection.exclude = exclude
            layer_collection.hide_viewport = hide_layer

        return collection

    @staticmethod
    def set_collections(
        collections: List[Union[bpy.types.Collection, str]],
        color_tag: str = "NONE",
        exclude: bool = False,
        hide_select: bool = False,
        hide_layer: bool = False,
        hide_viewport: bool = False,
        hide_render: bool = False,
    ) -> List[bpy.types.Collection]:
        """
        Set collections properties.

        collections (List[Union[bpy.types.Collection, str]]) - List of collections or names of collections.
        color_tag (enum in ['NONE', 'COLOR_01', 'COLOR_02' ,'COLOR_03' ,'COLOR_04' ,'COLOR_05' , 'COLOR_06', 'COLOR_07', 'COLOR_08'], default 'NONE') - Color of the collections.
        exclude (bool, optional) - Exclude from view layer.
        hide_select (bool, optional) - Hide collections in selection.
        hide_layer (bool, optional) - Hide layer in viewport.
        hide_viewport (bool, optional) - Disable in viewports.
        hide_render (bool, optional) - Disable in renders.
        return (List[bpy.types.Collection]) - Collections.
        """
        collections_list = []

        for collection in collections:
            if isinstance(collection, str):
                collection = bpy.data.collections.get(collection)
                if not collection:
                    continue

            layer_collection = Collection.get_layer_collection(collection)
            layer_collection.collection.color_tag = color_tag
            layer_collection.collection.hide_select = hide_select
            layer_collection.collection.hide_viewport = hide_viewport
            layer_collection.collection.hide_render = hide_render
            layer_collection.exclude = exclude
            layer_collection.hide_viewport = hide_layer

            collections_list.append(collection)

        return collections_list

    @staticmethod
    def link_collection(
        collection: Union[bpy.types.Collection, str],
        parent_collection: bpy.types.Collection = None,
    ) -> bpy.types.Collection:
        """
        Link collection to parent.

        collection (Union[bpy.types.Collection, str]) - Collection or name of the collection to link.
        parent_collection (bpy.types.Collection) - Parent collection to link to.
        return (bpy.types.Collection) - Collection.
        """
        if isinstance(collection, str):
            collection = bpy.data.collections.get(collection)
            if not collection:
                return None

        if parent_collection is None:
            parent_collection = bpy.context.scene.collection

        if not parent_collection.children.get(collection.name):
            parent_collection.children.link(collection)

        return collection

    @staticmethod
    def remove_collection(
        collection: Union[bpy.types.Collection, str],
        children: bool = False,
        recursive: bool = False,
        empty_only: bool = False,
    ):
        """
        Remove collection and its children.

        collection (Union[bpy.types.Collection, str]) - Collection or name of the collection to remove.
        children (bool) - Remove children collections of collecion.
        recursive (bool) - Remove recursive children collections of collecion.
        empty_only (bool) - Remove only empty collections.
        """
        if isinstance(collection, str):
            collection = bpy.data.collections.get(collection)
            if not collection:
                return None

        if empty_only:
            if recursive:
                collections = [col for col in collection.children_recursive if not col.all_objects]
            elif children:
                collections = [col for col in collection.children if not col.all_objects]
        else:
            collections = collection.children_recursive if recursive else collection.children

        for col in reversed(collections):
            bpy.data.collections.remove(col)

        bpy.data.collections.remove(collection)

    @staticmethod
    def remove_collections(empty_only: bool = True):
        """
        Remove collections.

        empty_only (bool) - Remove only empty collections.
        """
        collections = [col for col in bpy.data.collections if (not empty_only) or (empty_only and not len(col.all_objects))]

        for col in reversed(collections):
            bpy.data.collections.remove(col)

    @staticmethod
    def append_collection(filepath: str, collection: str, parent_collection: bpy.types.Collection = None) -> bpy.types.Collection:
        """
        Append a collection from the filepath.

        collection (str) - Name of the collection.
        parent_collection (bpy.types.Collection) - Collection to parent the appended collection.
        return (bpy.types.Collection) - The appended collection.
        """
        with bpy.data.libraries.load(filepath) as (data_from, data_to):
            if collection not in data_from.collections:
                raise ValueError(f"Collection '{collection}' not found in the source blend file.")

            data_to.collections = [collection]

        # Link the appended collections to the specified or current collection
        target_collection = parent_collection or bpy.context.scene.collection

        for col in data_to.collections:
            target_collection.children.link(col)

        return data_to.collections[0]

    @staticmethod
    def append_collections(
        filepath: str,
        collections: List[str],
        parent_collection: bpy.types.Collection = None,
    ) -> List[bpy.types.Collection]:
        """
        Append collections from the filepath.

        collections (List[str]) - List of collection names.
        parent_collection (bpy.types.Collection) - Collection to parent the appended collections.
        return (List[bpy.types.Collection]) - The appended collections.
        """
        # Load collections from the file and filter by names
        with bpy.data.libraries.load(filepath) as (data_from, data_to):
            if not data_from.collections:
                raise ValueError("No matching collections found in the source blend file.")

            data_to.collections = [name for name in data_from.collections if name in collections]

        # Link the appended collections to the specified or current collection
        target_collection = parent_collection or bpy.context.scene.collection

        for col in data_to.collections:
            target_collection.children.link(col)

        return data_to.collections

    @staticmethod
    def find_layer_collection(
        layer_collection: bpy.types.LayerCollection,
        collection: Union[bpy.types.Collection, str],
    ) -> bpy.types.LayerCollection:
        """
        Find layer collection.

        layer_collection (bpy.types.LayerCollection) - Layer collection to find child layer collection.
        collection (Union[bpy.types.Collection, str]) - Collection or name of the collection.
        """
        collection_name = collection.name if isinstance(collection, bpy.types.Collection) else collection

        if layer_collection.name == collection_name:
            return layer_collection

        for child_layer_collection in layer_collection.children:
            if result := Collection.find_layer_collection(child_layer_collection, collection_name):
                return result

    @staticmethod
    def get_layer_collection(
        collection: Union[bpy.types.Collection, str],
        children: bool = False,
        recursive: bool = False,
    ) -> Union[bpy.types.LayerCollection, List[bpy.types.LayerCollection], None]:
        """
        Get layer collection or List of layer collections.

        collection (Union[bpy.types.Collection, str]) - Collection or name of the collection.
        children (bool) - Get layer collection children.
        recursive (bool) - Get layer collection children recursively.
        return (Union[bpy.types.LayerCollection, List[bpy.types.LayerCollection]]) - Get layer collection or List of layer collections.
        """
        if isinstance(collection, str):
            collection = bpy.data.collections.get(collection)
            if not collection:
                return None

        if children:
            return Collection.get_layer_collections([collection] + list(collection.children))
        elif recursive:
            return Collection.get_layer_collections([collection] + list(collection.children_recursive))
        else:
            return Collection.find_layer_collection(bpy.context.view_layer.layer_collection, collection)

    @staticmethod
    def get_layer_collections(collections: List[Union[bpy.types.Collection, str]]) -> List[bpy.types.LayerCollection]:
        """
        Get layer collections.

        collections (List[Union[bpy.types.Collection, str]]) - List of collections or name of collections.
        return (List[bpy.types.LayerCollection]) - List of layer collections.
        """
        layer_collections = []

        for collection in collections:
            if layer_collection := Collection.find_layer_collection(bpy.context.view_layer.layer_collection, collection):
                layer_collections.append(layer_collection)

        return layer_collections
